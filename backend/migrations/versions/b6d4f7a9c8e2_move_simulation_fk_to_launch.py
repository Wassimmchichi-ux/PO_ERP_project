"""Move simulation-launch FK onto Launch

Revision ID: b6d4f7a9c8e2
Revises: 1c4b0dbabc9f
Create Date: 2026-08-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b6d4f7a9c8e2'
down_revision: Union[str, None] = '1c4b0dbabc9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('Launch', sa.Column('simulation_id', sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE "Launch" AS launch
        SET simulation_id = simulation.simulation_id
        FROM "Simulation" AS simulation
        WHERE launch.launch_id = simulation.launch_id
        """
    )
    op.alter_column('Launch', 'simulation_id', existing_type=sa.Integer(), nullable=False)
    op.drop_constraint('Launch_launch_id_fkey', 'Launch', type_='foreignkey')
    op.create_unique_constraint('Launch_simulation_id_key', 'Launch', ['simulation_id'])
    op.create_foreign_key(
        'Launch_simulation_id_fkey',
        'Launch',
        'Simulation',
        ['simulation_id'],
        ['simulation_id'],
        deferrable=True,
        initially='IMMEDIATE',
    )
    op.drop_constraint('Simulation_launch_id_key', 'Simulation', type_='unique')
    op.drop_column('Simulation', 'launch_id')


def downgrade() -> None:
    op.add_column('Simulation', sa.Column('launch_id', sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE "Simulation" AS simulation
        SET launch_id = launch.launch_id
        FROM "Launch" AS launch
        WHERE launch.simulation_id = simulation.simulation_id
        """
    )
    op.alter_column('Simulation', 'launch_id', existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint('Simulation_launch_id_key', 'Simulation', ['launch_id'])
    op.drop_constraint('Launch_simulation_id_fkey', 'Launch', type_='foreignkey')
    op.drop_constraint('Launch_simulation_id_key', 'Launch', type_='unique')
    op.create_foreign_key(
        'Launch_launch_id_fkey',
        'Launch',
        'Simulation',
        ['launch_id'],
        ['launch_id'],
        deferrable=True,
        initially='IMMEDIATE',
    )
    op.drop_column('Launch', 'simulation_id')
