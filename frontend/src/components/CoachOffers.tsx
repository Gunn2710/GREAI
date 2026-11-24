/** What the coach offers in a reply: actions and plan changes, each with the button that does it. */
import {
  ArrowRight,
  BookCheck,
  CalendarCheck,
  Check,
  NotebookPen,
  PencilLine,
  Repeat,
  SlidersHorizontal,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { api, ApiError } from '../lib/api'
import { FOCUSES, FORMATS, saveStudyPrefs } from '../lib/prefs'
import type { CoachAction, PlanProposal, Profile } from '../lib/types'

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

export function ActionCard({ action }: { action: CoachAction }) {
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

/** A suggested plan change with a Save button. */
export function ProposalCard({ proposal }: { proposal: PlanProposal }) {
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
