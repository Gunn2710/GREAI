/** Labels and colours for comfort tiers, depth and word frequency, shared by the
 * Comfort components and the pages that use them. */
import type { DepthName, Tier } from './types'

export const TIER_LABEL: Record<Tier, string> = {
  new: 'New',
  learning: 'Learning',
  shaky: 'Shaky',
  comfortable: 'Comfortable',
  mastered: 'Mastered',
}

/** Written out in full so Tailwind can find the class names. */
export const TIER_FILL: Record<Tier, string> = {
  new: 'bg-tier-new',
  learning: 'bg-tier-learning',
  shaky: 'bg-tier-shaky',
  comfortable: 'bg-tier-comfortable',
  mastered: 'bg-tier-mastered',
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

export function formatDue(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now()
  if (ms <= 0) return 'now'
  const min = Math.round(ms / 60000)
  if (min < 60) return `in ${min} min`
  const hours = Math.round(min / 60)
  if (hours < 36) return `in ${hours} h`
  return `in ${Math.round(hours / 24)} days`
}
