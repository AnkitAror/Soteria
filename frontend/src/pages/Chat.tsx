import { useCallback, useEffect, useRef, useState } from 'react'
import { apiFetch } from '../lib/api'
import type {
  ChatMessage,
  ChatSessionSummary,
  ChatSessionsResponse,
  ChatMessagesResponse,
  ChatUsage,
} from '../lib/types'

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function usageStyle(usage: ChatUsage) {
  if (usage.remaining <= 0) return 'text-red-600 dark:text-red-400'
  if (usage.remaining / usage.limit <= 0.3) return 'text-amber-600 dark:text-amber-400'
  return 'text-gray-400 dark:text-gray-500'
}

export function Chat() {
  const [sessions, setSessions] = useState<ChatSessionSummary[] | null>(null)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[] | null>(null)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [sending, setSending] = useState(false)
  const [question, setQuestion] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [usage, setUsage] = useState<ChatUsage | null>(null)
  const threadEndRef = useRef<HTMLDivElement>(null)

  const loadUsage = useCallback(async () => {
    try {
      setUsage(await apiFetch<ChatUsage>('/api/chat/usage'))
    } catch {
      // non-critical: leave the badge hidden rather than surfacing an error
    }
  }, [])

  const loadSessions = useCallback(async (selectId?: string) => {
    try {
      const response = await apiFetch<ChatSessionsResponse>('/api/chat/sessions')
      setSessions(response.sessions)
      if (selectId) {
        setActiveSessionId(selectId)
      } else {
        setActiveSessionId((current) => current ?? response.sessions[0]?.id ?? null)
      }
    } catch {
      setError('Could not load chat sessions.')
    }
  }, [])

  useEffect(() => {
    void loadSessions()
    void loadUsage()
  }, [loadSessions, loadUsage])

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([])
      return
    }
    setLoadingMessages(true)
    setError(null)
    apiFetch<ChatMessagesResponse>(`/api/chat/sessions/${activeSessionId}/messages`)
      .then((response) => setMessages(response.messages))
      .catch(() => setError('Could not load this conversation.'))
      .finally(() => setLoadingMessages(false))
  }, [activeSessionId])

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const handleNewSession = async () => {
    try {
      const created = await apiFetch<ChatSessionSummary>('/api/chat/sessions', {
        method: 'POST',
        body: JSON.stringify({}),
      })
      setSessions((current) => [created, ...(current ?? [])])
      setActiveSessionId(created.id)
      setMessages([])
    } catch {
      setError('Could not start a new chat.')
    }
  }

  const handleDeleteSession = async (id: string) => {
    try {
      await apiFetch(`/api/chat/sessions/${id}`, { method: 'DELETE' })
      setSessions((current) => current?.filter((s) => s.id !== id) ?? current)
      if (activeSessionId === id) {
        setActiveSessionId(null)
        setMessages(null)
      }
    } catch {
      setError('Could not delete this chat.')
    }
  }

  const handleSend = async () => {
    const text = question.trim()
    if (!text || sending) return

    setError(null)
    setSending(true)
    setQuestion('')

    let sessionId = activeSessionId
    try {
      if (!sessionId) {
        const created = await apiFetch<ChatSessionSummary>('/api/chat/sessions', {
          method: 'POST',
          body: JSON.stringify({}),
        })
        sessionId = created.id
        setSessions((current) => [created, ...(current ?? [])])
        setActiveSessionId(created.id)
        setMessages([])
      }

      const optimisticUserMessage: ChatMessage = {
        id: `pending-${Date.now()}`,
        role: 'user',
        message: text,
        sql_generated: null,
        citations: [],
        created_at: new Date().toISOString(),
      }
      setMessages((current) => [...(current ?? []), optimisticUserMessage])

      const assistantMessage = await apiFetch<ChatMessage>(
        `/api/chat/sessions/${sessionId}/messages`,
        { method: 'POST', body: JSON.stringify({ question: text }) },
      )
      setMessages((current) => [...(current ?? []), assistantMessage])
      void loadSessions(sessionId)
      void loadUsage()
    } catch {
      setError('Could not get an answer. Try again.')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-11rem)] gap-6">
      <aside className="flex w-64 shrink-0 flex-col gap-2 overflow-y-auto">
        <button
          type="button"
          onClick={() => void handleNewSession()}
          className="rounded-md bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
        >
          New chat
        </button>

        {sessions === null ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading…</p>
        ) : sessions.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">No conversations yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {sessions.map((s) => (
              <li key={s.id} className="group flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setActiveSessionId(s.id)}
                  className={`flex-1 truncate rounded-md px-3 py-2 text-left text-sm ${
                    activeSessionId === s.id
                      ? 'bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900'
                      : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
                  }`}
                >
                  {s.title || 'New conversation'}
                </button>
                <button
                  type="button"
                  onClick={() => void handleDeleteSession(s.id)}
                  className="hidden text-xs text-gray-400 hover:text-red-600 group-hover:block"
                  aria-label="Delete conversation"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <div className="flex flex-1 flex-col rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        {(error || usage) && (
          <div className="flex items-center gap-4 border-b border-gray-100 px-5 py-2 dark:border-gray-800">
            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
            {usage && (
              <span className={`ml-auto shrink-0 text-xs font-medium ${usageStyle(usage)}`}>
                {usage.used} / {usage.limit} Gemini requests used today
              </span>
            )}
          </div>
        )}

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {loadingMessages ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">Loading conversation…</p>
          ) : !messages || messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Ask about your spending, subscriptions, or accounts.
              </p>
            </div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                <div
                  className={`max-w-[75%] rounded-xl px-4 py-3 text-sm ${
                    m.role === 'user'
                      ? 'bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900'
                      : 'bg-gray-50 text-gray-900 dark:bg-gray-800/60 dark:text-gray-50'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.message}</p>
                  {m.citations.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {m.citations.map((c, i) => (
                        <span
                          key={i}
                          title={c.detail}
                          className="rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300"
                        >
                          {c.label}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="mt-1 text-xs opacity-60">{formatTime(m.created_at)}</p>
                </div>
              </div>
            ))
          )}
          {sending && (
            <div className="flex justify-start">
              <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-500 dark:bg-gray-800/60 dark:text-gray-400">
                Thinking…
              </div>
            </div>
          )}
          <div ref={threadEndRef} />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault()
            void handleSend()
          }}
          className="flex gap-2 border-t border-gray-100 p-4 dark:border-gray-800"
        >
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={sending}
            placeholder="How much did I spend on dining last month?"
            className="flex-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-50"
          />
          <button
            type="submit"
            disabled={sending || !question.trim()}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
