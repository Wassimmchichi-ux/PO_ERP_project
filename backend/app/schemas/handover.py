"""Pydantic schemas for warehouse handover workflows."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HandoverItemResponse(BaseModel):
    material_part_number: str
    description: str
    roll_size: Decimal | None = None
    quantity: Decimal
    unit: str


class HandoverAccessResponse(BaseModel):
    delivery_inst_id: int
    ref: str
    simulation_id: int
    project_id: int | None = None
    project_code: str | None = None
    project_name: str | None = None
    created_at: datetime
    created_by: str | None = None
    required_at: datetime
    delivery_code: str
    code_expires_at: datetime
    code_used: bool
    code_used_at: datetime | None = None
    status: str
    receiver_name: str | None = None
    warehouse_team_leader_name: str | None = None
    signed_document_id: int | None = None
    signed_file_name: str | None = None
    uploaded_at: datetime | None = None
    items: list[HandoverItemResponse]

    model_config = ConfigDict(from_attributes=True)


class HandoverCollectionRequest(BaseModel):
    receiver_name: str = Field(min_length=1, max_length=100)
    warehouse_team_leader_name: str = Field(min_length=1, max_length=100)


class HandoverDocumentUploadResponse(BaseModel):
    document_id: int
    file_name: str
    file_path: str
    uploaded_at: datetime
    handover: HandoverAccessResponse
