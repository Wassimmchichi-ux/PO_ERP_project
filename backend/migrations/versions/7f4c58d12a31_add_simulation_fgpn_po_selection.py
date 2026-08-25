"""Add selected PO FGPN rows to Simulation

Revision ID: 7f4c58d12a31
Revises: 2edd97502fc4
Create Date: 2026-08-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7f4c58d12a31'
down_revision: Union[str, None] = '2edd97502fc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'SimulationFGPN',
        sa.Column('simulation_fgpn_id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('simulation_id', sa.Integer(), nullable=False),
        sa.Column('po_id', sa.Integer(), nullable=False),
        sa.Column('fgpn_id', sa.Integer(), nullable=False),
        sa.Column('po_line_id', sa.Integer(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('po_quantity', sa.Numeric(10, 4), nullable=False),
        sa.Column('simulation_quantity', sa.Numeric(10, 4), nullable=False),
        sa.Column('launchable_quantity', sa.Numeric(10, 4), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['fgpn_id'], ['FGPN.fgpn_id'], deferrable=True, initially='IMMEDIATE'),
        sa.ForeignKeyConstraint(['po_id'], ['PurchaseOrder.po_id'], deferrable=True, initially='IMMEDIATE'),
        sa.ForeignKeyConstraint(['po_line_id'], ['PurchaseOrderLine.po_line_id'], deferrable=True, initially='IMMEDIATE'),
        sa.ForeignKeyConstraint(['simulation_id'], ['Simulation.simulation_id'], deferrable=True, initially='IMMEDIATE'),
        sa.PrimaryKeyConstraint('simulation_fgpn_id'),
    )
    op.create_index(
        'SimulationFGPN_simulation_po_fgpn_idx',
        'SimulationFGPN',
        ['simulation_id', 'po_id', 'fgpn_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('SimulationFGPN_simulation_po_fgpn_idx', table_name='SimulationFGPN')
    op.drop_table('SimulationFGPN')
