"""Application settings using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # General
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Profile: "local" (SQLite+ChromaDB) or "server" (PostgreSQL+Qdrant+Neo4j)
    profile: str = "local"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # --- Traceability store ---
    traceability_store: str = "sqlite"  # "sqlite" | "postgres"

    # SQLite (local profile)
    sqlite_path: str = "~/.kb-engine/kb.db"

    # PostgreSQL (server profile)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "kb_engine"
    postgres_password: str = "changeme"
    postgres_db: str = "kb_engine"
    database_url: str | None = None

    # --- Vector store ---
    vector_store: str = "chroma"  # "chroma" | "qdrant"

    # ChromaDB (local profile)
    chroma_path: str = "~/.kb-engine/chroma"

    # Qdrant (server profile)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_api_key: str | None = None
    qdrant_collection: str = "kb_engine_embeddings"

    # --- Graph store ---
    graph_store: str = "falkordb"  # "sqlite" | "neo4j" | "falkordb" | "none"

    # FalkorDB (local profile)
    falkordb_path: str = "~/.kb-engine/graph.db"

    # Neo4j (server profile)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"

    # --- Embeddings (independent of profile) ---
    embedding_provider: str = "local"  # "local" | "openai"
    local_embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # OpenAI
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4-turbo-preview"

    # Chunking
    chunk_size_min: int = 100
    chunk_size_target: int = 512
    chunk_size_max: int = 1024
    chunk_overlap: int = 50

    # Extraction
    extraction_use_llm: bool = False
    extraction_confidence_threshold: float = 0.7

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Build database URL if not provided (server profile)
        if self.database_url is None and self.traceability_store == "postgres":
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        # Resolve paths
        self.sqlite_path = str(Path(self.sqlite_path).expanduser())
        self.chroma_path = str(Path(self.chroma_path).expanduser())
        self.falkordb_path = str(Path(self.falkordb_path).expanduser())
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate cross-field configuration."""
        profile = self.profile.lower()
        traceability = self.traceability_store.lower()
        vector = self.vector_store.lower()
        graph = self.graph_store.lower()

        if profile not in {"local", "server"}:
            raise ValueError(f"Unknown profile: {self.profile}")

        if profile == "local":
            if traceability != "sqlite":
                raise ValueError("profile=local requires traceability_store=sqlite")
            if vector != "chroma":
                raise ValueError("profile=local requires vector_store=chroma")
            if graph not in {"sqlite", "falkordb", "none"}:
                raise ValueError("profile=local requires graph_store=sqlite|falkordb|none")
        elif profile == "server":
            if traceability != "postgres":
                raise ValueError("profile=server requires traceability_store=postgres")
            if vector != "qdrant":
                raise ValueError("profile=server requires vector_store=qdrant")
            if graph not in {"neo4j", "none"}:
                raise ValueError("profile=server requires graph_store=neo4j|none")

        if traceability == "postgres" and not self.database_url:
            raise ValueError("database_url is required when traceability_store=postgres")

        if self.embedding_provider.lower() == "openai" and not self.openai_api_key:
            raise ValueError("openai_api_key is required when embedding_provider=openai")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def is_local_profile(self) -> bool:
        return self.profile.lower() == "local"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
