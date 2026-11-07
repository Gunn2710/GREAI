import { ArrowLeft, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ErrorAlert, LoadingCard } from '@/components/Status'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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

  if (!data) return error ? <ErrorAlert>{error}</ErrorAlert> : <LoadingCard />
  const { word, card } = data

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Button variant="ghost" size="sm" className="-ml-3 text-muted-foreground" asChild>
          <Link to="/words">
            <ArrowLeft />
            All words
          </Link>
        </Button>
      </div>
      <div className="grid items-start gap-4 md:grid-cols-[3fr_2fr]">
        <Card>
          <CardContent className="flex flex-col gap-4">
            <WordCard word={word} />
            {ai_enabled &&
              (mnemonic ? (
                <Alert>
                  <Sparkles />
                  <AlertDescription className="text-foreground">
                    <p>
                      <b className="font-semibold">Mnemonic:</b> {mnemonic}
                    </p>
                  </AlertDescription>
                </Alert>
              ) : (
                <div>
                  <Button variant="outline" onClick={makeMnemonic} disabled={mnemonicBusy}>
                    <Sparkles />
                    {mnemonicBusy ? 'Thinking…' : 'Give me a mnemonic'}
                  </Button>
                </div>
              ))}
            {error && <ErrorAlert>{error}</ErrorAlert>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Your comfort</CardTitle>
          </CardHeader>
          <CardContent>
            {card && card.tier !== 'new' ? (
              <CardStats card={card} />
            ) : (
              <p className="text-sm text-muted-foreground">You haven't studied this word yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
      {ai_enabled ? (
        <Card>
          <CardHeader>
            <CardTitle>Tutor</CardTitle>
            <CardDescription>Ask anything about “{word.lemma}”.</CardDescription>
          </CardHeader>
          <CardContent>
            <TutorChat wordId={word.id} lemma={word.lemma} />
          </CardContent>
        </Card>
      ) : (
        <p className="px-1 text-xs text-muted-foreground">
          The AI tutor is off. Set GRE_AI_ENABLED=true and add Claude credentials on the server.
        </p>
      )}
    </div>
  )
}
