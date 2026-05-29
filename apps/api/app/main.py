"""FastAPI entrypoint: lifespan wiring + routes."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import build_graph
from app.api import routes_chat, routes_health, routes_history
from app.config import get_settings
from app.mcp.client import init_mcp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # 1. Load MCP sports tools (retry-tolerant; the app still starts if it fails).
    try:
        app.state.tools = await init_mcp()
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCP tools failed to load at startup: %s", exc)
        app.state.tools = []

    # 2. Ensure RAG collections exist (best-effort).
    try:
        from sports_oracle_rag import ensure_collections  # type: ignore

        await ensure_collections()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Qdrant collection setup skipped: %s", exc)

    # 3. Postgres checkpointer for conversation memory (best-effort).
    checkpointer = None
    cm = None
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        cm = AsyncPostgresSaver.from_conn_string(settings.checkpoint_dsn)
        checkpointer = await cm.__aenter__()
        await checkpointer.setup()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Postgres checkpointer unavailable, running stateless: %s", exc)
        checkpointer = None

    # 4. Build the agent graph.
    app.state.graph = build_graph(checkpointer=checkpointer)
    logger.info("Sports Oracle API ready (tools=%d)", len(app.state.tools))

    yield

    if cm is not None:
        try:
            await cm.__aexit__(None, None, None)
        except Exception:  # noqa: BLE001
            pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Sports Oracle API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin, "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_health.router)
    app.include_router(routes_chat.router)
    app.include_router(routes_history.router)
    return app


app = create_app()
