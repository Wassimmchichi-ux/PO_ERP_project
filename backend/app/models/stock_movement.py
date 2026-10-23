"""Immutable stock movement ledger used by every material workflow."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StockMovement(Base):
    __tablename__ = "StockMovement"

    movement_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    stock_unit_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("StockUnit.stock_unit_id", ondelete="SET NULL", deferrable=True),
        nullable=True,
    )
    supplier_order_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "SupplierMaterialOrder.supplier_order_id",
            ondelete="SET NULL",
            deferrable=True,
        ),
        nullable=True,
    )
    material_part_number: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("Material.material_part_number", deferrable=True),
        nullable=False,
    )
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity_change: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    warehouse_quantity_after: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stock_unit_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", deferrable=True), nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    material: Mapped["Material"] = relationship("Material")
    actor: Mapped["User"] = relationship("User")
    stock_unit: Mapped["StockUnit | None"] = relationship("StockUnit")
    supplier_order: Mapped["SupplierMaterialOrder | None"] = relationship(
        "SupplierMaterialOrder"
    )
