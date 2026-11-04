import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CardStats, DEPTH_LABEL, TIER_LABEL, formatDue } from '../components/Comfort'
import { Question, type Submit } from '../components/Question'
import { WordCard } from '../components/WordCard'
import { api, ApiError } from '../lib/api'
import type { AnswerResult, StudyItem } from '../lib/types'

type Phase =
  | { kind: 'loading' }
  | { kind: 'question'; item: StudyItem; isNew: boolean; likelyKnown: boolean }
  | { kind: 'result'; item: StudyItem; result: AnswerResult; response: Record<string, unknown> }
  | { kind: 'done'; nextDue: string | null }
  | { kind: 'error'; message: string }

export default function Study() {
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' })
  const [busy, setBusy] = useState(false)
  const [count, setCount] = useState(0)

  const loadNext = useCallback(async () => {
    setPhase({ kind: 'loading' })
    try {
      const res = await api.next()
      setPhase(
        res.done
          ? { kind: 'done', nextDue: res.next_due }
          : { kind: 'question', item: res.item, isNew: res.is_new_word, likelyKnown: res.likely_known },
      )
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof ApiError ? e.message : 'Could not reach the server' })
    }
  }, [])

  useEffect(() => {
    loadNext()
  }, [loadNext])

  const submit: Submit = async (response, ms, confidence) => {
    if (phase.kind !== 'question') return
    setBusy(true)
    try {
      const result = await api.answer(phase.item.id, response, ms, confidence)
      setPhase({ kind: 'result', item: phase.item, result, response })
      setCount((c) => c + 1)
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof ApiError ? e.message : 'Could not submit answer' })
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (phase.kind !== 'result') return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter') loadNext()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phase.kind, loadNext])

  return (
    <div className="study">
      <div className="row space muted small">
        <span>Vocabulary session</span>
        <span>{count} answered</span>
      </div>

      {phase.kind === 'loading' && <div className="panel muted">Loading…</div>}

      {phase.kind === 'error' && (
        <div className="panel">
          <p className="error">{phase.message}</p>
          <button onClick={loadNext}>Try again</button>
        </div>
      )}

      {phase.kind === 'done' && (
        <div className="panel center">
          <h2>All caught up</h2>
          <p className="muted">
            {phase.nextDue ? `Your next review is due ${formatDue(phase.nextDue)}.` : 'No reviews scheduled.'} New
            words for today are done too. You can raise the daily limit in Settings.
          </p>
          <div className="row center">
            <button onClick={loadNext}>Check again</button>
            <Link to="/" className="button primary">
              Back to dashboard
            </Link>
          </div>
        </div>
      )}

      {phase.kind === 'question' && (
        <div className="panel">
          {phase.isNew && <div className="new-word">New word</div>}
          {phase.likelyKnown && <div className="new-word quick-check">Quick check: you probably know this one</div>}
          <Question key={phase.item.id} item={phase.item} busy={busy} onSubmit={submit} />
        </div>
      )}

      {phase.kind === 'result' && <Result {...phase} onNext={loadNext} />}
    </div>
  )
}

function Result({
  item,
  result,
  response,
  onNext,
}: {
  item: StudyItem
  result: AnswerResult
  response: Record<string, unknown>
  onNext: () => void
}) {
  const delta = result.comfort_after - result.comfort_before
  const options = item.payload.options ?? []
  const correctSet = new Set(
    result.feedback.correct_indices ?? (result.feedback.correct_index !== undefined ? [result.feedback.correct_index] : []),
  )
  const chosen = new Set(
    Array.isArray(response.selected) ? (response.selected as number[]) : typeof response.selected === 'number' ? [response.selected] : [],
  )

  return (
    <div className="panel">
      <div className={`verdict ${result.correct ? 'ok' : 'bad'}`}>
        {item.item_type === 'flashcard' ? (result.correct ? 'Got it' : 'Marked for relearning') : result.correct ? 'Correct' : 'Not quite'}
        <span className="small">
          {' '}
          · rated <b>{result.rating}</b>
        </span>
      </div>

      {item.payload.sentence && <p className="sentence">{item.payload.sentence}</p>}
      {options.length > 0 && (
        <div className={`options ${item.item_type === 'synonyms' ? 'grid' : ''}`}>
          {options.map((opt, i) => (
            <div key={i} className={`option static ${correctSet.has(i) ? 'correct' : chosen.has(i) ? 'wrong' : ''}`}>
              {opt}
            </div>
          ))}
        </div>
      )}

      {result.feedback.ai_feedback && (
        <div className="ai-feedback">
          <p>{result.feedback.ai_feedback}</p>
          {result.feedback.improved_sentence && (
            <p className="muted">
              Suggested: <i>{result.feedback.improved_sentence}</i>
            </p>
          )}
        </div>
      )}

      <div className="comfort-change">
        <div className="row space">
          <span>
            Comfort {result.comfort_before.toFixed(0)} → <b>{result.comfort_after.toFixed(0)}</b>{' '}
            <span className={delta >= 0 ? 'up' : 'down'}>
              ({delta >= 0 ? '+' : ''}
              {delta.toFixed(0)})
            </span>
          </span>
          <span className="row">
            {result.promoted && <span className="badge promoted">Level up: {DEPTH_LABEL[result.card.depth_name]}</span>}
            {result.demoted && <span className="badge demoted">Back to {DEPTH_LABEL[result.card.depth_name]}</span>}
            <span className="muted small">{TIER_LABEL[result.card.tier]}</span>
          </span>
        </div>
        <CardStats card={result.card} />
      </div>

      <WordCard word={result.word} linkToDetail />

      <div className="row end">
        <button className="primary" onClick={onNext} autoFocus>
          Next (Enter)
        </button>
      </div>
    </div>
  )
}
