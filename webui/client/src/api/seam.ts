/* The one data seam for pages not yet wired to the bridge (brief: "every new read goes through typed
 * async functions in api.ts or a sibling api/ module per workspace").
 *
 * Every read returns `Sourced<T>`: the data plus where it came from. Until a read is wired it resolves
 * fixture data and says `source: 'demo'`; a later ticket swaps the body for a bridge call and returns
 * `source: 'live'` without touching any component. Pages show the "demo data" chip whenever any read
 * they rendered is demo.
 *
 *   // api/models.ts
 *   export const getRegistry = () => demo(REGISTRY_FIXTURE)
 *   // page
 *   const reg = useSourced(getRegistry, [])
 */
import { useEffect, useState, type DependencyList } from 'react'

export type Source = 'demo' | 'live'
export interface Sourced<T> { data: T; source: Source }

/** Resolve fixture data asynchronously (one macrotask, so loading states exist and are testable). */
export function demo<T>(data: T, delayMs = 60): Promise<Sourced<T>> {
  return new Promise(resolve => window.setTimeout(() => resolve({ data: structuredCloneSafe(data), source: 'demo' }), delayMs))
}

/** Wrap a live bridge call so it fits the same shape. */
export async function live<T>(p: Promise<T>): Promise<Sourced<T>> { return { data: await p, source: 'live' } }

function structuredCloneSafe<T>(v: T): T {
  try { return structuredClone(v) } catch { return v }
}

export interface SourcedState<T> { data: T | null; source: Source | null; loading: boolean; error: Error | null; reload: () => void }

/** Load a Sourced read in a component. Errors are returned (render them loudly), never swallowed. */
export function useSourced<T>(fn: () => Promise<Sourced<T>>, deps: DependencyList): SourcedState<T> {
  return useAbortableSourced(() => fn(), deps)
}

/** `useSourced` for a read that takes an AbortSignal (AR, the speed pass): the signal fires when the read is
 *  superseded — its deps changed, the page went away — so a read that hands it to `fetch` stops instead of
 *  finishing for nobody. Kept apart from `useSourced` so no existing read is handed an argument it would
 *  mistake for one of its own. */
export function useAbortableSourced<T>(fn: (signal: AbortSignal) => Promise<Sourced<T>>, deps: DependencyList): SourcedState<T> {
  const [state, setState] = useState<{ data: T | null; source: Source | null; loading: boolean; error: Error | null }>({ data: null, source: null, loading: true, error: null })
  const [nonce, setNonce] = useState(0)
  useEffect(() => {
    let alive = true
    const ctl = new AbortController()
    setState(s => ({ ...s, loading: true, error: null }))
    fn(ctl.signal).then(r => { if (alive) setState({ data: r.data, source: r.source, loading: false, error: null }) },
      e => { if (alive) { console.error('read failed', e); setState(s => ({ ...s, loading: false, error: e instanceof Error ? e : new Error(String(e)) })) } })
    return () => { alive = false; ctl.abort() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])
  return { ...state, reload: () => setNonce(n => n + 1) }
}
