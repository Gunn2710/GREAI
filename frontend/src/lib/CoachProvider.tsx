import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError } from './api'
import { CoachContext, type CoachMessage, type CoachPage } from './coach'
import { useConfig } from './config'

const OPEN_KEY = 'coach-open'
const WIDE = '(min-width: 1024px)'

/** Wide screens start with the side chat open, unless it was minimized last time;
 * narrower screens (where it would cover the page) start with the bubble. */
function startOpen(): boolean {
  if (!window.matchMedia(WIDE).matches) return false
  try {
    return localStorage.getItem(OPEN_KEY) !== '0'
  } catch {
    return true
  }
}

function where(page: CoachPage) {
  if (page?.kind === 'study') return { study_item_id: page.itemId }
  if (page?.kind === 'practice') return { practice_item_id: page.itemId }
  if (page?.kind === 'word') return { word_id: page.wordId }
  return {}
}

/** Holds the coach chat for the whole app (see useCoach). */
export function CoachProvider({ children }: { children: ReactNode }) {
  const { ai_enabled } = useConfig()
  const [page, setPage] = useState<CoachPage>(null)
  const [open, setOpenState] = useState(startOpen)
  const setOpen = useCallback((value: boolean) => {
    setOpenState(value)
    try {
      localStorage.setItem(OPEN_KEY, value ? '1' : '0')
    } catch {
      // storage blocked: it just won't be remembered
    }
  }, [])
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

  const ask = useCallback(
    (text: string) => {
      setOpen(true)
      setQueued(text)
    },
    [setOpen],
  )

  // A page asked the coach something (e.g. a button on the word page): send it
  // once the saved chat is loaded, so the question carries on from it.
  useEffect(() => {
    if (!queued || !loaded || busy) return
    setQueued(null)
    send(queued)
  }, [queued, loaded, busy, send])

  const value = useMemo(
    () => ({ page, setPage, open, setOpen, messages, loaded, busy, status, error, remaining, send, clear, ask }),
    [page, open, setOpen, messages, loaded, busy, status, error, remaining, send, clear, ask],
  )
  return <CoachContext.Provider value={value}>{children}</CoachContext.Provider>
}
