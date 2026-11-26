/* Stop 7 · Seed search: "find more like this one". A shelf of seeds searched in advance over every channel, and
   the stretch the visitor marked in Explore, searched live. A match counts when it is closer than chance allows:
   the cut is set where the same search on noise copies of the channels would rarely reach. */
import { useEffect, useMemo, useState } from 'react'
import { Hist, Spark } from '../charts'
import { api, breadth, fmtH, go, numWord, useDemo } from '../store'
import type { Seed } from '../api'
import { tourSignal } from '../tour'

/** Live results by stretch, for the life of the page: coming back to the Seed page does not search again. */
const LIVE = new Map<string, Seed>()

export function SeedPage() {
  const { m, thread, set, slice } = useDemo()
  const [seeds, setSeeds] = useState<Seed[] | null>(null)
  const [live, setLive] = useState<Seed | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)
  useEffect(() => { api.seeds().then(r => setSeeds(r.seeds), e => setErr(String(e.message || e))) }, [])
  const sl = slice(thread.slice)
  // a marked stretch is a seed only when it can be searched: 8 samples to 5 minutes
  const span = thread.span && thread.span[1] - thread.span[0] >= 8 && (thread.span[1] - thread.span[0]) / sl.fs <= 300 ? thread.span : null
  const liveKey = span ? `${thread.slice}:${span[0]}:${span[1]}` : null
  useEffect(() => {
    if (thread.seed !== 'live' || !span || !liveKey) return
    if (live && `${live.slice}:${live.a}:${live.b}` === liveKey) return
    const hit = LIVE.get(liveKey)
    if (hit) { setLive(hit); return }
    setSearching(true); setErr(null)
    api.liveSeed(thread.slice, span[0], span[1]).then(r => { LIVE.set(liveKey, r); setLive(r); setSearching(false) },
      e => { setErr(String(e.message || e)); setSearching(false) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thread.seed, liveKey])
  // a family's own seed, opened from the Library, is answered even when it is not on the shelf (the shelf keeps the
  // seeds with at least 3 matches closer than chance): "none closer than chance" is an answer too, a blank page is not
  const chosen: Seed | null = thread.seed === 'live' ? live : (seeds?.find(s => s.id === thread.seed) ?? null)
  const shelf = useMemo(() => {
    const on = seeds?.filter(s => s.n_kept >= 3) ?? null
    return on && chosen && thread.seed !== 'live' && !on.includes(chosen) ? [chosen, ...on] : on
  }, [seeds, chosen, thread.seed])
  useEffect(() => { if (chosen) tourSignal('seed') }, [chosen?.id])

  return (
    <div className="page-body seed">
      <div className="shelf" data-tour="shelf">
        {span && <button className={`seed-card${thread.seed === 'live' ? ' on' : ''}`} onClick={() => set({ seed: 'live' })} data-testid="seed-live">
          <div className="seed-name">Your marked stretch</div>
          <div className="muted small">{slice(thread.slice).label} · {fmtH(span[0], slice(thread.slice).fs)}</div>
          {live && <Spark snip={live.exemplar} width={130} height={40} color="#0d9488" />}
        </button>}
        {shelf?.map(s => {
          const ds = m.datasets.find(d => d.key === s.dataset)!
          return <button key={s.id} className={`seed-card${thread.seed === s.id ? ' on' : ''}`} onClick={() => set({ seed: s.id })} data-testid={`seed-${s.id}`}>
            <div className="seed-name">{s.name}</div>
            <div className="muted small">{ds.name}</div>
            <Spark snip={s.exemplar} width={130} height={40} color="#0d9488" />
          </button>
        })}
      </div>

      {err && <div className="card error-line">{err}</div>}
      {searching && <div className="card searching" data-testid="seed-searching"><span className="spinner" /> Searching {breadth(m).channels} channels in {numWord(breadth(m).species)} species…</div>}
      {!chosen && !searching && !err && <div className="card hint-card">Pick a seed above{span ? ', or search for your marked stretch' : ''}.</div>}
      {chosen && !searching && <SeedResult s={chosen} />}
    </div>
  )
}

function SeedResult({ s }: { s: Seed }) {
  const { m, set, slice } = useDemo()
  const ds = m.datasets.find(d => d.key === s.dataset)!
  const hist = useMemo(() => {
    const all = [...s.matches.map(x => x.distance), ...s.null]
    if (!all.length) return null
    const lo = Math.min(...all), hi = Math.max(...s.matches.map(x => x.distance), ...(s.null.length ? [s.null[Math.floor(s.null.length * 0.6)]] : []))
    const nb = 28
    const edges = Array.from({ length: nb + 1 }, (_, i) => lo + (i / nb) * (hi - lo || 1))
    const bin = (v: number[]) => { const c = new Array(nb).fill(0); for (const x of v) { const i = Math.floor((x - lo) / ((hi - lo) || 1) * nb); if (i >= 0 && i < nb) c[i]++ } return c }
    const perDraw = Math.max(1, s.null_draws / Math.max(1, m.slices.length))
    return { edges, mine: bin(s.matches.map(x => x.distance)), noise: bin(s.null).map(c => c / perDraw) }
  }, [s, m.slices.length])
  const cut = s.cut
  return (
    <div className="seed-result">
      <div className="card big-stat" data-tour="seed-result" data-testid="seed-summary">
        <div className="exemplar"><Spark snip={s.exemplar} width={170} height={64} color="#0d9488" /><div className="lab">{s.name} · {ds.name}</div></div>
        <div><div className="num">{s.n_kept}</div><div className="lab">matches closer than chance</div></div>
        {m.datasets.map(d => <div key={d.key}><div className="num small-num">{s.kept_by_dataset[d.key] ?? 0}</div><div className="lab">in {d.name.toLowerCase()}</div></div>)}
        {s.elapsed_s != null && <div className="muted small">searched live in {s.elapsed_s.toFixed(2)} s</div>}
      </div>
      {hist && <div className="card">
        <h3>How close each match is</h3>
        <Hist edges={hist.edges} cut={cut} testid="seed-hist" series={[
          { counts: hist.noise, color: '#c7cbd1', label: 'on noise copies' }, { counts: hist.mine, color: '#0d9488', label: 'on the recordings' }]} xLabel="distance (smaller = closer)" />
      </div>}
      <div className="card">
        <h3>The closest matches</h3>
        <div className="gallery" data-testid="seed-gallery">
          {s.matches.slice(0, 24).map((x, i) => {
            const sl = slice(x.slice)
            const d = m.datasets.find(q => q.key === x.dataset)!
            const kept = cut != null && x.distance <= cut
            return <button key={i} className={`match${kept ? ' kept' : ''}`} title="open in Explore" onClick={() => {
              const pad = Math.round(1800 * sl.fs)
              set({ slice: x.slice, view: [Math.max(0, x.index - pad), Math.min(sl.n, x.index + x.length + pad)], span: [x.index, x.index + x.length] }); go('explore')
            }}>
              {x.snip && <Spark snip={x.snip} width={120} height={40} color={kept ? '#0d9488' : '#9ca3af'}
                shade={x.pad != null ? [x.pad / Math.max(1, x.snip.dt * sl.fs), (x.pad + x.length) / Math.max(1, x.snip.dt * sl.fs)] : undefined} />}
              <div className="match-meta"><span className={`sp sp-${x.dataset}`}>{d.name}</span> {sl.label}</div>
            </button>
          })}
        </div>
      </div>
      <div className="cta-bar"><span className="grow" />
        <button className="btn primary big" data-testid="to-stats" onClick={() => go('stats')}>See the spike statistics</button></div>
    </div>
  )
}
