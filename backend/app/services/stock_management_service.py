"""Stock Management Service.

Provides operational queries for warehouse, production (WIP), and in-transit stock.
"""
import logging
import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions.base import ConflictException, NotFoundException, ValidationException
from app.models.audit_log import AuditLog
from app.models.material import Material
from app.models.stock_unit import StockUnit
from app.policies import PolicyActor, policy_engine, system_actor
from app.repositories import stock_repository
from app.policies.rules import is_assignable_stock_owner
from app.schemas.stock import (
    ExpectedArrivalUpdateRequest,
    StockSummaryItem,
    ProductionStockItem,
    InTransitItem,
    MaterialStockDetailResponse,
    StockDashboardStats,
    StockUnitReceptionRequest,
    StockUnitReceptionResponse,
    StockUnitReceptionBatchRequest,
    StockUnitReceptionBatchResponse,
    MaterialThresholdUpdateRequest,
    StockReceptionCorrectionRequest,
    StockMovementItem,
)
from app.services import stock_movement_service

logger = logging.getLogger(__name__)


def _compute_remaining_production(sent: Decimal, consumed: Decimal) -> Decimal:
    """Compute remaining production quantity, ensuring it doesn't drop below zero."""
    remaining = sent - consumed
    if remaining < 0:
        logger.warning("Computed negative remaining production stock! Sent: %s, Consumed: %s. Clamping to 0.", sent, consumed)
        return Decimal('0.0000')
    return remaining


def get_stock_summary(db: Session) -> list[StockSummaryItem]:
    """Get aggregated material availability."""
    warehouse_stock = stock_repository.get_warehouse_stock_by_material(db)
    production_stock = stock_repository.get_production_stock_by_material(db)
    in_transit_stock = stock_repository.get_in_transit_stock_by_material(db)
    consumption = stock_repository.get_cutting_consumption_by_material(db)
    materials = stock_repository.get_all_materials(db)
    
    results = []
    for material, mtype in materials:
        mpn = material.material_part_number
        if not mpn:
            continue
            
        w_qty = warehouse_stock.get(mpn, Decimal('0.0000'))
        p_sent = production_stock.get(mpn, Decimal('0.0000'))
        p_cons = consumption.get(mpn, Decimal('0.0000'))
        p_qty = _compute_remaining_production(p_sent, p_cons)
        t_qty = in_transit_stock.get(mpn, Decimal('0.0000'))
        
        total = w_qty + p_qty
        status = 'AVAILABLE' if total > 0 else 'OUT_OF_STOCK'
        
        # Only include materials that have some stock or transit, or active status
        if total > 0 or t_qty > 0 or material.status == 'Active':
            results.append(StockSummaryItem(
                material_part_number=mpn,
                description=material.description,
                material_type=mtype.name,
                unit=mtype.unit,
                critical_threshold=material.critical_threshold or Decimal("0"),
                unit_price=material.unit_price,
                warehouse_quantity=w_qty,
                production_quantity=p_qty,
                in_transit_quantity=t_qty,
                total_available_quantity=total,
                status=status
            ))
            
    return results


def get_production_stock(db: Session) -> list[ProductionStockItem]:
    """Get production/WIP remaining quantities per material."""
    production_stock = stock_repository.get_production_stock_by_material(db)
    consumption = stock_repository.get_cutting_consumption_by_material(db)
    materials = stock_repository.get_all_materials(db)
    
    results = []
    for material, mtype in materials:
        mpn = material.material_part_number
        if not mpn:
            continue
            
        p_sent = production_stock.get(mpn, Decimal('0.0000'))
        p_cons = consumption.get(mpn, Decimal('0.0000'))
        
        if p_sent > 0 or p_cons > 0:
            remaining = _compute_remaining_production(p_sent, p_cons)
            results.append(ProductionStockItem(
                material_part_number=mpn,
                description=material.description,
                unit=mtype.unit,
                total_sent_to_production=p_sent,
                total_cutting_consumption=p_cons,
                remaining_production_quantity=remaining
            ))
            
    return results


def _build_in_transit_item(
    su,
    material,
    mtype,
    supplier_line=None,
    supplier_order=None,
) -> InTransitItem:
    days = None
    if su.expected_arrival_date:
        delta = su.expected_arrival_date.date() - date.today()
        days = delta.days
        
    expected_quantity = (
        supplier_line.expected_quantity if supplier_line is not None else su.quantity
    )
    actual_quantity = (
        supplier_line.actual_quantity if supplier_line is not None else None
    )
    quantity_difference = (
        actual_quantity - expected_quantity if actual_quantity is not None else None
    )
    workflow_status = "UNLINKED_TRANSIT"
    if supplier_order is not None:
        workflow_status = {
            "OPEN": "IN_TRANSIT",
            "ARRIVAL_ENTERED": "AWAITING_CONFIRMATION",
            "CONFIRMED": "CONFIRMED",
        }.get(supplier_order.status, supplier_order.status)

    return InTransitItem(
        stock_unit_id=su.stock_unit_id,
        stock_unit_reference=su.business_unit_id,
        material_part_number=su.material_part_number,
        description=material.description,
        unit=mtype.unit,
        quantity=su.quantity,
        expected_quantity=expected_quantity,
        actual_quantity=actual_quantity,
        quantity_difference=quantity_difference,
        compatible=(
            actual_quantity == expected_quantity if actual_quantity is not None else None
        ),
        expected_arrival_date=su.expected_arrival_date.date() if su.expected_arrival_date else None,
        days_until_arrival=days,
        status="DELAYED" if days is not None and days < 0 else "ON_TIME",
        workflow_status=workflow_status,
        assigned_user_id=su.user_id,
        assigned_user_name=su.user.full_name if su.user else None,
        assigned_user_role=su.user.role if su.user else None,
        supplier_order_id=supplier_order.supplier_order_id if supplier_order else None,
        supplier_order_line_id=(
            supplier_line.supplier_order_line_id if supplier_line else None
        ),
        stock_unit_kind=supplier_line.stock_unit_kind if supplier_line else None,
        supplier_name=supplier_order.supplier_name if supplier_order else None,
        supplier_reference=supplier_order.supplier_reference if supplier_order else None,
        supplier_order_status=supplier_order.status if supplier_order else None,
        project_id=supplier_order.project_id if supplier_order else None,
        project_code=(
            supplier_order.project.project_code if supplier_order else None
        ),
        project_name=supplier_order.project.name if supplier_order else None,
        arrival_entered_by_name=(
            supplier_line.arrival_entered_by_user.full_name
            if supplier_line is not None and supplier_line.arrival_entered_by_user
            else None
        ),
        arrival_entered_at=(
            supplier_line.arrival_entered_at if supplier_line is not None else None
        ),
    )


def get_in_transit_stock(db: Session, from_date: Optional[date] = None, to_date: Optional[date] = None) -> list[InTransitItem]:
    units = stock_repository.get_in_transit_stock_units(db, from_date, to_date)
    return [
        _build_in_transit_item(su, m, mt, supplier_line, supplier_order)
        for su, m, mt, supplier_line, supplier_order in units
    ]


def get_todays_arrivals(db: Session) -> list[InTransitItem]:
    today = date.today()
    return get_in_transit_stock(db, from_date=today, to_date=today)


def update_expected_arrival(
    db: Session,
    stock_unit_id: int,
    request: ExpectedArrivalUpdateRequest,
    user_id: uuid.UUID,
    *,
    actor: PolicyActor,
) -> InTransitItem:
    """Reschedule an open supplier delivery and record its previous date and reason."""
    policy_engine.require(actor, "stock.transit.write")
    stock_unit = db.execute(
        select(StockUnit).where(StockUnit.stock_unit_id == stock_unit_id).with_for_update()
    ).scalar_one_or_none()
    if stock_unit is None:
        raise NotFoundException(f"StockUnit {stock_unit_id} not found.")
    if stock_unit.status != "IN_TRANSIT":
        raise ConflictException("Only in-transit stock can have its expected arrival date changed.")
    previous_date = stock_unit.expected_arrival_date.date() if stock_unit.expected_arrival_date else None
    material_info = stock_repository.get_material_with_type(db, stock_unit.material_part_number)
    if material_info is None:
        raise NotFoundException(f"Material {stock_unit.material_part_number} not found.")
    supplier_line = stock_repository.get_supplier_order_line_for_stock_unit(db, stock_unit_id)
    if supplier_line is not None and supplier_line.order.status != "OPEN":
        raise ConflictException(
            "Expected arrival cannot be changed after warehouse receipt entry."
        )
    if previous_date != request.expected_arrival_date:
        stock_unit.expected_arrival_date = datetime.combine(request.expected_arrival_date, datetime.min.time())
        stock_unit.updated_at = datetime.now()
        if supplier_line is not None:
            supplier_line.expected_arrival_date = request.expected_arrival_date
            supplier_line.order.updated_at = stock_unit.updated_at
        db.add(AuditLog(
            user_id=user_id,
            action="UPDATE_EXPECTED_ARRIVAL",
            entity_type="StockUnit",
            entity_id=stock_unit_id,
            timestamp=stock_unit.updated_at,
            reason=request.reason,
            details=json.dumps({
                "previous_expected_arrival_date": previous_date.isoformat() if previous_date else None,
                "expected_arrival_date": request.expected_arrival_date.isoformat(),
                "actor_role": actor.role,
            }),
        ))
        stock_movement_service.record_movement(
            db,
            material_part_number=stock_unit.material_part_number,
            movement_type="ETA_CHANGED",
            quantity_change=Decimal("0"),
            actor_user_id=user_id,
            stock_unit_id=stock_unit.stock_unit_id,
            supplier_order_id=supplier_line.supplier_order_id if supplier_line else None,
            stock_unit_reference=stock_unit.business_unit_id,
            source_reference=(
                supplier_line.order.supplier_reference if supplier_line else None
            ),
            from_status="IN_TRANSIT",
            to_status="IN_TRANSIT",
            reason=request.reason,
            note=(
                f"Expected arrival changed from {previous_date or 'unset'} "
                f"to {request.expected_arrival_date}."
            ),
            occurred_at=stock_unit.updated_at,
        )
    db.commit()
    supplier_order = supplier_line.order if supplier_line is not None else None
    return _build_in_transit_item(
        stock_unit, *material_info, supplier_line, supplier_order
    )


def get_material_stock_detail(db: Session, material_part_number: str) -> MaterialStockDetailResponse:
    mat_info = stock_repository.get_material_with_type(db, material_part_number)
    if not mat_info:
        raise NotFoundException(f"Material {material_part_number} not found.")
        
    material, mtype = mat_info
    warehouse = stock_repository.get_stock_quantity_by_material_and_statuses(
        db,
        material_part_number,
        ['WAREHOUSE'],
    )
    prod_sent = stock_repository.get_stock_quantity_by_material_and_statuses(
        db,
        material_part_number,
        ['PRODUCTION'],
    )
    in_transit = stock_repository.get_stock_quantity_by_material_and_statuses(
        db,
        material_part_number,
        ['IN_TRANSIT'],
    )
    consumed = stock_repository.get_cutting_consumption_for_material(db, material_part_number)
    
    prod_rem = _compute_remaining_production(prod_sent, consumed)
    
    return MaterialStockDetailResponse(
        material_part_number=material_part_number,
        description=material.description,
        unit=mtype.unit,
        warehouse=warehouse,
        production=prod_rem,
        in_transit=in_transit,
        total_available=warehouse + prod_rem,
        total_consumed=consumed
    )


def get_dashboard_stats(db: Session) -> StockDashboardStats:
    mat_in_wh = stock_repository.count_distinct_materials_by_status(db, ['WAREHOUSE'])
    mat_in_prod = stock_repository.count_distinct_materials_by_status(db, ['PRODUCTION'])
    
    all_in_transit = stock_repository.count_in_transit_entries(db)
    today = stock_repository.count_in_transit_entries(db, target_date=date.today())
    future = stock_repository.count_in_transit_entries(db, future_only=True)
    
    return StockDashboardStats(
        total_materials_in_warehouse=mat_in_wh,
        total_materials_in_production=mat_in_prod,
        total_in_transit_entries=all_in_transit,
        todays_expected_arrivals_count=today,
        upcoming_arrivals_count=future
    )


def confirm_production_handover(
    db: Session,
    stock_unit_id: int,
    handover_document_id: int,
    *,
    actor: Optional[PolicyActor] = None,
    actor_user_id: uuid.UUID | None = None,
) -> MaterialStockDetailResponse:
    """Confirm production received an issued stock unit using a signed handover document."""
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "handover.confirm")

    stock_units = stock_repository.get_stock_units_by_ids(db, [stock_unit_id])
    stock_unit = stock_units.get(stock_unit_id)
    if stock_unit is None:
        raise NotFoundException(f"StockUnit {stock_unit_id} not found.")

    try:
        stock_repository.mark_stock_unit_received_by_production(
            stock_unit,
            handover_document_id=handover_document_id,
        )
    except ValueError as exc:
        from app.exceptions.base import ValidationException
        raise ValidationException(str(exc)) from exc

    if actor_user_id is None:
        if acting_actor.user_id is not None:
            actor_user_id = acting_actor.user_id
        else:
            from app.repositories.bom_repository import _get_system_user
            actor_user_id = _get_system_user(db)
    stock_movement_service.record_movement(
        db,
        material_part_number=stock_unit.material_part_number,
        movement_type="PRODUCTION_RECEIVED",
        quantity_change=stock_unit.quantity,
        actor_user_id=actor_user_id,
        stock_unit_id=stock_unit.stock_unit_id,
        stock_unit_reference=stock_unit.business_unit_id,
        from_status="ISSUED_TO_PRODUCTION",
        to_status="PRODUCTION",
        source_reference=str(handover_document_id),
        note="Signed production handover confirmed.",
    )

    db.commit()
    return get_material_stock_detail(db, stock_unit.material_part_number)


def record_stock_unit_reception(
    db: Session,
    request: StockUnitReceptionRequest,
    reception_user_id,
    *,
    actor: Optional[PolicyActor] = None,
) -> StockUnitReceptionResponse:
    """Record a warehouse/in-transit stock unit and optional launch owner."""
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "stock.receive")

    if request.status not in {"WAREHOUSE", "IN_TRANSIT"}:
        raise ValidationException("Stock reception status must be WAREHOUSE or IN_TRANSIT.")
    if request.status == "IN_TRANSIT" and request.expected_arrival_date is None:
        raise ValidationException("expected_arrival_date is required for IN_TRANSIT stock.")

    if stock_repository.get_material_with_type(db, request.material_part_number) is None:
        raise NotFoundException(f"Material {request.material_part_number} not found.")
    if request.business_unit_id and db.scalar(
        select(StockUnit.stock_unit_id).where(
            StockUnit.business_unit_id == request.business_unit_id.strip()
        )
    ) is not None:
        raise ConflictException(f"Stock-unit identifier {request.business_unit_id} already exists.")

    assigned_user = None
    if request.assigned_user_id is not None:
        assigned_user = stock_repository.get_user(db, request.assigned_user_id)
        if assigned_user is None:
            raise NotFoundException(f"Assigned user {request.assigned_user_id} not found.")
        policy_engine.require(acting_actor, "stock.assign_owner")
        if not is_assignable_stock_owner(assigned_user.role):
            raise ValidationException("Stock can only be affected to a launch engineer or launch manager.")

    stock_unit = stock_repository.create_stock_unit_reception(
        db,
        material_part_number=request.material_part_number,
        quantity=request.quantity,
        status=request.status,
        expected_arrival_date=request.expected_arrival_date,
        assigned_user_id=request.assigned_user_id,
        reception_user_id=reception_user_id,
        business_unit_id=request.business_unit_id.strip() if request.business_unit_id else None,
    )
    if stock_unit.business_unit_id is None:
        stock_unit.business_unit_id = f"SU-{stock_unit.stock_unit_id:08d}"
    stock_movement_service.record_movement(
        db,
        material_part_number=stock_unit.material_part_number,
        movement_type=(
            "WAREHOUSE_RECEPTION" if stock_unit.status == "WAREHOUSE" else "TRANSIT_DECLARED"
        ),
        quantity_change=stock_unit.quantity,
        actor_user_id=reception_user_id,
        stock_unit_id=stock_unit.stock_unit_id,
        stock_unit_reference=stock_unit.business_unit_id,
        source_reference=(request.source_reference or "").strip() or None,
        to_status=stock_unit.status,
        note="Manual warehouse entry.",
        occurred_at=stock_unit.created_at,
    )
    db.commit()
    db.refresh(stock_unit)

    return StockUnitReceptionResponse(
        stock_unit_id=stock_unit.stock_unit_id,
        business_unit_id=stock_unit.business_unit_id,
        material_part_number=stock_unit.material_part_number,
        quantity=stock_unit.quantity,
        status=stock_unit.status,
        expected_arrival_date=stock_unit.expected_arrival_date,
        assigned_user_id=stock_unit.user_id,
        assigned_user_name=assigned_user.full_name if assigned_user else None,
        assigned_user_role=assigned_user.role if assigned_user else None,
        created_at=stock_unit.created_at,
    )


def update_material_threshold(
    db: Session,
    material_part_number: str,
    request: MaterialThresholdUpdateRequest,
    user_id: uuid.UUID,
    *,
    actor: PolicyActor,
) -> StockSummaryItem:
    policy_engine.require(actor, "stock.threshold.write")
    material = db.scalar(
        select(Material)
        .where(Material.material_part_number == material_part_number)
        .with_for_update()
    )
    if material is None:
        raise NotFoundException(f"Material {material_part_number} not found.")
    previous = material.critical_threshold
    material.critical_threshold = request.critical_threshold
    db.add(AuditLog(
        user_id=user_id,
        action="UPDATE_MATERIAL_CRITICAL_THRESHOLD",
        entity_type="Material",
        entity_id=material.id,
        timestamp=datetime.now(),
        details=json.dumps({
            "material_part_number": material_part_number,
            "previous": str(previous) if previous is not None else None,
            "current": str(request.critical_threshold),
        }),
    ))
    db.commit()
    return next(
        item for item in get_stock_summary(db)
        if item.material_part_number == material_part_number
    )


def record_stock_unit_receptions(
    db: Session,
    request: StockUnitReceptionBatchRequest,
    reception_user_id: uuid.UUID,
    *,
    actor: PolicyActor,
) -> StockUnitReceptionBatchResponse:
    """Receive several physical stock units atomically under one delivery reference."""
    policy_engine.require(actor, "stock.receive")
    if stock_repository.get_material_with_type(db, request.material_part_number) is None:
        raise NotFoundException(f"Material {request.material_part_number} not found.")
    assigned_user = None
    if request.assigned_user_id is not None:
        assigned_user = stock_repository.get_user(db, request.assigned_user_id)
        if assigned_user is None:
            raise NotFoundException(f"Assigned user {request.assigned_user_id} not found.")
        policy_engine.require(actor, "stock.assign_owner")
        if not is_assignable_stock_owner(assigned_user.role):
            raise ValidationException("Stock can only be affected to a launch engineer or launch manager.")

    created: list[StockUnit] = []
    source_reference = (request.source_reference or "").strip() or None
    for quantity in request.quantities:
        stock_unit = stock_repository.create_stock_unit_reception(
            db,
            material_part_number=request.material_part_number,
            quantity=quantity,
            status="WAREHOUSE",
            expected_arrival_date=None,
            assigned_user_id=request.assigned_user_id,
            reception_user_id=reception_user_id,
        )
        stock_unit.business_unit_id = f"SU-{stock_unit.stock_unit_id:08d}"
        stock_movement_service.record_movement(
            db,
            material_part_number=stock_unit.material_part_number,
            movement_type="WAREHOUSE_RECEPTION",
            quantity_change=stock_unit.quantity,
            actor_user_id=reception_user_id,
            stock_unit_id=stock_unit.stock_unit_id,
            stock_unit_reference=stock_unit.business_unit_id,
            source_reference=source_reference,
            to_status="WAREHOUSE",
            note="Manual warehouse batch reception.",
            occurred_at=stock_unit.created_at,
        )
        created.append(stock_unit)
    db.commit()
    responses = [
        StockUnitReceptionResponse(
            stock_unit_id=item.stock_unit_id,
            business_unit_id=item.business_unit_id,
            material_part_number=item.material_part_number,
            quantity=item.quantity,
            status=item.status,
            expected_arrival_date=item.expected_arrival_date,
            assigned_user_id=item.user_id,
            assigned_user_name=assigned_user.full_name if assigned_user else None,
            assigned_user_role=assigned_user.role if assigned_user else None,
            created_at=item.created_at,
        )
        for item in created
    ]
    return StockUnitReceptionBatchResponse(
        items=responses,
        stock_unit_count=len(responses),
        total_quantity=sum((item.quantity for item in created), Decimal("0")),
    )


def correct_stock_unit_reception(
    db: Session,
    stock_unit_id: int,
    request: StockReceptionCorrectionRequest,
    user_id: uuid.UUID,
    *,
    actor: PolicyActor,
) -> StockUnitReceptionResponse:
    policy_engine.require(actor, "stock.reception.correct")
    stock_unit = db.execute(
        select(StockUnit)
        .where(StockUnit.stock_unit_id == stock_unit_id)
        .with_for_update()
    ).scalar_one_or_none()
    if stock_unit is None:
        raise NotFoundException(f"StockUnit {stock_unit_id} not found.")
    if stock_unit.status != "WAREHOUSE" or stock_unit.reception_date is None:
        raise ConflictException("Only a received warehouse stock unit can be corrected.")
    if stock_repository.get_supplier_order_line_for_stock_unit(db, stock_unit_id) is not None:
        raise ConflictException(
            "Supplier-order receipts must be reconciled through the supplier arrival workflow."
        )
    if (
        datetime.now() - stock_unit.reception_date > timedelta(hours=24)
        and actor.normalized_role not in {"ADMIN", "LAUNCH_MANAGER", "LAUNCH_ENGINEER"}
    ):
        raise ConflictException(
            "The 24-hour correction window is closed; launch engineering must review the correction."
        )
    previous = stock_unit.quantity
    delta = request.quantity - previous
    stock_unit.quantity = request.quantity
    stock_unit.updated_at = datetime.now()
    stock_movement_service.record_movement(
        db,
        material_part_number=stock_unit.material_part_number,
        movement_type="RECEPTION_CORRECTED",
        quantity_change=delta,
        actor_user_id=user_id,
        stock_unit_id=stock_unit.stock_unit_id,
        stock_unit_reference=stock_unit.business_unit_id,
        from_status="WAREHOUSE",
        to_status="WAREHOUSE",
        reason=request.reason,
        note=f"Reception quantity corrected from {previous} to {request.quantity}.",
        occurred_at=stock_unit.updated_at,
    )
    db.add(AuditLog(
        user_id=user_id,
        action="CORRECT_STOCK_RECEPTION",
        entity_type="StockUnit",
        entity_id=stock_unit.stock_unit_id,
        timestamp=stock_unit.updated_at,
        reason=request.reason,
        details=json.dumps({"previous": str(previous), "current": str(request.quantity)}),
    ))
    db.commit()
    db.refresh(stock_unit)
    assigned_user = stock_repository.get_user(db, stock_unit.user_id) if stock_unit.user_id else None
    return StockUnitReceptionResponse(
        stock_unit_id=stock_unit.stock_unit_id,
        business_unit_id=stock_unit.business_unit_id,
        material_part_number=stock_unit.material_part_number,
        quantity=stock_unit.quantity,
        status=stock_unit.status,
        expected_arrival_date=stock_unit.expected_arrival_date,
        assigned_user_id=stock_unit.user_id,
        assigned_user_name=assigned_user.full_name if assigned_user else None,
        assigned_user_role=assigned_user.role if assigned_user else None,
        created_at=stock_unit.created_at,
    )


def get_stock_history(
    db: Session,
    *,
    movement_type: str | None = None,
    material_part_number: str | None = None,
    limit: int = 500,
) -> list[StockMovementItem]:
    return stock_movement_service.list_movements(
        db,
        movement_type=movement_type,
        material_part_number=material_part_number,
        limit=limit,
    )
