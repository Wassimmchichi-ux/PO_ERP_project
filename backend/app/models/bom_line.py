"""BOMLine ORM model."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Identity, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BOMLine(Base):
    __tablename__ = "BOMLine"
    __table_args__ = (
        Index("BOMLine_bom_id_line_number_idx", "bom_id", "line_number", unique=True),
    )

    bom_line_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    bom_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("BOM.bom_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_part_number: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("Material.material_part_number", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    coefficient: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    part_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cover_revision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cover_pn: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity_tpdm: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    cover_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    total_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    total_sqm: Mapped[Decimal | None] = mapped_column(Numeric(10,4), nullable=True)

    bom: Mapped["BOM"] = relationship("BOM", back_populates="lines")
    material: Mapped["Material"] = relationship("Material", back_populates="bom_lines")
