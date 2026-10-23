"""Align simulation and add supplier arrival protocol.

Revision ID: b4d8e1f3a607
Revises: f2a6c9d1e405
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b4d8e1f3a607"
down_revision: Union[str, None] = "f2a6c9d1e405"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("Simulation", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "Simulation_project_id_fkey",
        "Simulation", "Project", ["project_id"], ["project_id"],
        deferrable=True, initially="IMMEDIATE",
    )
    op.execute(sa.text('''
        UPDATE "Simulation" AS simulation
        SET project_id = source.project_id
        FROM (
            SELECT simulation_fgpn.simulation_id, MIN(fgpn.project_id) AS project_id
            FROM "SimulationFGPN" AS simulation_fgpn
            JOIN "FGPN" AS fgpn ON fgpn.fgpn_id = simulation_fgpn.fgpn_id
            GROUP BY simulation_fgpn.simulation_id
        ) AS source
        WHERE source.simulation_id = simulation.simulation_id
    '''))
    op.execute(sa.text('''
        UPDATE "Simulation"
        SET project_id = (SELECT MIN(project_id) FROM "Project")
        WHERE project_id IS NULL
    '''))
    op.alter_column("Simulation", "project_id", nullable=False)
    op.add_column(
        "Simulation",
        sa.Column("workflow_status", sa.String(30), server_default="READY", nullable=False),
    )
    op.add_column("Simulation", sa.Column("document_due_at", sa.DateTime(), nullable=True))
    op.add_column("Simulation", sa.Column("launched_at", sa.DateTime(), nullable=True))
    op.alter_column("Simulation", "mtg_minutes_document_id", nullable=True)
    op.drop_column("Simulation", "allocation_strategy")
    op.create_check_constraint(
        "Simulation_workflow_status_ck",
        "Simulation",
        "workflow_status IN ('AWAITING_DOCUMENT', 'READY', 'RELEASED', 'LAUNCHED')",
    )

    op.add_column("StockUnit", sa.Column("business_unit_id", sa.String(100), nullable=True))
    op.create_unique_constraint(
        "StockUnit_business_unit_id_key", "StockUnit", ["business_unit_id"]
    )
    op.add_column("CuttingConsumption", sa.Column("stock_unit_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "CuttingConsumption_stock_unit_id_fkey",
        "CuttingConsumption", "StockUnit", ["stock_unit_id"], ["stock_unit_id"],
        deferrable=True, initially="IMMEDIATE",
    )

    op.create_table(
        "SupplierMaterialOrder",
        sa.Column("supplier_order_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("supplier_name", sa.String(150), nullable=False),
        sa.Column("supplier_reference", sa.String(100), nullable=True),
        sa.Column("ordered_for_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), server_default="OPEN", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("discrepancy_reason", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["Project.project_id"], deferrable=True),
        sa.ForeignKeyConstraint(["ordered_for_user_id"], ["users.id"], deferrable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], deferrable=True),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], deferrable=True),
        sa.CheckConstraint(
            "status IN ('OPEN', 'ARRIVAL_ENTERED', 'CONFIRMED', 'CANCELLED')",
            name="SupplierMaterialOrder_status_ck",
        ),
    )
    op.create_table(
        "SupplierMaterialOrderLine",
        sa.Column("supplier_order_line_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("supplier_order_id", sa.Integer(), nullable=False),
        sa.Column("material_part_number", sa.String(50), nullable=False),
        sa.Column("stock_unit_kind", sa.String(20), nullable=False),
        sa.Column("business_unit_id", sa.String(100), nullable=False),
        sa.Column("expected_quantity", sa.Numeric(10, 4), nullable=False),
        sa.Column("expected_arrival_date", sa.Date(), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(10, 4), nullable=True),
        sa.Column("actual_business_unit_id", sa.String(100), nullable=True),
        sa.Column("arrival_entered_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("arrival_entered_at", sa.DateTime(), nullable=True),
        sa.Column("stock_unit_id", sa.Integer(), nullable=False, unique=True),
        sa.ForeignKeyConstraint(
            ["supplier_order_id"], ["SupplierMaterialOrder.supplier_order_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["material_part_number"], ["Material.material_part_number"], deferrable=True
        ),
        sa.ForeignKeyConstraint(["arrival_entered_by"], ["users.id"], deferrable=True),
        sa.ForeignKeyConstraint(["stock_unit_id"], ["StockUnit.stock_unit_id"], deferrable=True),
        sa.CheckConstraint(
            "stock_unit_kind IN ('ROLL', 'COMPONENT')",
            name="SupplierMaterialOrderLine_kind_ck",
        ),
    )
    op.create_table(
        "Notification",
        sa.Column("notification_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], deferrable=True),
    )
    op.create_index(
        "Notification_user_unread_idx",
        "Notification", ["user_id", "read_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("Notification_user_unread_idx", table_name="Notification")
    op.drop_table("Notification")
    op.drop_table("SupplierMaterialOrderLine")
    op.drop_table("SupplierMaterialOrder")
    op.drop_constraint("CuttingConsumption_stock_unit_id_fkey", "CuttingConsumption", type_="foreignkey")
    op.drop_column("CuttingConsumption", "stock_unit_id")
    op.drop_constraint("StockUnit_business_unit_id_key", "StockUnit", type_="unique")
    op.drop_column("StockUnit", "business_unit_id")

    op.drop_constraint("Simulation_workflow_status_ck", "Simulation", type_="check")
    op.add_column(
        "Simulation",
        sa.Column(
            "allocation_strategy", sa.String(30), server_default="PRIORITY_PLUS_MANUAL", nullable=False
        ),
    )
    op.alter_column("Simulation", "mtg_minutes_document_id", nullable=False)
    op.drop_column("Simulation", "launched_at")
    op.drop_column("Simulation", "document_due_at")
    op.drop_column("Simulation", "workflow_status")
    op.drop_constraint("Simulation_project_id_fkey", "Simulation", type_="foreignkey")
    op.drop_column("Simulation", "project_id")
