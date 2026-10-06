/* fixup-ag seam (ii) — the Shape clustering block's page IS the dendrogram (it replaces Analyse › Training's fixture
 * block 3). Drawn because the Grouping payload carries `tree` (a payload convention, registry.tsx), never because of
 * the block's name.
 *
 *   · the tree, truncated to its last merges; a cut line the researcher DRAGS — k follows. Moving the cut reads the
 *     kept tree through the bridge (`/api/shape/trees/{key}/cut`); it never rebuilds it. *Apply this cut* writes k
 *     into the block (the run after re-uses the tree);
 *   · the proposal per k (silhouette on the clustered sample, specks by the baseline's rule) — a guide;
 *   · each cluster at the cut, clickable: its MEDOID (the most typical real window — a centre in shape space is not a
 *     trace), a seeded dozen of random members, the mean normalised shape with its spread, the count, the scale and
 *     recording mix, the raw amplitude range, where the event sits; members open in Explore;
 *   · the mapping table: each cluster → a name (optional) and interesting / not; specks listed and mapped like the
 *     rest. It is the block's `mapping` parameter, so the template and Models › Launch read the same mapping.
 *
 * Every piece that fails to draw is a red card (ErrorBoundary) and a console error — never a blank. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from '../../api'
import { getClusterCards, getClusterDetail, getFrozen, getTreeCut, type Cards, type ClusterCard, type ClusterDetail, type CutAt, type DetailWindow, type Frozen, type MappingEntry, type TreeInfo, type TreePayload } from '../../api/shape'
import { useSize } from '../../charts/useSize'
import { navigate } from '../../state'
import { Guard } from './ShapeViews'
import { fmtN, type ProcessProps } from './common'

const errText = (e: unknown) => e instanceof ApiError ? e.message : String(e)
const CLASS_WORDS: Record<string, string> = { interesting: 'interesting', not_interesting: 'not interesting' }
const scaleOf = (s: Record<string, number>, k: string) => s[k] ?? 0

/** The k a cut at height h makes: every merge above it splits one more cluster off. */
export const kAt = (heights: number[], h: number) => heights.filter(x => x > h).length + 1
/** A height inside the gap that gives exactly k (heights sorted high → low). */
export const heightFor = (heights: number[], maxH: number, k: number) => {
  if (k <= 1) return maxH * 1.04
  const hi = heights[k - 2] ?? maxH, lo = heights[k - 1] ?? 0
  return (hi + lo) / 2
}

export function TreePage({ q, p }: { q: ProcessProps; p: TreePayload }) {
  const t = p.tree!
  const [k, setK] = useState<number>(t.k)
  const [cut, setCut] = useState<CutAt | null>(null)
  const [cutErr, setCutErr] = useState<string | null>(null)
  const [sel, setSel] = useState<number | null>(null)
  const [frozen, setFrozen] = useState<Frozen | null>(t.frozen ?? null)
  useEffect(() => { setK(t.k); setSel(null) }, [t.key, t.k])
  /* seam (iii): once a run on this pool has a test score, the cut and the mapping are fixed — here as in Launch */
  useEffect(() => {
    let alive = true
    if (t.pool_key) getFrozen(t.pool_key).then(r => { if (alive) setFrozen(r.frozen) }).catch(e => console.error('freeze read failed', e))
    return () => { alive = false }
  }, [t.pool_key])
  useEffect(() => {
    let alive = true
    setCutErr(null)
    getTreeCut(t.key, k).then(c => { if (alive) setCut(c) }).catch(e => { if (alive) { setCut(null); setCutErr(errText(e)) } })
    return () => { alive = false }
  }, [t.key, k])
  const applied = t.k
  return (
    <div className="stack" style={{ gap: 12 }} data-testid="tree-page">
      <div className="bp-tiles" style={{ marginTop: 0 }}>
        <div className="bp-tile"><div className="k">clustered · the tree</div><div className="v" data-testid="tree-clustered">{t.n_clustered.toLocaleString()}</div></div>
        <div className="bp-tile"><div className="k">assigned · nearest centre</div><div className="v" data-testid="tree-assigned">{t.n_assigned.toLocaleString()}</div></div>
        <div className="bp-tile"><div className="k">not clustered · val / test / exam</div><div className="v">{Object.values(t.not_clustered).reduce((a, b) => a + b, 0).toLocaleString()}</div></div>
        <div className="bp-tile"><div className="k">cut applied to the block</div><div className="v" data-testid="tree-applied-k">k = {applied}{t.k_param === 0 ? ' (proposed)' : ''}</div></div>
      </div>
      <div className="muted small" data-testid="tree-rule">{t.rule} · shapes: align {t.align ?? 'grid'} · detrend {t.detrend ?? 'off'}{t.propose_cached ? ' · proposal read from beside the tree' : ''} · {t.method_text} · {t.stratified_by} · seed {t.seed} · tree {t.reused ? 're-used' : 'built'}{t.ward_seconds !== null ? ` · Ward ${t.ward_seconds} s` : ''}{t.peak_rss_mb ? ` · peak memory ${Math.round(t.peak_rss_mb).toLocaleString()} MB` : ''}{t.loaded_from ? ` · loaded from ${t.loaded_from}` : ''}</div>
      {frozen && <div className="error-card" data-testid="tree-frozen" style={{ padding: '6px 10px' }}><h3>The cut and the mapping are frozen</h3><div className="small">run {frozen.run_id} ({frozen.name}) has a test score on this pool at k = {frozen.k}: a different cut or interesting / not mapping is refused here and on Models › Launch. Browsing other cuts is fine.</div></div>}
      <Guard label="the dendrogram">
        <Dendrogram t={t} k={k} onK={kk => { setK(kk); setSel(null) }} />
      </Guard>
      <div className="row" style={{ gap: 8, alignItems: 'center' }}>
        <span className="mono small" data-testid="tree-preview-k">cut · k = {k}{k === t.propose.suggested_k ? ' · the proposal' : ''}</span>
        <button className="btn sm" onClick={() => setK(x => Math.max(2, x - 1))} data-testid="tree-k-down" disabled={k <= 2}>− k</button>
        <button className="btn sm" onClick={() => setK(x => Math.min(t.dendrogram.heights.length, x + 1))} data-testid="tree-k-up">+ k</button>
        {t.propose.suggested_k && <button className="btn sm" onClick={() => setK(t.propose.suggested_k!)} data-testid="tree-k-proposed">the proposal (k = {t.propose.suggested_k})</button>}
        <span style={{ flex: 1 }} />
        <button className="btn primary sm" onClick={() => q.setParam('k', k)} disabled={(k === applied && t.k_param !== 0) || (!!frozen && k !== frozen.k)} data-testid="tree-apply-cut"
          title={frozen && k !== frozen.k ? `frozen at k = ${frozen.k} by run ${frozen.run_id}` : 'writes k into this block; the run after re-uses the kept tree'}>{k === applied ? `k = ${k} is applied` : `Apply this cut (k = ${k})`}</button>
      </div>
      <Guard label="the proposal per k"><ProposeTable t={t} k={k} onK={setK} /></Guard>
      {cutErr && <div className="error-card" data-testid="tree-cut-error"><h3>the clusters at k = {k} did not load</h3><div className="mono small">{cutErr}</div></div>}
      <CardStrip tkey={t.key} k={k} sel={sel} onSel={setSel} />
      {cut && <Guard label="the clusters at the cut"><ClusterTable cut={cut} sel={sel} onSel={setSel} /></Guard>}
      {sel !== null && <Guard label={`cluster ${sel}`}><ClusterPanel tkey={t.key} k={k} c={sel} /></Guard>}
      <Guard label="the mapping table"><MappingTable q={q} t={t} cut={cut} frozen={frozen} /></Guard>
    </div>
  )
}

/* ---------------- the dendrogram, with a cut line to drag ---------------- */
function Dendrogram({ t, k, onK }: { t: TreeInfo; k: number; onK: (k: number) => void }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const d = t.dendrogram
  const W = Math.max(200, size.width), H = 260, padL = 44, padR = 10, padT = 10, padB = 34
  const xs = d.icoord.flat(), xmin = Math.min(...xs, 5), xmax = Math.max(...xs, 15)
  const maxH = (d.max_height || 1) * 1.04
  const X = (v: number) => padL + (v - xmin) / Math.max(1e-9, xmax - xmin) * (W - padL - padR)
  const Y = (h: number) => padT + (1 - h / maxH) * (H - padT - padB)
  const hInv = (py: number) => Math.max(0, (1 - (py - padT) / (H - padT - padB)) * maxH)
  const cutH = heightFor(d.heights, d.max_height, k)
  const drag = useRef(false)
  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    if (!drag.current) return
    const svg = e.currentTarget.ownerSVGElement; if (!svg) return
    const kk = Math.max(2, Math.min(d.heights.length, kAt(d.heights, hInv(e.clientY - svg.getBoundingClientRect().top))))
    if (kk !== k) onK(kk)
  }
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => f * d.max_height)
  return (
    <div className="sh-dendro" ref={ref} data-testid="dendrogram">
      {size.width > 0 && (
        <svg width={W} height={H}>
          {ticks.map((v, i) => <g key={i}><line x1={padL - 4} x2={padL} y1={Y(v)} y2={Y(v)} stroke="var(--muted)" /><text x={padL - 6} y={Y(v) + 3} textAnchor="end" style={{ fontSize: 9 }} fill="var(--muted)">{fmtN(v)}</text></g>)}
          <text x={4} y={(H - padB + padT) / 2} transform={`rotate(-90 8 ${(H - padB + padT) / 2})`} textAnchor="middle" style={{ fontSize: 9 }} fill="var(--muted)">Ward height</text>
          {d.icoord.map((xx, i) => {
            const yy = d.dcoord[i]
            const above = Math.max(...yy) > cutH
            return <polyline key={i} points={xx.map((x, j) => `${X(x)},${Y(yy[j])}`).join(' ')} fill="none" stroke={above ? 'var(--grey-400, #9aa1ab)' : 'var(--blue, #0a84ff)'} strokeWidth={1.2} />
          })}
          {d.leaves.map((lab, i) => <text key={i} x={X(5 + 10 * i)} y={H - padB + 12} textAnchor="middle" style={{ fontSize: 8 }} fill="var(--muted)">{lab.startsWith('(') ? lab.slice(1, -1) : '1'}</text>)}
          <text x={W - padR} y={H - 6} textAnchor="end" style={{ fontSize: 9 }} fill="var(--muted)">the last {d.leaves.length} merges of {d.n_leaves.toLocaleString()} leaves · numbers = windows under each branch</text>
          <g data-testid="dendrogram-cut">
            <line x1={padL} x2={W - padR} y1={Y(cutH)} y2={Y(cutH)} stroke="var(--amber, #e8900c)" strokeWidth={1.6} strokeDasharray="5 3" />
            <text x={W - padR - 4} y={Y(cutH) - 4} textAnchor="end" style={{ fontSize: 11, fontWeight: 600, paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }} fill="var(--amber, #e8900c)">cut · k = {k} · drag</text>
            <rect x={padL} y={Y(cutH) - 7} width={W - padL - padR} height={14} fill="transparent" style={{ cursor: 'ns-resize' }} data-testid="dendrogram-cut-handle"
              onPointerDown={e => { drag.current = true; e.currentTarget.setPointerCapture(e.pointerId) }} onPointerMove={onMove}
              onPointerUp={e => { drag.current = false; e.currentTarget.releasePointerCapture(e.pointerId) }} />
          </g>
        </svg>
      )}
    </div>
  )
}

function ProposeTable({ t, k, onK }: { t: TreeInfo; k: number; onK: (k: number) => void }) {
  const rows = t.propose.by_k
  return (
    <details data-testid="tree-propose">
      <summary className="muted" style={{ cursor: 'pointer', fontSize: 11.5 }}>the proposal per k · {t.propose.suggestion_rule}</summary>
      <table className="sh-table" style={{ marginTop: 4 }}>
        <thead><tr><th>k</th><th className="r">silhouette</th><th className="r">real clusters</th><th>specks (under {t.propose.small_below})</th><th>sizes</th></tr></thead>
        <tbody>{rows.map(r => (
          <tr key={r.k} className={`clickable${r.k === k ? ' sel' : ''}`} onClick={() => onK(r.k)} data-testid={`tree-propose-${r.k}`}>
            <td>{r.k}{r.k === t.propose.suggested_k ? ' ★' : ''}</td><td className="r">{r.silhouette === null ? '—' : r.silhouette.toFixed(3)}</td>
            <td className="r">{r.effective_k}</td><td>{r.small_clusters.length ? r.small_clusters.join(', ') : '—'}</td>
            <td className="mono small">{Object.values(r.sizes).sort((a, b) => b - a).map(n => n.toLocaleString()).join(' · ')}</td>
          </tr>))}</tbody>
      </table>
      <div className="muted small">{t.propose.note}</div>
    </details>
  )
}

function ClusterTable({ cut, sel, onSel }: { cut: CutAt; sel: number | null; onSel: (c: number) => void }) {
  return (
    <div>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>The clusters at k = {cut.k}</h3><span className="sg">click one · every training window, sampled and assigned ({cut.n_clustered.toLocaleString()} + {cut.n_assigned.toLocaleString()})</span></div>
      <table className="sh-table" data-testid="tree-clusters">
        <thead><tr><th>cluster</th><th className="r">windows</th><th className="r">1 min</th><th className="r">10 min</th><th className="r">30 min</th><th>recordings</th><th className="r">median range (mV)</th><th className="r">event at (median)</th></tr></thead>
        <tbody>{cut.clusters.map(c => (
          <tr key={c.cluster} className={`clickable${sel === c.cluster ? ' sel' : ''}`} onClick={() => onSel(c.cluster)} data-testid={`tree-cluster-${c.cluster}`}>
            <td><b>{c.cluster}</b>{c.speck ? <span className="chip grey" style={{ marginLeft: 4, height: 16, fontSize: 9 }}>speck</span> : null}</td>
            <td className="r">{c.n.toLocaleString()}</td>
            <td className="r">{scaleOf(c.scales, '1').toLocaleString()}</td><td className="r">{scaleOf(c.scales, '10').toLocaleString()}</td><td className="r">{scaleOf(c.scales, '30').toLocaleString()}</td>
            <td className="mono small">{Object.entries(c.recordings).map(([r, n]) => `${r.replace(/\.mat$/, '')} ${n.toLocaleString()}`).join(' · ')}</td>
            <td className="r">{c.median_range_mv === null ? '—' : fmtN(c.median_range_mv)}</td>
            <td className="r">{c.peak_frac_median === null ? '—' : c.peak_frac_median.toFixed(2)}</td>
          </tr>))}</tbody>
      </table>
      <div className="muted small">event at = where the window's largest excursion sits, 0 the start, 1 the end · a speck is under {cut.small_below.toLocaleString()} windows (the baseline's rule)</div>
    </div>
  )
}

/* ---------------- one card per cluster at the cut (the researcher, 2026-10-06) ----------------
 * EVERY cluster at the current cut gets a card — 24 at k = 24 — redrawn when the cut moves, read from the kept tree
 * (`/api/shape/trees/{key}/cards`); nothing is re-run. A card that cannot be drawn is a red card. */
function CardStrip({ tkey, k, sel, onSel }: { tkey: string; k: number; sel: number | null; onSel: (c: number) => void }) {
  const [cards, setCards] = useState<Cards | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    setErr(null)
    getClusterCards(tkey, k).then(c => { if (alive) setCards(c) }).catch(e => { if (alive) { setCards(null); setErr(errText(e)) } })
    return () => { alive = false }
  }, [tkey, k])
  if (err) return <div className="error-card" data-testid="tree-cards-error"><h3>the clusters at k = {k} could not be drawn</h3><div className="mono small">{err}</div></div>
  if (!cards || cards.k !== k) return <div className="muted mono small" data-testid="tree-cards-loading">drawing the {k} clusters at this cut…</div>
  return (
    <div>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>What each cluster looks like at k = {cards.k}</h3><span className="sg">{cards.cards.length} cards · the medoid (brown) and {cards.n_members} members each · click a card for the cluster · {cards.note}</span></div>
      <div className="sh-cards" data-testid="tree-cards" data-k={cards.k} data-n={cards.cards.length}>
        {cards.cards.map(c => <Guard key={c.cluster} label={`the card of cluster ${c.cluster}`}><Card c={c} on={sel === c.cluster} onSel={onSel} /></Guard>)}
      </div>
    </div>
  )
}

function Card({ c, on, onSel }: { c: ClusterCard; on: boolean; onSel: (c: number) => void }) {
  if (c.error || !c.medoid) return <div className="error-card sh-card-one" data-testid={`tree-card-${c.cluster}`}><h3>cluster {c.cluster}</h3><div className="mono small">{c.error ?? 'no medoid'}</div></div>
  return (
    <button type="button" className={`sh-card-one${on ? ' on' : ''}`} onClick={() => onSel(c.cluster)} data-testid={`tree-card-${c.cluster}`} title={`cluster ${c.cluster} · ${c.n.toLocaleString()} windows`}>
      <div className="cap"><b>{c.cluster}</b> · {c.n.toLocaleString()} · {Object.entries(c.scales ?? {}).map(([s, n]) => `${s}m ${n}`).join(' ')}</div>
      <Spark v={c.medoid.shape} w={150} h={46} colour="#b35900" />
      <div className="mini-row">{(c.members ?? []).map(m => <Spark key={m.row} v={m.shape} w={36} h={22} colour="var(--text)" />)}</div>
    </button>
  )
}

/* ---------------- one cluster ---------------- */
function Spark({ v, w = 140, h = 44, band, colour = 'var(--text)', testid }: { v: number[]; w?: number; h?: number; band?: { lo: number[]; hi: number[] }; colour?: string; testid?: string }) {
  const all = band ? [...band.lo, ...band.hi, ...v] : v
  const lo = Math.min(...all), hi = Math.max(...all)
  const sy = (y: number) => h - 2 - (y - lo) / ((hi - lo) || 1) * (h - 4)
  const sx = (i: number) => 1 + i / Math.max(1, v.length - 1) * (w - 2)
  return (
    <svg width={w} height={h} data-testid={testid}>
      {band && <polygon points={[...band.hi.map((y, i) => `${sx(i)},${sy(y)}`), ...band.lo.map((y, i) => `${sx(band.lo.length - 1 - i)},${sy(band.lo[band.lo.length - 1 - i])}`)].join(' ')} fill="#cfe0fb" />}
      <polyline points={v.map((y, i) => `${sx(i)},${sy(y)}`).join(' ')} fill="none" stroke={colour} strokeWidth={1.1} />
    </svg>
  )
}

const where = (w: DetailWindow) => `${w.source_file.replace(/\.mat$/, '')} CH${w.channel + 1} · ${(w.start / w.fs / 3600).toFixed(2)} h · ${w.scale_min} min`

function WindowCard({ w, medoid }: { w: DetailWindow; medoid?: boolean }) {
  return (
    <div className={`sh-mini${medoid ? ' medoid' : ''}`} data-testid={medoid ? 'cluster-medoid' : 'cluster-member'}>
      <div className="cap" title={where(w)}>{medoid ? 'MEDOID · ' : ''}{where(w)}</div>
      {w.raw_mv ? <Spark v={w.raw_mv} w={medoid ? 300 : 140} h={medoid ? 80 : 40} colour="var(--text)" /> : <div className="muted small">no raw trace</div>}
      <div className="cap">{w.raw_range_mv === null ? 'range unmeasured' : `range ${fmtN(w.raw_range_mv)} ${w.unit ?? ''}`} · event at {w.peak_frac === null ? '—' : w.peak_frac.toFixed(2)}</div>
      <button className="btn sm ghost" style={{ padding: '0 4px', height: 18, fontSize: 10 }} onClick={() => navigate(`explore/signal/${w.recording_id}`)} data-testid="member-open-explore" title="open this window's channel in Explore">open in Explore ↗</button>
    </div>
  )
}

function ClusterPanel({ tkey, k, c }: { tkey: string; k: number; c: number }) {
  const [d, setD] = useState<ClusterDetail | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    setD(null); setErr(null)
    getClusterDetail(tkey, k, c).then(x => { if (alive) setD(x) }).catch(e => { if (alive) setErr(errText(e)) })
    return () => { alive = false }
  }, [tkey, k, c])
  const band = useMemo(() => d ? { lo: d.mean.map((m, i) => m - d.sd[i]), hi: d.mean.map((m, i) => m + d.sd[i]) } : null, [d])
  if (err) return <div className="error-card" data-testid="cluster-error"><h3>cluster {c} at k = {k} cannot be drawn</h3><div className="mono small">{err}</div></div>
  if (!d) return <div className="muted mono small" data-testid="cluster-loading">reading cluster {c}…</div>
  const a = d.amplitude_mv
  const peakMax = Math.max(1, ...d.peak_position_hist)
  return (
    <div className="card card-pad" data-testid="cluster-panel" style={{ background: 'var(--bg)' }}>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Cluster {d.cluster} at k = {d.k}</h3>
        <span className="sg">{d.n.toLocaleString()} windows · {d.n_in_sample.toLocaleString()} in the tree · {d.n_assigned.toLocaleString()} assigned</span></div>
      <div className="row" style={{ gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <WindowCard w={d.medoid} medoid />
        <div>
          <div className="muted small">mean normalised shape ± 1 sd · all {d.n.toLocaleString()} members</div>
          <Spark v={d.mean} band={band ?? undefined} w={260} h={80} colour="var(--blue, #0a84ff)" testid="cluster-mean" />
        </div>
        <div className="stack" style={{ gap: 4, minWidth: 220 }}>
          <div className="mono small" data-testid="cluster-scales">scales · {d.scales.map(s => `${s.scale_min} min ${s.n.toLocaleString()}`).join(' · ')}</div>
          <div className="mono small" data-testid="cluster-recordings">recordings · {d.recordings.map(r => `${r.recording.replace(/\.mat$/, '')} ${r.n.toLocaleString()}`).join(' · ')}</div>
          <div className="mono small" data-testid="cluster-amplitude">raw range · {a.min === null ? 'unmeasured' : `${fmtN(a.min)} … ${fmtN(a.max!)} mV (median ${fmtN(a.median!)}, middle half ${fmtN(a.q25!)}–${fmtN(a.q75!)})`}</div>
          <div className="mono small">channels · {d.channels.length} ({d.channels.slice(0, 6).map(x => `CH${x.channel + 1}`).join(', ')}{d.channels.length > 6 ? ', …' : ''})</div>
          <div className="muted small">where the event sits (0 start → 1 end)</div>
          <svg width={200} height={30} data-testid="cluster-peak-hist">{d.peak_position_hist.map((n, i) => <rect key={i} x={i * 20} y={30 - n / peakMax * 28} width={18} height={n / peakMax * 28} fill="#9aa1ab" />)}</svg>
          <div className="muted small">{d.medoid.rule}</div>
        </div>
      </div>
      <div className="bp-card-title" style={{ marginTop: 10 }}><h3 style={{ fontSize: 12 }}>{d.members.length} random members</h3><span className="sg">seed {d.members_seed} · raw traces in mV, each on its own y</span></div>
      <div className="sh-cluster-grid" data-testid="cluster-members">{d.members.map(w => <WindowCard key={w.row} w={w} />)}</div>
    </div>
  )
}

/* ---------------- the mapping table ----------------
 * It follows the cut on the page (the researcher, 2026-10-06): its rows are the clusters at the PREVIEWED k, and an
 * edit writes both the block's k and its mapping at that k — so mapping a new cut needs no re-run first. The run after
 * re-uses the kept tree and records the Grouping at that k. Frozen once a run on the pool has a test score. */
function MappingTable({ q, t, cut, frozen }: { q: ProcessProps; t: TreeInfo; cut: CutAt | null; frozen: Frozen | null }) {
  const m = t.mapping
  const k = cut?.k ?? t.k
  const rows = cut ? cut.clusters : t.clusters
  const [draft, setDraft] = useState<Record<string, MappingEntry>>(() => (m.k === k || m.k === null ? m.clusters : {}))
  useEffect(() => { setDraft(m.k === k || m.k === null ? m.clusters : {}) }, [t.key, k, JSON.stringify(m)])   // eslint-disable-line react-hooks/exhaustive-deps
  const locked = !!frozen
  const write = (next: Record<string, MappingEntry>) => {
    setDraft(next)
    if (k !== t.k_param) q.setParam('k', k)
    q.setParam('mapping', JSON.stringify({ k, clusters: next }))
  }
  const set = (c: number, patch: Partial<MappingEntry>) => write({ ...draft, [String(c)]: { name: draft[String(c)]?.name ?? '', class: draft[String(c)]?.class ?? null, ...patch } })
  const done = rows.filter(c => draft[String(c.cluster)]?.class).length
  const stateWords: Record<string, string> = { none: 'no mapping yet', partial: 'partly mapped', complete: 'every cluster mapped', stale: `made at k = ${m.k}; the run's cut is k = ${t.k}` }
  return (
    <div className="sh-mapping" data-testid="mapping-table" data-k={k}>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Mapping · each cluster at k = {k} → interesting / not</h3>
        <span className="sg" data-testid="mapping-state">{done} of {rows.length} mapped at this cut · the last run: {stateWords[t.mapping_state] ?? t.mapping_state}{k !== t.k ? ` · editing writes k = ${k} into the block (re-run to record it)` : ''}</span></div>
      {locked && <div className="muted small" data-testid="mapping-frozen">frozen by run {frozen!.run_id}: names can change, classes and the cut cannot</div>}
      <table className="sh-table">
        <thead><tr><th>cluster</th><th className="r">windows</th><th>name (optional)</th><th>class</th></tr></thead>
        <tbody>{rows.map(c => {
          const e = draft[String(c.cluster)]
          return (
            <tr key={c.cluster} data-testid={`mapping-row-${c.cluster}`}>
              <td><b>{c.cluster}</b>{c.speck ? <span className="chip grey" style={{ marginLeft: 4, height: 16, fontSize: 9 }}>speck</span> : null}</td>
              <td className="r">{c.n.toLocaleString()}</td>
              <td><input value={e?.name ?? ''} placeholder="e.g. sharkfin" onChange={ev => setDraft({ ...draft, [String(c.cluster)]: { name: ev.target.value, class: e?.class ?? null } })}
                onBlur={ev => set(c.cluster, { name: ev.target.value })} data-testid={`mapping-name-${c.cluster}`} disabled={locked && k !== frozen!.k} /></td>
              <td><select value={e?.class ?? ''} onChange={ev => set(c.cluster, { class: (ev.target.value || null) as MappingEntry['class'] })} data-testid={`mapping-class-${c.cluster}`} disabled={locked}>
                <option value="">—</option><option value="interesting">{CLASS_WORDS.interesting}</option><option value="not_interesting">{CLASS_WORDS.not_interesting}</option>
              </select></td>
            </tr>
          )
        })}</tbody>
      </table>
      <div className="muted small">the mapping is this block's <code>mapping</code> parameter — saved with the template, read by Models › Launch, frozen once a run on this pool has a test score · no human label takes part in forming the clusters</div>
    </div>
  )
}
