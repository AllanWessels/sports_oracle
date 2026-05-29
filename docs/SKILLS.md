# Oracle Capabilities ("Skills")

What the Sports Oracle can do for a user, and the agent tools/flows behind each.
This is the user-facing capability surface — keep it in sync as features land.

## Factual Q&A
- **Scores & results** — final/live scores for a game or team. (`get_live_scores`, `get_fixtures`)
- **Schedules & fixtures** — upcoming games for a team, league, or date range. (`get_fixtures`)
- **Standings & tables** — league position, points, form. (`get_standings`)
- **Team & player stats** — season stats, recent form, splits. (`get_team_stats`, `get_player_stats`)
- **Head-to-head** — historical meetings between two teams. (`get_head_to_head`)
- **Injuries & availability** — current injury reports. (`get_injuries`)
- **Rules, formats & history** — offside, competition formats, records, bios. (RAG `reference_docs`)
- **News & narrative** — recent previews/analysis context. (RAG `news`)

## Predictions ("the oracle")
- **Match forecasts** — who wins an upcoming game, win/draw probabilities.
- **Transparent reasoning** — ranked key factors (form, H2H, injuries, odds) + caveats.
- **Calibrated confidence** — a blended score (data completeness × model self-rating ×
  odds agreement), shown as a badge. Conservative when signals are missing.
- *Always labeled informational only — not betting advice.*

## Cross-cutting
- **Multi-sport** — soccer, NBA/NFL/MLB/NHL, tennis, F1, and more via provider fallback.
- **Citations** — every factual claim references a numbered source (API + timestamp, or doc/url).
- **Streaming** — answers stream token-by-token over SSE.
- **Memory** — conversations persist (single-user) and resume via LangGraph checkpoints.
- **Semantic cache** — repeated/related questions are served fast, respecting per-data-class TTL.

## Agent flow (how a turn is handled)
1. **Route** intent (factual / prediction / chitchat) + check semantic cache.
2. **Plan** — resolve entities (teams/players), build a tool plan, set a freshness floor.
3. **Gather** — call MCP tools and retrieve RAG chunks (in parallel for factual).
4. **Predict** (if prediction) — build features → reason → blend confidence.
5. **Synthesize** — stream a cited answer; attach prediction + confidence.
6. **Persist & cache** — save to Postgres; write-through to the Qdrant cache with TTL.
