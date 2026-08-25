"""SimulationFGPN ORM model."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Identity, Index, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SimulationFGPN(Base):
    __tablename__ = "SimulationFGPN"
    __table_args__ = (
        Index(
            "SimulationFGPN_simulation_po_fgpn_idx",
            "simulation_id",
            "po_id",
            "fgpn_id",
        ),
    )

    simulation_fgpn_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    simulation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Simulation.simulation_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    po_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("PurchaseOrder.po_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    fgpn_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("FGPN.fgpn_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    po_line_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("PurchaseOrderLine.po_line_id", deferrable=True, initially="IMMEDIATE"),
        nullable=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    po_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    simulation_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    launchable_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    simulation: Mapped["Simulation"] = relationship(
        "Simulation",
        back_populates="selected_fgpns",
    )
    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder")
    fgpn: Mapped["FGPN"] = relationship("FGPN")
    po_line: Mapped["PurchaseOrderLine | None"] = relationship("PurchaseOrderLine")
