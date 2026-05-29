import { useEffect } from 'react'
import { useConversationsStore } from '../store/conversations'
import type { ConversationSummary } from '../types'

interface Props {
  onSelectConversation: (id: string) => void
  onNewChat: () => void
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffDays === 0) {
      return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(d)
    }
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) {
      return new Intl.DateTimeFormat('en-US', { weekday: 'short' }).format(d)
    }
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(d)
  } catch {
    return ''
  }
}

interface ConversationItemProps {
  conv: ConversationSummary
  isActive: boolean
  onClick: () => void
}

function ConversationItem({ conv, isActive, onClick }: ConversationItemProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 rounded-lg transition-all group
        ${
          isActive
            ? 'bg-brand-600/20 border border-brand-500/30 text-white'
            : 'hover:bg-surface-700 text-slate-300 hover:text-white border border-transparent'
        }`}
      aria-current={isActive ? 'page' : undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium truncate leading-snug flex-1">
          {conv.title || 'New conversation'}
        </span>
        <span className="text-[10px] text-slate-500 shrink-0 mt-0.5 group-hover:text-slate-400 transition-colors">
          {formatDate(conv.updated_at)}
        </span>
      </div>
    </button>
  )
}

export function Sidebar({ onSelectConversation, onNewChat }: Props) {
  const { conversations, loadingConversations, conversationsError, fetchConversations, activeConversationId } =
    useConversationsStore()

  useEffect(() => {
    fetchConversations().catch(() => undefined)
  }, [fetchConversations])

  return (
    <aside className="flex flex-col h-full bg-surface-900 border-r border-surface-700 w-64 shrink-0">
      {/* Brand header */}
      <div className="px-4 py-4 border-b border-surface-700">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-cyan-500
              flex items-center justify-center text-white text-xs font-bold shadow-lg">
            SO
          </div>
          <div>
            <h1 className="text-sm font-bold text-white leading-tight">Sports Oracle</h1>
            <p className="text-[10px] text-slate-500">AI sports intelligence</p>
          </div>
        </div>
      </div>

      {/* New chat button */}
      <div className="px-3 py-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg
            bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium
            transition-all shadow-md hover:shadow-brand-600/30"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 5v14M5 12h14" strokeLinecap="round" />
          </svg>
          New Chat
        </button>
      </div>

      {/* Conversations list */}
      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
        {loadingConversations && (
          <div className="flex justify-center py-8">
            <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {conversationsError && (
          <div className="mx-2 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
            <p className="text-xs text-rose-400">{conversationsError}</p>
            <button
              onClick={() => fetchConversations().catch(() => undefined)}
              className="mt-1 text-xs text-rose-400 hover:text-rose-300 underline"
            >
              Retry
            </button>
          </div>
        )}

        {!loadingConversations && !conversationsError && conversations.length === 0 && (
          <p className="text-xs text-slate-500 text-center py-8 px-3">
            No conversations yet.
            <br />
            Ask your first question!
          </p>
        )}

        {conversations.map((conv) => (
          <ConversationItem
            key={conv.id}
            conv={conv}
            isActive={conv.id === activeConversationId}
            onClick={() => onSelectConversation(conv.id)}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-surface-700">
        <p className="text-[10px] text-slate-600 leading-snug">
          Predictions are informational only and not betting advice.
        </p>
      </div>
    </aside>
  )
}
