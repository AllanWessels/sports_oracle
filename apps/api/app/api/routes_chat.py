"""Streaming chat endpoint (Server-Sent Events)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from langchain_core.messages import HumanMessage
from sse_starlette.sse import EventSourceResponse

from sports_oracle_shared import ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def _chunk_text(content) -> str:
    """Extract plain text from an AIMessageChunk content (str or block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _sse(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data, default=str)}


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    graph = request.app.state.graph
    conv_id = req.conversation_id

    async def event_stream():
        citations: list = []
        prediction = None
        out_conv_id = conv_id
        config = {"configurable": {"thread_id": conv_id or "new"}}
        inputs = {"query": req.message, "conversation_id": conv_id,
                  "messages": [HumanMessage(content=req.message)]}
        try:
            async for ev in graph.astream_events(inputs, config=config, version="v2"):
                kind = ev["event"]
                if kind == "on_chat_model_stream" and "synthesis" in (ev.get("tags") or []):
                    text = _chunk_text(ev["data"]["chunk"].content)
                    if text:
                        yield _sse("token", {"text": text})
                elif kind == "on_tool_start":
                    yield _sse("tool", {"name": ev.get("name", "tool"), "status": "calling"})
                elif kind == "on_chain_end":
                    name = ev.get("name")
                    out = ev["data"].get("output") or {}
                    if not isinstance(out, dict):
                        continue
                    if name == "classify_and_cache":
                        yield _sse("intent", {"intent": out.get("intent", "factual")})
                        if out.get("cache_hit"):
                            yield _sse("token", {"text": out["cache_hit"].get("answer", "")})
                    elif name == "reason_predict" and out.get("prediction") is not None:
                        prediction = out["prediction"]
                        yield _sse("prediction", prediction.model_dump(mode="json"))
                    elif name in ("synthesize", "stream_cached"):
                        for c in out.get("citations", []) or []:
                            payload = c.model_dump(mode="json") if hasattr(c, "model_dump") else c
                            citations.append(payload)
                            yield _sse("citation", payload)
                    elif name == "persist_and_cache":
                        out_conv_id = out.get("conversation_id", out_conv_id)
            yield _sse("done", {"conversation_id": out_conv_id})
        except Exception as exc:  # noqa: BLE001
            logger.exception("chat stream failed")
            yield _sse("error", {"message": str(exc)})

    return EventSourceResponse(event_stream())
