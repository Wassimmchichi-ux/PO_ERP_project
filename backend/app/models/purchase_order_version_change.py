"""PurchaseOrderVersionChange ORM model."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PurchaseOrderVersionChange(Base):
    __tablename__ = "PurchaseOrderVersionChange"

    change_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    po_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("PurchaseOrderVersion.po_version_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="PO_HEADER, PO_LINE",
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    po_version: Mapped["PurchaseOrderVersion"] = relationship(
        "PurchaseOrderVersion",
        back_populates="changes",
    )
