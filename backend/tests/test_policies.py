"""Tests for centralized ERP policy behavior."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.exceptions.base import ForbiddenException
from app.policies import PolicyActor, normalize_role, policy_engine, system_actor
from app.policies.rules import is_assignable_stock_owner


def test_policy_normalizes_backend_and_legacy_role_labels() -> None:
    assert normalize_role("LAUNCH ENGINEER") == "LAUNCH_ENGINEER"
    assert normalize_role("WAREHOUSE_Personnel") == "WAREHOUSE_PERSONNEL"


def test_rbac_allows_launch_engineer_bom_upload_but_denies_warehouse_personnel() -> None:
    launch_engineer = PolicyActor(user_id=None, role="LAUNCH_ENGINEER")
    warehouse_user = PolicyActor(user_id=None, role="WAREHOUSE_PERSONNEL")

    assert policy_engine.can(launch_engineer, "bom.upload").allowed is True
    assert policy_engine.can(warehouse_user, "bom.upload").allowed is False

    with pytest.raises(ForbiddenException):
        policy_engine.require(warehouse_user, "bom.upload")


def test_purchase_order_approval_thresholds_are_role_based() -> None:
    engineer = PolicyActor(user_id=None, role="LAUNCH_ENGINEER")
    manager = PolicyActor(user_id=None, role="LAUNCH_MANAGER")

    assert policy_engine.can(engineer, "po.approve", context={"amount": Decimal("4999.99")}).allowed
    assert not policy_engine.can(engineer, "po.approve", context={"amount": Decimal("5000.01")}).allowed
    assert policy_engine.can(manager, "po.approve", context={"amount": Decimal("20000")}).allowed


def test_stock_owner_rule_is_reusable_outside_routes() -> None:
    assert is_assignable_stock_owner("LAUNCH_MANAGER") is True
    assert is_assignable_stock_owner("LAUNCH ENGINEER") is True
    assert is_assignable_stock_owner("WAREHOUSE_TEAM_LEADER") is False


def test_system_actor_preserves_current_prototype_behavior() -> None:
    assert policy_engine.can(system_actor(), "po.import", context={"amount": Decimal("999999")}).allowed
