"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient

from kb_engine.api.main import app
from kb_engine.api.routers import health as health_router
from kb_engine.config.settings import Settings


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

    def test_readiness_check(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test readiness check endpoint."""
        class DummyTraceability:
            async def list_documents(self, limit: int = 1):
                return []

        class DummyVector:
            async def get_collection_info(self):
                return {"count": 0}

        class DummyFactory:
            def __init__(self, settings):
                self._settings = settings

            async def get_traceability_repository(self):
                return DummyTraceability()

            async def get_vector_repository(self):
                return DummyVector()

            async def get_graph_repository(self):
                return None

            async def close(self):
                return None

        def fake_settings() -> Settings:
            return Settings(
                _env_file=None,
                profile="local",
                traceability_store="sqlite",
                vector_store="chroma",
                graph_store="none",
            )

        monkeypatch.setattr(health_router, "RepositoryFactory", DummyFactory)
        monkeypatch.setattr(health_router, "get_settings", fake_settings)

        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["checks"] == {"traceability": "ok", "vector": "ok", "graph": "skipped"}

    def test_liveness_check(self, client: TestClient) -> None:
        """Test liveness check endpoint."""
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
