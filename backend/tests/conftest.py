"""Shared pytest fixtures."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    """A TestClient wrapping a freshly-built app instance.

    Uses ``create_app()`` directly (not the module-level ``app``) so
    each test gets an independently constructed application, which
    matters once dependency overrides (e.g. a fake DB session) are
    introduced in later milestones.
    """
    return TestClient(create_app())
