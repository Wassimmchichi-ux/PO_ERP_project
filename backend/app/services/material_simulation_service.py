"""Service for Material Simulation."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.exceptions.base import ConflictException, NotFoundException, ValidationException
from app.models import Document
from app.policies import PolicyActor, policy_engine, system_actor
from app.repositories import simulation_repository, stock_repository
from app.schemas.simulation import (
    SimulationPreviewRequest, 
    SimulationPreviewResult,
    MaterialSimulationSummary,
    FgpnSimulationSummary,
    AllocationDetail,
    FgpnSimulationRequest,
    LaunchAvailabilityIssue,
    LaunchReviewResult,
    LaunchSimulationResponse,
    SimulationOptionLine,
    SimulationOptionsResponse,
    SimulationSaveRequest,
    SimulationSaveResponse,
    SimulationWorkflowResponse,
)
from app.services.simulation_allocator import (
    StockSlot, 
    MaterialPool, 
    FgpnDemand, 
    run_allocation_engine
)
from app.services import stock_movement_service


def _material_suggestion(mpn: str, shortfall: Decimal, include_in_transit: bool, in_transit: Decimal) -> str | None:
    if shortfall <= 0:
        return None
    if not include_in_transit and in_transit > 0:
        return f"Include in-transit stock or procure at least {shortfall} more of {mpn}."
    return f"Procure or release at least {shortfall} more of {mpn}."


def _fgpn_suggestion(summary_status: str, launchable: Decimal, requested: Decimal) -> str | None:
    if summary_status == 'FULLY_COVERED':
        return None
    if launchable > 0:
        return f"Launch {launchable} now and wait/procure materials for the remaining {requested - launchable}."
    return "Do not launch this FGPN yet; required materials are not available."


def _preview_suggestion(is_feasible: bool, material_summaries: list[MaterialSimulationSummary]) -> str | None:
    if is_feasible:
        return "All selected PO+FGPN quantities can be launched with the current simulation scope."

    blocking_materials = [m.material_part_number for m in material_summaries if m.shortfall > 0]
    if not blocking_materials:
        return "Review selected quantities and BOM data before launching."

    shown = ", ".join(blocking_materials[:3])
    if len(blocking_materials) > 3:
        shown += f", and {len(blocking_materials) - 3} more"
    return f"Prioritize resolving material shortfalls for {shown} before launching the uncovered quantities."


def list_simulation_options(
    db: Session,
    project_id: int,
    *,
    actor: PolicyActor | None = None,
) -> SimulationOptionsResponse:
    """Return current outstanding PO/FGPN rows for the ordered planner."""
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "simulation.run")
    project = simulation_repository.get_project(db, project_id)
    if project is None:
        raise NotFoundException(f"Project {project_id} not found.")
    if project.status != "Active":
        raise ValidationException(f"Project {project_id} is not active.")
    if (
        acting_actor.normalized_role == "LAUNCH_ENGINEER"
        and acting_actor.user_id is not None
        and acting_actor.user_id != project.launch_engineer_user_id
    ):
        raise ValidationException("Launch engineers may view only their assigned project.")

    lines = simulation_repository.list_current_po_lines_for_project(db, project_id)
    planned = simulation_repository.get_planned_launch_quantities_by_po_line(
        db, [line.po_line_id for line in lines]
    )
    return SimulationOptionsResponse(
        project_id=project_id,
        lines=[
            SimulationOptionLine(
                po_id=line.po_version.purchase_order.po_id,
                po_number=line.po_version.purchase_order.po_number,
                po_line_id=line.po_line_id,
                fgpn_id=line.fgpn_id,
                fgpn_code=line.fgpn.fgpn_code,
                description=line.description or line.fgpn.description,
                ordered_quantity=line.ordered_quantity,
                already_planned_quantity=planned.get(line.po_line_id, Decimal("0")),
                outstanding_quantity=max(
                    Decimal("0"),
                    line.ordered_quantity - planned.get(line.po_line_id, Decimal("0")),
                ),
            )
            for line in lines
            if line.ordered_quantity - planned.get(line.po_line_id, Decimal("0")) > 0
        ],
    )


def _normalize_stock_scope_mode(mode: str | None) -> str:
    normalized = (mode or "ALL").strip().upper()
    if normalized not in {"ALL", "OWNED_ONLY"}:
        raise ValidationException("stock_scope_mode must be ALL or OWNED_ONLY.")
    return normalized


def _is_roll_material_type(material_type_name: str | None, unit: str | None) -> bool:
    name = (material_type_name or "").strip().lower()
    normalized_unit = (unit or "").strip().lower()
    return name in {"m", "roll", "rolls", "roll material"} or normalized_unit in {
        "m",
        "me",
        "meter",
        "meters",
        "sqm",
        "m2",
    }


def _simulation_unit(unit: str | None) -> str:
    """Current business rule: the BOM Total sqm field is treated as metres."""
    normalized = (unit or "").strip().lower()
    if normalized in {"m", "me", "meter", "meters", "sqm", "m2"}:
        return "m"
    if normalized in {"ea", "piece", "pieces"}:
        return "pcs"
    return unit or "pcs"


def _stock_owner_metadata(stock_unit) -> tuple[uuid.UUID | None, str | None, str | None]:
    owner = getattr(stock_unit, "user", None)
    return (
        getattr(stock_unit, "user_id", None),
        owner.full_name if owner else None,
        owner.role if owner else None,
    )


def _build_pools(
    db: Session,
    include_in_transit: bool,
    *,
    stock_scope_mode: str = "ALL",
    stock_owner_user_id: uuid.UUID | None = None,
    include_global_stock: bool = False,
    target_date: date | None = None,
) -> dict[str, MaterialPool]:
    """Build material pools by querying physical stock units."""
    assigned_only = stock_scope_mode == "OWNED_ONLY"
    materials = stock_repository.get_all_materials(db)
    if assigned_only:
        wh_units = stock_repository.get_positive_stock_units_by_status(
            db,
            'WAREHOUSE',
            assigned_user_id=stock_owner_user_id,
            assigned_only=True,
            include_global_stock=include_global_stock,
        )
        prod_units = stock_repository.get_positive_stock_units_by_status(
            db,
            'PRODUCTION',
            assigned_user_id=stock_owner_user_id,
            assigned_only=True,
            include_global_stock=include_global_stock,
        )
    else:
        wh_units = stock_repository.get_positive_stock_units_by_status(db, 'WAREHOUSE')
        prod_units = stock_repository.get_positive_stock_units_by_status(db, 'PRODUCTION')
    consumption_by_unit = stock_repository.get_cutting_consumption_by_stock_unit(db)
    legacy_consumption = stock_repository.get_unassigned_cutting_consumption_by_material(db)
    reserved_by_unit = stock_repository.get_reserved_quantities_by_stock_unit(db)
    transit_units = []
    if include_in_transit:
        if assigned_only:
            transit_units = stock_repository.get_positive_stock_units_by_status(
                db,
                'IN_TRANSIT',
                target_date=target_date,
                assigned_user_id=stock_owner_user_id,
                assigned_only=True,
                include_global_stock=include_global_stock,
            )
        else:
            transit_units = stock_repository.get_positive_stock_units_by_status(
                db, 'IN_TRANSIT', target_date=target_date,
            )
        
    pools = {}
    for mat, mtype in materials:
        mpn = mat.material_part_number
        if not mpn:
            continue
        is_roll = _is_roll_material_type(mtype.name, mtype.unit)
            
        pool = MaterialPool(material_part_number=mpn)
        
        # Add warehouse
        for su in [u for u in wh_units if u.material_part_number == mpn]:
            available_quantity = max(
                Decimal('0'), su.quantity - reserved_by_unit.get(su.stock_unit_id, Decimal('0'))
            )
            if available_quantity <= 0:
                continue
            assigned_user_id, assigned_user_name, assigned_user_role = _stock_owner_metadata(su)
            pool.warehouse_slots.append(StockSlot(
                stock_unit_id=su.stock_unit_id,
                source='WAREHOUSE',
                quantity=available_quantity,
                business_unit_id=su.business_unit_id,
                material_type=mtype.name,
                can_split=not is_roll,
                expected_arrival_date=su.expected_arrival_date,
                assigned_user_id=assigned_user_id,
                assigned_user_name=assigned_user_name,
                assigned_user_role=assigned_user_role,
            ))
            
        # Production remainder stays tied to its business stock-unit identifier.
        legacy_remaining = legacy_consumption.get(mpn, Decimal('0'))
        for su in [u for u in prod_units if u.material_part_number == mpn]:
            linked_consumed = consumption_by_unit.get(su.stock_unit_id, Decimal('0'))
            after_linked = max(Decimal('0'), su.quantity - linked_consumed)
            legacy_applied = min(after_linked, legacy_remaining)
            legacy_remaining -= legacy_applied
            rem = max(
                Decimal('0'),
                after_linked
                - legacy_applied
                - reserved_by_unit.get(su.stock_unit_id, Decimal('0')),
            )
            if rem <= 0:
                continue
            assigned_user_id, assigned_user_name, assigned_user_role = _stock_owner_metadata(su)
            pool.production_slots.append(StockSlot(
                stock_unit_id=su.stock_unit_id,
                source='PRODUCTION',
                quantity=rem,
                business_unit_id=su.business_unit_id,
                material_type=mtype.name,
                assigned_user_id=assigned_user_id,
                assigned_user_name=assigned_user_name,
                assigned_user_role=assigned_user_role,
            ))
            
        # Add in-transit
        for su in [u for u in transit_units if u.material_part_number == mpn]:
            available_quantity = max(
                Decimal('0'), su.quantity - reserved_by_unit.get(su.stock_unit_id, Decimal('0'))
            )
            if available_quantity <= 0:
                continue
            assigned_user_id, assigned_user_name, assigned_user_role = _stock_owner_metadata(su)
            pool.in_transit_slots.append(StockSlot(
                stock_unit_id=su.stock_unit_id,
                source='IN_TRANSIT',
                quantity=available_quantity,
                business_unit_id=su.business_unit_id,
                material_type=mtype.name,
                can_split=not is_roll,
                expected_arrival_date=su.expected_arrival_date,
                assigned_user_id=assigned_user_id,
                assigned_user_name=assigned_user_name,
                assigned_user_role=assigned_user_role,
            ))
            
        pools[mpn] = pool
        
    return pools


def preview_simulation(
    db: Session,
    request: SimulationPreviewRequest,
    *,
    actor: PolicyActor | None = None,
) -> SimulationPreviewResult:
    """Run a read-only simulation."""
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "simulation.run")

    if request.include_in_transit and request.target_date is None:
        raise ValidationException("target_date is required when including in-transit stock.")

    if not request.fgpns:
        raise ValidationException("At least one FGPN is required for simulation.")

    project = simulation_repository.get_project(db, request.project_id)
    if project is None:
        raise ValidationException(f"Project {request.project_id} not found.")
    if project.status != "Active":
        raise ValidationException(f"Project {request.project_id} is not active.")
    if (
        acting_actor.normalized_role == "LAUNCH_ENGINEER"
        and acting_actor.user_id is not None
        and acting_actor.user_id != project.launch_engineer_user_id
    ):
        raise ValidationException("Launch engineers may simulate only their assigned project.")

    stock_scope_mode = _normalize_stock_scope_mode(request.stock_scope_mode)
    if stock_scope_mode == "OWNED_ONLY":
        if request.stock_owner_user_id is None:
            raise ValidationException("stock_owner_user_id is required when stock_scope_mode is OWNED_ONLY.")
        stock_owner = stock_repository.get_user(db, request.stock_owner_user_id)
        if stock_owner is None:
            raise ValidationException(f"Stock owner user {request.stock_owner_user_id} not found.")
        if not stock_repository.is_affectable_stock_owner(stock_owner):
            raise ValidationException("Owned-only simulation owner must be a launch engineer or launch manager.")
        if request.stock_owner_user_id != project.launch_engineer_user_id:
            raise ValidationException(
                "Owned-only stock must belong to the launch engineer assigned to the selected project."
            )
        if (
            acting_actor.normalized_role == "LAUNCH_ENGINEER"
            and acting_actor.user_id is not None
            and request.stock_owner_user_id != acting_actor.user_id
        ):
            raise ValidationException("Launch engineers may use only their own assigned stock.")
        
    fgpn_ids = [f.fgpn_id for f in request.fgpns]
    po_line_ids = [f.po_line_id for f in request.fgpns if f.po_line_id is not None]
    po_fgpn_pairs = [(f.po_id, f.fgpn_id) for f in request.fgpns if f.po_line_id is None]
    
    boms = simulation_repository.get_current_boms_for_fgpns(db, fgpn_ids)
    fgpns_db = simulation_repository.get_fgpns(db, fgpn_ids)
    po_lines_db = simulation_repository.get_po_lines(db, po_line_ids)
    current_po_lines_db = simulation_repository.get_current_po_lines_for_po_fgpns(
        db,
        po_fgpn_pairs,
    )

    resolved_po_lines = []
    for req in request.fgpns:
        line = (
            po_lines_db.get(req.po_line_id)
            if req.po_line_id is not None
            else current_po_lines_db.get((req.po_id, req.fgpn_id))
        )
        if line is not None:
            resolved_po_lines.append(line)
    planned_by_line = simulation_repository.get_planned_launch_quantities_by_po_line(
        db,
        [line.po_line_id for line in resolved_po_lines],
    )
    
    # 1. Build Demands
    demands = []
    for request_index, req in enumerate(request.fgpns, start=1):
        if req.fgpn_id not in fgpns_db:
            raise ValidationException(f"FGPN {req.fgpn_id} not found.")
        if req.fgpn_id not in boms:
            raise ValidationException(f"No current BOM found for FGPN {req.fgpn_id}.")
        if fgpns_db[req.fgpn_id].project_id != request.project_id:
            raise ValidationException(
                f"FGPN {req.fgpn_id} does not belong to project {request.project_id}."
            )
        po_line = (
            po_lines_db.get(req.po_line_id)
            if req.po_line_id is not None
            else current_po_lines_db.get((req.po_id, req.fgpn_id))
        )
        if req.po_line_id is not None and po_line is None:
            raise ValidationException(f"PO line {req.po_line_id} not found.")
        if po_line is None:
            raise ValidationException(
                f"No current PO line found for PO {req.po_id} and FGPN {req.fgpn_id}."
            )
        if po_line is not None and po_line.fgpn_id != req.fgpn_id:
            raise ValidationException(
                f"PO line {req.po_line_id} does not belong to FGPN {req.fgpn_id}."
            )
        if po_line.po_version is not None and po_line.po_version.purchase_order is not None:
            resolved_po = po_line.po_version.purchase_order
            resolved_po_id = resolved_po.po_id
            if resolved_po_id != req.po_id:
                raise ValidationException(
                    f"PO line {po_line.po_line_id} does not belong to PO {req.po_id}."
                )
            if resolved_po.current_version_id != po_line.po_version_id:
                raise ValidationException(
                    f"PO line {po_line.po_line_id} is not part of the current PO version."
                )

        already_planned = planned_by_line.get(po_line.po_line_id, Decimal("0"))
        outstanding = max(Decimal("0"), po_line.ordered_quantity - already_planned)
        if req.requested_quantity > outstanding:
            raise ValidationException(
                f"Requested quantity {req.requested_quantity} exceeds outstanding quantity "
                f"{outstanding} for PO line {po_line.po_line_id}."
            )
            
        bom = boms[req.fgpn_id]
        fgpn = fgpns_db[req.fgpn_id]
        po_quantity = po_line.ordered_quantity if po_line is not None else req.requested_quantity
        priority = req.priority
        po_number = None
        if po_line is not None and po_line.po_version is not None:
            po = po_line.po_version.purchase_order
            po_number = po.po_number if po is not None else None
        
        sim_qty = req.requested_quantity
            
        demand = FgpnDemand(
            fgpn_id=req.fgpn_id,
            fgpn_code=fgpn.fgpn_code,
            priority=priority,
            po_quantity=po_quantity,
            requested_quantity=sim_qty,
            po_id=req.po_id,
            po_line_id=po_line.po_line_id,
            po_number=po_number,
            request_sequence=request_index
        )
        
        # Calculate material demand based on part_type
        for line in bom.lines:
            base_qty = Decimal('0')
            if line.part_type == 'M':
                base_qty = line.total_sqm if line.total_sqm is not None else Decimal('0')
            elif line.part_type == 'S':
                base_qty = line.total_quantity if line.total_quantity is not None else Decimal('0')
            else:
                # Fallback for any other part types to total_quantity
                base_qty = line.total_quantity if line.total_quantity is not None else Decimal('0')
                
            mat_qty = base_qty * sim_qty * request.safety_coefficient
            if mat_qty > 0:
                current = demand.material_demands.get(line.material_part_number, Decimal('0'))
                demand.material_demands[line.material_part_number] = current + mat_qty

        if not demand.material_demands:
            raise ValidationException(
                f"Current BOM for FGPN {req.fgpn_id} has no positive material demand."
            )
                
        demands.append(demand)
        
    # 2. Build Stock Pools
    if stock_scope_mode == "OWNED_ONLY":
        pools = _build_pools(
            db,
            request.include_in_transit,
            stock_scope_mode=stock_scope_mode,
            stock_owner_user_id=request.stock_owner_user_id,
            include_global_stock=request.include_global_stock,
            target_date=request.target_date,
        )
    else:
        pools = _build_pools(db, request.include_in_transit, target_date=request.target_date)
    
    # 3. Run Allocator
    demands, allocations = run_allocation_engine(demands, pools)
    
    # 4. Format Results
    mat_map = {m.material_part_number: (m, mt) for m, mt in stock_repository.get_all_materials(db) if m.material_part_number}
    if stock_scope_mode == "OWNED_ONLY":
        in_transit_stock = stock_repository.get_in_transit_stock_by_material(
            db,
            target_date=request.target_date,
            assigned_user_id=request.stock_owner_user_id,
            assigned_only=True,
            include_global_stock=request.include_global_stock,
        )
    else:
        in_transit_stock = stock_repository.get_in_transit_stock_by_material(db, target_date=request.target_date)
    
    # Aggregate material summaries
    mat_summaries = {}
    for demand in demands:
        for mpn, req_qty in demand.material_demands.items():
            if mpn not in mat_summaries:
                m, mt = mat_map.get(mpn, (None, None))
                mat_summaries[mpn] = {
                    'description': m.description if m else 'Unknown',
                    'unit': _simulation_unit(mt.unit if mt else None),
                    'total_demand': Decimal('0'),
                    'allocated_quantity': Decimal('0'),
                    'shortfall': Decimal('0')
                }
            mat_summaries[mpn]['total_demand'] += req_qty
            mat_summaries[mpn]['shortfall'] += demand.material_shortages.get(mpn, Decimal('0'))
            mat_summaries[mpn]['allocated_quantity'] += (req_qty - demand.material_shortages.get(mpn, Decimal('0')))
            
    result_mats = []
    for mpn, sums in mat_summaries.items():
        pool = pools.get(mpn)
        wh = sum(s.initial_quantity for s in pool.warehouse_slots) if pool else Decimal('0')
        prod = sum(s.initial_quantity for s in pool.production_slots) if pool else Decimal('0')
        allocated_transit = sum(s.initial_quantity for s in pool.in_transit_slots) if pool else Decimal('0')
        transit = allocated_transit if request.include_in_transit else in_transit_stock.get(mpn, Decimal('0'))
        avail = wh + prod + allocated_transit
        
        status = 'COVERED'
        if sums['shortfall'] > 0:
            status = 'PARTIALLY_COVERED' if sums['allocated_quantity'] > 0 else 'NOT_COVERED'
            
        result_mats.append(MaterialSimulationSummary(
            material_part_number=mpn,
            description=sums['description'],
            unit=sums['unit'],
            total_demand=sums['total_demand'],
            warehouse_stock=wh,
            cutman_wip=prod,
            in_transit=transit,
            available_stock=avail,
            allocated_quantity=sums['allocated_quantity'],
            shortfall=sums['shortfall'],
            status=status,
            suggestion=_material_suggestion(mpn, sums['shortfall'], request.include_in_transit, transit)
        ))
        
    # Format FGPN Summaries
    result_fgpns = []
    for d in demands:
        status = 'FULLY_COVERED'
        if not d.is_fully_covered:
            status = 'PARTIALLY_COVERED' if d.percent_covered > 0 else 'NOT_COVERED'
            
        result_fgpns.append(FgpnSimulationSummary(
            po_id=d.po_id,
            fgpn_id=d.fgpn_id,
            fgpn_code=d.fgpn_code,
            po_line_id=d.po_line_id,
            po_number=d.po_number,
            po_quantity=d.po_quantity,
            simulation_quantity=d.requested_quantity,
            launchable_quantity=d.launchable_quantity,
            priority=d.priority,
            coverage_percent=d.percent_covered,
            status=status,
            material_requirements=d.material_demands,
            material_allocations=d.material_allocations,
            material_shortages=d.material_shortages,
            suggestion=_fgpn_suggestion(status, d.launchable_quantity, d.requested_quantity)
        ))
        
    alloc_details = []
    slot_allocs = {}
    for _, slot, qty in allocations:
        key = id(slot)
        if key not in slot_allocs:
            slot_allocs[key] = {
                'slot': slot,
                'allocated': Decimal('0')
            }
        slot_allocs[key]['allocated'] += qty
        
    slot_to_mpn = {}
    for mpn, pool in pools.items():
        for s in pool.all_slots():
            slot_to_mpn[id(s)] = mpn
            
    for key, data in slot_allocs.items():
        slot = data['slot']
        mpn = slot_to_mpn.get(key, "Unknown")
        alloc_details.append(AllocationDetail(
            stock_unit_id=slot.stock_unit_id,
            business_unit_id=slot.business_unit_id,
            material_part_number=mpn,
            source=slot.source,
            assigned_user_id=slot.assigned_user_id,
            assigned_user_name=slot.assigned_user_name,
            assigned_user_role=slot.assigned_user_role,
            is_whole_issue=not slot.can_split,
            available_quantity=slot.initial_quantity,
            allocated_quantity=data['allocated'],
            remaining_quantity=slot.remaining,
            expected_arrival_date=slot.expected_arrival_date.date() if slot.expected_arrival_date else None
        ))
        
    is_feasible = all(d.is_fully_covered for d in demands)
    total_requested = sum((d.requested_quantity for d in demands), Decimal('0'))
    total_launchable = sum((d.launchable_quantity for d in demands), Decimal('0'))
        
    return SimulationPreviewResult(
        target_date=request.target_date,
        stock_scope='INCLUDING_IN_TRANSIT' if request.include_in_transit else 'CURRENT_STOCK',
        stock_scope_mode=stock_scope_mode,
        stock_owner_user_id=request.stock_owner_user_id if stock_scope_mode == "OWNED_ONLY" else None,
        include_global_stock=request.include_global_stock if stock_scope_mode == "OWNED_ONLY" else False,
        is_feasible=is_feasible,
        total_requested_quantity=total_requested,
        total_launchable_quantity=total_launchable,
        suggestion=_preview_suggestion(is_feasible, result_mats),
        material_summaries=result_mats,
        fgpn_summaries=result_fgpns,
        allocation_details=alloc_details
    )


def save_simulation(
    db: Session,
    request: SimulationSaveRequest,
    user_id: str,
    *,
    actor: PolicyActor | None = None,
) -> SimulationSaveResponse:
    """Run preview and save the result."""
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "simulation.run")

    # Enforce limit of 100 simulations per user
    user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    current_count = simulation_repository.count_user_simulations(db, user_uuid)
    if current_count >= 100:
        raise ValidationException("You have reached the limit of 100 saved simulations. Please delete some before saving a new one.")
        
    if request.preview_request.target_date not in (None, request.target_date):
        raise ValidationException("Preview and save target dates must match.")
    preview_request = request.preview_request.model_copy(update={"target_date": request.target_date})
    preview = preview_simulation(db, preview_request, actor=acting_actor)
    stock_repository.lock_stock_units_for_materials(
        db,
        [material.material_part_number for material in preview.material_summaries],
    )
    # Re-run after acquiring the material locks so a competing save cannot reserve
    # quantities calculated before the first transaction committed.
    preview = preview_simulation(db, preview_request, actor=acting_actor)
    
    # Extract shortfalls
    shortfalls = {}
    for mat in preview.material_summaries:
        if mat.shortfall > 0:
            shortfalls[mat.material_part_number] = str(mat.shortfall)
            
    # Extract allocations
    db_allocs = []
    for alloc in preview.allocation_details:
        if alloc.stock_unit_id is not None:
            db_allocs.append({
                'stock_unit_id': alloc.stock_unit_id,
                'allocated_quantity': alloc.allocated_quantity,
                'source_location': alloc.source,
                'is_whole_issue': alloc.is_whole_issue,
            })
            
    sim_id = simulation_repository.save_simulation(
        db,
        project_id=request.preview_request.project_id,
        simulation_mode=preview.stock_scope,
        stock_scope_mode=preview.stock_scope_mode,
        stock_owner_user_id=preview.stock_owner_user_id,
        include_global_stock=preview.include_global_stock,
        target_date=request.target_date,
        safety_coefficient=request.preview_request.safety_coefficient,
        is_feasible=preview.is_feasible,
        shortfall_json=json.dumps(shortfalls),
        mtg_minutes_document_id=request.mtg_minutes_document_id,
        created_by=user_uuid,
        allocations=db_allocs,
        selected_fgpns=[
            {
                'po_id': fgpn.po_id,
                'fgpn_id': fgpn.fgpn_id,
                'po_line_id': fgpn.po_line_id,
                'priority': fgpn.priority,
                'po_quantity': fgpn.po_quantity,
                'simulation_quantity': fgpn.simulation_quantity,
                'launchable_quantity': fgpn.launchable_quantity,
            }
            for fgpn in preview.fgpn_summaries
        ],
    )
    
    db.commit()
    saved = simulation_repository.get_simulation(db, sim_id)
    return SimulationSaveResponse(
        simulation_id=sim_id,
        status=saved.workflow_status,
        document_due_at=saved.document_due_at,
    )


def attach_meeting_document(
    db: Session,
    simulation_id: int,
    document_id: int,
    *,
    actor: PolicyActor | None = None,
) -> SimulationWorkflowResponse:
    """Attach the required PV while its reservation is active."""
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "simulation.run")
    simulation = simulation_repository.get_simulation_for_update(db, simulation_id)
    if simulation is None:
        raise NotFoundException(f"Simulation {simulation_id} not found.")
    if simulation.workflow_status == "LAUNCHED":
        raise ConflictException("A launched simulation cannot change its meeting document.")
    if simulation.workflow_status == "RELEASED" or (
        simulation.document_due_at is not None
        and simulation.document_due_at <= datetime.now()
    ):
        _release_reservation_rows(simulation)
        db.commit()
        raise ConflictException(
            "The 24-hour document window expired. Run and save a new simulation."
        )

    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundException(f"Document {document_id} not found.")
    if document.document_type != "MTG_MINUTES":
        raise ValidationException("The attached document must have type MTG_MINUTES.")

    simulation.mtg_minutes_document_id = document_id
    simulation.workflow_status = "READY"
    simulation.document_due_at = None
    db.commit()
    return SimulationWorkflowResponse(simulation_id=simulation_id, status="READY")


def _release_reservation_rows(simulation) -> None:
    simulation.workflow_status = "RELEASED"
    for allocation in simulation.stock_allocations:
        if allocation.allocation_type == "SIMULATION" and allocation.status == "RESERVED":
            allocation.status = "RELEASED"


def release_expired_reservation(
    db: Session,
    simulation_id: int,
    *,
    actor: PolicyActor | None = None,
) -> SimulationWorkflowResponse:
    """Release an expired reservation; never reverse an executed launch."""
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "simulation.run")
    simulation = simulation_repository.get_simulation_for_update(db, simulation_id)
    if simulation is None:
        raise NotFoundException(f"Simulation {simulation_id} not found.")
    if simulation.workflow_status == "LAUNCHED":
        return SimulationWorkflowResponse(simulation_id=simulation_id, status="LAUNCHED")
    if simulation.mtg_minutes_document_id is not None:
        return SimulationWorkflowResponse(simulation_id=simulation_id, status=simulation.workflow_status)
    if simulation.document_due_at is None or simulation.document_due_at > datetime.now():
        raise ConflictException("The document window is still active; the reservation cannot be released yet.")
    _release_reservation_rows(simulation)
    db.commit()
    return SimulationWorkflowResponse(simulation_id=simulation_id, status="RELEASED")


def _saved_simulation_preview_request(
    simulation,
    selected_fgpns,
    *,
    for_launch: bool = False,
) -> SimulationPreviewRequest:
    return SimulationPreviewRequest(
        project_id=simulation.project_id,
        fgpns=[
            FgpnSimulationRequest(
                po_id=row.po_id,
                fgpn_id=row.fgpn_id,
                po_line_id=row.po_line_id,
                priority=row.priority,
                requested_quantity=row.simulation_quantity,
            )
            for row in selected_fgpns
        ],
        include_in_transit=(
            simulation.simulation_mode == 'INCLUDING_IN_TRANSIT' and not for_launch
        ),
        target_date=simulation.target_date,
        safety_coefficient=simulation.safety_coefficient,
        stock_scope_mode=simulation.stock_scope_mode,
        stock_owner_user_id=simulation.stock_owner_user_id,
        include_global_stock=simulation.include_global_stock,
    )


def _launch_allocations_from_preview(preview: SimulationPreviewResult) -> list[dict]:
    return [
        {
            'stock_unit_id': alloc.stock_unit_id,
            'allocated_quantity': alloc.allocated_quantity,
            'source_location': alloc.source,
            'is_whole_issue': alloc.is_whole_issue,
        }
        for alloc in preview.allocation_details
        if alloc.stock_unit_id is not None
    ]


def _launch_allocations_from_saved_simulation(simulation_allocations) -> list[dict]:
    return [
        {
            'stock_unit_id': alloc.stock_unit_id,
            'allocated_quantity': alloc.allocated_quantity,
            'source_location': alloc.source_location,
            'is_whole_issue': alloc.is_whole_issue,
        }
        for alloc in simulation_allocations
    ]


def _find_unavailable_saved_allocations(
    db: Session, simulation_allocations, *, target_date: date,
) -> list[LaunchAvailabilityIssue]:
    stock_units = stock_repository.get_stock_units_by_ids(
        db,
        [alloc.stock_unit_id for alloc in simulation_allocations],
    )
    issues = []
    for alloc in simulation_allocations:
        stock_unit = stock_units.get(alloc.stock_unit_id)
        if stock_unit is None:
            issues.append(LaunchAvailabilityIssue(
                stock_unit_id=alloc.stock_unit_id,
                material_part_number="UNKNOWN",
                requested_quantity=alloc.allocated_quantity,
                available_quantity=Decimal('0'),
                current_status="MISSING",
                reason="Stock unit no longer exists.",
            ))
            continue

        reason = None
        if alloc.status != "RESERVED":
            reason = "The saved reservation is no longer active."
        elif alloc.source_location == "PRODUCTION":
            consumed = stock_repository.get_cutting_consumption_by_stock_unit(db).get(
                stock_unit.stock_unit_id, Decimal("0")
            )
            if stock_unit.status != "PRODUCTION" or stock_unit.quantity - consumed < alloc.allocated_quantity:
                reason = "The identified production remainder is no longer available."
        elif stock_unit.status == "IN_TRANSIT":
            reason = "Supplier ETA is planning information; warehouse arrival must be confirmed before launch."
        elif not stock_repository.is_stock_unit_available_for_quantity(stock_unit, alloc.allocated_quantity):
            reason = "Stock unit was already consumed, moved, or no longer has enough quantity."
        if reason:
            issues.append(LaunchAvailabilityIssue(
                stock_unit_id=stock_unit.stock_unit_id,
                material_part_number=stock_unit.material_part_number,
                requested_quantity=alloc.allocated_quantity,
                available_quantity=stock_unit.quantity,
                current_status=stock_unit.status,
                reason=reason,
            ))
    return issues


def review_simulation_for_launch(
    db: Session,
    simulation_id: int,
    *,
    actor: PolicyActor | None = None,
) -> LaunchReviewResult:
    """Review whether a saved simulation can still become a launch."""
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "simulation.view")

    simulation = simulation_repository.get_simulation(db, simulation_id)
    if simulation is None:
        raise NotFoundException(f"Simulation {simulation_id} not found.")
    if simulation.workflow_status == "AWAITING_DOCUMENT":
        if simulation.document_due_at is not None and simulation.document_due_at <= datetime.now():
            return LaunchReviewResult(
                simulation_id=simulation_id,
                can_launch=False,
                original_allocations_available=False,
                message="The 24-hour meeting-document window expired; save a new simulation.",
            )
        return LaunchReviewResult(
            simulation_id=simulation_id,
            can_launch=False,
            original_allocations_available=True,
            message="Attach the meeting document before launching this simulation.",
        )
    if simulation.workflow_status == "RELEASED":
        return LaunchReviewResult(
            simulation_id=simulation_id,
            can_launch=False,
            original_allocations_available=False,
            message="This reservation was released; save a new simulation.",
        )
    if simulation.workflow_status == "LAUNCHED":
        return LaunchReviewResult(
            simulation_id=simulation_id,
            can_launch=True,
            original_allocations_available=True,
            message="This simulation was already launched.",
        )

    simulation_allocations = simulation_repository.get_simulation_allocations(
        db,
        simulation_id,
        allocation_type='SIMULATION',
    )
    issues = _find_unavailable_saved_allocations(db, simulation_allocations, target_date=simulation.target_date)
    if not issues:
        return LaunchReviewResult(
            simulation_id=simulation_id,
            can_launch=True,
            original_allocations_available=True,
            message="Saved simulation stock units are still available.",
        )

    selected_fgpns = simulation_repository.get_simulation_selected_fgpns(db, simulation_id)
    replacement_preview = preview_simulation(
        db,
        _saved_simulation_preview_request(simulation, selected_fgpns, for_launch=True),
        actor=acting_actor,
    )
    if replacement_preview.is_feasible:
        return LaunchReviewResult(
            simulation_id=simulation_id,
            can_launch=True,
            original_allocations_available=False,
            reallocated=True,
            message="Some saved stock units are unavailable, but current stock can satisfy the same launch quantities with replacements.",
            unavailable_stock_units=issues,
            replacement_preview=replacement_preview,
        )

    return LaunchReviewResult(
        simulation_id=simulation_id,
        can_launch=False,
        original_allocations_available=False,
        reallocated=True,
        message="Some saved stock units are unavailable and no replacement allocation can satisfy the saved launch quantities.",
        unavailable_stock_units=issues,
        replacement_preview=replacement_preview,
    )


def launch_saved_simulation(
    db: Session,
    simulation_id: int,
    *,
    actor: PolicyActor | None = None,
) -> LaunchSimulationResponse:
    """Confirm a saved simulation as a launch and issue stock to production."""
    acting_actor = actor or system_actor()
    policy_engine.require(acting_actor, "launch.manage")

    simulation = simulation_repository.get_simulation_for_update(db, simulation_id)
    if simulation is None:
        raise NotFoundException(f"Simulation {simulation_id} not found.")
    if simulation.launched_at is not None or simulation.workflow_status == "LAUNCHED":
        existing = simulation_repository.get_simulation_allocations(
            db, simulation_id, allocation_type="LAUNCH",
        )
        return LaunchSimulationResponse(
            simulation_id=simulation_id,
            status="LAUNCHED",
            launch_allocation_count=len(existing),
            idempotent_replay=True,
        )
    if simulation.workflow_status == "AWAITING_DOCUMENT":
        if simulation.document_due_at is not None and simulation.document_due_at <= datetime.now():
            _release_reservation_rows(simulation)
            db.commit()
            raise ConflictException(
                "The meeting document was not attached within 24 hours; the reservation was released."
            )
        raise ConflictException("Attach the meeting document before launching this simulation.")
    if simulation.workflow_status == "RELEASED":
        raise ConflictException("This reservation was released; run and save a new simulation.")

    review = review_simulation_for_launch(db, simulation_id, actor=acting_actor)
    if not review.can_launch:
        raise ConflictException(
            "Cannot launch: saved stock units are unavailable and replacement stock cannot satisfy the launch.",
            details=review.model_dump(),
        )

    if review.reallocated and review.replacement_preview is not None:
        launch_allocations = _launch_allocations_from_preview(review.replacement_preview)
    else:
        launch_allocations = _launch_allocations_from_saved_simulation(
            simulation_repository.get_simulation_allocations(
                db,
                simulation_id,
                allocation_type='SIMULATION',
            )
        )

    stock_units = stock_repository.get_stock_units_by_ids(
        db,
        [alloc['stock_unit_id'] for alloc in launch_allocations],
        for_update=True,
    )
    actual_launch_allocations = []
    if acting_actor.user_id is not None:
        movement_actor_user_id = acting_actor.user_id
    else:
        from app.repositories.bom_repository import _get_system_user
        movement_actor_user_id = _get_system_user(db)
    for alloc in launch_allocations:
        stock_unit = stock_units.get(alloc['stock_unit_id'])
        if stock_unit is None:
            raise ConflictException(
                f"Cannot launch: StockUnit {alloc['stock_unit_id']} no longer exists."
            )
        try:
            source_status = stock_unit.status
            if alloc['source_location'] == "PRODUCTION":
                if stock_unit.status != "PRODUCTION":
                    raise ValueError(
                        f"Production StockUnit {stock_unit.stock_unit_id} is no longer in production."
                    )
                issued_stock_unit = stock_unit
            else:
                issued_stock_unit = stock_repository.issue_stock_unit_to_production(
                    db,
                    stock_unit,
                    alloc['allocated_quantity'],
                    is_whole_issue=alloc['is_whole_issue'],
                )
                stock_movement_service.record_movement(
                    db,
                    material_part_number=stock_unit.material_part_number,
                    movement_type="STOCK_ISSUED_TO_PRODUCTION",
                    quantity_change=-alloc['allocated_quantity'],
                    actor_user_id=movement_actor_user_id,
                    stock_unit_id=issued_stock_unit.stock_unit_id,
                    stock_unit_reference=issued_stock_unit.business_unit_id,
                    from_status=source_status,
                    to_status="ISSUED_TO_PRODUCTION",
                    note=f"Simulation {simulation_id} launch allocation.",
                )
            actual_launch_allocations.append({
                **alloc,
                'stock_unit_id': issued_stock_unit.stock_unit_id,
            })
        except ValueError as exc:
            raise ConflictException(str(exc)) from exc

    created = simulation_repository.add_stock_allocations(
        db,
        simulation_id=simulation_id,
        allocations=actual_launch_allocations,
        allocation_type='LAUNCH',
        status='COMMITTED',
    )
    simulation.launched_at = datetime.now()
    simulation.workflow_status = "LAUNCHED"
    for allocation in simulation.stock_allocations:
        if allocation.allocation_type == "SIMULATION" and allocation.status == "RESERVED":
            allocation.status = "RELEASED"
    db.commit()

    return LaunchSimulationResponse(
        simulation_id=simulation_id,
        status='LAUNCHED',
        reallocated=review.reallocated,
        launch_allocation_count=len(created),
    )
