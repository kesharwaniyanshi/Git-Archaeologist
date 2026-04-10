'use client'

import { BadgeCheck, Clock3, Fingerprint, GaugeCircle, ListChecks, MessageSquareText } from 'lucide-react'

interface Result {
  commit_hash: string
  message: string
  summary: string
  relevance_score: number
  status: string
}

interface ResultsViewProps {
  results: {
    answer?: string
    confidence?: string
    confidence_score?: number
    results?: Result[]
    metadata?: {
      total_commits_indexed?: number
      candidates_analyzed?: number
      query_time_seconds?: number
    }
  }
}

export default function ResultsView({ results }: ResultsViewProps) {
  if (!results) return null

  const { answer, confidence, confidence_score, results: commits, metadata } = results

  return (
    <div className="mt-6 space-y-6 fade-up">
      {answer && (
        <div className="rounded-xl surface-panel panel-hover p-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="inline-flex items-center gap-2 text-base font-semibold tracking-wide">
              <MessageSquareText className="h-4 w-4 text-[hsl(var(--primary-glow))]" />
              Synthesized Analysis
            </h2>
            {confidence && (
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                confidence === 'High' ? 'bg-[hsl(var(--success)/0.2)] text-[hsl(var(--success))]' :
                confidence === 'Medium' ? 'bg-[hsl(var(--warning)/0.2)] text-[hsl(var(--warning))]' :
                'bg-[hsl(var(--danger)/0.2)] text-[hsl(var(--danger))]'
              }`}>
                {confidence} Confidence {confidence_score ? `(${(confidence_score * 100).toFixed(0)}%)` : ''}
              </span>
            )}
          </div>
          <p className="whitespace-pre-wrap text-sm leading-7 text-[hsl(var(--foreground))]">{answer}</p>
        </div>
      )}

      {metadata && (
        <div className="rounded-xl surface-panel panel-hover p-4">
          <div className="grid gap-3 text-sm sm:grid-cols-3">
            <div className="rounded-lg bg-[hsl(var(--surface-0)/0.8)] p-3">
              <span className="mb-1 inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.14em] text-[hsl(var(--muted-foreground))]">
                <ListChecks className="h-3.5 w-3.5" />
                Total Commits
              </span>
              <span className="mt-1 block font-mono text-base text-[hsl(var(--foreground))]">{metadata.total_commits_indexed ?? '-'}</span>
            </div>
            <div className="rounded-lg bg-[hsl(var(--surface-0)/0.8)] p-3">
              <span className="mb-1 inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.14em] text-[hsl(var(--muted-foreground))]">
                <GaugeCircle className="h-3.5 w-3.5" />
                Candidates
              </span>
              <span className="mt-1 block font-mono text-base text-[hsl(var(--foreground))]">{metadata.candidates_analyzed ?? '-'}</span>
            </div>
            <div className="rounded-lg bg-[hsl(var(--surface-0)/0.8)] p-3">
              <span className="mb-1 inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.14em] text-[hsl(var(--muted-foreground))]">
                <Clock3 className="h-3.5 w-3.5" />
                Execution Time
              </span>
              <span className="mt-1 block font-mono text-base text-[hsl(var(--foreground))]">{metadata.query_time_seconds?.toFixed(2) ?? '-'}s</span>
            </div>
          </div>
        </div>
      )}

      {commits && commits.length > 0 && (
        <div className="space-y-4">
          <h3 className="inline-flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-[hsl(var(--muted-foreground))]">
            <Fingerprint className="h-3.5 w-3.5" />
            Relevant Evidence
          </h3>
          {commits.map((commit, idx) => (
            <div
              key={commit.commit_hash}
              className="rounded-xl surface-panel panel-hover p-5"
            >
              <div className="mb-3 flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="text-xl font-bold text-[hsl(var(--primary))]">#{idx + 1}</span>
                  <code className="rounded bg-[hsl(var(--surface-0)/0.85)] px-2 py-1 text-xs text-[hsl(var(--primary-glow))]">
                    {commit.commit_hash.substring(0, 8)}
                  </code>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[hsl(var(--muted-foreground))]">Relevance</span>
                  <div className="flex items-center gap-1">
                    <div className="h-2 w-24 overflow-hidden rounded-full bg-[hsl(var(--surface-3))]">
                      <div
                        className="h-full bg-gradient-to-r from-[hsl(var(--primary))] to-[hsl(var(--primary-glow))]"
                        style={{ width: `${Math.min(commit.relevance_score * 100, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-[hsl(var(--foreground))]">
                      {(commit.relevance_score * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>

              <h4 className="mb-2 text-sm font-semibold text-[hsl(var(--foreground))]">{commit.message}</h4>

              {commit.summary && commit.summary !== commit.message && (
                <div className="mt-3 border-t border-[hsl(var(--border))] pt-3">
                  <p className="mb-1 text-xs uppercase tracking-[0.14em] text-[hsl(var(--muted-foreground))]">AI Summary</p>
                  <p className="text-sm leading-6 text-[hsl(var(--foreground))]">{commit.summary}</p>
                </div>
              )}

              {commit.status && (
                <div className="mt-3 flex items-center gap-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${
                    commit.status === 'success' ? 'bg-[hsl(var(--success)/0.2)] text-[hsl(var(--success))]' :
                    'bg-[hsl(var(--surface-3))] text-[hsl(var(--muted-foreground))]'
                  }`}>
                    {commit.status === 'success' ? <BadgeCheck className="mr-1 inline h-3 w-3" /> : null}
                    {commit.status}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
