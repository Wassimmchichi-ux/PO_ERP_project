"""Simulation ORM model."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Identity, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Simulation(Base):
    __tablename__ = "Simulation"

    simulation_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    simulation_mode: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="CURRENT_STOCK, INCLUDING_IN_TRANSIT",
    )
    allocation_strategy: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="PRIORITY",
        comment="PRIORITY, MANUAL, PRIORITY_PLUS_MANUAL",
    )
    stock_scope_mode: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="ALL",
        comment="ALL, OWNED_ONLY",
    )
    stock_owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=True,
    )
    include_global_stock: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="When OWNED_ONLY, include global stock units with no affected owner.",
    )
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    safety_coefficient: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="2",
    )
    is_feasible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    shortfall_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    mtg_minutes_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )

    mtg_minutes_document: Mapped["Document"] = relationship("Document")
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    stock_owner: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[stock_owner_user_id],
    )
    launch: Mapped["Launch | None"] = relationship(
        "Launch",
        back_populates="simulation",
        uselist=False,
    )
    stock_allocations: Mapped[list["StockAllocation"]] = relationship(
        "StockAllocation",
        back_populates="simulation",
    )
    selected_fgpns: Mapped[list["SimulationFGPN"]] = relationship(
        "SimulationFGPN",
        back_populates="simulation",
    )
    handovers: Mapped[list["StockIssueHandover"]] = relationship(
        "StockIssueHandover",
        back_populates="simulation",
    )
