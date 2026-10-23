"""Retain the exact source file used for a purchase-order parsing draft.

Revision ID: f2a6c9d1e405
Revises: e0f4a6b8c123
"""
from alembic import op
import sqlalchemy as sa


revision = "f2a6c9d1e405"
down_revision = "e0f4a6b8c123"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ParsedPurchaseOrder", sa.Column("source_content", sa.LargeBinary(), nullable=True))
    op.add_column(
        "ParsedPurchaseOrder",
        sa.Column("source_content_type", sa.String(length=100), nullable=True),
    )


def downgrade():
    op.drop_column("ParsedPurchaseOrder", "source_content_type")
    op.drop_column("ParsedPurchaseOrder", "source_content")
