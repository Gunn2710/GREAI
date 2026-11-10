import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

/** What's on screen, so the coach can talk about it. */
export type CoachPage =
  | { kind: 'study'; itemId: string; answered: boolean; flashcard: boolean }
  | { kind: 'practice'; itemId: string; answered: boolean }
  | { kind: 'word'; wordId: number; lemma: string }
  | null

interface CoachState {
  page: CoachPage
  setPage: (page: CoachPage) => void
  open: boolean
  setOpen: (open: boolean) => void
  /** A message to send as soon as the chat panel is ready. */
  queued: string | null
  /** Open the chat and send `text`. */
  ask: (text: string) => void
  takeQueued: () => string | null
}

const CoachContext = createContext<CoachState | null>(null)

export function CoachProvider({ children }: { children: ReactNode }) {
  const [page, setPage] = useState<CoachPage>(null)
  const [open, setOpen] = useState(false)
  const [queued, setQueued] = useState<string | null>(null)
  const ask = useCallback((text: string) => {
    setQueued(text)
    setOpen(true)
  }, [])
  const takeQueued = useCallback(() => {
    const text = queued
    setQueued(null)
    return text
  }, [queued])
  const value = useMemo(
    () => ({ page, setPage, open, setOpen, queued, ask, takeQueued }),
    [page, open, queued, ask, takeQueued],
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
