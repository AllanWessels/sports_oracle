# Progress Tracker

Milestones for the Sports Oracle build. Updated after each milestone, then
committed + pushed.

| # | Milestone | Status | Notes |
|---|-----------|--------|-------|
| 0 | Repo scaffold, contract DTOs, compose, docs | ✅ done | shared_py contract + docker-compose + docs |
| 1 | MCP server: 9 tools, 4 providers | ✅ done | ESPN(keyless)/TheSportsDB/API-Football/balldontlie, 69 tests |
| 2 | LangGraph agent + SSE | ✅ done | router/cache→factual(gather‖retrieve)/prediction→synth→persist |
| 3 | Postgres persistence + checkpoints | ✅ done | db_py: models/repo/alembic, 19 tests; PG checkpointer |
| 4 | Web chat UI (streaming, citations, badge) | ✅ done | Vite+React, SSE, PredictionCard + ConfidenceBadge |
| 5 | RAG pipeline (Qdrant hybrid + rerank + cache) | ✅ done | rag_py: fastembed GPU, 3 collections, 58 tests; ingest worker |
| 6 | Prediction sub-flow + confidence blend | ✅ done | features→reason→blended (completeness×self×odds) |
| 7 | Multi-provider breadth + hardening | 🔄 partial | providers in place; live E2E + rate-limit tuning pending |

All component unit suites pass locally (mcp_sports 69, db 19, rag 58, api 2).
Remaining before a live demo: `docker compose up` end-to-end verification with a
real `ANTHROPIC_API_KEY`, and confirming live provider endpoints respond.

Legend: ✅ done · 🔄 in progress · ⬜ todo

## Parallelization map

Independent components fanned out to Sonnet sub-agents (disjoint directories):

- **mcp_sports** — providers + tools + FastMCP server.
- **rag** (`apps/api/app/rag`) + **ingest** — embeddings, Qdrant, hybrid search.
- **db** (`apps/api/app/db` + services) — SQLAlchemy models, migrations.
- **web** — React chat UI against the SSE contract.

Integration hub built on the main thread: `apps/api/app/agent/graph.py`,
FastAPI routes, MCP client wiring.

## Changelog

- **M0** — Foundation: shared DTO contract (`packages/shared_py`), docker-compose
  (+GPU overlay), Makefile, README, CLAUDE.md, architecture & skills docs.
- **M2** — API integration hub: FastAPI + LangGraph agent, MCP client, SSE route,
  prediction sub-flow with blended confidence, services (citations/cache/persist).
- **M3+M4** — DB persistence package (SQLAlchemy 2.0 + alembic) and the Vite+React
  web chat UI. Reconciled hub to `get_session_factory()`; aligned web port to 5173.
- **M1+M5+M6** — MCP sports server (9 tools, 4 providers, keyless ESPN primary) and
  RAG library (`packages/rag_py`, fastembed dense+sparse+rerank, 3 Qdrant
  collections, GPU-aware) + ingest worker. Reconciled `semantic_cache` to the real
  RAG API (`build_point`/`upsert`, Qdrant `Filter`, `data_class`). Fixed two real
  bugs found by tests: APISports `get_fixtures` contract drift and a chunker
  overflow on delimiter-free oversized sections.
