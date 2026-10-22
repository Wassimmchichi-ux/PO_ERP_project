"""Regression tests for dated transit planning and supplier changes."""
import json
import asyncio
import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.exceptions.base import ConflictException, ForbiddenException, NotFoundException, ValidationException
from app.models import Material, MaterialType, StockUnit, User
from app.models.audit_log import AuditLog
from app.policies import PolicyActor
from app.repositories import simulation_repository, stock_repository
from app.schemas.simulation import FgpnSimulationRequest, SimulationPreviewRequest, SimulationSaveRequest
from app.schemas.stock import ExpectedArrivalUpdateRequest
from app.services import material_simulation_service as simulations
from app.services.stock_management_service import update_expected_arrival
from app.services.simulation_allocator import FgpnDemand, MaterialPool, StockSlot, allocate_material, run_allocation_engine

TARGET = date(2026, 11, 10)
ENGINEER_ID = uuid.UUID("bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb")
ENGINEER = PolicyActor(user_id=ENGINEER_ID, role="LAUNCH_ENGINEER")


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=ENGINEER_ID, full_name="Planning Engineer", registration_number="LE-TEST",
            password_hash="test", role="LAUNCH_ENGINEER", status="ACTIVE", failed_login_count=0,
            is_locked=False, must_change_password=False, created_at=datetime(2026, 11, 1)))
        session.add(MaterialType(material_type_id=1, name="S", unit="pcs"))
        session.add(Material(material_part_number="MAT-1", description="Component", material_type_id=1, unit_price=Decimal("1")))
        session.commit()
        yield session
    engine.dispose()


def add_stock(db, quantity, *, status="IN_TRANSIT", eta=None, owner=None):
    unit = StockUnit(material_part_number="MAT-1", quantity=Decimal(str(quantity)), status=status,
        expected_arrival_date=eta, user_id=owner, created_at=datetime(2026, 11, 1))
    db.add(unit)
    db.flush()
    return unit


def request(**changes):
    values = dict(fgpns=[FgpnSimulationRequest(po_id=1, fgpn_id=1, requested_quantity=20)],
        allocation_strategy="PRIORITY", safety_coefficient=Decimal("1"), include_in_transit=True, target_date=TARGET)
    values.update(changes)
    return SimulationPreviewRequest(**values)


@pytest.fixture()
def demand(monkeypatch):
    bom = SimpleNamespace(lines=[SimpleNamespace(material_part_number="MAT-1", part_type="S", total_quantity=Decimal("1"))])
    line = SimpleNamespace(po_line_id=1, fgpn_id=1, ordered_quantity=Decimal("20"),
        po_version=SimpleNamespace(purchase_order=SimpleNamespace(po_id=1, po_number="PO-TEST")))
    monkeypatch.setattr(simulation_repository, "get_current_boms_for_fgpns", lambda *args: {1: bom})
    monkeypatch.setattr(simulation_repository, "get_fgpns", lambda *args: {1: SimpleNamespace(fgpn_code="FG-TEST")})
    monkeypatch.setattr(simulation_repository, "get_po_lines", lambda *args: {})
    monkeypatch.setattr(simulation_repository, "get_current_po_lines_for_po_fgpns", lambda *args: {(1, 1): line})


@pytest.mark.parametrize("strategy", ["PRIORITY", "MANUAL", "PRIORITY_PLUS_MANUAL"])
@pytest.mark.parametrize("split", [True, False])
def test_production_before_warehouse_and_transit(strategy, split):
    pool = MaterialPool(material_part_number="MAT-1",
        production_slots=[StockSlot(None, "PRODUCTION", Decimal("5"))],
        warehouse_slots=[StockSlot(1, "WAREHOUSE", Decimal("8"), can_split=split)],
        in_transit_slots=[StockSlot(2, "IN_TRANSIT", Decimal("10"), can_split=split)])
    row = FgpnDemand(1, "FG", 1, Decimal("15"), Decimal("15"))
    row.material_demands["MAT-1"] = Decimal("15")
    _, allocations = run_allocation_engine([row], {"MAT-1": pool}, strategy)
    assert [(slot.source, qty) for _, slot, qty in allocations] == [
        ("PRODUCTION", Decimal("5")), ("WAREHOUSE", Decimal("8")),
        ("IN_TRANSIT", Decimal("2") if split else Decimal("10"))]
    assert row.is_fully_covered


def test_production_avoids_opening_new_roll():
    pool = MaterialPool(material_part_number="ROLL",
        production_slots=[StockSlot(None, "PRODUCTION", Decimal("6"))],
        warehouse_slots=[StockSlot(1, "WAREHOUSE", Decimal("60"), can_split=False)])
    covered, allocations = allocate_material(pool, Decimal("4"))
    assert covered == Decimal("4")
    assert len(allocations) == 1 and allocations[0][0].source == "PRODUCTION"
    assert pool.production_slots[0].remaining == Decimal("2")
    assert pool.warehouse_slots[0].remaining == Decimal("60")


def test_preview_filters_arrivals_inclusively_and_reports_same_totals(db, demand):
    add_stock(db, 7, status="WAREHOUSE")
    add_stock(db, 5, status="PRODUCTION")
    early = add_stock(db, 2, eta=datetime(2026, 11, 9))
    on_date = add_stock(db, 3, eta=datetime(2026, 11, 10, 23, 59, 59))
    late = add_stock(db, 50, eta=datetime(2026, 11, 11))
    undated = add_stock(db, 50)
    add_stock(db, 0, eta=datetime(2026, 11, 9))
    result = simulations.preview_simulation(db, request(), actor=ENGINEER)
    summary = result.material_summaries[0]
    assert result.target_date == TARGET
    assert summary.in_transit == Decimal("5")
    assert summary.available_stock == Decimal("17")
    assert result.total_launchable_quantity == Decimal("17") and not result.is_feasible
    assert [item.source for item in result.allocation_details] == ["PRODUCTION", "WAREHOUSE", "IN_TRANSIT", "IN_TRANSIT"]
    ids = {item.stock_unit_id for item in result.allocation_details}
    assert {early.stock_unit_id, on_date.stock_unit_id} <= ids
    assert late.stock_unit_id not in ids and undated.stock_unit_id not in ids
    assert stock_repository.get_in_transit_stock_by_material(db, target_date=TARGET) == {"MAT-1": Decimal("5")}
    current = simulations.preview_simulation(db, request(include_in_transit=False), actor=ENGINEER)
    assert current.material_summaries[0].available_stock == Decimal("12")
    assert current.material_summaries[0].in_transit == Decimal("5")


def test_target_date_is_required_only_for_transit(db, demand):
    with pytest.raises(ValidationException, match="target_date is required"):
        simulations.preview_simulation(db, request(target_date=None), actor=ENGINEER)
    assert simulations.preview_simulation(db, request(include_in_transit=False, target_date=None), actor=ENGINEER).target_date is None


@pytest.mark.parametrize("include_global, expected", [(False, Decimal("2")), (True, Decimal("5"))])
def test_date_filter_preserves_owner_scope(db, demand, include_global, expected):
    add_stock(db, 2, eta=datetime(2026, 11, 10), owner=ENGINEER_ID)
    add_stock(db, 3, eta=datetime(2026, 11, 10))
    add_stock(db, 40, eta=datetime(2026, 11, 11), owner=ENGINEER_ID)
    result = simulations.preview_simulation(db, request(stock_scope_mode="OWNED_ONLY",
        stock_owner_user_id=ENGINEER_ID, include_global_stock=include_global), actor=ENGINEER)
    assert result.material_summaries[0].available_stock == expected


@pytest.mark.parametrize("role", ["LAUNCH_ENGINEER", "LAUNCH_MANAGER", "ADMIN"])
def test_reschedule_persists_date_and_audit(db, role):
    stock = add_stock(db, 20, eta=datetime(2026, 11, 10))
    result = update_expected_arrival(db, stock.stock_unit_id,
        ExpectedArrivalUpdateRequest(expected_arrival_date=date(2026, 11, 12), reason="  Supplier delay  "),
        ENGINEER_ID, actor=PolicyActor(user_id=ENGINEER_ID, role=role))
    db.expire_all()
    assert db.get(StockUnit, stock.stock_unit_id).expected_arrival_date == datetime(2026, 11, 12)
    assert result.expected_arrival_date == date(2026, 11, 12)
    audit = db.scalars(select(AuditLog)).one()
    assert audit.user_id == ENGINEER_ID and audit.entity_id == stock.stock_unit_id and audit.reason == "Supplier delay"
    assert json.loads(audit.details) == {"previous_expected_arrival_date": "2026-11-10", "expected_arrival_date": "2026-11-12", "actor_role": role}
    assert stock_repository.get_in_transit_stock_by_material(db, target_date=TARGET) == {}


@pytest.mark.parametrize("role", ["WAREHOUSE_PERSONNEL", "WAREHOUSE_TEAM_LEADER", "PLANT_MANAGER", "MANUFACTURING_OPERATOR"])
def test_other_roles_cannot_reschedule(db, role):
    stock = add_stock(db, 20, eta=datetime(2026, 11, 10))
    with pytest.raises(ForbiddenException):
        update_expected_arrival(db, stock.stock_unit_id,
            ExpectedArrivalUpdateRequest(expected_arrival_date=TARGET, reason="Supplier update"),
            ENGINEER_ID, actor=PolicyActor(user_id=ENGINEER_ID, role=role))
    assert db.scalars(select(AuditLog)).all() == []


@pytest.mark.parametrize("status", ["WAREHOUSE", "PRODUCTION", "ISSUED_TO_PRODUCTION"])
def test_cannot_reschedule_received_or_issued_stock(db, status):
    stock = add_stock(db, 20, status=status)
    with pytest.raises(ConflictException):
        update_expected_arrival(db, stock.stock_unit_id,
            ExpectedArrivalUpdateRequest(expected_arrival_date=TARGET, reason="Supplier update"), ENGINEER_ID, actor=ENGINEER)
    assert stock.expected_arrival_date is None


def test_missing_unit_and_invalid_change_request(db):
    with pytest.raises(NotFoundException):
        update_expected_arrival(db, 999, ExpectedArrivalUpdateRequest(expected_arrival_date=TARGET, reason="Update"), ENGINEER_ID, actor=ENGINEER)
    for payload in [{"expected_arrival_date": "bad", "reason": "Update"},
                    {"expected_arrival_date": str(TARGET), "reason": "   "},
                    {"expected_arrival_date": None, "reason": "Update"}]:
        with pytest.raises(ValidationError):
            ExpectedArrivalUpdateRequest(**payload)


def test_arrival_date_http_contract(db, demand):
    import httpx
    from fastapi import FastAPI
    from app.api.stock import router as stock_router
    from app.api.simulation import router as simulation_router
    from app.dependencies.db import get_db
    from app.exceptions.handlers import register_exception_handlers

    stock = add_stock(db, 20, eta=datetime(2026, 11, 10))
    db.commit()
    app = FastAPI()
    app.include_router(stock_router)
    app.include_router(simulation_router)
    register_exception_handlers(app)
    async def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            path = f"/stock/units/{stock.stock_unit_id}/expected-arrival"
            payload = {"expected_arrival_date": "2026-11-12", "reason": "Supplier delay"}
            denied = await client.patch(path, json=payload, headers={"X-ERP-Role": "WAREHOUSE_PERSONNEL"})
            assert denied.status_code == 403
            headers = {"X-ERP-User-Id": str(ENGINEER_ID)}
            invalid = await client.patch(path, json={**payload, "reason": "  "}, headers=headers)
            assert invalid.status_code == 422
            changed = await client.patch(path, json=payload, headers=headers)
            assert changed.status_code == 200 and changed.json()["expected_arrival_date"] == "2026-11-12"
            listed = await client.get("/stock/in-transit", headers=headers)
            assert listed.json()["items"][0]["expected_arrival_date"] == "2026-11-12"
            filtered = await client.get(f"/stock/in-transit?to_date={TARGET}", headers=headers)
            assert filtered.json()["items"] == []
            invalid_preview = await client.post("/simulations/preview", json=request(target_date=None).model_dump(mode="json"), headers=headers)
            assert invalid_preview.status_code == 422
            preview = await client.post("/simulations/preview", json=request().model_dump(mode="json"), headers=headers)
            assert preview.status_code == 200 and not preview.json()["is_feasible"]
    asyncio.run(exercise())


def test_save_uses_top_level_target_date_and_rejects_mismatch(db, demand, monkeypatch):
    add_stock(db, 20, eta=datetime(2026, 11, 11))
    saved = {}
    monkeypatch.setattr(simulation_repository, "count_user_simulations", lambda *args: 0)
    def capture(db, **kwargs):
        saved.update(kwargs)
        return 123
    monkeypatch.setattr(simulation_repository, "save_simulation", capture)
    simulations.save_simulation(db, SimulationSaveRequest(preview_request=request(target_date=None),
        target_date=TARGET, mtg_minutes_document_id=1), ENGINEER_ID, actor=ENGINEER)
    assert saved["target_date"] == TARGET
    assert saved["is_feasible"] is False and saved["allocations"] == []
    with pytest.raises(ValidationException, match="must match"):
        simulations.save_simulation(db, SimulationSaveRequest(preview_request=request(),
            target_date=date(2026, 11, 12), mtg_minutes_document_id=1), ENGINEER_ID, actor=ENGINEER)


@pytest.mark.parametrize("replacement", [False, True])
def test_supplier_delay_revalidates_saved_launch_at_original_target(db, demand, monkeypatch, replacement):
    stock = add_stock(db, 20, eta=datetime(2026, 11, 10))
    simulation = SimpleNamespace(simulation_id=1, target_date=TARGET, allocation_strategy="PRIORITY",
        simulation_mode="INCLUDING_IN_TRANSIT", safety_coefficient=Decimal("1"),
        stock_scope_mode="ALL", stock_owner_user_id=None, include_global_stock=False)
    allocation = SimpleNamespace(stock_unit_id=stock.stock_unit_id, allocated_quantity=Decimal("20"))
    selection = SimpleNamespace(po_id=1, fgpn_id=1, po_line_id=None, simulation_quantity=Decimal("20"))
    monkeypatch.setattr(simulation_repository, "get_simulation", lambda *args: simulation)
    monkeypatch.setattr(simulation_repository, "get_simulation_allocations", lambda *args, **kwargs: [allocation])
    monkeypatch.setattr(simulation_repository, "get_simulation_selected_fgpns", lambda *args: [selection])
    assert simulations.review_simulation_for_launch(db, 1, actor=ENGINEER).can_launch
    update_expected_arrival(db, stock.stock_unit_id,
        ExpectedArrivalUpdateRequest(expected_arrival_date=date(2026, 11, 12), reason="Transport delay"), ENGINEER_ID, actor=ENGINEER)
    if replacement:
        add_stock(db, 20, status="WAREHOUSE")
    review = simulations.review_simulation_for_launch(db, 1, actor=ENGINEER)
    assert review.can_launch is replacement and review.original_allocations_available is False
    assert review.replacement_preview.target_date == TARGET
    assert review.replacement_preview.material_summaries[0].in_transit == Decimal("0")
    if not replacement:
        with pytest.raises(ConflictException):
            simulations.launch_saved_simulation(db, 1, actor=PolicyActor(user_id=ENGINEER_ID, role="LAUNCH_MANAGER"))
