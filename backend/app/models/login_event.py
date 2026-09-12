# app/models/login_event.py

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoginEvent(Base):
    __tablename__ = "login_events"
    __table_args__ = (
        Index("login_events_attempted_rn_occurred_at_idx", "attempted_rn", "occurred_at"),
        {"comment": "Stores successful and failed attempts, including attempts for an unknown username."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )

    attempted_rn: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    succeeded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        ENUM(
            "NONE",
            "UNKNOWN_USER",
            "INVALID_PASSWORD",
            "ACCOUNT_LOCKED",
            "ACCOUNT_INACTIVE",
            name="failure_reason",
            create_type=False,
        ),
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default="now()",
    )
