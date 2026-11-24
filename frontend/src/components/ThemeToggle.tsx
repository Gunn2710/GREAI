import { Monitor, Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { THEME_LABEL, THEMES, useTheme, type Theme } from '../lib/theme'

const ICON = { light: Sun, dark: Moon, system: Monitor }

/** Header button: each click moves Light → Dark → System. */
export function ThemeToggle() {
  const [theme, setTheme] = useTheme()
  const next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length]
  const Icon = ICON[theme]
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      onClick={() => setTheme(next)}
      title={`Theme: ${THEME_LABEL[theme]} (click for ${THEME_LABEL[next]})`}
      aria-label={`Theme: ${THEME_LABEL[theme]}. Switch to ${THEME_LABEL[next]}`}
    >
      <Icon />
    </Button>
  )
}

/** Light / Dark / System side by side, for the Settings page. */
export function ThemePicker() {
  const [theme, setTheme] = useTheme()
  return (
    <Tabs value={theme} onValueChange={(v) => setTheme(v as Theme)}>
      <TabsList aria-label="Theme">
        {THEMES.map((t) => {
          const Icon = ICON[t]
          return (
            <TabsTrigger key={t} value={t} className="px-3">
              <Icon />
              {THEME_LABEL[t]}
            </TabsTrigger>
          )
        })}
      </TabsList>
    </Tabs>
  )
}
