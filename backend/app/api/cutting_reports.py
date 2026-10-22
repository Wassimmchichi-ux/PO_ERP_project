"""CutMan source uploads and explicitly reviewed consumption posting."""
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.dependencies.auth import actor_user_id_or_system, get_current_policy_actor
from app.dependencies.db import get_db
from app.exceptions.base import NotFoundException, ValidationException
from app.models import CuttingReportImport
from app.policies import PolicyActor, policy_engine
from app.schemas.cutting_report import CuttingReportPostRequest, CuttingReportResponse
from app.services import cutting_report_service

router = APIRouter(prefix="/stock/cutting-reports", tags=["stock"])


@router.get("", response_model=list[CuttingReportResponse])
def list_reports(db: Annotated[Session, Depends(get_db)], actor: Annotated[PolicyActor, Depends(get_current_policy_actor)]):
    return cutting_report_service.list_reports(db, actor=actor)


@router.post("", response_model=CuttingReportResponse)
async def import_report(db: Annotated[Session, Depends(get_db)], actor: Annotated[PolicyActor, Depends(get_current_policy_actor)], file: UploadFile = File(...)):
    policy_engine.require(actor, "stock.cutman.import")
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise ValidationException("Cutting report exceeds the 20 MB limit.")
    return cutting_report_service.import_report(db, content, file.filename or "report.xlsx", actor_user_id_or_system(db, actor), actor=actor)


@router.post("/{report_id}/post", response_model=CuttingReportResponse)
def post_report(report_id: int, request: CuttingReportPostRequest,
    db: Annotated[Session, Depends(get_db)], actor: Annotated[PolicyActor, Depends(get_current_policy_actor)]):
    policy_engine.require(actor, "stock.cutman.import")
    return cutting_report_service.post_report(db, report_id, request, actor_user_id_or_system(db, actor), actor=actor)


@router.get("/{report_id}/source")
def download_source(report_id: int, db: Annotated[Session, Depends(get_db)], actor: Annotated[PolicyActor, Depends(get_current_policy_actor)]):
    policy_engine.require(actor, "stock.view")
    report = db.get(CuttingReportImport, report_id)
    if report is None:
        raise NotFoundException(f"Cutting report {report_id} not found.")
    return Response(content=report.source_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="cutting-report-{report_id}.xlsx"'})
