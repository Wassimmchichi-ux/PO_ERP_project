"""Authentication-to-policy dependencies.

The current academic prototype does not implement password/token login yet.
For now, API clients may pass one of these headers:

* ``X-ERP-User-Id`` with a database user UUID.
* ``X-ERP-Registration-Number`` with a user registration number.
* ``X-ERP-Role`` with a canonical or legacy role label for demo sessions.

Routes receive a ``PolicyActor`` from this module and pass it to services.
That keeps authentication concerns outside the policy/business-rule layer.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.exceptions.base import UnauthorizedException
from app.models.user import User
from app.policies import PolicyActor, normalize_role, system_actor


def get_current_policy_actor(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[str | None, Header(alias="X-ERP-User-Id")] = None,
    registration_number: Annotated[
        str | None,
        Header(alias="X-ERP-Registration-Number"),
    ] = None,
    role: Annotated[str | None, Header(alias="X-ERP-Role")] = None,
) -> PolicyActor:
    """Resolve the request caller into the small actor object policies need."""

    if user_id:
        try:
            parsed_user_id = uuid.UUID(user_id)
        except ValueError as exc:
            raise UnauthorizedException("X-ERP-User-Id must be a valid UUID.") from exc
        user = db.get(User, parsed_user_id)
        return _actor_from_user(user)

    if registration_number:
        user = (
            db.query(User)
            .filter(User.registration_number == registration_number)
            .one_or_none()
        )
        return _actor_from_user(user)

    if role:
        try:
            normalized_role = normalize_role(role)
        except ValueError as exc:
            raise UnauthorizedException("X-ERP-Role is not a recognized ERP role.") from exc
        return PolicyActor(user_id=None, role=normalized_role)

    return system_actor()


def actor_user_id_or_system(db: Session, actor: PolicyActor) -> uuid.UUID:
    """Return the authenticated user id, falling back to the seeded system user."""

    if actor.user_id is not None:
        return actor.user_id

    from app.repositories.bom_repository import _get_system_user

    return _get_system_user(db)


def _actor_from_user(user: User | None) -> PolicyActor:
    if user is None:
        raise UnauthorizedException("ERP user was not found.")
    if user.status != "ACTIVE" or user.is_locked:
        raise UnauthorizedException("ERP user account is inactive or locked.")
    return PolicyActor(user_id=user.id, role=user.role)
