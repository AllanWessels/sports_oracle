import { useEffect, useRef } from 'react'
import { useConversationsStore } from '../store/conversations'
import { useChatStream } from '../hooks/useChatStream'
import { MessageBubble } from './MessageBubble'
import { Composer } from './Composer'

export function ChatWindow() {
  const { messages, loadingMessages, messagesError } = useConversationsStore()
  const { streaming, sendMessage, abort } = useChatStream()
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages / tokens
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col h-full min-w-0">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-1">
        {loadingMessages && (
          <div className="flex justify-center py-12">
            <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {messagesError && (
          <div className="max-w-lg mx-auto p-4 rounded-xl bg-rose-500/10 border border-rose-500/20">
            <p className="text-sm text-rose-400">{messagesError}</p>
          </div>
        )}

        {!loadingMessages && messages.length === 0 && !streaming.isStreaming && (
          <WelcomeScreen onSend={sendMessage} />
        )}

        {messages.map((msg, i) => {
          const isLastAssistant =
            msg.role === 'assistant' && i === messages.length - 1
          return (
            <MessageBubble
              key={i}
              message={msg}
              liveToolChips={isLastAssistant && streaming.isStreaming ? streaming.toolChips : []}
              isStreaming={isLastAssistant && streaming.isStreaming}
            />
          )
        })}

        {/* Error banner */}
        {streaming.error && (
          <div className="flex justify-start mb-4">
            <div className="max-w-[80%] px-4 py-3 rounded-xl bg-rose-500/10 border border-rose-500/20">
              <p className="text-sm text-rose-400">
                <span className="font-semibold">Error: </span>
                {streaming.error}
              </p>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <Composer
        onSend={sendMessage}
        disabled={streaming.isStreaming}
        isStreaming={streaming.isStreaming}
        onAbort={abort}
      />
    </div>
  )
}

interface WelcomeScreenProps {
  onSend: (message: string) => void
}

function WelcomeScreen({ onSend }: WelcomeScreenProps) {
  const EXAMPLES = [
    "Who will win the Champions League this season?",
    "What are Erling Haaland's stats this season?",
    'Predict the outcome of Real Madrid vs Barcelona',
    'How has LeBron James performed in the last 10 games?',
  ]

  return (
    <div className="flex flex-col items-center justify-center h-full py-12 px-6 animate-fade-in">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-cyan-500
          flex items-center justify-center text-white text-2xl font-bold shadow-xl mb-5">
        SO
      </div>
      <h2 className="text-2xl font-bold text-white mb-2">Sports Oracle</h2>
      <p className="text-slate-400 text-center max-w-sm mb-8 leading-relaxed">
        Ask me anything about sports — stats, predictions, fixtures, records, or just chat.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
        {EXAMPLES.map((ex) => (
          <ExampleButton key={ex} text={ex} onSend={onSend} />
        ))}
      </div>

      <p className="mt-8 text-[11px] text-slate-600 text-center max-w-xs">
        Predictions are informational only and are not betting advice.
      </p>
    </div>
  )
}

interface ExampleButtonProps {
  text: string
  onSend: (message: string) => void
}

function ExampleButton({ text, onSend }: ExampleButtonProps) {
  return (
    <button
      onClick={() => onSend(text)}
      className="text-left px-4 py-3 rounded-xl border border-surface-600
        bg-surface-800 hover:bg-surface-700 hover:border-brand-500/50
        text-sm text-slate-300 hover:text-white transition-all
        group flex items-center gap-3"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-brand-500 group-hover:bg-brand-400 shrink-0 transition-colors" />
      {text}
    </button>
  )
}
