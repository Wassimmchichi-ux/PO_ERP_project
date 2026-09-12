"""Project CRUD API router."""
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectDeactivateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
def list_projects(db: Annotated[Session, Depends(get_db)]) -> ProjectListResponse:
    return project_service.list_projects(db)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    return project_service.create_project(db, request)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Annotated[Session, Depends(get_db)]) -> ProjectResponse:
    return project_service.get_project(db, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    request: ProjectUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    return project_service.update_project(db, project_id, request)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Annotated[Session, Depends(get_db)]) -> Response:
    project_service.delete_project(db, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/deactivate", response_model=ProjectResponse)
def deactivate_project(
    project_id: int,
    request: ProjectDeactivateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    return project_service.deactivate_project(db, project_id, request)
