"""System administrator API router."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.schemas.admin import (
    AdminUserCreateRequest,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    ReferenceItemCreateRequest,
    ReferenceItemResponse,
    ReferenceItemUpdateRequest,
    ReferenceListName,
    ReferenceListsResponse,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=AdminUserListResponse)
def list_users(db: Annotated[Session, Depends(get_db)]) -> AdminUserListResponse:
    return admin_service.list_users(db)


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    request: AdminUserCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AdminUserResponse:
    return admin_service.create_user(db, request)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: uuid.UUID,
    request: AdminUserUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AdminUserResponse:
    return admin_service.update_user(db, user_id, request)


@router.post("/users/{user_id}/activate", response_model=AdminUserResponse)
def activate_user(user_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> AdminUserResponse:
    return admin_service.set_user_active(db, user_id, True)


@router.post("/users/{user_id}/deactivate", response_model=AdminUserResponse)
def deactivate_user(user_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> AdminUserResponse:
    return admin_service.set_user_active(db, user_id, False)


@router.post("/users/{user_id}/lock", response_model=AdminUserResponse)
def lock_user(user_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> AdminUserResponse:
    return admin_service.set_user_locked(db, user_id, True)


@router.post("/users/{user_id}/unlock", response_model=AdminUserResponse)
def unlock_user(user_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> AdminUserResponse:
    return admin_service.set_user_locked(db, user_id, False)


@router.post("/users/{user_id}/force-password-reset", response_model=AdminUserResponse)
def force_password_reset(
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> AdminUserResponse:
    return admin_service.force_password_reset(db, user_id)


@router.get("/reference-lists", response_model=ReferenceListsResponse)
def list_reference_items(db: Annotated[Session, Depends(get_db)]) -> ReferenceListsResponse:
    return admin_service.list_reference_items(db)


@router.post(
    "/reference-lists/{list_name}",
    response_model=ReferenceItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reference_item(
    list_name: ReferenceListName,
    request: ReferenceItemCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ReferenceItemResponse:
    return admin_service.create_reference_item(db, list_name, request)


@router.patch("/reference-lists/{list_name}/{item_id}", response_model=ReferenceItemResponse)
def update_reference_item(
    list_name: ReferenceListName,
    item_id: int,
    request: ReferenceItemUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ReferenceItemResponse:
    return admin_service.update_reference_item(db, list_name, item_id, request)
