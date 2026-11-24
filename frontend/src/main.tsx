import { ClerkProvider } from '@clerk/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthGate } from './lib/auth'
import { CLERK_PUBLISHABLE_KEY } from './lib/clerk'
import { CoachProvider } from './lib/CoachProvider'
import { ConfigProvider } from './lib/ConfigProvider'
import './index.css'

const app = (
  <BrowserRouter>
    <ConfigProvider>
      <CoachProvider>
        <App />
      </CoachProvider>
    </ConfigProvider>
  </BrowserRouter>
)

// With VITE_CLERK_PUBLISHABLE_KEY set, users sign in with Clerk and the API
// receives their session token; without it the app runs in dev mode.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {CLERK_PUBLISHABLE_KEY ? (
      <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY}>
        <AuthGate>{app}</AuthGate>
      </ClerkProvider>
    ) : (
      app
    )}
  </StrictMode>,
)
