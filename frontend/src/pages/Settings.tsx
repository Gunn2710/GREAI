import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, getDevUser, setDevUser } from '../lib/api'
import { useConfig } from '../lib/config'
import type { Profile } from '../lib/types'

export default function Settings() {
  const config = useConfig()
  const [profile, setProfile] = useState<Profile | null>(null)
  const [saved, setSaved] = useState(false)
  const [devUser, setDevUserState] = useState(getDevUser())

  useEffect(() => {
    api.profile().then(setProfile)
  }, [])

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!profile) return
    setProfile(await api.saveProfile(profile))
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  function switchUser(e: FormEvent) {
    e.preventDefault()
    setDevUser(devUser.trim() || 'dev-user')
    window.location.assign('/')
  }

  if (!profile) return <div className="panel muted">Loading…</div>

  const num = (v: string) => (v === '' ? null : Number(v))

  return (
    <div className="settings">
      <form className="panel form" onSubmit={save}>
        <h2>Study plan</h2>
        <label>
          Test date
          <input
            type="date"
            value={profile.test_date ?? ''}
            onChange={(e) => setProfile({ ...profile, test_date: e.target.value || null })}
          />
        </label>
        <label>
          Target Verbal score
          <input
            type="number"
            min={130}
            max={170}
            value={profile.target_verbal ?? ''}
            onChange={(e) => setProfile({ ...profile, target_verbal: num(e.target.value) })}
          />
        </label>
        <label>
          Target Quant score <span className="muted small">(Quant practice coming later)</span>
          <input
            type="number"
            min={130}
            max={170}
            value={profile.target_quant ?? ''}
            onChange={(e) => setProfile({ ...profile, target_quant: num(e.target.value) })}
          />
        </label>
        <label>
          New words per day
          <input
            type="number"
            min={0}
            max={100}
            value={profile.daily_new_words}
            onChange={(e) => setProfile({ ...profile, daily_new_words: Number(e.target.value) })}
          />
        </label>
        <div className="row end">
          {saved && <span className="up small">Saved</span>}
          <button className="primary" type="submit">
            Save
          </button>
        </div>
      </form>

      <div className="panel row space">
        <div>
          <h3>Placement check</h3>
          <p className="muted small">Retake it any time to re-estimate your vocabulary level.</p>
        </div>
        <Link to="/placement" className="button">
          Take placement check
        </Link>
      </div>

      {config.auth_mode === 'dev' && (
        <form className="panel form" onSubmit={switchUser}>
          <h2>Dev user</h2>
          <p className="muted small">
            Accounts aren't connected yet, so the server uses this id to separate users. It will be replaced by Clerk sign-in.
          </p>
          <label>
            User id
            <input value={devUser} onChange={(e) => setDevUserState(e.target.value)} />
          </label>
          <div className="row end">
            <button type="submit">Switch user</button>
          </div>
        </form>
      )}

      <div className="panel small muted">
        AI: {config.ai_enabled ? `on (${config.model})` : 'off'} · Auth: {config.auth_mode}
      </div>
    </div>
  )
}
