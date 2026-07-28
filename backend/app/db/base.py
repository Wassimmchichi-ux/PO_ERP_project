"""SQLAlchemy declarative base and reusable model mixins.

No ERP entities are defined here — this is only the shared foundation
every future model (Project, PurchaseOrder, Material, ...) will build
on, so that behavior like "how is a primary key generated" or "how is
a timestamp stamped" is defined exactly once.

Spring Boot equivalent: an ``@MappedSuperclass`` with an
``@Id @GeneratedValue`` UUID field, ``@CreationTimestamp`` /
``@UpdateTimestamp`` auditing fields, and a Hibernate ``@Where``
soft-delete filter.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for every ORM model in the application."""
    pass


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key generated application-side.

    UUIDs (over auto-increment integers) avoid leaking record counts
    through the API and make it safe to generate an id before a row is
    persisted — useful once services start composing multiple related
    inserts in one transaction.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Adds created_at / updated_at columns maintained by the database.

    Using ``server_default=func.now()`` and ``server_onupdate`` (via
    ``onupdate``) means the database is the source of truth for these
    timestamps, not application clocks — consistent even if the app is
    scaled across multiple hosts with slight clock drift.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Adds a nullable deleted_at column for soft-deletable entities.

    Deliberately opt-in per model (mixed in explicitly), not applied to
    ``Base`` globally: the SRS is explicit that some records must be
    genuinely immutable (audit/traceability entries) and should never
    expose a delete path at all, soft or otherwise. Mixing this in is a
    conscious per-model decision.
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
