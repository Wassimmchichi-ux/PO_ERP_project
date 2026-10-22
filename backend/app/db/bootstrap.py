"""Create an empty development schema or upgrade an existing versioned database.

Use --reset only for disposable development data. --seed-business-documents
loads the supplied document samples without inventing PO/BOM associations.
"""
import argparse
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Base, Contact, Customer, DeliveryMethod, FGPN, Material, Project, StockUnit, User
from app.policies import PolicyActor
from app.repositories import bom_repository
from app.schemas.parsed_purchase_order import ParsedPurchaseOrderImportRequest
from app.services import cutting_report_service, parsed_purchase_order_service
from app.utils.bom_workbook_extractor import parse_bom_workbook_many

BACKEND_DIR = Path(__file__).resolve().parents[2]


def initialize_schema(*, reset=False):
    if reset and settings.is_production:
        raise RuntimeError("Development reset is disabled in production.")
    engine = create_engine(settings.DATABASE_URL)
    if engine.dialect.name != "postgresql":
        raise RuntimeError("This bootstrap command targets PostgreSQL.")
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with engine.begin() as connection:
        if reset:
            connection.execute(text('DROP SCHEMA IF EXISTS public CASCADE'))
            connection.execute(text('CREATE SCHEMA public'))
        tables = set(inspect(connection).get_table_names())
        empty = not (tables - {"alembic_version"})
        if empty:
            # Legacy enums use create_type=False because historical installs
            # came from a SQL dump. Explicitly create them for fresh databases.
            seen = set()
            for table in Base.metadata.tables.values():
                for column in table.columns:
                    if isinstance(column.type, ENUM) and column.type.name not in seen:
                        column.type.create(connection, checkfirst=True)
                        seen.add(column.type.name)
            Base.metadata.create_all(connection)
        elif "alembic_version" not in tables:
            raise RuntimeError("Existing unversioned schema: select a known migration baseline or use --reset for disposable data.")
    if empty:
        command.stamp(config, "head")
    else:
        command.upgrade(config, "head")
    return engine


def seed_documents(engine, source_dir: Path):
    if settings.is_production:
        raise RuntimeError("Business-test seeding is disabled in production.")
    required = ["Adient PO 2301480082.pdf", "Adient PO 2301478532.PDF", "Adient PO 2301438886.pdf",
                "MBOM 07_08_2026-02-Test.xlsx", "cutting_report-test .xlsx"]
    for filename in required:
        if not (source_dir / filename).is_file():
            raise RuntimeError(f"Missing source document: {filename}")
    with Session(engine, expire_on_commit=False) as db:
        if db.scalar(select(Project).where(Project.project_code == "BUSINESS-TEST")):
            raise RuntimeError("Business-test seed already exists. Use --reset when deliberately replacing the disposable test dataset.")
        now = datetime.now()
        engineer = User(id=uuid.uuid4(), full_name="Business Test Engineer", registration_number="DOC-ENGINEER",
            role="LAUNCH_ENGINEER", password_hash="development-placeholder", status="ACTIVE", created_at=now)
        db.add(engineer)
        db.flush()
        actor = PolicyActor(user_id=engineer.id, role=engineer.role)
        project = Project(project_code="BUSINESS-TEST", name="Adient supplied document tests", launch_engineer_user_id=engineer.id,
            status="Active", created_at=now, updated_at=now)
        customer = Customer(customer_code="ADIENT-TEST", name="Adient document test customer", status="Active", created_at=now, updated_at=now)
        delivery = DeliveryMethod(name="Document test delivery", status="Active")
        db.add_all([project, customer, delivery])
        db.flush()
        contact = Contact(customer_id=customer.customer_id, name="Document test contact", status="Active", created_at=now, updated_at=now)
        db.add(contact)
        db.commit()
        imported = []
        for filename in required[:3]:
            source = source_dir / filename
            draft = parsed_purchase_order_service.parse_purchase_order_bytes(db, source_file_name=filename,
                content=source.read_bytes(), user_id=engineer.id, actor=actor)
            result = parsed_purchase_order_service.import_parsed_purchase_order(db, draft.parsed_po_id,
                ParsedPurchaseOrderImportRequest(project_id=project.project_id, customer_id=customer.customer_id,
                    contact_id=contact.contact_id, delivery_method_id=delivery.delivery_method_id), engineer.id, actor=actor)
            imported.append({"file": filename, "po_id": result.po_id, "lines": result.line_count})
        workbook = source_dir / required[3]
        boms = parse_bom_workbook_many(workbook.read_bytes(), source_filename=workbook.name)
        for parsed in boms:
            # The supplied BOM codes do not match these PO codes. Create
            # distinct master records, with no fabricated customer-order link.
            fgpn = FGPN(project_id=project.project_id, fgpn_code=parsed.finished_good_part_number,
                description=parsed.finished_good_description or parsed.finished_good_part_number,
                unit_price=Decimal("0"), status="Active", created_at=now, updated_at=now)
            db.add(fgpn)
            db.flush()
            bom_repository.save_bom_version(db, parsed_bom=parsed, fgpn=fgpn, version=1, source_filename=workbook.name, commit=False)
        db.commit()
        # Explicit development quantities, not quantities claimed by the source
        # workbooks. They exercise current/future stock and ETA editing.
        for material in db.scalars(select(Material)).all():
            for status, quantity in [("PRODUCTION", "20"), ("WAREHOUSE", "100"), ("IN_TRANSIT", "50")]:
                db.add(StockUnit(material_part_number=material.material_part_number, status=status,
                    quantity=Decimal(quantity), created_at=now, user_id=engineer.id,
                    expected_arrival_date=now + timedelta(days=7) if status == "IN_TRANSIT" else None))
        db.commit()
        cutting = cutting_report_service.import_report(db, (source_dir / required[4]).read_bytes(), required[4], engineer.id, actor=actor)
        print({"purchase_orders": imported, "bom_codes": [bom.finished_good_part_number for bom in boms],
            "cutting_report_id": cutting.report_id, "cutting_rows": len(cutting.lines), "test_stock_per_bom_material": "production 20 / warehouse 100 / transit 50",
            "unresolved": "PO-to-BOM and cutting-material mappings require confirmation; cutting usage remains staged."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Drop and recreate the disposable development schema")
    parser.add_argument("--seed-business-documents", action="store_true")
    parser.add_argument("--business-test-dir", type=Path, default=BACKEND_DIR.parent / "ressources" / "business-test")
    args = parser.parse_args()
    engine = initialize_schema(reset=args.reset)
    try:
        if args.seed_business_documents:
            seed_documents(engine, args.business_test_dir)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
