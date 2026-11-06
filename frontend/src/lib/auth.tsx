import { SignIn, SignOutButton, UserButton, useAuth, useUser } from '@clerk/react'
import { useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, setTokenProvider } from './api'

/** Clerk is on when a publishable key is configured (frontend/.env). */
export const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined
export const clerkEnabled = Boolean(CLERK_PUBLISHABLE_KEY)

type Access = 'checking' | 'approved' | 'denied'

/** Shows Clerk's sign-in until there is a session, checks with the API that
 *  the account is approved, then sends every API request with the session
 *  token. Must render inside <ClerkProvider>. */
export function AuthGate({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, userId, getToken } = useAuth()
  const [access, setAccess] = useState<{ userId: string | null; state: Access }>({ userId: null, state: 'checking' })

  if (isSignedIn) {
    // Set during render, not in an effect: children's effects (their first API
    // calls) run before this component's effects would.
    setTokenProvider(() => getToken())
  }

  useEffect(() => {
    if (!isSignedIn || !userId) return
    let cancelled = false
    api
      .me()
      .then(() => !cancelled && setAccess({ userId, state: 'approved' }))
      .catch((e) => {
        if (cancelled) return
        // Only "not approved" blocks the app; other errors surface on the pages.
        const denied = e instanceof ApiError && e.status === 403
        setAccess({ userId, state: denied ? 'denied' : 'approved' })
      })
    return () => {
      cancelled = true
    }
  }, [isSignedIn, userId])

  if (!isLoaded || (isSignedIn && (access.userId !== userId || access.state === 'checking'))) {
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
  if (access.state === 'denied') return <NotApproved />
  return <>{children}</>
}

function NotApproved() {
  const { user } = useUser()
  return (
    <div className="auth-screen">
      <h1>GRE Prep</h1>
      <div className="panel center not-approved">
        <h2>Access not approved</h2>
        <p className="muted">
          {user?.primaryEmailAddress?.emailAddress ?? 'This account'} isn't on the approved list for this app. Sign
          in with an approved account, or ask the owner for access.
        </p>
        <SignOutButton>
          <button className="primary">Sign out</button>
        </SignOutButton>
      </div>
    </div>
  )
}

/** Clerk's account menu (profile, sign out), or nothing in dev mode. */
export function AccountButton() {
  return clerkEnabled ? <UserButton /> : null
}
