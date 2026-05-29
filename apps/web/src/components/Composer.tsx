import { useCallback, useRef, useState, type KeyboardEvent } from 'react'

interface Props {
  onSend: (message: string) => void
  disabled?: boolean
  isStreaming?: boolean
  onAbort?: () => void
}

export function Composer({ onSend, disabled = false, isStreaming = false, onAbort }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [value, disabled, onSend])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const handleInput = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [])

  const canSend = value.trim().length > 0 && !disabled

  return (
    <div className="border-t border-surface-700 bg-surface-800/80 backdrop-blur px-4 py-3">
      <div
        className={`flex items-end gap-3 rounded-xl border transition-colors
          ${disabled ? 'border-surface-700 bg-surface-800' : 'border-surface-600 bg-surface-700 focus-within:border-brand-500'}`}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          disabled={disabled && !isStreaming}
          rows={1}
          placeholder={isStreaming ? 'Oracle is thinking…' : 'Ask the Sports Oracle…'}
          aria-label="Message input"
          className="flex-1 bg-transparent resize-none px-4 py-3 text-sm text-slate-100
            placeholder:text-slate-500 focus:outline-none disabled:opacity-50
            min-h-[44px] max-h-[200px] leading-relaxed"
        />

        <div className="flex items-center gap-1.5 pr-2 pb-2">
          {isStreaming && onAbort && (
            <button
              onClick={onAbort}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                bg-rose-500/10 text-rose-400 border border-rose-500/20
                hover:bg-rose-500/20 transition-colors"
              aria-label="Stop streaming"
            >
              <span className="w-2.5 h-2.5 rounded-sm bg-rose-400" />
              Stop
            </button>
          )}
          <button
            onClick={handleSend}
            disabled={!canSend}
            aria-label="Send message"
            className={`flex items-center justify-center w-9 h-9 rounded-lg transition-all
              ${
                canSend
                  ? 'bg-brand-500 hover:bg-brand-400 text-white shadow-md hover:shadow-brand-500/25'
                  : 'bg-surface-600 text-slate-500 cursor-not-allowed'
              }`}
          >
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M22 2L11 13" />
              <path d="M22 2L15 22 11 13 2 9l20-7z" />
            </svg>
          </button>
        </div>
      </div>

      <p className="text-center text-[10px] text-slate-600 mt-2">
        Press Enter to send · Shift+Enter for new line
      </p>
    </div>
  )
}
