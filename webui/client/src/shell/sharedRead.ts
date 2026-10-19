/* night-c (2026-10-19): one read shared by every component that shows the same ambient number.
 *
 * The header's "N need you" asked GET /api/review/counts on every Header mount, and a page mounts its header
 * twice (loading, then loaded): four reads of a ~2.5 s route in the Review inspector's first 10 s on the scale
 * fixture, and the chip flashed "0 need you" grey on each remount. A shared read keeps the last answer (a
 * remount shows it at once), asks at most once at a time, and not again within `ttlMs` unless forced. A failed
 * read keeps the last value and reports why (`error()`), never a guess.
 *
 * No imports, so tests run it under Node (tests/test_night_c_shell.py). Near-sibling: `heldOutLock.ts` dedupes
 * its read the same way but lives in the demo store; this one is plain module state for a number. */

export interface SharedRead<T> {
  get(): T
  error(): string | null
  subscribe(fn: () => void): () => void
  /** Ask unless an answer is younger than ttlMs (or `force`); joins a read already in flight. */
  refresh(force?: boolean): Promise<void>
}

export function makeSharedRead<T>(fetcher: () => Promise<T>, opts: { ttlMs: number; initial: T }): SharedRead<T> {
  let value = opts.initial
  let err: string | null = null
  let at = -Infinity
  let inflight: Promise<void> | null = null
  const subs = new Set<() => void>()
  const emit = () => { for (const f of [...subs]) f() }
  return {
    get: () => value,
    error: () => err,
    subscribe(fn) { subs.add(fn); return () => { subs.delete(fn) } },
    refresh(force = false) {
      if (inflight) return inflight
      if (!force && Date.now() - at < opts.ttlMs) return Promise.resolve()
      inflight = fetcher()
        .then(v => { value = v; err = null }, e => { err = e instanceof Error ? e.message : String(e) })
        .finally(() => { inflight = null; at = Date.now(); emit() })
      return inflight
    },
  }
}
