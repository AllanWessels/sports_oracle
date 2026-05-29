import { useCallback, useRef, useState } from 'react'
import { streamChat } from '../api/client'
import { useConversationsStore } from '../store/conversations'
import type { ActiveToolChip, StreamingMessage } from '../types'

const INITIAL_STREAMING: StreamingMessage = {
  tokens: '',
  toolChips: [],
  citations: [],
  prediction: null,
  intent: null,
  isStreaming: false,
  error: null,
}

export function useChatStream() {
  const [streaming, setStreaming] = useState<StreamingMessage>(INITIAL_STREAMING)
  const abortRef = useRef<AbortController | null>(null)

  const store = useConversationsStore()

  const sendMessage = useCallback(
    (message: string) => {
      if (streaming.isStreaming) return

      const conversationId = store.activeConversationId ?? undefined

      // Optimistically append user message
      store.appendUserMessage(message)
      // Add a placeholder assistant message
      store.appendAssistantMessage('')

      setStreaming({
        tokens: '',
        toolChips: [],
        citations: [],
        prediction: null,
        intent: null,
        isStreaming: true,
        error: null,
      })

      const ctrl = streamChat(message, conversationId, {
        onOpen: () => {
          setStreaming((s) => ({ ...s, isStreaming: true, error: null }))
        },

        onIntent: (data) => {
          store.setLastAssistantIntent(data.intent)
          setStreaming((s) => ({ ...s, intent: data.intent }))
        },

        onTool: (data) => {
          const chip: ActiveToolChip = { name: data.name, status: data.status }
          setStreaming((s) => ({
            ...s,
            toolChips: [...s.toolChips.filter((t) => t.name !== data.name), chip],
          }))
        },

        onToken: (data) => {
          store.updateLastAssistantTokens(data.text)
          setStreaming((s) => ({ ...s, tokens: s.tokens + data.text }))
        },

        onCitation: (data) => {
          store.addLastAssistantCitation(data)
          setStreaming((s) => ({ ...s, citations: [...s.citations, data] }))
        },

        onPrediction: (data) => {
          store.setLastAssistantPrediction(data)
          setStreaming((s) => ({ ...s, prediction: data }))
        },

        onDone: (data) => {
          store.finaliseConversation(data.conversation_id, data.message_id)
          // Refresh conversation list in the background
          store.fetchConversations().catch(() => undefined)
          setStreaming((s) => ({ ...s, isStreaming: false, toolChips: [] }))
        },

        onError: (data) => {
          setStreaming((s) => ({ ...s, isStreaming: false, error: data.message }))
        },

        onClose: () => {
          setStreaming((s) => ({ ...s, isStreaming: false }))
        },
      })

      abortRef.current = ctrl
    },
    [streaming.isStreaming, store],
  )

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setStreaming((s) => ({ ...s, isStreaming: false }))
  }, [])

  return { streaming, sendMessage, abort }
}
