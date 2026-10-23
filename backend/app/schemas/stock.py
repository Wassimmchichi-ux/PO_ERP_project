"""Pydantic schemas for Stock Management workflows."""
from datetime import date, datetime
from decimal import Decimal
import uuid
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ExpectedArrivalUpdateRequest(BaseModel):
    expected_arrival_date: date
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class StockSummaryItem(BaseModel):
    material_part_number: str
    description: str
    material_type: str
    unit: str
    critical_threshold: Decimal
    unit_price: Decimal
    warehouse_quantity: Decimal
    production_quantity: Decimal
    in_transit_quantity: Decimal
    total_available_quantity: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)


class StockSummaryListResponse(BaseModel):
    items: list[StockSummaryItem]
    total: int


class ProductionStockItem(BaseModel):
    material_part_number: str
    description: str
    unit: str
    total_sent_to_production: Decimal
    total_cutting_consumption: Decimal
    remaining_production_quantity: Decimal

    model_config = ConfigDict(from_attributes=True)


class ProductionStockListResponse(BaseModel):
    items: list[ProductionStockItem]
    total: int


class InTransitItem(BaseModel):
    stock_unit_id: int
    stock_unit_reference: Optional[str] = None
    material_part_number: str
    description: str
    unit: str
    quantity: Decimal
    expected_quantity: Decimal
    actual_quantity: Optional[Decimal] = None
    quantity_difference: Optional[Decimal] = None
    compatible: Optional[bool] = None
    expected_arrival_date: Optional[date]
    days_until_arrival: Optional[int]
    status: str
    workflow_status: str
    assigned_user_id: Optional[uuid.UUID] = None
    assigned_user_name: Optional[str] = None
    assigned_user_role: Optional[str] = None
    supplier_order_id: Optional[int] = None
    supplier_order_line_id: Optional[int] = None
    stock_unit_kind: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_reference: Optional[str] = None
    supplier_order_status: Optional[str] = None
    project_id: Optional[int] = None
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    arrival_entered_by_name: Optional[str] = None
    arrival_entered_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InTransitListResponse(BaseModel):
    items: list[InTransitItem]
    total: int


class MaterialStockDetailResponse(BaseModel):
    material_part_number: str
    description: str
    unit: str
    warehouse: Decimal
    production: Decimal
    in_transit: Decimal
    total_available: Decimal
    total_consumed: Decimal
    
    model_config = ConfigDict(from_attributes=True)


class StockDashboardStats(BaseModel):
    total_materials_in_warehouse: int
    total_materials_in_production: int
    total_in_transit_entries: int
    todays_expected_arrivals_count: int
    upcoming_arrivals_count: int


class ProductionHandoverRequest(BaseModel):
    handover_document_id: int


class ProductionHandoverResponse(BaseModel):
    stock_unit_id: int
    status: str = "PRODUCTION"
    material_detail: MaterialStockDetailResponse


class StockUnitReceptionRequest(BaseModel):
    business_unit_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    material_part_number: str
    quantity: Decimal = Field(gt=0)
    status: str = Field(default="WAREHOUSE", description="WAREHOUSE or IN_TRANSIT")
    expected_arrival_date: Optional[datetime] = None
    assigned_user_id: Optional[uuid.UUID] = None
    source_reference: Optional[str] = Field(default=None, max_length=100)


class StockUnitReceptionResponse(BaseModel):
    stock_unit_id: int
    business_unit_id: Optional[str] = None
    material_part_number: str
    quantity: Decimal
    status: str
    expected_arrival_date: Optional[datetime] = None
    assigned_user_id: Optional[uuid.UUID] = None
    assigned_user_name: Optional[str] = None
    assigned_user_role: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockUnitReceptionBatchRequest(BaseModel):
    material_part_number: str
    quantities: list[Annotated[Decimal, Field(gt=0)]] = Field(min_length=1, max_length=500)
    assigned_user_id: Optional[uuid.UUID] = None
    source_reference: Optional[str] = Field(default=None, max_length=100)


class StockUnitReceptionBatchResponse(BaseModel):
    items: list[StockUnitReceptionResponse]
    stock_unit_count: int
    total_quantity: Decimal


class MaterialThresholdUpdateRequest(BaseModel):
    critical_threshold: Decimal = Field(ge=0)


class StockReceptionCorrectionRequest(BaseModel):
    quantity: Decimal = Field(gt=0)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]


class StockMovementItem(BaseModel):
    movement_id: int
    occurred_at: datetime
    actor_user_id: uuid.UUID
    actor_name: str
    material_part_number: str
    material_description: str
    unit: str
    movement_type: str
    quantity_change: Decimal
    warehouse_quantity_after: Optional[Decimal] = None
    stock_unit_id: Optional[int] = None
    stock_unit_reference: Optional[str] = None
    supplier_order_id: Optional[int] = None
    supplier_name: Optional[str] = None
    source_reference: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    reason: Optional[str] = None
    note: Optional[str] = None


class StockMovementListResponse(BaseModel):
    items: list[StockMovementItem]
    total: int
