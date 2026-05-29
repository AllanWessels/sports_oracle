"""Tool-gathering node: bind MCP tools to Claude and run the tool-calling loop."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.agent.llm import predict_model
from app.agent.prompts import PLANNER_SYSTEM
from app.agent.state import OracleState
from app.config import get_settings
from app.mcp import client as mcp_client

logger = logging.getLogger(__name__)


def _tool_map() -> dict:
    return {t.name: t for t in mcp_client.get_tools()}


async def _run_tool_loop(query: str, tools: list, system: str) -> list[dict]:
    """Let Claude call MCP tools until it stops; collect serialized envelopes."""
    settings = get_settings()
    model = predict_model().bind_tools(tools) if tools else predict_model()
    tool_map = {t.name: t for t in tools}
    messages = [SystemMessage(content=system), HumanMessage(content=query)]
    collected: list[dict] = []

    for _ in range(settings.max_tool_iterations):
        ai = await model.ainvoke(messages)
        messages.append(ai)
        calls = getattr(ai, "tool_calls", None) or []
        if not calls:
            break
        for call in calls:
            tool = tool_map.get(call["name"])
            if tool is None:
                continue
            try:
                result = await tool.ainvoke(call["args"])
            except Exception as exc:  # noqa: BLE001 — surface tool failures to the model
                result = json.dumps({"error": str(exc)})
                logger.warning("Tool %s failed: %s", call["name"], exc)
            collected.append(_as_envelope(call["name"], result))
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
    return collected


def _as_envelope(tool_name: str, result) -> dict:
    """Normalize a tool result into a dict we can carry in state for citations."""
    if isinstance(result, dict):
        payload = result
    else:
        try:
            payload = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            payload = {"data": result}
    payload.setdefault("tool", tool_name)
    return payload


async def gather(state: OracleState) -> dict:
    """Factual gather: call all sports tools needed to answer."""
    tools = mcp_client.get_tools()
    results = await _run_tool_loop(state["query"], tools, PLANNER_SYSTEM)
    return {"tool_results": results}
