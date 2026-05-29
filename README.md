# 🔮 Sports Oracle

A conversational **sports oracle**: ask anything about any sport, player, team,
cup, or upcoming game and get grounded, cited answers — plus **reasoned
predictions** for upcoming games with a transparent confidence score.

Under the hood it pairs a **LangGraph** agent (Claude) with live sports data
reached over **MCP**, all backed by a hybrid **RAG** pipeline on Qdrant.

## Architecture

```
Browser (Vite+React) ──SSE──▶ FastAPI (LangGraph agent) ──MCP──▶ mcp-sports ──▶ free sports APIs
                                     │  └──▶ Anthropic (Claude, streamed)
                                     ├──▶ Postgres  (chats, citations, predictions, checkpoints)
                                     └──▶ Qdrant    (RAG: semantic cache + reference + news)
```

| Service | Role |
|---|---|
| `web` | Vite + React streaming chat UI (citations + confidence badge) |
| `api` | FastAPI + LangGraph agent; MCP client; RAG |
| `mcp-sports` | Our FastMCP server wrapping free sports REST APIs |
| `ingest-worker` | Scheduled RAG ingestion (reference docs, news, TTL sweeps) |
| `postgres` | Chat history, citations, predictions, LangGraph checkpoints |
| `qdrant` | Vector store: hybrid (dense + sparse) search + rerank |

## Quick start

```bash
cp .env.example .env        # add ANTHROPIC_API_KEY; sports works keyless
make up                     # build + run everything (CPU)
make up-gpu                 # ...or with the NVIDIA GPU overlay
make seed                   # load the reference-docs corpus
```

Then open http://localhost:5173. Two live dashboards ship alongside the chat:

- **http://localhost:5173/dashboard/routing** — LangGraph traffic: what % of turns
  go factual / prediction / chitchat / cache-hit, latency and effectiveness per route.
- **http://localhost:5173/dashboard/eval** — RAGAS scores (faithfulness, relevancy,
  context precision/recall), citation-validity rate, and recent judged turns.

## Key choices

- **Generation:** Claude (`claude-opus-4-8` synth/predict, `claude-sonnet-4-6` routing).
- **Data:** keyless-first (ESPN unofficial, TheSportsDB) + free-tier (API-Football,
  balldontlie) via `.env`, all behind one MCP tool surface with provider fallback.
- **RAG:** local embeddings (no embedding API) via `fastembed` — BGE dense +
  SPLADE sparse + cross-encoder rerank, **GPU-accelerated when available**.
- **Predictions:** confidence is *blended* (data completeness × model self-rating ×
  odds agreement), never raw LLM output. Always shows factors + caveats.

## Evaluation & observability

Every turn is captured to an `eval_traces` row (free, in-graph) and scored **out of
band** by an async [RAGAS](https://docs.ragas.io) judge on the ingest worker —
faithfulness, answer relevancy, context precision/recall (Claude judge + **local**
fastembed embeddings, no paid embedding API) plus a deterministic citation-contract
check. The two dashboards above read a metrics API (`/metrics/routing`, `/eval`,
`/traces`) and refresh live. Run the scorecard over the golden set with `make eval`.

Predictions are evaluated only for groundedness of their cited references — never
for whether the pick was "right".

CI (GitHub Actions) gates every PR: `ruff` + `pytest` per component, web build +
`vitest`, and a **Playwright** real-navigation e2e suite. See `packages/eval_py`.

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — full design.
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — milestone tracker.
- [`docs/SKILLS.md`](docs/SKILLS.md) — what the oracle can do (capabilities).
- [`CLAUDE.md`](CLAUDE.md) — guidance for working in this codebase.

> Predictions are informational only — not betting advice.
