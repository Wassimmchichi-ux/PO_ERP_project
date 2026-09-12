"""Pydantic schemas for customer delivery from launches."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CustomerDeliveryLineRequest(BaseModel):
    launch_fgpn_id: int
    delivered_quantity: Decimal = Field(gt=0)


class CustomerDeliveryRequest(BaseModel):
    lines: list[CustomerDeliveryLineRequest] = Field(min_length=1)


class LaunchFgpnDeliveryResponse(BaseModel):
    launch_fgpn_id: int
    fgpn_id: int
    fgpn_code: str
    description: str | None = None
    planned_quantity: Decimal
    delivered_quantity: Decimal
    remaining_quantity: Decimal


class LaunchDeliveryResponse(BaseModel):
    launch_id: int
    simulation_id: int
    project_id: int | None = None
    project_code: str | None = None
    project_name: str | None = None
    status: str
    planned_date: str
    cmr_document_id: int | None = None
    cmr_file_name: str | None = None
    customer_delivered_at: datetime | None = None
    lines: list[LaunchFgpnDeliveryResponse]


class CustomerDeliveryConfirmResponse(BaseModel):
    document_id: int
    file_name: str
    uploaded_at: datetime
    launch: LaunchDeliveryResponse


class LaunchDeliveryListResponse(BaseModel):
    items: list[LaunchDeliveryResponse]
    total: int
