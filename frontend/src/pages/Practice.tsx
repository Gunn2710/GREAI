import { ArrowRight, Lightbulb, Sparkles, Square, SquareCheck } from 'lucide-react'
import { Fragment, useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { OptionButton, OptionResult, Verdict } from '@/components/Option'
import { HintButton, ModeTag } from '@/components/Question'
import { ErrorAlert, LoadingCard } from '@/components/Status'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { api, ApiError } from '../lib/api'
import type { PracticeItem, PracticeKind, PracticeResult, PracticeSummary } from '../lib/types'

const KINDS: { kind: PracticeKind; label: string }[] = [
  { kind: 'mixed', label: 'Mixed' },
  { kind: 'tc', label: 'Text Completion' },
  { kind: 'se', label: 'Sentence Equivalence' },
]
const ROMAN = ['i', 'ii', 'iii']
/** Answer columns side by side for 2-3 blanks, stacked on phones. */
const BLANK_COLUMNS: Record<number, string> = { 1: '', 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-3' }

/** Same bands as the placement level. */
function levelLabel(rating: number): string {
  if (rating < -0.5) return 'Building'
  if (rating < 0.5) return 'Developing'
  if (rating < 1.5) return 'Strong'
  return 'Advanced'
}

type Phase =
  | { kind: 'loading' }
  | { kind: 'question'; item: PracticeItem }
  | { kind: 'result'; item: PracticeItem; result: PracticeResult; selected: number[] }
  | { kind: 'error'; message: string }

export default function Practice() {
  const [kind, setKind] = useState<PracticeKind>('mixed')
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' })
  const [summary, setSummary] = useState<PracticeSummary | null>(null)

  const loadNext = useCallback(async (k: PracticeKind) => {
    setPhase({ kind: 'loading' })
    try {
      const { item } = await api.practiceNext(k)
      setPhase({ kind: 'question', item })
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof ApiError ? e.message : 'Could not reach the server' })
    }
  }, [])

  useEffect(() => {
    loadNext(kind)
  }, [kind, loadNext])

  useEffect(() => {
    api.practiceSummary().then(setSummary).catch(() => setSummary(null))
  }, [phase.kind])

  useEffect(() => {
    if (phase.kind !== 'result') return
    const onKey = (e: KeyboardEvent) => e.key === 'Enter' && loadNext(kind)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phase.kind, kind, loadNext])

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <Tabs value={kind} onValueChange={(v) => setKind(v as PracticeKind)}>
        <TabsList className="w-full sm:w-fit" aria-label="Question type">
          {KINDS.map((k) => (
            <TabsTrigger key={k.kind} value={k.kind} className="sm:px-3">
              {k.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {summary && (
        <div className="grid grid-cols-2 gap-4">
          {(['tc', 'se'] as const).map((k) => (
            <Card key={k} className="gap-1 px-4 py-4">
              <div className="text-xs text-muted-foreground">{summary[k].name}</div>
              <div className="text-2xl font-semibold tracking-tight">
                {summary[k].rating == null ? '–' : levelLabel(summary[k].rating!)}
              </div>
              <div className="text-xs text-muted-foreground">
                {summary[k].attempts
                  ? `${summary[k].attempts} answered · ${Math.round((summary[k].accuracy ?? 0) * 100)}% correct`
                  : `${summary[k].questions} questions`}
              </div>
            </Card>
          ))}
        </div>
      )}

      {phase.kind === 'loading' && <LoadingCard />}
      {phase.kind === 'error' && (
        <div className="flex flex-col items-start gap-3">
          <ErrorAlert>{phase.message}</ErrorAlert>
          <Button variant="outline" onClick={() => loadNext(kind)}>
            Try again
          </Button>
        </div>
      )}
      {phase.kind === 'question' && (
        <Question
          key={phase.item.id}
          item={phase.item}
          onAnswered={(result, selected) => setPhase({ kind: 'result', item: phase.item, result, selected })}
          onError={(message) => setPhase({ kind: 'error', message })}
        />
      )}
      {phase.kind === 'result' && <Result {...phase} onNext={() => loadNext(kind)} />}
    </div>
  )
}

/** Renders the passage, drawing each {n} marker as a blank (filled with `fills[n-1]` when set). */
function Passage({ text, fills, multi }: { text: string; fills: (string | null)[]; multi: boolean }) {
  const parts = text.split(/\{(\d)\}/)
  return (
    <p className="text-lg leading-8">
      {parts.map((part, i) => {
        if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>
        const n = Number(part) - 1
        return (
          <span
            key={i}
            className={cn(
              'inline-block min-w-24 border-b-2 px-1 text-center',
              fills[n] ? 'border-primary font-semibold' : 'border-muted-foreground/50',
            )}
          >
            {multi && <sup className="mr-0.5 font-normal text-muted-foreground">({ROMAN[n]})</sup>}
            {fills[n] ?? ' '.repeat(12)}
          </span>
        )
      })}
    </p>
  )
}

function Question({
  item,
  onAnswered,
  onError,
}: {
  item: PracticeItem
  onAnswered: (r: PracticeResult, selected: number[]) => void
  onError: (m: string) => void
}) {
  const shownAt = useRef(performance.now())
  const isTc = item.item_type === 'tc'
  const blanks = item.payload.blanks ?? []
  const [selected, setSelected] = useState<(number | null)[]>(isTc ? blanks.map(() => null) : [])
  const [clue, setClue] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const complete = isTc ? selected.every((s) => s !== null) : selected.length === 2
  const fills = isTc
    ? selected.map((s, b) => (s === null ? null : blanks[b][s]))
    : [selected.length === 1 ? item.payload.options![selected[0]!] : null]

  function pickTc(blank: number, option: number) {
    setSelected((s) => s.map((v, i) => (i === blank ? option : v)))
  }

  function toggleSe(option: number) {
    setSelected((s) => (s.includes(option) ? s.filter((x) => x !== option) : s.length < 2 ? [...s, option] : s))
  }

  async function hint() {
    setClue((await api.practiceHint(item.id)).clue)
  }

  async function submit() {
    setBusy(true)
    const response = { selected: selected as number[] }
    try {
      onAnswered(await api.practiceAnswer(item.id, response, performance.now() - shownAt.current), selected as number[])
    } catch (e) {
      onError(e instanceof ApiError ? e.message : 'Could not submit your answer')
    }
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <ModeTag>
          {item.kind_name}
          {isTc && blanks.length > 1 && ` · ${blanks.length} blanks`} · {item.payload.difficulty}
        </ModeTag>
        <Passage text={item.payload.text} fills={fills} multi={blanks.length > 1} />

        {isTc ? (
          <>
            <p className="text-sm text-muted-foreground">
              {blanks.length === 1
                ? 'Choose the word that best completes the text.'
                : 'Choose one entry for each blank. All blanks must be right to get credit.'}
            </p>
            <div className={cn('grid gap-3', BLANK_COLUMNS[blanks.length])}>
              {blanks.map((opts, b) => (
                <div key={b} className="flex flex-col gap-2">
                  {blanks.length > 1 && <ColumnHead>Blank ({ROMAN[b]})</ColumnHead>}
                  {opts.map((opt, o) => (
                    <OptionButton
                      key={o}
                      state={selected[b] === o ? 'selected' : 'idle'}
                      disabled={busy}
                      onClick={() => pickTc(b, o)}
                    >
                      {opt}
                    </OptionButton>
                  ))}
                </div>
              ))}
            </div>
          </>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              Select the <b className="font-semibold text-foreground">two</b> answers that each complete the sentence and
              produce sentences alike in meaning.
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {item.payload.options!.map((opt, o) => {
                const on = selected.includes(o)
                const Box = on ? SquareCheck : Square
                return (
                  <OptionButton
                    key={o}
                    state={on ? 'selected' : 'idle'}
                    disabled={busy}
                    onClick={() => toggleSe(o)}
                    aria-pressed={on}
                  >
                    <Box className={cn('size-4 shrink-0', on ? 'text-primary' : 'text-muted-foreground')} />
                    {opt}
                  </OptionButton>
                )
              })}
            </div>
          </>
        )}

        {clue && (
          <Alert>
            <Lightbulb />
            <AlertDescription className="text-foreground">Clue: {clue}</AlertDescription>
          </Alert>
        )}
        <div className="flex items-center justify-between gap-2">
          <HintButton used={!!clue} disabled={busy} onHint={hint} />
          <Button disabled={!complete || busy} onClick={submit}>
            Check answer
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function ColumnHead({ children }: { children: ReactNode }) {
  return <div className="text-center text-xs text-muted-foreground">{children}</div>
}

function Result({
  item,
  result,
  selected,
  onNext,
}: {
  item: PracticeItem
  result: PracticeResult
  selected: number[]
  onNext: () => void
}) {
  const isTc = item.item_type === 'tc'
  const blanks = item.payload.blanks ?? []
  const correct = result.feedback.correct_indices
  const delta = result.rating_after - result.rating_before

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <Verdict ok={result.correct}>{result.correct ? 'Correct' : 'Not quite'}</Verdict>
        <p className="text-lg leading-8">{result.feedback.filled_text}</p>

        {isTc ? (
          <div className={cn('grid gap-3', BLANK_COLUMNS[blanks.length])}>
            {blanks.map((opts, b) => (
              <div key={b} className="flex flex-col gap-2">
                {blanks.length > 1 && <ColumnHead>Blank ({ROMAN[b]})</ColumnHead>}
                {opts.map((opt, o) => (
                  <OptionResult key={o} state={correct[b] === o ? 'correct' : selected[b] === o ? 'wrong' : 'idle'}>
                    {opt}
                  </OptionResult>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {item.payload.options!.map((opt, o) => (
              <OptionResult key={o} state={correct.includes(o) ? 'correct' : selected.includes(o) ? 'wrong' : 'idle'}>
                {opt}
              </OptionResult>
            ))}
          </div>
        )}

        <Alert>
          <Sparkles />
          <AlertDescription className="text-foreground">
            <p>{result.feedback.explanation}</p>
          </AlertDescription>
        </Alert>

        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span>
            {item.kind_name}: <b className="font-semibold">{levelLabel(result.rating_after)}</b>{' '}
            <span className={cn('tabular-nums', delta >= 0 ? 'text-success' : 'text-destructive')}>
              ({delta >= 0 ? '+' : ''}
              {delta.toFixed(2)})
            </span>
          </span>
          <span className="text-muted-foreground">Difficulty: {result.difficulty}</span>
        </div>

        {result.feedback.words.length > 0 && (
          <div className="flex flex-col gap-2">
            <span className="text-xs text-muted-foreground">Vocabulary in this question</span>
            <div className="flex flex-wrap gap-1.5">
              {result.feedback.words.map((w) => (
                <Badge key={w.id} variant="outline" className="px-2.5 py-1 text-sm font-normal" asChild>
                  <Link to={`/words/${w.id}`} title={w.definition}>
                    {w.lemma}
                  </Link>
                </Badge>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end">
          <Button onClick={onNext} autoFocus>
            Next
            <kbd className="font-sans text-xs opacity-60">Enter</kbd>
            <ArrowRight />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
