"""create purchase order tables

Revision ID: 0001_create_purchase_orders
Revises:
Create Date: 2026-07-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0001_create_purchase_orders"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("po_number", sa.String(length=50), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("change_date", sa.Date(), nullable=False),
        sa.Column("supplier_no", sa.String(length=50), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("supplier_address", sa.Text(), nullable=True),
        sa.Column("buyer_name", sa.String(length=255), nullable=False),
        sa.Column("buyer_vat", sa.String(length=50), nullable=True),
        sa.Column("buyer_register_nr", sa.String(length=50), nullable=True),
        sa.Column("invoicing_party_taxid", sa.String(length=50), nullable=True),
        sa.Column("delivery_contact", sa.String(length=255), nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("payment_terms", sa.String(length=255), nullable=True),
        sa.Column("incoterms", sa.String(length=255), nullable=True),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("contact_tel", sa.String(length=50), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("header_text", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("stated_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("computed_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("totals_match", sa.Boolean(), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "change_date >= order_date",
            name="ck_purchase_orders_change_date_on_or_after_order_date",
        ),
        sa.CheckConstraint(
            "computed_total >= 0",
            name="ck_purchase_orders_computed_total_non_negative",
        ),
        sa.CheckConstraint("line_count > 0", name="ck_purchase_orders_line_count_positive"),
        sa.CheckConstraint(
            "stated_total >= 0",
            name="ck_purchase_orders_stated_total_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "po_number",
            "version",
            name="uq_purchase_orders_po_number_version",
        ),
    )
    op.create_index(
        "ix_purchase_orders_po_number",
        "purchase_orders",
        ["po_number"],
        unique=False,
    )
    op.create_index(
        "ix_purchase_orders_supplier_no",
        "purchase_orders",
        ["supplier_no"],
        unique=False,
    )

    op.create_table(
        "purchase_order_lines",
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.String(length=20), nullable=False),
        sa.Column("plant", sa.String(length=50), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("material_group", sa.String(length=50), nullable=True),
        sa.Column("part_number", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("customer_part_ref", sa.String(length=100), nullable=True),
        sa.Column("item_category", sa.String(length=100), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=5), nullable=False),
        sa.Column("total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_order_lines_quantity_positive"),
        sa.CheckConstraint("total >= 0", name="ck_purchase_order_lines_total_non_negative"),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_purchase_order_lines_unit_price_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "purchase_order_id",
            "line_no",
            name="uq_purchase_order_lines_order_line_no",
        ),
    )
    op.create_index(
        "ix_purchase_order_lines_part_number",
        "purchase_order_lines",
        ["part_number"],
        unique=False,
    )
    op.create_index(
        "ix_purchase_order_lines_purchase_order_id",
        "purchase_order_lines",
        ["purchase_order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_order_lines_purchase_order_id",
        table_name="purchase_order_lines",
    )
    op.drop_index("ix_purchase_order_lines_part_number", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")

    op.drop_index("ix_purchase_orders_supplier_no", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_po_number", table_name="purchase_orders")
    op.drop_table("purchase_orders")
