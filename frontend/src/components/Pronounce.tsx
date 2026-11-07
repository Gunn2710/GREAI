import { Volume2 } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { isAppleMobile, speak, speechSupported } from '../lib/speech'

const HINT_KEY = 'gre.silentSwitchHintShown'

function hintAlreadyShown(): boolean {
  try {
    return localStorage.getItem(HINT_KEY) === '1'
  } catch {
    return false
  }
}

/** A speaker button that says the word aloud. Hidden where speech isn't supported. */
export function SpeakButton({ text }: { text: string }) {
  const [hint, setHint] = useState(false)
  if (!speechSupported) return null

  function onClick() {
    speak(text)
    if (isAppleMobile && !hintAlreadyShown()) {
      setHint(true)
      try {
        localStorage.setItem(HINT_KEY, '1')
      } catch {
        /* storage unavailable: the hint may show again */
      }
    }
  }

  return (
    <span className="inline-flex items-center gap-1.5 align-middle">
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="text-muted-foreground"
        onClick={onClick}
        aria-label={`Hear “${text}”`}
        title="Hear it"
      >
        <Volume2 />
      </Button>
      {hint && <span className="text-xs font-normal text-muted-foreground">No sound? Turn off silent mode.</span>}
    </span>
  )
}

/** Respelling such as "luh-KAH-nik", with the stressed syllable in bold. */
export function Pronunciation({ value, className }: { value: string | null | undefined; className?: string }) {
  if (!value) return null
  return (
    <span className={cn('block text-muted-foreground', className)} aria-label={`Pronounced ${value}`}>
      {value.split(' or ').map((variant, v) => (
        <Fragment key={v}>
          {v > 0 && <span> or </span>}
          {variant.split('-').map((syllable, i) => (
            <Fragment key={i}>
              {i > 0 && '-'}
              {syllable === syllable.toUpperCase() ? (
                <b className="font-semibold text-foreground">{syllable.toLowerCase()}</b>
              ) : (
                syllable
              )}
            </Fragment>
          ))}
        </Fragment>
      ))}
    </span>
  )
}
