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
| 8 | Evaluation & observability (RAGAS + dashboards) | ✅ done | per-turn `eval_traces` capture, async RAGAS judge, eval + routing dashboards |
| 9 | CI + extensive test harness (Playwright UI nav) | ✅ done | GitHub Actions gate; real browser-nav e2e, no theatre |

**149 tests pass locally** (mcp_sports 69, db 19, rag 58, api 3). The api suite
includes an in-process graph-flow integration test (router→gather→synthesize→
persist with mocked Claude/MCP and gracefully-degraded DB/RAG). The full FastAPI
app + LangGraph graph import and build cleanly.

Remaining before a live demo (needs Docker + a real `ANTHROPIC_API_KEY`, which
this build environment lacks): `docker compose up` end-to-end run, and confirming
the live free-provider endpoints respond. See "Verification" below.

## Verification

```bash
cp .env.example .env && $EDITOR .env      # set ANTHROPIC_API_KEY
make up                                    # or: make up-gpu
make seed                                  # load reference corpus into Qdrant
# open http://localhost:5173 and ask:
#   "What are the offside rules?"          -> RAG reference citation
#   "When do the Lakers play next?"        -> MCP tool + citation
#   "Who will win Arsenal vs Chelsea?"     -> prediction + confidence badge
make test                                  # run all suites in the api container
```

Fast-degradation guards (3–4s timeouts) ensure a down Qdrant/DB never stalls a
turn — the agent answers from whatever sources are available.

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
- **M8+M9** — Evaluation & observability + CI/test harness. `packages/eval_py`
  (RAGAS faithfulness/relevancy/context precision+recall with a Claude judge and
  local fastembed embeddings, a deterministic citation-contract check, routing
  aggregates, golden dataset, `make eval`). Every turn is captured to an
  `eval_traces` row by an in-graph `eval_capture` node and scored **out of band**
  by an async RAGAS judge on the ingest worker. A metrics API (`/metrics/*`) feeds
  two live React dashboards — **routing** (traffic % per intent/cache, latency,
  effectiveness) and **eval** (RAGAS scores, citation validity, recent traces).
  GitHub Actions CI (ruff + pytest matrix, web build + vitest, Playwright
  real-navigation e2e) gates every PR. Also fixed pre-existing breaks CI exposed:
  the web `tsc` build, the Tailwind typography plugin, and broken monorepo
  workspace packaging.
