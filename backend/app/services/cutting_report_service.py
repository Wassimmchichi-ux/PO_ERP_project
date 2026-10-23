"""Stage source cutting reports, then post explicitly confirmed consumption."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions.base import ConflictException, NotFoundException, ValidationException
from app.models import (
    AuditLog,
    CuttingConsumption,
    CuttingReportImport,
    Document,
    Launch,
    Material,
    StockUnit,
)
from app.policies import PolicyActor, policy_engine
from app.repositories import stock_repository
from app.schemas.cutting_report import CuttingReportPostRequest, CuttingReportResponse
from app.utils.cutting_report_extractor import extract_cutting_report
from app.services import stock_movement_service


def _response(report: CuttingReportImport, *, duplicate=False) -> CuttingReportResponse:
    return CuttingReportResponse(
        report_id=report.report_id, file_name=report.file_name,
        imported_at=report.imported_at, posted_at=report.posted_at,
        posted_launch_id=report.posted_launch_id, confirmed_usage_unit=report.confirmed_usage_unit,
        already_imported=duplicate, lines=report.source_rows,
        warnings=[] if report.posted_at else [
            "Spreading Usage is a reported usage quantity, not a remaining-stock balance.",
            "Confirm the launch, measurement unit and consumption basis before posting. Import alone does not change stock.",
        ],
    )


def list_reports(db: Session, *, actor: PolicyActor) -> list[CuttingReportResponse]:
    policy_engine.require(actor, "stock.view")
    reports = db.scalars(select(CuttingReportImport).order_by(CuttingReportImport.imported_at.desc()).limit(50)).all()
    return [_response(report) for report in reports]


def import_report(db: Session, content: bytes, filename: str, user_id: uuid.UUID, *, actor: PolicyActor) -> CuttingReportResponse:
    policy_engine.require(actor, "stock.cutman.import")
    rows = extract_cutting_report(content, filename)
    digest = sha256(content).hexdigest()
    existing = db.scalar(select(CuttingReportImport).where(CuttingReportImport.file_sha256 == digest))
    if existing:
        return _response(existing, duplicate=True)
    report = CuttingReportImport(file_name=Path(filename).name[:255], file_sha256=digest,
        source_content=content, source_rows=[row.as_dict() for row in rows],
        imported_by=user_id, imported_at=datetime.now())
    db.add(report)
    try:
        db.flush()
        db.add(AuditLog(user_id=user_id, action="IMPORT_CUTTING_REPORT", entity_type="CuttingReportImport",
            entity_id=report.report_id, timestamp=datetime.now(), details=json.dumps({"sha256": digest, "rows": len(rows)})))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(select(CuttingReportImport).where(CuttingReportImport.file_sha256 == digest))
        if existing:
            return _response(existing, duplicate=True)
        raise ConflictException("Could not record this cutting report.") from exc
    return _response(report)


def post_report(db: Session, report_id: int, request: CuttingReportPostRequest, user_id: uuid.UUID, *, actor: PolicyActor) -> CuttingReportResponse:
    policy_engine.require(actor, "stock.cutman.import")
    report = db.scalar(select(CuttingReportImport).where(CuttingReportImport.report_id == report_id).with_for_update())
    if report is None:
        raise NotFoundException(f"Cutting report {report_id} not found.")
    if report.posted_at is not None:
        raise ConflictException("This cutting report has already been posted.")
    if db.get(Launch, request.launch_id) is None:
        raise NotFoundException(f"Launch {request.launch_id} not found. A report cannot invent a launch association.")
    fingerprints = [row["fingerprint"] for row in report.source_rows]
    if len(set(fingerprints)) != len(fingerprints):
        raise ConflictException("The report contains ambiguous repeated cutting events; reconcile the source rows before posting.")
    if db.scalar(select(CuttingConsumption.consumption_id).where(CuttingConsumption.source_event_fingerprint.in_(fingerprints)).limit(1)):
        raise ConflictException("A cutting event from this report was already posted. Reconcile overlapping or corrected exports.")

    totals = defaultdict(Decimal)
    normalized_rows = []
    unit_aliases = {"m": "m", "me": "m", "meter": "m", "meters": "m", "sqm": "m", "m2": "m", "pcs": "pcs", "ea": "pcs", "kg": "kg"}
    nesting_names = []
    for row in report.source_rows:
        amount = Decimal(row["spreading_usage"]).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if amount <= 0 or amount > Decimal("999999.9999"):
            raise ValidationException(f"Row {row['row_number']}: usage is outside consumption precision/range.")
        totals[row["material_part_number"]] += amount
        nesting_name = (
            row["raw_fields"].get("Original nesting name")
            or request.stock_unit_ids_by_row.get(row["row_number"])
            or ""
        ).strip()
        if not nesting_name:
            raise ValidationException(
                f"Row {row['row_number']}: Original nesting name is required as the stock-unit identifier."
            )
        nesting_names.append(nesting_name)
        normalized_rows.append((row, amount, nesting_name))
    # Serialize imports affecting the same material and validate the complete
    # report before writing any consumption rows.
    materials = db.scalars(select(Material).where(Material.material_part_number.in_(sorted(totals))).order_by(Material.material_part_number).with_for_update()).all()
    material_map = {material.material_part_number: material for material in materials}
    stock_units = db.scalars(
        select(StockUnit)
        .where(StockUnit.business_unit_id.in_(set(nesting_names)))
        .with_for_update()
    ).all()
    units_by_business_id = {unit.business_unit_id: unit for unit in stock_units}
    consumption_by_unit = stock_repository.get_cutting_consumption_by_stock_unit(db)
    usage_by_unit = defaultdict(Decimal)
    for row, amount, nesting_name in normalized_rows:
        stock_unit = units_by_business_id.get(nesting_name)
        if stock_unit is None:
            raise ValidationException(
                f"Row {row['row_number']}: stock unit '{nesting_name}' was not found."
            )
        if stock_unit.status != "PRODUCTION":
            raise ValidationException(
                f"Row {row['row_number']}: stock unit '{nesting_name}' is not in PRODUCTION."
            )
        if stock_unit.material_part_number != row["material_part_number"]:
            raise ValidationException(
                f"Row {row['row_number']}: stock unit '{nesting_name}' belongs to material "
                f"{stock_unit.material_part_number}, not {row['material_part_number']}."
            )
        usage_by_unit[stock_unit.stock_unit_id] += amount

    for part, amount in totals.items():
        material = material_map.get(part)
        if material is None:
            raise ValidationException(f"Unknown material {part}. Resolve its master-data mapping before posting.")
        stored_unit = unit_aliases.get(material.material_type.unit.strip().lower())
        if stored_unit != request.usage_unit:
            raise ValidationException(f"Material {part} has unit {material.material_type.unit}; it does not match confirmed usage unit {request.usage_unit}.")
    for stock_unit_id, amount in usage_by_unit.items():
        stock_unit = next(unit for unit in stock_units if unit.stock_unit_id == stock_unit_id)
        remaining = max(
            Decimal("0"),
            stock_unit.quantity - consumption_by_unit.get(stock_unit_id, Decimal("0")),
        )
        if amount > remaining:
            raise ValidationException(
                f"Reported usage {amount} for stock unit {stock_unit.business_unit_id} exceeds "
                f"its remaining production quantity {remaining}."
            )

    now = datetime.now()
    document = Document(document_type="CUTMAN_REPORT", file_name=report.file_name,
        file_path=f"/stock/cutting-reports/{report.report_id}/source", uploaded_at=report.imported_at,
        uploaded_by=report.imported_by, version=1)
    db.add(document)
    try:
        db.flush()
        for row, amount, nesting_name in normalized_rows:
            stock_unit = units_by_business_id[nesting_name]
            db.add(CuttingConsumption(launch_id=request.launch_id, material_part_number=row["material_part_number"],
                quantity_consumed=amount, nesting_name=nesting_name, stock_unit_id=stock_unit.stock_unit_id,
                cutman_document_id=document.document_id, consumed_at=datetime.fromisoformat(row["started_at"]),
                source_report_id=report.report_id, source_row_number=row["row_number"], source_event_fingerprint=row["fingerprint"]))
            stock_movement_service.record_movement(
                db,
                material_part_number=row["material_part_number"],
                movement_type="CUTMAN_CONSUMPTION",
                quantity_change=-amount,
                actor_user_id=user_id,
                stock_unit_id=stock_unit.stock_unit_id,
                stock_unit_reference=stock_unit.business_unit_id,
                from_status="PRODUCTION",
                to_status="PRODUCTION",
                source_reference=report.file_name,
                note=f"CutMan report {report.report_id}, row {row['row_number']}.",
                occurred_at=datetime.fromisoformat(row["started_at"]),
            )
        report.posted_launch_id = request.launch_id
        report.posted_by = user_id
        report.posted_at = now
        report.confirmed_usage_unit = request.usage_unit
        db.add(AuditLog(user_id=user_id, action="POST_CUTTING_CONSUMPTION", entity_type="CuttingReportImport",
            entity_id=report_id, timestamp=now, details=json.dumps({"launch_id": request.launch_id, "unit": request.usage_unit, "materials": {part: str(amount) for part, amount in totals.items()}})))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictException("A cutting event was posted concurrently; refresh the report history.") from exc
    return _response(report)
