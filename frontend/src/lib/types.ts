export type Tier = 'new' | 'learning' | 'shaky' | 'comfortable' | 'mastered'
export type DepthName = 'new' | 'recognize' | 'recall' | 'discriminate' | 'use'
export type Confidence = 'sure' | 'unsure' | 'guess'
export type ItemType = 'flashcard' | 'meaning' | 'cloze' | 'synonyms' | 'usage'

export interface AppConfig {
  ai_enabled: boolean
  auth_mode: 'dev' | 'clerk'
  model: string
  /** false until /api/config has answered */
  loaded: boolean
}

export interface Profile {
  test_date: string | null
  target_verbal: number | null
  target_quant: number | null
  daily_new_words: number
}

export interface WordDetail {
  id: number
  lemma: string
  pos: string
  pronunciation: string | null
  definition: string
  nuance: string | null
  phrases: string[]
  examples: string[]
  synonyms: string[]
  antonyms: string[]
  confusables: string[]
  cluster: string
  tier: number
  /** Study set number (1 = most common words) */
  set?: number | null
}

export type SetStatus = 'done' | 'reviewing' | 'current' | 'locked'

export interface WordSet {
  number: number
  /** frequency tier of its words (1-3) */
  tier: number
  size: number
  started: number
  learned: number
  status: SetStatus
}

export interface SetsResponse {
  sets: WordSet[]
  current: number | null
}

export interface CardSummary {
  comfort: number
  tier: Tier
  depth: number
  depth_name: DepthName
  recall_probability: number | null
  stability_days?: number
  due: string | null
  reps: number
  lapses: number
}

export interface StudyItem {
  id: string
  item_type: ItemType
  section: string
  hint_available: boolean
  payload: {
    word?: string
    pos?: string
    pronunciation?: string | null
    prompt?: string
    sentence?: string
    options?: string[]
    back?: WordDetail
  }
}

export type NextResponse =
  | {
      done: false
      item: StudyItem
      is_new_word: boolean
      likely_known: boolean
      card: CardSummary
      /** the set new words are coming from, null once every word is started */
      set: (WordSet & { total: number }) | null
    }
  | { done: true; next_due: string | null }

export interface Hint {
  eliminate?: number[]
  reveal?: number
}

export interface AnswerResult {
  correct: boolean
  score: number
  rating: 'again' | 'hard' | 'good' | 'easy'
  promoted: boolean
  demoted: boolean
  comfort_before: number
  comfort_after: number
  feedback: {
    correct_index?: number
    correct_indices?: number[]
    ai_feedback?: string
    improved_sentence?: string
  }
  card: CardSummary
  word: WordDetail
}

export interface Stats {
  total_words: number
  sets: { total: number; done: number; current: WordSet | null }
  tiers: Record<Tier, number>
  depth: Record<DepthName, number>
  due_now: number
  due_today: number
  new_available_today: number
  reviews_today: number
  accuracy_30d: number | null
  streak_days: number
  forecast: { date: string; due: number }[]
  weakest: { word: WordDetail; card: CardSummary }[]
}

export interface WordListEntry {
  id: number
  lemma: string
  pos: string
  tier: number
  set: number | null
  definition: string
  cluster: string
  card: CardSummary
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface PlacementItem {
  id: string
  word: string
  pos: string
  pronunciation: string | null
  options: string[]
  number: number
  max: number
}

export interface PlacementResult {
  run_id: string
  finished_at: string | null
  theta: number
  se: number
  level: string
  answered: number
  correct: number
  fast_tracked: number
  known_share: Record<string, number>
  missed: WordDetail[]
}

export type PlacementStep =
  | { done: false; item: PlacementItem; run_id?: string }
  | { done: true; result: PlacementResult }

export type PracticeKind = 'tc' | 'se' | 'mixed'

export interface PracticeItem {
  id: string
  item_type: 'tc' | 'se'
  kind_name: string
  hint_available: boolean
  payload: {
    text: string
    blanks?: string[][]
    options?: string[]
    difficulty: 'easy' | 'medium' | 'hard'
  }
}

export interface PracticeResult {
  correct: boolean
  difficulty: string
  rating_before: number
  rating_after: number
  feedback: {
    correct_indices: number[]
    explanation: string
    filled_text: string
    words: { id: number; lemma: string; definition: string }[]
  }
}

export type PracticeSummary = Record<
  'tc' | 'se',
  { name: string; rating: number | null; attempts: number; accuracy: number | null; questions: number }
>
