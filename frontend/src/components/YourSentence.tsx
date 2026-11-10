/**
 * "Your sentence": an optional sentence the student writes with a word to help
 * them remember it. Shown wherever the word's meaning is revealed.
 */
import { NotebookPen, Pencil, Plus } from 'lucide-react'
import { useState, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError } from '../lib/api'

const MAX = 500

/** The saved sentence, read-only (e.g. on the back of a flashcard). */
export function SentenceNote({ sentence }: { sentence: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-dashed px-4 py-3">
      <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <NotebookPen className="size-3.5" />
        Your sentence
      </span>
      <p className="text-sm">{sentence}</p>
    </div>
  )
}

/** Write, edit or remove your sentence for a word. */
export function YourSentence({
  wordId,
  lemma,
  initial,
  onSaved,
}: {
  wordId: number
  lemma: string
  initial: string | null
  onSaved?: (sentence: string | null) => void
}) {
  const [saved, setSaved] = useState(initial)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(initial ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save(text: string) {
    setBusy(true)
    setError(null)
    try {
      const { my_sentence } = await api.saveSentence(wordId, text)
      setSaved(my_sentence)
      setDraft(my_sentence ?? '')
      setEditing(false)
      onSaved?.(my_sentence)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not save your sentence')
    } finally {
      setBusy(false)
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      if (draft.trim()) save(draft)
    } else if (e.key === 'Escape') {
      setDraft(saved ?? '')
      setEditing(false)
    }
  }

  if (!editing && !saved) {
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
          <Plus />
          Add your sentence
        </Button>
        <span className="text-xs text-muted-foreground">Optional: use “{lemma}” in your own words to remember it.</span>
      </div>
    )
  }

  if (!editing && saved) {
    return (
      <div className="flex flex-col gap-1 rounded-lg border border-dashed px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <NotebookPen className="size-3.5" />
            Your sentence
          </span>
          <Button variant="ghost" size="xs" onClick={() => setEditing(true)} aria-label="Edit your sentence">
            <Pencil />
            Edit
          </Button>
        </div>
        <p className="text-sm">{saved}</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-dashed px-4 py-3">
      <label
        htmlFor={`sentence-${wordId}`}
        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground"
      >
        <NotebookPen className="size-3.5" />
        Your sentence
      </label>
      <Textarea
        id={`sentence-${wordId}`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={`Write a sentence with “${lemma}” that's easy for you to remember…`}
        maxLength={MAX}
        rows={2}
        autoFocus
        className="min-h-16"
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => save(draft)} disabled={busy || !draft.trim()}>
          {busy ? 'Saving…' : 'Save'}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setDraft(saved ?? '')
            setEditing(false)
            setError(null)
          }}
          disabled={busy}
        >
          Cancel
        </Button>
        {saved && (
          <Button variant="ghost" size="sm" className="text-destructive" onClick={() => save('')} disabled={busy}>
            Remove
          </Button>
        )}
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {draft.length}/{MAX}
        </span>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
