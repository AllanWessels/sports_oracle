# Progress Tracker

Milestones for the Sports Oracle build. Updated after each milestone, then
committed + pushed.

| # | Milestone | Status | Notes |
|---|-----------|--------|-------|
| 0 | Repo scaffold, contract DTOs, compose, docs | ✅ done | shared_py contract + docker-compose + docs |
| 1 | MCP server: ESPN provider + core tools | 🔄 in progress | search/fixtures/standings/stats, keyless |
| 2 | Minimal LangGraph agent (factual) + SSE | ⬜ todo | router→plan→tools→synthesize, MCP client |
| 3 | Postgres persistence + checkpoints | ⬜ todo | conversations/messages/citations/predictions |
| 4 | Web chat UI (streaming, citations, badge) | 🔄 in progress | Vite+React |
| 5 | RAG pipeline (Qdrant hybrid + rerank + cache) | 🔄 in progress | fastembed GPU, 3 collections |
| 6 | Prediction sub-flow + confidence blend | ⬜ todo | features→reason→blended confidence |
| 7 | Multi-provider breadth + hardening | ⬜ todo | balldontlie, TheSportsDB, API-Sports, rate limits, news |

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
