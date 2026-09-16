/* Models fixtures (spec §7b, frames models-1 … models-5). Demo data only — nothing here is read from the database.
 * Shared facts (recordings, classes, window set, models, jobs, test block) come from the §0 canon. */
import { CLASSES, JOBS, MODELS, RECORDINGS, WINDOW_SET, seeded, syntheticTrace } from './canon'

/* ------------------------------------------------------------------ classes ------------------------------------------------------------------ */
/** Display order used on every Models frame (a display order, not a key change — inventory conflict 3). */
export const MODEL_CLASSES = ['spike-train', 'plateau', 'burst', 'slow-drift'] as const
export type ModelClass = typeof MODEL_CLASSES[number]
export const CLASS_SHORT: Record<ModelClass, string> = { 'spike-train': 's-tr', plateau: 'plat', burst: 'burst', 'slow-drift': 's-dr' }
export const CLASS_COLOUR: Record<ModelClass, string> = Object.fromEntries(MODEL_CLASSES.map(c => [c, CLASSES.find(k => k.name === c)!.colour])) as Record<ModelClass, string>

/* ------------------------------------------------------------------ launch ------------------------------------------------------------------ */
export interface TemplateStage { id: string; index: number; label: string; glyph: string; signature: string }
export interface TrainingTemplate {
  name: string; version: number; source: 'Signal' | 'WindowSet'; classes: number; multiClass: boolean; classifier: string
  stages: TemplateStage[]; clusterStage: string; matrixStage: string; windowsStage?: string; sessionDefault: string
}
export const TRAINING_TEMPLATES: TrainingTemplate[] = [
  {
    name: 'cnn_windows_v3', version: 3, source: 'Signal', classes: 4, multiClass: true, classifier: 'EfficientNet-B0 · 224 px GASF+GADF+RP',
    sessionDefault: 'train_cnn_M2aug_sep14', clusterStage: '03 Cluster', matrixStage: '02 Window matrix', windowsStage: '01 Sliding windows',
    stages: [
      { id: 'src', index: 0, label: 'Source', glyph: 'source', signature: 'Signal' },
      { id: 's1', index: 1, label: 'Sliding windows', glyph: 'sliding_windows', signature: 'Signal → WindowSet' },
      { id: 's2', index: 2, label: 'Window matrix', glyph: 'window_matrix', signature: 'WindowSet → WindowSet + features' },
      { id: 's3', index: 3, label: 'Cluster', glyph: 'cluster', signature: 'WindowSet → Grouping' },
      { id: 's4', index: 4, label: 'Image encode', glyph: 'image_encode', signature: 'WindowSet → Encoding' },
      { id: 's5', index: 5, label: 'CNN classifier', glyph: 'classifier', signature: 'Encoding → Model' },
    ],
  },
  {
    name: 'cnn_windowset_v1', version: 1, source: 'WindowSet', classes: 4, multiClass: true, classifier: 'EfficientNet-B0 · 224 px GASF+GADF+RP',
    sessionDefault: 'train_cnnws_M2aug_sep14', clusterStage: '02 Cluster', matrixStage: '01 Window matrix',
    stages: [
      { id: 'src', index: 0, label: 'Source', glyph: 'source', signature: 'WindowSet' },
      { id: 's1', index: 1, label: 'Window matrix', glyph: 'window_matrix', signature: 'WindowSet → WindowSet + features' },
      { id: 's2', index: 2, label: 'Cluster', glyph: 'cluster', signature: 'WindowSet → Grouping' },
      { id: 's3', index: 3, label: 'Image encode', glyph: 'image_encode', signature: 'WindowSet → Encoding' },
      { id: 's4', index: 4, label: 'CNN classifier', glyph: 'classifier', signature: 'Encoding → Model' },
    ],
  },
]

const M2 = RECORDINGS.find(r => r.key === 'M2_aug_fs1')!
const LLM = RECORDINGS.find(r => r.key === 'L_LM_Jul26_J')!
export interface SourceChannelRow {
  key: string; recording: string; recordingKey: string; channel: string; hours: number; windows: number | null
  humanVerdicts: number; classesSeen: [number, number] | null; flag?: string; disabledReason?: string
  /** per-class verdicts in MODEL_CLASSES order (fixture maths for the count table) */
  perClass: [number, number, number, number]
}
export const SOURCE_CHANNELS: SourceChannelRow[] = [
  { key: 'M2_aug_fs1:CH2_A1', recording: M2.source_file.replace('.mat', ''), recordingKey: M2.key, channel: 'CH2_A1', hours: M2.duration_h, windows: 5220, humanVerdicts: 640, classesSeen: [4, 4], perClass: [180, 110, 60, 290] },
  { key: 'M2_aug_fs1:CH4_A2', recording: M2.source_file.replace('.mat', ''), recordingKey: M2.key, channel: 'CH4_A2', hours: M2.duration_h, windows: 5220, humanVerdicts: 1080, classesSeen: [4, 4], perClass: [290, 270, 128, 392] },
  { key: 'M2_aug_fs1:CH7_B2', recording: M2.source_file.replace('.mat', ''), recordingKey: M2.key, channel: 'CH7_B2', hours: M2.duration_h, windows: 5220, humanVerdicts: 420, classesSeen: [3, 4], flag: 'no plateau verdicts', perClass: [121, 0, 60, 239] },
  // canon (§0) wins over the frame's "92 h": L_LM_Jul26_J is 22.4 h
  { key: 'L_LM_Jul26_J:CH1', recording: LLM.label, recordingKey: LLM.key, channel: 'CH1', hours: LLM.duration_h, windows: null, humanVerdicts: 0, classesSeen: null, perClass: [0, 0, 0, 0], disabledReason: '10 Hz (inferred) · the template’s sliding windows expect 1 Hz' },
]
export const DEFAULT_CHANNELS = ['CH2_A1', 'CH4_A2', 'CH7_B2']

export interface WindowSetRow {
  id: string; version: number; channels: string[] | 'all'; channelsLabel: string; windows: number; split: 'blocked' | 'none' | 'no split'
  verdictsNow: number; verdictsAtSave: number; badge: 'train-safe' | 'not train-safe' | 'no split · B7'; windowS: number
  savedFrom: string; disabledReason?: string; recordingKey: string; clusterWindows: number
}
export const WINDOW_SETS: WindowSetRow[] = [
  { id: WINDOW_SET.id, version: WINDOW_SET.version, channels: WINDOW_SET.channels, channelsLabel: '3 channels', windows: WINDOW_SET.windows, split: 'blocked', verdictsNow: WINDOW_SET.labelled_every_arm, verdictsAtSave: 1980, badge: 'train-safe', windowS: WINDOW_SET.length_s, savedFrom: 'saved from 01 Sliding windows of cnn_windows_v3 · recipe a7f39c2e', recordingKey: 'M2_aug_fs1', clusterWindows: WINDOW_SET.windows },
  { id: 'ws_M3jul_8ch_300s', version: 2, channels: ['CH1', 'CH2', 'CH3', 'CH4', 'CH5', 'CH6', 'CH7', 'CH8'], channelsLabel: '8 channels', windows: 22400, split: 'blocked', verdictsNow: 610, verdictsAtSave: 610, badge: 'train-safe', windowS: 300, savedFrom: 'saved from 01 Sliding windows of cnn_windows_v2 · recipe 5d10e7b4', recordingKey: 'M3_jul', clusterWindows: 22400 },
  { id: 'ws_verif_cnn_cluster_v1', version: 1, channels: ['CH4_A2'], channelsLabel: 'CH4_A2', windows: 40, split: 'none', verdictsNow: 33, verdictsAtSave: 0, badge: 'not train-safe', windowS: 600, savedFrom: 'saved from the cnn_cluster_v1 verification sample', disabledReason: 'not train-safe · spacing check failed', recordingKey: 'M2_aug_fs1', clusterWindows: 40 },
  { id: 'ws_humanlabel_frame0b', version: 1, channels: 'all', channelsLabel: 'all channels', windows: 4812, split: 'no split', verdictsNow: 4812, verdictsAtSave: 4812, badge: 'no split · B7', windowS: 600, savedFrom: 'saved from human-annotated windows (frame 0b)', disabledReason: 'no split (B7) · a split filter is not built yet', recordingKey: 'M2_aug_fs1', clusterWindows: 4812 },
]

/** Base class counts per split for the canon 3-channel launch (train 1,490 · val 218 · test 432 = 2,140). */
export const BASE_SPLIT_COUNTS = {
  train: [412, 268, 190, 620],
  val: [61, 38, 27, 92],
  test: [118, 74, 31, 209],
} as const
export const TEST_WARN_BELOW = 50

/** Frame split-strip positions (1-based block numbers) for 10 blocks at test 20 % / validation 10 %. */
export const FRAME_SPLIT_BLOCKS: Record<string, { test: number[]; val: number[] }> = {
  CH2_A1: { test: [4, 9], val: [7] },
  CH4_A2: { test: [5, 9], val: [8] },
  CH7_B2: { test: [6, 8], val: [7] },
}

export const ESTIMATE_MODEL = {
  /** hours per label arm for the canon 3-channel launch; RF once; the 5 full-model shuffles */
  perArmH: 1.6, rfH: 0.1, modelNullsH: 2.3, hpcRatio: 0.25, diskGbPer3ch: 3.9, localLimitH: 2,
}
export const TRAINING_JOB_IDS = JOBS.filter(j => j.id === 'j-0212' || j.id === 'j-0214').map(j => j.id)
export const NEXT_JOB_NUMBER = 218

export interface LaunchSetup {
  templates: TrainingTemplate[]; channels: SourceChannelRow[]; windowSets: WindowSetRow[]
  trainingJobs: string[]; heldOut: { key: string; label: string; reason: string }
}
export const LAUNCH_SETUP: LaunchSetup = {
  templates: TRAINING_TEMPLATES, channels: SOURCE_CHANNELS, windowSets: WINDOW_SETS, trainingJobs: TRAINING_JOB_IDS,
  heldOut: { key: 'M4_aug', label: 'M4_aug', reason: 'M4_aug is held out and locked (D6). It is refused in every workspace, Models included. Unlocking needs the recording name typed and is logged.' },
}

/* ------------------------------------------------------------------ results ------------------------------------------------------------------ */
export type ArmKey = 'a' | 'b' | 'rf'
export interface PerClassRow { cls: ModelClass; precision: number; recall: number; f1: number; n: number }
export interface CalibrationRow { cls: ModelClass; curve: [number, number][]; ece: number }
export interface ArmResult {
  arm: ArmKey; label: string; short: string; macroF1: number; ci: [number, number]; balancedAcc: number; rfF1: number
  nullF1: number; nullP: string; shuffles: number[]; testWindows: number; nullDist: number[]
  confusion: number[][]; perClass: PerClassRow[]; calibration: CalibrationRow[] | null
  curves: { train: [number, number][]; val: [number, number][] } | null; earlyStop: number | null
  checks: { label: string; state: 'pass' | 'warn' | 'fail' | 'pending'; to?: string }[] | null
  registryId: string | null
}

function nullDistribution(seed: number, mean: number, sd: number, n = 200): number[] {
  const r = seeded(seed)
  return Array.from({ length: n }, () => {
    const u = Math.max(1e-6, r()), v = r()
    return +(mean + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)).toFixed(3)
  })
}
function calCurve(seed: number, bend: number): [number, number][] {
  const r = seeded(seed)
  return Array.from({ length: 10 }, (_, i) => {
    const s = (i + 0.5) / 10
    return [+s.toFixed(3), +Math.min(1, Math.max(0, s + bend * Math.sin(s * Math.PI) + (r() - 0.5) * 0.06)).toFixed(3)] as [number, number]
  })
}
function lossCurves(seed: number, stop: number): { train: [number, number][]; val: [number, number][] } {
  const r = seeded(seed)
  const train: [number, number][] = [], val: [number, number][] = []
  for (let e = 1; e <= 30; e++) {
    const t = 0.34 + 1.05 * Math.exp(-(e - 1) / 7)
    train.push([e, +(t + (r() - 0.5) * 0.004).toFixed(4)])
    val.push([e, +(t + 0.06 + 0.0016 * Math.max(0, e - stop) ** 1.35 + (r() - 0.5) * 0.004).toFixed(4)])
  }
  return { train, val }
}
const confusionFrom = (rows: number[][]) => rows
function perClassFrom(conf: number[][]): PerClassRow[] {
  return MODEL_CLASSES.map((cls, i) => {
    const n = conf[i].reduce((a, b) => a + b, 0)
    const predicted = conf.reduce((a, row) => a + row[i], 0)
    const precision = conf[i][i] / Math.max(1, predicted), recall = conf[i][i] / Math.max(1, n)
    return { cls, precision: +precision.toFixed(2), recall: +recall.toFixed(2), f1: +((2 * precision * recall) / Math.max(1e-9, precision + recall)).toFixed(2), n }
  })
}

// frame 3 confusion (rows = label), rows sum to the class test counts 118 / 74 / 31 / 209 = 432 (canon test block)
const CONF_A = confusionFrom([[92, 9, 5, 12], [9, 49, 1, 15], [5, 1, 16, 9], [8, 15, 6, 180]])
const CONF_B = confusionFrom([[80, 8, 9, 21], [7, 40, 2, 25], [6, 2, 13, 10], [12, 22, 9, 166]])
const CONF_RF = confusionFrom([[70, 14, 9, 25], [13, 36, 3, 22], [8, 4, 9, 10], [16, 24, 8, 161]])

// the frame prints A's per-class row; kept verbatim so the page matches frame 3 exactly
const PER_CLASS_A: PerClassRow[] = [
  { cls: 'spike-train', precision: 0.81, recall: 0.78, f1: 0.79, n: 118 },
  { cls: 'plateau', precision: 0.66, recall: 0.66, f1: 0.66, n: 74 },
  { cls: 'burst', precision: 0.57, recall: 0.52, f1: 0.54, n: 31 },
  { cls: 'slow-drift', precision: 0.83, recall: 0.86, f1: 0.85, n: 209 },
]

export const ARM_RESULTS: Record<ArmKey, ArmResult> = {
  a: {
    arm: 'a', label: 'A · manual labels', short: 'arm A', macroF1: 0.71, ci: [0.66, 0.75], balancedAcc: 0.70, rfF1: 0.58, nullF1: 0.26, nullP: 'p < 0.005',
    shuffles: [0.24, 0.26, 0.27, 0.28, 0.29], testWindows: MODELS.test_block_windows, nullDist: nullDistribution(11, 0.26, 0.035),
    confusion: CONF_A, perClass: PER_CLASS_A,
    calibration: [
      { cls: 'spike-train', curve: calCurve(21, 0.03), ece: 0.04 },
      { cls: 'plateau', curve: calCurve(22, 0.05), ece: 0.06 },
      { cls: 'burst', curve: calCurve(23, -0.12), ece: 0.11 },
      { cls: 'slow-drift', curve: calCurve(24, 0.02), ece: 0.03 },
    ],
    curves: lossCurves(31, 21), earlyStop: 21,
    checks: [
      { label: 'beats label-shuffle null · p < 0.005 (needs < 0.01)', state: 'pass' },
      { label: 'beats RF baseline · ΔF1 0.13, CI 0.07–0.19 excludes 0', state: 'pass' },
      { label: 'test windows never seen in training', state: 'pass' },
      { label: 'calibration ECE ≤ 0.10 on 3 classes', state: 'pass' },
      { label: 'burst ECE 0.11 · 31 test windows (≥ 50 wanted)', state: 'warn' },
      { label: `human verification · ${MODELS.verification.judged} of ${MODELS.verification.of} judged (Registry)`, state: 'pending', to: 'models/registry/cnn_windows_v3.manual' },
    ],
    registryId: 'cnn_windows_v3.manual',
  },
  b: {
    arm: 'b', label: 'B · cluster labels', short: 'arm B', macroF1: 0.62, ci: [0.57, 0.67], balancedAcc: 0.61, rfF1: 0.51, nullF1: 0.26, nullP: 'p < 0.005',
    shuffles: [0.23, 0.25, 0.26, 0.27, 0.28], testWindows: MODELS.test_block_windows, nullDist: nullDistribution(12, 0.26, 0.036),
    confusion: CONF_B, perClass: perClassFrom(CONF_B),
    calibration: [
      { cls: 'spike-train', curve: calCurve(41, 0.08), ece: 0.09 },
      { cls: 'plateau', curve: calCurve(42, 0.13), ece: 0.14 },
      { cls: 'burst', curve: calCurve(43, -0.15), ece: 0.16 },
      { cls: 'slow-drift', curve: calCurve(44, 0.04), ece: 0.05 },
    ],
    curves: lossCurves(51, 18), earlyStop: 18,
    checks: [
      { label: 'beats label-shuffle null · p < 0.005 (needs < 0.01)', state: 'pass' },
      { label: 'beats RF baseline · ΔF1 0.11, CI 0.05–0.17 excludes 0', state: 'pass' },
      { label: 'test windows never seen in training', state: 'pass' },
      { label: 'calibration ECE ≤ 0.10 on 2 classes · plateau 0.14, burst 0.16', state: 'fail' },
      { label: 'burst · 31 test windows (≥ 50 wanted)', state: 'warn' },
      { label: 'human verification · not started (Registry)', state: 'pending', to: 'models/registry/cnn_windows_v3.cluster' },
    ],
    registryId: 'cnn_windows_v3.cluster',
  },
  rf: {
    arm: 'rf', label: 'RF baseline', short: 'RF baseline', macroF1: 0.58, ci: [0.53, 0.63], balancedAcc: 0.57, rfF1: 0.58, nullF1: 0.26, nullP: 'p < 0.005',
    shuffles: [], testWindows: MODELS.test_block_windows, nullDist: nullDistribution(11, 0.26, 0.035),
    confusion: CONF_RF, perClass: perClassFrom(CONF_RF), calibration: null, curves: null, earlyStop: null, checks: null, registryId: null,
  },
}

/* Calibration: the suggested threshold per class at a target precision (frame 3 prints target precision 0.8 and the
 * four suggested values; 0.7 / 0.9 move deterministically around them). The RF baseline has no calibration. */
export const CAL_TARGETS = ['0.7', '0.8', '0.9'] as const
export type CalTarget = typeof CAL_TARGETS[number]
export interface Suggestion { thr: number; precision: number; recall: number }
const SUGGEST_AT_08: Record<ArmKey, Record<ModelClass, Suggestion> | null> = {
  a: {
    'spike-train': { thr: 0.62, precision: 0.80, recall: 0.66 },
    plateau: { thr: 0.55, precision: 0.78, recall: 0.61 },
    burst: { thr: 0.71, precision: 0.81, recall: 0.44 },
    'slow-drift': { thr: 0.40, precision: 0.82, recall: 0.88 },
  },
  b: {
    'spike-train': { thr: 0.66, precision: 0.79, recall: 0.58 },
    plateau: { thr: 0.61, precision: 0.77, recall: 0.49 },
    burst: { thr: 0.78, precision: 0.80, recall: 0.31 },
    'slow-drift': { thr: 0.44, precision: 0.81, recall: 0.80 },
  },
  rf: null,
}
const clamp01 = (v: number) => Math.min(0.99, Math.max(0.01, v))
export function suggestionFor(arm: ArmKey, cls: ModelClass, target: CalTarget): Suggestion | null {
  const base = SUGGEST_AT_08[arm]
  if (!base) return null
  const d = Number(target) - 0.8
  return {
    thr: +clamp01(base[cls].thr + d * 0.55).toFixed(2),
    precision: +clamp01(base[cls].precision + d * 0.95).toFixed(2),
    recall: +clamp01(base[cls].recall - d * 1.3).toFixed(2),
  }
}

export interface ResultsJob { id: string; title: string; status: 'finished' | 'running' | 'failed'; detail: string; session: string; template: string; error?: string; since?: string; overrun?: string }
export const RESULT_JOBS: ResultsJob[] = [
  { id: 'j-0212', title: 'cnn_windows_v3 paired arms', status: 'finished', detail: 'imported 13 Sep 21:40', session: 'train_cnn_M2aug_sep12', template: 'cnn_windows_v3' },
  { id: 'j-0214', title: 'cnn_windows_v3 seed repeats', status: 'running', detail: 'running on hpc-1 since 11:05 · 3.3× its 1 h estimate', session: 'train_cnn_M2aug_sep13_seeds', template: 'cnn_windows_v3', since: '11:05', overrun: '3.3×' },
  { id: 'j-0209', title: 'j-0209', status: 'failed', detail: 'failed', session: 'train_cnn_M2aug_sep10', template: 'cnn_windows_v2', error: 'j-0209 failed on the cluster and returned no manifest · nothing to import (Jobs › j-0209 has the log)' },
]

/* ------------------------------------------------------------------ compare ------------------------------------------------------------------ */
export interface CompareModel {
  id: string; label: string; short: string; template: string; windowSet: string; split: string; classifier: string
  labelSource: string; labelKind: 'manual' | 'cluster'; job: string; macroF1: number; ci: [number, number]; rfF1: number; rfCi: [number, number]
  group: string; testWindows: number
}
export const COMPARE_MODELS: CompareModel[] = [
  { id: 'cnn_windows_v3.manual', label: 'arm A · manual labels', short: 'manual', template: 'cnn_windows_v3', windowSet: 'ws_M2aug_3ch_600s', split: 'split + test block', classifier: 'classifier + options', labelSource: 'Review verdicts', labelKind: 'manual', job: 'j-0212', macroF1: 0.71, ci: [0.66, 0.75], rfF1: 0.58, rfCi: [0.53, 0.63], group: 'j-0212 · paired arms', testWindows: 432 },
  { id: 'cnn_windows_v3.cluster', label: 'arm B · cluster labels', short: 'cluster', template: 'cnn_windows_v3', windowSet: 'ws_M2aug_3ch_600s', split: 'split + test block', classifier: 'classifier + options', labelSource: '03 Cluster k=4', labelKind: 'cluster', job: 'j-0212', macroF1: 0.62, ci: [0.57, 0.67], rfF1: 0.51, rfCi: [0.46, 0.56], group: 'j-0212 · paired arms', testWindows: 432 },
  { id: 'cnn_windows_v2.manual', label: 'cnn_windows_v2 · manual · v2', short: 'v2 manual', template: 'cnn_windows_v2', windowSet: 'ws_M2aug_2ch_600s', split: 'split sep-08', classifier: 'classifier + options', labelSource: 'Review verdicts', labelKind: 'manual', job: 'j-0198', macroF1: 0.66, ci: [0.60, 0.71], rfF1: 0.55, rfCi: [0.49, 0.60], group: 'registered', testWindows: 301 },
  { id: 'cnn_cluster_v1', label: 'cnn_cluster_v1 · v1', short: 'cluster v1', template: 'cnn_cluster_v1', windowSet: 'ws_M2aug_3ch_600s', split: 'split sep-11', classifier: 'ResNet-18 · 128 px GASF', labelSource: '03 Cluster k=5', labelKind: 'cluster', job: 'j-0205', macroF1: 0.63, ci: [0.57, 0.68], rfF1: 0.50, rfCi: [0.44, 0.55], group: 'registered', testWindows: 388 },
]
export const COMPARE_NULL_BAND: [number, number] = [0.2, 0.32]
export const PAIRED_DIFF = { delta: 0.09, ci: [0.03, 0.15] as [number, number], mcnemarP: 0.04, sd: 0.031 }
/** The bootstrap resamples behind PAIRED_DIFF (400 draws over test blocks), drawn as the paired-difference density. */
export const PAIRED_DIST: number[] = nullDistribution(77, PAIRED_DIFF.delta, PAIRED_DIFF.sd, 400)
export const PER_CLASS_DELTA: { cls: ModelClass; d: number; ci: [number, number] }[] = [
  { cls: 'spike-train', d: 0.05, ci: [-0.02, 0.12] },
  { cls: 'plateau', d: 0.14, ci: [0.05, 0.23] },
  { cls: 'burst', d: 0.02, ci: [-0.11, 0.15] },
  { cls: 'slow-drift', d: 0.11, ci: [0.05, 0.17] },
]
export const CLUSTER_MAP = {
  clusters: ['c1', 'c2', 'c3', 'c4'],
  values: [[71, 9, 12, 8], [6, 58, 3, 33], [10, 2, 44, 44], [5, 12, 6, 77]],
  mapping: [
    { c: 'c1', cls: 'spike-train' as ModelClass, purity: 71 }, { c: 'c2', cls: 'plateau' as ModelClass, purity: 58 },
    { c: 'c3', cls: 'burst' as ModelClass, purity: 44, impure: 'c3 splits burst / slow-drift' }, { c: 'c4', cls: 'slow-drift' as ModelClass, purity: 77 },
  ],
}
export const AGREEMENT = { bothRight: 283, onlyA: 58, onlyB: 37, bothWrong: 54 }
export const PER_CHANNEL = [
  { channel: 'CH2_A1', windows: 128, a: 0.68, b: 0.61 },
  { channel: 'CH4_A2', windows: 209, a: 0.75, b: 0.66 },
  { channel: 'CH7_B2', windows: 95, a: 0.66, b: 0.55 },
]
export type DisagreementFilter = 'only-a' | 'only-b' | 'both-wrong'
export interface Disagreement {
  id: string; channel: string; hour: number; block: number; verdict: ModelClass
  a: { cls: ModelClass; score: number; thr: number }; b: { cls: ModelClass; cluster: string; score: number }
  bClusters: [string, number][]; note?: string; values: number[]
}
const THR: Record<ModelClass, number> = { 'spike-train': 0.62, plateau: 0.55, burst: 0.71, 'slow-drift': 0.40 }
const CLUSTER_OF: Record<ModelClass, string> = { 'spike-train': 'c1', plateau: 'c2', burst: 'c3', 'slow-drift': 'c4' }
export const FILTER_COUNTS: Record<DisagreementFilter, number> = { 'only-a': AGREEMENT.onlyA, 'only-b': AGREEMENT.onlyB, 'both-wrong': AGREEMENT.bothWrong }
export const FILTER_FRAME_INDEX: Record<DisagreementFilter, number> = { 'only-a': 7, 'only-b': 1, 'both-wrong': 12 }

/** Deterministic disagreement window `i` (1-based) of a filter. The two frame windows are pinned. */
export function disagreementAt(filter: DisagreementFilter, i: number): Disagreement {
  const chs = PER_CHANNEL.map(c => c.channel)
  if (filter === 'only-a' && i === 7) return {
    id: 'w-10482', channel: 'CH4_A2', hour: 192.40, block: 4, verdict: 'spike-train', a: { cls: 'spike-train', score: 0.81, thr: 0.62 }, b: { cls: 'slow-drift', cluster: 'c4', score: 0.64 },
    bClusters: [['c4', 0.64], ['c1', 0.29], ['c3', 0.05]], values: windowTrace(10482, 'spike-train'),
  }
  if (filter === 'both-wrong' && i === 12) return {
    id: 'w-11907', channel: 'CH7_B2', hour: 318.60, block: 7, verdict: 'plateau', a: { cls: 'burst', score: 0.58, thr: 0.71 }, b: { cls: 'slow-drift', cluster: 'c4', score: 0.52 },
    bClusters: [['c4', 0.52], ['c2', 0.41], ['c1', 0.07]], note: 'plateau is c2, second', values: windowTrace(11907, 'plateau'),
  }
  const r = seeded(filter.length * 1000 + i * 37)
  const verdict = MODEL_CLASSES[Math.floor(r() * 4)]
  const other = (not: ModelClass) => { const xs = MODEL_CLASSES.filter(c => c !== not); return xs[Math.floor(r() * xs.length)] }
  const aCls = filter === 'only-a' ? verdict : other(verdict)
  const bCls = filter === 'only-b' ? verdict : other(verdict)
  const bScore = +(0.45 + r() * 0.4).toFixed(2)
  const second = other(bCls)
  const idn = 10000 + Math.floor(r() * 3000)
  const block = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10][Math.floor(r() * 10)]
  return {
    id: `w-${idn}`, channel: chs[Math.floor(r() * chs.length)], hour: +((block - 1) * 72.1 + r() * 72).toFixed(2), block, verdict,
    a: { cls: aCls, score: +(0.4 + r() * 0.5).toFixed(2), thr: THR[aCls] }, b: { cls: bCls, cluster: CLUSTER_OF[bCls], score: bScore },
    bClusters: [[CLUSTER_OF[bCls], bScore], [CLUSTER_OF[second], +((1 - bScore) * 0.7).toFixed(2)], ['c' + (1 + Math.floor(r() * 4)), +((1 - bScore) * 0.2).toFixed(2)]],
    values: windowTrace(idn, verdict),
  }
}
function windowTrace(seed: number, cls: ModelClass): number[] {
  const shape = cls === 'plateau' ? 'plateau' : cls === 'spike-train' ? 'spike' : 'sharkfin'
  const events = cls === 'spike-train' ? [{ at: 140, depth: 0.22, width: 24, shape }, { at: 330, depth: 0.3, width: 26, shape }, { at: 470, depth: 0.18, width: 22, shape }]
    : cls === 'burst' ? [{ at: 250, depth: 0.28, width: 18, shape }, { at: 290, depth: 0.24, width: 18, shape }, { at: 320, depth: 0.2, width: 16, shape }]
      : cls === 'plateau' ? [{ at: 220, depth: 0.2, width: 160, shape }] : []
  return syntheticTrace({ n: 600, seed, baseline: -0.1, noise: 0.03, events: events as { at: number; depth: number; width: number; shape: 'sharkfin' | 'spike' | 'plateau' }[] }).map((v, k) => +(v + (cls === 'slow-drift' ? -0.0006 * k : 0)).toFixed(5))
}

/* ------------------------------------------------------------------ registry ------------------------------------------------------------------ */
export type RegistryStatus = 'candidate' | 'registered' | 'retired' | 'rejected'
export interface UsedBy { template: string; signature: string; discoveryRuns: number }
export interface RegistryCheck { label: string; detail: string; state: 'pass' | 'warn' | 'fail' }
export interface Verification { judged: number; of: number; agree: number; perClass: { cls: ModelClass; agree: number; judged: number }[]; note?: string }
export interface SignOff { actor: string; at: string; reason: string; name: string; version: string }
export interface RegistryModel {
  id: string; name: string; labelKind: 'manual' | 'cluster'; version: number; from: string; status: RegistryStatus; testF1: number
  usedBy: UsedBy[]; checks: RegistryCheck[]; verification: Verification; signoff?: SignOff; registeringAs?: string
  thresholds?: Record<ModelClass, number>; rejectedBecause?: string[]
}
const TPL_SIG = 'Signal → … → Model → Threshold → SpanSet'
const [REG_V2, REG_RF, REG_CLUSTER] = MODELS.registered
const [CAND_MANUAL] = MODELS.candidates
export const REGISTRY_MODELS: RegistryModel[] = [
  {
    id: 'cnn_windows_v3.manual', name: 'cnn_windows_v3 · manual', labelKind: 'manual', version: 1, from: CAND_MANUAL.from, status: 'candidate', testF1: 0.71, usedBy: [],
    registeringAs: CAND_MANUAL.registering_as,
    checks: [
      { label: 'beats label-shuffle null', detail: 'p < 0.005 · needs < 0.01', state: 'pass' },
      { label: 'beats RF baseline', detail: 'ΔF1 0.13 · CI 0.07–0.19', state: 'pass' },
      { label: 'test windows unseen in training', detail: 'verified from manifest', state: 'pass' },
      { label: 'calibration ECE ≤ 0.10', detail: '3 of 4 classes', state: 'pass' },
      { label: 'burst: ECE 0.11 · 31 test windows', detail: 'warning — reason required', state: 'warn' },
    ],
    verification: {
      judged: MODELS.verification.judged, of: MODELS.verification.of, agree: MODELS.verification.agree, note: 'burst disagreements: 3 predicted slow-drift',
      perClass: [{ cls: 'spike-train', agree: 9, judged: 10 }, { cls: 'plateau', agree: 7, judged: 8 }, { cls: 'burst', agree: 4, judged: 7 }, { cls: 'slow-drift', agree: 8, judged: 8 }],
    },
    thresholds: { 'spike-train': 0.62, plateau: 0.55, burst: 0.71, 'slow-drift': 0.40 },
  },
  {
    id: 'cnn_windows_v3.cluster', name: 'cnn_windows_v3 · cluster', labelKind: 'cluster', version: 1, from: 'j-0212', status: 'candidate', testF1: 0.62, usedBy: [],
    registeringAs: 'cnn_windows_v3_cluster',
    checks: [
      { label: 'beats label-shuffle null', detail: 'p < 0.005 · needs < 0.01', state: 'pass' },
      { label: 'beats RF baseline', detail: 'ΔF1 0.11 · CI 0.05–0.17', state: 'pass' },
      { label: 'test windows unseen in training', detail: 'verified from manifest', state: 'pass' },
      { label: 'calibration ECE ≤ 0.10', detail: '2 of 4 classes · plateau 0.14, burst 0.16', state: 'fail' },
      { label: 'burst: 31 test windows', detail: 'warning — reason required', state: 'warn' },
    ],
    verification: { judged: 0, of: 40, agree: 0, perClass: MODEL_CLASSES.map(cls => ({ cls, agree: 0, judged: 0 })) },
    thresholds: { 'spike-train': 0.66, plateau: 0.61, burst: 0.78, 'slow-drift': 0.44 },
  },
  {
    id: 'cnn_windows_v2.manual.v2', name: REG_V2.name, labelKind: 'manual', version: REG_V2.version, from: '30 Aug', status: 'registered', testF1: 0.66,
    usedBy: [{ template: REG_V2.used_by[0], signature: TPL_SIG, discoveryRuns: 3 }, { template: REG_V2.used_by[1], signature: TPL_SIG, discoveryRuns: 1 }],
    checks: [
      { label: 'beats label-shuffle null', detail: 'p < 0.005', state: 'pass' },
      { label: 'beats RF baseline', detail: 'ΔF1 0.11 · CI 0.04–0.18', state: 'pass' },
      { label: 'test windows unseen in training', detail: 'verified from manifest', state: 'pass' },
      { label: 'calibration ECE ≤ 0.10', detail: '4 of 4 classes', state: 'pass' },
    ],
    verification: { judged: 40, of: 40, agree: 34, perClass: [{ cls: 'spike-train', agree: 10, judged: 11 }, { cls: 'plateau', agree: 8, judged: 9 }, { cls: 'burst', agree: 6, judged: 9 }, { cls: 'slow-drift', agree: 10, judged: 11 }] },
    signoff: { actor: 'this installation', at: '30 Aug 16:12', reason: 'All checks pass; verification agreement 85 %.', name: 'cnn_windows_v2_manual', version: 'v2' },
    thresholds: { 'spike-train': 0.64, plateau: 0.57, burst: 0.69, 'slow-drift': 0.42 },
  },
  {
    // canon.ts: rf_windows_v1 is used by no template (frame shows "1 template"; §0 canon wins — inventory conflict 1)
    id: 'rf_windows_v1.manual', name: REG_RF.name, labelKind: 'manual', version: REG_RF.version, from: '20 Aug', status: 'registered', testF1: 0.58, usedBy: [],
    checks: [
      { label: 'beats label-shuffle null', detail: 'p < 0.005', state: 'pass' },
      { label: 'test windows unseen in training', detail: 'verified from manifest', state: 'pass' },
      { label: 'calibration ECE ≤ 0.10', detail: '4 of 4 classes', state: 'pass' },
    ],
    verification: { judged: 40, of: 40, agree: 30, perClass: [{ cls: 'spike-train', agree: 8, judged: 10 }, { cls: 'plateau', agree: 7, judged: 10 }, { cls: 'burst', agree: 6, judged: 10 }, { cls: 'slow-drift', agree: 9, judged: 10 }] },
    signoff: { actor: 'this installation', at: '20 Aug 10:40', reason: 'Reference baseline for later CNN arms.', name: 'rf_windows_v1_manual', version: 'v1' },
    thresholds: { 'spike-train': 0.58, plateau: 0.52, burst: 0.66, 'slow-drift': 0.38 },
  },
  {
    id: 'cnn_cluster_v1', name: `${REG_CLUSTER.name} · cluster`, labelKind: 'cluster', version: REG_CLUSTER.version, from: REG_CLUSTER.registered ?? '14 Sep', status: 'registered', testF1: 0.63,
    usedBy: [{ template: REG_CLUSTER.used_by[0], signature: TPL_SIG, discoveryRuns: 2 }],
    checks: [
      { label: 'beats label-shuffle null', detail: 'p < 0.005', state: 'pass' },
      { label: 'beats RF baseline', detail: 'ΔF1 0.13 · CI 0.06–0.20', state: 'pass' },
      { label: 'test windows unseen in training', detail: 'verified from manifest', state: 'pass' },
      { label: 'calibration ECE ≤ 0.10', detail: '4 of 4 classes', state: 'pass' },
    ],
    verification: { judged: 40, of: 40, agree: 31, perClass: [{ cls: 'spike-train', agree: 9, judged: 10 }, { cls: 'plateau', agree: 7, judged: 10 }, { cls: 'burst', agree: 6, judged: 10 }, { cls: 'slow-drift', agree: 9, judged: 10 }] },
    signoff: { actor: 'this installation', at: '14 Sep 09:05', reason: 'Cluster-label model for cnn_detect_cluster_v1.', name: 'cnn_cluster_v1', version: 'v1' },
    thresholds: { 'spike-train': 0.60, plateau: 0.58, burst: 0.70, 'slow-drift': 0.41 },
  },
  {
    id: 'cnn_windows_v2.manual.v1', name: 'cnn_windows_v2 · manual', labelKind: 'manual', version: 1, from: '12 Aug', status: 'retired', testF1: 0.61, usedBy: [],
    checks: [
      { label: 'beats label-shuffle null', detail: 'p < 0.005', state: 'pass' },
      { label: 'beats RF baseline', detail: 'ΔF1 0.06 · CI 0.01–0.11', state: 'pass' },
      { label: 'test windows unseen in training', detail: 'verified from manifest', state: 'pass' },
      { label: 'calibration ECE ≤ 0.10', detail: '4 of 4 classes', state: 'pass' },
    ],
    verification: { judged: 40, of: 40, agree: 32, perClass: MODEL_CLASSES.map(cls => ({ cls, agree: 8, judged: 10 })) },
    signoff: { actor: 'this installation', at: '12 Aug 15:30', reason: 'First manual-label CNN.', name: 'cnn_windows_v2_manual', version: 'v1' },
    thresholds: { 'spike-train': 0.66, plateau: 0.59, burst: 0.72, 'slow-drift': 0.45 },
  },
  {
    id: 'cnn_windows_v2.cluster.v1', name: 'cnn_windows_v2 · cluster', labelKind: 'cluster', version: 1, from: '12 Aug', status: 'rejected', testF1: 0.49, usedBy: [],
    checks: [
      { label: 'beats label-shuffle null', detail: 'p < 0.005', state: 'pass' },
      { label: 'beats RF baseline', detail: 'ΔF1 −0.02 · CI −0.08–0.04 crosses 0', state: 'fail' },
      { label: 'test windows unseen in training', detail: 'verified from manifest', state: 'pass' },
      { label: 'calibration ECE ≤ 0.10', detail: '1 of 4 classes', state: 'fail' },
    ],
    verification: { judged: 40, of: 40, agree: 21, perClass: MODEL_CLASSES.map(cls => ({ cls, agree: 5, judged: 10 })) },
    rejectedBecause: ['beats RF baseline — ΔF1 −0.02, CI −0.08–0.04 crosses 0', 'calibration ECE ≤ 0.10 — only 1 of 4 classes', 'human verification — 21 of 40 agree (53 %)'],
    signoff: { actor: 'this installation', at: '12 Aug 15:34', reason: 'Does not beat its RF baseline.', name: 'cnn_windows_v2_cluster', version: 'v1' },
  },
]
export const REGISTRY_NOTE = 'A registered model is inserted in Analyse as a Model stage; its calibration thresholds become the Threshold stage’s recommended values.'
