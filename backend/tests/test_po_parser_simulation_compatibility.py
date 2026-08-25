"""Compatibility checks between parsed PO JSON and simulation inputs."""
from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

from app.utils import bom_workbook_extractor as bom_xlsx


ROOT = Path(__file__).resolve().parents[2]
PARSED_PO_PATH = ROOT / "2301438886.json"
MBOM_PATH = ROOT / "MBOM_08_08_2025-02.xlsx"


def test_parsed_po_has_fields_needed_to_create_po_lines_for_simulation() -> None:
    """Parsed PO rows have enough data to seed PurchaseOrderLine rows."""
    parsed_po = json.loads(PARSED_PO_PATH.read_text())

    assert parsed_po["po_number"] == "2301438886"
    assert parsed_po["version"] == "2"
    assert parsed_po["line_count"] == len(parsed_po["lines"]) == 27
    assert parsed_po["totals_match"] is True

    first_line = parsed_po["lines"][0]
    assert {
        "line_no",
        "part_number",
        "description",
        "quantity",
        "unit_price",
        "due_date",
    }.issubset(first_line)


def test_parsed_po_part_numbers_must_be_resolved_to_bom_fgpn_codes() -> None:
    """The parser output uses PO revision codes, while MBOM uses BOM FGPN codes."""
    parsed_po = json.loads(PARSED_PO_PATH.read_text())
    po_part_numbers = [line["part_number"] for line in parsed_po["lines"]]
    mbom_fgpn_codes = _mbom_fgpn_codes()

    exact_matches = [part for part in po_part_numbers if part in mbom_fgpn_codes]
    normalized_matches = {
        part: _mbom_candidates_for_po_part(part, mbom_fgpn_codes)
        for part in po_part_numbers
    }
    normalized_matches = {
        part: candidates
        for part, candidates in normalized_matches.items()
        if candidates
    }

    assert exact_matches == []
    assert len(normalized_matches) == 9
    assert normalized_matches["6855879-9E43-AF"] == ["6855879-9E43-000"]
    assert normalized_matches["7197885-5F94-AE"] == ["7197885-5F94-000"]
    assert "7417370-8AC3-AD" not in normalized_matches


def _mbom_fgpn_codes() -> set[str]:
    with zipfile.ZipFile(BytesIO(MBOM_PATH.read_bytes())) as workbook:
        shared_strings = bom_xlsx._read_shared_strings(workbook)
        sheet_path = bom_xlsx._find_sheet_path(workbook, bom_xlsx._SOURCE_SHEET_NAME)
        rows = bom_xlsx._read_sheet_rows(workbook, sheet_path, shared_strings)

    header_row_number, header_map = bom_xlsx._find_header_row(rows)
    return bom_xlsx._discover_fgpns(rows, header_row_number, header_map)


def _mbom_candidates_for_po_part(po_part_number: str, mbom_fgpn_codes: set[str]) -> list[str]:
    """Match PO revision suffixes to BOM FGPN codes with the same base."""
    base = po_part_number.rsplit("-", 1)[0]
    return sorted(code for code in mbom_fgpn_codes if code.startswith(f"{base}-"))
