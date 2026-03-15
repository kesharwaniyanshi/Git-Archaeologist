import { Activity, PanelLeftClose, PanelLeftOpen, SearchCode } from 'lucide-react'

type HeaderProps = {
  sidebarOpen: boolean
  onToggleSidebar: () => void
}

export default function Header({ sidebarOpen, onToggleSidebar }: HeaderProps) {
  return (
    <header className="border-b border-[hsl(var(--border))] bg-[hsl(var(--surface-1)/0.85)] backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-[1500px] items-center justify-between gap-3 px-3 py-3 sm:px-5 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="electric-ring inline-flex h-9 w-9 items-center justify-center rounded-md border border-[hsl(var(--border-soft))] bg-[hsl(var(--surface-2))] text-[hsl(var(--foreground))] transition hover:border-[hsl(var(--primary)/0.4)] hover:text-[hsl(var(--primary-glow))]"
            aria-label="Toggle sidebar"
            title="Toggle sidebar"
          >
            {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          </button>

          <div className="terminal-chrome rounded-md border border-[hsl(var(--border-soft))] bg-[hsl(var(--surface-2))] px-2.5 py-1">
            <span className="terminal-dot terminal-dot-danger" />
            <span className="terminal-dot terminal-dot-warning" />
            <span className="terminal-dot terminal-dot-success" />
          </div>

          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold tracking-tight sm:text-xl">
              <span className="mr-2 inline-flex align-middle icon-badge p-1">
                <SearchCode className="h-3.5 w-3.5" />
              </span>
              Git Archaeologist
            </h1>
            <p className="truncate text-xs text-[hsl(var(--muted-foreground))]">Forensic RAG for commit intent analysis</p>
          </div>
        </div>

        <div className="status-pill inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium text-[hsl(var(--primary-glow))]">
          <Activity className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
          API Ready
        </div>
      </div>
    </header>
  )
}
