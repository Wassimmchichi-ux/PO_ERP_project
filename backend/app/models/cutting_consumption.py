"""CuttingConsumption ORM model."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CuttingConsumption(Base):
    __tablename__ = "CuttingConsumption"

    consumption_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    launch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Launch.launch_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    material_part_number: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("Material.material_part_number", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    quantity_consumed: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    nesting_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cutman_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    consumed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    launch: Mapped["Launch"] = relationship(
        "Launch",
        back_populates="cutting_consumptions",
    )
    material: Mapped["Material"] = relationship(
        "Material",
        back_populates="cutting_consumptions",
    )
    cutman_document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[cutman_document_id],
    )
