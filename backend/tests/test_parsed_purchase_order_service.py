"""Tests for parsed purchase order staging and correction flow."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.exceptions.base import ValidationException
from app.models import Contact, Customer, DeliveryMethod, FGPN, FGPNPriceHistory, Project, PurchaseOrder, PurchaseOrderLine, PurchaseOrderVersion, User
from app.schemas.parsed_purchase_order import (
    ParsedPurchaseOrderCorrectionInput,
    ParsedPurchaseOrderCorrectionsRequest,
    ParsedPurchaseOrderCreateRequest,
    ParsedPurchaseOrderImportRequest,
)
from app.services import parsed_purchase_order_service
from app.services import purchase_order_service


ROOT = Path(__file__).resolve().parents[2]
BUSINESS_TEST = ROOT / "ressources" / "business-test"
PARSED_PO_PATH = BUSINESS_TEST / "Adient PO 2301480082.pdf"
PO_DOCUMENTS = [
    ("Adient PO 2301480082.pdf", "2301480082", 14, "32986.95", "2026-01-30", "2026-03-10", "6134270-AX08-AC"),
    ("Adient PO 2301478532.PDF", "2301478532", 50, "26329.26", "2026-01-28", "2026-02-10", "8134279-9A08-AB"),
    ("Adient PO 2301438886.pdf", "2301438886", 27, "68765.27", "2025-10-27", "2026-06-09", "9955879-BA63-AC"),
]


def _sample_payload(path: Path = PARSED_PO_PATH) -> dict:
    return parsed_purchase_order_service._parse_simple_purchase_order_payload(path.read_bytes())
TEST_USER_ID = uuid.UUID("bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb")


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = session_factory()
    try:
        session.add(
            User(
                id=TEST_USER_ID,
                full_name="Launch Engineer",
                registration_number="LE-001",
                password_hash="test",
                role="LAUNCH_ENGINEER",
                status="ACTIVE",
                failed_login_count=0,
                is_locked=False,
                must_change_password=False,
                created_at=datetime(2026, 8, 29, 9, 0, 0),
            )
        )
        now = datetime(2026, 8, 29, 9, 0, 0)
        session.add_all(
            [
                Project(
                    project_id=1,
                    project_code="P-2261",
                    name="Covers B-SUV Seat Trim",
                    launch_engineer_user_id=TEST_USER_ID,
                    status="Active",
                    created_at=now,
                    updated_at=now,
                ),
                Customer(
                    customer_id=1,
                    customer_code="AREA",
                    name="Aurea Automotive",
                    status="Active",
                    created_at=now,
                    updated_at=now,
                ),
                Contact(
                    contact_id=1,
                    customer_id=1,
                    name="Launch Contact",
                    status="Active",
                    created_at=now,
                    updated_at=now,
                ),
                DeliveryMethod(delivery_method_id=1, name="Truck", status="Active"),
            ]
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_parsed_po_payload_can_be_stored_corrected_and_validated(db_session: Session) -> None:
    payload = _sample_payload()

    created = parsed_purchase_order_service.create_parsed_purchase_order(
        db_session,
        ParsedPurchaseOrderCreateRequest(
            source_file_name=PARSED_PO_PATH.name,
            parser_name="external-po-parser",
            parsed_payload=payload,
        ),
        TEST_USER_ID,
    )

    corrected = parsed_purchase_order_service.save_parsed_purchase_order_corrections(
        db_session,
        created.parsed_po_id,
        ParsedPurchaseOrderCorrectionsRequest(
            corrections=[
                ParsedPurchaseOrderCorrectionInput(
                    field_path="lines[0].quantity",
                    corrected_value=22,
                ),
                ParsedPurchaseOrderCorrectionInput(
                    field_path="contact_email",
                    corrected_value="launch@example.com",
                ),
            ],
        ),
        TEST_USER_ID,
    )

    validation = parsed_purchase_order_service.validate_parsed_purchase_order(
        db_session,
        created.parsed_po_id,
    )

    assert created.status == "PARSED"
    assert corrected.status == "VALIDATED"
    assert corrected.parsed_payload["lines"][0]["quantity"] == "8"
    assert corrected.effective_payload["lines"][0]["quantity"] == 22
    assert corrected.effective_payload["contact_email"] == "launch@example.com"
    correction_by_path = {correction.field_path: correction for correction in corrected.corrections}
    assert correction_by_path["lines[0].quantity"].original_value == "8"
    assert validation.is_valid is True
    assert validation.status == "VALIDATED"
    assert any("FGPN mapping" in warning for warning in validation.warnings)


def test_saving_invalid_corrections_runs_validation_and_keeps_corrected_status(
    db_session: Session,
) -> None:
    payload = _sample_payload()
    created = parsed_purchase_order_service.create_parsed_purchase_order(
        db_session,
        ParsedPurchaseOrderCreateRequest(parsed_payload=payload),
        TEST_USER_ID,
    )

    corrected = parsed_purchase_order_service.save_parsed_purchase_order_corrections(
        db_session,
        created.parsed_po_id,
        ParsedPurchaseOrderCorrectionsRequest(
            corrections=[
                ParsedPurchaseOrderCorrectionInput(
                    field_path="lines[0].quantity",
                    corrected_value=0,
                ),
            ],
        ),
        TEST_USER_ID,
    )

    validation = parsed_purchase_order_service.validate_parsed_purchase_order(
        db_session,
        created.parsed_po_id,
    )

    assert corrected.status == "CORRECTED"
    assert validation.is_valid is False
    assert "Line 1 has invalid quantity." in validation.errors


def test_parsed_po_correction_rejects_unknown_field_path(db_session: Session) -> None:
    payload = _sample_payload()
    created = parsed_purchase_order_service.create_parsed_purchase_order(
        db_session,
        ParsedPurchaseOrderCreateRequest(parsed_payload=payload),
        TEST_USER_ID,
    )

    with pytest.raises(ValidationException):
        parsed_purchase_order_service.save_parsed_purchase_order_corrections(
            db_session,
            created.parsed_po_id,
            ParsedPurchaseOrderCorrectionsRequest(
                corrections=[
                    ParsedPurchaseOrderCorrectionInput(
                        field_path="lines[99].quantity",
                        corrected_value=1,
                    ),
                ],
            ),
            TEST_USER_ID,
        )


def test_validated_parsed_po_import_creates_po_lines_and_fgpns(db_session: Session) -> None:
    payload = _sample_payload()
    distinct_part_numbers = {line["part_number"] for line in payload["lines"]}
    created = parsed_purchase_order_service.create_parsed_purchase_order(
        db_session,
        ParsedPurchaseOrderCreateRequest(
            source_file_name=PARSED_PO_PATH.name,
            parsed_payload=payload,
        ),
        TEST_USER_ID,
    )

    result = parsed_purchase_order_service.import_parsed_purchase_order(
        db_session,
        created.parsed_po_id,
        ParsedPurchaseOrderImportRequest(
            project_id=1,
            customer_id=1,
            contact_id=1,
            delivery_method_id=1,
        ),
        TEST_USER_ID,
    )

    po = db_session.get(PurchaseOrder, result.po_id)
    lines = db_session.query(PurchaseOrderLine).filter_by(po_version_id=result.po_version_id).all()
    fgpns = db_session.query(FGPN).filter(FGPN.fgpn_id.in_(result.created_fgpn_ids)).all()

    assert result.status == "IMPORTED"
    assert result.created_po is True
    assert result.line_count == payload["line_count"]
    assert len(result.created_fgpn_ids) == len(distinct_part_numbers)
    assert po.current_version_id == result.po_version_id
    assert len(lines) == payload["line_count"]
    assert {line.fgpn_id for line in lines}.issubset(set(result.created_fgpn_ids))
    assert {fgpn.project_id for fgpn in fgpns} == {1}


def test_imported_po_is_returned_by_purchase_order_register(db_session: Session) -> None:
    """The register must query final PO tables, not parser staging records."""
    payload = _sample_payload()
    created = parsed_purchase_order_service.create_parsed_purchase_order(
        db_session,
        ParsedPurchaseOrderCreateRequest(parsed_payload=payload),
        TEST_USER_ID,
    )
    imported = parsed_purchase_order_service.import_parsed_purchase_order(
        db_session,
        created.parsed_po_id,
        ParsedPurchaseOrderImportRequest(
            project_id=1,
            customer_id=1,
            contact_id=1,
            delivery_method_id=1,
        ),
        TEST_USER_ID,
    )

    register = purchase_order_service.list_purchase_orders(db_session)

    assert register.total == 1
    item = register.items[0]
    assert item.po_id == imported.po_id
    assert item.po_number == payload["po_number"]
    assert item.project_id == 1
    assert item.current_version == payload["version"]
    assert item.status == "Unplanned"
    assert item.ordered_quantity == sum(
        (Decimal(str(line["quantity"])) for line in payload["lines"]), Decimal("0")
    )
    assert item.delivered_quantity == Decimal("0")
    assert item.remaining_quantity == item.ordered_quantity
    assert item.fgpn_codes == sorted({line["part_number"] for line in payload["lines"]})


def test_unlinked_imported_po_can_be_viewed_and_deleted(db_session: Session) -> None:
    payload = _sample_payload()
    created = parsed_purchase_order_service.create_parsed_purchase_order(
        db_session,
        ParsedPurchaseOrderCreateRequest(parsed_payload=payload),
        TEST_USER_ID,
    )
    imported = parsed_purchase_order_service.import_parsed_purchase_order(
        db_session,
        created.parsed_po_id,
        ParsedPurchaseOrderImportRequest(
            project_id=1,
            customer_id=1,
            contact_id=1,
            delivery_method_id=1,
        ),
        TEST_USER_ID,
    )

    detail = purchase_order_service.get_purchase_order(db_session, imported.po_id)
    purchase_order_service.delete_purchase_order(db_session, imported.po_id)

    assert detail.po_id == imported.po_id
    assert detail.source_file_name == f"{payload['po_number']}.json"
    assert len(detail.lines) == payload["line_count"]
    assert db_session.get(PurchaseOrder, imported.po_id) is None
    assert purchase_order_service.list_purchase_orders(db_session).total == 0


def test_parsed_po_import_updates_fgpn_price_history_when_price_changes(db_session: Session) -> None:
    payload = _sample_payload()
    first_import = parsed_purchase_order_service.create_parsed_purchase_order(
        db_session,
        ParsedPurchaseOrderCreateRequest(parsed_payload=payload),
        TEST_USER_ID,
    )
    parsed_purchase_order_service.import_parsed_purchase_order(
        db_session,
        first_import.parsed_po_id,
        ParsedPurchaseOrderImportRequest(
            project_id=1,
            customer_id=1,
            contact_id=1,
            delivery_method_id=1,
        ),
        TEST_USER_ID,
    )

    changed_payload = _sample_payload()
    changed_payload["version"] = "2"
    changed_payload["lines"][0]["unit_price"] = 99.99
    changed_payload["lines"][0]["total"] = str(Decimal(changed_payload["lines"][0]["quantity"]) * Decimal("99.99"))
    changed_import = parsed_purchase_order_service.create_parsed_purchase_order(
        db_session,
        ParsedPurchaseOrderCreateRequest(parsed_payload=changed_payload),
        TEST_USER_ID,
    )
    result = parsed_purchase_order_service.import_parsed_purchase_order(
        db_session,
        changed_import.parsed_po_id,
        ParsedPurchaseOrderImportRequest(
            project_id=1,
            customer_id=1,
            contact_id=1,
            delivery_method_id=1,
        ),
        TEST_USER_ID,
    )

    fgpn = db_session.query(FGPN).filter_by(project_id=1, fgpn_code=payload["lines"][0]["part_number"]).one()
    history = db_session.query(FGPNPriceHistory).filter_by(fgpn_id=fgpn.fgpn_id).one()

    assert result.created_po is False
    assert result.updated_fgpn_price_history_ids == [history.price_history_id]
    assert fgpn.unit_price == history.new_price
    assert history.old_price != history.new_price


@pytest.mark.parametrize("filename,number,count,total,order_date,due_date,first_part", PO_DOCUMENTS)
def test_business_purchase_order_pdfs_parse_and_import(
    db_session: Session, filename: str, number: str, count: int, total: str,
    order_date: str, due_date: str, first_part: str,
) -> None:
    path = BUSINESS_TEST / filename
    created = parsed_purchase_order_service.parse_purchase_order_bytes(
        db_session,
        source_file_name=path.name,
        content=path.read_bytes(),
        user_id=TEST_USER_ID,
    )
    payload = created.parsed_payload
    assert created.parser_name == "adient-po-parser"
    assert created.has_source_file is True
    source_content, source_type, source_name = parsed_purchase_order_service.get_parsed_purchase_order_source(
        db_session, created.parsed_po_id,
    )
    assert source_content == path.read_bytes()
    assert source_type == "application/pdf"
    assert source_name == filename
    assert payload["po_number"] == number
    assert payload["version"] == 1
    assert payload["line_count"] == count
    assert payload["computed_total"] == payload["stated_total"] == total
    assert payload["totals_match"] is True
    assert payload["currency"] == "EUR"
    assert payload["order_date"] == order_date
    assert payload["lines"][0]["part_number"] == first_part
    assert [int(line["line_no"]) for line in payload["lines"]] == list(range(1, count + 1))
    assert {line["due_date"] for line in payload["lines"]} == {due_date}
    assert {line["uom"] for line in payload["lines"]} == {"EA"}
    assert payload["extraction_errors"] == []

    validation = parsed_purchase_order_service.validate_parsed_purchase_order(db_session, created.parsed_po_id)
    assert validation.errors == []
    result = parsed_purchase_order_service.import_parsed_purchase_order(
        db_session, created.parsed_po_id,
        ParsedPurchaseOrderImportRequest(project_id=1, customer_id=1, contact_id=1, delivery_method_id=1),
        TEST_USER_ID,
    )
    version = db_session.get(PurchaseOrderVersion, result.po_version_id)
    lines = db_session.query(PurchaseOrderLine).filter_by(po_version_id=result.po_version_id).order_by(PurchaseOrderLine.line_number).all()
    assert version.document_date == date.fromisoformat(order_date)
    assert version.document.file_path == f"/purchase-orders/parsed/{created.parsed_po_id}/source"
    assert len(lines) == count
    for source_line, stored_line in zip(payload["lines"], lines, strict=True):
        assert stored_line.fgpn.fgpn_code == source_line["part_number"]
        assert stored_line.ordered_quantity == Decimal(source_line["quantity"])
        assert stored_line.unit_price == Decimal(source_line["unit_price"])
        assert stored_line.fgpn.unit_price == Decimal(source_line["unit_price"])
        assert stored_line.delivery_date == date.fromisoformat(due_date)


def test_purchase_order_page_breaks_and_source_precision_are_preserved() -> None:
    payload = _sample_payload()
    assert payload["lines"][1]["part_number"] == "6134270-KK21-AC"
    assert payload["lines"][9]["part_number"] == "6433896-PPC3-AB"
    assert payload["lines"][3]["unit_price"] == "142.27395"
    assert payload["tax_total"] is None  # Blank on source document, not an assumed zero.
    assert payload["lines"][-1]["customer_references"] == ["A2448207201", "A2049207201"]
    replacement = _sample_payload(BUSINESS_TEST / "Adient PO 2301478532.PDF")
    assert replacement["replaced_po_number"] == "2301475999"
    assert replacement["lines"][34]["part_number"] == "6433897-CCC3-AB"


def test_purchase_order_with_no_text_layer_is_rejected() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(ValidationException, match="no readable text layer"):
        parsed_purchase_order_service._parse_simple_purchase_order_payload(stream.getvalue())


def test_malformed_pdf_is_rejected() -> None:
    with pytest.raises(ValidationException, match="Could not read"):
        parsed_purchase_order_service._parse_simple_purchase_order_payload(b"%PDF-1.7 invalid")


def test_unrecognized_adient_row_is_not_silently_ignored() -> None:
    content = b"""Purchase Order
NO: 2301480082 Version: 1
00001 1198 Mar 10, 2026 907010 8 EA 145,08000 1.160,64
6134270-AX08-AC RCB 5 SEATER WO AIRBAG
00002 1198 Mar 10, 2026 907010 eight EA unreadable 870,48
Line Total EUR 2.031,12
"""
    payload = parsed_purchase_order_service._parse_simple_purchase_order_payload(content)
    errors, _ = parsed_purchase_order_service._validate_effective_payload(payload)
    assert any("Could not read item row 00002" in error for error in errors)


def test_simple_text_purchase_order_remains_supported() -> None:
    payload = parsed_purchase_order_service._parse_simple_purchase_order_payload(
        b"PO: PO-240100\n2026-01-01\n1 FGPN-1001 Seat cover 2 10.50 21.00 2026-02-01\nTotal 21.00"
    )
    assert payload["po_number"] == "PO-240100"
    assert payload["line_count"] == 1
    assert payload["lines"][0]["unit_price"] == "10.50"
    assert parsed_purchase_order_service._validate_effective_payload(payload)[0] == []


def test_same_fgpn_code_is_reused_across_purchase_orders_in_same_project(db_session: Session) -> None:
    payload = _sample_payload()
    first_import = parsed_purchase_order_service.create_parsed_purchase_order(
        db_session,
        ParsedPurchaseOrderCreateRequest(parsed_payload=payload),
        TEST_USER_ID,
    )
    first_result = parsed_purchase_order_service.import_parsed_purchase_order(
        db_session,
        first_import.parsed_po_id,
        ParsedPurchaseOrderImportRequest(
            project_id=1,
            customer_id=1,
            contact_id=1,
            delivery_method_id=1,
        ),
        TEST_USER_ID,
    )

    second_payload = _sample_payload()
    second_payload["po_number"] = "2301416001"
    second_import = parsed_purchase_order_service.create_parsed_purchase_order(
        db_session,
        ParsedPurchaseOrderCreateRequest(parsed_payload=second_payload),
        TEST_USER_ID,
    )
    second_result = parsed_purchase_order_service.import_parsed_purchase_order(
        db_session,
        second_import.parsed_po_id,
        ParsedPurchaseOrderImportRequest(
            project_id=1,
            customer_id=1,
            contact_id=1,
            delivery_method_id=1,
        ),
        TEST_USER_ID,
    )

    part_number = payload["lines"][0]["part_number"]
    first_line = (
        db_session.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.po_version.has(po_id=first_result.po_id))
        .filter(PurchaseOrderLine.fgpn.has(fgpn_code=part_number))
        .one()
    )
    second_line = (
        db_session.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.po_version.has(po_id=second_result.po_id))
        .filter(PurchaseOrderLine.fgpn.has(fgpn_code=part_number))
        .one()
    )

    assert first_result.po_id != second_result.po_id
    assert first_line.fgpn_id == second_line.fgpn_id
