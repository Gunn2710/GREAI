import { NavLink, Route, Routes } from 'react-router-dom'
import { AccountButton, clerkEnabled } from './lib/auth'
import { useConfig } from './lib/config'
import Dashboard from './pages/Dashboard'
import Placement from './pages/Placement'
import Practice from './pages/Practice'
import Settings from './pages/Settings'
import Study from './pages/Study'
import WordPage from './pages/WordPage'
import Words from './pages/Words'

export default function App() {
  const config = useConfig()
  // The two halves must agree on auth, or every request fails with 401.
  const mismatch =
    config.loaded && (config.auth_mode === 'clerk') !== clerkEnabled
      ? clerkEnabled
        ? 'Signed in with Clerk, but the API is in dev mode (GRE_AUTH_MODE=dev): everyone shares data by dev user id.'
        : 'The API requires Clerk sign-in (GRE_AUTH_MODE=clerk), but VITE_CLERK_PUBLISHABLE_KEY is not set in frontend/.env.'
      : null

  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/" className="brand">
          GRE Prep
        </NavLink>
        <nav>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/study">Vocab</NavLink>
          <NavLink to="/practice">Practice</NavLink>
          <NavLink to="/words">Words</NavLink>
          <NavLink to="/settings">Settings</NavLink>
          <AccountButton />
        </nav>
      </header>
      {mismatch && <div className="panel error small">{mismatch}</div>}
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/study" element={<Study />} />
          <Route path="/placement" element={<Placement />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/words" element={<Words />} />
          <Route path="/words/:id" element={<WordPage />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
