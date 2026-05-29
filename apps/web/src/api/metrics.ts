// Client for the eval + routing observability endpoints (/metrics/*).

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export interface RouteStats {
  count: number
  pct: number
  latency_ms_p50: number | null
  latency_ms_p95: number | null
  avg_tool_results: number
}

export interface SeriesPoint {
  bucket: string
  total: number
  [route: string]: number | string
}

export interface RoutingMetrics {
  window_hours: number
  total: number
  routes: Record<string, RouteStats>
  cache_hit_rate: number
  tool_call_rate: number
  series: SeriesPoint[]
}

export interface EvalMetrics {
  window_hours: number
  judged: number
  pending: number
  means: Record<string, number | null>
  citation_valid_rate: number | null
}

export interface TraceRow {
  id: string
  query: string
  intent: string
  route: string
  answer: string
  latency_ms: number | null
  faithfulness: number | null
  answer_relevancy: number | null
  context_precision: number | null
  context_recall: number | null
  citation_valid: boolean | null
  judged_at: string | null
  created_at: string | null
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json() as Promise<T>
}

export const getRoutingMetrics = (hours = 24): Promise<RoutingMetrics> =>
  getJSON(`/metrics/routing?hours=${hours}`)

export const getEvalMetrics = (hours = 24): Promise<EvalMetrics> =>
  getJSON(`/metrics/eval?hours=${hours}`)

export const getTraces = (limit = 25, intent?: string): Promise<{ traces: TraceRow[] }> =>
  getJSON(`/metrics/traces?limit=${limit}${intent ? `&intent=${intent}` : ''}`)
