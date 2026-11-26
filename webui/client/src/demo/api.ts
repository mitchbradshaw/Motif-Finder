/* The NeurIPS demo's client side of the station API (webui/server/demo_station.py). Every read is a pre-cooked
   answer that never changes for the life of the build, so a GET is cached for good: a second visit to a page is
   free. Writes carry the station's claim token (an old tab cannot write into the next visitor's copy). */

export type Dataset = { key: string; name: string; latin: string; source_file: string; recording: string;
  channels: number[]; hours: [number, number]; blurb: string }
export type Slice = { id: number; dataset: string; channel: number; label: string; fs: number; n: number;
  units: string; t0_s: number; source_file: string; source_recording_id: number; source_start_idx: number }
export type Knob = { label: string; unit: string; values: number[]; default: number }
export type Detector = { key: string; label: string; blurb: string; knobs: Record<string, Knob> }
export type Combo = { id: string; look_for: 'drops' | 'rises'; window_s: number; detector: string; knobs: Record<string, number> }
export type Manifest = {
  datasets: Dataset[]; slices: Slice[]; combos: Combo[]; default_combo: string; station: number
  menu: { look_for: { key: string; label: string }[]; clean_windows_s: number[]; detectors: Detector[] }
  references: { key: string; label: string; combo: string | null }[]; null: { method: string; draws: number }
}
export type Envelope = { a: number; b: number; step: number; lo: number[]; hi: number[] }
export type AutoEv = { s: number; e: number; onset: number | null; extremum: number | null; end: number | null;
  depth_mv: number | null; confidence: number | null; p_r4: number | null; sources: string; label: string;
  fall_s: number | null; width_s: number | null }
export type ChainEv = { s: number; e: number; score: number | null; onset_idx?: number | null; extremum_idx?: number | null;
  recovery_idx?: number | null; event_amplitude_mv?: number | null; event_width_s?: number | null; duration_s?: number | null;
  max_slope_mv_s?: number | null; interval_after_s?: number | null }
export type Chain = { combo: string; slice: number; n: number; events: ChainEv[]; null: number[];
  letters: { seg: number; letters: string[] } | null; intervals: Record<string, { cv?: number | null; lv?: number | null; median_s?: number | null }> | null }
export type SliceSummary = { slice: number; n: number; null_mean: number | null; null_sd: number | null; spans: [number, number][] }
export type Summary = { combo: string | null; per_slice: SliceSummary[]; by_dataset: Record<string, { n: number; null: number | null }>;
  n: number; null: number | null; ratio: number | null }
export type Reference = { key: string; label: string; combo: string | null; n: number; null: number | null; ratio: number | null;
  by_dataset: Record<string, { n: number; null: number | null }> }
export type JudgeItem = { item: number; slice: number; s: number; e: number; onset: number | null; extremum: number | null;
  depth_mv: number | null; researcher: 'yes' | 'no' | 'unsure' | null }
export type Judge = { combo: string; items: JudgeItem[]; verdicts: Record<string, string> }
export type Snip = { dt: number; v: number[] }
export type LibEv = { id: string; slice: number; dataset: string; top: number; bottom: number; recovery: number | null;
  depth_mv: number | null; fall_s: number | null; width_s: number | null; steep_s: number | null; source: string;
  family?: string; snip: Snip; snip_a: number; t_h: number }
export type Family = { id: string; dataset: string; name: string; n: number; medoid: string; shape: number[];
  median_depth_mv: number | null; median_width_s: number | null }
export type Train = { id: string; dataset: string; slice: number; n: number; members: string[]; start: number; end: number;
  median_interval_s: number | null; cv: number | null }
export type Library = { events: LibEv[]; families: Family[]; trains: Train[]; totals: { catalogue_spans?: number; recordings?: number } }
export type Match = { slice: number; dataset: string; index: number; length: number; distance: number; snip?: Snip; pad?: number }
export type Seed = { id: string; name: string; dataset: string; slice: number; event?: string; family?: string | null;
  a: number; b: number; fs: number; exemplar: Snip; matches: Match[]; n_matches: number; null: number[]; null_draws: number;
  cut: number | null; n_kept: number; kept_by_dataset: Record<string, number>; elapsed_s?: number }
export type DatasetStats = { n: number; rate_per_h: number[]; intervals: { edges_s: number[]; counts: number[] } | null;
  median_interval_s: number | null; cv: number | null; lv: number | null; scatter: [number, number][];
  icicles: { dt: number; t0: number; v: number[]; depth: number }[]; slopes_mv_s: number[] }
export type Stats = Record<string, DatasetStats>
export type StationState = { station: number; hub: string | null; epoch: number; runs: { id: number; combo: string; at: number }[];
  verdicts: Record<string, Record<string, string>> }

const cache = new Map<string, Promise<unknown>>()

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, { method, headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined })
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try { const j = await r.json(); if (j && j.detail) msg = String(j.detail) } catch { /* not json */ }
    throw new ApiError(r.status, msg)
  }
  return r.json() as Promise<T>
}

/** A read that never changes: fetched once, shared by every caller. A failure is not cached. */
export function cached<T>(url: string): Promise<T> {
  const hit = cache.get(url)
  if (hit) return hit as Promise<T>
  const p = req<T>('GET', url)
  cache.set(url, p)
  p.catch(() => cache.delete(url))
  return p
}

// ── the claim (which visitor this station belongs to) ──

const CLAIM_KEY = 'mw.claim'

export function claimToken(): string | null {
  try {
    const u = new URL(window.location.href)
    const q = u.searchParams.get('claim')
    if (q) {
      sessionStorage.setItem(CLAIM_KEY, q)
      localStorage.setItem(CLAIM_KEY, q)
      u.searchParams.delete('claim')
      window.history.replaceState(null, '', u.pathname + (u.search ? u.search : '') + u.hash)
      return q
    }
    return sessionStorage.getItem(CLAIM_KEY) || localStorage.getItem(CLAIM_KEY)
  } catch { return null }
}

const tok = () => encodeURIComponent(claimToken() ?? '')

export const api = {
  manifest: () => cached<Manifest>('/api/demo/manifest'),
  signal: (sid: number, a: number, b: number, px: number, combo?: string) =>
    cached<Envelope>(`/api/demo/signal/${sid}?a=${Math.round(a)}&b=${Math.round(b)}&px=${Math.round(px)}${combo ? `&combo=${combo}` : ''}`),
  snippets: (sid: number, spans: [number, number][], px = 120) => {
    const key = `/api/demo/snippets#${sid}:${px}:${spans.map(([a, b]) => `${a}-${b}`).join(',')}`
    const hit = cache.get(key)
    if (hit) return hit as Promise<Envelope[]>
    const p = req<Envelope[]>('POST', '/api/demo/snippets', { slice: sid, spans, px })
    cache.set(key, p)
    p.catch(() => cache.delete(key))
    return p
  },
  auto: (sid: number) => cached<{ slice: number; n: number; events: AutoEv[] }>(`/api/demo/auto/${sid}`),
  chain: (combo: string, sid: number) => cached<Chain>(`/api/demo/chain/${combo}/${sid}`),
  discovery: (combo: string) => cached<Summary>(`/api/demo/discovery/${combo}`),
  references: () => cached<Reference[]>('/api/demo/references'),
  library: () => cached<Library>('/api/demo/library'),
  seeds: () => cached<{ seeds: Seed[]; k: number }>('/api/demo/seeds'),
  stats: (source: string) => cached<Stats>(`/api/demo/stats?source=${encodeURIComponent(source)}`),
  judge: (combo: string) => req<Judge>('GET', `/api/demo/judge/${combo}`),
  state: () => req<StationState>('GET', '/api/demo/state'),
  addRun: (combo: string) => req<{ id: number }>('POST', `/api/demo/runs?token=${tok()}`, { combo }),
  verdict: (combo: string, item: number, verdict: string) =>
    req<{ ok: boolean; verdicts: Record<string, string> }>('POST', `/api/demo/judge?token=${tok()}`, { combo, item, verdict }),
  liveSeed: (slice: number, a: number, b: number) => req<Seed>('POST', '/api/demo/seed/live', { slice, a, b }),
  ping: () => req<{ mine: boolean; station: number; epoch: number; hub: string | null }>('POST', '/api/demo/ping', { token: claimToken() }),
  startOver: () => req<{ ok: boolean; epoch: number }>('POST', '/api/demo/start-over', { token: claimToken() }),
}

/** The hub's "get me a station" address, from this page's host (the hub is on the station port's base). */
export function hubClaimUrl(hub: string | null): string {
  const port = hub ? new URL(hub).port : '8900'
  return `${window.location.protocol}//${window.location.hostname}:${port}/claim`
}
