# Sports Oracle — Implementation Plan

## Context

`sports_oracle` is a greenfield repo (empty except `.git`). The goal is a **sports oracle**: a web chat app where a user can ask anything about any sport, player, team, cup, or upcoming game and get a grounded answer — and, because it's an *oracle*, **reasoned predictions** for upcoming games with a transparent confidence score. The agent core is **LangGraph**, it reaches live sports data through **MCP** (we build our own MCP server wrapping free sports APIs), and it is backed by a **world-class RAG pipeline**.

### Decisions (locked via interview)
- **Experience:** Web chat app (streaming, history, citations, confidence badge).
- **Backend:** Python · FastAPI · LangGraph. Generation: **Claude** (`claude-opus-4-8` for synthesis/prediction, `claude-sonnet-4-6` for routing) via Anthropic API, streamed.
- **Data layer:** Build our **own MCP server** wrapping free sports REST APIs. Keyless-first (ESPN unofficial, TheSportsDB free) + free-tier-with-key (API-Football/API-Sports, balldontlie) from `.env`. **Broad multi-sport** coverage.
- **RAG:** **Qdrant** (scales, containerizes well, strong hybrid search/filtering) + Postgres for app data. **Local embeddings** (no embedding API) via `fastembed` (BGE dense + SPLADE sparse + cross-encoder rerank). Corpus = (a) semantic cache of API/live data, (b) rules/history/reference, (c) news/analysis.
- **Oracle scope:** Both factual Q&A **and** reasoned predictions (confidence + ranked factors + caveats).
- **Persistence:** Single-user, **no auth**, conversations persisted in Postgres.
- **Keys:** Keyless + free-tier via `.env`.
- **Runtime:** `docker-compose` for local **and** cloud-ready Dockerfiles.

## Architecture

```
Browser (Vite+React) --SSE--> FastAPI (LangGraph agent) --MCP--> mcp-sports --> free sports APIs
                                       |  \--Anthropic (Claude, streamed)
                                       |--> Postgres (chats, citations, predictions, checkpoints)
                                       \--> Qdrant (RAG: cache + reference + news, hybrid + rerank)
```
Containers: `web`, `api`, `mcp-sports`, `ingest-worker`, `postgres`, `qdrant`.

## Monorepo layout (key paths)
```
apps/api/        FastAPI + LangGraph agent (MCP client)
  app/main.py, config.py, deps.py
  app/api/routes_chat.py (SSE), routes_history.py, routes_health.py
  app/agent/graph.py, state.py, nodes/{router,planner,retrieve,tools,predict,synthesize,cache}.py
  app/mcp/client.py             # langchain-mcp-adapters bootstrap
  app/rag/{embeddings,qdrant_store,rerank,schema}.py
  app/db/{models,session,migrations/}   # SQLAlchemy 2.0 async + alembic
  app/services/{semantic_cache,citations}.py
apps/mcp_sports/ FastMCP server (streamable-HTTP)
  server.py
  tools/{search,fixtures,stats,standings,headtohead,injuries,odds}.py
  providers/{base,espn,thesportsdb,apisports,balldontlie}.py
  core/{registry,normalize,httpclient,cache}.py
apps/ingest/     APScheduler worker: jobs/{reference_docs,news,reindex}.py
apps/web/        Vite+React: ChatWindow, MessageBubble, Citations, ConfidenceBadge, Composer; hooks/useChatStream
packages/shared_py/   shared pydantic DTOs (Citation, Prediction, ToolResult)
data/reference/  seed rules/history markdown   data/seed/  offline fixtures
docker-compose.yml, docker-compose.override.yml, .env.example, Makefile, README.md
```
**Frontend = Vite+React** (single-user, no SSR/auth → smallest, fastest; static nginx container). Streaming via `fetch`+`ReadableStream` / `@microsoft/fetch-event-source` against FastAPI SSE.

## LangGraph agent design

**State (`OracleState`)**: `messages` (add_messages), `query`, `intent` (factual|prediction|chitchat), `entities`, `tool_plan`, `tool_results`, `rag_hits`, `cache_hit`, `prediction`, `citations`, `answer`, `freshness_floor`.

**Graph**:
```
START -> classify_and_cache
   (fresh semantic-cache hit) -> stream_cached -> END
   (miss) -> plan (resolve entities via MCP search_*, build tool_plan + freshness_floor)
   -> [intent==factual]    gather: tools_node || retrieve_node (parallel)
   -> [intent==prediction] gather_predict -> build_features -> reason_predict
   -> synthesize (STREAM answer + citations + confidence)
   -> persist_and_cache (Postgres + write-through to Qdrant cache w/ TTL) -> END
```
- Router: cheap `claude-sonnet-4-6` structured output `{intent, sport, confidence}`.
- Tools node: standard LangGraph tool-calling loop over MCP tools (cap ~4 iterations).
- Synthesize: streams only synthesis tokens (`stream_mode="messages"`); enforces citation contract — every claim maps to `[n]` → tool source (provider+endpoint+fetched_at) or RAG chunk (doc id+url).
- Checkpointing: LangGraph `AsyncPostgresSaver`, `thread_id = conversation_id`.

**Prediction sub-flow**:
1. `gather_predict`: bundle MCP calls — fixtures (+last N for form), head_to_head, standings, injuries, odds (best-effort).
2. `build_features`: transparent feature dict — weighted recent form, goal/point diff, home/away splits, H2H, rest days, injury flags, de-vigged market-implied prob.
3. `reason_predict` (`claude-opus-4-8`): structured JSON `pick`, `win_probability`, `confidence` (label+0–1), ranked `key_factors`, `caveats`.
4. **Confidence is blended**, not raw LLM: `data_completeness × model_self_rating × odds_agreement` → honest badge. Always show factors + caveats + "informational, not betting advice".

## MCP server design
Single **FastMCP** server (`mcp-sports`), default **streamable-HTTP** transport (own container; stdio for debug). Tools return a uniform envelope `{ data, source:{provider,endpoint,fetched_at}, ttl_seconds }`.

Tools: `search_entities`, `get_fixtures`, `get_live_scores`, `get_team_stats`, `get_player_stats`, `get_standings`, `get_head_to_head`, `get_injuries`, `get_odds`.

`core/registry.py` maps **sport → provider chain w/ fallback**, skipping providers whose key is absent:
- Soccer: API-Football → ESPN → TheSportsDB
- NBA: balldontlie + ESPN
- NFL/MLB/NHL: ESPN primary, TheSportsDB metadata
- Tennis/F1/other: API-Sports if key else ESPN/TheSportsDB

Providers implement a `Provider` protocol returning normalized DTOs (`core/normalize.py`). `core/httpclient.py`: shared async `httpx`, per-provider token-bucket rate limit, backoff+jitter, ETag, realistic UA, `cachetools` TTL cache. Missing odds/injuries → null (agent lowers confidence).

FastAPI connects as MCP client via **`langchain-mcp-adapters`** (`MultiServerMCPClient` in lifespan → `get_tools()` → bound to Claude).

## RAG pipeline
- **Embeddings (no API):** `fastembed` ONNX/CPU — dense `BAAI/bge-small-en-v1.5` (384-d) + sparse SPLADE (`Splade_PP_en_v1`, BM25 fallback flag) + reranker `bge-reranker-base`. Models **baked into image** at build (offline start).
- **Qdrant collections:** `sports_cache` (api_response|qa_answer; payload incl. `expires_at`), `reference_docs` (long-lived), `news` (medium TTL + recency decay). Named vectors dense+sparse.
- **Chunking:** reference = heading-aware ~512-tok/64 overlap (prepend section title); news = ~256–400 tok paragraphs + headline chunk; api responses = one compact normalized summary chunk.
- **Hybrid retrieval:** Qdrant Query API prefetch dense+sparse → **RRF** server-side → recency boost (`exp(-age/half_life)`) + `expires_at>now` filter → top-30 → cross-encoder rerank → top-6 → each carries source+timestamp = citation.
- **Freshness/TTL:** live 30–60s, fixtures/standings 5–15m, season stats 6–24h, injuries 1–6h, odds 5m, reference ∞, news 14–30d. Semantic-cache hit = dense cos ≥ 0.92 AND entity match AND not expired.
- **Ingestion (`apps/ingest`):** `reference_docs.py` (idempotent seed via `make seed`), `news.py` (RSS, scheduled), `reindex.py` (expire sweeps). Agent also write-through caches inline.

## Postgres schema
`conversations`, `messages` (role, content, intent, idx), `citations` (ref_num, source_type, provider, endpoint, url, fetched_at, snippet), `predictions` (pick, win_probability, confidence_num/label, factors jsonb, caveats jsonb), `semantic_cache_meta` (qdrant_point_id, entities, fetched_at, expires_at, hit_count). LangGraph checkpoint tables auto-created. Indexes: `messages(conversation_id, idx)`, `semantic_cache_meta(expires_at)`, `predictions(fixture_ref)`.

## Key dependencies
- **Python:** fastapi, uvicorn[standard], pydantic v2, pydantic-settings, sse-starlette, langgraph, langchain-core, langchain-anthropic, langchain-mcp-adapters, mcp (FastMCP), anthropic, qdrant-client, fastembed, sqlalchemy 2, asyncpg, alembic, httpx, cachetools, tenacity, apscheduler, feedparser; dev: pytest, pytest-asyncio, respx, ruff, mypy.
- **Node (web):** react 18, vite 5, typescript, zustand, react-markdown+remark-gfm, @microsoft/fetch-event-source, tailwind; dev: vitest, @testing-library/react.

## docker-compose + .env
Services: `web` (nginx static), `api` (uvicorn), `mcp-sports` (FastMCP :8765), `ingest-worker`, `postgres:16-alpine` (vol+healthcheck), `qdrant` (vol+`/readyz`). `override.yml` adds bind-mounts + reload + `vite dev`. `.env.example` keys: `ANTHROPIC_API_KEY`, `MODEL_*`, `APISPORTS_KEY`, `BALLDONTLIE_KEY`, `THESPORTSDB_KEY=3`, `ESPN_BASE`, `MCP_SPORTS_URL`, `DATABASE_URL`, `QDRANT_URL`, `EMBED_MODEL/SPARSE_MODEL/RERANK_MODEL`, `CACHE_SIM_THRESHOLD=0.92`, `WEB_ORIGIN`, `NEWS_FEEDS`.

## Build order (fastest path to end-to-end)
0. **Skeleton:** compose w/ postgres+qdrant + FastAPI `/health` green.
1. **MCP server, ESPN provider, 1–2 sports:** `search_entities/get_fixtures/get_standings/get_team_stats`; test via MCP Inspector.
2. **Minimal agent (factual), full SSE stream:** `/chat` → `router→plan→tools→synthesize`, MCP client wired. First true end-to-end milestone.
3. **Persistence:** conversations/messages/citations + Postgres checkpointer + history routes.
4. **Web chat:** streaming UI, history sidebar, citation rendering.
5. **RAG:** Qdrant collections, fastembed hybrid + rerank, semantic cache (write-through + short-circuit), reference-docs seed, `retrieve` node.
6. **Prediction sub-flow:** `gather_predict→build_features→reason_predict`, confidence blend, API-Football h2h/injuries/odds, ConfidenceBadge.
7. **Breadth + hardening:** balldontlie/TheSportsDB/API-Sports, rate-limit/fallback chains, news ingest, TTL sweeps.

## Verification
- `make up` (full stack), `make seed` (reference docs).
- **Unit:** provider adapters with `respx` mocks; normalize DTOs; RAG chunking + RRF fusion; confidence-blend function.
- **MCP contract:** script each tool through MCP client, assert envelope + non-empty for known entity ("Lakers").
- **Agent integration:** pytest w/ stubbed Anthropic for deterministic routing; one live smoke per intent.
- **E2E manual (3 canned prompts):** "score of the last Lakers game?" (factual+citations) · "what are the offside rules?" (RAG reference) · "who wins Arsenal vs Chelsea this weekend?" (prediction + confidence + factors). Confirm streaming, citations, badge.
- **Cache:** repeat factual prompt → served from semantic cache (log marker/faster), respects TTL.

## Risks & mitigations
- **Unofficial ESPN endpoints break:** isolate behind `Provider`, registry fallback, ETag+backoff+UA, short TTL, contract tests; never sole path.
- **Free-tier rate limits:** aggressive semantic + in-proc caching, longer TTLs, lazy odds/injury fetch only on prediction, per-provider token bucket → graceful partial data.
- **Prediction overconfidence:** blended confidence, ranked factors + caveats, de-vig odds anchor, disclaimer, conservative when data missing.
- **Model size in container:** fastembed ONNX/CPU, bge-small (~130MB), models baked at build, BM25-only fallback flag.
- **Stale cache:** hard `expires_at` filter + recency decay + scheduled sweeps; live scores bypass cache.
- **Startup/transport:** load MCP tools in lifespan w/ retry; `/ready` unhealthy until tools + collections confirmed; compose healthcheck ordering.
