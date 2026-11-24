/* Auto-detect (2026-11-23, the researcher: "integrate the auto-detect into the site"). Routes in
 * `webui/server/autodetect_routes.py`; the core is `Working/autodetect/service.py`. One button on a channel runs the
 * reference line-up as a job (real progress, a time left); the result is read back for the page; a send puts the
 * candidates (and the sequences they make) in Review. */
import { ApiError, fetchBridge, READ_TIMEOUT_MS } from '../api'

async function rq<T>(path: string, init?: RequestInit): Promise<T> {
  const write = !!init?.method && init.method !== 'GET'
  const r = await fetchBridge(path, { headers: { 'content-type': 'application/json' }, ...init }, write ? null : READ_TIMEOUT_MS)
  if (!r.ok) {
    let body: any = null  // eslint-disable-line @typescript-eslint/no-explicit-any
    try { body = await r.json() } catch { /* not json */ }
    const d = body?.detail
    const msg = body?.error ?? (typeof d === 'string' ? d : d?.message) ?? `${r.status} ${r.statusText}`
    throw new ApiError(r.status, msg, d ?? body, body?.traceback)
  }
  return r.json() as Promise<T>
}

export interface AdSetup {
  ready: boolean; problems: string[]; missing_detectors: string[]; version: string; seconds_per_sample: number
  /** what any run costs whatever its length */
  fixed_s?: number
  rules: { rise_sharpness?: number; min_steady_samples?: number; min_significance?: number }; results_root?: string
}
export interface AdSummary { candidates: number; at_05: number; drops_05: number; rises_05: number; sequences: number; wall_s: number }
export interface AdSent {
  at: string; min_confidence: number; polarities: string[]; queue_id: number | null; sequence_queue_id: number | null
  detections: number; sequences: number; candidate_ids: number[]
  /** the result's own sequence ids this send put in sequence review (absent on a send before 2026-11-23 late) */
  sequence_ids?: number[]
}
export interface AdListed {
  job_id: number; recording_id: number; created_at: string | null; version: string | null
  stretch: { start_idx: number; end_idx: number; n_samples: number } | null; summary: AdSummary | null; sent: AdSent[]
}
export interface AdJobSnap {
  job_id: number; status: string; elapsed_s: number; error: { message: string } | null
  progress: { done: number; total: number | null; message: string }; meta: Record<string, unknown>
}
/** Candidates column by column; sample indices are relative to the result's stretch (`start_idx`). */
export interface AdCands {
  id: number[]; s: number[]; e: number[]; c: number[]; p: (number | null)[]; k: number[]; src: number[]; seq: number[]
  pol: number[]; dep: (number | null)[]; ex: (number | null)[]; inv: number[]; both: number[]; shp: (number | null)[]
  rec: boolean[]; fam: string[]; lifts: string[]; sp: (number | null)[]
}
export interface AdSeqs { id: number[]; s: number[]; e: number[]; n: number[]; mc: (number | null)[]; pol: number[] }
export interface AdResult {
  job_id: number; version: string | null; created_at: string | null; wall_s: number | null
  recording: { id: number; source_file: string; channel: number; fs: number; units: string | null; n_samples: number }
  start_idx: number; n: number; fs: number; candidates: AdCands; sequences: AdSeqs
  sources: string[]; source_labels: Record<string, string>; summary: AdSummary | null; notes: string[]
  floor_mv: number | null; missing_detectors: string[]; sent: AdSent[]
  /** the spans judged on this recording - all that Review can match a sent candidate against */
  judged_here?: number
  rules: { rise_sharpness?: number | null; drop_rule?: { min_steady_samples?: number; min_significance?: number; sharp?: number } | null }
}
export interface AdSignal {
  recording_id: number; start_idx: number; n: number; fs: number; unit: string; unit_note: string | null
  scale: number; offset: number; missing: number; b64: string
}
export interface AdSendResult {
  queue_id: number | null; detections: number; sequence_queue_id: number | null; sequences: number; already_sent: number
  sequences_already_sent?: number; run_id?: number
  /** one machine run per lane: candidates that overlap go in different runs, so Review asks about each one */
  run_ids?: number[]; items?: number
  /** how many of the sent candidates Review holds back as the same event as one already judged; null when not counted */
  held_back?: number | null; held_back_error?: string
}

export const getAdSetup = () => rq<AdSetup>('/api/autodetect/setup')
export const startAutoDetect = (recording_id: number, t0_s: number | null, t1_s: number | null) =>
  rq<{ job_id: number; estimate_s: number; status: string }>('/api/autodetect/runs', { method: 'POST', body: JSON.stringify({ recording_id, t0_s, t1_s }) })
export const listAutoDetect = (recording_id: number) =>
  rq<{ results: AdListed[]; running: AdJobSnap | null }>(`/api/autodetect/runs?recording_id=${recording_id}`)
export const getAutoDetect = (job_id: number) => rq<AdResult>(`/api/autodetect/runs/${job_id}`)
export const getAdSignal = (recording_id: number, start_idx: number, end_idx: number) =>
  rq<AdSignal>(`/api/autodetect/signal/${recording_id}?start_idx=${start_idx}&end_idx=${end_idx}`)
export const sendAutoDetect = (job_id: number, body: { min_confidence: number; polarities: string[]; candidate_ids?: number[] | null; sequences: boolean }) =>
  rq<AdSendResult>(`/api/autodetect/runs/${job_id}/send`, { method: 'POST', body: JSON.stringify(body) })
