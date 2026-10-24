"""Queries for the Purchase Orders register.

PO Intake writes immutable versions to the normalized purchase-order tables.
This service deliberately reads the current version of each PO, rather than
the parser staging table, so the register only shows successfully imported
orders.
"""
from __future__ import annotations

import logging
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
    VersionComparisonResponse,
    VersionComparisonRow,
)

logger = logging.getLogger(__name__)


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
    deletion_reason: str,
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
    logger.info(
        "Purchase order %s (po_id=%d) deleted. Reason: %s. Actor: %s",
        purchase_order.po_number,
        po_id,
        deletion_reason,
        actor.role if actor else "system",
    )
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


def get_po_version_pdf(
    db: Session,
    po_version_id: int,
    actor: PolicyActor | None = None,
) -> tuple[bytes, str]:
    """Retrieve the original PDF content and filename for a PO version."""
    policy_engine.require(actor or system_actor(), "po.view")

    version = db.execute(
        select(PurchaseOrderVersion)
        .where(PurchaseOrderVersion.po_version_id == po_version_id)
        .options(joinedload(PurchaseOrderVersion.document))
    ).scalar_one_or_none()

    if version is None or version.document is None:
        raise NotFoundException(f"Purchase order version {po_version_id} not found.")

    doc = version.document
    filename = doc.file_name

    from pathlib import Path

    candidates = [
        Path(doc.file_path) if doc.file_path else None,
        Path("/app/uploads") / filename,
        Path("backend/uploads") / filename,
        Path("/uploads") / filename,
        Path("ressources/business-test") / filename,
        Path("/app/ressources/business-test") / filename,
        Path("uploads") / filename,
    ]

    for d in [Path("/app/uploads"), Path("backend/uploads"), Path("ressources/business-test"), Path("/app/ressources/business-test")]:
        if d.is_dir():
            for p in d.iterdir():
                if p.name.lower() == filename.lower():
                    candidates.append(p)

    for p in candidates:
        if p and p.is_file():
            try:
                content = p.read_bytes()
                if content:
                    return content, filename
            except OSError as e:
                logger.warning("Error reading PO PDF from %s: %s", p, e)

    raise NotFoundException(f"Original PDF file '{filename}' was not found on the server.")


def compare_po_versions(
    db: Session,
    po_id: int,
    v1: int,
    v2: int,
    actor: PolicyActor | None = None,
) -> VersionComparisonResponse:
    """Compare field-by-field differences between two versions of the same PO."""
    policy_engine.require(actor or system_actor(), "po.view")

    po = db.execute(
        select(PurchaseOrder).where(PurchaseOrder.po_id == po_id)
    ).scalar_one_or_none()
    if po is None:
        raise NotFoundException(f"Purchase order {po_id} not found.")

    va = db.execute(
        select(PurchaseOrderVersion)
        .where(PurchaseOrderVersion.po_id == po_id, PurchaseOrderVersion.version_number == v1)
        .options(
            joinedload(PurchaseOrderVersion.document),
            joinedload(PurchaseOrderVersion.creator),
            selectinload(PurchaseOrderVersion.lines).joinedload(PurchaseOrderLine.fgpn),
            selectinload(PurchaseOrderVersion.changes),
        )
    ).scalar_one_or_none()

    vb = db.execute(
        select(PurchaseOrderVersion)
        .where(PurchaseOrderVersion.po_id == po_id, PurchaseOrderVersion.version_number == v2)
        .options(
            joinedload(PurchaseOrderVersion.document),
            joinedload(PurchaseOrderVersion.creator),
            selectinload(PurchaseOrderVersion.lines).joinedload(PurchaseOrderLine.fgpn),
            selectinload(PurchaseOrderVersion.changes),
        )
    ).scalar_one_or_none()

    if va is None:
        raise NotFoundException(f"Version {v1} not found for PO {po.po_number}.")
    if vb is None:
        raise NotFoundException(f"Version {v2} not found for PO {po.po_number}.")

    rows: list[VersionComparisonRow] = []

    def add_header(label: str, val_a, val_b):
        sa = str(val_a) if val_a is not None and str(val_a).strip() else None
        sb = str(val_b) if val_b is not None and str(val_b).strip() else None
        if sa is None and sb is None:
            return
        status = "Unchanged"
        if sa is None:
            status = "Added"
        elif sb is None:
            status = "Removed"
        elif sa != sb:
            status = "Changed"
        rows.append(VersionComparisonRow(field=label, a=sa, b=sb, status=status))

    # Header comparisons
    add_header("Document Date", va.document_date, vb.document_date)
    add_header("Source File", va.document.file_name if va.document else None, vb.document.file_name if vb.document else None)
    add_header("Car Model", va.car_model, vb.car_model)
    add_header("Engineering Phase", va.engineering_phase_level, vb.engineering_phase_level)
    add_header("PO Level", va.po_level, vb.po_level)
    add_header("Reason of PO", va.reason_of_purchase_order, vb.reason_of_purchase_order)
    add_header("Change Reason", va.change_reason, vb.change_reason)

    qty_a = sum(l.ordered_quantity for l in va.lines)
    qty_b = sum(l.ordered_quantity for l in vb.lines)
    add_header("Total Ordered Quantity", f"{qty_a:g}", f"{qty_b:g}")

    amt_a = sum(l.ordered_quantity * l.unit_price for l in va.lines)
    amt_b = sum(l.ordered_quantity * l.unit_price for l in vb.lines)
    add_header("Total Amount (EUR)", f"{amt_a:,.2f}", f"{amt_b:,.2f}")

    add_header("Total Line Count", str(len(va.lines)), str(len(vb.lines)))

    # Line-by-line comparison by FGPN
    lines_a = {l.fgpn.fgpn_code: l for l in va.lines if l.fgpn}
    lines_b = {l.fgpn.fgpn_code: l for l in vb.lines if l.fgpn}
    all_fgpns = sorted(set(lines_a.keys()) | set(lines_b.keys()))

    for code in all_fgpns:
        la = lines_a.get(code)
        lb = lines_b.get(code)
        if la is not None and lb is not None:
            if la.ordered_quantity != lb.ordered_quantity:
                rows.append(VersionComparisonRow(
                    field=f"{code} — Quantity",
                    a=f"{la.ordered_quantity:g}",
                    b=f"{lb.ordered_quantity:g}",
                    status="Changed",
                ))
            if la.unit_price != lb.unit_price:
                rows.append(VersionComparisonRow(
                    field=f"{code} — Unit Price",
                    a=f"{la.unit_price:g}",
                    b=f"{lb.unit_price:g}",
                    status="Changed",
                ))
            if la.delivery_date != lb.delivery_date:
                rows.append(VersionComparisonRow(
                    field=f"{code} — Delivery Date",
                    a=str(la.delivery_date) if la.delivery_date else "—",
                    b=str(lb.delivery_date) if lb.delivery_date else "—",
                    status="Changed",
                ))
            if (
                la.ordered_quantity == lb.ordered_quantity
                and la.unit_price == lb.unit_price
                and la.delivery_date == lb.delivery_date
            ):
                rows.append(VersionComparisonRow(
                    field=f"{code} (Qty {la.ordered_quantity:g})",
                    a=f"{la.ordered_quantity:g} pcs",
                    b=f"{lb.ordered_quantity:g} pcs",
                    status="Unchanged",
                ))
        elif la is not None:
            rows.append(VersionComparisonRow(
                field=f"{code}",
                a=f"Qty {la.ordered_quantity:g} @ {la.unit_price:g}",
                b=None,
                status="Removed",
            ))
        elif lb is not None:
            rows.append(VersionComparisonRow(
                field=f"{code}",
                a=None,
                b=f"Qty {lb.ordered_quantity:g} @ {lb.unit_price:g}",
                status="Added",
            ))

    return VersionComparisonResponse(
        po_id=po.po_id,
        po_number=po.po_number,
        version_a=v1,
        version_b=v2,
        rows=rows,
    )
