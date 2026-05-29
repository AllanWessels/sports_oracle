"""Synthesis node: build citations + stream the final grounded answer."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.llm import synth_model
from app.agent.prompts import SYNTH_SYSTEM
from app.agent.state import OracleState
from app.services.citations import build_citations

logger = logging.getLogger(__name__)


def _context_block(tool_results: list[dict], rag_hits: list, citations: list) -> str:
    lines = ["Numbered sources you may cite:"]
    for c in citations:
        lines.append(f"[{c.ref_num}] ({c.source_type}/{c.provider}) {c.snippet or c.url or ''}")
    lines.append("\nRaw tool data:")
    for r in tool_results:
        lines.append(json.dumps(r, default=str)[:2000])
    if rag_hits:
        lines.append("\nRetrieved context:")
        for h in rag_hits:
            lines.append(f"- {h.title or ''}: {h.text[:600]}")
    return "\n".join(lines)


async def synthesize(state: OracleState) -> dict:
    tool_results = state.get("tool_results", [])
    rag_hits = state.get("rag_hits", [])
    prediction = state.get("prediction")

    citations = build_citations(tool_results, rag_hits)
    context = _context_block(tool_results, rag_hits, citations)

    user_block = f"User question: {state['query']}\n\n{context}"
    if prediction is not None:
        user_block += f"\n\nPrediction to present:\n{prediction.model_dump_json()}"

    # Tagged so the SSE route can isolate these tokens from other model calls.
    model = synth_model().with_config({"tags": ["synthesis"], "run_name": "synthesis"})
    resp = await model.ainvoke(
        [SystemMessage(content=SYNTH_SYSTEM), HumanMessage(content=user_block)]
    )
    answer = resp.content if isinstance(resp.content, str) else str(resp.content)

    return {
        "answer": answer,
        "citations": citations,
        "messages": [AIMessage(content=answer)],
    }
