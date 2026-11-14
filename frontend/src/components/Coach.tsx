/**
 * The study coach. On the home page it is the whole page (CoachChat); on every
 * other page it shrinks to a chat bubble in the corner that opens into a side
 * chat (Coach). Both show the same conversation (lib/coach.tsx). It knows the
 * student's progress and what's on screen, and offers actions the student
 * confirms with a button.
 */
import {
  ArrowRight,
  BookCheck,
  CalendarCheck,
  Check,
  MessageCircle,
  NotebookPen,
  PencilLine,
  Repeat,
  RotateCcw,
  SendHorizontal,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { api, ApiError } from '../lib/api'
import { useCoach, type CoachMessage, type CoachPage } from '../lib/coach'
import { useConfig } from '../lib/config'
import { FOCUSES, FORMATS, saveStudyPrefs } from '../lib/prefs'
import type { CoachAction, CoachNote, PlanProposal, Profile } from '../lib/types'

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

/** The chat bubble and side chat, on every page except Home (where the chat is the page). */
export function Coach() {
  const { ai_enabled } = useConfig()
  const { open, setOpen } = useCoach()
  const onHome = useLocation().pathname === '/'

  useEffect(() => {
    if (!open || onHome) return
    const onKey = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onHome, setOpen])

  if (!ai_enabled || onHome) return null

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
        <CoachChat variant="panel" />
      </section>
    </>
  )
}

/**
 * The conversation: messages, suggested questions, offered actions and the
 * message box. `page` fills the home page (the message box sticks to the
 * bottom of the window); `panel` fills the side chat.
 */
export function CoachChat({ variant }: { variant: 'page' | 'panel' }) {
  const { page, setOpen, messages, loaded, busy, status, error, remaining, send, clear } = useCoach()
  const [draft, setDraft] = useState('')
  const [showNotes, setShowNotes] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const isPage = variant === 'page'

  useEffect(() => {
    if (!isPage) return
    // The chat opens at its newest message, not where the browser last left the page.
    const before = history.scrollRestoration
    history.scrollRestoration = 'manual'
    return () => {
      history.scrollRestoration = before
    }
  }, [isPage])

  useEffect(() => {
    // On the home page the window scrolls (past the message box stuck to the bottom).
    if (isPage) window.scrollTo({ top: document.documentElement.scrollHeight })
    else endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, status, isPage])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  async function submit(text: string) {
    if (!text.trim() || busy) return
    setShowNotes(false)
    setDraft('')
    if (!(await send(text))) setDraft(text)
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    submit(draft)
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit(draft)
    }
  }

  const starters = pageStarters(page)
  const hintWarning =
    (page?.kind === 'study' && !page.answered && !page.flashcard) || (page?.kind === 'practice' && !page.answered)

  return (
    <div
      className={cn('flex flex-col', isPage ? 'mx-auto min-h-[calc(100svh-9rem)] w-full max-w-2xl' : 'min-h-0 flex-1')}
    >
      <header className={cn('flex items-center gap-3', isPage ? 'pb-4' : 'border-b px-4 py-3')}>
        <div
          className={cn(
            'flex shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground',
            isPage ? 'size-10' : 'size-8',
          )}
        >
          <Sparkles className={isPage ? 'size-5' : 'size-4'} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          {isPage ? (
            <h1 className="text-xl leading-7 font-semibold tracking-tight">Study coach</h1>
          ) : (
            <h2 className="text-sm leading-5 font-semibold">Study coach</h2>
          )}
          <p className="truncate text-xs text-muted-foreground">{pageLabel(page)}</p>
        </div>
        <Button
          variant={showNotes ? 'secondary' : 'ghost'}
          size="icon-sm"
          onClick={() => setShowNotes((v) => !v)}
          aria-label="What the coach remembers about you"
          aria-pressed={showNotes}
          title="What I remember"
        >
          <NotebookPen />
        </Button>
        {messages.length > 0 && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => {
              setShowNotes(false)
              clear()
            }}
            disabled={busy}
            aria-label="Start a new chat"
            title="New chat"
          >
            <RotateCcw />
          </Button>
        )}
        {!isPage && (
          <Button variant="ghost" size="icon-sm" onClick={() => setOpen(false)} aria-label="Close the study coach">
            <X />
          </Button>
        )}
      </header>

      <div className={cn('flex flex-1 flex-col gap-3', isPage ? 'py-2' : 'overflow-y-auto px-4 py-4')}>
        {showNotes ? (
          <Notes />
        ) : (
          <>
            {loaded && messages.length === 0 && (
              <div className="flex flex-col gap-3">
                <p className={cn('text-muted-foreground', isPage ? 'text-base' : 'text-sm')}>
                  Hi! I can see your progress and help you plan, pick what to work on, and answer GRE and vocabulary
                  questions. I can also set things up for you, like a drill on words you mix up.
                </p>
                <div className="flex flex-col items-start gap-2">
                  {[...starters, ...GENERAL].map((s) => (
                    <Starter key={s} text={s} onClick={() => submit(s)} disabled={busy} />
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
                <Reply key={i} message={m} status={i === messages.length - 1 ? status : null} />
              ),
            )}
            {error && <p className="text-sm text-destructive">{error}</p>}
          </>
        )}
        <div ref={endRef} />
      </div>

      <div
        className={cn(
          'flex flex-col gap-2',
          isPage ? 'sticky bottom-0 -mx-4 bg-background px-4 pt-3 pb-4' : 'border-t px-4 pt-3 pb-4',
        )}
      >
        {messages.length > 0 && starters.length > 0 && !showNotes && (
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {starters.map((s) => (
              <Starter key={s} text={s} onClick={() => submit(s)} disabled={busy} small />
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
        {remaining !== null && remaining <= 10 && (
          <p className="text-xs text-muted-foreground">
            {remaining === 0
              ? 'No AI requests left today. They reset at midnight UTC.'
              : `${remaining} AI ${remaining === 1 ? 'request' : 'requests'} left today.`}
          </p>
        )}
      </div>
    </div>
  )
}

/** One reply from the coach, with any plan change or actions it offered. */
function Reply({ message, status }: { message: CoachMessage; status: string | null }) {
  const waiting = message.pending && !message.content
  return (
    <div className="flex max-w-[90%] flex-col gap-2 self-start">
      <div
        className={cn(
          'rounded-2xl bg-muted px-3.5 py-2 text-sm whitespace-pre-wrap',
          waiting && 'text-muted-foreground',
        )}
      >
        {waiting ? `${status ?? 'Thinking'}…` : <Emphasis text={message.content} />}
      </div>
      {message.proposal && <ProposalCard proposal={message.proposal} />}
      {message.actions.map((a, i) => (
        <ActionCard key={i} action={a} />
      ))}
    </div>
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

/** A card for something the coach offered, with the button that does it. */
function OfferCard({
  icon,
  title,
  children,
  button,
  done,
  run,
}: {
  icon: ReactNode
  title: string
  children?: ReactNode
  button: string
  /** What to show once it's done. */
  done: ReactNode
  run: () => Promise<void>
}) {
  const [state, setState] = useState<'idle' | 'working' | 'done'>('idle')
  const [error, setError] = useState<string | null>(null)

  async function go() {
    setState('working')
    setError(null)
    try {
      await run()
      setState('done')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong')
      setState('idle')
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl border p-3 text-sm">
      <div className="flex items-center gap-2 font-medium [&_svg]:size-4 [&_svg]:text-primary">
        {icon}
        {title}
      </div>
      {children}
      {state === 'done' ? (
        <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-success">
          <Check className="size-4" />
          {done}
        </div>
      ) : (
        <Button size="sm" className="self-start" onClick={go} disabled={state === 'working'}>
          {state === 'working' ? 'Working…' : button}
        </Button>
      )}
      {error && <p className="text-destructive">{error}</p>}
    </div>
  )
}

function GoLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="inline-flex items-center gap-1 font-medium text-foreground underline underline-offset-2">
      {children}
      <ArrowRight className="size-3.5" />
    </Link>
  )
}

function ActionCard({ action }: { action: CoachAction }) {
  switch (action.type) {
    case 'review_now':
      return (
        <OfferCard
          icon={<Repeat />}
          title={action.title}
          button="Review these now"
          run={async () => {
            await api.reviewNow(action.words.map((w) => w.id))
          }}
          done={
            <>
              <span>They're due now.</span>
              <GoLink to="/study">Go to Vocab</GoLink>
            </>
          }
        >
          <div className="flex flex-wrap gap-1.5">
            {action.words.map((w) => (
              <Link
                key={w.id}
                to={`/words/${w.id}`}
                className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium hover:underline"
              >
                {w.lemma}
              </Link>
            ))}
          </div>
        </OfferCard>
      )
    case 'mark_known':
      return (
        <OfferCard
          icon={<BookCheck />}
          title={`Mark “${action.word.lemma}” as known`}
          button="I know this word"
          run={async () => {
            await api.markKnown(action.word.id)
          }}
          done="Marked as known. It will come back in a few days for a quick recall check."
        >
          <p className="text-muted-foreground">It skips the learning steps; a miss later sends it back.</p>
        </OfferCard>
      )
    case 'study_settings': {
      const focus = FOCUSES.find((f) => f.focus === action.changes.focus)
      const format = FORMATS.find((f) => f.format === action.changes.format)
      return (
        <OfferCard
          icon={<SlidersHorizontal />}
          title="Change your Vocab settings"
          button="Save settings"
          run={async () => saveStudyPrefs(action.changes)}
          done="Saved. Vocab uses these now."
        >
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            {focus && (
              <>
                <dt className="text-muted-foreground">New word frequency</dt>
                <dd className="font-semibold">{focus.label}</dd>
              </>
            )}
            {format && (
              <>
                <dt className="text-muted-foreground">Study mode</dt>
                <dd className="font-semibold">{format.label}</dd>
              </>
            )}
          </dl>
        </OfferCard>
      )
    }
    case 'open_practice':
      return (
        <Button variant="outline" size="sm" className="self-start" asChild>
          <Link to={`/practice?section=${action.section}&kind=${action.kind}`}>
            Practice {action.label}
            <ArrowRight />
          </Link>
        </Button>
      )
    case 'save_sentence':
      return (
        <OfferCard
          icon={<PencilLine />}
          title={`Save as your sentence for “${action.word.lemma}”`}
          button="Save my sentence"
          run={async () => {
            await api.saveSentence(action.word.id, action.sentence)
          }}
          done={
            <>
              <span>Saved.</span>
              <GoLink to={`/words/${action.word.id}`}>See the word</GoLink>
            </>
          }
        >
          <blockquote className="border-l-2 pl-3 text-muted-foreground italic">{action.sentence}</blockquote>
        </OfferCard>
      )
    case 'noted':
    case 'forgot':
      return (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <NotebookPen className="size-3.5 shrink-0" />
          {action.type === 'noted' ? 'Noted' : 'Forgot'}: {action.text}
        </p>
      )
  }
}

/** What the coach remembers about the student, which they can delete. */
function Notes() {
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

/** A suggested plan change with a Save button. */
function ProposalCard({ proposal }: { proposal: PlanProposal }) {
  const keys = (Object.keys(FIELD_LABEL) as (keyof Profile)[]).filter((k) => k in proposal.changes)
  return (
    <OfferCard
      icon={<CalendarCheck />}
      title="Suggested plan"
      button="Save to my plan"
      run={async () => {
        // Start from the saved plan so changes made since the suggestion are kept.
        const current = await api.profile()
        await api.saveProfile({ ...current, ...proposal.changes })
      }}
      done="Saved to your plan"
    >
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
    </OfferCard>
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
