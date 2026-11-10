import { ArrowRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { api } from '../lib/api'
import type { Stats } from '../lib/types'

interface Area {
  name: string
  blurb: string
  /** Where to go; areas without one are shown as "Coming soon". */
  to?: string
  action?: string
}

interface Section {
  name: string
  scoring: string
  areas: Area[]
}

const SECTIONS: Section[] = [
  {
    name: 'Verbal Reasoning',
    scoring: 'Scored 130–170',
    areas: [
      {
        name: 'Vocabulary',
        blurb: 'Adaptive review that learns how comfortable you are with each word.',
        to: '/study',
        action: 'Study',
      },
      {
        name: 'Text Completion & Sentence Equivalence',
        blurb: 'Fill-in-the-blank questions matched to your level.',
        to: '/practice',
        action: 'Practice',
      },
      {
        name: 'Reading Comprehension',
        blurb: 'Passages with questions on meaning, structure, and inference.',
        to: '/practice?section=verbal&kind=rc',
        action: 'Practice',
      },
    ],
  },
  {
    name: 'Quantitative Reasoning',
    scoring: 'Scored 130–170',
    areas: [
      {
        name: 'Arithmetic, Algebra, Geometry & Data Analysis',
        blurb: 'Quantitative Comparison, multiple-choice, and numeric-entry questions matched to your level.',
        to: '/practice?section=quant',
        action: 'Practice',
      },
    ],
  },
  {
    name: 'Analytical Writing',
    scoring: 'Scored 0–6',
    areas: [{ name: 'Analyze an Issue', blurb: 'Timed essays with feedback against the scoring rubric.' }],
  },
]

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    // The vocab summary is a bonus; the home page works without it.
    api.stats().then(setStats).catch(() => setStats(null))
  }, [])

  const todo = stats ? stats.due_now + stats.new_available_today : 0

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight">Your GRE prep</h1>
            <p className="text-sm text-muted-foreground">
              {stats
                ? todo > 0
                  ? `${stats.sets.current ? `Set ${stats.sets.current.number} of ${stats.sets.total} · ` : ''}${stats.due_now} vocab reviews due · ${stats.new_available_today} new words left today`
                  : 'Vocabulary is all caught up for today.'
                : 'Pick a section to get started.'}
            </p>
          </div>
          <Button size="lg" asChild>
            <Link to="/study">
              {todo > 0 ? 'Continue vocab' : 'Study vocab'}
              <ArrowRight />
            </Link>
          </Button>
        </CardContent>
      </Card>

      {SECTIONS.map((section) => {
        const available = section.areas.some((a) => a.to)
        return (
          <Card key={section.name} className="gap-4">
            <CardHeader>
              <CardTitle className={cn('text-lg', !available && 'text-muted-foreground')}>{section.name}</CardTitle>
              <CardDescription>{section.scoring}</CardDescription>
              {!available && (
                <CardAction>
                  <ComingSoon />
                </CardAction>
              )}
            </CardHeader>
            <CardContent>
              <ul className="divide-y border-t">
                {section.areas.map((area) => (
                  <li key={area.name} className="flex items-center gap-4 py-3 last:pb-0">
                    <div className={cn('flex flex-1 flex-col gap-0.5', !area.to && 'opacity-60')}>
                      <span className="font-medium">{area.name}</span>
                      <span className="text-sm text-muted-foreground">{area.blurb}</span>
                    </div>
                    {area.to ? (
                      <Button variant="outline" size="sm" asChild>
                        <Link to={area.to}>
                          {area.action}
                          <ArrowRight />
                        </Link>
                      </Button>
                    ) : (
                      available && <ComingSoon />
                    )}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

function ComingSoon() {
  return (
    <Badge variant="secondary" className="text-muted-foreground">
      Coming soon
    </Badge>
  )
}
