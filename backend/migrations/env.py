"""Alembic migration environment.

Injects the application's own DATABASE_URL and declarative Base
metadata into Alembic, rather than duplicating connection config in
alembic.ini. As models are added under app/models/, they must be
imported here (or in a central app/models/__init__.py that this
imports) so ``alembic revision --autogenerate`` can see them.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base

# --- Import all model modules here so Base.metadata is fully populated
# --- before autogenerate runs.
from app.models.audit_log import AuditLog
from app.models.bom import BOM
from app.models.bom_line import BOMLine
from app.models.contact import Contact
from app.models.correction_event import CorrectionEvent
from app.models.customer import Customer
from app.models.cutting_consumption import CuttingConsumption
from app.models.delivery_method import DeliveryMethod
from app.models.document import Document
from app.models.fgpn import FGPN
from app.models.fgpn_price_history import FGPNPriceHistory
from app.models.launch import Launch
from app.models.launch_fgpn import LaunchFGPN
from app.models.launch_po import LaunchPO
from app.models.launch_verification import LaunchVerification
from app.models.login_event import LoginEvent
from app.models.manufacturing_receiver import ManufacturingReceiver
from app.models.material import Material
from app.models.material_type import MaterialType
from app.models.po_status_history import POStatusHistory
from app.models.project import Project
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_line import PurchaseOrderLine
from app.models.purchase_order_version import PurchaseOrderVersion
from app.models.purchase_order_version_change import PurchaseOrderVersionChange
from app.models.simulation import Simulation
from app.models.stock_allocation import StockAllocation
from app.models.stock_issue_handover import StockIssueHandover
from app.models.stock_unit import StockUnit
from app.models.user import User

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL only)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
