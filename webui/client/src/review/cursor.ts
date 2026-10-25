/* tq-review (2026-10-25): the Inspector's cursor — where the researcher is in a queue and what is pending for that
 * spot, as one model. It replaces two settle timers, a `live` flag, an `onItem` ref mirroring the item id, a `timers`
 * ref cleared in three places and the "still on this item?" guards inside the flash and advance callbacks.
 *
 * - `land(id, signal, io)` is one landing on an item. An item not held yet is read only once it has been on screen
 *   STEP_SETTLE_MS (night-a: fast stepping sends no read for the items passed); a held one — read, or being read — is
 *   read at once (night-review). Once the settle has passed and the read is in, the prefetch window (`prefetch.ts`,
 *   the rule) is read one item at a time, nearest first. One signal ends all of it: the next landing aborts it.
 * - `createCursor()` holds where the researcher is and the one pending advance after a verdict. A move to another
 *   item, an undo or an unmount cancels it; `after()` sets it only if the researcher is still on the item the
 *   verdict was given on, checked right after the write's await.
 *
 * Pure, no imports: `tests/test_tq_review.py` runs it under Node. */

/** night-a: an item not yet held is read once it has been on screen this long. */
export const STEP_SETTLE_MS = 150
/** night-review: the verdict flash, and the auto-advance after it, counted from the bridge's accept — a frame. */
export const ADVANCE_MS = 60

export interface LandingIO<T> {
  /** read, or being read, at the options the card asks for */
  held(id: string): boolean
  read(id: string): Promise<T>
  /** read one item ahead of the step to it; settles when the read does and never rejects */
  warm(id: string): Promise<void>
  /** the ids to keep warm from this item, nearest first — empty when the read found nothing */
  window(got: T): string[]
}

/** Resolves true once `ms` have passed, false as soon as `signal` aborts (its timer is then cleared). */
function settle(ms: number, signal: AbortSignal): Promise<boolean> {
  return new Promise(resolve => {
    if (signal.aborted) return resolve(false)
    const stop = () => { clearTimeout(timer); resolve(false) }
    const timer = setTimeout(() => { signal.removeEventListener('abort', stop); resolve(true) }, ms)
    signal.addEventListener('abort', stop, { once: true })
  })
}

/** One landing on `id`; rejects with an AbortError when it was superseded before its read was sent. */
export async function land<T>(id: string, signal: AbortSignal, io: LandingIO<T>, settleMs: number = STEP_SETTLE_MS): Promise<T> {
  const settled = settle(settleMs, signal)
  if (!io.held(id) && !await settled) throw new DOMException('superseded', 'AbortError')
  const got = await io.read(id)
  void settled.then(async stayed => {
    if (!stayed) return
    for (const next of io.window(got)) {
      if (signal.aborted) return
      await io.warm(next)
    }
  })
  return got
}

export interface Cursor {
  /** the item the researcher is on (null before the first landing) */
  readonly at: string | null
  /** the researcher is on `id` now; a different item cancels the pending advance (a re-read of the same one keeps it) */
  moveTo(id: string): void
  /** schedule `fire` ADVANCE_MS from now if the researcher is still on `from`, replacing any pending one */
  after(from: string, fire: () => void): boolean
  /** drop the pending advance (an undo, an unmount) */
  cancel(): void
}

export function createCursor(advanceMs: number = ADVANCE_MS): Cursor {
  let at: string | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  const cancel = () => { clearTimeout(timer); timer = undefined }
  return {
    get at() { return at },
    moveTo(id) { if (id !== at) { cancel(); at = id } },
    after(from, fire) {
      if (at !== from) return false
      cancel()
      timer = setTimeout(() => { timer = undefined; fire() }, advanceMs)
      return true
    },
    cancel,
  }
}
