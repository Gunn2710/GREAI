import { Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ComfortMeter, DEPTH_LABEL, FREQUENCY_LABEL, FrequencyBadge, TierBadge, formatDue } from '../components/Comfort'
import { SetTile } from '../components/Sets'
import { api } from '../lib/api'
import type { SetsResponse, WordListEntry, WordSet } from '../lib/types'

export default function Words() {
  const [params, setParams] = useSearchParams()
  const selected = Number(params.get('set')) || null
  const [search, setSearch] = useState('')
  const [words, setWords] = useState<WordListEntry[] | null>(null)
  const [sets, setSets] = useState<SetsResponse | null>(null)

  useEffect(() => {
    api.sets().then(setSets).catch(() => setSets(null))
  }, [])

  useEffect(() => {
    const t = setTimeout(() => {
      api.words(search.trim() || undefined).then(setWords).catch(() => setWords([]))
    }, 200)
    return () => clearTimeout(t)
  }, [search])

  const shown = words?.filter((w) => !selected || w.set === selected) ?? []
  const selectedSet = sets?.sets.find((s) => s.number === selected)
  const select = (n: number | null) => {
    const opening = n !== null && n !== selected
    setParams(opening ? { set: String(n) } : {}, { replace: true })
    // The list sits below the set tiles; bring the chosen set's words into view.
    if (opening) requestAnimationFrame(() => document.getElementById('word-list')?.scrollIntoView({ behavior: 'smooth' }))
  }

  // Phones show only the word and comfort; extra columns appear as the screen widens.
  const wide = 'hidden md:table-cell'
  const wider = 'hidden lg:table-cell'

  return (
    <div className="flex flex-col gap-4">
      {sets && sets.sets.length > 0 && <SetsCard data={sets} selected={selected} onSelect={select} />}
      <Card id="word-list" className="scroll-mt-28">
        <CardHeader>
          <CardTitle className="text-lg">{selectedSet ? `Set ${selectedSet.number}` : 'All words'}</CardTitle>
          <CardDescription>
            {selectedSet
              ? `${setLabel(selectedSet)} · ${selectedSet.size} words`
              : words
                ? `${words.length} ${search.trim() ? 'matching words' : 'words'}`
                : 'Loading…'}
          </CardDescription>
          <CardAction>
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="w-40 pl-8 sm:w-56"
                placeholder="Search…"
                aria-label="Search words"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {selectedSet && (
            <div>
              <Button variant="outline" size="sm" onClick={() => select(null)}>
                <X />
                Show all words
              </Button>
            </div>
          )}
          {!words ? (
            <div className="flex flex-col gap-2">
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-8" />
              ))}
            </div>
          ) : shown.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No words match.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Word</TableHead>
                  <TableHead className={wide}>Meaning</TableHead>
                  <TableHead className={wide}>On the GRE</TableHead>
                  <TableHead>Comfort</TableHead>
                  <TableHead className={wider}>Depth</TableHead>
                  <TableHead className={wider}>Next review</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((w) => (
                  <TableRow key={w.id}>
                    <TableCell>
                      <Link to={`/words/${w.id}`} className="font-medium hover:underline">
                        {w.lemma}
                      </Link>{' '}
                      <span className="text-xs text-muted-foreground italic">{w.pos}</span>
                    </TableCell>
                    <TableCell className={`${wide} w-full max-w-0 truncate text-muted-foreground`} title={w.definition}>
                      {w.definition}
                    </TableCell>
                    <TableCell className={wide}>
                      <FrequencyBadge tier={w.tier} />
                    </TableCell>
                    <TableCell className="min-w-28">
                      <div className="flex flex-col gap-1.5">
                        <TierBadge tier={w.card.tier} />
                        {w.card.tier !== 'new' && <ComfortMeter value={w.card.comfort} tier={w.card.tier} />}
                      </div>
                    </TableCell>
                    <TableCell className={wider}>{DEPTH_LABEL[w.card.depth_name]}</TableCell>
                    <TableCell className={`${wider} text-muted-foreground`}>
                      {w.card.due && w.card.reps > 0 ? formatDue(w.card.due) : '–'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

/** GregMat sets have their own section; the rest are grouped by frequency. */
function setLabel(s: WordSet) {
  return s.source === 'gregmat' ? 'GregMat groups' : `More words: ${FREQUENCY_LABEL[s.tier].toLowerCase()}`
}

/** Every set: GregMat's groups first, then the rest of the bank by how often its words show up. */
function SetsCard({
  data,
  selected,
  onSelect,
}: {
  data: SetsResponse
  selected: number | null
  onSelect: (n: number) => void
}) {
  const groups = new Map<string, WordSet[]>()
  for (const s of data.sets) groups.set(setLabel(s), [...(groups.get(setLabel(s)) ?? []), s])
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Sets</CardTitle>
        <CardDescription>
          GregMat&apos;s groups in order, then the rest of the word bank, most common first. New words come from the
          current set; the next one opens once you have started every word in it. Pick a set to see its words.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {[...groups].map(([label, sets]) => (
          <section key={label} className="flex flex-col gap-2">
            <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</h3>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
              {sets.map((s) => (
                <SetTile key={s.number} set={s} selected={s.number === selected} onSelect={() => onSelect(s.number)} />
              ))}
            </div>
          </section>
        ))}
      </CardContent>
    </Card>
  )
}
