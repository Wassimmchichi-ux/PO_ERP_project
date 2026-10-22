"""Merge schema branches and preserve the unit printed on each BOM row.

Revision ID: c8d2e4f6a901
Revises: 9a8b7c6d5e4f, a7b8c9d0e1f2
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa


revision = "c8d2e4f6a901"
down_revision = ("9a8b7c6d5e4f", "a7b8c9d0e1f2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Leave historical rows NULL: the normalized material type does not prove
    # which unit was present in the original workbook.
    op.add_column("BOMLine", sa.Column("source_unit", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("BOMLine", "source_unit")
