import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RoutingDashboard } from '../dashboards/RoutingDashboard'

vi.mock('../../api/metrics', () => ({
  getRoutingMetrics: vi.fn(),
}))

import { getRoutingMetrics } from '../../api/metrics'

const SAMPLE = {
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

describe('RoutingDashboard', () => {
  beforeEach(() => {
    vi.mocked(getRoutingMetrics).mockResolvedValue(SAMPLE)
  })

  it('renders traffic split, rates, and per-route rows from the API', async () => {
    render(
      <MemoryRouter>
        <RoutingDashboard />
      </MemoryRouter>,
    )

    // Stats resolve after the first poll
    expect(await screen.findByTestId('stat-Total turns')).toHaveTextContent('5')
    expect(screen.getByTestId('stat-Cache hit rate')).toHaveTextContent('20%')
    expect(screen.getByTestId('stat-Tool-call rate')).toHaveTextContent('40%')

    // Per-route breakdown (text fallback for the pie)
    expect(screen.getByTestId('route-factual')).toHaveTextContent('3')
    expect(screen.getByTestId('route-factual')).toHaveTextContent('60%')
    expect(screen.getByTestId('route-prediction')).toHaveTextContent('1')
    expect(screen.getByTestId('route-cache')).toBeInTheDocument()
  })
})
