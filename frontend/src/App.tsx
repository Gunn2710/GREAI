import { GraduationCap } from 'lucide-react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Coach, CoachChat } from '@/components/Coach'
import { ErrorAlert } from '@/components/Status'
import { cn } from '@/lib/utils'
import { AccountButton, clerkEnabled } from './lib/auth'
import { useCoach } from './lib/coach'
import { useConfig } from './lib/config'
import Dashboard from './pages/Dashboard'
import Home from './pages/Home'
import Placement from './pages/Placement'
import Practice from './pages/Practice'
import Settings from './pages/Settings'
import Study from './pages/Study'
import WordPage from './pages/WordPage'
import Words from './pages/Words'

const NAV = [
  { to: '/', label: 'Home', end: true },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/study', label: 'Vocab' },
  { to: '/practice', label: 'Practice' },
  { to: '/words', label: 'Words' },
  { to: '/settings', label: 'Settings' },
]

export default function App() {
  const config = useConfig()
  const coach = useCoach()
  // Home is the study coach's chat; other pages have it as a bubble.
  const onHome = useLocation().pathname === '/'
  const chatHome = config.ai_enabled && onHome
  // The two halves must agree on auth, or every request fails with 401.
  const mismatch =
    config.loaded && (config.auth_mode === 'clerk') !== clerkEnabled
      ? clerkEnabled
        ? 'Signed in with Clerk, but the API is in dev mode (GRE_AUTH_MODE=dev): everyone shares data by dev user id.'
        : 'The API requires Clerk sign-in (GRE_AUTH_MODE=clerk), but VITE_CLERK_PUBLISHABLE_KEY is not set in .env.'
      : null

  return (
    // On wide screens the open coach sits beside the page instead of over it.
    <div className={cn('min-h-svh', config.ai_enabled && coach.open && !onHome && 'lg:pr-[416px]')}>
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
      <main className={cn('mx-auto flex max-w-4xl flex-col gap-4 px-4 pt-6', chatHome ? 'pb-0' : 'pb-24')}>
        {mismatch && <ErrorAlert>{mismatch}</ErrorAlert>}
        <Routes>
          {/* Without AI, Home lists the sections instead. */}
          <Route path="/" element={config.ai_enabled ? <CoachChat variant="page" /> : <Home />} />
          <Route path="/dashboard" element={<Dashboard />} />
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
