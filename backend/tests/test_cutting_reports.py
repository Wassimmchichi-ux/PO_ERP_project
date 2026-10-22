"""Use the supplied cutting export to validate staging and consumption accounting."""
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

import pytest
from sqlalchemy import select, func

from app.exceptions.base import ConflictException, ForbiddenException, NotFoundException, ValidationException
from app.models import CuttingConsumption, CuttingReportImport, Launch, Material, MaterialType, Simulation, StockUnit
from app.policies import PolicyActor
from app.schemas.cutting_report import CuttingReportPostRequest
from app.services.cutting_report_service import import_report, post_report
from app.services.stock_management_service import get_material_stock_detail
from app.utils.cutting_report_extractor import extract_cutting_report
from tests.test_simulation_database import db_session, seeded_db, TEST_USER_ID

SOURCE = Path(__file__).resolve().parents[2] / "ressources" / "business-test" / "cutting_report-test .xlsx"
MATERIAL = "6718062-180020-D"
ACTOR = PolicyActor(user_id=TEST_USER_ID, role="LAUNCH_ENGINEER")


def test_new_cutting_export_ignores_formatted_blank_rows():
    rows = extract_cutting_report(SOURCE.read_bytes(), SOURCE.name)
    assert len(rows) == 1
    assert rows[0].row_number == 2 and rows[0].material_part_number == MATERIAL
    assert rows[0].started_at == datetime(2026, 8, 3, 0, 3, 20)
    assert rows[0].spreading_usage.quantize(Decimal(".0001")) == Decimal("67.2580")
    assert rows[0].raw_fields["CNC Length"] == "4.4824000000000002"
    assert rows[0].raw_fields["Last status"] == ""


@pytest.fixture()
def production(db_session, seeded_db):
    now = datetime(2026, 8, 1)
    material_type = MaterialType(name="CUTTING_TEST", unit="m")
    db_session.add(material_type)
    db_session.flush()
    db_session.add(Material(material_part_number=MATERIAL, description="Cutting source material", material_type_id=material_type.material_type_id, unit_price=0))
    db_session.flush()
    db_session.add(StockUnit(material_part_number=MATERIAL, quantity=100, status="PRODUCTION", created_at=now))
    simulation = Simulation(simulation_mode="CURRENT_STOCK", target_date=date(2026, 8, 1), is_feasible=True,
        mtg_minutes_document_id=101, created_at=now, created_by=TEST_USER_ID)
    db_session.add(simulation)
    db_session.flush()
    launch = Launch(simulation_id=simulation.simulation_id, planned_date=date(2026, 8, 1), delivery_method_id=1, receiver_id=1,
        status="IN_PROGRESS", completed_by=TEST_USER_ID, verified_by=TEST_USER_ID, verification_document_id=103, created_at=now, updated_at=now)
    db_session.add(launch)
    db_session.commit()
    return launch.launch_id


def stage(db):
    return import_report(db, SOURCE.read_bytes(), SOURCE.name, TEST_USER_ID, actor=ACTOR)


def posting(launch_id, unit="m"):
    return CuttingReportPostRequest(launch_id=launch_id, usage_unit=unit, confirm_usage_is_consumption=True)


def test_import_keeps_original_and_does_not_change_stock(db_session, production):
    first = stage(db_session)
    duplicate = stage(db_session)
    assert duplicate.report_id == first.report_id and duplicate.already_imported
    assert db_session.scalar(select(func.count()).select_from(CuttingReportImport)) == 1
    assert db_session.get(CuttingReportImport, first.report_id).source_content == SOURCE.read_bytes()
    assert db_session.scalar(select(func.count()).select_from(CuttingConsumption)) == 0
    assert get_material_stock_detail(db_session, MATERIAL).production == 100


def test_confirmed_consumption_reduces_wip_and_cannot_repeat(db_session, production):
    staged = stage(db_session)
    result = post_report(db_session, staged.report_id, posting(production), TEST_USER_ID, actor=ACTOR)
    assert result.posted_launch_id == production and result.posted_at is not None
    assert get_material_stock_detail(db_session, MATERIAL).production == Decimal("32.7420")
    row = db_session.scalars(select(CuttingConsumption)).one()
    assert row.quantity_consumed == Decimal("67.2580")
    assert row.source_row_number == 2 and row.source_report_id == staged.report_id
    assert row.consumed_at == datetime(2026, 8, 3, 0, 3, 20)
    with pytest.raises(ConflictException, match="already been posted"):
        post_report(db_session, staged.report_id, posting(production), TEST_USER_ID, actor=ACTOR)
    assert get_material_stock_detail(db_session, MATERIAL).production == Decimal("32.7420")


def test_overlapping_exports_cannot_double_count(db_session, production):
    original = stage(db_session)
    post_report(db_session, original.report_id, posting(production), TEST_USER_ID, actor=ACTOR)
    stream = BytesIO(SOURCE.read_bytes())
    with ZipFile(stream, "a") as workbook:
        workbook.comment = b"Re-export of the same cutting events"
    other = import_report(db_session, stream.getvalue(), "reexport.xlsx", TEST_USER_ID, actor=ACTOR)
    assert other.report_id != original.report_id
    with pytest.raises(ConflictException, match="already posted"):
        post_report(db_session, other.report_id, posting(production), TEST_USER_ID, actor=ACTOR)


@pytest.mark.parametrize("problem", ["unit", "stock", "material", "launch"])
def test_posting_validates_linkage_units_and_balances_before_any_write(db_session, production, problem):
    staged = stage(db_session)
    request = posting(production)
    if problem == "unit":
        request = posting(production, "sqm")
    elif problem == "stock":
        db_session.scalars(select(StockUnit).where(StockUnit.material_part_number == MATERIAL)).one().quantity = 10
    elif problem == "material":
        report = db_session.get(CuttingReportImport, staged.report_id)
        report.source_rows = [{**report.source_rows[0], "material_part_number": "UNKNOWN"}]
    else:
        request = posting(99999)
    db_session.commit()
    with pytest.raises((ValidationException, NotFoundException)):
        post_report(db_session, staged.report_id, request, TEST_USER_ID, actor=ACTOR)
    assert db_session.scalar(select(func.count()).select_from(CuttingConsumption)) == 0
    assert db_session.get(CuttingReportImport, staged.report_id).posted_at is None


def test_warehouse_role_cannot_import_or_post_cutting_usage(db_session, production):
    actor = PolicyActor(user_id=TEST_USER_ID, role="WAREHOUSE_PERSONNEL")
    with pytest.raises(ForbiddenException):
        import_report(db_session, SOURCE.read_bytes(), SOURCE.name, TEST_USER_ID, actor=actor)
    report = stage(db_session)
    with pytest.raises(ForbiddenException):
        post_report(db_session, report.report_id, posting(production), TEST_USER_ID, actor=actor)


@pytest.mark.parametrize("content,name", [(b"not a workbook", "report.xlsx"), (b"select * from stock", "report.sql")])
def test_cutting_import_rejects_unsupported_or_invalid_sources(content, name):
    with pytest.raises(ValidationException):
        extract_cutting_report(content, name)
