import { GraduationCap } from 'lucide-react'
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Coach, CoachChat } from '@/components/Coach'
import { ErrorAlert } from '@/components/Status'
import { cn } from '@/lib/utils'
import { AccountButton, clerkEnabled } from './lib/auth'
import { useCoach } from './lib/coach'
import { useConfig } from './lib/config'
import { COACH_FREE } from './lib/routes'
import Dashboard from './pages/Dashboard'
import Placement from './pages/Placement'
import Practice from './pages/Practice'
import Settings from './pages/Settings'
import Study from './pages/Study'
import WordPage from './pages/WordPage'
import Words from './pages/Words'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/study', label: 'Vocab' },
  { to: '/practice', label: 'Practice' },
  { to: '/words', label: 'Words' },
  { to: '/settings', label: 'Settings' },
]

export default function App() {
  const config = useConfig()
  const coach = useCoach()
  // The study coach is a side chat (or its bubble) on every page, and can go full screen at /chat.
  const { pathname } = useLocation()
  const onChat = config.ai_enabled && pathname === '/chat'
  // The two halves must agree on auth, or every request fails with 401.
  const mismatch =
    config.loaded && (config.auth_mode === 'clerk') !== clerkEnabled
      ? clerkEnabled
        ? 'Signed in with Clerk, but the API is in dev mode (GRE_AUTH_MODE=dev): everyone shares data by dev user id.'
        : 'The API requires Clerk sign-in (GRE_AUTH_MODE=clerk), but VITE_CLERK_PUBLISHABLE_KEY is not set in .env.'
      : null

  return (
    // On wide screens the open coach sits beside the page instead of over it.
    <div
      className={cn('min-h-svh', config.ai_enabled && coach.open && !COACH_FREE.includes(pathname) && 'lg:pr-[416px]')}
    >
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        {/* Phones: brand and account on one row, the nav scrolls on the row below. */}
        <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-4 px-4 sm:h-14">
          <NavLink to="/" className="flex h-12 items-center gap-2 font-semibold tracking-tight sm:h-auto">
            <GraduationCap className="size-5" />
            GRE Prep
          </NavLink>
          <nav className="order-last -mx-4 flex w-[calc(100%+2rem)] gap-1 overflow-x-auto px-3 pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:order-none sm:mx-0 sm:w-auto sm:flex-1 sm:p-0">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground',
                    isActive && 'bg-accent text-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center">
            <AccountButton />
          </div>
        </div>
      </header>
      <main className={cn('mx-auto flex max-w-4xl flex-col gap-4 px-4 pt-6', onChat ? 'pb-0' : 'pb-24')}>
        {mismatch && <ErrorAlert>{mismatch}</ErrorAlert>}
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Navigate to="/" replace />} />
          {/* The study coach full screen (from the side chat's full-screen button). */}
          <Route
            path="/chat"
            element={config.ai_enabled ? <CoachChat variant="page" /> : config.loaded && <Navigate to="/" replace />}
          />
          <Route path="/study" element={<Study />} />
          <Route path="/placement" element={<Placement />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/words" element={<Words />} />
          <Route path="/words/:id" element={<WordPage />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
      <Coach />
    </div>
  )
}
