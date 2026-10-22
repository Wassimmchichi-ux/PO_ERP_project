"""Stock unit ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.user import User


class StockUnit(Base):
    __tablename__ = "StockUnit"

    stock_unit_id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    material_part_number: Mapped[str] = mapped_column(
        String(50),
        ForeignKey(
            "Material.material_part_number",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        ENUM(
            "WAREHOUSE",
            "PRODUCTION",
            "ISSUED_TO_PRODUCTION",
            "IN_TRANSIT",
            name="stock_unit_status",
            create_type=False,
        ),
        nullable=False,
        comment="WAREHOUSE, PRODUCTION, ISSUED_TO_PRODUCTION, IN_TRANSIT",
    )
    expected_arrival_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="just for in transit StockUnits",
    )
    parent_stock_unit_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("StockUnit.stock_unit_id", deferrable=True, initially="IMMEDIATE"),
        nullable=True,
        comment="Set when a component/accessory package is split for launch issue traceability",
    )
    handover_document_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=True,
        comment="Signed handover document proving production received issued materials",
    )
    issued_to_production_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    received_by_production_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    reception_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    reception_username: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    Send_prod_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=True,
        comment=(
            "Optional affected launch engineer/manager. NULL means global enterprise stock."
        ),
    )

    material: Mapped[Material] = relationship(
        "Material",
        back_populates="stock_units",
    )
    stock_allocations: Mapped[list["StockAllocation"]] = relationship(
        "StockAllocation",
        back_populates="stock_unit",
    )
    parent_stock_unit: Mapped["StockUnit | None"] = relationship(
        "StockUnit",
        remote_side=[stock_unit_id],
        back_populates="split_children",
    )
    split_children: Mapped[list["StockUnit"]] = relationship(
        "StockUnit",
        back_populates="parent_stock_unit",
    )
    handover_document: Mapped["Document | None"] = relationship("Document")
    user: Mapped[User | None] = relationship("User")
