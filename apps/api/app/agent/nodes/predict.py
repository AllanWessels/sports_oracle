"""Prediction sub-flow: gather signals, build features, reason, blend confidence."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import predict_model
from app.agent.nodes.tools import _run_tool_loop
from app.agent.prompts import PREDICT_SYSTEM
from app.agent.state import OracleState
from app.mcp import client as mcp_client
from sports_oracle_shared import (
    ConfidenceLabel,
    Prediction,
    PredictionFactor,
)

logger = logging.getLogger(__name__)

# Signals we hope to have for a confident prediction. Missing ones reduce
# data-completeness, which in turn caps the blended confidence.
EXPECTED_SIGNALS = ["fixtures", "head_to_head", "standings", "injuries", "odds"]

PREDICT_GATHER_SYSTEM = (
    "Gather the data needed to forecast the upcoming fixture the user asked about. "
    "Resolve both teams with search_entities, then call get_fixtures (recent form + "
    "the upcoming match), get_head_to_head, get_standings, get_injuries, and get_odds. "
    "It is fine if odds or injuries are unavailable."
)


async def gather_predict(state: OracleState) -> dict:
    tools = mcp_client.get_tools()
    results = await _run_tool_loop(state["query"], tools, PREDICT_GATHER_SYSTEM)
    return {"tool_results": results}


def _data_completeness(tool_results: list[dict]) -> float:
    seen = set()
    for r in tool_results:
        name = r.get("tool", "")
        for sig in EXPECTED_SIGNALS:
            if sig in name and r.get("data") is not None:
                seen.add(sig)
    return len(seen) / len(EXPECTED_SIGNALS)


def _odds_agreement(parsed: dict, tool_results: list[dict]) -> float:
    """1.0 when model lean matches market-implied favorite; 0.5 when unknown."""
    odds = next((r for r in tool_results if "odds" in r.get("tool", "")), None)
    data = (odds or {}).get("data")
    if not data:
        return 0.5
    implied = {
        "home": data.get("implied_home"),
        "draw": data.get("implied_draw"),
        "away": data.get("implied_away"),
    }
    implied = {k: v for k, v in implied.items() if v is not None}
    if not implied:
        return 0.5
    market_fav = max(implied, key=implied.get)
    model_p = parsed.get("win_probability", 0.5)
    model_lean = "home" if model_p >= 0.5 else "away"
    return 1.0 if market_fav == model_lean or market_fav == "draw" else 0.6


def _label(score: float) -> ConfidenceLabel:
    if score >= 0.66:
        return ConfidenceLabel.HIGH
    if score >= 0.4:
        return ConfidenceLabel.MEDIUM
    return ConfidenceLabel.LOW


async def reason_predict(state: OracleState) -> dict:
    """Build features, call the predict model, and blend a calibrated confidence."""
    tool_results = state.get("tool_results", [])
    features = {"signals": tool_results, "entities": state.get("entities", {})}

    resp = await predict_model().ainvoke(
        [
            SystemMessage(content=PREDICT_SYSTEM),
            HumanMessage(content=f"Question: {state['query']}\n\nFeatures:\n{json.dumps(features, default=str)[:12000]}"),
        ]
    )
    raw = resp.content if isinstance(resp.content, str) else str(resp.content)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1].lstrip("json").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Predict model returned non-JSON; defaulting to low confidence")
        parsed = {"pick": "uncertain", "win_probability": 0.5, "confidence_self": 0.2,
                  "key_factors": [], "caveats": ["Insufficient structured data."]}

    completeness = _data_completeness(tool_results)
    self_conf = float(parsed.get("confidence_self", 0.3))
    agreement = _odds_agreement(parsed, tool_results)
    blended = round(completeness * self_conf * agreement, 3)

    entities = state.get("entities", {})
    teams = entities.get("teams", [])
    fixture_ref = " vs ".join(teams) if teams else "upcoming fixture"

    prediction = Prediction(
        sport=entities.get("sport", "unknown"),
        fixture_ref=fixture_ref,
        pick=parsed.get("pick", "uncertain"),
        win_probability=float(parsed.get("win_probability", 0.5)),
        draw_probability=parsed.get("draw_probability"),
        confidence_num=blended,
        confidence_label=_label(blended),
        key_factors=[
            PredictionFactor(
                name=f.get("name", "factor"),
                direction=f.get("direction", "neutral"),
                weight=float(f.get("weight", 0.0)),
                detail=f.get("detail"),
            )
            for f in parsed.get("key_factors", [])
        ],
        caveats=parsed.get("caveats", []),
        data_completeness=completeness,
    )
    logger.info("Prediction pick=%s conf=%.2f completeness=%.2f", prediction.pick, blended, completeness)
    return {"prediction": prediction}
