/* In-memory client store for the empty frontend (brief: "writes stay in memory").
 *
 * Save, register, verdict, apply and import go here. The store is module-level, so it survives
 * navigation between routes, and deliberately NOT persisted, so a reload resets it to the fixtures.
 * Nothing in here ever reaches the bridge or a database.
 *
 *   const [queues, setQueues] = useDemoState('review.queues', () => FIXTURE_QUEUES)
 *   recordDemoWrite('review', 'verdict', { item: 'q-12/4', verdict: 'interesting' })
 */
import { useCallback, useSyncExternalStore } from 'react'

type Listener = () => void
const values = new Map<string, unknown>()
const listeners = new Map<string, Set<Listener>>()

function emit(key: string) { listeners.get(key)?.forEach(l => l()) }
function subscribe(key: string, l: Listener) {
  let s = listeners.get(key)
  if (!s) { s = new Set(); listeners.set(key, s) }
  s.add(l)
  return () => { s!.delete(l) }
}

export function getDemo<T>(key: string, init: () => T): T {
  if (!values.has(key)) values.set(key, init())
  return values.get(key) as T
}

export function setDemo<T>(key: string, next: T | ((prev: T) => T)) {
  const prev = values.get(key) as T
  const v = typeof next === 'function' ? (next as (p: T) => T)(prev) : next
  if (Object.is(v, prev)) return
  values.set(key, v)
  emit(key)
}

/** useState whose value lives in the module-level demo store under `key` (namespace it by workspace). */
export function useDemoState<T>(key: string, init: () => T): [T, (next: T | ((prev: T) => T)) => void] {
  const value = useSyncExternalStore(
    useCallback((l: Listener) => subscribe(key, l), [key]),
    () => getDemo(key, init),
  )
  const set = useCallback((next: T | ((prev: T) => T)) => setDemo(key, next), [key])
  return [value, set]
}

/* ---- the write log: every in-memory write is recorded, so a page can say what it would have stored ---- */
export interface DemoWrite { seq: number; at: number; workspace: string; kind: string; detail: Record<string, unknown> }
let seq = 1
const LOG_KEY = '__demo.writes'

export function recordDemoWrite(workspace: string, kind: string, detail: Record<string, unknown> = {}): DemoWrite {
  const w: DemoWrite = { seq: seq++, at: Date.now(), workspace, kind, detail }
  setDemo<DemoWrite[]>(LOG_KEY, prev => [...(prev ?? []), w].slice(-500))
  return w
}

export function useDemoWrites(workspace?: string): DemoWrite[] {
  const [all] = useDemoState<DemoWrite[]>(LOG_KEY, () => [])
  return workspace ? all.filter(w => w.workspace === workspace) : all
}

/** Test hook: the smoke test and critics can read what the page wrote without a database. */
declare global { interface Window { __demoStore?: { keys: () => string[]; get: (k: string) => unknown; writes: () => DemoWrite[] } } }
if (typeof window !== 'undefined') {
  window.__demoStore = { keys: () => [...values.keys()], get: k => values.get(k), writes: () => (values.get(LOG_KEY) as DemoWrite[]) ?? [] }
}
