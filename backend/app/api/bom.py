"""BOM API router.

This module is responsible for exactly three things:

1. Declaring the HTTP route (method, path, response model, status code).
2. Parsing and validating the incoming multipart/form-data request
   (files + optional form fields).
3. Delegating to the service layer and returning the typed response.

No business logic lives here.  In particular:

* The FGPN is **not** accepted as a request parameter.
* The version is **not** accepted as a request parameter.
* File extension validation is **not** performed here (the service owns that).
* Database access does **not** happen here.
"""
from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.schemas.bom import BomUploadResult
from app.services.bom_extraction_service import upload_bom_files

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/boms", tags=["bom"])


@router.post(
    "/upload",
    response_model=BomUploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one or more BOM Excel workbooks",
    description=(
        "Accepts one or more `.xlsx`/`.xls` BOM workbooks as a multipart upload. "
        "The Finished-Good Part Number is extracted automatically from each workbook. "
        "The version is auto-incremented based on the latest stored version for that "
        "part number (starts at 1 for new BOMs). "
        "Optional metadata fields (`development_level`, `uploaded_by`, `notes`) "
        "are applied uniformly to every BOM version created in this request."
    ),
)
async def upload_bom(
    files: Annotated[
        list[UploadFile],
        File(description="One or more Excel BOM workbooks (.xlsx or .xls)."),
    ],
    db: Annotated[Session, Depends(get_db)],
    development_level: Annotated[
        Optional[str],
        Form(description="Optional development-level tag (e.g. 'proto', 'series')."),
    ] = None,
    uploaded_by: Annotated[
        Optional[str],
        Form(description="Optional identifier of the user performing the upload."),
    ] = None,
    notes: Annotated[
        Optional[str],
        Form(description="Optional free-text notes for the created BOM version(s)."),
    ] = None,
) -> BomUploadResult:
    """Receive uploaded BOM files and delegate to the service layer.

    FastAPI handles multipart parsing, dependency injection of the database
    session, and serialisation of the returned Pydantic model.  All workflow
    logic (parsing, versioning, persistence) is handled by
    :func:`~app.services.bom_extraction_service.upload_bom_files`.
    """
    logger.info(
        "upload_bom: received %d file(s) development_level=%s uploaded_by=%s",
        len(files),
        development_level,
        uploaded_by,
    )

    return await upload_bom_files(
        db,
        files,
        development_level=development_level,
        uploaded_by=uploaded_by,
        notes=notes,
    )