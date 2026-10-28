/* Cross-channel census reads and writes (xc-S1; webui/server/cross_routes.py over Working/cross_census.py) — live.
 *
 *  · `GET /api/cross/census?source_file=&detector=` — the latest census of one detector on one recording (its
 *    summary, hash, stale and why), the detectors offered (each full or with its reason), whether the layout is
 *    known, the rules in words, and a census job already running; `census: null` when none has been run. The page
 *    never computes the census on load (D20).
 *  · `POST /api/cross/census` — starts a `cross_census` job (423 held out; 422 not full, in words; 409 one running).
 *  · `GET /api/cross/census/{id}/cooccurrences` — its rows, filtered (for S7's candidate list).
 *
 *  Every number and every rule's words come from the bridge; nothing here recomputes one. */
import { ApiError, fetchBridge, READ_TIMEOUT_MS, type JobRow } from '../api'

export type CensusBin = 'artifact' | 'propagation' | 'independent_recurrence' | 'shared_driver' | 'pack_unknown' | 'unmeasured'
export const CENSUS_BINS: CensusBin[] = ['artifact', 'propagation', 'independent_recurrence', 'shared_driver', 'pack_unknown', 'unmeasured']

export interface CensusTimetable {
  n_noncopy: number; count: number; L_s: number | null; median_lag_s: number | null; mad_s: number | null
  p: number | null
  /** the Benjamini–Hochberg level the test was held to; null when it fails (or was not testable) */
  q: number | null
  testable: boolean; reason: string | null; pool: number; null_mean: number | null; null_p95: number | null
}
export interface CensusPair {
  a: number; b: number; a_name: string; b_name: string; pack: string
  /** co-occurrences of this pair, against its rotation null */
  n: number; null_mean: number; null_p95: number; p: number; q: number | null
  bins: Record<CensusBin, number>
  timetable: CensusTimetable
}
export interface CensusOverall { n: number; null_mean: number | null; null_p95: number | null; p: number | null; pairs: number }
export interface CensusSharedDriver extends CensusOverall { packs: string[]; copies: number; q: number | null }
export interface CensusInstant {
  instant_id: number; breadth: number; channels: number[]; names: string[]; packs: string[]; onset_s: number
  common_mode: boolean; why: string | null; n_events: number; p: number; q: number | null
}
export interface CensusRules {
  co_occurrence: string; window: string; lag_search: string; onset: string; common_mode: string; correction: string
  bins: Record<CensusBin, string>
  /** the bins are per-co-occurrence classifications with no null; the claim is the excess and timetable tests */
  bins_note: string
  /** a pair inside one instant is an artifact whatever its own lag (D9) */
  absorbed: string
  nulls: { excess: string; waveform: string; timetable: string; breadth: string; shared_driver: string }
}
export interface CensusSummary {
  source_file: string; detector: string; hash: string; fs: number; hours: number
  n_channels: number; n_events: number; n_cooccurrences: number
  events_per_channel: Record<string, number>; onset_from: { label: number; steepest_fall: number }
  bins: Record<CensusBin, number>; common_mode_pairs: number; unmeasured: number
  /** pairs moved to artifact because both their events sit in one instant (fix round) */
  absorbed_into_instants?: number
  layout_known: boolean; layout_note: string | null; pack_unknown: number; packs: string[]
  pairs: CensusPair[]
  overall: { within_pack: CensusOverall; shared_driver: CensusOverall }
  shared_driver: CensusSharedDriver[]
  breadth: CensusInstant[]
  breadth_null: { k: number; mean: number; p95: number }
  bh: { method: string; q: number; families: { excess: number; timetable: number; breadth: number; shared_driver: number } }
  rules: CensusRules
  timing_s?: number
}
export interface CensusRow {
  id: number; sourceFile: string; detector: string; hash: string; status: string
  createdAt: string; finishedAt: string | null; actor: string | null
  summary: CensusSummary; rule: Record<string, number>; consts: Record<string, unknown>; nullPath: string | null
  stale: boolean; staleWhy: string[]
}
export interface CensusDetector { detector: string; full: boolean; reason: string | null; nWithRun: number; nChannels: number }
export interface CensusRead {
  sourceFile: string; detector: string
  census: CensusRow | null
  detectors: CensusDetector[]
  layoutKnown: boolean; layoutNote: string | null; packs: string[]
  rules: CensusRules
  /** a census job of this file and detector already running (a job snapshot), so a reload picks it up */
  running: JobRow | null
}
export interface CensusAck { job_id: number; kind: 'cross_census'; status: string; sourceFile: string; detector: string }
export interface CensusCooccurrence {
  id: number; census_id: number; det_a_id: number; det_b_id: number; rec_a_id: number; rec_b_id: number
  onset_a_s: number; onset_b_s: number; lag_s: number | null; r: number | null; bin: CensusBin
  cross_pack: boolean | null; instant_id: number | null; common_mode: boolean
  chance: Record<string, unknown> | null; floor: Record<string, unknown> | null; amplitude_ratio: number | null
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const write = !!init?.method && init.method !== 'GET'
  const r = await fetchBridge(path, { headers: { 'content-type': 'application/json' }, ...init }, write ? null : READ_TIMEOUT_MS)
  if (!r.ok) {
    let body: any = null   // eslint-disable-line @typescript-eslint/no-explicit-any
    try { body = await r.json() } catch { /* not json */ }
    const msg = body?.error ?? (typeof body?.detail === 'string' ? body.detail : body?.detail?.message) ?? `${r.status} ${r.statusText}`
    throw new ApiError(r.status, msg, body?.detail ?? body, body?.traceback)
  }
  return r.json() as Promise<T>
}

/** 423 for the held-out recording; 404 for an unregistered file. */
export const getCensus = (sourceFile: string, detector?: string) =>
  call<CensusRead>(`/api/cross/census?source_file=${encodeURIComponent(sourceFile)}${detector ? `&detector=${encodeURIComponent(detector)}` : ''}`)

/** 422 (in words) when the detector has no real run on every channel; 409 when one is already running. */
export const startCensus = (sourceFile: string, detector?: string) =>
  call<CensusAck>('/api/cross/census', { method: 'POST', body: JSON.stringify({ source_file: sourceFile, detector: detector ?? null }) })

export const getCensusCooccurrences = (censusId: number, q: { bin?: CensusBin; a?: number; b?: number; instant?: number; limit?: number; offset?: number } = {}) => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== null) p.set(k, String(v))
  const qs = p.toString()
  return call<{ censusId: number; total: number; rows: CensusCooccurrence[] }>(`/api/cross/census/${censusId}/cooccurrences${qs ? `?${qs}` : ''}`)
}
