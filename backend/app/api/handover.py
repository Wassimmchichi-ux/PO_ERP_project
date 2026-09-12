"""Warehouse handover API router."""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.schemas.handover import (
    HandoverAccessResponse,
    HandoverCollectionRequest,
    HandoverDocumentUploadResponse,
)
from app.services import handover_service

router = APIRouter(prefix="/handovers", tags=["handover"])


@router.get("/access/{delivery_code}", response_model=HandoverAccessResponse)
def open_handover_by_code(
    delivery_code: str,
    db: Annotated[Session, Depends(get_db)],
) -> HandoverAccessResponse:
    """Open the warehouse terminal view for a valid delivery access code."""
    return handover_service.get_handover_for_code(db, delivery_code)


@router.post("/access/{delivery_code}/confirm", response_model=HandoverAccessResponse)
def confirm_handover_collection(
    delivery_code: str,
    request: HandoverCollectionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> HandoverAccessResponse:
    """Record receiver and warehouse team leader details when material is collected."""
    return handover_service.confirm_collection(db, delivery_code, request)


@router.post(
    "/access/{delivery_code}/signed-document",
    response_model=HandoverDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_signed_handover_document(
    delivery_code: str,
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
    uploaded_by: str | None = Form(None),
) -> HandoverDocumentUploadResponse:
    """Store the signed PDF proving material was handed over to production."""
    return handover_service.upload_signed_document(db, delivery_code, file, uploaded_by)
