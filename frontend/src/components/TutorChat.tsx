import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../lib/api'
import type { ChatMessage } from '../lib/types'

const STARTERS = [
  'How is this different from its synonyms?',
  'Give me a trickier example sentence.',
  'Quiz me on this word.',
]

export function TutorChat({ wordId, lemma }: { wordId: number; lemma: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send(text: string) {
    const content = text.trim()
    if (!content || busy) return
    const history: ChatMessage[] = [...messages, { role: 'user', content }]
    setMessages(history)
    setDraft('')
    setBusy(true)
    setError(null)
    try {
      const { reply } = await api.tutor(wordId, history)
      setMessages([...history, { role: 'assistant', content: reply }])
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong')
      setMessages(messages)
      setDraft(content)
    } finally {
      setBusy(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    send(draft)
  }

  return (
    <div className="tutor">
      <h3>Tutor</h3>
      {messages.length === 0 && (
        <div className="chips">
          {STARTERS.map((s) => (
            <button key={s} className="chip" onClick={() => send(s)} disabled={busy}>
              {s}
            </button>
          ))}
        </div>
      )}
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.content}
          </div>
        ))}
        {busy && <div className="msg assistant muted">Thinking…</div>}
      </div>
      {error && <p className="error">{error}</p>}
      <form onSubmit={onSubmit} className="row">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={`Ask about “${lemma}”…`}
          maxLength={2000}
        />
        <button type="submit" className="primary" disabled={busy || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
