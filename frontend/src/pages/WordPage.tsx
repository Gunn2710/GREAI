import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CardStats } from '../components/Comfort'
import { TutorChat } from '../components/TutorChat'
import { WordCard } from '../components/WordCard'
import { api, ApiError } from '../lib/api'
import { useConfig } from '../lib/config'
import type { CardSummary, WordDetail } from '../lib/types'

export default function WordPage() {
  const id = Number(useParams().id)
  const { ai_enabled } = useConfig()
  const [data, setData] = useState<{ word: WordDetail; card: CardSummary | null } | null>(null)
  const [mnemonic, setMnemonic] = useState<string | null>(null)
  const [mnemonicBusy, setMnemonicBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setData(null)
    setMnemonic(null)
    api.word(id).then(setData).catch(() => setError('Word not found'))
  }, [id])

  async function makeMnemonic() {
    setMnemonicBusy(true)
    setError(null)
    try {
      setMnemonic((await api.mnemonic(id)).mnemonic)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not create a mnemonic')
    } finally {
      setMnemonicBusy(false)
    }
  }

  if (!data) return <div className="panel muted">{error ?? 'Loading…'}</div>
  const { word, card } = data

  return (
    <div className="word-page">
      <Link to="/words" className="small">
        ← All words
      </Link>
      <div className="two-col">
        <div className="panel">
          <WordCard word={word} />
          {ai_enabled && (
            <div className="mnemonic">
              {mnemonic ? (
                <p>
                  <b>Mnemonic:</b> {mnemonic}
                </p>
              ) : (
                <button onClick={makeMnemonic} disabled={mnemonicBusy}>
                  {mnemonicBusy ? 'Thinking…' : 'Give me a mnemonic'}
                </button>
              )}
            </div>
          )}
          {error && <p className="error">{error}</p>}
        </div>
        <div className="panel">
          <h3>Your comfort</h3>
          {card && card.tier !== 'new' ? <CardStats card={card} /> : <p className="muted">You haven't studied this word yet.</p>}
        </div>
      </div>
      {ai_enabled ? (
        <div className="panel">
          <TutorChat wordId={word.id} lemma={word.lemma} />
        </div>
      ) : (
        <p className="muted small">The AI tutor is off. Set GRE_AI_ENABLED=true and add Claude credentials on the server.</p>
      )}
    </div>
  )
}
