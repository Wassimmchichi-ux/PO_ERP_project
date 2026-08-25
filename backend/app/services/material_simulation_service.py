"""Service for Material Simulation."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.exceptions.base import ConflictException, NotFoundException, ValidationException
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
    SimulationSaveRequest,
    SimulationSaveResponse
)
from app.services.stock_management_service import _compute_remaining_production
from app.services.simulation_allocator import (
    StockSlot, 
    MaterialPool, 
    FgpnDemand, 
    run_allocation_engine
)


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


def _is_roll_material_type(material_type_name: str | None, unit: str | None) -> bool:
    name = (material_type_name or "").strip().lower()
    normalized_unit = (unit or "").strip().lower()
    return name in {"m", "roll", "rolls", "roll material"} or normalized_unit in {
        "m",
        "meter",
        "meters",
        "sqm",
        "m2",
    }


def _build_pools(db: Session, include_in_transit: bool) -> dict[str, MaterialPool]:
    """Build material pools by querying physical stock units."""
    materials = stock_repository.get_all_materials(db)
    wh_units = stock_repository.get_positive_stock_units_by_status(db, 'WAREHOUSE')
    prod_sent_map = stock_repository.get_production_stock_by_material(db)
    cons_map = stock_repository.get_cutting_consumption_by_material(db)
    transit_units = []
    if include_in_transit:
        transit_units = stock_repository.get_positive_stock_units_by_status(db, 'IN_TRANSIT')
        
    pools = {}
    for mat, mtype in materials:
        mpn = mat.material_part_number
        if not mpn:
            continue
        is_roll = _is_roll_material_type(mtype.name, mtype.unit)
            
        pool = MaterialPool(material_part_number=mpn)
        
        # Add warehouse
        for su in [u for u in wh_units if u.material_part_number == mpn]:
            pool.warehouse_slots.append(StockSlot(
                stock_unit_id=su.stock_unit_id,
                source='WAREHOUSE',
                quantity=su.quantity,
                material_type=mtype.name,
                can_split=not is_roll,
                expected_arrival_date=su.expected_arrival_date
            ))
            
        # Add production (we create one virtual slot for the remaining qty)
        sent = prod_sent_map.get(mpn, Decimal('0'))
        consumed = cons_map.get(mpn, Decimal('0'))
        rem = _compute_remaining_production(sent, consumed)
        if rem > 0:
            pool.production_slots.append(StockSlot(
                stock_unit_id=None,  # Virtual slot representing aggregated production remainder
                source='PRODUCTION',
                quantity=rem,
                material_type=mtype.name
            ))
            
        # Add in-transit
        for su in [u for u in transit_units if u.material_part_number == mpn]:
            pool.in_transit_slots.append(StockSlot(
                stock_unit_id=su.stock_unit_id,
                source='IN_TRANSIT',
                quantity=su.quantity,
                material_type=mtype.name,
                can_split=not is_roll,
                expected_arrival_date=su.expected_arrival_date
            ))
            
        pools[mpn] = pool
        
    return pools


def preview_simulation(db: Session, request: SimulationPreviewRequest) -> SimulationPreviewResult:
    """Run a read-only simulation."""
    if not request.fgpns:
        raise ValidationException("At least one FGPN is required for simulation.")
        
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
    
    # 1. Build Demands
    demands = []
    for request_index, req in enumerate(request.fgpns, start=1):
        if req.fgpn_id not in fgpns_db:
            raise ValidationException(f"FGPN {req.fgpn_id} not found.")
        if req.fgpn_id not in boms:
            raise ValidationException(f"No current BOM found for FGPN {req.fgpn_id}.")
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
            resolved_po_id = po_line.po_version.purchase_order.po_id
            if resolved_po_id != req.po_id:
                raise ValidationException(
                    f"PO line {po_line.po_line_id} does not belong to PO {req.po_id}."
                )
            
        bom = boms[req.fgpn_id]
        fgpn = fgpns_db[req.fgpn_id]
        po_quantity = po_line.ordered_quantity if po_line is not None else req.requested_quantity
        priority = request_index
        po_number = None
        if po_line is not None and po_line.po_version is not None:
            po = po_line.po_version.purchase_order
            po_number = po.po_number if po is not None else None
        
        # Calculate simulation qty based on strategy
        sim_qty = req.requested_quantity
        if request.allocation_strategy in ('MANUAL', 'PRIORITY_PLUS_MANUAL') and req.manual_quantity is not None:
            sim_qty = req.manual_quantity
            
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
                
        demands.append(demand)
        
    # 2. Build Stock Pools
    pools = _build_pools(db, request.include_in_transit)
    
    # 3. Run Allocator
    demands, allocations = run_allocation_engine(demands, pools, request.allocation_strategy)
    
    # 4. Format Results
    mat_map = {m.material_part_number: (m, mt) for m, mt in stock_repository.get_all_materials(db) if m.material_part_number}
    in_transit_stock = stock_repository.get_in_transit_stock_by_material(db)
    
    # Aggregate material summaries
    mat_summaries = {}
    for demand in demands:
        for mpn, req_qty in demand.material_demands.items():
            if mpn not in mat_summaries:
                m, mt = mat_map.get(mpn, (None, None))
                mat_summaries[mpn] = {
                    'description': m.description if m else 'Unknown',
                    'unit': mt.unit if mt else 'pcs',
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
        
    # Format Allocation Details
    alloc_details = []
    for fgpn_code, slot, qty in allocations:
        # Note: the UI wants per-material allocation details, not necessarily per-FGPN,
        # but our allocator tracks it per-slot.
        pass # We'll just group by slot
        
    # Group allocations by slot
    slot_allocs = {}
    for _, slot, qty in allocations:
        key = id(slot)
        if key not in slot_allocs:
            slot_allocs[key] = {
                'slot': slot,
                'allocated': Decimal('0')
            }
        slot_allocs[key]['allocated'] += qty
        
    # In order to know material part number for a slot, we need to find it in the pools
    # A faster way: just pass mpn through the allocator. Let's fix that.
    # Actually, we can just look it up.
    slot_to_mpn = {}
    for mpn, pool in pools.items():
        for s in pool.all_slots():
            slot_to_mpn[id(s)] = mpn
            
    for key, data in slot_allocs.items():
        slot = data['slot']
        mpn = slot_to_mpn.get(key, "Unknown")
        alloc_details.append(AllocationDetail(
            stock_unit_id=slot.stock_unit_id,
            material_part_number=mpn,
            source=slot.source,
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
        stock_scope='INCLUDING_IN_TRANSIT' if request.include_in_transit else 'CURRENT_STOCK',
        allocation_strategy=request.allocation_strategy,
        is_feasible=is_feasible,
        total_requested_quantity=total_requested,
        total_launchable_quantity=total_launchable,
        suggestion=_preview_suggestion(is_feasible, result_mats),
        material_summaries=result_mats,
        fgpn_summaries=result_fgpns,
        allocation_details=alloc_details
    )


def save_simulation(db: Session, request: SimulationSaveRequest, user_id: str) -> SimulationSaveResponse:
    """Run preview and save the result."""
    # Enforce limit of 100 simulations per user
    user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    current_count = simulation_repository.count_user_simulations(db, user_uuid)
    if current_count >= 100:
        raise ValidationException("You have reached the limit of 100 saved simulations. Please delete some before saving a new one.")
        
    preview = preview_simulation(db, request.preview_request)
    
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
        launch_id=request.launch_id,
        simulation_mode=preview.stock_scope,
        allocation_strategy=preview.allocation_strategy,
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
    return SimulationSaveResponse(simulation_id=sim_id)


def _saved_simulation_preview_request(
    simulation,
    selected_fgpns,
) -> SimulationPreviewRequest:
    return SimulationPreviewRequest(
        launch_id=simulation.launch_id,
        fgpns=[
            FgpnSimulationRequest(
                po_id=row.po_id,
                fgpn_id=row.fgpn_id,
                po_line_id=row.po_line_id,
                requested_quantity=row.simulation_quantity,
            )
            for row in selected_fgpns
        ],
        allocation_strategy=simulation.allocation_strategy,
        include_in_transit=simulation.simulation_mode == 'INCLUDING_IN_TRANSIT',
        safety_coefficient=simulation.safety_coefficient,
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


def _find_unavailable_saved_allocations(db: Session, simulation_allocations) -> list[LaunchAvailabilityIssue]:
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

        if not stock_repository.is_stock_unit_available_for_quantity(stock_unit, alloc.allocated_quantity):
            issues.append(LaunchAvailabilityIssue(
                stock_unit_id=stock_unit.stock_unit_id,
                material_part_number=stock_unit.material_part_number,
                requested_quantity=alloc.allocated_quantity,
                available_quantity=stock_unit.quantity,
                current_status=stock_unit.status,
                reason="Stock unit was already consumed, moved, or no longer has enough quantity.",
            ))
    return issues


def review_simulation_for_launch(db: Session, simulation_id: int) -> LaunchReviewResult:
    """Review whether a saved simulation can still become a launch."""
    simulation = simulation_repository.get_simulation(db, simulation_id)
    if simulation is None:
        raise NotFoundException(f"Simulation {simulation_id} not found.")

    simulation_allocations = simulation_repository.get_simulation_allocations(
        db,
        simulation_id,
        allocation_type='SIMULATION',
    )
    issues = _find_unavailable_saved_allocations(db, simulation_allocations)
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
        _saved_simulation_preview_request(simulation, selected_fgpns),
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


def launch_saved_simulation(db: Session, simulation_id: int) -> LaunchSimulationResponse:
    """Confirm a saved simulation as a launch and issue stock to production."""
    review = review_simulation_for_launch(db, simulation_id)
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
    )
    actual_launch_allocations = []
    for alloc in launch_allocations:
        stock_unit = stock_units.get(alloc['stock_unit_id'])
        if stock_unit is None:
            raise ConflictException(
                f"Cannot launch: StockUnit {alloc['stock_unit_id']} no longer exists."
            )
        try:
            issued_stock_unit = stock_repository.issue_stock_unit_to_production(
                db,
                stock_unit,
                alloc['allocated_quantity'],
                is_whole_issue=alloc['is_whole_issue'],
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
        status='ISSUED_TO_PRODUCTION',
    )
    db.commit()

    return LaunchSimulationResponse(
        simulation_id=simulation_id,
        status='LAUNCHED',
        reallocated=review.reallocated,
        launch_allocation_count=len(created),
    )
