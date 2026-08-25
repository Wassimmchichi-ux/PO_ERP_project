"""BOM upload orchestration service."""
from __future__ import annotations

import logging
from typing import Optional
from decimal import Decimal

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.exceptions.base import ValidationException
from app.repositories import bom_repository
from app.schemas.bom import BomUploadResult, BomVersionResponse, BomMaterialLineResponse
from app.utils.bom_workbook_extractor import ParsedBom, parse_bom_workbook

logger = logging.getLogger(__name__)


_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"xlsx", "xls"})


def _is_excel_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED_EXTENSIONS


async def upload_bom_files(
    db: Session,
    files: list[UploadFile],
    *,
    development_level: Optional[str] = None,
    uploaded_by: Optional[str] = None,
    notes: Optional[str] = None,
) -> BomUploadResult:
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
        raise ValidationException("One or more files have an unsupported format. Only .xlsx and .xls files are accepted.", details={"rejected_files": rejected_filenames})
    if not accepted:
        raise ValidationException("No valid Excel files were found in the upload.", details=None)

    results: list[BomVersionResponse] = []

    for file, content in accepted:
        filename = file.filename or ""

        parsed: ParsedBom = parse_bom_workbook(content, source_filename=filename)

        # Look up existing FGPN — raises ValidationException if not found
        fgpn = bom_repository.find_fgpn_by_code(db, parsed.finished_good_part_number)

        # Compute next version scoped to this FGPN
        next_version = bom_repository.compute_next_version(db, fgpn.fgpn_id)

        bom = bom_repository.save_bom_version(
            db,
            parsed_bom=parsed,
            fgpn=fgpn,
            version=next_version,
            source_filename=filename,
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
                material_description=line.material.description if line.material else None
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

    return BomUploadResult(
        uploaded_count=len(results),
        versions=results,
    )