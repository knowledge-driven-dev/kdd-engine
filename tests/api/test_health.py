"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient

from kb_engine.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.mark.api
class TestHealthEndpoints:
    """Tests for health endpoints."""

    def test_health_check(self, client: TestClient) -> None:
        """Test basic health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_readiness_check(self, client: TestClient) -> None:
        """Test readiness check endpoint."""
        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # May include additional checks info
        if "checks" in data:
            assert all(v == "ok" for v in data["checks"].values())

    def test_liveness_check(self, client: TestClient) -> None:
        """Test liveness check endpoint."""
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
