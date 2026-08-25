"""Pydantic schemas for BOM workflows."""
from datetime import date, time
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BomUploadMetadata(BaseModel):
    """Optional metadata the client may include alongside a BOM workbook upload.

    The Finished-Good Part Number and version are **not** accepted from the
    client: the FGPN is extracted automatically from the workbook, and the
    version is auto-incremented by the service after querying the database.
    """

    development_level: Optional[str] = Field(default=None, max_length=50)
    uploaded_by: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None


class BomUploadRequest(BaseModel):
    """Shape of the optional JSON/form metadata sent with the upload.

    Mirrors :class:`BomUploadMetadata` and exists as a separate type so that
    the API layer can document the multipart form fields explicitly.
    """

    development_level: Optional[str] = Field(default=None, max_length=50)
    uploaded_by: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None


class BomMaterialLineResponse(BaseModel):
    """A normalized material row extracted from a BOM workbook."""

    source_row_number: int
    material_part_number: str
    material_description: Optional[str] = None
    cover_revision: Optional[str] = None
    cover_pn: Optional[str] = None
    cover_description: Optional[str] = None
    part_type: Optional[str] = None
    coefficient: Decimal
    quantity_tpdm: Optional[Decimal] = None
    total_quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    total_sqm: Optional[Decimal] = None
    raw_row: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class BomExtractionResponse(BaseModel):
    """Preview of the BOM snapshot produced from one workbook and PN."""

    finished_good_part_number: str
    finished_good_description: Optional[str] = None
    version: str
    development_level: Optional[str] = None
    source_filename: str
    uploaded_by: Optional[str] = None
    source_reported_by: Optional[str] = None
    source_report_date: Optional[date] = None
    source_report_time: Optional[time] = None
    material_row_count: int
    unique_material_count: int
    lines: list[BomMaterialLineResponse]


class BomDocumentResponse(BaseModel):
    """Document metadata exposed by the API, excluding binary content."""

    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str

    model_config = ConfigDict(from_attributes=True)


class BomVersionResponse(BaseModel):
    """Stored BOM version snapshot."""

    id: int
    fgpn_id: int
    finished_good_part_number: str
    version: int
    development_level: Optional[str] = None
    source_filename: str
    uploaded_by: Optional[str] = None
    source_reported_by: Optional[str] = None
    source_report_date: Optional[date] = None
    source_report_time: Optional[time] = None
    material_row_count: int
    is_current: bool
    notes: Optional[str] = None
    document: Optional[BomDocumentResponse] = None
    material_lines: list[BomMaterialLineResponse] = []

    model_config = ConfigDict(from_attributes=True)


class BomResponse(BaseModel):
    """BOM master with its version history."""

    id: UUID
    finished_good_part_number: str
    finished_good_description: Optional[str] = None
    status: str
    versions: list[BomVersionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class BomListResponse(BaseModel):
    """Paginated BOM listing."""

    items: list[BomResponse]
    total: int


class BomUploadResult(BaseModel):
    """Response returned by the BOM upload endpoint.

    Contains a summary count and the full detail of every BOM version that
    was created during the upload request.  One version is created per
    uploaded file.
    """

    uploaded_count: int
    versions: list[BomVersionResponse]


class BomCompareRequest(BaseModel):
    """Request body for comparing two saved BOM versions."""

    base_version_id: UUID
    target_version_id: UUID


class BomMaterialChangeResponse(BaseModel):
    """One field-level material difference between two BOM versions."""

    material_part_number: str
    field_name: str
    base_value: Optional[str] = None
    target_value: Optional[str] = None
    change_type: str


class BomComparisonResponse(BaseModel):
    """BOM comparison result shaped for the frontend comparison page."""

    base_version_id: UUID
    target_version_id: UUID
    added_materials: int
    modified_materials: int
    removed_materials: int
    unchanged_materials: int
    changes: list[BomMaterialChangeResponse]
