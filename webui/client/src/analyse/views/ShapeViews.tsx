/* fixup-ag — the pages of the RQ1 version-2 chain, drawn by the drawing standard (registry.tsx), never by block name:
 *
 *   · a WindowSet payload that is a POOL (`pool_windows`) draws the pool — windows per recording × scale × role, what
 *     was dropped and why, the members — and, when the block has a `window_sets` parameter (the convention: a str
 *     parameter of that name lists saved window-set ids), the library of saved sets with a tick each;
 *   · `windowset->windowset` (Trace shape) draws the windows before and after: what the noise floor left out, per
 *     recording × scale, every window's raw range against its dataset's floor, and where in the window the largest
 *     excursion sits;
 *   · a Grouping that kept its tree (`tree`) draws the tree's summary (seam ii: the dendrogram page).
 *
 * A piece that cannot be drawn says so in a red card (ErrorBoundary around each), never a blank. */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { ApiError } from '../../api'
import { getWindowSetLibrary, type CountRow, type HistData, type LibrarySet, type PoolPayload, type TreePayload, type WindowSetLibrary } from '../../api/shape'
import { Histogram } from '../../kit'
import { ErrorBoundary } from '../../shell/ErrorBoundary'
import { fmtN, type ProcessProps, type ViewCtx } from './common'
import '../shape.css'

const ROLES = ['train', 'validation', 'test', 'exam'] as const
const KIND_WORDS: Record<string, string> = { unlabelled: 'unlabelled set', pool: 'pool', labelled_across_channels: 'labelled · across channels', labelled_one_channel: 'labelled · one channel' }
const fmtScale = (s: number | null | undefined) => s === null || s === undefined ? 'mixed' : `${s} min`

/* ---------------- the library of saved window sets, with a tick each ---------------- */
export function parseSetIds(v: unknown): number[] | 'all' {
  const s = String(v ?? '').trim()
  if (s.toLowerCase() === 'all unlabelled') return 'all'
  return s.split(/[,;]/).map(x => x.trim()).filter(Boolean).map(Number).filter(Number.isFinite)
}

export function PoolPicker({ q }: { q: ProcessProps }) {
  const [lib, setLib] = useState<WindowSetLibrary | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    getWindowSetLibrary().then(l => { if (alive) setLib(l) }).catch(e => { if (alive) setErr(e instanceof ApiError ? e.message : String(e)) })
    return () => { alive = false }
  }, [])
  const raw = q.step.params.window_sets ?? q.card?.params.find(p => p.name === 'window_sets')?.default
  const parsed = parseSetIds(raw)
  const ticked = useMemo(() => {
    if (!lib) return [] as number[]
    return parsed === 'all' ? lib.sets.filter(s => s.kind === 'unlabelled').map(s => s.id) : parsed
  }, [lib, parsed])
  if (err) return <div className="error-card" data-testid="pool-library-error"><h3>the library of window sets did not load</h3><div className="mono small">{err}</div></div>
  if (!lib) return <div className="muted mono small" data-testid="pool-library-loading">reading the library of saved window sets…</div>
  const set = (ids: number[]) => q.setParam('window_sets', ids.join(','))
  const toggle = (id: number) => set(ticked.includes(id) ? ticked.filter(i => i !== id) : [...ticked, id])
  const reopen = String(q.step.params.pool ?? '').trim()
  return (
    <div className="sh-card" data-testid="pool-library">
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>The library of saved window sets</h3>
        <span className="sg">{lib.sets.length} saved · {ticked.length} ticked · {parsed === 'all' ? 'every unlabelled set (the default)' : 'in the order ticked — the first listed wins a duplicate or an overlap'}</span></div>
      {reopen && <div className="callout small" data-testid="pool-reopen-note">re-opening saved pool <b>{reopen}</b> as the source · the ticks and the plan below are ignored until the <code>pool</code> parameter is cleared</div>}
      {lib.sets.length === 0 ? <div className="muted mono small">no window set is saved yet · Library › Window sets › New window set makes them</div> : (
        <table className="sh-table" data-testid="pool-library-table">
          <thead><tr><th /><th>set</th><th>kind</th><th>recording</th><th>scale</th><th className="r">channels</th><th className="r">windows</th></tr></thead>
          <tbody>
            {lib.sets.map(s => <LibraryRow key={s.id} s={s} on={ticked.includes(s.id)} order={ticked.indexOf(s.id)} onToggle={() => toggle(s.id)} disabled={!!reopen} />)}
          </tbody>
        </table>
      )}
      <div className="row" style={{ gap: 6, marginTop: 6 }}>
        <button className="btn sm" onClick={() => set(lib.sets.filter(s => s.kind === 'unlabelled').map(s => s.id))} data-testid="pool-tick-unlabelled" disabled={!!reopen}>tick every unlabelled set</button>
        <button className="btn sm" onClick={() => set([])} data-testid="pool-tick-none" disabled={!!reopen}>untick all</button>
        <span className="muted small" style={{ marginLeft: 'auto' }}>{lib.note}</span>
      </div>
    </div>
  )
}

function LibraryRow({ s, on, order, onToggle, disabled }: { s: LibrarySet; on: boolean; order: number; onToggle: () => void; disabled: boolean }) {
  return (
    <tr className={on ? 'on' : ''} data-testid={`pool-set-${s.id}`}>
      <td><input type="checkbox" checked={on} onChange={onToggle} disabled={disabled} aria-label={`tick ${s.name}`} data-testid={`pool-tick-${s.id}`} />{on && <span className="sh-order">{order + 1}</span>}</td>
      <td className="mono" title={s.labels_source ?? ''}>{s.name} <span className="muted">v{s.version}</span></td>
      <td>{KIND_WORDS[s.kind] ?? s.kind}</td>
      <td className="mono small">{Object.entries(s.per_recording).length ? Object.entries(s.per_recording).map(([sf, n]) => `${sf.replace(/\.mat$/, '')} ${n.toLocaleString()}`).join(' · ') : s.source_files.join(', ')}</td>
      <td>{s.kind === 'pool' ? (s.scales_min ?? []).map(x => `${x}`).join(' / ') + ' min' : fmtScale(s.scale_min)}</td>
      <td className="r">{s.n_channels}</td>
      <td className="r">{s.n_windows.toLocaleString()}</td>
    </tr>
  )
}

/* ---------------- the pool: recording × scale × role ---------------- */
function CountTable({ rows, testid, cols = ROLES as unknown as string[] }: { rows: CountRow[]; testid: string; cols?: string[] }) {
  const recs = Array.from(new Set(rows.map(r => r.recording))).sort()
  const scales = Array.from(new Set(rows.map(r => r.scale_min))).sort((a, b) => a - b)
  const cell = (rec: string, sc: number, role: string) => rows.filter(r => r.recording === rec && r.scale_min === sc && r.role === role).reduce((a, r) => a + r.n, 0)
  const total = (role: string) => rows.filter(r => r.role === role).reduce((a, r) => a + r.n, 0)
  return (
    <table className="sh-table" data-testid={testid}>
      <thead><tr><th>recording</th><th>scale</th>{cols.map(c => <th key={c} className="r">{c}</th>)}<th className="r">total</th></tr></thead>
      <tbody>
        {recs.flatMap(rec => scales.map(sc => {
          const vals = cols.map(c => cell(rec, sc, c))
          const t = vals.reduce((a, b) => a + b, 0)
          return t ? <tr key={`${rec}-${sc}`}><td className="mono">{rec.replace(/\.mat$/, '')}</td><td>{sc} min</td>{vals.map((v, i) => <td key={i} className="r">{v.toLocaleString()}</td>)}<td className="r b">{t.toLocaleString()}</td></tr> : null
        }))}
        <tr className="tot"><td>all</td><td />{cols.map(c => <td key={c} className="r b">{total(c).toLocaleString()}</td>)}<td className="r b">{cols.reduce((a, c) => a + total(c), 0).toLocaleString()}</td></tr>
      </tbody>
    </table>
  )
}

const DROP_WORDS: Record<string, string> = { gap: 'in a gap between roles', straddle: 'straddling a role boundary', artifact: 'artifact (checked again)', duplicate: 'exact duplicates', overlap_within_scale: 'overlap within a scale', overlap_across_scales: 'overlap across scales', sampled_out: 'sampled out (the per-scale draw)' }

export function PoolView({ p }: { p: PoolPayload }) {
  const pw = p.pool_windows!
  const pool = p.pool
  return (
    <div className="stack" style={{ gap: 10 }} data-testid="pool-view">
      <div className="bp-tiles" style={{ marginTop: 0 }}>
        <div className="bp-tile"><div className="k">windows</div><div className="v" data-testid="pool-n">{pw.n.toLocaleString()}</div></div>
        {ROLES.map(r => <div className="bp-tile" key={r}><div className="k">{r}</div><div className="v">{(pw.by_role[r] ?? 0).toLocaleString()}</div></div>)}
        <div className="bp-tile"><div className="k">per scale</div><div className="v">{Object.entries(pw.by_scale).map(([k, v]) => `${k} min ${v.toLocaleString()}`).join(' · ')}</div></div>
        {pool && <div className="bp-tile"><div className="k">pool</div><div className="v mono" title={pool.path}>{pool.name} v{pool.version} · {pool.saved}</div></div>}
      </div>
      <div><div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Windows per recording × scale × role</h3><span className="sg">a role is a stretch of time laid before any window was placed · the exam is the held-out pack</span></div>
        <CountTable rows={pw.by} testid="pool-counts" /></div>
      {pool && (
        <div className="row" style={{ gap: 14, alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Removed, and why</h3><span className="sg">nothing is dropped silently</span></div>
            <table className="sh-table" data-testid="pool-dropped"><tbody>
              {Object.entries(DROP_WORDS).map(([k, w]) => <tr key={k}><td>{w}</td><td className="r">{(pool.dropped[k] ?? 0).toLocaleString()}</td></tr>)}
              <tr><td>left out when the sets were built (artifact, Settings, non-finite)</td><td className="r">{Object.entries(pool.at_build).filter(([k]) => k !== 'sampled_out').reduce((a, [, v]) => a + v, 0).toLocaleString()}</td></tr>
            </tbody></table>
            <div className="muted small" style={{ marginTop: 4 }}>rule <b>{pool.rule}</b> · {pool.rule_text}</div>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Members, in order</h3><span className="sg">key {pool.key}</span></div>
            <table className="sh-table" data-testid="pool-members"><thead><tr><th>set</th><th className="r">offered</th><th className="r">kept</th></tr></thead><tbody>
              {pool.members.map(m => <tr key={m.id}><td className="mono">{m.name} v{m.version}</td><td className="r">{m.n_offered.toLocaleString()}</td><td className="r">{m.n_kept.toLocaleString()}</td></tr>)}
            </tbody></table>
            <div className="muted small" style={{ marginTop: 4 }}>plan: {pool.plan.n_blocks} time blocks · test {pool.plan.test_frac} · validation {pool.plan.validation_frac} · gap {Math.round(pool.plan.gap_s / 60)} min · {pool.plan.hold_out_pack ? `pack ${pool.plan.hold_out_pack} held out as the exam` : 'no pack held out'}{pool.sample ? ` · drawn per scale (seed ${pool.seed}): ${Object.entries(pool.sample).map(([k, v]) => `${k} min ${v.toLocaleString()}`).join(', ')}` : ' · every window kept'}</div>
            {pool.checks && <div className="muted small mono" data-testid="pool-checks">checks: {Object.entries(pool.checks).map(([k, v]) => `${k} ${v.toLocaleString()}`).join(' · ')}</div>}
          </div>
        </div>
      )}
    </div>
  )
}

/* ---------------- Trace shape: before and after ---------------- */
function LogHist({ h, floor, testid, height = 120 }: { h: HistData | null | undefined; floor?: number | null; testid: string; height?: number }) {
  if (!h || !h.counts.length) return <div className="muted mono small" data-testid={testid}>no measured range to draw</div>
  const e = h.log ? h.edges.map(v => Math.log10(v)) : h.edges
  const bins = h.counts.map((c, i) => ({ x0: e[i], x1: e[i + 1], count: c }))
  const fmt = h.log ? (v: number) => fmtN(10 ** v) : (v: number) => fmtN(v)
  const thr = floor && h.log && floor > 0 ? { value: Math.log10(floor), label: `floor ${fmtN(floor)} mV`, colour: 'var(--red)' } : undefined
  return <div data-testid={testid}><Histogram bins={bins} height={height} format={fmt} threshold={thr} xTicks={5} colour="var(--blue-200)" label={testid} /></div>
}

export function ShapeView({ p }: { p: PoolPayload }) {
  const s = p.shape!
  const floors = Object.entries(s.floors)
  const under = s.under_floor
  return (
    <div className="stack" style={{ gap: 10 }} data-testid="shape-view">
      <div className="bp-tiles" style={{ marginTop: 0 }}>
        <div className="bp-tile"><div className="k">windows in</div><div className="v">{s.n_in.toLocaleString()}</div></div>
        <div className="bp-tile"><div className="k">under the noise floor · left out</div><div className={`v${under.n ? ' red' : ''}`} data-testid="shape-under-floor">{s.noise_floor ? under.n.toLocaleString() : `off (${under.n_would_be.toLocaleString()} would go)`}</div></div>
        <div className="bp-tile"><div className="k">unmeasured · kept</div><div className="v">{s.unmeasured.n.toLocaleString()}</div></div>
        <div className="bp-tile"><div className="k">kept · shapes of {s.resample_length} points</div><div className="v">{s.n_kept.toLocaleString()}</div></div>
      </div>
      <div className="muted small">{under.rule} · floors: {floors.map(([sf, f]) => `${sf.replace(/\.mat$/, '')} ${fmtN(f.floor_mv)} mV (${f.from})`).join(' · ')} · {s.method}</div>
      {s.noise_floor && under.n > 0 && <div><div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Left out under the floor, per recording × scale × role</h3></div><CountTable rows={under.by} testid="shape-under-floor-table" /></div>}
      {s.unmeasured.n > 0 && <div className="callout small" data-testid="shape-unmeasured">{s.unmeasured.n.toLocaleString()} windows come from a recording with no declared unit: {s.unmeasured.rule}</div>}
      <div className="row" style={{ gap: 14, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Raw range of the kept windows</h3><span className="sg">peak to peak, mV, log axis · the red line is the floor</span></div>
          <LogHist h={s.raw_range_hist} floor={floors.length === 1 ? floors[0][1].floor_mv : Math.min(...floors.map(([, f]) => f.floor_mv))} testid="shape-range-hist" />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Where the largest excursion sits in its window</h3><span className="sg">0 = the start, 1 = the end · per scale</span></div>
          {Object.entries(s.peak_frac_by_scale ?? {}).map(([sc, h]) => <div key={sc}><div className="muted small mono">{sc} min</div><LogHist h={h} testid={`shape-peak-hist-${sc}`} height={70} /></div>)}
        </div>
      </div>
      <div className="muted small mono" title={s.shape_file}>vectors on disk · key {s.shape_key} · {s.seconds} s</div>
    </div>
  )
}

/* ---------------- the kept tree, plain (seam ii draws the dendrogram) ---------------- */
export function TreeSummary({ p }: { p: TreePayload }) {
  const t = p.tree!
  return (
    <div className="stack" style={{ gap: 8 }} data-testid="tree-summary">
      <div className="bp-tiles" style={{ marginTop: 0 }}>
        <div className="bp-tile"><div className="k">clustered (the tree)</div><div className="v" data-testid="tree-clustered">{t.n_clustered.toLocaleString()}</div></div>
        <div className="bp-tile"><div className="k">assigned to the nearest centre</div><div className="v" data-testid="tree-assigned">{t.n_assigned.toLocaleString()}</div></div>
        <div className="bp-tile"><div className="k">not clustered · val / test / exam</div><div className="v">{Object.values(t.not_clustered).reduce((a, b) => a + b, 0).toLocaleString()}</div></div>
        <div className="bp-tile"><div className="k">clusters at the cut</div><div className="v">{t.k}{t.k_param === 0 ? ' (proposed)' : ''}</div></div>
      </div>
      <div className="muted small">{t.rule} · {t.method_text} · tree {t.reused ? 're-used' : 'built'}{t.ward_seconds !== null ? ` · Ward ${t.ward_seconds} s` : ''}{t.peak_rss_mb ? ` · peak memory ${Math.round(t.peak_rss_mb).toLocaleString()} MB` : ''}{t.loaded_from ? ` · loaded from ${t.loaded_from}` : ''}</div>
    </div>
  )
}

export function Guard({ label, children }: { label: string; children: ReactNode }) {
  return <ErrorBoundary label={label}>{children}</ErrorBoundary>
}

/* ---------------- thumbnails (the chain row): one glanceable shape each ---------------- */
const ROLE_COLOUR: Record<string, string> = { train: '#a8c1ec', validation: '#fdc77e', test: '#86d69e', exam: '#c9b3f5' }

/** A pool on a chain row: its windows as one bar split by role, the scales and the floor count written on it. */
export function PoolThumb({ p, ctx }: { p: PoolPayload; ctx: ViewCtx }) {
  const pw = p.pool_windows!
  const w = Math.max(10, ctx.width), h = Math.max(20, ctx.height)
  let x = 0
  const total = Math.max(1, pw.n)
  return (
    <svg width={w} height={h} data-testid="pool-thumb">
      {ROLES.map(r => { const ww = (pw.by_role[r] ?? 0) / total * (w - 8); const el = <rect key={r} x={4 + x} y={h / 2 - 9} width={Math.max(0, ww)} height={18} fill={ROLE_COLOUR[r]}><title>{`${r} ${(pw.by_role[r] ?? 0).toLocaleString()}`}</title></rect>; x += ww; return el })}
      <text x={8} y={h / 2 + 4} style={{ fontSize: 11 }} fill="var(--text)">{pw.n.toLocaleString()} windows · {ROLES.filter(r => pw.by_role[r]).map(r => `${r} ${pw.by_role[r].toLocaleString()}`).join(' · ')} · {Object.keys(pw.by_scale).map(k => `${k} min`).join(' / ')}{p.shape ? ` · ${p.shape.noise_floor ? `${p.shape.under_floor.n.toLocaleString()} under the floor left out` : 'floor off'}` : ''}</text>
    </svg>
  )
}

/** A kept tree on a chain row: the cluster sizes at the cut as bars, specks grey. */
export function TreeThumb({ p, ctx }: { p: TreePayload; ctx: ViewCtx }) {
  const t = p.tree!
  const w = Math.max(10, ctx.width), h = Math.max(20, ctx.height)
  const cl = t.clusters
  const max = Math.max(1, ...cl.map(c => c.n))
  const bw = Math.max(4, Math.min(40, (w - 260) / Math.max(1, cl.length) - 3))
  return (
    <svg width={w} height={h} data-testid="tree-thumb">
      {cl.map((c, i) => { const bh = (c.n / max) * (h - 10); return <rect key={c.cluster} x={4 + i * (bw + 3)} y={h - 4 - bh} width={bw} height={bh} fill={c.speck ? 'var(--grey-300, #c8ccd2)' : 'var(--blue-400, #5b9bff)'}><title>{`cluster ${c.cluster} · ${c.n.toLocaleString()} windows${c.speck ? ' · speck' : ''}`}</title></rect> })}
      <text x={8 + cl.length * (bw + 3)} y={h / 2 + 4} style={{ fontSize: 11 }} fill="var(--text)">k {t.k} · clustered {t.n_clustered.toLocaleString()} · assigned {t.n_assigned.toLocaleString()}</text>
    </svg>
  )
}
