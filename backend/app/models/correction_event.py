"""CorrectionEvent ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CorrectionEvent(Base):
    __tablename__ = "CorrectionEvent"

    correction_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    entity_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="PO, PO_LINE",
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    original_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    corrected_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    corrected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    audit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("AuditLog.audit_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )

    corrector: Mapped["User"] = relationship("User")
    audit: Mapped["AuditLog"] = relationship(
        "AuditLog",
        back_populates="correction_events",
    )
