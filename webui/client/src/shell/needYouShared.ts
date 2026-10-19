/* night-c: the header's review count through one shared read (shell/sharedRead.ts). Same route and the same
 * failure rule as api/needYou.ts (`useReviewNeedYou`, kept for its other callers): a failed read is logged and
 * shows the last known count (0 before any answer), so a Review outage never takes another workspace's header
 * down. Asked on header mount, at most once per 15 s across every header. */
import { useEffect, useSyncExternalStore } from 'react'
import { makeSharedRead } from './sharedRead'

const counts = makeSharedRead<number>(async () => {
  const r = await fetch('/api/review/counts', { headers: { 'content-type': 'application/json' } })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  const d = await r.json() as { need_you?: number }
  return Number(d?.need_you ?? 0)
}, { ttlMs: 15_000, initial: 0 })

export function useSharedNeedYou(): number {
  const n = useSyncExternalStore(counts.subscribe, counts.get)
  useEffect(() => {
    void counts.refresh().then(() => { const e = counts.error(); if (e) console.warn('review counts unavailable for the header chip', e) })
  }, [])
  return n
}
