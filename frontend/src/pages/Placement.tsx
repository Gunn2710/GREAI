import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { OptionButton, OptionKey } from '@/components/Option'
import { ErrorAlert } from '@/components/Status'
import { WordTitle } from '@/components/WordCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { FREQUENCY_LABEL } from '../components/Comfort'
import { Pronunciation } from '../components/Pronounce'
import { api, ApiError } from '../lib/api'
import type { PlacementItem, PlacementResult } from '../lib/types'

type Phase =
  | { kind: 'intro' }
  | { kind: 'question'; runId: string; item: PlacementItem }
  | { kind: 'result'; result: PlacementResult }

export default function Placement() {
  const [phase, setPhase] = useState<Phase>({ kind: 'intro' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const shownAt = useRef(0)

  function show(runId: string, item: PlacementItem) {
    shownAt.current = performance.now()
    setPhase({ kind: 'question', runId, item })
  }

  async function begin() {
    setBusy(true)
    setError(null)
    try {
      const res = await api.placementStart()
      if (!res.done) show(res.run_id, res.item)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start the placement check')
    } finally {
      setBusy(false)
    }
  }

  async function choose(selected: number | null) {
    if (phase.kind !== 'question' || busy) return
    setBusy(true)
    setError(null)
    try {
      const res = await api.placementAnswer(phase.runId, phase.item.id, selected, performance.now() - shownAt.current)
      if (res.done) setPhase({ kind: 'result', result: res.result })
      else show(phase.runId, res.item)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not submit your answer')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      {phase.kind === 'intro' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Placement check</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <p>
              20 quick questions, about 4 minutes. Each one shows a word: pick its meaning, or choose{' '}
              <b className="font-semibold">I don't know</b>. Please don't guess; an honest "I don't know" gives a better
              estimate.
            </p>
            <p className="text-muted-foreground">
              Questions adapt to your answers. Words you get right are marked as known and come back later for a quick
              check. Later, new words you very likely know are fast-tracked instead of taught from scratch.
            </p>
            {error && <ErrorAlert>{error}</ErrorAlert>}
            <div className="flex justify-end">
              <Button disabled={busy} onClick={begin}>
                Start
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {phase.kind === 'question' && (
        <Card>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <span className="text-xs text-muted-foreground tabular-nums">
                Question {phase.item.number} of {phase.item.max}
              </span>
              <Progress value={((phase.item.number - 1) / phase.item.max) * 100} />
            </div>
            <div className="flex flex-col gap-1">
              <WordTitle word={phase.item.word} pos={phase.item.pos} large />
              <Pronunciation value={phase.item.pronunciation} />
            </div>
            <div className="flex flex-col gap-2">
              {phase.item.options.map((opt, i) => (
                <OptionButton key={`${phase.item.id}-${i}`} disabled={busy} onClick={() => choose(i)}>
                  <OptionKey index={i} />
                  {opt}
                </OptionButton>
              ))}
              <OptionButton
                className="justify-center border-dashed text-muted-foreground"
                disabled={busy}
                onClick={() => choose(null)}
              >
                I don't know
              </OptionButton>
            </div>
            {error && <ErrorAlert>{error}</ErrorAlert>}
          </CardContent>
        </Card>
      )}

      {phase.kind === 'result' && <PlacementSummary result={phase.result} />}
    </div>
  )
}

export function PlacementSummary({ result }: { result: PlacementResult }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>Your vocabulary level</CardDescription>
        <CardTitle className="text-2xl tracking-tight">{result.level}</CardTitle>
        <CardDescription>
          {result.correct} of {result.answered} correct. {result.fast_tracked} words marked as known; they'll come back
          for a quick check instead of being taught from scratch.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <section className="flex flex-col gap-3">
          <h3 className="font-semibold">Words you likely know already</h3>
          {Object.entries(result.known_share).map(([tier, share]) => (
            <div key={tier} className="grid grid-cols-[8.5rem_1fr_2.75rem] items-center gap-3 text-sm">
              <span>{FREQUENCY_LABEL[Number(tier)]}</span>
              <Progress value={share * 100} />
              <span className="text-right tabular-nums">{Math.round(share * 100)}%</span>
            </div>
          ))}
          <p className="text-xs text-muted-foreground">
            Estimated from 20 answers, so treat it as a rough guide. It sharpens as you study and as more people take the
            check.
          </p>
        </section>

        {result.missed.length > 0 && (
          <section className="flex flex-col gap-3">
            <h3 className="font-semibold">Words to learn first</h3>
            <div className="flex flex-wrap gap-1.5">
              {result.missed.map((w) => (
                <Badge key={w.id} variant="outline" className="px-2.5 py-1 text-sm font-normal" asChild>
                  <Link to={`/words/${w.id}`}>{w.lemma}</Link>
                </Badge>
              ))}
            </div>
          </section>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" asChild>
            <Link to="/dashboard">Dashboard</Link>
          </Button>
          <Button asChild>
            <Link to="/study">Start studying</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
