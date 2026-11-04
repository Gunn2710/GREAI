import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Pronunciation, SpeakButton } from './Pronounce'
import type { Confidence, StudyItem, WordDetail } from '../lib/types'

export type Submit = (response: Record<string, unknown>, responseMs: number, confidence?: Confidence) => void

interface Props {
  item: StudyItem
  busy: boolean
  onSubmit: Submit
}

const MODE_LABEL: Record<StudyItem['item_type'], string> = {
  flashcard: 'Flashcard',
  meaning: 'Meaning',
  cloze: 'In context',
  synonyms: 'Synonym pair',
  usage: 'Use it',
}

export function Question(props: Props) {
  const { item } = props
  return (
    <div className="question">
      <div className="mode-tag">{MODE_LABEL[item.item_type]}</div>
      {item.item_type === 'flashcard' && <Flashcard {...props} />}
      {(item.item_type === 'meaning' || item.item_type === 'cloze') && <SingleChoice {...props} />}
      {item.item_type === 'synonyms' && <PairChoice {...props} />}
      {item.item_type === 'usage' && <Usage {...props} />}
    </div>
  )
}

/** Milliseconds since the item appeared. */
function useElapsed(itemId: string) {
  const shownAt = useRef(performance.now())
  useEffect(() => {
    shownAt.current = performance.now()
  }, [itemId])
  return () => performance.now() - shownAt.current
}

function ConfidenceButtons({ disabled, onPick }: { disabled: boolean; onPick: (c: Confidence) => void }) {
  return (
    <div className="confidence">
      <span className="muted small">How sure are you?</span>
      <div className="row">
        <button className="primary" disabled={disabled} onClick={() => onPick('sure')}>
          Sure
        </button>
        <button disabled={disabled} onClick={() => onPick('unsure')}>
          Unsure
        </button>
        <button disabled={disabled} onClick={() => onPick('guess')}>
          Guess
        </button>
      </div>
    </div>
  )
}

function HintButton({ item, used, onHint }: { item: StudyItem; used: boolean; onHint: () => void }) {
  if (!item.hint_available) return null
  return (
    <button className="link" disabled={used} onClick={onHint}>
      {used ? 'Hint used' : 'Hint'}
    </button>
  )
}

function Flashcard({ item, busy, onSubmit }: Props) {
  const elapsed = useElapsed(item.id)
  const [revealedMs, setRevealedMs] = useState<number | null>(null)
  const back = item.payload.back as WordDetail

  if (revealedMs === null) {
    return (
      <>
        <h2 className="prompt-word">
          {item.payload.word} <SpeakButton text={item.payload.word!} /> <span className="pos">{item.payload.pos}</span>
        </h2>
        <Pronunciation value={item.payload.pronunciation} />
        <p className="muted">Do you know what it means? Think of the meaning, then reveal it.</p>
        <button className="primary" onClick={() => setRevealedMs(elapsed())}>
          Show meaning
        </button>
      </>
    )
  }

  const rate = (r: number) => onSubmit({ self_rating: r }, revealedMs)
  return (
    <>
      <h2 className="prompt-word">
        {back.lemma} <SpeakButton text={back.lemma} /> <span className="pos">{back.pos}</span>
      </h2>
      <Pronunciation value={back.pronunciation} />
      <p className="definition">{back.definition}</p>
      {back.nuance && <p className="nuance">{back.nuance}</p>}
      {back.examples[0] && <p className="example">“{back.examples[0]}”</p>}
      <div className="rating">
        <span className="muted small">How well did you know it?</span>
        <div className="row">
          <button disabled={busy} onClick={() => rate(1)}>Didn't know</button>
          <button disabled={busy} onClick={() => rate(2)}>Hard</button>
          <button disabled={busy} className="primary" onClick={() => rate(3)}>Good</button>
          <button disabled={busy} onClick={() => rate(4)}>Easy</button>
        </div>
      </div>
    </>
  )
}

function SingleChoice({ item, busy, onSubmit }: Props) {
  const elapsed = useElapsed(item.id)
  const [selected, setSelected] = useState<number | null>(null)
  const [selectedMs, setSelectedMs] = useState(0)
  const [eliminated, setEliminated] = useState<number[]>([])
  const [hintUsed, setHintUsed] = useState(false)
  const options = item.payload.options ?? []

  function pick(i: number) {
    setSelected(i)
    setSelectedMs(elapsed())
  }

  async function hint() {
    setHintUsed(true)
    const h = await api.hint(item.id)
    setEliminated(h.eliminate ?? [])
    if (selected !== null && h.eliminate?.includes(selected)) setSelected(null)
  }

  return (
    <>
      <p className="prompt">{item.payload.prompt}</p>
      {item.payload.word && (
        <p className="word-line">
          <SpeakButton text={item.payload.word} /> <Pronunciation value={item.payload.pronunciation} />
        </p>
      )}
      {item.payload.sentence && <p className="sentence">{item.payload.sentence}</p>}
      <div className="options">
        {options.map((opt, i) => (
          <button
            key={i}
            className={`option ${selected === i ? 'selected' : ''}`}
            disabled={eliminated.includes(i) || busy}
            onClick={() => pick(i)}
          >
            <span className="option-key">{String.fromCharCode(65 + i)}</span>
            {opt}
          </button>
        ))}
      </div>
      <div className="row space">
        <HintButton item={item} used={hintUsed} onHint={hint} />
        {selected !== null && (
          <ConfidenceButtons disabled={busy} onPick={(c) => onSubmit({ selected }, selectedMs, c)} />
        )}
      </div>
    </>
  )
}

function PairChoice({ item, busy, onSubmit }: Props) {
  const elapsed = useElapsed(item.id)
  const [selected, setSelected] = useState<number[]>([])
  const [selectedMs, setSelectedMs] = useState(0)
  const [revealed, setRevealed] = useState<number | null>(null)
  const [hintUsed, setHintUsed] = useState(false)
  const options = item.payload.options ?? []

  function toggle(i: number) {
    const next = selected.includes(i) ? selected.filter((x) => x !== i) : [...selected, i].slice(-2)
    setSelected(next)
    if (next.length === 2) setSelectedMs(elapsed())
  }

  async function hint() {
    setHintUsed(true)
    const h = await api.hint(item.id)
    if (h.reveal !== undefined) {
      setRevealed(h.reveal)
      setSelected((s) => (s.includes(h.reveal!) ? s : [h.reveal!, ...s].slice(0, 2)))
    }
  }

  return (
    <>
      <p className="prompt">{item.payload.prompt}</p>
      <div className="options grid">
        {options.map((opt, i) => (
          <button
            key={i}
            className={`option ${selected.includes(i) ? 'selected' : ''} ${revealed === i ? 'revealed' : ''}`}
            disabled={busy}
            onClick={() => toggle(i)}
          >
            {opt}
          </button>
        ))}
      </div>
      <div className="row space">
        <HintButton item={item} used={hintUsed} onHint={hint} />
        {selected.length === 2 && (
          <ConfidenceButtons disabled={busy} onPick={(c) => onSubmit({ selected }, selectedMs, c)} />
        )}
      </div>
    </>
  )
}

function Usage({ item, busy, onSubmit }: Props) {
  const elapsed = useElapsed(item.id)
  const [sentence, setSentence] = useState('')
  return (
    <>
      <h2 className="prompt-word">
        {item.payload.word} <SpeakButton text={item.payload.word!} /> <span className="pos">{item.payload.pos}</span>
      </h2>
      <Pronunciation value={item.payload.pronunciation} />
      <p className="prompt">{item.payload.prompt}</p>
      <textarea
        rows={3}
        value={sentence}
        maxLength={600}
        onChange={(e) => setSentence(e.target.value)}
        placeholder="Your sentence…"
      />
      <div className="row end">
        <button
          className="primary"
          disabled={busy || sentence.trim().split(/\s+/).length < 4}
          onClick={() => onSubmit({ sentence }, elapsed())}
        >
          {busy ? 'Checking…' : 'Check my sentence'}
        </button>
      </div>
    </>
  )
}
