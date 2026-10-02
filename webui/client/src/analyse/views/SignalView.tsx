/* Signal view (fixup-h). Minimum: BEFORE AND AFTER OVERLAID, the input grey beneath. All six Signal blocks are
 * preprocessing, so a detrend, a bandpass and an invert each used to draw as "a trace" and you could not see
 * what the block did.
 *
 * One axis or two. When the block leaves the scale alone (a low-pass: the output sits inside the input's range)
 * both are drawn on ONE axis, so the difference between them is the picture. When the block CHANGES the scale
 * (baseline removal takes a channel off a −447 mV offset; a normalise changes the unit) one axis would flatten
 * one of the two to a line, so both are drawn: the original on the left in grey, the new one on the right in
 * blue. The rule is measured, not declared per block: two axes when one shared axis would give either trace
 * less than `SHARE_MIN` of the plot's height.
 *
 * Nothing is resampled: the points are the server's min/max envelope (every sample when they fit), the note
 * says which, and samples 3 px or more apart are dotted so drawn resolution cannot pass for real resolution. */
import type { SignalPayload } from '../../api'
import { EnvelopePath } from '../../charts/primitives'
import { makeY } from '../../charts/scale'
import { axisUnit } from '../../charts/units'
import { AxisLabels, finiteRange, fmtN, nearest, resolutionWords, useHoverT, type ViewCtx } from './common'

/** below this share of the plot height on a shared axis, a trace is being flattened — draw two axes instead */
const SHARE_MIN = 0.35

export function sharesScale(a: [number, number], b: [number, number]): boolean {
  const lo = Math.min(a[0], b[0]), hi = Math.max(a[1], b[1])
  const union = hi - lo
  if (!(union > 0)) return true
  return (a[1] - a[0]) / union >= SHARE_MIN && (b[1] - b[0]) / union >= SHARE_MIN
}

export function SignalView({ p, ctx }: { p: SignalPayload; ctx: ViewCtx }) {
  const out = p.y_range ?? finiteRange(p.envelope.v) ?? [-1, 1]
  const ghost = ctx.ghost && ctx.ghost.t.length ? ctx.ghost : null
  const gr = ghost ? finiteRange(ghost.v) : null
  const shared = !!gr && sharesScale(out, gr) && (ctx.ghostUnit ?? p.unit) === p.unit
  const yOut = shared && gr ? makeY(Math.min(out[0], gr[0]), Math.max(out[1], gr[1]), ctx.height) : makeY(out[0], out[1], ctx.height)
  const yIn = gr ? (shared ? yOut : makeY(gr[0], gr[1], ctx.height)) : null
  const unit = axisUnit(p.unit)
  const mid = (r: [number, number]) => (r[0] < 0 && r[1] > 0 ? 0 : (r[0] + r[1]) / 2)
  const [hover, handlers] = useHoverT(ctx.x)
  const plotW = ctx.x.range()[1] - ctx.x.range()[0]
  const n = p.envelope.t.length
  const dots = !p.envelope.decimated && n > 1 && plotW / (n - 1) >= 3
  const flat = !(out[1] > out[0])
  const stroke = ctx.sourceStyle ? 'var(--trace)' : 'var(--trace-blue)'
  const readout = (() => {
    if (!ctx.interactive || hover === null || !n) return null
    const i = nearest(p.envelope.t, hover)
    const v = p.envelope.v[i]
    const gi = ghost ? nearest(ghost.t, hover) : -1
    const gv = ghost && gi >= 0 ? ghost.v[gi] : null
    const px = ctx.x(p.envelope.t[i])
    return (
      <g pointerEvents="none" data-testid="signal-readout">
        <line x1={px} x2={px} y1={0} y2={ctx.height} stroke="var(--blue)" strokeOpacity={0.5} strokeDasharray="3 3" />
        {v !== null && <circle cx={px} cy={yOut(v)} r={2.6} fill="var(--blue)" />}
        {gv !== null && yIn && <circle cx={ctx.x(ghost!.t[gi])} cy={yIn(gv)} r={2.6} fill="var(--muted)" />}
        <text x={Math.min(px + 6, ctx.width - 210)} y={14} style={{ fill: 'var(--text-2)', paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>
          {gv !== null ? `before ${fmtN(gv)} → ` : ''}{v !== null ? `after ${fmtN(v)}` : 'no value'}{unit ? ` ${unit}` : ''}
        </text>
      </g>
    )
  })()
  return (
    <svg width={ctx.width} height={ctx.height} data-render="signal" data-plot-box data-rule9="trace" data-flat={flat ? '1' : '0'}
      data-axes={!ghost ? 'one' : shared ? 'shared' : 'dual'} {...(ctx.interactive ? handlers : {})}>
      {ghost && yIn && <g data-ghost><EnvelopePath t={ghost.t} v={ghost.v} x={ctx.x} y={yIn} stroke="var(--trace-ghost)" testid="ghost" /></g>}
      <g data-trace><EnvelopePath t={p.envelope.t} v={p.envelope.v} x={ctx.x} y={yOut} stroke={stroke} testid="signal-path" /></g>
      {dots && <g data-sample-dots pointerEvents="none">{p.envelope.t.map((t, i) => p.envelope.v[i] === null ? null : <circle key={i} cx={ctx.x(t)} cy={yOut(p.envelope.v[i] as number)} r={1.5} fill={stroke} />)}</g>}
      {!ghost || shared
        ? <AxisLabels y={yOut} values={shared && gr ? [Math.max(out[1], gr[1]), Math.min(out[0], gr[0])] : [out[1], mid(out), out[0]]} side="left" width={ctx.width} unit={unit} />
        : <>
          <AxisLabels y={yIn!} values={[gr![1], gr![0]]} side="left" width={ctx.width} unit={axisUnit(ctx.ghostUnit ?? p.unit)} colour="var(--muted)" />
          <AxisLabels y={yOut} values={[out[1], out[0]]} side="right" width={ctx.width} unit={unit} colour="var(--blue-600)" />
        </>}
      {ghost && (
        <text x={ctx.width / 2} y={ctx.height - 5} textAnchor="middle" fill="var(--muted-2)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }} data-testid="signal-axes-note">
          {shared ? 'before (grey) and after (blue) on one axis' : 'before (grey) on the left axis · after (blue) on the right axis'}
        </text>
      )}
      {readout}
    </svg>
  )
}

/** The line of words under the settings-tier plot: what was drawn, and what the block did to the range. */
export function SignalNote({ p, ctx }: { p: SignalPayload; ctx: ViewCtx }) {
  const out = p.y_range ?? finiteRange(p.envelope.v)
  const gr = ctx.ghost ? finiteRange(ctx.ghost.v) : null
  const unit = axisUnit(p.unit) || ''
  return (
    <div className="muted mono small" style={{ marginTop: 4 }} data-testid="signal-note">
      {resolutionWords(p.envelope, p.fs)}
      {gr && out && <> · range before {fmtN(gr[0])} … {fmtN(gr[1])} {unit} ({fmtN(gr[1] - gr[0])} wide) → after {fmtN(out[0])} … {fmtN(out[1])} {unit} ({fmtN(out[1] - out[0])} wide)</>}
    </div>
  )
}
