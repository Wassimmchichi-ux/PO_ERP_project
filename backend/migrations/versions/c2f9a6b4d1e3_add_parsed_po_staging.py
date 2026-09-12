"""Add parsed PO staging tables

Revision ID: c2f9a6b4d1e3
Revises: b6d4f7a9c8e2
Create Date: 2026-08-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c2f9a6b4d1e3'
down_revision: Union[str, None] = 'b6d4f7a9c8e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.create_table(
        'ParsedPurchaseOrder',
        sa.Column('parsed_po_id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('source_file_name', sa.String(length=255), nullable=True),
        sa.Column('parser_name', sa.String(length=100), nullable=True),
        sa.Column('parser_version', sa.String(length=50), nullable=True),
        sa.Column(
            'status',
            sa.String(length=30),
            server_default='PARSED',
            nullable=False,
            comment='PARSED, CORRECTED, VALIDATED, IMPORTED, REJECTED',
        ),
        sa.Column('parsed_payload', json_type, nullable=False),
        sa.Column('validated_po_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], deferrable=True, initially='IMMEDIATE'),
        sa.ForeignKeyConstraint(['document_id'], ['Document.document_id'], deferrable=True, initially='IMMEDIATE'),
        sa.ForeignKeyConstraint(['validated_po_id'], ['PurchaseOrder.po_id'], deferrable=True, initially='IMMEDIATE'),
        sa.PrimaryKeyConstraint('parsed_po_id'),
    )
    op.create_table(
        'ParsedPurchaseOrderCorrection',
        sa.Column('correction_id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('parsed_po_id', sa.Integer(), nullable=False),
        sa.Column(
            'field_path',
            sa.String(length=255),
            nullable=False,
            comment='Header field or nested path like lines[0].quantity',
        ),
        sa.Column('original_value', json_type, nullable=True),
        sa.Column('corrected_value', json_type, nullable=True),
        sa.Column('confirmed', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('corrected_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('corrected_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['corrected_by'], ['users.id'], deferrable=True, initially='IMMEDIATE'),
        sa.ForeignKeyConstraint(['parsed_po_id'], ['ParsedPurchaseOrder.parsed_po_id'], deferrable=True, initially='IMMEDIATE'),
        sa.PrimaryKeyConstraint('correction_id'),
    )
    op.create_index(
        'ParsedPurchaseOrderCorrection_parsed_po_id_field_path_idx',
        'ParsedPurchaseOrderCorrection',
        ['parsed_po_id', 'field_path'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        'ParsedPurchaseOrderCorrection_parsed_po_id_field_path_idx',
        table_name='ParsedPurchaseOrderCorrection',
    )
    op.drop_table('ParsedPurchaseOrderCorrection')
    op.drop_table('ParsedPurchaseOrder')
