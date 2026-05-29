import { create } from 'zustand'
import type { ConversationSummary, Message, CitationEvent, PredictionEvent, Intent } from '../types'
import { listConversations as apiFetchConversations, getMessages as apiFetchMessages } from '../api/client'

interface ConversationsState {
  // List panel
  conversations: ConversationSummary[]
  loadingConversations: boolean
  conversationsError: string | null

  // Active conversation
  activeConversationId: string | null
  messages: Message[]
  loadingMessages: boolean
  messagesError: string | null

  // Actions
  fetchConversations: () => Promise<void>
  loadConversation: (id: string) => Promise<void>
  startNewConversation: () => void
  setActiveConversationId: (id: string) => void

  // Live message mutations (called from useChatStream)
  appendUserMessage: (content: string) => void
  appendAssistantMessage: (content: string) => void
  updateLastAssistantTokens: (text: string) => void
  setLastAssistantIntent: (intent: Intent) => void
  addLastAssistantCitation: (citation: CitationEvent) => void
  setLastAssistantPrediction: (prediction: PredictionEvent) => void
  finaliseConversation: (conversationId: string, messageId: string) => void
  upsertConversationSummary: (summary: ConversationSummary) => void
}

export const useConversationsStore = create<ConversationsState>((set, get) => ({
  conversations: [],
  loadingConversations: false,
  conversationsError: null,

  activeConversationId: null,
  messages: [],
  loadingMessages: false,
  messagesError: null,

  fetchConversations: async () => {
    set({ loadingConversations: true, conversationsError: null })
    try {
      const conversations = await apiFetchConversations()
      set({ conversations, loadingConversations: false })
    } catch (err) {
      set({
        loadingConversations: false,
        conversationsError: err instanceof Error ? err.message : 'Failed to load conversations',
      })
    }
  },

  loadConversation: async (id: string) => {
    set({ loadingMessages: true, messagesError: null, activeConversationId: id, messages: [] })
    try {
      const { messages } = await apiFetchMessages(id)
      set({ messages, loadingMessages: false })
    } catch (err) {
      set({
        loadingMessages: false,
        messagesError: err instanceof Error ? err.message : 'Failed to load messages',
      })
    }
  },

  startNewConversation: () => {
    set({ activeConversationId: null, messages: [] })
  },

  setActiveConversationId: (id: string) => {
    set({ activeConversationId: id })
  },

  appendUserMessage: (content: string) => {
    const msg: Message = { role: 'user', content, created_at: new Date().toISOString() }
    set((s) => ({ messages: [...s.messages, msg] }))
  },

  appendAssistantMessage: (_content: string) => {
    const msg: Message = {
      role: 'assistant',
      content: '',
      citations: [],
      prediction: undefined,
      created_at: new Date().toISOString(),
    }
    set((s) => ({ messages: [...s.messages, msg] }))
  },

  updateLastAssistantTokens: (text: string) => {
    set((s) => {
      const msgs = [...s.messages]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, content: last.content + text }
      }
      return { messages: msgs }
    })
  },

  setLastAssistantIntent: (intent: Intent) => {
    set((s) => {
      const msgs = [...s.messages]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, intent }
      }
      return { messages: msgs }
    })
  },

  addLastAssistantCitation: (citation: CitationEvent) => {
    set((s) => {
      const msgs = [...s.messages]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = {
          ...last,
          citations: [...(last.citations ?? []), citation],
        }
      }
      return { messages: msgs }
    })
  },

  setLastAssistantPrediction: (prediction: PredictionEvent) => {
    set((s) => {
      const msgs = [...s.messages]
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, prediction }
      }
      return { messages: msgs }
    })
  },

  finaliseConversation: (conversationId: string, _messageId: string) => {
    const { activeConversationId } = get()
    if (!activeConversationId) {
      set({ activeConversationId: conversationId })
    }
  },

  upsertConversationSummary: (summary: ConversationSummary) => {
    set((s) => {
      const existing = s.conversations.findIndex((c) => c.id === summary.id)
      if (existing >= 0) {
        const next = [...s.conversations]
        next[existing] = summary
        return { conversations: next }
      }
      return { conversations: [summary, ...s.conversations] }
    })
  },
}))
