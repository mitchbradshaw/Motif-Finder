/* Jobs fixtures (frames jobs-1 … jobs-4, spec §7c, P24). Canon ids, titles and statuses come from
 * fixtures/canon.ts (JOBS, REVIEW_QUEUES, RECORDINGS, LOCAL_LIMITS); everything the frames add on top of the
 * canon (local jobs, queue counts, today's finished rows, run stages, checks, scripts, the j-0212 manifest)
 * lives here. Demo data only — pages read it through api/jobs.ts, never directly. Invented rows are listed in
 * webui/pages/fog/jobs.md. */
import { JOBS, LOCAL_LIMITS, RECORDINGS, REVIEW_QUEUES, TEMPLATES, WINDOW_SET } from './canon'

const canon = (id: string) => {
  const j = JOBS.find(x => x.id === id)
  if (!j) throw new Error(`canon job ${id} is missing from fixtures/canon.ts`)
  return j
}
const queue = (id: string) => {
  const q = REVIEW_QUEUES.find(x => x.id === id)
  if (!q) throw new Error(`canon review queue ${id} is missing from fixtures/canon.ts`)
  return q
}
const M2 = RECORDINGS.find(r => r.key === 'M2_aug_fs1')!
const M3 = RECORDINGS.find(r => r.key === 'M3_jul')!

export type Workspace = 'Analyse' | 'Discovery' | 'Models' | 'Library' | 'Review' | 'Explore'
export const WORKSPACE_ICON: Record<Workspace, 'branch' | 'target' | 'layers' | 'library' | 'checklist' | 'wave'> = {
  Analyse: 'branch', Discovery: 'target', Models: 'layers', Library: 'library', Review: 'checklist', Explore: 'wave',
}

/* ------------------------------------------------------------------ paused runs (§7c.2) */
export type StageState = 'done' | 'cached' | 'cluster' | 'waits'
export interface RunStage { n: number; name: string; state: StageState; lines: [string, string] }
export type CheckState = 'pass' | 'fail' | 'warn' | 'pending'
export interface ResultCheck { key: string; label: string; detail: string; state: CheckState }
export type ResultState = 'waiting' | 'arrived'
export interface PausedRun {
  id: string; workspace: 'Analyse' | 'Discovery'; kindLabel: string; template: string; version?: number
  recording: string; recordingKey: string; channels: string[]; channelsLabel: string; durationH: number; started: string
  stageCount: number; pausedAt: number; stageName: string; stages: RunStage[]
  clusterJob: string | null; where: string; since: string; lookedAgo: string
  defaultResult: ResultState
  result: { root: string; path: string; shortPath: string; size: string; foundAt: string; m: string; recipe: string }
  checks: ResultCheck[]
  timeline: { t: string; label: string; tone: 'grey' | 'amber' | 'green' }[]
  continueNote: string; remaining: string; localEstimate: string; limit: string
  openIn: { label: string; route: string }
}

const R0431 = canon('r-0431'), A0098 = canon('a-0098'), J0217 = canon('j-0217')

export const PAUSED_RUNS: PausedRun[] = [
  {
    id: R0431.id, workspace: 'Discovery', kindLabel: 'Discovery run', template: R0431.title, version: 3,
    recording: M2.label, recordingKey: M2.key, channels: ['CH2_A1', 'CH3_A2', 'CH4_A2'], channelsLabel: 'CH2_A1–CH4_A2', durationH: M2.duration_h, started: '14 Sep 08:02',
    stageCount: 4, pausedAt: 3, stageName: 'Matrix profile',
    stages: [
      { n: 1, name: 'Source', state: 'done', lines: ['3 channels · 45.2 h', 'read 08:02'] },
      { n: 2, name: 'Bandpass filter', state: 'cached', lines: ['0.005 – 0.1 Hz', '12 s locally'] },
      { n: 3, name: 'Matrix profile', state: 'cluster', lines: [`m = 120 s · ~6 h locally, over the ${LOCAL_LIMITS.discovery} limit`, `sent to the cluster as ${J0217.id}`] },
      { n: 4, name: 'Threshold to spans', state: 'waits', lines: ['runs locally after stage 3', '~40 s'] },
    ],
    clusterJob: J0217.id, where: 'hpc-1 · cpu-array', since: '2 h', lookedAgo: '1 min ago', defaultResult: 'waiting',
    result: { root: './PROFILES', path: './PROFILES/M2_aug_fs1_CH2-4_1Hz_m120_9b24e1f0.npz', shortPath: './PROFILES/…CH2-4_m120_9b24e1f0.npz', size: '1.9 GB', foundAt: '14:31', m: '120 s', recipe: '9b24e1f0' },
    checks: [
      { key: 'place', label: 'in the place the run expects', detail: 'named by the convention in Storage', state: 'pass' },
      { key: 'recipe', label: "produced by this run's script", detail: 'recipe hash 9b24e1 matches', state: 'pass' },
      { key: 'channels', label: 'one profile per channel', detail: 'CH2_A1 · CH3_A2 · CH4_A2', state: 'pass' },
      { key: 'length', label: 'length matches the signal', detail: '162,600 samples each (45.2 h at 1 Hz, less m)', state: 'pass' },
      { key: 'finite', label: 'values finite', detail: 'no NaN or Inf', state: 'pass' },
      { key: 'nulls', label: 'null draws included', detail: '200 circular shifts', state: 'pass' },
    ],
    timeline: [
      { t: '08:02', label: 'started', tone: 'grey' },
      { t: '08:05', label: 'paused · SLURM script created', tone: 'amber' },
      { t: '08:20', label: 'marked submitted', tone: 'grey' },
      { t: '11:40', label: 'marked running', tone: 'grey' },
      { t: '14:31', label: 'result found in ./PROFILES', tone: 'green' },
    ],
    continueNote: `Continue stores this file as stage 3's artifact, marks ${J0217.id} finished, and runs stage 4 locally (~40 s).`,
    remaining: '~40 s', localEstimate: '~6 h', limit: LOCAL_LIMITS.discovery,
    openIn: { label: 'Open in Discovery', route: 'discovery/runs' },
  },
  {
    id: A0098.id, workspace: 'Analyse', kindLabel: 'Analyse chain', template: A0098.title,
    recording: M2.label, recordingKey: M2.key, channels: ['CH4_A2'], channelsLabel: 'CH4_A2', durationH: M2.duration_h, started: '13 Sep 23:10',
    stageCount: 5, pausedAt: 2, stageName: 'Matrix profile',
    stages: [
      { n: 1, name: 'Source', state: 'done', lines: ['CH4_A2 · 721 h', 'read 23:10'] },
      { n: 2, name: 'Matrix profile', state: 'cluster', lines: [`m = 600 s · ~6.4 h locally, over the ${LOCAL_LIMITS.analyse} limit`, 'SLURM script run by hand on hpc-1'] },
      { n: 3, name: 'Symbolic encoding', state: 'waits', lines: ['SAX · 8 symbols', '~50 s'] },
      { n: 4, name: 'Threshold to spans', state: 'waits', lines: ['cut discords above 2.5 σ', '~40 s'] },
      { n: 5, name: 'Compare SAX vs MP', state: 'waits', lines: ['span overlap, IoU ≥ 0.5', '~20 s'] },
    ],
    clusterJob: null, where: 'hpc-1 · cpu-array', since: '13 h', lookedAgo: '13 h ago', defaultResult: 'arrived',
    result: { root: './PROFILES', path: './PROFILES/M2_aug_fs1_CH4_1Hz_m600_a7f39c2e.npz', shortPath: './PROFILES/…CH4_m600_a7f39c2e.npz', size: '0.6 GB', foundAt: '00:52', m: '600 s', recipe: 'a7f39c2e' },
    checks: [
      { key: 'place', label: 'in the place the run expects', detail: 'named by the convention in Storage', state: 'pass' },
      { key: 'recipe', label: "produced by this run's script", detail: 'recipe hash a7f39c matches', state: 'pass' },
      { key: 'channels', label: 'one profile per channel', detail: 'CH4_A2', state: 'pass' },
      { key: 'length', label: 'length matches the signal', detail: '2,595,001 samples (721 h at 1 Hz, less m)', state: 'pass' },
      { key: 'finite', label: 'values finite', detail: 'no NaN or Inf', state: 'pass' },
      { key: 'nulls', label: 'null draws included', detail: '200 circular shifts', state: 'pass' },
    ],
    timeline: [
      { t: '23:10', label: 'started', tone: 'grey' },
      { t: '23:11', label: 'paused · SLURM script created', tone: 'amber' },
      { t: '23:30', label: 'script run by hand', tone: 'grey' },
      { t: '00:52', label: 'result found in ./PROFILES', tone: 'green' },
    ],
    continueNote: "Continue stores this file as stage 2's artifact and runs stages 3–5 locally (~2 min).",
    remaining: '~2 min', localEstimate: '~6.4 h', limit: LOCAL_LIMITS.analyse,
    openIn: { label: 'Open in Analyse', route: 'analyse/chain?template=sax_vs_mp' },
  },
]

/* ------------------------------------------------------------------ cluster jobs (§7c.4) */
export type ClusterStatus = 'queue' | 'submitted' | 'running' | 'finished' | 'failed' | 'cancelled'
export interface ClusterJob {
  id: string; title: string; sub: string; workspace: Workspace; forRun?: string
  profile: string; status: ClusterStatus
  marks: { created: string; submitted?: string; running?: string; finished?: string; failed?: string }
  runningForH?: number; estimateH: number; estimateLabel: string
  clusterJobId: string; returnFrom: string; returnTo: string; script: string; scriptName: string
  openIn: { label: string; route: string }; importedAt?: string; error?: string; isNew?: boolean
}
const J0212 = canon('j-0212'), J0214 = canon('j-0214'), J0209 = canon('j-0209')

export const PROFILES = ['hpc-1 · cpu-array', 'hpc-1 · gpu-single', 'hpc-1 · gpu-long', 'hpc-1 · bigmem']

const script = (lines: string[]) => lines.join('\n')
export const CLUSTER_JOBS: ClusterJob[] = [
  {
    id: J0217.id, title: 'matrix profile · 3 channels', sub: `for ${J0217.for} · Discovery`, workspace: 'Discovery', forRun: J0217.for,
    profile: 'hpc-1 · cpu-array', status: 'running', marks: { created: '08:05', submitted: '08:20', running: J0217.since! }, runningForH: 2, estimateH: 6,
    estimateLabel: '6 h · calibrated 10 Sep', clusterJobId: '4418311', returnFrom: `/scratch/$USER/cnn/out/${J0217.id}`, returnTo: './PROFILES', scriptName: `${J0217.id}.sh`,
    script: script([
      '#SBATCH --account=a_myco --partition=cpu_long --array=0-2',
      '#SBATCH --cpus-per-task=16 --mem=64G --time=12:00:00',
      'module load python/3.11 && conda activate cnn',
      'CH=(CH2_A1 CH3_A2 CH4_A2)',
      `python -m pipeline.stage --run ${J0217.for} --stage 3 --recipe 9b24…e1f0 --channel \${CH[$SLURM_ARRAY_TASK_ID]} --out /scratch/$USER/cnn/out/${J0217.id}`,
    ]),
    openIn: { label: `Open ${J0217.for} in Jobs`, route: `jobs/run/${J0217.for}` },
  },
  {
    id: J0212.id, title: 'cnn_windows_v3 · paired arms', sub: 'Models training', workspace: 'Models',
    profile: 'hpc-1 · gpu-single', status: 'finished', marks: { created: '12 Sep 17:02', submitted: '12 Sep 17:10', running: '12 Sep 17:40', finished: '13 Sep 21:40' }, estimateH: 24,
    estimateLabel: '24 h · calibrated 12 Sep', clusterJobId: '4417620', returnFrom: `/scratch/$USER/cnn/out/${J0212.id}`, returnTo: './cluster_out', scriptName: `${J0212.id}.sh`, importedAt: '13 Sep 21:40',
    script: script([
      '#SBATCH --account=a_myco --partition=gpu_long --nodes=1',
      '#SBATCH --gres=gpu:1 --cpus-per-task=8 --mem=32G --time=36:00:00',
      'module load cuda/12.1 && conda activate cnn',
      `python -m pipeline.train --job ${J0212.id} --recipe 5c1e…a07b --arms manual,cluster --window-set ${WINDOW_SET.id} --out /scratch/$USER/cnn/out/${J0212.id}`,
    ]),
    openIn: { label: 'Open in Models › Results', route: 'models/results' },
  },
  {
    id: J0214.id, title: 'cnn_windows_v3 · seed repeats', sub: 'Models training', workspace: 'Models',
    profile: 'hpc-1 · gpu-single', status: 'running', marks: { created: '10:50', submitted: '10:58', running: J0214.since! }, runningForH: 3.3, estimateH: 1,
    estimateLabel: '1 h · calibrated 12 Sep', clusterJobId: '4418093', returnFrom: `/scratch/$USER/cnn/out/${J0214.id}`, returnTo: './cluster_out', scriptName: `${J0214.id}.sh`,
    script: script([
      '#SBATCH --account=a_myco --partition=gpu_short --nodes=1',
      '#SBATCH --gres=gpu:1 --cpus-per-task=8 --mem=32G --time=04:00:00',
      'module load cuda/12.1 && conda activate cnn',
      `python -m pipeline.train --job ${J0214.id} --recipe 5c1e...a07b --seeds 3 --out /scratch/$USER/cnn/out/${J0214.id}`,
    ]),
    openIn: { label: 'Open in Models › Results', route: 'models/results' },
  },
  {
    id: J0209.id, title: `matrix profile · ${M3.label} CH1–CH8`, sub: 'for r-0402 · Discovery', workspace: 'Discovery', forRun: 'r-0402',
    profile: 'hpc-1 · cpu-array', status: 'failed', marks: { created: '13 Sep 18:20', submitted: '13 Sep 18:31', running: '13 Sep 19:02', failed: '09:12' }, estimateH: 9,
    estimateLabel: '9 h · calibrated 10 Sep', clusterJobId: '4417902', returnFrom: `/scratch/$USER/cnn/out/${J0209.id}`, returnTo: './PROFILES', scriptName: `${J0209.id}.sh`,
    error: 'marked failed by hand · the cluster log said the array ran out of memory on CH6',
    script: script([
      '#SBATCH --account=a_myco --partition=cpu_long --array=0-7',
      '#SBATCH --cpus-per-task=16 --mem=32G --time=12:00:00',
      'module load python/3.11 && conda activate cnn',
      'CH=(CH1 CH2 CH3 CH4 CH5 CH6 CH7 CH8)',
      `python -m pipeline.stage --run r-0402 --stage 3 --recipe 41d0…c3a9 --channel \${CH[$SLURM_ARRAY_TASK_ID]} --out /scratch/$USER/cnn/out/${J0209.id}`,
    ]),
    openIn: { label: 'Open in Discovery', route: 'discovery/runs' },
  },
]

/* ------------------------------------------------------------------ running locally */
export interface LocalJob { id: string; title: string; sub: string; workspace: Workspace; progress: number; left: string; route: string }
export const LOCAL_JOBS: LocalJob[] = [
  { id: 'a-0101', title: 'image encoding · CH4_A2', sub: 'Analyse chain · stage 4/6', workspace: 'Analyse', progress: 0.62, left: '4 min left', route: 'analyse/chain' },
  { id: 'l-0009', title: 'regroup g-09 · frequency content', sub: 'Library grouping', workspace: 'Library', progress: 0.3, left: '7 min left', route: 'library/grouping' },
]

/* ------------------------------------------------------------------ review queues */
export interface QueueJob { id: string; title: string; sub: string; left: number; total: number; pace?: string; eta: string; blind: boolean; idle: boolean; forWhat?: string }
const q12 = queue('q-12'), q15 = queue('q-15'), q18 = queue('q-18'), q19 = queue('q-19')
export const QUEUE_JOBS: QueueJob[] = [
  { id: q12.id, title: `Discovery · ${q12.source}`, sub: 'discovery run', left: 942, total: 1284, pace: '~1.9 s each', eta: '~30 min', blind: false, idle: false },
  { id: q15.id, title: `Seed search · ${q15.source.replace('seed search ', '')} E-0102`, sub: 'seed search', left: 57, total: 118, eta: '~3 min', blind: false, idle: false },
  { id: q18.id, title: 'Training windows', sub: 'training windows', left: 18400, total: 20000, eta: '~31 h', blind: !!q18.blind, idle: true },
  { id: q19.id, title: 'Model verification', sub: 'model verification', left: q19.left!, total: q19.total!, eta: '~1 min', blind: !!q19.blind, idle: false, forWhat: 'for registration' },
]

/* ------------------------------------------------------------------ finished and cancelled today */
export interface FinishedJob { id: string; title: string; sub: string; workspace: Workspace; where: string; status: 'finished' | 'cancelled'; at: string; took: string; route: string }
const [t0, t1, t2] = TEMPLATES.named
export const FINISHED_TODAY: FinishedJob[] = [
  { id: 'a-0099', title: `${t0} · ${M2.label} CH4_A2`, sub: 'Analyse chain · 4 stages', workspace: 'Analyse', where: 'this machine', status: 'finished', at: '10:12', took: '48 s', route: 'analyse/chain' },
  { id: 'a-0100', title: `banded_sax_lp · ${M3.label} CH3`, sub: 'Analyse chain · 5 stages', workspace: 'Analyse', where: 'this machine', status: 'finished', at: '10:41', took: '2 min', route: 'analyse/chain' },
  { id: 'r-0429', title: `${t1} · ${M2.label} CH1_A1–CH16_D2`, sub: 'Discovery run · 16 channels', workspace: 'Discovery', where: 'this machine', status: 'finished', at: '09:30', took: '14 min', route: 'discovery/runs' },
  { id: 'r-0430', title: `${t2} · L_LM_Jul26_J CH1–CH5`, sub: 'Discovery run · 5 channels', workspace: 'Discovery', where: 'this machine', status: 'finished', at: '11:02', took: '6 min', route: 'discovery/runs' },
  { id: 'l-0008', title: 'regroup g-08 · sequences', sub: 'Library grouping', workspace: 'Library', where: 'this machine', status: 'finished', at: '08:47', took: '9 min', route: 'library/atlas?unit=sequences' },
  { id: 'q-11', title: 'Seed search · r-0409 E-0102', sub: 'Review queue · 64 judged', workspace: 'Review', where: 'Review', status: 'finished', at: '09:58', took: '22 min', route: 'review/queue/q-15' },
  { id: 'a-0096', title: 'spike_shape_v1 · F-03 slope interrogation', sub: 'Analyse chain · cancelled at stage 2', workspace: 'Analyse', where: 'this machine', status: 'cancelled', at: '08:40', took: '1 min', route: 'analyse/interrogation' },
]

/* ------------------------------------------------------------------ manifest inbox (§7c.4, §9.6) */
export interface Manifest { jobId: string; title: string; at: string; contains: string[]; checks: string[]; imported: boolean; resultsRoute: string; resultsLabel: string }
export const INBOX = {
  watching: './cluster_out', every: '5 min', lastLooked: '2 min ago',
  manifests: [
    { jobId: J0212.id, title: 'cnn_windows_v3 · paired arms', at: '13 Sep 21:40', imported: true, resultsRoute: 'models/results', resultsLabel: 'Models › Results',
      contains: ['model per arm · manual, cluster · RF baseline', 'random-forest baseline', 'nulls · 200 RF shuffles, 5 model shuffles', `window set ${WINDOW_SET.id}`, 'metrics and test predictions'],
      checks: ['recipe hash matches the launch', 'every arm and null present', 'test windows identical across arms', 'no test window in training'] },
  ] as Manifest[],
  /** What arrives when the inbox looks again while j-0214 is still marked running (demo). */
  pending: { jobId: J0214.id, title: 'cnn_windows_v3 · seed repeats', at: 'just now', imported: false, resultsRoute: 'models/results', resultsLabel: 'Models › Results',
    contains: ['model per seed · 3 seeds, manual arm', 'nulls · 5 model shuffles per seed', `window set ${WINDOW_SET.id}`, 'metrics and test predictions'],
    checks: ['recipe hash matches the launch', 'every arm and null present', 'test windows identical across arms', 'no test window in training'] } as Manifest,
}

/* ------------------------------------------------------------------ upload results and continue (§7c.3) */
export type UploadFileKey = 'mismatch' | 'ok-no-nulls' | 'ok' | 'held-out'
export interface UploadFile {
  key: UploadFileKey; name: string; size: string; from: string
  checks: ResultCheck[]; refusal?: { title: string; body: string; newRun?: string }
}
const baseChecks = (overrides: Partial<Record<string, Partial<ResultCheck>>>): ResultCheck[] => ([
  { key: 'readable', label: 'readable matrix-profile file', detail: 'npz · profile, index, meta', state: 'pass' },
  { key: 'channels', label: 'one profile per channel', detail: 'CH2_A1 · CH3_A2 · CH4_A2', state: 'pass' },
  { key: 'length', label: 'length matches the signal', detail: '2,595,481 samples per channel (721 h at 1 Hz, less m)', state: 'pass' },
  { key: 'finite', label: 'values finite', detail: 'no NaN or Inf', state: 'pass' },
  { key: 'params', label: "made with this run's parameters", detail: 'm = 120 s · recipe 9b24e1f0', state: 'pass' },
  { key: 'nulls', label: 'null draws', detail: '200 circular shifts', state: 'pass' },
] as ResultCheck[]).map(c => ({ ...c, ...(overrides[c.key] ?? {}) }))

export const UPLOAD_FILES: UploadFile[] = [
  { key: 'mismatch', name: 'mp_M2aug_CH2-4.npz', size: '1.9 GB', from: 'from Downloads · copied off hpc-1 by hand',
    checks: baseChecks({ params: { state: 'fail', detail: 'file says m = 60 s · recipe 77ab10c3 — the run expects m = 120 s · 9b24e1f0' }, nulls: { state: 'warn', detail: "not in the file — stage 3's null would run separately" } }),
    refusal: { title: 'This file cannot continue r-0431', body: 'It was made with different parameters. Continuing with it would give the run a recipe it did not follow.', newRun: 'm = 60 s' } },
  { key: 'ok-no-nulls', name: 'mp_M2aug_CH2-4_m120.npz', size: '1.8 GB', from: 'from Downloads · copied off hpc-1 by hand',
    checks: baseChecks({ nulls: { state: 'warn', detail: "not in the file — stage 3's null would run separately" } }) },
  { key: 'ok', name: 'mp_M2aug_CH2-4_m120_nulls.npz', size: '2.1 GB', from: 'from /mnt/hpc-1/scratch · copied by hand', checks: baseChecks({}) },
  { key: 'held-out', name: 'mp_M4aug_CH2-4_m120.npz', size: '0.8 GB', from: 'from Downloads · copied off hpc-1 by hand',
    checks: baseChecks({ readable: { detail: 'npz · profile, index, meta · source M4_aug_concat_fs1.mat' }, channels: { state: 'fail', detail: 'channels are from M4_aug, which is held out (D6)' }, length: { state: 'fail', detail: '1,080,000 samples per channel — M4_aug is 300 h, the run is on 721 h' }, finite: { state: 'pending', detail: 'not checked — the file is refused' }, params: { state: 'pending', detail: 'not checked — the file is refused' }, nulls: { state: 'pending', detail: 'not checked' } }),
    refusal: { title: 'This file cannot continue r-0431', body: 'It was computed on M4_aug, the held-out recording (D6). Held-out data is refused everywhere until the final evaluation.' } },
]
export const UPLOAD_NULL_NOTE = { title: 'When a file passes but has no null draws', body: `its null (200 circular shifts) runs next — ~25 min, over the ${LOCAL_LIMITS.discovery} limit, so it goes to the cluster.` }
