"""Tests for Simulation Demand Calculation."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.schemas.simulation import SimulationPreviewRequest, FgpnSimulationRequest
from app.services.material_simulation_service import preview_simulation
from app.models.bom import BOM
from app.models.bom_line import BOMLine
from app.models.fgpn import FGPN
from app.models.material import Material
from app.models.material_type import MaterialType
from app.services.simulation_allocator import MaterialPool, StockSlot


def test_simulation_request_rejects_duplicate_po_line_selection():
    with pytest.raises(ValueError, match="selected only once"):
        SimulationPreviewRequest(
            project_id=1,
            fgpns=[
                FgpnSimulationRequest(
                    po_id=1,
                    po_line_id=10,
                    fgpn_id=1,
                    priority=1,
                    requested_quantity=Decimal("5"),
                ),
                FgpnSimulationRequest(
                    po_id=1,
                    po_line_id=10,
                    fgpn_id=1,
                    priority=2,
                    requested_quantity=Decimal("3"),
                ),
            ],
        )


class MockSession:
    """A minimal mock for SQLAlchemy Session to isolate calculation logic."""
    def __init__(self, fgpn_id, bom):
        self.fgpn_id = fgpn_id
        self.bom = bom
        self.queries = []
        
    def execute(self, stmt):
        self.queries.append(stmt)
        # Mocking the execute response is complex for our build_pools,
        # so we will actually patch the repositories to isolate just the logic.
        pass


def test_simulation_demand_calculation(monkeypatch):
    """Verify that part_type M uses total_sqm and S uses total_quantity."""
    
    # 1. Setup Mock BOM
    fgpn_id = 1
    fgpn = FGPN(fgpn_id=fgpn_id, project_id=1, fgpn_code="6855872-7S08-000")
    
    bom = BOM(bom_id=1, fgpn_id=fgpn_id, is_current=True)
    # M row
    line_m = BOMLine(
        material_part_number="MAT-M",
        part_type="M",
        coefficient=Decimal('10.0'),  # Should be ignored
        total_sqm=Decimal('0.6558'),  # Should be used
        total_quantity=Decimal('5.0') # Should be ignored for M
    )
    # S row
    line_s = BOMLine(
        material_part_number="MAT-S",
        part_type="S",
        coefficient=Decimal('10.0'),  # Should be ignored
        total_sqm=Decimal('0.6558'),  # Should be ignored for S
        total_quantity=Decimal('2.0') # Should be used
    )
    bom.lines = [line_m, line_s]
    
    # 2. Mock Repositories
    import app.repositories.simulation_repository as sim_repo
    import app.services.material_simulation_service as sim_svc
    
    monkeypatch.setattr(sim_repo, 'get_current_boms_for_fgpns', lambda db, ids: {fgpn_id: bom})
    monkeypatch.setattr(sim_repo, 'get_project', lambda db, project_id: SimpleNamespace(project_id=1, status="Active", launch_engineer_user_id=None))
    monkeypatch.setattr(sim_repo, 'get_planned_launch_quantities_by_po_line', lambda *args: {})
    monkeypatch.setattr(sim_repo, 'get_fgpns', lambda db, ids: {fgpn_id: fgpn})
    monkeypatch.setattr(sim_repo, 'get_po_lines', lambda db, ids: {})
    monkeypatch.setattr(
        sim_repo,
        'get_current_po_lines_for_po_fgpns',
        lambda db, pairs: {
            (1, fgpn_id): SimpleNamespace(
                po_line_id=10,
                po_version_id=1,
                fgpn_id=fgpn_id,
                ordered_quantity=Decimal('300'),
                po_version=SimpleNamespace(
                    purchase_order=SimpleNamespace(po_id=1, po_number="PO-001", current_version_id=1)
                ),
            )
        },
    )
    
    # Mock build_pools to return empty pools
    monkeypatch.setattr(sim_svc, '_build_pools', lambda db, inc, **kwargs: {})
    # Mock stock repository to avoid DB calls
    import app.repositories.stock_repository as stock_repo
    monkeypatch.setattr(stock_repo, 'get_all_materials', lambda db: [])
    monkeypatch.setattr(stock_repo, 'get_in_transit_stock_by_material', lambda db, **kwargs: {})
    
    # 3. Create Request
    req = SimulationPreviewRequest(
        project_id=1,
        fgpns=[
            FgpnSimulationRequest(
                po_id=1,
                fgpn_id=fgpn_id,
                requested_quantity=Decimal('300'),
                priority=1
            )
        ],
        safety_coefficient=Decimal('1.0')
    )
    
    # 4. Execute
    # We pass None for db since all DB calls are mocked
    result = preview_simulation(None, req)
    
    # 5. Verify
    # We want to check the demand computed before allocation, 
    # but preview_simulation returns material_summaries containing total_demand.
    
    summaries = {s.material_part_number: s for s in result.material_summaries}
    
    # Demand for M: 0.6558 * 300 = 196.74
    assert summaries["MAT-M"].total_demand == Decimal('196.74')
    
    # Demand for S: 2 * 300 = 600
    assert summaries["MAT-S"].total_demand == Decimal('600.0')


def test_selected_fgpn_priority_reports_launchable_quantities(monkeypatch):
    """Selected FGPN rows should be simulated by priority, not by all PO FGPNs."""
    fgpn_1 = FGPN(fgpn_id=1, project_id=1, fgpn_code="FGPN-001")
    fgpn_2 = FGPN(fgpn_id=2, project_id=1, fgpn_code="FGPN-002")

    bom_1 = BOM(bom_id=1, fgpn_id=1, is_current=True)
    bom_1.lines = [
        BOMLine(
            material_part_number="MAT-1",
            part_type="S",
            coefficient=Decimal('0'),
            total_quantity=Decimal('1'),
        )
    ]

    bom_2 = BOM(bom_id=2, fgpn_id=2, is_current=True)
    bom_2.lines = [
        BOMLine(
            material_part_number="MAT-1",
            part_type="S",
            coefficient=Decimal('0'),
            total_quantity=Decimal('1'),
        )
    ]

    import app.repositories.simulation_repository as sim_repo
    import app.repositories.stock_repository as stock_repo
    import app.services.material_simulation_service as sim_svc

    monkeypatch.setattr(sim_repo, 'get_current_boms_for_fgpns', lambda db, ids: {1: bom_1, 2: bom_2})
    monkeypatch.setattr(sim_repo, 'get_project', lambda db, project_id: SimpleNamespace(project_id=1, status="Active", launch_engineer_user_id=None))
    monkeypatch.setattr(sim_repo, 'get_planned_launch_quantities_by_po_line', lambda *args: {})
    monkeypatch.setattr(sim_repo, 'get_fgpns', lambda db, ids: {1: fgpn_1, 2: fgpn_2})
    monkeypatch.setattr(sim_repo, 'get_po_lines', lambda db, ids: {})
    monkeypatch.setattr(
        sim_repo,
        'get_current_po_lines_for_po_fgpns',
        lambda db, pairs: {
            (101, 1): SimpleNamespace(
                po_line_id=11,
                po_version_id=11,
                fgpn_id=1,
                ordered_quantity=Decimal('100'),
                po_version=SimpleNamespace(
                    purchase_order=SimpleNamespace(po_id=101, po_number="PO-101", current_version_id=11)
                ),
            ),
            (202, 2): SimpleNamespace(
                po_line_id=22,
                po_version_id=22,
                fgpn_id=2,
                ordered_quantity=Decimal('200'),
                po_version=SimpleNamespace(
                    purchase_order=SimpleNamespace(po_id=202, po_number="PO-202", current_version_id=22)
                ),
            ),
        },
    )
    monkeypatch.setattr(
        sim_svc,
        '_build_pools',
        lambda db, inc, **kwargs: {
            "MAT-1": MaterialPool(
                material_part_number="MAT-1",
                warehouse_slots=[StockSlot(1, 'WAREHOUSE', Decimal('150'))],
            )
        },
    )
    monkeypatch.setattr(
        stock_repo,
        'get_all_materials',
        lambda db: [
            (
                Material(
                    material_part_number="MAT-1",
                    description="Material 1",
                    material_type_id=1,
                    unit_price=Decimal('0'),
                    status="Active",
                ),
                MaterialType(material_type_id=1, name="Default", unit="pcs", status="Active"),
            )
        ],
    )
    monkeypatch.setattr(stock_repo, 'get_in_transit_stock_by_material', lambda db, **kwargs: {})

    req = SimulationPreviewRequest(
        project_id=1,
        fgpns=[
            FgpnSimulationRequest(po_id=101, fgpn_id=1, requested_quantity=Decimal('100'), priority=1),
            FgpnSimulationRequest(po_id=202, fgpn_id=2, requested_quantity=Decimal('200'), priority=2),
        ],
        safety_coefficient=Decimal('1.0'),
    )

    result = preview_simulation(None, req)

    summaries = {s.fgpn_code: s for s in result.fgpn_summaries}
    assert summaries["FGPN-001"].po_id == 101
    assert summaries["FGPN-002"].po_id == 202
    assert summaries["FGPN-001"].launchable_quantity == Decimal('100')
    assert summaries["FGPN-001"].status == "FULLY_COVERED"
    assert summaries["FGPN-002"].launchable_quantity == Decimal('50')
    assert summaries["FGPN-002"].status == "PARTIALLY_COVERED"
    assert result.total_requested_quantity == Decimal('300')
    assert result.total_launchable_quantity == Decimal('150')

    material_summary = result.material_summaries[0]
    assert material_summary.total_demand == Decimal('300.0')
    assert material_summary.allocated_quantity == Decimal('150.0')
    assert material_summary.shortfall == Decimal('150.0')


def test_build_pools_marks_roll_slots_as_whole_issue(monkeypatch):
    """Warehouse and in-transit rolls are not splittable; component packages are splittable."""
    import app.repositories.stock_repository as stock_repo
    import app.services.material_simulation_service as sim_svc

    roll = Material(
        material_part_number="ROLL-MAT",
        description="Roll material",
        material_type_id=1,
        unit_price=Decimal('0'),
        status="Active",
    )
    component = Material(
        material_part_number="COMP-MAT",
        description="Component material",
        material_type_id=2,
        unit_price=Decimal('0'),
        status="Active",
    )
    roll_type = MaterialType(material_type_id=1, name="M", unit="m", status="Active")
    component_type = MaterialType(material_type_id=2, name="S", unit="pcs", status="Active")

    warehouse_units = [
        SimpleNamespace(
            stock_unit_id=1,
            business_unit_id="ROLL-1",
            user=None,
            user_id=None,
            material_part_number="ROLL-MAT",
            quantity=Decimal('60'),
            expected_arrival_date=None,
        ),
        SimpleNamespace(
            stock_unit_id=2,
            business_unit_id="COMP-1",
            user=None,
            user_id=None,
            material_part_number="COMP-MAT",
            quantity=Decimal('50'),
            expected_arrival_date=None,
        ),
    ]
    transit_units = [
        SimpleNamespace(
            stock_unit_id=3,
            business_unit_id="ROLL-2",
            user=None,
            user_id=None,
            material_part_number="ROLL-MAT",
            quantity=Decimal('40'),
            expected_arrival_date=None,
        )
    ]

    monkeypatch.setattr(stock_repo, 'get_all_materials', lambda db: [(roll, roll_type), (component, component_type)])
    monkeypatch.setattr(
        stock_repo,
        'get_positive_stock_units_by_status',
        lambda db, status, **kwargs: (
            warehouse_units if status == 'WAREHOUSE' else transit_units if status == 'IN_TRANSIT' else []
        ),
    )
    monkeypatch.setattr(stock_repo, 'get_cutting_consumption_by_stock_unit', lambda db: {})
    monkeypatch.setattr(stock_repo, 'get_unassigned_cutting_consumption_by_material', lambda db: {})
    monkeypatch.setattr(stock_repo, 'get_reserved_quantities_by_stock_unit', lambda db: {})

    pools = sim_svc._build_pools(None, include_in_transit=True)

    assert pools["ROLL-MAT"].warehouse_slots[0].can_split is False
    assert pools["ROLL-MAT"].in_transit_slots[0].can_split is False
    assert pools["COMP-MAT"].warehouse_slots[0].can_split is True
