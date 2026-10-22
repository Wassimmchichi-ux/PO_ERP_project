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
)
from app.services import material_simulation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulations", tags=["simulation"])


@router.post("/preview", response_model=SimulationPreviewResult)
def preview_simulation(
    request: SimulationPreviewRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[PolicyActor, Depends(get_current_policy_actor)],
) -> SimulationPreviewResult:
    """Run a read-only material simulation based on requested FGPNs and allocation strategy."""
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
