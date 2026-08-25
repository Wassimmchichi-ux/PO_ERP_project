"""LaunchFGPN ORM model."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Identity, Index, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LaunchFGPN(Base):
    __tablename__ = "LaunchFGPN"
    __table_args__ = (
        Index(
            "LaunchFGPN_launch_id_fgpn_id_po_line_id_idx",
            "launch_id",
            "fgpn_id",
            "po_line_id",
            unique=True,
        ),
    )

    launch_fgpn_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    launch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Launch.launch_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    fgpn_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("FGPN.fgpn_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    po_line_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("PurchaseOrderLine.po_line_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    launch: Mapped["Launch"] = relationship("Launch", back_populates="launch_fgpns")
    fgpn: Mapped["FGPN"] = relationship("FGPN", back_populates="launch_fgpns")
    po_line: Mapped["PurchaseOrderLine"] = relationship(
        "PurchaseOrderLine",
        back_populates="launch_fgpns",
    )
