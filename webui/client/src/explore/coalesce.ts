/* night-b: one read for callers that ask for the same thing at the same moment (the Signal page's two whole-channel
 * span reads, 2.5–5 s each on a 90 k-detection channel). Only the read IN FLIGHT is shared: once it settles the key
 * is dropped, so a re-read after a write is a fresh read and a failure is never served twice. Pure, no imports, so
 * `tests/test_webui_night_b_spans_once.py` runs it under Node. Near-siblings: `analyse/useAdapters.ts` and
 * `shell/heldOutLock.ts` share one unkeyed read each; this one is keyed. */
export function coalesced<K, T>(read: (key: K) => Promise<T>, keyOf: (key: K) => string = k => String(k)): (key: K) => Promise<T> {
  const flying = new Map<string, Promise<T>>()
  return key => {
    const k = keyOf(key)
    let p = flying.get(k)
    if (!p) {
      p = read(key).finally(() => { flying.delete(k) })
      flying.set(k, p)
    }
    return p
  }
}
