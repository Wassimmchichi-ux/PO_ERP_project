"""Read schemas for the imported purchase-order register."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class PurchaseOrderListItem(BaseModel):
    """Current-version summary rendered by the Purchase Orders register."""

    po_id: int
    po_number: str
    project_id: int | None = None
    project_code: str | None = None
    project_name: str | None = None
    jit_customer: str
    oem_customer: str | None = None
    contact_name: str
    current_version: int | None = None
    status: str
    fgpn_codes: list[str]
    ordered_quantity: Decimal
    delivered_quantity: Decimal
    remaining_quantity: Decimal
    open_amount: Decimal
    delivery_date: date | None = None
    delivery_week: str | None = None
    updated_at: datetime


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderListItem]
    total: int


class PurchaseOrderLineDetail(BaseModel):
    po_line_id: int
    item_number: str | None = None
    fgpn_code: str
    description: str | None = None
    ordered_quantity: Decimal
    delivered_quantity: Decimal
    remaining_quantity: Decimal
    unit_price: Decimal
    open_amount: Decimal
    delivery_date: date | None = None


class PurchaseOrderVersionDetail(BaseModel):
    po_version_id: int
    version_number: int
    document_date: date | None = None
    source_file_name: str
    created_at: datetime
    created_by_name: str
    change_reason: str | None = None
    is_current: bool


class PurchaseOrderDeleteRequest(BaseModel):
    """Body accepted by DELETE /purchase-orders/{po_id}."""

    deletion_reason: str


class PurchaseOrderDetailResponse(PurchaseOrderListItem):
    contact_email: str | None = None
    contact_phone: str | None = None
    document_date: date | None = None
    car_model: str | None = None
    engineering_phase_level: str | None = None
    purchase_order_level: str | None = None
    reason: str | None = None
    source_file_name: str | None = None
    lines: list[PurchaseOrderLineDetail]
    versions: list[PurchaseOrderVersionDetail]


class VersionComparisonRow(BaseModel):
    field: str
    a: str | None = None
    b: str | None = None
    status: str  # "Unchanged" | "Changed" | "Added" | "Removed"


class VersionComparisonResponse(BaseModel):
    po_id: int
    po_number: str
    version_a: int
    version_b: int
    rows: list[VersionComparisonRow]
