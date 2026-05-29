"""Health and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict:
    state = request.app.state
    tools_ready = bool(getattr(state, "tools", None))
    graph_ready = getattr(state, "graph", None) is not None
    ok = tools_ready and graph_ready
    return {
        "status": "ready" if ok else "starting",
        "mcp_tools": tools_ready,
        "graph": graph_ready,
    }
