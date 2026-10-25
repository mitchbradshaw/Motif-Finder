/* tq-reads (2026-10-25): a shared read's snapshot in a component — the last good value and the version — re-rendered
 * when a read lands or the read is invalidated. Kept apart from `sharedRead.ts` so that module stays pure for Node. */
import { useSyncExternalStore } from 'react'
import type { SharedRead, SharedSnapshot } from './sharedRead'

export function useSharedRead<T, K>(r: SharedRead<T, K>): SharedSnapshot<T> {
  return useSyncExternalStore(r.subscribe, r.snapshot)
}
