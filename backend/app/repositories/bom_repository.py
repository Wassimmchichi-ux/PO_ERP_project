"""Repository layer for BOM persistence."""
from __future__ import annotations

import logging
import uuid
from typing import Optional
import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions.base import ConflictException, NotFoundException, ValidationException
from app.utils.bom_workbook_extractor import ParsedBom
from app.models.audit_log import AuditLog
from app.models.bom import BOM
from app.models.bom_line import BOMLine
from app.models.document import Document
from app.models.fgpn import FGPN
from app.models.material import Material
from app.models.material_type import MaterialType
from app.models.user import User
from app.models.project import Project

logger = logging.getLogger(__name__)


def _get_system_user(db: Session) -> uuid.UUID:
    """Get or create a default system user to satisfy foreign keys."""
    user = db.execute(select(User).where(User.registration_number == 'SYSTEM')).scalar_one_or_none()
    if not user:
        user = User(
            full_name="System User",
            registration_number="SYSTEM",
            password_hash="dummy",
            role="SUPERADMIN"
        )
        db.add(user)
        db.flush()
    return user.id


def _get_system_audit(db: Session, user_id: uuid.UUID) -> int:
    audit = AuditLog(
        user_id=user_id,
        action="CREATE",
        entity_type="BOM",
        timestamp=datetime.datetime.now(),
        reason="System default audit log",
        details="BOM upload"
    )
    db.add(audit)
    db.flush()
    return audit.audit_id


def _get_or_create_material_type(db: Session, name: str = 'Default', unit: str = 'pcs') -> int:
    mt = db.execute(select(MaterialType).where(MaterialType.name == name)).scalar_one_or_none()
    if not mt:
        mt = MaterialType(name=name, unit=unit, status='Active')
        db.add(mt)
        db.flush()
    return mt.material_type_id


def _material_type_for_bom_line(db: Session, part_type: Optional[str], unit: Optional[str]) -> int:
    normalized = (part_type or '').strip().upper()
    if normalized == 'M':
        return _get_or_create_material_type(db, 'M', 'sqm')
    if normalized == 'S':
        return _get_or_create_material_type(db, 'S', 'pcs')
    return _get_or_create_material_type(db, normalized or 'Default', unit or 'pcs')


def find_fgpn_by_code(db: Session, fgpn_code: str) -> FGPN:
    """Find an existing FGPN by its part number code.

    Raises:
        ValidationException: If no FGPN with the given code exists.
    """
    fgpns = db.execute(
        select(FGPN).where(FGPN.fgpn_code == fgpn_code)
    ).scalars().all()

    if not fgpns:
        raise ValidationException(
            f"No FGPN found with part number '{fgpn_code}'. "
            f"The FGPN must already exist in the database before uploading a BOM.",
            details={"fgpn_code": fgpn_code},
        )
    if len(fgpns) > 1:
        raise ValidationException(
            f"More than one FGPN found with part number '{fgpn_code}'. "
            "FGPN is now scoped by PO, so upload must identify the target PO before saving this BOM.",
            details={
                "fgpn_code": fgpn_code,
                "matches": [
                    {"fgpn_id": item.fgpn_id, "po_id": item.po_id, "project_id": item.project_id}
                    for item in fgpns
                ],
            },
        )
    return fgpns[0]


def get_latest_version_by_fgpn_id(db: Session, fgpn_id: int) -> Optional[int]:
    """Get the latest BOM version number for a given FGPN id."""
    stmt = select(func.max(BOM.version)).where(BOM.fgpn_id == fgpn_id)
    result = db.execute(stmt).scalar_one_or_none()
    return result if result is not None else None


def compute_next_version(db: Session, fgpn_id: int) -> int:
    """Compute the next BOM version number for a given FGPN id.

    Version numbers are scoped per FGPN:
    - If no BOM exists for this FGPN: returns 1
    - Otherwise: returns max(version) + 1
    """
    latest = get_latest_version_by_fgpn_id(db, fgpn_id)
    return (latest + 1) if latest is not None else 1


def save_bom_version(
    db: Session,
    *,
    parsed_bom: ParsedBom,
    fgpn: FGPN,
    version: int,
    source_filename: str,
) -> BOM:
    """Create a new BOM version for the given FGPN.

    This function:
    1. Checks for version collision.
    2. Creates a Document record for the uploaded file.
    3. Demotes any existing is_current BOMs for this FGPN.
    4. Creates the BOM record.
    5. Creates all BOMLine records.
    6. Commits the transaction.
    7. Returns the refreshed BOM with its lines loaded.
    """
    # Check collision
    existing = db.execute(
        select(BOM)
        .where(BOM.fgpn_id == fgpn.fgpn_id)
        .where(BOM.version == version)
    ).scalar_one_or_none()

    if existing is not None:
        raise ConflictException(
            f"BOM version {version} already exists for part number "
            f"'{parsed_bom.finished_good_part_number}'.",
            details={
                "finished_good_part_number": parsed_bom.finished_good_part_number,
                "version": version,
                "existing_bom_id": existing.bom_id,
            },
        )

    sys_user_id = _get_system_user(db)
    sys_audit_id = _get_system_audit(db, sys_user_id)
    # Create Document record for the uploaded Excel file
    bom_document = Document(
        document_type='BOM',
        file_name=source_filename,
        file_path='/uploads/' + source_filename,
        uploaded_at=datetime.datetime.now(),
        uploaded_by=sys_user_id,
        version=version
    )
    db.add(bom_document)
    db.flush()

    # Demote existing is_current BOMs for this FGPN
    previous = db.execute(
        select(BOM)
        .where(BOM.fgpn_id == fgpn.fgpn_id)
        .where(BOM.is_current.is_(True))
    ).scalars().all()
    for prev in previous:
        prev.is_current = False

    bom = BOM(
        fgpn_id=fgpn.fgpn_id,
        version=version,
        document_id=bom_document.document_id,
        is_current=True,
        source_reported_by=parsed_bom.source_reported_by,
        source_report_date=parsed_bom.source_report_date,
        source_report_time=parsed_bom.source_report_time,
        audit_id=sys_audit_id
    )
    db.add(bom)
    db.flush()

    for line in parsed_bom.lines:
        material_type_id = _material_type_for_bom_line(db, line.part_type, line.unit)
        # Ensure material exists
        material = db.execute(select(Material).where(Material.material_part_number == line.material_part_number)).scalar_one_or_none()
        if not material:
            material = Material(
                material_part_number=line.material_part_number,
                description=line.material_description or 'Unknown Material',
                material_type_id=material_type_id,
                status='Active',
                unit_price=Decimal("0.0000") 
            )
            db.add(material)
            db.flush()
        else:
            material.material_type_id = material_type_id

        bom_line = BOMLine(
            bom_id=bom.bom_id,
            line_number=line.source_row_number,
            material_part_number=line.material_part_number,
            coefficient=line.coefficient,
            part_type=line.part_type,
            cover_revision=line.cover_revision,
            cover_pn=line.cover_pn,
            quantity_tpdm=line.quantity_tpdm,
            cover_description=line.cover_description,
            total_quantity=line.total_quantity,
            total_sqm=line.total_sqm
        )
        db.add(bom_line)

    # Commit changes to persist all rows
    db.commit()

    # Refresh the bom instance and expire relationship cache to force reload
    db.refresh(bom)

    return bom



#Logique open point: 
# THE UNIT PRICE  should be entered after the material is added to the database (from BOM upload or by Warehouse Team Leader)
# Detect the materailType from the BOM, and add the type if the material doesn't exist from {M, C, S}
