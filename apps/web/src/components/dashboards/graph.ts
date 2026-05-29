import type { RouteStats } from '../../api/metrics'

/**
 * Build the LangGraph agent diagram as Mermaid, annotating the conditional
 * router edges with live traffic %. The topology is static (mirrors
 * apps/api/app/agent/graph.py); the percentages come from /metrics/routing.
 *
 * Pure + deterministic so it can be unit-tested without rendering.
 */
export function buildGraphMermaid(routes: Record<string, RouteStats> | undefined): string {
  const pct = (key: string): string => {
    const r = routes?.[key]
    return r ? ` ${r.pct}%` : ''
  }
  // Note: `end` is a reserved word in Mermaid — use safe node ids (s0/e0).
  return [
    'graph TD',
    '  s0([START]) --> classify_and_cache',
    `  classify_and_cache -. "cache${pct('cache')}" .-> stream_cached`,
    `  classify_and_cache -. "factual${pct('factual')}" .-> gather`,
    '  classify_and_cache -. "factual" .-> retrieve',
    `  classify_and_cache -. "prediction${pct('prediction')}" .-> gather_predict`,
    `  classify_and_cache -. "chitchat${pct('chitchat')}" .-> synthesize`,
    '  gather --> synthesize',
    '  retrieve --> synthesize',
    '  gather_predict --> reason_predict',
    '  reason_predict --> synthesize',
    '  synthesize --> persist_and_cache',
    '  stream_cached --> persist_and_cache',
    '  persist_and_cache --> eval_capture',
    '  eval_capture --> e0([END])',
  ].join('\n')
}
