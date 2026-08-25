"""DeliveryMethod ORM model."""
from __future__ import annotations

from sqlalchemy import Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DeliveryMethod(Base):
    __tablename__ = "DeliveryMethod"

    delivery_method_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Active",
        comment="Active, Inactive",
    )

    purchase_order_lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine",
        back_populates="delivery_method",
    )
    launches: Mapped[list["Launch"]] = relationship(
        "Launch",
        back_populates="delivery_method",
    )
