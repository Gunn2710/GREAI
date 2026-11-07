import { ArrowRight, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { OptionResult, Verdict } from '@/components/Option'
import { ErrorAlert, LoadingCard } from '@/components/Status'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { CardStats, DEPTH_LABEL, TIER_LABEL, formatDue } from '../components/Comfort'
import { Question, type Submit } from '../components/Question'
import { SetProgress } from '../components/Sets'
import { WordCard } from '../components/WordCard'
import { api, ApiError } from '../lib/api'
import type { AnswerResult, StudyItem, WordSet } from '../lib/types'

type Phase =
  | { kind: 'loading' }
  | { kind: 'question'; item: StudyItem; isNew: boolean; likelyKnown: boolean }
  | { kind: 'result'; item: StudyItem; result: AnswerResult; response: Record<string, unknown> }
  | { kind: 'done'; nextDue: string | null }
  | { kind: 'error'; message: string }

export default function Study() {
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' })
  const [busy, setBusy] = useState(false)
  const [count, setCount] = useState(0)
  const [set, setSet] = useState<(WordSet & { total: number }) | null>(null)

  const loadNext = useCallback(async () => {
    setPhase({ kind: 'loading' })
    try {
      const res = await api.next()
      if (!res.done) setSet(res.set)
      setPhase(
        res.done
          ? { kind: 'done', nextDue: res.next_due }
          : { kind: 'question', item: res.item, isNew: res.is_new_word, likelyKnown: res.likely_known },
      )
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof ApiError ? e.message : 'Could not reach the server' })
    }
  }, [])

  useEffect(() => {
    loadNext()
  }, [loadNext])

  const submit: Submit = async (response, ms, confidence) => {
    if (phase.kind !== 'question') return
    setBusy(true)
    try {
      const result = await api.answer(phase.item.id, response, ms, confidence)
      setPhase({ kind: 'result', item: phase.item, result, response })
      setCount((c) => c + 1)
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof ApiError ? e.message : 'Could not submit answer' })
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (phase.kind !== 'result') return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter') loadNext()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phase.kind, loadNext])

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        {set ? (
          <Link to={`/words?set=${set.number}`} className="flex items-center gap-3 hover:text-foreground">
            <span>
              <span className="font-medium text-foreground">Set {set.number}</span> of {set.total}
            </span>
            <SetProgress set={set} className="w-20" />
            <span className="tabular-nums">
              {set.started}/{set.size} started
            </span>
          </Link>
        ) : (
          <span>Vocabulary session</span>
        )}
        <span className="tabular-nums">{count} answered</span>
      </div>

      {phase.kind === 'loading' && <LoadingCard />}

      {phase.kind === 'error' && (
        <div className="flex flex-col items-start gap-3">
          <ErrorAlert>{phase.message}</ErrorAlert>
          <Button variant="outline" onClick={loadNext}>
            Try again
          </Button>
        </div>
      )}

      {phase.kind === 'done' && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-4 text-center">
            <h2 className="text-xl font-semibold tracking-tight">All caught up</h2>
            <p className="max-w-md text-sm text-muted-foreground">
              {phase.nextDue ? `Your next review is due ${formatDue(phase.nextDue)}.` : 'No reviews scheduled.'} New
              words for today are done too. You can raise the daily limit in Settings.
            </p>
            <div className="mt-2 flex flex-wrap justify-center gap-2">
              <Button variant="outline" onClick={loadNext}>
                Check again
              </Button>
              <Button asChild>
                <Link to="/dashboard">Back to dashboard</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {phase.kind === 'question' && (
        <Card>
          <CardContent className="flex flex-col gap-3">
            {(phase.isNew || phase.likelyKnown) && (
              <div className="flex flex-wrap gap-2">
                {phase.isNew && <Badge>New word</Badge>}
                {phase.likelyKnown && (
                  <Badge className="bg-success-soft text-success">Quick check: you probably know this one</Badge>
                )}
              </div>
            )}
            <Question key={phase.item.id} item={phase.item} busy={busy} onSubmit={submit} />
          </CardContent>
        </Card>
      )}

      {phase.kind === 'result' && <Result {...phase} onNext={loadNext} />}
    </div>
  )
}

function Result({
  item,
  result,
  response,
  onNext,
}: {
  item: StudyItem
  result: AnswerResult
  response: Record<string, unknown>
  onNext: () => void
}) {
  const delta = result.comfort_after - result.comfort_before
  const options = item.payload.options ?? []
  const correctSet = new Set(
    result.feedback.correct_indices ?? (result.feedback.correct_index !== undefined ? [result.feedback.correct_index] : []),
  )
  const chosen = new Set(
    Array.isArray(response.selected) ? (response.selected as number[]) : typeof response.selected === 'number' ? [response.selected] : [],
  )

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <Verdict ok={result.correct}>
          {item.item_type === 'flashcard' ? (result.correct ? 'Got it' : 'Marked for relearning') : result.correct ? 'Correct' : 'Not quite'}
          <span className="text-sm font-normal opacity-80">
            · rated <b className="font-semibold">{result.rating}</b>
          </span>
        </Verdict>

        {item.payload.sentence && <p className="rounded-lg bg-muted px-4 py-3 text-lg">{item.payload.sentence}</p>}
        {options.length > 0 && (
          <div className={cn('grid gap-2', item.item_type === 'synonyms' && 'grid-cols-2 sm:grid-cols-3')}>
            {options.map((opt, i) => (
              <OptionResult key={i} state={correctSet.has(i) ? 'correct' : chosen.has(i) ? 'wrong' : 'idle'}>
                {opt}
              </OptionResult>
            ))}
          </div>
        )}

        {result.feedback.ai_feedback && (
          <Alert>
            <Sparkles />
            <AlertDescription className="text-foreground">
              <p>{result.feedback.ai_feedback}</p>
              {result.feedback.improved_sentence && (
                <p className="text-muted-foreground">
                  Suggested: <i>{result.feedback.improved_sentence}</i>
                </p>
              )}
            </AlertDescription>
          </Alert>
        )}

        <div className="flex flex-col gap-3 rounded-lg border p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="tabular-nums">
              Comfort {result.comfort_before.toFixed(0)} → <b className="font-semibold">{result.comfort_after.toFixed(0)}</b>{' '}
              <span className={delta >= 0 ? 'text-success' : 'text-destructive'}>
                ({delta >= 0 ? '+' : ''}
                {delta.toFixed(0)})
              </span>
            </span>
            <span className="flex flex-wrap items-center gap-2">
              {result.promoted && (
                <Badge className="bg-success-soft text-success">Level up: {DEPTH_LABEL[result.card.depth_name]}</Badge>
              )}
              {result.demoted && (
                <Badge className="bg-destructive-soft text-destructive">Back to {DEPTH_LABEL[result.card.depth_name]}</Badge>
              )}
              <span className="text-xs text-muted-foreground">{TIER_LABEL[result.card.tier]}</span>
            </span>
          </div>
          <CardStats card={result.card} />
        </div>

        <Separator />
        <WordCard word={result.word} linkToDetail />

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
