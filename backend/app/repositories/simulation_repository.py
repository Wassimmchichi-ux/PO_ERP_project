"""Repository layer for Simulation."""
from __future__ import annotations

import datetime
import json
import uuid
from decimal import Decimal

from sqlalchemy import and_, select, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.bom import BOM
from app.models.bom_line import BOMLine
from app.models.simulation import Simulation
from app.models.simulation_fgpn import SimulationFGPN
from app.models.stock_allocation import StockAllocation
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_line import PurchaseOrderLine
from app.models.purchase_order_version import PurchaseOrderVersion
from app.models.fgpn import FGPN
from app.models.launch import Launch
from app.models.launch_fgpn import LaunchFGPN
from app.models.project import Project


def get_current_boms_for_fgpns(db: Session, fgpn_ids: list[int]) -> dict[int, BOM]:
    """Fetch the active BOM and its lines for the given FGPN IDs."""
    stmt = (
        select(BOM)
        .options(selectinload(BOM.lines).joinedload(BOMLine.material))
        .where(BOM.fgpn_id.in_(fgpn_ids))
        .where(BOM.is_current.is_(True))
    )
    boms = db.execute(stmt).scalars().all()
    return {bom.fgpn_id: bom for bom in boms}


def get_po_lines(db: Session, po_line_ids: list[int]) -> dict[int, PurchaseOrderLine]:
    """Fetch PO lines by their IDs."""
    if not po_line_ids:
        return {}
    stmt = (
        select(PurchaseOrderLine)
        .options(
            joinedload(PurchaseOrderLine.po_version)
            .joinedload(PurchaseOrderVersion.purchase_order)
        )
        .where(PurchaseOrderLine.po_line_id.in_(po_line_ids))
    )
    lines = db.execute(stmt).scalars().all()
    return {line.po_line_id: line for line in lines}


def get_current_po_lines_for_po_fgpns(
    db: Session,
    po_fgpn_pairs: list[tuple[int, int]],
) -> dict[tuple[int, int], PurchaseOrderLine]:
    """Fetch current-version PO lines keyed by (po_id, fgpn_id)."""
    if not po_fgpn_pairs:
        return {}

    filters = [
        and_(PurchaseOrder.po_id == po_id, PurchaseOrderLine.fgpn_id == fgpn_id)
        for po_id, fgpn_id in set(po_fgpn_pairs)
    ]
    stmt = (
        select(PurchaseOrderLine)
        .join(
            PurchaseOrderVersion,
            PurchaseOrderLine.po_version_id == PurchaseOrderVersion.po_version_id,
        )
        .join(
            PurchaseOrder,
            PurchaseOrder.current_version_id == PurchaseOrderVersion.po_version_id,
        )
        .options(
            joinedload(PurchaseOrderLine.po_version)
            .joinedload(PurchaseOrderVersion.purchase_order)
        )
        .where(or_(*filters))
    )
    lines = db.execute(stmt).scalars().all()
    return {
        (line.po_version.purchase_order.po_id, line.fgpn_id): line
        for line in lines
        if line.po_version is not None and line.po_version.purchase_order is not None
    }


def get_fgpns(db: Session, fgpn_ids: list[int]) -> dict[int, FGPN]:
    """Fetch FGPNs by their IDs."""
    stmt = select(FGPN).where(FGPN.fgpn_id.in_(fgpn_ids))
    fgpns = db.execute(stmt).scalars().all()
    return {fgpn.fgpn_id: fgpn for fgpn in fgpns}


def get_project(db: Session, project_id: int) -> Project | None:
    """Fetch the project that scopes a simulation."""
    return db.get(Project, project_id)


def get_planned_launch_quantities_by_po_line(
    db: Session,
    po_line_ids: list[int],
) -> dict[int, Decimal]:
    """Return quantities already committed to non-cancelled launches."""
    if not po_line_ids:
        return {}
    stmt = (
        select(
            LaunchFGPN.po_line_id,
            func.coalesce(func.sum(LaunchFGPN.planned_quantity), 0),
        )
        .join(Launch, Launch.launch_id == LaunchFGPN.launch_id)
        .where(LaunchFGPN.po_line_id.in_(po_line_ids))
        .where(Launch.status != "CANCELLED")
        .group_by(LaunchFGPN.po_line_id)
    )
    return {po_line_id: quantity for po_line_id, quantity in db.execute(stmt).all()}


def list_current_po_lines_for_project(db: Session, project_id: int) -> list[PurchaseOrderLine]:
    """List current-version PO lines whose FGPN belongs to one project."""
    stmt = (
        select(PurchaseOrderLine)
        .join(PurchaseOrderVersion, PurchaseOrderLine.po_version_id == PurchaseOrderVersion.po_version_id)
        .join(PurchaseOrder, PurchaseOrder.current_version_id == PurchaseOrderVersion.po_version_id)
        .join(FGPN, FGPN.fgpn_id == PurchaseOrderLine.fgpn_id)
        .options(
            joinedload(PurchaseOrderLine.po_version).joinedload(PurchaseOrderVersion.purchase_order),
            joinedload(PurchaseOrderLine.fgpn),
        )
        .where(FGPN.project_id == project_id)
        .order_by(PurchaseOrder.po_number, PurchaseOrderLine.line_number)
    )
    return list(db.execute(stmt).scalars().all())


def get_simulation_allocations(
    db: Session,
    simulation_id: int,
    allocation_type: str = 'SIMULATION',
) -> list[StockAllocation]:
    """Fetch allocation records for a saved simulation."""
    stmt = (
        select(StockAllocation)
        .options(joinedload(StockAllocation.stock_unit))
        .where(StockAllocation.simulation_id == simulation_id)
        .where(StockAllocation.allocation_type == allocation_type)
    )
    return db.execute(stmt).scalars().all()


def get_simulation_selected_fgpns(db: Session, simulation_id: int) -> list[SimulationFGPN]:
    """Fetch the saved PO+FGPN demand rows for a simulation."""
    stmt = (
        select(SimulationFGPN)
        .where(SimulationFGPN.simulation_id == simulation_id)
        .order_by(SimulationFGPN.priority, SimulationFGPN.simulation_fgpn_id)
    )
    return db.execute(stmt).scalars().all()


def get_simulation(db: Session, simulation_id: int) -> Simulation | None:
    """Fetch one simulation."""
    return db.execute(
        select(Simulation).where(Simulation.simulation_id == simulation_id)
    ).scalar_one_or_none()


def get_simulation_for_update(db: Session, simulation_id: int) -> Simulation | None:
    """Lock one simulation so launch execution is serialized."""
    return db.execute(
        select(Simulation)
        .where(Simulation.simulation_id == simulation_id)
        .with_for_update()
    ).scalar_one_or_none()


def add_stock_allocations(
    db: Session,
    *,
    simulation_id: int,
    allocations: list[dict],
    allocation_type: str,
    status: str,
) -> list[StockAllocation]:
    """Add stock allocation records for an existing simulation."""
    created = []
    for alloc in allocations:
        sa = StockAllocation(
            simulation_id=simulation_id,
            stock_unit_id=alloc['stock_unit_id'],
            allocated_quantity=alloc['allocated_quantity'],
            allocation_type=allocation_type,
            is_whole_issue=alloc.get('is_whole_issue', False),
            source_location=alloc['source_location'],
            status=status,
            created_at=datetime.datetime.now(),
        )
        db.add(sa)
        created.append(sa)
    db.flush()
    return created


def save_simulation(
    db: Session,
    *,
    simulation_mode: str,
    stock_scope_mode: str,
    stock_owner_user_id: uuid.UUID | None,
    include_global_stock: bool,
    project_id: int,
    target_date: datetime.date,
    safety_coefficient: Decimal,
    is_feasible: bool,
    shortfall_json: str,
    mtg_minutes_document_id: int | None,
    created_by: uuid.UUID,
    allocations: list[dict],
    selected_fgpns: list[dict],
) -> int:
    """Save the official simulation and its allocations."""
    
    now = datetime.datetime.now()
    sim = Simulation(
        project_id=project_id,
        simulation_mode=simulation_mode,
        stock_scope_mode=stock_scope_mode,
        stock_owner_user_id=stock_owner_user_id,
        include_global_stock=include_global_stock,
        target_date=target_date,
        safety_coefficient=safety_coefficient,
        is_feasible=is_feasible,
        shortfall_json=shortfall_json,
        mtg_minutes_document_id=mtg_minutes_document_id,
        workflow_status="READY" if mtg_minutes_document_id is not None else "AWAITING_DOCUMENT",
        document_due_at=(
            None
            if mtg_minutes_document_id is not None
            else now + datetime.timedelta(hours=24)
        ),
        created_at=now,
        created_by=created_by
    )
    db.add(sim)
    db.flush()

    for selected in selected_fgpns:
        sim_fgpn = SimulationFGPN(
            simulation_id=sim.simulation_id,
            po_id=selected['po_id'],
            fgpn_id=selected['fgpn_id'],
            po_line_id=selected.get('po_line_id'),
            priority=selected['priority'],
            po_quantity=selected['po_quantity'],
            simulation_quantity=selected['simulation_quantity'],
            launchable_quantity=selected['launchable_quantity'],
            created_at=datetime.datetime.now(),
        )
        db.add(sim_fgpn)
    
    add_stock_allocations(
        db,
        simulation_id=sim.simulation_id,
        allocations=allocations,
        allocation_type='SIMULATION',
        status='RESERVED',
    )
        
    db.flush()
    return sim.simulation_id


def count_user_simulations(db: Session, user_id: uuid.UUID) -> int:
    """Count how many simulations the user has currently saved."""
    stmt = select(func.count(Simulation.simulation_id)).where(Simulation.created_by == user_id)
    return db.execute(stmt).scalar() or 0
