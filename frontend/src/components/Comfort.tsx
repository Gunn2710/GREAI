import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { DEPTH_LABEL, FREQUENCY_LABEL, TIER_FILL, TIER_LABEL, formatDue } from '../lib/comfort'
import type { CardSummary, DepthName, Tier } from '../lib/types'

/** Filled for the most common words, outlined for the rest, fainter for advanced. */
const FREQUENCY_STYLE: Record<number, string> = {
  1: 'border-transparent bg-secondary text-secondary-foreground',
  2: '',
  3: 'text-muted-foreground',
}

export function FrequencyBadge({ tier }: { tier: number }) {
  return (
    <Badge variant="outline" className={FREQUENCY_STYLE[tier]} title="How often this word appears on the GRE">
      {FREQUENCY_LABEL[tier] ?? 'Unrated'}
    </Badge>
  )
}

export function TierBadge({ tier }: { tier: Tier }) {
  return (
    <Badge variant="outline">
      <span className={cn('size-2 rounded-full', TIER_FILL[tier])} />
      {TIER_LABEL[tier]}
    </Badge>
  )
}

export function ComfortMeter({ value, tier }: { value: number; tier: Tier }) {
  return (
    <div className="h-2 min-w-16 overflow-hidden rounded-full bg-muted" title={`Comfort ${value.toFixed(0)} / 100`}>
      <div
        className={cn('h-full rounded-full transition-[width] duration-500', TIER_FILL[tier])}
        style={{ width: `${Math.max(2, value)}%` }}
      />
    </div>
  )
}

/** Four-step ladder: highlights levels the word has reached. */
export function DepthLadder({ depth }: { depth: number }) {
  const steps: DepthName[] = ['recognize', 'recall', 'discriminate', 'use']
  return (
    <div className="flex gap-1" aria-label={`Depth ${depth} of 4`}>
      {steps.map((s, i) => (
        <span
          key={s}
          className={cn(
            'flex-1 truncate rounded-md py-0.5 text-center text-[11px] font-medium',
            i < depth ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground',
          )}
        >
          {DEPTH_LABEL[s]}
        </span>
      ))}
    </div>
  )
}

export function CardStats({ card }: { card: CardSummary }) {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between gap-2">
        <TierBadge tier={card.tier} />
        <span className="text-sm text-muted-foreground tabular-nums">{card.comfort.toFixed(0)} / 100</span>
      </div>
      <ComfortMeter value={card.comfort} tier={card.tier} />
      <DepthLadder depth={card.depth} />
      <div className="text-xs text-muted-foreground">
        {card.recall_probability != null && <>Recall now {Math.round(card.recall_probability * 100)}% · </>}
        {card.due && <>Next review {formatDue(card.due)}</>}
      </div>
    </div>
  )
}
