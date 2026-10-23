"""Parsed purchase order staging models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Identity, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

JSON_DOCUMENT = JSONB().with_variant(JSON(), "sqlite")


class ParsedPurchaseOrder(Base):
    __tablename__ = "ParsedPurchaseOrder"

    parsed_po_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    document_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=True,
    )
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parser_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="PARSED",
        comment="PARSED, CORRECTED, VALIDATED, IMPORTED, REJECTED",
    )
    parsed_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    validated_po_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("PurchaseOrder.po_id", deferrable=True, initially="IMMEDIATE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    document: Mapped["Document | None"] = relationship("Document")
    creator: Mapped["User"] = relationship("User")
    validated_purchase_order: Mapped["PurchaseOrder | None"] = relationship("PurchaseOrder")
    corrections: Mapped[list["ParsedPurchaseOrderCorrection"]] = relationship(
        "ParsedPurchaseOrderCorrection",
        back_populates="parsed_purchase_order",
        cascade="all, delete-orphan",
    )
