/* THE single client-side dispatch seam: renderByType(payload, ctx) → ReactNode, keyed on payload.type.
   Since fixup-h the seven interchange types are drawn by the type views of `views/registry.tsx` — one component
   per view, used here with interaction off (the chain thumbnail) and by the block page with it on. This file
   keeps the seam, the error card, and the fixture renderers of the concept-frame demo chains. Every
   time-aligned view draws against the caller's xScale so all rows on a chain page share one time axis. */
import type { EnvelopeSeries, ErrorPayload, Payload } from '../api'
import { EnvelopePath, SpanBands, YLabels } from '../charts/primitives'
import { makeY, type XScale } from '../charts/scale'
import type { DisplayUnit } from '../charts/units'
import type { DemoPayload, DemoScoresPayload, DemoSignalPayload, DemoSlopePayload, DemoSpansPayload, DemoStripsPayload, DemoTextPayload, DemoWindowsPayload } from '../api/analyse'
import { TypeView, hasView } from './views/registry'

export { CAT9, SYM3 } from './views/EncodingView'
export { motifLabels } from './views/ScoresView'

export interface RenderCtx {
  x: XScale; width: number; height: number
  ghost?: EnvelopeSeries | null      // the nearest upstream signal, drawn behind in grey
  ghostUnit?: DisplayUnit            // the unit that signal is drawn in
  t0: number; t1: number
  hideKey?: boolean                  // block pages carry the key in their own legend row
  throwForTest?: boolean             // ?throw=1: prove the ErrorBoundary catches a renderer throw
  sourceStyle?: boolean              // the source row draws its signal near-black (frame chain-1)
}

export function renderByType(payload: Payload | DemoPayload, ctx: RenderCtx): React.ReactNode {
  if (ctx.throwForTest) throw new Error('deliberate render failure (?throw=1)')
  if ('error' in payload && payload.error) return <ErrorR p={payload as ErrorPayload} />
  switch (payload.type) {
    /* demo payloads (api/analyse.ts): the B24 detection chain and the other concept-frame chains, drawn on the same axis */
    case 'demo.signal': return <DemoSignalR p={payload as DemoSignalPayload} ctx={ctx} />
    case 'demo.slope': return <DemoSlopeR p={payload as DemoSlopePayload} ctx={ctx} />
    case 'demo.strips': return <DemoStripsR p={payload as DemoStripsPayload} ctx={ctx} />
    case 'demo.spans': return <DemoSpansR p={payload as DemoSpansPayload} ctx={ctx} />
    case 'demo.scores': return <DemoScoresR p={payload as DemoScoresPayload} ctx={ctx} />
    case 'demo.windows': return <DemoWindowsR p={payload as DemoWindowsPayload} ctx={ctx} />
    case 'demo.text': return <div className="bp-model" style={{ padding: '6px 12px' }} data-render="demo-text">{(payload as DemoTextPayload).lines.map((l, i) => <div key={i}>{l}</div>)}</div>
    default:
      // the seven interchange types: one type view each, interaction off (the thumbnail tier)
      if (hasView(payload.type)) return <TypeView payload={payload as Payload} ctx={{ ...ctx, interactive: false }} />
      return <ErrorR p={{ type: payload.type, error: `no view for payload type "${payload.type}"`, summary: '' }} />
  }
}

/* ---------- helpers ---------- */
function finiteRange(v: (number | null)[]): [number, number] | null {
  let lo = Infinity, hi = -Infinity
  for (const x of v) if (x !== null && Number.isFinite(x)) { if (x < lo) lo = x; if (x > hi) hi = x }
  return lo <= hi ? [lo, hi] : null
}

/* ---------- demo payloads ---------- */
/** k 5 letters d D S U u and k 3 down / same / up (frame chain-3 legend). */
export const SYM5 = ['#8e2b1e', '#f59e0b', '#d4d4d8', '#9db8e8', '#2c5aa0']
export const SYM3_DEMO = ['#f59e0b', '#e5e7eb', '#9db8e8']
function DemoSignalR({ p, ctx }: { p: DemoSignalPayload; ctx: RenderCtx }) {
  const y = makeY(p.y_range[0], p.y_range[1], ctx.height, 6, 6)
  return (
    <svg width={ctx.width} height={ctx.height} data-render="demo-signal">
      {p.ghost && <EnvelopePath t={p.ghost.t} v={p.ghost.v} x={ctx.x} y={y} stroke="var(--trace-ghost)" testid="ghost" />}
      {p.baseline && <EnvelopePath t={p.baseline.t} v={p.baseline.v} x={ctx.x} y={y} stroke="#e8590c" width={1.6} />}
      <EnvelopePath t={p.envelope.t} v={p.envelope.v} x={ctx.x} y={y} stroke={ctx.sourceStyle ? 'var(--trace)' : 'var(--trace-blue)'} width={ctx.sourceStyle ? 1.1 : 1.4} testid="signal-path" />
      {!ctx.sourceStyle && <YLabels y={y} values={[p.y_range[1], p.y_range[0]]} unit="mV" />}
    </svg>
  )
}
function DemoSlopeR({ p, ctx }: { p: DemoSlopePayload; ctx: RenderCtx }) {
  const cap = p.k * p.sigma * 1.6
  const ext = Math.max(p.k * p.sigma * 1.15, ...p.slopes.map(v => Math.min(Math.abs(v), cap)))
  const y = makeY(-ext, ext, ctx.height, 6, 6)
  const cw = Math.max(1, ctx.x(p.t0_s + p.seg_s) - ctx.x(p.t0_s) - 0.6)
  const q = (v: number) => (v <= -p.k * p.sigma ? 0 : v <= -3 * p.sigma ? 1 : v < 3 * p.sigma ? 2 : v < p.k * p.sigma ? 3 : 4)
  return (
    <svg width={ctx.width} height={ctx.height} data-render="demo-slope">
      <line x1={0} x2={ctx.width} y1={y(0)} y2={y(0)} stroke="var(--border)" />
      {p.slopes.map((v, i) => { const c = Math.max(-ext, Math.min(ext, v)); return <rect key={i} x={ctx.x(p.t0_s + i * p.seg_s)} y={Math.min(y(0), y(c))} width={cw} height={Math.max(1, Math.abs(y(c) - y(0)))} fill={SYM5[q(v)]} opacity={0.85} /> })}
      {[3, -3].map(k => <line key={k} x1={0} x2={ctx.width} y1={y(k * p.sigma)} y2={y(k * p.sigma)} stroke="var(--text-2)" strokeDasharray="4 3" strokeOpacity={0.5} />)}
    </svg>
  )
}
function DemoStripsR({ p, ctx }: { p: DemoStripsPayload; ctx: RenderCtx }) {
  const cw = Math.max(1, ctx.x(p.t0_s + p.seg_s) - ctx.x(p.t0_s))
  const gap = 6; const h = (ctx.height - gap * (p.strips.length + 1)) / p.strips.length
  return (
    <svg width={ctx.width} height={ctx.height} data-render="demo-strips">
      {p.strips.map((s, j) => (
        <g key={j} transform={`translate(0,${gap + j * (h + gap)})`}>
          {s.symbols.map((sym, i) => <rect key={i} x={ctx.x(p.t0_s + i * p.seg_s)} width={cw + 0.3} height={h} fill={s.alphabet === 5 ? SYM5[sym] : SYM3_DEMO[sym]}><title>{`${s.label} · segment ${i} · ${s.alphabet === 5 ? 'dDSUu'[sym] : ['down', 'same', 'up'][sym]}`}</title></rect>)}
        </g>
      ))}
    </svg>
  )
}
function DemoSpansR({ p, ctx }: { p: DemoSpansPayload; ctx: RenderCtx }) {
  const r = finiteRange(p.ghost.v) ?? [0, 1]
  const y = makeY(r[0], r[1], ctx.height, 8, 8)
  return (
    <svg width={ctx.width} height={ctx.height} data-render="demo-spans">
      <SpanBands spans={p.spans.map((s, i) => ({ ...s, kind: 'grey' as const, id: i, title: s.label }))} x={ctx.x} height={ctx.height} minPx={2} />
      <EnvelopePath t={p.ghost.t} v={p.ghost.v} x={ctx.x} y={y} stroke="var(--muted)" testid="spans-ghost" />
      <text x={ctx.width - 6} y={ctx.height - 5} textAnchor="end" fill="var(--muted-2)">{p.spans.length} span{p.spans.length === 1 ? '' : 's'}</text>
    </svg>
  )
}
function DemoScoresR({ p, ctx }: { p: DemoScoresPayload; ctx: RenderCtx }) {
  const y = makeY(0, p.y_max, ctx.height, 14, 12)
  return (
    <svg width={ctx.width} height={ctx.height} data-render="demo-scores">
      {p.p5 != null && <><rect x={0} y={y(p.p5 + 0.35)} width={ctx.width} height={Math.abs(y(p.p5 - 0.35) - y(p.p5 + 0.35))} fill="rgba(107,114,128,0.14)" /><line x1={0} x2={ctx.width} y1={y(p.p5)} y2={y(p.p5)} stroke="var(--muted)" /></>}
      <EnvelopePath t={p.envelope.t} v={p.envelope.v} x={ctx.x} y={y} stroke="var(--blue)" width={1.3} testid="scores-path" />
      {p.marks.map(m => {
        const px = ctx.x(m.t_s); const c = m.kind === 'motif' ? 'var(--green)' : 'var(--red)'
        return <g key={m.label} data-testid={`mark-${m.label}`}><line x1={px} x2={px} y1={12} y2={ctx.height} stroke={c} strokeOpacity={0.7} /><rect x={px - 12} y={1} width={24} height={11} rx={2} fill={c} /><text x={px} y={9.5} textAnchor="middle" style={{ fontSize: 8.5, fontWeight: 600, fill: '#fff' }}>{m.label}</text></g>
      })}
      <YLabels y={y} values={[p.y_max, p.y_max / 2, 0]} digits={0} />
      <text x={ctx.width - 6} y={ctx.height - 3} textAnchor="end" fill="var(--muted)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}><tspan fill="var(--blue)">━</tspan> profile  <tspan fill="var(--muted)">━</tspan> surrogate p5  <tspan fill="var(--green)">━</tspan> motif  <tspan fill="var(--red)">━</tspan> discord</text>
    </svg>
  )
}
function DemoWindowsR({ p, ctx }: { p: DemoWindowsPayload; ctx: RenderCtx }) {
  const r = finiteRange(p.ghost.v) ?? [0, 1]
  const y = makeY(r[0], r[1], ctx.height - 16, 6, 4)
  return (
    <svg width={ctx.width} height={ctx.height} data-render="demo-windows">
      <EnvelopePath t={p.ghost.t} v={p.ghost.v} x={ctx.x} y={y} stroke="var(--trace-ghost)" />
      {p.starts_s.map((s, i) => <line key={i} x1={ctx.x(s)} x2={ctx.x(s)} y1={ctx.height - 14} y2={ctx.height - (i % 2 ? 8 : 4)} stroke="var(--blue)" />)}
      <text x={ctx.width - 6} y={11} textAnchor="end" fill="var(--muted)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{p.summary}</text>
    </svg>
  )
}

/* ---------- error ---------- */
function ErrorR({ p }: { p: ErrorPayload }) {
  return (
    <div className="error-card" style={{ padding: '8px 12px' }} data-testid="error-card">
      <h3>payload {p.type} could not be rendered</h3>
      <div className="mono" style={{ fontSize: 11.5 }}>{p.error}</div>
      {p.traceback && <pre>{p.traceback}</pre>}
    </div>
  )
}
