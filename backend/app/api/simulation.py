"""Simulation API router."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies.auth import actor_user_id_or_system, get_current_policy_actor
from app.dependencies.db import get_db
from app.policies import PolicyActor
from app.schemas.simulation import (
    LaunchReviewResult,
    LaunchSimulationResponse,
    SimulationPreviewRequest,
    SimulationPreviewResult,
    SimulationSaveRequest,
    SimulationSaveResponse,
    SimulationDocumentRequest,
    SimulationOptionsResponse,
    SimulationWorkflowResponse,
)
from app.services import material_simulation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulations", tags=["simulation"])


@router.get("/options/{project_id}", response_model=SimulationOptionsResponse)
def list_simulation_options(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SimulationOptionsResponse:
    """List current outstanding PO/FGPN rows for one project."""
    return material_simulation_service.list_simulation_options(db, project_id, actor=actor)


@router.post("/preview", response_model=SimulationPreviewResult)
def preview_simulation(
    request: SimulationPreviewRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SimulationPreviewResult:
    """Run the ordered multi-PO simulation for the requested FGPN quantities."""
    return material_simulation_service.preview_simulation(db, request, actor=actor)


@router.post("", response_model=SimulationSaveResponse, status_code=status.HTTP_201_CREATED)
def save_simulation(
    request: SimulationSaveRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SimulationSaveResponse:
    """Save an official simulation result and its stock allocations."""
    user_id = str(actor_user_id_or_system(db, actor))
    return material_simulation_service.save_simulation(db, request, user_id, actor=actor)


@router.put("/{simulation_id}/meeting-document", response_model=SimulationWorkflowResponse)
def attach_meeting_document(
    simulation_id: int,
    request: SimulationDocumentRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SimulationWorkflowResponse:
    """Attach the meeting record before the 24-hour reservation expires."""
    return material_simulation_service.attach_meeting_document(
        db, simulation_id, request.mtg_minutes_document_id, actor=actor,
    )


@router.post("/{simulation_id}/release-expired", response_model=SimulationWorkflowResponse)
def release_expired_simulation(
    simulation_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SimulationWorkflowResponse:
    """Release a missing-document reservation after its deadline."""
    return material_simulation_service.release_expired_reservation(
        db, simulation_id, actor=actor,
    )


@router.post("/{simulation_id}/launch-review", response_model=LaunchReviewResult)
def review_simulation_for_launch(
    simulation_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> LaunchReviewResult:
    """Review whether a saved simulation can still be launched with current stock."""
    return material_simulation_service.review_simulation_for_launch(
        db,
        simulation_id,
        actor=actor,
    )


@router.post("/{simulation_id}/launch", response_model=LaunchSimulationResponse)
def launch_saved_simulation(
    simulation_id: int,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> LaunchSimulationResponse:
    """Confirm a saved simulation as a launch and issue stock to production."""
    return material_simulation_service.launch_saved_simulation(db, simulation_id, actor=actor)
