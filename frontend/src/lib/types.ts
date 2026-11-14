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
  /** frequency tier of its words (1-3); GregMat sets mix tiers */
  tier: number
  /** "gregmat": one of GregMat's groups, in order; "bank": the rest of the word bank */
  source: 'gregmat' | 'bank'
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
    /** Your own sentence with the word (flashcards: shown on the back). */
    my_sentence?: string | null
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
  | {
      done: true
      next_due: string | null
      /** words not started yet; 0 means there is nothing left to "study more" */
      unseen_words: number
      /** today's new-word allowance, including any "study more" words */
      new_word_limit: number
    }

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
  my_sentence?: string | null
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

/** Plan changes the coach suggested; nothing is saved until the student clicks Save. */
export interface PlanProposal {
  changes: Partial<Profile>
  current: Profile
}

interface WordRef {
  id: number
  lemma: string
}

/** Something the coach offered to do (each one waits for a button click), or a note it made. */
export type CoachAction =
  | { type: 'review_now'; title: string; words: WordRef[] }
  | { type: 'mark_known'; word: WordRef }
  | { type: 'study_settings'; changes: { focus?: StudyFocus; format?: StudyFormat } }
  | { type: 'open_practice'; section: 'verbal' | 'quant'; kind: string; label: string }
  | { type: 'save_sentence'; word: WordRef; sentence: string }
  | { type: 'noted'; text: string }
  | { type: 'forgot'; text: string }

/** A message from the student's saved chat with the coach. */
export interface SavedChatMessage extends ChatMessage {
  proposal: PlanProposal | null
  actions: CoachAction[]
}

export interface CoachReply {
  reply: string
  counted_as_hint: boolean
  proposal: PlanProposal | null
  actions: CoachAction[]
  /** AI requests left today, or null when there is no limit. */
  remaining: number | null
}

/** What a streamed coach reply sends as it's written. */
export type CoachEvent =
  | { type: 'text'; text: string }
  | { type: 'status'; text: string }
  | ({ type: 'done' } & CoachReply)
  | { type: 'error'; detail: string }

export interface CoachNote {
  id: number
  text: string
  created_at: string
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

/** A single question type, or a mix: 'mixed' is Verbal, 'quant' is Quant. */
export type PracticeType = 'tc' | 'se' | 'rc' | 'qc' | 'qmc' | 'qne'
export type PracticeKind = PracticeType | 'mixed' | 'quant'
export type StudyFormat = 'mixed' | 'flashcard' | 'mcq'

/** Whether the next Vocab word leans toward due reviews or new words. */
export type StudyFocus = 'review' | 'balanced' | 'new'

export interface DataTable {
  columns: string[]
  rows: string[][]
}

export interface PracticeItem {
  id: string
  item_type: PracticeType
  kind_name: string
  hint_available: boolean
  payload: {
    difficulty: 'easy' | 'medium' | 'hard'
    /** tc / se */
    text?: string
    blanks?: string[][]
    /** se, rc, qc, qmc */
    options?: string[]
    /** rc / qmc: pick one, or select every right option */
    select?: 'one' | 'all'
    /** rc */
    passage?: string
    question?: string
    order?: number
    of?: number
    /** rc passage topic, or quant topic (arithmetic, algebra, geometry, data) */
    topic?: string
    /** quant */
    table?: DataTable | null
    info?: string | null
    quantity_a?: string
    quantity_b?: string
    unit?: string | null
    fraction?: boolean
  }
}

/** What the learner sent: chosen option indices, or a typed value for numeric entry. */
export interface PracticeResponse {
  selected?: number[]
  value?: string
}

export interface PracticeResult {
  correct: boolean
  difficulty: string
  rating_before: number
  rating_after: number
  feedback: {
    explanation: string
    correct_indices?: number[]
    /** numeric entry */
    correct_answer?: string
    /** tc / se */
    filled_text?: string
    /** bank words among the options (tc / se) or in the passage (rc) */
    words?: { id: number; lemma: string; definition: string }[]
  }
}

export type PracticeSummary = Record<
  PracticeType,
  {
    name: string
    section: 'verbal' | 'quant'
    rating: number | null
    attempts: number
    accuracy: number | null
    questions: number
  }
>
