"""Backfill a baseline ledger row for pre-existing stock units.

Revision ID: e9a1c4f6b802
Revises: d8f0b3e5a709
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa


revision = "e9a1c4f6b802"
down_revision = "d8f0b3e5a709"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text('''
        INSERT INTO "StockMovement" (
            stock_unit_id,
            supplier_order_id,
            material_part_number,
            movement_type,
            quantity_change,
            warehouse_quantity_after,
            from_status,
            to_status,
            stock_unit_reference,
            source_reference,
            actor_user_id,
            occurred_at,
            reason,
            note
        )
        SELECT
            stock.stock_unit_id,
            supplier_line.supplier_order_id,
            stock.material_part_number,
            CASE stock.status
                WHEN 'WAREHOUSE' THEN 'WAREHOUSE_BASELINE'
                WHEN 'IN_TRANSIT' THEN 'TRANSIT_BASELINE'
                WHEN 'PRODUCTION' THEN 'PRODUCTION_BASELINE'
                ELSE 'ISSUED_BASELINE'
            END,
            stock.quantity,
            (
                SELECT COALESCE(SUM(warehouse.quantity), 0)
                FROM "StockUnit" AS warehouse
                WHERE warehouse.material_part_number = stock.material_part_number
                  AND warehouse.status = 'WAREHOUSE'
            ),
            NULL,
            stock.status,
            stock.business_unit_id,
            supplier_order.supplier_reference,
            actor.id,
            stock.created_at,
            NULL,
            'Baseline generated for stock that existed before the movement ledger.'
        FROM "StockUnit" AS stock
        CROSS JOIN (
            SELECT id FROM users ORDER BY created_at, id LIMIT 1
        ) AS actor
        LEFT JOIN "SupplierMaterialOrderLine" AS supplier_line
          ON supplier_line.stock_unit_id = stock.stock_unit_id
        LEFT JOIN "SupplierMaterialOrder" AS supplier_order
          ON supplier_order.supplier_order_id = supplier_line.supplier_order_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM "StockMovement" AS movement
            WHERE movement.stock_unit_id = stock.stock_unit_id
        )
    '''))


def downgrade() -> None:
    op.execute(sa.text('''
        DELETE FROM "StockMovement"
        WHERE note = 'Baseline generated for stock that existed before the movement ledger.'
    '''))
