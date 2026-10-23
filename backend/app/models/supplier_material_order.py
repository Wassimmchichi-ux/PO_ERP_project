"""Supplier material order header created by launch engineering."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SupplierMaterialOrder(Base):
    __tablename__ = "SupplierMaterialOrder"

    supplier_order_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Project.project_id", deferrable=True), nullable=False,
    )
    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Supplier.supplier_id", deferrable=True), nullable=False,
    )
    # Snapshots preserve the legal label used when the order was created even
    # if an administrator later updates the supplier master.
    supplier_name: Mapped[str] = mapped_column(String(150), nullable=False)
    supplier_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ordered_for_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", deferrable=True), nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", deferrable=True), nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="OPEN",
        comment="OPEN, ARRIVAL_ENTERED, CONFIRMED, CANCELLED",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", deferrable=True), nullable=True,
    )
    discrepancy_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    project: Mapped["Project"] = relationship("Project")
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="material_orders")
    ordered_for: Mapped["User"] = relationship("User", foreign_keys=[ordered_for_user_id])
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    confirmer: Mapped["User | None"] = relationship("User", foreign_keys=[confirmed_by])
    lines: Mapped[list["SupplierMaterialOrderLine"]] = relationship(
        "SupplierMaterialOrderLine", back_populates="order", cascade="all, delete-orphan",
    )
