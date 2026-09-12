"""Launch ORM model."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Launch(Base):
    __tablename__ = "Launch"

    launch_id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    simulation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Simulation.simulation_id", deferrable=True, initially="IMMEDIATE"),
        unique=True,
        nullable=False,
    )
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_method_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("DeliveryMethod.delivery_method_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    receiver_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ManufacturingReceiver.receiver_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="PLANNED, IN_PROGRESS, DONE, PACKAGED, DELIVERED, VERIFIED",
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    verified_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    cmr_document_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=True,
    )
    customer_delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    delivery_method: Mapped["DeliveryMethod"] = relationship(
        "DeliveryMethod",
        back_populates="launches",
    )
    receiver: Mapped["ManufacturingReceiver"] = relationship(
        "ManufacturingReceiver",
        back_populates="launches",
    )
    completed_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[completed_by],
    )
    verified_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[verified_by],
    )
    verification_document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[verification_document_id],
    )
    cmr_document: Mapped["Document | None"] = relationship(
        "Document",
        foreign_keys=[cmr_document_id],
    )
    simulation: Mapped["Simulation"] = relationship(
        "Simulation",
        foreign_keys=[simulation_id],
        back_populates="launch",
        uselist=False,
    )
    launch_pos: Mapped[list["LaunchPO"]] = relationship(
        "LaunchPO",
        back_populates="launch",
    )
    launch_fgpns: Mapped[list["LaunchFGPN"]] = relationship(
        "LaunchFGPN",
        back_populates="launch",
    )
    cutting_consumptions: Mapped[list["CuttingConsumption"]] = relationship(
        "CuttingConsumption",
        back_populates="launch",
    )
    verifications: Mapped[list["LaunchVerification"]] = relationship(
        "LaunchVerification",
        back_populates="launch",
    )
