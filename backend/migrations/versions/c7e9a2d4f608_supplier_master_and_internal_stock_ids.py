"""Add supplier master and link material orders.

Revision ID: c7e9a2d4f608
Revises: b4d8e1f3a607
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e9a2d4f608"
down_revision: Union[str, None] = "b4d8e1f3a607"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "Supplier",
        sa.Column("supplier_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("supplier_reference", sa.String(50), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("status", sa.String(20), server_default="Active", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("supplier_reference", name="Supplier_supplier_reference_key"),
    )
    op.add_column(
        "SupplierMaterialOrder",
        sa.Column("supplier_id", sa.Integer(), nullable=True),
    )
    # Preserve old test/prototype orders as individual migrated supplier
    # records. Administrators can deactivate them and create the official
    # reference/full-name master values after the upgrade.
    op.execute(sa.text('''
        INSERT INTO "Supplier" (
            supplier_reference, full_name, status, created_at, updated_at
        )
        SELECT
            'MIGRATED-' || supplier_order_id,
            supplier_name,
            'Active',
            created_at,
            updated_at
        FROM "SupplierMaterialOrder"
    '''))
    op.execute(sa.text('''
        UPDATE "SupplierMaterialOrder" AS material_order
        SET supplier_id = supplier.supplier_id
        FROM "Supplier" AS supplier
        WHERE supplier.supplier_reference = 'MIGRATED-' || material_order.supplier_order_id
    '''))
    op.alter_column("SupplierMaterialOrder", "supplier_id", nullable=False)
    op.create_foreign_key(
        "SupplierMaterialOrder_supplier_id_fkey",
        "SupplierMaterialOrder",
        "Supplier",
        ["supplier_id"],
        ["supplier_id"],
        deferrable=True,
        initially="IMMEDIATE",
    )
    op.create_index(
        "SupplierMaterialOrder_supplier_id_idx",
        "SupplierMaterialOrder",
        ["supplier_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "SupplierMaterialOrder_supplier_id_idx",
        table_name="SupplierMaterialOrder",
    )
    op.drop_constraint(
        "SupplierMaterialOrder_supplier_id_fkey",
        "SupplierMaterialOrder",
        type_="foreignkey",
    )
    op.drop_column("SupplierMaterialOrder", "supplier_id")
    op.drop_table("Supplier")
