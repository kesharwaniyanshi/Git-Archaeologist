'use client'

import { useEffect, useState } from 'react'
import SearchInterface from '@/components/SearchInterface'
import Header from '@/components/Header'
import ScanHistory from '@/components/ScanHistory'
import AuthModal from '@/components/auth/AuthModal'
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

  useEffect(() => {
    // Chat components are temporarily isolated for Phase 4 Repository Linking focus.
    setScans([])
  }, [])

  const handleLogin = () => {
    setAuthModalOpen(true)
  }

  const handleLogout = async () => {
    logout()
  }

  const handleResults = (data: any) => {
    setResults(data)
  }

  const handleSelectScan = async (scanId: string) => {}
  const handleNewChat = async () => {}

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

          {results && !loading && (
            <div className="fade-up mt-6 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface-1))] p-6">
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
      </section>

      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </main>
  )
}
