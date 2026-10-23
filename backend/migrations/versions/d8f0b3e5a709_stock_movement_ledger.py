"""Add the immutable stock movement ledger.

Revision ID: d8f0b3e5a709
Revises: c7e9a2d4f608
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d8f0b3e5a709"
down_revision = "c7e9a2d4f608"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "StockMovement",
        sa.Column("movement_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("stock_unit_id", sa.Integer(), nullable=True),
        sa.Column("supplier_order_id", sa.Integer(), nullable=True),
        sa.Column("material_part_number", sa.String(50), nullable=False),
        sa.Column("movement_type", sa.String(50), nullable=False),
        sa.Column("quantity_change", sa.Numeric(10, 4), nullable=False),
        sa.Column("warehouse_quantity_after", sa.Numeric(10, 4), nullable=True),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=True),
        sa.Column("stock_unit_reference", sa.String(100), nullable=True),
        sa.Column("source_reference", sa.String(100), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["stock_unit_id"], ["StockUnit.stock_unit_id"],
            ondelete="SET NULL", deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["supplier_order_id"], ["SupplierMaterialOrder.supplier_order_id"],
            ondelete="SET NULL", deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["material_part_number"], ["Material.material_part_number"],
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], deferrable=True,
        ),
    )
    op.create_index(
        "StockMovement_material_date_idx",
        "StockMovement",
        ["material_part_number", "occurred_at"],
    )
    op.create_index(
        "StockMovement_unit_date_idx",
        "StockMovement",
        ["stock_unit_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("StockMovement_unit_date_idx", table_name="StockMovement")
    op.drop_index("StockMovement_material_date_idx", table_name="StockMovement")
    op.drop_table("StockMovement")
