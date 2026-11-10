/**
 * Reading Comprehension and Quant practice questions: the stem (passage,
 * quantities, text and tables), the answer controls, and the answered view.
 * Text Completion and Sentence Equivalence live in pages/Practice.tsx.
 */
import { Square, SquareCheck } from 'lucide-react'
import { useState } from 'react'
import { OptionButton, OptionKey, OptionResult } from '@/components/Option'
import { ModeTag } from '@/components/Question'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type { DataTable, PracticeItem, PracticeResponse, PracticeResult } from '../lib/types'

const TOPIC_LABEL: Record<string, string> = {
  arithmetic: 'Arithmetic',
  algebra: 'Algebra',
  geometry: 'Geometry',
  data: 'Data analysis',
}

/** The small caps line above a question, e.g. "Reading Comprehension · Ecology · medium". */
export function FormatTag({ item }: { item: PracticeItem }) {
  const p = item.payload
  const topic = item.item_type === 'rc' ? p.topic : TOPIC_LABEL[p.topic ?? '']
  return <ModeTag>{[item.kind_name, topic, p.difficulty].filter(Boolean).join(' · ')}</ModeTag>
}

/** Everything above the answer choices. */
export function Stem({ item }: { item: PracticeItem }) {
  const p = item.payload
  if (item.item_type === 'rc') {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 rounded-lg border bg-muted/40 p-4 text-[0.95rem] leading-7">
          {p.passage!.split(/\n\n+/).map((para, i) => (
            <p key={i}>{para}</p>
          ))}
        </div>
        <div className="flex flex-col gap-1">
          {p.of! > 1 && (
            <span className="text-xs text-muted-foreground">
              Question {p.order} of {p.of} on this passage
            </span>
          )}
          <p className="text-lg leading-8 font-medium">{p.question}</p>
        </div>
      </div>
    )
  }
  if (item.item_type === 'qc') {
    return (
      <div className="flex flex-col gap-3">
        {p.info && <p className="text-center text-lg leading-8">{p.info}</p>}
        {p.table && <DataTableView table={p.table} />}
        <div className="grid grid-cols-2 gap-3">
          {(['Quantity A', 'Quantity B'] as const).map((label, i) => (
            <div key={label} className="flex flex-col items-center gap-2 rounded-lg border p-4 text-center">
              <span className="text-xs font-medium text-muted-foreground">{label}</span>
              <span className="text-lg leading-7">{i === 0 ? p.quantity_a : p.quantity_b}</span>
            </div>
          ))}
        </div>
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-lg leading-8">{p.text}</p>
      {p.table && <DataTableView table={p.table} />}
    </div>
  )
}

function DataTableView({ table }: { table: DataTable }) {
  return (
    <div className="mx-auto w-full max-w-md rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            {table.columns.map((c) => (
              <TableHead key={c} className="text-center">
                {c}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {table.rows.map((row, r) => (
            <TableRow key={r}>
              {row.map((cell, c) => (
                <TableCell key={c} className="text-center tabular-nums">
                  {cell}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function instructions(item: PracticeItem): string {
  const p = item.payload
  switch (item.item_type) {
    case 'qc':
      return 'Compare Quantity A and Quantity B, using any information given.'
    case 'qne':
      return p.fraction
        ? 'Enter your answer as a fraction, like 3/4. It does not need to be reduced.'
        : 'Enter your answer as a number. Fractions like 3/4 also work.'
    default:
      return p.select === 'all'
        ? 'Consider each choice separately and select all that apply.'
        : 'Select one answer choice.'
  }
}

/** Answer controls; reports the current response, or null while it is incomplete. */
export function Answer({
  item,
  disabled,
  onChange,
  onSubmit,
}: {
  item: PracticeItem
  disabled: boolean
  onChange: (response: PracticeResponse | null) => void
  onSubmit: () => void
}) {
  const [selected, setSelected] = useState<number[]>([])
  const [value, setValue] = useState('')
  const multi = item.payload.select === 'all'

  function toggle(o: number) {
    const next = multi ? (selected.includes(o) ? selected.filter((x) => x !== o) : [...selected, o]) : [o]
    setSelected(next)
    onChange(next.length ? { selected: next } : null)
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">{instructions(item)}</p>
      {item.item_type === 'qne' ? (
        <div className="flex items-center gap-2">
          <Input
            aria-label="Your answer"
            className="w-40 text-center text-lg tabular-nums"
            inputMode={item.payload.fraction ? 'text' : 'decimal'}
            placeholder={item.payload.fraction ? 'a/b' : ''}
            autoComplete="off"
            autoFocus
            value={value}
            disabled={disabled}
            onChange={(e) => {
              setValue(e.target.value)
              onChange(e.target.value.trim() ? { value: e.target.value.trim() } : null)
            }}
            onKeyDown={(e) => e.key === 'Enter' && value.trim() && onSubmit()}
          />
          {item.payload.unit && <span className="text-muted-foreground">{item.payload.unit}</span>}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {item.payload.options!.map((opt, o) => {
            const on = selected.includes(o)
            const Box = on ? SquareCheck : Square
            return (
              <OptionButton
                key={o}
                state={on ? 'selected' : 'idle'}
                disabled={disabled}
                onClick={() => toggle(o)}
                aria-pressed={on}
              >
                {multi ? (
                  <Box className={cn('size-4 shrink-0', on ? 'text-primary' : 'text-muted-foreground')} />
                ) : (
                  <OptionKey index={o} />
                )}
                {opt}
              </OptionButton>
            )
          })}
        </div>
      )}
    </div>
  )
}

/** The answer choices (or typed value) marked right and wrong after answering. */
export function AnswerReview({
  item,
  result,
  response,
}: {
  item: PracticeItem
  result: PracticeResult
  response: PracticeResponse
}) {
  if (item.item_type === 'qne') {
    const unit = item.payload.unit ? ` ${item.payload.unit}` : ''
    return (
      <div className="flex flex-col gap-2 sm:flex-row">
        <OptionResult state={result.correct ? 'correct' : 'wrong'}>
          Your answer: <b className="font-semibold tabular-nums">{response.value}</b>
          {unit}
        </OptionResult>
        {!result.correct && (
          <OptionResult state="correct">
            Correct answer: <b className="font-semibold tabular-nums">{result.feedback.correct_answer}</b>
            {unit}
          </OptionResult>
        )}
      </div>
    )
  }
  const correct = result.feedback.correct_indices ?? []
  const chosen = response.selected ?? []
  const multi = item.payload.select === 'all'
  return (
    <div className="flex flex-col gap-2">
      {item.payload.options!.map((opt, o) => (
        <OptionResult key={o} state={correct.includes(o) ? 'correct' : chosen.includes(o) ? 'wrong' : 'idle'}>
          {multi ? (
            chosen.includes(o) ? (
              <SquareCheck className="size-4 shrink-0" />
            ) : (
              <Square className="size-4 shrink-0 text-muted-foreground" />
            )
          ) : (
            <OptionKey index={o} />
          )}
          {opt}
        </OptionResult>
      ))}
    </div>
  )
}
