/**
 * Light, dark, or follow the system. The choice is remembered per browser and
 * applied as the .dark class on <html> (index.html applies it before the first
 * paint, so there's no flash of the wrong theme).
 */
import { useCallback, useEffect, useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dark' | 'system'

export const THEMES: Theme[] = ['light', 'dark', 'system']
export const THEME_LABEL: Record<Theme, string> = { light: 'Light', dark: 'Dark', system: 'System' }

const KEY = 'theme'
const EVENT = 'theme-changed'
const DARK = '(prefers-color-scheme: dark)'

function saved(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

function apply(theme: Theme) {
  const dark = theme === 'dark' || (theme === 'system' && window.matchMedia(DARK).matches)
  document.documentElement.classList.toggle('dark', dark)
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange)
  window.addEventListener('storage', onChange)
  return () => {
    window.removeEventListener(EVENT, onChange)
    window.removeEventListener('storage', onChange)
  }
}

/** The current choice and a setter; every component using it stays in sync. */
export function useTheme(): [Theme, (theme: Theme) => void] {
  const theme = useSyncExternalStore(subscribe, saved)
  const setTheme = useCallback((next: Theme) => {
    try {
      if (next === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, next)
    } catch {
      // storage blocked: the choice lasts until the page reloads
    }
    apply(next)
    window.dispatchEvent(new Event(EVENT))
  }, [])
  return [theme, setTheme]
}

/** Keeps <html> in step with the choice, and with the system while on System. Mount once. */
export function useApplyTheme() {
  const [theme] = useTheme()
  useEffect(() => {
    apply(theme)
    if (theme !== 'system') return
    const media = window.matchMedia(DARK)
    const onChange = () => apply('system')
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [theme])
}
