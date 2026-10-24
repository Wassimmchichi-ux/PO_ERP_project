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

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_policy_actor
from app.dependencies.db import get_db
from app.policies import PolicyActor
from app.schemas.bom import BomUploadResult, BomVersionResponse
from app.services import bom_extraction_service
from app.services.bom_extraction_service import upload_bom_files

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/boms", tags=["bom"])


@router.post(
    "/upload",
    response_model=BomUploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one or more BOM Excel workbooks",
    description=(
        "Accepts one or more `.xlsx` BOM workbooks as a multipart upload. "
        "The Finished-Good Part Number is extracted automatically from each workbook. "
        "The version is auto-incremented based on the latest stored version for that "
        "part number (starts at 1 for new BOMs). "
        "A single workbook may contain several FGPNs; one BOM version is created "
        "for every discovered FGPN. "
        "Optional metadata fields (`development_level`, `uploaded_by`, `notes`) "
        "are applied uniformly to every BOM version created in this request."
    ),
)
async def upload_bom(
    files: Annotated[
        list[UploadFile],
        File(description="One or more Excel BOM workbooks (.xlsx)."),
    ],
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
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
    project_id: Annotated[
        Optional[int],
        Form(description="Optional project id used when an FGPN code exists in several projects."),
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
        project_id=project_id,
        actor=actor,
    )



@router.get("", response_model=list[BomVersionResponse])
def list_boms(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
    project_id: Annotated[Optional[int], Query(description="Filter BOMs by project ID")] = None,
) -> list[BomVersionResponse]:
    """List all stored BOM versions and their extracted material lines."""
    return bom_extraction_service.list_boms(db, project_id=project_id, actor=actor)


@router.get("/{bom_id}/download")
def download_bom(
    bom_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
):
    """Download the original uploaded Excel workbook for a BOM."""
    filename, content = bom_extraction_service.get_bom_file_content(db, bom_id, actor=actor)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/template/{fgpn}")
def download_fgpn_template(
    fgpn: str,
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
):
    """Download sample / template MBOM Excel workbook for a specific FGPN."""
    from pathlib import Path
    from fastapi import HTTPException
    for base in [Path("/app/uploads/sample_mbom"), Path("backend/uploads/sample_mbom"), Path("ressources/mbom_files/single_fgpn")]:
        file_path = base / f"MBOM_{fgpn}.xlsx"
        if file_path.exists():
            with open(file_path, "rb") as f:
                content = f.read()
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="MBOM_{fgpn}.xlsx"'},
            )
    raise HTTPException(status_code=404, detail=f"No template found for FGPN {fgpn}")
