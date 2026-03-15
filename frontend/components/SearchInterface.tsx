'use client'

import { useState } from 'react'
import { Database, Play, ScanSearch, SlidersHorizontal, Sparkles } from 'lucide-react'
import { analyzeQuery } from '@/lib/api'

interface SearchInterfaceProps {
  onResults: (results: any) => void
  onLoading: (loading: boolean) => void
  onError: (error: string | null) => void
  onQuerySubmitted?: (query: string) => void
  chatSessionId?: string | null
}

export default function SearchInterface({ onResults, onLoading, onError, onQuerySubmitted, chatSessionId }: SearchInterfaceProps) {
  const [query, setQuery] = useState('')
  const [repoPath, setRepoPath] = useState('/Users/yanshikesharwani/vscode/Git Archaeologist')
  const [topK, setTopK] = useState(5)
  const [maxCommits, setMaxCommits] = useState(500)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) {
      onError('Please enter a question')
      return
    }

    onLoading(true)
    onError(null)
    onResults(null)
    onQuerySubmitted?.(query)

    try {
      const data = await analyzeQuery({
        repo_path: repoPath,
        query: query,
        chat_session_id: chatSessionId ?? undefined,
        top_k: topK,
        max_commits: maxCommits,
      })
      onResults(data)
    } catch (err: any) {
      onError(err.message || 'Failed to analyze repository')
    } finally {
      onLoading(false)
    }
  }

  return (
    <div className="fade-up rounded-2xl surface-panel panel-hover p-5 sm:p-6">
      <div className="terminal-chrome">
        <span className="terminal-dot terminal-dot-danger" />
        <span className="terminal-dot terminal-dot-warning" />
        <span className="terminal-dot terminal-dot-success" />
        <span className="ml-2 text-xs font-mono text-[hsl(var(--muted-foreground))]">command-bar.tsx</span>
      </div>

      <form onSubmit={handleSubmit} className="mt-4 space-y-5">
        <div>
          <label className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-[hsl(var(--muted-foreground))]">
            <Database className="h-3.5 w-3.5" />
            Repository Path
          </label>
          <input
            type="text"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            className="electric-ring h-11 w-full rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface-0)/0.8)] px-3 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))]"
            placeholder="/path/to/your/repo"
          />
        </div>

        <div>
          <label className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-[hsl(var(--muted-foreground))]">
            <ScanSearch className="h-3.5 w-3.5" />
            Your Question
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={4}
            className="electric-ring w-full resize-none rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface-0)/0.8)] px-3 py-2 text-sm leading-6 text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))]"
            placeholder="Why was authentication changed? What caused the performance improvement?"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-[hsl(var(--muted-foreground))]">
              <Sparkles className="h-3.5 w-3.5" />
              Top Results
            </label>
            <input
              type="number"
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value))}
              min={1}
              max={20}
              className="electric-ring h-11 w-full rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface-0)/0.8)] px-3 text-sm text-[hsl(var(--foreground))]"
            />
          </div>

          <div>
            <label className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-[hsl(var(--muted-foreground))]">
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Max Commits <span className="ml-1 font-mono text-[hsl(var(--primary))]">{maxCommits}</span>
            </label>
            <input
              type="range"
              value={maxCommits}
              onChange={(e) => setMaxCommits(parseInt(e.target.value))}
              min={50}
              max={5000}
              step={50}
              className="mt-3 h-2 w-full cursor-pointer appearance-none rounded-lg bg-[hsl(var(--surface-3))] accent-[hsl(var(--primary))]"
            />
          </div>
        </div>

        <button
          type="submit"
          className="glow-electric electric-ring w-full rounded-lg border border-[hsl(var(--primary)/0.5)] bg-[hsl(var(--primary))] px-4 py-3 text-sm font-semibold text-[hsl(var(--surface-0))] transition duration-200 hover:-translate-y-[1px] hover:bg-[hsl(var(--primary-glow))]"
        >
          <span className="inline-flex items-center gap-2">
            <Play className="h-4 w-4" />
            Excavate Commit History
          </span>
        </button>
      </form>
    </div>
  )
}
