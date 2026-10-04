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

/* ---------------- every layer of a decomposition (fixup-ac) ----------------
 * A Signal block that passes ONE layer of a decomposition on (`preprocessing.wavelet_bands`) puts every layer in
 * its payload (`layers`, a payload convention — docs/BLOCK_INTEGRATION.md §2 — never the block's name). They are
 * drawn stacked on the page's own time axis under the before/after plot: the input first, grey, then each layer,
 * fastest first, the one that went on highlighted. Each row is its own rule-9 plot on a y measured from its own
 * trace with a scale bar (rule 4: small multiples never share a y — the slow layers are many times the size of the
 * fast ones, and a shared axis would draw the fast ones flat). One shared hover line runs through every row, so a
 * drop can be followed down the stack: the layers are sample-aligned, and so is the picture. Each row carries the
 * y it was drawn on (`data-y-domain`, `data-y-range`) so the smoke gate can read values back off the DOM. */
const LAYER_ROW_H = 46

function LayerRow({ name, label, t, v, x, width, chosen, input, unit, hover, handlers }: {
  name: string; label: string; t: number[]; v: (number | null)[]; x: ViewCtx['x']; width: number; chosen: boolean; input?: boolean
  unit: string; hover: number | null; handlers: ReturnType<typeof useHoverT>[1]
}) {
  const r = finiteRange(v)
  const flat = !r || !(r[1] > r[0])
  const y = makeY(r ? r[0] : -1, r ? r[1] : 1, LAYER_ROW_H, 6, 6)
  const [d0, d1] = y.domain(), [p0, p1] = y.range()
  const bar = r && r[1] > r[0] ? niceBarSize(r[1] - r[0]) : 0
  const barPx = bar ? Math.abs(y(r![0]) - y(r![0] + bar)) : 0
  const stroke = input ? 'var(--trace-ghost)' : chosen ? 'var(--trace-blue)' : 'var(--trace)'
  return (
    <svg width={width} height={LAYER_ROW_H} data-render="signal-layer" data-layer={name} data-chosen={chosen ? '1' : '0'} data-input={input ? '1' : '0'}
      data-rule9="layer" data-flat={flat ? '1' : '0'} data-y-domain={`${d0},${d1}`} data-y-range={`${p0},${p1}`} style={{ display: 'block' }} {...handlers}>
      {chosen && <rect x={0} y={0} width={width} height={LAYER_ROW_H} fill="var(--band-selected)" data-testid="layer-chosen" />}
      <line x1={0} x2={width} y1={LAYER_ROW_H - 0.5} y2={LAYER_ROW_H - 0.5} stroke="var(--border, #e5e7eb)" />
      <g data-trace><EnvelopePath t={t} v={v} x={x} y={y} stroke={stroke} width={chosen ? 1.4 : 1} /></g>
      {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={0} y2={LAYER_ROW_H} stroke="var(--blue)" strokeOpacity={0.5} strokeDasharray="3 3" pointerEvents="none" />}
      <text x={6} y={13} style={{ fill: chosen ? 'var(--blue-600)' : 'var(--text-2)', fontWeight: chosen ? 600 : 400, paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }} pointerEvents="none">
        {label}{chosen ? ' · goes on down the chain' : ''}
      </text>
      {barPx > 0 && (
        <g pointerEvents="none" data-testid="layer-scale-bar">
          <line x1={width - 4} x2={width - 4} y1={LAYER_ROW_H - 6 - barPx} y2={LAYER_ROW_H - 6} stroke="var(--text-2)" strokeWidth={2} />
          <text x={width - 8} y={LAYER_ROW_H - 6 - barPx / 2 + 3} textAnchor="end" style={{ fontFamily: 'var(--font-mono)', fontSize: 9, fill: 'var(--muted)', paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>
            {fmtN(bar)}{unit ? ` ${unit}` : ''}
          </text>
        </g>
      )}
    </svg>
  )
}

/** the largest 1 / 2 / 5 × 10^k at most half a row's span (charts/ScaleBar.tsx's rule) */
function niceBarSize(span: number): number {
  if (!(span > 0) || !Number.isFinite(span)) return 0
  const target = span * 0.5, k = Math.pow(10, Math.floor(Math.log10(target))), m = target / k
  return (m >= 5 ? 5 : m >= 2 ? 2 : 1) * k
}

export function SignalLayers({ p, ctx }: { p: SignalPayload; ctx: ViewCtx }) {
  const layers = p.layers ?? []
  const unit = axisUnit(p.unit) || ''
  const [hover, handlers] = useHoverT(ctx.x)
  const ghost = ctx.ghost && ctx.ghost.t.length ? ctx.ghost : null
  const width = ctx.width
  return (
    <div data-testid="wavelet-layers" data-n-layers={layers.length}>
      {ghost && <LayerRow name="input" label="input · what this block was given" t={ghost.t} v={ghost.v} x={ctx.x} width={width} chosen={false} input
        unit={axisUnit(ctx.ghostUnit ?? p.unit) || ''} hover={hover} handlers={handlers} />}
      {layers.map(L => (
        <LayerRow key={L.name} name={L.name} label={L.label} t={L.envelope.t} v={L.envelope.v} x={ctx.x} width={width} chosen={L.chosen}
          unit={unit} hover={hover} handlers={handlers} />
      ))}
    </div>
  )
}

/** One line on the face — which layer went on, how deep, how it was padded — the rest behind the info icon. */
export function SignalLayersNote({ p }: { p: SignalPayload }) {
  const d = p.decomposition
  if (!d) return null
  const chosen = (p.layers ?? []).find(L => L.chosen)
  return (
    <div className="muted mono small" style={{ marginTop: 4 }} data-testid="wavelet-layers-note">
      {d.wavelet} · {d.levels} level{d.levels === 1 ? '' : 's'}{d.levels_auto ? ' (auto: from the span and the sample rate)' : ''} ·{' '}
      <b data-testid="wavelet-layer-chosen">{chosen ? chosen.label : d.layer_label}</b> goes on ·{' '}
      {d.padding.padded_to !== d.padding.n ? `padded ${d.padding.n.toLocaleString()} → ${d.padding.padded_to.toLocaleString()} samples and trimmed back` : 'no padding needed'}
      {d.reconstruction_error != null && <> · the layers add up to the input (largest difference {fmtN(d.reconstruction_error)}, in the recording's stored unit)</>}
      {p.layers && p.layers[0] && <> · {resolutionWords(p.layers[0].envelope, p.fs)}</>}
    </div>
  )
}
