"""FGPN ORM model."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class FGPN(Base):
    __tablename__ = "FGPN"

    fgpn_id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "Project.project_id",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=False,
    )
    fgpn_code: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    trim_style: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    project: Mapped[Project] = relationship(
        "Project",
        back_populates="fgpns",
    )
    price_history: Mapped[list["FGPNPriceHistory"]] = relationship(
        "FGPNPriceHistory",
        back_populates="fgpn",
    )
    boms: Mapped[list["BOM"]] = relationship("BOM", back_populates="fgpn")
    purchase_order_lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine",
        back_populates="fgpn",
    )
    launch_fgpns: Mapped[list["LaunchFGPN"]] = relationship(
        "LaunchFGPN",
        back_populates="fgpn",
    )
