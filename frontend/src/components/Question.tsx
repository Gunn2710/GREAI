import { Lightbulb } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api } from '../lib/api'
import { OptionButton, OptionKey } from './Option'
import { SentenceNote } from './YourSentence'
import { Pronunciation, SpeakButton } from './Pronounce'
import { Phrases, Relations, WordTitle } from './WordCard'
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
    <div className="flex flex-col gap-4">
      <ModeTag>{MODE_LABEL[item.item_type]}</ModeTag>
      {item.item_type === 'flashcard' && <Flashcard {...props} />}
      {(item.item_type === 'meaning' || item.item_type === 'cloze') && <SingleChoice {...props} />}
      {item.item_type === 'synonyms' && <PairChoice {...props} />}
      {item.item_type === 'usage' && <Usage {...props} />}
    </div>
  )
}

export function ModeTag({ children }: { children: ReactNode }) {
  return <div className="text-xs font-medium tracking-wider text-muted-foreground uppercase">{children}</div>
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
    <div className="ml-auto flex flex-col items-end gap-2">
      <span className="text-xs text-muted-foreground">How sure are you?</span>
      <div className="flex gap-2">
        <Button disabled={disabled} onClick={() => onPick('sure')}>
          Sure
        </Button>
        <Button variant="outline" disabled={disabled} onClick={() => onPick('unsure')}>
          Unsure
        </Button>
        <Button variant="outline" disabled={disabled} onClick={() => onPick('guess')}>
          Guess
        </Button>
      </div>
    </div>
  )
}

export function HintButton({ used, disabled, onHint }: { used: boolean; disabled?: boolean; onHint: () => void }) {
  return (
    <Button variant="ghost" size="sm" className="text-muted-foreground" disabled={used || disabled} onClick={onHint}>
      <Lightbulb />
      {used ? 'Hint used' : 'Hint'}
    </Button>
  )
}

function Flashcard({ item, busy, onSubmit }: Props) {
  const elapsed = useElapsed(item.id)
  const [revealedMs, setRevealedMs] = useState<number | null>(null)
  const back = item.payload.back as WordDetail

  if (revealedMs === null) {
    return (
      <>
        <div className="flex flex-col gap-1">
          <WordTitle word={item.payload.word!} pos={item.payload.pos} large />
          <Pronunciation value={item.payload.pronunciation} />
        </div>
        <p className="text-sm text-muted-foreground">Do you know what it means? Think of the meaning, then reveal it.</p>
        <div>
          <Button size="lg" onClick={() => setRevealedMs(elapsed())}>
            Show meaning
          </Button>
        </div>
      </>
    )
  }

  const rate = (r: number) => onSubmit({ self_rating: r }, revealedMs)
  return (
    <>
      <div className="flex flex-col gap-1">
        <WordTitle word={back.lemma} pos={back.pos} large />
        <Pronunciation value={back.pronunciation} />
      </div>
      <div className="flex flex-col gap-1">
        <p className="text-base">{back.definition}</p>
        {back.nuance && <p className="text-sm text-muted-foreground italic">{back.nuance}</p>}
      </div>
      {/* `?? []`: flashcards issued before phrases existed don't carry them. */}
      <Phrases phrases={back.phrases ?? []} />
      {back.examples[0] && <p className="text-sm text-muted-foreground">“{back.examples[0]}”</p>}
      <Relations word={back} />
      {item.payload.my_sentence && <SentenceNote sentence={item.payload.my_sentence} />}
      <div className="mt-2 flex flex-col gap-2 border-t pt-4">
        <span className="text-xs text-muted-foreground">How well did you know it?</span>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Button variant="outline" disabled={busy} onClick={() => rate(1)}>
            Didn't know
          </Button>
          <Button variant="outline" disabled={busy} onClick={() => rate(2)}>
            Hard
          </Button>
          <Button disabled={busy} onClick={() => rate(3)}>
            Good
          </Button>
          <Button variant="outline" disabled={busy} onClick={() => rate(4)}>
            Easy
          </Button>
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
      <p className="font-medium">{item.payload.prompt}</p>
      {item.payload.word && (
        <div className="flex items-center gap-1">
          <SpeakButton text={item.payload.word} /> <Pronunciation value={item.payload.pronunciation} className="inline" />
        </div>
      )}
      {item.payload.sentence && <p className="rounded-lg bg-muted px-4 py-3 text-lg">{item.payload.sentence}</p>}
      <div className="flex flex-col gap-2">
        {options.map((opt, i) => (
          <OptionButton
            key={i}
            state={selected === i ? 'selected' : 'idle'}
            disabled={eliminated.includes(i) || busy}
            onClick={() => pick(i)}
          >
            <OptionKey index={i} />
            {opt}
          </OptionButton>
        ))}
      </div>
      <div className="flex flex-wrap items-end justify-between gap-2">
        {item.hint_available ? <HintButton used={hintUsed} onHint={hint} /> : <span />}
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
      <p className="font-medium">{item.payload.prompt}</p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {options.map((opt, i) => (
          <OptionButton
            key={i}
            state={selected.includes(i) ? 'selected' : revealed === i ? 'revealed' : 'idle'}
            disabled={busy}
            onClick={() => toggle(i)}
            aria-pressed={selected.includes(i)}
          >
            {opt}
          </OptionButton>
        ))}
      </div>
      <div className="flex flex-wrap items-end justify-between gap-2">
        {item.hint_available ? <HintButton used={hintUsed} onHint={hint} /> : <span />}
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
      <div className="flex flex-col gap-1">
        <WordTitle word={item.payload.word!} pos={item.payload.pos} large />
        <Pronunciation value={item.payload.pronunciation} />
      </div>
      <p className="font-medium">{item.payload.prompt}</p>
      <Textarea
        rows={3}
        value={sentence}
        maxLength={600}
        onChange={(e) => setSentence(e.target.value)}
        placeholder="Your sentence…"
      />
      <div className="flex justify-end">
        <Button
          disabled={busy || sentence.trim().split(/\s+/).length < 4}
          onClick={() => onSubmit({ sentence }, elapsed())}
        >
          {busy ? 'Checking…' : 'Check my sentence'}
        </Button>
      </div>
    </>
  )
}
