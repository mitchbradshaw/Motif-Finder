/* Jobs reads (frames jobs-1 … jobs-4, spec §7c). The fixture reads below resolve through the seam and say
 * `source: 'demo'`; their writes (marks, continue, cancel, place, import) stay in the in-memory store — see
 * jobs/store.ts. fixup-aj: the live reads at the end of this file (the bridge's jobs, the job directories written
 * for the cluster, the Manifest inbox's import) say `source: 'live'`. */
import { demo, live, type Sourced } from './seam'
import { listJobs, type JobRow, type JobStep } from '../api'
import {
  CLUSTER_JOBS, FINISHED_TODAY, INBOX, LOCAL_JOBS, PAUSED_RUNS, PROFILES, QUEUE_JOBS, UPLOAD_FILES, UPLOAD_NULL_NOTE, WORKSPACE_ICON,
  type ClusterJob, type FinishedJob, type LocalJob, type Manifest, type PausedRun, type QueueJob, type UploadFile, type UploadFileKey,
} from '../fixtures/jobs'

export type { ClusterJob, ClusterStatus, CheckState, FinishedJob, LocalJob, Manifest, PausedRun, QueueJob, ResultCheck, ResultState, RunStage, StageState, UploadFile, UploadFileKey, Workspace } from '../fixtures/jobs'
export { WORKSPACE_ICON }

export interface JobsOverview { paused: PausedRun[]; cluster: ClusterJob[]; local: LocalJob[]; queues: QueueJob[]; finished: FinishedJob[] }
/** Everything the All jobs page lists (§7c.1). */
export const getJobsOverview = (): Promise<Sourced<JobsOverview>> =>
  demo({ paused: PAUSED_RUNS, cluster: CLUSTER_JOBS, local: LOCAL_JOBS, queues: QUEUE_JOBS, finished: FINISHED_TODAY })

/** One paused run (§7c.2); `null` when the id is not a paused run. */
export const getPausedRun = (id: string): Promise<Sourced<PausedRun | null>> => demo(PAUSED_RUNS.find(r => r.id === id) ?? null)

/** One cluster job (§7c.4); `null` when the id is not a canon cluster job (added jobs come from the demo store). */
export const getClusterJob = (id: string): Promise<Sourced<ClusterJob | null>> => demo(CLUSTER_JOBS.find(j => j.id === id) ?? null)

export interface InboxData { watching: string; every: string; lastLooked: string; manifests: Manifest[]; pending: Manifest }
/** The manifest inbox (watched folder, arrived manifests, stage results for paused runs). */
export const getManifestInbox = (): Promise<Sourced<InboxData>> => demo(INBOX)

/** Cluster profiles from Settings › Compute & HPC. */
export const getProfiles = (): Promise<Sourced<string[]>> => demo(PROFILES)

export interface UploadData { files: UploadFile[]; nullNote: { title: string; body: string } }
/** The files a hand upload can pick from in the demo, with the checks each one produces (§7c.3). */
export const getUploadFiles = (): Promise<Sourced<UploadData>> => demo({ files: UPLOAD_FILES, nullNote: UPLOAD_NULL_NOTE })
export const UPLOAD_FILE_KEYS: UploadFileKey[] = ['mismatch', 'ok-no-nulls', 'ok', 'held-out']

/* ------------------------------------------------------------------ fixup-aj: what is live
 * The bridge's own job table (`GET /api/jobs`), the job directories the site wrote for the cluster
 * (`GET /api/hpc/exported`, `webui/server/jobs_routes.py`) and the Manifest inbox (`POST /api/hpc/inbox/import`,
 * which calls `Working.training.hpc_import.import_results` — the CLI's function). Everything above stays demo. */

async function hpcReq<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { 'content-type': 'application/json' }, ...init })
  if (!r.ok) {
    let body: unknown = null
    try { body = await r.json() } catch { /* not json */ }
    const detail = (body as { detail?: unknown } | null)?.detail
    throw new Error(`${r.status} ${typeof detail === 'string' ? detail : r.statusText}`)
  }
  return r.json() as Promise<T>
}

export type LiveStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
export interface LiveJob {
  id: number; kind: string; kindLabel: string; status: LiveStatus; stage: string; where: string
  /** 0…1, or null when the job does not count its work */
  fraction: number | null; message: string
  started: Date | null; finished: Date | null; durationS: number | null
  error: { message: string; type: string; traceback?: string } | null
  restored: boolean; route: string | null; routeLabel: string | null; jobDir: string | null
}

const KIND_LABEL: Record<string, string> = {
  chain_run: 'chain run', training: 'training', sweep: 'Discovery sweep', import: 'import', regroup: 'Library grouping',
  cross_channel: 'cross-channel',
}

function when(v: number | string | null | undefined): Date | null {
  if (v == null || v === '') return null
  const d = typeof v === 'number' ? new Date(v * 1000) : new Date(v)
  return Number.isNaN(d.getTime()) ? null : d
}

/** One row of the bridge's job table as Jobs shows it: kind, stage, progress, started, duration, error. */
export function toLiveJob(j: JobRow): LiveJob {
  const kind: string = j.kind ?? 'chain_run'
  const meta = (j.meta ?? {}) as Record<string, unknown>
  const started = when(j.started_at), finished = when(j.finished_at)
  const elapsed = (j as unknown as { elapsed_s?: number }).elapsed_s
  const durationS = started ? ((finished ?? (j.status === 'running' || j.status === 'queued' ? new Date() : null))?.getTime() ?? NaN) / 1000 - started.getTime() / 1000 : null
  let stage = String(meta.stage ?? meta.what ?? KIND_LABEL[kind] ?? kind)
  let fraction: number | null = null
  let message = ''
  if (kind === 'chain_run') {
    const steps: JobStep[] = j.steps ?? []
    const n = j.n_steps ?? steps.length
    const done = steps.filter(s => s.status === 'done').length
    const cur = steps.find(s => s.status === 'running') ?? (j.current_step != null ? steps[j.current_step] : undefined)
    stage = steps.length ? steps.map(s => s.algorithm).join(' → ') : 'chain run'
    fraction = n ? done / n : null
    message = cur ? `step ${cur.index + 1} of ${n} · ${cur.algorithm}` : n ? `${done} of ${n} steps` : ''
  } else {
    const p = (j.progress ?? {}) as { done?: number; total?: number | null; message?: string }
    if (p.total) fraction = Math.max(0, Math.min(1, (p.done ?? 0) / p.total))
    message = p.message ?? ''
  }
  if (j.status === 'completed') fraction = 1
  const res = (j.result ?? null) as { run_id?: number } | null
  let route: string | null = null, routeLabel: string | null = null
  if (kind === 'chain_run') { route = 'analyse/chain'; routeLabel = 'Analyse' }
  else if (kind === 'training') {
    route = res?.run_id && /B\.2/.test(stage) ? `models/results/b2/${res.run_id}` : /B\.2|forest|CNN|blind/.test(stage) ? 'models/results' : 'models/launch'
    routeLabel = 'Models'
  } else if (kind === 'sweep') { route = 'discovery/runs'; routeLabel = 'Discovery' }
  else if (kind === 'regroup' || kind === 'cross_channel' || (kind === 'import' && meta.what !== 'cluster results')) { route = 'library'; routeLabel = 'Library' }
  return {
    id: j.job_id, kind, kindLabel: KIND_LABEL[kind] ?? kind, status: j.status, stage, where: String(meta.where ?? 'this machine'),
    fraction, message, started, finished, durationS: Number.isFinite(durationS as number) ? durationS : (elapsed ?? null),
    error: j.error ? { message: j.error.message, type: j.error.type, traceback: j.error.traceback } : null,
    restored: !!j.restored, route, routeLabel, jobDir: typeof meta.job_dir === 'string' ? meta.job_dir : null,
  }
}

/** The bridge's real local jobs, newest first. */
export const getLocalJobs = (limit = 60): Promise<Sourced<LiveJob[]>> => live(listJobs(limit).then(rows => rows.map(toLiveJob)))

export interface CopyItem { what: string; path: string; bytes: number; note?: string }
export type ExportedState = 'written' | 'returned' | 'importing' | 'imported' | 'refused' | 'failed' | 'unreadable'
export interface ImportAttempt {
  job_id: number; job_dir: string | null; recipe_hash: string | null; outcome: 'imported' | 'refused' | 'failed' | 'importing' | string
  status: string; message: string; error_type: string | null; traceback: string | null; started_at: number | string | null; finished_at: number | string | null
}
export interface ExportedJob {
  name: string; job_dir: string; job_repo: string; kind: string | null; kind_label: string | null; recipe_hash: string | null
  recipe_ok: boolean | null; written_at: string | null; smoke: boolean; model: string | null; pool_key: string | null; n?: number | null
  scripts: { name: string; path: string; repo: string }[]; sbatch_command: string | null; copy: CopyItem[]; total_bytes: number
  returned: { status: string; recipe_hash: string | null; finished_at: string | null } | null
  imported: { run_id: number; name: string | null } | null; error: string | null
  state: ExportedState; reason: string | null; last_attempt: ImportAttempt | null
  open: { label: string; route: string; note?: string } | null
}
export interface ExportedList { jobs: ExportedJob[]; roots: string[]; mode: string; note: string }
/** Every job directory the site wrote for the cluster, with what to copy and its state. */
export const getExportedJobs = (): Promise<Sourced<ExportedList>> => live(hpcReq<ExportedList>('/api/hpc/exported'))
/** The Manifest inbox's import attempts, newest first. */
export const getInboxAttempts = (): Promise<Sourced<{ attempts: ImportAttempt[]; roots: string[] }>> => live(hpcReq('/api/hpc/inbox'))
/** Hand the inbox a returned job directory: a local `import` job (the CLI's import function) — follow it with `subscribeJob`. */
export const importReturnedJob = (path: string) =>
  hpcReq<{ job_id: number; status: string }>('/api/hpc/inbox/import', { method: 'POST', body: JSON.stringify({ path }) })
