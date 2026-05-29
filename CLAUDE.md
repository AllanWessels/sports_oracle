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
apps/api/            FastAPI + LangGraph agent — the integration hub (MCP client, RAG, SSE)
apps/mcp_sports/     FastMCP server wrapping free sports APIs (9 tools, 4 providers)
apps/ingest/         Scheduled RAG ingestion worker (reference docs, news, TTL sweeps)
apps/web/            Vite + React streaming chat UI (citations + confidence badge)
packages/shared_py/  Shared pydantic DTOs — THE CONTRACT between services
packages/rag_py/     RAG library: fastembed hybrid search + rerank over Qdrant (GPU-aware)
packages/db_py/      SQLAlchemy 2.0 async persistence + Alembic migrations
docs/                Architecture, progress, capabilities
data/reference/      Seed reference corpus (rules/history) for RAG
```

The four `packages/`/`apps/` components are independent and were built in
parallel; `apps/api/app/agent/graph.py` is the hub that wires them together.

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

Phases M0–M6 are done; M7 (live E2E + provider hardening) is partial — see
`docs/PROGRESS.md`. 149 unit/integration tests pass across all components.

## Running & testing

```bash
cp .env.example .env          # set ANTHROPIC_API_KEY; sports works keyless
make up        # full stack (CPU)      |  make up-gpu  # NVIDIA overlay
make seed      # load reference corpus into Qdrant
make test      # all pytest suites in the api container
```

Per-component tests run with PYTHONPATH set to the package(s) under test plus
`packages/shared_py`, e.g.
`PYTHONPATH=apps/mcp_sports:packages/shared_py pytest apps/mcp_sports/tests`.
The api graph-flow test is hermetic — it mocks Claude/MCP and stubs RAG/DB, so
it never downloads models or needs live services.

## After each milestone

Update `docs/PROGRESS.md`, refresh this file and `docs/SKILLS.md` if
capabilities changed, then commit + push to
`claude/sports-oracle-mcp-langgraph-UKbkw`.
