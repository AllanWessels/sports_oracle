import type { PredictionEvent } from '../types'
import { ConfidenceBadge } from './ConfidenceBadge'

interface Props {
  prediction: PredictionEvent
}

const DIRECTION_COLOR: Record<string, string> = {
  positive: 'text-emerald-400',
  negative: 'text-rose-400',
  neutral: 'text-slate-400',
}

function directionIcon(dir: string): string {
  if (dir === 'positive') return '↑'
  if (dir === 'negative') return '↓'
  return '→'
}

function fmt(p: number): string {
  return `${(p * 100).toFixed(1)}%`
}

export function PredictionCard({ prediction: p }: Props) {
  const sortedFactors = [...p.key_factors].sort((a, b) => b.weight - a.weight)
  const maxWeight = Math.max(...sortedFactors.map((f) => f.weight), 1)

  return (
    <div className="mt-3 rounded-xl border border-brand-800/60 bg-gradient-to-br from-surface-800 to-surface-900 overflow-hidden animate-slide-up">
      {/* Header */}
      <div className="px-4 py-3 bg-brand-900/40 border-b border-brand-800/40 flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wider">
            {p.sport} · Prediction
          </p>
          <p className="text-sm text-slate-300 mt-0.5">{p.fixture_ref}</p>
        </div>
        <ConfidenceBadge label={p.confidence_label} num={p.confidence_num} showBar />
      </div>

      {/* Pick & Probabilities */}
      <div className="px-4 py-3 border-b border-surface-700">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              Pick
            </p>
            <p className="text-lg font-bold text-white mt-0.5">{p.pick}</p>
          </div>
          <div className="flex gap-4 ml-auto">
            <div className="text-center">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Win</p>
              <p className="text-base font-semibold text-emerald-400 tabular-nums">
                {fmt(p.win_probability)}
              </p>
            </div>
            {p.draw_probability != null && (
              <div className="text-center">
                <p className="text-[10px] text-slate-500 uppercase tracking-wider">Draw</p>
                <p className="text-base font-semibold text-amber-400 tabular-nums">
                  {fmt(p.draw_probability)}
                </p>
              </div>
            )}
            <div className="text-center">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Loss</p>
              <p className="text-base font-semibold text-rose-400 tabular-nums">
                {fmt(1 - p.win_probability - (p.draw_probability ?? 0))}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Key Factors */}
      {sortedFactors.length > 0 && (
        <div className="px-4 py-3 border-b border-surface-700">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Key Factors
          </p>
          <ul className="space-y-2.5">
            {sortedFactors.map((factor, i) => {
              const barWidth = `${(factor.weight / maxWeight) * 100}%`
              const dirColor =
                DIRECTION_COLOR[factor.direction.toLowerCase()] ?? DIRECTION_COLOR['neutral']
              return (
                <li key={i} className="space-y-0.5">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="flex items-center gap-1">
                      <span className={`font-mono text-sm ${dirColor}`}>
                        {directionIcon(factor.direction.toLowerCase())}
                      </span>
                      <span className="text-slate-200 font-medium">{factor.name}</span>
                    </span>
                    <span className="tabular-nums text-slate-400 text-[11px] shrink-0">
                      {(factor.weight * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surface-700 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-brand-500/70 transition-all duration-700"
                      style={{ width: barWidth }}
                    />
                  </div>
                  {factor.detail && (
                    <p className="text-[11px] text-slate-500 leading-tight">{factor.detail}</p>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {/* Caveats */}
      {p.caveats.length > 0 && (
        <div className="px-4 py-3 border-b border-surface-700">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
            Caveats
          </p>
          <ul className="space-y-1">
            {p.caveats.map((c, i) => (
              <li key={i} className="flex gap-2 text-xs text-slate-400">
                <span className="text-amber-500 shrink-0 mt-0.5">⚠</span>
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Disclaimer */}
      <div className="px-4 py-2.5 bg-amber-500/5 border-t border-amber-500/20">
        <p className="text-[10px] text-amber-400/70 leading-snug">
          <span className="font-semibold">Informational only — not betting advice.</span>{' '}
          {p.disclaimer}
        </p>
      </div>
    </div>
  )
}
