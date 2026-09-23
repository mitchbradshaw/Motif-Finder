/* Plots: SVG on d3 scales (scales only), light grounds, thin lines, mV never normalised.
 * Trace, MiniTrace, LineChart, Histogram, Bars, Scatter, Heatmap, BandStrip, NullBand, SmallMultiples.
 * Every plot sizes to its container width unless `width` is given. */
import { scaleLinear } from 'd3'
import { useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import { EnvelopePath, SpanBands, TimeAxis, type BandKind } from '../charts/primitives'
import { makeX } from '../charts/scale'
import { useSize } from '../charts/useSize'
import { Button } from './display'
import { fmtInt, sampleIndices } from './hooks'
import { cx, tid, type TestIdProps } from './portal'
import { Pager } from './nav'

type Lin = ReturnType<typeof scaleLinear<number, number>>
const GROUND = { white: '#ffffff', grey: '#f5f6f8' }
const minus = (s: string) => s.replace('-', '−')

function useWidth(width?: number): [React.RefObject<HTMLDivElement | null>, number] {
  const [ref, size] = useSize<HTMLDivElement>()
  return [ref, width ?? size.width]
}
function ticks(lo: number, hi: number, n: number) { return scaleLinear().domain([lo, hi]).ticks(n) }
function fmtNum(v: number, step: number) {
  const d = step >= 1 ? 0 : Math.min(4, Math.ceil(-Math.log10(step)))
  return minus(v.toFixed(d))
}
export function Legend({ items, style }: { items: { label: ReactNode; colour: string; shape?: 'box' | 'line' | 'dot' }[]; style?: CSSProperties }) {
  return <div className="k-plot-legend" style={style}>{items.map((it, i) => <span key={i}><i className={cx('sw', it.shape === 'line' && 'line', it.shape === 'dot' && 'dot')} style={{ background: it.colour }} />{it.label}</span>)}</div>
}

function XAxisNum({ x, y, n = 6, format, label, tickValues }: { x: Lin; y: number; n?: number; format?: (v: number) => string; label?: string; tickValues?: number[] }) {
  const [d0, d1] = x.domain(); const [r0, r1] = x.range()
  const tv = tickValues ?? ticks(d0, d1, n)
  const step = tv.length > 1 ? Math.abs(tv[1] - tv[0]) : 1
  return (
    <g>
      <line x1={r0} x2={r1} y1={y} y2={y} stroke="var(--border)" />
      {tv.map(v => { const px = x(v); const anchor = px - r0 < 14 ? 'start' : r1 - px < 14 ? 'end' : 'middle'; return <g key={v} transform={`translate(${px},${y})`}><line y2={3} stroke="var(--border-strong)" /><text y={13} textAnchor={anchor}>{format ? format(v) : fmtNum(v, step)}</text></g> })}
      {label && <text className="axis-title" x={r1} y={y + 25} textAnchor="end">{label}</text>}
    </g>
  )
}
function YAxisNum({ y, x, n = 4, format, label, grid, width }: { y: Lin; x: number; n?: number; format?: (v: number) => string; label?: string; grid?: boolean; width?: number }) {
  const [d0, d1] = y.domain()
  const tv = ticks(d0, d1, n)
  const step = tv.length > 1 ? Math.abs(tv[1] - tv[0]) : 1
  return (
    <g>
      {tv.map(v => <g key={v}>{grid && width && <line x1={x + 4} x2={width} y1={y(v)} y2={y(v)} stroke="var(--grey-100)" />}<text x={x} y={y(v) + 3} textAnchor="end">{format ? format(v) : fmtNum(v, step)}</text></g>)}
      {label && <text className="axis-title" x={x} y={Math.min(...y.range()) - 6} textAnchor="end">{label}</text>}
    </g>
  )
}

/** Symmetric-ish mV labels: top, 0 (if inside), bottom, e.g. "+0.4 / 0 / −0.4". */
function mvTicks(lo: number, hi: number): number[] {
  const r = hi - lo
  const step = Math.pow(10, Math.floor(Math.log10(r || 1)))
  const top = Math.floor(hi / step * 2) / 2 * step, bot = Math.ceil(lo / step * 2) / 2 * step
  const out = [top, bot]
  if (lo < 0 && hi > 0) out.splice(1, 0, 0)
  return [...new Set(out.map(v => +v.toPrecision(6)))]
}
// Number(…) round-trips toPrecision's exponent form ("4.0e+2") back to plain digits ("400"): hundreds of mV are
// ordinary since fixup-b stopped printing stored volts as mV
const fmtMvTick = (v: number) => v === 0 ? '0' : `${v > 0 ? '+' : '−'}${String(Number(Math.abs(v).toPrecision(2)))}`

function decimate(values: number[], t: number[], buckets: number): [number[], number[]] {
  if (values.length <= buckets * 2) return [t, values]
  const size = values.length / buckets, tt: number[] = [], vv: number[] = []
  for (let b = 0; b < buckets; b++) {
    const s = Math.floor(b * size), e = Math.min(values.length, Math.floor((b + 1) * size))
    let mi = s, ma = s
    for (let i = s; i < e; i++) { if (values[i] < values[mi]) mi = i; if (values[i] > values[ma]) ma = i }
    const [a, c] = mi < ma ? [mi, ma] : [ma, mi]
    tt.push(t[a], t[c]); vv.push(values[a], values[c])
  }
  return [tt, vv]
}
function extent(arrs: number[][]): [number, number] {
  let lo = Infinity, hi = -Infinity
  for (const a of arrs) for (const v of a) { if (Number.isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v } }
  return lo === Infinity ? [-1, 1] : [lo, hi]
}

/* ================= Trace ================= */
export interface TraceBand { start_s: number; end_s: number; kind: BandKind; label?: string; id?: string | number }
export interface TraceMarker { t: number; label?: string; colour?: string }
export interface TraceProps extends TestIdProps {
  /** Samples in mV (never normalised). */
  values: number[]; fs?: number; t0?: number
  /** h: hours-since-start axis (spec §0) · s: seconds relative to t0 ("0 s … 35 s") · none. */
  timeUnit?: 'h' | 's' | 'none'
  yDomain?: [number, number]; height?: number; width?: number; stroke?: string; strokeWidth?: number
  overlays?: { values: number[]; stroke: string; label?: string; width?: number }[]
  bands?: TraceBand[]; markers?: TraceMarker[]; onBandClick?: (b: TraceBand) => void
  ground?: 'white' | 'grey'; bordered?: boolean; unitLabel?: boolean; zeroLine?: boolean; crosshair?: boolean; style?: CSSProperties
}
export function Trace({ values, fs = 1, t0 = 0, timeUnit = 'h', yDomain, height = 140, width, stroke = 'var(--trace)', strokeWidth = 1, overlays = [], bands = [], markers = [], onBandClick, ground = 'white', bordered, unitLabel = true, zeroLine = true, crosshair = true, style, ...t }: TraceProps) {
  const [ref, w] = useWidth(width)
  const [hover, setHover] = useState<number | null>(null)
  const padL = 44, padR = 10, padT = 8, padB = timeUnit === 'none' ? 6 : 22
  const n = values.length
  const t1 = t0 + Math.max(1, n - 1) / fs
  const [lo, hi] = yDomain ?? (() => { const [a, b] = extent([values, ...overlays.map(o => o.values)]); const m = (b - a) * 0.08 || 0.1; return [a - m, b + m] as [number, number] })()
  const x = makeX(t0, t1, w, padL, padR)
  const y = scaleLinear().domain([lo, hi]).range([height - padB, padT])
  const series = useMemo(() => {
    const tt = values.map((_, i) => t0 + i / fs)
    const buckets = Math.max(50, Math.floor(w - padL - padR))
    return { main: decimate(values, tt, buckets), over: overlays.map(o => decimate(o.values, o.values.map((_, i) => t0 + i / fs), buckets)) }
  }, [values, overlays, t0, fs, w])
  const yt = mvTicks(lo, hi)
  const sTicks = timeUnit === 's' ? ticks(0, t1 - t0, 6) : []
  return (
    <div ref={ref} className={cx('k-plot', bordered && 'bordered')} style={style} data-testid={tid(t)}>
      {w > 0 && (
        <svg width={w} height={height} role="img" aria-label={`trace, ${n} samples, ${minus(lo.toFixed(2))} to ${minus(hi.toFixed(2))} mV`}
          onPointerMove={crosshair ? e => { const r = e.currentTarget.getBoundingClientRect(); const px = e.clientX - r.left; setHover(px >= padL && px <= w - padR ? x.invert(px) : null) } : undefined}
          onPointerLeave={() => setHover(null)}>
          <rect x={padL} y={padT} width={Math.max(0, w - padL - padR)} height={height - padT - padB} fill={GROUND[ground]} />
          <g transform={`translate(0,${padT})`}><SpanBands spans={bands} x={x} height={height - padT - padB} onClick={onBandClick} /></g>
          {bands.filter(b => b.label).map((b, i) => <text key={i} x={x(b.start_s) + 4} y={padT + 11} style={{ fill: 'var(--blue-600)' }}>{b.label}</text>)}
          {zeroLine && lo < 0 && hi > 0 && <line x1={padL} x2={w - padR} y1={y(0)} y2={y(0)} stroke="var(--grey-200)" strokeDasharray="3 3" />}
          {yt.map(v => <text key={v} x={padL - 6} y={y(v) + 3} textAnchor="end">{fmtMvTick(v)}</text>)}
          {unitLabel && <text x={padL - 6} y={height - padB + (timeUnit === 'none' ? 0 : 14)} textAnchor="end" className="axis-title">mV</text>}
          {series.over.map((o, i) => <EnvelopePath key={i} t={o[0]} v={o[1]} x={x} y={y} stroke={overlays[i].stroke} width={overlays[i].width ?? 1.2} />)}
          <EnvelopePath t={series.main[0]} v={series.main[1]} x={x} y={y} stroke={stroke} width={strokeWidth} />
          {markers.map((m, i) => <g key={i}><line x1={x(m.t)} x2={x(m.t)} y1={padT} y2={height - padB} stroke={m.colour ?? 'var(--amber)'} strokeDasharray="3 2" />{m.label && <text x={x(m.t) + 3} y={padT + 10} style={{ fill: m.colour ?? 'var(--amber)' }}>{m.label}</text>}</g>)}
          {timeUnit === 'h' && <TimeAxis x={x} y={height - padB} t0={t0} t1={t1} n={5} />}
          {timeUnit === 's' && <g>{sTicks.map(v => { const px = x(t0 + v); const [r0, r1] = x.range(); return <text key={v} x={px} y={height - padB + 14} textAnchor={px - r0 < 14 ? 'start' : r1 - px < 14 ? 'end' : 'middle'}>{fmtNum(v, sTicks[1] - sTicks[0] || 1)} s</text> })}</g>}
          {hover !== null && (() => {
            const i = Math.max(0, Math.min(n - 1, Math.round((hover - t0) * fs)))
            const px = x(t0 + i / fs)
            return <g pointerEvents="none"><line x1={px} x2={px} y1={padT} y2={height - padB} stroke="var(--blue)" strokeOpacity={0.5} strokeDasharray="3 3" /><circle cx={px} cy={y(values[i])} r={2.5} fill="var(--blue)" />
              <text x={Math.min(px + 6, w - 110)} y={padT + 22} style={{ fill: 'var(--text-2)', paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{minus(values[i]?.toFixed(3) ?? '')} mV · {timeUnit === 'h' ? `${((t0 + i / fs) / 3600).toFixed(3)} h` : `${(i / fs).toFixed(1)} s`}</text></g>
          })()}
        </svg>
      )}
      {w === 0 && <div style={{ height }} />}
    </div>
  )
}

/* ================= MiniTrace ================= */
export interface MiniTraceProps extends TestIdProps {
  values: number[]
  /** Required: a family / small-multiple set shares one mV scale — the kit never auto-normalises a thumbnail. */
  yDomain: [number, number]
  width?: number | string; height?: number; stroke?: string; strokeWidth?: number
  overlays?: { values: number[]; stroke: string; width?: number }[]; ground?: 'white' | 'grey' | 'none'; zeroLine?: boolean; band?: [number, number]; bandColour?: string; title?: string; style?: CSSProperties
}
/** Sparkline thumbnail on a caller-supplied y domain. `width` may be "100%" (stretches, strokes stay thin). */
export function MiniTrace({ values, yDomain, width = 120, height = 36, stroke = 'var(--trace)', strokeWidth = 1.2, overlays = [], ground = 'grey', zeroLine = true, band, bandColour = 'var(--band-detected)', title, style, ...t }: MiniTraceProps) {
  const VW = 200
  const path = (vs: number[]) => {
    const n = vs.length; if (!n) return ''
    const y = scaleLinear().domain(yDomain).range([height - 2, 2])
    let d = ''
    const step = Math.max(1, Math.floor(n / 400))
    for (let i = 0; i < n; i += step) d += `${i ? 'L' : 'M'}${((i / Math.max(1, n - 1)) * VW).toFixed(1)} ${y(Math.max(yDomain[0], Math.min(yDomain[1], vs[i]))).toFixed(1)}`
    return d
  }
  const y0 = scaleLinear().domain(yDomain).range([height - 2, 2])(0)
  return (
    <svg className="k-mini" width={width} height={height} viewBox={`0 0 ${VW} ${height}`} preserveAspectRatio="none" role="img" aria-label={title ?? 'thumbnail trace'} style={{ background: ground === 'none' ? undefined : GROUND[ground], ...style }} data-testid={tid(t)}>
      {title && <title>{title}</title>}
      {band && values.length > 1 && <rect x={(band[0] / (values.length - 1)) * VW} width={((band[1] - band[0]) / (values.length - 1)) * VW} y={0} height={height} fill={bandColour} />}
      {zeroLine && yDomain[0] < 0 && yDomain[1] > 0 && <line x1={0} x2={VW} y1={y0} y2={y0} stroke="var(--grey-200)" vectorEffect="non-scaling-stroke" />}
      {overlays.map((o, i) => <path key={i} d={path(o.values)} fill="none" stroke={o.stroke} strokeWidth={o.width ?? 1.2} vectorEffect="non-scaling-stroke" />)}
      <path d={path(values)} fill="none" stroke={stroke} strokeWidth={strokeWidth} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  )
}

/* ================= LineChart ================= */
export interface LineSeries { label: string; colour: string; points: [number, number][]; dashed?: boolean; dots?: boolean; width?: number }
export interface LineChartProps extends TestIdProps {
  series: LineSeries[]; xDomain?: [number, number]; yDomain?: [number, number]; height?: number; width?: number
  markers?: { x: number; label?: string; colour?: string }[]; hLines?: { y: number; label?: string; colour?: string }[]; diagonal?: boolean
  xLabel?: string; yLabel?: string; xFormat?: (v: number) => string; yFormat?: (v: number) => string; legend?: boolean; ground?: 'white' | 'grey'; style?: CSSProperties
}
/** Numeric x/y lines (training curves, calibration with `diagonal`, choose-k). */
export function LineChart({ series, xDomain, yDomain, height = 180, width, markers = [], hLines = [], diagonal, xLabel, yLabel, xFormat, yFormat, legend = true, ground = 'white', style, ...t }: LineChartProps) {
  const [ref, w] = useWidth(width)
  const padL = 40, padR = 12, padT = 14, padB = xLabel ? 32 : 22
  const xs = series.flatMap(s => s.points.map(p => p[0])), ys = series.flatMap(s => s.points.map(p => p[1]))
  const xd = xDomain ?? extent([xs]), yd = yDomain ?? (() => { const [a, b] = extent([ys]); const m = (b - a) * 0.08 || 0.1; return [a - m, b + m] as [number, number] })()
  const x = scaleLinear().domain(xd).range([padL, Math.max(padL + 1, w - padR)])
  const y = scaleLinear().domain(yd).range([height - padB, padT])
  return (
    <div ref={ref} className="k-plot" style={style} data-testid={tid(t)}>
      {w > 0 && <svg width={w} height={height} role="img" aria-label={`line chart: ${series.map(s => s.label).join(', ')}`}>
        <rect x={padL} y={padT} width={Math.max(0, w - padL - padR)} height={height - padT - padB} fill={GROUND[ground]} />
        <YAxisNum y={y} x={padL - 6} format={yFormat} label={yLabel} grid width={w - padR} />
        {diagonal && <line x1={x(Math.max(xd[0], yd[0]))} y1={y(Math.max(xd[0], yd[0]))} x2={x(Math.min(xd[1], yd[1]))} y2={y(Math.min(xd[1], yd[1]))} stroke="var(--grey-200)" strokeWidth={1.5} />}
        {hLines.map((h, i) => <g key={i}><line x1={padL} x2={w - padR} y1={y(h.y)} y2={y(h.y)} stroke={h.colour ?? 'var(--amber)'} strokeDasharray="4 3" />{h.label && <text x={w - padR - 2} y={y(h.y) - 4} textAnchor="end" style={{ fill: h.colour ?? 'var(--amber)' }}>{h.label}</text>}</g>)}
        {markers.map((m, i) => <g key={i}><line x1={x(m.x)} x2={x(m.x)} y1={padT} y2={height - padB} stroke={m.colour ?? 'var(--muted)'} strokeWidth={1.5} />{m.label && <text x={x(m.x) + 4} y={padT + 10} style={{ fill: 'var(--text-2)' }}>{m.label}</text>}</g>)}
        {series.map((s, i) => (
          <g key={i}>
            <path d={s.points.map((p, k) => `${k ? 'L' : 'M'}${x(p[0]).toFixed(1)} ${y(p[1]).toFixed(1)}`).join('')} fill="none" stroke={s.colour} strokeWidth={s.width ?? 1.5} strokeDasharray={s.dashed ? '4 3' : undefined} strokeLinejoin="round" />
            {s.dots && s.points.map((p, k) => <circle key={k} cx={x(p[0])} cy={y(p[1])} r={2.5} fill={s.colour} />)}
          </g>
        ))}
        <XAxisNum x={x} y={height - padB} format={xFormat} label={xLabel} />
      </svg>}
      {w === 0 && <div style={{ height }} />}
      {legend && series.length > 1 && <Legend items={series.map(s => ({ label: s.label, colour: s.colour, shape: 'line' as const }))} />}
    </div>
  )
}

/* ================= Histogram ================= */
export interface HistBin { x0: number; x1: number; count: number }
export function binValues(values: number[], domain: [number, number], nBins: number): HistBin[] {
  const [a, b] = domain, wdt = (b - a) / nBins
  const bins = Array.from({ length: nBins }, (_, i) => ({ x0: a + i * wdt, x1: a + (i + 1) * wdt, count: 0 }))
  for (const v of values) { if (v < a || v > b) continue; bins[Math.min(nBins - 1, Math.floor((v - a) / wdt))].count++ }
  return bins
}
export interface HistogramProps extends TestIdProps {
  values?: number[]; bins?: HistBin[]; nBins?: number; domain?: [number, number]; colour?: string
  overlay?: { values?: number[]; bins?: HistBin[]; colour: string; label: string }
  threshold?: { value: number; label?: string; colour?: string }
  markers?: { x: number; label?: string; colour?: string; band?: [number, number] }[]
  dots?: { x: number; colour?: string }[]
  highlightBin?: (bin: HistBin, i: number) => boolean; highlightColour?: string
  height?: number; width?: number; xLabel?: string; yLabel?: string; format?: (v: number) => string; label?: string; style?: CSSProperties; showCounts?: boolean
}
/** Bars over bins, optional second series, threshold line, labelled markers with CI bands, and dots (models-3 null plot). */
export function Histogram({ values, bins, nBins = 20, domain, colour = '#d1d5db', overlay, threshold, markers = [], dots = [], highlightBin, highlightColour = 'var(--blue)', height = 160, width, xLabel, yLabel, format, label, style, showCounts = true, ...t }: HistogramProps) {
  const [ref, w] = useWidth(width)
  const dom: [number, number] = domain ?? (bins?.length ? [bins[0].x0, bins[bins.length - 1].x1] : extent([values ?? [], overlay?.values ?? []]))
  const b = bins ?? binValues(values ?? [], dom, nBins)
  const ob = overlay ? overlay.bins ?? binValues(overlay.values ?? [], dom, b.length) : null
  const padL = showCounts ? 34 : 8, padR = 10, padT = markers.some(m => m.label) ? 18 : 8, padB = (xLabel ? 32 : 22) + (dots.length ? 14 : 0)
  const maxC = Math.max(1, ...b.map(d => d.count), ...(ob ?? []).map(d => d.count))
  const x = scaleLinear().domain(dom).range([padL, Math.max(padL + 1, w - padR)])
  const plotBottom = height - padB + (dots.length ? 0 : 0)
  const y = scaleLinear().domain([0, maxC]).range([plotBottom - (dots.length ? 0 : 0), padT])
  return (
    <div ref={ref} className="k-plot" style={style} data-testid={tid(t)}>
      {w > 0 && <svg width={w} height={height} role="img" aria-label={label ?? `histogram, ${b.length} bins`}>
        {showCounts && <YAxisNum y={y} x={padL - 6} n={3} format={v => fmtInt(v)} label={yLabel} />}
        {markers.filter(m => m.band).map((m, i) => <rect key={`b${i}`} x={x(m.band![0])} width={Math.max(1, x(m.band![1]) - x(m.band![0]))} y={padT} height={plotBottom - padT} fill={m.colour ?? 'var(--green)'} opacity={0.14} />)}
        {b.map((d, i) => { const hl = highlightBin?.(d, i); return <rect key={i} x={x(d.x0) + 0.5} width={Math.max(0.5, x(d.x1) - x(d.x0) - 1)} y={y(d.count)} height={plotBottom - y(d.count)} fill={hl ? highlightColour : colour}><title>{`${fmtNum(d.x0, d.x1 - d.x0)}–${fmtNum(d.x1, d.x1 - d.x0)}: ${d.count}`}</title></rect> })}
        {ob && ob.map((d, i) => <rect key={`o${i}`} x={x(d.x0) + 0.5} width={Math.max(0.5, x(d.x1) - x(d.x0) - 1)} y={y(d.count)} height={plotBottom - y(d.count)} fill={overlay!.colour} opacity={0.55} />)}
        {threshold && <g><line x1={x(threshold.value)} x2={x(threshold.value)} y1={padT - 4} y2={plotBottom} stroke={threshold.colour ?? 'var(--amber)'} strokeWidth={1.5} strokeDasharray="4 3" />{threshold.label && <text x={x(threshold.value) + 4} y={padT + 6} style={{ fill: threshold.colour ?? 'var(--amber)' }}>{threshold.label}</text>}</g>}
        {markers.map((m, i) => <g key={i}><line x1={x(m.x)} x2={x(m.x)} y1={padT - 6} y2={plotBottom} stroke={m.colour ?? 'var(--text)'} strokeWidth={1.5} />{m.label && <text x={x(m.x) + (i % 2 ? 4 : -4)} y={padT - 7} textAnchor={i % 2 ? 'start' : 'end'} style={{ fill: m.colour ?? 'var(--text)' }}>{m.label}</text>}</g>)}
        {dots.map((d, i) => <circle key={`d${i}`} cx={x(d.x)} cy={plotBottom + 9} r={3.5} fill={d.colour ?? '#4b5563'} />)}
        <XAxisNum x={x} y={height - (xLabel ? 32 : 22) + (dots.length ? 14 : 0)} format={format} label={xLabel} n={5} />
      </svg>}
      {w === 0 && <div style={{ height }} />}
      {overlay && <Legend items={[{ label: label ?? 'values', colour }, { label: overlay.label, colour: overlay.colour }]} />}
    </div>
  )
}

/* ================= Bars ================= */
export interface BarSeries { key: string; label: string; colour: string; values: number[] }
export interface BarsProps extends TestIdProps {
  categories: string[]; series: BarSeries[]; mode?: 'grouped' | 'stacked'; height?: number; width?: number; yMax?: number
  valueLabels?: boolean; format?: (v: number) => string; yLabel?: string; highlight?: string | null; onBarClick?: (category: string, seriesKey: string) => void; legend?: boolean; style?: CSSProperties
}
/** Grouped or stacked vertical bars with category labels and optional value labels. */
export function Bars({ categories, series, mode = 'grouped', height = 180, width, yMax, valueLabels = true, format = v => fmtInt(v), yLabel, highlight, onBarClick, legend = true, style, ...t }: BarsProps) {
  const [ref, w] = useWidth(width)
  const padL = 36, padR = 8, padT = 16, padB = 22
  const totals = categories.map((_, ci) => mode === 'stacked' ? series.reduce((s, se) => s + (se.values[ci] ?? 0), 0) : Math.max(0, ...series.map(se => se.values[ci] ?? 0)))
  const max = yMax ?? Math.max(1, ...totals) * 1.08
  const y = scaleLinear().domain([0, max]).range([height - padB, padT])
  const band = (w - padL - padR) / Math.max(1, categories.length)
  const inner = band * 0.72
  return (
    <div ref={ref} className="k-plot" style={style} data-testid={tid(t)}>
      {w > 0 && <svg width={w} height={height} role="img" aria-label={`bar chart of ${categories.length} categories`}>
        <YAxisNum y={y} x={padL - 6} n={4} format={format} label={yLabel} grid width={w - padR} />
        {categories.map((c, ci) => {
          const x0 = padL + ci * band + (band - inner) / 2
          let acc = 0
          const dim = highlight != null && highlight !== c
          return (
            <g key={c} opacity={dim ? 0.4 : 1}>
              {series.map((s, si) => {
                const v = s.values[ci] ?? 0
                const bw = mode === 'stacked' ? inner : inner / series.length
                const bx = mode === 'stacked' ? x0 : x0 + si * bw
                const yTop = mode === 'stacked' ? y(acc + v) : y(v)
                const yBot = mode === 'stacked' ? y(acc) : y(0)
                acc += v
                return (
                  <g key={s.key} onClick={onBarClick ? () => onBarClick(c, s.key) : undefined} style={onBarClick ? { cursor: 'pointer' } : undefined}>
                    <rect x={bx + 0.5} width={Math.max(1, bw - 1)} y={yTop} height={Math.max(0, yBot - yTop)} fill={s.colour} rx={1.5}><title>{`${c} · ${s.label}: ${format(v)}`}</title></rect>
                    {valueLabels && mode === 'grouped' && bw > 14 && <text x={bx + bw / 2} y={yTop - 3} textAnchor="middle" className="val-label">{format(v)}</text>}
                  </g>
                )
              })}
              {valueLabels && mode === 'stacked' && <text x={x0 + inner / 2} y={y(acc) - 3} textAnchor="middle" className="val-label">{format(acc)}</text>}
              <text x={x0 + inner / 2} y={height - padB + 13} textAnchor="middle">{c}</text>
            </g>
          )
        })}
        <line x1={padL} x2={w - padR} y1={height - padB} y2={height - padB} stroke="var(--border)" />
      </svg>}
      {w === 0 && <div style={{ height }} />}
      {legend && series.length > 1 && <Legend items={series.map(s => ({ label: s.label, colour: s.colour }))} />}
    </div>
  )
}

/* ================= Scatter ================= */
export interface ScatterPoint { x: number; y: number; id: string; category?: string; label?: string }
export interface ScatterProps extends TestIdProps {
  points: ScatterPoint[]; colours?: Record<string, string>; xDomain?: [number, number]; yDomain?: [number, number]; height?: number; width?: number
  xLabel?: string; yLabel?: string; selected?: string[]; onSelect?: (id: string) => void; r?: number; diagonal?: boolean; legend?: boolean; style?: CSSProperties
}
/** Points coloured by category; click selects (selected points get a ring, others dim). */
export function Scatter({ points, colours = {}, xDomain, yDomain, height = 220, width, xLabel, yLabel, selected = [], onSelect, r = 3, diagonal, legend = true, style, ...t }: ScatterProps) {
  const [ref, w] = useWidth(width)
  const padL = 40, padR = 12, padT = 14, padB = xLabel ? 32 : 22
  const xd = xDomain ?? (() => { const [a, b] = extent([points.map(p => p.x)]); const m = (b - a) * 0.05 || 1; return [a - m, b + m] as [number, number] })()
  const yd = yDomain ?? (() => { const [a, b] = extent([points.map(p => p.y)]); const m = (b - a) * 0.05 || 1; return [a - m, b + m] as [number, number] })()
  const x = scaleLinear().domain(xd).range([padL, Math.max(padL + 1, w - padR)])
  const y = scaleLinear().domain(yd).range([height - padB, padT])
  const sel = new Set(selected)
  const cats = [...new Set(points.map(p => p.category).filter(Boolean))] as string[]
  return (
    <div ref={ref} className="k-plot" style={style} data-testid={tid(t)}>
      {w > 0 && <svg width={w} height={height} role="img" aria-label={`scatter of ${points.length} points`}>
        <YAxisNum y={y} x={padL - 6} label={yLabel} grid width={w - padR} />
        {diagonal && <line x1={x(xd[0])} y1={y(xd[0])} x2={x(xd[1])} y2={y(xd[1])} stroke="var(--grey-200)" />}
        {points.map(p => {
          const c = (p.category && colours[p.category]) || 'var(--blue)'
          const on = sel.has(p.id)
          return <circle key={p.id} cx={x(p.x)} cy={y(p.y)} r={on ? r + 1.5 : r} fill={c} fillOpacity={sel.size && !on ? 0.3 : 0.85} stroke={on ? 'var(--text)' : 'none'} strokeWidth={1.2}
            style={onSelect ? { cursor: 'pointer' } : undefined} onClick={onSelect ? () => onSelect(p.id) : undefined} data-point={p.id}><title>{p.label ?? `${p.id} (${fmtNum(p.x, 0.01)}, ${fmtNum(p.y, 0.01)})`}</title></circle>
        })}
        <XAxisNum x={x} y={height - padB} label={xLabel} />
      </svg>}
      {w === 0 && <div style={{ height }} />}
      {legend && cats.length > 0 && <Legend items={cats.map(c => ({ label: c, colour: colours[c] ?? 'var(--blue)', shape: 'dot' as const }))} />}
    </div>
  )
}

/* ================= Heatmap ================= */
export const RAMPS: Record<string, string[]> = {
  blue: ['#eef5ff', '#bfdcff', '#6fb2ff', '#0a84ff'],
  green: ['#fff7ec', '#dff2e7', '#8fd0ad', '#3aa874'],
  amber: ['#fff8ef', '#ffe2b8', '#f5b659', '#e8900c'],
  purple: ['#f6f1ff', '#ddd0ff', '#b39cf8', '#8e5cf7'],
  diverging: ['#e5484d', '#fdeaea', '#f5f6f8', '#e6f1ff', '#0a84ff'],
}
export interface HeatmapProps extends TestIdProps {
  rows: string[]; cols: string[]; values: (number | null)[][]; domain?: [number, number]; ramp?: keyof typeof RAMPS | string[]
  showValues?: boolean; format?: (v: number) => string; cellHeight?: number; gap?: number; rowLabelWidth?: number; colLabelHeight?: number; width?: number
  flagged?: (r: number, c: number) => boolean; selectedCols?: number[]; selectedRows?: number[]; onCellClick?: (r: number, c: number) => void
  nullLabel?: string; legendLabel?: string; legend?: boolean; style?: CSSProperties
}
/** Rows × cols matrix of rounded tiles with a colour ramp, printed values, "?" null cells, red flagged cells, selected columns. */
export function Heatmap({ rows, cols, values, domain = [0, 1], ramp = 'blue', showValues = true, format = v => v.toFixed(2), cellHeight = 30, gap = 4, rowLabelWidth = 110, colLabelHeight = 22, width, flagged, selectedCols = [], selectedRows = [], onCellClick, nullLabel = '?', legendLabel, legend = true, style, ...t }: HeatmapProps) {
  const [ref, w] = useWidth(width)
  const colours = Array.isArray(ramp) ? ramp : RAMPS[ramp] ?? RAMPS.blue
  const colour = scaleLinear<string, string>().domain(colours.map((_, i) => domain[0] + (i / (colours.length - 1)) * (domain[1] - domain[0]))).range(colours).clamp(true)
  const cw = Math.max(8, (w - rowLabelWidth - gap * cols.length) / Math.max(1, cols.length))
  const h = colLabelHeight + rows.length * (cellHeight + gap)
  const darkAt = domain[0] + (domain[1] - domain[0]) * 0.62
  return (
    <div ref={ref} className="k-plot" style={style} data-testid={tid(t)}>
      {w > 0 && <svg width={w} height={h} role="img" aria-label={`heatmap ${rows.length} × ${cols.length}`}>
        {cols.map((c, ci) => <text key={c} x={rowLabelWidth + ci * (cw + gap) + cw / 2} y={colLabelHeight - 8} textAnchor="middle" style={selectedCols.includes(ci) ? { fill: 'var(--blue-600)', fontWeight: 600 } : undefined}>{c}</text>)}
        {rows.map((r, ri) => (
          <g key={r} transform={`translate(0,${colLabelHeight + ri * (cellHeight + gap)})`}>
            <text x={0} y={cellHeight / 2 + 3} style={selectedRows.includes(ri) ? { fill: 'var(--blue-600)', fontWeight: 600 } : { fill: 'var(--text-2)' }}>{r}</text>
            {cols.map((_, ci) => {
              const v = values[ri]?.[ci] ?? null
              const cx0 = rowLabelWidth + ci * (cw + gap)
              const flag = flagged?.(ri, ci)
              const label = `${r} · ${cols[ci]}: ${v == null ? 'no data' : format(v)}${flag ? ' · flagged' : ''}`
              return (
                <g key={ci} className={cx('k-hm-cell', onCellClick && 'clickable')} onClick={onCellClick ? () => onCellClick(ri, ci) : undefined}
                  tabIndex={onCellClick ? 0 : undefined} role={onCellClick ? 'button' : undefined} aria-label={onCellClick ? label : undefined}
                  onKeyDown={onCellClick ? e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onCellClick(ri, ci) } } : undefined}>
                  <title>{label}</title>
                  <rect x={cx0} y={0} width={cw} height={cellHeight} rx={4} fill={v == null ? '#fff' : flag ? 'var(--red-100)' : colour(v)} stroke={v == null ? 'var(--border-strong)' : flag ? 'var(--red)' : 'none'} strokeWidth={flag ? 1.5 : 1} />
                  {v == null ? <text x={cx0 + cw / 2} y={cellHeight / 2 + 3} textAnchor="middle">{nullLabel}</text>
                    : showValues && cw > 22 && <text x={cx0 + cw / 2} y={cellHeight / 2 + 3} textAnchor="middle" style={{ fill: flag ? 'var(--k-red-text)' : v >= darkAt ? '#fff' : 'var(--text)' }}>{flag ? '! ' : ''}{format(v)}</text>}
                </g>
              )
            })}
          </g>
        ))}
        {selectedCols.map(ci => <rect key={`sc${ci}`} x={rowLabelWidth + ci * (cw + gap) - 2} y={colLabelHeight - 2} width={cw + 4} height={rows.length * (cellHeight + gap)} rx={6} fill="none" stroke="var(--blue)" strokeWidth={1.5} pointerEvents="none" />)}
      </svg>}
      {legend && <div className="k-hm-legend" style={{ marginTop: 6 }}>{legendLabel && <span>{legendLabel}</span>}<span className="ramp">{colours.map(c => <i key={c} style={{ background: c }} />)}</span><span>{format(domain[0])} → {format(domain[1])}</span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginLeft: 8 }}><i style={{ width: 14, height: 10, border: '1px solid var(--border-strong)', borderRadius: 2, display: 'inline-block' }} />{nullLabel} no data</span></div>}
    </div>
  )
}

/* ================= BandStrip ================= */
export interface BandSegment { start: number; end: number; colour?: string; kind?: 'train' | 'validation' | 'test' | 'gap' | BandKind; label?: string }
const SEG_COLOUR: Record<string, string> = { train: '#a8c1ec', validation: '#fdc77e', test: '#86d69e', gap: '#eef0f3', detected: 'var(--blue)', annotated: 'var(--green)', selected: 'var(--amber)', artifact: 'var(--red)', grey: '#dfe3e8' }
export interface BandStripProps extends TestIdProps {
  rows: { label: string; segments: BandSegment[] }[]; domain: [number, number]; timeUnit?: 'h' | 's' | 'none'
  rowHeight?: number; gap?: number; labelWidth?: number; width?: number; legend?: { label: string; colour: string }[]; segmentGap?: number; style?: CSSProperties
}
/** Horizontal coloured segments on a shared axis: train/validation/test blocks (models-1) or coverage ribbons (explore). Domain in seconds. */
export function BandStrip({ rows, domain, timeUnit = 'none', rowHeight = 14, gap = 6, labelWidth = 70, width, legend, segmentGap = 3, style, ...t }: BandStripProps) {
  const [ref, w] = useWidth(width)
  const axisH = timeUnit === 'none' ? 0 : 20
  const h = rows.length * (rowHeight + gap) + axisH
  const x = makeX(domain[0], domain[1], w, labelWidth, 4)
  return (
    <div ref={ref} className="k-plot" style={style} data-testid={tid(t)}>
      {w > 0 && <svg width={w} height={h} role="img" aria-label={`band strip, ${rows.length} rows`}>
        {rows.map((r, ri) => (
          <g key={r.label} transform={`translate(0,${ri * (rowHeight + gap)})`}>
            <text x={0} y={rowHeight / 2 + 3} style={{ fill: 'var(--text-2)' }}>{r.label}</text>
            {r.segments.map((s, si) => { const x0 = x(s.start) + segmentGap / 2, x1 = x(s.end) - segmentGap / 2; return <rect key={si} x={x0} y={0} width={Math.max(1, x1 - x0)} height={rowHeight} rx={2} fill={s.colour ?? SEG_COLOUR[s.kind ?? 'grey'] ?? '#dfe3e8'}><title>{s.label ?? s.kind ?? ''}</title></rect> })}
          </g>
        ))}
        {timeUnit === 'h' && <TimeAxis x={x} y={rows.length * (rowHeight + gap)} t0={domain[0]} t1={domain[1]} n={6} />}
        {timeUnit === 's' && <XAxisNum x={scaleLinear().domain(domain).range(x.range())} y={rows.length * (rowHeight + gap)} format={v => `${fmtNum(v, 1)} s`} />}
      </svg>}
      {legend && <Legend items={legend} />}
    </div>
  )
}

/* ================= NullBand ================= */
export interface NullBandProps extends TestIdProps {
  values: number[]; p5: number[]; p95: number[]; p50?: number[]; x?: number[]
  colour?: string; bandColour?: string; threshold?: { value: number; label?: string }; height?: number; width?: number
  xLabel?: string; yLabel?: string; xFormat?: (v: number) => string; yFormat?: (v: number) => string; labels?: { values?: string; band?: string }; style?: CSSProperties
}
/** A series drawn over its null p5–p95 band (and optional p50). */
export function NullBand({ values, p5, p95, p50, x: xs, colour = 'var(--trace-blue)', bandColour = 'rgba(107,114,128,0.18)', threshold, height = 160, width, xLabel, yLabel, xFormat, yFormat, labels = {}, style, ...t }: NullBandProps) {
  const [ref, w] = useWidth(width)
  const padL = 40, padR = 12, padT = 12, padB = xLabel ? 32 : 22
  const X = xs ?? values.map((_, i) => i)
  const [a, b] = extent([values, p5, p95, threshold ? [threshold.value] : []])
  const m = (b - a) * 0.08 || 0.1
  const x = scaleLinear().domain(extent([X])).range([padL, Math.max(padL + 1, w - padR)])
  const y = scaleLinear().domain([a - m, b + m]).range([height - padB, padT])
  const line = (vs: number[]) => vs.map((v, i) => `${i ? 'L' : 'M'}${x(X[i]).toFixed(1)} ${y(v).toFixed(1)}`).join('')
  const area = X.length ? `${line(p95)}${[...p5].reverse().map((v, k) => { const i = p5.length - 1 - k; return `L${x(X[i]).toFixed(1)} ${y(v).toFixed(1)}` }).join('')}Z` : ''
  return (
    <div ref={ref} className="k-plot" style={style} data-testid={tid(t)}>
      {w > 0 && <svg width={w} height={height} role="img" aria-label="series against its null band">
        <YAxisNum y={y} x={padL - 6} format={yFormat} label={yLabel} grid width={w - padR} />
        <path d={area} fill={bandColour} />
        {p50 && <path d={line(p50)} fill="none" stroke="var(--muted-2)" strokeDasharray="3 3" />}
        {threshold && <g><line x1={padL} x2={w - padR} y1={y(threshold.value)} y2={y(threshold.value)} stroke="var(--amber)" strokeDasharray="4 3" />{threshold.label && <text x={w - padR - 2} y={y(threshold.value) - 4} textAnchor="end" style={{ fill: 'var(--amber)' }}>{threshold.label}</text>}</g>}
        <path d={line(values)} fill="none" stroke={colour} strokeWidth={1.3} strokeLinejoin="round" />
        <XAxisNum x={x} y={height - padB} format={xFormat} label={xLabel} />
      </svg>}
      {w === 0 && <div style={{ height }} />}
      <Legend items={[{ label: labels.values ?? 'observed', colour, shape: 'line' }, { label: labels.band ?? 'null p5–p95', colour: bandColour }]} />
    </div>
  )
}

/* ================= SmallMultiples ================= */
export interface SmallMultiplesProps<T> extends TestIdProps {
  items: T[]
  /** Render one cell. `yDomain` is shared across ALL items (never per cell). */
  render: (item: T, ctx: { yDomain: [number, number]; index: number }) => ReactNode
  /** Values used to compute the shared y domain (ignored when `yDomain` is given). */
  getValues?: (item: T) => number[]; yDomain?: [number, number]
  /** Spec P8: at most `cap` cells at once (default 10). */
  cap?: number; columns?: number; title?: ReactNode; unitLabel?: string
  onSelect?: (item: T, index: number) => void; selectedIndex?: number | null; cellStyle?: CSSProperties; style?: CSSProperties
}
/** Grid of child plots capped at `cap` with "‹ 1–10 of 112 ›" paging and a seeded "resample" (P8), sharing one y domain. */
export function SmallMultiples<T>({ items, render, getValues, yDomain, cap = 10, columns = 5, title, unitLabel = 'shared y · mV', onSelect, selectedIndex, cellStyle, style, ...t }: SmallMultiplesProps<T>) {
  const [page, setPage] = useState(1)
  const [seed, setSeed] = useState<number | null>(null)
  const dom = useMemo<[number, number]>(() => {
    if (yDomain) return yDomain
    if (!getValues) return [-1, 1]
    const [a, b] = extent(items.map(getValues)); const m = (b - a) * 0.06 || 0.1
    return [a - m, b + m]
  }, [items, getValues, yDomain])
  const pageCount = Math.max(1, Math.ceil(items.length / cap))
  const p = Math.min(page, pageCount)
  const idx = seed !== null ? sampleIndices(items.length, cap, seed) : Array.from({ length: Math.min(cap, Math.max(0, items.length - (p - 1) * cap)) }, (_, i) => (p - 1) * cap + i)
  const over = items.length > cap
  return (
    <div className="k-sm" style={style} data-testid={tid(t)}>
      <div className="k-sm-head">
        {title && <span className="t">{title}</span>}
        <span>{unitLabel}</span>
        <span className="k-spacer" />
        {seed !== null
          ? <><span>{Math.min(cap, items.length)} of {fmtInt(items.length)} sampled</span><Button size="sm" variant="ghost" onClick={() => setSeed(null)} testid={tid(t) ? `${tid(t)}-pages` : undefined}>show in order</Button></>
          : over && <Pager format="range" page={p} pageCount={pageCount} total={items.length} pageSize={cap} onPage={setPage} label="page" testid={tid(t) ? `${tid(t)}-pager` : undefined} />}
        {over && <Button size="sm" variant="link" icon="shuffle" onClick={() => setSeed(s => (s ?? 0) + 1)} testid={tid(t) ? `${tid(t)}-resample` : undefined}>resample</Button>}
      </div>
      <div className="k-sm-grid" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
        {idx.map(i => (
          <div key={i} className={cx('k-sm-cell', onSelect && 'clickable', selectedIndex === i && 'on')} style={cellStyle}
            onClick={onSelect ? () => onSelect(items[i], i) : undefined} tabIndex={onSelect ? 0 : undefined} role={onSelect ? 'button' : undefined}
            onKeyDown={onSelect ? e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(items[i], i) } } : undefined}>
            {render(items[i], { yDomain: dom, index: i })}
          </div>
        ))}
      </div>
      {!items.length && <div className="k-plot-empty" style={{ position: 'static', padding: 16 }}>nothing to plot</div>}
    </div>
  )
}
