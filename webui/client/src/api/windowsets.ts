/* fixup-af — Library › Window sets › New window set: the live reads and the write over the core's unlabelled window
 * sets (`Working/training/pool.py`, routes at the end of `webui/server/training_routes.py`). RQ1 version 2: one
 * recording, one scale, its channels, a non-overlapping grid, artifact spans left out, a seeded sample where the
 * supply is large — saved into the library of window sets with NO roles (the train / test fence is laid over the
 * pool that combines sets; that page is `AG`'s *Window pool* block). */
import { live } from './seam'
import { ApiError, type JobRow } from '../api'

async function rq<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { 'content-type': 'application/json' }, ...init })
  if (!r.ok) {
    let body: any = null
    try { body = await r.json() } catch { /* not json */ }
    const msg = body?.error ?? (typeof body?.detail === 'string' ? body.detail : body?.detail?.message) ?? `${r.status} ${r.statusText}`
    throw new ApiError(r.status, msg, body?.detail ?? body, body?.traceback)
  }
  return r.json() as Promise<T>
}

export interface SourceChannel { recording_id: number; channel: number; name: string; hours: number; n_samples: number; artifact_spans: number }
export interface SourceRecording {
  source_file: string; name: string; fs: number; hours: number; channels: SourceChannel[]
  /** pack letter → zero-based channel indices (16-channel recordings only) */
  packs: Record<string, number[]>
  /** windows a non-overlapping grid cuts at each default scale, over every channel */
  supply: Record<string, number>
}
export interface SavedSetRef { id: number; name: string; version: number; kind: string; scale_min: number | null; n_windows: number; source_files: string[]; key: string | null }
export interface UnlabelledSources {
  recordings: SourceRecording[]; scales_min: number[]
  held_out: { file: string; name: string; locked: boolean; reason: string }
  exclusions: string; sets: SavedSetRef[]; note: string
}
export const getUnlabelledSources = () => live(rq<UnlabelledSources>('/api/windowsets/unlabelled/sources'))

export interface UnlabelledSetBody {
  source_file: string; channels: number[]; scales_min: number[]; grid?: number | null; stride_factor?: number; exclude_artifacts: boolean
  sample: Record<string, number>; seed: number; name?: string | null; notes?: string | null
}
export interface BuiltSet { window_set_id: number; name: string; version: number; key: string; scale_min: number; n_windows: number; counts: Record<string, number>; path: string }
export const buildUnlabelledSets = (body: UnlabelledSetBody) =>
  rq<JobRow>('/api/windowsets/unlabelled', { method: 'POST', body: JSON.stringify(body) })
