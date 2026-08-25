"""Document ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Document(Base):
    __tablename__ = "Document"

    document_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    document_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="PO, BOM, CUTMAN_REPORT, LAUNCH_SUMMARY, SIGNED_HANDOVER, MTG_MINUTES, OTHER",
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )

    uploader: Mapped["User"] = relationship("User")
    boms: Mapped[list["BOM"]] = relationship("BOM", back_populates="document")
