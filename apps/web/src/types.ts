// ── SSE Event types ────────────────────────────────────────────────────────────

export type Intent = 'factual' | 'prediction' | 'chitchat'

export interface IntentEvent {
  intent: Intent
}

export interface ToolEvent {
  name: string
  status: string
}

export interface TokenEvent {
  text: string
}

export interface CitationEvent {
  ref_num: number
  source_type: 'api' | 'rag_doc' | 'rag_news'
  provider: string
  url?: string
  snippet?: string
  fetched_at?: string
}

export type ConfidenceLabel = 'low' | 'medium' | 'high'

export interface KeyFactor {
  name: string
  direction: string
  weight: number
  detail?: string
}

export interface PredictionEvent {
  sport: string
  fixture_ref: string
  pick: string
  win_probability: number
  draw_probability?: number
  confidence_num: number
  confidence_label: ConfidenceLabel
  key_factors: KeyFactor[]
  caveats: string[]
  disclaimer: string
}

export interface DoneEvent {
  conversation_id: string
  message_id: string
}

export interface ErrorEvent {
  message: string
}

// ── Discriminated SSE union ────────────────────────────────────────────────────

export type SSEEventMap =
  | { type: 'intent'; data: IntentEvent }
  | { type: 'tool'; data: ToolEvent }
  | { type: 'token'; data: TokenEvent }
  | { type: 'citation'; data: CitationEvent }
  | { type: 'prediction'; data: PredictionEvent }
  | { type: 'done'; data: DoneEvent }
  | { type: 'error'; data: ErrorEvent }

// ── REST response types ────────────────────────────────────────────────────────

export interface ConversationSummary {
  id: string
  title: string
  updated_at: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  intent?: Intent
  created_at?: string
  citations?: CitationEvent[]
  prediction?: PredictionEvent
}

export interface ConversationMessages {
  messages: Message[]
}

// ── Streaming state ────────────────────────────────────────────────────────────

export interface ActiveToolChip {
  name: string
  status: string
}

export interface StreamingMessage {
  tokens: string
  toolChips: ActiveToolChip[]
  citations: CitationEvent[]
  prediction: PredictionEvent | null
  intent: Intent | null
  isStreaming: boolean
  error: string | null
}
