"""Tests for multi-FGPN BOM workbook extraction."""
from __future__ import annotations

import zipfile
from datetime import date, time
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from app.exceptions.base import ValidationException
from app.utils.bom_workbook_extractor import parse_bom_workbook, parse_bom_workbook_many


def _inline_cell(ref: str, value: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'


def _row(number: int, cells: dict[str, str]) -> str:
    return f'<row r="{number}">{"".join(_inline_cell(ref, value) for ref, value in cells.items())}</row>'


def _multi_fgpn_workbook() -> bytes:
    rows = [
        _row(1, {"C1": "08/08/2025", "H1": "10:30"}),
        _row(2, {"C2": "ERP_prototype"}),
        _row(
            4,
            {
                "A4": "COVER PN (TPDM)",
                "B4": "Cover description",
                "C4": "Material PN",
                "D4": "MATERIAL DESCRIPTION (primarly TPDM)",
                "E4": "Cover revision",
                "F4": "Part type",
                "G4": "Coefficient",
                "H4": "QUANTITY TPDM",
                "I4": "total qty",
                "J4": "UNIT",
                "K4": "Total m",
            },
        ),
        _row(
            5,
            {
                "A5": "FGPN-1001",
                "B5": "Right seat cover",
                "C5": "MAT-ROLL-01",
                "D5": "Prototype fabric",
                "E5": "A",
                "F5": "M",
                "G5": "1.25",
                "H5": "2",
                "I5": "2.50",
                "J5": "m",
                "K5": "2.50",
            },
        ),
        _row(
            6,
            {
                "A6": "FGPN-1002",
                "B6": "Left seat cover",
                "C6": "MAT-ROLL-02",
                "D6": "Prototype backing",
                "E6": "A",
                "F6": "M",
                "G6": "1.10",
                "H6": "3",
                "I6": "3.30",
                "J6": "m",
                "K6": "3.30",
            },
        ),
    ]
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(rows)}</sheetData>"
        "</worksheet>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Source DATA" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return output.getvalue()


def test_multi_fgpn_workbook_returns_one_parsed_bom_per_fgpn() -> None:
    parsed = parse_bom_workbook_many(
        _multi_fgpn_workbook(),
        source_filename="multi-bom.xlsx",
    )

    assert [bom.finished_good_part_number for bom in parsed] == ["FGPN-1001", "FGPN-1002"]
    assert [bom.material_row_count for bom in parsed] == [1, 1]
    assert parsed[0].lines[0].unit == "m"


def test_legacy_single_bom_parser_rejects_multi_fgpn_workbook() -> None:
    with pytest.raises(ValidationException):
        parse_bom_workbook(_multi_fgpn_workbook(), source_filename="multi-bom.xlsx")


def test_current_business_workbook_preserves_both_fgpns_materials_and_source_units() -> None:
    source = Path(__file__).resolve().parents[2] / "ressources" / "business-test" / "MBOM 07_08_2026-02-Test.xlsx"
    parsed = parse_bom_workbook_many(source.read_bytes(), source_filename=source.name)

    assert [bom.finished_good_part_number for bom in parsed] == [
        "6134635-AD40-000", "6134635-AT43-000"
    ]
    assert [bom.material_row_count for bom in parsed] == [3, 3]
    assert {line.material_part_number for bom in parsed for line in bom.lines} == {
        "6877665-150070_D", "6877665-150020_D", "5339613-N_D", "7092284-N_D"
    }
    for bom in parsed:
        assert bom.source_report_date == date(2026, 8, 7)
        assert bom.source_report_time == time(8, 56, 12)
        assert bom.finished_good_description == "RB 50% RH Style 1"
        roll, component_three, component_one = bom.lines
        assert roll.unit == "ME"
        assert roll.part_type == "M"
        assert roll.total_quantity == Decimal("0")
        assert roll.total_sqm.quantize(Decimal("0.0001")) == Decimal("0.2669")
        assert component_three.unit == component_one.unit == "EA"
        assert component_three.total_quantity == Decimal("3")
        assert component_one.total_quantity == Decimal("1")
