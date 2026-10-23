"""Contracts for supplier material planning and physical-arrival confirmation."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
import uuid

from pydantic import BaseModel, Field, model_validator


class SupplierOrderLineInput(BaseModel):
    supplier_order_line_id: Optional[int] = None
    material_part_number: str = Field(min_length=1, max_length=50)
    stock_unit_kind: Literal["ROLL", "COMPONENT"]
    expected_quantity: Decimal = Field(gt=0)
    expected_arrival_date: date


class SupplierOrderCreateRequest(BaseModel):
    project_id: int
    supplier_id: int
    lines: list[SupplierOrderLineInput] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_existing_line_ids(self) -> "SupplierOrderCreateRequest":
        ids = [line.supplier_order_line_id for line in self.lines if line.supplier_order_line_id]
        if len(ids) != len(set(ids)):
            raise ValueError("Each supplier order line may be included only once.")
        return self


class SupplierOrderUpdateRequest(SupplierOrderCreateRequest):
    pass


class SupplierArrivalLineInput(BaseModel):
    supplier_order_line_id: int
    # Zero is a valid warehouse observation: it records that an expected unit
    # did not arrive and forces a documented discrepancy at confirmation.
    actual_quantity: Decimal = Field(ge=0)


class SupplierArrivalEntryRequest(BaseModel):
    lines: list[SupplierArrivalLineInput] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_line_ids(self) -> "SupplierArrivalEntryRequest":
        ids = [line.supplier_order_line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Each supplier order line may be received only once per entry.")
        return self


class SupplierArrivalConfirmRequest(BaseModel):
    discrepancy_reason: Optional[str] = Field(default=None, max_length=1000)


class SupplierOrderLineResponse(BaseModel):
    supplier_order_line_id: int
    material_part_number: str
    description: str
    unit: str
    stock_unit_kind: str
    stock_unit_reference: str
    expected_quantity: Decimal
    expected_arrival_date: date
    actual_quantity: Optional[Decimal] = None
    stock_unit_id: int
    compatible: Optional[bool] = None
    quantity_difference: Optional[Decimal] = None
    arrival_entered_by_name: Optional[str] = None
    arrival_entered_at: Optional[datetime] = None


class SupplierOrderResponse(BaseModel):
    supplier_order_id: int
    project_id: int
    project_code: str
    project_name: str
    supplier_id: int
    supplier_name: str
    supplier_reference: Optional[str] = None
    ordered_for_user_id: uuid.UUID
    ordered_for_name: str
    ordered_for_role: str
    status: str
    created_at: datetime
    updated_at: datetime
    confirmed_at: Optional[datetime] = None
    discrepancy_reason: Optional[str] = None
    has_discrepancy: bool
    lines: list[SupplierOrderLineResponse]


class SupplierOrderListResponse(BaseModel):
    items: list[SupplierOrderResponse]
    total: int


class NotificationResponse(BaseModel):
    notification_id: int
    notification_type: str
    title: str
    message: str
    entity_type: str
    entity_id: int
    created_at: datetime
    read_at: Optional[datetime] = None
