/* Grouping view (fixup-h). Minimum: clusters over time, cluster sizes, and ONE EXEMPLAR DRAWN PER CLUSTER.
 * Thumbnail: the distribution of clusters over time as a heatmap — one row per cluster, time bucketed along the
 * shared axis, each cell the share of that bucket's windows the cluster holds. A strip of one colour per window
 * shows which cluster a window is in; the heatmap shows when a cluster is ACTIVE, which is the question a
 * glance at a chain row is asking.
 *
 * An exemplar is a member window — the one nearest its cluster's centroid — and never an average: a mean of
 * windows is a waveform the recording does not contain. Each is drawn on its own measured y with a scale bar. */
import { useEffect, useMemo, useState } from 'react'
import type { FamilyRow, FamilySummary, GroupingPayload } from '../../api'
import { measuredDomain } from '../../charts/domain'
import { About, Bars, EventTrace, InfoTip, ScaleBar, type SlideTrace } from '../../kit'
import { fmtDuration, fmtHours } from '../../state'
import { CAT9 } from './EncodingView'
import { Empty, loadWindow, type ViewCtx } from './common'

export const clusterColour = (p: GroupingPayload, id: number) => p.class_names
  ? (id < 0 ? '#b9bec7' : CAT9[id % 9])          // a labelled Grouping: excluded is grey, the classes keep their colour
  : p.families ? familyColour(id)                 // w2-f: a families Grouping: -1 (in no family) is grey, F keeps its colour
    // W3-F: -1 is "no label" (catalogue.cluster's left-out windows, snippets' unlabelled) — grey, never a cluster's
    // colour; `label_base` is the lowest REAL label (serialize.py), so a -1 does not shift every cluster's colour
    : id < 0 ? '#b9bec7' : CAT9[(((id - p.label_base) % 9) + 9) % 9]
/** One colour per family, shared by Shape families' strip and Event families' events; -1 (in no family) grey. */
export const familyColour = (f: number) => (f < 0 ? '#b9bec7' : CAT9[(((f - 1) % 9) + 9) % 9])
/** What a group is called: a labelled Grouping's class name (fixup-aa: `catalogue.manual_labels`), else `cluster N`. */
export const groupName = (p: GroupingPayload, id: number) => p.class_names?.[String(id)] ?? `cluster ${id}`
const BUCKET_PX = 10

export function GroupingView({ p, ctx }: { p: GroupingPayload; ctx: ViewCtx }) {
  const [r0, r1] = ctx.x.range()
  const heat = useMemo(() => {
    if (!p.strip) return null
    const cols = Math.max(1, Math.floor((r1 - r0) / BUCKET_PX))
    const ta = ctx.x.invert(r0), tb = ctx.x.invert(r1)
    const idOf = new Map(p.clusters.map((c, i) => [c.id, i]))
    const counts = p.clusters.map(() => new Array(cols).fill(0))
    const totals = new Array(cols).fill(0)
    p.strip.starts_s.forEach((s, i) => {
      const lab = p.labels[i]
      const row = lab === undefined ? undefined : idOf.get(lab)
      const c = Math.floor((((s + p.strip!.length_s / 2) - ta) / (tb - ta)) * cols)
      if (row === undefined || c < 0 || c >= cols) return
      counts[row][c]++; totals[c]++
    })
    return { cols, counts, totals, w: (r1 - r0) / cols }
  }, [p, r0, r1, ctx.x])
  if (!p.strip || !heat) return <Empty text={`${p.summary} · no time to draw against (the WindowSet this grouping was computed over was not seen)`} />
  const stripH = ctx.interactive ? 26 : 0
  const top = stripH + (ctx.interactive ? 6 : 0)
  const rowH = (ctx.height - top - 2) / Math.max(1, p.clusters.length)
  const cellW = Math.max(1, ctx.x(ctx.t0 + p.strip.length_s) - ctx.x(ctx.t0) - 0.5)
  return (
    <svg width={ctx.width} height={ctx.height} data-render="grouping" data-clusters={p.clusters.length}>
      {ctx.interactive && (
        <g data-testid="cluster-strip">
          {p.strip.starts_s.map((s, i) => {
            const lab = p.labels[i]; if (lab === undefined) return null
            return <rect key={i} x={ctx.x(s)} y={0} width={cellW} height={stripH} fill={clusterColour(p, lab)} opacity={0.9}><title>{`window ${i + 1} · ${groupName(p, lab)}`}</title></rect>
          })}
        </g>
      )}
      <g data-testid="cluster-heatmap">
        {p.clusters.map((c, row) => (
          <g key={c.id} transform={`translate(0,${top + row * rowH})`}>
            <rect x={r0} y={0} width={r1 - r0} height={Math.max(1, rowH - 1.5)} fill="var(--grey-100)" />
            {heat.counts[row].map((n, col) => n ? (
              <rect key={col} x={r0 + col * heat.w} y={0} width={heat.w + 0.4} height={Math.max(1, rowH - 1.5)} fill={clusterColour(p, c.id)} fillOpacity={0.15 + 0.85 * (n / heat.totals[col])}>
                <title>{`${groupName(p, c.id)} · ${n} of the ${heat.totals[col]} windows in this stretch`}</title>
              </rect>
            ) : null)}
            <text x={r0 + 4} y={Math.min(rowH - 3, 11)} style={{ fill: 'var(--text-2)', paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{p.class_names ? groupName(p, c.id) : c.id} · {c.count}</text>
          </g>
        ))}
      </g>
      <text x={ctx.width - 6} y={ctx.height - 4} textAnchor="end" fill="var(--muted)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>
        {ctx.interactive ? '' : p.coverage ? `${p.coverage.labelled.toLocaleString()} labelled of ${p.n.toLocaleString()}` : `${p.k} clusters${p.linkage ? ` · ${p.linkage}` : ''}`}{p.capped ? ` · the first ${(p.n_shown ?? p.labels.length).toLocaleString()} of ${p.n.toLocaleString()} windows` : ''}
      </text>
    </svg>
  )
}

export function ClusterSizes({ p }: { p: GroupingPayload }) {
  return (
    <div data-testid="cluster-sizes">
      <Bars categories={p.clusters.map(c => groupName(p, c.id))} series={[{ key: 'n', label: 'windows', colour: 'var(--blue)', values: p.clusters.map(c => c.count) }]}
        height={150} legend={false} yLabel="windows" />
    </div>
  )
}

function Exemplar({ p, ex, recordingId, unit }: { p: GroupingPayload; ex: NonNullable<GroupingPayload['exemplars']>[number]; recordingId: number; unit: string }) {
  const [tr, setTr] = useState<SlideTrace | null>(null)
  useEffect(() => {
    let alive = true
    setTr(null)
    loadWindow(recordingId, ex.start_s, ex.start_s + ex.length_s, 500).then(t => { if (alive) setTr(t) }, e => { if (alive) setTr({ t: [], v: [], decimated: false, nSource: 0, error: String(e?.message ?? e) }) })
    return () => { alive = false }
  }, [recordingId, ex.start_s, ex.length_s])
  const dom = tr ? measuredDomain(tr.v) : null
  const H = 70
  const colour = clusterColour(p, ex.cluster)
  return (
    <div className="k-slide" style={{ borderColor: colour }} data-testid={`exemplar-${ex.cluster}`}>
      <div className="r1"><b style={{ color: colour }}>{groupName(p, ex.cluster)}</b><span>{ex.n} windows</span></div>
      <div style={{ display: 'flex', gap: 2 }}>
        {!tr ? <div className="skeleton" style={{ height: H, flex: 1, borderRadius: 5 }} />
          : tr.error || !dom ? <div className="k-slide-note" style={{ height: H }}>{tr.error ?? 'no finite samples in this window'}</div>
            : <><EventTrace trace={tr} domain={dom} event={{ id: `c${ex.cluster}`, title: `${groupName(p, ex.cluster)} exemplar`, sort: {} }} height={H} colour={colour} /><ScaleBar domain={dom} height={H} unit={unit} /></>}
      </div>
      <div className="facts">window {ex.window + 1} · {fmtHours(ex.start_s, 3)} + {fmtDuration(ex.length_s)}</div>
      {tr && !tr.error && <div className="res">{tr.decimated ? `${tr.nSource.toLocaleString()} samples · min/max envelope` : `${tr.nSource.toLocaleString()} samples · every one drawn`}</div>}
    </div>
  )
}

/** One member window per cluster, drawn from the source channel. */
export function ClusterExemplars({ p, recordingId, unit }: { p: GroupingPayload; recordingId: number; unit: string }) {
  const ex = p.exemplars ?? []
  if (!ex.length) return <div className="muted mono small" data-testid="cluster-exemplars">no exemplar to draw: the WindowSet this grouping was computed over is not at hand, so no cluster has a window to show</div>
  return (
    <div data-testid="cluster-exemplars">
      <div className="bp-card-title" style={{ marginTop: 10 }}>
        <h3 style={{ fontSize: 13 }}>{p.class_names ? 'One exemplar per class' : 'One exemplar per cluster'}</h3>
        <span className="sg">a member window, never an average · each on its own y, sizes on the scale bars</span>
        <InfoTip title="Which window">{ex[0].rule}. The trace is the source channel over that window, as recorded.</InfoTip>
      </div>
      {/* w2-f: the block named these members itself (the snippet, a family's medoid) — its rule is the caption */}
      {ex[0].by === 'block' && <div className="mono small" data-testid="exemplar-rule" style={{ color: 'var(--text-2)', marginBottom: 4 }}>chosen by the block: {ex[0].rule}</div>}
      {/* fix 1 (critic 4): a label the block named no exemplar for is said, per cluster — not a silent gap */}
      {p.clusters.filter(c => (c as { exemplar_note?: string }).exemplar_note).map(c => <div key={c.id} className="mono small muted" data-testid="exemplar-none">cluster {c.id}: {(c as { exemplar_note?: string }).exemplar_note}</div>)}
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(5, ex.length)}, minmax(0, 1fr))`, gap: 8 }}>
        {ex.map(e => <Exemplar key={e.cluster} p={p} ex={e} recordingId={recordingId} unit={unit} />)}
      </div>
    </div>
  )
}

/* ---------------- w2-f: the families' table (Shape families, Event families) ---------------- */
const f2 = (v: number | null | undefined) => (v === null || v === undefined || !Number.isFinite(v) ? '—' : v.toFixed(2))

/** W3-G decision 15: which null(s) passed a family — the quiet stretches, the trend-kept surrogates, or both. */
const passedWords = (passed: string[]) => passed.length > 1 ? 'both'
  : /quiet/.test(passed[0] ?? '') ? 'quiet stretches' : /trend/.test(passed[0] ?? '') ? 'trend-kept' : (passed[0] ?? '')

/** A family's verdict against its method's null, as the block made it: amber "no better than noise", grey
 *  "untested" (Ward draws no null), green "beyond noise" only when `confident` is true — with WHICH null passed it
 *  (`passed_by`) and, when the quiet stretches could not be used, the fallback on the badge itself. Never derived
 *  here. The grey "null not trusted" branch is DORMANT (W3-F): it fired for k-Shape, whose `null_caveat` is None
 *  since W3-G gave it a trend-kept null; it is kept for a method that sets `confident` None with a caveat again. */
export function FamilyBadge({ f }: { f: FamilyRow }) {
  if (f.noise_like) return <span className="k-badge t-amber" data-testid={`family-badge-${f.family}`} data-verdict="noise-like" title={f.why ?? ''}>no better than noise</span>
  if (!f.tested) return <span className="k-badge t-grey" data-testid={`family-badge-${f.family}`} data-verdict="untested" title={f.why ?? 'this method draws no noise null'}>untested</span>
  if (f.confident === null) return <span className="k-badge t-grey" data-testid={`family-badge-${f.family}`} data-verdict="null-not-trusted" title={f.null_caveat ?? f.why ?? ''}><span data-testid="family-null-not-trusted">null not trusted</span></span>
  const passed = f.passed_by ?? []
  const fellBack = !!f.background?.reason && !(f.null_kind ?? '').startsWith('quiet')
  return (
    <span className="k-badge t-green" data-testid={`family-badge-${f.family}`} data-verdict="confident" title={f.why ?? ''}>
      beyond noise{passed.length ? <span data-testid={`family-passed-by-${f.family}`}> ({passedWords(passed)})</span> : null}
      {fellBack && <span data-testid={`family-fallback-${f.family}`}> · judged on trend-kept noise only: {f.background?.reason}</span>}
    </span>
  )
}

/** σ² first, as a NUMBER with its ratio to its own null (decision 3: no badge — eq. 17 carries the verdict). */
function FamilySquaredCell({ f }: { f: FamilyRow }) {
  const sq = (f.svd_entropy_variants ?? []).find(x => x.name === 'squared') ?? null
  const ratio = sq?.squared_vs_null_ratio
  return (
    <span data-testid={`family-squared-${f.family}`} title={sq?.note ?? 'σ²-weighted SVD entropy (share of variance): reported, not judged'}>
      <b className="mono">{f2(sq ? sq.score : f.svd_entropy_squared_norm)}</b>
      <span className="muted"> · noise {f2(sq ? sq.null_median : f.svd_entropy_squared_null_median)}{ratio != null ? ` · ${ratio.toFixed(2)}× p05` : ''}</span>
      {f.top_share !== null ? <span className="muted"> · main shape {Math.round(f.top_share * 100)} %</span> : null}
    </span>
  )
}

/** eq. 17 beside its null; the verdict is the block's `svd_entropy_beyond_noise` (svd_entropy's own margin). */
function FamilyCoherenceCell({ f }: { f: FamilyRow }) {
  const v = f.svd_entropy_beyond_noise
  return (
    <span data-testid={`family-coherence-${f.family}`} data-verdict={v === true ? 'beyond' : v === false ? 'noise' : 'none'} title={f.svd_entropy_why ?? f.svd_entropy_rule ?? ''}>
      <b className="mono">{f2(f.svd_entropy_norm)}</b>
      <span className="muted"> · noise {f2(f.svd_entropy_null_median)} (p05 {f2(f.svd_entropy_null_p05)})</span>
      {v === false && <span className="k-badge t-amber" style={{ marginLeft: 4 }} title={`not below ${f.svd_entropy_null_margin ?? 0.9} × the noise's p05 (a placeholder margin)`}>no more coherent than noise</span>}
      {v === true && <span className="muted"> · beyond noise{f.svd_entropy_passed_by?.length ? ` (${passedWords(f.svd_entropy_passed_by)})` : ''}</span>}
      {(v === null || v === undefined) && <span className="muted"> · {f.coherence_reason ?? 'no null'}</span>}
    </span>
  )
}

/** The quiet-stretch null's context, in one line: how much background, borrowed windows, overlap with detections. */
function FamilyNullContext({ f }: { f: FamilyRow }) {
  const bg = f.background ?? f.svd_entropy_background ?? null
  const bits = [
    f.background_s != null ? `${Math.round(f.background_s).toLocaleString()} s quiet` : bg?.background_s != null ? `${Math.round(bg.background_s).toLocaleString()} s quiet` : '',
    bg?.n_borrowed ? `${bg.n_borrowed} borrowed` : '',
    bg?.detection_overlap_share != null ? `${Math.round(bg.detection_overlap_share * 100)} % overlap a detection` : '',
    f.svd_entropy_background?.family_scored_on ? `scored on ${f.svd_entropy_background.family_scored_on}` : '',
  ].filter(Boolean)
  return bits.length ? <span className="muted" data-testid={`family-null-context-${f.family}`}>{bits.join(' · ')}</span> : <span className="muted">—</span>
}

/** Every family the block made, one row each, with every number on the face; the block's warnings and notes under it. */
export function FamilyTable({ families, summary, unit = 'members' }: { families: FamilyRow[]; summary?: FamilySummary; unit?: string }) {
  const th = { textAlign: 'left' as const, padding: '2px 8px', fontWeight: 500, color: 'var(--text-2)' }
  const td = { padding: '2px 8px', verticalAlign: 'top' as const }
  const frac = (v: number | null | undefined) => (v === null || v === undefined ? 'n/a' : `${Math.round(v * 100)} %`)
  return (
    <div data-testid="family-table" style={{ marginTop: 10 }}>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Families against noise</h3>
        <span className="sg">{summary?.method ?? ''}{summary ? ` · placed ${frac(summary.fraction_placed)} · confident ${frac(summary.fraction_confident)}${summary.n_noise_like ? ` · ${summary.n_noise_like} no better than noise` : ''}` : ''}</span>
        <InfoTip title="What the badge says">Each family is tested against noise: the recording's own quiet stretches (windows of the members' length cut where no event lies) and trend-kept phase-randomised surrogates; a family passes on either, and the badge says which. Coherence: 0 = all members the same shape, 1 = no shared shape. σ² (share of variance) leads, as a number against its own null; eq. 17 beside it carries the verdict, which needs the score clearly below the noise's.</InfoTip>
      </div>
      {families.length === 0
        ? <div className="mono small muted" data-testid="family-table-empty">no family was made{summary?.omitted && Object.keys(summary.omitted).length ? ` · left out: ${Object.entries(summary.omitted).map(([k, n]) => `${n} ${k.replace(/_/g, ' ')}`).join(' · ')}` : ''}</div>
        : <table className="mono" style={{ borderCollapse: 'collapse', fontSize: 11.5 }}>
          <thead><tr><th style={th}>family</th><th style={th}>{unit}</th><th style={th}>verdict · which null passed</th><th style={th}>σ² · its noise · main shape</th><th style={th}>eq. 17 beside its null (the verdict)</th><th style={th}>the null's background</th></tr></thead>
          <tbody>{families.map(f => (
            <tr key={f.family} data-testid={`family-row-${f.family}`}>
              <td style={td}><i style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 2, background: familyColour(f.family), marginRight: 5 }} />F{f.family}{f.library_label ? ` (${f.library_label})` : ''}</td>
              <td style={{ ...td, textAlign: 'right' }}>{f.size.toLocaleString()}</td>
              <td style={td}><FamilyBadge f={f} /></td>
              <td style={td}><FamilySquaredCell f={f} /></td>
              <td style={td}><FamilyCoherenceCell f={f} /></td>
              <td style={td}><FamilyNullContext f={f} /></td>
            </tr>
          ))}</tbody>
        </table>}
      {(summary?.warnings ?? []).map((w, i) => <div key={i} className="mono small" style={{ color: 'var(--amber-700, #b76a00)' }} data-testid="family-warning">{w}</div>)}
      {/* polish: the method's notes are how the table was made, one click away; the warnings above stay on the face */}
      {(summary?.notes ?? []).length > 0 && <About label={`notes on this table (${(summary?.notes ?? []).length})`} testid="family-notes-about">
        {(summary?.notes ?? []).map((w, i) => <div key={`n${i}`} className="mono small" data-testid="family-note">{w}</div>)}
      </About>}
    </div>
  )
}
