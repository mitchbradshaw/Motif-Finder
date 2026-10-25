/* tq-reads (2026-10-25): the one read shared by every caller that wants the same thing at once.
 *
 * Five copies of this idea grew up apart (the header's review count, the Library's groupings, the Signal page's
 * whole-channel reads, the held-out lock, the adapter registry); this module replaces all of them. A read
 *   - joins the read already in flight for the same key;
 *   - serves its answer to later callers until it is `ttlMs` old (0, the default: only the read in flight is
 *     shared, so a re-read after a write is a fresh read);
 *   - on a failure, either HOLDS it as the answer until the TTL passes (the last good value stays in the snapshot:
 *     the header's count) or DROPS it at once so the next caller asks again (the default: a failure is never served
 *     twice);
 *   - `invalidate()` forgets every answer, bumps `version` and tells every subscriber, so a reload anywhere re-reads
 *     once for every caller.
 * `snapshot()` is the last good value plus the version, the same object until one of them changes, so React reads it
 * through `useSyncExternalStore` (`useSharedRead.ts`). Pure, no imports: tests/test_webui_tq_reads.py runs it under
 * Node. `useSourced` (api/seam.ts) stays per-caller by design for every other read. */

export interface SharedSnapshot<T> { value: T; version: number }

export interface SharedRead<T, K = void> {
  read(key: K): Promise<T>
  snapshot(): SharedSnapshot<T>
  invalidate(): void
  subscribe(fn: () => void): () => void
}

export interface SharedReadOptions<T, K> {
  /** how long a settled answer is served, from when it landed (default 0: in flight only) */
  ttlMs?: number
  /** the snapshot's value before any answer */
  initial?: T
  /** 'hold': a failure stands until the TTL passes and the last value stays; 'drop' (default): forgotten at once */
  onFailure?: 'hold' | 'drop'
  /** the cache key of a key (default `String(key)`) */
  keyOf?: (key: K) => string
  now?: () => number
}

export function makeSharedRead<T, K = void>(fetcher: (key: K) => Promise<T>, opts: SharedReadOptions<T, K> = {}): SharedRead<T, K> {
  const { ttlMs = 0, onFailure = 'drop', keyOf = (k: K) => String(k), now = () => Date.now() } = opts
  // `at` is when the read settled; null while it is in flight
  const entries = new Map<string, { p: Promise<T>; at: number | null }>()
  let snap: SharedSnapshot<T> = { value: opts.initial as T, version: 0 }
  const subs = new Set<() => void>()
  const emit = (next: SharedSnapshot<T>) => { snap = next; for (const f of [...subs]) f() }
  return {
    read(key) {
      const k = keyOf(key)
      const hit = entries.get(k)
      if (hit && (hit.at === null || now() - hit.at < ttlMs)) return hit.p
      const entry = { p: fetcher(key), at: null as number | null }
      entries.set(k, entry)
      // an answer to a read that was invalidated (or replaced) while in flight changes nothing
      const settle = (keep: boolean) => {
        if (entries.get(k) !== entry) return false
        if (keep && ttlMs > 0) entry.at = now()
        else entries.delete(k)
        return true
      }
      entry.p.then(v => { if (settle(true)) emit({ ...snap, value: v }) }, () => { settle(onFailure === 'hold') })
      return entry.p
    },
    snapshot: () => snap,
    invalidate() { entries.clear(); emit({ ...snap, version: snap.version + 1 }) },
    subscribe(fn) { subs.add(fn); return () => { subs.delete(fn) } },
  }
}
