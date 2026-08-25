"""Database-backed tests for simulation and stock services."""
from __future__ import annotations

import uuid
import zipfile
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (
    Contact,
    Customer,
    DeliveryMethod,
    Document,
    FGPN,
    Launch,
    Project,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderVersion,
    StockUnit,
    User,
)
from app.models.cutting_consumption import CuttingConsumption
from app.models.simulation import Simulation
from app.models.stock_allocation import StockAllocation
from app.repositories import bom_repository
from app.schemas.simulation import (
    FgpnSimulationRequest,
    SimulationPreviewRequest,
    SimulationSaveRequest,
)
from app.services import material_simulation_service, stock_management_service
from app.utils import bom_workbook_extractor as bom_xlsx
from app.utils.bom_workbook_extractor import ParsedBom


MBOM_PATH = Path(__file__).resolve().parents[2] / "MBOM_08_08_2025-02.xlsx"
FGPN_CODES = ["6855872-7S08-000", "6855872-9K21-000"]
TEST_USER_ID = uuid.UUID("aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa")


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def seeded_db(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> dict[str, int | uuid.UUID]:
    now = datetime(2026, 8, 24, 9, 0, 0)
    user = User(
        id=TEST_USER_ID,
        full_name="System User",
        registration_number="SYSTEM",
        password_hash="test",
        role="ADMIN",
        status="ACTIVE",
        failed_login_count=0,
        is_locked=False,
        must_change_password=False,
        created_at=now,
    )
    db_session.add(user)

    project = Project(
        project_id=1,
        project_code="P-2261",
        name="Covers B-SUV Seat Trim",
        launch_engineer_user_id=TEST_USER_ID,
        status="Active",
        created_at=now,
        updated_at=now,
    )
    customer = Customer(
        customer_id=1,
        customer_code="AREA",
        name="Aurea Automotive",
        status="Active",
        created_at=now,
        updated_at=now,
    )
    contact = Contact(
        contact_id=1,
        customer_id=1,
        name="Launch Contact",
        status="Active",
        created_at=now,
        updated_at=now,
    )
    delivery_method = DeliveryMethod(delivery_method_id=1, name="Truck", status="Active")
    db_session.add_all([project, customer, contact, delivery_method])

    for fgpn_id, fgpn_code in enumerate(FGPN_CODES, start=1):
        db_session.add(
            FGPN(
                fgpn_id=fgpn_id,
                project_id=1,
                fgpn_code=fgpn_code,
                description=f"FGPN {fgpn_code}",
                unit_price=Decimal("0"),
                status="Active",
                created_at=now,
                updated_at=now,
            )
        )
    db_session.commit()
    monkeypatch.setattr(bom_repository, "_get_system_user", lambda db: TEST_USER_ID)

    for fgpn_code in FGPN_CODES:
        parsed = _parsed_mbom_for_fgpn(fgpn_code)
        fgpn = bom_repository.find_fgpn_by_code(db_session, fgpn_code)
        bom_repository.save_bom_version(
            db_session,
            parsed_bom=parsed,
            fgpn=fgpn,
            version=1,
            source_filename=f"MBOM_{fgpn_code}.xlsx",
        )

    po_document = Document(
        document_id=100,
        document_type="PO",
        file_name="po.pdf",
        file_path="/tmp/po.pdf",
        uploaded_at=now,
        uploaded_by=TEST_USER_ID,
        version=1,
    )
    meeting_document = Document(
        document_id=101,
        document_type="MTG_MINUTES",
        file_name="meeting-draft.pdf",
        file_path="/tmp/meeting-draft.pdf",
        uploaded_at=now,
        uploaded_by=TEST_USER_ID,
        version=1,
    )
    db_session.add_all([po_document, meeting_document])

    for index, fgpn_code in enumerate(FGPN_CODES, start=1):
        po_id = index
        version_id = index
        line_id = index
        db_session.add(
            PurchaseOrder(
                po_id=po_id,
                po_number=f"PO-8821{index}",
                customer_id=1,
                contact_id=1,
                current_version_id=version_id,
                current_status="Unplanned",
                created_at=now,
                updated_at=now,
            )
        )
        db_session.add(
            PurchaseOrderVersion(
                po_version_id=version_id,
                po_id=po_id,
                version_number=1,
                document_id=100,
                created_at=now,
                created_by=TEST_USER_ID,
            )
        )
        db_session.add(
            PurchaseOrderLine(
                po_line_id=line_id,
                po_version_id=version_id,
                line_number=1,
                fgpn_id=index,
                ordered_quantity=Decimal("100"),
                unit_price=Decimal("0"),
                delivery_method_id=1,
                created_at=now,
            )
        )
    db_session.commit()

    return {"user_id": TEST_USER_ID, "meeting_document_id": 101}


def test_preview_simulation_feasible_with_mbom_bom_and_stock_units(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
) -> None:
    parsed = _parsed_mbom_for_fgpn(FGPN_CODES[0])
    _insert_stock_for_requirements(
        db_session,
        _requirements_for(parsed, Decimal("10")),
        quantity_factor=Decimal("1.1"),
    )

    result = material_simulation_service.preview_simulation(
        db_session,
        SimulationPreviewRequest(
            fgpns=[
                FgpnSimulationRequest(po_id=1, fgpn_id=1, requested_quantity=Decimal("10")),
            ],
            allocation_strategy="PRIORITY",
            include_in_transit=False,
            safety_coefficient=Decimal("1"),
        ),
    )

    assert result.is_feasible is True
    assert result.total_launchable_quantity == Decimal("10")
    assert result.fgpn_summaries[0].po_number == "PO-88211"
    assert result.material_summaries
    assert any(detail.is_whole_issue for detail in result.allocation_details)


def test_preview_simulation_shortfall_with_mbom_bom_and_partial_stock(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
) -> None:
    parsed = _parsed_mbom_for_fgpn(FGPN_CODES[1])
    requirements = _requirements_for(parsed, Decimal("20"))
    first_material = next(iter(requirements))
    _insert_stock_for_requirements(
        db_session,
        {first_material: requirements[first_material]},
        quantity_factor=Decimal("1"),
    )

    result = material_simulation_service.preview_simulation(
        db_session,
        SimulationPreviewRequest(
            fgpns=[
                FgpnSimulationRequest(po_id=2, fgpn_id=2, requested_quantity=Decimal("20")),
            ],
            allocation_strategy="PRIORITY",
            include_in_transit=False,
            safety_coefficient=Decimal("1"),
        ),
    )

    assert result.is_feasible is False
    assert result.total_launchable_quantity < Decimal("20")
    assert any(summary.shortfall > 0 for summary in result.material_summaries)
    assert result.suggestion is not None


def test_stock_management_service_uses_remaining_wip_and_in_transit(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
) -> None:
    parsed = _parsed_mbom_for_fgpn(FGPN_CODES[0])
    material_part_number = next(iter(_requirements_for(parsed, Decimal("1"))))
    now = datetime(2026, 8, 24, 9, 0, 0)
    db_session.add_all(
        [
            StockUnit(
                stock_unit_id=9001,
                material_part_number=material_part_number,
                quantity=Decimal("100"),
                status="PRODUCTION",
                created_at=now,
            ),
            StockUnit(
                stock_unit_id=9002,
                material_part_number=material_part_number,
                quantity=Decimal("25"),
                status="IN_TRANSIT",
                expected_arrival_date=now,
                created_at=now,
            ),
            CuttingConsumption(
                consumption_id=1,
                launch_id=999,
                material_part_number=material_part_number,
                quantity_consumed=Decimal("30"),
                cutman_document_id=101,
                consumed_at=now,
            ),
        ]
    )
    db_session.commit()

    detail = stock_management_service.get_material_stock_detail(db_session, material_part_number)
    summary_by_material = {
        item.material_part_number: item
        for item in stock_management_service.get_stock_summary(db_session)
    }

    assert detail.production == Decimal("70.0000")
    assert detail.in_transit == Decimal("25.0000")
    assert summary_by_material[material_part_number].production_quantity == Decimal("70.0000")
    assert summary_by_material[material_part_number].in_transit_quantity == Decimal("25.0000")


def test_save_simulation_does_not_create_launch_until_meeting_approval(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
) -> None:
    parsed = _parsed_mbom_for_fgpn(FGPN_CODES[0])
    _insert_stock_for_requirements(
        db_session,
        _requirements_for(parsed, Decimal("5")),
        quantity_factor=Decimal("1.2"),
    )

    response = material_simulation_service.save_simulation(
        db_session,
        SimulationSaveRequest(
            launch_id=555,
            target_date=date(2026, 8, 25),
            mtg_minutes_document_id=seeded_db["meeting_document_id"],
            preview_request=SimulationPreviewRequest(
                launch_id=555,
                fgpns=[
                    FgpnSimulationRequest(po_id=1, fgpn_id=1, requested_quantity=Decimal("5")),
                ],
                allocation_strategy="PRIORITY",
                include_in_transit=False,
                safety_coefficient=Decimal("1"),
            ),
        ),
        user_id=str(seeded_db["user_id"]),
    )

    assert response.simulation_id is not None
    assert db_session.execute(select(func.count(Simulation.simulation_id))).scalar_one() == 1
    assert db_session.execute(select(func.count(Launch.launch_id))).scalar_one() == 0


def test_launch_saved_simulation_splits_component_stock_and_handover_moves_to_production(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
) -> None:
    parsed = _parsed_mbom_for_fgpn(FGPN_CODES[0])
    _insert_stock_for_requirements(
        db_session,
        _requirements_for(parsed, Decimal("5")),
        quantity_factor=Decimal("1.2"),
    )
    response = material_simulation_service.save_simulation(
        db_session,
        SimulationSaveRequest(
            launch_id=556,
            target_date=date(2026, 8, 25),
            mtg_minutes_document_id=seeded_db["meeting_document_id"],
            preview_request=SimulationPreviewRequest(
                launch_id=556,
                fgpns=[
                    FgpnSimulationRequest(po_id=1, fgpn_id=1, requested_quantity=Decimal("5")),
                ],
                allocation_strategy="PRIORITY",
                include_in_transit=False,
                safety_coefficient=Decimal("1"),
            ),
        ),
        user_id=str(seeded_db["user_id"]),
    )

    launch_response = material_simulation_service.launch_saved_simulation(
        db_session,
        response.simulation_id,
    )

    issued_children = db_session.execute(
        select(StockUnit).where(StockUnit.parent_stock_unit_id.is_not(None))
    ).scalars().all()
    launch_allocations = db_session.execute(
        select(StockAllocation)
        .where(StockAllocation.simulation_id == response.simulation_id)
        .where(StockAllocation.allocation_type == "LAUNCH")
    ).scalars().all()

    assert launch_response.status == "LAUNCHED"
    assert issued_children
    assert all(child.status == "ISSUED_TO_PRODUCTION" for child in issued_children)
    assert any(parent.quantity > 0 for parent in (child.parent_stock_unit for child in issued_children))
    assert {allocation.stock_unit_id for allocation in launch_allocations}.issuperset(
        {child.stock_unit_id for child in issued_children}
    )

    signed_handover = Document(
        document_id=102,
        document_type="SIGNED_HANDOVER",
        file_name="signed-handover.pdf",
        file_path="/tmp/signed-handover.pdf",
        uploaded_at=datetime(2026, 8, 24, 10, 0, 0),
        uploaded_by=TEST_USER_ID,
        version=1,
    )
    db_session.add(signed_handover)
    db_session.commit()

    child_to_handover = issued_children[0]
    stock_management_service.confirm_production_handover(
        db_session,
        child_to_handover.stock_unit_id,
        handover_document_id=102,
    )

    db_session.refresh(child_to_handover)
    assert child_to_handover.status == "PRODUCTION"
    assert child_to_handover.handover_document_id == 102
    assert child_to_handover.received_by_production_at is not None


def _parsed_mbom_for_fgpn(fgpn_code: str) -> ParsedBom:
    with zipfile.ZipFile(BytesIO(MBOM_PATH.read_bytes())) as workbook:
        shared_strings = bom_xlsx._read_shared_strings(workbook)
        sheet_path = bom_xlsx._find_sheet_path(workbook, bom_xlsx._SOURCE_SHEET_NAME)
        rows = bom_xlsx._read_sheet_rows(workbook, sheet_path, shared_strings)

    header_row_number, header_map = bom_xlsx._find_header_row(rows)
    lines = bom_xlsx._extract_material_lines(rows, header_row_number, header_map, fgpn_code)
    assert lines, f"Expected MBOM lines for {fgpn_code}"

    first_raw_row = lines[0].raw_row
    return ParsedBom(
        finished_good_part_number=fgpn_code,
        finished_good_description=first_raw_row.get("Cover description"),
        source_filename=MBOM_PATH.name,
        source_reported_by=bom_xlsx._clean_optional(bom_xlsx._cell_value(rows, 2, 3)),
        source_report_date=bom_xlsx._parse_report_date(rows),
        source_report_time=bom_xlsx._parse_report_time(rows),
        lines=lines,
    )


def _requirements_for(parsed_bom: ParsedBom, quantity: Decimal) -> dict[str, Decimal]:
    requirements: dict[str, Decimal] = {}
    for line in parsed_bom.lines:
        if line.part_type == "M":
            base_quantity = line.total_sqm or Decimal("0")
        elif line.part_type == "S":
            base_quantity = line.total_quantity or Decimal("0")
        else:
            base_quantity = line.total_quantity or Decimal("0")
        if base_quantity <= 0:
            continue
        requirements[line.material_part_number] = (
            requirements.get(line.material_part_number, Decimal("0"))
            + base_quantity * quantity
        )
    return requirements


def _insert_stock_for_requirements(
    db_session: Session,
    requirements: dict[str, Decimal],
    *,
    quantity_factor: Decimal,
) -> None:
    now = datetime(2026, 8, 24, 9, 0, 0)
    for index, (material_part_number, requirement) in enumerate(requirements.items(), start=1):
        db_session.add(
            StockUnit(
                stock_unit_id=index,
                material_part_number=material_part_number,
                quantity=(requirement * quantity_factor).quantize(Decimal("0.0001")),
                status="WAREHOUSE",
                created_at=now,
            )
        )
    db_session.commit()
