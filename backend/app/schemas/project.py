"""Pydantic schemas for project CRUD workflows."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreateRequest(BaseModel):
    project_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    launch_engineer_user_id: str | None = None
    jit_customer: Optional[str] = None
    oem_customer: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    car_model: Optional[str] = None


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=150)
    jit_customer: Optional[str] = None
    oem_customer: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    car_model: Optional[str] = None
    status: Optional[str] = None


class ProjectDeactivateRequest(BaseModel):
    meeting_document_id: int
    reason: str = Field(min_length=1, max_length=500)


class ProjectResponse(BaseModel):
    project_id: int
    project_code: str
    name: str
    launch_engineer_user_id: str
    status: str
    jit_customer: Optional[str] = None
    oem_customer: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    car_model: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deactivated_at: Optional[datetime] = None
    deactivation_document_id: Optional[int] = None
    linked_po_count: int = 0
    writable: bool = True

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
