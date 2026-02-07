"""Repository configuration models."""

from pydantic import BaseModel, Field


class FileTypeConfig(BaseModel):
    """Configuration for how a file type should be parsed and chunked."""

    parser: str = "markdown"  # "markdown" | "json" | "yaml" | "rst" | "plaintext"
    mime_type: str = "text/markdown"


EXTENSION_DEFAULTS: dict[str, FileTypeConfig] = {
    ".md": FileTypeConfig(parser="markdown", mime_type="text/markdown"),
    ".json": FileTypeConfig(parser="json", mime_type="application/json"),
    ".yaml": FileTypeConfig(parser="yaml", mime_type="text/yaml"),
    ".yml": FileTypeConfig(parser="yaml", mime_type="text/yaml"),
    ".rst": FileTypeConfig(parser="rst", mime_type="text/x-rst"),
    ".txt": FileTypeConfig(parser="plaintext", mime_type="text/plain"),
}


class RepositoryConfig(BaseModel):
    """Configuration for a Git repository to index."""

    name: str
    local_path: str
    remote_url: str | None = None
    branch: str = "main"
    include_patterns: list[str] = Field(default_factory=lambda: ["**/*.md"])
    exclude_patterns: list[str] = Field(default_factory=list)
    base_url_template: str | None = None  # e.g. "{remote}/blob/{branch}/{path}"
    file_type_config: dict[str, FileTypeConfig] = Field(
        default_factory=lambda: {".md": FileTypeConfig()}
    )
