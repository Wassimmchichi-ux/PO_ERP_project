"""Add PO version FGPN line uniqueness

Revision ID: a7b8c9d0e1f2
Revises: f6b7c8d9e0a1
Create Date: 2026-08-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6b7c8d9e0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'PurchaseOrderLine_po_version_id_fgpn_id_idx',
        'PurchaseOrderLine',
        ['po_version_id', 'fgpn_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('PurchaseOrderLine_po_version_id_fgpn_id_idx', table_name='PurchaseOrderLine')
