"""Administrator-maintained supplier master record."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Supplier(Base):
    __tablename__ = "Supplier"

    supplier_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    supplier_reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="Active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    material_orders: Mapped[list["SupplierMaterialOrder"]] = relationship(
        "SupplierMaterialOrder", back_populates="supplier",
    )
