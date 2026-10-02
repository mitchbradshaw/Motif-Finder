/* Grouping view (fixup-h). Minimum: clusters over time, cluster sizes, and ONE EXEMPLAR DRAWN PER CLUSTER.
 * Thumbnail: the distribution of clusters over time as a heatmap — one row per cluster, time bucketed along the
 * shared axis, each cell the share of that bucket's windows the cluster holds. A strip of one colour per window
 * shows which cluster a window is in; the heatmap shows when a cluster is ACTIVE, which is the question a
 * glance at a chain row is asking.
 *
 * An exemplar is a member window — the one nearest its cluster's centroid — and never an average: a mean of
 * windows is a waveform the recording does not contain. Each is drawn on its own measured y with a scale bar. */
import { useEffect, useMemo, useState } from 'react'
import type { GroupingPayload } from '../../api'
import { measuredDomain } from '../../charts/domain'
import { Bars, EventTrace, InfoTip, ScaleBar, type SlideTrace } from '../../kit'
import { fmtDuration, fmtHours } from '../../state'
import { CAT9 } from './EncodingView'
import { Empty, loadWindow, type ViewCtx } from './common'

export const clusterColour = (p: GroupingPayload, id: number) => CAT9[(((id - p.label_base) % 9) + 9) % 9]
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
            return <rect key={i} x={ctx.x(s)} y={0} width={cellW} height={stripH} fill={clusterColour(p, lab)} opacity={0.9}><title>{`window ${i + 1} · cluster ${lab}`}</title></rect>
          })}
        </g>
      )}
      <g data-testid="cluster-heatmap">
        {p.clusters.map((c, row) => (
          <g key={c.id} transform={`translate(0,${top + row * rowH})`}>
            <rect x={r0} y={0} width={r1 - r0} height={Math.max(1, rowH - 1.5)} fill="var(--grey-100)" />
            {heat.counts[row].map((n, col) => n ? (
              <rect key={col} x={r0 + col * heat.w} y={0} width={heat.w + 0.4} height={Math.max(1, rowH - 1.5)} fill={clusterColour(p, c.id)} fillOpacity={0.15 + 0.85 * (n / heat.totals[col])}>
                <title>{`cluster ${c.id} · ${n} of the ${heat.totals[col]} windows in this stretch`}</title>
              </rect>
            ) : null)}
            <text x={r0 + 4} y={Math.min(rowH - 3, 11)} style={{ fill: 'var(--text-2)', paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{c.id} · {c.count}</text>
          </g>
        ))}
      </g>
      <text x={ctx.width - 6} y={ctx.height - 4} textAnchor="end" fill="var(--muted)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>
        {ctx.interactive ? '' : `${p.k} clusters${p.linkage ? ` · ${p.linkage}` : ''}`}{p.capped ? ` · the first ${(p.n_shown ?? p.labels.length).toLocaleString()} of ${p.n.toLocaleString()} windows` : ''}
      </text>
    </svg>
  )
}

export function ClusterSizes({ p }: { p: GroupingPayload }) {
  return (
    <div data-testid="cluster-sizes">
      <Bars categories={p.clusters.map(c => `cluster ${c.id}`)} series={[{ key: 'n', label: 'windows', colour: 'var(--blue)', values: p.clusters.map(c => c.count) }]}
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
      <div className="r1"><b style={{ color: colour }}>cluster {ex.cluster}</b><span>{ex.n} windows</span></div>
      <div style={{ display: 'flex', gap: 2 }}>
        {!tr ? <div className="skeleton" style={{ height: H, flex: 1, borderRadius: 5 }} />
          : tr.error || !dom ? <div className="k-slide-note" style={{ height: H }}>{tr.error ?? 'no finite samples in this window'}</div>
            : <><EventTrace trace={tr} domain={dom} event={{ id: `c${ex.cluster}`, title: `cluster ${ex.cluster} exemplar`, sort: {} }} height={H} colour={colour} /><ScaleBar domain={dom} height={H} unit={unit} /></>}
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
        <h3 style={{ fontSize: 13 }}>One exemplar per cluster</h3>
        <span className="sg">a member window, never an average · each on its own y, sizes on the scale bars</span>
        <InfoTip title="Which window">{ex[0].rule}. The trace is the source channel over that window, as recorded.</InfoTip>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(5, ex.length)}, minmax(0, 1fr))`, gap: 8 }}>
        {ex.map(e => <Exemplar key={e.cluster} p={p} ex={e} recordingId={recordingId} unit={unit} />)}
      </div>
    </div>
  )
}
