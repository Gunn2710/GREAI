import { createContext, useContext, useEffect } from 'react'
import type { SavedChatMessage } from './types'

/** What's on screen, so the coach can talk about it. */
export type CoachPage =
  | { kind: 'study'; itemId: string; answered: boolean; flashcard: boolean }
  | { kind: 'practice'; itemId: string; answered: boolean }
  | { kind: 'word'; wordId: number; lemma: string }
  | null

/** A chat message; `pending` while the coach's reply is still being written. */
export type CoachMessage = SavedChatMessage & { pending?: boolean }

export interface CoachState {
  page: CoachPage
  setPage: (page: CoachPage) => void
  /** Whether the side chat is open (otherwise it's a bubble). Not used on the full-page chat. */
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
  /** Open the side chat and send `text`. */
  ask: (text: string) => void
}

export const CoachContext = createContext<CoachState | null>(null)

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
