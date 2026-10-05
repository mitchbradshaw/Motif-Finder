/* fixup-ag — the RQ1 version-2 chain: Window pool → Trace shape → Shape clustering (routes in
 * `webui/server/shape_routes.py`; the core is `Working/training/pool.py` + `Working/training/shape.py`).
 * The payload fields below ride on the existing WindowSet / Grouping payloads (`webui/server/serialize.py`):
 * a pool WindowSet carries `pool_windows` (+ `pool`, + `shape` after a Trace shape step); a Grouping that kept
 * its tree carries `tree`. */
import { ApiError, type GroupingPayload, type WindowsetPayload } from '../api'

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

/* ---------------- the library of saved window sets (the Window pool block's page) ---------------- */
export interface LibrarySet {
  id: number; name: string; version: number; kind: 'unlabelled' | 'pool' | 'labelled_across_channels' | 'labelled_one_channel' | string
  scale_min: number | null; scales_min: number[] | null; n_windows: number; source_files: string[]; key: string | null; created_at: string
  n_channels: number; per_recording: Record<string, number>; counts: Record<string, unknown> | null; hold_out_pack: string | null
  labels_source: string | null; rule: string | null; dropped: number | null
}
export interface WindowSetLibrary { sets: LibrarySet[]; defaults: Record<string, unknown>; rules: Record<string, string>; packs: Record<string, number[]>; note: string }
export const getWindowSetLibrary = () => rq<WindowSetLibrary>('/api/windowsets/library')

/* ---------------- payload extras ---------------- */
export interface CountRow { recording: string; scale_min: number; role: string; n: number }
export interface PoolInfo {
  window_set_id: number; name: string; version: number; key: string; path: string; saved: 'saved' | 'reused' | 're-opened'
  n_windows: number; by: CountRow[]; by_role: Record<string, number>; by_scale: Record<string, number>
  dropped: Record<string, number>; at_build: Record<string, number>; checks: Record<string, number> | null
  rule: string; rule_text: string; sample: Record<string, number> | null; seed: number
  members: { id: number; name: string; version: number; kind: string; key: string | null; n_offered: number; n_kept: number; dropped: Record<string, number> }[]
  plan: { n_blocks: number; test_frac: number; validation_frac: number; gap_s: number; hold_out_pack: string | null }
  stretches: Record<string, { exam_channels: number[]; stretches: { role: string; start_s: number; end_s: number }[]; duration_s: number }>
  summary: string
}
export interface HistData { counts: number[]; edges: number[]; log: boolean }
export interface ShapeInfo {
  resample_length: number; noise_floor: boolean; floors: Record<string, { floor_mv: number; from: string }>
  n_in: number; n_kept: number
  under_floor: { n: number; by: CountRow[]; n_would_be: number; rule: string }
  unmeasured: { n: number; by: CountRow[]; rule: string }
  method: string; seconds: number; shape_file: string; shape_key: string
  raw_range_hist?: HistData | null; raw_range_by_scale?: Record<string, HistData | null>
  peak_frac_hist?: HistData | null; peak_frac_by_scale?: Record<string, HistData | null>
}
export type PoolPayload = WindowsetPayload & {
  pool_windows?: { n: number; by: CountRow[]; by_role: Record<string, number>; by_scale: Record<string, number> }
  pool?: PoolInfo; shape?: ShapeInfo
}
export interface ProposeRow { k: number; silhouette: number | null; sizes: Record<string, number>; small_clusters: number[]; effective_k: number; cut_height: number }
export interface ClusterLine { cluster: number; n: number; speck: boolean; scales: Record<string, number>; recordings: Record<string, number>; median_range_mv: number | null; peak_frac_median: number | null }
export interface Dendrogram { icoord: number[][]; dcoord: number[][]; leaves: string[]; counts: number[]; heights: number[]; max_height: number; n_leaves: number }
export interface MappingEntry { name: string; class: 'interesting' | 'not_interesting' | null }
export interface TreeInfo {
  key: string; dir: string; reused: boolean; loaded_from: string | null; shape_file: string; shape_key: string
  k: number; k_param: number; suggested_k: number | null; cut_height: number
  n_train: number; n_clustered: number; n_assigned: number; not_clustered: Record<string, number>
  sample: number | null; seed: number; stratified_by: string; ward_seconds: number | null; peak_rss_mb: number | null
  method_text: string; library_method: string; resample_length: number
  dendrogram: Dendrogram
  propose: { by_k: ProposeRow[]; suggested_k: number | null; small_below: number; n_train: number; suggestion_rule: string; note: string }
  clusters: ClusterLine[]; small_below: number; mapping: Record<string, MappingEntry>; seconds: number; rule: string
}
export type TreePayload = GroupingPayload & { tree?: TreeInfo }

export const isPoolPayload = (p: unknown): p is PoolPayload => !!p && typeof p === 'object' && (p as PoolPayload).type === 'windowset' && !!(p as PoolPayload).pool_windows
export const isTreePayload = (p: unknown): p is TreePayload => !!p && typeof p === 'object' && (p as TreePayload).type === 'grouping' && !!(p as TreePayload).tree
