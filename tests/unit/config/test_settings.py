"""Tests for Settings validation."""

import pytest

from kb_engine.config.settings import Settings


def test_local_profile_requires_local_stores() -> None:
    with pytest.raises(ValueError, match="profile=local requires traceability_store=sqlite"):
        Settings(
            _env_file=None,
            profile="local",
            traceability_store="postgres",
            vector_store="chroma",
            graph_store="none",
        )


def test_server_profile_requires_server_stores() -> None:
    with pytest.raises(ValueError, match="profile=server requires traceability_store=postgres"):
        Settings(
            _env_file=None,
            profile="server",
            traceability_store="sqlite",
            vector_store="qdrant",
            graph_store="neo4j",
        )

    with pytest.raises(ValueError, match="profile=server requires vector_store=qdrant"):
        Settings(
            _env_file=None,
            profile="server",
            traceability_store="postgres",
            vector_store="chroma",
            graph_store="neo4j",
        )

    with pytest.raises(ValueError, match="profile=server requires graph_store=neo4j|none"):
        Settings(
            _env_file=None,
            profile="server",
            traceability_store="postgres",
            vector_store="qdrant",
            graph_store="sqlite",
        )


def test_openai_requires_api_key() -> None:
    with pytest.raises(ValueError, match="openai_api_key is required"):
        Settings(
            _env_file=None,
            profile="local",
            traceability_store="sqlite",
            vector_store="chroma",
            graph_store="none",
            embedding_provider="openai",
            openai_api_key=None,
        )
