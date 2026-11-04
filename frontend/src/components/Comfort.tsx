import type { CardSummary, DepthName, Tier } from '../lib/types'

export const TIER_LABEL: Record<Tier, string> = {
  new: 'New',
  learning: 'Learning',
  shaky: 'Shaky',
  comfortable: 'Comfortable',
  mastered: 'Mastered',
}

export const DEPTH_LABEL: Record<DepthName, string> = {
  new: 'Not started',
  recognize: 'Recognize',
  recall: 'Recall',
  discriminate: 'Discriminate',
  use: 'Use',
}

/** How often a word shows up on the GRE (word bank tier 1-3). */
export const FREQUENCY_LABEL: Record<number, string> = {
  1: 'High frequency',
  2: 'Medium frequency',
  3: 'Advanced',
}

export function FrequencyBadge({ tier }: { tier: number }) {
  return (
    <span className={`badge freq-${tier}`} title="How often this word appears on the GRE">
      {FREQUENCY_LABEL[tier] ?? 'Unrated'}
    </span>
  )
}

export function TierBadge({ tier }: { tier: Tier }) {
  return <span className={`badge tier-${tier}`}>{TIER_LABEL[tier]}</span>
}

export function ComfortMeter({ value, tier }: { value: number; tier: Tier }) {
  return (
    <div className="meter" title={`Comfort ${value.toFixed(0)} / 100`}>
      <div className={`meter-fill tier-bg-${tier}`} style={{ width: `${Math.max(2, value)}%` }} />
    </div>
  )
}

/** Five-step ladder: highlights levels the word has reached. */
export function DepthLadder({ depth }: { depth: number }) {
  const steps: DepthName[] = ['recognize', 'recall', 'discriminate', 'use']
  return (
    <div className="ladder" aria-label={`Depth ${depth} of 4`}>
      {steps.map((s, i) => (
        <span key={s} className={`ladder-step ${i < depth ? 'on' : ''}`}>
          {DEPTH_LABEL[s]}
        </span>
      ))}
    </div>
  )
}

export function CardStats({ card }: { card: CardSummary }) {
  return (
    <div className="card-stats">
      <div className="row space">
        <TierBadge tier={card.tier} />
        <span className="muted">{card.comfort.toFixed(0)} / 100</span>
      </div>
      <ComfortMeter value={card.comfort} tier={card.tier} />
      <DepthLadder depth={card.depth} />
      <div className="muted small">
        {card.recall_probability != null && <>Recall now {Math.round(card.recall_probability * 100)}% · </>}
        {card.due && <>Next review {formatDue(card.due)}</>}
      </div>
    </div>
  )
}

export function formatDue(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now()
  if (ms <= 0) return 'now'
  const min = Math.round(ms / 60000)
  if (min < 60) return `in ${min} min`
  const hours = Math.round(min / 60)
  if (hours < 36) return `in ${hours} h`
  return `in ${Math.round(hours / 24)} days`
}
