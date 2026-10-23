"""Supplier ETA planning, warehouse entry, arrival confirmation and notification."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.exceptions.base import ConflictException, NotFoundException, ValidationException
from app.models import (
    AuditLog,
    Material,
    Notification,
    Project,
    StockUnit,
    Supplier,
    SupplierMaterialOrder,
    SupplierMaterialOrderLine,
)
from app.policies import PolicyActor, policy_engine, system_actor
from app.schemas.supplier_order import (
    NotificationResponse,
    SupplierArrivalConfirmRequest,
    SupplierArrivalEntryRequest,
    SupplierOrderCreateRequest,
    SupplierOrderLineInput,
    SupplierOrderLineResponse,
    SupplierOrderListResponse,
    SupplierOrderResponse,
    SupplierOrderUpdateRequest,
)
from app.services import stock_movement_service


def _load_order(db: Session, supplier_order_id: int, *, lock: bool = False):
    # PostgreSQL cannot apply FOR UPDATE to the nullable side of the outer
    # joins produced by joinedload(). Use separate relationship queries for
    # locked workflow transitions so the primary SELECT locks only the order.
    related_loader = selectinload if lock else joinedload
    stmt = (
        select(SupplierMaterialOrder)
        .options(
            related_loader(SupplierMaterialOrder.project),
            related_loader(SupplierMaterialOrder.ordered_for),
            selectinload(SupplierMaterialOrder.lines).options(
                joinedload(SupplierMaterialOrderLine.material).joinedload(
                    Material.material_type
                ),
                joinedload(SupplierMaterialOrderLine.arrival_entered_by_user),
            ),
        )
        .where(SupplierMaterialOrder.supplier_order_id == supplier_order_id)
    )
    if lock:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def _response(order: SupplierMaterialOrder) -> SupplierOrderResponse:
    lines = []
    has_discrepancy = False
    for line in sorted(order.lines, key=lambda item: item.supplier_order_line_id):
        compatible = None
        quantity_difference = None
        if line.actual_quantity is not None:
            compatible = line.actual_quantity == line.expected_quantity
            quantity_difference = line.actual_quantity - line.expected_quantity
            has_discrepancy = has_discrepancy or not compatible
        lines.append(SupplierOrderLineResponse(
            supplier_order_line_id=line.supplier_order_line_id,
            material_part_number=line.material_part_number,
            description=line.material.description,
            unit=line.material.material_type.unit,
            stock_unit_kind=line.stock_unit_kind,
            stock_unit_reference=line.business_unit_id,
            expected_quantity=line.expected_quantity,
            expected_arrival_date=line.expected_arrival_date,
            actual_quantity=line.actual_quantity,
            stock_unit_id=line.stock_unit_id,
            compatible=compatible,
            quantity_difference=quantity_difference,
            arrival_entered_by_name=(
                line.arrival_entered_by_user.full_name
                if line.arrival_entered_by_user else None
            ),
            arrival_entered_at=line.arrival_entered_at,
        ))
    return SupplierOrderResponse(
        supplier_order_id=order.supplier_order_id,
        project_id=order.project_id,
        project_code=order.project.project_code,
        project_name=order.project.name,
        supplier_id=order.supplier_id,
        supplier_name=order.supplier_name,
        supplier_reference=order.supplier_reference,
        ordered_for_user_id=order.ordered_for_user_id,
        ordered_for_name=order.ordered_for.full_name,
        ordered_for_role=order.ordered_for.role,
        status=order.status,
        created_at=order.created_at,
        updated_at=order.updated_at,
        confirmed_at=order.confirmed_at,
        discrepancy_reason=order.discrepancy_reason,
        has_discrepancy=has_discrepancy,
        lines=lines,
    )


def _project_for_ordering(db: Session, project_id: int, actor: PolicyActor) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundException(f"Project {project_id} not found.")
    if project.status != "Active":
        raise ValidationException("Supplier material orders require an active project.")
    if (
        actor.normalized_role == "LAUNCH_ENGINEER"
        and actor.user_id is not None
        and actor.user_id != project.launch_engineer_user_id
    ):
        raise ValidationException("Launch engineers may order only for their assigned project.")
    return project


def _active_supplier(db: Session, supplier_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise NotFoundException(f"Supplier {supplier_id} not found.")
    if supplier.status.upper() != "ACTIVE":
        raise ValidationException("Select an active supplier from the administrator master list.")
    return supplier


def _validate_lines(
    db: Session,
    lines: list[SupplierOrderLineInput],
) -> None:
    """Validate material references; stock-unit identifiers are system-generated."""
    material_ids = set(db.scalars(
        select(Material.material_part_number).where(
            Material.material_part_number.in_({line.material_part_number for line in lines})
        )
    ).all())
    missing = sorted({line.material_part_number for line in lines} - material_ids)
    if missing:
        raise NotFoundException(f"Unknown material(s): {', '.join(missing)}.")


def _add_line(
    db: Session,
    order: SupplierMaterialOrder,
    line_input: SupplierOrderLineInput,
    owner_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> None:
    now = datetime.now()
    stock_unit = StockUnit(
        material_part_number=line_input.material_part_number,
        quantity=line_input.expected_quantity,
        status="IN_TRANSIT",
        expected_arrival_date=datetime.combine(
            line_input.expected_arrival_date, datetime.min.time()
        ),
        created_at=now,
        updated_at=now,
        user_id=owner_user_id,
    )
    db.add(stock_unit)
    db.flush()
    generated_identifier = f"SU-{stock_unit.stock_unit_id:08d}"
    stock_unit.business_unit_id = generated_identifier
    db.add(SupplierMaterialOrderLine(
        order=order,
        material_part_number=line_input.material_part_number,
        stock_unit_kind=line_input.stock_unit_kind,
        business_unit_id=generated_identifier,
        expected_quantity=line_input.expected_quantity,
        expected_arrival_date=line_input.expected_arrival_date,
        stock_unit_id=stock_unit.stock_unit_id,
    ))
    stock_movement_service.record_movement(
        db,
        material_part_number=line_input.material_part_number,
        movement_type="TRANSIT_DECLARED",
        quantity_change=line_input.expected_quantity,
        actor_user_id=actor_user_id,
        stock_unit_id=stock_unit.stock_unit_id,
        supplier_order_id=order.supplier_order_id,
        stock_unit_reference=generated_identifier,
        source_reference=order.supplier_reference,
        to_status="IN_TRANSIT",
        note=f"Supplier ETA {line_input.expected_arrival_date}.",
        occurred_at=now,
    )


def create_order(
    db: Session,
    request: SupplierOrderCreateRequest,
    actor_user_id: uuid.UUID,
    *,
    actor: PolicyActor | None = None,
) -> SupplierOrderResponse:
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "supplier.order.write")
    project = _project_for_ordering(db, request.project_id, acting_actor)
    supplier = _active_supplier(db, request.supplier_id)
    _validate_lines(db, request.lines)
    now = datetime.now()
    order = SupplierMaterialOrder(
        project_id=project.project_id,
        supplier_id=supplier.supplier_id,
        supplier_name=supplier.full_name,
        supplier_reference=supplier.supplier_reference,
        ordered_for_user_id=project.launch_engineer_user_id,
        created_by=actor_user_id,
        status="OPEN",
        created_at=now,
        updated_at=now,
    )
    db.add(order)
    db.flush()
    for line in request.lines:
        _add_line(db, order, line, project.launch_engineer_user_id, actor_user_id)
    db.add(AuditLog(
        user_id=actor_user_id,
        action="CREATE_SUPPLIER_MATERIAL_ORDER",
        entity_type="SupplierMaterialOrder",
        entity_id=order.supplier_order_id,
        timestamp=now,
        details=json.dumps({"project_id": project.project_id, "line_count": len(request.lines)}),
    ))
    db.commit()
    return _response(_load_order(db, order.supplier_order_id))


def list_orders(
    db: Session,
    *,
    actor: PolicyActor | None = None,
) -> SupplierOrderListResponse:
    acting_actor = actor or system_actor()
    if acting_actor.normalized_role in {"LAUNCH_ENGINEER", "LAUNCH_MANAGER"}:
        policy_engine.require(acting_actor, "supplier.order.write")
    else:
        if not (
            policy_engine.can(acting_actor, "supplier.arrival.enter").allowed
            or policy_engine.can(acting_actor, "supplier.arrival.confirm").allowed
        ):
            policy_engine.require(acting_actor, "stock.view")
    stmt = (
        select(SupplierMaterialOrder)
        .options(
            joinedload(SupplierMaterialOrder.project),
            joinedload(SupplierMaterialOrder.ordered_for),
            selectinload(SupplierMaterialOrder.lines),
        )
        .order_by(SupplierMaterialOrder.created_at.desc())
    )
    if acting_actor.normalized_role == "LAUNCH_ENGINEER" and acting_actor.user_id is not None:
        stmt = stmt.where(SupplierMaterialOrder.ordered_for_user_id == acting_actor.user_id)
    orders = list(db.execute(stmt).scalars().all())
    return SupplierOrderListResponse(items=[_response(order) for order in orders], total=len(orders))


def update_order(
    db: Session,
    supplier_order_id: int,
    request: SupplierOrderUpdateRequest,
    actor_user_id: uuid.UUID,
    *,
    actor: PolicyActor | None = None,
) -> SupplierOrderResponse:
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "supplier.order.write")
    order = _load_order(db, supplier_order_id, lock=True)
    if order is None:
        raise NotFoundException(f"Supplier order {supplier_order_id} not found.")
    if order.status != "OPEN":
        raise ConflictException("Only an open supplier order can be modified.")
    project = _project_for_ordering(db, request.project_id, acting_actor)
    if project.project_id != order.project_id:
        raise ValidationException("A supplier order cannot be moved to another project.")

    supplier = _active_supplier(db, request.supplier_id)
    _validate_lines(db, request.lines)

    by_line_id = {line.supplier_order_line_id: line for line in order.lines}
    requested_line_ids = {
        line.supplier_order_line_id
        for line in request.lines
        if line.supplier_order_line_id is not None
    }
    unknown_line_ids = requested_line_ids - set(by_line_id)
    if unknown_line_ids:
        raise ValidationException(
            f"Supplier order line(s) do not belong to this order: {sorted(unknown_line_ids)}."
        )
    for line_id, line in list(by_line_id.items()):
        if line_id not in requested_line_ids:
            stock_unit = db.get(StockUnit, line.stock_unit_id)
            stock_movement_service.record_movement(
                db,
                material_part_number=line.material_part_number,
                movement_type="TRANSIT_CANCELLED",
                quantity_change=-line.expected_quantity,
                actor_user_id=actor_user_id,
                stock_unit_id=line.stock_unit_id,
                supplier_order_id=order.supplier_order_id,
                stock_unit_reference=line.business_unit_id,
                source_reference=order.supplier_reference,
                from_status="IN_TRANSIT",
                note="Supplier order line removed.",
            )
            db.delete(line)
            if stock_unit is not None:
                db.delete(stock_unit)
    db.flush()

    for line_input in request.lines:
        line = (
            by_line_id.get(line_input.supplier_order_line_id)
            if line_input.supplier_order_line_id is not None
            else None
        )
        if line is None:
            _add_line(
                db, order, line_input, project.launch_engineer_user_id, actor_user_id
            )
            continue
        stock_unit = db.get(StockUnit, line.stock_unit_id)
        previous_material = line.material_part_number
        previous_quantity = line.expected_quantity
        previous_eta = line.expected_arrival_date
        line.material_part_number = line_input.material_part_number
        line.stock_unit_kind = line_input.stock_unit_kind
        line.expected_quantity = line_input.expected_quantity
        line.expected_arrival_date = line_input.expected_arrival_date
        stock_unit.material_part_number = line_input.material_part_number
        stock_unit.quantity = line_input.expected_quantity
        stock_unit.expected_arrival_date = datetime.combine(
            line_input.expected_arrival_date, datetime.min.time()
        )
        stock_unit.updated_at = datetime.now()
        if previous_material != line_input.material_part_number:
            stock_movement_service.record_movement(
                db,
                material_part_number=previous_material,
                movement_type="TRANSIT_CANCELLED",
                quantity_change=-previous_quantity,
                actor_user_id=actor_user_id,
                stock_unit_id=stock_unit.stock_unit_id,
                supplier_order_id=order.supplier_order_id,
                stock_unit_reference=stock_unit.business_unit_id,
                source_reference=order.supplier_reference,
                from_status="IN_TRANSIT",
                note="Supplier order line material changed.",
                occurred_at=stock_unit.updated_at,
            )
            stock_movement_service.record_movement(
                db,
                material_part_number=line_input.material_part_number,
                movement_type="TRANSIT_DECLARED",
                quantity_change=line_input.expected_quantity,
                actor_user_id=actor_user_id,
                stock_unit_id=stock_unit.stock_unit_id,
                supplier_order_id=order.supplier_order_id,
                stock_unit_reference=stock_unit.business_unit_id,
                source_reference=order.supplier_reference,
                to_status="IN_TRANSIT",
                note=f"Replacement supplier ETA {line_input.expected_arrival_date}.",
                occurred_at=stock_unit.updated_at,
            )
        elif (
            previous_quantity != line_input.expected_quantity
            or previous_eta != line_input.expected_arrival_date
        ):
            stock_movement_service.record_movement(
                db,
                material_part_number=line_input.material_part_number,
                movement_type="TRANSIT_UPDATED",
                quantity_change=line_input.expected_quantity - previous_quantity,
                actor_user_id=actor_user_id,
                stock_unit_id=stock_unit.stock_unit_id,
                supplier_order_id=order.supplier_order_id,
                stock_unit_reference=stock_unit.business_unit_id,
                source_reference=order.supplier_reference,
                from_status="IN_TRANSIT",
                to_status="IN_TRANSIT",
                note=(
                    f"Planned quantity {previous_quantity} → {line_input.expected_quantity}; "
                    f"ETA {previous_eta} → {line_input.expected_arrival_date}."
                ),
                occurred_at=stock_unit.updated_at,
            )

    order.supplier_id = supplier.supplier_id
    order.supplier_name = supplier.full_name
    order.supplier_reference = supplier.supplier_reference
    order.updated_at = datetime.now()
    db.add(AuditLog(
        user_id=actor_user_id,
        action="UPDATE_SUPPLIER_MATERIAL_ORDER",
        entity_type="SupplierMaterialOrder",
        entity_id=order.supplier_order_id,
        timestamp=order.updated_at,
        details=json.dumps({"line_count": len(request.lines)}),
    ))
    db.commit()
    # Editing can replace line rows. Expire the identity map so the response
    # reflects the committed relationship instead of a previously loaded list.
    db.expire_all()
    return _response(_load_order(db, supplier_order_id))


def delete_order(
    db: Session,
    supplier_order_id: int,
    actor_user_id: uuid.UUID,
    *,
    actor: PolicyActor | None = None,
) -> None:
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "supplier.order.write")
    order = _load_order(db, supplier_order_id, lock=True)
    if order is None:
        raise NotFoundException(f"Supplier order {supplier_order_id} not found.")
    if order.status != "OPEN":
        raise ConflictException("Only an open supplier order can be removed.")
    _project_for_ordering(db, order.project_id, acting_actor)
    stock_units = [db.get(StockUnit, line.stock_unit_id) for line in order.lines]
    for line in order.lines:
        stock_movement_service.record_movement(
            db,
            material_part_number=line.material_part_number,
            movement_type="TRANSIT_CANCELLED",
            quantity_change=-line.expected_quantity,
            actor_user_id=actor_user_id,
            stock_unit_id=line.stock_unit_id,
            supplier_order_id=order.supplier_order_id,
            stock_unit_reference=line.business_unit_id,
            source_reference=order.supplier_reference,
            from_status="IN_TRANSIT",
            note="Supplier order removed.",
        )
    db.delete(order)
    db.flush()
    for stock_unit in stock_units:
        if stock_unit is not None:
            db.delete(stock_unit)
    db.add(AuditLog(
        user_id=actor_user_id,
        action="DELETE_SUPPLIER_MATERIAL_ORDER",
        entity_type="SupplierMaterialOrder",
        entity_id=supplier_order_id,
        timestamp=datetime.now(),
    ))
    db.commit()


def enter_arrival(
    db: Session,
    supplier_order_id: int,
    request: SupplierArrivalEntryRequest,
    actor_user_id: uuid.UUID,
    *,
    actor: PolicyActor | None = None,
) -> SupplierOrderResponse:
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "supplier.arrival.enter")
    order = _load_order(db, supplier_order_id, lock=True)
    if order is None:
        raise NotFoundException(f"Supplier order {supplier_order_id} not found.")
    if order.status not in {"OPEN", "ARRIVAL_ENTERED"}:
        raise ConflictException("Arrival can be entered only before team-leader confirmation.")
    entries = {line.supplier_order_line_id: line for line in request.lines}
    expected_ids = {line.supplier_order_line_id for line in order.lines}
    if set(entries) != expected_ids:
        raise ValidationException("Actual quantities must be entered for every expected stock unit.")
    now = datetime.now()
    for line in order.lines:
        entry = entries[line.supplier_order_line_id]
        line.actual_quantity = entry.actual_quantity
        line.arrival_entered_by = actor_user_id
        line.arrival_entered_at = now
        stock_movement_service.record_movement(
            db,
            material_part_number=line.material_part_number,
            movement_type="ARRIVAL_ENTERED",
            quantity_change=Decimal("0"),
            actor_user_id=actor_user_id,
            stock_unit_id=line.stock_unit_id,
            supplier_order_id=order.supplier_order_id,
            stock_unit_reference=line.business_unit_id,
            source_reference=order.supplier_reference,
            from_status="IN_TRANSIT",
            to_status="IN_TRANSIT",
            note=(
                f"Warehouse entered actual quantity {entry.actual_quantity}; "
                f"planned quantity was {line.expected_quantity}."
            ),
            occurred_at=now,
        )
    order.status = "ARRIVAL_ENTERED"
    order.updated_at = now
    db.add(AuditLog(
        user_id=actor_user_id,
        action="ENTER_SUPPLIER_ARRIVAL",
        entity_type="SupplierMaterialOrder",
        entity_id=order.supplier_order_id,
        timestamp=now,
    ))
    db.commit()
    return _response(_load_order(db, supplier_order_id))


def confirm_arrival(
    db: Session,
    supplier_order_id: int,
    request: SupplierArrivalConfirmRequest,
    actor_user_id: uuid.UUID,
    *,
    actor: PolicyActor | None = None,
) -> SupplierOrderResponse:
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "supplier.arrival.confirm")
    order = _load_order(db, supplier_order_id, lock=True)
    if order is None:
        raise NotFoundException(f"Supplier order {supplier_order_id} not found.")
    if order.status != "ARRIVAL_ENTERED":
        raise ConflictException("Warehouse personnel must enter all received units before confirmation.")
    discrepancies = [
        line for line in order.lines
        if line.actual_quantity != line.expected_quantity
    ]
    reason = (request.discrepancy_reason or "").strip()
    if discrepancies and len(reason) < 10:
        raise ValidationException(
            "A discrepancy reason of at least 10 characters is required when actual stock differs."
        )

    now = datetime.now()
    for line in order.lines:
        stock_unit = db.execute(
            select(StockUnit).where(StockUnit.stock_unit_id == line.stock_unit_id).with_for_update()
        ).scalar_one()
        if stock_unit.status != "IN_TRANSIT":
            raise ConflictException(
                f"StockUnit {stock_unit.stock_unit_id} is no longer awaiting supplier arrival."
            )
        stock_unit.quantity = line.actual_quantity
        stock_unit.status = "WAREHOUSE"
        stock_unit.reception_date = now
        stock_unit.reception_username = line.arrival_entered_by
        stock_unit.updated_at = now
        stock_movement_service.record_movement(
            db,
            material_part_number=line.material_part_number,
            movement_type="SUPPLIER_RECEIPT_CONFIRMED",
            quantity_change=line.actual_quantity,
            actor_user_id=actor_user_id,
            stock_unit_id=stock_unit.stock_unit_id,
            supplier_order_id=order.supplier_order_id,
            stock_unit_reference=stock_unit.business_unit_id,
            source_reference=order.supplier_reference,
            from_status="IN_TRANSIT",
            to_status="WAREHOUSE",
            reason=reason or None,
            note=(
                f"Confirmed {line.actual_quantity}; planned {line.expected_quantity}."
            ),
            occurred_at=now,
        )

    order.status = "CONFIRMED"
    order.confirmed_at = now
    order.confirmed_by = actor_user_id
    order.discrepancy_reason = reason or None
    order.updated_at = now
    discrepancy_text = (
        f" {len(discrepancies)} stock unit(s) differ from the supplier plan; review is required."
        if discrepancies else
        " All received quantities match the supplier plan."
    )
    db.add(Notification(
        user_id=order.ordered_for_user_id,
        notification_type="SUPPLIER_ARRIVAL_CONFIRMED",
        title=f"Supplier arrival {order.supplier_reference or order.supplier_order_id} confirmed",
        message=(
            f"Warehouse team leader confirmed {len(order.lines)} stock unit(s) from "
            f"{order.supplier_name}.{discrepancy_text} Verify the material in the warehouse."
        ),
        entity_type="SupplierMaterialOrder",
        entity_id=order.supplier_order_id,
        created_at=now,
    ))
    db.add(AuditLog(
        user_id=actor_user_id,
        action="CONFIRM_SUPPLIER_ARRIVAL",
        entity_type="SupplierMaterialOrder",
        entity_id=order.supplier_order_id,
        timestamp=now,
        reason=reason or None,
        details=json.dumps({"discrepancy_count": len(discrepancies)}),
    ))
    db.commit()
    return _response(_load_order(db, supplier_order_id))


def list_notifications(
    db: Session,
    user_id: uuid.UUID,
    *,
    actor: PolicyActor | None = None,
) -> list[NotificationResponse]:
    policy_engine.require(actor or system_actor(), "notification.view")
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    ).all()
    return [NotificationResponse.model_validate(row, from_attributes=True) for row in rows]


def mark_notification_read(
    db: Session,
    notification_id: int,
    user_id: uuid.UUID,
    *,
    actor: PolicyActor | None = None,
) -> NotificationResponse:
    policy_engine.require(actor or system_actor(), "notification.view")
    notification = db.execute(
        select(Notification)
        .where(Notification.notification_id == notification_id)
        .where(Notification.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if notification is None:
        raise NotFoundException(f"Notification {notification_id} not found.")
    notification.read_at = notification.read_at or datetime.now()
    db.commit()
    return NotificationResponse.model_validate(notification, from_attributes=True)
