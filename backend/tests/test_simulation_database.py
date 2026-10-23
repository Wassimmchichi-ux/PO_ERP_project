"""Database-backed tests for simulation and stock services."""
from __future__ import annotations

import uuid
import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (
    BOM,
    BOMLine,
    Contact,
    Customer,
    DeliveryMethod,
    Document,
    FGPN,
    Launch,
    ManufacturingReceiver,
    Material,
    MaterialType,
    Project,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderVersion,
    StockUnit,
    Supplier,
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
from app.schemas.stock import StockUnitReceptionRequest
from app.services import bom_extraction_service, material_simulation_service, stock_management_service
from app.exceptions.base import ConflictException, ValidationException
from app.utils.bom_workbook_extractor import ParsedBom, parse_bom_workbook_many


MBOM_PATH = Path(__file__).resolve().parents[2] / "ressources" / "business-test" / "MBOM 07_08_2026-02-Test.xlsx"
FGPN_CODES = ["6134635-AD40-000", "6134635-AT43-000"]
TEST_USER_ID = uuid.UUID("aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa")
LAUNCH_ENGINEER_ID = uuid.UUID("bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb")


@pytest.fixture()
def business_workbook_upload():
    with SpooledTemporaryFile(max_size=1024 * 1024) as workbook:
        workbook.write(MBOM_PATH.read_bytes())
        workbook.seek(0)
        yield UploadFile(filename=MBOM_PATH.name, file=workbook)


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
    launch_engineer = User(
        id=LAUNCH_ENGINEER_ID,
        full_name="Wassim Mchichi",
        registration_number="LE-001",
        password_hash="test",
        role="LAUNCH_ENGINEER",
        status="ACTIVE",
        failed_login_count=0,
        is_locked=False,
        must_change_password=False,
        created_at=now,
    )
    db_session.add_all([
        user,
        launch_engineer,
        Supplier(
            supplier_id=1,
            supplier_reference="SUP-001",
            full_name="Atlas Technical Textiles",
            status="Active",
            created_at=now,
            updated_at=now,
        ),
    ])

    project = Project(
        project_id=1,
        project_code="P-2261",
        name="Covers B-SUV Seat Trim",
        launch_engineer_user_id=LAUNCH_ENGINEER_ID,
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
    receiver = ManufacturingReceiver(receiver_id=1, name="Main Production", status="Active")
    db_session.add_all([project, customer, contact, delivery_method, receiver])

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
    verification_document = Document(
        document_id=103,
        document_type="LAUNCH_VERIFICATION",
        file_name="launch-verification.pdf",
        file_path="/tmp/launch-verification.pdf",
        uploaded_at=now,
        uploaded_by=TEST_USER_ID,
        version=1,
    )
    db_session.add_all([po_document, meeting_document, verification_document])

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

    return {
        "user_id": TEST_USER_ID,
        "launch_engineer_id": LAUNCH_ENGINEER_ID,
        "meeting_document_id": 101,
        "verification_document_id": 103,
        "receiver_id": 1,
        "delivery_method_id": 1,
    }


def test_new_business_workbook_upload_preserves_units_and_versions_each_fgpn(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
    business_workbook_upload: UploadFile,
) -> None:
    result = asyncio.run(bom_extraction_service.upload_bom_files(
        db_session,
        [business_workbook_upload],
        project_id=1,
    ))

    assert result.uploaded_count == 2
    assert [version.finished_good_part_number for version in result.versions] == FGPN_CODES
    assert [version.version for version in result.versions] == [2, 2]
    for version in result.versions:
        assert version.material_row_count == 3
        assert [line.source_unit for line in version.material_lines] == ["ME", "EA", "EA"]
        assert [line.unit for line in version.material_lines] == ["ME", "EA", "EA"]
        assert version.material_lines[0].total_sqm == Decimal("0.2669")
        assert version.material_lines[0].total_quantity == Decimal("0")
    assert db_session.scalar(select(func.count()).select_from(BOM)) == 4
    assert db_session.scalar(select(func.count()).select_from(Material)) == 4
    current_boms = db_session.scalars(select(BOM).where(BOM.is_current.is_(True))).all()
    assert len(current_boms) == 2
    assert {bom.version for bom in current_boms} == {2}


def test_multi_fgpn_upload_rolls_back_all_versions_if_a_later_save_fails(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
    business_workbook_upload: UploadFile,
) -> None:
    initial_documents = db_session.scalar(select(func.count()).select_from(Document))
    save_bom = bom_repository.save_bom_version

    def save_until_second_fgpn(db: Session, **kwargs):
        if kwargs["parsed_bom"].finished_good_part_number == FGPN_CODES[1]:
            raise ValidationException("Test failure in second BOM")
        return save_bom(db, **kwargs)

    monkeypatch.setattr(bom_repository, "save_bom_version", save_until_second_fgpn)
    with pytest.raises(ValidationException, match="second BOM"):
        asyncio.run(bom_extraction_service.upload_bom_files(
            db_session,
            [business_workbook_upload],
            project_id=1,
        ))

    assert db_session.scalar(select(func.count()).select_from(BOM)) == 2
    assert db_session.scalar(select(func.count()).select_from(Document)) == initial_documents
    assert all(bom.version == 1 and bom.is_current for bom in db_session.scalars(select(BOM)))


def test_bom_upload_rejects_legacy_binary_excel_with_a_conversion_message(db_session: Session) -> None:
    with pytest.raises(ValidationException, match="convert legacy .xls files to .xlsx"):
        asyncio.run(bom_extraction_service.upload_bom_files(
            db_session,
            [UploadFile(filename="legacy.xls", file=BytesIO(b"legacy workbook"))],
        ))


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
            project_id=1,
            fgpns=[
                FgpnSimulationRequest(po_id=1, fgpn_id=1, priority=1, requested_quantity=Decimal("10")),
            ],
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
            project_id=1,
            fgpns=[
                FgpnSimulationRequest(po_id=2, fgpn_id=2, priority=1, requested_quantity=Decimal("20")),
            ],
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


def test_record_stock_reception_can_affect_stock_to_launch_engineer(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
) -> None:
    parsed = _parsed_mbom_for_fgpn(FGPN_CODES[0])
    material_part_number = next(iter(_requirements_for(parsed, Decimal("1"))))

    response = stock_management_service.record_stock_unit_reception(
        db_session,
        StockUnitReceptionRequest(
            material_part_number=material_part_number,
            quantity=Decimal("50"),
            status="WAREHOUSE",
            assigned_user_id=seeded_db["launch_engineer_id"],
        ),
        reception_user_id=seeded_db["user_id"],
    )

    stock_unit = db_session.get(StockUnit, response.stock_unit_id)

    assert response.assigned_user_id == seeded_db["launch_engineer_id"]
    assert response.assigned_user_name == "Wassim Mchichi"
    assert stock_unit is not None
    assert stock_unit.user_id == seeded_db["launch_engineer_id"]


def test_owned_simulation_can_include_or_exclude_global_stock(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
) -> None:
    parsed = _parsed_mbom_for_fgpn(FGPN_CODES[0])
    requirements = _requirements_for(parsed, Decimal("4"))
    _insert_stock_for_requirements(
        db_session,
        requirements,
        quantity_factor=Decimal("1.2"),
        owner_user_id=None,
        stock_unit_id_start=1000,
    )
    _insert_stock_for_requirements(
        db_session,
        requirements,
        quantity_factor=Decimal("0.25"),
        owner_user_id=seeded_db["launch_engineer_id"],
        stock_unit_id_start=2000,
    )

    all_stock_result = material_simulation_service.preview_simulation(
        db_session,
        SimulationPreviewRequest(
            project_id=1,
            fgpns=[
                FgpnSimulationRequest(po_id=1, fgpn_id=1, priority=1, requested_quantity=Decimal("4")),
            ],
            include_in_transit=False,
            safety_coefficient=Decimal("1"),
        ),
    )
    owner_only_result = material_simulation_service.preview_simulation(
        db_session,
        SimulationPreviewRequest(
            project_id=1,
            fgpns=[
                FgpnSimulationRequest(po_id=1, fgpn_id=1, priority=1, requested_quantity=Decimal("4")),
            ],
            include_in_transit=False,
            safety_coefficient=Decimal("1"),
            stock_scope_mode="OWNED_ONLY",
            stock_owner_user_id=seeded_db["launch_engineer_id"],
        ),
    )
    owner_plus_global_result = material_simulation_service.preview_simulation(
        db_session,
        SimulationPreviewRequest(
            project_id=1,
            fgpns=[
                FgpnSimulationRequest(po_id=1, fgpn_id=1, priority=1, requested_quantity=Decimal("4")),
            ],
            include_in_transit=False,
            safety_coefficient=Decimal("1"),
            stock_scope_mode="OWNED_ONLY",
            stock_owner_user_id=seeded_db["launch_engineer_id"],
            include_global_stock=True,
        ),
    )

    assert all_stock_result.is_feasible is True
    assert all_stock_result.stock_scope_mode == "ALL"
    assert owner_only_result.stock_scope_mode == "OWNED_ONLY"
    assert owner_only_result.stock_owner_user_id == seeded_db["launch_engineer_id"]
    assert owner_only_result.include_global_stock is False
    assert owner_only_result.is_feasible is False
    assert owner_only_result.total_launchable_quantity < Decimal("4")
    assert owner_only_result.allocation_details
    assert {
        detail.assigned_user_id
        for detail in owner_only_result.allocation_details
        if detail.stock_unit_id is not None
    } == {seeded_db["launch_engineer_id"]}
    assert owner_plus_global_result.stock_scope_mode == "OWNED_ONLY"
    assert owner_plus_global_result.include_global_stock is True
    assert owner_plus_global_result.is_feasible is True
    assert {
        detail.assigned_user_id
        for detail in owner_plus_global_result.allocation_details
        if detail.stock_unit_id is not None
    }.issubset({seeded_db["launch_engineer_id"], None})


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
            target_date=date(2026, 8, 25),
            mtg_minutes_document_id=seeded_db["meeting_document_id"],
            preview_request=SimulationPreviewRequest(
                project_id=1,
                fgpns=[
                    FgpnSimulationRequest(po_id=1, fgpn_id=1, priority=1, requested_quantity=Decimal("5")),
                ],
                include_in_transit=False,
                safety_coefficient=Decimal("1"),
            ),
        ),
        user_id=str(seeded_db["user_id"]),
    )

    assert response.simulation_id is not None
    assert db_session.execute(select(func.count(Simulation.simulation_id))).scalar_one() == 1
    assert db_session.execute(select(func.count(Launch.launch_id))).scalar_one() == 0


def test_missing_meeting_document_reservation_expires_after_24_hours(
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
            target_date=date(2026, 8, 25),
            preview_request=SimulationPreviewRequest(
                project_id=1,
                fgpns=[FgpnSimulationRequest(
                    po_id=1,
                    fgpn_id=1,
                    priority=1,
                    requested_quantity=Decimal("5"),
                )],
                safety_coefficient=Decimal("1"),
            ),
        ),
        user_id=str(seeded_db["user_id"]),
    )
    simulation = db_session.get(Simulation, response.simulation_id)
    assert response.status == "AWAITING_DOCUMENT"
    assert simulation.document_due_at is not None
    simulation.document_due_at = datetime.now() - timedelta(seconds=1)
    db_session.commit()

    review = material_simulation_service.review_simulation_for_launch(
        db_session, response.simulation_id,
    )
    assert review.can_launch is False
    assert "expired" in review.message

    with pytest.raises(ConflictException, match="reservation was released"):
        material_simulation_service.launch_saved_simulation(
            db_session, response.simulation_id,
        )
    db_session.refresh(simulation)
    allocations = db_session.scalars(
        select(StockAllocation).where(
            StockAllocation.simulation_id == response.simulation_id,
            StockAllocation.allocation_type == "SIMULATION",
        )
    ).all()
    assert simulation.workflow_status == "RELEASED"
    assert allocations and {row.status for row in allocations} == {"RELEASED"}


def test_preview_rejects_quantity_above_current_po_outstanding_demand(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
) -> None:
    with pytest.raises(ValidationException, match="exceeds outstanding quantity"):
        material_simulation_service.preview_simulation(
            db_session,
            SimulationPreviewRequest(
                project_id=1,
                fgpns=[FgpnSimulationRequest(
                    po_id=1,
                    fgpn_id=1,
                    po_line_id=1,
                    priority=1,
                    requested_quantity=Decimal("101"),
                )],
                safety_coefficient=Decimal("1"),
            ),
        )


def test_preview_rejects_an_explicit_line_from_an_older_po_version(
    db_session: Session,
    seeded_db: dict[str, int | uuid.UUID],
) -> None:
    db_session.add(PurchaseOrderVersion(
        po_version_id=10,
        po_id=1,
        version_number=2,
        document_id=100,
        created_at=datetime.now(),
        created_by=TEST_USER_ID,
    ))
    db_session.add(PurchaseOrderLine(
        po_line_id=10,
        po_version_id=10,
        line_number=1,
        fgpn_id=1,
        ordered_quantity=Decimal("100"),
        unit_price=Decimal("0"),
        delivery_method_id=1,
        created_at=datetime.now(),
    ))
    db_session.flush()
    db_session.get(PurchaseOrder, 1).current_version_id = 10
    db_session.commit()

    with pytest.raises(ValidationException, match="not part of the current PO version"):
        material_simulation_service.preview_simulation(
            db_session,
            SimulationPreviewRequest(
                project_id=1,
                fgpns=[FgpnSimulationRequest(
                    po_id=1,
                    fgpn_id=1,
                    po_line_id=1,
                    priority=1,
                    requested_quantity=Decimal("5"),
                )],
                safety_coefficient=Decimal("1"),
            ),
        )


def test_saved_simulation_can_be_promoted_to_launch_record(
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
            target_date=date(2026, 8, 25),
            mtg_minutes_document_id=seeded_db["meeting_document_id"],
            preview_request=SimulationPreviewRequest(
                project_id=1,
                fgpns=[
                    FgpnSimulationRequest(po_id=1, fgpn_id=1, priority=1, requested_quantity=Decimal("5")),
                ],
                include_in_transit=False,
                safety_coefficient=Decimal("1"),
            ),
        ),
        user_id=str(seeded_db["user_id"]),
    )

    now = datetime(2026, 8, 25, 9, 0, 0)
    launch = Launch(
        simulation_id=response.simulation_id,
        planned_date=date(2026, 8, 25),
        delivery_method_id=seeded_db["delivery_method_id"],
        receiver_id=seeded_db["receiver_id"],
        status="PLANNED",
        completed_by=seeded_db["user_id"],
        verified_by=seeded_db["user_id"],
        verification_document_id=seeded_db["verification_document_id"],
        created_at=now,
        updated_at=now,
    )
    db_session.add(launch)
    db_session.commit()

    saved_launch = db_session.execute(select(Launch)).scalar_one()
    saved_simulation = db_session.get(Simulation, response.simulation_id)

    assert saved_launch.simulation_id == response.simulation_id
    assert saved_simulation.launch.launch_id == saved_launch.launch_id


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
    # Add an explicit component so the partial-package regression remains
    # independent of changes to the reference workbook's material mix.
    component_type = MaterialType(name="TEST_COMPONENT", unit="pcs")
    db_session.add(component_type)
    db_session.flush()
    db_session.add(Material(material_part_number="TEST-COMP", description="Test component",
        material_type_id=component_type.material_type_id, unit_price=Decimal("1")))
    db_session.flush()
    bom = db_session.scalars(select(BOM).where(BOM.fgpn_id == 1, BOM.is_current.is_(True))).one()
    bom.lines.append(BOMLine(line_number=max(line.line_number for line in bom.lines) + 1,
        material_part_number="TEST-COMP", part_type="S", coefficient=Decimal("1"), total_quantity=Decimal("1")))
    db_session.add(StockUnit(material_part_number="TEST-COMP", quantity=Decimal("6"),
        status="WAREHOUSE", created_at=datetime(2026, 8, 24)))
    db_session.commit()
    response = material_simulation_service.save_simulation(
        db_session,
        SimulationSaveRequest(
            target_date=date(2026, 8, 25),
            mtg_minutes_document_id=seeded_db["meeting_document_id"],
            preview_request=SimulationPreviewRequest(
                project_id=1,
                fgpns=[
                    FgpnSimulationRequest(po_id=1, fgpn_id=1, priority=1, requested_quantity=Decimal("5")),
                ],
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
    replay_response = material_simulation_service.launch_saved_simulation(
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
    assert replay_response.status == "LAUNCHED"
    assert replay_response.idempotent_replay is True
    assert replay_response.launch_allocation_count == launch_response.launch_allocation_count
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
    parsed = parse_bom_workbook_many(MBOM_PATH.read_bytes(), source_filename=MBOM_PATH.name)
    return next(bom for bom in parsed if bom.finished_good_part_number == fgpn_code)


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
    owner_user_id: uuid.UUID | None = None,
    stock_unit_id_start: int = 1,
) -> None:
    now = datetime(2026, 8, 24, 9, 0, 0)
    for index, (material_part_number, requirement) in enumerate(requirements.items(), start=1):
        db_session.add(
            StockUnit(
                stock_unit_id=stock_unit_id_start + index - 1,
                material_part_number=material_part_number,
                quantity=(requirement * quantity_factor).quantize(Decimal("0.0001")),
                status="WAREHOUSE",
                created_at=now,
                user_id=owner_user_id,
            )
        )
    db_session.commit()
