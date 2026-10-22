"""Policy decision engine.

This module keeps role checks and business decisions out of route handlers and
services. Client-specific policy modules can later wrap or replace this engine
without changing the generic ERP core.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.exceptions.base import ForbiddenException
from app.policies.context import PolicyActor
from app.policies.permissions import Permission, ROLE_PERMISSIONS, normalize_role
from app.policies.rules import can_approve_purchase_order


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


class PolicyEngine:
    """Simple RBAC plus reusable business-rule checks."""

    def can(
        self,
        actor: PolicyActor,
        permission: Permission,
        *,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        if actor.is_system:
            return PolicyDecision(True, "system actor")

        try:
            role = normalize_role(actor.role)
        except ValueError:
            return PolicyDecision(False, "unknown role")

        if permission not in ROLE_PERMISSIONS.get(role, frozenset()):
            return PolicyDecision(False, f"role {role} lacks {permission}")

        if permission == "po.approve":
            amount = _decimal_context_value(context, "amount", default=Decimal("0"))
            if not can_approve_purchase_order(actor, amount):
                return PolicyDecision(False, f"approval amount {amount} exceeds role threshold")

        return PolicyDecision(True, "allowed")

    def require(
        self,
        actor: PolicyActor,
        permission: Permission,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        decision = self.can(actor, permission, context=context)
        if not decision.allowed:
            raise ForbiddenException(
                "The current user is not allowed to perform this action.",
                details={"permission": permission, "reason": decision.reason},
            )


def _decimal_context_value(
    context: dict[str, Any] | None,
    key: str,
    *,
    default: Decimal,
) -> Decimal:
    if context is None or context.get(key) in (None, ""):
        return default
    return Decimal(str(context[key]))


policy_engine = PolicyEngine()
