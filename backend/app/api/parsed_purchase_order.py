"""Parsed purchase order review API."""
from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies.auth import actor_user_id_or_system, get_current_policy_actor
from app.dependencies.db import get_db
from app.exceptions.base import ValidationException
from app.policies import PolicyActor
from app.schemas.parsed_purchase_order import (
    ParsedPurchaseOrderCorrectionsRequest,
    ParsedPurchaseOrderCreateRequest,
    ParsedPurchaseOrderImportRequest,
    ParsedPurchaseOrderImportResult,
    ParsedPurchaseOrderResponse,
    ParsedPurchaseOrderValidationResult,
)
from app.services import parsed_purchase_order_service

router = APIRouter(prefix="/purchase-orders/parsed", tags=["purchase-order-parsing"])


@router.post(
    "",
    response_model=ParsedPurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_parsed_purchase_order(
    request: ParsedPurchaseOrderCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> ParsedPurchaseOrderResponse:
    """Store parser output before launch-engineer correction."""
    user_id = actor_user_id_or_system(db, actor)
    return parsed_purchase_order_service.create_parsed_purchase_order(
        db,
        request,
        user_id,
        actor=actor,
    )


@router.post(
    "/upload-json",
    response_model=ParsedPurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_parsed_purchase_order_json(
    file: Annotated[UploadFile, File(description="Corrected or raw parsed PO JSON file.")],
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> ParsedPurchaseOrderResponse:
    """Store a parsed PO JSON file before review/import."""
    try:
        payload = json.loads((await file.read()).decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise ValidationException("Uploaded file must be a valid UTF-8 JSON document.") from exc
    user_id = actor_user_id_or_system(db, actor)
    return parsed_purchase_order_service.create_parsed_purchase_order(
        db,
        ParsedPurchaseOrderCreateRequest(
            source_file_name=file.filename,
            parser_name="external-json",
            parsed_payload=payload,
        ),
        user_id,
        actor=actor,
    )


@router.post(
    "/parse",
    response_model=ParsedPurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def parse_purchase_order_upload(
    file: Annotated[UploadFile, File(description="Text-extractable PO PDF or text export.")],
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> ParsedPurchaseOrderResponse:
    """Run the simple built-in PO parser and store the output for review."""
    user_id = actor_user_id_or_system(db, actor)
    return parsed_purchase_order_service.parse_purchase_order_bytes(
        db,
        source_file_name=file.filename,
        content=await file.read(),
        user_id=user_id,
        actor=actor,
    )


@router.get("/{parsed_po_id}", response_model=ParsedPurchaseOrderResponse)
def get_parsed_purchase_order(
    parsed_po_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> ParsedPurchaseOrderResponse:
    """Return original parser output, correction diffs, and effective values."""
    return parsed_purchase_order_service.get_parsed_purchase_order(db, parsed_po_id)


@router.put("/{parsed_po_id}/corrections", response_model=ParsedPurchaseOrderResponse)
def save_parsed_purchase_order_corrections(
    parsed_po_id: int,
    request: ParsedPurchaseOrderCorrectionsRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> ParsedPurchaseOrderResponse:
    """Store launch-engineer corrections by field path."""
    user_id = actor_user_id_or_system(db, actor)
    return parsed_purchase_order_service.save_parsed_purchase_order_corrections(
        db,
        parsed_po_id,
        request,
        user_id,
        actor=actor,
    )


@router.post("/{parsed_po_id}/validate", response_model=ParsedPurchaseOrderValidationResult)
def validate_parsed_purchase_order(
    parsed_po_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> ParsedPurchaseOrderValidationResult:
    """Validate the effective corrected PO payload before final import."""
    return parsed_purchase_order_service.validate_parsed_purchase_order(
        db,
        parsed_po_id,
        actor=actor,
    )


@router.post("/{parsed_po_id}/import", response_model=ParsedPurchaseOrderImportResult)
def import_parsed_purchase_order(
    parsed_po_id: int,
    request: ParsedPurchaseOrderImportRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> ParsedPurchaseOrderImportResult:
    """Import the effective corrected PO into PurchaseOrder tables."""
    user_id = actor_user_id_or_system(db, actor)
    return parsed_purchase_order_service.import_parsed_purchase_order(
        db,
        parsed_po_id,
        request,
        user_id,
        actor=actor,
    )
