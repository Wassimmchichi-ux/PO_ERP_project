"""Unit tests for the Simulation Allocator."""
from decimal import Decimal
from types import SimpleNamespace

from app.services.simulation_allocator import (
    StockSlot,
    MaterialPool,
    FgpnDemand,
    allocate_material,
    run_allocation_engine
)
from app.models.stock_unit import StockUnit
from app.repositories.stock_repository import issue_stock_unit_to_production


def test_allocate_exact_match():
    """Local refinement should pick the exact matching slot."""
    pool = MaterialPool(
        material_part_number='MAT1',
        warehouse_slots=[
            StockSlot(1, 'WAREHOUSE', Decimal('100.0')),
            StockSlot(2, 'WAREHOUSE', Decimal('50.0')),
            StockSlot(3, 'WAREHOUSE', Decimal('200.0'))
        ]
    )
    allocated, allocs = allocate_material(pool, Decimal('50.0'))
    
    assert allocated == Decimal('50.0')
    assert len(allocs) == 1
    assert allocs[0][0].stock_unit_id == 2
    assert allocs[0][1] == Decimal('50.0')


def test_greedy_allocation_fragments():
    """Should consume smallest fragments first if no single slot matches."""
    pool = MaterialPool(
        material_part_number='MAT1',
        warehouse_slots=[
            StockSlot(1, 'WAREHOUSE', Decimal('100.0')),
            StockSlot(2, 'WAREHOUSE', Decimal('10.0')),
            StockSlot(3, 'WAREHOUSE', Decimal('20.0'))
        ]
    )
    allocated, allocs = allocate_material(pool, Decimal('25.0'))
    
    assert allocated == Decimal('25.0')
    assert len(allocs) == 2
    # Should pick 10.0 and 20.0 (consuming 15.0 of it)
    ids = [a[0].stock_unit_id for a in allocs]
    assert 2 in ids
    assert 3 in ids


def test_whole_slot_roll_is_not_split():
    """A warehouse/in-transit roll slot should be issued whole even for partial demand."""
    pool = MaterialPool(
        material_part_number='ROLL1',
        warehouse_slots=[StockSlot(1, 'WAREHOUSE', Decimal('60.0'), can_split=False)]
    )

    allocated, allocs = allocate_material(pool, Decimal('50.0'))

    assert allocated == Decimal('50.0')
    assert len(allocs) == 1
    assert allocs[0][0].stock_unit_id == 1
    assert allocs[0][1] == Decimal('60.0')
    assert pool.warehouse_slots[0].remaining == Decimal('0.0')


def test_whole_slot_roll_chooses_smallest_sufficient_combination():
    """Whole-roll allocation should avoid sending extra rolls when one roll can cover demand."""
    pool = MaterialPool(
        material_part_number='ROLL1',
        warehouse_slots=[
            StockSlot(1, 'WAREHOUSE', Decimal('30.0'), can_split=False),
            StockSlot(2, 'WAREHOUSE', Decimal('40.0'), can_split=False),
            StockSlot(3, 'WAREHOUSE', Decimal('100.0'), can_split=False),
        ]
    )

    allocated, allocs = allocate_material(pool, Decimal('80.0'))

    assert allocated == Decimal('80.0')
    assert len(allocs) == 1
    assert allocs[0][0].stock_unit_id == 3
    assert allocs[0][1] == Decimal('100.0')
    assert pool.warehouse_slots[0].remaining == Decimal('30.0')
    assert pool.warehouse_slots[1].remaining == Decimal('40.0')
    assert pool.warehouse_slots[2].remaining == Decimal('0.0')


def test_insufficient_stock():
    """Should allocate maximum possible and report shortfall."""
    pool = MaterialPool(
        material_part_number='MAT1',
        warehouse_slots=[StockSlot(1, 'WAREHOUSE', Decimal('50.0'))],
        production_slots=[StockSlot(2, 'PRODUCTION', Decimal('30.0'))]
    )
    allocated, allocs = allocate_material(pool, Decimal('100.0'))
    
    assert allocated == Decimal('80.0')
    assert len(allocs) == 2


def test_priority_mode_allocation():
    """Priority mode should fully satisfy high priority before low."""
    pool = MaterialPool(
        material_part_number='MAT1',
        warehouse_slots=[StockSlot(1, 'WAREHOUSE', Decimal('100.0'))]
    )
    
    fgpn1 = FgpnDemand(1, 'FG1', priority=1, po_quantity=Decimal('10'), requested_quantity=Decimal('10'))
    fgpn1.material_demands['MAT1'] = Decimal('60.0')
    
    fgpn2 = FgpnDemand(2, 'FG2', priority=2, po_quantity=Decimal('10'), requested_quantity=Decimal('10'))
    fgpn2.material_demands['MAT1'] = Decimal('60.0')
    
    demands, allocs = run_allocation_engine(
        [fgpn2, fgpn1], # out of order
        {'MAT1': pool},
        'PRIORITY'
    )
    
    assert fgpn1.is_fully_covered is True
    assert fgpn1.percent_covered == Decimal('100.0')
    
    assert fgpn2.is_fully_covered is False
    assert fgpn2.material_shortages['MAT1'] == Decimal('20.0')


def test_priority_mode_does_not_overallocate_non_limiting_material():
    """Partial FGPN coverage should allocate only materials needed for launchable items."""
    mat1 = MaterialPool(
        material_part_number='MAT1',
        warehouse_slots=[StockSlot(1, 'WAREHOUSE', Decimal('100.0'))]
    )
    mat2 = MaterialPool(
        material_part_number='MAT2',
        warehouse_slots=[StockSlot(2, 'WAREHOUSE', Decimal('50.0'))]
    )

    fgpn = FgpnDemand(1, 'FG1', priority=1, po_quantity=Decimal('100'), requested_quantity=Decimal('100'))
    fgpn.material_demands['MAT1'] = Decimal('100.0')
    fgpn.material_demands['MAT2'] = Decimal('100.0')

    demands, allocs = run_allocation_engine(
        [fgpn],
        {'MAT1': mat1, 'MAT2': mat2},
        'PRIORITY'
    )

    assert fgpn.launchable_quantity == Decimal('50.0')
    assert fgpn.material_allocations['MAT1'] == Decimal('50.0')
    assert fgpn.material_allocations['MAT2'] == Decimal('50.0')
    assert fgpn.material_shortages['MAT1'] == Decimal('50.0')
    assert fgpn.material_shortages['MAT2'] == Decimal('50.0')


def test_manual_mode_allocation():
    """Manual mode should distribute proportionally if insufficient."""
    pool = MaterialPool(
        material_part_number='MAT1',
        warehouse_slots=[StockSlot(1, 'WAREHOUSE', Decimal('100.0'))]
    )
    
    fgpn1 = FgpnDemand(1, 'FG1', priority=1, po_quantity=Decimal('10'), requested_quantity=Decimal('10'))
    fgpn1.material_demands['MAT1'] = Decimal('75.0')
    
    fgpn2 = FgpnDemand(2, 'FG2', priority=1, po_quantity=Decimal('10'), requested_quantity=Decimal('10'))
    fgpn2.material_demands['MAT1'] = Decimal('75.0')
    
    demands, allocs = run_allocation_engine(
        [fgpn1, fgpn2],
        {'MAT1': pool},
        'MANUAL'
    )
    
    # Each wants 75 (total 150), available 100. So each gets (75/150)*100 = 50.
    assert fgpn1.material_shortages['MAT1'] == Decimal('25.0')
    assert fgpn2.material_shortages['MAT1'] == Decimal('25.0')


def test_priority_plus_manual_mode():
    """Priority + Manual mode respects priority order but uses manual quantities."""
    pool = MaterialPool(
        material_part_number='MAT1',
        warehouse_slots=[StockSlot(1, 'WAREHOUSE', Decimal('100.0'))]
    )
    
    fgpn1 = FgpnDemand(1, 'FG1', priority=2, po_quantity=Decimal('10'), requested_quantity=Decimal('0'))
    fgpn1.material_demands['MAT1'] = Decimal('0.0')
    
    fgpn2 = FgpnDemand(2, 'FG2', priority=1, po_quantity=Decimal('10'), requested_quantity=Decimal('10'))
    fgpn2.material_demands['MAT1'] = Decimal('100.0')
    
    demands, allocs = run_allocation_engine(
        [fgpn1, fgpn2],
        {'MAT1': pool},
        'PRIORITY_PLUS_MANUAL'
    )
    
    assert fgpn2.is_fully_covered is True
    assert fgpn1.is_fully_covered is True # 0 demand is fully covered


def test_launch_issue_reduces_component_package_quantity():
    """A launch allocation for a component package should only subtract issued quantity."""
    class FakeSession:
        def __init__(self):
            self.created = []

        def add(self, stock_unit):
            stock_unit.stock_unit_id = 2
            self.created.append(stock_unit)

        def flush(self):
            pass

    db = FakeSession()
    stock_unit = StockUnit(
        stock_unit_id=1,
        material_part_number='COMP1',
        quantity=Decimal('50.0'),
        status='WAREHOUSE',
    )

    issued = issue_stock_unit_to_production(db, stock_unit, Decimal('7.0'), is_whole_issue=False)

    assert stock_unit.quantity == Decimal('43.0')
    assert stock_unit.status == 'WAREHOUSE'
    assert issued.stock_unit_id == 2
    assert issued.parent_stock_unit_id == 1
    assert issued.quantity == Decimal('7.0')
    assert issued.status == 'ISSUED_TO_PRODUCTION'


def test_launch_issue_consumes_whole_roll_stock_unit():
    """A launch allocation for a roll should consume the whole stock unit."""
    stock_unit = StockUnit(
        stock_unit_id=1,
        material_part_number='ROLL1',
        quantity=Decimal('60.0'),
        status='WAREHOUSE',
    )

    issued = issue_stock_unit_to_production(SimpleNamespace(), stock_unit, Decimal('50.0'), is_whole_issue=True)

    assert issued is stock_unit
    assert stock_unit.quantity == Decimal('60.0')
    assert stock_unit.status == 'ISSUED_TO_PRODUCTION'
