"""Role and permission definitions for the generic ERP core."""
from __future__ import annotations

from typing import Literal

RoleCode = Literal[
    "ADMIN",
    "PLANT_MANAGER",
    "LAUNCH_ENGINEER",
    "LAUNCH_MANAGER",
    "WAREHOUSE_PERSONNEL",
    "WAREHOUSE_TEAM_LEADER",
    "MANUFACTURING_OPERATOR",
]

Permission = Literal[
    "admin.manage_users",
    "admin.reference.write",
    "audit.view",
    "bom.view",
    "bom.upload",
    "customer_delivery.view",
    "customer_delivery.write",
    "document.view",
    "finance.view",
    "finance.write",
    "handover.confirm",
    "handover.create",
    "launch.manage",
    "po.approve",
    "po.import",
    "po.parse",
    "po.update",
    "po.view",
    "project.view",
    "project.write",
    "simulation.run",
    "simulation.view",
    "stock.assign_owner",
    "stock.transit.write",
    "stock.cutman.import",
    "stock.receive",
    "stock.view",
]


_ROLE_ALIASES: dict[str, RoleCode] = {
    "ADMIN": "ADMIN",
    "SYSTEM_ADMINISTRATOR": "ADMIN",
    "SYSTEM ADMINISTRATOR": "ADMIN",
    "PLANT_MANAGER": "PLANT_MANAGER",
    "PLANT MANAGER": "PLANT_MANAGER",
    "LAUNCH_ENGINEER": "LAUNCH_ENGINEER",
    "LAUNCH ENGINEER": "LAUNCH_ENGINEER",
    "LAUNCH_MANAGER": "LAUNCH_MANAGER",
    "LAUNCH MANAGER": "LAUNCH_MANAGER",
    "WAREHOUSE_PERSONNEL": "WAREHOUSE_PERSONNEL",
    "WAREHOUSE_PERSONNEL".replace("_", " "): "WAREHOUSE_PERSONNEL",
    "WAREHOUSE_PERSONnel".upper(): "WAREHOUSE_PERSONNEL",
    "WAREHOUSE_TEAM_LEADER": "WAREHOUSE_TEAM_LEADER",
    "WAREHOUSE TEAM LEADER": "WAREHOUSE_TEAM_LEADER",
    "MANUFACTURING_OPERATOR": "MANUFACTURING_OPERATOR",
    "MANUFACTURING OPERATOR": "MANUFACTURING_OPERATOR",
}


def normalize_role(role: str) -> RoleCode:
    """Normalize legacy/user-facing role labels into canonical policy roles."""

    token = str(role).strip().replace("-", "_")
    token = " ".join(token.split())
    normalized = _ROLE_ALIASES.get(token.upper()) or _ROLE_ALIASES.get(
        token.replace(" ", "_").upper()
    )
    if normalized is None:
        raise ValueError(f"Unknown role code: {role}")
    return normalized


ADMIN_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        "admin.manage_users",
        "admin.reference.write",
        "audit.view",
        "bom.view",
        "bom.upload",
        "customer_delivery.view",
        "customer_delivery.write",
        "document.view",
        "finance.view",
        "finance.write",
        "handover.confirm",
        "handover.create",
        "launch.manage",
        "po.approve",
        "po.import",
        "po.parse",
        "po.update",
        "po.view",
        "project.view",
        "project.write",
        "simulation.run",
        "simulation.view",
        "stock.assign_owner",
        "stock.transit.write",
        "stock.cutman.import",
        "stock.receive",
        "stock.view",
    }
)

ROLE_PERMISSIONS: dict[RoleCode, frozenset[Permission]] = {
    "ADMIN": ADMIN_PERMISSIONS,
    "PLANT_MANAGER": frozenset(
        {
            "audit.view",
            "bom.view",
            "customer_delivery.view",
            "document.view",
            "finance.view",
            "po.approve",
            "po.view",
            "project.view",
            "simulation.view",
            "stock.view",
        }
    ),
    "LAUNCH_MANAGER": frozenset(
        {
            "audit.view",
            "bom.upload",
            "bom.view",
            "customer_delivery.view",
            "customer_delivery.write",
            "document.view",
            "finance.view",
            "finance.write",
            "handover.create",
            "launch.manage",
            "po.approve",
            "po.import",
            "po.parse",
            "po.update",
            "po.view",
            "project.view",
            "project.write",
            "simulation.run",
            "simulation.view",
            "stock.assign_owner",
            "stock.transit.write",
            "stock.cutman.import",
            "stock.view",
        }
    ),
    "LAUNCH_ENGINEER": frozenset(
        {
            "audit.view",
            "bom.upload",
            "bom.view",
            "customer_delivery.view",
            "customer_delivery.write",
            "document.view",
            "finance.view",
            "finance.write",
            "handover.create",
            "po.approve",
            "po.import",
            "po.parse",
            "po.update",
            "po.view",
            "project.view",
            "project.write",
            "simulation.run",
            "simulation.view",
            "stock.assign_owner",
            "stock.transit.write",
            "stock.cutman.import",
            "stock.view",
        }
    ),
    "WAREHOUSE_TEAM_LEADER": frozenset(
        {
            "document.view",
            "handover.confirm",
            "handover.create",
            "stock.receive",
            "stock.view",
        }
    ),
    "WAREHOUSE_PERSONNEL": frozenset({"stock.receive", "stock.view"}),
    "MANUFACTURING_OPERATOR": frozenset({"handover.confirm", "stock.view"}),
}
