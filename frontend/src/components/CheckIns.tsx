import { cn } from '@/lib/utils'
import type { Stats } from '../lib/types'

/** About four months, ending with this week. */
const WEEKS = 18
const DAY = 86_400_000
const CELL = '16px'
/** Fewest words for each shade; the first shade is "didn't study". */
const LEVELS = [0, 1, 10, 25, 50]
const SHADES = [
  'bg-muted',
  'bg-violet-200 dark:bg-violet-950',
  'bg-violet-400 dark:bg-violet-800',
  'bg-violet-600 dark:bg-violet-600',
  'bg-violet-800 dark:bg-violet-400',
]

function level(words: number) {
  let i = 0
  while (i + 1 < LEVELS.length && words >= LEVELS[i + 1]) i++
  return i
}

/** Dates are UTC days (the server's, like the streak), so the maths stays in UTC. */
function parse(date: string) {
  return Date.parse(date + 'T00:00:00Z')
}

function label(ms: number, options: Intl.DateTimeFormatOptions) {
  return new Date(ms).toLocaleDateString(undefined, { timeZone: 'UTC', ...options })
}

/** GitHub-style check-ins for the last four months: one square per day, deeper purple the more words studied. */
export function CheckIns({ activity }: { activity: Stats['activity'] }) {
  const words = new Map(activity.days.map((d) => [d.date, d.words]))
  const today = parse(activity.today)
  // Columns are weeks starting on Sunday; the last one holds today.
  const start = today - new Date(today).getUTCDay() * DAY - (WEEKS - 1) * 7 * DAY
  const weeks = Array.from({ length: WEEKS }, (_, w) => Array.from({ length: 7 }, (_, d) => start + (w * 7 + d) * DAY))

  // A month's name sits over its first full week, unless it would crowd the one before.
  const months: { week: number; name: string }[] = []
  weeks.forEach((days, w) => {
    const month = new Date(days[0]).getUTCMonth()
    if (w > 0 && month === new Date(weeks[w - 1][0]).getUTCMonth()) return
    if (months.length && w - months[months.length - 1].week < 3) months.pop()
    months.push({ week: w, name: label(days[0], { month: 'short' }) })
  })

  const studied = activity.days.filter((d) => parse(d.date) >= start).length
  const summary = `Studied on ${studied} ${studied === 1 ? 'day' : 'days'} in the last 4 months`

  return (
    <div className="flex w-fit max-w-full flex-col gap-3">
      {/* Small squares like GitHub's; they shrink further to fit a phone. */}
      <div
        className="grid gap-[3px] text-[10px] leading-none text-muted-foreground"
        style={{ gridTemplateColumns: `auto repeat(${WEEKS}, minmax(0, ${CELL}))` }}
        role="img"
        aria-label={summary}
      >
        {months.map((m) => (
          <span key={m.week} className="pb-0.5 whitespace-nowrap" style={{ gridRow: 1, gridColumn: m.week + 2 }}>
            {m.name}
          </span>
        ))}
        {['Mon', 'Wed', 'Fri'].map((name, i) => (
          <span key={name} className="flex items-center pr-1" style={{ gridRow: i * 2 + 3, gridColumn: 1 }}>
            {name}
          </span>
        ))}
        {weeks.map((days, w) =>
          days.map((day, d) => {
            if (day > today) return null
            const date = new Date(day).toISOString().slice(0, 10)
            const n = words.get(date) ?? 0
            const when = label(day, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
            return (
              <span
                key={date}
                className={cn(
                  'aspect-square rounded-[3px]',
                  SHADES[level(n)],
                  day === today && 'ring-1 ring-foreground/50',
                )}
                style={{ gridRow: d + 2, gridColumn: w + 2 }}
                title={`${n ? `${n} ${n === 1 ? 'word' : 'words'}` : 'No words'} on ${when}`}
              />
            )
          }),
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 text-xs text-muted-foreground">
        <span className="tabular-nums">{summary}</span>
        <span className="flex items-center gap-[3px]" aria-hidden="true">
          <span className="mr-1">Less</span>
          {SHADES.map((shade, i) => (
            <span
              key={shade}
              className={cn('size-2.5 rounded-[2px]', shade)}
              title={
                i === 0
                  ? 'No words'
                  : i === SHADES.length - 1
                    ? `${LEVELS[i]}+ words`
                    : `${LEVELS[i]}–${LEVELS[i + 1] - 1} words`
              }
            />
          ))}
          <span className="ml-1">More</span>
        </span>
      </div>
    </div>
  )
}
