"""Expected and actual supplier stock-unit quantities."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Identity, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SupplierMaterialOrderLine(Base):
    __tablename__ = "SupplierMaterialOrderLine"

    supplier_order_line_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    supplier_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("SupplierMaterialOrder.supplier_order_id", ondelete="CASCADE"), nullable=False,
    )
    material_part_number: Mapped[str] = mapped_column(
        String(50), ForeignKey("Material.material_part_number", deferrable=True), nullable=False,
    )
    stock_unit_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    business_unit_id: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    expected_arrival_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    actual_business_unit_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    arrival_entered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", deferrable=True), nullable=True,
    )
    arrival_entered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stock_unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("StockUnit.stock_unit_id", deferrable=True), unique=True, nullable=False,
    )

    order: Mapped["SupplierMaterialOrder"] = relationship(
        "SupplierMaterialOrder", back_populates="lines",
    )
    material: Mapped["Material"] = relationship("Material")
    stock_unit: Mapped["StockUnit"] = relationship("StockUnit")
    arrival_entered_by_user: Mapped["User | None"] = relationship("User")
