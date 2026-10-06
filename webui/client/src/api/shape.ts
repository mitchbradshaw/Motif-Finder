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
  /** fixup-ag continuation: one histogram per recording × scale on shared log bins, with that recording's floor */
  raw_range_by?: Record<string, { floor_mv: number | null; from: string | null; scales: Record<string, HistData | null> }>
  align?: 'grid' | 'centre'; detrend?: 'off' | 'linear'; align_rule?: string; detrend_rule?: string; swing_rule?: string
  recut?: { n_moved: number; n_clamped: number; n_pinned_by_artifact: number; n_near_duplicate: number; n_overlap_within_scale: number
    by_scale: Record<string, { moved: number; clamped: number; near_duplicate: number }>; rule: string }
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
  align?: string; detrend?: string; propose_cached?: boolean
  pool_key?: string | null; frozen?: Frozen | null
  n_train: number; n_clustered: number; n_assigned: number; not_clustered: Record<string, number>
  sample: number | null; seed: number; stratified_by: string; ward_seconds: number | null; peak_rss_mb: number | null
  method_text: string; library_method: string; resample_length: number
  dendrogram: Dendrogram
  propose: { by_k: ProposeRow[]; suggested_k: number | null; small_below: number; n_train: number; suggestion_rule: string; note: string }
  clusters: ClusterLine[]; small_below: number; mapping: { k: number | null; clusters: Record<string, MappingEntry> }
  mapping_state: 'none' | 'partial' | 'complete' | 'stale'; seconds: number; rule: string
}
export type TreePayload = GroupingPayload & { tree?: TreeInfo }

export const isPoolPayload = (p: unknown): p is PoolPayload => !!p && typeof p === 'object' && (p as PoolPayload).type === 'windowset' && !!(p as PoolPayload).pool_windows
export const isTreePayload = (p: unknown): p is TreePayload => !!p && typeof p === 'object' && (p as TreePayload).type === 'grouping' && !!(p as TreePayload).tree

/* ---------------- seam (ii): the dendrogram page reads the kept tree by its key ---------------- */
export interface CutAt { key: string; k: number; cut_height: number; clusters: ClusterLine[]; small_below: number; n_clustered: number; n_assigned: number; n_train: number }
export interface DetailWindow {
  row: number; recording_id: number; source_file: string; channel: number; start: number; length: number; fs: number
  scale_min: number; role: string; raw_range_mv: number | null; peak_frac: number | null; shape: number[]; raw_mv: number[] | null; unit: string | null
}
export interface ClusterDetail {
  key: string; cluster: number; k: number; n: number; n_in_sample: number; n_assigned: number
  medoid: DetailWindow & { rule: string }; members: DetailWindow[]; members_seed: number; mean: number[]; sd: number[]
  scales: { scale_min: number; n: number }[]; recordings: { recording: string; n: number }[]; channels: { recording: string; channel: number; n: number }[]
  amplitude_mv: { min: number | null; q25: number | null; median: number | null; q75: number | null; max: number | null; n_measured: number }
  peak_position_hist: number[]
}
export const getTreeCut = (key: string, k: number) => rq<CutAt>(`/api/shape/trees/${encodeURIComponent(key)}/cut?k=${k}`)
export const getClusterDetail = (key: string, k: number, c: number, seed = 0) => rq<ClusterDetail>(`/api/shape/trees/${encodeURIComponent(key)}/cluster?k=${k}&c=${c}&seed=${seed}`)

/* ---------------- one card per cluster at the cut (the researcher, 2026-10-06) ---------------- */
export interface ClusterCard { cluster: number; n: number; scales?: Record<string, number>; medoid?: DetailWindow; members?: DetailWindow[]; error?: string }
export interface Cards { key: string; k: number; n_members: number; cut_height: number; cards: ClusterCard[]; note: string }
export const getClusterCards = (key: string, k: number) => rq<Cards>(`/api/shape/trees/${encodeURIComponent(key)}/cards?k=${k}`)

/* ---------------- seam (iii): arm B.2 on Models › Launch ---------------- */
export interface Frozen { run_id: number; k: number; mapping: { k: number | null; clusters: Record<string, MappingEntry> }; name: string }
export interface B2Check { name: string; level: 'pass' | 'warn' | 'error'; detail: string }
export interface B2Run {
  run_id: number; status: string; name: string; started_at: string; finished_at: string | null; duration_s: number | null
  pool: { id: number; name: string; version: number; key: string }; template: { id: number; name: string }; k: number
  mapping: { k: number | null; clusters: Record<string, MappingEntry> }; scored: boolean
  diagnostic: { kind: string; accuracy: number; macro_f1: number; chance_largest_cluster: number; n_held_back: number; note: string } | null
  exams: Record<string, { status: string; n: number; by_class: Record<string, number> }>; results_path: string | null; error: string | null
  /** fixup-ai: a B.2 run is a forest or a CNN */
  kind?: string; model?: string; smoke?: boolean
}
export interface B2Setup {
  template: { id: number; name: string; steps: { stage: string; algorithm: string; params: Record<string, unknown> }[] }
  pool: { id: number; name: string; version: number; key: string; n_windows: number; by: CountRow[]; by_role: Record<string, number>
    recordings: { source_file: string; name: string; channels: { channel: number; name: string; role: 'train' | 'exam'; n: number }[] }[]
    plan: { n_blocks: number; test_frac: number; validation_frac: number; gap_s: number; hold_out_pack: string | null }; rule: string }
  arm: { name: string; label: string; k: number; mapping: { k: number | null; clusters: Record<string, MappingEntry> }; read_only: boolean; mapping_state: string; where: string }
  shape: { align: string; detrend: string; resample_length: number; noise_floor: boolean }
  cluster: { sample: number; seed: number }
  inputs: { features: string; stages: string[]; rule: string }
  frozen: Frozen | null; checks: B2Check[]; defaults: { n_estimators: number; class_weight: string; random_state: number }
  runs: B2Run[]; slurm: string
  /** fixup-ai: the CNN arm (encodings, defaults, the image rule, the null, how results return) */
  cnn?: import('./cnn').CnnSetup
}
export const getB2Setup = (template: number, pool: number) => rq<B2Setup>(`/api/models/b2/setup?template=${template}&pool=${pool}`)
export const trainB2 = (body: { template: number; pool: number; n_estimators?: number }) =>
  rq<{ job_id: number; status: string }>('/api/models/b2/train', { method: 'POST', body: JSON.stringify(body) })
export const getB2Runs = () => rq<{ runs: B2Run[] }>('/api/models/b2/runs')
export const getFrozen = (poolKey: string) => rq<{ frozen: Frozen | null }>(`/api/models/b2/frozen?pool_key=${encodeURIComponent(poolKey)}`)

/* ---------------- Library › Window sets: rename ---------------- */
export const renameWindowSet = (id: number, name: string) =>
  rq<{ id: number; name: string; version: number; key: string | null; changed: boolean; was?: string }>(`/api/windowsets/${id}/name`, { method: 'PATCH', body: JSON.stringify({ name }) })
