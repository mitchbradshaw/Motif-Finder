/* night (2026-10-20): min and max by a loop, never `Math.max(...xs)`.
 *
 * The seed page's cut card spread every candidate and null distance into Math.max's argument list; on the October
 * database a preview's cut sweep holds ~10^5 distances, and that many arguments is `RangeError: Maximum call stack
 * size exceeded` - the Discovery workspace's red card. Non-finite values are skipped (a NaN used to make the whole
 * axis NaN). An empty input gives [Infinity, -Infinity], so `Math.max(1, maxOf(xs))` floors exactly as
 * `Math.max(1, ...xs)` did and callers that need a real pair test `lo <= hi`. No imports: tests run it under Node. */

export function extentOf(...lists: ReadonlyArray<ArrayLike<number>>): [number, number] {
  let lo = Infinity, hi = -Infinity
  for (const xs of lists) {
    for (let i = 0; i < xs.length; i++) {
      const v = xs[i]
      if (!Number.isFinite(v)) continue
      if (v < lo) lo = v
      if (v > hi) hi = v
    }
  }
  return [lo, hi]
}

export function maxOf(...lists: ReadonlyArray<ArrayLike<number>>): number { return extentOf(...lists)[1] }

export function minOf(...lists: ReadonlyArray<ArrayLike<number>>): number { return extentOf(...lists)[0] }
