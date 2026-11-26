/* The demo's shared state: the route (hash), the manifest, and the visitor's thread through the stops: which
   channel and stretch they are on, the detector they built, the run they made, the seed they picked. Kept in
   sessionStorage so a reload keeps the thread; "Start over" (or a station reset) clears it. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, type Manifest, type Slice } from './api'

export type Route = { page: string; parts: string[]; query: Record<string, string> }

function parse(): Route {
  const h = window.location.hash.replace(/^#\/?/, '')
  const [path, qs] = h.split('?')
  const parts = (path || 'welcome').split('/').filter(Boolean)
  const query: Record<string, string> = {}
  new URLSearchParams(qs || '').forEach((v, k) => { query[k] = v })
  return { page: parts[0] || 'welcome', parts, query }
}

export function go(path: string) {
  const next = '#/' + path.replace(/^#?\/?/, '')
  if (window.location.hash !== next) window.location.hash = next
}

export type Thread = {
  slice: number            // the channel being explored / analysed
  view: [number, number]   // the Explore window, samples
  span: [number, number] | null   // the marked stretch
  combo: string            // the visitor's detector (a builder setting)
  ran: string | null       // the detector last run in Discovery
  seed: string | null      // the seed shown on the Seed page ('live' = the marked stretch)
  autoOn: boolean          // Auto-detect drawn in Explore
  source: string           // Spike statistics' source
}

const KEY = 'mw.thread'

function loadThread(): Partial<Thread> {
  try { return JSON.parse(sessionStorage.getItem(KEY) || '{}') } catch { return {} }
}

type Ctx = { route: Route; m: Manifest; thread: Thread; set: (p: Partial<Thread>) => void; reset: () => void;
  slice: (id: number) => Slice }
const C = createContext<Ctx | null>(null)

export function useDemo(): Ctx {
  const c = useContext(C)
  if (!c) throw new Error('useDemo outside the provider')
  return c
}

export function defaultThread(m: Manifest): Thread {
  const lead = m.slices.find(s => s.dataset === m.datasets[0].key) ?? m.slices[0]
  // the tour opens on the heart of lion's mane CH14's train: hours 6-10 of the slice
  const fs = lead.fs
  return { slice: lead.id, view: [Math.round(6 * 3600 * fs), Math.round(10 * 3600 * fs)], span: null,
    combo: m.default_combo, ran: null, seed: null, autoOn: false, source: 'library' }
}

export function DemoProvider({ m, children }: { m: Manifest; children: ReactNode }) {
  const [route, setRoute] = useState<Route>(parse)
  const [thread, setThread] = useState<Thread>(() => ({ ...defaultThread(m), ...loadThread() }))
  useEffect(() => {
    const on = () => setRoute(parse())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  useEffect(() => { try { sessionStorage.setItem(KEY, JSON.stringify(thread)) } catch { /* private mode */ } }, [thread])
  const set = useCallback((p: Partial<Thread>) => setThread(t => ({ ...t, ...p })), [])
  const reset = useCallback(() => {
    try { sessionStorage.removeItem(KEY); localStorage.removeItem('mw.tour') } catch { /* private mode */ }
    setThread(defaultThread(m))
  }, [m])
  const bySlice = useMemo(() => new Map(m.slices.map(s => [s.id, s])), [m])
  const slice = useCallback((id: number) => bySlice.get(id) ?? m.slices[0], [bySlice, m])
  return <C.Provider value={{ route, m, thread, set, reset, slice }}>{children}</C.Provider>
}

// ── small formatting helpers shared by the pages ──

export function fmtH(samples: number, fs: number): string {
  const h = samples / fs / 3600
  const hh = Math.floor(h)
  const mm = Math.round((h - hh) * 60)
  return mm === 60 ? `${hh + 1}:00` : `${hh}:${String(mm).padStart(2, '0')}`
}

export function fmtDur(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)} s`
  if (seconds < 5400) return `${Math.round(seconds / 60)} min`
  return `${(seconds / 3600).toFixed(1)} h`
}

export function fmtNum(v: number | null | undefined, nd = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '–'
  const a = Math.abs(v)
  if (a >= 100) return Math.round(v).toLocaleString()
  if (a >= 10) return v.toFixed(Math.max(0, nd - 1))
  return v.toFixed(nd + (a < 1 ? 1 : 0))
}

/** A builder setting's plain-words name, e.g. "Drop detector · 98 s letters · 8σ gate · drift 82 min". */
export function comboLabel(m: Manifest, id: string, short = false): string {
  const c = m.combos.find(x => x.id === id)
  if (!c) return id
  const d = m.menu.detectors.find(x => x.key === c.detector)
  const knobs = d ? Object.entries(d.knobs).map(([k, kn]) => `${fmtKnob(c.knobs[k])} ${kn.unit} ${kn.label.toLowerCase()}`) : []
  const head = `${d?.label ?? c.detector}${c.look_for === 'rises' ? ' (rises)' : ''}`
  return short ? head : [head, ...knobs, `drift ${Math.round(c.window_s / 60)} min`].join(' · ')
}

/** "1 event", "2 events". */
export function plural(n: number, word: string, many = `${word}s`): string {
  return `${n.toLocaleString()} ${n === 1 ? word : many}`
}

/** How far the demo reaches, read off the manifest so no page types a count: electrodes, recordings, species.
 *  Species counts distinct Latin names (chocolate oyster is a strain of oyster, so it adds a recording, not a species). */
export function breadth(m: Manifest): { channels: number; recordings: number; species: number } {
  return { channels: m.slices.length, recordings: m.datasets.length, species: new Set(m.datasets.map(d => d.latin)).size }
}

const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']

/** 3 -> "three": a small count reads better as a word inside a sentence. */
export function numWord(n: number): string {
  return WORDS[n] ?? n.toLocaleString()
}

export function fmtKnob(v: number): string {
  return Number.isInteger(v) ? String(v) : String(Math.round(v))
}

export function useAsync<T>(f: () => Promise<T>, deps: unknown[]): { data: T | null; error: Error | null; loading: boolean } {
  const [st, setSt] = useState<{ data: T | null; error: Error | null; loading: boolean }>({ data: null, error: null, loading: true })
  useEffect(() => {
    let alive = true
    setSt(s => ({ data: s.data, error: null, loading: true }))
    f().then(d => { if (alive) setSt({ data: d, error: null, loading: false }) },
            e => { if (alive) setSt({ data: null, error: e instanceof Error ? e : new Error(String(e)), loading: false }) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return st
}

export { api }
