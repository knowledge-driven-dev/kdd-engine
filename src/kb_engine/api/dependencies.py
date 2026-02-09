"""FastAPI dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends, Request

from kb_engine.config import Settings, get_settings
from kb_engine.services.indexing import IndexingService
from kb_engine.services.retrieval import RetrievalService


def get_settings_dep() -> Settings:
    """Get application settings."""
    return get_settings()


async def get_indexing_service(request: Request) -> IndexingService:
    """Get the indexing service from app state."""
    if hasattr(request.app.state, "indexing_service"):
        return request.app.state.indexing_service

    # Initialize on first request using the profile-based factory
    settings = get_settings()
    service = await _create_indexing_service(settings)
    request.app.state.indexing_service = service
    return service


async def get_retrieval_service(request: Request) -> RetrievalService:
    """Get the retrieval service from app state."""
    if hasattr(request.app.state, "retrieval_service"):
        return request.app.state.retrieval_service

    settings = get_settings()
    service = await _create_retrieval_service(settings)
    request.app.state.retrieval_service = service
    return service


async def _create_indexing_service(settings: Settings) -> IndexingService:
    """Create the indexing service based on settings profile."""
    from kb_engine.embedding.config import EmbeddingConfig
    from kb_engine.pipelines.indexation import IndexationPipeline
    from kb_engine.repositories.factory import RepositoryFactory

    factory = RepositoryFactory(settings)
    traceability = await factory.get_traceability_repository()
    vector = await factory.get_vector_repository()
    graph_strategy = await factory.get_graph_strategy()

    embedding_config = EmbeddingConfig(
        provider=settings.embedding_provider,
        local_model_name=settings.local_embedding_model,
        openai_model=settings.openai_embedding_model,
    )

    pipeline = IndexationPipeline(
        traceability_repo=traceability,
        vector_repo=vector,
        graph_strategy=graph_strategy,
        embedding_config=embedding_config,
    )

    return IndexingService(pipeline=pipeline)


async def _create_retrieval_service(settings: Settings) -> RetrievalService:
    """Create the retrieval service based on settings profile."""
    from kb_engine.embedding.config import EmbeddingConfig
    from kb_engine.pipelines.inference.pipeline import RetrievalPipeline
    from kb_engine.repositories.factory import RepositoryFactory

    factory = RepositoryFactory(settings)
    traceability = await factory.get_traceability_repository()
    vector = await factory.get_vector_repository()
    graph = await factory.get_graph_repository()

    embedding_config = EmbeddingConfig(
        provider=settings.embedding_provider,
        local_model_name=settings.local_embedding_model,
        openai_model=settings.openai_embedding_model,
    )

    pipeline = RetrievalPipeline(
        traceability_repo=traceability,
        vector_repo=vector,
        graph_repo=graph,
        embedding_config=embedding_config,
    )

    return RetrievalService(pipeline=pipeline)


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
IndexingServiceDep = Annotated[IndexingService, Depends(get_indexing_service)]
RetrievalServiceDep = Annotated[RetrievalService, Depends(get_retrieval_service)]
