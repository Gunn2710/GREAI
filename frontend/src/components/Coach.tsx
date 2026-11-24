/**
 * The study coach. It starts as a side chat (Coach) that minimizes into a
 * bubble in the corner, and can go full screen on its own page (/chat,
 * CoachChat). Both show the same conversation (lib/CoachProvider.tsx). It knows the
 * student's progress and what's on screen, and offers actions the student
 * confirms with a button.
 */
import { Maximize2, MessageCircle, Minimize2, NotebookPen, RotateCcw, SendHorizontal, Sparkles, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { useCoach, type CoachMessage, type CoachPage } from '../lib/coach'
import { COACH_FREE } from '../lib/routes'
import { useConfig } from '../lib/config'
import { Notes } from './CoachNotes'
import { ActionCard, ProposalCard } from './CoachOffers'

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

/** The side chat, or the bubble it minimizes to, on every page except those in COACH_FREE. */
export function Coach() {
  const { ai_enabled } = useConfig()
  const { open, setOpen } = useCoach()
  const onHome = COACH_FREE.includes(useLocation().pathname)
  // Take keyboard focus only when the student opens it, not when it starts open.
  const [opened, setOpened] = useState(false)

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
        onClick={() => {
          setOpened(true)
          setOpen(true)
        }}
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
        <CoachChat variant="panel" autoFocus={opened} />
      </section>
    </>
  )
}

/**
 * The conversation: messages, suggested questions, offered actions and the
 * message box. `page` fills the chat page (the message box sticks to the
 * bottom of the window); `panel` fills the side chat.
 */
export function CoachChat({ variant, autoFocus = true }: { variant: 'page' | 'panel'; autoFocus?: boolean }) {
  const { page, setOpen, messages, loaded, busy, status, error, remaining, send, clear } = useCoach()
  const navigate = useNavigate()
  const location = useLocation()
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
    // On the chat page the window scrolls (past the message box stuck to the bottom).
    if (isPage) window.scrollTo({ top: document.documentElement.scrollHeight })
    else endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, status, isPage])

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus()
  }, [autoFocus])

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
        {isPage ? (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => {
              // Back to the page it was opened from, with the side chat open.
              setOpen(true)
              navigate((location.state as { from?: string } | null)?.from ?? '/')
            }}
            aria-label="Exit full screen"
            title="Exit full screen"
          >
            <Minimize2 />
          </Button>
        ) : (
          <>
            <Button
              variant="ghost"
              size="icon-sm"
              className="hidden sm:inline-flex"
              onClick={() => navigate('/chat', { state: { from: location.pathname + location.search } })}
              aria-label="Full screen"
              title="Full screen"
            >
              <Maximize2 />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setOpen(false)}
              aria-label="Minimize the study coach"
              title="Minimize"
            >
              <X />
            </Button>
          </>
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
