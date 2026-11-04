import { Link } from 'react-router-dom'
import { FrequencyBadge } from './Comfort'
import { Pronunciation, SpeakButton } from './Pronounce'
import { useConfig } from '../lib/config'
import type { WordDetail } from '../lib/types'

export function WordCard({ word, linkToDetail = false }: { word: WordDetail; linkToDetail?: boolean }) {
  const { ai_enabled } = useConfig()
  return (
    <div className="word-card">
      <div className="row space">
        <h3>
          {word.lemma} <SpeakButton text={word.lemma} /> <span className="pos">{word.pos}</span>{' '}
          <FrequencyBadge tier={word.tier} />
        </h3>
        {linkToDetail && (
          <Link to={`/words/${word.id}`} className="small">
            {ai_enabled ? 'Ask the tutor →' : 'Word details →'}
          </Link>
        )}
      </div>
      <Pronunciation value={word.pronunciation} />
      <p className="definition">{word.definition}</p>
      {word.nuance && <p className="nuance">{word.nuance}</p>}
      <ul className="examples">
        {word.examples.map((ex) => (
          <li key={ex}>{ex}</li>
        ))}
      </ul>
      <dl className="relations">
        {word.synonyms.length > 0 && (
          <>
            <dt>Synonyms</dt>
            <dd>{word.synonyms.join(', ')}</dd>
          </>
        )}
        {word.antonyms.length > 0 && (
          <>
            <dt>Antonyms</dt>
            <dd>{word.antonyms.join(', ')}</dd>
          </>
        )}
        {word.confusables.length > 0 && (
          <>
            <dt>Don't confuse with</dt>
            <dd>{word.confusables.join(', ')}</dd>
          </>
        )}
      </dl>
    </div>
  )
}
