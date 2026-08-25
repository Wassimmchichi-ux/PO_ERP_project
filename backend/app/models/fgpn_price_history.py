"""FGPNPriceHistory ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FGPNPriceHistory(Base):
    __tablename__ = "FGPNPriceHistory"

    price_history_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    fgpn_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("FGPN.fgpn_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    old_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    new_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    audit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("AuditLog.audit_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )

    fgpn: Mapped["FGPN"] = relationship("FGPN", back_populates="price_history")
    changer: Mapped["User"] = relationship("User")
    audit: Mapped["AuditLog"] = relationship(
        "AuditLog",
        back_populates="fgpn_price_history",
    )
