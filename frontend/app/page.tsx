'use client'

import { useCallback, useEffect, useState } from 'react'
import SearchInterface from '@/components/SearchInterface'
import Header from '@/components/Header'
import ScanHistory from '@/components/ScanHistory'
import AuthModal from '@/components/auth/AuthModal'
import ChatPanel from '@/components/ChatPanel'
import { useAuth } from '@/lib/auth'
import { ChatSessionItem, RepositoryResponse, listChatSessions } from '@/lib/api'

export default function Home() {
  const [results, setResults] = useState<RepositoryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sessions, setSessions] = useState<ChatSessionItem[]>([])
  const [chatSessionId, setChatSessionId] = useState<string | null>(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)

  const { user: authUser, loading: authLoading, logout } = useAuth()

  // Load chat sessions when authenticated
  const fetchSessions = useCallback(async () => {
    if (!authUser) {
      setSessions([])
      return
    }
    try {
      const data = await listChatSessions(50)
      setSessions(data.sessions)
    } catch (err) {
      console.error('Failed to load sessions', err)
    }
  }, [authUser])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const handleLogin = () => {
    setAuthModalOpen(true)
  }

  const handleLogout = async () => {
    logout()
  }

  const handleResults = (data: RepositoryResponse) => {
    setResults(data)
  }

  const handleSelectSession = (sessionId: string) => {
    setChatSessionId(sessionId)
  }

  const handleNewChat = () => {
    setChatSessionId(null)
  }
  
  const handleNewSessionCreated = (sessionId: string) => {
    setChatSessionId(sessionId)
    fetchSessions()
  }

  return (
    <main className="flex h-screen min-h-screen flex-col">
      <Header
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        authUser={authUser}
        authLoading={authLoading}
        onLogin={handleLogin}
        onLogout={handleLogout}
      />
      
      <section className="mx-auto flex w-full max-w-[1500px] flex-1 gap-0 overflow-hidden px-3 pb-4 pt-50 sm:px-5 sm:pt-50 lg:px-8">
        {sidebarOpen && (
          <aside className="fade-up hidden w-[320px] shrink-0 border-r border-[hsl(var(--border))] pr-4 lg:block h-full">
            <ScanHistory
              sessions={sessions}
              activeSessionId={chatSessionId}
              onSelectSession={handleSelectSession}
              onNewChat={handleNewChat}
            />
          </aside>
        )}

        <div className="min-w-0 flex-1 pl-0 lg:pl-6 flex flex-col h-full gap-4">
          <div className="shrink-0">
            <SearchInterface
              onResults={handleResults}
              onLoading={setLoading}
              onError={setError}
            />

            {loading && (
              <div className="fade-up mt-4 rounded-xl surface-panel p-5">
                <div className="terminal-chrome">
                  <span className="terminal-dot terminal-dot-danger" />
                  <span className="terminal-dot terminal-dot-warning" />
                  <span className="terminal-dot terminal-dot-success" />
                  <span className="ml-2 text-xs font-mono text-[hsl(var(--muted-foreground))]">excavation.log</span>
                </div>
                <div className="mt-4 flex items-center gap-3">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-[hsl(var(--primary))] border-t-transparent" />
                  <p className="text-sm text-[hsl(var(--foreground))]">Excavating commit history and generating evidence...</p>
                </div>
              </div>
            )}

            {error && (
              <div className="fade-up mt-4 rounded-xl border border-[hsl(var(--danger)/0.55)] bg-[hsl(var(--danger)/0.1)] p-4">
                <p className="text-sm text-[hsl(var(--danger))]">{error}</p>
              </div>
            )}

            {results && !loading && (
              <div className="fade-up mt-4 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface-1))] p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-bold text-[hsl(var(--foreground))]">{results.owner} / {results.name}</h3>
                    <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">Repository successfully mapped and currently actively syncing via Background Threads!</p>
                  </div>
                  <div className="rounded-full border border-[hsl(var(--success)/0.3)] bg-[hsl(var(--success)/0.1)] px-3 py-1 font-mono text-xs font-semibold text-[hsl(var(--success))]">
                    ACTIVE INGESTION
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex-1 overflow-hidden min-h-[400px]">
            <ChatPanel 
              sessionId={chatSessionId} 
              repositoryId={results?.id}
              onNewSessionCreated={handleNewSessionCreated}
            />
          </div>
        </div>
      </section>

      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </main>
  )
}
