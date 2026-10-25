/* night-c: the header's review count through one shared read (api/sharedRead.ts). A failed read is logged and shows
 * the last known count (0 before any answer), so a Review outage never takes another workspace's header down; the
 * failure stands for the TTL like an answer would. Asked on header mount, at most once per 15 s across every header,
 * and a remount shows the last answer at once (no "0 need you" flash). */
import { useEffect } from 'react'
import { makeSharedRead } from '../api/sharedRead'
import { useSharedRead } from '../api/useSharedRead'

const counts = makeSharedRead<number>(async () => {
  const r = await fetch('/api/review/counts', { headers: { 'content-type': 'application/json' } })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  const d = await r.json() as { need_you?: number }
  return Number(d?.need_you ?? 0)
}, { ttlMs: 15_000, initial: 0, onFailure: 'hold' })

export function useSharedNeedYou(): number {
  const { value } = useSharedRead(counts)
  useEffect(() => {
    counts.read().catch(e => console.warn('review counts unavailable for the header chip', e instanceof Error ? e.message : String(e)))
  }, [])
  return value
}
