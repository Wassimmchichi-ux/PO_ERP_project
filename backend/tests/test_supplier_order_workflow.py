"""Supplier planning and legally separated warehouse-arrival workflow."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.exceptions.base import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models import Material, Notification, StockMovement, StockUnit, Supplier
from app.policies import PolicyActor
from app.schemas.admin import ReferenceItemCreateRequest, ReferenceItemUpdateRequest
from app.schemas.stock import (
    ExpectedArrivalUpdateRequest,
    MaterialThresholdUpdateRequest,
    StockReceptionCorrectionRequest,
    StockUnitReceptionBatchRequest,
)
from app.schemas.supplier_order import (
    SupplierArrivalConfirmRequest,
    SupplierArrivalEntryRequest,
    SupplierArrivalLineInput,
    SupplierOrderCreateRequest,
    SupplierOrderLineInput,
    SupplierOrderUpdateRequest,
)
from app.services import admin_service, supplier_order_service
from app.services.stock_management_service import (
    correct_stock_unit_reception,
    get_in_transit_stock,
    get_stock_history,
    get_stock_summary,
    record_stock_unit_receptions,
    update_expected_arrival,
    update_material_threshold,
)
from tests.test_simulation_database import (
    LAUNCH_ENGINEER_ID,
    TEST_USER_ID,
    db_session,
    seeded_db,
)


ENGINEER = PolicyActor(user_id=LAUNCH_ENGINEER_ID, role="LAUNCH_ENGINEER")
PERSONNEL = PolicyActor(user_id=TEST_USER_ID, role="WAREHOUSE_PERSONNEL")
TEAM_LEADER = PolicyActor(user_id=TEST_USER_ID, role="WAREHOUSE_TEAM_LEADER")


def _material(db_session) -> str:
    return db_session.scalars(select(Material.material_part_number).order_by(Material.material_part_number)).first()


def _request(material: str, *, quantity: str = "50", eta: date = date(2026, 11, 10)):
    return SupplierOrderCreateRequest(
        project_id=1,
        supplier_id=1,
        lines=[
            SupplierOrderLineInput(
                material_part_number=material,
                stock_unit_kind="ROLL",
                expected_quantity=Decimal(quantity),
                expected_arrival_date=eta,
            )
        ],
    )


def test_locked_order_query_does_not_outer_join_nullable_relationships():
    """PostgreSQL rejects FOR UPDATE on the nullable side of an outer join."""
    captured_sql = ""

    class Result:
        @staticmethod
        def scalar_one_or_none():
            return None

    class CapturingSession:
        @staticmethod
        def execute(statement):
            nonlocal captured_sql
            captured_sql = str(
                statement.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            )
            return Result()

    supplier_order_service._load_order(CapturingSession(), 1, lock=True)

    assert "FOR UPDATE" in captured_sql
    assert "JOIN" not in captured_sql


def test_administrator_maintains_supplier_reference_master(db_session, seeded_db):
    created = admin_service.create_reference_item(
        db_session,
        "suppliers",
        ReferenceItemCreateRequest(value="North Coast Components", code="NCC-204"),
    )
    supplier_id = int(created.id.split(":")[1])
    assert created.value == "North Coast Components"
    assert created.detail == "NCC-204"
    assert db_session.get(Supplier, supplier_id).supplier_reference == "NCC-204"

    updated = admin_service.update_reference_item(
        db_session,
        "suppliers",
        supplier_id,
        ReferenceItemUpdateRequest(active=False),
    )
    assert updated.active is False

    request = _request(_material(db_session))
    request.supplier_id = supplier_id
    with pytest.raises(ValidationException, match="active supplier"):
        supplier_order_service.create_order(
            db_session,
            request,
            LAUNCH_ENGINEER_ID,
            actor=ENGINEER,
        )


def test_engineer_plan_personnel_entry_and_team_leader_confirmation(db_session, seeded_db):
    material = _material(db_session)
    created = supplier_order_service.create_order(
        db_session, _request(material), LAUNCH_ENGINEER_ID, actor=ENGINEER,
    )
    assert created.status == "OPEN"
    assert created.ordered_for_user_id == LAUNCH_ENGINEER_ID
    stock = db_session.get(StockUnit, created.lines[0].stock_unit_id)
    assert stock.status == "IN_TRANSIT"
    assert stock.business_unit_id == f"SU-{stock.stock_unit_id:08d}"
    assert stock.user_id == LAUNCH_ENGINEER_ID
    transit_item = get_in_transit_stock(db_session)[0]
    assert transit_item.supplier_order_id == created.supplier_order_id
    assert transit_item.supplier_order_line_id == created.lines[0].supplier_order_line_id
    assert transit_item.stock_unit_reference == stock.business_unit_id
    assert transit_item.project_code == created.project_code
    assert transit_item.supplier_name == "Atlas Technical Textiles"
    assert transit_item.supplier_reference == "SUP-001"
    assert transit_item.expected_quantity == Decimal("50")
    assert transit_item.actual_quantity is None
    assert transit_item.workflow_status == "IN_TRANSIT"
    assert db_session.scalars(
        select(StockMovement).where(
            StockMovement.supplier_order_id == created.supplier_order_id,
            StockMovement.movement_type == "TRANSIT_DECLARED",
        )
    ).one().quantity_change == Decimal("50")

    changed = update_expected_arrival(
        db_session,
        stock.stock_unit_id,
        ExpectedArrivalUpdateRequest(
            expected_arrival_date=date(2026, 11, 11),
            reason="Supplier confirmed a one-day delay.",
        ),
        LAUNCH_ENGINEER_ID,
        actor=ENGINEER,
    )
    refreshed_order = supplier_order_service.list_orders(db_session, actor=ENGINEER).items[0]
    assert changed.expected_arrival_date == date(2026, 11, 11)
    assert refreshed_order.lines[0].expected_arrival_date == date(2026, 11, 11)

    entered = supplier_order_service.enter_arrival(
        db_session,
        created.supplier_order_id,
        SupplierArrivalEntryRequest(lines=[SupplierArrivalLineInput(
            supplier_order_line_id=created.lines[0].supplier_order_line_id,
            actual_quantity=Decimal("48"),
        )]),
        TEST_USER_ID,
        actor=PERSONNEL,
    )
    assert entered.status == "ARRIVAL_ENTERED" and entered.has_discrepancy
    assert db_session.get(StockUnit, stock.stock_unit_id).status == "IN_TRANSIT"
    pending_confirmation = next(
        item
        for item in get_in_transit_stock(db_session)
        if item.stock_unit_id == stock.stock_unit_id
    )
    assert pending_confirmation.workflow_status == "AWAITING_CONFIRMATION"
    assert pending_confirmation.expected_quantity == Decimal("50")
    assert pending_confirmation.actual_quantity == Decimal("48")
    assert pending_confirmation.quantity_difference == Decimal("-2")
    assert pending_confirmation.compatible is False
    assert pending_confirmation.arrival_entered_by_name == "System User"
    with pytest.raises(ConflictException, match="after warehouse receipt entry"):
        update_expected_arrival(
            db_session,
            stock.stock_unit_id,
            ExpectedArrivalUpdateRequest(
                expected_arrival_date=date(2026, 11, 12),
                reason="This edit must be locked after physical receipt entry.",
            ),
            LAUNCH_ENGINEER_ID,
            actor=ENGINEER,
        )

    with pytest.raises(ValidationException, match="discrepancy reason"):
        supplier_order_service.confirm_arrival(
            db_session,
            created.supplier_order_id,
            SupplierArrivalConfirmRequest(),
            TEST_USER_ID,
            actor=TEAM_LEADER,
        )

    confirmed = supplier_order_service.confirm_arrival(
        db_session,
        created.supplier_order_id,
        SupplierArrivalConfirmRequest(discrepancy_reason="Supplier delivered two metres less."),
        TEST_USER_ID,
        actor=TEAM_LEADER,
    )
    db_session.refresh(stock)
    assert confirmed.status == "CONFIRMED"
    assert stock.status == "WAREHOUSE" and stock.quantity == Decimal("48")
    assert all(
        item.stock_unit_id != stock.stock_unit_id
        for item in get_in_transit_stock(db_session)
    )
    notification = db_session.scalars(select(Notification)).one()
    assert notification.user_id == LAUNCH_ENGINEER_ID
    assert "Verify the material" in notification.message
    movement_types = [
        movement.movement_type
        for movement in db_session.scalars(
            select(StockMovement).where(
                StockMovement.supplier_order_id == created.supplier_order_id
            )
        )
    ]
    assert movement_types == [
        "TRANSIT_DECLARED",
        "ETA_CHANGED",
        "ARRIVAL_ENTERED",
        "SUPPLIER_RECEIPT_CONFIRMED",
    ]


def test_missing_delivery_can_be_recorded_as_zero(db_session, seeded_db):
    material = _material(db_session)
    created = supplier_order_service.create_order(
        db_session, _request(material), LAUNCH_ENGINEER_ID, actor=ENGINEER,
    )
    entered = supplier_order_service.enter_arrival(
        db_session,
        created.supplier_order_id,
        SupplierArrivalEntryRequest(lines=[SupplierArrivalLineInput(
            supplier_order_line_id=created.lines[0].supplier_order_line_id,
            actual_quantity=Decimal("0"),
        )]),
        TEST_USER_ID,
        actor=PERSONNEL,
    )

    assert entered.lines[0].actual_quantity == Decimal("0")
    assert entered.lines[0].quantity_difference == Decimal("-50")
    assert entered.has_discrepancy is True
    pending = next(
        item
        for item in get_in_transit_stock(db_session)
        if item.stock_unit_id == created.lines[0].stock_unit_id
    )
    assert pending.workflow_status == "AWAITING_CONFIRMATION"
    assert pending.actual_quantity == Decimal("0")


def test_manual_reception_summary_history_correction_and_threshold(db_session, seeded_db):
    material = _material(db_session)
    received = record_stock_unit_receptions(
        db_session,
        StockUnitReceptionBatchRequest(
            material_part_number=material,
            quantities=[Decimal("12"), Decimal("8")],
            source_reference="DN-TEST-001",
        ),
        TEST_USER_ID,
        actor=PERSONNEL,
    )
    assert received.stock_unit_count == 2
    assert received.total_quantity == Decimal("20")
    assert all(item.business_unit_id.startswith("SU-") for item in received.items)
    summary = next(item for item in get_stock_summary(db_session) if item.material_part_number == material)
    assert summary.warehouse_quantity == Decimal("20")

    corrected = correct_stock_unit_reception(
        db_session,
        received.items[0].stock_unit_id,
        StockReceptionCorrectionRequest(
            quantity=Decimal("10"),
            reason="Physical recount found two metres less.",
        ),
        TEST_USER_ID,
        actor=TEAM_LEADER,
    )
    assert corrected.quantity == Decimal("10")
    summary = next(item for item in get_stock_summary(db_session) if item.material_part_number == material)
    assert summary.warehouse_quantity == Decimal("18")

    update_material_threshold(
        db_session,
        material,
        MaterialThresholdUpdateRequest(critical_threshold=Decimal("25")),
        LAUNCH_ENGINEER_ID,
        actor=ENGINEER,
    )
    summary = next(item for item in get_stock_summary(db_session) if item.material_part_number == material)
    assert summary.critical_threshold == Decimal("25")
    history = get_stock_history(db_session, material_part_number=material)
    assert [item.movement_type for item in history[:3]] == [
        "RECEPTION_CORRECTED",
        "WAREHOUSE_RECEPTION",
        "WAREHOUSE_RECEPTION",
    ]
    assert all(item.actor_name == "System User" for item in history[:3])


def test_open_order_can_be_modified_and_removed_by_engineering(db_session, seeded_db):
    material = _material(db_session)
    created = supplier_order_service.create_order(
        db_session, _request(material), LAUNCH_ENGINEER_ID, actor=ENGINEER,
    )
    update_request = _request(material, quantity="60", eta=date(2026, 11, 12))
    update_request.lines[0].supplier_order_line_id = created.lines[0].supplier_order_line_id
    updated = supplier_order_service.update_order(
        db_session,
        created.supplier_order_id,
        SupplierOrderUpdateRequest(**update_request.model_dump()),
        LAUNCH_ENGINEER_ID,
        actor=ENGINEER,
    )
    assert updated.lines[0].supplier_order_line_id == created.lines[0].supplier_order_line_id
    assert updated.lines[0].stock_unit_id == created.lines[0].stock_unit_id
    assert updated.lines[0].expected_quantity == Decimal("60")
    assert updated.lines[0].expected_arrival_date == date(2026, 11, 12)
    supplier_order_service.delete_order(
        db_session, created.supplier_order_id, LAUNCH_ENGINEER_ID, actor=ENGINEER,
    )
    assert db_session.get(StockUnit, created.lines[0].stock_unit_id) is None


def test_order_update_revalidates_materials_on_existing_stock_units(db_session, seeded_db):
    material = _material(db_session)
    created = supplier_order_service.create_order(
        db_session, _request(material), LAUNCH_ENGINEER_ID, actor=ENGINEER,
    )
    request = _request(material)
    request.lines[0].material_part_number = "UNKNOWN-MATERIAL"
    with pytest.raises(NotFoundException, match="Unknown material"):
        supplier_order_service.update_order(
            db_session,
            created.supplier_order_id,
            SupplierOrderUpdateRequest(**request.model_dump()),
            LAUNCH_ENGINEER_ID,
            actor=ENGINEER,
        )


def test_roles_cannot_bypass_supplier_arrival_separation(db_session, seeded_db):
    material = _material(db_session)
    with pytest.raises(ForbiddenException):
        supplier_order_service.create_order(
            db_session, _request(material), TEST_USER_ID, actor=PERSONNEL,
        )
    created = supplier_order_service.create_order(
        db_session, _request(material), LAUNCH_ENGINEER_ID, actor=ENGINEER,
    )
    with pytest.raises(ForbiddenException):
        supplier_order_service.confirm_arrival(
            db_session, created.supplier_order_id, SupplierArrivalConfirmRequest(),
            TEST_USER_ID, actor=PERSONNEL,
        )
    with pytest.raises(ConflictException):
        supplier_order_service.confirm_arrival(
            db_session, created.supplier_order_id, SupplierArrivalConfirmRequest(),
            TEST_USER_ID, actor=TEAM_LEADER,
        )
