"""Original cutting exports and reviewed consumption-posting metadata."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, JSON, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CuttingReportImport(Base):
    __tablename__ = "CuttingReportImport"

    report_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_rows: Mapped[list] = mapped_column(JSON, nullable=False)
    imported_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    posted_launch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("Launch.launch_id"), nullable=True)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_usage_unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
