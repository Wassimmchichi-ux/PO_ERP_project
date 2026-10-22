"""Field-level corrections for parsed purchase order staging."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Identity, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

JSON_VALUE = JSONB().with_variant(JSON(), "sqlite")


class ParsedPurchaseOrderCorrection(Base):
    __tablename__ = "ParsedPurchaseOrderCorrection"
    __table_args__ = (
        Index(
            "ParsedPurchaseOrderCorrection_parsed_po_id_field_path_idx",
            "parsed_po_id",
            "field_path",
            unique=True,
        ),
    )

    correction_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    parsed_po_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ParsedPurchaseOrder.parsed_po_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    field_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Header field or nested path like lines[0].quantity",
    )
    original_value: Mapped[Any | None] = mapped_column(JSON_VALUE, nullable=True)
    corrected_value: Mapped[Any | None] = mapped_column(JSON_VALUE, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    corrected_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    corrected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    parsed_purchase_order: Mapped["ParsedPurchaseOrder"] = relationship(
        "ParsedPurchaseOrder",
        back_populates="corrections",
    )
    corrector: Mapped["User"] = relationship("User")
