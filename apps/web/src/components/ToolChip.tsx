import type { ActiveToolChip } from '../types'

interface Props {
  chip: ActiveToolChip
}

const TOOL_ICONS: Record<string, string> = {
  search: '🔍',
  rag: '📚',
  stats: '📊',
  odds: '🎯',
  weather: '🌤️',
  news: '📰',
}

function getIcon(name: string): string {
  const lower = name.toLowerCase()
  for (const [key, icon] of Object.entries(TOOL_ICONS)) {
    if (lower.includes(key)) return icon
  }
  return '⚡'
}

export function ToolChip({ chip }: Props) {
  return (
    <span className="tool-chip" role="status" aria-label={`Consulting ${chip.name}`}>
      <span aria-hidden="true">{getIcon(chip.name)}</span>
      <span className="capitalize">
        {chip.status === 'running' ? `Consulting ${chip.name}…` : `${chip.name}: ${chip.status}`}
      </span>
    </span>
  )
}
