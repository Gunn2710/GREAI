import { Check } from 'lucide-react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { LoadingCard } from '@/components/Status'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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

  if (!profile) return <LoadingCard />

  const num = (v: string) => (v === '' ? null : Number(v))

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Study plan</CardTitle>
          <CardDescription>Your test date, goals and daily pace.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid max-w-md gap-4" onSubmit={save}>
            <Field id="test-date" label="Test date">
              <Input
                id="test-date"
                type="date"
                value={profile.test_date ?? ''}
                onChange={(e) => setProfile({ ...profile, test_date: e.target.value || null })}
              />
            </Field>
            <Field id="target-verbal" label="Target Verbal score">
              <Input
                id="target-verbal"
                type="number"
                min={130}
                max={170}
                value={profile.target_verbal ?? ''}
                onChange={(e) => setProfile({ ...profile, target_verbal: num(e.target.value) })}
              />
            </Field>
            <Field id="target-quant" label="Target Quant score" note="Quant practice coming later">
              <Input
                id="target-quant"
                type="number"
                min={130}
                max={170}
                value={profile.target_quant ?? ''}
                onChange={(e) => setProfile({ ...profile, target_quant: num(e.target.value) })}
              />
            </Field>
            <Field id="daily-new" label="New words per day">
              <Input
                id="daily-new"
                type="number"
                min={0}
                max={100}
                value={profile.daily_new_words}
                onChange={(e) => setProfile({ ...profile, daily_new_words: Number(e.target.value) })}
              />
            </Field>
            <div className="flex items-center justify-end gap-3">
              {saved && (
                <span className="flex items-center gap-1 text-sm text-success">
                  <Check className="size-4" />
                  Saved
                </span>
              )}
              <Button type="submit">Save</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h2 className="font-semibold">Placement check</h2>
            <p className="text-sm text-muted-foreground">Retake it any time to re-estimate your vocabulary level.</p>
          </div>
          <Button variant="outline" asChild>
            <Link to="/placement">Take placement check</Link>
          </Button>
        </CardContent>
      </Card>

      {config.auth_mode === 'dev' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Dev user</CardTitle>
            <CardDescription>
              Accounts aren't connected yet, so the server uses this id to separate users. It will be replaced by Clerk
              sign-in.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid max-w-md gap-4" onSubmit={switchUser}>
              <Field id="dev-user" label="User id">
                <Input id="dev-user" value={devUser} onChange={(e) => setDevUserState(e.target.value)} />
              </Field>
              <div className="flex justify-end">
                <Button type="submit" variant="outline">
                  Switch user
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <p className="px-1 text-xs text-muted-foreground">
        AI: {config.ai_enabled ? `on (${config.model})` : 'off'} · Auth: {config.auth_mode}
      </p>
    </div>
  )
}

function Field({ id, label, note, children }: { id: string; label: string; note?: string; children: ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>
        {label}
        {note && <span className="font-normal text-muted-foreground">({note})</span>}
      </Label>
      {children}
    </div>
  )
}
