import { History, Sparkles, Timer } from 'lucide-react'

type ScanRecord = {
  id: string
  query: string
  createdAt: string
  confidence?: string
  resultsCount: number
}

type ScanHistoryProps = {
  scans: ScanRecord[]
}

function formatTime(value: string): string {
  const date = new Date(value)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function ScanHistory({ scans }: ScanHistoryProps) {
  return (
    <div className="surface-panel sticky top-4 rounded-2xl p-4">
      <div className="terminal-chrome">
        <span className="terminal-dot terminal-dot-danger" />
        <span className="terminal-dot terminal-dot-warning" />
        <span className="terminal-dot terminal-dot-success" />
        <span className="ml-2 text-xs font-mono text-[hsl(var(--muted-foreground))]">scan-history</span>
      </div>

      <div className="mt-4">
        <h2 className="inline-flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-[hsl(var(--muted-foreground))]">
          <History className="h-3.5 w-3.5" />
          Recent Excavations
        </h2>
      </div>

      {scans.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-[hsl(var(--border))] bg-[hsl(var(--surface-0)/0.6)] p-4 text-sm text-[hsl(var(--muted-foreground))]">
          No scans yet. Run a query to populate history.
        </div>
      ) : (
        <ul className="mt-4 space-y-2">
          {scans.map((scan) => (
            <li key={scan.id} className="fade-up panel-hover rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface-0)/0.7)] p-3">
              <p className="line-clamp-2 text-sm text-[hsl(var(--foreground))]">{scan.query}</p>
              <div className="mt-2 flex items-center justify-between text-xs text-[hsl(var(--muted-foreground))]">
                <span className="inline-flex items-center gap-1 font-mono"><Timer className="h-3 w-3" />{formatTime(scan.createdAt)}</span>
                <span>{scan.resultsCount} hits</span>
              </div>
              {scan.confidence && (
                <div className="mt-1 inline-flex items-center gap-1 text-xs text-[hsl(var(--primary-glow))]">
                  <Sparkles className="h-3 w-3" />
                  {scan.confidence} confidence
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
