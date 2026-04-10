'use client'

import React, { useState, useEffect, useRef } from 'react'
import { Send, User as UserIcon, Bot, Loader2, Sparkles } from 'lucide-react'
import { ChatMessageItem, sendMessage, getChatHistory, createChatSession } from '@/lib/api'
import { toast } from 'sonner'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface ChatPanelProps {
  sessionId: string | null
  repositoryId?: string // used to contextulize if no session, but we create session on first send
  onNewSessionCreated?: (sessionId: string) => void
}

export default function ChatPanel({ sessionId, repositoryId, onNewSessionCreated }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessageItem[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Load chat history when session changes
  useEffect(() => {
    if (sessionId) {
      setIsLoading(true)
      getChatHistory(sessionId)
        .then((data) => {
          setMessages(data.messages)
          scrollToBottom()
        })
        .catch((err) => {
          console.error(err)
          toast.error('Failed to load chat history')
        })
        .finally(() => setIsLoading(false))
    } else {
      setMessages([])
    }
  }, [sessionId])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // Auto-scroll when messages change
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessageContent = input.trim()
    setInput('')
    setIsLoading(true)

    // Add optimistic user message
    const tempUserId = `temp-${Date.now()}`
    setMessages((prev) => [
      ...prev,
      { id: tempUserId, role: 'user', content: userMessageContent, created_at: new Date().toISOString() }
    ])

    try {
      let currentSessionId = sessionId

      if (!currentSessionId) {
        const sess = await createChatSession(repositoryId)
        currentSessionId = sess.chat_session_id
        if (onNewSessionCreated) onNewSessionCreated(currentSessionId)
      }
      if (!currentSessionId) throw new Error('Missing chat session id')

      const res = await sendMessage(currentSessionId, userMessageContent)
      setMessages((prev) => [
        // remove temp user message
        ...prev.filter(m => m.id !== tempUserId),
        res.user_message,
        res.assistant_message
      ])
    } catch (error) {
      console.error(error)
      toast.error('Failed to send message')
      // Remove temp user message on error
      setMessages((prev) => prev.filter(m => m.id !== tempUserId))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--surface-0)/0.7)]">
      {/* Header */}
      <div className="flex h-12 items-center border-b border-[hsl(var(--border))] px-4">
        <div className="terminal-chrome">
          <span className="terminal-dot terminal-dot-danger" />
          <span className="terminal-dot terminal-dot-warning" />
          <span className="terminal-dot terminal-dot-success" />
          <span className="ml-2 text-xs font-mono text-[hsl(var(--muted-foreground))]">archaeologist-shell</span>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        {messages.length === 0 && !isLoading && (
          <div className="flex h-full flex-col items-center justify-center text-center opacity-70">
            <Sparkles className="h-10 w-10 text-[hsl(var(--primary))] mb-3" />
            <p className="text-[hsl(var(--muted-foreground))]">Ask a question about the repository history.</p>
            <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">E.g., "Why were the auth tests disabled last week?"</p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[hsl(var(--primary)/0.2)] text-[hsl(var(--primary))]">
                <Bot className="h-5 w-5" />
              </div>
            )}
            
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 ${
              msg.role === 'user' 
                ? 'bg-[hsl(var(--primary))] text-[hsl(var(--surface-0))] rounded-tr-sm' 
                : 'bg-[hsl(var(--surface-panel))] border border-[hsl(var(--border))] text-[hsl(var(--foreground))] rounded-tl-sm'
            }`}>
              {msg.role === 'user' ? (
                <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
              ) : (
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({node, inline, className, children, ...props}: any) {
                        const match = /language-(\w+)/.exec(className || '')
                        return !inline && match ? (
                          <SyntaxHighlighter
                            {...props}
                            children={String(children).replace(/\n$/, '')}
                            style={vscDarkPlus as any}
                            language={match[1]}
                            PreTag="div"
                            customStyle={{ margin: '1em 0', borderRadius: '0.5rem', background: '#0d1117' }}
                          />
                        ) : (
                          <code {...props} className="bg-[hsl(var(--surface-2))] px-1.5 py-0.5 rounded-md font-mono text-xs text-[hsl(var(--primary-glow))]">
                            {children}
                          </code>
                        )
                      }
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              )}
            </div>
            
            {msg.role === 'user' && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[hsl(var(--surface-2))] text-[hsl(var(--foreground))]">
                <UserIcon className="h-5 w-5" />
              </div>
            )}
          </div>
        ))}
        {isLoading && (
           <div className="flex justify-start gap-3">
             <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[hsl(var(--primary)/0.2)] text-[hsl(var(--primary))]">
               <Loader2 className="h-5 w-5 animate-spin" />
             </div>
             <div className="flex items-center rounded-2xl rounded-tl-sm bg-[hsl(var(--surface-panel))] border border-[hsl(var(--border))] px-4 py-3">
                <span className="flex space-x-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[hsl(var(--muted-foreground))]" style={{ animationDelay: '0ms' }} />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[hsl(var(--muted-foreground))]" style={{ animationDelay: '150ms' }} />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[hsl(var(--muted-foreground))]" style={{ animationDelay: '300ms' }} />
                </span>
             </div>
           </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-[hsl(var(--border))] bg-[hsl(var(--surface-panel))] p-3">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
            placeholder="Ask about the repository history..."
            className="electric-ring flex-1 rounded-xl border border-[hsl(var(--border-soft))] bg-[hsl(var(--surface-0))] px-4 py-3 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="glow-electric electric-ring flex h-auto w-12 shrink-0 items-center justify-center rounded-xl bg-[hsl(var(--primary))] text-[hsl(var(--surface-0))] transition-transform hover:-translate-y-[1px] disabled:opacity-50 disabled:hover:translate-y-0"
          >
            <Send className="h-5 w-5" />
          </button>
        </form>
      </div>
    </div>
  )
}
