"""Add simulation stock owner scope

Revision ID: e4a1b2c3d4f5
Revises: d9e8a7c6b5f4
Create Date: 2026-08-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e4a1b2c3d4f5'
down_revision: Union[str, None] = 'd9e8a7c6b5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'Simulation',
        sa.Column(
            'stock_scope_mode',
            sa.String(length=30),
            server_default='ALL',
            nullable=False,
            comment='ALL, OWNED_ONLY',
        ),
    )
    op.add_column(
        'Simulation',
        sa.Column('stock_owner_user_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'Simulation_stock_owner_user_id_fkey',
        'Simulation',
        'users',
        ['stock_owner_user_id'],
        ['id'],
        deferrable=True,
        initially='IMMEDIATE',
    )
    op.alter_column(
        'StockUnit',
        'user_id',
        existing_type=postgresql.UUID(as_uuid=True),
        comment='Optional affected launch engineer/manager. NULL means global enterprise stock.',
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'StockUnit',
        'user_id',
        existing_type=postgresql.UUID(as_uuid=True),
        comment='it is an open point: a Launch engineer that recall for material is it owned by him or it is owned by every other launch engineer',
        existing_nullable=True,
    )
    op.drop_constraint('Simulation_stock_owner_user_id_fkey', 'Simulation', type_='foreignkey')
    op.drop_column('Simulation', 'stock_owner_user_id')
    op.drop_column('Simulation', 'stock_scope_mode')
