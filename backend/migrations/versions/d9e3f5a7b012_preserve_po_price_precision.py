"""Preserve all five decimals printed on Adient purchase orders.

Revision ID: d9e3f5a7b012
Revises: c8d2e4f6a901
"""
from alembic import op
import sqlalchemy as sa


revision = "d9e3f5a7b012"
down_revision = "c8d2e4f6a901"
branch_labels = None
depends_on = None

_PRICE_COLUMNS = (
    ("FGPN", "unit_price"),
    ("PurchaseOrderLine", "unit_price"),
    ("FGPNPriceHistory", "old_price"),
    ("FGPNPriceHistory", "new_price"),
)


def upgrade() -> None:
    for table, column in _PRICE_COLUMNS:
        op.alter_column(
            table, column,
            existing_type=sa.Numeric(10, 4),
            type_=sa.Numeric(14, 5),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Do not silently round imported prices or overflow the old precision.
    for table, column in _PRICE_COLUMNS:
        op.execute(sa.text(f'''
            DO $$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM "{table}"
                    WHERE "{column}" <> round("{column}", 4)
                       OR abs("{column}") >= 1000000
                ) THEN
                    RAISE EXCEPTION 'Cannot reduce {table}.{column} precision without losing data';
                END IF;
            END $$;
        '''))
        op.alter_column(
            table, column,
            existing_type=sa.Numeric(14, 5),
            type_=sa.Numeric(10, 4),
            existing_nullable=False,
        )
