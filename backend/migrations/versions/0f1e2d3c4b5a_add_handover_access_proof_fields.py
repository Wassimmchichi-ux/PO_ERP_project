"""Add handover access proof fields

Revision ID: 0f1e2d3c4b5a
Revises: f6b7c8d9e0a1
Create Date: 2026-09-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0f1e2d3c4b5a"
down_revision: Union[str, None] = "f6b7c8d9e0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("StockIssueHandover", "signed_document_id", nullable=True)
    op.add_column("StockIssueHandover", sa.Column("code_used_at", sa.DateTime(), nullable=True))
    op.add_column(
        "StockIssueHandover",
        sa.Column("warehouse_team_leader_name", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("StockIssueHandover", "warehouse_team_leader_name")
    op.drop_column("StockIssueHandover", "code_used_at")
    op.alter_column("StockIssueHandover", "signed_document_id", nullable=False)
