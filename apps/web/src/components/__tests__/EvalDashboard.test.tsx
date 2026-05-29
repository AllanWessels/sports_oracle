import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { EvalDashboard } from '../dashboards/EvalDashboard'

vi.mock('../../api/metrics', () => ({
  getEvalMetrics: vi.fn(),
  getTraces: vi.fn(),
}))

import { getEvalMetrics, getTraces } from '../../api/metrics'

describe('EvalDashboard', () => {
  beforeEach(() => {
    vi.mocked(getEvalMetrics).mockResolvedValue({
      window_hours: 24,
      judged: 2,
      pending: 3,
      means: { faithfulness: 0.8, answer_relevancy: 0.4, context_precision: null, context_recall: null },
      citation_valid_rate: 0.5,
    })
    vi.mocked(getTraces).mockResolvedValue({
      traces: [
        {
          id: '1', query: 'offside?', intent: 'factual', route: 'factual', answer: 'a [1]',
          latency_ms: 120, faithfulness: 0.9, answer_relevancy: 0.8,
          context_precision: 1, context_recall: 1, citation_valid: true,
          judged_at: 't', created_at: 't',
        },
      ],
    })
  })

  it('renders RAGAS score cards, judged/pending, and recent traces', async () => {
    render(
      <MemoryRouter>
        <EvalDashboard />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('score-Faithfulness')).toHaveTextContent('80%')
    expect(screen.getByTestId('score-Answer relevancy')).toHaveTextContent('40%')
    // missing metric renders an em-dash, not 0%
    expect(screen.getByTestId('score-Context precision')).toHaveTextContent('—')
    expect(screen.getByTestId('score-Citation valid')).toHaveTextContent('50%')
    expect(screen.getByTestId('judged')).toHaveTextContent('2')
    expect(screen.getByTestId('pending')).toHaveTextContent('3')

    // recent traces table populated from getTraces
    const rows = await screen.findAllByTestId('trace-row')
    expect(rows).toHaveLength(1)
    expect(rows[0]).toHaveTextContent('offside?')
    expect(rows[0]).toHaveTextContent('90%')
  })
})
