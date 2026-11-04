/**
 * Read words aloud with the browser's built-in voice (Web Speech API).
 * Supported by Safari on macOS, iOS and iPadOS, and by Chrome/Edge/Firefox.
 */
const synth: SpeechSynthesis | null =
  typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null

export const speechSupported = synth !== null

/** iPhone/iPad (iPadOS reports itself as a Mac with touch). Their Safari
 *  speech is silenced by the ring/silent switch. */
export const isAppleMobile =
  typeof navigator !== 'undefined' &&
  (/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1))

// Apple's built-in US voices first, then any US English voice, then any English.
const PREFERRED = ['Samantha', 'Ava', 'Allison', 'Alex', 'Google US English']
let voice: SpeechSynthesisVoice | null = null

function pickVoice() {
  const voices = synth?.getVoices() ?? []
  voice =
    PREFERRED.map((name) => voices.find((v) => v.name.startsWith(name) && v.lang.startsWith('en'))).find(Boolean) ??
    voices.find((v) => v.lang === 'en-US') ??
    voices.find((v) => v.lang.startsWith('en')) ??
    null
}

if (synth) {
  pickVoice()
  // Voices load asynchronously in most browsers.
  synth.addEventListener?.('voiceschanged', pickVoice)
}

// Keep a reference while speaking: some engines stop an utterance that gets
// garbage-collected mid-sentence.
let current: SpeechSynthesisUtterance | null = null

export function speak(text: string) {
  if (!synth) return
  if (synth.speaking || synth.pending) synth.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'en-US'
  if (voice) utterance.voice = voice
  utterance.rate = 0.9
  utterance.onend = () => {
    if (current === utterance) current = null
  }
  current = utterance
  synth.speak(utterance)
}
