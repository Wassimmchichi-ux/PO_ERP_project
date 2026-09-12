"""Customer delivery API router."""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.schemas.customer_delivery import (
    CustomerDeliveryConfirmResponse,
    CustomerDeliveryRequest,
    LaunchDeliveryListResponse,
)
from app.services import customer_delivery_service

router = APIRouter(prefix="/customer-deliveries", tags=["customer-deliveries"])


@router.get("/launches", response_model=LaunchDeliveryListResponse)
def list_launches_for_delivery(
    db: Annotated[Session, Depends(get_db)],
) -> LaunchDeliveryListResponse:
    return customer_delivery_service.list_launches_for_delivery(db)


@router.post(
    "/launches/{launch_id}/confirm",
    response_model=CustomerDeliveryConfirmResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm_customer_delivery(
    launch_id: int,
    db: Annotated[Session, Depends(get_db)],
    payload: str = Form(...),
    cmr_file: UploadFile = File(...),
    uploaded_by: str | None = Form(None),
) -> CustomerDeliveryConfirmResponse:
    request = CustomerDeliveryRequest.model_validate_json(payload)
    return customer_delivery_service.confirm_customer_delivery(
        db,
        launch_id,
        request,
        cmr_file,
        uploaded_by,
    )
