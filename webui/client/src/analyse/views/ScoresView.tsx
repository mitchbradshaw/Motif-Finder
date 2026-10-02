/* Scores view (fixup-h). Thumbnail: the score curve alone. Settings page: the curve with THE SOURCE SIGNAL ABOVE
 * IT ON THE SAME X (a score is only readable against what it scored), the value histogram, and the threshold if
 * one exists — the cut of the block that consumes these scores, drawn as a level and never as a guess. */
import type { ScoresPayload } from '../../api'
import { EnvelopePath } from '../../charts/primitives'
import { makeY, type XScale } from '../../charts/scale'
import { axisUnit } from '../../charts/units'
import { Histogram } from '../../kit'
import { AxisLabels, CutLineH, Empty, finiteRange, fmtN, nearest, resolutionWords, useHoverT, type ViewCtx } from './common'

export function motifLabels(p: ScoresPayload): { t_s: number; v: number; label: string; kind: 'motif' | 'discord' }[] {
  const out: { t_s: number; v: number; label: string; kind: 'motif' | 'discord' }[] = []
  const low = p.top?.low ?? []
  const pair = low.length >= 2 && Math.abs(low[0].v - low[1].v) < 1e-6   // a motif pair has equal profile values at both ends
  low.forEach((m, i) => out.push({ ...m, kind: 'motif', label: pair ? (i === 0 ? 'M1a' : i === 1 ? 'M1b' : `M${i}`) : `M${i + 1}` }))
  ;(p.top?.high ?? []).forEach((d, i) => out.push({ ...d, kind: 'discord', label: `D${i + 1}` }))
  return out
}

/** What the numbers are. Only a matrix profile is a z-normalised distance; every other Scores is just a score. */
export const scoreWords = (p: ScoresPayload) => (p.m ? 'z-norm distance' : 'score')

export interface ScoreCut { value: number; label: string; onChange?: (v: number) => void }

/** The score axis: its own range, opened to zero when the scores are one-signed. */
export function scoreY(p: ScoresPayload, height: number, top = 14): XScale | null {
  const r = p.value_range ?? finiteRange(p.envelope.v)
  if (!r) return null
  return makeY(Math.min(0, r[0]), Math.max(0, r[1]), height, top, 4)
}

export function ScoresView({ p, ctx, cut, marks = true }: { p: ScoresPayload; ctx: ViewCtx; cut?: ScoreCut | null; marks?: boolean }) {
  const r = p.value_range ?? finiteRange(p.envelope.v)
  const [hover, handlers] = useHoverT(ctx.x)
  if (!r) return <Empty text="no finite scores" />
  // settings tier: the top third is the source signal on its own axis, the rest is the curve — one svg, one x
  const ghost = ctx.interactive && ctx.ghost && ctx.ghost.t.length ? ctx.ghost : null
  const sigH = ghost ? Math.round(ctx.height * 0.34) : 0
  const curveH = ctx.height - sigH
  const y = scoreY(p, curveH)!
  const gr = ghost ? finiteRange(ghost.v) : null
  const yG = gr ? makeY(gr[0], gr[1], sigH, 4, 6) : null
  const ms = marks ? motifLabels(p) : []
  const flat = !(r[1] > r[0])
  const readout = (() => {
    if (!ctx.interactive || hover === null || !p.envelope.t.length) return null
    const i = nearest(p.envelope.t, hover)
    const v = p.envelope.v[i]
    const px = ctx.x(p.envelope.t[i])
    return (
      <g pointerEvents="none" data-testid="scores-readout">
        <line x1={px} x2={px} y1={0} y2={ctx.height} stroke="var(--blue)" strokeOpacity={0.5} strokeDasharray="3 3" />
        {v !== null && <circle cx={px} cy={sigH + y(v)} r={2.6} fill="var(--blue)" />}
        <text x={Math.min(px + 6, ctx.width - 150)} y={sigH + 26} style={{ fill: 'var(--text-2)', paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{v === null ? 'no value (NaN)' : `${scoreWords(p)} ${fmtN(v)}`}</text>
      </g>
    )
  })()
  return (
    <svg width={ctx.width} height={ctx.height} data-render="scores" data-plot-box data-rule9="trace" data-flat={flat ? '1' : '0'} {...(ctx.interactive ? handlers : {})}>
      {ghost && yG && (
        <g data-testid="scores-source-signal">
          <EnvelopePath t={ghost.t} v={ghost.v} x={ctx.x} y={yG} stroke="var(--trace)" />
          <AxisLabels y={yG} values={[gr![1], gr![0]]} side="left" width={ctx.width} unit={axisUnit(ctx.ghostUnit)} />
          {/* a windowed score (a matrix profile) names its window: drawn to scale on the signal, at the lowest
              score and at its nearest neighbour */}
          {p.m && p.fs > 0 && ms.filter(m => m.label === 'M1a' || m.label === 'M1' || m.label === 'M1b').map(m => {
            const w = Math.max(2, ctx.x(m.t_s + p.m! / p.fs) - ctx.x(m.t_s)); const nn = m.label === 'M1b'
            return <rect key={m.label} x={ctx.x(m.t_s)} y={3} width={w} height={sigH - 6} fill={nn ? 'var(--band-annotated)' : 'var(--band-detected)'} stroke={nn ? 'var(--green)' : 'var(--blue)'} data-testid={`window-${m.label}`}><title>{`${nn ? 'nearest neighbour' : 'the window at the lowest score'} · m = ${(p.m! / p.fs).toFixed(0)} s (${p.m} samples), to scale`}</title></rect>
          })}
          <text x={ctx.width - 6} y={11} textAnchor="end" fill="var(--muted-2)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>the signal that was scored · same x{p.m ? ` · boxes: the window m = ${(p.m / p.fs).toFixed(0)} s, to scale` : ''}</text>
          <line x1={0} x2={ctx.width} y1={sigH} y2={sigH} stroke="var(--border)" />
        </g>
      )}
      <g transform={`translate(0,${sigH})`}>
        <g data-trace><EnvelopePath t={p.envelope.t} v={p.envelope.v} x={ctx.x} y={y} stroke="var(--blue)" testid="scores-path" /></g>
        {ms.map(m => {
          const px = ctx.x(m.t_s); const c = m.kind === 'motif' ? 'var(--green)' : 'var(--red)'
          return (
            <g key={m.label} data-testid={`mark-${m.label}`}>
              <line x1={px} x2={px} y1={12} y2={curveH} stroke={c} strokeOpacity={0.6} />
              <rect x={px - 12} y={1} width={24} height={11} rx={2} fill={c} />
              <text x={px} y={9.5} textAnchor="middle" fill="#fff" style={{ fontSize: 8.5, fontWeight: 600 }}>{m.label}</text>
            </g>
          )
        })}
        <AxisLabels y={y} values={[Math.max(0, r[1]), Math.min(0, r[0])]} side="left" width={ctx.width} />
        {cut && <CutLineH y={y} value={cut.value} onChange={cut.onChange} width={ctx.width} label={cut.label} testid="threshold-line" />}
        <text x={46} y={curveH - 4} fill="var(--muted-2)">{scoreWords(p)}{p.nan_tail ? ` · NaN tail ${p.nan_tail}` : ''}</text>
        {!ctx.hideKey && ms.length > 0 && (
          <g transform={`translate(${ctx.width - 6},${curveH - 5})`}>
            <text textAnchor="end" fill="var(--muted)"><tspan fill="var(--blue)">━</tspan> {p.m ? 'profile' : 'score'}   <tspan fill="var(--green)">●</tspan> lowest   <tspan fill="var(--red)">●</tspan> highest</text>
          </g>
        )}
      </g>
      {readout}
    </svg>
  )
}

/** The value histogram (the payload's own 40 bins), with the cut marked when there is one. */
export function ScoreHistogram({ p, cut, testid = 'score-histogram' }: { p: ScoresPayload; cut?: ScoreCut | null; testid?: string }) {
  const h = p.histogram
  if (!h) return <div className="muted mono small" data-testid={testid}>no finite value to bin</div>
  const bins = h.counts.map((count, i) => ({ x0: h.edges[i], x1: h.edges[i + 1], count }))
  const above = cut ? h.counts.reduce((a, c, i) => a + (h.edges[i] >= cut.value ? c : h.edges[i + 1] > cut.value ? c * ((h.edges[i + 1] - cut.value) / (h.edges[i + 1] - h.edges[i])) : 0), 0) : null
  return (
    <div data-testid={testid}>
      <Histogram bins={bins} height={130} colour="var(--blue-200)" highlightBin={cut ? b => b.x0 >= cut.value : undefined} highlightColour="var(--amber)"
        threshold={cut ? { value: cut.value, label: cut.label } : undefined} xLabel={scoreWords(p)} format={v => fmtN(v)} label={`${scoreWords(p)} values`} />
      <div className="muted mono small">{resolutionWords(p.envelope, p.fs)}{above !== null ? ` · ≈ ${Math.round(above).toLocaleString()} values above the cut` : ''}</div>
    </div>
  )
}
