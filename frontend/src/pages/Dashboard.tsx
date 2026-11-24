import { ArrowRight } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ErrorAlert } from '@/components/Status'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { CheckIns } from '../components/CheckIns'
import { ComfortMeter } from '../components/Comfort'
import { DEPTH_LABEL, FREQUENCY_LABEL, TIER_FILL, TIER_LABEL } from '../lib/comfort'
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
    api
      .stats()
      .then(setStats)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Could not reach the server'))
    api
      .placementLatest()
      .then((r) => setPlacement(r.result))
      .catch(() => setPlacement(null))
  }, [])

  if (error) return <ErrorAlert>{error}. Is the backend running on :8000?</ErrorAlert>
  if (!stats) return <DashboardSkeleton />

  const todo = stats.due_now + stats.new_available_today
  const maxForecast = Math.max(1, ...stats.forecast.map((f) => f.due))
  const startedWords = stats.total_words - stats.tiers.new
  const set = stats.sets.current

  return (
    <div className="flex flex-col gap-4">
      {/* Today: what's waiting, and where the current set stands. */}
      <Card>
        <CardContent className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-col gap-1">
              <h1 className="text-2xl font-semibold tracking-tight">
                {todo > 0 ? `${todo} items ready` : 'All caught up'}
              </h1>
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
          </div>
          {set && (
            <>
              <Separator />
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm">
                  <span>
                    <span className="font-medium">Set {set.number}</span>{' '}
                    <span className="text-muted-foreground">
                      of {stats.sets.total} · {set.source === 'gregmat' ? 'GregMat group' : FREQUENCY_LABEL[set.tier]}
                    </span>
                  </span>
                  <span className="text-muted-foreground tabular-nums">
                    {set.learned} learned · {set.started} of {set.size} started
                    {stats.sets.done > 0 && ` · ${stats.sets.done} ${stats.sets.done === 1 ? 'set' : 'sets'} done`}
                    {' · '}
                    <Link to={`/words?set=${set.number}`} className="text-foreground hover:underline">
                      All sets
                    </Link>
                  </span>
                </div>
                <SetProgress set={set} className="h-2" />
              </div>
            </>
          )}
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

      {/* Check-ins take the width their grid needs; the numbers fill the rest. */}
      <div className="grid gap-4 md:grid-cols-[auto_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Check-ins</CardTitle>
            <CardDescription>Words studied each day</CardDescription>
            <CardAction>
              <Badge variant="secondary" className="tabular-nums">
                {stats.streak_days}-day streak
              </Badge>
            </CardAction>
          </CardHeader>
          <CardContent>
            <CheckIns activity={stats.activity} />
          </CardContent>
        </Card>
        <section className="grid grid-cols-2 gap-4">
          <Tile label="reviews today" value={stats.reviews_today} />
          <Tile
            label="accuracy, last 30 days"
            value={stats.accuracy_30d == null ? '–' : `${Math.round(stats.accuracy_30d * 100)}%`}
          />
          <Tile label={`of ${stats.total_words} words started`} value={startedWords} />
          <Tile label="vocab level" value={placement ? placement.level : '–'} />
        </section>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Comfort</CardTitle>
            <CardDescription>How well you know each word</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {TIERS.map((t) => (
              <Row
                key={t}
                label={
                  <span className="flex items-center gap-2">
                    <span className={cn('size-2 rounded-full', TIER_FILL[t])} />
                    {TIER_LABEL[t]}
                  </span>
                }
                value={stats.tiers[t]}
                of={stats.total_words}
                fill={TIER_FILL[t]}
              />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Depth of knowledge</CardTitle>
            <CardDescription>Highest level reached per started word</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {DEPTHS.map((d) => (
              <Row
                key={d}
                label={DEPTH_LABEL[d]}
                value={DEPTHS.slice(DEPTHS.indexOf(d)).reduce((n, k) => n + stats.depth[k], 0)}
                of={startedWords}
              />
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className={cn(stats.weakest.length === 0 && 'md:col-span-2')}>
          <CardHeader>
            <CardTitle>Upcoming reviews</CardTitle>
            <CardDescription>Next 7 days</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-1 items-end">
            <div className="flex h-32 w-full items-end gap-2">
              {stats.forecast.map((f, i) => (
                <div
                  key={f.date}
                  className="flex flex-1 flex-col items-center justify-end gap-1"
                  title={`${f.date}: ${f.due}`}
                >
                  <span className="text-xs tabular-nums">{f.due || ''}</span>
                  <div
                    className="min-h-0.5 w-full max-w-8 rounded-t-sm bg-primary"
                    style={{ height: `${(f.due / maxForecast) * 80}px` }}
                  />
                  <span className="text-xs text-muted-foreground">
                    {i === 0
                      ? 'Today'
                      : new Date(f.date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short' })}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {stats.weakest.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Needs attention</CardTitle>
              <CardDescription>Your least comfortable words</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="divide-y">
                {stats.weakest.map(({ word, card }) => (
                  <li key={word.id} className="flex items-center gap-3 py-2 first:pt-0 last:pb-0">
                    <Link to={`/words/${word.id}`} className="w-28 shrink-0 truncate font-medium hover:underline">
                      {word.lemma}
                    </Link>
                    <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">{word.definition}</span>
                    <span className="w-14 shrink-0">
                      <ComfortMeter value={card.comfort} tier={card.tier} />
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="justify-center gap-1 px-5 py-4">
      <div className="text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </Card>
  )
}

/** A labelled bar with its count, used by Comfort and Depth so the two cards line up. */
function Row({ label, value, of, fill }: { label: ReactNode; value: number; of: number; fill?: string }) {
  return (
    <div className="grid grid-cols-[7rem_1fr_2.5rem] items-center gap-3 text-sm">
      <span>{label}</span>
      {fill ? (
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div className={cn('h-full rounded-full', fill)} style={{ width: `${of ? (value / of) * 100 : 0}%` }} />
        </div>
      ) : (
        <Progress value={of ? (value / of) * 100 : 0} />
      )}
      <span className="text-right tabular-nums">{value}</span>
    </div>
  )
}

/** The dashboard's shape while its numbers load, so nothing jumps when they arrive. */
function DashboardSkeleton() {
  const rows = (n: number) => Array.from({ length: n }, (_, i) => <Skeleton key={i} className="h-4 w-full" />)
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading your dashboard">
      <Card>
        <CardContent className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-col gap-2">
              <Skeleton className="h-7 w-44" />
              <Skeleton className="h-4 w-64" />
            </div>
            <Skeleton className="h-10 w-40" />
          </div>
          <Separator />
          <div className="flex flex-col gap-2">
            <Skeleton className="h-4 w-56" />
            <Skeleton className="h-2 w-full" />
          </div>
        </CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-[auto_1fr]">
        <Card>
          <CardContent className="flex flex-col gap-3">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-36 w-full md:w-[24rem]" />
          </CardContent>
        </Card>
        <section className="grid grid-cols-2 gap-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Card key={i} className="justify-center gap-2 px-5 py-4">
              <Skeleton className="h-7 w-14" />
              <Skeleton className="h-3 w-20" />
            </Card>
          ))}
        </section>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {[5, 4].map((n) => (
          <Card key={n}>
            <CardContent className="flex flex-col gap-3">
              <Skeleton className="h-5 w-32" />
              {rows(n)}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
