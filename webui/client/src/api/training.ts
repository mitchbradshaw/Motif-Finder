/* Analyse › Training reads. Every read returns Sourced<T> through `demo(FIXTURE)`; a later ticket swaps a
 * body for a bridge call without touching a component (see api/seam.ts). Nothing here touches the bridge. */
import { demo } from './seam'
import {
  BOUNDARY_WINDOWS, CHAIN, CHAIN_HUMAN, CLUSTER, CLUSTER_CLASSES, CONTINGENCY, CRITERIA, DENDROGRAM, ENCODE,
  ENCODINGS, ESTIMATES, FEATURE_GROUPS, HISTORY_RUNS, HUMAN_SOURCE, HUMAN_TICKS, IMPORT_TEMPLATES, K_RANGE,
  K_SWEEP, LABEL_SOURCES, MATRIX, MODEL_STAGES, NULL_SPEC, OCCUPANCY, PRE_TRAIN_CHECKS, RANDOM_SPLIT_WARNING,
  SIGNAL, SIGNAL_Y, SOURCE_CHOICES, STABILITY, TRAINING_PARAMS, TRIAL, WINDOWS, WINDOW_CHECKS,
  type TrainingBlock,
} from '../fixtures/training'

export type { TrainingBlock }
export type SourceKind = 'signal' | 'human-windows'

/** The chain in hand. P15: with the WindowSet source the sliding-windows stage is *absent*, not greyed. */
export const chainFor = (source: SourceKind): TrainingBlock[] => (source === 'human-windows' ? CHAIN_HUMAN : CHAIN)

/** The block route index (1-based) for a block id under the source in hand — the stages renumber under 0b. */
export function stageIndex(source: SourceKind, id: string): number | null {
  return chainFor(source).find(b => b.id === id)?.index ?? null
}

export interface TrainingChain {
  chain: TrainingBlock[]
  signal: { values: number[]; yDomain: [number, number] }
  windows: typeof WINDOWS
  occupancy: typeof OCCUPANCY
  encodings: typeof ENCODINGS
  human: typeof HUMAN_SOURCE
  humanTicks: boolean[]
  sources: typeof SOURCE_CHOICES
  history: typeof HISTORY_RUNS
  imports: typeof IMPORT_TEMPLATES
  nullSpec: typeof NULL_SPEC
  estimate: string
}
/** The training chain page (frames training-0, training-0b). */
export const getTrainingChain = (source: SourceKind) =>
  demo<TrainingChain>({
    chain: chainFor(source),
    signal: { values: SIGNAL, yDomain: SIGNAL_Y },
    windows: WINDOWS,
    occupancy: OCCUPANCY,
    encodings: ENCODINGS,
    human: HUMAN_SOURCE,
    humanTicks: HUMAN_TICKS,
    sources: SOURCE_CHOICES,
    history: HISTORY_RUNS,
    imports: IMPORT_TEMPLATES,
    nullSpec: NULL_SPEC,
    estimate: ESTIMATES.chain,
  })

export interface WindowsBlock {
  chain: TrainingBlock[]
  windows: typeof WINDOWS
  boundary: typeof BOUNDARY_WINDOWS
  checks: typeof WINDOW_CHECKS
  randomWarning: string
  signal: { values: number[]; yDomain: [number, number] }
}
/** 01 Sliding windows — `Signal → WindowSet` (§6.8, §6.9, P12). */
export const getWindowsBlock = () =>
  demo<WindowsBlock>({
    chain: CHAIN, windows: WINDOWS, boundary: BOUNDARY_WINDOWS, checks: WINDOW_CHECKS,
    randomWarning: RANDOM_SPLIT_WARNING, signal: { values: SIGNAL, yDomain: SIGNAL_Y },
  })

export interface MatrixBlock {
  chain: TrainingBlock[]
  groups: typeof FEATURE_GROUPS
  matrix: typeof MATRIX
  signal: { values: number[]; yDomain: [number, number] }
}
/** 02 Window matrix — `WindowSet → WindowSet + features` (P12: label-derived groups off by default). */
export const getMatrixBlock = (source: SourceKind = 'signal') =>
  demo<MatrixBlock>({ chain: chainFor(source), groups: FEATURE_GROUPS, matrix: MATRIX, signal: { values: SIGNAL, yDomain: SIGNAL_Y } })

export interface ClusterBlock {
  chain: TrainingBlock[]
  classes: typeof CLUSTER_CLASSES
  cluster: typeof CLUSTER
  criteria: typeof CRITERIA
  dendrogram: typeof DENDROGRAM
  occupancy: typeof OCCUPANCY
  contingency: typeof CONTINGENCY
  stability: typeof STABILITY
  kRange: number[]
  kSweep: typeof K_SWEEP
}
/** 03 Cluster — `WindowSet → Grouping` (B4: the criterion is the finding unless it is fixed first). */
export const getClusterBlock = (source: SourceKind = 'signal') =>
  demo<ClusterBlock>({
    chain: chainFor(source), classes: CLUSTER_CLASSES, cluster: CLUSTER, criteria: CRITERIA, dendrogram: DENDROGRAM,
    occupancy: OCCUPANCY, contingency: CONTINGENCY, stability: STABILITY, kRange: K_RANGE, kSweep: K_SWEEP,
  })

export interface EncodeBlock {
  chain: TrainingBlock[]
  encode: typeof ENCODE
  encodings: typeof ENCODINGS
  classes: typeof CLUSTER_CLASSES
}
/** 04 Encode — `WindowSet → Encoding` (§6.8). */
export const getEncodeBlock = (source: SourceKind = 'signal') =>
  demo<EncodeBlock>({ chain: chainFor(source), encode: ENCODE, encodings: ENCODINGS, classes: CLUSTER_CLASSES })

export interface ModelBlock {
  chain: TrainingBlock[]
  stages: typeof MODEL_STAGES
  labelSources: typeof LABEL_SOURCES
  params: typeof TRAINING_PARAMS
  checks: typeof PRE_TRAIN_CHECKS
  trial: typeof TRIAL
}
/** 05 Model — `Encoding + labels → Model` (P11: the training itself happens in Models). */
export const getModelBlock = (source: SourceKind = 'signal') =>
  demo<ModelBlock>({ chain: chainFor(source), stages: MODEL_STAGES, labelSources: LABEL_SOURCES, params: TRAINING_PARAMS, checks: PRE_TRAIN_CHECKS, trial: TRIAL })
