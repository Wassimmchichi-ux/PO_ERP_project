"""Repository functions for parsed purchase order staging."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exceptions.base import ConflictException, ValidationException
from app.models.audit_log import AuditLog
from app.models.contact import Contact
from app.models.customer import Customer
from app.models.delivery_method import DeliveryMethod
from app.models.document import Document
from app.models.fgpn import FGPN
from app.models.fgpn_price_history import FGPNPriceHistory
from app.models.parsed_purchase_order import ParsedPurchaseOrder
from app.models.parsed_purchase_order_correction import ParsedPurchaseOrderCorrection
from app.models.project import Project
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_line import PurchaseOrderLine
from app.models.purchase_order_version import PurchaseOrderVersion


def create_parsed_purchase_order(
    db: Session,
    *,
    parsed_payload: dict[str, Any],
    created_by: uuid.UUID,
    document_id: int | None = None,
    source_file_name: str | None = None,
    source_content: bytes | None = None,
    source_content_type: str | None = None,
    parser_name: str | None = None,
    parser_version: str | None = None,
) -> ParsedPurchaseOrder:
    now = datetime.now()
    parsed_po = ParsedPurchaseOrder(
        document_id=document_id,
        source_file_name=source_file_name,
        source_content=source_content,
        source_content_type=source_content_type,
        parser_name=parser_name,
        parser_version=parser_version,
        status="PARSED",
        parsed_payload=parsed_payload,
        created_at=now,
        created_by=created_by,
        updated_at=now,
    )
    db.add(parsed_po)
    db.flush()
    return parsed_po


def get_parsed_purchase_order(db: Session, parsed_po_id: int) -> ParsedPurchaseOrder | None:
    stmt = (
        select(ParsedPurchaseOrder)
        .options(selectinload(ParsedPurchaseOrder.corrections))
        .execution_options(populate_existing=True)
        .where(ParsedPurchaseOrder.parsed_po_id == parsed_po_id)
    )
    return db.execute(stmt).scalar_one_or_none()


def upsert_corrections(
    db: Session,
    *,
    parsed_po: ParsedPurchaseOrder,
    corrections: list[dict[str, Any]],
    corrected_by: uuid.UUID,
) -> list[ParsedPurchaseOrderCorrection]:
    existing = {correction.field_path: correction for correction in parsed_po.corrections}
    now = datetime.now()
    saved: list[ParsedPurchaseOrderCorrection] = []

    for correction_data in corrections:
        field_path = correction_data["field_path"]
        correction = existing.get(field_path)
        if correction is None:
            correction = ParsedPurchaseOrderCorrection(
                parsed_po_id=parsed_po.parsed_po_id,
                field_path=field_path,
                original_value=correction_data.get("original_value"),
                corrected_value=correction_data.get("corrected_value"),
                confirmed=correction_data.get("confirmed", True),
                corrected_by=corrected_by,
                corrected_at=now,
            )
            db.add(correction)
        else:
            correction.original_value = correction_data.get("original_value")
            correction.corrected_value = correction_data.get("corrected_value")
            correction.confirmed = correction_data.get("confirmed", True)
            correction.corrected_by = corrected_by
            correction.corrected_at = now
        saved.append(correction)

    if corrections:
        parsed_po.status = "CORRECTED"
        parsed_po.updated_at = now

    db.flush()
    return saved


def mark_validation_status(
    db: Session,
    *,
    parsed_po: ParsedPurchaseOrder,
    status: str,
) -> ParsedPurchaseOrder:
    parsed_po.status = status
    parsed_po.updated_at = datetime.now()
    db.flush()
    return parsed_po


def import_effective_purchase_order(
    db: Session,
    *,
    parsed_po: ParsedPurchaseOrder,
    effective_payload: dict[str, Any],
    project_id: int,
    customer_id: int,
    contact_id: int,
    delivery_method_id: int,
    document_id: int | None,
    change_reason: str | None,
    imported_by: uuid.UUID,
) -> dict[str, Any]:
    _validate_import_context(
        db,
        project_id=project_id,
        customer_id=customer_id,
        contact_id=contact_id,
        delivery_method_id=delivery_method_id,
        document_id=document_id or parsed_po.document_id,
    )

    now = datetime.now()
    po_number = str(effective_payload["po_number"]).strip()
    version_number = int(_decimal_required(effective_payload.get("version"), "version"))
    po = db.execute(
        select(PurchaseOrder).where(PurchaseOrder.po_number == po_number)
    ).scalar_one_or_none()
    created_po = False

    if po is None:
        po = PurchaseOrder(
            po_number=po_number,
            customer_id=customer_id,
            contact_id=contact_id,
            current_version_id=None,
            current_status="Unplanned",
            created_at=now,
            updated_at=now,
        )
        db.add(po)
        db.flush()
        created_po = True
    else:
        po.customer_id = customer_id
        po.contact_id = contact_id
        po.updated_at = now

    existing_version = db.execute(
        select(PurchaseOrderVersion)
        .where(PurchaseOrderVersion.po_id == po.po_id)
        .where(PurchaseOrderVersion.version_number == version_number)
    ).scalar_one_or_none()
    if existing_version is not None:
        raise ConflictException(
            f"PO {po_number} version {version_number} already exists.",
            details={
                "po_id": po.po_id,
                "po_version_id": existing_version.po_version_id,
            },
        )

    po_document_id = document_id or parsed_po.document_id
    if po_document_id is None:
        document = Document(
            document_type="PO",
            file_name=parsed_po.source_file_name or f"{po_number}.json",
            file_path=(
                f"/purchase-orders/parsed/{parsed_po.parsed_po_id}/source"
                if parsed_po.source_content is not None
                else f"/uploads/{parsed_po.source_file_name or f'{po_number}.json'}"
            ),
            version=version_number,
            uploaded_at=now,
            uploaded_by=imported_by,
        )
        db.add(document)
        db.flush()
        po_document_id = document.document_id

    po_version = PurchaseOrderVersion(
        po_id=po.po_id,
        version_number=version_number,
        document_id=po_document_id,
        document_date=_date_or_none(effective_payload.get("order_date") or effective_payload.get("document_date")),
        created_at=now,
        created_by=imported_by,
        change_reason=change_reason,
    )
    db.add(po_version)
    db.flush()

    created_fgpn_ids: list[int] = []
    updated_fgpn_price_history_ids: list[int] = []

    for line in effective_payload["lines"]:
        part_number = str(line["part_number"]).strip()
        unit_price = _decimal_required(line.get("unit_price"), f"{part_number}.unit_price")
        fgpn = db.execute(
            select(FGPN)
            .where(FGPN.project_id == project_id)
            .where(FGPN.fgpn_code == part_number)
        ).scalar_one_or_none()

        if fgpn is None:
            fgpn = FGPN(
                project_id=project_id,
                fgpn_code=part_number,
                description=line.get("description"),
                trim_style=line.get("customer_part_ref"),
                unit_price=unit_price,
                status="Active",
                created_at=now,
                updated_at=now,
            )
            db.add(fgpn)
            db.flush()
            created_fgpn_ids.append(fgpn.fgpn_id)
        elif fgpn.unit_price != unit_price:
            audit = AuditLog(
                user_id=imported_by,
                action="UPDATE_PRICE",
                entity_type="FGPN",
                entity_id=fgpn.fgpn_id,
                timestamp=now,
                reason="PO import detected unit price change",
                details=f"PO {po_number} version {version_number}",
            )
            db.add(audit)
            db.flush()
            price_history = FGPNPriceHistory(
                fgpn_id=fgpn.fgpn_id,
                old_price=fgpn.unit_price,
                new_price=unit_price,
                effective_date=now,
                changed_by=imported_by,
                audit_id=audit.audit_id,
            )
            db.add(price_history)
            db.flush()
            updated_fgpn_price_history_ids.append(price_history.price_history_id)
            fgpn.unit_price = unit_price
            fgpn.updated_at = now

        po_line = PurchaseOrderLine(
            po_version_id=po_version.po_version_id,
            line_number=_line_number(line.get("line_no")),
            item_number=str(line.get("line_no")) if line.get("line_no") is not None else None,
            fgpn_id=fgpn.fgpn_id,
            description=line.get("description"),
            ordered_quantity=_decimal_required(line.get("quantity"), f"{part_number}.quantity"),
            unit_price=unit_price,
            delivery_date=_date_or_none(line.get("due_date")),
            delivery_method_id=delivery_method_id,
            created_at=now,
        )
        db.add(po_line)

    db.flush()
    po.current_version_id = po_version.po_version_id
    po.updated_at = now
    parsed_po.status = "IMPORTED"
    parsed_po.validated_po_id = po.po_id
    parsed_po.updated_at = now
    db.flush()

    return {
        "po_id": po.po_id,
        "po_version_id": po_version.po_version_id,
        "created_po": created_po,
        "line_count": len(effective_payload["lines"]),
        "created_fgpn_ids": created_fgpn_ids,
        "updated_fgpn_price_history_ids": updated_fgpn_price_history_ids,
    }


def _validate_import_context(
    db: Session,
    *,
    project_id: int,
    customer_id: int,
    contact_id: int,
    delivery_method_id: int,
    document_id: int | None,
) -> None:
    if db.get(Project, project_id) is None:
        raise ValidationException(f"Project {project_id} not found.")
    if db.get(Customer, customer_id) is None:
        raise ValidationException(f"Customer {customer_id} not found.")
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise ValidationException(f"Contact {contact_id} not found.")
    if contact.customer_id != customer_id:
        raise ValidationException(f"Contact {contact_id} does not belong to customer {customer_id}.")
    if db.get(DeliveryMethod, delivery_method_id) is None:
        raise ValidationException(f"Delivery method {delivery_method_id} not found.")
    if document_id is not None and db.get(Document, document_id) is None:
        raise ValidationException(f"Document {document_id} not found.")


def _decimal_required(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationException(f"Invalid decimal value for {field_name}.") from exc


def _date_or_none(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationException(f"Invalid date value: {value}.") from exc


def _line_number(value: Any) -> int:
    if value in (None, ""):
        raise ValidationException("PO line is missing line_no.")
    return int(str(value))
