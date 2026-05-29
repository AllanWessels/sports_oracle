import { describe, expect, it } from 'vitest'
import { buildGraphMermaid } from '../dashboards/graph'

const routes = {
  factual: { count: 3, pct: 60, latency_ms_p50: 1, latency_ms_p95: 2, avg_tool_results: 1 },
  prediction: { count: 1, pct: 20, latency_ms_p50: 1, latency_ms_p95: 2, avg_tool_results: 0 },
  cache: { count: 1, pct: 20, latency_ms_p50: 1, latency_ms_p95: 2, avg_tool_results: 0 },
}

describe('buildGraphMermaid', () => {
  it('includes the graph nodes and conditional router edges', () => {
    const m = buildGraphMermaid(routes)
    expect(m).toContain('graph TD')
    expect(m).toContain('classify_and_cache')
    expect(m).toContain('gather_predict --> reason_predict')
    expect(m).toContain('persist_and_cache --> eval_capture')
    // dashed router edges
    expect(m).toContain('classify_and_cache -. "factual 60%" .-> gather')
    expect(m).toContain('classify_and_cache -. "prediction 20%" .-> gather_predict')
    expect(m).toContain('classify_and_cache -. "cache 20%" .-> stream_cached')
  })

  it('omits percentages when routes are missing', () => {
    const m = buildGraphMermaid(undefined)
    expect(m).toContain('classify_and_cache -. "factual" .-> gather')
    expect(m).not.toContain('%')
  })
})
