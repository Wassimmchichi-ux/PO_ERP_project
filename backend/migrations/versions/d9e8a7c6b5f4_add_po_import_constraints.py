"""Add PO import constraints

Revision ID: d9e8a7c6b5f4
Revises: c2f9a6b4d1e3
Create Date: 2026-08-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9e8a7c6b5f4'
down_revision: Union[str, None] = 'c2f9a6b4d1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'PurchaseOrder',
        'current_version_id',
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_index(
        'FGPN_project_id_fgpn_code_idx',
        'FGPN',
        ['project_id', 'fgpn_code'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('FGPN_project_id_fgpn_code_idx', table_name='FGPN')
    op.alter_column(
        'PurchaseOrder',
        'current_version_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
