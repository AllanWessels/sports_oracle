"""Router node: classify intent + extract entities, and check the semantic cache."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import router_model
from app.agent.prompts import ROUTER_SYSTEM
from app.agent.state import OracleState
from app.services import semantic_cache

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1].lstrip("json").strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return {}


async def classify_and_cache(state: OracleState) -> dict:
    query = state["query"]
    started_at = time.time()  # turn clock starts here, for eval-capture latency

    # 1. Classify intent + entities.
    resp = await router_model().ainvoke(
        [SystemMessage(content=ROUTER_SYSTEM), HumanMessage(content=query)]
    )
    parsed = _extract_json(resp.content if isinstance(resp.content, str) else str(resp.content))
    intent = parsed.get("intent", "factual")
    entities = {
        "sport": parsed.get("sport", "unknown"),
        "teams": parsed.get("teams", []),
        "players": parsed.get("players", []),
        "league": parsed.get("league"),
        "is_upcoming": parsed.get("is_upcoming", False),
    }

    # 2. Semantic cache lookup (skip for predictions — those are time-sensitive).
    cache_hit = None
    if intent == "factual":
        cache_hit = await semantic_cache.lookup(query, entities)

    logger.info("Routed intent=%s entities=%s cache_hit=%s", intent, entities, bool(cache_hit))
    return {
        "intent": intent,
        "entities": entities,
        "cache_hit": cache_hit,
        "started_at": started_at,
    }
