"""Simulation API router."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.schemas.simulation import (
    LaunchReviewResult,
    LaunchSimulationResponse,
    SimulationPreviewRequest, 
    SimulationPreviewResult,
    SimulationSaveRequest,
    SimulationSaveResponse
)
from app.services import material_simulation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulations", tags=["simulation"])


@router.post("/preview", response_model=SimulationPreviewResult)
def preview_simulation(
    request: SimulationPreviewRequest,
    db: Annotated[Session, Depends(get_db)]
) -> SimulationPreviewResult:
    """Run a read-only material simulation based on requested FGPNs and allocation strategy."""
    return material_simulation_service.preview_simulation(db, request)


@router.post("", response_model=SimulationSaveResponse, status_code=status.HTTP_201_CREATED)
def save_simulation(
    request: SimulationSaveRequest,
    db: Annotated[Session, Depends(get_db)]
) -> SimulationSaveResponse:
    """Save an official simulation result and its stock allocations."""
    # Dummy user id for now until authentication is added
    from app.repositories.bom_repository import _get_system_user
    user_id = str(_get_system_user(db))
    return material_simulation_service.save_simulation(db, request, user_id)


@router.post("/{simulation_id}/launch-review", response_model=LaunchReviewResult)
def review_simulation_for_launch(
    simulation_id: int,
    db: Annotated[Session, Depends(get_db)]
) -> LaunchReviewResult:
    """Review whether a saved simulation can still be launched with current stock."""
    return material_simulation_service.review_simulation_for_launch(db, simulation_id)


@router.post("/{simulation_id}/launch", response_model=LaunchSimulationResponse)
def launch_saved_simulation(
    simulation_id: int,
    db: Annotated[Session, Depends(get_db)]
) -> LaunchSimulationResponse:
    """Confirm a saved simulation as a launch and issue stock to production."""
    return material_simulation_service.launch_saved_simulation(db, simulation_id)
