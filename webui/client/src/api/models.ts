/* Models reads (spec §7b). Every read resolves fixture data through the seam and says `source: 'demo'`; a later ticket
 * swaps a body for a bridge call without touching the pages. Writes (register, retire, launch) stay in the in-memory
 * demo store on the pages themselves. */
import { demo, type Sourced } from './seam'
import {
  ARM_RESULTS, AGREEMENT, CLUSTER_MAP, COMPARE_MODELS, COMPARE_NULL_BAND, LAUNCH_SETUP, PAIRED_DIFF, PER_CHANNEL, PER_CLASS_DELTA,
  REGISTRY_MODELS, RESULT_JOBS, disagreementAt,
  type ArmKey, type ArmResult, type CompareModel, type Disagreement, type DisagreementFilter, type LaunchSetup, type RegistryModel, type ResultsJob,
} from '../fixtures/models'

export type {
  ArmKey, ArmResult, CompareModel, Disagreement, DisagreementFilter, LaunchSetup, RegistryModel, ResultsJob,
} from '../fixtures/models'
export type { ModelClass, RegistryStatus, SourceChannelRow, TrainingTemplate, WindowSetRow, Verification, RegistryCheck, UsedBy, SignOff } from '../fixtures/models'
export {
  MODEL_CLASSES, CLASS_SHORT, CLASS_COLOUR, BASE_SPLIT_COUNTS, FRAME_SPLIT_BLOCKS, ESTIMATE_MODEL, TEST_WARN_BELOW, NEXT_JOB_NUMBER, DEFAULT_CHANNELS,
  FILTER_COUNTS, FILTER_FRAME_INDEX, REGISTRY_NOTE,
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
  models: CompareModel[]; nullBand: [number, number]; paired: typeof PAIRED_DIFF; perClassDelta: typeof PER_CLASS_DELTA
  clusterMap: typeof CLUSTER_MAP; agreement: typeof AGREEMENT; perChannel: typeof PER_CHANNEL
}
/** Compare: the models that can be picked and the paired j-0212 comparison (manual vs cluster labels). */
export const getCompare = (): Promise<Sourced<CompareData>> => demo({
  models: COMPARE_MODELS, nullBand: COMPARE_NULL_BAND, paired: PAIRED_DIFF, perClassDelta: PER_CLASS_DELTA, clusterMap: CLUSTER_MAP, agreement: AGREEMENT, perChannel: PER_CHANNEL,
})

/** One window of the step-through (1-based index within the filter). */
export const getDisagreement = (filter: DisagreementFilter, i: number): Promise<Sourced<Disagreement>> => demo(disagreementAt(filter, i), 30)

/** Registry: every model with its checks, verification progress, sign-off and the templates using it. */
export const getRegistry = (): Promise<Sourced<RegistryModel[]>> => demo(REGISTRY_MODELS)
