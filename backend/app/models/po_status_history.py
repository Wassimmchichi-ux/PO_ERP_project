"""POStatusHistory ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class POStatusHistory(Base):
    __tablename__ = "POStatusHistory"

    status_history_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    po_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("PurchaseOrder.po_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    old_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("AuditLog.audit_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder",
        back_populates="status_history",
    )
    changer: Mapped["User"] = relationship("User")
    audit: Mapped["AuditLog"] = relationship(
        "AuditLog",
        back_populates="po_status_history",
    )
