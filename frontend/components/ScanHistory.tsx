import { History, Plus, MessageSquare, Timer } from 'lucide-react'
import { ChatSessionItem } from '@/lib/api'

type ScanHistoryProps = {
  sessions: ChatSessionItem[]
  activeSessionId?: string | null
  onSelectSession?: (sessionId: string) => void
  onNewChat?: () => void
}

function formatTime(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function ScanHistory({ sessions, activeSessionId, onSelectSession, onNewChat }: ScanHistoryProps) {
  return (
    <div className="surface-panel sticky top-4 rounded-2xl p-4 h-[calc(100vh-2rem)] flex flex-col">
      <div className="terminal-chrome shrink-0">
        <span className="terminal-dot terminal-dot-danger" />
        <span className="terminal-dot terminal-dot-warning" />
        <span className="terminal-dot terminal-dot-success" />
        <span className="ml-2 text-xs font-mono text-[hsl(var(--muted-foreground))]">chat-history</span>
      </div>

      <div className="mt-4 shrink-0">
        <div className="flex items-center justify-between gap-2">
          <h2 className="inline-flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-[hsl(var(--muted-foreground))]">
            <History className="h-3.5 w-3.5" />
            Chat Sessions
          </h2>
          <button
            type="button"
            onClick={onNewChat}
            className="electric-ring inline-flex h-8 items-center justify-center gap-1 rounded-md border border-[hsl(var(--border-soft))] bg-[hsl(var(--surface-2))] px-2 text-xs font-medium text-[hsl(var(--foreground))] transition hover:border-[hsl(var(--primary)/0.4)] hover:text-[hsl(var(--primary-glow))]"
          >
            <Plus className="h-3.5 w-3.5" />
            New
          </button>
        </div>
      </div>

      {sessions.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-[hsl(var(--border))] bg-[hsl(var(--surface-0)/0.6)] p-4 text-sm text-[hsl(var(--muted-foreground))]">
          No chat history yet. Link a repository and start analyzing.
        </div>
      ) : (
        <ul className="mt-4 space-y-2 flex-1 overflow-y-auto pr-1">
          {sessions.map((session) => (
            <li
              key={session.chat_session_id}
              onClick={() => onSelectSession?.(session.chat_session_id)}
              className={`fade-up panel-hover cursor-pointer rounded-lg border p-3 ${
                activeSessionId === session.chat_session_id
                  ? 'border-[hsl(var(--primary)/0.7)] bg-[hsl(var(--primary)/0.12)]'
                  : 'border-[hsl(var(--border))] bg-[hsl(var(--surface-0)/0.7)]'
              }`}
            >
              <p className="line-clamp-2 text-sm text-[hsl(var(--foreground))]">
                {session.title || 'New Chat'}
              </p>
              <div className="mt-2 flex items-center justify-between text-xs text-[hsl(var(--muted-foreground))]">
                {session.updated_at && (
                  <span className="inline-flex items-center gap-1 font-mono">
                    <Timer className="h-3 w-3" />{formatTime(session.updated_at)}
                  </span>
                )}
                <span className="inline-flex items-center gap-1">
                  <MessageSquare className="h-3 w-3" />
                  {session.message_count} msgs
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
