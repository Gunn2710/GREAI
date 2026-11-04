import { Fragment, useState } from 'react'
import { isAppleMobile, speak, speechSupported } from '../lib/speech'

const HINT_KEY = 'gre.silentSwitchHintShown'

function hintAlreadyShown(): boolean {
  try {
    return localStorage.getItem(HINT_KEY) === '1'
  } catch {
    return false
  }
}

/** A 🔊 button that says the word aloud. Hidden where speech isn't supported. */
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
    <span className="speak">
      <button type="button" className="speak-button" onClick={onClick} aria-label={`Hear “${text}”`} title="Hear it">
        🔊
      </button>
      {hint && <span className="speak-hint">No sound? Turn off silent mode.</span>}
    </span>
  )
}

/** Respelling such as "luh-KAH-nik", with the stressed syllable in bold. */
export function Pronunciation({ value }: { value: string | null | undefined }) {
  if (!value) return null
  return (
    <span className="pronunciation" aria-label={`Pronounced ${value}`}>
      {value.split(' or ').map((variant, v) => (
        <Fragment key={v}>
          {v > 0 && <span className="muted"> or </span>}
          {variant.split('-').map((syllable, i) => (
            <Fragment key={i}>
              {i > 0 && '-'}
              {syllable === syllable.toUpperCase() ? <b>{syllable.toLowerCase()}</b> : syllable}
            </Fragment>
          ))}
        </Fragment>
      ))}
    </span>
  )
}
