'use client'

import { useEffect, useState } from 'react'
import SearchInterface from '@/components/SearchInterface'
import ResultsView from '@/components/ResultsView'
import Header from '@/components/Header'
import ScanHistory from '@/components/ScanHistory'
import AuthModal from '@/components/auth/AuthModal'
import {
  createChatSession,
  getChatHistory,
  listChatSessions,
} from '@/lib/api'
import { useAuth } from '@/lib/auth'

type ScanRecord = {
  id: string
  query: string
  createdAt: string
  confidence?: string
  resultsCount: number
}

export default function Home() {
  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [lastQuery, setLastQuery] = useState('')
  const [scans, setScans] = useState<ScanRecord[]>([])
  const [chatSessionId, setChatSessionId] = useState<string | null>(null)
  const [activeScanId, setActiveScanId] = useState<string | null>(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)

  const { user: authUser, loading: authLoading, logout } = useAuth()

  const loadSessions = async () => {
    try {
      const data = await listChatSessions(undefined, 50)
      const mapped: ScanRecord[] = (data.sessions || []).map((session: any) => ({
        id: session.chat_session_id,
        query: session.last_user_query || 'New chat session',
        createdAt: session.updated_at || session.created_at || new Date().toISOString(),
        resultsCount: Math.max(0, Math.floor((session.message_count || 0) / 2)),
      }))
      setScans(mapped)
    } catch {
      // Keep local experience functional even if chat listing fails.
    }
  }

  useEffect(() => {
    loadSessions()
  }, [])

  const handleLogin = () => {
    setAuthModalOpen(true)
  }

  const handleLogout = async () => {
    logout()
  }

  const handleResults = (data: any) => {
    setResults(data)
    if (data?.chat_session_id) {
      setChatSessionId(data.chat_session_id)
      setActiveScanId(data.chat_session_id)
    }
    if (!lastQuery || !data) return

    const record: ScanRecord = {
      id: data?.chat_session_id || `${Date.now()}`,
      query: lastQuery,
      createdAt: new Date().toISOString(),
      confidence: data.confidence,
      resultsCount: data.results?.length ?? 0,
    }
    setScans((prev) => {
      const withoutCurrent = prev.filter((item) => item.id !== record.id)
      return [record, ...withoutCurrent].slice(0, 50)
    })
  }

  const handleSelectScan = async (scanId: string) => {
    setActiveScanId(scanId)
    setChatSessionId(scanId)
    setError(null)
    setLoading(true)
    try {
      const history = await getChatHistory(scanId)
      const messages: any[] = history?.messages || []
      const lastUser = [...messages].reverse().find((msg) => msg.role === 'user')
      const lastAssistant = [...messages].reverse().find((msg) => msg.role === 'assistant')

      if (lastUser?.content) {
        setLastQuery(lastUser.content)
      }

      setResults({
        query: lastUser?.content || '',
        answer: lastAssistant?.content || 'No assistant response in this chat yet.',
        evidence_count: lastAssistant?.metadata?.evidence_count || 0,
        chat_session_id: scanId,
      })
    } catch (err: any) {
      setError(err?.message || 'Failed to load chat history')
    } finally {
      setLoading(false)
    }
  }

  const handleNewChat = async () => {
    setError(null)
    setResults(null)
    setLastQuery('')
    try {
      const created = await createChatSession()
      const newId = created?.chat_session_id
      if (!newId) {
        return
      }
      setChatSessionId(newId)
      setActiveScanId(newId)
      setScans((prev) => [
        {
          id: newId,
          query: 'New chat session',
          createdAt: new Date().toISOString(),
          resultsCount: 0,
        },
        ...prev,
      ])
    } catch (err: any) {
      setError(err?.message || 'Failed to create new chat session')
    }
  }

  return (
    <main className="min-h-screen">
      <Header
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        authUser={authUser}
        authLoading={authLoading}
        onLogin={handleLogin}
        onLogout={handleLogout}
      />
      <section className="mx-auto flex w-full max-w-[1500px] gap-0 px-3 pb-8 pt-4 sm:px-5 lg:px-8">
        {sidebarOpen && (
          <aside className="fade-up hidden w-[320px] shrink-0 border-r border-[hsl(var(--border))] pr-4 lg:block">
            <ScanHistory
              scans={scans}
              activeScanId={activeScanId}
              onSelectScan={handleSelectScan}
              onNewChat={handleNewChat}
            />
          </aside>
        )}

        <div className="min-w-0 flex-1 pl-0 lg:pl-6">
          <SearchInterface
            onResults={handleResults}
            onLoading={setLoading}
            onError={setError}
            onQuerySubmitted={setLastQuery}
            chatSessionId={chatSessionId}
          />

          {loading && (
            <div className="fade-up mt-6 rounded-xl surface-panel p-5">
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
            <div className="fade-up mt-6 rounded-xl border border-[hsl(var(--danger)/0.55)] bg-[hsl(var(--danger)/0.1)] p-4">
              <p className="text-sm text-[hsl(var(--danger))]">{error}</p>
            </div>
          )}

          {results && !loading && <ResultsView results={results} />}
        </div>
      </section>

      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </main>
  )
}
