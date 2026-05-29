import { fetchEventSource } from '@microsoft/fetch-event-source'
import type {
  ConversationMessages,
  ConversationSummary,
  CitationEvent,
  DoneEvent,
  ErrorEvent,
  IntentEvent,
  PredictionEvent,
  SSEEventMap,
  TokenEvent,
  ToolEvent,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

// ── Typed event handler callbacks ─────────────────────────────────────────────

export interface StreamHandlers {
  onIntent?: (data: IntentEvent) => void
  onTool?: (data: ToolEvent) => void
  onToken?: (data: TokenEvent) => void
  onCitation?: (data: CitationEvent) => void
  onPrediction?: (data: PredictionEvent) => void
  onDone?: (data: DoneEvent) => void
  onError?: (data: ErrorEvent) => void
  onOpen?: () => void
  onClose?: () => void
}

function parseEvent(eventType: string, rawData: string): SSEEventMap | null {
  try {
    const data: unknown = JSON.parse(rawData)
    switch (eventType) {
      case 'intent':
        return { type: 'intent', data: data as IntentEvent }
      case 'tool':
        return { type: 'tool', data: data as ToolEvent }
      case 'token':
        return { type: 'token', data: data as TokenEvent }
      case 'citation':
        return { type: 'citation', data: data as CitationEvent }
      case 'prediction':
        return { type: 'prediction', data: data as PredictionEvent }
      case 'done':
        return { type: 'done', data: data as DoneEvent }
      case 'error':
        return { type: 'error', data: data as ErrorEvent }
      default:
        return null
    }
  } catch {
    return null
  }
}

// ── streamChat ─────────────────────────────────────────────────────────────────

export function streamChat(
  message: string,
  conversationId: string | undefined,
  handlers: StreamHandlers,
): AbortController {
  const ctrl = new AbortController()

  const body: Record<string, string> = { message }
  if (conversationId) body['conversation_id'] = conversationId

  fetchEventSource(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: ctrl.signal,

    onopen: async (response) => {
      if (response.ok) {
        handlers.onOpen?.()
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
    },

    onmessage: (ev) => {
      const parsed = parseEvent(ev.event, ev.data)
      if (!parsed) return

      switch (parsed.type) {
        case 'intent':
          handlers.onIntent?.(parsed.data)
          break
        case 'tool':
          handlers.onTool?.(parsed.data)
          break
        case 'token':
          handlers.onToken?.(parsed.data)
          break
        case 'citation':
          handlers.onCitation?.(parsed.data)
          break
        case 'prediction':
          handlers.onPrediction?.(parsed.data)
          break
        case 'done':
          handlers.onDone?.(parsed.data)
          break
        case 'error':
          handlers.onError?.(parsed.data)
          break
      }
    },

    onclose: () => {
      handlers.onClose?.()
    },

    onerror: (err) => {
      if (err instanceof Error && err.name === 'AbortError') return
      handlers.onError?.({ message: err instanceof Error ? err.message : 'Stream error' })
      throw err // stop retrying
    },
  }).catch((err: unknown) => {
    if (err instanceof Error && err.name !== 'AbortError') {
      handlers.onError?.({ message: err.message })
    }
  })

  return ctrl
}

// ── REST helpers ───────────────────────────────────────────────────────────────

export async function listConversations(): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_BASE}/conversations`)
  if (!res.ok) throw new Error(`Failed to list conversations: ${res.status}`)
  return res.json() as Promise<ConversationSummary[]>
}

export async function getMessages(id: string): Promise<ConversationMessages> {
  const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(id)}/messages`)
  if (!res.ok) throw new Error(`Failed to load messages: ${res.status}`)
  return res.json() as Promise<ConversationMessages>
}
