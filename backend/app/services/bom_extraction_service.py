"""BOM upload orchestration service."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.exceptions.base import ValidationException
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
