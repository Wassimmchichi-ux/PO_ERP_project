"""Core Simulation Allocation Algorithm."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
import uuid
from typing import Optional


@dataclass
class StockSlot:
    """Represents a discrete chunk of available material."""
    stock_unit_id: Optional[int]
    source: str  # WAREHOUSE, PRODUCTION, IN_TRANSIT
    quantity: Decimal
    business_unit_id: Optional[str] = None
    material_type: Optional[str] = None
    can_split: bool = True
    available: bool = True
    expected_arrival_date: Optional[datetime] = None
    assigned_user_id: Optional[uuid.UUID] = None
    assigned_user_name: Optional[str] = None
    assigned_user_role: Optional[str] = None
    initial_quantity: Decimal = field(init=False)

    def __post_init__(self) -> None:
        self.initial_quantity = self.quantity

    @property
    def remaining(self) -> Decimal:
        return self.quantity if self.available else Decimal('0')


@dataclass
class MaterialPool:
    """Total stock available for a given material."""
    material_part_number: str
    warehouse_slots: list[StockSlot] = field(default_factory=list)
    production_slots: list[StockSlot] = field(default_factory=list)
    in_transit_slots: list[StockSlot] = field(default_factory=list)

    def total_available(self) -> Decimal:
        return sum((s.remaining for s in self.all_slots()), Decimal('0'))

    def all_slots(self) -> list[StockSlot]:
        return self.production_slots + self.warehouse_slots + self.in_transit_slots


@dataclass
class FgpnDemand:
    """Material demand for a specific FGPN."""
    fgpn_id: int
    fgpn_code: str
    priority: int
    po_quantity: Decimal
    requested_quantity: Decimal
    po_id: int = 0
    po_line_id: Optional[int] = None
    po_number: Optional[str] = None
    request_sequence: int = 0
    material_demands: dict[str, Decimal] = field(default_factory=dict)
    
    # Track fulfillment
    percent_covered: Decimal = Decimal('100.0')
    is_fully_covered: bool = True
    material_shortages: dict[str, Decimal] = field(default_factory=dict)
    material_allocations: dict[str, Decimal] = field(default_factory=dict)

    @property
    def launchable_quantity(self) -> Decimal:
        """Return the maximum finished-good quantity covered by allocated materials."""
        if self.requested_quantity <= 0:
            return Decimal('0')
        if not self.material_demands:
            return self.requested_quantity

        feasible_quantities = []
        for mpn, demand in self.material_demands.items():
            if demand <= 0:
                continue
            allocated = self.material_allocations.get(mpn, Decimal('0'))
            feasible_quantities.append((allocated / demand) * self.requested_quantity)

        if not feasible_quantities:
            return self.requested_quantity

        launchable = min(feasible_quantities)
        return min(self.requested_quantity, launchable)


def allocate_material(
    pool: MaterialPool, 
    demand: Decimal
) -> tuple[Decimal, list[tuple[StockSlot, Decimal]]]:
    """Greedy + Local Refinement allocation algorithm.
    
    Tries to allocate `demand` from `pool` in a specific order:
    1. PRODUCTION
    2. WAREHOUSE
    3. IN_TRANSIT
    
    Inside each source, it sorts by remaining quantity ASC to minimize leftovers,
    but checks if a single slot fits perfectly first.
    
    Returns:
        allocated_total: Decimal
        allocations: list of (StockSlot, allocated_amount)
    """
    if demand <= 0:
        return Decimal('0'), []

    total_allocated = Decimal('0')
    allocations = []
    remaining_demand = demand

    for source_slots in (pool.production_slots, pool.warehouse_slots, pool.in_transit_slots):
        if remaining_demand <= 0:
            break

        available_slots = [s for s in source_slots if s.remaining > 0]
        if not available_slots:
            continue

        splittable_slots = [s for s in available_slots if s.can_split]
        whole_slots = [s for s in available_slots if not s.can_split]

        if whole_slots:
            chosen_slots = _choose_whole_slots(whole_slots, remaining_demand)
            for slot in chosen_slots:
                physical_qty = slot.remaining
                covered_qty = min(physical_qty, remaining_demand)
                slot.quantity = Decimal('0')
                slot.available = False
                total_allocated += covered_qty
                remaining_demand -= covered_qty
                allocations.append((slot, physical_qty))
                if remaining_demand <= 0:
                    break

            if remaining_demand <= 0:
                break

        if not splittable_slots:
            continue

        # LOCAL REFINEMENT: Is there a single splittable slot that exactly matches demand?
        exact_match = [s for s in splittable_slots if s.remaining == remaining_demand]
        if exact_match:
            chosen = exact_match[0]
            chosen.quantity -= remaining_demand
            if chosen.quantity <= 0:
                chosen.quantity = Decimal('0')
                chosen.available = False
            total_allocated += remaining_demand
            allocations.append((chosen, remaining_demand))
            remaining_demand = Decimal('0')
            break
            
        # GREEDY: Sort by smallest first to consume fragments before breaking large blocks
        splittable_slots.sort(key=lambda s: s.remaining)
        
        for slot in splittable_slots:
            if remaining_demand <= 0:
                break
                
            qty_to_take = min(slot.remaining, remaining_demand)
            slot.quantity -= qty_to_take
            if slot.quantity <= 0:
                slot.quantity = Decimal('0')
                slot.available = False
            total_allocated += qty_to_take
            remaining_demand -= qty_to_take
            allocations.append((slot, qty_to_take))

    return total_allocated, allocations


def _choose_whole_slots(slots: list[StockSlot], demand: Decimal) -> list[StockSlot]:
    """Choose all-or-nothing slots with the least physical over-issue."""
    sorted_slots = sorted(slots, key=lambda s: s.remaining)
    total_available = sum((s.remaining for s in sorted_slots), Decimal('0'))
    if total_available <= demand:
        return sorted_slots

    best: tuple[Decimal, Decimal, int, list[StockSlot]] | None = None

    def search(index: int, chosen: list[StockSlot], total: Decimal) -> None:
        nonlocal best
        if total >= demand:
            over_issue = total - demand
            candidate = (over_issue, total, len(chosen), chosen.copy())
            if best is None or candidate[:3] < best[:3]:
                best = candidate
            return
        if index >= len(sorted_slots):
            return
        if best is not None and total >= best[1]:
            return

        search(index + 1, chosen, total)
        chosen.append(sorted_slots[index])
        search(index + 1, chosen, total + sorted_slots[index].remaining)
        chosen.pop()

    if len(sorted_slots) <= 18:
        search(0, [], Decimal('0'))
        if best is not None:
            return sorted(best[3], key=lambda s: s.remaining)

    chosen = []
    total = Decimal('0')
    for slot in sorted_slots:
        chosen.append(slot)
        total += slot.remaining
        if total >= demand:
            break
    return chosen


def run_allocation_engine(
    fgpn_demands: list[FgpnDemand],
    material_pools: dict[str, MaterialPool],
) -> tuple[list[FgpnDemand], list[tuple[str, StockSlot, Decimal]]]:
    """Allocate an ordered multi-PO plan and optimize physical units globally.

    The ordered FGPN rows are the only planning mode. Each row already contains
    the engineer's editable quantity. Finished-good coverage is lexicographic:
    priority 1 receives the largest whole-piece quantity it can launch, then
    priority 2 uses the remaining material, and so on.

    Physical units are selected once per material for the combined covered
    demand. This prevents one FGPN from consuming whole rolls that could cover
    several selected POs together. ``allocate_material`` preserves the source
    order and performs exact minimum-over-issue subset selection for bounded
    whole-roll sets.
    """
    fgpn_demands.sort(key=lambda f: (f.priority, f.request_sequence, f.fgpn_id))
    logical_remaining = {
        mpn: pool.total_available() for mpn, pool in material_pools.items()
    }

    for fgpn in fgpn_demands:
        per_piece: dict[str, Decimal] = {}
        launch_limits: list[Decimal] = []
        for mpn, demand in fgpn.material_demands.items():
            if demand <= 0:
                continue
            usage = demand / fgpn.requested_quantity
            per_piece[mpn] = usage
            available = logical_remaining.get(mpn, Decimal("0"))
            launch_limits.append((available / usage).to_integral_value(rounding=ROUND_FLOOR))

        launchable = min([fgpn.requested_quantity, *launch_limits]) if launch_limits else Decimal("0")
        launchable = max(Decimal("0"), launchable)
        coverage_percents: list[Decimal] = []

        for mpn, demand in fgpn.material_demands.items():
            covered = per_piece.get(mpn, Decimal("0")) * launchable
            fgpn.material_allocations[mpn] = covered
            logical_remaining[mpn] = max(
                Decimal("0"), logical_remaining.get(mpn, Decimal("0")) - covered
            )
            shortfall = demand - covered
            if shortfall > 0:
                fgpn.is_fully_covered = False
                fgpn.material_shortages[mpn] = shortfall
            coverage_percents.append((covered / demand) * 100 if demand > 0 else Decimal("100"))

        fgpn.percent_covered = min(coverage_percents) if coverage_percents else Decimal("0")

    covered_by_material: dict[str, Decimal] = {}
    for fgpn in fgpn_demands:
        for mpn, quantity in fgpn.material_allocations.items():
            covered_by_material[mpn] = covered_by_material.get(mpn, Decimal("0")) + quantity

    all_allocations: list[tuple[str, StockSlot, Decimal]] = []
    for mpn in sorted(covered_by_material):
        covered_demand = covered_by_material[mpn]
        if covered_demand <= 0:
            continue
        pool = material_pools.get(mpn)
        if pool is None:
            continue
        allocated, slot_allocations = allocate_material(pool, covered_demand)
        if allocated != covered_demand:
            raise RuntimeError(
                f"Global stock-unit selection covered {allocated} of {covered_demand} for {mpn}."
            )
        all_allocations.extend(("GLOBAL", slot, quantity) for slot, quantity in slot_allocations)

    return fgpn_demands, all_allocations
