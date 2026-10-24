"""BOM upload orchestration service."""
from __future__ import annotations
from pathlib import Path

import logging
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.exceptions.base import NotFoundException, ValidationException
from app.models.bom import BOM
from app.models.bom_line import BOMLine
from app.models.fgpn import FGPN
from app.policies import PolicyActor, policy_engine, system_actor
from app.repositories import bom_repository
from app.schemas.bom import BomUploadResult, BomVersionResponse, BomMaterialLineResponse
from app.utils.bom_workbook_extractor import parse_bom_workbook_many

logger = logging.getLogger(__name__)


_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"xlsx"})


def _is_excel_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED_EXTENSIONS


async def upload_bom_files(
    db: Session,
    files: list[UploadFile],
    *,
    development_level: Optional[str] = None,
    uploaded_by: Optional[str] = None,
    notes: Optional[str] = None,
    project_id: Optional[int] = None,
    actor: Optional[PolicyActor] = None,
) -> BomUploadResult:
    policy_engine.require(actor or system_actor(), "bom.upload")

    if not files:
        raise ValidationException("At least one BOM file must be provided.", details=None)

    accepted: list[tuple[UploadFile, bytes]] = []
    rejected_filenames: list[str] = []

    for file in files:
        filename = file.filename or ""
        if not filename:
            continue
        if not _is_excel_file(filename):
            rejected_filenames.append(filename)
            continue
        content = await file.read()
        if not content:
            raise ValidationException(f"The uploaded file '{filename}' is empty.", details={"filename": filename})
        accepted.append((file, content))
        upload_dir = Path("/app/uploads") if Path("/app").exists() else Path("backend/uploads")
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
            with open(upload_dir / filename, "wb") as f_out:
                f_out.write(content)
        except Exception as e:
            logger.warning("Could not persist file to %s: %s", upload_dir / filename, e)

    if rejected_filenames:
        raise ValidationException("One or more files have an unsupported format. Only .xlsx files are accepted; convert legacy .xls files to .xlsx first.", details={"rejected_files": rejected_filenames})
    if not accepted:
        raise ValidationException("No valid Excel files were found in the upload.", details=None)

    # Validate every workbook and resolve every FGPN before creating versions.
    # One upload can contain several FGPNs and must not leave a partial import.
    pending_boms = []
    for file, content in accepted:
        filename = file.filename or ""
        for parsed in parse_bom_workbook_many(content, source_filename=filename):
            fgpn = bom_repository.find_fgpn_by_code(
                db,
                parsed.finished_good_part_number,
                project_id=project_id,
            )
            pending_boms.append((parsed, fgpn, filename))

    results: list[BomVersionResponse] = []
    try:
        for parsed, fgpn, filename in pending_boms:
            next_version = bom_repository.compute_next_version(db, fgpn.fgpn_id)

            bom = bom_repository.save_bom_version(
                db,
                parsed_bom=parsed,
                fgpn=fgpn,
                version=next_version,
                source_filename=filename,
                commit=False,
            )

            # Build material lines list from saved BOMLine records
            material_lines = [
                BomMaterialLineResponse(
                    source_row_number=line.line_number,
                    material_part_number=line.material_part_number,
                    cover_revision=line.cover_revision,
                    cover_pn=line.cover_pn,
                    cover_description=line.cover_description,
                    quantity_tpdm=line.quantity_tpdm,
                    total_quantity=line.total_quantity,
                    total_sqm=line.total_sqm,
                    coefficient=line.coefficient,
                    part_type=line.part_type,
                    material_description=line.material.description if line.material else None,
                    unit=line.source_unit,
                    source_unit=line.source_unit,
                )
                for line in bom.lines
            ]

            results.append(
                BomVersionResponse(
                    id=bom.bom_id,
                    fgpn_id=fgpn.fgpn_id,
                    finished_good_part_number=fgpn.fgpn_code,
                    version=bom.version,
                    source_filename=filename,
                    material_row_count=parsed.material_row_count,
                    is_current=bom.is_current,
                    material_lines=material_lines,
                    source_reported_by=parsed.source_reported_by,
                    source_report_date=parsed.source_report_date,
                    source_report_time=parsed.source_report_time,
                    project_id=fgpn.project_id,
                    project_code=fgpn.project.project_code if fgpn.project else None,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return BomUploadResult(
        uploaded_count=len(results),
        versions=results,
    )



def list_boms(
    db: Session,
    *,
    project_id: Optional[int] = None,
    actor: Optional[PolicyActor] = None,
) -> list[BomVersionResponse]:
    """Return all stored BOM versions and their extracted material lines."""
    policy_engine.require(actor or system_actor(), "bom.view")

    stmt = (
        select(BOM)
        .options(
            joinedload(BOM.fgpn).joinedload(FGPN.project),
            joinedload(BOM.document),
            selectinload(BOM.lines).joinedload(BOMLine.material),
        )
        .order_by(BOM.bom_id.desc())
    )
    if project_id is not None:
        stmt = stmt.join(BOM.fgpn).where(FGPN.project_id == project_id)

    boms = db.execute(stmt).scalars().all()
    results: list[BomVersionResponse] = []
    for bom in boms:
        material_lines = [
            BomMaterialLineResponse(
                source_row_number=line.line_number,
                material_part_number=line.material_part_number,
                cover_revision=line.cover_revision,
                cover_pn=line.cover_pn,
                cover_description=line.cover_description,
                quantity_tpdm=line.quantity_tpdm,
                total_quantity=line.total_quantity,
                total_sqm=line.total_sqm,
                coefficient=line.coefficient,
                part_type=line.part_type,
                material_description=line.material.description if line.material else None,
                unit=line.source_unit,
                source_unit=line.source_unit,
            )
            for line in sorted(bom.lines, key=lambda l: l.line_number)
        ]
        results.append(
            BomVersionResponse(
                id=bom.bom_id,
                fgpn_id=bom.fgpn_id,
                finished_good_part_number=bom.fgpn.fgpn_code if bom.fgpn else "UNKNOWN",
                version=bom.version,
                source_filename=bom.document.file_name if bom.document else "unknown.xlsx",
                material_row_count=len(bom.lines),
                is_current=bom.is_current,
                material_lines=material_lines,
                source_reported_by=bom.source_reported_by,
                source_report_date=bom.source_report_date,
                source_report_time=bom.source_report_time,
                project_id=bom.fgpn.project_id if bom.fgpn else None,
                project_code=bom.fgpn.project.project_code if bom.fgpn and bom.fgpn.project else None,
            )
        )
    return results


def get_bom_file_content(
    db: Session,
    bom_id: int,
    actor: Optional[PolicyActor] = None,
) -> tuple[str, bytes]:
    policy_engine.require(actor or system_actor(), "bom.view")

    stmt = (
        select(BOM)
        .options(
            joinedload(BOM.document),
            joinedload(BOM.fgpn),
        )
        .where(BOM.bom_id == bom_id)
    )
    bom = db.execute(stmt).scalar_one_or_none()
    if bom is None:
        raise NotFoundException(f"BOM version {bom_id} not found.")

    filename = bom.document.file_name if (bom.document and bom.document.file_name) else f"BOM_{bom.fgpn.fgpn_code}.xlsx"

    search_dirs = [
        Path("/app/uploads"),
        Path("backend/uploads"),
        Path("uploads"),
        Path("/business-test"),
        Path("/business-test/mbom_files"),
        Path("ressources/mbom_files"),
        Path("ressources/business-test"),
        Path("ressources/business-test/mbom_files"),
    ]
    for d in search_dirs:
        candidate = d / filename
        if candidate.exists() and candidate.is_file():
            with open(candidate, "rb") as f_in:
                return filename, f_in.read()
        single_candidate = d / "single_fgpn" / filename
        if single_candidate.exists() and single_candidate.is_file():
            with open(single_candidate, "rb") as f_in:
                return filename, f_in.read()

    raise NotFoundException(f"Original BOM file '{filename}' was not found on disk.")
