"""Material ORM model."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.material_type import MaterialType
    from app.models.stock_unit import StockUnit


class Material(Base):
    __tablename__ = "Material"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    material_part_number: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )
    description: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    material_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "MaterialType.material_type_id",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Active",
    )
    critical_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
    )

    material_type: Mapped[MaterialType] = relationship(
        "MaterialType",
        back_populates="materials",
    )
    stock_units: Mapped[list[StockUnit]] = relationship(
        "StockUnit",
        back_populates="material",
    )
    bom_lines: Mapped[list["BOMLine"]] = relationship(
        "BOMLine",
        back_populates="material",
    )
    cutting_consumptions: Mapped[list["CuttingConsumption"]] = relationship(
        "CuttingConsumption",
        back_populates="material",
    )
