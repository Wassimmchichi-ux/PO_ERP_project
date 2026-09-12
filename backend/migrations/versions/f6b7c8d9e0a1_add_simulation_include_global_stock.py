"""Add simulation include global stock flag

Revision ID: f6b7c8d9e0a1
Revises: e4a1b2c3d4f5
Create Date: 2026-08-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6b7c8d9e0a1'
down_revision: Union[str, None] = 'e4a1b2c3d4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'Simulation',
        sa.Column(
            'include_global_stock',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
            comment='When OWNED_ONLY, include global stock units with no affected owner.',
        ),
    )


def downgrade() -> None:
    op.drop_column('Simulation', 'include_global_stock')
