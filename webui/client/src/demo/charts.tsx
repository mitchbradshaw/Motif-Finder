/* The demo's drawings: plain SVG, sized to their box, fed by pre-cooked numbers. Waveforms are never normalised
   (each trace is drawn on its own measured domain, in mV), as on the site (theme.css's fixed visual rules). */
import { useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react'
import { api, type Envelope, type Snip } from './api'

export function useWidth<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T | null>(null)
  const [w, setW] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(es => { for (const e of es) setW(Math.floor(e.contentRect.width)) })
    ro.observe(el)
    setW(Math.floor(el.getBoundingClientRect().width))
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

export type Box = { s: number; e: number; tone?: 'auto' | 'mine' | 'ref' | 'lib' | 'match'; alpha?: number; mark?: number | null }

const TONE: Record<string, string> = { auto: '#8e5cf7', mine: '#0a84ff', ref: '#e8900c', lib: '#22a06b', match: '#0d9488' }

function niceStep(rangeH: number, maxTicks: number): number {
  const cands = [1 / 60, 2 / 60, 5 / 60, 10 / 60, 15 / 60, 0.5, 1, 2, 3, 4, 6, 12]
  return cands.find(c => rangeH / c <= maxTicks) ?? 12
}

export function hLabel(h: number): string {
  const hh = Math.floor(h + 1e-9)
  const mm = Math.round((h - hh) * 60)
  return mm === 0 ? `${hh} h` : `${hh}:${String(mm).padStart(2, '0')}`
}

type TraceProps = {
  sid: number; fs: number; a: number; b: number; height?: number; combo?: string
  boxes?: Box[]; span?: [number, number] | null; onSpan?: (a: number, b: number) => void
  onBox?: (i: number) => void; axis?: boolean; color?: string; testid?: string; tour?: string; ghost?: boolean
}

/** One channel between samples a and b: the min/max band per pixel, event boxes, a draggable selection. */
export function Trace({ sid, fs, a, b, height = 220, combo, boxes, span, onSpan, onBox, axis = true, color, testid, tour, ghost }: TraceProps) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [env, setEnv] = useState<Envelope | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [drag, setDrag] = useState<[number, number] | null>(null)
  const px = Math.max(200, Math.min(1600, w))
  useEffect(() => {
    if (!w) return
    let alive = true
    api.signal(sid, a, b, px, combo).then(e => { if (alive) { setEnv(e); setErr(null) } }, e => { if (alive) setErr(String(e.message || e)) })
    return () => { alive = false }
  }, [sid, a, b, px, combo, w])
  const H = height
  const padT = 8, padB = axis ? 22 : 6
  const plotH = H - padT - padB
  const geo = useMemo(() => {
    if (!env || !w) return null
    let lo = Infinity, hi = -Infinity
    for (let i = 0; i < env.lo.length; i++) { if (env.lo[i] < lo) lo = env.lo[i]; if (env.hi[i] > hi) hi = env.hi[i] }
    if (!Number.isFinite(lo)) return null
    const pad = (hi - lo) * 0.06 || 1
    lo -= pad; hi += pad
    const X = (i: number) => ((i - a) / (b - a)) * w
    const Y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * plotH
    const n = env.lo.length
    let d = ''
    for (let k = 0; k < n; k++) d += `${k ? 'L' : 'M'}${X(env.a + k * env.step).toFixed(1)},${Y(env.hi[k]).toFixed(1)}`
    for (let k = n - 1; k >= 0; k--) d += `L${X(env.a + k * env.step + env.step).toFixed(1)},${Y(env.lo[k]).toFixed(1)}`
    return { d: d + 'Z', X, Y, lo, hi }
  }, [env, w, a, b, plotH])
  const toSample = (clientX: number, el: Element) => {
    const r = el.getBoundingClientRect()
    return Math.round(a + ((clientX - r.left) / r.width) * (b - a))
  }
  const ticks = useMemo(() => {
    const h0 = a / fs / 3600, h1 = b / fs / 3600
    const st = niceStep(h1 - h0, Math.max(3, Math.floor(w / 110)))
    const out: number[] = []
    for (let t = Math.ceil(h0 / st) * st; t <= h1 + 1e-9; t += st) out.push(t)
    return out
  }, [a, b, fs, w])
  const sel = drag ?? span
  return (
    <div ref={ref} className="trace" style={{ height: H }} data-testid={testid} data-tour={tour}>
      {err && <div className="chart-error">Could not draw this channel: {err}</div>}
      {!env && !err && <div className="skeleton" style={{ height: H }} />}
      {geo && (
        <svg width={w} height={H} style={{ touchAction: onSpan ? 'none' : 'auto', cursor: onSpan ? 'crosshair' : 'default' }}
          onPointerDown={e => { if (!onSpan) return; (e.target as Element).setPointerCapture?.(e.pointerId); const s0 = toSample(e.clientX, e.currentTarget); setDrag([s0, s0]) }}
          onPointerMove={e => { if (drag) setDrag([drag[0], toSample(e.clientX, e.currentTarget)]) }}
          onPointerUp={e => {
            const svg = e.currentTarget
            if (drag) {
              const [p, q] = [Math.min(...drag), Math.max(...drag)]
              setDrag(null)
              if ((q - p) / (b - a) * w > 5) { onSpan?.(Math.max(0, p), q); return }
            }
            if (onBox && boxes) {
              const s = toSample(e.clientX, svg)
              const tol = (b - a) / w * 4
              const i = boxes.findIndex(bx => s >= bx.s - tol && s <= bx.e + tol)
              if (i >= 0) onBox(i)
            }
          }}>
          {sel && sel[1] > sel[0] && <rect x={geo.X(sel[0])} y={padT} width={Math.max(2, geo.X(sel[1]) - geo.X(sel[0]))} height={plotH}
            fill="rgba(10,132,255,0.12)" stroke="#0a84ff" strokeWidth={1} data-testid="selection" />}
          {boxes?.map((bx, i) => {
            const x0 = geo.X(bx.s), x1 = geo.X(bx.e)
            if (x1 < 0 || x0 > w) return null
            const col = TONE[bx.tone ?? 'mine']
            return <g key={i}>
              <rect x={x0} y={padT} width={Math.max(1.5, x1 - x0)} height={plotH} fill={col} opacity={(bx.alpha ?? 0.6) * 0.28} />
              {bx.mark != null && <path d={`M${geo.X(bx.mark) - 4},${padT + 1}L${geo.X(bx.mark) + 4},${padT + 1}L${geo.X(bx.mark)},${padT + 8}Z`} fill={col} opacity={bx.alpha ?? 0.9} />}
            </g>
          })}
          <path d={geo.d} fill={ghost ? '#c7cbd1' : (color ?? '#1f2937')} stroke={ghost ? '#c7cbd1' : (color ?? '#1f2937')} strokeWidth={0.6} />
          {axis && <g className="axis">
            {ticks.map(t => { const x = ((t * 3600 * fs - a) / (b - a)) * w; return <g key={t}><line x1={x} x2={x} y1={H - padB} y2={H - padB + 4} stroke="#9ca3af" /><text x={x} y={H - 6} textAnchor={x < 24 ? 'start' : x > w - 24 ? 'end' : 'middle'}>{hLabel(t)}</text></g> })}
            <text x={4} y={padT + 10} className="ylab">{fmtMv(geo.hi)}</text>
            <text x={4} y={H - padB - 4} className="ylab">{fmtMv(geo.lo)}</text>
          </g>}
        </svg>
      )}
    </div>
  )
}

export function fmtMv(v: number) {
  const a = Math.abs(v)
  return `${a >= 100 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : v.toFixed(2)} mV`
}

/** The whole slice, small, with the Explore window on it; click or drag to move the window. */
export function Overview({ sid, fs, n, view, onMove, boxes }: { sid: number; fs: number; n: number; view: [number, number]; onMove: (c: number) => void; boxes?: Box[] }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [down, setDown] = useState(false)
  const at = (clientX: number, el: Element) => { const r = el.getBoundingClientRect(); return Math.round(((clientX - r.left) / r.width) * n) }
  return (
    <div ref={ref} className="overview" data-tour="overview">
      <Trace sid={sid} fs={fs} a={0} b={n} height={64} axis={false} boxes={boxes} color="#6b7280" />
      {w > 0 && <div className="ov-hit" onPointerDown={e => { setDown(true); (e.target as Element).setPointerCapture?.(e.pointerId); onMove(at(e.clientX, e.currentTarget)) }}
        onPointerMove={e => { if (down) onMove(at(e.clientX, e.currentTarget)) }} onPointerUp={() => setDown(false)}>
        <div className="ov-win" style={{ left: (view[0] / n) * w, width: Math.max(4, ((view[1] - view[0]) / n) * w) }} />
      </div>}
    </div>
  )
}

/** A 24 h timeline with a tick per event: where a detector fires. */
export function Strip({ n, spans, height = 18, tone = 'mine' }: { n: number; spans: [number, number][]; height?: number; tone?: string }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const col = TONE[tone] ?? tone
  return (
    <div ref={ref} className="strip" style={{ height }}>
      {w > 0 && <svg width={w} height={height}>
        <rect x={0} y={0} width={w} height={height} fill="#f5f6f8" rx={3} />
        {spans.map(([s, e], i) => <rect key={i} x={(s / n) * w} y={2} width={Math.max(1.2, ((e - s) / n) * w)} height={height - 4} fill={col} opacity={0.75} />)}
      </svg>}
    </div>
  )
}

/** A small waveform: a snippet's own domain, no axes. */
export function Spark({ snip, width = 160, height = 48, color = '#1f2937', shade, testid }: { snip: Snip; width?: number; height?: number; color?: string; shade?: [number, number]; testid?: string }) {
  const v = snip.v
  if (!v.length) return <svg width={width} height={height} />
  let lo = Infinity, hi = -Infinity
  for (const z of v) { if (z < lo) lo = z; if (z > hi) hi = z }
  const pad = (hi - lo) * 0.08 || 1
  const X = (i: number) => (i / Math.max(1, v.length - 1)) * (width - 2) + 1
  const Y = (z: number) => 2 + (1 - (z - lo + pad) / (hi - lo + 2 * pad)) * (height - 4)
  const d = v.map((z, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(z).toFixed(1)}`).join('')
  return (
    <svg width={width} height={height} data-testid={testid}>
      {shade && <rect x={X(shade[0])} y={0} width={Math.max(1, X(shade[1]) - X(shade[0]))} height={height} fill="rgba(13,148,136,0.12)" />}
      <path d={d} fill="none" stroke={color} strokeWidth={1.3} strokeLinejoin="round" />
    </svg>
  )
}

/** A normalised shape (a family's centre): drawn as is, it is already a z-score curve. */
export function ShapeLine({ v, width = 120, height = 44, color = '#22a06b' }: { v: number[]; width?: number; height?: number; color?: string }) {
  return <Spark snip={{ dt: 1, v }} width={width} height={height} color={color} />
}

type HistProps = { edges: number[]; series: { counts: number[]; color: string; label: string }[]; logX?: boolean; cut?: number | null;
  height?: number; xLabel?: string; testid?: string }

export function Hist({ edges, series, logX, cut, height = 150, xLabel, testid }: HistProps) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const padL = 8, padR = 8, padB = 26, padT = 8
  const maxC = Math.max(1, ...series.flatMap(s => s.counts))
  const tx = (v: number) => logX ? Math.log10(Math.max(v, 1e-9)) : v
  const x0 = tx(edges[0]), x1 = tx(edges[edges.length - 1])
  const X = (v: number) => padL + ((tx(v) - x0) / (x1 - x0 || 1)) * (w - padL - padR)
  const Y = (c: number) => padT + (1 - c / maxC) * (height - padT - padB)
  const ticks = logX ? edges.filter((_, i) => i % 5 === 0) : edges.filter((_, i) => i % Math.ceil(edges.length / 6) === 0)
  // decimals from the spacing of the ticks, so close ticks never print the same label twice (0.42 and 0.46 as "0.4")
  const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : 1
  const nd = step >= 5 ? 0 : step >= 0.5 ? 1 : step >= 0.05 ? 2 : 3
  return (
    <div ref={ref} className="hist" data-testid={testid}>
      {w > 0 && <svg width={w} height={height}>
        {series.map((s, k) => s.counts.map((c, i) => c > 0 && (
          <rect key={`${k}-${i}`} x={X(edges[i]) + 0.5} y={Y(c)} width={Math.max(1, X(edges[i + 1]) - X(edges[i]) - 1)} height={Y(0) - Y(c)}
            fill={s.color} opacity={series.length > 1 ? 0.65 : 0.85} />)))}
        <line x1={padL} x2={w - padR} y1={Y(0)} y2={Y(0)} stroke="#d1d5db" />
        {cut != null && <g><line x1={X(cut)} x2={X(cut)} y1={padT} y2={Y(0)} stroke="#22a06b" strokeWidth={2} strokeDasharray="4 3" />
          <text x={X(cut) + 4} y={padT + 10} className="axis-t" fill="#1a8a5a">cut</text></g>}
        {ticks.map((t, i) => {
          // a label at either end is anchored inward, so a narrow column does not clip it to "min" or ".0 s"
          const x = X(t)
          const anchor = x < 30 ? 'start' : x > w - 30 ? 'end' : 'middle'
          return <text key={i} x={anchor === 'start' ? Math.max(0, x - 2) : anchor === 'end' ? Math.min(w, x + 2) : x} y={height - 8}
            textAnchor={anchor} className="axis-t">{fmtTick(t, logX, nd)}</text>
        })}
      </svg>}
      {(series.length > 1 || xLabel) && <div className="legend">{series.length > 1 && series.map(s => <span key={s.label}><i style={{ background: s.color }} />{s.label}</span>)}{xLabel && <span className="grow" />}{xLabel && <span>{xLabel}</span>}</div>}
    </div>
  )
}

function fmtTick(v: number, logX?: boolean, nd = 1) {
  if (logX) return v >= 3600 ? `${(v / 3600).toFixed(v >= 36000 ? 0 : 1)} h` : v >= 60 ? `${Math.round(v / 60)} min` : `${Math.round(v)} s`
  return v.toFixed(nd)
}

/** Depth against width, log-log: every point an event. */
export function Scatter({ pts, height = 170, color = '#0a84ff', xLabel = 'width (s)', yLabel = 'depth (mV)' }: { pts: [number, number][]; height?: number; color?: string; xLabel?: string; yLabel?: string }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const ok = pts.filter(([x, y]) => x > 0 && y > 0)
  if (!ok.length) return <div ref={ref} className="empty-chart" style={{ height }}>no events to draw</div>
  const lx = ok.map(p => Math.log10(p[0])), ly = ok.map(p => Math.log10(p[1]))
  const [ax, bx] = [Math.min(...lx), Math.max(...lx)], [ay, by] = [Math.min(...ly), Math.max(...ly)]
  const padL = 30, padB = 22, padT = 6, padR = 8
  const X = (v: number) => padL + ((v - ax) / ((bx - ax) || 1)) * (w - padL - padR)
  const Y = (v: number) => padT + (1 - (v - ay) / ((by - ay) || 1)) * (height - padT - padB)
  return (
    <div ref={ref} className="scatter">
      {w > 0 && <svg width={w} height={height}>
        {ok.map((p, i) => <circle key={i} cx={X(lx[i])} cy={Y(ly[i])} r={2.3} fill={color} opacity={0.45} />)}
        <text x={w - padR} y={height - 6} textAnchor="end" className="axis-t">{xLabel}</text>
        <text x={padL - 2} y={padT + 9} textAnchor="end" className="axis-t" transform={`rotate(-90 ${padL - 18} ${padT + 30})`}>{yLabel}</text>
        <text x={padL} y={height - 6} className="axis-t">{fmtPow(10 ** ax)}</text>
        <text x={4} y={padT + 10} className="axis-t">{fmtPow(10 ** by)}</text>
        <text x={4} y={height - padB} className="axis-t">{fmtPow(10 ** ay)}</text>
      </svg>}
    </div>
  )
}

function fmtSecs(v: number) { return v >= 3600 ? `${(v / 3600).toFixed(1)} h` : v >= 90 ? `${Math.round(v / 60)} min` : `${Math.round(v)} s` }

function fmtPow(v: number) { return v >= 100 ? v.toFixed(0) : v >= 1 ? v.toFixed(1) : v.toPrecision(2) }

/** Every event from its onset at its own size, in mV relative to the onset: the "icicles". */
export function Icicles({ rows, height = 200, maxS }: { rows: { dt: number; t0: number; v: number[]; depth: number }[]; height?: number; maxS?: number }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  if (!rows.length) return <div ref={ref} className="empty-chart" style={{ height }}>no events to draw</div>
  // the window: up to the 85th percentile of the events' lengths, so one long drop does not squash the rest
  const ends = rows.map(r => r.t0 + r.dt * r.v.length).sort((x, y) => x - y)
  const tEnd = maxS ?? ends[Math.min(ends.length - 1, Math.floor(ends.length * 0.85))]
  const t0 = Math.max(Math.min(...rows.map(r => r.t0)), -0.25 * tEnd)
  const clip = (r: { dt: number; t0: number; v: number[] }) => r.v.filter((_, k) => { const t = r.t0 + k * r.dt; return t >= t0 && t <= tEnd })
  let lo = 0, hi = 0
  for (const r of rows) for (const z of clip(r)) { if (z < lo) lo = z; if (z > hi) hi = z }
  const dMax = Math.max(...rows.map(r => r.depth), 1e-9)
  const X = (t: number) => ((t - t0) / ((tEnd - t0) || 1)) * (w - 8) + 4
  const Y = (z: number) => 6 + (1 - (z - lo) / ((hi - lo) || 1)) * (height - 26)
  return (
    <div ref={ref} className="icicles" data-tour="icicles">
      {w > 0 && <svg width={w} height={height}>
        {rows.map((r, i) => {
          const pts = r.v.map((z, k) => [r.t0 + k * r.dt, z] as [number, number]).filter(([t]) => t >= t0 && t <= tEnd)
          const d = pts.map(([t, z], k) => `${k ? 'L' : 'M'}${X(t).toFixed(1)},${Y(z).toFixed(1)}`).join('')
          const f = r.depth / dMax
          return <path key={i} d={d} fill="none" stroke={`rgb(${Math.round(150 - 140 * f)},${Math.round(190 - 100 * f)},255)`} strokeWidth={1.1} opacity={0.75} />
        })}
        <text x={4} y={height - 6} className="axis-t">onset</text>
        <text x={w - 4} y={height - 6} textAnchor="end" className="axis-t">{fmtSecs(tEnd)} after onset</text>
        <text x={w - 4} y={Y(lo) - 2} textAnchor="end" className="axis-t">{fmtMv(lo)}</text>
      </svg>}
    </div>
  )
}

/** The steepest-slope rose: how steep each event's fastest fall is, as an angle (45° = the reference slope). */
export function Rose({ slopes, refSlope, size = 170, color = '#0a84ff' }: { slopes: number[]; refSlope: number; size?: number; color?: string }) {
  const bins = 9
  const counts = new Array(bins).fill(0)
  for (const s of slopes) {
    const ang = Math.atan(Math.abs(s) / (refSlope || 1)) * 180 / Math.PI
    counts[Math.min(bins - 1, Math.floor(ang / (90 / bins)))]++
  }
  const max = Math.max(1, ...counts)
  const R = size - 26, cx = 14, cy = 10
  const wedge = (k: number) => {
    const r = (Math.sqrt(counts[k] / max)) * R
    const a0 = (k * 90 / bins) * Math.PI / 180, a1 = ((k + 1) * 90 / bins) * Math.PI / 180
    return `M${cx},${cy}L${cx + r * Math.cos(a0)},${cy + r * Math.sin(a0)}A${r},${r} 0 0 1 ${cx + r * Math.cos(a1)},${cy + r * Math.sin(a1)}Z`
  }
  return (
    <svg width={size} height={size} className="rose" data-tour="rose">
      {[0.33, 0.66, 1].map(f => <path key={f} d={`M${cx + R * f},${cy}A${R * f},${R * f} 0 0 1 ${cx},${cy + R * f}`} fill="none" stroke="#e5e7eb" />)}
      <line x1={cx} y1={cy} x2={cx + R * Math.cos(Math.PI / 4)} y2={cy + R * Math.sin(Math.PI / 4)} stroke="#d1d5db" strokeDasharray="3 3" />
      {counts.map((_, k) => <path key={k} d={wedge(k)} fill={color} opacity={0.7} stroke="#fff" strokeWidth={0.5} />)}
      <text x={cx + R - 2} y={cy + 12} textAnchor="end" className="axis-t">gentle</text>
      <text x={cx + 2} y={cy + R + 12} className="axis-t">steep</text>
    </svg>
  )
}

export function Bars({ values, height = 90, color = '#0a84ff', labels }: { values: number[]; height?: number; color?: string; labels?: string[] }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const max = Math.max(1, ...values)
  const bw = w / Math.max(1, values.length)
  return (
    <div ref={ref} className="bars">
      {w > 0 && <svg width={w} height={height}>
        {values.map((v, i) => <rect key={i} x={i * bw + 1} y={(1 - v / max) * (height - 16)} width={Math.max(1, bw - 2)} height={(v / max) * (height - 16)} fill={color} opacity={0.8} />)}
        {labels?.map((l, i) => l ? <text key={i} x={i === 0 ? 1 : i * bw + bw / 2} y={height - 3} textAnchor={i === 0 ? 'start' : 'middle'} className="axis-t">{l}</text> : null)}
      </svg>}
    </div>
  )
}

export function Info({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="info" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)} onClick={() => setOpen(o => !o)}>
      i{open && <span className="info-pop">{children}</span>}
    </span>
  )
}
