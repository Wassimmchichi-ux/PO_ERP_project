"""Policy context objects.

Authentication answers "who is calling?". The policy layer starts after that:
it receives a small actor object and decides what business action is allowed.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.policies.permissions import RoleCode, normalize_role


@dataclass(frozen=True)
class PolicyActor:
    """The minimum user information required by authorization/business rules."""

    user_id: uuid.UUID | None
    role: RoleCode | str
    is_system: bool = False

    @property
    def normalized_role(self) -> RoleCode:
        return normalize_role(self.role)


def system_actor() -> PolicyActor:
    """Internal actor used by prototype routes that do not yet authenticate."""

    return PolicyActor(user_id=None, role="ADMIN", is_system=True)
