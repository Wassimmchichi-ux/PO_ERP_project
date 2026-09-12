"""Add project and customer delivery attributes

Revision ID: 9a8b7c6d5e4f
Revises: 0f1e2d3c4b5a
Create Date: 2026-09-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a8b7c6d5e4f"
down_revision: Union[str, None] = "0f1e2d3c4b5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("Project", sa.Column("jit_customer", sa.String(length=150), nullable=True))
    op.add_column("Project", sa.Column("oem_customer", sa.String(length=150), nullable=True))
    op.add_column("Project", sa.Column("contact_name", sa.String(length=150), nullable=True))
    op.add_column("Project", sa.Column("contact_email", sa.String(length=150), nullable=True))
    op.add_column("Project", sa.Column("contact_phone", sa.String(length=50), nullable=True))
    op.add_column("Project", sa.Column("car_model", sa.String(length=100), nullable=True))
    op.add_column("Project", sa.Column("deactivated_at", sa.DateTime(), nullable=True))
    op.add_column("Project", sa.Column("deactivation_document_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "Project_deactivation_document_id_fkey",
        "Project",
        "Document",
        ["deactivation_document_id"],
        ["document_id"],
        deferrable=True,
        initially="IMMEDIATE",
    )

    op.add_column("Launch", sa.Column("cmr_document_id", sa.Integer(), nullable=True))
    op.add_column("Launch", sa.Column("customer_delivered_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "Launch_cmr_document_id_fkey",
        "Launch",
        "Document",
        ["cmr_document_id"],
        ["document_id"],
        deferrable=True,
        initially="IMMEDIATE",
    )

    op.add_column(
        "LaunchFGPN",
        sa.Column("delivered_quantity", sa.Numeric(10, 4), server_default="0", nullable=False),
    )
    op.add_column("LaunchFGPN", sa.Column("last_customer_delivery_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("LaunchFGPN", "last_customer_delivery_at")
    op.drop_column("LaunchFGPN", "delivered_quantity")
    op.drop_constraint("Launch_cmr_document_id_fkey", "Launch", type_="foreignkey")
    op.drop_column("Launch", "customer_delivered_at")
    op.drop_column("Launch", "cmr_document_id")
    op.drop_constraint("Project_deactivation_document_id_fkey", "Project", type_="foreignkey")
    op.drop_column("Project", "deactivation_document_id")
    op.drop_column("Project", "deactivated_at")
    op.drop_column("Project", "car_model")
    op.drop_column("Project", "contact_phone")
    op.drop_column("Project", "contact_email")
    op.drop_column("Project", "contact_name")
    op.drop_column("Project", "oem_customer")
    op.drop_column("Project", "jit_customer")
