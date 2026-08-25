"""Pydantic schemas for Simulation workflows."""
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FgpnSimulationRequest(BaseModel):
    po_id: int
    fgpn_id: int
    po_line_id: Optional[int] = None
    priority: Optional[int] = None
    requested_quantity: Decimal = Field(gt=0)
    manual_quantity: Optional[Decimal] = Field(default=None, gt=0)


class SimulationPreviewRequest(BaseModel):
    launch_id: Optional[int] = None
    project_id: Optional[int] = None
    fgpns: list[FgpnSimulationRequest] = Field(min_length=1)
    
    allocation_strategy: str = Field(
        ..., 
        description="PRIORITY, MANUAL, or PRIORITY_PLUS_MANUAL"
    )
    include_in_transit: bool = False
    safety_coefficient: Decimal = Field(default=Decimal('2.0'), gt=0)


class AllocationDetail(BaseModel):
    stock_unit_id: Optional[int]  # None for virtual remaining production pool
    material_part_number: str
    source: str  # WAREHOUSE, PRODUCTION, IN_TRANSIT
    is_whole_issue: bool = False
    available_quantity: Decimal
    allocated_quantity: Decimal
    remaining_quantity: Decimal
    expected_arrival_date: Optional[date] = None
    
    model_config = ConfigDict(from_attributes=True)


class MaterialSimulationSummary(BaseModel):
    material_part_number: str
    description: str
    unit: str
    total_demand: Decimal
    warehouse_stock: Decimal
    in_transit: Decimal
    cutman_wip: Decimal
    available_stock: Decimal
    allocated_quantity: Decimal
    shortfall: Decimal
    status: str  # COVERED, PARTIALLY_COVERED, NOT_COVERED
    suggestion: Optional[str] = None


class FgpnSimulationSummary(BaseModel):
    po_id: int
    fgpn_id: int
    fgpn_code: str
    po_line_id: Optional[int] = None
    po_number: Optional[str] = None
    po_quantity: Decimal
    simulation_quantity: Decimal
    launchable_quantity: Decimal
    priority: int
    coverage_percent: Decimal
    status: str
    material_requirements: dict[str, Decimal] = Field(default_factory=dict)
    material_allocations: dict[str, Decimal] = Field(default_factory=dict)
    material_shortages: dict[str, Decimal] = Field(default_factory=dict)  # material_part_number -> shortfall
    suggestion: Optional[str] = None


class SimulationPreviewResult(BaseModel):
    stock_scope: str  # CURRENT_STOCK or INCLUDING_IN_TRANSIT
    allocation_strategy: str
    is_feasible: bool
    total_requested_quantity: Decimal
    total_launchable_quantity: Decimal
    suggestion: Optional[str] = None
    material_summaries: list[MaterialSimulationSummary]
    fgpn_summaries: list[FgpnSimulationSummary]
    allocation_details: list[AllocationDetail]


class SimulationSaveRequest(BaseModel):
    launch_id: int
    preview_request: SimulationPreviewRequest
    target_date: date
    mtg_minutes_document_id: int


class SimulationSaveResponse(BaseModel):
    simulation_id: int
    status: str = "SAVED"


class LaunchAvailabilityIssue(BaseModel):
    stock_unit_id: int
    material_part_number: str
    requested_quantity: Decimal
    available_quantity: Decimal
    current_status: str
    reason: str


class LaunchReviewResult(BaseModel):
    simulation_id: int
    can_launch: bool
    original_allocations_available: bool
    reallocated: bool = False
    message: str
    unavailable_stock_units: list[LaunchAvailabilityIssue] = Field(default_factory=list)
    replacement_preview: Optional[SimulationPreviewResult] = None


class LaunchSimulationResponse(BaseModel):
    simulation_id: int
    status: str
    reallocated: bool = False
    launch_allocation_count: int
