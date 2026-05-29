import type { CitationEvent } from '../types'

interface Props {
  citations: CitationEvent[]
}

const SOURCE_LABELS: Record<CitationEvent['source_type'], string> = {
  api: 'API',
  rag_doc: 'Document',
  rag_news: 'News',
}

const SOURCE_ICONS: Record<CitationEvent['source_type'], string> = {
  api: '🔌',
  rag_doc: '📄',
  rag_news: '📰',
}

function formatFetchedAt(ts?: string): string {
  if (!ts) return ''
  try {
    return new Intl.DateTimeFormat('en-US', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(ts))
  } catch {
    return ts
  }
}

export function Citations({ citations }: Props) {
  if (citations.length === 0) return null

  return (
    <div className="mt-3 pt-3 border-t border-surface-700">
      <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
        Sources
      </p>
      <ol className="space-y-2 list-none m-0 p-0">
        {citations.map((c) => (
          <li key={c.ref_num} className="flex gap-2.5 text-xs">
            <span className="flex-none flex items-center justify-center w-5 h-5 rounded bg-brand-900 text-brand-400 text-[10px] font-bold mt-0.5">
              {c.ref_num}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span aria-hidden="true">{SOURCE_ICONS[c.source_type]}</span>
                <span className="font-medium text-slate-300">{c.provider}</span>
                <span className="px-1.5 py-0.5 rounded text-[10px] bg-surface-700 text-slate-400">
                  {SOURCE_LABELS[c.source_type]}
                </span>
                {c.fetched_at && (
                  <span className="text-slate-500 text-[10px]">
                    {formatFetchedAt(c.fetched_at)}
                  </span>
                )}
              </div>
              {c.snippet && (
                <p className="mt-0.5 text-slate-400 italic line-clamp-2">"{c.snippet}"</p>
              )}
              {c.url && (
                <a
                  href={c.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand-400 hover:text-brand-300 truncate block mt-0.5 transition-colors"
                >
                  {c.url}
                </a>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
