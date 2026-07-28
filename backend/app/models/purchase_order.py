"""Purchase order persistence models.

These models represent the already-extracted PO data after OCR/parsing has
completed. They deliberately do not know anything about PDF extraction.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class PurchaseOrder(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Purchase order header data from an extracted JSON payload."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint(
            "po_number",
            "version",
            name="uq_purchase_orders_po_number_version",
        ),
        CheckConstraint(
            "stated_total >= 0",
            name="ck_purchase_orders_stated_total_non_negative",
        ),
        CheckConstraint(
            "computed_total >= 0",
            name="ck_purchase_orders_computed_total_non_negative",
        ),
        CheckConstraint("line_count > 0", name="ck_purchase_orders_line_count_positive"),
        CheckConstraint(
            "change_date >= order_date",
            name="ck_purchase_orders_change_date_on_or_after_order_date",
        ),
        Index("ix_purchase_orders_po_number", "po_number"),
        Index("ix_purchase_orders_supplier_no", "supplier_no"),
    )

    po_number: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    order_date: Mapped[date] = mapped_column(nullable=False)
    change_date: Mapped[date] = mapped_column(nullable=False)

    supplier_no: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    buyer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_vat: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    buyer_register_nr: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    invoicing_party_taxid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    delivery_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    delivery_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payment_terms: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    incoterms: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_tel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    header_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    stated_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    computed_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    totals_match: Mapped[bool] = mapped_column(nullable=False, default=False)
    line_count: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.line_no",
    )


class PurchaseOrderLine(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A single line item belonging to a purchase order."""

    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint(
            "purchase_order_id",
            "line_no",
            name="uq_purchase_order_lines_order_line_no",
        ),
        CheckConstraint("quantity > 0", name="ck_purchase_order_lines_quantity_positive"),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_purchase_order_lines_unit_price_non_negative",
        ),
        CheckConstraint("total >= 0", name="ck_purchase_order_lines_total_non_negative"),
        Index("ix_purchase_order_lines_purchase_order_id", "purchase_order_id"),
        Index("ix_purchase_order_lines_part_number", "part_number"),
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_no: Mapped[str] = mapped_column(String(20), nullable=False)
    plant: Mapped[str] = mapped_column(String(50), nullable=False)
    due_date: Mapped[date] = mapped_column(nullable=False)
    material_group: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    part_number: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_part_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    item_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 5), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
