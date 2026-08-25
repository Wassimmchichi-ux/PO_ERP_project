"""Repository layer for Stock Management."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from decimal import Decimal

from sqlalchemy import func, select, and_, or_
from sqlalchemy.orm import Session

from app.models.stock_unit import StockUnit
from app.models.cutting_consumption import CuttingConsumption
from app.models.material import Material
from app.models.material_type import MaterialType


def get_warehouse_stock_by_material(db: Session) -> dict[str, Decimal]:
    """Returns total warehouse quantity per material_part_number."""
    stmt = (
        select(
            StockUnit.material_part_number,
            func.coalesce(func.sum(StockUnit.quantity), 0).label('total_qty')
        )
        .where(StockUnit.status == 'WAREHOUSE')
        .group_by(StockUnit.material_part_number)
    )
    result = db.execute(stmt).all()
    return {row.material_part_number: row.total_qty for row in result}


def get_production_stock_by_material(db: Session) -> dict[str, Decimal]:
    """Returns production-received WIP quantity per material_part_number."""
    stmt = (
        select(
            StockUnit.material_part_number,
            func.coalesce(func.sum(StockUnit.quantity), 0).label('total_qty')
        )
        .where(StockUnit.status == 'PRODUCTION')
        .group_by(StockUnit.material_part_number)
    )
    result = db.execute(stmt).all()
    return {row.material_part_number: row.total_qty for row in result}


def get_in_transit_stock_by_material(db: Session) -> dict[str, Decimal]:
    """Returns total in transit quantity per material_part_number."""
    stmt = (
        select(
            StockUnit.material_part_number,
            func.coalesce(func.sum(StockUnit.quantity), 0).label('total_qty')
        )
        .where(StockUnit.status == 'IN_TRANSIT')
        .group_by(StockUnit.material_part_number)
    )
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


def get_all_materials(db: Session) -> list[tuple[Material, MaterialType]]:
    """Get all materials with their types for joining."""
    stmt = (
        select(Material, MaterialType)
        .join(MaterialType, Material.material_type_id == MaterialType.material_type_id)
        .order_by(Material.material_part_number)
    )
    return db.execute(stmt).all()  # type: ignore


def get_positive_stock_units_by_status(db: Session, status: str) -> list[StockUnit]:
    """Get positive-quantity stock units for one stock status."""
    stmt = (
        select(StockUnit)
        .where(StockUnit.status == status)
        .where(StockUnit.quantity > 0)
    )
    return db.execute(stmt).scalars().all()


def get_stock_units_by_ids(db: Session, stock_unit_ids: list[int]) -> dict[int, StockUnit]:
    """Get stock units keyed by id."""
    if not stock_unit_ids:
        return {}
    stmt = select(StockUnit).where(StockUnit.stock_unit_id.in_(stock_unit_ids))
    units = db.execute(stmt).scalars().all()
    return {unit.stock_unit_id: unit for unit in units}


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


def get_in_transit_stock_units(db: Session, from_date: Optional[date] = None, to_date: Optional[date] = None) -> list[tuple[StockUnit, Material, MaterialType]]:
    """Get detailed in transit stock units with their materials."""
    stmt = (
        select(StockUnit, Material, MaterialType)
        .join(Material, StockUnit.material_part_number == Material.material_part_number)
        .join(MaterialType, Material.material_type_id == MaterialType.material_type_id)
        .where(StockUnit.status == 'IN_TRANSIT')
    )
    
    if from_date:
        stmt = stmt.where(func.date(StockUnit.expected_arrival_date) >= from_date)
    if to_date:
        stmt = stmt.where(func.date(StockUnit.expected_arrival_date) <= to_date)
        
    stmt = stmt.order_by(StockUnit.expected_arrival_date.asc().nulls_last())
    return db.execute(stmt).all()  # type: ignore


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
