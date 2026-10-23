"""Repository layer for Stock Management."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional
from decimal import Decimal

from sqlalchemy import func, select, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.stock_unit import StockUnit
from app.models.cutting_consumption import CuttingConsumption
from app.models.material import Material
from app.models.material_type import MaterialType
from app.models.user import User
from app.models.stock_allocation import StockAllocation
from app.models.simulation import Simulation
from app.models.supplier_material_order import SupplierMaterialOrder
from app.models.supplier_material_order_line import SupplierMaterialOrderLine
from app.policies.rules import is_assignable_stock_owner


def get_warehouse_stock_by_material(
    db: Session,
    *,
    assigned_user_id: uuid.UUID | None = None,
    assigned_only: bool = False,
    include_global_stock: bool = False,
) -> dict[str, Decimal]:
    """Returns total warehouse quantity per material_part_number."""
    stmt = (
        select(
            StockUnit.material_part_number,
            func.coalesce(func.sum(StockUnit.quantity), 0).label('total_qty')
        )
        .where(StockUnit.status == 'WAREHOUSE')
    )
    if assigned_only:
        stmt = _filter_by_stock_owner_scope(stmt, assigned_user_id, include_global_stock)
    stmt = stmt.group_by(StockUnit.material_part_number)
    result = db.execute(stmt).all()
    return {row.material_part_number: row.total_qty for row in result}


def get_production_stock_by_material(
    db: Session,
    *,
    assigned_user_id: uuid.UUID | None = None,
    assigned_only: bool = False,
    include_global_stock: bool = False,
) -> dict[str, Decimal]:
    """Returns production-received WIP quantity per material_part_number."""
    stmt = (
        select(
            StockUnit.material_part_number,
            func.coalesce(func.sum(StockUnit.quantity), 0).label('total_qty')
        )
        .where(StockUnit.status == 'PRODUCTION')
    )
    if assigned_only:
        stmt = _filter_by_stock_owner_scope(stmt, assigned_user_id, include_global_stock)
    stmt = stmt.group_by(StockUnit.material_part_number)
    result = db.execute(stmt).all()
    return {row.material_part_number: row.total_qty for row in result}


def get_in_transit_stock_by_material(
    db: Session,
    *,
    assigned_user_id: uuid.UUID | None = None,
    assigned_only: bool = False,
    include_global_stock: bool = False,
    target_date: date | None = None,
) -> dict[str, Decimal]:
    """Returns total in transit quantity per material_part_number."""
    stmt = (
        select(
            StockUnit.material_part_number,
            func.coalesce(func.sum(StockUnit.quantity), 0).label('total_qty')
        )
        .where(StockUnit.status == 'IN_TRANSIT')
        .where(StockUnit.quantity > 0)
    )
    if target_date is not None:
        stmt = stmt.where(func.date(StockUnit.expected_arrival_date) <= target_date)
    if assigned_only:
        stmt = _filter_by_stock_owner_scope(stmt, assigned_user_id, include_global_stock)
    stmt = stmt.group_by(StockUnit.material_part_number)
    result = db.execute(stmt).all()
    return {row.material_part_number: row.total_qty for row in result}


def get_cutting_consumption_by_material(db: Session) -> dict[str, Decimal]:
    """Returns total consumed quantity per material_part_number."""
    stmt = (
        select(
            CuttingConsumption.material_part_number,
            func.coalesce(func.sum(CuttingConsumption.quantity_consumed), 0).label('total_consumed')
        )
        .group_by(CuttingConsumption.material_part_number)
    )
    result = db.execute(stmt).all()
    return {row.material_part_number: row.total_consumed for row in result}


def get_cutting_consumption_by_stock_unit(db: Session) -> dict[int, Decimal]:
    """Return posted CutMan usage keyed by the resolved business stock unit."""
    stmt = (
        select(
            CuttingConsumption.stock_unit_id,
            func.coalesce(func.sum(CuttingConsumption.quantity_consumed), 0),
        )
        .where(CuttingConsumption.stock_unit_id.is_not(None))
        .group_by(CuttingConsumption.stock_unit_id)
    )
    return {stock_unit_id: quantity for stock_unit_id, quantity in db.execute(stmt).all()}


def get_unassigned_cutting_consumption_by_material(db: Session) -> dict[str, Decimal]:
    """Retain compatibility for historical consumption without a nesting identifier link."""
    stmt = (
        select(
            CuttingConsumption.material_part_number,
            func.coalesce(func.sum(CuttingConsumption.quantity_consumed), 0),
        )
        .where(CuttingConsumption.stock_unit_id.is_(None))
        .group_by(CuttingConsumption.material_part_number)
    )
    return {part: quantity for part, quantity in db.execute(stmt).all()}


def get_reserved_quantities_by_stock_unit(db: Session) -> dict[int, Decimal]:
    """Return active saved-simulation reservations keyed by physical stock unit."""
    stmt = (
        select(
            StockAllocation.stock_unit_id,
            func.coalesce(func.sum(StockAllocation.allocated_quantity), 0),
        )
        .join(Simulation, Simulation.simulation_id == StockAllocation.simulation_id)
        .where(StockAllocation.allocation_type == "SIMULATION")
        .where(StockAllocation.status == "RESERVED")
        .where(Simulation.workflow_status.in_(("AWAITING_DOCUMENT", "READY")))
        .where(
            or_(
                Simulation.document_due_at.is_(None),
                Simulation.document_due_at > datetime.now(),
            )
        )
        .group_by(StockAllocation.stock_unit_id)
    )
    return {stock_unit_id: quantity for stock_unit_id, quantity in db.execute(stmt).all()}


def get_all_materials(db: Session) -> list[tuple[Material, MaterialType]]:
    """Get all materials with their types for joining."""
    stmt = (
        select(Material, MaterialType)
        .join(MaterialType, Material.material_type_id == MaterialType.material_type_id)
        .order_by(Material.material_part_number)
    )
    return db.execute(stmt).all()  # type: ignore


def get_positive_stock_units_by_status(
    db: Session,
    status: str,
    *,
    assigned_user_id: uuid.UUID | None = None,
    assigned_only: bool = False,
    include_global_stock: bool = False,
    target_date: date | None = None,
) -> list[StockUnit]:
    """Get positive-quantity stock units for one stock status."""
    stmt = (
        select(StockUnit)
        .options(joinedload(StockUnit.user))
        .where(StockUnit.status == status)
        .where(StockUnit.quantity > 0)
        .order_by(StockUnit.stock_unit_id)
    )
    if target_date is not None:
        stmt = stmt.where(func.date(StockUnit.expected_arrival_date) <= target_date)
    if assigned_only:
        stmt = _filter_by_stock_owner_scope(stmt, assigned_user_id, include_global_stock)
    return db.execute(stmt).scalars().all()


def _filter_by_stock_owner_scope(stmt, assigned_user_id: uuid.UUID | None, include_global_stock: bool):
    if include_global_stock:
        return stmt.where(or_(StockUnit.user_id == assigned_user_id, StockUnit.user_id.is_(None)))
    return stmt.where(StockUnit.user_id == assigned_user_id)


def get_stock_units_by_ids(
    db: Session,
    stock_unit_ids: list[int],
    *,
    for_update: bool = False,
) -> dict[int, StockUnit]:
    """Get stock units keyed by id."""
    if not stock_unit_ids:
        return {}
    stmt = (
        select(StockUnit)
        .where(StockUnit.stock_unit_id.in_(stock_unit_ids))
        .order_by(StockUnit.stock_unit_id)
    )
    if for_update:
        stmt = stmt.with_for_update()
    else:
        stmt = stmt.options(joinedload(StockUnit.user))
    units = db.execute(stmt).scalars().all()
    return {unit.stock_unit_id: unit for unit in units}


def lock_stock_units_for_materials(db: Session, material_part_numbers: list[str]) -> None:
    """Serialize reservations competing for any stock of the same materials."""
    if not material_part_numbers:
        return
    db.execute(
        select(StockUnit.stock_unit_id)
        .where(StockUnit.material_part_number.in_(set(material_part_numbers)))
        .order_by(StockUnit.stock_unit_id)
        .with_for_update()
    ).all()


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    """Return a user by id."""
    return db.get(User, user_id)


def is_affectable_stock_owner(user: User) -> bool:
    """Return whether stock can be affected to this user."""
    return is_assignable_stock_owner(user.role)


def create_stock_unit_reception(
    db: Session,
    *,
    material_part_number: str,
    quantity: Decimal,
    status: str,
    expected_arrival_date: datetime | None,
    assigned_user_id: uuid.UUID | None,
    reception_user_id: uuid.UUID | None,
    business_unit_id: str | None = None,
) -> StockUnit:
    """Create a stock unit received or recorded by warehouse."""
    now = datetime.now()
    stock_unit = StockUnit(
        business_unit_id=business_unit_id,
        material_part_number=material_part_number,
        quantity=quantity,
        status=status,
        expected_arrival_date=expected_arrival_date,
        reception_date=now,
        reception_username=reception_user_id,
        created_at=now,
        updated_at=now,
        user_id=assigned_user_id,
    )
    db.add(stock_unit)
    db.flush()
    return stock_unit


def is_stock_unit_available_for_quantity(stock_unit: StockUnit, quantity: Decimal) -> bool:
    """Return whether the current stock unit can satisfy a launch allocation."""
    return stock_unit.status in ('WAREHOUSE', 'IN_TRANSIT') and stock_unit.quantity >= quantity


def issue_stock_unit_to_production(
    db: Session,
    stock_unit: StockUnit,
    quantity: Decimal,
    *,
    is_whole_issue: bool,
) -> StockUnit:
    """Apply a launch issue to a stock unit."""
    if not is_stock_unit_available_for_quantity(stock_unit, quantity):
        raise ValueError(f"StockUnit {stock_unit.stock_unit_id} is not available for quantity {quantity}.")

    now = datetime.now()
    if is_whole_issue:
        stock_unit.status = 'ISSUED_TO_PRODUCTION'
        stock_unit.issued_to_production_at = now
        stock_unit.updated_at = now
        return stock_unit

    if stock_unit.quantity == quantity:
        stock_unit.status = 'ISSUED_TO_PRODUCTION'
        stock_unit.issued_to_production_at = now
        stock_unit.updated_at = now
        return stock_unit

    stock_unit.quantity -= quantity
    stock_unit.updated_at = now
    issued_stock_unit = StockUnit(
        material_part_number=stock_unit.material_part_number,
        quantity=quantity,
        status='ISSUED_TO_PRODUCTION',
        parent_stock_unit_id=stock_unit.stock_unit_id,
        issued_to_production_at=now,
        created_at=now,
        updated_at=now,
        user_id=stock_unit.user_id,
    )
    db.add(issued_stock_unit)
    db.flush()
    return issued_stock_unit


def mark_stock_unit_received_by_production(
    stock_unit: StockUnit,
    *,
    handover_document_id: int,
) -> None:
    """Mark an issued stock unit as received by production after signed handover."""
    if stock_unit.status != 'ISSUED_TO_PRODUCTION':
        raise ValueError(
            f"StockUnit {stock_unit.stock_unit_id} must be ISSUED_TO_PRODUCTION before handover."
        )
    now = datetime.now()
    stock_unit.status = 'PRODUCTION'
    stock_unit.handover_document_id = handover_document_id
    stock_unit.received_by_production_at = now
    stock_unit.updated_at = now


def get_material_with_type(db: Session, material_part_number: str) -> Optional[tuple[Material, MaterialType]]:
    """Get one material and its material type."""
    stmt = (
        select(Material, MaterialType)
        .join(MaterialType, Material.material_type_id == MaterialType.material_type_id)
        .where(Material.material_part_number == material_part_number)
    )
    return db.execute(stmt).first()


def get_stock_quantity_by_material_and_statuses(
    db: Session,
    material_part_number: str,
    statuses: list[str],
) -> Decimal:
    """Return summed stock quantity for one material across the requested statuses."""
    stmt = (
        select(func.coalesce(func.sum(StockUnit.quantity), 0))
        .where(StockUnit.material_part_number == material_part_number)
        .where(StockUnit.status.in_(statuses))
    )
    return db.execute(stmt).scalar() or Decimal('0')


def get_cutting_consumption_for_material(db: Session, material_part_number: str) -> Decimal:
    """Return total cutting consumption for one material."""
    stmt = (
        select(func.coalesce(func.sum(CuttingConsumption.quantity_consumed), 0))
        .where(CuttingConsumption.material_part_number == material_part_number)
    )
    return db.execute(stmt).scalar() or Decimal('0')


def get_in_transit_stock_units(
    db: Session,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> list[
    tuple[
        StockUnit,
        Material,
        MaterialType,
        SupplierMaterialOrderLine | None,
        SupplierMaterialOrder | None,
    ]
]:
    """Get detailed transit units and their optional supplier-order source."""
    stmt = (
        select(
            StockUnit,
            Material,
            MaterialType,
            SupplierMaterialOrderLine,
            SupplierMaterialOrder,
        )
        .options(
            joinedload(StockUnit.user),
            joinedload(SupplierMaterialOrderLine.arrival_entered_by_user),
            joinedload(SupplierMaterialOrder.project),
        )
        .join(Material, StockUnit.material_part_number == Material.material_part_number)
        .join(MaterialType, Material.material_type_id == MaterialType.material_type_id)
        .outerjoin(
            SupplierMaterialOrderLine,
            SupplierMaterialOrderLine.stock_unit_id == StockUnit.stock_unit_id,
        )
        .outerjoin(
            SupplierMaterialOrder,
            SupplierMaterialOrder.supplier_order_id
            == SupplierMaterialOrderLine.supplier_order_id,
        )
        .where(StockUnit.status == 'IN_TRANSIT')
    )
    
    if from_date:
        stmt = stmt.where(func.date(StockUnit.expected_arrival_date) >= from_date)
    if to_date:
        stmt = stmt.where(func.date(StockUnit.expected_arrival_date) <= to_date)
        
    stmt = stmt.order_by(StockUnit.expected_arrival_date.asc().nulls_last())
    return db.execute(stmt).all()  # type: ignore


def get_supplier_order_line_for_stock_unit(
    db: Session,
    stock_unit_id: int,
) -> SupplierMaterialOrderLine | None:
    """Return the supplier-order line that declared a stock unit, when applicable."""
    return db.execute(
        select(SupplierMaterialOrderLine)
        .options(
            joinedload(SupplierMaterialOrderLine.order).joinedload(
                SupplierMaterialOrder.project
            ),
            joinedload(SupplierMaterialOrderLine.arrival_entered_by_user),
        )
        .where(SupplierMaterialOrderLine.stock_unit_id == stock_unit_id)
    ).scalar_one_or_none()


def count_distinct_materials_by_status(db: Session, status_list: list[str]) -> int:
    """Count how many distinct materials have stock in the given statuses."""
    stmt = (
        select(func.count(func.distinct(StockUnit.material_part_number)))
        .where(StockUnit.status.in_(status_list))
        .where(StockUnit.quantity > 0)
    )
    return db.execute(stmt).scalar() or 0


def count_in_transit_entries(db: Session, target_date: Optional[date] = None, future_only: bool = False) -> int:
    """Count in-transit entries, optionally for a specific date or future."""
    stmt = select(func.count(StockUnit.stock_unit_id)).where(StockUnit.status == 'IN_TRANSIT')
    
    if target_date:
        stmt = stmt.where(func.date(StockUnit.expected_arrival_date) == target_date)
    elif future_only:
        stmt = stmt.where(func.date(StockUnit.expected_arrival_date) > func.current_date())
        
    return db.execute(stmt).scalar() or 0
