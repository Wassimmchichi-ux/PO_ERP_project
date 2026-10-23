"""Pydantic schemas for Simulation workflows."""
from datetime import date, datetime
from decimal import Decimal
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FgpnSimulationRequest(BaseModel):
    po_id: int
    fgpn_id: int
    po_line_id: Optional[int] = None
    priority: int = Field(gt=0)
    requested_quantity: Decimal = Field(gt=0)


class SimulationPreviewRequest(BaseModel):
    project_id: int
    fgpns: list[FgpnSimulationRequest] = Field(min_length=1)
    include_in_transit: bool = False
    target_date: Optional[date] = Field(
        default=None,
        description="Required when including in-transit stock; only arrivals on or before this date qualify.",
    )
    safety_coefficient: Decimal = Field(default=Decimal('2.0'), ge=1)
    stock_scope_mode: Literal["ALL", "OWNED_ONLY"] = Field(
        default="ALL",
        description="ALL or OWNED_ONLY. OWNED_ONLY filters physical stock units by stock_owner_user_id.",
    )
    stock_owner_user_id: Optional[uuid.UUID] = None
    include_global_stock: bool = Field(
        default=False,
        description="When stock_scope_mode is OWNED_ONLY, also include global stock units with no assigned owner.",
    )

    @model_validator(mode="after")
    def validate_ordered_selections(self) -> "SimulationPreviewRequest":
        priorities = [item.priority for item in self.fgpns]
        expected = list(range(1, len(self.fgpns) + 1))
        if sorted(priorities) != expected:
            raise ValueError("FGPN priorities must be unique and contiguous from 1 to the number of selections.")

        selection_keys = [
            (item.po_id, item.po_line_id if item.po_line_id is not None else item.fgpn_id)
            for item in self.fgpns
        ]
        if len(selection_keys) != len(set(selection_keys)):
            raise ValueError("Each PO line/FGPN may be selected only once per simulation.")

        for item in self.fgpns:
            if item.requested_quantity != item.requested_quantity.to_integral_value():
                raise ValueError("Finished-good simulation quantities must be whole pieces.")
        return self


class AllocationDetail(BaseModel):
    stock_unit_id: Optional[int]  # None for virtual remaining production pool
    business_unit_id: Optional[str] = None
    material_part_number: str
    source: str  # WAREHOUSE, PRODUCTION, IN_TRANSIT
    assigned_user_id: Optional[uuid.UUID] = None
    assigned_user_name: Optional[str] = None
    assigned_user_role: Optional[str] = None
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
    target_date: Optional[date] = None
    stock_scope: str  # CURRENT_STOCK or INCLUDING_IN_TRANSIT
    stock_scope_mode: str = "ALL"
    stock_owner_user_id: Optional[uuid.UUID] = None
    include_global_stock: bool = False
    is_feasible: bool
    total_requested_quantity: Decimal
    total_launchable_quantity: Decimal
    suggestion: Optional[str] = None
    material_summaries: list[MaterialSimulationSummary]
    fgpn_summaries: list[FgpnSimulationSummary]
    allocation_details: list[AllocationDetail]


class SimulationOptionLine(BaseModel):
    po_id: int
    po_number: str
    po_line_id: int
    fgpn_id: int
    fgpn_code: str
    description: Optional[str] = None
    ordered_quantity: Decimal
    already_planned_quantity: Decimal
    outstanding_quantity: Decimal


class SimulationOptionsResponse(BaseModel):
    project_id: int
    lines: list[SimulationOptionLine]


class SimulationSaveRequest(BaseModel):
    preview_request: SimulationPreviewRequest
    target_date: date
    mtg_minutes_document_id: Optional[int] = None


class SimulationSaveResponse(BaseModel):
    simulation_id: int
    status: str
    document_due_at: Optional[datetime] = None


class SimulationDocumentRequest(BaseModel):
    mtg_minutes_document_id: int


class SimulationWorkflowResponse(BaseModel):
    simulation_id: int
    status: str
    document_due_at: Optional[datetime] = None


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
    idempotent_replay: bool = False
