/**
 * The study coach: a chat bubble in the corner of every page that opens into
 * a side chat. It knows the student's progress and what's on screen (see
 * lib/coach.tsx), and can suggest plan changes for the student to save.
 */
import { CalendarCheck, Check, MessageCircle, RotateCcw, SendHorizontal, Sparkles, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { api, ApiError } from '../lib/api'
import { useCoach, type CoachPage } from '../lib/coach'
import { useConfig } from '../lib/config'
import type { ChatMessage, PlanProposal, Profile } from '../lib/types'

type Message = ChatMessage & { proposal?: PlanProposal | null }

const GENERAL = [
  'What is my current vocabulary progress?',
  'Which section should I work on?',
  'Help me set a target progress.',
]

function pageStarters(page: CoachPage): string[] {
  if (!page) return []
  if (page.kind === 'word')
    return [`Give me a memory trick for “${page.lemma}”`, 'How is it different from its synonyms?']
  if (page.kind === 'practice') {
    return page.answered
      ? ['Explain the answer', 'How do I spot this faster next time?']
      : ['Give me a hint', 'What is this question asking?', 'What concept does this test?']
  }
  if (page.answered) return ['Explain the answer', 'Have I mixed this word up before?']
  if (page.flashcard) return ['Give me a memory trick', 'Use it in a GRE-style sentence']
  return ['Give me a hint', 'What is this question asking?']
}

function pageLabel(page: CoachPage): string {
  if (!page) return 'Knows your progress and plan'
  if (page.kind === 'word') return `Looking at “${page.lemma}” with you`
  return 'Looking at this question with you'
}

export function Coach() {
  const { ai_enabled } = useConfig()
  const { page, open, setOpen, queued, takeQueued } = useCoach()
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, busy, open])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  async function send(text: string) {
    const content = text.trim()
    if (!content || busy) return
    const thread: Message[] = [...messages, { role: 'user', content }]
    setMessages(thread)
    setDraft('')
    setBusy(true)
    setError(null)
    try {
      const history = thread.slice(-40).map(({ role, content }) => ({ role, content }))
      const where =
        page?.kind === 'study'
          ? { study_item_id: page.itemId }
          : page?.kind === 'practice'
            ? { practice_item_id: page.itemId }
            : page?.kind === 'word'
              ? { word_id: page.wordId }
              : {}
      const res = await api.coach(history, where)
      setMessages([...thread, { role: 'assistant', content: res.reply, proposal: res.proposal }])
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong')
      setMessages(messages)
      setDraft(content)
    } finally {
      setBusy(false)
    }
  }

  // A page asked the coach something (e.g. a button on the word page).
  useEffect(() => {
    if (open && queued && !busy) {
      const text = takeQueued()
      if (text) send(text)
    }
    // send() reads the latest state; running on `queued` is enough.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, queued])

  useEffect(() => {
    if (!open) return
    const onKey = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, setOpen])

  if (!ai_enabled) return null

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    send(draft)
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send(draft)
    }
  }

  const starters = pageStarters(page)
  const hintWarning =
    (page?.kind === 'study' && !page.answered && !page.flashcard) || (page?.kind === 'practice' && !page.answered)

  if (!open) {
    return (
      <Button
        className="fixed right-4 bottom-4 z-40 size-14 rounded-full shadow-lg [&_svg:not([class*='size-'])]:size-6"
        onClick={() => setOpen(true)}
        aria-label="Open the study coach"
        title="Study coach"
      >
        <MessageCircle />
      </Button>
    )
  }

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30 sm:hidden" onClick={() => setOpen(false)} aria-hidden />
      <section
        role="dialog"
        aria-label="Study coach"
        className="fixed inset-x-0 bottom-0 z-50 flex h-[85svh] flex-col rounded-t-2xl border bg-background shadow-xl sm:inset-x-auto sm:right-4 sm:bottom-4 sm:h-[min(640px,calc(100svh-2rem))] sm:w-[400px] sm:rounded-2xl"
      >
        <header className="flex items-center gap-3 border-b px-4 py-3">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </div>
          <div className="flex min-w-0 flex-1 flex-col">
            <h2 className="text-sm leading-5 font-semibold">Study coach</h2>
            <p className="truncate text-xs text-muted-foreground">{pageLabel(page)}</p>
          </div>
          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => {
                setMessages([])
                setError(null)
              }}
              disabled={busy}
              aria-label="Start a new chat"
              title="New chat"
            >
              <RotateCcw />
            </Button>
          )}
          <Button variant="ghost" size="icon-sm" onClick={() => setOpen(false)} aria-label="Close the study coach">
            <X />
          </Button>
        </header>

        <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          {messages.length === 0 && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                Hi! I can see your progress and help you plan, pick what to work on, and answer GRE and vocabulary
                questions.
              </p>
              <div className="flex flex-col items-start gap-2">
                {[...starters, ...GENERAL].map((s) => (
                  <Starter key={s} text={s} onClick={() => send(s)} disabled={busy} />
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) =>
            m.role === 'user' ? (
              <div
                key={i}
                className="max-w-[85%] self-end rounded-2xl bg-primary px-3.5 py-2 text-sm whitespace-pre-wrap text-primary-foreground"
              >
                {m.content}
              </div>
            ) : (
              <div key={i} className="flex max-w-[90%] flex-col gap-2 self-start">
                <div className="rounded-2xl bg-muted px-3.5 py-2 text-sm whitespace-pre-wrap">
                  <Emphasis text={m.content} />
                </div>
                {m.proposal && <ProposalCard proposal={m.proposal} />}
              </div>
            ),
          )}
          {busy && (
            <div className="self-start rounded-2xl bg-muted px-3.5 py-2 text-sm text-muted-foreground">Thinking…</div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div ref={endRef} />
        </div>

        <div className="flex flex-col gap-2 border-t px-4 pt-3 pb-4">
          {messages.length > 0 && starters.length > 0 && (
            <div className="-mx-4 flex gap-2 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {starters.map((s) => (
                <Starter key={s} text={s} onClick={() => send(s)} disabled={busy} small />
              ))}
            </div>
          )}
          {hintWarning && (
            <p className="text-xs text-muted-foreground">
              I won't give the answer away before you answer, and asking about this question counts as a hint.
            </p>
          )}
          <form onSubmit={onSubmit} className="flex items-end gap-2">
            <Textarea
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask your study coach…"
              aria-label="Message the study coach"
              maxLength={2000}
              rows={1}
              className="max-h-32 min-h-9 resize-none py-1.5"
            />
            <Button type="submit" size="icon" disabled={busy || !draft.trim()} aria-label="Send">
              <SendHorizontal />
            </Button>
          </form>
        </div>
      </section>
    </>
  )
}

function Starter({
  text,
  onClick,
  disabled,
  small = false,
}: {
  text: string
  onClick: () => void
  disabled: boolean
  small?: boolean
}) {
  return (
    <Button
      variant="outline"
      size={small ? 'xs' : 'sm'}
      className={cn(
        'h-auto rounded-full text-left whitespace-normal',
        small ? 'shrink-0 py-1 whitespace-nowrap' : 'py-1.5',
      )}
      onClick={onClick}
      disabled={disabled}
    >
      {text}
    </Button>
  )
}

const FIELD_LABEL: Record<keyof Profile, string> = {
  test_date: 'Test date',
  target_verbal: 'Verbal target',
  target_quant: 'Quant target',
  daily_new_words: 'New words per day',
}

function show(key: keyof Profile, value: Profile[keyof Profile]): string {
  if (value === null || value === undefined) return 'not set'
  if (key === 'test_date') {
    return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }
  return String(value)
}

/** A suggested plan change with a Save button. */
function ProposalCard({ proposal }: { proposal: PlanProposal }) {
  const [state, setState] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [error, setError] = useState<string | null>(null)
  const keys = (Object.keys(FIELD_LABEL) as (keyof Profile)[]).filter((k) => k in proposal.changes)

  async function save() {
    setState('saving')
    setError(null)
    try {
      // Start from the saved plan so changes made since the suggestion are kept.
      const current = await api.profile()
      await api.saveProfile({ ...current, ...proposal.changes })
      setState('saved')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not save')
      setState('idle')
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl border p-3 text-sm">
      <div className="flex items-center gap-2 font-medium">
        <CalendarCheck className="size-4 text-primary" />
        Suggested plan
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        {keys.map((k) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground">{FIELD_LABEL[k]}</dt>
            <dd>
              <span className="text-muted-foreground line-through decoration-muted-foreground/60">
                {show(k, proposal.current[k])}
              </span>{' '}
              → <b className="font-semibold">{show(k, proposal.changes[k] as Profile[keyof Profile])}</b>
            </dd>
          </div>
        ))}
      </dl>
      {state === 'saved' ? (
        <p className="flex items-center gap-1.5 text-success">
          <Check className="size-4" />
          Saved to your plan
        </p>
      ) : (
        <Button size="sm" className="self-start" onClick={save} disabled={state === 'saving'}>
          {state === 'saving' ? 'Saving…' : 'Save to my plan'}
        </Button>
      )}
      {error && <p className="text-destructive">{error}</p>}
    </div>
  )
}

/** Shows **bold** and *italic* from a reply as text styles (no other markdown, no HTML). */
function Emphasis({ text }: { text: string }) {
  return text.split(/(\*\*[^*\n]+\*\*|\*[^*\n]+\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? (
      <strong key={i} className="font-semibold">
        {part.slice(2, -2)}
      </strong>
    ) : part.startsWith('*') && part.endsWith('*') && part.length > 2 ? (
      <em key={i}>{part.slice(1, -1)}</em>
    ) : (
      part
    ),
  )
}
