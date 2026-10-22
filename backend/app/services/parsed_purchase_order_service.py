"""Business logic for parsed purchase order review."""
from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy.orm import Session

from app.exceptions.base import NotFoundException, ValidationException
from app.policies import PolicyActor, policy_engine, system_actor
from app.repositories import parsed_purchase_order_repository
from app.schemas.parsed_purchase_order import (
    ParsedPurchaseOrderCorrectionResponse,
    ParsedPurchaseOrderCorrectionsRequest,
    ParsedPurchaseOrderCreateRequest,
    ParsedPurchaseOrderImportRequest,
    ParsedPurchaseOrderImportResult,
    ParsedPurchaseOrderResponse,
    ParsedPurchaseOrderValidationResult,
)

_PATH_TOKEN_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?")
_REQUIRED_HEADER_FIELDS = ("po_number", "version", "lines")
_REQUIRED_LINE_FIELDS = ("line_no", "part_number", "quantity", "unit_price", "total", "due_date")
_PO_NUMBER_RE = re.compile(
    r"\b(?:purchase\s+order|P\.O\.|PO)\s*(?:number|no\.?|#)?\s*:?\s*((?:[A-Z]{1,3}-?)?\d{4,10})\b",
    re.I,
)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4})\b")
_MONEY_RE = re.compile(r"[-+]?\d+(?:[.,]\d{1,4})?")
_LINE_RE = re.compile(
    r"^\s*(?P<line_no>\d{1,4})\s+"
    r"(?P<part_number>[A-Z0-9][A-Z0-9._/-]{3,})\s+"
    r"(?P<description>.*?)\s+"
    r"(?P<quantity>\d+(?:[.,]\d+)?)\s+"
    r"(?P<unit_price>\d+(?:[.,]\d+)?)\s+"
    r"(?P<total>\d+(?:[.,]\d+)?)"
    r"(?:\s+(?P<due_date>\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4}))?\s*$",
    re.I,
)
_ADIENT_HEADER_RE = re.compile(r"\bNO\s*:\s*(\d{4,12})\s+Version\s*:\s*(\d+)\b", re.I)
_MONTH_DATE_PATTERN = r"[A-Za-z]{3}\s+\d{1,2},\s+\d{4}"
_ADIENT_LINE_RE = re.compile(
    r"^(?P<line_no>\d{5})\s+(?P<plant>\d+)\s+"
    r"(?:(?P<invoice_not_required>X|Yes|No)\s+)?"
    rf"(?P<due_date>{_MONTH_DATE_PATTERN})\s+"
    r"(?P<material_group>\d+)\s+(?P<quantity>\d[\d.,]*)\s+"
    r"(?P<uom>[A-Z]+)\s+(?P<unit_price>\d[\d.,]*)\s+(?P<total>\d[\d.,]*)$",
    re.I,
)
_ADIENT_PART_RE = re.compile(r"^(?P<part_number>\d{6,8}-[A-Z0-9]{4}-[A-Z0-9]{2,3})\s+(?P<description>.+)$", re.I)


def create_parsed_purchase_order(
    db: Session,
    request: ParsedPurchaseOrderCreateRequest,
    user_id: str | uuid.UUID,
    actor: PolicyActor | None = None,
) -> ParsedPurchaseOrderResponse:
    policy_engine.require(actor or system_actor(), "po.parse")

    user_uuid = _normalize_user_id(user_id)
    _validate_payload_is_po_like(request.parsed_payload)

    parsed_po = parsed_purchase_order_repository.create_parsed_purchase_order(
        db,
        document_id=request.document_id,
        source_file_name=request.source_file_name,
        parser_name=request.parser_name,
        parser_version=request.parser_version,
        parsed_payload=request.parsed_payload,
        created_by=user_uuid,
    )
    db.commit()
    db.refresh(parsed_po)
    return _to_response(parsed_po)


def parse_purchase_order_bytes(
    db: Session,
    *,
    source_file_name: str | None,
    content: bytes,
    user_id: str | uuid.UUID,
    actor: PolicyActor | None = None,
) -> ParsedPurchaseOrderResponse:
    """Parse text-layer Adient PDFs or simple tabular text into a review draft."""
    policy_engine.require(actor or system_actor(), "po.parse")
    payload = _parse_simple_purchase_order_payload(content)
    return create_parsed_purchase_order(
        db,
        ParsedPurchaseOrderCreateRequest(
            source_file_name=source_file_name,
            parser_name="adient-po-parser" if payload.get("source_format") == "ADIENT_PO" else "simple-regex-po-parser",
            parser_version="2026-10-22",
            parsed_payload=payload,
        ),
        user_id,
        actor=actor,
    )


def get_parsed_purchase_order(db: Session, parsed_po_id: int) -> ParsedPurchaseOrderResponse:
    parsed_po = _get_required_parsed_po(db, parsed_po_id)
    return _to_response(parsed_po)


def save_parsed_purchase_order_corrections(
    db: Session,
    parsed_po_id: int,
    request: ParsedPurchaseOrderCorrectionsRequest,
    user_id: str | uuid.UUID,
    actor: PolicyActor | None = None,
) -> ParsedPurchaseOrderResponse:
    policy_engine.require(actor or system_actor(), "po.update")

    parsed_po = _get_required_parsed_po(db, parsed_po_id)
    user_uuid = _normalize_user_id(user_id)
    effective_payload = _effective_payload(parsed_po.parsed_payload, parsed_po.corrections)

    correction_dicts = []
    for correction in request.corrections:
        original_value = correction.original_value
        if original_value is None:
            original_value = _read_path(effective_payload, correction.field_path)
        correction_dicts.append(
            {
                "field_path": correction.field_path,
                "original_value": original_value,
                "corrected_value": correction.corrected_value,
                "confirmed": correction.confirmed,
            }
        )

    parsed_purchase_order_repository.upsert_corrections(
        db,
        parsed_po=parsed_po,
        corrections=correction_dicts,
        corrected_by=user_uuid,
    )
    for correction in correction_dicts:
        if correction["confirmed"]:
            _write_path(effective_payload, correction["field_path"], correction["corrected_value"])

    errors, _warnings = _validate_effective_payload(effective_payload)
    parsed_purchase_order_repository.mark_validation_status(
        db,
        parsed_po=parsed_po,
        status="CORRECTED" if errors else "VALIDATED",
    )
    db.commit()
    parsed_po = _get_required_parsed_po(db, parsed_po_id)
    return _to_response(parsed_po)


def validate_parsed_purchase_order(
    db: Session,
    parsed_po_id: int,
    actor: PolicyActor | None = None,
) -> ParsedPurchaseOrderValidationResult:
    policy_engine.require(actor or system_actor(), "po.update")

    parsed_po = _get_required_parsed_po(db, parsed_po_id)
    payload = _effective_payload(parsed_po.parsed_payload, parsed_po.corrections)
    errors, warnings = _validate_effective_payload(payload)
    status = "VALIDATED" if not errors else "CORRECTED" if parsed_po.corrections else "PARSED"

    parsed_purchase_order_repository.mark_validation_status(
        db,
        parsed_po=parsed_po,
        status=status,
    )
    db.commit()

    return ParsedPurchaseOrderValidationResult(
        parsed_po_id=parsed_po_id,
        status=status,
        is_valid=not errors,
        errors=errors,
        warnings=warnings,
        effective_payload=payload,
    )


def import_parsed_purchase_order(
    db: Session,
    parsed_po_id: int,
    request: ParsedPurchaseOrderImportRequest,
    user_id: str | uuid.UUID,
    actor: PolicyActor | None = None,
) -> ParsedPurchaseOrderImportResult:
    policy_engine.require(actor or system_actor(), "po.import")

    parsed_po = _get_required_parsed_po(db, parsed_po_id)
    payload = _effective_payload(parsed_po.parsed_payload, parsed_po.corrections)
    errors, _warnings = _validate_effective_payload(payload)
    if errors:
        raise ValidationException(
            "Parsed PO must be valid before import.",
            details={"errors": errors},
        )

    import_result = parsed_purchase_order_repository.import_effective_purchase_order(
        db,
        parsed_po=parsed_po,
        effective_payload=payload,
        project_id=request.project_id,
        customer_id=request.customer_id,
        contact_id=request.contact_id,
        delivery_method_id=request.delivery_method_id,
        document_id=request.document_id,
        change_reason=request.change_reason,
        imported_by=_normalize_user_id(user_id),
    )
    db.commit()

    return ParsedPurchaseOrderImportResult(
        parsed_po_id=parsed_po_id,
        status="IMPORTED",
        **import_result,
    )


def _get_required_parsed_po(db: Session, parsed_po_id: int):
    parsed_po = parsed_purchase_order_repository.get_parsed_purchase_order(db, parsed_po_id)
    if parsed_po is None:
        raise NotFoundException(f"Parsed purchase order {parsed_po_id} not found.")
    return parsed_po


def _to_response(parsed_po) -> ParsedPurchaseOrderResponse:
    corrections = sorted(parsed_po.corrections, key=lambda correction: correction.field_path)
    return ParsedPurchaseOrderResponse(
        parsed_po_id=parsed_po.parsed_po_id,
        document_id=parsed_po.document_id,
        source_file_name=parsed_po.source_file_name,
        parser_name=parsed_po.parser_name,
        parser_version=parsed_po.parser_version,
        status=parsed_po.status,
        parsed_payload=parsed_po.parsed_payload,
        effective_payload=_effective_payload(parsed_po.parsed_payload, corrections),
        validated_po_id=parsed_po.validated_po_id,
        created_at=parsed_po.created_at,
        created_by=parsed_po.created_by,
        updated_at=parsed_po.updated_at,
        corrections=[
            ParsedPurchaseOrderCorrectionResponse.model_validate(correction)
            for correction in corrections
        ],
    )


def _effective_payload(parsed_payload: dict[str, Any], corrections) -> dict[str, Any]:
    payload = copy.deepcopy(parsed_payload)
    for correction in sorted(corrections, key=lambda item: item.field_path):
        if correction.confirmed:
            _write_path(payload, correction.field_path, correction.corrected_value)
    return payload


def _validate_payload_is_po_like(payload: dict[str, Any]) -> None:
    missing = [field for field in _REQUIRED_HEADER_FIELDS if field not in payload]
    if missing:
        raise ValidationException(
            "Parsed PO payload is missing required fields.",
            details={"missing_fields": missing},
        )
    if not isinstance(payload.get("lines"), list):
        raise ValidationException("Parsed PO payload field 'lines' must be a list.")


def _parse_simple_purchase_order_payload(content: bytes) -> dict[str, Any]:
    text = _decode_document_text(content)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact = "\n".join(lines)

    if _ADIENT_HEADER_RE.search(compact):
        return _parse_adient_purchase_order_payload(lines, compact)

    po_match = _PO_NUMBER_RE.search(compact)
    all_dates = [_normalize_date(match.group(1)) for match in _DATE_RE.finditer(compact)]
    parsed_lines = []
    computed_total = Decimal("0")

    for line in lines:
        match = _LINE_RE.match(line)
        if match is None:
            continue
        item = match.groupdict()
        quantity = _normalize_number(item["quantity"])
        unit_price = _normalize_number(item["unit_price"])
        total = _normalize_number(item["total"])
        computed_total += Decimal(total)
        parsed_lines.append(
            {
                "line_no": item["line_no"],
                "part_number": item["part_number"],
                "description": item["description"].strip(),
                "quantity": quantity,
                "unit_price": unit_price,
                "total": total,
                "due_date": _normalize_date(item["due_date"]) if item.get("due_date") else (all_dates[-1] if all_dates else ""),
            }
        )

    stated_total = _extract_stated_total(compact)
    return {
        "po_number": po_match.group(1).upper() if po_match else "",
        "version": 1,
        "document_date": all_dates[0] if all_dates else "",
        "delivery_date": all_dates[-1] if all_dates else "",
        "line_count": len(parsed_lines),
        "lines": parsed_lines,
        "computed_total": str(computed_total.quantize(Decimal("0.01"))) if parsed_lines else "0.00",
        "stated_total": stated_total,
        "raw_text_preview": compact[:2000],
    }


def _parse_adient_purchase_order_payload(lines: list[str], text: str) -> dict[str, Any]:
    """Associate each item table row with its following part block, across pages.

    The six-digit material-group column is not the FGPN. The FGPN is printed
    below the row and can move to the following page together with its customer
    references. Keep missing/unrecognized fields visible for review.
    """
    headers = _ADIENT_HEADER_RE.findall(text)
    po_number, version = headers[0]
    errors: list[str] = []
    if len(set(headers)) != 1:
        errors.append("The PDF contains conflicting purchase-order numbers or versions.")

    parsed_lines: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in lines:
        line = re.sub(r"\s+", " ", raw_line).strip()
        row = _ADIENT_LINE_RE.fullmatch(line)
        if row:
            values = row.groupdict()
            current = {
                "line_no": values["line_no"],
                "plant": values["plant"],
                "material_group": values["material_group"],
                "invoice_not_required": values["invoice_not_required"],
                "part_number": "",
                "description": "",
                "quantity": _normalize_number(values["quantity"]),
                "uom": values["uom"].upper(),
                "unit_price": _normalize_number(values["unit_price"]),
                "total": _normalize_number(values["total"]),
                "due_date": _normalize_date(values["due_date"]),
                "customer_part_ref": "",
                "customer_references": [],
            }
            parsed_lines.append(current)
            continue
        if re.match(r"^\d{5}\s+\d+\s", line):
            errors.append(f"Could not read item row {line.split()[0]}; review the source PDF.")
            current = None
            continue
        part = _ADIENT_PART_RE.fullmatch(line)
        if part and current is not None:
            if current["part_number"]:
                errors.append(f"Item {current['line_no']} has more than one part-number block.")
            else:
                current.update(part.groupdict())
            continue
        if current is not None and current["part_number"] and "||" in line:
            references = line.split("||", 1)[1].removesuffix("-HC:")
            current["customer_references"] = [value.strip() for value in references.split("|") if value.strip()]
            current["customer_part_ref"] = "|".join(current["customer_references"])

    def header_date(label: str) -> str:
        match = re.search(rf"{label}\s*:\s*({_MONTH_DATE_PATTERN})", text, re.I)
        return _normalize_date(match.group(1)) if match else ""

    def total_field(label: str) -> tuple[str | None, str | None]:
        match = re.search(rf"{label}\s+([A-Z]{{3}})(?:[ \t]+([\d.,]+))?", text)
        return (match.group(1), _normalize_number(match.group(2)) if match.group(2) else None) if match else (None, None)

    currency, stated_total = total_field("Line Total")
    _, tax_total = total_field("Tax Total")
    _, currency_total = total_field("Currency Total")
    computed_total = sum((Decimal(item["total"]) for item in parsed_lines), Decimal("0"))
    supplier_number = re.search(r"Supplier No\s*:\s*(\d+)", text)
    replacement = re.search(r"This PO will replace\s+(\d+)", text, re.I)
    due_dates = sorted({item["due_date"] for item in parsed_lines})
    return {
        "source_format": "ADIENT_PO",
        "contact_email": "",
        "po_number": po_number,
        "version": int(version),
        "order_date": header_date("Order Date"),
        "document_date": header_date("Order Date"),
        "change_date": header_date("Change Date"),
        "delivery_date": due_dates[-1] if due_dates else "",
        "supplier_number": supplier_number.group(1) if supplier_number else None,
        "replaced_po_number": replacement.group(1) if replacement else None,
        "currency": currency,
        "line_count": len(parsed_lines),
        "lines": parsed_lines,
        "computed_total": str(computed_total.quantize(Decimal("0.01"))),
        "stated_total": stated_total,
        "tax_total": tax_total,
        "currency_total": currency_total,
        "totals_match": stated_total is not None and computed_total == Decimal(stated_total),
        "extraction_errors": errors,
        "raw_text_preview": text[:2000],
    }


def _decode_document_text(content: bytes) -> str:
    if content.lstrip().startswith(b"%PDF"):
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted and reader.decrypt("") == 0:
                raise ValidationException("Password-protected PDFs must be unlocked before upload.")
            pdf_text = "\n".join(
                page.extract_text(extraction_mode="layout", layout_mode_space_vertically=False) or ""
                for page in reader.pages
            )
        except (PdfReadError, ValueError, KeyError) as exc:
            raise ValidationException("Could not read the purchase-order PDF.") from exc
        if not pdf_text.strip():
            raise ValidationException("The PDF has no readable text layer. Apply OCR before upload.")
        return pdf_text

    for encoding in ("utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1", errors="ignore")


def _normalize_number(value: str) -> str:
    # Adient uses a decimal comma and a period for thousands (1.160,64000).
    value = value.replace("\u00a0", "").replace(" ", "")
    if "," in value:
        return value.replace(".", "").replace(",", ".")
    return value


def _normalize_date(value: str) -> str:
    if not value:
        return ""
    value = value.replace("/", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return value


def _extract_stated_total(text: str) -> str | None:
    for line in reversed(text.splitlines()):
        if "total" not in line.lower():
            continue
        matches = _MONEY_RE.findall(line)
        if matches:
            return _normalize_number(matches[-1])
    return None


def _validate_effective_payload(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = [str(error) for error in payload.get("extraction_errors", [])]
    warnings: list[str] = []

    for field in _REQUIRED_HEADER_FIELDS:
        if payload.get(field) in (None, ""):
            errors.append(f"Missing required header field: {field}.")

    lines = payload.get("lines")
    if not isinstance(lines, list) or not lines:
        errors.append("PO must contain at least one line.")
        return errors, warnings

    expected_line_count = payload.get("line_count")
    if expected_line_count is not None and _decimal_or_none(expected_line_count) != Decimal(len(lines)):
        warnings.append("line_count does not match the number of parsed lines.")

    distinct_part_numbers: set[str] = set()
    line_numbers: set[Decimal] = set()
    computed_total = Decimal("0")

    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            errors.append(f"Line {index + 1} must be an object.")
            continue

        for field in _REQUIRED_LINE_FIELDS:
            if line.get(field) in (None, ""):
                errors.append(f"Line {index + 1} is missing required field: {field}.")

        part_number = line.get("part_number")
        if part_number:
            distinct_part_numbers.add(str(part_number))

        quantity = _decimal_or_none(line.get("quantity"))
        unit_price = _decimal_or_none(line.get("unit_price"))
        total = _decimal_or_none(line.get("total"))

        line_no = _decimal_or_none(line.get("line_no"))
        if line_no is None or line_no <= 0 or line_no != line_no.to_integral_value():
            errors.append(f"Line {index + 1} has invalid line_no.")
        elif line_no in line_numbers:
            errors.append(f"Line {index + 1} repeats line_no {line.get('line_no')}.")
        else:
            line_numbers.add(line_no)
        try:
            datetime.strptime(str(line.get("due_date")), "%Y-%m-%d")
        except ValueError:
            errors.append(f"Line {index + 1} has invalid due_date.")

        if quantity is None or quantity <= 0:
            errors.append(f"Line {index + 1} has invalid quantity.")
        if unit_price is None or unit_price < 0:
            errors.append(f"Line {index + 1} has invalid unit_price.")
        if total is None or total < 0:
            errors.append(f"Line {index + 1} has invalid total.")
        if quantity is not None and unit_price is not None and total is not None:
            expected_total = (quantity * unit_price).quantize(Decimal("0.01"))
            if abs(expected_total - total.quantize(Decimal("0.01"))) > Decimal("0.01"):
                warnings.append(f"Line {index + 1} total does not match quantity * unit_price.")
            computed_total += total

    parsed_computed_total = _decimal_or_none(payload.get("computed_total"))
    stated_total = _decimal_or_none(payload.get("stated_total"))
    if parsed_computed_total is not None and abs(computed_total - parsed_computed_total) > Decimal("0.01"):
        warnings.append("computed_total does not match the sum of line totals.")
    if stated_total is not None and abs(computed_total - stated_total) > Decimal("0.01"):
        warnings.append("stated_total does not match the sum of line totals.")

    if distinct_part_numbers:
        warnings.append(
            f"{len(distinct_part_numbers)} distinct PO part number(s) still need FGPN mapping before import."
        )

    return errors, warnings


def _read_path(payload: dict[str, Any], field_path: str) -> Any:
    current: Any = payload
    for key, index in _parse_path(field_path):
        if not isinstance(current, dict) or key not in current:
            raise ValidationException(f"Field path '{field_path}' does not exist.")
        current = current[key]
        if index is not None:
            if not isinstance(current, list) or index >= len(current):
                raise ValidationException(f"Field path '{field_path}' does not exist.")
            current = current[index]
    return current


def _write_path(payload: dict[str, Any], field_path: str, value: Any) -> None:
    tokens = _parse_path(field_path)
    current: Any = payload
    for key, index in tokens[:-1]:
        if not isinstance(current, dict) or key not in current:
            raise ValidationException(f"Field path '{field_path}' does not exist.")
        current = current[key]
        if index is not None:
            if not isinstance(current, list) or index >= len(current):
                raise ValidationException(f"Field path '{field_path}' does not exist.")
            current = current[index]

    key, index = tokens[-1]
    if not isinstance(current, dict) or key not in current:
        raise ValidationException(f"Field path '{field_path}' does not exist.")
    if index is None:
        current[key] = value
        return

    target = current[key]
    if not isinstance(target, list) or index >= len(target):
        raise ValidationException(f"Field path '{field_path}' does not exist.")
    target[index] = value


def _parse_path(field_path: str) -> list[tuple[str, int | None]]:
    tokens: list[tuple[str, int | None]] = []
    for part in field_path.split("."):
        match = _PATH_TOKEN_RE.fullmatch(part)
        if match is None:
            raise ValidationException(f"Invalid correction field path: {field_path}.")
        key, index = match.groups()
        tokens.append((key, int(index) if index is not None else None))
    if not tokens:
        raise ValidationException("Correction field path cannot be empty.")
    return tokens


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _normalize_user_id(user_id: str | uuid.UUID) -> uuid.UUID:
    return uuid.UUID(user_id) if isinstance(user_id, str) else user_id
