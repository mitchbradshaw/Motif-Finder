/* Jobs reads (frames jobs-1 … jobs-4, spec §7c). Every read resolves fixture data through the seam and says
 * `source: 'demo'`; a later ticket swaps each body for a bridge call without touching the pages. Writes (marks,
 * continue, cancel, place, import) stay in the in-memory store — see jobs/store.ts. */
import { demo, type Sourced } from './seam'
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
