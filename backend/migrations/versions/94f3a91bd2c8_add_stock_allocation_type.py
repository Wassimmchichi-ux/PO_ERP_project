"""Add allocation type to StockAllocation

Revision ID: 94f3a91bd2c8
Revises: 7f4c58d12a31
Create Date: 2026-08-24 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '94f3a91bd2c8'
down_revision: Union[str, None] = '7f4c58d12a31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'StockAllocation',
        sa.Column(
            'allocation_type',
            sa.String(length=20),
            server_default='SIMULATION',
            nullable=False,
            comment='SIMULATION, LAUNCH',
        ),
    )
    op.add_column(
        'StockAllocation',
        sa.Column('is_whole_issue', sa.Boolean(), server_default='false', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('StockAllocation', 'is_whole_issue')
    op.drop_column('StockAllocation', 'allocation_type')
