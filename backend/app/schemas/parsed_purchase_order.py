"""Schemas for parsed purchase order review and correction."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ParsedPurchaseOrderCreateRequest(BaseModel):
    document_id: Optional[int] = None
    source_file_name: Optional[str] = None
    parser_name: Optional[str] = None
    parser_version: Optional[str] = None
    parsed_payload: dict[str, Any]


class ParsedPurchaseOrderCorrectionInput(BaseModel):
    field_path: str = Field(min_length=1, max_length=255)
    corrected_value: Any
    original_value: Any = None
    confirmed: bool = True


class ParsedPurchaseOrderCorrectionsRequest(BaseModel):
    corrections: list[ParsedPurchaseOrderCorrectionInput] = Field(default_factory=list)


class ParsedPurchaseOrderCorrectionResponse(BaseModel):
    correction_id: int
    parsed_po_id: int
    field_path: str
    original_value: Any = None
    corrected_value: Any = None
    confirmed: bool
    corrected_by: uuid.UUID
    corrected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParsedPurchaseOrderResponse(BaseModel):
    parsed_po_id: int
    document_id: Optional[int] = None
    source_file_name: Optional[str] = None
    has_source_file: bool = False
    parser_name: Optional[str] = None
    parser_version: Optional[str] = None
    status: str
    parsed_payload: dict[str, Any]
    effective_payload: dict[str, Any]
    validated_po_id: Optional[int] = None
    created_at: datetime
    created_by: uuid.UUID
    updated_at: datetime
    corrections: list[ParsedPurchaseOrderCorrectionResponse] = Field(default_factory=list)


class ParsedPurchaseOrderValidationResult(BaseModel):
    parsed_po_id: int
    status: str
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    effective_payload: dict[str, Any]


class ParsedPurchaseOrderImportRequest(BaseModel):
    project_id: int
    customer_id: int
    contact_id: int
    delivery_method_id: int
    document_id: Optional[int] = None
    change_reason: Optional[str] = None


class ParsedPurchaseOrderImportResult(BaseModel):
    parsed_po_id: int
    po_id: int
    po_version_id: int
    status: str
    created_po: bool
    line_count: int
    created_fgpn_ids: list[int] = Field(default_factory=list)
    updated_fgpn_price_history_ids: list[int] = Field(default_factory=list)
