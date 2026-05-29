"""MCP client bootstrap.

Connects to the `mcp-sports` FastMCP server over streamable-HTTP and exposes its
tools as LangChain `StructuredTool`s (via langchain-mcp-adapters) for binding to
Claude. Tools are loaded once at startup and cached on the app state.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_mcp_adapters.client import MultiServerMCPClient

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[MultiServerMCPClient] = None
_tools: list = []


async def init_mcp() -> list:
    """Create the MCP client and load tools. Idempotent."""
    global _client, _tools
    if _tools:
        return _tools

    settings = get_settings()
    _client = MultiServerMCPClient(
        {
            "sports": {
                "url": settings.mcp_sports_url,
                "transport": settings.mcp_transport,
            }
        }
    )
    _tools = await _client.get_tools()
    logger.info("Loaded %d MCP sports tools: %s", len(_tools), [t.name for t in _tools])
    return _tools


def get_tools() -> list:
    return _tools


def get_tools_by_name(*names: str) -> list:
    """Return the subset of loaded tools matching the given names."""
    wanted = set(names)
    return [t for t in _tools if t.name in wanted]
