"""Append-only stock movement ledger helpers."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Material, StockMovement
from app.repositories import stock_repository
from app.schemas.stock import StockMovementItem


def record_movement(
    db: Session,
    *,
    material_part_number: str,
    movement_type: str,
    quantity_change: Decimal,
    actor_user_id: uuid.UUID,
    stock_unit_id: int | None = None,
    supplier_order_id: int | None = None,
    stock_unit_reference: str | None = None,
    source_reference: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    reason: str | None = None,
    note: str | None = None,
    occurred_at: datetime | None = None,
) -> StockMovement:
    """Add one immutable ledger row inside the caller's transaction."""
    db.flush()
    warehouse_after = stock_repository.get_stock_quantity_by_material_and_statuses(
        db, material_part_number, ["WAREHOUSE"]
    )
    movement = StockMovement(
        stock_unit_id=stock_unit_id,
        supplier_order_id=supplier_order_id,
        material_part_number=material_part_number,
        movement_type=movement_type,
        quantity_change=quantity_change,
        warehouse_quantity_after=warehouse_after,
        from_status=from_status,
        to_status=to_status,
        stock_unit_reference=stock_unit_reference,
        source_reference=source_reference,
        actor_user_id=actor_user_id,
        occurred_at=occurred_at or datetime.now(),
        reason=reason,
        note=note,
    )
    db.add(movement)
    return movement


def list_movements(
    db: Session,
    *,
    movement_type: str | None = None,
    material_part_number: str | None = None,
    limit: int = 500,
) -> list[StockMovementItem]:
    stmt = (
        select(StockMovement)
        .options(
            joinedload(StockMovement.actor),
            joinedload(StockMovement.material).joinedload(Material.material_type),
            joinedload(StockMovement.supplier_order),
        )
        .order_by(StockMovement.occurred_at.desc(), StockMovement.movement_id.desc())
        .limit(limit)
    )
    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
    if material_part_number:
        stmt = stmt.where(StockMovement.material_part_number == material_part_number)
    movements = db.scalars(stmt).unique().all()
    return [
        StockMovementItem(
            movement_id=item.movement_id,
            occurred_at=item.occurred_at,
            actor_user_id=item.actor_user_id,
            actor_name=item.actor.full_name,
            material_part_number=item.material_part_number,
            material_description=item.material.description,
            unit=item.material.material_type.unit,
            movement_type=item.movement_type,
            quantity_change=item.quantity_change,
            warehouse_quantity_after=item.warehouse_quantity_after,
            stock_unit_id=item.stock_unit_id,
            stock_unit_reference=item.stock_unit_reference,
            supplier_order_id=item.supplier_order_id,
            supplier_name=item.supplier_order.supplier_name if item.supplier_order else None,
            source_reference=item.source_reference,
            from_status=item.from_status,
            to_status=item.to_status,
            reason=item.reason,
            note=item.note,
        )
        for item in movements
    ]
