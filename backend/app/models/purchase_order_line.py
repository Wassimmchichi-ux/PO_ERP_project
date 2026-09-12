"""PurchaseOrderLine ORM model."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Identity, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PurchaseOrderLine(Base):
    __tablename__ = "PurchaseOrderLine"
    __table_args__ = (
        Index(
            "PurchaseOrderLine_po_version_id_line_number_idx",
            "po_version_id",
            "line_number",
            unique=True,
        ),
        Index(
            "PurchaseOrderLine_po_version_id_fgpn_id_idx",
            "po_version_id",
            "fgpn_id",
            unique=True,
        ),
    )

    po_line_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    po_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("PurchaseOrderVersion.po_version_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fgpn_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("FGPN.fgpn_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    development_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trim_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ordered_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pickup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_method_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("DeliveryMethod.delivery_method_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    po_version: Mapped["PurchaseOrderVersion"] = relationship(
        "PurchaseOrderVersion",
        back_populates="lines",
    )
    fgpn: Mapped["FGPN"] = relationship(
        "FGPN",
        back_populates="purchase_order_lines",
    )
    delivery_method: Mapped["DeliveryMethod"] = relationship(
        "DeliveryMethod",
        back_populates="purchase_order_lines",
    )
    launch_fgpns: Mapped[list["LaunchFGPN"]] = relationship(
        "LaunchFGPN",
        back_populates="po_line",
    )
