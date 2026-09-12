"""PurchaseOrder ORM model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PurchaseOrder(Base):
    __tablename__ = "PurchaseOrder"

    po_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    po_number: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Customer.customer_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    contact_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Contact.contact_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    current_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("PurchaseOrderVersion.po_version_id", deferrable=True, initially="IMMEDIATE"),
        nullable=True,
    )
    current_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Unplanned, In Progress, Done, Packaged, Delivered",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="purchase_orders",
    )
    contact: Mapped["Contact"] = relationship(
        "Contact",
        back_populates="purchase_orders",
    )
    current_version: Mapped["PurchaseOrderVersion"] = relationship(
        "PurchaseOrderVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    versions: Mapped[list["PurchaseOrderVersion"]] = relationship(
        "PurchaseOrderVersion",
        foreign_keys="PurchaseOrderVersion.po_id",
        back_populates="purchase_order",
    )
    status_history: Mapped[list["POStatusHistory"]] = relationship(
        "POStatusHistory",
        back_populates="purchase_order",
    )
    launch_pos: Mapped[list["LaunchPO"]] = relationship(
        "LaunchPO",
        back_populates="purchase_order",
    )
