import { useCallback } from 'react'
import { getEvalMetrics, getTraces } from '../../api/metrics'
import { usePolling } from '../../hooks/usePolling'
import { DashboardNav } from './DashboardNav'

const METRIC_LABELS: Record<string, string> = {
  faithfulness: 'Faithfulness',
  answer_relevancy: 'Answer relevancy',
  context_precision: 'Context precision',
  context_recall: 'Context recall',
}

function pct(v: number | null | undefined): string {
  return v == null ? '—' : `${(v * 100).toFixed(0)}%`
}

function ScoreCard({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-xl bg-surface-800 border border-surface-700 p-4">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold text-white" data-testid={`score-${label}`}>
        {pct(value)}
      </p>
    </div>
  )
}

export function EvalDashboard() {
  const { data, error, loading } = usePolling(() => getEvalMetrics(24), 5000)
  const tracesFetcher = useCallback(() => getTraces(25), [])
  const traces = usePolling(tracesFetcher, 5000)

  return (
    <div className="flex flex-col h-screen overflow-y-auto bg-surface-900">
      <DashboardNav title="Evaluation (RAGAS)" />
      <div className="p-6 space-y-6">
        {error && (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 p-3 text-sm text-rose-400">
            {error}
          </div>
        )}
        {loading && !data && <p className="text-slate-400">Loading metrics…</p>}

        {data && (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {Object.keys(METRIC_LABELS).map((k) => (
                <ScoreCard key={k} label={METRIC_LABELS[k]} value={data.means[k] ?? null} />
              ))}
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
              <ScoreCard label="Citation valid" value={data.citation_valid_rate} />
              <div className="rounded-xl bg-surface-800 border border-surface-700 p-4">
                <p className="text-xs text-slate-400">Judged</p>
                <p className="mt-1 text-2xl font-bold text-white" data-testid="judged">
                  {data.judged}
                </p>
              </div>
              <div className="rounded-xl bg-surface-800 border border-surface-700 p-4">
                <p className="text-xs text-slate-400">Pending</p>
                <p className="mt-1 text-2xl font-bold text-white" data-testid="pending">
                  {data.pending}
                </p>
              </div>
            </div>

            <section className="rounded-xl bg-surface-800 border border-surface-700 overflow-hidden">
              <h2 className="text-sm font-semibold text-white px-4 py-3 border-b border-surface-700">
                Recent traces
              </h2>
              <table className="w-full text-sm">
                <thead className="text-xs text-slate-400">
                  <tr className="text-left">
                    <th className="px-4 py-2 font-medium">Query</th>
                    <th className="px-4 py-2 font-medium">Route</th>
                    <th className="px-4 py-2 font-medium">Faithful.</th>
                    <th className="px-4 py-2 font-medium">Cited</th>
                  </tr>
                </thead>
                <tbody>
                  {(traces.data?.traces ?? []).map((t) => (
                    <tr key={t.id} className="border-t border-surface-700/60" data-testid="trace-row">
                      <td className="px-4 py-2 text-slate-200 truncate max-w-xs">{t.query}</td>
                      <td className="px-4 py-2 text-slate-300 capitalize">{t.route}</td>
                      <td className="px-4 py-2 text-slate-300">{pct(t.faithfulness)}</td>
                      <td className="px-4 py-2">
                        {t.citation_valid == null ? (
                          <span className="text-slate-500">—</span>
                        ) : t.citation_valid ? (
                          <span className="text-emerald-400">✓</span>
                        ) : (
                          <span className="text-rose-400">✗</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
