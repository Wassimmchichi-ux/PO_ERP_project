"""Contact ORM model."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer


class Contact(Base):
    __tablename__ = "Contact"

    contact_id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "Customer.customer_id",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    customer: Mapped[Customer] = relationship(
        "Customer",
        back_populates="contacts",
    )
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        "PurchaseOrder",
        back_populates="contact",
    )
