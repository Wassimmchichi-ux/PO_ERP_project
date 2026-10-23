"""Pydantic schemas for system administrator workflows."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


BackendRole = Literal[
    "ADMIN",
    "PLANT_MANAGER",
    "LAUNCH_ENGINEER",
    "LAUNCH_MANAGER",
    "WAREHOUSE_Personnel",
    "WAREHOUSE_TEAM_LEADER",
    "MANUFACTURING_OPERATOR",
]
RecordStatus = Literal["ACTIVE", "INACTIVE"]
ReferenceListName = Literal[
    "customers",
    "contacts",
    "finished-goods-part-numbers",
    "manufacturing-receivers",
    "delivery-methods",
    "material-types",
    "suppliers",
]


class AdminUserCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    registration_number: str = Field(min_length=1, max_length=80)
    role: BackendRole
    temporary_password: str | None = Field(default=None, max_length=120)
    project_ids: list[int] = Field(default_factory=list)


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    registration_number: str | None = Field(default=None, max_length=80)
    role: BackendRole | None = None
    status: RecordStatus | None = None
    project_ids: list[int] | None = None
    must_change_password: bool | None = None


class AdminUserResponse(BaseModel):
    id: str
    full_name: str
    registration_number: str
    role: str
    status: str
    is_locked: bool
    must_change_password: bool
    failed_login_count: int
    locked_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    project_ids: list[int]


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int


class ReferenceItemCreateRequest(BaseModel):
    value: str = Field(min_length=1, max_length=150)
    detail: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    customer_id: int | None = None
    unit: str | None = Field(default=None, max_length=10)


class ReferenceItemUpdateRequest(BaseModel):
    value: str | None = Field(default=None, max_length=150)
    detail: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    customer_id: int | None = None
    unit: str | None = Field(default=None, max_length=10)
    active: bool | None = None


class ReferenceItemResponse(BaseModel):
    id: str
    list: str
    value: str
    detail: str | None = None
    active: bool
    linked_records: int


class ReferenceListsResponse(BaseModel):
    items: list[ReferenceItemResponse]
    total: int
