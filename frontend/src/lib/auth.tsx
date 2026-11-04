import { SignIn, UserButton, useAuth } from '@clerk/react'
import type { ReactNode } from 'react'
import { setTokenProvider } from './api'

/** Clerk is on when a publishable key is configured (frontend/.env). */
export const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined
export const clerkEnabled = Boolean(CLERK_PUBLISHABLE_KEY)

/** Shows Clerk's sign-in until there is a session, then sends every API
 *  request with the session token. Must render inside <ClerkProvider>. */
export function AuthGate({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useAuth()

  if (!isLoaded) {
    return (
      <div className="app">
        <div className="panel muted">Loading…</div>
      </div>
    )
  }
  if (!isSignedIn) {
    return (
      <div className="auth-screen">
        <h1>GRE Prep</h1>
        <p className="muted">Sign in to keep your progress across devices.</p>
        <SignIn routing="hash" />
      </div>
    )
  }

  // Set during render, not in an effect: children's effects (their first API
  // calls) run before this component's effects would.
  setTokenProvider(() => getToken())
  return <>{children}</>
}

/** Clerk's account menu (profile, sign out), or nothing in dev mode. */
export function AccountButton() {
  return clerkEnabled ? <UserButton /> : null
}
