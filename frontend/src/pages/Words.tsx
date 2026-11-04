import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ComfortMeter, DEPTH_LABEL, FREQUENCY_LABEL, FrequencyBadge, TierBadge, formatDue } from '../components/Comfort'
import { api } from '../lib/api'
import type { WordListEntry } from '../lib/types'

const FILTERS = [0, 1, 2, 3] as const

export default function Words() {
  const [search, setSearch] = useState('')
  const [frequency, setFrequency] = useState<number>(0)
  const [words, setWords] = useState<WordListEntry[] | null>(null)

  useEffect(() => {
    const t = setTimeout(() => {
      api.words(search.trim() || undefined).then(setWords).catch(() => setWords([]))
    }, 200)
    return () => clearTimeout(t)
  }, [search])

  const count = (tier: number) => words?.filter((w) => !tier || w.tier === tier).length ?? 0
  const shown = words?.filter((w) => !frequency || w.tier === frequency) ?? []

  return (
    <div className="panel">
      <div className="row space">
        <h2>Word bank</h2>
        <input className="search" placeholder="Search…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <div className="filters" role="group" aria-label="Filter by GRE frequency">
        {FILTERS.map((tier) => (
          <button key={tier} className={frequency === tier ? 'on' : ''} onClick={() => setFrequency(tier)}>
            {tier ? FREQUENCY_LABEL[tier] : 'All'} ({count(tier)})
          </button>
        ))}
      </div>
      {!words ? (
        <p className="muted">Loading…</p>
      ) : (
        <div className="table-wrap">
          <table className="words-table">
            <thead>
              <tr>
                <th>Word</th>
                <th className="hide-sm">Meaning</th>
                <th className="hide-sm">On the GRE</th>
                <th>Comfort</th>
                <th className="hide-sm">Depth</th>
                <th className="hide-sm">Next review</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((w) => (
                <tr key={w.id}>
                  <td>
                    <Link to={`/words/${w.id}`}>{w.lemma}</Link> <span className="pos">{w.pos}</span>
                  </td>
                  <td className="muted small hide-sm">{w.definition}</td>
                  <td className="nowrap hide-sm">
                    <FrequencyBadge tier={w.tier} />
                  </td>
                  <td className="comfort-cell">
                    <TierBadge tier={w.card.tier} />
                    {w.card.tier !== 'new' && <ComfortMeter value={w.card.comfort} tier={w.card.tier} />}
                  </td>
                  <td className="small nowrap hide-sm">{DEPTH_LABEL[w.card.depth_name]}</td>
                  <td className="small muted nowrap hide-sm">{w.card.due && w.card.reps > 0 ? formatDue(w.card.due) : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
