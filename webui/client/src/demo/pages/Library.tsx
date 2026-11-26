/* Stop 6 · Library: the drops the researcher accepted, inside the demo's recordings, grouped into shape families
   (each drop drawn at its own size: normalising would hide that small and large drops share a shape), and the
   trains they form. */
import { useMemo, useState } from 'react'
import { Icicles, ShapeLine, Spark, Strip } from '../charts'
import { api, fmtDur, fmtH, fmtNum, go, numWord, useAsync, useDemo } from '../store'
import type { Family, LibEv, Library } from '../api'
import { tourSignal } from '../tour'

export function memberRows(evs: LibEv[], fs: (sid: number) => number) {
  return evs.map(e => {
    const f = fs(e.slice)
    const step = Math.max(1, Math.round(e.snip.dt * f))
    const k = Math.min(e.snip.v.length - 1, Math.max(0, Math.round((e.top - e.snip_a) / step)))
    const base = e.snip.v[k] ?? 0
    return { dt: e.snip.dt, t0: -(e.top - e.snip_a) / f, v: e.snip.v.map(z => z - base), depth: Math.abs(e.depth_mv ?? 0) }
  })
}

export function LibraryPage() {
  const { m, set, slice } = useDemo()
  const lib = useAsync(() => api.library(), [])
  const seeds = useAsync(() => api.seeds(), [])
  const [open, setOpen] = useState<string | null>(null)
  const L = lib.data
  const byId = useMemo(() => new Map((L?.events ?? []).map(e => [e.id, e])), [L])
  if (lib.error) return <div className="page-body"><div className="card error-line">{lib.error.message}</div></div>
  if (!L) return <div className="page-body"><div className="skeleton" style={{ height: 400 }} /></div>
  const fam = open ? L.families.find(f => f.id === open) ?? null : null

  const searchFamily = (f: Family) => {
    const shelf = seeds.data?.seeds.find(s => s.family === f.id)
    if (shelf) { set({ seed: shelf.id }); go('seed'); return }
    const e = byId.get(f.medoid)
    if (!e) return
    const fall = Math.max(3, e.bottom - e.top)
    const a = Math.max(0, e.top - Math.max(2, Math.round(fall / 3)))
    const end = e.recovery && e.recovery > e.bottom ? e.recovery : e.bottom + 2 * fall
    const b = Math.min(end, e.bottom + 4 * fall, a + Math.round(300 * slice(e.slice).fs))
    set({ slice: e.slice, span: [a, Math.max(b, e.bottom + 2)], seed: 'live' })
    go('seed')
  }

  return (
    <div className="page-body library">
      <div className="card big-stat">
        <div><div className="num">{L.events.length}</div><div className="lab">drops the researcher accepted in these {numWord(m.datasets.length)} recordings</div></div>
        <div><div className="num">{L.families.length}</div><div className="lab">shape families</div></div>
        <div><div className="num">{L.trains.length}</div><div className="lab">trains: five or more drops, under an hour apart</div></div>
        {L.totals.catalogue_spans != null && L.totals.recordings != null && <div className="muted small" style={{ maxWidth: 220 }}>
          The full catalogue holds {L.totals.catalogue_spans.toLocaleString()} accepted spans from {L.totals.recordings} recordings.</div>}
      </div>

      {m.datasets.map(ds => {
        const fams = L.families.filter(f => f.dataset === ds.key)
        const trains = L.trains.filter(t => t.dataset === ds.key)
        return (
          <div key={ds.key} className="card ds-block" data-tour={ds.key === m.datasets[0].key ? 'families' : undefined}>
            <div className="ds-head"><b>{ds.name}</b> <i className="muted">{ds.latin}</i><span className="grow" />
              <span className="muted small">{L.events.filter(e => e.dataset === ds.key).length} drops</span></div>
            <div className="fam-row">
              {fams.map(f => <FamilyCard key={f.id} f={f} L={L} on={open === f.id} onClick={() => { setOpen(open === f.id ? null : f.id); tourSignal('family') }} />)}
            </div>
            {fam && fam.dataset === ds.key && <FamilyDetail f={fam} L={L} onSearch={() => { tourSignal('family-seed'); searchFamily(fam) }}
              onOpen={e => { const s = slice(e.slice); const pad = Math.round(900 * s.fs); set({ slice: e.slice, view: [Math.max(0, e.top - pad), Math.min(s.n, e.top + pad)], span: [Math.max(0, e.top - Math.round(60 * s.fs)), Math.min(s.n, (e.recovery ?? e.bottom) + Math.round(60 * s.fs))] }); go('explore') }} />}
            {trains.length > 0 && <div className="trains">
              <div className="sub-h">Trains</div>
              {trains.map(t => {
                const s = slice(t.slice)
                const spans = t.members.map(id => byId.get(id)).filter((e): e is LibEv => !!e).map(e => [e.top, e.recovery ?? e.bottom] as [number, number])
                return <div key={t.id} className="train-row">
                  <span className="ch-lab">{s.label}</span>
                  <span className="train-txt"><b>{t.n}</b> drops · every {fmtDur(t.median_interval_s ?? 0)} · {fmtH(t.start, s.fs)}–{fmtH(t.end, s.fs)}{t.cv != null ? ` · CV ${fmtNum(t.cv, 2)}` : ''}</span>
                  <Strip n={s.n} spans={spans} tone="lib" />
                  <button className="link" onClick={() => { const pad = Math.round(600 * s.fs); set({ slice: t.slice, view: [Math.max(0, t.start - pad), Math.min(s.n, t.end + pad)], span: null }); go('explore') }}>open</button>
                </div>
              })}
            </div>}
          </div>
        )
      })}
    </div>
  )
}

function FamilyCard({ f, L, on, onClick }: { f: Family; L: Library; on: boolean; onClick: () => void }) {
  const med = L.events.find(e => e.id === f.medoid)
  return (
    <button className={`fam-card${on ? ' on' : ''}`} onClick={onClick} data-testid={`fam-${f.id}`}>
      <div className="fam-name">{f.name}</div>
      {med ? <Spark snip={med.snip} width={150} height={50} color="#22a06b" /> : <ShapeLine v={f.shape} width={150} height={50} />}
      <div className="fam-meta"><b>{f.n}</b> drops · {fmtNum(f.median_depth_mv)} mV · {fmtNum(f.median_width_s)} s</div>
    </button>
  )
}

function FamilyDetail({ f, L, onSearch, onOpen }: { f: Family; L: Library; onSearch: () => void; onOpen: (e: LibEv) => void }) {
  const { slice } = useDemo()
  const members = L.events.filter(e => e.family === f.id)
  const rows = memberRows(members.slice(0, 60), sid => slice(sid).fs)
  return (
    <div className="fam-detail" data-testid="family-detail">
      <div className="fam-detail-grid">
        <div>
          <div className="sub-h">All {members.length} drops of {f.name}, each at its own size</div>
          <Icicles rows={rows} height={200} />
        </div>
        <div className="fam-side">
          <button className="btn primary" data-tour="family-seed" data-testid="family-seed" onClick={onSearch}>Search for more like these</button>
          <div className="thumbs">{members.slice(0, 9).map(e => <button key={e.id} className="thumb" onClick={() => onOpen(e)} title="open in Explore">
            <Spark snip={e.snip} width={92} height={34} /></button>)}</div>
        </div>
      </div>
    </div>
  )
}
