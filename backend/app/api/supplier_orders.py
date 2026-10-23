"""Supplier material order and arrival protocol endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies.auth import actor_user_id_or_system, get_current_policy_actor
from app.dependencies.db import get_db
from app.policies import PolicyActor
from app.schemas.supplier_order import (
    NotificationResponse,
    SupplierArrivalConfirmRequest,
    SupplierArrivalEntryRequest,
    SupplierOrderCreateRequest,
    SupplierOrderListResponse,
    SupplierOrderResponse,
    SupplierOrderUpdateRequest,
)
from app.services import supplier_order_service


router = APIRouter(tags=["supplier-material-orders"])


@router.get("/supplier-material-orders", response_model=SupplierOrderListResponse)
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SupplierOrderListResponse:
    return supplier_order_service.list_orders(db, actor=actor)


@router.post(
    "/supplier-material-orders",
    response_model=SupplierOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_order(
    request: SupplierOrderCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SupplierOrderResponse:
    return supplier_order_service.create_order(
        db, request, actor_user_id_or_system(db, actor), actor=actor,
    )


@router.put("/supplier-material-orders/{supplier_order_id}", response_model=SupplierOrderResponse)
def update_order(
    supplier_order_id: int,
    request: SupplierOrderUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SupplierOrderResponse:
    return supplier_order_service.update_order(
        db, supplier_order_id, request, actor_user_id_or_system(db, actor), actor=actor,
    )


@router.delete("/supplier-material-orders/{supplier_order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(
    supplier_order_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> Response:
    supplier_order_service.delete_order(
        db, supplier_order_id, actor_user_id_or_system(db, actor), actor=actor,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/supplier-material-orders/{supplier_order_id}/arrival",
    response_model=SupplierOrderResponse,
)
def enter_arrival(
    supplier_order_id: int,
    request: SupplierArrivalEntryRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SupplierOrderResponse:
    return supplier_order_service.enter_arrival(
        db, supplier_order_id, request, actor_user_id_or_system(db, actor), actor=actor,
    )


@router.post(
    "/supplier-material-orders/{supplier_order_id}/confirm",
    response_model=SupplierOrderResponse,
)
def confirm_arrival(
    supplier_order_id: int,
    request: SupplierArrivalConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SupplierOrderResponse:
    return supplier_order_service.confirm_arrival(
        db, supplier_order_id, request, actor_user_id_or_system(db, actor), actor=actor,
    )


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> list[NotificationResponse]:
    return supplier_order_service.list_notifications(
        db, actor_user_id_or_system(db, actor), actor=actor,
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> NotificationResponse:
    return supplier_order_service.mark_notification_read(
        db, notification_id, actor_user_id_or_system(db, actor), actor=actor,
    )
