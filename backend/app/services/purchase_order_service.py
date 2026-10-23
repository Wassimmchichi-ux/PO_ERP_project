"""Queries for the Purchase Orders register.

PO Intake writes immutable versions to the normalized purchase-order tables.
This service deliberately reads the current version of each PO, rather than
the parser staging table, so the register only shows successfully imported
orders.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.exceptions.base import ConflictException, NotFoundException
from app.models import (
    FGPN,
    ParsedPurchaseOrder,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderVersion,
    SimulationFGPN,
)
from app.policies import PolicyActor, policy_engine, system_actor
from app.schemas.purchase_order import (
    PurchaseOrderDetailResponse,
    PurchaseOrderLineDetail,
    PurchaseOrderListItem,
    PurchaseOrderListResponse,
    PurchaseOrderVersionDetail,
)


def list_purchase_orders(
    db: Session,
    *,
    actor: PolicyActor | None = None,
) -> PurchaseOrderListResponse:
    """Return each PO once, including totals from its current version."""
    policy_engine.require(actor or system_actor(), "po.view")

    statement = (
        select(PurchaseOrder)
        .options(
            joinedload(PurchaseOrder.customer),
            joinedload(PurchaseOrder.contact),
            joinedload(PurchaseOrder.current_version)
            .selectinload(PurchaseOrderVersion.lines)
            .joinedload(PurchaseOrderLine.fgpn)
            .joinedload(FGPN.project),
            joinedload(PurchaseOrder.current_version)
            .selectinload(PurchaseOrderVersion.lines)
            .selectinload(PurchaseOrderLine.launch_fgpns),
        )
        .order_by(PurchaseOrder.updated_at.desc(), PurchaseOrder.po_id.desc())
    )
    purchase_orders = db.execute(statement).scalars().all()
    items = [_to_list_item(purchase_order) for purchase_order in purchase_orders]
    return PurchaseOrderListResponse(items=items, total=len(items))


def get_purchase_order(
    db: Session,
    po_id: int,
    *,
    actor: PolicyActor | None = None,
) -> PurchaseOrderDetailResponse:
    """Return the current PO and immutable version metadata for its detail page."""
    policy_engine.require(actor or system_actor(), "po.view")
    purchase_order = db.execute(
        select(PurchaseOrder)
        .where(PurchaseOrder.po_id == po_id)
        .options(
            joinedload(PurchaseOrder.customer),
            joinedload(PurchaseOrder.contact),
            joinedload(PurchaseOrder.current_version)
            .joinedload(PurchaseOrderVersion.document),
            joinedload(PurchaseOrder.current_version)
            .selectinload(PurchaseOrderVersion.lines)
            .joinedload(PurchaseOrderLine.fgpn)
            .joinedload(FGPN.project),
            joinedload(PurchaseOrder.current_version)
            .selectinload(PurchaseOrderVersion.lines)
            .selectinload(PurchaseOrderLine.launch_fgpns),
            selectinload(PurchaseOrder.versions).joinedload(PurchaseOrderVersion.document),
            selectinload(PurchaseOrder.versions).joinedload(PurchaseOrderVersion.creator),
        )
    ).scalar_one_or_none()
    if purchase_order is None:
        raise NotFoundException(f"Purchase order {po_id} not found.")

    current_version = purchase_order.current_version
    lines = current_version.lines if current_version is not None else []
    return PurchaseOrderDetailResponse(
        **_to_list_item(purchase_order).model_dump(),
        contact_email=purchase_order.contact.email,
        contact_phone=purchase_order.contact.phone,
        document_date=current_version.document_date if current_version else None,
        car_model=current_version.car_model if current_version else None,
        engineering_phase_level=current_version.engineering_phase_level if current_version else None,
        purchase_order_level=current_version.po_level if current_version else None,
        reason=current_version.reason_of_purchase_order if current_version else None,
        source_file_name=current_version.document.file_name if current_version else None,
        lines=[_to_line_detail(line) for line in sorted(lines, key=lambda item: item.line_number)],
        versions=[
            PurchaseOrderVersionDetail(
                po_version_id=version.po_version_id,
                version_number=version.version_number,
                document_date=version.document_date,
                source_file_name=version.document.file_name,
                created_at=version.created_at,
                created_by_name=version.creator.full_name,
                change_reason=version.change_reason,
                is_current=version.po_version_id == purchase_order.current_version_id,
            )
            for version in sorted(
                purchase_order.versions,
                key=lambda item: item.version_number,
                reverse=True,
            )
        ],
    )


def delete_purchase_order(
    db: Session,
    po_id: int,
    *,
    actor: PolicyActor | None = None,
) -> None:
    """Remove an unplanned test/import PO while preserving linked operations."""
    # Import permission is intentionally required: only the roles allowed to
    # create a PO may remove an unlinked test/import record.
    policy_engine.require(actor or system_actor(), "po.import")
    purchase_order = db.execute(
        select(PurchaseOrder)
        .where(PurchaseOrder.po_id == po_id)
        .options(
            selectinload(PurchaseOrder.versions)
            .selectinload(PurchaseOrderVersion.lines)
            .selectinload(PurchaseOrderLine.launch_fgpns),
            selectinload(PurchaseOrder.versions).selectinload(PurchaseOrderVersion.changes),
            selectinload(PurchaseOrder.launch_pos),
            selectinload(PurchaseOrder.status_history),
        )
    ).scalar_one_or_none()
    if purchase_order is None:
        raise NotFoundException(f"Purchase order {po_id} not found.")

    linked_to_launch = bool(purchase_order.launch_pos) or any(
        line.launch_fgpns for version in purchase_order.versions for line in version.lines
    )
    linked_to_simulation = db.scalar(
        select(SimulationFGPN.simulation_fgpn_id)
        .where(SimulationFGPN.po_id == po_id)
        .limit(1)
    )
    if linked_to_launch or linked_to_simulation is not None:
        raise ConflictException(
            "This purchase order is used by a simulation or launch and cannot be deleted.",
        )

    # Break the cyclic current-version reference before removing its versions.
    purchase_order.current_version_id = None
    db.flush()
    for status_event in purchase_order.status_history:
        db.delete(status_event)
    for version in purchase_order.versions:
        for change in version.changes:
            db.delete(change)
        for line in version.lines:
            db.delete(line)
        db.delete(version)

    # The intake draft remains available for another review/import cycle.
    db.execute(
        update(ParsedPurchaseOrder)
        .where(ParsedPurchaseOrder.validated_po_id == po_id)
        .values(validated_po_id=None, status="VALIDATED")
    )
    db.delete(purchase_order)
    db.commit()


def _to_list_item(purchase_order: PurchaseOrder) -> PurchaseOrderListItem:
    current_version = purchase_order.current_version
    lines = current_version.lines if current_version is not None else []
    ordered_quantity = sum((Decimal(line.ordered_quantity) for line in lines), Decimal("0"))
    delivered_quantity = sum(
        (
            sum(
                (Decimal(allocation.delivered_quantity) for allocation in line.launch_fgpns),
                Decimal("0"),
            )
            for line in lines
        ),
        Decimal("0"),
    )


    # Do not expose a negative outstanding amount if a correction was posted
    # after a delivery. The delivery workflow remains the source of delivered
    # quantities, while the current PO version remains the source of pricing.
    remaining_quantity = max(Decimal("0"), ordered_quantity - delivered_quantity)
    open_amount = sum(
        (
            max(
                Decimal("0"),
                Decimal(line.ordered_quantity)
                - sum(
                    (Decimal(allocation.delivered_quantity) for allocation in line.launch_fgpns),
                    Decimal("0"),
                ),
            )
            * Decimal(line.unit_price)
            for line in lines
        ),
        Decimal("0"),
    )

    projects = {
        line.fgpn.project
        for line in lines
        if line.fgpn is not None and line.fgpn.project
    }
    # PO Intake imports all lines against one selected project. Keeping this
    # deterministic makes an inconsistent legacy PO still readable.
    project = min(projects, key=lambda item: item.project_id) if projects else None
    delivery_date = _latest_delivery_date(lines)

    return PurchaseOrderListItem(
        po_id=purchase_order.po_id,
        po_number=purchase_order.po_number,
        project_id=project.project_id if project else None,
        project_code=project.project_code if project else None,
        project_name=project.name if project else None,
        jit_customer=(
            project.jit_customer
            if project and project.jit_customer
            else purchase_order.customer.name
        ),
        oem_customer=project.oem_customer if project else None,
        contact_name=purchase_order.contact.name,
        current_version=current_version.version_number if current_version else None,
        status=purchase_order.current_status,
        fgpn_codes=sorted({line.fgpn.fgpn_code for line in lines if line.fgpn is not None}),
        ordered_quantity=ordered_quantity,
        delivered_quantity=delivered_quantity,
        remaining_quantity=remaining_quantity,
        open_amount=open_amount,
        delivery_date=delivery_date,
        delivery_week=f"W{delivery_date.isocalendar().week:02d}" if delivery_date else None,
        updated_at=purchase_order.updated_at,
    )


def _to_line_detail(line: PurchaseOrderLine) -> PurchaseOrderLineDetail:
    delivered_quantity = sum(
        (Decimal(allocation.delivered_quantity) for allocation in line.launch_fgpns),
        Decimal("0"),
    )
    remaining_quantity = max(Decimal("0"), Decimal(line.ordered_quantity) - delivered_quantity)
    return PurchaseOrderLineDetail(
        po_line_id=line.po_line_id,
        item_number=line.item_number,
        fgpn_code=line.fgpn.fgpn_code,
        description=line.description or line.fgpn.description,
        ordered_quantity=Decimal(line.ordered_quantity),
        delivered_quantity=delivered_quantity,
        remaining_quantity=remaining_quantity,
        unit_price=Decimal(line.unit_price),
        open_amount=remaining_quantity * Decimal(line.unit_price),
        delivery_date=line.delivery_date,
    )


def _latest_delivery_date(lines: list[PurchaseOrderLine]) -> date | None:
    dates = [line.delivery_date for line in lines if line.delivery_date is not None]
    return max(dates) if dates else None
