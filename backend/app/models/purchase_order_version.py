"""PurchaseOrderVersion ORM model."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Identity, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PurchaseOrderVersion(Base):
    __tablename__ = "PurchaseOrderVersion"
    __table_args__ = (
        Index(
            "PurchaseOrderVersion_po_id_version_number_idx",
            "po_id",
            "version_number",
            unique=True,
        ),
    )

    po_version_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    po_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("PurchaseOrder.po_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    car_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    engineering_phase_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    po_level: Mapped[str | None] = mapped_column(String(6), nullable=True)
    reason_of_purchase_order: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    change_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder",
        foreign_keys=[po_id],
        back_populates="versions",
    )
    document: Mapped["Document"] = relationship("Document")
    creator: Mapped["User"] = relationship("User")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine",
        back_populates="po_version",
    )
    changes: Mapped[list["PurchaseOrderVersionChange"]] = relationship(
        "PurchaseOrderVersionChange",
        back_populates="po_version",
    )
