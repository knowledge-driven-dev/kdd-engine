"""Health check endpoints."""

from fastapi import APIRouter, HTTPException, status

from kb_engine.config import get_settings
from kb_engine.repositories.factory import RepositoryFactory

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check() -> dict[str, str | dict[str, str]]:
    """Readiness check - verifies all dependencies are available."""
    settings = get_settings()
    checks: dict[str, str] = {}
    errors: dict[str, str] = {}
    factory = RepositoryFactory(settings)

    try:
        try:
            traceability = await factory.get_traceability_repository()
            await traceability.list_documents(limit=1)
            checks["traceability"] = "ok"
        except Exception as exc:
            errors["traceability"] = exc.__class__.__name__

        try:
            vector = await factory.get_vector_repository()
            await vector.get_collection_info()
            checks["vector"] = "ok"
        except Exception as exc:
            errors["vector"] = exc.__class__.__name__

        graph_store = settings.graph_store.lower()
        if graph_store == "none":
            checks["graph"] = "skipped"
        elif graph_store == "falkordb":
            try:
                from kb_engine.smart.stores.falkordb_graph import FalkorDBGraphStore

                store = FalkorDBGraphStore(settings.falkordb_path)
                store.initialize()
                store.close()
                checks["graph"] = "ok"
            except Exception as exc:
                errors["graph"] = exc.__class__.__name__
        else:
            try:
                graph = await factory.get_graph_repository()
                if graph is None:
                    checks["graph"] = "skipped"
                else:
                    await graph.find_nodes(limit=1)
                    checks["graph"] = "ok"
            except Exception as exc:
                errors["graph"] = exc.__class__.__name__
    finally:
        await factory.close()

    if errors:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "checks": {**checks, **errors}},
        )

    return {"status": "ok", "checks": checks}


@router.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Liveness check - verifies the service is running."""
    return {"status": "ok"}
