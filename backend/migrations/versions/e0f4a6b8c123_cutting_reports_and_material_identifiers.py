"""Retain cutting exports and support full material identifiers.

Revision ID: e0f4a6b8c123
Revises: d9e3f5a7b012
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e0f4a6b8c123'
down_revision = 'd9e3f5a7b012'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('StockUnit', 'CuttingConsumption'):
        op.alter_column(table, 'material_part_number', existing_type=sa.String(10), type_=sa.String(50), existing_nullable=False)
    op.create_table('CuttingReportImport',
        sa.Column('report_id', sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_sha256', sa.String(64), nullable=False, unique=True),
        sa.Column('source_content', sa.LargeBinary(), nullable=False),
        sa.Column('source_rows', sa.JSON(), nullable=False),
        sa.Column('imported_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('imported_at', sa.DateTime(), nullable=False),
        sa.Column('posted_launch_id', sa.Integer(), sa.ForeignKey('Launch.launch_id'), nullable=True),
        sa.Column('posted_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('posted_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_usage_unit', sa.String(10), nullable=True),
    )
    op.add_column('CuttingConsumption', sa.Column('source_report_id', sa.Integer(), nullable=True))
    op.add_column('CuttingConsumption', sa.Column('source_row_number', sa.Integer(), nullable=True))
    op.add_column('CuttingConsumption', sa.Column('source_event_fingerprint', sa.String(64), nullable=True))
    op.create_foreign_key('fk_cutting_consumption_report', 'CuttingConsumption', 'CuttingReportImport', ['source_report_id'], ['report_id'])
    op.create_unique_constraint('uq_cutting_consumption_source_event', 'CuttingConsumption', ['source_event_fingerprint'])


def downgrade():
    op.drop_constraint('uq_cutting_consumption_source_event', 'CuttingConsumption', type_='unique')
    op.drop_constraint('fk_cutting_consumption_report', 'CuttingConsumption', type_='foreignkey')
    for column in ('source_event_fingerprint', 'source_row_number', 'source_report_id'):
        op.drop_column('CuttingConsumption', column)
    op.drop_table('CuttingReportImport')
    for table in ('StockUnit', 'CuttingConsumption'):
        op.alter_column(table, 'material_part_number', existing_type=sa.String(50), type_=sa.String(10), existing_nullable=False)
