"""Configuration via environment variables for the RAG library."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RagSettings(BaseSettings):
    """All RAG-layer configuration drawn from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Qdrant
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")

    # Embedding models
    embed_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBED_MODEL")
    sparse_model: str = Field(
        default="prithivida/Splade_PP_en_v1", alias="SPARSE_MODEL"
    )
    rerank_model: str = Field(default="BAAI/bge-reranker-base", alias="RERANK_MODEL")

    # Device: auto | cuda | cpu
    embed_device: Literal["auto", "cuda", "cpu"] = Field(
        default="auto", alias="EMBED_DEVICE"
    )

    # Batch size for embedding calls
    embed_batch_size: int = Field(default=64, alias="EMBED_BATCH_SIZE")

    # How many candidates to rerank before slicing to top_k
    rerank_candidates: int = Field(default=20, alias="RERANK_CANDIDATES")


# Module-level singleton — import and use directly
settings = RagSettings()
