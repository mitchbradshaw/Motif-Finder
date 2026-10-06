/* fixup-ai — arm B.2 with a CNN (routes in `webui/server/cnn_routes.py`; the core is
 * `Working/training/shape_cnn.py`, `cnn_job.py`, `full_ward.py`, `hpc_import.py`). *Create SLURM script* writes a job
 * directory the cluster runs without the database; the results come back by `python -m Working.training
 * import-results <job>` (and Jobs › Manifest inbox, AJ). */

async function rq<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { 'content-type': 'application/json' }, ...init })
  if (!r.ok) {
    let body: unknown = null
    try { body = await r.json() } catch { /* not json */ }
    const detail = (body as { detail?: unknown } | null)?.detail
    throw new Error(`${r.status} ${typeof detail === 'string' ? detail : r.statusText}`)
  }
  return r.json() as Promise<T>
}

export type Encoding = 'fusion' | 'GASF' | 'GADF' | 'recurrence'
export interface CnnDefaults { backbone: string; pretrained: boolean; img_size: number; epochs: number; batch_size: number; lr: number; weight_decay: number; schedule: string; class_weight: string; augmentation: string; random_state: number; refit: boolean }
export interface Measured { encode_ms_by_scale?: Record<string, number>; train_img_per_s?: number; predict_img_per_s?: number; device?: string; run_id?: number }
export interface CnnSetup {
  encodings: Encoding[]; default_encoding: Encoding; defaults: CnnDefaults; smoke_defaults: { n_train: number; n_predict: number; epochs: number; batch_size: number }
  images_rule: string; augmentation: string; null: { n: number; default_on: boolean; note: string }
  measured: Record<string, { local: Measured | null; cluster: Measured | null }>; returns: string; fusion_note: string
}
export interface CopyRow { what: string; path: string; bytes: number; note?: string }
export interface Estimate {
  label: string; seconds: number | null
  parts: { encode_s: number | null; encode_cpu_s: number | null; train_s: number; predict_s: number }
  images: { fit: number; eval: number; epochs: number }; cache_bytes: number; this_cpu_train_s: number | null
  assumptions: string[]; measured_from: { local: number | null; cluster: number | null }
}
export interface CnnSlurm {
  job_dir: string; job_repo: string; recipe_hash: string; model: string; n_windows: number; n_train: number; n_predict: number
  by_scale: Record<string, number>; copy: CopyRow[]; total_bytes: number; estimate: Estimate; script: string; script_path: string
  sbatch_command: string; null_script: string | null; null_script_path: string | null; null: { n: number; on: boolean; note: string; gpu_hours?: number | null; sbatch_command?: string }
  slurm_time: string; chain_jobs: number; jobs_needed: number | null; deadline_min: number; warnings: string[]; images_rule: string; steps: string[]; returns: string
}
export interface CnnSmoke { run_id: number; results_path: string; job_dir: string; measured: Measured; timings: Record<string, number>; export_s: number; total_s: number; n_windows: number; created: boolean }
export interface WardSlurm {
  job_dir: string; job_repo: string; recipe_hash: string; n: number
  memory: { n: number; bytes_distances: number; bytes_peak: number; request_gb: number; rule: string }
  seconds_estimate: number; slurm_time: string; partition: string; script: string; script_path: string; sbatch_command: string
  copy: CopyRow[]; total_bytes: number; steps: string[]; returns: string; warnings: string[]
  frozen: { run_id: number; k: number } | null; frozen_note: string | null
}

export interface CnnBody { template: number; pool: number; encoding: Encoding; cnn?: Partial<CnnDefaults>; smoke?: Record<string, number>; null?: boolean }
export const createCnnSlurm = (body: CnnBody) =>
  rq<{ job_id: number; status: string }>('/api/models/b2/cnn/slurm', { method: 'POST', body: JSON.stringify(body) })
export const runCnnSmoke = (body: CnnBody) =>
  rq<{ job_id: number; status: string }>('/api/models/b2/cnn/smoke', { method: 'POST', body: JSON.stringify(body) })
export const createWardSlurm = (treeKey: string) =>
  rq<WardSlurm>(`/api/shape/trees/${treeKey}/ward-slurm`, { method: 'POST', body: '{}' })

export function fmtBytes(b: number) {
  if (b >= 2 ** 30) return `${(b / 2 ** 30).toFixed(2)} GB`
  if (b >= 2 ** 20) return `${(b / 2 ** 20).toFixed(1)} MB`
  if (b >= 2 ** 10) return `${(b / 2 ** 10).toFixed(0)} KB`
  return `${b} B`
}
export function fmtSecs(s: number | null | undefined) {
  if (s == null) return '—'
  if (s >= 3600) return `${(s / 3600).toFixed(1)} h`
  if (s >= 60) return `${(s / 60).toFixed(1)} min`
  return `${s.toFixed(0)} s`
}
