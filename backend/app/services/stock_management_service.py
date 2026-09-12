"""Stock Management Service.

Provides operational queries for warehouse, production (WIP), and in-transit stock.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.exceptions.base import NotFoundException, ValidationException
from app.repositories import stock_repository
from app.schemas.stock import (
    StockSummaryItem,
    ProductionStockItem,
    InTransitItem,
    MaterialStockDetailResponse,
    StockDashboardStats,
    StockUnitReceptionRequest,
    StockUnitReceptionResponse,
)

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
                unit=mtype.unit,
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


def _build_in_transit_item(su, material, mtype) -> InTransitItem:
    days = None
    if su.expected_arrival_date:
        delta = su.expected_arrival_date.date() - date.today()
        days = delta.days
        
    return InTransitItem(
        stock_unit_id=su.stock_unit_id,
        material_part_number=su.material_part_number,
        description=material.description,
        unit=mtype.unit,
        quantity=su.quantity,
        expected_arrival_date=su.expected_arrival_date.date() if su.expected_arrival_date else None,
        days_until_arrival=days,
        status="DELAYED" if days is not None and days < 0 else "ON_TIME",
        assigned_user_id=su.user_id,
        assigned_user_name=su.user.full_name if su.user else None,
        assigned_user_role=su.user.role if su.user else None,
    )


def get_in_transit_stock(db: Session, from_date: Optional[date] = None, to_date: Optional[date] = None) -> list[InTransitItem]:
    units = stock_repository.get_in_transit_stock_units(db, from_date, to_date)
    return [_build_in_transit_item(su, m, mt) for su, m, mt in units]


def get_todays_arrivals(db: Session) -> list[InTransitItem]:
    today = date.today()
    return get_in_transit_stock(db, from_date=today, to_date=today)


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


def confirm_production_handover(db: Session, stock_unit_id: int, handover_document_id: int) -> MaterialStockDetailResponse:
    """Confirm production received an issued stock unit using a signed handover document."""
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

    db.commit()
    return get_material_stock_detail(db, stock_unit.material_part_number)


def record_stock_unit_reception(
    db: Session,
    request: StockUnitReceptionRequest,
    reception_user_id,
) -> StockUnitReceptionResponse:
    """Record a warehouse/in-transit stock unit and optional launch owner."""
    if request.status not in {"WAREHOUSE", "IN_TRANSIT"}:
        raise ValidationException("Stock reception status must be WAREHOUSE or IN_TRANSIT.")
    if request.status == "IN_TRANSIT" and request.expected_arrival_date is None:
        raise ValidationException("expected_arrival_date is required for IN_TRANSIT stock.")

    if stock_repository.get_material_with_type(db, request.material_part_number) is None:
        raise NotFoundException(f"Material {request.material_part_number} not found.")

    assigned_user = None
    if request.assigned_user_id is not None:
        assigned_user = stock_repository.get_user(db, request.assigned_user_id)
        if assigned_user is None:
            raise NotFoundException(f"Assigned user {request.assigned_user_id} not found.")
        if not stock_repository.is_affectable_stock_owner(assigned_user):
            raise ValidationException("Stock can only be affected to a launch engineer or launch manager.")

    stock_unit = stock_repository.create_stock_unit_reception(
        db,
        material_part_number=request.material_part_number,
        quantity=request.quantity,
        status=request.status,
        expected_arrival_date=request.expected_arrival_date,
        assigned_user_id=request.assigned_user_id,
        reception_user_id=reception_user_id,
    )
    db.commit()
    db.refresh(stock_unit)

    return StockUnitReceptionResponse(
        stock_unit_id=stock_unit.stock_unit_id,
        material_part_number=stock_unit.material_part_number,
        quantity=stock_unit.quantity,
        status=stock_unit.status,
        expected_arrival_date=stock_unit.expected_arrival_date,
        assigned_user_id=stock_unit.user_id,
        assigned_user_name=assigned_user.full_name if assigned_user else None,
        assigned_user_role=assigned_user.role if assigned_user else None,
        created_at=stock_unit.created_at,
    )
