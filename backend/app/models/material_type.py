"""Material type ORM model."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.material import Material


class MaterialType(Base):
    __tablename__ = "MaterialType"

    material_type_id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="c, m, s",
    )
    unit: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="m, kg, pcs, etc.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Active",
        comment="Active, Inactive",
    )

    materials: Mapped[list[Material]] = relationship(
        "Material",
        back_populates="material_type",
    )
