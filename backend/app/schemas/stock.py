"""Pydantic schemas for Stock Management workflows."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class StockSummaryItem(BaseModel):
    material_part_number: str
    description: str
    unit: str
    warehouse_quantity: Decimal
    production_quantity: Decimal
    in_transit_quantity: Decimal
    total_available_quantity: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)


class StockSummaryListResponse(BaseModel):
    items: list[StockSummaryItem]
    total: int


class ProductionStockItem(BaseModel):
    material_part_number: str
    description: str
    unit: str
    total_sent_to_production: Decimal
    total_cutting_consumption: Decimal
    remaining_production_quantity: Decimal

    model_config = ConfigDict(from_attributes=True)


class ProductionStockListResponse(BaseModel):
    items: list[ProductionStockItem]
    total: int


class InTransitItem(BaseModel):
    stock_unit_id: int
    material_part_number: str
    description: str
    unit: str
    quantity: Decimal
    expected_arrival_date: Optional[date]
    days_until_arrival: Optional[int]
    status: str

    model_config = ConfigDict(from_attributes=True)


class InTransitListResponse(BaseModel):
    items: list[InTransitItem]
    total: int


class MaterialStockDetailResponse(BaseModel):
    material_part_number: str
    description: str
    unit: str
    warehouse: Decimal
    production: Decimal
    in_transit: Decimal
    total_available: Decimal
    total_consumed: Decimal
    
    model_config = ConfigDict(from_attributes=True)


class StockDashboardStats(BaseModel):
    total_materials_in_warehouse: int
    total_materials_in_production: int
    total_in_transit_entries: int
    todays_expected_arrivals_count: int
    upcoming_arrivals_count: int


class ProductionHandoverRequest(BaseModel):
    handover_document_id: int


class ProductionHandoverResponse(BaseModel):
    stock_unit_id: int
    status: str = "PRODUCTION"
    material_detail: MaterialStockDetailResponse
