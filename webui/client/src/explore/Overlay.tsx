/* Explore › Cross-channel › overlay (prompt cross-channel-overlay, the researcher 2026-10-18): every channel of the
   recording on ONE tall axis, so the eye compares shapes across channels without hopping between rows.

   Geometry (the grilling of 2026-10-18):
   - each channel is drawn about its OWN mean over the window (the mean of the envelope the bridge sent), so the volts
     of DC offset between electrodes never flatten a trace — the same reason the stack's default is 'centred';
   - channels sit in EQUAL lanes by rank, the first channel at the top and the last at the bottom: a lane is at least
     LANE_MIN px and the block at least BLOCK_MIN px tall;
   - one SHARED gain for every channel (mV per pixel), so a bigger wiggle still looks bigger: the (lower) median
     channel's own range spans GAIN_LANES lanes, so neighbours overlap a little, which is what an overlay is for. A
     wiggle that runs past the block is clipped by the block — except a channel whose whole range cannot fit the
     block at the shared gain: that one is drawn at its own gain and marked ÷N beside its name (site-x,
     overlayModel.ts::overlayGains), and a lane drawn flatter than FLAT_PX says "flat at this gain";
   - selected ("bold") channels draw at full opacity and a thicker stroke, the rest faded behind them;
   - align by lag (off by default) slides a channel by the lag the bridge measured against the reference, so a wave
     that travels across the electrodes lines up; the shift is printed beside the name.

   Props only — no page state, no fetch — so Discovery can mount it later (the researcher: "I might even transfer it").
   The parent owns the selection, the align switch and the box; this component draws and reports. Near-sibling:
   CrossChannelPage's stacked rows (one svg per row, crossScale.ts::stackGeom) — not reused because a stack gives each
   row its own box, and the overlay's point is one box. */
import { useId, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { scaleLinear } from 'd3'
import { makeX, polylinePath } from '../charts/scale'
import { mvDigits } from './util'
import { cx } from '../kit'
import { mergeDetectionMarks, overlayGains } from './overlayModel'

/** One channel as the overlay draws it. `t` is absolute seconds (the envelope's own, non-uniform once decimated),
 *  `v` the envelope's values in the recording's display unit, a null a gap. */
export interface OverlayChannel {
  id: number; name: string; colour: string
  t: number[]; v: (number | null)[]
  /** lag against the reference in seconds, as measured by the bridge; null = undefined on this window */
  lag_s: number | null
  /** detections on this channel inside the window (absolute seconds), drawn as thin caps in the channel's colour */
  detections?: { id: number; t0: number; t1: number }[]
  /** a read failure, said beside the name rather than drawn as a blank lane */
  error?: string
}

export interface OverlayProps {
  /** drawn top to bottom in this order (rank: CH1 first) */
  channels: OverlayChannel[]
  /** [t0, t1] absolute seconds — the x domain */
  window: [number, number]
  /** ids drawn bold; everything else is faded */
  selected: number[]
  onSelect: (ids: number[]) => void
  /** the box: [t0, t1] on the reference's clock, or null when cleared */
  brush: [number, number] | null
  onBrush: (w: [number, number] | null) => void
  /** align by lag (shift each channel by its lag_s); the parent owns it, the A key and the header switch ask for it */
  align: boolean
  onAlign?: (on: boolean) => void
  /** the reference never moves; a |lag| past maxLagS is not shifted, and the name says so */
  referenceId?: number
  maxLagS?: number
  /** a region drawn across the whole block (the window's own span) */
  band?: [number, number] | null
  /** tick positions (absolute s) and their labels */
  ticks?: { t: number; label: string }[]
  /** the unit the values are in, in words ("mV") */
  unitLabel?: string
  /** the plot's width in px (the parent measures its card) */
  width: number
  testid?: string
}

export const LANE_MIN = 28
export const BLOCK_MIN = 420
export const GAIN_LANES = 1.6
export const OVERLAY_NAME_W = 118
const NAME_W = OVERLAY_NAME_W
const PAD_T = 10
const PAD_B = 10

/** A fixed categorical palette: a channel's colour is its rank in the recording, the same everywhere on the page. */
export const CHANNEL_PALETTE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#0f766e',
  '#bcbd22', '#17becf', '#393b79', '#e7969c', '#637939', '#ad494a', '#6b6ecf', '#843c39']
export const channelColour = (rank: number) => CHANNEL_PALETTE[((rank % CHANNEL_PALETTE.length) + CHANNEL_PALETTE.length) % CHANNEL_PALETTE.length]

/** The shift align-by-lag applies to one channel (0 = stays where it was). */
export function overlayShift(c: OverlayChannel, align: boolean, referenceId?: number, maxLagS = Infinity): number {
  if (!align || c.id === referenceId || c.lag_s === null || !Number.isFinite(c.lag_s) || Math.abs(c.lag_s) > maxLagS) return 0
  return c.lag_s
}

export const fmtShift = (s: number) => `${s >= 0 ? '+' : '−'}${Math.abs(s).toFixed(Math.abs(s) >= 10 ? 0 : 1)} s`

function stats(v: (number | null)[]): { mean: number; lo: number; hi: number } | null {
  let n = 0, sum = 0, lo = Infinity, hi = -Infinity
  for (const x of v) { if (x === null || !Number.isFinite(x)) continue; n++; sum += x; if (x < lo) lo = x; if (x > hi) hi = x }
  return n ? { mean: sum / n, lo, hi } : null
}

/** The geometry in numbers, exported so a test or a caption can read what was drawn. */
export function overlayGeometry(channels: OverlayChannel[]) {
  const n = Math.max(1, channels.length)
  const height = Math.max(BLOCK_MIN, n * LANE_MIN + PAD_T + PAD_B)
  const lane = (height - PAD_T - PAD_B) / n
  const st = channels.map(c => stats(c.v))
  // site-x: one shared gain (the median channel's range spans GAIN_LANES lanes), except for a channel that cannot fit
  // the block at it — drawn at its own gain and labelled with the factor (overlayModel.ts::overlayGains)
  const gains = overlayGains(st.map(s => (s ? s.hi - s.lo : null)), lane, height, GAIN_LANES)
  const centre = channels.map((_, i) => PAD_T + lane * (i + 0.5))
  return { height, lane, pxPerUnit: gains.shared, medianSpan: gains.medianSpan, gains: gains.rows, centre, stats: st }
}

/** The value nearest in time to t on one envelope (binary search over its own t). */
function valueAt(t: number[], v: (number | null)[], at: number): number | null {
  if (!t.length) return null
  let lo = 0, hi = t.length - 1
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (t[m] < at) lo = m; else hi = m }
  const i = Math.abs(t[lo] - at) <= Math.abs(t[hi] - at) ? lo : hi
  return v[i] ?? null
}

export function Overlay(p: OverlayProps) {
  const { channels, window: [t0, t1], selected, width } = p
  const plotW = Math.max(1, width - NAME_W)
  const x = useMemo(() => makeX(t0, t1, plotW), [t0, t1, plotW])
  const g = useMemo(() => overlayGeometry(channels), [channels])
  const bold = useMemo(() => new Set(selected), [selected])
  const shifts = channels.map(c => overlayShift(c, p.align, p.referenceId, p.maxLagS))
  const yOf = (i: number) => { const m = g.stats[i]?.mean ?? 0; return scaleLinear().domain([m, m + 1]).range([g.centre[i], g.centre[i] - (g.gains[i]?.pxPerUnit ?? g.pxPerUnit)]) }
  const paths = useMemo(() => channels.map((c, i) => {
    const s = shifts[i]
    const tt = s ? c.t.map(t => t - s) : c.t
    return polylinePath(tt, c.v, x, yOf(i))
  }), [channels, x, g, shifts.join(',')])  // eslint-disable-line react-hooks/exhaustive-deps

  const [hoverT, setHoverT] = useState<number | null>(null)
  const [drag, setDrag] = useState<{ x0: number; x1: number } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const clipId = `ex-ov-clip-${useId().replace(/:/g, '')}`   // one id per mounted overlay (Discovery may mount a second)
  const localX = (e: PointerEvent) => { const r = svgRef.current!.getBoundingClientRect(); return Math.max(0, Math.min(plotW, e.clientX - r.left)) }
  const localY = (e: PointerEvent) => e.clientY - svgRef.current!.getBoundingClientRect().top

  const toggle = (id: number, many: boolean) => {
    if (many) p.onSelect(bold.has(id) ? selected.filter(s => s !== id) : [...selected, id])
    else p.onSelect(bold.has(id) && selected.length === 1 ? [] : [id])
  }
  /** a click without a drag picks the trace nearest the pointer (within 10 px), else clears the box */
  const pick = (px: number, py: number, many: boolean) => {
    const at = x.invert(px)
    let best = -1, dist = 10
    channels.forEach((c, i) => {
      const val = valueAt(c.t, c.v, at + shifts[i])
      if (val === null) return
      const d = Math.abs(yOf(i)(val) - py)
      if (d < dist) { dist = d; best = i }
    })
    if (best >= 0) toggle(channels[best].id, many)
    else p.onBrush(null)
  }
  const onDown = (e: PointerEvent<SVGRectElement>) => { e.currentTarget.setPointerCapture(e.pointerId); const lx = localX(e); setDrag({ x0: lx, x1: lx }) }
  const onMove = (e: PointerEvent<SVGRectElement>) => { const lx = localX(e); setHoverT(x.invert(lx)); if (drag) setDrag({ ...drag, x1: lx }) }
  const onUp = (e: PointerEvent<SVGRectElement>) => {
    if (!drag) return
    const lx = localX(e)
    setDrag(null)
    if (Math.abs(lx - drag.x0) < 4) { pick(lx, localY(e), e.shiftKey); return }
    const a = x.invert(Math.min(drag.x0, lx)), b = x.invert(Math.max(drag.x0, lx))
    p.onBrush([Math.max(t0, a), Math.min(t1, b)])
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault()
      const ranks = channels.map((c, i) => (bold.has(c.id) ? i : -1)).filter(i => i >= 0)
      const from = ranks.length ? (e.key === 'ArrowUp' ? ranks[0] : ranks[ranks.length - 1]) : (e.key === 'ArrowUp' ? channels.length : -1)
      const to = Math.max(0, Math.min(channels.length - 1, from + (e.key === 'ArrowUp' ? -1 : 1)))
      if (channels[to]) p.onSelect([channels[to].id])
    } else if ((e.key === 'a' || e.key === 'A') && !e.ctrlKey && !e.metaKey) {
      e.preventDefault(); p.onAlign?.(!p.align)
    } else if (e.key === 'Escape' && p.brush) {
      e.preventDefault(); p.onBrush(null)
    }
  }

  const H = g.height
  const boldRows = channels.map((c, i) => ({ c, i })).filter(({ c }) => bold.has(c.id))
  const places = mvDigits(0, g.medianSpan)
  const box = drag ? [Math.min(drag.x0, drag.x1), Math.max(drag.x0, drag.x1)] : p.brush ? [x(p.brush[0]), x(p.brush[1])] : null
  return (
    <div className="ex-ov" data-testid={p.testid ?? 'overlay'} data-height={H} data-lane={g.lane.toFixed(1)} data-channels={channels.length}
      data-bold-count={selected.length} data-align={p.align ? 'lag' : 'recorded'} tabIndex={0} onKeyDown={onKey}
      aria-label="overlay of every channel: ↑ / ↓ move the bold channel, A aligns by lag, drag a box to act on a window">
      <div className="ex-ov-names" style={{ height: H, width: NAME_W }}>
        {channels.map((c, i) => {
          const on = bold.has(c.id)
          const s = shifts[i]
          const past = p.align && c.id !== p.referenceId && c.lag_s !== null && p.maxLagS !== undefined && Math.abs(c.lag_s) > p.maxLagS
          return (
            <button key={c.id} type="button" className={cx('ex-ov-name', on && 'on')} style={{ top: g.centre[i], color: c.colour }}
              onClick={e => toggle(c.id, e.shiftKey)} data-testid={`ov-name-${c.name}`} data-bold={on ? 'yes' : 'no'}
              title={`${on ? 'unbold' : 'bold'} ${c.name} · shift-click for several${c.error ? ` · read failed: ${c.error}` : ''}`}>
              <span className="sw" style={{ background: c.colour }} />{c.name}
              {p.align && c.id !== p.referenceId && (
                <span className={cx('sh mono', past && 'past')} data-testid={`ov-shift-${c.name}`} data-shift={s}>
                  {past ? 'past max' : c.lag_s === null ? '— s' : fmtShift(s)}
                </span>)}
              {g.gains[i]?.ownScale && (
                <span className="own mono" data-testid={`ov-own-scale-${c.name}`} data-factor={g.gains[i].factor.toFixed(1)}
                  title={`${c.name} spans ${(g.stats[i]!.hi - g.stats[i]!.lo).toFixed(places)} ${p.unitLabel ?? ''} in this window, ${g.gains[i].factor.toFixed(0)}× the median channel's range: at the shared gain it would run off the plot, so it is drawn at its own gain, ${g.gains[i].factor.toFixed(0)}× smaller — its amplitude does not compare with the others'`}>
                  ÷{g.gains[i].factor >= 10 ? g.gains[i].factor.toFixed(0) : g.gains[i].factor.toFixed(1)}</span>)}
              {c.error && <span className="err" data-testid={`ov-error-${c.name}`}>!</span>}
            </button>
          )
        })}
      </div>
      <svg ref={svgRef} width={plotW} height={H} className="ex-ov-svg" data-plot-box="">
        <defs><clipPath id={clipId}><rect x={0} y={0} width={plotW} height={H} /></clipPath></defs>
        {p.band && <rect x={x(p.band[0])} y={0} width={Math.max(0, x(p.band[1]) - x(p.band[0]))} height={H} fill="var(--band-selected)" data-testid="ov-band" />}
        {(p.ticks ?? []).map(k => <line key={k.t} x1={x(k.t)} x2={x(k.t)} y1={0} y2={H} stroke="var(--border)" strokeOpacity={0.6} />)}
        <g clipPath={`url(#${clipId})`} data-trace="">
          {/* faded first, bold last, so a bold trace is never painted under a faded one */}
          {channels.map((c, i) => ({ c, i })).sort((a, b) => Number(bold.has(a.c.id)) - Number(bold.has(b.c.id))).map(({ c, i }) => {
            const on = bold.has(c.id)
            return (
              <g key={c.id} data-testid={`ov-row-${c.name}`} data-shift={shifts[i] || undefined}>
                {/* site-x: detections as dashed brackets, merged where they overlap, open where they run past the window —
                    drawn as solid bars in the trace's colour they read as a flat trace across the top of every lane */}
                {mergeDetectionMarks((c.detections ?? []).map(d => ({ t0: d.t0 - shifts[i], t1: d.t1 - shifts[i] })), t0, t1).map(m => {
                  const a = x(m.t0), b = Math.max(x(m.t0) + 2, x(m.t1)), yy = g.centre[i] - g.lane / 2 + 4
                  return (
                    <g key={`${m.t0}-${m.t1}`} data-testid="ov-detection" data-n={m.n} opacity={on ? 0.6 : 0.25}>
                      <line x1={a} x2={b} y1={yy} y2={yy} stroke={c.colour} strokeWidth={1.5} strokeDasharray="5 3" />
                      {!m.openLeft && <line x1={a} x2={a} y1={yy - 3} y2={yy + 3} stroke={c.colour} strokeWidth={1.5} />}
                      {!m.openRight && <line x1={b} x2={b} y1={yy - 3} y2={yy + 3} stroke={c.colour} strokeWidth={1.5} />}
                      <title>{`${c.name} · ${m.n} detection${m.n === 1 ? '' : 's'}${m.openLeft || m.openRight ? ' · runs past the window' : ''}`}</title>
                    </g>)
                })}
                {(c.error || !g.stats[i]) && <text x={6} y={g.centre[i] + 4} className="mono ex-ov-lane-note" fill={c.colour} data-testid={`ov-lane-note-${c.name}`}>
                  {c.name}: {c.error ? `read failed — ${c.error.split(':')[0]}` : 'no finite sample in this window'}<title>{c.error ?? 'every value in this window is missing'}</title></text>}
                {g.gains[i]?.flat && !c.error && <text x={6} y={g.centre[i] - 4} className="mono ex-ov-lane-note" fill={c.colour} data-testid={`ov-lane-flat-${c.name}`} data-px={g.gains[i].px.toFixed(2)}>
                  {c.name}: flat at this gain — its range {(g.stats[i]!.hi - g.stats[i]!.lo).toFixed(places)} {p.unitLabel ?? ''} draws {g.gains[i].px.toFixed(1)} px; the stacked view's y: per channel draws its shape</text>}
                <path d={paths[i]} fill="none" stroke={c.colour} strokeWidth={on ? 1.8 : 1} strokeOpacity={on ? 1 : selected.length ? 0.18 : 0.75}
                  strokeLinejoin="round" vectorEffect="non-scaling-stroke" data-testid={`ov-trace-${c.name}`} data-bold={on ? 'yes' : 'no'} />
              </g>
            )
          })}
        </g>
        {box && <rect x={box[0]} y={0} width={Math.max(1, box[1] - box[0])} height={H} fill="var(--blue)" fillOpacity={0.1} stroke="var(--blue)" strokeOpacity={0.6} data-testid="ov-brush" />}
        {hoverT !== null && !drag && <line x1={x(hoverT)} x2={x(hoverT)} y1={0} y2={H} stroke="var(--blue)" strokeOpacity={0.5} strokeDasharray="3 3" data-testid="ov-crosshair" />}
        <rect x={0} y={0} width={plotW} height={H} fill="transparent" style={{ cursor: 'crosshair' }} data-testid="ov-hit"
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={() => setHoverT(null)} />
      </svg>
      {hoverT !== null && (
        <div className="ex-ov-readout mono" style={{ left: NAME_W + Math.min(x(hoverT) + 8, plotW - 170) }} data-testid="ov-readout">
          <div className="muted">t = {(hoverT - t0).toFixed(1)} s into the window</div>
          {boldRows.length === 0 && <div className="muted">make a channel bold to read its value</div>}
          {boldRows.slice(0, 8).map(({ c, i }) => {
            const val = valueAt(c.t, c.v, hoverT + shifts[i])
            return <div key={c.id}><span style={{ color: c.colour }}>{c.name}</span> {val === null ? '—' : val.toFixed(places)} {p.unitLabel ?? ''}</div>
          })}
          {boldRows.length > 8 && <div className="muted">+{boldRows.length - 8} more bold</div>}
        </div>
      )}
    </div>
  )
}
