"""AuditLog ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "AuditLog"

    audit_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User")
    fgpn_price_history: Mapped[list["FGPNPriceHistory"]] = relationship(
        "FGPNPriceHistory",
        back_populates="audit",
    )
    boms: Mapped[list["BOM"]] = relationship("BOM", back_populates="audit")
    po_status_history: Mapped[list["POStatusHistory"]] = relationship(
        "POStatusHistory",
        back_populates="audit",
    )
    correction_events: Mapped[list["CorrectionEvent"]] = relationship(
        "CorrectionEvent",
        back_populates="audit",
    )
