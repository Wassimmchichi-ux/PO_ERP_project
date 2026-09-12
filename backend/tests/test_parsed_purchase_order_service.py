"""Tests for parsed purchase order staging and correction flow."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.exceptions.base import ValidationException
from app.models import Contact, Customer, DeliveryMethod, FGPN, FGPNPriceHistory, Project, PurchaseOrder, PurchaseOrderLine, User
from app.schemas.parsed_purchase_order import (
    ParsedPurchaseOrderCorrectionInput,
    ParsedPurchaseOrderCorrectionsRequest,
    ParsedPurchaseOrderCreateRequest,
    ParsedPurchaseOrderImportRequest,
)
from app.services import parsed_purchase_order_service


ROOT = Path(__file__).resolve().parents[2]
PARSED_PO_PATH = ROOT / "2301416000.json"
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
                role="LAUNCH ENGINEER",
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
    payload = json.loads(PARSED_PO_PATH.read_text())

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
    assert corrected.parsed_payload["lines"][0]["quantity"] == 21
    assert corrected.effective_payload["lines"][0]["quantity"] == 22
    assert corrected.effective_payload["contact_email"] == "launch@example.com"
    correction_by_path = {correction.field_path: correction for correction in corrected.corrections}
    assert correction_by_path["lines[0].quantity"].original_value == 21
    assert validation.is_valid is True
    assert validation.status == "VALIDATED"
    assert any("FGPN mapping" in warning for warning in validation.warnings)


def test_saving_invalid_corrections_runs_validation_and_keeps_corrected_status(
    db_session: Session,
) -> None:
    payload = json.loads(PARSED_PO_PATH.read_text())
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
    payload = json.loads(PARSED_PO_PATH.read_text())
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
    payload = json.loads(PARSED_PO_PATH.read_text())
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


def test_parsed_po_import_updates_fgpn_price_history_when_price_changes(db_session: Session) -> None:
    payload = json.loads(PARSED_PO_PATH.read_text())
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

    changed_payload = json.loads(PARSED_PO_PATH.read_text())
    changed_payload["version"] = "2"
    changed_payload["lines"][0]["unit_price"] = 99.99
    changed_payload["lines"][0]["total"] = changed_payload["lines"][0]["quantity"] * 99.99
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


def test_same_fgpn_code_is_reused_across_purchase_orders_in_same_project(db_session: Session) -> None:
    payload = json.loads(PARSED_PO_PATH.read_text())
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

    second_payload = json.loads(PARSED_PO_PATH.read_text())
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
