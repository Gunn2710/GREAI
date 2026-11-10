import { ArrowRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { FrequencyBadge } from './Comfort'
import { Pronunciation, SpeakButton } from './Pronounce'
import type { WordDetail } from '../lib/types'

/** The word in large type with its speaker button and part of speech. */
export function WordTitle({
  word,
  pos,
  large = false,
  children,
}: {
  word: string
  pos?: string | null
  large?: boolean
  children?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <h2 className={cn('font-semibold tracking-tight', large ? 'text-3xl' : 'text-2xl')}>{word}</h2>
      <SpeakButton text={word} />
      {pos && <span className="text-sm text-muted-foreground italic">{pos}</span>}
      {children}
    </div>
  )
}

/** The most common ways the word is used, as chips. */
export function Phrases({ phrases }: { phrases: string[] }) {
  if (phrases.length === 0) return null
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Common phrases</span>
      <ul className="flex flex-wrap gap-1.5">
        {phrases.map((p) => (
          <li key={p}>
            <Badge variant="outline" className="px-2.5 py-1 text-sm font-normal">
              {p}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Synonyms, antonyms and easily confused words. */
export function Relations({ word }: { word: Pick<WordDetail, 'synonyms' | 'antonyms' | 'confusables'> }) {
  const rows: [string, string[]][] = [
    ['Synonyms', word.synonyms],
    ['Antonyms', word.antonyms],
    ["Don't confuse with", word.confusables],
  ]
  if (rows.every(([, words]) => words.length === 0)) return null
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-sm">
      {rows.map(
        ([label, words]) =>
          words.length > 0 && (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">{label}</dt>
              <dd>{words.join(', ')}</dd>
            </div>
          ),
      )}
    </dl>
  )
}

export function WordCard({ word, linkToDetail = false }: { word: WordDetail; linkToDetail?: boolean }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <WordTitle word={word.lemma} pos={word.pos}>
            <FrequencyBadge tier={word.tier} />
            {word.set != null && (
              <Badge variant="outline" asChild>
                <Link to={`/words?set=${word.set}`}>Set {word.set}</Link>
              </Badge>
            )}
          </WordTitle>
          <Pronunciation value={word.pronunciation} />
        </div>
        {linkToDetail && (
          <Button variant="ghost" size="sm" asChild>
            <Link to={`/words/${word.id}`}>
              Word details
              <ArrowRight />
            </Link>
          </Button>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <p className="text-base">{word.definition}</p>
        {word.nuance && <p className="text-sm text-muted-foreground italic">{word.nuance}</p>}
      </div>
      <Phrases phrases={word.phrases} />
      <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-muted-foreground">
        {word.examples.map((ex) => (
          <li key={ex}>{ex}</li>
        ))}
      </ul>
      <Relations word={word} />
    </div>
  )
}
