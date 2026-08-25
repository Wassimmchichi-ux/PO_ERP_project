"""StockAllocation ORM model."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StockAllocation(Base):
    __tablename__ = "StockAllocation"

    allocation_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    simulation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Simulation.simulation_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    stock_unit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("StockUnit.stock_unit_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    allocated_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    allocation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="SIMULATION",
        comment="SIMULATION, LAUNCH",
    )
    is_whole_issue: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    source_location: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="WAREHOUSE, PRODUCTION",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Reserved",
        comment="Reserved, Released, Delivered",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    simulation: Mapped["Simulation"] = relationship(
        "Simulation",
        back_populates="stock_allocations",
    )
    stock_unit: Mapped["StockUnit"] = relationship(
        "StockUnit",
        back_populates="stock_allocations",
    )
