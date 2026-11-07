import { CircleCheck, Lock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { TIER_FILL } from './Comfort'
import type { SetStatus, WordSet } from '../lib/types'

/** Learned words in green, started-but-not-learned in grey, on one bar. */
export function SetProgress({ set, className }: { set: WordSet; className?: string }) {
  const pct = (n: number) => `${(n / Math.max(1, set.size)) * 100}%`
  return (
    <div
      className={cn('flex h-1.5 overflow-hidden rounded-full bg-muted', className)}
      title={`${set.learned} learned · ${set.started} started of ${set.size}`}
    >
      <div className={cn('h-full', TIER_FILL.comfortable)} style={{ width: pct(set.learned) }} />
      <div className="h-full bg-primary/25" style={{ width: pct(set.started - set.learned) }} />
    </div>
  )
}

export function SetStatusMark({ status }: { status: SetStatus }) {
  if (status === 'current') return <Badge>Current</Badge>
  if (status === 'done') return <CircleCheck className="size-4 text-success" aria-label="Done" />
  if (status === 'locked') return <Lock className="size-3.5 text-muted-foreground" aria-label="Locked" />
  return <span className="text-xs text-muted-foreground">Reviewing</span>
}

export function SetTile({
  set,
  selected,
  onSelect,
}: {
  set: WordSet
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        'flex flex-col gap-2 rounded-lg border bg-card p-3 text-left transition-colors hover:bg-accent/60 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
        selected && 'border-primary ring-1 ring-primary',
        set.status === 'locked' && !selected && 'text-muted-foreground',
      )}
    >
      <div className="flex h-5 items-center justify-between gap-2">
        <span className="text-sm font-medium">Set {set.number}</span>
        <SetStatusMark status={set.status} />
      </div>
      <SetProgress set={set} />
      <span className="text-xs text-muted-foreground tabular-nums">
        {set.learned} learned · {set.started}/{set.size} started
      </span>
    </button>
  )
}
