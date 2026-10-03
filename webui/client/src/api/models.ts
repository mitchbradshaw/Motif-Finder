/* Models reads (spec §7b). Every read resolves fixture data through the seam and says `source: 'demo'`; a later ticket
 * swaps a body for a bridge call without touching the pages. Writes (register, retire, launch) stay in the in-memory
 * demo store on the pages themselves. */
import { demo, live, type Sourced } from './seam'
import { ApiError } from '../api'
import {
  ARM_RESULTS, AGREEMENT, CLUSTER_MAP, COMPARE_MODELS, COMPARE_NULL_BAND, LAUNCH_SETUP, PAIRED_DIFF, PAIRED_DIST, PER_CHANNEL, PER_CLASS_DELTA,
  REGISTRY_MODELS, RESULT_JOBS, disagreementAt,
  type ArmKey, type ArmResult, type CompareModel, type Disagreement, type DisagreementFilter, type LaunchSetup, type RegistryModel, type ResultsJob,
} from '../fixtures/models'

export type {
  ArmKey, ArmResult, CompareModel, Disagreement, DisagreementFilter, LaunchSetup, RegistryModel, ResultsJob,
} from '../fixtures/models'
export type { ModelClass, RegistryStatus, SourceChannelRow, TrainingTemplate, WindowSetRow, Verification, RegistryCheck, UsedBy, SignOff, CalTarget, Suggestion, PerClassRow, CalibrationRow } from '../fixtures/models'
export {
  MODEL_CLASSES, CLASS_SHORT, CLASS_COLOUR, BASE_SPLIT_COUNTS, FRAME_SPLIT_BLOCKS, ESTIMATE_MODEL, TEST_WARN_BELOW, NEXT_JOB_NUMBER, DEFAULT_CHANNELS,
  FILTER_COUNTS, FILTER_FRAME_INDEX, REGISTRY_NOTE, CAL_TARGETS, suggestionFor,
} from '../fixtures/models'

/** Launch: training templates (terminal type Model), source channels, saved window sets, training jobs, held-out lock. */
export const getLaunchSetup = (): Promise<Sourced<LaunchSetup>> => demo(LAUNCH_SETUP)

/** The training jobs a Results page can open. */
export const getResultJobs = (): Promise<Sourced<ResultsJob[]>> => demo(RESULT_JOBS)

export interface JobResults { job: ResultsJob; arms: Record<ArmKey, ArmResult> | null }
/** Results of one training job. A failed job rejects (the page renders the error loudly); a running one has no arms yet. */
export function getJobResults(jobId: string): Promise<Sourced<JobResults>> {
  const job = RESULT_JOBS.find(j => j.id === jobId)
  if (!job) return new Promise((_, reject) => window.setTimeout(() => reject(new Error(`no training job called ${jobId} · Models knows ${RESULT_JOBS.map(j => j.id).join(', ')}`)), 60))
  if (job.status === 'failed') return new Promise((_, reject) => window.setTimeout(() => reject(new Error(job.error ?? `${jobId} failed`)), 60))
  return demo({ job, arms: job.status === 'finished' ? ARM_RESULTS : null })
}

export interface CompareData {
  models: CompareModel[]; nullBand: [number, number]; paired: typeof PAIRED_DIFF; pairedDist: number[]; perClassDelta: typeof PER_CLASS_DELTA
  clusterMap: typeof CLUSTER_MAP; agreement: typeof AGREEMENT; perChannel: typeof PER_CHANNEL
}
/** Compare: the models that can be picked and the paired j-0212 comparison (manual vs cluster labels). */
export const getCompare = (): Promise<Sourced<CompareData>> => demo({
  models: COMPARE_MODELS, nullBand: COMPARE_NULL_BAND, paired: PAIRED_DIFF, pairedDist: PAIRED_DIST, perClassDelta: PER_CLASS_DELTA,
  clusterMap: CLUSTER_MAP, agreement: AGREEMENT, perChannel: PER_CHANNEL,
})

/** One window of the step-through (1-based index within the filter). */
export const getDisagreement = (filter: DisagreementFilter, i: number): Promise<Sourced<Disagreement>> => demo(disagreementAt(filter, i), 30)

/** Registry: every model with its checks, verification progress, sign-off and the templates using it. */
export const getRegistry = (): Promise<Sourced<RegistryModel[]>> => demo(REGISTRY_MODELS)

/* ======================================================================================================
 * fixup-ab — the LIVE reads and writes of Models › Launch, Results and Compare, over the core's paired
 * training job (`Working/training/`, routes in `webui/server/training_routes.py`). Registry above stays a
 * fixture page: its registration gate needs blind window-verdict queues that do not exist yet.
 * ====================================================================================================== */
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
const pst = <T,>(path: string, body: unknown) => rq<T>(path, { method: 'POST', body: JSON.stringify(body) })

export type PairedArm = 'A' | 'B'
export type ExamKey = 'i_later_block' | 'ii_unseen_channels' | 'iii_held_out'
export const EXAM_TITLES: Record<ExamKey, string> = {
  i_later_block: 'exam (i) · a later time block of the training channels',
  ii_unseen_channels: 'exam (ii) · channels never trained on',
  iii_held_out: 'exam (iii) · the held-out recording',
}
export const CLASS_NAMES = ['not_interesting', 'interesting'] as const

export interface TrainingTemplateLive {
  name: string; id?: number; description: string; steps: string[]; on_label_grid: boolean; length: number | null; grid: number | null
  stages: string[]; reason: string | null; n_estimators: number
}
export interface ChannelSource {
  recording_id: number; channel: number; name: string; hours: number; fs: number; verdicts: number; interesting: number; not_interesting: number; artifact: number
}
export interface RecordingSource { source_file: string; name: string; channels: ChannelSource[] }
export interface RoleCounts { interesting: number; not_interesting: number; n: number }
export interface SetMember { id: number; window_set_id: number; recording_id: number; channel: number; role: 'train' | 'exam'; n_windows: number; counts: Record<string, any> }
export interface PooledSetRow {
  id: number; name: string; version: number; path: string; n_windows: number; window_length: number; stride: number; gap: number
  recipe_hash: string; created_at: string; labels_source: string
  split: Record<string, any>; spacing: Record<string, boolean>; coverage: { by_role: Record<string, RoleCounts>; dropped_for_gap: number; dropped_for_overlap: number; stages: string[]; [k: string]: any }
  members: SetMember[]; runs: PairedRunRow[]
}
export interface PairedRunRow {
  run_id: number; status: string; name: string | null; started_at: string; finished_at: string | null; duration_s: number | null; config_hash: string
  window_set: { id?: number; name: string; version?: number; key: string }; k: number; error: string | null
  macro_f1: { A: number; B: number; delta: number } | null; results_path: string | null
}
export interface ModelsSetup {
  templates: TrainingTemplateLive[]; recordings: RecordingSource[]; recordings_without_verdicts: string[]
  held_out: { file: string; name: string; locked: boolean; where: string; reason: string }
  window_sets: PooledSetRow[]; runs: PairedRunRow[]
  defaults: { split: { rule: string; n_blocks: number; test_frac: number; validation_frac: number; gap_windows: number }; stages: string[]; length: number; grid: number
    rf_shuffles: number; full_shuffles: number; bootstrap_n: number; block_hours: number; n_estimators: number; linkage: string; test_warn_below: number }
  local_limit_s: number; hpc_note: string; note: string
}
export const getModelsSetup = () => live(rq<ModelsSetup>('/api/models/setup'))

export interface PooledSetBody {
  name: string; source_file: string; channels: number[]; exam_channels: number[]; length: number; grid: number; stages: string[]
  split: { n_blocks: number; test_frac: number; validation_frac: number; gap_windows: number }; template?: string; notes?: string
}
export const savePooledWindowSet = (body: PooledSetBody) => pst<import('../api').JobRow>('/api/models/windowsets', body)

export interface CutRow {
  k: number; silhouette: number | null; sizes: Record<string, number>; small_clusters: number[]; effective_k: number
  contingency: number[][]; translation: Record<string, string>; purity: { cluster: number; n: number; purity: number | null; majority: string | null; impure: boolean }[]
}
export interface Proposal { linkage: string; n_windows_clustered: number; features: string[]; by_k: CutRow[]; suggested_k: number | null; small_below: number; suggestion_rule: string; note: string; window_set_id: number; key: string }
export const proposeCut = (window_set_id: number, k_min = 2, k_max = 8, linkage = 'ward') => pst<Proposal>('/api/models/propose', { window_set_id, k_min, k_max, linkage })

export interface RecipeBody {
  window_set_id: number; k: number | null; translation?: Record<string, string> | null; linkage?: string; n_estimators?: number
  rf_shuffles?: number; full_shuffles?: number; bootstrap_n?: number; block_hours?: number; reference?: boolean
}
export interface CheckRow { name: string; ok: boolean; level: 'pass' | 'warn' | 'error'; detail: string }
export interface Estimate { seconds: number; parts: Record<string, number>; n_fits: number; seconds_per_fit: number; where: 'local' | 'slurm'; local_limit_s: number }
export interface ChecksResult { checks: CheckRow[]; estimate: Estimate; recipe: Record<string, any>; recipe_hash: string; by_role: Record<string, RoleCounts>; ok: boolean }
export const checkPairedJob = (body: RecipeBody) => pst<ChecksResult>('/api/models/checks', body)
export const trainPairedJob = (body: RecipeBody) => pst<import('../api').JobRow>('/api/models/train', body)
export interface SlurmResult { script: string; script_path: string; recipe_path: string; sbatch_command: string; slurm_time: string; warnings: string[]; note: string; estimate: Estimate }
export const slurmPairedJob = (body: RecipeBody) => pst<SlurmResult>('/api/models/slurm', body)

export interface ClassScore { precision: number; recall: number; f1: number; n: number; n_predicted: number; f1_ci?: [number | null, number | null] }
export interface ArmScore {
  n: number; macro_f1: number; macro_f1_ci: [number | null, number | null]; balanced_accuracy: number; accuracy: number
  confusion: number[][]; confusion_labels: string[]; per_class: Record<string, ClassScore>
  null: { method: string; draws: number[]; p: number | null; mean: number | null; q95: number | null; full_model: string }
}
export interface PerChannelRow { channel: number; name?: string; n: number; interesting: number; one_class: boolean; A: number | null; B: number | null; accuracy_A: number | null; accuracy_B: number | null }
export interface ExamResult {
  status: 'scored' | 'empty' | 'locked'; n_windows: number; reason?: string; class_counts?: Record<string, number>; n_units?: number; unit?: string
  arms?: Record<PairedArm, ArmScore>
  paired?: { delta_f1: number; delta_f1_ci: [number | null, number | null]; delta_draws_sample: number[]; mcnemar: { b: number; c: number; p: number; method: string }
    agreement: { both_right: number; only_a: number; only_b: number; both_wrong: number }; per_class_delta: Record<string, { delta: number; ci: [number | null, number | null] }> }
  per_channel?: PerChannelRow[]
}
export interface ReferenceRow {
  name: string; status: string; reason?: string; file?: string; trained_differently?: string
  exams?: Record<string, { status: string; macro_f1?: number; balanced_accuracy?: number; n?: number; reason?: string }>
}
export interface Calibration {
  n: number; reason?: string; n_positive?: number; ece?: number; target_precision?: number
  bins?: { lo: number; hi: number; n: number; mean_p: number; fraction_positive: number }[]
  suggested?: { threshold: number; precision: number; recall: number } | null; suggested_reason?: string | null
}
export interface PairedResults {
  recipe: Record<string, any>; recipe_hash: string; run_id: number
  window_set: { name: string; id: number; version: number; key: string; n_windows: number; by_role: Record<string, RoleCounts>; source_file: string
    channels: number[]; exam_channels: number[]; length: number; grid: number; stages: string[]; split: Record<string, any>; per_channel: Record<string, any>[] }
  checks: CheckRow[]; features: { kept: string[]; removed: Record<string, string[]> }
  cluster: { k: number; linkage: string; n_windows: number; sizes: Record<string, number>; contingency: number[][]; contingency_columns: string[]
    purity: CutRow['purity']; impure_below: number; silhouette: number | null; translation: Record<string, string>; translation_source: string }
  training: Record<PairedArm, { label_source: string; n_train: number; classifier: Record<string, any>; n_classes: number; class_counts: Record<string, number>
    feature_importance: { feature: string; importance: number }[]; model_path: string | null }>
  exams: Record<ExamKey, ExamResult>; calibration: Record<PairedArm, Calibration>
  yardstick_b: { status: string; note: string }; reference: ReferenceRow[]; notes: string[]; timings: Record<string, number>
}
export interface PairedRun { run_id: number; status: string; name: string | null; config_hash: string; recipe: Record<string, any>; started_at: string
  finished_at: string | null; duration_s: number | null; error: string | null; results_path: string | null; results: PairedResults | null }
export const getPairedRuns = () => live(rq<{ runs: PairedRunRow[]; jobs: import('../api').JobRow[] }>('/api/models/runs'))
export const getPairedRun = (id: number) => live(rq<PairedRun>(`/api/models/runs/${id}`))

export interface CompareExam {
  status: string; reason?: string; n_windows?: number; class_counts?: Record<string, number>; n_units?: number; unit?: string
  arms?: Record<PairedArm, { macro_f1: number; macro_f1_ci: [number | null, number | null]; balanced_accuracy: number; null_band: [number, number]; null_p: number | null; per_class: Record<string, ClassScore> }>
  delta_f1?: number; delta_f1_ci?: [number | null, number | null]; delta_draws_sample?: number[]
  mcnemar?: { b: number; c: number; p: number; method: string }; agreement?: { both_right: number; only_a: number; only_b: number; both_wrong: number }
  per_class_delta?: Record<string, { delta: number; ci: [number | null, number | null] }>; per_channel?: PerChannelRow[]
}
export interface PairedCompare {
  run_id: number; recipe_hash: string; attributable: boolean; differs: { name: string; a: string; b: string; same: boolean }[]
  exams: Record<ExamKey, CompareExam>; cluster: PairedResults['cluster']; notes: string[]; reference: ReferenceRow[]; yardstick_b: { status: string; note: string }
}
export const getPairedCompare = (id: number) => live(rq<PairedCompare>(`/api/models/runs/${id}/compare`))
export type DisagreeFilter = 'only_a' | 'only_b' | 'both_wrong'
export interface DisagreementLive {
  run_id: number; exam: string; filter: DisagreeFilter; i: number; n: number; counts: Record<DisagreeFilter, number>
  window: { recording_id: number; channel: number; channel_name: string; start: number; end: number; fs: number }
  human: string; a: string; b: string; trace: number[]; unit: string | null
}
export const getPairedDisagreement = (id: number, filter: DisagreeFilter, i: number, exam: ExamKey = 'i_later_block') =>
  rq<DisagreementLive>(`/api/models/runs/${id}/disagreements?filter=${filter}&i=${i}&exam=${exam}`)
