/* What the seven type views share (fixup-h): the drawing context, the axis and resolution helpers, the image
 * canvas, the draggable cut, and the one loader that turns a stretch of a channel into real samples. */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { getWindow, type AdapterCard, type EncodingFrame, type EnvelopeSeries, type Payload, type Step } from '../../api'
import { TimeAxis } from '../../charts/primitives'
import { clamp, makeX, type XScale } from '../../charts/scale'
import { useSize } from '../../charts/useSize'
import type { DisplayUnit } from '../../charts/units'
import type { SlideTrace } from '../../kit'
import type { SourceSpan } from '../../state'

/** What a type view draws against. The chain row and the block page hand over the same thing; the block page
 *  sets `interactive`, and that flag is the WHOLE difference between the two tiers — one component per view. */
export interface ViewCtx {
  x: XScale; width: number; height: number
  t0: number; t1: number
  /** the nearest upstream Signal, drawn grey beneath */
  ghost?: EnvelopeSeries | null
  ghostUnit?: DisplayUnit
  /** chain thumbnail: off. Block settings page: on (hover, click, drag, and the evidence beside the shape). */
  interactive?: boolean
  hideKey?: boolean
  sourceStyle?: boolean
}

/** Everything the settings tier knows beyond the payload: the step and its card, what came before it, the span. */
export interface ProcessProps {
  payload: Payload | null
  ctx: ViewCtx
  step: Step
  card: AdapterCard | undefined
  index: number
  /** the payload of the step immediately before (null for the first step or when it has no result) */
  upstream: Payload | null
  /** the step after this one, when there is one */
  next: Step | null; nextCard: AdapterCard | undefined
  source: SourceSpan
  /** the unit the source channel is drawn in ('mV', or '' when the recording declares none) */
  sourceUnit: string
  stale: boolean
  setParam: (name: string, value: unknown) => void
  jobId: number | null
  dbRunId: number | null
  chainName: string
}

export function finiteRange(v: ReadonlyArray<number | null | undefined>): [number, number] | null {
  let lo = Infinity, hi = -Infinity
  for (const x of v) if (x !== null && x !== undefined && Number.isFinite(x)) { if (x < lo) lo = x; if (x > hi) hi = x }
  return lo <= hi ? [lo, hi] : null
}

export const Empty = ({ text }: { text: string }) => <div className="an-plot-empty">{text}</div>

export const fmtN = (v: number): string => {
  if (!Number.isFinite(v)) return '—'
  const a = Math.abs(v)
  return a === 0 ? '0' : a >= 1000 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : a >= 0.01 ? v.toFixed(3) : v.toExponential(2)
}

/** How a series was drawn, in words that can be checked: every sample, or a min/max envelope of how many. */
export function resolutionWords(env: { n_source?: number; n_points?: number; decimated?: boolean } | null | undefined, fs?: number): string {
  if (!env || !env.n_source) return ''
  const rate = fs ? ` · ${fs % 1 === 0 ? fs : fs.toFixed(2)} Hz` : ''
  return env.decimated
    ? `${env.n_source.toLocaleString()} samples${rate} · min/max envelope, ${(env.n_points ?? 0).toLocaleString()} points — each column carries its true minimum and maximum`
    : `${env.n_source.toLocaleString()} samples${rate} · every sample drawn`
}

/** y labels on either side of a plot, in the axis's own colour (a dual-axis plot must say whose numbers are whose). */
export function AxisLabels({ y, values, side, width, unit = '', colour = 'var(--muted)' }: { y: XScale; values: number[]; side: 'left' | 'right'; width: number; unit?: string; colour?: string }) {
  const [d0, d1] = y.domain()
  const range = Math.abs(d1 - d0) || 1
  const nd = Math.min(6, Math.max(1, Math.ceil(-Math.log10(range)) + 2))
  return (
    <g pointerEvents="none" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3, strokeLinejoin: 'round' }} data-axis={side}>
      {values.map((v, i) => (
        <text key={i} x={side === 'left' ? 4 : width - 4} y={clamp(y(v) + 3, 10, y.range()[0] + 2)} textAnchor={side === 'left' ? 'start' : 'end'} style={{ fill: colour }}>
          {(v > 0 ? '+' : '') + (v === 0 ? '0' : v.toFixed(nd))}{unit ? ' ' + unit : ''}
        </text>
      ))}
    </g>
  )
}

/* ---------------- images ---------------- */
const VIRIDIS: [number, number, number][] = [[68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37]]
export function viridis(u: number): [number, number, number] {
  const k = Math.max(0, Math.min(0.9999, u)) * (VIRIDIS.length - 1); const i = Math.floor(k); const f = k - i
  const a = VIRIDIS[i], b = VIRIDIS[i + 1]
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]
}
/** grey: not a point on the viridis ramp, so a cell with no data cannot be read as a value */
export const NO_DATA: [number, number, number] = [156, 163, 175]
export const NO_DATA_CSS = `rgb(${NO_DATA.join(',')})`

function bytesOf(b64: string): Uint8Array {
  const raw = atob(b64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

/** uint8 pixels (1 or 3 channels, row-major) on a canvas: viridis for one channel, the bytes themselves for three,
 *  and the no-data mask in grey. The canvas is the pixel grid; CSS stretches it, pixelated. */
export function PixelCanvas({ pixels, mask, shape, channels, style, testid }: {
  pixels: string; mask?: string | null; shape: [number, number]; channels: number; style?: React.CSSProperties; testid?: string
}) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const c = ref.current
    if (!c) return
    const [h, w] = shape
    const bytes = bytesOf(pixels)
    const blank = mask ? bytesOf(mask) : null
    const img = new ImageData(w, h)
    for (let i = 0; i < w * h; i++) {
      let r: number, g: number, b: number
      if (blank && blank[i]) [r, g, b] = NO_DATA
      else if (channels === 3) { r = bytes[i * 3]; g = bytes[i * 3 + 1]; b = bytes[i * 3 + 2] }
      else [r, g, b] = viridis(bytes[i * channels] / 255)
      img.data[i * 4] = r; img.data[i * 4 + 1] = g; img.data[i * 4 + 2] = b; img.data[i * 4 + 3] = 255
    }
    c.width = w; c.height = h
    c.getContext('2d')?.putImageData(img, 0, 0)
  }, [pixels, mask, shape[0], shape[1], channels])   // eslint-disable-line react-hooks/exhaustive-deps
  return <canvas ref={ref} data-testid={testid} data-shape={`${shape[0]}x${shape[1]}`} style={{ imageRendering: 'pixelated', display: 'block', ...style }} />
}

export const FrameCanvas = ({ frame, style, testid }: { frame: EncodingFrame; style?: React.CSSProperties; testid?: string }) =>
  <PixelCanvas pixels={frame.pixels_b64} mask={frame.nan_b64} shape={frame.shape} channels={frame.channels} style={style} testid={testid} />

/** The colour bar: the ramp with the REAL value range at its ends, and the no-data grey named beside it. */
export function ColourBar({ range, channels = 1, noData, width = 160 }: { range: [number, number] | null; channels?: number; noData?: { cells: number; of: number } | null; width?: number }) {
  const stops = Array.from({ length: 9 }, (_, i) => `rgb(${viridis(i / 8).map(Math.round).join(',')}) ${(i / 8) * 100}%`).join(', ')
  return (
    <div className="mono" data-testid="colour-bar" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10.5, color: 'var(--muted)', flexWrap: 'wrap' }}>
      {channels === 3
        ? <span>three channels drawn as RGB · bytes {range ? `${fmtN(range[0])} … ${fmtN(range[1])}` : '—'} · no colour bar applies</span>
        : range
          ? <><span data-testid="colour-bar-lo">{fmtN(range[0])}</span><span style={{ width, height: 9, borderRadius: 3, background: `linear-gradient(90deg, ${stops})` }} /><span data-testid="colour-bar-hi">{fmtN(range[1])}</span><span>· one range for every frame of this result</span></>
          : <span>no finite value: there is no range to state</span>}
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }} data-testid="no-data-key">
        <i style={{ width: 12, height: 9, borderRadius: 2, background: NO_DATA_CSS, display: 'inline-block' }} />
        no data{noData && noData.cells > 0 ? ` · ${noData.cells.toLocaleString()} of ${noData.of.toLocaleString()} cells shown` : noData ? ' · none in the frames shown' : ''}
      </span>
    </div>
  )
}

/* ---------------- settings-tier scaffolding ---------------- */
/** A labelled strip on the page's time axis; the children draw into an svg of the measured width. */
export function Strip({ label, sub, height, t0, t1, children, axis, testid }: { label: string; sub?: ReactNode; height: number; t0: number; t1: number; children: (x: XScale, w: number, h: number) => ReactNode; axis?: boolean; testid?: string }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width)
  const x = makeX(t0, t1, w)
  const h = height + (axis ? 18 : 0)
  return (
    <div className="bp-strip" data-testid={testid}>
      <div className="lbl"><b>{label}</b>{sub}</div>
      <div className="sur plot-surface" ref={ref} style={{ height: h }}>
        {size.width > 0 && <svg width={w} height={h}>{children(x, w, height)}{axis && <TimeAxis x={x} y={height + 2} t0={t0} t1={t1} n={7} ends />}</svg>}
      </div>
    </div>
  )
}

/** A surface of the measured width with no label gutter: the type view at full size. */
export function Surface({ height, t0, t1, children, testid, axis = true }: { height: number; t0: number; t1: number; children: (x: XScale, w: number) => ReactNode; testid?: string; axis?: boolean }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width)
  const x = makeX(t0, t1, w)
  return (
    <>
      <div className="plot-surface" ref={ref} style={{ height, position: 'relative' }} data-testid={testid}>
        {size.width > 0 && children(x, w)}
      </div>
      {axis && <div style={{ paddingTop: 2 }}><svg width="100%" height={20}>{size.width > 0 && <TimeAxis x={x} y={2} t0={t0} t1={t1} n={7} ends />}</svg></div>}
    </>
  )
}

export const StaleVeil = ({ on }: { on: boolean }) => on ? <><div className="an-plot-veil" /><span className="an-stale-pill" style={{ top: 4 }}>⏱ last run shown · stale</span></> : null

/** A draggable horizontal cut line (pointer capture on a wide invisible grab rect). Without `onChange` it is a
 *  plain marked level: a threshold that exists but is not this block's to move. */
export function CutLineH({ y, value, onChange, width, label, colour = 'var(--amber)', testid }: { y: XScale; value: number; onChange?: (v: number) => void; width: number; label: string; colour?: string; testid?: string }) {
  const drag = useRef(false)
  const py = clamp(y(value), 0, y.range()[0])
  const [lo, hi] = [Math.min(...y.domain()), Math.max(...y.domain())]
  const move = (e: React.PointerEvent<SVGRectElement>) => {
    if (!drag.current || !onChange) return
    const svg = e.currentTarget.ownerSVGElement; if (!svg) return
    const r = svg.getBoundingClientRect()
    onChange(+clamp(y.invert(e.clientY - r.top), lo, hi).toPrecision(4))
  }
  const text = `${label}${onChange ? ' · drag' : ''}`
  const bw = text.length * 6.1 + 12
  return (
    <g data-testid={testid} data-draggable={onChange ? '1' : '0'}>
      <line x1={0} x2={width} y1={py} y2={py} stroke={colour} strokeWidth={1.5} strokeDasharray={onChange ? undefined : '5 3'} />
      <rect x={width - bw - 4} y={py + 3} width={bw} height={14} rx={3} fill="var(--amber-100)" stroke={colour} />
      <text x={width - bw / 2 - 4} y={py + 13} textAnchor="middle" fill="#8a4b00" style={{ fontSize: 10 }}>{text}</text>
      {onChange && <rect x={0} y={py - 7} width={width} height={14} fill="transparent" style={{ cursor: 'ns-resize' }}
        onPointerDown={e => { drag.current = true; e.currentTarget.setPointerCapture(e.pointerId) }}
        onPointerMove={move}
        onPointerUp={e => { drag.current = false; e.currentTarget.releasePointerCapture(e.pointerId) }} />}
    </g>
  )
}

/** Hover state for an svg: the time under the pointer, or null. */
export function useHoverT(x: XScale): [number | null, { onPointerMove: (e: React.PointerEvent<SVGSVGElement>) => void; onPointerLeave: () => void }] {
  const [t, setT] = useState<number | null>(null)
  return [t, {
    onPointerMove: e => { const r = e.currentTarget.getBoundingClientRect(); setT(x.invert(e.clientX - r.left)) },
    onPointerLeave: () => setT(null),
  }]
}

/** index of the point of `t` nearest to `at` (t ascending) */
export function nearest(t: number[], at: number): number {
  let lo = 0, hi = t.length - 1
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (t[m] < at) lo = m; else hi = m }
  return Math.abs(t[lo] - at) <= Math.abs(t[hi] - at) ? lo : hi
}

/** A stretch of the source channel as real samples (or, past the pixel budget, a min/max envelope that says so). */
export function loadWindow(recordingId: number, t0: number, t1: number, px = 600): Promise<SlideTrace> {
  return getWindow(recordingId, t0, t1, px).then(w => ({ t: w.envelope.t, v: w.envelope.v, decimated: w.envelope.decimated, nSource: w.envelope.n_source }))
}
