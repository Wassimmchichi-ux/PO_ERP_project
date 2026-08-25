# app/models/user.py

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    registration_number: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        ENUM("ADMIN","LAUNCH ENGINEER","LAUNCH MANAGER","PLANT MANAGER","WAREHOUSE TEAM LEADER","WAREHOUSE PERSONNEL", name="role_code", create_type=False),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        ENUM("ACTIVE", "INACTIVE", name="record_status", create_type=False),
        nullable=False,
        server_default="ACTIVE",
    )

    failed_login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default="now()",
    )
