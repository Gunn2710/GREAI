import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ComfortMeter, DEPTH_LABEL, TIER_LABEL, TierBadge } from '../components/Comfort'
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

  if (error) return <div className="panel error">{error}. Is the backend running on :8000?</div>
  if (!stats) return <div className="panel muted">Loading…</div>

  const todo = stats.due_now + stats.new_available_today
  const maxForecast = Math.max(1, ...stats.forecast.map((f) => f.due))
  const startedWords = stats.total_words - stats.tiers.new

  return (
    <div className="dashboard">
      <section className="hero panel">
        <div>
          <h2>{todo > 0 ? `${todo} items ready` : 'All caught up'}</h2>
          <p className="muted">
            {stats.due_now} reviews due · {stats.new_available_today} new words left today
          </p>
        </div>
        <Link to="/study" className="button primary big">
          {todo > 0 ? 'Start studying' : 'Practice'}
        </Link>
      </section>

      {placement === null && (
        <section className="panel callout row space">
          <div>
            <h3>Skip what you already know</h3>
            <p className="muted">A 4-minute placement check estimates your level and fast-tracks words you already know.</p>
          </div>
          <Link to="/placement" className="button">
            Take placement check
          </Link>
        </section>
      )}

      <section className="tiles">
        <Tile label="Vocab level" value={placement ? placement.level : '–'} />
        <Tile label="Reviews today" value={stats.reviews_today} />
        <Tile label="Accuracy (30 d)" value={stats.accuracy_30d == null ? '–' : `${Math.round(stats.accuracy_30d * 100)}%`} />
        <Tile label="Words started" value={`${startedWords} / ${stats.total_words}`} />
        <Tile label="Streak" value={`${stats.streak_days} d`} />
      </section>

      <section className="panel">
        <h3>Comfort</h3>
        <div className="stacked">
          {TIERS.map((t) =>
            stats.tiers[t] ? (
              <div
                key={t}
                className={`stacked-seg tier-bg-${t}`}
                style={{ flexGrow: stats.tiers[t] }}
                title={`${TIER_LABEL[t]}: ${stats.tiers[t]}`}
              />
            ) : null,
          )}
        </div>
        <div className="legend">
          {TIERS.map((t) => (
            <span key={t}>
              <TierBadge tier={t} /> {stats.tiers[t]}
            </span>
          ))}
        </div>
      </section>

      <div className="two-col">
        <section className="panel">
          <h3>Depth of knowledge</h3>
          <p className="muted small">Highest level reached per started word</p>
          {DEPTHS.map((d) => {
            const atOrAbove = DEPTHS.slice(DEPTHS.indexOf(d)).reduce((n, k) => n + stats.depth[k], 0)
            return (
              <div key={d} className="bar-row">
                <span className="bar-label">{DEPTH_LABEL[d]}</span>
                <div className="bar">
                  <div className="bar-fill" style={{ width: `${startedWords ? (atOrAbove / startedWords) * 100 : 0}%` }} />
                </div>
                <span className="bar-value">{atOrAbove}</span>
              </div>
            )
          })}
        </section>

        <section className="panel">
          <h3>Upcoming reviews</h3>
          <div className="forecast">
            {stats.forecast.map((f, i) => (
              <div key={f.date} className="forecast-col" title={`${f.date}: ${f.due}`}>
                <span className="small">{f.due || ''}</span>
                <div className="forecast-bar" style={{ height: `${(f.due / maxForecast) * 80}px` }} />
                <span className="muted small">
                  {i === 0 ? 'Today' : new Date(f.date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short' })}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {stats.weakest.length > 0 && (
        <section className="panel">
          <h3>Needs attention</h3>
          <ul className="word-rows">
            {stats.weakest.map(({ word, card }) => (
              <li key={word.id}>
                <Link to={`/words/${word.id}`}>{word.lemma}</Link>
                <span className="muted small grow">{word.definition}</span>
                <span className="meter-cell">
                  <ComfortMeter value={card.comfort} tier={card.tier} />
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="tile panel">
      <div className="tile-value">{value}</div>
      <div className="muted small">{label}</div>
    </div>
  )
}
