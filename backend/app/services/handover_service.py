"""Warehouse handover service functions."""
from __future__ import annotations

import datetime as dt
import shutil
from decimal import Decimal
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.exceptions.base import NotFoundException, ValidationException
from app.models import AuditLog, Document, FGPN, Project, StockIssueHandover
from app.models.material import Material
from app.models.material_type import MaterialType
from app.models.simulation import Simulation
from app.models.simulation_fgpn import SimulationFGPN
from app.models.stock_allocation import StockAllocation
from app.models.stock_unit import StockUnit
from app.repositories.bom_repository import _get_system_user
from app.schemas.handover import (
    HandoverAccessResponse,
    HandoverCollectionRequest,
    HandoverDocumentUploadResponse,
    HandoverItemResponse,
)

UPLOAD_ROOT = Path("uploads") / "handovers"


def get_handover_for_code(db: Session, delivery_code: str) -> HandoverAccessResponse:
    handover = _get_handover_by_code(db, delivery_code)
    _ensure_code_can_open(handover)
    return _to_response(db, handover)


def confirm_collection(
    db: Session,
    delivery_code: str,
    request: HandoverCollectionRequest,
) -> HandoverAccessResponse:
    handover = _get_handover_by_code(db, delivery_code)
    _ensure_code_can_open(handover)

    now = dt.datetime.now()
    handover.receiver_name = request.receiver_name.strip()
    handover.warehouse_team_leader_name = request.warehouse_team_leader_name.strip()
    handover.code_used_at = now
    if handover.status in {"Draft", "Code_Generated"}:
        handover.status = "Document_Generated"

    _audit(
        db,
        action="HANDOVER_CODE_USED",
        entity_id=handover.delivery_inst_id,
        details=(
            f"{handover.delivery_code} opened by {handover.warehouse_team_leader_name} "
            f"for receiver {handover.receiver_name}"
        ),
    )
    db.commit()
    db.refresh(handover)
    return _to_response(db, handover)


def upload_signed_document(
    db: Session,
    delivery_code: str,
    file: UploadFile,
    uploaded_by: str | None = None,
) -> HandoverDocumentUploadResponse:
    handover = _get_handover_by_code(db, delivery_code)
    if not file.filename:
        raise ValidationException("A signed handover PDF file is required.")
    if not file.filename.lower().endswith(".pdf"):
        raise ValidationException("Signed handover proof must be uploaded as a PDF.")

    user_id = _get_system_user(db)
    now = dt.datetime.now()
    safe_name = Path(file.filename).name.replace(" ", "_")
    stored_name = f"DI-{handover.delivery_inst_id}_{now:%Y%m%d%H%M%S}_{safe_name}"
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_ROOT / stored_name
    with stored_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    document = Document(
        document_type="SIGNED_HANDOVER",
        file_name=safe_name,
        file_path=str(stored_path),
        uploaded_at=now,
        uploaded_by=user_id,
    )
    db.add(document)
    db.flush()

    handover.signed_document_id = document.document_id
    handover.uploaded_at = now
    handover.uploader_username = (uploaded_by or handover.warehouse_team_leader_name or "warehouse").strip()
    handover.status = "Signed_Uploaded"

    _audit(
        db,
        action="SIGNED_HANDOVER_UPLOADED",
        entity_id=handover.delivery_inst_id,
        details=f"{document.file_name} stored for delivery instruction {handover.delivery_inst_id}",
    )
    db.commit()
    db.refresh(document)
    db.refresh(handover)

    return HandoverDocumentUploadResponse(
        document_id=document.document_id,
        file_name=document.file_name,
        file_path=document.file_path,
        uploaded_at=document.uploaded_at,
        handover=_to_response(db, handover),
    )


def _get_handover_by_code(db: Session, delivery_code: str) -> StockIssueHandover:
    normalized = delivery_code.strip()
    handover = db.execute(
        select(StockIssueHandover)
        .options(
            selectinload(StockIssueHandover.signed_document),
            selectinload(StockIssueHandover.simulation)
            .selectinload(Simulation.selected_fgpns)
            .selectinload(SimulationFGPN.fgpn)
            .selectinload(FGPN.project),
            selectinload(StockIssueHandover.simulation).selectinload(Simulation.creator),
            selectinload(StockIssueHandover.simulation).selectinload(Simulation.launch),
        )
        .where(StockIssueHandover.delivery_code == normalized)
    ).scalar_one_or_none()
    if handover is None:
        raise NotFoundException("No delivery instruction matches this access code.")
    return handover


def _ensure_code_can_open(handover: StockIssueHandover) -> None:
    if handover.status == "Expired" or handover.code_expires_at < dt.datetime.now():
        handover.status = "Expired"
        raise ValidationException("This delivery access code has expired.")
    if handover.status == "Validated":
        raise ValidationException("This delivery instruction has already been validated.")


def _to_response(db: Session, handover: StockIssueHandover) -> HandoverAccessResponse:
    simulation = handover.simulation
    project = _handover_project(simulation)
    required_at = _required_at(simulation)
    created_at = simulation.created_at if simulation else dt.datetime.now()
    signed = handover.signed_document

    return HandoverAccessResponse(
        delivery_inst_id=handover.delivery_inst_id,
        ref=f"DI-{created_at:%Y}-{handover.delivery_inst_id:03d}",
        simulation_id=handover.simulation_id,
        project_id=project.project_id if project else None,
        project_code=project.project_code if project else None,
        project_name=project.name if project else None,
        created_at=created_at,
        created_by=simulation.creator.registration_number if simulation and simulation.creator else None,
        required_at=required_at,
        delivery_code=handover.delivery_code,
        code_expires_at=handover.code_expires_at,
        code_used=handover.code_used_at is not None or handover.status in {"Document_Generated", "Signed_Uploaded", "Validated"},
        code_used_at=handover.code_used_at,
        status=handover.status,
        receiver_name=handover.receiver_name,
        warehouse_team_leader_name=handover.warehouse_team_leader_name,
        signed_document_id=handover.signed_document_id,
        signed_file_name=signed.file_name if signed else None,
        uploaded_at=handover.uploaded_at,
        items=_handover_items(db, handover.simulation_id),
    )


def _handover_project(simulation: Simulation | None) -> Project | None:
    if simulation is None:
        return None
    first = next(iter(simulation.selected_fgpns), None)
    return first.fgpn.project if first and first.fgpn else None


def _required_at(simulation: Simulation | None) -> dt.datetime:
    if simulation and simulation.launch:
        return dt.datetime.combine(simulation.launch.planned_date, dt.time(hour=6))
    if simulation:
        return dt.datetime.combine(simulation.target_date, dt.time(hour=6))
    return dt.datetime.now()


def _handover_items(db: Session, simulation_id: int) -> list[HandoverItemResponse]:
    rows = db.execute(
        select(
            StockUnit.material_part_number,
            Material.description,
            MaterialType.unit,
            func.sum(StockAllocation.allocated_quantity).label("quantity"),
        )
        .join(StockUnit, StockUnit.stock_unit_id == StockAllocation.stock_unit_id)
        .join(Material, Material.material_part_number == StockUnit.material_part_number)
        .join(MaterialType, MaterialType.material_type_id == Material.material_type_id)
        .where(StockAllocation.simulation_id == simulation_id)
        .where(StockAllocation.allocation_type == "LAUNCH")
        .group_by(StockUnit.material_part_number, Material.description, MaterialType.unit)
        .order_by(StockUnit.material_part_number)
    ).all()

    if not rows:
        rows = db.execute(
            select(
                StockUnit.material_part_number,
                Material.description,
                MaterialType.unit,
                func.sum(StockAllocation.allocated_quantity).label("quantity"),
            )
            .join(StockUnit, StockUnit.stock_unit_id == StockAllocation.stock_unit_id)
            .join(Material, Material.material_part_number == StockUnit.material_part_number)
            .join(MaterialType, MaterialType.material_type_id == Material.material_type_id)
            .where(StockAllocation.simulation_id == simulation_id)
            .group_by(StockUnit.material_part_number, Material.description, MaterialType.unit)
            .order_by(StockUnit.material_part_number)
        ).all()

    return [
        HandoverItemResponse(
            material_part_number=row.material_part_number,
            description=row.description,
            roll_size=None,
            quantity=row.quantity or Decimal("0"),
            unit=row.unit,
        )
        for row in rows
    ]


def _audit(db: Session, *, action: str, entity_id: int, details: str) -> None:
    db.add(
        AuditLog(
            user_id=_get_system_user(db),
            action=action,
            entity_type="StockIssueHandover",
            entity_id=entity_id,
            timestamp=dt.datetime.now(),
            reason="Warehouse team leader handover workflow",
            details=details,
        )
    )
