import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import type { Message, CitationEvent } from '../types'
import { Citations } from './Citations'
import { PredictionCard } from './PredictionCard'
import { ToolChip } from './ToolChip'
import type { ActiveToolChip } from '../types'

interface Props {
  message: Message
  /** Live tool chips shown only for the in-flight assistant message */
  liveToolChips?: ActiveToolChip[]
  /** Whether this message is currently streaming */
  isStreaming?: boolean
}

/** Replace [n] patterns in text with styled citation marker spans (utility exposed for tests) */
export function injectCitationMarkers(text: string, _citations: CitationEvent[]): string {
  // Actual injection is done via react-markdown custom components (makeCitationComponents).
  // This utility is kept for test-time inspection of the text pattern only.
  return text
}

// We use a custom text-node renderer to replace [n] with citation markers
function makeCitationComponents(citations: CitationEvent[]): Components {
  return {
    // Wrap paragraphs to inject citation markers inside them
    p({ children }) {
      return <p>{transformChildren(children, citations)}</p>
    },
    li({ children }) {
      return <li>{transformChildren(children, citations)}</li>
    },
  }
}

function transformChildren(
  children: ReactNode,
  citations: CitationEvent[],
): ReactNode {
  if (!Array.isArray(children)) {
    return transformNode(children, citations)
  }
  return children.map((child, i) => (
    <span key={i}>{transformNode(child, citations)}</span>
  ))
}

function transformNode(node: ReactNode, citations: CitationEvent[]): ReactNode {
  if (typeof node !== 'string') return node
  // Split on [n] markers
  const parts = node.split(/(\[\d+\])/)
  if (parts.length === 1) return node
  return parts.map((part, i) => {
    const match = /^\[(\d+)\]$/.exec(part)
    if (!match) return part
    const num = parseInt(match[1], 10)
    const citation = citations.find((c) => c.ref_num === num)
    return (
      <a
        key={i}
        href={citation?.url ?? '#'}
        target={citation?.url ? '_blank' : undefined}
        rel="noopener noreferrer"
        className="citation-marker"
        title={citation ? `${citation.provider}: ${citation.snippet ?? ''}` : `[${num}]`}
        aria-label={`Citation ${num}`}
      >
        {num}
      </a>
    )
  })
}

const INTENT_BADGE: Record<string, { label: string; className: string }> = {
  factual: { label: 'Factual', className: 'bg-sky-500/10 text-sky-400 border-sky-500/20' },
  prediction: { label: 'Prediction', className: 'bg-brand-500/10 text-brand-400 border-brand-500/20' },
  chitchat: { label: 'Chat', className: 'bg-slate-500/10 text-slate-400 border-slate-500/20' },
}

export function MessageBubble({ message, liveToolChips = [], isStreaming = false }: Props) {
  const isUser = message.role === 'user'
  const citations = message.citations ?? []
  const components = makeCitationComponents(citations)

  if (isUser) {
    return (
      <div className="flex justify-end mb-4 animate-fade-in">
        <div
          className="max-w-[75%] px-4 py-2.5 rounded-2xl rounded-br-sm
            bg-brand-600 text-white text-sm leading-relaxed shadow-lg"
        >
          {message.content}
        </div>
      </div>
    )
  }

  // Assistant bubble
  const intentBadge = message.intent ? INTENT_BADGE[message.intent] : null

  return (
    <div className="flex justify-start mb-6 animate-fade-in">
      {/* Avatar */}
      <div className="flex-none w-8 h-8 rounded-full bg-gradient-to-br from-brand-500 to-cyan-500
          flex items-center justify-center text-white text-xs font-bold shadow-lg mr-3 mt-0.5 shrink-0">
        SO
      </div>

      <div className="max-w-[85%] min-w-0">
        {/* Intent badge */}
        {intentBadge && (
          <span
            className={`inline-block mb-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold
              border tracking-wide uppercase ${intentBadge.className}`}
          >
            {intentBadge.label}
          </span>
        )}

        {/* Tool chips */}
        {liveToolChips.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {liveToolChips.map((chip) => (
              <ToolChip key={chip.name} chip={chip} />
            ))}
          </div>
        )}

        {/* Message content */}
        <div
          className="px-4 py-3 rounded-2xl rounded-tl-sm
            bg-surface-800 border border-surface-700 shadow-md"
        >
          {message.content ? (
            <div className="prose-chat" data-testid="message-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {message.content}
              </ReactMarkdown>
            </div>
          ) : isStreaming ? (
            <span className="flex gap-1 items-center py-1" aria-label="Loading">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </span>
          ) : null}

          {/* Streaming cursor */}
          {isStreaming && message.content && (
            <span
              className="inline-block w-0.5 h-4 bg-brand-400 ml-0.5 align-middle animate-pulse"
              aria-hidden="true"
            />
          )}
        </div>

        {/* Prediction card */}
        {message.prediction && <PredictionCard prediction={message.prediction} />}

        {/* Citations */}
        {citations.length > 0 && (
          <div className="px-4 py-3 mt-1 rounded-xl bg-surface-800/60 border border-surface-700">
            <Citations citations={citations} />
          </div>
        )}
      </div>
    </div>
  )
}

