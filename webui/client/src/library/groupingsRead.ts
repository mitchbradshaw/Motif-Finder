/* night-b: one read of a list that many hooks on one page want at once (the Library's groupings: the page, the
 * gate, both resolved-id hooks, the grouping bar, the drawer — ten callers on the atlas, ten reads within ~10 ms).
 * Callers inside `ttlMs` of a read share it; a later open reads fresh; `invalidate()` makes the next read a new
 * one and tells every subscriber, so a reload anywhere refreshes every caller with one read. A failed read is
 * dropped, never served again. Pure, no imports, so `tests/test_webui_night_b_groupings_read.py` runs it under Node.
 * Near-sibling: `useSourced` (api/seam.ts) is per-caller by design and stays that way for every other read. */
export interface SharedRead<T> {
  read: () => Promise<T>
  version: () => number
  invalidate: () => void
  subscribe: (fn: () => void) => () => void
}

export function sharedRead<T>(fetcher: () => Promise<T>, opts: { ttlMs?: number; now?: () => number } = {}): SharedRead<T> {
  const ttl = opts.ttlMs ?? 2000
  const now = opts.now ?? (() => Date.now())
  let version = 0
  let cache: { v: number; t: number; p: Promise<T> } | null = null
  const subs = new Set<() => void>()
  return {
    read() {
      const t = now()
      if (cache && cache.v === version && t - cache.t < ttl) return cache.p
      const entry = { v: version, t, p: fetcher() }
      cache = entry
      entry.p.catch(() => { if (cache === entry) cache = null })
      return entry.p
    },
    version: () => version,
    invalidate() { version += 1; cache = null; subs.forEach(fn => fn()) },
    subscribe(fn) { subs.add(fn); return () => { subs.delete(fn) } },
  }
}
