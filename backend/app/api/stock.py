"""Stock API router."""
import logging
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.schemas.stock import (
    StockSummaryListResponse,
    ProductionStockListResponse,
    InTransitListResponse,
    MaterialStockDetailResponse,
    ProductionHandoverRequest,
    ProductionHandoverResponse,
    StockDashboardStats,
    StockUnitReceptionRequest,
    StockUnitReceptionResponse,
)
from app.repositories.bom_repository import _get_system_user
from app.services import stock_management_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stock", tags=["stock"])


@router.post("/units/reception", response_model=StockUnitReceptionResponse, status_code=status.HTTP_201_CREATED)
def record_stock_unit_reception(
    request: StockUnitReceptionRequest,
    db: Annotated[Session, Depends(get_db)]
) -> StockUnitReceptionResponse:
    """Record warehouse/in-transit stock and optionally affect it to a launch owner."""
    user_id = _get_system_user(db)
    return stock_management_service.record_stock_unit_reception(db, request, user_id)


@router.get("/summary", response_model=StockSummaryListResponse)
def get_stock_summary(
    db: Annotated[Session, Depends(get_db)]
) -> StockSummaryListResponse:
    """Get aggregated material availability across warehouse, production, and in-transit."""
    items = stock_management_service.get_stock_summary(db)
    return StockSummaryListResponse(items=items, total=len(items))


@router.get("/production", response_model=ProductionStockListResponse)
def get_production_stock(
    db: Annotated[Session, Depends(get_db)]
) -> ProductionStockListResponse:
    """Get production/WIP remaining quantities per material."""
    items = stock_management_service.get_production_stock(db)
    return ProductionStockListResponse(items=items, total=len(items))


@router.get("/in-transit", response_model=InTransitListResponse)
def get_in_transit_stock(
    db: Annotated[Session, Depends(get_db)],
    from_date: Optional[date] = Query(None, description="Start date (inclusive)"),
    to_date: Optional[date] = Query(None, description="End date (inclusive)")
) -> InTransitListResponse:
    """Get in-transit stock entries, optionally filtered by expected arrival date range."""
    items = stock_management_service.get_in_transit_stock(db, from_date, to_date)
    return InTransitListResponse(items=items, total=len(items))


@router.get("/in-transit/today", response_model=InTransitListResponse)
def get_todays_arrivals(
    db: Annotated[Session, Depends(get_db)]
) -> InTransitListResponse:
    """Get all in-transit material expected to arrive today."""
    items = stock_management_service.get_todays_arrivals(db)
    return InTransitListResponse(items=items, total=len(items))


@router.get("/dashboard", response_model=StockDashboardStats)
def get_dashboard_stats(
    db: Annotated[Session, Depends(get_db)]
) -> StockDashboardStats:
    """Get aggregated statistics useful for the ERP UI."""
    return stock_management_service.get_dashboard_stats(db)


@router.get("/materials/{material_part_number}", response_model=MaterialStockDetailResponse)
def get_material_stock_detail(
    material_part_number: str,
    db: Annotated[Session, Depends(get_db)]
) -> MaterialStockDetailResponse:
    """Get stock detail (warehouse, production, in-transit) for a specific material."""
    return stock_management_service.get_material_stock_detail(db, material_part_number)


@router.post("/units/{stock_unit_id}/production-handover", response_model=ProductionHandoverResponse)
def confirm_production_handover(
    stock_unit_id: int,
    request: ProductionHandoverRequest,
    db: Annotated[Session, Depends(get_db)]
) -> ProductionHandoverResponse:
    """Confirm production received an issued stock unit after signed handover upload."""
    detail = stock_management_service.confirm_production_handover(
        db,
        stock_unit_id,
        request.handover_document_id,
    )
    return ProductionHandoverResponse(stock_unit_id=stock_unit_id, material_detail=detail)
