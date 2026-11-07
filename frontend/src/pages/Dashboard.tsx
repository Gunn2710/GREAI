import { ArrowRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorAlert, LoadingCard } from '@/components/Status'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { ComfortMeter, DEPTH_LABEL, FREQUENCY_LABEL, TIER_FILL, TIER_LABEL, TierBadge } from '../components/Comfort'
import { SetProgress } from '../components/Sets'
import { api, ApiError } from '../lib/api'
import type { DepthName, PlacementResult, Stats, Tier } from '../lib/types'

const TIERS: Tier[] = ['mastered', 'comfortable', 'shaky', 'learning', 'new']
const DEPTHS: DepthName[] = ['recognize', 'recall', 'discriminate', 'use']

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [placement, setPlacement] = useState<PlacementResult | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.stats().then(setStats).catch((e) => setError(e instanceof ApiError ? e.message : 'Could not reach the server'))
    api.placementLatest().then((r) => setPlacement(r.result)).catch(() => setPlacement(null))
  }, [])

  if (error) return <ErrorAlert>{error}. Is the backend running on :8000?</ErrorAlert>
  if (!stats) return <LoadingCard />

  const todo = stats.due_now + stats.new_available_today
  const maxForecast = Math.max(1, ...stats.forecast.map((f) => f.due))
  const startedWords = stats.total_words - stats.tiers.new

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight">{todo > 0 ? `${todo} items ready` : 'All caught up'}</h1>
            <p className="text-sm text-muted-foreground">
              {stats.due_now} reviews due · {stats.new_available_today} new words left today
            </p>
          </div>
          <Button size="lg" asChild>
            <Link to="/study">
              {todo > 0 ? 'Start studying' : 'Practice'}
              <ArrowRight />
            </Link>
          </Button>
        </CardContent>
      </Card>

      {placement === null && (
        <Card className="border-primary/40">
          <CardContent className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-col gap-1">
              <h2 className="font-semibold">Skip what you already know</h2>
              <p className="text-sm text-muted-foreground">
                A 4-minute placement check estimates your level and fast-tracks words you already know.
              </p>
            </div>
            <Button variant="outline" asChild>
              <Link to="/placement">Take placement check</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {stats.sets.current && (
        <Card>
          <CardContent className="flex flex-col gap-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div className="flex items-baseline gap-2">
                <h2 className="font-semibold">Set {stats.sets.current.number}</h2>
                <span className="text-sm text-muted-foreground">
                  of {stats.sets.total} · {FREQUENCY_LABEL[stats.sets.current.tier]}
                </span>
              </div>
              <Button variant="ghost" size="sm" asChild>
                <Link to={`/words?set=${stats.sets.current.number}`}>
                  All sets
                  <ArrowRight />
                </Link>
              </Button>
            </div>
            <SetProgress set={stats.sets.current} className="h-2" />
            <p className="text-sm text-muted-foreground tabular-nums">
              {stats.sets.current.learned} learned · {stats.sets.current.started} of {stats.sets.current.size} started
              {stats.sets.done > 0 && ` · ${stats.sets.done} ${stats.sets.done === 1 ? 'set' : 'sets'} done`}
            </p>
          </CardContent>
        </Card>
      )}

      <section className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
        <Tile label="Vocab level" value={placement ? placement.level : '–'} />
        <Tile label="Reviews today" value={stats.reviews_today} />
        <Tile label="Accuracy (30 d)" value={stats.accuracy_30d == null ? '–' : `${Math.round(stats.accuracy_30d * 100)}%`} />
        <Tile label="Words started" value={`${startedWords} / ${stats.total_words}`} />
        <Tile label="Streak" value={`${stats.streak_days} d`} />
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Comfort</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex h-3 gap-0.5 overflow-hidden rounded-full bg-muted">
            {TIERS.map((t) =>
              stats.tiers[t] ? (
                <div
                  key={t}
                  className={`min-w-1 ${TIER_FILL[t]}`}
                  style={{ flexGrow: stats.tiers[t] }}
                  title={`${TIER_LABEL[t]}: ${stats.tiers[t]}`}
                />
              ) : null,
            )}
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {TIERS.map((t) => (
              <span key={t} className="flex items-center gap-1.5 tabular-nums">
                <TierBadge tier={t} /> {stats.tiers[t]}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Depth of knowledge</CardTitle>
            <CardDescription>Highest level reached per started word</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {DEPTHS.map((d) => {
              const atOrAbove = DEPTHS.slice(DEPTHS.indexOf(d)).reduce((n, k) => n + stats.depth[k], 0)
              return (
                <div key={d} className="grid grid-cols-[6.5rem_1fr_2rem] items-center gap-3 text-sm">
                  <span>{DEPTH_LABEL[d]}</span>
                  <Progress value={startedWords ? (atOrAbove / startedWords) * 100 : 0} />
                  <span className="text-right tabular-nums">{atOrAbove}</span>
                </div>
              )
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Upcoming reviews</CardTitle>
            <CardDescription>Next 7 days</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-32 items-end gap-2">
              {stats.forecast.map((f, i) => (
                <div key={f.date} className="flex flex-1 flex-col items-center justify-end gap-1" title={`${f.date}: ${f.due}`}>
                  <span className="text-xs tabular-nums">{f.due || ''}</span>
                  <div
                    className="min-h-0.5 w-full max-w-8 rounded-t-sm bg-primary"
                    style={{ height: `${(f.due / maxForecast) * 80}px` }}
                  />
                  <span className="text-xs text-muted-foreground">
                    {i === 0 ? 'Today' : new Date(f.date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short' })}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {stats.weakest.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Needs attention</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {stats.weakest.map(({ word, card }) => (
                <li key={word.id} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                  <Link to={`/words/${word.id}`} className="font-medium hover:underline">
                    {word.lemma}
                  </Link>
                  <span className="flex-1 truncate text-sm text-muted-foreground">{word.definition}</span>
                  <span className="w-20 shrink-0">
                    <ComfortMeter value={card.comfort} tier={card.tier} />
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="gap-1 px-4 py-4">
      <div className="text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </Card>
  )
}
