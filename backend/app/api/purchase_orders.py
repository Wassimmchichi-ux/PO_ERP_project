"""Purchase-order register API."""
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_policy_actor
from app.dependencies.db import get_db
from app.policies import PolicyActor
from fastapi import Query
from app.schemas.purchase_order import (
    PurchaseOrderDeleteRequest,
    PurchaseOrderDetailResponse,
    PurchaseOrderListResponse,
    VersionComparisonResponse,
)
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
    body: PurchaseOrderDeleteRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> Response:
    """Delete an unlinked PO after the owner confirms a deletion reason."""
    purchase_order_service.delete_purchase_order(
        db, po_id, deletion_reason=body.deletion_reason, actor=actor
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/versions/{po_version_id}/pdf")
def get_po_version_pdf(
    po_version_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> Response:
    """Return the original PDF file associated with this purchase order version."""
    content, filename = purchase_order_service.get_po_version_pdf(
        db, po_version_id=po_version_id, actor=actor
    )
    safe_filename = filename.replace('"', "").replace("\r", "").replace("\n", "")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "Content-Type": "application/pdf",
        },
    )


@router.get("/{po_id}/compare", response_model=VersionComparisonResponse)
def compare_purchase_order_versions(
    po_id: int,
    v1: Annotated[int, Query(description="First version number to compare")],
    v2: Annotated[int, Query(description="Second version number to compare")],
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> VersionComparisonResponse:
    """Compare field-by-field differences between two versions of the same PO."""
    return purchase_order_service.compare_po_versions(
        db, po_id=po_id, v1=v1, v2=v2, actor=actor
    )
