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

Then open http://localhost:5173.

## Key choices

- **Generation:** Claude (`claude-opus-4-8` synth/predict, `claude-sonnet-4-6` routing).
- **Data:** keyless-first (ESPN unofficial, TheSportsDB) + free-tier (API-Football,
  balldontlie) via `.env`, all behind one MCP tool surface with provider fallback.
- **RAG:** local embeddings (no embedding API) via `fastembed` — BGE dense +
  SPLADE sparse + cross-encoder rerank, **GPU-accelerated when available**.
- **Predictions:** confidence is *blended* (data completeness × model self-rating ×
  odds agreement), never raw LLM output. Always shows factors + caveats.

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — full design.
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — milestone tracker.
- [`docs/SKILLS.md`](docs/SKILLS.md) — what the oracle can do (capabilities).
- [`CLAUDE.md`](CLAUDE.md) — guidance for working in this codebase.

> Predictions are informational only — not betting advice.
