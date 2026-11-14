/**
 * Vocab study settings, remembered per browser (a convenience only): the study
 * mode and how often new words come up. The study coach can change them too,
 * so a change is announced with an event the Vocab page listens for.
 */
import type { StudyFocus, StudyFormat } from './types'

export const FORMATS: { format: StudyFormat; label: string }[] = [
  { format: 'mixed', label: 'Mixed' },
  { format: 'flashcard', label: 'Flashcards' },
  { format: 'mcq', label: 'Multiple choice' },
]

export const FOCUSES: { focus: StudyFocus; label: string; title: string }[] = [
  { focus: 'review', label: 'Less', title: 'Clear due reviews before new words' },
  { focus: 'balanced', label: 'Balanced', title: 'About half new words, half reviews' },
  { focus: 'new', label: 'More', title: "New words first, up to today's limit, then reviews" },
]

const FORMAT_KEY = 'study-format'
const FOCUS_KEY = 'study-focus'
export const PREFS_EVENT = 'study-prefs-changed'

function load(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function save(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // storage blocked: the choice just won't be remembered
  }
}

export function savedFormat(): StudyFormat {
  const v = load(FORMAT_KEY)
  return FORMATS.some((f) => f.format === v) ? (v as StudyFormat) : 'mixed'
}

export function savedFocus(): StudyFocus {
  const v = load(FOCUS_KEY)
  return FOCUSES.some((f) => f.focus === v) ? (v as StudyFocus) : 'review'
}

/** Save study settings and tell an open Vocab page about them. */
export function saveStudyPrefs(prefs: { format?: StudyFormat; focus?: StudyFocus }) {
  if (prefs.format) save(FORMAT_KEY, prefs.format)
  if (prefs.focus) save(FOCUS_KEY, prefs.focus)
  window.dispatchEvent(new Event(PREFS_EVENT))
}
