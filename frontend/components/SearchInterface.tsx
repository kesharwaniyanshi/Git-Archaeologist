'use client'

import { useState } from 'react'
import { Database, Link, Loader2 } from 'lucide-react'
import { RepositoryResponse, linkRepository, AuthUser } from '@/lib/api'
import { toast } from 'sonner'

interface SearchInterfaceProps {
  onResults: (results: RepositoryResponse) => void
  onLoading: (loading: boolean) => void
  onError: (error: string | null) => void
  authUser: AuthUser | null
  onLogin: () => void
}

export default function SearchInterface({ onResults, onLoading, onError, authUser, onLogin }: SearchInterfaceProps) {
  const [repoPath, setRepoPath] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!authUser) {
      onLogin()
      return
    }

    if (!repoPath.trim()) return

    setIsSubmitting(true)
    onLoading(true)
    onError(null)

    try {
      const data = await linkRepository({ url: repoPath })
      toast.success(`Successfully linked ${data.owner}/${data.name}!`)
      // Pass the repo data securely up to the UI layout
      onResults(data)
    } catch (err: unknown) {
      const errorMsg =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to link repository')
          : 'Failed to link repository'
      onError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setIsSubmitting(false)
      onLoading(false)
    }
  }

  return (
    <div className="fade-up rounded-2xl surface-panel panel-hover p-5 sm:p-6">
      <div className="terminal-chrome">
        <span className="terminal-dot terminal-dot-danger" />
        <span className="terminal-dot terminal-dot-warning" />
        <span className="terminal-dot terminal-dot-success" />
        <span className="ml-2 text-xs font-mono text-[hsl(var(--muted-foreground))]">repository-linker.tsx</span>
      </div>

      <div className="mt-4 pb-3">
        <h2 className="text-xl font-bold text-[hsl(var(--foreground))]">Link a GitHub Repository</h2>
        <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
          Submit any public GitHub URL to automatically trace, synchronize, and index its code evolution dynamically into our SQL storage!
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-[hsl(var(--muted-foreground))]">
            <Database className="h-3.5 w-3.5" />
            GitHub URL
          </label>
          <input
            type="text"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            disabled={!authUser}
            className="electric-ring h-11 w-full rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface-0)/0.8)] px-3 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] disabled:opacity-50 disabled:cursor-not-allowed"
            placeholder="https://github.com/isocpp/CppCoreGuidelines"
          />
        </div>

        <button
          type="submit"
          disabled={isSubmitting || (!!authUser && !repoPath.trim())}
          className="glow-electric electric-ring w-full rounded-lg border border-[hsl(var(--primary)/0.5)] bg-[hsl(var(--primary))] px-4 py-3 text-sm font-semibold text-[hsl(var(--surface-0))] transition duration-200 hover:-translate-y-[1px] hover:bg-[hsl(var(--primary-glow))] disabled:opacity-50 disabled:hover:translate-y-0"
        >
          <span className="inline-flex items-center gap-2">
            {!authUser ? <Link className="h-4 w-4" /> : isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link className="h-4 w-4" />}
            {!authUser ? 'Sign in to link repository' : isSubmitting ? 'Syncing...' : 'Link Repository'}
          </span>
        </button>
      </form>
    </div>
  )
}
