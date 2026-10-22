"""Cutting report staging and explicit consumption confirmation."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class CuttingReportLine(BaseModel):
    sheet: str
    row_number: int
    material_part_number: str
    description: str
    started_at: datetime
    spreading_usage: Decimal
    raw_fields: dict[str, str]


class CuttingReportResponse(BaseModel):
    report_id: int
    file_name: str
    imported_at: datetime
    posted_at: datetime | None
    posted_launch_id: int | None
    confirmed_usage_unit: str | None
    already_imported: bool = False
    lines: list[CuttingReportLine]
    warnings: list[str]


class CuttingReportPostRequest(BaseModel):
    launch_id: int = Field(gt=0)
    usage_unit: Literal["m", "sqm", "pcs", "kg"]
    confirm_usage_is_consumption: Literal[True]
