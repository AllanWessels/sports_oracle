# CLAUDE.md — working in Sports Oracle

Guidance for AI agents (and humans) contributing to this repo.

## What this is

A sports oracle: a web chat app that answers factual sports questions **and**
makes reasoned predictions about upcoming games. LangGraph agent (Claude) +
MCP-wrapped free sports APIs + hybrid RAG on Qdrant. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and
[`docs/PROGRESS.md`](docs/PROGRESS.md) for current status.

## Repo map

```
apps/api/         FastAPI + LangGraph agent (MCP client, RAG)
apps/mcp_sports/  FastMCP server wrapping free sports APIs
apps/ingest/      Scheduled RAG ingestion worker
apps/web/         Vite + React chat UI
packages/shared_py/  Shared pydantic DTOs — THE CONTRACT between services
docs/             Architecture, progress, capabilities
data/reference/   Seed reference corpus (rules/history) for RAG
```

## The contract comes first

`packages/shared_py/sports_oracle_shared` is the single source of truth for data
shapes crossing service boundaries (`ToolEnvelope`, `Citation`, `Prediction`,
`RagChunk`, normalized `Team`/`Player`/`Fixture`/...). Change models there, not
ad-hoc per service. Every MCP tool returns a `ToolEnvelope`; every provider
adapter normalizes upstream JSON into the shared sports models.

## Conventions

- Python 3.11+, async-first (FastAPI, asyncpg, httpx). Type hints everywhere; pass `ruff` + `mypy`.
- LLM models come from env (`MODEL_ROUTER`, `MODEL_SYNTH`, `MODEL_PREDICT`) — never hardcode model ids.
- Local embeddings/reranker run on GPU when available (`EMBED_DEVICE=auto`); never call a paid embedding API.
- Secrets only via `.env`; keyless providers must keep working with no keys set.
- Tests: `pytest` with `respx` mocking upstream HTTP. Don't hit live APIs in unit tests.

## Build order & status

Work proceeds in phases (see `docs/PROGRESS.md`). Independent components
(`mcp_sports`, `rag`, `db`, `web`) are built in parallel; the LangGraph
`graph.py` is the integration hub that ties them together.

## After each milestone

Update `docs/PROGRESS.md`, refresh this file and `docs/SKILLS.md` if
capabilities changed, then commit + push to
`claude/sports-oracle-mcp-langgraph-UKbkw`.
