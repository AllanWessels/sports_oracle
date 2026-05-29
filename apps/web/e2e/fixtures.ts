import type { Page } from '@playwright/test'

export const ROUTING_METRICS = {
  window_hours: 24,
  total: 5,
  routes: {
    factual: { count: 3, pct: 60, latency_ms_p50: 100, latency_ms_p95: 300, avg_tool_results: 1 },
    prediction: { count: 1, pct: 20, latency_ms_p50: 500, latency_ms_p95: 500, avg_tool_results: 0 },
    cache: { count: 1, pct: 20, latency_ms_p50: 10, latency_ms_p95: 10, avg_tool_results: 0 },
  },
  cache_hit_rate: 0.2,
  tool_call_rate: 0.4,
  series: [{ bucket: '2026-05-29T10:00:00+00:00', total: 5, factual: 3 }],
}

export const EVAL_METRICS = {
  window_hours: 24,
  judged: 2,
  pending: 3,
  means: { faithfulness: 0.8, answer_relevancy: 0.4, context_precision: 0.7, context_recall: 0.6 },
  citation_valid_rate: 0.5,
}

export const TRACES = {
  traces: [
    {
      id: '1', query: 'offside?', intent: 'factual', route: 'factual', answer: 'a [1]',
      latency_ms: 120, faithfulness: 0.9, answer_relevancy: 0.8,
      context_precision: 1, context_recall: 1, citation_valid: true, judged_at: 't', created_at: 't',
    },
  ],
}

const SSE = [
  'event: intent',
  'data: {"intent":"factual"}',
  '',
  'event: token',
  'data: {"text":"Arsenal play in the Premier League. [1]"}',
  '',
  'event: citation',
  'data: {"ref_num":1,"source_type":"rag_doc","provider":"offside.md","snippet":"Law 11"}',
  '',
  'event: done',
  'data: {"conversation_id":"c1","message_id":"m1"}',
  '',
  '',
].join('\n')

/** Intercept all backend calls so the e2e is hermetic (no live API). */
export async function mockBackend(page: Page): Promise<void> {
  const json = (body: unknown) => ({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })

  await page.route('**/conversations', (r) => r.fulfill(json([])))
  await page.route('**/metrics/routing*', (r) => r.fulfill(json(ROUTING_METRICS)))
  await page.route('**/metrics/eval*', (r) => r.fulfill(json(EVAL_METRICS)))
  await page.route('**/metrics/traces*', (r) => r.fulfill(json(TRACES)))
  await page.route('**/chat', (r) =>
    r.fulfill({ status: 200, contentType: 'text/event-stream', body: SSE }),
  )
}
