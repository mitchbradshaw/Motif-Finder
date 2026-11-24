/* Explore › Auto-detect's plot: the stretch on a canvas with every candidate shaded by its confidence, a marker
   below every drop's bottom (▼) and above every rise's peak (▲) so a narrow one shows at any zoom, a thin strip that
   marks every box, the sequences in a band above (drops, then rises), and an overview strip below with the view's
   box. Scroll zooms at the cursor, drag pans, shift-drag zooms into a range, double-click shows the whole stretch,
   hover reads a candidate, click selects it. The drawing is the reference viewer's (scripts/autodetect/
   viewer_template.html), the one the researcher reviewed; the numbers come from autoDetectModel.ts. */
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent, type WheelEvent } from 'react'
import type { AdCands, AdSeqs } from '../api/autodetect'
import { COLOUR, alphaOf, byStart, clock, eachVisible, envelope, isShown, longest, rgba, tickStep, valueStep, type Filter, type Sig } from './autoDetectModel'

export interface ViewerProps {
  sig: Sig; cands: AdCands; seqs: AdSeqs; sources: string[]; filter: Filter
  markers: boolean; showSeq: boolean
  /** [v0, v1): stretch sample indices */
  view: [number, number]; onView: (v: [number, number]) => void
  selected: number; onSelect: (i: number) => void
  /** the hover card's lines for candidate i */
  describe: (i: number) => string[]
  height?: number
}

const ML = 58, MR = 12, MT = 6, MB = 22, STRIP = 12, SHADE_MIN_PX = 3, MIN_SPAN = 30

interface Geo { x0: number; x1: number; yTop: number; yBot: number; stripY: number; seqH: number; seqTwo: boolean; X: (i: number) => number }

function cssVar(name: string, fallback: string) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

function sizeCanvas(c: HTMLCanvasElement) {
  const dpr = window.devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight
  if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr) }
  const g = c.getContext('2d')!
  g.setTransform(dpr, 0, 0, dpr, 0, 0)
  return { g, w, h }
}

export function clampView(v0: number, v1: number, n: number): [number, number] {
  const span = Math.max(MIN_SPAN, Math.min(n, v1 - v0))
  let a = v0, b = v0 + span
  if (a < 0) { a = 0; b = span }
  if (b > n) { b = n; a = n - span }
  return [a, b]
}

export function AutoDetectViewer(p: ViewerProps) {
  const { sig, cands } = p
  const cv = useRef<HTMLCanvasElement>(null)
  const ov = useRef<HTMLCanvasElement>(null)
  const latest = useRef(p)
  latest.current = p
  const order = useMemo(() => byStart(cands), [cands])
  const maxDur = useMemo(() => longest(cands), [cands])
  const geo = useRef<Geo | null>(null)
  const hover = useRef(-1)
  const drag = useRef<{ x: number; cx: number; v0: number; v1: number; moved: boolean; box: boolean } | null>(null)
  const [tip, setTip] = useState<{ left: number; top: number; lines: string[] } | null>(null)
  const [width, setWidth] = useState(0)
  const frame = useRef(0)

  const colOf = useCallback((i: number) => (cands.k[i] === 1 ? COLOUR.scan : cands.pol[i] ? COLOUR.rise : COLOUR.drop), [cands])

  const draw = useCallback(() => {
    const c = cv.current
    if (!c) return
    const q = latest.current
    const { g, w, h } = sizeCanvas(c)
    if (!w || !h) return
    const shown = (i: number) => isShown(q.cands, q.sources, q.filter, i)
    const seqTwo = q.seqs.pol.some(v => v === 1) && q.seqs.pol.some(v => v === 0)
    const seqH = q.showSeq && q.seqs.s.length ? (seqTwo ? 26 : 16) : 0
    const stripY = MT + seqH + 1
    const x0 = ML, x1 = w - MR, yTop = MT + seqH + STRIP, yBot = h - MB
    const cols = Math.max(1, Math.floor(x1 - x0))
    const [v0, v1] = q.view
    const X = (i: number) => x0 + (i - v0) / (v1 - v0) * (x1 - x0)
    geo.current = { x0, x1, yTop, yBot, stripY, seqH, seqTwo, X }
    g.clearRect(0, 0, w, h)
    const env = envelope(sig, v0, v1, cols)
    let lo = Infinity, hi = -Infinity
    for (let k = 0; k < cols; k++) { const a = env.mins[k], z = env.maxs[k]; if (a < lo) lo = a; if (z > hi) hi = z }
    if (!Number.isFinite(lo)) { lo = -1; hi = 1 }
    if (hi - lo < 1e-6) { lo -= 0.5; hi += 0.5 }
    const pad = (hi - lo) * 0.06; lo -= pad; hi += pad
    const Yp = (v: number) => yBot - (v - lo) / (hi - lo) * (yBot - yTop)
    const muted = cssVar('--muted', '#6b7280'), grid = cssVar('--border', '#e5e7eb'), trace = cssVar('--trace', '#1f2933')
    // grid and axes
    g.font = '11px system-ui, sans-serif'; g.fillStyle = muted; g.strokeStyle = grid; g.lineWidth = 1
    const xs = tickStep(v1 - v0, Math.max(3, Math.floor((x1 - x0) / 110)), sig.fs)
    const t0 = sig.start_idx
    const first = Math.ceil((v0 + t0) / xs) * xs - t0
    g.textAlign = 'center'; g.textBaseline = 'top'
    for (let t = first; t <= v1; t += xs) {
      const x = X(t); g.beginPath(); g.moveTo(x + 0.5, yTop); g.lineTo(x + 0.5, yBot); g.stroke()
      g.fillText(clock((t + t0) / sig.fs, xs / sig.fs < 60), x, h - MB + 5)
    }
    const ys = valueStep(lo, hi, 5)
    g.textAlign = 'right'; g.textBaseline = 'middle'
    for (let v = Math.ceil(lo / ys) * ys; v <= hi; v += ys) {
      const y = Yp(v); g.beginPath(); g.moveTo(x0, y + 0.5); g.lineTo(x1, y + 0.5); g.stroke()
      g.fillText(Math.abs(ys) < 0.01 ? v.toFixed(3) : Math.abs(ys) < 0.1 ? v.toFixed(2) : Math.abs(ys) < 1 ? v.toFixed(1) : v.toFixed(0), x0 - 6, y)
    }
    g.save(); g.translate(13, (yTop + yBot) / 2); g.rotate(-Math.PI / 2); g.textAlign = 'center'; g.fillText(sig.unit, 0, 0); g.restore()
    // the strip: every shown box as a tick
    g.save(); g.beginPath(); g.rect(x0, stripY, x1 - x0, STRIP - 2); g.clip()
    g.fillStyle = grid; g.fillRect(x0, stripY, x1 - x0, STRIP - 2)
    eachVisible(q.cands, order, maxDur, v0, v1, i => {
      if (!shown(i)) return
      const a = X(q.cands.s[i]), b = X(q.cands.e[i])
      g.fillStyle = rgba(colOf(i), Math.min(1, alphaOf(q.cands.c[i]) + 0.3)); g.fillRect(a, stripY, Math.max(1, b - a), STRIP - 2)
    })
    g.restore()
    // boxes wide enough to shade
    g.save(); g.beginPath(); g.rect(x0, yTop, x1 - x0, yBot - yTop); g.clip()
    eachVisible(q.cands, order, maxDur, v0, v1, i => {
      if (!shown(i)) return
      const a = X(q.cands.s[i]), b = X(q.cands.e[i])
      if (b - a < SHADE_MIN_PX) return
      g.fillStyle = rgba(colOf(i), alphaOf(q.cands.c[i])); g.fillRect(a, yTop, b - a, yBot - yTop)
    })
    // the trace
    g.strokeStyle = trace; g.lineWidth = 1; g.beginPath()
    if (env.spp > 1.2) {
      let pen = false
      for (let k = 0; k < cols; k++) {
        const a = env.mins[k], z = env.maxs[k]
        if (!(a === a)) { pen = false; continue }
        const x = x0 + k + 0.5
        if (!pen) { g.moveTo(x, Yp(z)); pen = true } else g.lineTo(x, Yp(z))
        g.lineTo(x, Yp(a))
      }
    } else {
      let pen = false
      for (let i = Math.max(0, Math.floor(v0) - 1); i <= Math.min(sig.n - 1, Math.ceil(v1) + 1); i++) {
        const v = sig.y[i]
        if (!(v === v)) { pen = false; continue }
        const x = X(i + 0.5), y = Yp(v)
        if (!pen) { g.moveTo(x, y); pen = true } else g.lineTo(x, y)
      }
    }
    g.stroke()
    if (env.spp < 0.12) {
      g.fillStyle = trace
      for (let i = Math.max(0, Math.floor(v0)); i <= Math.min(sig.n - 1, Math.ceil(v1)); i++) {
        const v = sig.y[i]; if (v === v) { g.beginPath(); g.arc(X(i + 0.5), Yp(v), 2, 0, 6.29); g.fill() }
      }
    }
    // markers: below every drop's bottom, above every rise's peak
    const fine = env.spp <= 1.2
    const markAt = (i: number) => {
      const ex = q.cands.ex[i] as number, x = X(ex + 0.5), k = Math.max(0, Math.min(cols - 1, Math.floor(x - x0)))
      const v = fine ? sig.y[Math.max(0, Math.min(sig.n - 1, ex))] : (q.cands.pol[i] ? env.maxs[k] : env.mins[k])
      return { x, y: Yp(v) + (q.cands.pol[i] ? -9 : 9) }
    }
    const tri = (x: number, y: number, up: boolean, size: number, fill: string, stroke?: string) => {
      g.beginPath()
      if (up) { g.moveTo(x, y - size); g.lineTo(x - size * 0.8, y + size * 0.4); g.lineTo(x + size * 0.8, y + size * 0.4) }
      else { g.moveTo(x, y + size); g.lineTo(x - size * 0.8, y - size * 0.4); g.lineTo(x + size * 0.8, y - size * 0.4) }
      g.closePath(); g.fillStyle = fill; g.fill()
      if (stroke) { g.strokeStyle = stroke; g.lineWidth = 1.5; g.stroke() }
    }
    if (q.markers) {
      eachVisible(q.cands, order, maxDur, v0, v1, i => {
        if (!shown(i) || q.cands.ex[i] == null) return
        const { x, y } = markAt(i)
        if (x < x0 - 6 || x > x1 + 6 || !(y === y)) return
        tri(x, y, q.cands.pol[i] === 1, 5, rgba(colOf(i), 0.45 + 0.55 * Math.max(0, Math.min(1, (q.cands.c[i] - 0.3) / 0.7))))
      })
    }
    const ink = cssVar('--text', '#111827')
    for (const [i, wdt] of [[hover.current, 1], [q.selected, 2]] as const) {
      if (i < 0 || i >= q.cands.s.length || !shown(i)) continue
      const a = X(q.cands.s[i]), b = X(q.cands.e[i])
      if (b < x0 || a > x1) continue
      g.strokeStyle = ink; g.lineWidth = wdt; g.strokeRect(a + 0.5, yTop + 0.5, Math.max(1.5, b - a) - 1, yBot - yTop - 1)
      if (q.cands.ex[i] != null) { const { x, y } = markAt(i); if (y === y) tri(x, y, q.cands.pol[i] === 1, 7, colOf(i), ink) }
    }
    g.restore()
    // sequences
    if (seqH) {
      g.save(); g.beginPath(); g.rect(x0, MT, x1 - x0, seqH); g.clip()
      const rowH = seqTwo ? 11 : seqH - 5
      for (let k = 0; k < q.seqs.s.length; k++) {
        const a = X(q.seqs.s[k]), b = X(q.seqs.e[k]); if (b < x0 || a > x1) continue
        const rise = q.seqs.pol[k] === 1, y = MT + 2 + (seqTwo && rise ? 13 : 0)
        g.fillStyle = rgba(rise ? COLOUR.seqRise : COLOUR.seqDrop, 0.85); g.fillRect(a, y, Math.max(2, b - a), rowH)
        if (b - a > 70) {
          g.fillStyle = '#fff'; g.textAlign = 'left'; g.textBaseline = 'middle'; g.font = '600 10px system-ui'
          g.fillText(`S${q.seqs.id[k]} · ${q.seqs.n[k]} ${rise ? 'rises' : 'drops'}`, Math.max(a, x0) + 4, y + rowH / 2 + 0.5)
        }
      }
      g.restore()
    }
    const d = drag.current
    if (d && d.box) {
      const a = Math.min(d.x, d.cx), b = Math.max(d.x, d.cx), blue = cssVar('--blue', '#2563eb')
      g.fillStyle = rgba(blue.startsWith('#') ? blue : '#2563eb', 0.12); g.fillRect(a, yTop, b - a, yBot - yTop)
      g.strokeStyle = blue; g.strokeRect(a + 0.5, yTop + 0.5, b - a, yBot - yTop)
    }
    drawOverview()
  }, [sig, order, maxDur, colOf])  // eslint-disable-line react-hooks/exhaustive-deps -- drawOverview reads refs only

  // the overview strip: the whole stretch, the shown boxes, the sequences, and the view's box
  const ovCache = useRef<{ key: string; img: HTMLCanvasElement } | null>(null)
  const drawOverview = useCallback(() => {
    const c = ov.current
    if (!c) return
    const q = latest.current
    const { g, w, h } = sizeCanvas(c)
    if (!w || !h) return
    const key = `${w}x${h}|${q.filter.minc}|${q.filter.drop}|${q.filter.rise}|${[...q.filter.src].sort().join(',')}|${q.cands.s.length}`
    if (!ovCache.current || ovCache.current.key !== key) {
      const dpr = window.devicePixelRatio || 1
      const off = document.createElement('canvas'); off.width = Math.round(w * dpr); off.height = Math.round(h * dpr)
      const o = off.getContext('2d')!; o.setTransform(dpr, 0, 0, dpr, 0, 0)
      const cols = Math.max(1, Math.floor(w)), env = envelope(sig, 0, sig.n, cols)
      let lo = Infinity, hi = -Infinity
      for (let k = 0; k < cols; k++) { if (env.mins[k] < lo) lo = env.mins[k]; if (env.maxs[k] > hi) hi = env.maxs[k] }
      const top = 4, bot = h - 14
      o.fillStyle = cssVar('--card', '#ffffff'); o.fillRect(0, 0, w, h)
      o.strokeStyle = cssVar('--muted', '#6b7280'); o.lineWidth = 1; o.beginPath()
      for (let k = 0; k < cols; k++) {
        const a = env.mins[k], z = env.maxs[k]; if (!(a === a)) continue
        o.moveTo(k + 0.5, bot - (z - lo) / (hi - lo + 1e-12) * (bot - top)); o.lineTo(k + 0.5, bot - (a - lo) / (hi - lo + 1e-12) * (bot - top))
      }
      o.stroke()
      for (let i = 0; i < q.cands.s.length; i++) {
        if (!isShown(q.cands, q.sources, q.filter, i)) continue
        o.fillStyle = rgba(colOf(i), 0.25 + 0.75 * Math.max(0, (q.cands.c[i] - 0.3) / 0.7))
        o.fillRect(q.cands.s[i] / sig.n * w, h - 12, Math.max(1, (q.cands.e[i] - q.cands.s[i]) / sig.n * w), 5)
      }
      for (let k = 0; k < q.seqs.s.length; k++) {
        o.fillStyle = q.seqs.pol[k] === 1 ? COLOUR.seqRise : COLOUR.seqDrop
        o.fillRect(q.seqs.s[k] / sig.n * w, h - 6, Math.max(2, (q.seqs.e[k] - q.seqs.s[k]) / sig.n * w), 4)
      }
      ovCache.current = { key, img: off }
    }
    g.clearRect(0, 0, w, h); g.drawImage(ovCache.current.img, 0, 0, w, h)
    const a = q.view[0] / sig.n * w, b = q.view[1] / sig.n * w, blue = '#2563eb'
    g.fillStyle = rgba(blue, 0.16); g.fillRect(a, 0, Math.max(3, b - a), h)
    g.strokeStyle = blue; g.lineWidth = 1.5; g.strokeRect(a + 0.5, 0.5, Math.max(3, b - a) - 1, h - 1)
  }, [sig, colOf])

  const schedule = useCallback(() => {
    if (frame.current) return
    frame.current = requestAnimationFrame(() => { frame.current = 0; draw() })
  }, [draw])
  useEffect(() => () => { if (frame.current) cancelAnimationFrame(frame.current) }, [])
  useEffect(() => { schedule() }, [p.view, p.filter, p.markers, p.showSeq, p.selected, width, cands, p.seqs, schedule])
  useEffect(() => {
    const el = cv.current?.parentElement
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // ── pointer ──
  const localX = (e: { clientX: number }) => { const r = cv.current!.getBoundingClientRect(); return e.clientX - r.left }
  const sampleAt = (x: number) => { const gg = geo.current!; const [v0, v1] = latest.current.view; return v0 + (x - gg.x0) / (gg.x1 - gg.x0) * (v1 - v0) }
  const setView = (v0: number, v1: number) => latest.current.onView(clampView(v0, v1, sig.n))
  const pick = (x: number, y: number) => {
    const gg = geo.current
    if (!gg || x < gg.x0 || x > gg.x1 || y < gg.stripY || y > gg.yBot) return -1
    const q = latest.current, s = sampleAt(x), tol = 3 / (gg.x1 - gg.x0) * (q.view[1] - q.view[0])
    let best = -1
    eachVisible(q.cands, order, maxDur, s - tol, s + tol, i => {
      if (!isShown(q.cands, q.sources, q.filter, i)) return
      if (best < 0 || q.cands.e[i] - q.cands.s[i] < q.cands.e[best] - q.cands.s[best]) best = i
    })
    return best
  }
  const onWheel = (e: WheelEvent<HTMLCanvasElement>) => {
    const gg = geo.current
    if (!gg) return
    const [v0, v1] = latest.current.view, span = v1 - v0
    if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) { const d = e.deltaX / (gg.x1 - gg.x0) * span; setView(v0 + d, v1 + d); return }
    const frac = Math.max(0, Math.min(1, (localX(e) - gg.x0) / (gg.x1 - gg.x0)))
    const c = v0 + frac * span, ns = span * Math.pow(1.0015, e.deltaY)
    setView(c - frac * ns, c - frac * ns + ns)
  }
  // React's wheel listener is passive: stop the page scrolling under the plot with a native one
  useEffect(() => {
    const c = cv.current
    if (!c) return
    const stop = (e: globalThis.WheelEvent) => e.preventDefault()
    c.addEventListener('wheel', stop, { passive: false })
    return () => c.removeEventListener('wheel', stop)
  }, [])
  const onDown = (e: PointerEvent<HTMLCanvasElement>) => {
    cv.current!.setPointerCapture(e.pointerId)
    const x = localX(e), [v0, v1] = latest.current.view
    drag.current = { x, cx: x, v0, v1, moved: false, box: e.shiftKey }
  }
  const onMove = (e: PointerEvent<HTMLCanvasElement>) => {
    const x = localX(e), r = cv.current!.getBoundingClientRect(), y = e.clientY - r.top
    const d = drag.current
    if (d) {
      d.cx = x; if (Math.abs(x - d.x) > 3) d.moved = true
      if (d.box) { schedule(); return }
      const gg = geo.current!, dx = (x - d.x) / (gg.x1 - gg.x0) * (d.v1 - d.v0)
      setView(d.v0 - dx, d.v1 - dx); setTip(null); return
    }
    const i = pick(x, y)
    if (i !== hover.current) { hover.current = i; schedule() }
    if (i < 0) { setTip(null); return }
    setTip({ left: Math.min(x + 14, r.width - 300), top: y + 14, lines: latest.current.describe(i) })
  }
  const onUp = (e: PointerEvent<HTMLCanvasElement>) => {
    const d = drag.current
    drag.current = null
    if (!d) return
    const x = localX(e), r = cv.current!.getBoundingClientRect()
    if (d.box && d.moved) { setView(sampleAt(Math.min(d.x, x)), sampleAt(Math.max(d.x, x))); return }
    if (!d.moved) { const i = pick(x, e.clientY - r.top); if (i >= 0) latest.current.onSelect(i) }
    schedule()
  }
  // the overview: click or drag to move the view
  const ovDrag = useRef<{ x: number; v0: number } | null>(null)
  const ovDown = (e: PointerEvent<HTMLCanvasElement>) => {
    const c = ov.current!, r = c.getBoundingClientRect(), x = e.clientX - r.left, s = x / r.width * sig.n
    c.setPointerCapture(e.pointerId)
    const [v0, v1] = latest.current.view, span = v1 - v0
    if (s < v0 || s > v1) setView(s - span / 2, s + span / 2)
    ovDrag.current = { x, v0: s < v0 || s > v1 ? s - span / 2 : v0 }
  }
  const ovMove = (e: PointerEvent<HTMLCanvasElement>) => {
    const od = ovDrag.current
    if (!od) return
    const r = ov.current!.getBoundingClientRect(), x = e.clientX - r.left
    const [v0, v1] = latest.current.view, span = v1 - v0
    const nv = od.v0 + (x - od.x) / r.width * sig.n
    if (Math.abs(nv - v0) > 0.5) setView(nv, nv + span)
  }

  return (
    <div className="ad-viewer" data-testid="ad-viewer" data-candidates={cands.s.length}>
      <div className="ad-plotwrap">
        <canvas ref={cv} className="ad-main" style={{ height: p.height ?? 400 }} data-testid="ad-canvas"
          onWheel={onWheel} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}
          onPointerLeave={() => { hover.current = -1; setTip(null); schedule() }}
          onDoubleClick={() => setView(0, sig.n)} />
        {tip && (
          <div className="ad-tip" style={{ left: tip.left, top: tip.top }} data-testid="ad-tip">
            {tip.lines.map((l, k) => <div key={k} className={k === 0 ? 't' : undefined}>{l}</div>)}
          </div>
        )}
      </div>
      <canvas ref={ov} className="ad-overview" data-testid="ad-overview" onPointerDown={ovDown} onPointerMove={ovMove}
        onPointerUp={() => { ovDrag.current = null }} />
    </div>
  )
}
