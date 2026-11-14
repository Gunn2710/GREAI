import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError } from './api'
import { useConfig } from './config'
import type { SavedChatMessage } from './types'

/** What's on screen, so the coach can talk about it. */
export type CoachPage =
  | { kind: 'study'; itemId: string; answered: boolean; flashcard: boolean }
  | { kind: 'practice'; itemId: string; answered: boolean }
  | { kind: 'word'; wordId: number; lemma: string }
  | null

/** A chat message; `pending` while the coach's reply is still being written. */
export type CoachMessage = SavedChatMessage & { pending?: boolean }

interface CoachState {
  page: CoachPage
  setPage: (page: CoachPage) => void
  /** Whether the chat bubble is open (pages other than Home). */
  open: boolean
  setOpen: (open: boolean) => void
  /** The chat, shared by the home page and the bubble. */
  messages: CoachMessage[]
  /** The saved chat has been loaded (see /coach/history). */
  loaded: boolean
  busy: boolean
  /** What the coach is doing before its reply starts, e.g. "Looking at your weak spots". */
  status: string | null
  error: string | null
  /** AI requests left today, or null when there is no limit. */
  remaining: number | null
  /** Send a message; resolves false if it failed (the chat is left as it was). */
  send: (text: string) => Promise<boolean>
  /** Start a new chat. */
  clear: () => Promise<void>
  /** Open the chat bubble and send `text`. */
  ask: (text: string) => void
}

const CoachContext = createContext<CoachState | null>(null)

function where(page: CoachPage) {
  if (page?.kind === 'study') return { study_item_id: page.itemId }
  if (page?.kind === 'practice') return { practice_item_id: page.itemId }
  if (page?.kind === 'word') return { word_id: page.wordId }
  return {}
}

export function CoachProvider({ children }: { children: ReactNode }) {
  const { ai_enabled } = useConfig()
  const [page, setPage] = useState<CoachPage>(null)
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<CoachMessage[]>([])
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [remaining, setRemaining] = useState<number | null>(null)
  const [queued, setQueued] = useState<string | null>(null)

  // The saved chat is loaded once, so it survives a refresh (it's per account, on the server).
  useEffect(() => {
    if (!ai_enabled || loaded) return
    let cancelled = false
    api
      .coachHistory()
      .then((res) => {
        if (cancelled) return
        setMessages(res.messages)
        setRemaining(res.remaining)
      })
      .catch(() => {
        /* no saved chat to show: start empty */
      })
      .finally(() => !cancelled && setLoaded(true))
    return () => {
      cancelled = true
    }
  }, [ai_enabled, loaded])

  const send = useCallback(
    async (text: string) => {
      const content = text.trim()
      if (!content || busy) return false
      const before = messages
      const reply: CoachMessage = { role: 'assistant', content: '', proposal: null, actions: [], pending: true }
      setMessages([...before, { role: 'user', content, proposal: null, actions: [] }, reply])
      setBusy(true)
      setError(null)
      setStatus(null)
      // Update the reply being written (always the last message).
      const update = (change: (m: CoachMessage) => CoachMessage) =>
        setMessages((current) => [...current.slice(0, -1), change(current[current.length - 1])])
      try {
        await api.coachStream(content, where(page), (event) => {
          if (event.type === 'text') {
            setStatus(null)
            update((m) => ({ ...m, content: m.content + event.text }))
          } else if (event.type === 'status') {
            setStatus(event.text)
          } else if (event.type === 'done') {
            update(() => ({
              role: 'assistant',
              content: event.reply,
              proposal: event.proposal,
              actions: event.actions,
            }))
            setRemaining(event.remaining)
          }
        })
        return true
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'Something went wrong')
        setMessages(before)
        return false
      } finally {
        setBusy(false)
        setStatus(null)
      }
    },
    [busy, messages, page],
  )

  const clear = useCallback(async () => {
    setError(null)
    try {
      await api.clearCoachHistory()
      setMessages([])
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start a new chat')
    }
  }, [])

  const ask = useCallback((text: string) => {
    setOpen(true)
    setQueued(text)
  }, [])

  // A page asked the coach something (e.g. a button on the word page): send it
  // once the saved chat is loaded, so the question carries on from it.
  useEffect(() => {
    if (!queued || !loaded || busy) return
    setQueued(null)
    send(queued)
  }, [queued, loaded, busy, send])

  const value = useMemo(
    () => ({ page, setPage, open, setOpen, messages, loaded, busy, status, error, remaining, send, clear, ask }),
    [page, open, messages, loaded, busy, status, error, remaining, send, clear, ask],
  )
  return <CoachContext.Provider value={value}>{children}</CoachContext.Provider>
}

export function useCoach(): CoachState {
  const state = useContext(CoachContext)
  if (!state) throw new Error('useCoach needs a CoachProvider')
  return state
}

/** Tell the coach what this page shows; cleared when the page goes away. */
export function useCoachPage(page: CoachPage) {
  const { setPage } = useCoach()
  const key = JSON.stringify(page)
  useEffect(() => {
    setPage(JSON.parse(key) as CoachPage)
    return () => setPage(null)
  }, [key, setPage])
}
