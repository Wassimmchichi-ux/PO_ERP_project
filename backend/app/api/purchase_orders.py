"""Purchase-order register API."""
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_policy_actor
from app.dependencies.db import get_db
from app.policies import PolicyActor
from app.schemas.purchase_order import PurchaseOrderDetailResponse, PurchaseOrderListResponse
from app.services import purchase_order_service

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


@router.get("", response_model=PurchaseOrderListResponse)
def list_purchase_orders(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> PurchaseOrderListResponse:
    """List current imported PO versions for the Purchase Orders register."""
    return purchase_order_service.list_purchase_orders(db, actor=actor)


@router.get("/{po_id}", response_model=PurchaseOrderDetailResponse)
def get_purchase_order(
    po_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> PurchaseOrderDetailResponse:
    """Get one imported purchase order for its detail page."""
    return purchase_order_service.get_purchase_order(db, po_id, actor=actor)


@router.delete("/{po_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_purchase_order(
    po_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> Response:
    """Delete an unlinked test/import PO; operationally linked POs are retained."""
    purchase_order_service.delete_purchase_order(db, po_id, actor=actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
