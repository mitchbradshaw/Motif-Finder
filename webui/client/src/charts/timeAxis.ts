/* A trace's own time axis — pure TypeScript, no imports, so `tests/test_webui_review_axis.py` can run it
 * under Node as well as the browser (fixup-g).
 *
 * The bridge serves every trace as interleaved `t` (seconds) and `v` (mV). Once a window has more samples
 * than twice the pixels it will be drawn on, the points are a peak-preserving envelope: FEWER than the
 * samples, and not evenly spaced (each pixel-bucket emits its min and its max at their own sample times).
 * So nothing may place point `i` at `t0 + i / fs`; a point sits where its `t` says. The helpers here are the
 * small arithmetic every consumer of such a trace needs, stated once. */

/** Index of the point whose time is nearest `time`, by binary search on an ascending `t`; -1 when empty. */
export function nearestIndex(t: ReadonlyArray<number>, time: number): number {
  const n = t.length
  if (n === 0) return -1
  let lo = 0, hi = n - 1
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (t[mid] < time) lo = mid + 1
    else hi = mid
  }
  // `lo` is the first index with t >= time; the nearest is that or the one before it
  if (lo > 0 && Math.abs(t[lo - 1] - time) <= Math.abs(t[lo] - time)) return lo - 1
  return lo
}

/** The points of `(t, v)` whose time lies in `[t0, t1]`, in order. `v` may hold nulls (an all-NaN bucket). */
export function sliceWindow<V>(t: ReadonlyArray<number>, v: ReadonlyArray<V>, t0: number, t1: number): { t: number[]; v: V[] } {
  const tt: number[] = [], vv: V[] = []
  const n = Math.min(t.length, v.length)
  for (let i = 0; i < n; i++) {
    const x = t[i]
    if (x >= t0 && x <= t1) { tt.push(x); vv.push(v[i]) }
  }
  return { t: tt, v: vv }
}

/** A value list the plots can draw: a null (an all-NaN envelope bucket) becomes NaN, which lifts the pen. */
export function drawable(v: ReadonlyArray<number | null | undefined>): number[] {
  return v.map(x => (x === null || x === undefined ? NaN : x))
}
