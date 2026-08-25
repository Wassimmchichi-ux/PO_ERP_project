"""LaunchPO ORM model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LaunchPO(Base):
    __tablename__ = "LaunchPO"
    __table_args__ = (
        Index("LaunchPO_launch_id_po_id_idx", "launch_id", "po_id", unique=True),
    )

    launch_po_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    launch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Launch.launch_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    po_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("PurchaseOrder.po_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    launch: Mapped["Launch"] = relationship("Launch", back_populates="launch_pos")
    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder",
        back_populates="launch_pos",
    )
