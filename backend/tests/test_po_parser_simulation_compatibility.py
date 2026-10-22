"""Verify the supplied PO formats and report unresolved PO/BOM associations."""
from pathlib import Path
import pytest

from app.services.parsed_purchase_order_service import _parse_simple_purchase_order_payload
from app.utils.bom_workbook_extractor import parse_bom_workbook_many

BUSINESS_TEST = Path(__file__).resolve().parents[2] / "ressources" / "business-test"
PO_DOCUMENTS = [
    ("Adient PO 2301480082.pdf", "2301480082", 14),
    ("Adient PO 2301478532.PDF", "2301478532", 50),
    ("Adient PO 2301438886.pdf", "2301438886", 27),
]


@pytest.mark.parametrize("filename,number,count", PO_DOCUMENTS)
def test_purchase_orders_have_fields_needed_for_simulation_inputs(filename, number, count):
    payload = _parse_simple_purchase_order_payload((BUSINESS_TEST / filename).read_bytes())
    assert payload["po_number"] == number and payload["version"] == 1
    assert payload["line_count"] == len(payload["lines"]) == count
    assert payload["totals_match"] is True
    for line in payload["lines"]:
        assert {"line_no", "part_number", "description", "quantity", "unit_price", "due_date"} <= line.keys()
        assert line["part_number"] and line["due_date"]


@pytest.mark.parametrize("filename,number,count", PO_DOCUMENTS)
def test_new_documents_require_explicit_po_bom_mapping(filename, number, count):
    """Independent test samples must not be silently treated as matching orders."""
    payload = _parse_simple_purchase_order_payload((BUSINESS_TEST / filename).read_bytes())
    path = BUSINESS_TEST / "MBOM 07_08_2026-02-Test.xlsx"
    boms = parse_bom_workbook_many(path.read_bytes(), source_filename=path.name)
    codes = {bom.finished_good_part_number for bom in boms}
    assert codes == {"6134635-AD40-000", "6134635-AT43-000"}
    assert not codes.intersection(line["part_number"] for line in payload["lines"])
