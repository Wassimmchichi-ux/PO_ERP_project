"""StockIssueHandover ORM model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StockIssueHandover(Base):
    __tablename__ = "StockIssueHandover"

    delivery_inst_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    simulation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Simulation.simulation_id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    delivery_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    code_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    receiver_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    signed_document_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=True,
    )
    code_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    warehouse_team_leader_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    uploader_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    validation_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    validation_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="Draft",
        comment="Draft, Code_Generated, Document_Generated, Signed_Uploaded, Validated, Expired",
    )

    simulation: Mapped["Simulation"] = relationship(
        "Simulation",
        back_populates="handovers",
    )
    signed_document: Mapped["Document | None"] = relationship("Document")
