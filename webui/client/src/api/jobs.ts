/* Jobs reads — all live (fixup-jobs; the fixture reads that fed the page's demo half are gone with it).
 *
 *  · the bridge's own job table (`GET /api/jobs`): what is in progress here, what finished, what failed;
 *  · every job the site wrote for the cluster (`GET /api/hpc/cluster`, `webui/server/jobs_routes.py`): the job
 *    directories (CNN, Ward), Discovery's seed searches on the cluster, the flat recipe scripts — one list, each
 *    row with its state and how its results come back;
 *  · the Manifest inbox (`POST /api/hpc/inbox/import`, `GET /api/hpc/inbox`) and the seed-result import by path
 *    (`POST /api/hpc/seed/import`), both through the core's own import functions.
 *  The review queues come from `api/review.ts` (`getQueues`). */
import { live, type Sourced } from './seam'
import { listJobs, type JobRow, type JobStep } from '../api'

export type Workspace = 'Analyse' | 'Discovery' | 'Models' | 'Library' | 'Review' | 'Explore'
export const WORKSPACE_ICON: Record<Workspace, 'branch' | 'target' | 'layers' | 'library' | 'checklist' | 'wave'> = {
  Analyse: 'branch', Discovery: 'target', Models: 'layers', Library: 'library', Review: 'checklist', Explore: 'wave',
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { 'content-type': 'application/json' }, ...init })
  if (!r.ok) {
    let body: unknown = null
    try { body = await r.json() } catch { /* not json */ }
    const detail = (body as { detail?: unknown } | null)?.detail
    const msg = typeof detail === 'string' ? detail
      : detail && typeof detail === 'object' && typeof (detail as { message?: unknown }).message === 'string' ? (detail as { message: string }).message
        : r.statusText
    throw new Error(`${r.status} ${msg}`)
  }
  return r.json() as Promise<T>
}

/* ------------------------------------------------------------------ the bridge's own jobs */
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

export const isActive = (j: LiveJob) => j.status === 'running' || j.status === 'queued'

/** The bridge's real local jobs, newest first. */
export const getLocalJobs = (limit = 60): Promise<Sourced<LiveJob[]>> => live(listJobs(limit).then(rows => rows.map(toLiveJob)))

/* ------------------------------------------------------------------ the cluster */
export interface CopyItem { what: string; path: string; bytes: number; note?: string }
export type ClusterState = 'written' | 'partial' | 'returned' | 'importing' | 'imported' | 'refused' | 'failed' | 'unreadable'
export type ClusterSource = 'job_dir' | 'seed' | 'script'
export type ImportHow = 'inbox' | 'seed' | null
export interface ImportAttempt {
  job_id: number; job_dir: string | null; recipe_hash: string | null; outcome: 'imported' | 'refused' | 'failed' | 'importing' | string
  status: string; message: string; error_type: string | null; traceback: string | null; started_at: number | string | null; finished_at: number | string | null
}
/** One job the site wrote for the cluster, whatever wrote it (`GET /api/hpc/cluster`). */
export interface ClusterJob {
  source: ClusterSource; name: string; kind: string | null; kind_label: string | null; workspace: Workspace
  /** seed rows: the run row's label, key and session */
  label: string | null; run_key: string | null; session: string | null; run_status: string | null
  job_dir: string | null; job_repo: string | null; recipe_hash: string | null; recipe_ok: boolean | null
  written_at: string | null; smoke: boolean; model: string | null; pool_key: string | null; n?: number | null
  scripts: { name: string; path: string; repo: string }[]; sbatch_command: string | null; copy: CopyItem[]; total_bytes: number
  returned: { status: string; recipe_hash: string | null; finished_at: string | null } | null
  imported: { run_id: number | null; name: string | null; at?: string } | null; error: string | null
  state: ClusterState; reason: string | null; last_attempt: ImportAttempt | null
  open: { label: string; route: string; note?: string } | null
  /** how its results come back: the Manifest inbox (a job directory), the seed import (a result file), or not through the site */
  import_how: ImportHow; import_path: string | null; import_note: string | null; result_path: string | null
  progress: { channels_done: number; channels: number | null } | null; estimate_s: number | null; draws: number | null
}
export interface ClusterCounts { written: number; partial: number; returned: number; importing: number; imported: number; refused: number; failed: number; unreadable: number; to_import: number; waiting: number; total: number }
export interface ClusterList { jobs: ClusterJob[]; roots: string[]; mode: string; counts: ClusterCounts; note: string }
/** Every job the site wrote for the cluster, newest first, with counts by state. */
export const getClusterJobs = (): Promise<Sourced<ClusterList>> => live(req<ClusterList>('/api/hpc/cluster'))

/** The job directories alone (`GET /api/hpc/exported`); the page reads the unified list, this stays for callers that want only those. */
export interface ExportedList { jobs: ClusterJob[]; roots: string[]; mode: string; note: string }
export const getExportedJobs = (): Promise<Sourced<ExportedList>> => live(req<ExportedList>('/api/hpc/exported'))

/** The Manifest inbox's import attempts, newest first. */
export const getInboxAttempts = (): Promise<Sourced<{ attempts: ImportAttempt[]; roots: string[] }>> => live(req('/api/hpc/inbox'))
/** Hand the inbox a returned job directory: a local `import` job (the CLI's import function) — follow it with `getJob`. */
export const importReturnedJob = (path: string) =>
  req<{ job_id: number; status: string }>('/api/hpc/inbox/import', { method: 'POST', body: JSON.stringify({ path }) })

export interface SeedImportAck { run_key: string; job_id: number | null; label: string; candidates?: number; nullDraws?: number; note?: string }
/** Import a seed job's result file by path, through the Seed page's own import; a refusal is the thrown error's message. */
export const importSeedResult = (path: string) =>
  req<SeedImportAck>('/api/hpc/seed/import', { method: 'POST', body: JSON.stringify({ path }) })

export const wsOf = (w: string | null | undefined): Workspace => (w && w in WORKSPACE_ICON ? (w as Workspace) : 'Analyse')
