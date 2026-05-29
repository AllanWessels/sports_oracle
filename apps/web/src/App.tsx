import { useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { ChatWindow } from './components/ChatWindow'
import { useConversationsStore } from './store/conversations'

export function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { loadConversation, startNewConversation } = useConversationsStore()

  const handleSelectConversation = (id: string) => {
    loadConversation(id).catch(() => undefined)
    setSidebarOpen(false)
  }

  const handleNewChat = () => {
    startNewConversation()
    setSidebarOpen(false)
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface-900">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar — always visible on lg+, drawer on mobile */}
      <div
        className={`fixed inset-y-0 left-0 z-30 transition-transform duration-300 lg:static lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <Sidebar
          onSelectConversation={handleSelectConversation}
          onNewChat={handleNewChat}
        />
      </div>

      {/* Main content */}
      <main className="flex flex-col flex-1 min-w-0 h-full">
        {/* Mobile topbar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-700 lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-lg hover:bg-surface-700 text-slate-400 hover:text-white transition-colors"
            aria-label="Open sidebar"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 12h18M3 6h18M3 18h18" strokeLinecap="round" />
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-brand-500 to-cyan-500
                flex items-center justify-center text-white text-[10px] font-bold">
              SO
            </div>
            <span className="text-sm font-semibold text-white">Sports Oracle</span>
          </div>
        </div>

        <ChatWindow />
      </main>
    </div>
  )
}
