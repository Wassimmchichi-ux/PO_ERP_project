"""LaunchVerification ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LaunchVerification(Base):
    __tablename__ = "LaunchVerification"

    verification_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    launch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Launch.launch_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    summary_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    engineer_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    verified_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    verified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="PENDING, VERIFIED, REJECTED",
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    launch: Mapped["Launch"] = relationship("Launch", back_populates="verifications")
    summary_document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[summary_document_id],
    )
    engineer_document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[engineer_document_id],
    )
    verifier: Mapped["User"] = relationship("User")
