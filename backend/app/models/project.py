"""Project ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.fgpn import FGPN


class Project(Base):
    __tablename__ = "Project"

    project_id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    project_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    jit_customer: Mapped[str | None] = mapped_column(String(150), nullable=True)
    oem_customer: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    car_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    launch_engineer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Active",
        comment="Active, Inactive",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deactivation_document_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("Document.document_id", deferrable=True, initially="IMMEDIATE"),
        nullable=True,
    )

    fgpns: Mapped[list[FGPN]] = relationship(
        "FGPN",
        back_populates="project",
    )
    launch_engineer_user: Mapped["User"] = relationship("User")
