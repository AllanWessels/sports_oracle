"""MCP Sports server entry point.

Transport selection via ``MCP_TRANSPORT`` env var:
  - ``streamable-http`` (default) — listens on ``MCP_HOST:MCP_PORT/mcp``
  - ``stdio``                     — for local process-based clients

Usage:
    python server.py
    MCP_TRANSPORT=stdio python server.py
"""

from __future__ import annotations

import logging
import os
import sys

# Ensure the app root is on sys.path so relative imports work whether the
# server is run directly or via ``python -m``.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from mcp.server.fastmcp import FastMCP  # noqa: E402

import tools.fixtures as fixtures_mod  # noqa: E402
import tools.h2h as h2h_mod  # noqa: E402
import tools.injuries as injuries_mod  # noqa: E402
import tools.odds as odds_mod  # noqa: E402
import tools.search as search_mod  # noqa: E402
import tools.standings as standings_mod  # noqa: E402
import tools.stats as stats_mod  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
_PORT = int(os.environ.get("MCP_PORT", "8765"))
_TRANSPORT = os.environ.get("MCP_TRANSPORT", "streamable-http")

# ---------------------------------------------------------------------------
# Instantiate the FastMCP application
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "mcp-sports",
    host=_HOST,
    port=_PORT,
)

# ---------------------------------------------------------------------------
# Register all tool groups
# ---------------------------------------------------------------------------

search_mod.register(mcp)
fixtures_mod.register(mcp)
stats_mod.register(mcp)
standings_mod.register(mcp)
h2h_mod.register(mcp)
injuries_mod.register(mcp)
odds_mod.register(mcp)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.getLogger(__name__).info(
        "Starting mcp-sports server (transport=%s, host=%s, port=%s)",
        _TRANSPORT,
        _HOST,
        _PORT,
    )
    if _TRANSPORT == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http")
