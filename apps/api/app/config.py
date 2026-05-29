"""Application settings, loaded from environment (.env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    anthropic_api_key: str = ""
    model_synth: str = "claude-opus-4-8"
    model_router: str = "claude-sonnet-4-6"
    model_predict: str = "claude-opus-4-8"

    # MCP
    mcp_sports_url: str = "http://mcp-sports:8765/mcp"
    mcp_transport: str = "streamable-http"

    # Postgres
    database_url: str = "postgresql+asyncpg://oracle:oracle@postgres:5432/sports_oracle"

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""

    # RAG
    embed_device: str = "auto"
    cache_sim_threshold: float = 0.92

    # App
    web_origin: str = "http://localhost:5173"
    log_level: str = "info"

    # Agent tuning
    max_tool_iterations: int = 4

    @property
    def checkpoint_dsn(self) -> str:
        """psycopg-style DSN for LangGraph's AsyncPostgresSaver."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
