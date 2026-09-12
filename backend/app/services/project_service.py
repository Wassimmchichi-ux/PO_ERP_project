"""Project CRUD service functions."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions.base import ConflictException, NotFoundException, ValidationException
from app.models import AuditLog, Document, FGPN, Project, PurchaseOrder, PurchaseOrderLine, PurchaseOrderVersion
from app.repositories.bom_repository import _get_system_user
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectDeactivateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)


def list_projects(db: Session) -> ProjectListResponse:
    projects = db.execute(select(Project).order_by(Project.project_code)).scalars().all()
    items = [_to_response(db, project) for project in projects]
    return ProjectListResponse(items=items, total=len(items))


def get_project(db: Session, project_id: int) -> ProjectResponse:
    return _to_response(db, _get_project(db, project_id))


def create_project(db: Session, request: ProjectCreateRequest) -> ProjectResponse:
    if db.execute(select(Project).where(Project.project_code == request.project_code)).scalar_one_or_none():
        raise ConflictException(f"Project {request.project_code} already exists.")

    now = dt.datetime.now()
    owner_id = uuid.UUID(request.launch_engineer_user_id) if request.launch_engineer_user_id else _get_system_user(db)
    project = Project(
        project_code=request.project_code.strip(),
        name=request.name.strip(),
        launch_engineer_user_id=owner_id,
        status="Active",
        jit_customer=_clean(request.jit_customer),
        oem_customer=_clean(request.oem_customer),
        contact_name=_clean(request.contact_name),
        contact_email=_clean(request.contact_email),
        contact_phone=_clean(request.contact_phone),
        car_model=_clean(request.car_model),
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.flush()
    _audit(db, "PROJECT_CREATED", project.project_id, f"{project.project_code} created")
    db.commit()
    db.refresh(project)
    return _to_response(db, project)


def update_project(db: Session, project_id: int, request: ProjectUpdateRequest) -> ProjectResponse:
    project = _get_project(db, project_id)
    for field in (
        "name",
        "jit_customer",
        "oem_customer",
        "contact_name",
        "contact_email",
        "contact_phone",
        "car_model",
        "status",
    ):
        value = getattr(request, field)
        if value is not None:
            setattr(project, field, value.strip() if isinstance(value, str) else value)
    project.updated_at = dt.datetime.now()
    _audit(db, "PROJECT_UPDATED", project.project_id, f"{project.project_code} updated")
    db.commit()
    db.refresh(project)
    return _to_response(db, project)


def delete_project(db: Session, project_id: int) -> None:
    project = _get_project(db, project_id)
    linked = _linked_po_count(db, project.project_id)
    if linked:
        raise ConflictException(
            "Project has linked purchase orders and must be deactivated with a meeting document.",
            details={"linked_po_count": linked},
        )
    _audit(db, "PROJECT_DELETED", project.project_id, f"{project.project_code} deleted before PO upload")
    db.delete(project)
    db.commit()


def deactivate_project(db: Session, project_id: int, request: ProjectDeactivateRequest) -> ProjectResponse:
    project = _get_project(db, project_id)
    document = db.get(Document, request.meeting_document_id)
    if document is None:
        raise NotFoundException(f"Meeting document {request.meeting_document_id} not found.")
    project.status = "Inactive"
    project.deactivated_at = dt.datetime.now()
    project.deactivation_document_id = document.document_id
    project.updated_at = project.deactivated_at
    _audit(db, "PROJECT_DEACTIVATED", project.project_id, request.reason)
    db.commit()
    db.refresh(project)
    return _to_response(db, project)


def _get_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundException(f"Project {project_id} not found.")
    return project


def _linked_po_count(db: Session, project_id: int) -> int:
    return db.execute(
        select(func.count(func.distinct(PurchaseOrder.po_id)))
        .join(PurchaseOrderVersion, PurchaseOrderVersion.po_id == PurchaseOrder.po_id)
        .join(PurchaseOrderLine, PurchaseOrderLine.po_version_id == PurchaseOrderVersion.po_version_id)
        .join(FGPN, FGPN.fgpn_id == PurchaseOrderLine.fgpn_id)
        .where(FGPN.project_id == project_id)
    ).scalar_one()


def _to_response(db: Session, project: Project) -> ProjectResponse:
    return ProjectResponse(
        project_id=project.project_id,
        project_code=project.project_code,
        name=project.name,
        launch_engineer_user_id=str(project.launch_engineer_user_id),
        status=project.status,
        jit_customer=project.jit_customer,
        oem_customer=project.oem_customer,
        contact_name=project.contact_name,
        contact_email=project.contact_email,
        contact_phone=project.contact_phone,
        car_model=project.car_model,
        created_at=project.created_at,
        updated_at=project.updated_at,
        deactivated_at=project.deactivated_at,
        deactivation_document_id=project.deactivation_document_id,
        linked_po_count=_linked_po_count(db, project.project_id),
    )


def _clean(value: str | None) -> str | None:
    cleaned = value.strip() if value else None
    return cleaned or None


def _audit(db: Session, action: str, entity_id: int, details: str) -> None:
    db.add(
        AuditLog(
            user_id=_get_system_user(db),
            action=action,
            entity_type="Project",
            entity_id=entity_id,
            timestamp=dt.datetime.now(),
            reason="Project lifecycle workflow",
            details=details,
        )
    )
