import { Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { api, ApiError } from '../lib/api'
import type { CoachNote } from '../lib/types'

/** What the coach remembers about the student, which they can delete. */
export function Notes() {
  const [notes, setNotes] = useState<CoachNote[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .coachNotes()
      .then((res) => setNotes(res.notes))
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Could not load notes'))
  }, [])

  async function remove(id: number) {
    setError(null)
    try {
      setNotes((await api.deleteCoachNote(id)).notes)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not delete the note')
    }
  }

  return (
    <div className="flex flex-col gap-3 text-sm">
      <div className="flex flex-col gap-1">
        <h3 className="font-semibold">What I remember about you</h3>
        <p className="text-muted-foreground">
          Short notes I keep between chats, like your goals and how you like things explained. Delete any you don't want
          me to use.
        </p>
      </div>
      {notes === null && !error && <p className="text-muted-foreground">Loading…</p>}
      {notes?.length === 0 && <p className="text-muted-foreground">Nothing yet.</p>}
      {notes && notes.length > 0 && (
        <ul className="divide-y rounded-xl border">
          {notes.map((n) => (
            <li key={n.id} className="flex items-start gap-2 py-2 pr-1.5 pl-3">
              <span className="flex-1 pt-1">{n.text}</span>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => remove(n.id)}
                aria-label={`Delete note: ${n.text}`}
                title="Delete"
              >
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="text-destructive">{error}</p>}
    </div>
  )
}
