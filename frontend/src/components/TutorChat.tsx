import { SendHorizontal } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
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
    <div className="flex flex-col gap-3">
      {messages.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {STARTERS.map((s) => (
            <Button key={s} variant="outline" size="sm" className="rounded-full" onClick={() => send(s)} disabled={busy}>
              {s}
            </Button>
          ))}
        </div>
      )}
      {(messages.length > 0 || busy) && (
        <div className="flex flex-col gap-2">
          {messages.map((m, i) => (
            <div
              key={i}
              className={cn(
                'max-w-[85%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap',
                m.role === 'user' ? 'self-end bg-primary text-primary-foreground' : 'self-start bg-muted',
              )}
            >
              {m.content}
            </div>
          ))}
          {busy && <div className="self-start rounded-2xl bg-muted px-4 py-2 text-sm text-muted-foreground">Thinking…</div>}
        </div>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
      <form onSubmit={onSubmit} className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={`Ask about “${lemma}”…`}
          maxLength={2000}
        />
        <Button type="submit" disabled={busy || !draft.trim()}>
          <SendHorizontal />
          Send
        </Button>
      </form>
    </div>
  )
}
