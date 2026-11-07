import { CircleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/** Placeholder card while a page loads. */
export function LoadingCard() {
  return (
    <Card aria-busy="true" aria-label="Loading">
      <CardContent className="flex flex-col gap-3">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
      </CardContent>
    </Card>
  )
}

export function ErrorAlert({ children }: { children: ReactNode }) {
  return (
    <Alert variant="destructive">
      <CircleAlert />
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  )
}
