import type { ConfidenceLabel } from '../types'

interface Props {
  label: ConfidenceLabel
  num: number // 0–100
  showBar?: boolean
}

const LABEL_CONFIG: Record<
  ConfidenceLabel,
  { color: string; barColor: string; bg: string; text: string }
> = {
  low: {
    color: 'text-amber-400',
    barColor: 'bg-amber-400',
    bg: 'bg-amber-400/10 border-amber-400/30',
    text: 'Low',
  },
  medium: {
    color: 'text-sky-400',
    barColor: 'bg-sky-400',
    bg: 'bg-sky-400/10 border-sky-400/30',
    text: 'Medium',
  },
  high: {
    color: 'text-emerald-400',
    barColor: 'bg-emerald-400',
    bg: 'bg-emerald-400/10 border-emerald-400/30',
    text: 'High',
  },
}

export function ConfidenceBadge({ label, num, showBar = false }: Props) {
  const cfg = LABEL_CONFIG[label]
  const pct = Math.max(0, Math.min(100, num))

  return (
    <div className={`inline-flex flex-col gap-1 px-3 py-1.5 rounded-lg border ${cfg.bg}`}>
      <div className="flex items-center gap-2">
        <span className={`text-xs font-semibold uppercase tracking-wide ${cfg.color}`}>
          {cfg.text} Confidence
        </span>
        <span className={`text-sm font-bold tabular-nums ${cfg.color}`}>{pct}%</span>
      </div>
      {showBar && (
        <div className="confidence-gauge w-32">
          <div
            className={`h-full rounded-full transition-all duration-700 ${cfg.barColor}`}
            style={{ width: `${pct}%` }}
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Confidence: ${pct}%`}
          />
        </div>
      )}
    </div>
  )
}
