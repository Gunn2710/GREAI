/**
 * Loading states: the screen shown while the app starts (signing in, first
 * request to the server) and a thin progress bar at the top of the window
 * while any request takes longer than a moment.
 */
import { GraduationCap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { onRequests } from '../lib/api'

/** Shown while the app starts. After a few seconds it explains the wait: the
 * server may be starting up (a cold start after a quiet spell). */
export function AppLoading() {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 3000)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div role="status" className="flex min-h-svh flex-col items-center justify-center gap-4 px-4 text-center">
      <div className="relative flex size-14 items-center justify-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-primary/25 motion-reduce:animate-none" />
        <span className="relative flex size-14 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <GraduationCap className="size-7" />
        </span>
      </div>
      <p className="font-medium">Loading your study plan…</p>
      <p
        className={cn(
          'max-w-xs text-sm text-muted-foreground transition-opacity duration-500',
          slow ? 'opacity-100' : 'opacity-0',
        )}
        aria-hidden={!slow}
      >
        Waking up the server. The first visit in a while can take a few seconds.
      </p>
    </div>
  )
}

/** A thin bar across the top of the window while a request is taking a moment. */
export function TopLoader() {
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    const unsubscribe = onRequests((count) => {
      clearTimeout(timer)
      // Quick requests don't flash the bar; it shows once one takes over 250 ms.
      if (count > 0) timer = setTimeout(() => setBusy(true), 250)
      else setBusy(false)
    })
    return () => {
      clearTimeout(timer)
      unsubscribe()
    }
  }, [])

  if (!busy) return null
  return (
    <div
      role="progressbar"
      aria-label="Loading"
      className="pointer-events-none fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden bg-primary/15"
    >
      <div className="h-full w-1/3 animate-loading-bar rounded-full bg-primary motion-reduce:w-full motion-reduce:animate-none motion-reduce:opacity-60" />
    </div>
  )
}
