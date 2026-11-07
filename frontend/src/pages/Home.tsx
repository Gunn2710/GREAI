import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
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
      { name: 'Reading Comprehension', blurb: 'Passages with questions on meaning, structure, and inference.' },
    ],
  },
  {
    name: 'Quantitative Reasoning',
    scoring: 'Scored 130–170',
    areas: [
      { name: 'Arithmetic & Algebra', blurb: 'Number properties, exponents, equations, and inequalities.' },
      { name: 'Geometry', blurb: 'Lines, angles, triangles, circles, and coordinate geometry.' },
      { name: 'Data Analysis', blurb: 'Statistics, probability, and reading tables and graphs.' },
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
    <div className="home">
      <section className="hero panel">
        <div>
          <h2>Your GRE prep</h2>
          <p className="muted">
            {stats
              ? todo > 0
                ? `${stats.due_now} vocab reviews due · ${stats.new_available_today} new words left today`
                : 'Vocabulary is all caught up for today.'
              : 'Pick a section to get started.'}
          </p>
        </div>
        <Link to="/study" className="button primary big">
          {todo > 0 ? 'Continue vocab' : 'Study vocab'}
        </Link>
      </section>

      {SECTIONS.map((section) => {
        const available = section.areas.some((a) => a.to)
        return (
          <section key={section.name} className={`panel gre-section${available ? '' : ' soon'}`}>
            <div className="row space">
              <h3>{section.name}</h3>
              {available ? (
                <span className="muted small">{section.scoring}</span>
              ) : (
                <span className="badge coming-soon">Coming soon</span>
              )}
            </div>
            <ul className="areas">
              {section.areas.map((area) => (
                <li key={area.name} className={area.to ? 'area' : 'area soon'}>
                  <div className="grow">
                    <div className="area-name">{area.name}</div>
                    <div className="muted small">{area.blurb}</div>
                  </div>
                  {area.to ? (
                    <Link to={area.to} className="button">
                      {area.action}
                    </Link>
                  ) : (
                    available && <span className="badge coming-soon">Coming soon</span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}
