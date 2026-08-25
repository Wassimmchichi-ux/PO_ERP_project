"""Add stock unit split and production handover fields

Revision ID: 1c4b0dbabc9f
Revises: 94f3a91bd2c8
Create Date: 2026-08-24 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1c4b0dbabc9f'
down_revision: Union[str, None] = '94f3a91bd2c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('StockUnit', sa.Column('parent_stock_unit_id', sa.Integer(), nullable=True))
    op.add_column('StockUnit', sa.Column('handover_document_id', sa.Integer(), nullable=True))
    op.add_column('StockUnit', sa.Column('issued_to_production_at', sa.DateTime(), nullable=True))
    op.add_column('StockUnit', sa.Column('received_by_production_at', sa.DateTime(), nullable=True))
    op.create_foreign_key(
        'StockUnit_parent_stock_unit_id_fkey',
        'StockUnit',
        'StockUnit',
        ['parent_stock_unit_id'],
        ['stock_unit_id'],
        deferrable=True,
        initially='IMMEDIATE',
    )
    op.create_foreign_key(
        'StockUnit_handover_document_id_fkey',
        'StockUnit',
        'Document',
        ['handover_document_id'],
        ['document_id'],
        deferrable=True,
        initially='IMMEDIATE',
    )


def downgrade() -> None:
    op.drop_constraint('StockUnit_handover_document_id_fkey', 'StockUnit', type_='foreignkey')
    op.drop_constraint('StockUnit_parent_stock_unit_id_fkey', 'StockUnit', type_='foreignkey')
    op.drop_column('StockUnit', 'received_by_production_at')
    op.drop_column('StockUnit', 'issued_to_production_at')
    op.drop_column('StockUnit', 'handover_document_id')
    op.drop_column('StockUnit', 'parent_stock_unit_id')
