/* The held-out lock (spec §0 D6) as the bridge enforces it NOW (a2-p1): Settings › Datasets' `heldout.on`, read by
   every route on every request. The header chip, and the pages that decide in the browser whether to ask for the
   held-out recording's data at all, read it from here.

   The value lives in the demo-store key Settings › Datasets already mirrors its SAVED lock into (settings/store.ts
   `HELD_OUT_KEY_STORE`), so a save there shows everywhere at once. GET /api/held-out refreshes it whenever a page
   mounts the header and when the window regains focus, so another tab's toggle is picked up without a reload. Until
   the first answer the lock reads ON: closed is the default, as it is on the bridge. A failed read keeps the last
   state and says so (`error`), never a guess. */
import { useEffect } from 'react'
import { getHeldOutLock } from '../api'
import { makeSharedRead } from '../api/sharedRead'
import { getDemo, setDemo, useDemoState } from '../kit/store'

/** The demo-store key the lock lives under — the one Settings › Datasets writes on save. */
export const HELD_OUT_LOCK_KEY = 'settings.heldOut'

export interface HeldOutLock {
  /** true while the lock is on: every workspace refuses the held-out recording */
  on: boolean
  /** the held-out recording's directory stem (`M4_aug_concat_fs1`) */
  recording: string
  /** how to unlock it, in the bridge's words */
  unlock?: string
  /** why the last read of GET /api/held-out failed, when it did */
  error?: string | null
}

const DEFAULT: HeldOutLock = { on: true, recording: 'M4_aug_concat_fs1' }
const init = () => DEFAULT

/** The lock as this tab last heard it — for a plain function that cannot subscribe (a hook should use
 *  `useHeldOutLock`, so its component re-renders when the lock changes). */
export function heldOutLocked(): boolean {
  return getDemo<HeldOutLock>(HELD_OUT_LOCK_KEY, init).on !== false
}

/** Ask the bridge for the lock (api/sharedRead.ts): one request in flight at most, and none within a second of the
 *  last answer. An answer that lands after Settings › Datasets saved a new state is dropped (that save is newer than
 *  the question). The read itself never fails: a failure is written into the lock's `error`. */
const LOCK_READ = makeSharedRead(() => {
  const asked = getDemo<HeldOutLock>(HELD_OUT_LOCK_KEY, init)
  return getHeldOutLock()
    .then(s => setDemo<HeldOutLock>(HELD_OUT_LOCK_KEY, prev => (prev !== undefined && prev !== asked ? prev
      : { on: s.locked, recording: s.recording, unlock: s.unlock, error: null })))
    .catch(e => setDemo<HeldOutLock>(HELD_OUT_LOCK_KEY, prev => ({ ...(prev ?? DEFAULT), error: e instanceof Error ? e.message : String(e) })))
}, { ttlMs: 1000 })

/** The lock, subscribed: the caller re-renders when it changes. Asks the bridge on mount and on window focus. */
export function useHeldOutLock(): HeldOutLock {
  const [lock] = useDemoState<HeldOutLock>(HELD_OUT_LOCK_KEY, init)
  useEffect(() => {
    void LOCK_READ.read()
    const onFocus = () => { void LOCK_READ.read() }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [])
  return lock
}
