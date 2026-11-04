import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import type { PracticeItem, PracticeKind, PracticeResult, PracticeSummary } from '../lib/types'

const KINDS: { kind: PracticeKind; label: string }[] = [
  { kind: 'mixed', label: 'Mixed' },
  { kind: 'tc', label: 'Text Completion' },
  { kind: 'se', label: 'Sentence Equivalence' },
]
const ROMAN = ['i', 'ii', 'iii']

/** Same bands as the placement level. */
function levelLabel(rating: number): string {
  if (rating < -0.5) return 'Building'
  if (rating < 0.5) return 'Developing'
  if (rating < 1.5) return 'Strong'
  return 'Advanced'
}

type Phase =
  | { kind: 'loading' }
  | { kind: 'question'; item: PracticeItem }
  | { kind: 'result'; item: PracticeItem; result: PracticeResult; selected: number[] }
  | { kind: 'error'; message: string }

export default function Practice() {
  const [kind, setKind] = useState<PracticeKind>('mixed')
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' })
  const [summary, setSummary] = useState<PracticeSummary | null>(null)

  const loadNext = useCallback(async (k: PracticeKind) => {
    setPhase({ kind: 'loading' })
    try {
      const { item } = await api.practiceNext(k)
      setPhase({ kind: 'question', item })
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof ApiError ? e.message : 'Could not reach the server' })
    }
  }, [])

  useEffect(() => {
    loadNext(kind)
  }, [kind, loadNext])

  useEffect(() => {
    api.practiceSummary().then(setSummary).catch(() => setSummary(null))
  }, [phase.kind])

  useEffect(() => {
    if (phase.kind !== 'result') return
    const onKey = (e: KeyboardEvent) => e.key === 'Enter' && loadNext(kind)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phase.kind, kind, loadNext])

  return (
    <div className="study practice">
      <div className="filters" role="group" aria-label="Question type">
        {KINDS.map((k) => (
          <button key={k.kind} className={kind === k.kind ? 'on' : ''} onClick={() => setKind(k.kind)}>
            {k.label}
          </button>
        ))}
      </div>

      {summary && (
        <div className="practice-summary">
          {(['tc', 'se'] as const).map((k) => (
            <div key={k} className="panel tile">
              <div className="muted small">{summary[k].name}</div>
              <div className="tile-value">{summary[k].rating == null ? '–' : levelLabel(summary[k].rating!)}</div>
              <div className="muted small">
                {summary[k].attempts
                  ? `${summary[k].attempts} answered · ${Math.round((summary[k].accuracy ?? 0) * 100)}% correct`
                  : `${summary[k].questions} questions`}
              </div>
            </div>
          ))}
        </div>
      )}

      {phase.kind === 'loading' && <div className="panel muted">Loading…</div>}
      {phase.kind === 'error' && (
        <div className="panel">
          <p className="error">{phase.message}</p>
          <button onClick={() => loadNext(kind)}>Try again</button>
        </div>
      )}
      {phase.kind === 'question' && (
        <Question
          key={phase.item.id}
          item={phase.item}
          onAnswered={(result, selected) => setPhase({ kind: 'result', item: phase.item, result, selected })}
          onError={(message) => setPhase({ kind: 'error', message })}
        />
      )}
      {phase.kind === 'result' && <Result {...phase} onNext={() => loadNext(kind)} />}
    </div>
  )
}

/** Renders the passage, drawing each {n} marker as a blank (filled with `fills[n-1]` when set). */
function Passage({ text, fills, multi }: { text: string; fills: (string | null)[]; multi: boolean }) {
  const parts = text.split(/\{(\d)\}/)
  return (
    <p className="passage">
      {parts.map((part, i) => {
        if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>
        const n = Number(part) - 1
        return (
          <span key={i} className={`blank ${fills[n] ? 'filled' : ''}`}>
            {multi && <sup>({ROMAN[n]})</sup>}
            {fills[n] ?? ' '.repeat(12)}
          </span>
        )
      })}
    </p>
  )
}

function Question({
  item,
  onAnswered,
  onError,
}: {
  item: PracticeItem
  onAnswered: (r: PracticeResult, selected: number[]) => void
  onError: (m: string) => void
}) {
  const shownAt = useRef(performance.now())
  const isTc = item.item_type === 'tc'
  const blanks = item.payload.blanks ?? []
  const [selected, setSelected] = useState<(number | null)[]>(isTc ? blanks.map(() => null) : [])
  const [clue, setClue] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const complete = isTc ? selected.every((s) => s !== null) : selected.length === 2
  const fills = isTc
    ? selected.map((s, b) => (s === null ? null : blanks[b][s]))
    : [selected.length === 1 ? item.payload.options![selected[0]!] : null]

  function pickTc(blank: number, option: number) {
    setSelected((s) => s.map((v, i) => (i === blank ? option : v)))
  }

  function toggleSe(option: number) {
    setSelected((s) => (s.includes(option) ? s.filter((x) => x !== option) : s.length < 2 ? [...s, option] : s))
  }

  async function hint() {
    setClue((await api.practiceHint(item.id)).clue)
  }

  async function submit() {
    setBusy(true)
    const response = { selected: selected as number[] }
    try {
      onAnswered(await api.practiceAnswer(item.id, response, performance.now() - shownAt.current), selected as number[])
    } catch (e) {
      onError(e instanceof ApiError ? e.message : 'Could not submit your answer')
    }
  }

  return (
    <div className="panel question">
      <div className="row space">
        <div className="mode-tag">
          {item.kind_name}
          {isTc && blanks.length > 1 && ` · ${blanks.length} blanks`} · {item.payload.difficulty}
        </div>
      </div>
      <Passage text={item.payload.text} fills={fills} multi={blanks.length > 1} />

      {isTc ? (
        <>
          {blanks.length === 1 && <p className="muted small">Choose the word that best completes the text.</p>}
          {blanks.length > 1 && (
            <p className="muted small">Choose one entry for each blank. All blanks must be right to get credit.</p>
          )}
          <div className={`blank-columns cols-${blanks.length}`}>
            {blanks.map((opts, b) => (
              <div key={b} className="blank-column">
                {blanks.length > 1 && <div className="column-head">Blank ({ROMAN[b]})</div>}
                {opts.map((opt, o) => (
                  <button
                    key={o}
                    className={`option ${selected[b] === o ? 'selected' : ''}`}
                    disabled={busy}
                    onClick={() => pickTc(b, o)}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <p className="muted small">
            Select the <b>two</b> answers that each complete the sentence and produce sentences alike in meaning.
          </p>
          <div className="options grid">
            {item.payload.options!.map((opt, o) => (
              <button
                key={o}
                className={`option ${selected.includes(o) ? 'selected' : ''}`}
                disabled={busy}
                onClick={() => toggleSe(o)}
                aria-pressed={selected.includes(o)}
              >
                <span className="checkbox">{selected.includes(o) ? '☑' : '☐'}</span>
                {opt}
              </button>
            ))}
          </div>
        </>
      )}

      {clue && <p className="clue">Clue: {clue}</p>}
      <div className="row space">
        <button className="link" disabled={!!clue || busy} onClick={hint}>
          {clue ? 'Hint used' : 'Hint'}
        </button>
        <button className="primary" disabled={!complete || busy} onClick={submit}>
          Check answer
        </button>
      </div>
    </div>
  )
}

function Result({
  item,
  result,
  selected,
  onNext,
}: {
  item: PracticeItem
  result: PracticeResult
  selected: number[]
  onNext: () => void
}) {
  const isTc = item.item_type === 'tc'
  const blanks = item.payload.blanks ?? []
  const correct = result.feedback.correct_indices
  const delta = result.rating_after - result.rating_before

  return (
    <div className="panel">
      <div className={`verdict ${result.correct ? 'ok' : 'bad'}`}>{result.correct ? 'Correct' : 'Not quite'}</div>
      <p className="passage">{result.feedback.filled_text}</p>

      {isTc ? (
        <div className={`blank-columns cols-${blanks.length}`}>
          {blanks.map((opts, b) => (
            <div key={b} className="blank-column">
              {blanks.length > 1 && <div className="column-head">Blank ({ROMAN[b]})</div>}
              {opts.map((opt, o) => (
                <div
                  key={o}
                  className={`option static ${correct[b] === o ? 'correct' : selected[b] === o ? 'wrong' : ''}`}
                >
                  {opt}
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <div className="options grid">
          {item.payload.options!.map((opt, o) => (
            <div
              key={o}
              className={`option static ${correct.includes(o) ? 'correct' : selected.includes(o) ? 'wrong' : ''}`}
            >
              {opt}
            </div>
          ))}
        </div>
      )}

      <div className="ai-feedback">
        <p>{result.feedback.explanation}</p>
      </div>

      <div className="row space small">
        <span>
          {item.kind_name}: {levelLabel(result.rating_after)}{' '}
          <span className={delta >= 0 ? 'up' : 'down'}>
            ({delta >= 0 ? '+' : ''}
            {delta.toFixed(2)})
          </span>
        </span>
        <span className="muted">Difficulty: {result.difficulty}</span>
      </div>

      {result.feedback.words.length > 0 && (
        <div className="vocab-links">
          <span className="muted small">Vocabulary in this question:</span>
          <div className="chips">
            {result.feedback.words.map((w) => (
              <Link key={w.id} to={`/words/${w.id}`} className="chip button" title={w.definition}>
                {w.lemma}
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="row end">
        <button className="primary" onClick={onNext} autoFocus>
          Next (Enter)
        </button>
      </div>
    </div>
  )
}
