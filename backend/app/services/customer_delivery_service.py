"""Customer delivery service functions."""
from __future__ import annotations

import datetime as dt
import shutil
from decimal import Decimal
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exceptions.base import NotFoundException, ValidationException
from app.models import AuditLog, Document, FGPN, Launch, LaunchFGPN, Project
from app.repositories.bom_repository import _get_system_user
from app.schemas.customer_delivery import (
    CustomerDeliveryConfirmResponse,
    CustomerDeliveryLineRequest,
    CustomerDeliveryRequest,
    LaunchDeliveryListResponse,
    LaunchDeliveryResponse,
    LaunchFgpnDeliveryResponse,
)

UPLOAD_ROOT = Path("uploads") / "cmr"


def list_launches_for_delivery(db: Session) -> LaunchDeliveryListResponse:
    launches = db.execute(
        select(Launch)
        .options(
            selectinload(Launch.cmr_document),
            selectinload(Launch.launch_fgpns).selectinload(LaunchFGPN.fgpn).selectinload(FGPN.project),
        )
        .order_by(Launch.planned_date.desc(), Launch.launch_id.desc())
    ).scalars().all()
    items = [_to_response(launch) for launch in launches]
    return LaunchDeliveryListResponse(items=items, total=len(items))


def confirm_customer_delivery(
    db: Session,
    launch_id: int,
    request: CustomerDeliveryRequest,
    cmr_file: UploadFile,
    uploaded_by: str | None,
) -> CustomerDeliveryConfirmResponse:
    launch = _get_launch(db, launch_id)
    if not cmr_file.filename:
        raise ValidationException("A signed CMR PDF is required.")
    if not cmr_file.filename.lower().endswith(".pdf"):
        raise ValidationException("Customer delivery CMR must be uploaded as a PDF.")

    lines_by_id = {line.launch_fgpn_id: line for line in launch.launch_fgpns}
    for line_request in request.lines:
        line = lines_by_id.get(line_request.launch_fgpn_id)
        if line is None:
            raise ValidationException(
                f"Launch FGPN {line_request.launch_fgpn_id} does not belong to launch {launch_id}."
            )
        remaining = Decimal(line.planned_quantity) - Decimal(line.delivered_quantity)
        if line_request.delivered_quantity > remaining:
            raise ValidationException(
                f"Delivered quantity for {line.fgpn.fgpn_code} exceeds remaining quantity.",
                details={"remaining_quantity": str(remaining)},
            )

    user_id = _get_system_user(db)
    now = dt.datetime.now()
    safe_name = Path(cmr_file.filename).name.replace(" ", "_")
    stored_name = f"LAUNCH-{launch.launch_id}_{now:%Y%m%d%H%M%S}_{safe_name}"
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_ROOT / stored_name
    with stored_path.open("wb") as target:
        shutil.copyfileobj(cmr_file.file, target)

    document = Document(
        document_type="CMR",
        file_name=safe_name,
        file_path=str(stored_path),
        uploaded_at=now,
        uploaded_by=user_id,
    )
    db.add(document)
    db.flush()

    for line_request in request.lines:
        line = lines_by_id[line_request.launch_fgpn_id]
        line.delivered_quantity = Decimal(line.delivered_quantity) + line_request.delivered_quantity
        line.last_customer_delivery_at = now

    launch.cmr_document_id = document.document_id
    launch.customer_delivered_at = now
    if all(Decimal(line.delivered_quantity) >= Decimal(line.planned_quantity) for line in launch.launch_fgpns):
        launch.status = "DELIVERED"
        launch.delivered_at = now
    else:
        launch.status = "IN_PROGRESS"
    launch.updated_at = now

    _audit(
        db,
        launch.launch_id,
        f"CMR {document.file_name} uploaded by {uploaded_by or 'system'} for {len(request.lines)} FGPN line(s)",
    )
    db.commit()
    db.refresh(document)
    db.refresh(launch)

    return CustomerDeliveryConfirmResponse(
        document_id=document.document_id,
        file_name=document.file_name,
        uploaded_at=document.uploaded_at,
        launch=_to_response(_get_launch(db, launch_id)),
    )


def _get_launch(db: Session, launch_id: int) -> Launch:
    launch = db.execute(
        select(Launch)
        .options(
            selectinload(Launch.cmr_document),
            selectinload(Launch.launch_fgpns).selectinload(LaunchFGPN.fgpn).selectinload(FGPN.project),
        )
        .where(Launch.launch_id == launch_id)
    ).scalar_one_or_none()
    if launch is None:
        raise NotFoundException(f"Launch {launch_id} not found.")
    return launch


def _to_response(launch: Launch) -> LaunchDeliveryResponse:
    project = _project_for_launch(launch)
    cmr = launch.cmr_document
    return LaunchDeliveryResponse(
        launch_id=launch.launch_id,
        simulation_id=launch.simulation_id,
        project_id=project.project_id if project else None,
        project_code=project.project_code if project else None,
        project_name=project.name if project else None,
        status=launch.status,
        planned_date=launch.planned_date.isoformat(),
        cmr_document_id=launch.cmr_document_id,
        cmr_file_name=cmr.file_name if cmr else None,
        customer_delivered_at=launch.customer_delivered_at,
        lines=[
            LaunchFgpnDeliveryResponse(
                launch_fgpn_id=line.launch_fgpn_id,
                fgpn_id=line.fgpn_id,
                fgpn_code=line.fgpn.fgpn_code,
                description=line.fgpn.description,
                planned_quantity=line.planned_quantity,
                delivered_quantity=line.delivered_quantity,
                remaining_quantity=Decimal(line.planned_quantity) - Decimal(line.delivered_quantity),
            )
            for line in sorted(launch.launch_fgpns, key=lambda item: item.launch_fgpn_id)
        ],
    )


def _project_for_launch(launch: Launch) -> Project | None:
    first = next(iter(launch.launch_fgpns), None)
    return first.fgpn.project if first and first.fgpn else None


def _audit(db: Session, entity_id: int, details: str) -> None:
    db.add(
        AuditLog(
            user_id=_get_system_user(db),
            action="CUSTOMER_DELIVERY_CONFIRMED",
            entity_type="Launch",
            entity_id=entity_id,
            timestamp=dt.datetime.now(),
            reason="Customer delivery workflow",
            details=details,
        )
    )
