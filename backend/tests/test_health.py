"""Smoke test for the health check endpoint."""
from fastapi.testclient import TestClient


def test_health_check_returns_healthy(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
