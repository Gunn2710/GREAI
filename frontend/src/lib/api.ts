import type {
  AnswerResult,
  AppConfig,
  CoachEvent,
  CoachNote,
  Confidence,
  Hint,
  NextResponse,
  PlacementResult,
  PlacementStep,
  PracticeItem,
  PracticeKind,
  PracticeResult,
  PracticeSummary,
  Profile,
  SavedChatMessage,
  SetsResponse,
  Stats,
  StudyFocus,
  StudyFormat,
  WordDetail,
  WordListEntry,
  CardSummary,
} from './types'

/**
 * Auth hook-up point. Today the backend runs in dev mode and identifies users
 * by the X-Dev-User header. With Clerk, call
 *   setTokenProvider(() => getToken())   // from useAuth()
 * once at startup and every request will carry the session JWT instead.
 */
type TokenProvider = () => Promise<string | null>
let tokenProvider: TokenProvider = async () => null

export function setTokenProvider(fn: TokenProvider) {
  tokenProvider = fn
}

const DEV_USER_KEY = 'gre.devUser'

export function getDevUser(): string {
  try {
    return localStorage.getItem(DEV_USER_KEY) || 'dev-user'
  } catch {
    return 'dev-user'
  }
}

export function setDevUser(id: string) {
  try {
    localStorage.setItem(DEV_USER_KEY, id)
  } catch {
    /* storage unavailable: stay on the default user */
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  const token = await tokenProvider()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  else headers.set('X-Dev-User', getDevUser())

  const res = await fetch(`/api${path}`, { ...init, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  return res
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await send(path, init)
  return res.json() as Promise<T>
}

/** A coach reply as it's written: calls `onEvent` for each server-sent event. */
async function coachStream(
  message: string,
  page: { study_item_id?: string; practice_item_id?: string; word_id?: number },
  onEvent: (event: CoachEvent) => void,
): Promise<void> {
  const res = await send('/coach/chat/stream', { method: 'POST', body: JSON.stringify({ message, ...page }) })
  if (!res.body) throw new ApiError(500, 'No reply from the server')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    let end
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const chunk = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ')) continue
        const event = JSON.parse(line.slice(6)) as CoachEvent
        if (event.type === 'error') throw new ApiError(500, event.detail)
        onEvent(event)
      }
    }
    if (done) return
  }
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  config: () => request<AppConfig>('/config'),
  me: () => request<{ user_id: string }>('/me'),
  profile: () => request<Profile>('/me/profile'),
  saveProfile: (p: Profile) => request<Profile>('/me/profile', { method: 'PUT', body: JSON.stringify(p) }),

  next: (format: StudyFormat = 'mixed', focus: StudyFocus = 'review') =>
    request<NextResponse>(`/study/next?format=${format}&focus=${focus}`),
  hint: (itemId: string) => post<Hint>(`/study/items/${itemId}/hint`),
  studyMore: (words: number) => post<{ extra_today: number; new_word_limit: number }>('/study/more', { words }),
  answer: (itemId: string, response: Record<string, unknown>, responseMs: number, confidence?: Confidence) =>
    post<AnswerResult>(`/study/items/${itemId}/answer`, {
      response,
      response_ms: Math.round(responseMs),
      confidence: confidence ?? null,
    }),

  stats: () => request<Stats>('/stats'),

  placementStart: () => post<PlacementStep & { run_id: string }>('/placement/start'),
  placementAnswer: (runId: string, itemId: string, selected: number | null, responseMs: number) =>
    post<PlacementStep>(`/placement/${runId}/answer`, {
      item_id: itemId,
      selected,
      response_ms: Math.round(responseMs),
    }),
  practiceNext: (kind: PracticeKind) => request<{ item: PracticeItem }>(`/practice/next?kind=${kind}`),
  practiceHint: (itemId: string) => post<{ clue: string }>(`/practice/items/${itemId}/hint`),
  practiceAnswer: (itemId: string, response: Record<string, unknown>, responseMs: number) =>
    post<PracticeResult>(`/practice/items/${itemId}/answer`, { response, response_ms: Math.round(responseMs) }),
  practiceSummary: () => request<PracticeSummary>('/practice/summary'),
  placementLatest: () => request<{ result: PlacementResult | null }>('/placement/latest'),
  sets: () => request<SetsResponse>('/sets'),
  words: (search?: string) =>
    request<WordListEntry[]>(`/words${search ? `?search=${encodeURIComponent(search)}` : ''}`),
  word: (id: number) =>
    request<{ word: WordDetail; card: CardSummary | null; my_sentence: string | null }>(`/words/${id}`),
  saveSentence: (id: number, sentence: string) =>
    request<{ my_sentence: string | null }>(`/words/${id}/sentence`, {
      method: 'PUT',
      body: JSON.stringify({ sentence }),
    }),
  coachStream,
  coachHistory: () => request<{ messages: SavedChatMessage[]; remaining: number | null }>('/coach/history'),
  coachNotes: () => request<{ notes: CoachNote[] }>('/coach/notes'),
  deleteCoachNote: (id: number) => request<{ notes: CoachNote[] }>(`/coach/notes/${id}`, { method: 'DELETE' }),
  reviewNow: (wordIds: number[]) => post<{ due_now: number }>('/study/review-now', { word_ids: wordIds }),
  markKnown: (id: number) => post<{ card: CardSummary }>(`/words/${id}/known`),
  clearCoachHistory: () => request<{ messages: SavedChatMessage[] }>('/coach/history', { method: 'DELETE' }),
  mnemonic: (id: number) => post<{ mnemonic: string }>(`/words/${id}/mnemonic`),
}
