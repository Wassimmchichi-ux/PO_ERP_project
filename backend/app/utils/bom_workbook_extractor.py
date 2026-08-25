"""Extract BOM snapshots from uploaded XLSX workbooks.

This module is a **pure parsing utility**.  It has exactly one external
dependency (``app.exceptions.base``) and zero knowledge of:

* FastAPI or HTTP (no ``UploadFile``, no ``HTTPException``)
* SQLAlchemy or any database
* The version numbering scheme

Its only contract: given raw workbook bytes and an optional source filename
it returns a structured :class:`ParsedBom` that the calling service layer can
inspect, version, and persist.

The Finished-Good Part Number (FGPN) is **read from the workbook itself** —
specifically the ``COVER PN (TPDM)`` column in the ``Source DATA`` sheet.
The parser asserts that all data rows carry a consistent single FGPN and
raises :class:`~app.exceptions.base.ValidationException` if more than one
distinct value is found.
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import PurePosixPath
from typing import Optional

from app.exceptions.base import ValidationException


# ---------------------------------------------------------------------------
# XML namespace maps
# ---------------------------------------------------------------------------

_WORKBOOK_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}

# ---------------------------------------------------------------------------
# Workbook layout constants
# ---------------------------------------------------------------------------

_SOURCE_SHEET_NAME = "Source DATA"

#: Maps semantic field names to their exact column header text in the sheet.
_HEADER_ALIASES: dict[str, str] = {
    "finished_good_part_number": "COVER PN (TPDM)",
    "finished_good_description": "Cover description",
    "material_part_number": "Material PN",
    "material_description": "MATERIAL DESCRIPTION (primarly TPDM)",
    "cover_revision": "Cover revision",
    "part_type": "Part type",
    "coefficient": "Coefficient",
    "quantity_tpdm": "QUANTITY TPDM",
    "total_quantity": "total qty",
    "unit": "UNIT",
    "total_sqm": "Total sqm",
}

#: A header row is only accepted when it contains **all** of these fields.
_REQUIRED_HEADERS: frozenset[str] = frozenset(
    {
        "finished_good_part_number",
        "material_part_number",
        "coefficient",
        "quantity_tpdm",
        "unit",
    }
)


# ---------------------------------------------------------------------------
# Public result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedBomLine:
    """One material requirement row extracted from the workbook.

    All numeric fields are stored as :class:`~decimal.Decimal` to avoid
    floating-point rounding surprises when the service layer passes them
    into the database (``NUMERIC`` columns).
    """

    source_row_number: int
    material_part_number: str
    material_description: Optional[str]
    cover_revision: Optional[str]
    cover_pn: Optional[str]
    quantity_tpdm: Optional[Decimal]
    cover_description: Optional[str]
    part_type: Optional[str]
    coefficient: Decimal
    total_quantity: Optional[Decimal]
    unit: Optional[str]
    total_sqm: Optional[Decimal]
    raw_row: dict[str, str]


@dataclass(frozen=True)
class ParsedBom:
    """The complete structured result of parsing one BOM workbook.

    The parser is responsible for discovering ``finished_good_part_number``
    from the workbook.  ``version`` is intentionally absent: version
    computation requires a database lookup and belongs in the service layer.
    """

    finished_good_part_number: str
    finished_good_description: Optional[str] # is the cover description it still the same for each PN
    source_filename: str
    source_reported_by: Optional[str]
    source_report_date: Optional[date]
    source_report_time: Optional[time]
    lines: list[ParsedBomLine]

    @property
    def material_row_count(self) -> int:
        """Total number of material lines parsed from the workbook."""
        return len(self.lines)

    @property
    def unique_material_count(self) -> int:
        """Number of distinct material part numbers in this BOM."""
        return len({line.material_part_number for line in self.lines})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_bom_workbook(
    workbook_bytes: bytes,
    *,
    source_filename: str,
) -> ParsedBom:
    """Parse a BOM XLSX workbook and return a structured :class:`ParsedBom`.

    This function is the **sole public entry-point** of this module.  It:

    1. Validates the bytes form a valid XLSX archive.
    2. Locates the ``Source DATA`` sheet.
    3. Discovers the FGPN from the ``COVER PN (TPDM)`` column.
    4. Asserts exactly one distinct FGPN is present (one finished good per file).
    5. Extracts all material lines that belong to that FGPN.
    6. Validates numeric fields are non-negative.

    Args:
        workbook_bytes: Raw bytes of the uploaded ``.xlsx`` file.
        source_filename: Original filename, used only for error context.

    Returns:
        A single :class:`ParsedBom` with all fields populated from the workbook.

    Raises:
        ValidationException: If the file is not a valid XLSX, the
            ``Source DATA`` sheet is missing, the required headers are absent,
            no data rows are found, or more than one distinct FGPN is present
            (each uploaded file must correspond to exactly one finished good).
    """
    filename = _clean_required(source_filename, "source_filename")

    try:
        with zipfile.ZipFile(BytesIO(workbook_bytes)) as workbook:
            shared_strings = _read_shared_strings(workbook)
            sheet_path = _find_sheet_path(workbook, _SOURCE_SHEET_NAME)
            rows = _read_sheet_rows(workbook, sheet_path, shared_strings)
    except zipfile.BadZipFile as exc:
        raise ValidationException(
            "The uploaded BOM workbook is not a valid XLSX file.",
            details={"filename": filename},
        ) from exc

    source_report_date = _parse_report_date(rows)
    source_report_time = _parse_report_time(rows)
    source_reported_by = _cell_value(rows, 2, 3)
    header_row_number, header_map = _find_header_row(rows)

    discovered_fgpns = _discover_fgpns(rows, header_row_number, header_map)

    if len(discovered_fgpns) == 0:
        raise ValidationException(
            "No data rows were found in the Source DATA sheet.",
            details={"filename": filename},
        )

    if len(discovered_fgpns) > 1:
        raise ValidationException(
            "The workbook contains more than one Finished-Good Part Number. "
            "Each uploaded file must correspond to exactly one finished good.",
            details={
                "filename": filename,
                "discovered_part_numbers": sorted(discovered_fgpns),
            },
        )

    finished_good_part_number = next(iter(discovered_fgpns))

    extracted_lines = _extract_material_lines(
        rows, header_row_number, header_map, finished_good_part_number
    )

    if not extracted_lines:
        raise ValidationException(
            "No BOM material rows were found for the discovered part number.",
            details={"finished_good_part_number": finished_good_part_number},
        )

    first_raw_row = extracted_lines[0].raw_row
    finished_good_description = first_raw_row.get(
        _HEADER_ALIASES["finished_good_description"]
    )

    return ParsedBom(
        finished_good_part_number=finished_good_part_number,
        finished_good_description=_clean_optional(finished_good_description),
        source_filename=filename,
        source_reported_by=_clean_optional(source_reported_by),
        source_report_date=source_report_date,
        source_report_time=source_report_time,
        lines=extracted_lines,
    )


# ---------------------------------------------------------------------------
# Internal helpers — parsing
# ---------------------------------------------------------------------------


def _discover_fgpns(
    rows: dict[int, dict[int, str]],
    header_row_number: int,
    header_map: dict[str, int],
) -> set[str]:
    """Return the set of distinct FGPN values found in all data rows."""
    fgpn_col = header_map["finished_good_part_number"]
    fgpns: set[str] = set()
    for row_number in sorted(row for row in rows if row > header_row_number):
        row = rows[row_number]
        value = _clean_optional(row.get(fgpn_col))
        if value is not None:
            fgpns.add(value)
    return fgpns


def _extract_material_lines(
    rows: dict[int, dict[int, str]],
    header_row_number: int,
    header_map: dict[str, int],
    part_number: str,
) -> list[ParsedBomLine]:
    """Collect and validate all material rows that match *part_number*."""
    lines: list[ParsedBomLine] = []
    for row_number in sorted(row for row in rows if row > header_row_number):
        row = rows[row_number]
        row_part_number = _clean_optional(row.get(header_map["finished_good_part_number"]))
        if row_part_number != part_number:
            continue

        raw_row = {
            header: row.get(column_index, "")
            for header, column_index in _raw_header_columns(header_map).items()
        }
        material_part_number = _clean_required(
            row.get(header_map["material_part_number"]),
            f"material_part_number row {row_number}",
        )
        line = ParsedBomLine(
            source_row_number=row_number,
            material_part_number=material_part_number,
            material_description=_clean_optional(
                row.get(header_map.get("material_description", -1))
            ),
            cover_revision=_clean_optional(row.get(header_map.get("cover_revision", -1))),
            cover_pn=_clean_optional(row.get(header_map.get("finished_good_part_number", -1))),
            quantity_tpdm=_decimal_required(
                row.get(header_map["quantity_tpdm"]),
                f"quantity_tpdm row {row_number}",
            ),
            cover_description=_clean_optional(row.get(header_map.get("finished_good_description", -1))),
            part_type=_clean_optional(row.get(header_map.get("part_type", -1))),
            coefficient=_decimal_required(
                row.get(header_map["coefficient"]),
                f"coefficient row {row_number}",
            ),
            total_quantity=_decimal_optional(row.get(header_map.get("total_quantity", -1))),
            unit=_clean_optional(row.get(header_map["unit"])),
            total_sqm=_decimal_optional(row.get(header_map.get("total_sqm", -1))),
            raw_row=raw_row,
        )
        _validate_line(line)
        lines.append(line)
    return lines


def _validate_line(line: ParsedBomLine) -> None:
    """Raise :class:`~app.exceptions.base.ValidationException` for invalid numeric fields."""
    errors: list[dict] = []
    if line.coefficient < 0:
        errors.append({"field": "coefficient", "row": line.source_row_number})
    if line.quantity_tpdm is not None and line.quantity_tpdm < 0:
        errors.append({"field": "quantity_tpdm", "row": line.source_row_number})
    if line.total_quantity is not None and line.total_quantity < 0:
        errors.append({"field": "total_quantity", "row": line.source_row_number})
    if line.total_sqm is not None and line.total_sqm < 0:
        errors.append({"field": "total_sqm", "row": line.source_row_number})
    if errors:
        raise ValidationException("Invalid BOM numeric values.", details=errors)


def _find_header_row(
    rows: dict[int, dict[int, str]],
) -> tuple[int, dict[str, int]]:
    """Scan rows top-to-bottom until the header row is found.

    Returns:
        A tuple of (row_number, header_map) where *header_map* maps
        semantic field names (e.g. ``"coefficient"``) to their 1-based
        column index in the sheet.

    Raises:
        ValidationException: If no row contains all required headers.
    """
    normalized_aliases = {
        _normalize_header(header): field for field, header in _HEADER_ALIASES.items()
    }
    for row_number, row in rows.items():
        header_map: dict[str, int] = {}
        for column_index, value in row.items():
            field = normalized_aliases.get(_normalize_header(value))
            if field:
                header_map[field] = column_index
        if _REQUIRED_HEADERS.issubset(header_map):
            return row_number, header_map

    raise ValidationException(
        "The BOM workbook does not contain the expected Source DATA headers.",
        details={"required_headers": sorted(_REQUIRED_HEADERS)},
    )


def _raw_header_columns(header_map: dict[str, int]) -> dict[str, int]:
    """Map each alias display name to its column index, for raw_row capture."""
    return {
        source_header: header_map[field_name]
        for field_name, source_header in _HEADER_ALIASES.items()
        if field_name in header_map
    }


# ---------------------------------------------------------------------------
# Internal helpers — XLSX ZIP/XML plumbing
# ---------------------------------------------------------------------------


def _find_sheet_path(workbook: zipfile.ZipFile, sheet_name: str) -> str:
    """Resolve the internal ZIP path of the named worksheet.

    Raises:
        ValidationException: If the sheet is not found in the workbook.
    """
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rel_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    relationship_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rel_root.findall("rel:Relationship", _REL_NS)
    }

    for sheet in workbook_root.findall("m:sheets/m:sheet", _WORKBOOK_NS):
        if sheet.attrib.get("name") != sheet_name:
            continue
        relation_id = sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = relationship_targets[relation_id]
        return _workbook_target_to_zip_path(target)

    raise ValidationException(
        "The BOM workbook is missing the Source DATA sheet.",
        details={"sheet_name": sheet_name},
    )


def _workbook_target_to_zip_path(target: str) -> str:
    path = PurePosixPath(target)
    if not target.startswith("/"):
        path = PurePosixPath("xl") / path
    return str(path).lstrip("/")


def _read_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    return [
        "".join(text.text or "" for text in item.findall(".//m:t", _WORKBOOK_NS))
        for item in root.findall("m:si", _WORKBOOK_NS)
    ]


def _read_sheet_rows(
    workbook: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> dict[int, dict[int, str]]:
    root = ET.fromstring(workbook.read(sheet_path))
    rows: dict[int, dict[int, str]] = {}
    for row in root.findall("m:sheetData/m:row", _WORKBOOK_NS):
        row_number = int(row.attrib["r"])
        cells: dict[int, str] = {}
        for cell in row.findall("m:c", _WORKBOOK_NS):
            cells[_column_number(cell.attrib["r"])] = _read_cell_value(
                cell, shared_strings
            )
        rows[row_number] = cells
    return rows


def _read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//m:t", _WORKBOOK_NS))

    value = cell.find("m:v", _WORKBOOK_NS)
    if value is None or value.text is None:
        return ""

    raw_value = value.text
    if cell_type == "s":
        return shared_strings[int(raw_value)]
    return raw_value


def _column_number(cell_reference: str) -> int:
    column_letters = "".join(c for c in cell_reference if c.isalpha())
    column_number = 0
    for c in column_letters:
        column_number = column_number * 26 + ord(c.upper()) - 64
    return column_number


# ---------------------------------------------------------------------------
# Internal helpers — value coercion
# ---------------------------------------------------------------------------


def _cell_value(rows: dict[int, dict[int, str]], row: int, column: int) -> Optional[str]:
    return _clean_optional(rows.get(row, {}).get(column))


def _parse_report_date(rows: dict[int, dict[int, str]]) -> Optional[date]:
    value = _cell_value(rows, 1, 3)
    if value is None:
        return None
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    return None


def _parse_report_time(rows: dict[int, dict[int, str]]) -> Optional[time]:
    value = _cell_value(rows, 1, 8)
    if value is None:
        return None
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, pattern).time()
        except ValueError:
            continue
    return None


def _clean_required(value: Optional[str], field_name: str) -> str:
    cleaned = _clean_optional(value)
    if cleaned is None:
        raise ValidationException(
            "A required BOM field is missing.",
            details={"field": field_name},
        )
    return cleaned


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _decimal_required(value: Optional[str], field_name: str) -> Decimal:
    parsed = _decimal_optional(value)
    if parsed is None:
        raise ValidationException(
            "A required BOM numeric field is missing or invalid.",
            details={"field": field_name, "value": value},
        )
    return parsed


def _decimal_optional(value: Optional[str]) -> Optional[Decimal]:
    cleaned = _clean_optional(value)
    if cleaned is None or cleaned.startswith("#"):
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _normalize_header(value: Optional[str]) -> str:
    cleaned = _clean_optional(value)
    if cleaned is None:
        return ""
    return re.sub(r"\s+", " ", cleaned.casefold())
