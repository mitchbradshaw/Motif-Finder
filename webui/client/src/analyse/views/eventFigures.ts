/* night-analyse (2026-10-20): the pure helpers behind the Event shape and Intervals figures and the span-set
 * slideshow's highlighted band. No imports: `tests/test_night_analyse_helpers.py` runs this file under Node.
 *
 * Nothing here derives a MEASURE: the measures are the bridge's. These place what the payload carries — a
 * waveform aligned for an overlay, a series scaled to share one plot, the order of classes counted as
 * transitions, which events to draw when there are too many.
 *
 * Near siblings, and why not them: `kit/extent.ts` gives a range but not the 0..1 scale with a flat series at 0.5;
 * `views/common.tsx::finiteRange` the same (and that file imports React, which Node cannot run). */

type Num = number | null | undefined

const fin = (v: Num): v is number => v !== null && v !== undefined && Number.isFinite(v)

/** np.gradient of a sampled trace (central differences inside, one-sided at the ends); null where a neighbour is
 *  missing. */
export function gradient(v: ArrayLike<Num>): (number | null)[] {
  const n = v.length
  const g: (number | null)[] = new Array(n).fill(null)
  if (n < 2) return g
  for (let i = 0; i < n; i++) {
    const a = i === 0 ? v[0] : v[i - 1], b = i === n - 1 ? v[n - 1] : v[i + 1]
    const span = i === 0 || i === n - 1 ? 1 : 2
    g[i] = fin(a) && fin(b) ? (b - a) / span : null
  }
  return g
}

/** The sample of the steepest slope (largest |np.gradient|) inside [lo, hi] (inclusive; defaults to the whole
 *  trace): the slope the rose reads. The first of equals; `lo` for a flat trace; -1 for no sample. */
export function steepestIndex(v: ArrayLike<Num>, lo = 0, hi = v.length - 1): number {
  if (!v.length) return -1
  lo = Math.max(0, lo); hi = Math.min(v.length - 1, hi)
  if (hi < lo) return -1
  const g = gradient(v)
  let best = -1, bestAbs = -1
  for (let i = lo; i <= hi; i++) {
    const x = g[i]
    if (x === null) continue
    if (Math.abs(x) > bestAbs) { bestAbs = Math.abs(x); best = i }
  }
  return best < 0 ? lo : best
}

/** A waveform z-scored on its own samples (population sd); a flat waveform is all zeros; a gap stays a gap. */
export function zscore(v: ArrayLike<Num>): (number | null)[] {
  let s = 0, k = 0
  for (let i = 0; i < v.length; i++) { const x = v[i]; if (fin(x)) { s += x; k++ } }
  if (!k) return Array.from(v, () => null)
  const m = s / k
  let ss = 0
  for (let i = 0; i < v.length; i++) { const x = v[i]; if (fin(x)) ss += (x - m) * (x - m) }
  const sd = Math.sqrt(ss / k)
  return Array.from(v, x => (fin(x) ? (sd > 0 ? (x - m) / sd : 0) : null))
}

export interface Aligned { dt: number[]; z: (number | null)[]; steep: number }

/** One event's waveform for the overlay: z-scored, its time measured from its steepest-slope sample. `range`
 *  ([onset_s, extremum_s], when the bridge names them) restricts where the steepest slope is looked for — the
 *  fall the rose measures — else the whole window. Null for an empty waveform. */
export function alignOnSteepest(t: number[], v: ArrayLike<Num>, range: [number, number] | null): Aligned | null {
  if (!t.length || t.length !== v.length) return null
  let lo = 0, hi = t.length - 1
  if (range) {
    const a = Math.min(range[0], range[1]), b = Math.max(range[0], range[1])
    const L = t.findIndex(x => x >= a - 1e-9)
    let H = -1
    for (let i = t.length - 1; i >= 0; i--) if (t[i] <= b + 1e-9) { H = i; break }
    if (L >= 0 && H >= L) { lo = L; hi = H }
  }
  const steep = steepestIndex(v, lo, hi)
  if (steep < 0) return null
  return { dt: t.map(x => x - t[steep]), z: zscore(v), steep }
}

/** A series scaled to 0..1 over its own finite range, for display beside other series; the real value is read off
 *  the payload, never back off this. A flat series sits at 0.5; a missing value stays missing. */
export function normaliseSeries(vals: ArrayLike<Num>): { y: (number | null)[]; lo: number | null; hi: number | null } {
  let lo = Infinity, hi = -Infinity
  for (let i = 0; i < vals.length; i++) { const x = vals[i]; if (fin(x)) { if (x < lo) lo = x; if (x > hi) hi = x } }
  if (!(lo <= hi)) return { y: Array.from(vals, () => null), lo: null, hi: null }
  const r = hi - lo
  return { y: Array.from(vals, x => (fin(x) ? (r > 0 ? (x - lo) / r : 0.5) : null)), lo, hi }
}

export interface Transitions { keys: string[]; counts: number[][]; rowTotal: number[]; rowPct: (number | null)[][] }

/** For each class, the class of the next event in time order — within one group (an interval across groups means
 *  nothing, the Intervals block's rule). An event with no time is skipped. Percentages are of the row. */
export function transitionMatrix(cls: ArrayLike<string>, t: ArrayLike<Num>, keys: string[], groups: ArrayLike<string> | null): Transitions {
  const at = new Map(keys.map((k, i) => [k, i]))
  const counts = keys.map(() => keys.map(() => 0))
  const by = new Map<string, number[]>()
  for (let i = 0; i < cls.length; i++) {
    if (!fin(t[i])) continue
    const g = groups ? groups[i] : ''
    let L = by.get(g); if (!L) by.set(g, L = [])
    L.push(i)
  }
  for (const L of by.values()) {
    L.sort((a, b) => (t[a] as number) - (t[b] as number) || a - b)
    for (let k = 1; k < L.length; k++) {
      const a = at.get(cls[L[k - 1]]), b = at.get(cls[L[k]])
      if (a !== undefined && b !== undefined) counts[a][b]++
    }
  }
  const rowTotal = counts.map(r => r.reduce((s, x) => s + x, 0))
  const rowPct = counts.map((r, i) => r.map(x => (rowTotal[i] ? (100 * x) / rowTotal[i] : null)))
  return { keys, counts, rowTotal, rowPct }
}

/** At most `cap` indices of `n`, spread evenly over all of them, the first and last kept. */
export function evenSample(n: number, cap: number): number[] {
  if (n <= 0 || cap <= 0) return []
  if (n <= cap) return Array.from({ length: n }, (_, i) => i)
  if (cap === 1) return [0]
  const out: number[] = []
  for (let k = 0; k < cap; k++) out.push(Math.round((k * (n - 1)) / (cap - 1)))
  return out
}

/** The span-set slideshow's window: the detection [s, e] plus `frac` (15 %) of its width either side, never fewer
 *  than `minSamples` samples, clipped to the run's span [t0, t1]. The detection itself is the highlighted band. */
export function slideWindow(s: number, e: number, fs: number, t0: number, t1: number, frac = 0.15, minSamples = 3): [number, number] {
  const pad = Math.max(frac * Math.max(0, e - s), minSamples / (fs > 0 ? fs : 1))
  return [Math.max(t0, s - pad), Math.min(t1, e + pad)]
}

/** The early -> late ramp (a sequential blue -> violet -> amber), f in 0..1 (clamped). */
const RAMP: [number, number, number][] = [[37, 99, 235], [124, 58, 237], [219, 39, 119], [234, 138, 0]]
export function rampColour(f: number): string {
  const x = Math.min(1, Math.max(0, Number.isFinite(f) ? f : 0)) * (RAMP.length - 1)
  const i = Math.min(RAMP.length - 2, Math.floor(x)), u = x - i
  const c = RAMP[i].map((a, k) => Math.round(a + (RAMP[i + 1][k] - a) * u))
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`
}

/** True for an Event shape feature table (its amplitude and steepest-slope columns: a payload convention, never the
 *  block's name). The page is chosen by this as well as by the rose, because a step restored from the step cache
 *  with no meta sidecar carries its table and marks but no rose (the demo's W1 chain, 2026-10-21). */
export function isEventShapeTable(columns: ReadonlyArray<string> | null | undefined): boolean {
  return !!columns && columns.includes('event_amplitude_mv') && columns.includes('max_slope_mv_s')
}
