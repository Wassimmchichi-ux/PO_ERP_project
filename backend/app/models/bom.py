"""BOM ORM model."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BOM(Base):
    __tablename__ = "BOM"

    bom_id: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )

    # ---------------------------------------------------------
    # BOM identity / version
    # ---------------------------------------------------------

    fgpn_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "FGPN.fgpn_id",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "Document.document_id",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=False,
    )

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # ---------------------------------------------------------
    # Information extracted FROM the BOM Excel file
    # ---------------------------------------------------------

    source_reported_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    source_report_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    source_report_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )


    # ---------------------------------------------------------
    # Audit
    # ---------------------------------------------------------

    audit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "AuditLog.audit_id",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=False,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    fgpn: Mapped["FGPN"] = relationship(
        "FGPN",
        back_populates="boms",
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="boms",
    )

    audit: Mapped["AuditLog"] = relationship(
        "AuditLog",
        back_populates="boms",
    )

    lines: Mapped[list["BOMLine"]] = relationship(
        "BOMLine",
        back_populates="bom",
    )