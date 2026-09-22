/* Shared time-axis helpers. One xScale per surface; every row on a chain page
   uses the same one, which is what makes the rows share a time axis. */
import { scaleLinear, type ScaleLinear } from 'd3'
import { fmtAxis } from '../state'

export type XScale = ScaleLinear<number, number>

export function makeX(t0: number, t1: number, width: number, padL = 0, padR = 0): XScale {
  return scaleLinear().domain([t0, t1]).range([padL, Math.max(padL + 1, width - padR)])
}
export function makeY(lo: number, hi: number, height: number, padT = 4, padB = 4): XScale {
  if (!(hi > lo)) { const c = lo || 0; lo = c - 1; hi = c + 1 }
  const m = (hi - lo) * 0.06
  return scaleLinear().domain([lo - m, hi + m]).range([height - padB, padT])
}

/** ~n nice ticks over [t0,t1] in seconds, plus labels in the span's natural unit. */
export function timeTicks(t0: number, t1: number, n = 6): { t: number; label: string }[] {
  const span = t1 - t0
  const s = scaleLinear().domain([t0, t1])
  return s.ticks(n).map(t => ({ t, label: fmtAxis(t, span) }))
}

/* ---- label de-collision (fixup-a item 17) ----------------------------------
 * `d3`'s `.ticks(n)` chooses positions knowing nothing about how wide `fmtAxis`
 * will render them, so on a narrow surface with wide labels (hours to one
 * decimal, e.g. `291.9 h`) adjacent labels overlap. `TimeAxis` used to guard
 * only the two ends, and only when `ends` was asked for; in the default path
 * there was no collision test at all.
 *
 * The axis font is the mono face at 10px (`theme.css`: `svg text`), so one
 * character advances about 6 px. 6.2 is deliberately a shade generous: an
 * over-estimate drops a tick that would just have fitted, an under-estimate
 * prints two labels on top of each other. */
const AXIS_CHAR_PX = 6.2
const AXIS_GAP_PX = 6
/** The anchor `TimeAxis` renders each label with — kept here so the width
 *  estimate and the rendering cannot disagree about where a label sits. */
export function axisAnchor(px: number, r0: number, r1: number): 'start' | 'end' | 'middle' {
  return px - r0 < 24 ? 'start' : r1 - px < 24 ? 'end' : 'middle'
}

/** Drop any tick whose label would overlap the one before it, left to right.
 *  `pinEnds` keeps the first and last tick whatever else goes: they are the
 *  window's own bounds and the reason the caller asked for them. */
export function decollideTicks(ticks: { t: number; label: string }[], x: XScale, pinEnds = false): { t: number; label: string }[] {
  if (ticks.length < 2) return ticks
  const [r0, r1] = x.range()
  const box = (k: { t: number; label: string }): [number, number] => {
    const px = x(k.t)
    const w = k.label.length * AXIS_CHAR_PX
    const a = axisAnchor(px, r0, r1)
    return a === 'start' ? [px, px + w] : a === 'end' ? [px - w, px] : [px - w / 2, px + w / 2]
  }
  const boxes = ticks.map(box)
  const drop = new Set<number>()
  if (pinEnds) {
    // the last label is kept, so its neighbours yield to it rather than the reverse
    const last = ticks.length - 1
    for (let i = last - 1; i >= 1; i--) {
      if (boxes[i][1] + AXIS_GAP_PX > boxes[last][0]) drop.add(i)
      else break
    }
  }
  const out: { t: number; label: string }[] = []
  let prevRight = -Infinity
  for (let i = 0; i < ticks.length; i++) {
    if (drop.has(i)) continue
    if (boxes[i][0] < prevRight + AXIS_GAP_PX) continue
    out.push(ticks[i])
    prevRight = boxes[i][1]
  }
  return out
}

/** Build an SVG path "M x y L x y ..." from interleaved (t, v) arrays; null breaks the line. */
export function polylinePath(t: number[], v: (number | null)[], x: XScale, y: XScale): string {
  let d = ''
  let pen = false
  for (let i = 0; i < t.length; i++) {
    const vv = v[i]
    if (vv === null || vv === undefined || Number.isNaN(vv)) { pen = false; continue }
    const px = x(t[i]); const py = y(vv)
    d += (pen ? 'L' : 'M') + px.toFixed(1) + ' ' + py.toFixed(1)
    pen = true
  }
  return d
}

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
