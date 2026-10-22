"""Reusable business policy rules for the generic ERP core."""
from __future__ import annotations

from decimal import Decimal

from app.policies.context import PolicyActor
from app.policies.permissions import Permission, RoleCode


PO_APPROVAL_THRESHOLDS: dict[RoleCode, Decimal | None] = {
    "LAUNCH_ENGINEER": Decimal("5000.00"),
    "LAUNCH_MANAGER": Decimal("25000.00"),
    "PLANT_MANAGER": None,
    "ADMIN": None,
}

STOCK_OWNER_ROLES: frozenset[RoleCode] = frozenset(
    {"LAUNCH_ENGINEER", "LAUNCH_MANAGER"}
)


def can_approve_purchase_order(actor: PolicyActor, amount: Decimal) -> bool:
    """Return whether *actor* can approve a PO of *amount*."""

    if amount < 0:
        return False
    threshold = PO_APPROVAL_THRESHOLDS.get(actor.normalized_role)
    if threshold is None:
        return actor.normalized_role in PO_APPROVAL_THRESHOLDS
    return amount <= threshold


def is_assignable_stock_owner(role: RoleCode | str) -> bool:
    """Return whether stock may be assigned to a user with *role*."""

    from app.policies.permissions import normalize_role

    return normalize_role(role) in STOCK_OWNER_ROLES


def requires_active_launch(permission: Permission) -> bool:
    """Business actions that should later be scoped to an active launch."""

    return permission in {
        "bom.upload",
        "handover.create",
        "launch.manage",
        "po.import",
        "po.update",
        "simulation.run",
        "stock.assign_owner",
    }
