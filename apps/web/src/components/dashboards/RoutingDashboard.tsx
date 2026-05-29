import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getRoutingMetrics } from '../../api/metrics'
import { usePolling } from '../../hooks/usePolling'
import { DashboardNav } from './DashboardNav'

const ROUTE_COLORS: Record<string, string> = {
  factual: '#38bdf8',
  prediction: '#a78bfa',
  chitchat: '#34d399',
  cache: '#fbbf24',
}
const colorFor = (route: string) => ROUTE_COLORS[route] ?? '#94a3b8'

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surface-800 border border-surface-700 p-4">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold text-white" data-testid={`stat-${label}`}>
        {value}
      </p>
    </div>
  )
}

export function RoutingDashboard() {
  const { data, error, loading } = usePolling(() => getRoutingMetrics(24), 5000)

  const routeRows = data
    ? Object.entries(data.routes).map(([route, s]) => ({ route, ...s }))
    : []

  return (
    <div className="flex flex-col h-screen overflow-y-auto bg-surface-900">
      <DashboardNav title="LangGraph Routing" />
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
              <Stat label="Total turns" value={String(data.total)} />
              <Stat label="Cache hit rate" value={`${(data.cache_hit_rate * 100).toFixed(0)}%`} />
              <Stat label="Tool-call rate" value={`${(data.tool_call_rate * 100).toFixed(0)}%`} />
              <Stat label="Routes" value={String(routeRows.length)} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <section className="rounded-xl bg-surface-800 border border-surface-700 p-4">
                <h2 className="text-sm font-semibold text-white mb-3">Traffic by route</h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={routeRows} dataKey="count" nameKey="route" outerRadius={90} label>
                        {routeRows.map((r) => (
                          <Cell key={r.route} fill={colorFor(r.route)} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                {/* Accessible/text fallback — also what tests assert against */}
                <ul className="mt-2 space-y-1">
                  {routeRows.map((r) => (
                    <li key={r.route} className="text-xs text-slate-300" data-testid={`route-${r.route}`}>
                      <span className="font-medium capitalize">{r.route}</span>: {r.count} ({r.pct}%)
                    </li>
                  ))}
                </ul>
              </section>

              <section className="rounded-xl bg-surface-800 border border-surface-700 p-4">
                <h2 className="text-sm font-semibold text-white mb-3">p95 latency by route (ms)</h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={routeRows}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="route" stroke="#94a3b8" fontSize={12} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <Tooltip />
                      <Bar dataKey="latency_ms_p95" fill="#38bdf8" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>
            </div>

            <section className="rounded-xl bg-surface-800 border border-surface-700 p-4">
              <h2 className="text-sm font-semibold text-white mb-3">Volume over time</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="bucket" stroke="#94a3b8" fontSize={11} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip />
                    <Line type="monotone" dataKey="total" stroke="#38bdf8" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
