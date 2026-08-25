"""ManufacturingReceiver ORM model."""
from __future__ import annotations

from sqlalchemy import Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ManufacturingReceiver(Base):
    __tablename__ = "ManufacturingReceiver"

    receiver_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Active",
        comment="Active, Inactive",
    )

    launches: Mapped[list["Launch"]] = relationship(
        "Launch",
        back_populates="receiver",
    )
