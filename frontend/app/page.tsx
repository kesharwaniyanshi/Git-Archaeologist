'use client'

import { useState } from 'react'
import SearchInterface from '@/components/SearchInterface'
import ResultsView from '@/components/ResultsView'
import Header from '@/components/Header'
import ScanHistory from '@/components/ScanHistory'

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

  const handleResults = (data: any) => {
    setResults(data)
    if (data?.chat_session_id) {
      setChatSessionId(data.chat_session_id)
    }
    if (!lastQuery || !data) return

    const record: ScanRecord = {
      id: `${Date.now()}`,
      query: lastQuery,
      createdAt: new Date().toISOString(),
      confidence: data.confidence,
      resultsCount: data.results?.length ?? 0,
    }
    setScans((prev) => [record, ...prev].slice(0, 10))
  }

  return (
    <main className="min-h-screen">
      <Header sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen((v) => !v)} />
      <section className="mx-auto flex w-full max-w-[1500px] gap-0 px-3 pb-8 pt-4 sm:px-5 lg:px-8">
        {sidebarOpen && (
          <aside className="fade-up hidden w-[320px] shrink-0 border-r border-[hsl(var(--border))] pr-4 lg:block">
            <ScanHistory scans={scans} />
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
    </main>
  )
}
