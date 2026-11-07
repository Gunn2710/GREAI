import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { FREQUENCY_LABEL } from '../components/Comfort'
import { Pronunciation, SpeakButton } from '../components/Pronounce'
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
    <div className="study">
      {phase.kind === 'intro' && (
        <div className="panel">
          <h2>Placement check</h2>
          <p>
            20 quick questions, about 4 minutes. Each one shows a word: pick its meaning, or choose{' '}
            <b>I don't know</b>. Please don't guess; an honest "I don't know" gives a better estimate.
          </p>
          <p className="muted">
            Questions adapt to your answers. Words you get right are marked as known and come back later for a quick check.
            Later, new words you very likely know are fast-tracked instead of taught from scratch.
          </p>
          {error && <p className="error">{error}</p>}
          <div className="row end">
            <button className="primary" disabled={busy} onClick={begin}>
              Start
            </button>
          </div>
        </div>
      )}

      {phase.kind === 'question' && (
        <div className="panel">
          <div className="row space small muted">
            <span>
              Question {phase.item.number} of {phase.item.max}
            </span>
          </div>
          <div className="bar placement-progress">
            <div className="bar-fill" style={{ width: `${((phase.item.number - 1) / phase.item.max) * 100}%` }} />
          </div>
          <h2 className="prompt-word">
            {phase.item.word} <SpeakButton text={phase.item.word} /> <span className="pos">{phase.item.pos}</span>
          </h2>
          <Pronunciation value={phase.item.pronunciation} />
          <div className="options">
            {phase.item.options.map((opt, i) => (
              <button key={`${phase.item.id}-${i}`} className="option" disabled={busy} onClick={() => choose(i)}>
                <span className="option-key">{String.fromCharCode(65 + i)}</span>
                {opt}
              </button>
            ))}
            <button className="option dont-know" disabled={busy} onClick={() => choose(null)}>
              I don't know
            </button>
          </div>
          {error && <p className="error">{error}</p>}
        </div>
      )}

      {phase.kind === 'result' && <PlacementSummary result={phase.result} />}
    </div>
  )
}

export function PlacementSummary({ result }: { result: PlacementResult }) {
  return (
    <div className="panel">
      <div className="muted small">Your vocabulary level</div>
      <h2>{result.level}</h2>
      <p className="muted">
        {result.correct} of {result.answered} correct. {result.fast_tracked} words marked as known; they'll come back for a
        quick check instead of being taught from scratch.
      </p>

      <h3>Words you likely know already</h3>
      {Object.entries(result.known_share).map(([tier, share]) => (
        <div key={tier} className="bar-row wide">
          <span className="bar-label">{FREQUENCY_LABEL[Number(tier)]}</span>
          <div className="bar">
            <div className="bar-fill" style={{ width: `${share * 100}%` }} />
          </div>
          <span className="bar-value">{Math.round(share * 100)}%</span>
        </div>
      ))}
      <p className="muted small">
        Estimated from 20 answers, so treat it as a rough guide. It sharpens as you study and as more people take the check.
      </p>

      {result.missed.length > 0 && (
        <>
          <h3>Words to learn first</h3>
          <div className="chips">
            {result.missed.map((w) => (
              <Link key={w.id} to={`/words/${w.id}`} className="chip button">
                {w.lemma}
              </Link>
            ))}
          </div>
        </>
      )}

      <div className="row end">
        <Link to="/dashboard" className="button">
          Dashboard
        </Link>
        <Link to="/study" className="button primary">
          Start studying
        </Link>
      </div>
    </div>
  )
}
