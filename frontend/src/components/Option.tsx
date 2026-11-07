import { cva } from 'class-variance-authority'
import { CircleCheck, CircleX } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** idle/selected/revealed while answering; correct/wrong when showing the result. */
type OptionState = 'idle' | 'selected' | 'revealed' | 'correct' | 'wrong'

const optionStyles = cva(
  'flex w-full items-center gap-3 rounded-lg border bg-card px-4 py-3 text-left text-sm transition-colors',
  {
    variants: {
      state: {
        idle: '',
        selected: 'border-primary ring-1 ring-primary',
        revealed: 'border-dashed border-primary',
        correct: 'border-success bg-success-soft',
        wrong: 'border-destructive bg-destructive-soft',
      },
    },
    defaultVariants: { state: 'idle' },
  },
)

/** An answer choice the learner can pick. */
export function OptionButton({ state, className, ...props }: ComponentProps<'button'> & { state?: OptionState }) {
  return (
    <button
      type="button"
      className={cn(
        optionStyles({ state }),
        'cursor-pointer hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

/** An answer choice shown after answering, marked right or wrong. */
export function OptionResult({ state, children }: { state?: OptionState; children: ReactNode }) {
  return <div className={optionStyles({ state })}>{children}</div>
}

/** The A/B/C letter in front of an option. */
export function OptionKey({ index }: { index: number }) {
  return (
    <span className="flex size-6 shrink-0 items-center justify-center rounded-md border bg-background text-xs font-semibold text-muted-foreground">
      {String.fromCharCode(65 + index)}
    </span>
  )
}

/** The "Correct" / "Not quite" banner at the top of a result. */
export function Verdict({ ok, children }: { ok: boolean; children: ReactNode }) {
  const Icon = ok ? CircleCheck : CircleX
  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-2 rounded-lg px-4 py-3 text-lg font-semibold',
        ok ? 'bg-success-soft text-success' : 'bg-destructive-soft text-destructive',
      )}
    >
      <Icon className="size-5" />
      {children}
    </div>
  )
}
