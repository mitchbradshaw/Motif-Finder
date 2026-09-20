/* Analyse › Training fixtures (frames prototyping/imgs/analyse-training/*.pdf).
 * Demo data only — nothing here is read from the database. Shared entities come from fixtures/canon.ts
 * (spec §0 placeholder canon), so these pages agree with Models, Library, Review and Jobs.
 *
 * Arithmetic note (fog): the frames draw a 543-window set but per-class counts that sum to 343. 543 is
 * the anchor (1,629 images = 543 × 3 encodings; 131 reviewed + 412 unreviewed = 543), so the two largest
 * classes are scaled to make the partition sum to 543. Every other frame number is kept as drawn. */
import { FAMILY_COLOURS, seeded, syntheticTrace } from './canon'

/* ------------------------------------------------------------------ identity ------------------------------------------------------------------ */
export const NAME = 'cnn_windows_v3'
export const RECORDING = 'M2_aug fs1'
export const CHANNEL = 'CH4_A2'
export const SPAN_H = 45.2
export const SPAN_S = SPAN_H * 3600
export const RECIPE = 'a7f3…9c'
export const TRIAL_RECIPE = 'c9e2…41'

export const NULL_SPEC = {
  label: 'label shuffle',
  detail: 'Every grouping and every trained arm is repeated with its labels shuffled, so a reported agreement is read against what chance gives on the same windows. The shuffle keeps the split, so a leak shows up as a null that is too good.',
}

/* The one synthetic mV trace for CH4_A2 over 45.2 h, drawn at reduced rate so a whole span fits a card. */
export const SIGNAL_N = 1400
export const SIGNAL_FS = SIGNAL_N / SPAN_S
export const SIGNAL: number[] = syntheticTrace({
  n: SIGNAL_N, seed: 4207, baseline: -0.14, noise: 0.011,
  events: [
    { at: 210, depth: 0.12, width: 26 }, { at: 430, depth: 0.09, width: 18 },
    { at: 615, depth: 0.16, width: 34 }, { at: 866, depth: 0.22, width: 12, shape: 'spike' },
    { at: 1010, depth: 0.10, width: 40, shape: 'plateau' }, { at: 1240, depth: 0.13, width: 22 },
  ],
})
export const SIGNAL_Y: [number, number] = [-0.42, 0.06]

/* ------------------------------------------------------------------ the chain ------------------------------------------------------------------ */
export type TrainingStatus = 'cached' | 'stale' | 'new' | 'running' | 'paused' | 'failed' | 'on cluster' | 'invalid'

export interface TrainingBlock {
  id: string
  /** null on the source block; otherwise the displayed stage number (1-based, = the block route index). */
  index: number | null
  label: string
  signature: string
  glyph: string
  /** the two-line row summary under the badge */
  summary: string
  /** one-line plain-language caption under the row plot (spec §3: captions are load-bearing) */
  caption: string
  route: string | null
  onCluster?: boolean
}

export const CHAIN: TrainingBlock[] = [
  { id: 'source', index: null, label: 'Source', signature: '— → Signal', glyph: 'source', summary: `${CHANNEL} · span 0–${SPAN_H} h`, caption: 'one channel, one span — the scope small enough to see every intermediate', route: 'analyse/training' },
  { id: 'windows', index: 1, label: 'Sliding windows', signature: 'Signal → WindowSet', glyph: 'sliding_windows', summary: '10 min · stride 5 min · gap 10 min', caption: 'windows overlap 50 % · no window crosses a split boundary', route: 'analyse/training/block/1' },
  { id: 'matrix', index: 2, label: 'Window matrix', signature: 'WindowSet → WindowSet + features', glyph: 'window_matrix', summary: '4 of 5 groups · CNN scores off', caption: 'Catch22 · Entropy · Wavelet · CNN scores + RF excluded', route: 'analyse/training/block/2', onCluster: true },
  { id: 'cluster', index: 3, label: 'Cluster', signature: 'WindowSet → Grouping', glyph: 'cluster', summary: 'average linkage · k 6', caption: `class per window across ${SPAN_H} h`, route: 'analyse/training/block/3' },
  { id: 'encode', index: 4, label: 'Encode', signature: 'WindowSet → Encoding', glyph: 'image_encode', summary: 'GASF · GADF · RP · 224 px', caption: '3 of 4 encodings ticked · 1,629 images · stale — cluster k changed', route: 'analyse/training/block/4' },
  { id: 'model', index: 5, label: 'Model', signature: 'Encoding + labels → Model', glyph: 'model', summary: 'EfficientNet-B0 · trained in Models', caption: 'trial here on CH4 only · labels from 03 cluster · split from 01', route: 'analyse/training/block/5' },
]

/** The illustrative WindowSet source (frame 0b): P15 — the sliding-windows stage is *absent*, not skipped. */
export const CHAIN_HUMAN: TrainingBlock[] = [
  { id: 'source', index: null, label: 'Source', signature: '— → WindowSet', glyph: 'sliding_windows', summary: '412 windows · 38 % interesting', caption: 'one tick per window · green interesting · grey not_interesting · sampled 160 of 412', route: 'analyse/training' },
  { ...CHAIN[2], index: 1, route: 'analyse/training/block/2' },
  { ...CHAIN[3], index: 2, caption: 'class per window across 412 windows', route: 'analyse/training/block/3' },
  { ...CHAIN[4], index: 3, caption: '3 of 4 encodings ticked · 1,236 images · stale — cluster k changed', route: 'analyse/training/block/4' },
  { ...CHAIN[5], index: 4, caption: 'trial here on CH4 only · labels from 02 Cluster · the split rides on the source window set (B7)', route: 'analyse/training/block/5' },
]

/** Stage badges follow one rule: everything from `staleFrom` on is stale, 05 has never run.
 * `staleFrom` is a stage number in the *signal* chain; under a different source the stages renumber, so
 * it is resolved to a block id first and the run of stale blocks is taken by position in `blocks`. */
export function chainStatuses(staleFrom: number | null, blocks: TrainingBlock[] = CHAIN): Record<string, TrainingStatus> {
  const staleId = staleFrom == null ? null : CHAIN.find(b => b.index === staleFrom)?.id ?? null
  const staleAt = staleId ? blocks.findIndex(b => b.id === staleId) : -1
  const out: Record<string, TrainingStatus> = {}
  blocks.forEach((b, i) => {
    if (b.index == null) out[b.id] = 'cached'
    else if (b.id === 'model') out[b.id] = 'new'
    else out[b.id] = staleAt >= 0 && i >= staleAt ? 'stale' : 'cached'
  })
  return out
}

export const RUN_STEPS = ['01 Sliding windows', '02 Window matrix', '03 Cluster', '04 Encode', '05 Train model']

export const ESTIMATES = {
  chain: '≈ 3 h 10 min',
  windowsStale: 'gap 5 → 10 min · 01 → 05 stale',
  matrix: 'cached 2 Sept',
  cluster: '≈ 40 s · local',
  chooseK: 'sweep k 2–12 · ≈ 2 min local',
  encode: '≈ 6 min · 1,629 images',
  model: 'trial ≈ 2 h 40 on cluster',
}

/* ------------------------------------------------------------------ 01 sliding windows ------------------------------------------------------------------ */
export interface SplitBlock { kind: 'train' | 'validation' | 'test'; label: string; start_h: number; end_h: number; windows: number }

export const WINDOWS = {
  total: 543,
  assigned: 524,
  droppedAtGaps: 19,
  droppedByPendingGap: 12,
  unreviewed: 412,
  reviewed: 131,
  interesting: 48,
  queueCap: 20000,
  params: {
    from: 'sliding' as 'sliding' | 'window-set',
    length_min: 10,
    stride_min: 5,
    gap_min: 10,
    previousGap_min: 5,
    split: '70 / 15 / 15',
    blocks: '4 contiguous',
    seed: '17',
  },
  recommended: { length_min: 10, stride_min: 5, gap_min: 10, split: '70 / 15 / 15', blocks: '4 contiguous', seed: '17' },
  blocks: [
    { kind: 'train', label: 'train · 185 windows', start_h: 0, end_h: 15.2, windows: 185 },
    { kind: 'validation', label: 'val · 76 windows', start_h: 16.4, end_h: 22.6, windows: 76 },
    { kind: 'train', label: 'train · 163 windows', start_h: 23.8, end_h: 37.1, windows: 163 },
    { kind: 'test', label: 'test · 100 windows', start_h: 38.3, end_h: 45.2, windows: 100 },
  ] as SplitBlock[],
  gaps: [[15.2, 16.4], [22.6, 23.8], [37.1, 38.3]] as [number, number][],
  boundary: { from_h: 15.2, to_h: 16.4, gap_min: 10, note: '10 min window · 5 min stride → neighbours share half their samples', verdict: 'a gap of at least one window length means no training window shares a sample with a validation window' },
  verdictsPerSplit: [
    { split: 'train', windows: 348, reviewed: 88, interesting: 31 },
    { split: 'val', windows: 76, reviewed: 19, interesting: 8 },
    { split: 'test', windows: 100, reviewed: 24, interesting: 9 },
  ],
  verdictNote: 'cluster labels exist for every window; manual labels only for reviewed ones — the paired comparison in Models uses windows with both',
}

/* ---- the split geometry, derived from the two parameters that shape it ----
 * The default (70 / 15 / 15 over 4 contiguous blocks) is the frame's own geometry and is returned
 * verbatim; any other ratio or block count is laid out from the same rule so the strip, the window
 * counts and the per-split verdict bars all move when the parameter moves. */
const SPLIT_PATTERNS: Record<number, SplitBlock['kind'][]> = {
  2: ['train', 'test'],
  4: ['train', 'validation', 'train', 'test'],
  6: ['train', 'validation', 'train', 'test', 'train', 'validation'],
}
/** The visual break between blocks (the leakage gap itself is minutes wide — too thin to draw). */
const BLOCK_BREAK_H = 1.2
const kindLabel = (k: SplitBlock['kind']) => (k === 'validation' ? 'val' : k)

export interface SplitLayout {
  blocks: SplitBlock[]
  verdicts: { split: string; windows: number; reviewed: number; interesting: number }[]
  isDefault: boolean
}

export function splitLayout(ratio: string, blocksLabel: string): SplitLayout {
  const n = parseInt(blocksLabel, 10) || 4
  if (ratio === WINDOWS.params.split && n === 4) return { blocks: WINDOWS.blocks, verdicts: WINDOWS.verdictsPerSplit, isDefault: true }
  const pat = SPLIT_PATTERNS[n] ?? SPLIT_PATTERNS[4]
  const [tr, va, te] = ratio.split('/').map(s => Number(s.trim()) / 100)
  const share: Record<string, number> = { train: tr, validation: va, test: te }
  const slots: Record<string, number> = {}
  pat.forEach(k => { slots[k] = (slots[k] ?? 0) + 1 })
  const usable = SPAN_H - BLOCK_BREAK_H * (n - 1)
  let t = 0
  const blocks: SplitBlock[] = pat.map(kind => {
    const dur = (usable * share[kind]) / slots[kind]
    const b: SplitBlock = {
      kind, label: '', start_h: +t.toFixed(2), end_h: +(t + dur).toFixed(2),
      windows: Math.round((dur / usable) * WINDOWS.assigned),
    }
    b.label = `${kindLabel(kind)} · ${b.windows} windows`
    t += dur + BLOCK_BREAK_H
    return b
  })
  const per = (kind: string) => blocks.filter(b => b.kind === kind).reduce((s, b) => s + b.windows, 0)
  const verdicts = (['train', 'validation', 'test'] as const).map(kind => {
    const w = per(kind)
    return {
      split: kindLabel(kind), windows: w,
      reviewed: Math.round((w / WINDOWS.assigned) * WINDOWS.reviewed),
      interesting: Math.round((w / WINDOWS.assigned) * WINDOWS.interesting),
    }
  })
  return { blocks, verdicts, isDefault: false }
}

/** The breaks between blocks, as [start_h, end_h] pairs — where windows are dropped. */
export const splitGaps = (blocks: SplitBlock[]): [number, number][] =>
  blocks.slice(0, -1).map((b, i) => [b.end_h, blocks[i + 1].start_h] as [number, number])

/** Total windows lost at the block breaks: one gap's worth per break, scaled by the gap length. */
export const droppedAtGaps = (gapMin: number, nBlocks: number) =>
  Math.max(0, Math.round((WINDOWS.droppedAtGaps * (nBlocks - 1) * gapMin) / (3 * WINDOWS.params.gap_min)))

/** Windows a *change* of gap drops (or gives back): the frame's "gap 5 → 10 min drops 12 windows". */
export const droppedByGapChange = (fromMin: number, toMin: number, nBlocks: number) =>
  Math.round((nBlocks - 1) * Math.abs(toMin - fromMin) * 0.8)

export const WINDOW_CHECKS = [
  { id: 'boundary', label: 'no window crosses a split boundary', state: 'pass' as const },
  { id: 'gap', label: 'gap 10 min ≥ window 10 min', state: 'pass' as const },
  { id: 'linked', label: 'linked recordings (fs1 / fs2) never split — n/a on one channel', state: 'pass' as const },
  { id: 'unseen', label: '412 of 543 windows have no human verdict — the manual-label arm needs them', state: 'warn' as const },
]

export const RANDOM_SPLIT_WARNING = 'a random split leaks: overlapping windows land on both sides, so a validation window shares half its samples with a training window (P12)'

/** The boundary close-up: window bars either side of the gap, the dropped ones in red. */
export const BOUNDARY_WINDOWS = [
  { start_h: 14.60, end_h: 14.77, side: 'train' as const, dropped: false },
  { start_h: 14.68, end_h: 14.85, side: 'train' as const, dropped: false },
  { start_h: 14.77, end_h: 14.93, side: 'train' as const, dropped: false },
  { start_h: 14.85, end_h: 15.02, side: 'train' as const, dropped: false },
  { start_h: 14.93, end_h: 15.10, side: 'train' as const, dropped: false },
  { start_h: 15.02, end_h: 15.18, side: 'train' as const, dropped: true },
  { start_h: 15.10, end_h: 15.27, side: 'gap' as const, dropped: true },
  { start_h: 15.18, end_h: 15.35, side: 'gap' as const, dropped: true },
  { start_h: 16.40, end_h: 16.57, side: 'val' as const, dropped: false },
  { start_h: 16.48, end_h: 16.65, side: 'val' as const, dropped: false },
]

/* ------------------------------------------------------------------ 02 window matrix ------------------------------------------------------------------ */
export interface FeatureGroup {
  id: string; label: string; count: number; features: string[]
  labelDerived: boolean
  /** off by default for label-derived groups (P12) */
  included: boolean
  collapsedByDefault: boolean
}

export const FEATURE_GROUPS: FeatureGroup[] = [
  { id: 'catch22', label: 'Catch22', count: 22, features: Array.from({ length: 22 }, (_, i) => `c22_${String(i + 1).padStart(2, '0')}`), labelDerived: false, included: true, collapsedByDefault: true },
  { id: 'entropy', label: 'Entropy', count: 6, features: ['sample', 'shannon', 'permutation', 'svd', 'spectral', 'approximate'], labelDerived: false, included: true, collapsedByDefault: false },
  { id: 'rf', label: 'Random Forest', count: 2, features: ['p interesting', 'p not_interesting'], labelDerived: true, included: false, collapsedByDefault: false },
  { id: 'wavelet', label: 'Wavelet energy', count: 4, features: ['band 1', 'band 2', 'band 3', 'band 4'], labelDerived: false, included: true, collapsedByDefault: false },
  { id: 'cnn', label: 'CNN scores', count: 6, features: ['base · int', 'base · not', 'GASF · int', 'GASF · not', 'GADF · int', 'GADF · not'], labelDerived: true, included: false, collapsedByDefault: false },
]

export const MATRIX_COLS = 56
/** column index of the deviation band the frame marks at 28 h */
export const MATRIX_BAND_COL = 34
export const MATRIX_SELECTED_COL = 34

/** z-scored feature values, clipped at ±3σ, deterministic per feature id. */
export function matrixValues(featureIds: string[], seed = 991): number[][] {
  return featureIds.map((id, r) => {
    const rnd = seeded(seed + r * 37 + id.length)
    return Array.from({ length: MATRIX_COLS }, (_, c) => {
      const band = Math.exp(-((c - MATRIX_BAND_COL) ** 2) / 4) * 2.6
      const v = (rnd() - 0.5) * 5.4 + band + Math.sin((c / MATRIX_COLS) * 6 + r) * 0.8
      return Math.max(-3, Math.min(3, +v.toFixed(2)))
    })
  })
}

export const MATRIX = {
  normalise: 'z-score · per channel',
  clip: '± 3 σ',
  windowsFrom: '10 min · stride 5 min · 543',
  readout: { window: 283, from_h: 28.2, to_h: 28.4, klass: 'C3', feature: 'sample entropy +2.7σ', band: 'band at 28 h: 4 of 4 included groups deviate' },
  labelDerivedWarning: 'CNN scores and the Random Forest group come from models trained on manual verdicts — including them leaks manual labels into the clustering you compare against',
  compute: {
    state: 'cached', recipe: `recipe ${RECIPE}`, where: 'computed on the cluster in 14 min, 2 Sept',
    localNote: 'recomputing locally would take ≈ 3 h — above the 20 min local limit',
    localLimit: '20 min',
  },
  greyNote: 'CNN rows greyed = excluded from 03',
}

export const SLURM_MATRIX = `#!/bin/bash
#SBATCH --job-name=ub_matrix_${NAME}
#SBATCH --time=00:30:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=8

python -m pipeline.run --recipe ${RECIPE} --from-stage 02 --to-stage 02 \\
    --artifacts ./artifacts --manifest cluster_out/manifest.json`

/* ------------------------------------------------------------------ 03 cluster ------------------------------------------------------------------ */
/** D8 categorical palette: a class colour must never read as a verdict, so no pure red/green/blue. */
export const CLASS_COLOURS: Record<string, string> = {
  C1: FAMILY_COLOURS['F-01'], C2: FAMILY_COLOURS['F-03'], C3: FAMILY_COLOURS['F-04'],
  C4: FAMILY_COLOURS['F-05'], C5: FAMILY_COLOURS['F-02'], C6: FAMILY_COLOURS['F-10'],
}

export interface ClusterClass {
  id: string; windows: number; reviewed: number; interesting: number
  feature: string; tooSmall: boolean; colour: string
  train: number; val: number; test: number
  medoid: number[]; members: number[][]
}

function classTraces(seed: number, depth: number, width: number, shape?: 'sharkfin' | 'spike' | 'plateau') {
  const mk = (s: number) => syntheticTrace({ n: 120, seed: s, baseline: -0.14, noise: 0.008, events: [{ at: 48, depth, width, shape }] })
  return { medoid: mk(seed), members: [mk(seed + 11), mk(seed + 23)] }
}

const rawClasses = [
  { id: 'C1', windows: 260, reviewed: 74, interesting: 25, artifact: 3, feature: 'sample entropy −1.4σ', seed: 301, depth: 0.10, width: 30, shape: undefined },
  { id: 'C2', windows: 180, reviewed: 39, interesting: 17, artifact: 2, feature: 'wavelet b2 +1.9σ', seed: 317, depth: 0.16, width: 18, shape: undefined },
  { id: 'C3', windows: 51, reviewed: 9, interesting: 1, artifact: 3, feature: 'RF p_int +1.1σ', seed: 331, depth: 0.08, width: 44, shape: 'plateau' as const },
  { id: 'C4', windows: 32, reviewed: 8, interesting: 5, artifact: 1, feature: 'permutation +2.2σ', seed: 347, depth: 0.19, width: 10, shape: 'spike' as const },
  { id: 'C5', windows: 13, reviewed: 1, interesting: 0, artifact: 0, feature: 'spectral −2.8σ', seed: 359, depth: 0.05, width: 60, shape: 'plateau' as const },
  { id: 'C6', windows: 7, reviewed: 0, interesting: 0, artifact: 0, feature: 'approximate +3.0σ', seed: 373, depth: 0.24, width: 14, shape: 'spike' as const },
]

export const CLUSTER_CLASSES: ClusterClass[] = rawClasses.map(c => ({
  id: c.id, windows: c.windows, reviewed: c.reviewed, interesting: c.interesting,
  feature: c.feature, tooSmall: c.windows < 20, colour: CLASS_COLOURS[c.id],
  train: Math.round(c.windows * 348 / 543), val: Math.round(c.windows * 76 / 543), test: Math.round(c.windows * 100 / 543),
  ...classTraces(c.seed, c.depth, c.width, c.shape),
}))

export const CLASS_Y: [number, number] = [-0.42, 0.02]

export const CONTINGENCY = rawClasses.map(c => ({
  id: c.id,
  interesting: c.interesting,
  not_interesting: c.reviewed - c.interesting - c.artifact,
  artifact: c.artifact,
  no_verdict: c.windows - c.reviewed,
}))

export const STABILITY = [
  { id: 'C1', jaccard: 0.86 }, { id: 'C2', jaccard: 0.79 }, { id: 'C3', jaccard: 0.61 },
  { id: 'C4', jaccard: 0.74 }, { id: 'C5', jaccard: 0.38 }, { id: 'C6', jaccard: 0.22 },
]

export const CLUSTER = {
  params: { criterion: 'fixed-cut', linkage: 'average', distance: 'z-norm Euclidean', cut: 10.1, k: 6 },
  recommended: { criterion: 'fixed-cut', linkage: 'average', distance: 'z-norm Euclidean', cut: 10.1 },
  silhouette: 0.24,
  cophenetic: 0.91,
  truncation: 'truncated to the last 40 merges of 543',
  criterionWarning: 'fix the criterion before reporting cluster labels — or k becomes the finding',
  occupancyNote: 'C3 and C4 each cover one stretch — possibly regimes, not motif types',
  footerNote: '04 and 05 are stale from an earlier cut · 243 windows in these classes have no human verdict',
  ari: 0.21, nmi: 0.18, reviewedFor: 131,
  sweepNote: 'peak k 2 (average) — one class would hold 91 % of windows',
  bootstrap: 'bootstrap 100× · mean Jaccard',
}

export const CRITERIA = [
  { value: 'fixed-k', title: 'fixed k', description: 'set before looking' },
  { value: 'fixed-cut', title: 'fixed cut height', description: 'current · 10.1' },
  { value: 'max-silhouette', title: 'max silhouette', description: 'within a linkage' },
  { value: 'gap', title: 'gap statistic', description: 'vs uniform reference' },
  { value: 'min-class', title: 'smallest class ≥ N', description: 'trainable classes only' },
]

export const K_RANGE = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
export const K_SWEEP: Record<string, Record<string, number[]>> = {
  silhouette: {
    average: [0.300, 0.272, 0.256, 0.251, 0.240, 0.215, 0.205, 0.196, 0.186, 0.176, 0.166],
    ward: [0.214, 0.236, 0.250, 0.254, 0.244, 0.234, 0.226, 0.219, 0.209, 0.199, 0.190],
    complete: [0.195, 0.206, 0.216, 0.206, 0.196, 0.190, 0.181, 0.176, 0.170, 0.165, 0.160],
  },
  gap: {
    average: [0.42, 0.51, 0.58, 0.62, 0.64, 0.63, 0.61, 0.58, 0.55, 0.52, 0.49],
    ward: [0.38, 0.47, 0.55, 0.60, 0.62, 0.62, 0.60, 0.57, 0.54, 0.51, 0.48],
    complete: [0.31, 0.40, 0.47, 0.52, 0.55, 0.55, 0.53, 0.51, 0.48, 0.45, 0.42],
  },
  'min-class': {
    average: [231, 118, 64, 31, 13, 9, 7, 5, 4, 3, 2],
    ward: [248, 141, 82, 44, 22, 14, 10, 8, 6, 5, 4],
    complete: [196, 96, 51, 26, 11, 8, 6, 4, 3, 2, 2],
  },
}
export const LINKAGE_COLOURS: Record<string, string> = { average: 'var(--blue)', ward: '#8e5cf7', complete: '#9CA3AF' }
export const LINKAGE_R: Record<string, number> = { average: 0.91, ward: 0.52, complete: 0.78 }

/* ---- dendrogram (no kit component: see webui/pages/requests/training.md) ---- */
export interface DendroNode { id: string; height: number; klass?: string; children?: [DendroNode, DendroNode] }

function buildDendro(): DendroNode {
  const rnd = seeded(8123)
  const roots: DendroNode[] = CLUSTER_CLASSES.map((c, ci) => {
    let nodes: DendroNode[] = Array.from({ length: 4 }, (_, i) => ({ id: `${c.id}-${i}`, height: 0, klass: c.id }))
    /* The subtrees have to reach the cut for the cut to be cutting anything: each class tops out just
     * under 10.1 and the merges that join the classes sit above it (heights below). */
    let h = 3.4 + rnd() * 0.7
    while (nodes.length > 1) {
      const next: DendroNode[] = []
      for (let i = 0; i < nodes.length; i += 2) {
        if (i + 1 < nodes.length) { next.push({ id: `${c.id}-m${i}-${h.toFixed(2)}`, height: +h.toFixed(2), klass: c.id, children: [nodes[i], nodes[i + 1]] }); h += 2.1 + rnd() * 0.9 }
        else next.push(nodes[i])
      }
      nodes = next
      h += 0.5 + ci * 0.15
    }
    /* Every class has to close under the cut, or the cut at 10.1 slices a class in two and the picture
     * stops agreeing with "cut 10.1 → 6 classes". */
    const top = (n: DendroNode): number => (n.children ? Math.max(n.height, top(n.children[0]), top(n.children[1])) : 0)
    const scale = (n: DendroNode, f: number): DendroNode =>
      n.children ? { ...n, height: +(n.height * f).toFixed(2), children: [scale(n.children[0], f), scale(n.children[1], f)] } : n
    const max = top(nodes[0])
    return max > 0 ? scale(nodes[0], (8.7 + ci * 0.22) / max) : nodes[0]
  })
  const heights = [10.9, 12.4, 13.9, 15.4, 17.2]
  let acc = roots[0]
  for (let i = 1; i < roots.length; i++) acc = { id: `merge-${i}`, height: heights[i - 1], children: [acc, roots[i]] }
  return acc
}
export const DENDROGRAM = buildDendro()
export const DENDRO_MAX = 17.6

/** Where each class sits along the 45.2 h span (frame "Where classes occur in time"). */
export const OCCUPANCY: { klass: string; start_h: number; end_h: number }[] = [
  { klass: 'C2', start_h: 0, end_h: 2.1 }, { klass: 'C1', start_h: 2.1, end_h: 5.6 },
  { klass: 'C5', start_h: 5.6, end_h: 6.8 }, { klass: 'C4', start_h: 6.8, end_h: 8.2 },
  { klass: 'C2', start_h: 8.2, end_h: 9.4 }, { klass: 'C3', start_h: 9.4, end_h: 12.6 },
  { klass: 'C1', start_h: 12.6, end_h: 15.1 }, { klass: 'C2', start_h: 15.1, end_h: 17.0 },
  { klass: 'C1', start_h: 17.0, end_h: 23.4 }, { klass: 'C3', start_h: 23.4, end_h: 29.8 },
  { klass: 'C4', start_h: 29.8, end_h: 35.0 }, { klass: 'C3', start_h: 35.0, end_h: 36.4 },
  { klass: 'C6', start_h: 36.4, end_h: 37.0 }, { klass: 'C4', start_h: 37.0, end_h: 40.8 },
  { klass: 'C1', start_h: 40.8, end_h: 42.6 }, { klass: 'C3', start_h: 42.6, end_h: 45.2 },
]

/* ---- one window ↔ one time ↔ one class, used by 02, 03 and 04 alike ----
 * Every page that names a window has to agree about when it is and which class it fell in, or the
 * readout on 02 and the card on 04 say different things about the same window. The occupancy strip is
 * the one grouping on the page, so it is what decides. */
export const hoursForWindow = (w: number) =>
  +Math.min(SPAN_H, ((w - 1) * WINDOWS.params.stride_min) / 60).toFixed(2)

export const windowLengthH = WINDOWS.params.length_min / 60

export function classForWindow(w: number): string {
  const h = hoursForWindow(w)
  return (OCCUPANCY.find(o => h >= o.start_h && h < o.end_h) ?? OCCUPANCY[OCCUPANCY.length - 1]).klass
}

/** `n` windows that really do fall in `klass` — the browse grid has to open what its card says. */
export function windowsOfClass(klass: string, n: number, nonce = 0): number[] {
  const all: number[] = []
  for (let w = 1; w <= WINDOWS.total; w++) if (classForWindow(w) === klass) all.push(w)
  if (!all.length) return Array.from({ length: n }, (_, i) => i + 1)
  return Array.from({ length: n }, (_, i) => all[((i * 37 + nonce * 11) % all.length + all.length) % all.length]).sort((a, b) => a - b)
}

/** The window a matrix column stands for (columns are time bins over the same span). */
export const windowForColumn = (c: number, cols: number) =>
  Math.max(1, Math.min(WINDOWS.total, Math.round(((c + 0.5) / cols) * WINDOWS.total)))

/* ------------------------------------------------------------------ 04 encode ------------------------------------------------------------------ */
export type EncodingKind = 'gasf' | 'gadf' | 'rp' | 'fusion'
export interface EncodingSpec { id: EncodingKind; label: string; included: boolean; note: string }

export const ENCODINGS: EncodingSpec[] = [
  { id: 'gasf', label: 'GASF', included: true, note: 'Gramian angular summation field' },
  { id: 'gadf', label: 'GADF', included: true, note: 'Gramian angular difference field' },
  { id: 'rp', label: 'Recurrence', included: true, note: `recurrence plot at ε 0.20` },
  { id: 'fusion', label: 'Fusion RGB', included: false, note: 'GASF / GADF / RP stacked as one RGB image' },
]

/** The readout a matrix column resolves to — the same window, hour and class 04 will show. */
export function readoutForColumn(c: number, cols = MATRIX_COLS) {
  const window = windowForColumn(c, cols)
  return { col: c, window, from_h: hoursForWindow(window), klass: classForWindow(window) }
}
export const MATRIX_READOUT = readoutForColumn(MATRIX_BAND_COL)

/** Which split block a window falls in (train / val / test), from the split geometry on screen. */
export function splitForWindow(w: number, blocks: SplitBlock[] = WINDOWS.blocks): string {
  const h = hoursForWindow(w)
  const b = blocks.find(x => h >= x.start_h && h < x.end_h)
  return b ? `${kindLabel(b.kind)} block` : 'dropped at a gap'
}

const ENCODE_WINDOW = 118

export const ENCODE = {
  window: ENCODE_WINDOW,
  total: 543,
  klass: classForWindow(ENCODE_WINDOW),
  split: splitForWindow(ENCODE_WINDOW),
  onset_h: hoursForWindow(ENCODE_WINDOW),
  verdict: 'no verdict',
  signalNote: 'the signal for this window · 10 min · z-scored',
  params: { encoder: 'existing · v2', size: '224 × 224', paa: 'none', epsilon: 0.20, fusion: 'GASF / GADF / RP', writeTo: 'artifacts/encodings' },
  recommended: { encoder: 'existing · v2', size: '224 × 224', paa: 'none', epsilon: 0.20 },
  note: 'existing encoders stay — trained models expect exactly these images; new encoders or sizes register as new versions',
  newVersionNote: 'a different encoder set or image size registers as a NEW encoder version — already-trained models keep the old one',
  bytesPerImage: 0.6 * 1024 ** 3 / 1629,
  minutesPerThousand: 3.68,
  browseNote: '3 sampled windows per class',
  splitFloor: 20,
  footer: "04 is stale because 03's cut changed · fusion is unticked so its images are skipped",
}

/** What an image costs: the disk estimate for this signature is images × px × channels (§6.8). */
export const PX_OF: Record<string, number> = { '224 × 224': 224, '256 × 256': 256, '128 × 128': 128 }
export const PAA_FACTOR: Record<string, number> = { none: 1, '2 ×': 0.5, '4 ×': 0.25 }
export function encodeCost(images: number, size: string, paa: string) {
  const px = PX_OF[size] ?? 224
  const scale = ((px * px) / (224 * 224)) * (PAA_FACTOR[paa] ?? 1)
  return { bytes: images * ENCODE.bytesPerImage * scale, minutes: (images / 1000) * ENCODE.minutesPerThousand * scale }
}

/** Deterministic pseudo-image for one encoding of one window: an n × n grid in [-1, 1]. */
export function encodingImage(kind: EncodingKind, window: number, n = 22): number[][] {
  const rnd = seeded(window * 97 + kind.length * 13 + 5)
  const base = Array.from({ length: n }, () => rnd() * 2 - 1)
  const out: number[][] = []
  for (let i = 0; i < n; i++) {
    const row: number[] = []
    for (let j = 0; j < n; j++) {
      const a = base[i], b = base[j]
      let v: number
      if (kind === 'gasf') v = Math.cos(a + b)
      else if (kind === 'gadf') v = Math.sin(a - b)
      else if (kind === 'rp') v = Math.abs(a - b) < 0.4 ? 0.9 : -0.6 + Math.abs(a - b) * 0.3
      else v = (Math.cos(a + b) + Math.sin(a - b)) / 2
      row.push(+v.toFixed(3))
    }
    out.push(row)
  }
  return out
}

export function windowTrace(window: number): number[] {
  return syntheticTrace({ n: 120, seed: 600 + window, baseline: -0.14, noise: 0.009, events: [{ at: 54, depth: 0.15, width: 26 }] })
}

/* ------------------------------------------------------------------ 05 model ------------------------------------------------------------------ */
export interface StageRow { id: string; label: string; status: TrainingStatus; cost: string; costMin: number; runsOn: string; note: string; ticked: boolean; skippable: boolean }

export const MODEL_STAGES: StageRow[] = [
  { id: '01', label: 'Sliding windows', status: 'cached', cost: '< 1 s', costMin: 0.02, runsOn: '—', note: 'reused from cache', ticked: false, skippable: true },
  { id: '02', label: 'Window matrix', status: 'cached', cost: '14 min', costMin: 14, runsOn: 'cluster', note: `reused · recipe prefix a7f3`, ticked: false, skippable: true },
  { id: '03', label: 'Cluster', status: 'cached', cost: '40 s', costMin: 0.67, runsOn: 'local', note: 'skipped · labels read from cache', ticked: false, skippable: true },
  { id: '04', label: 'Encode', status: 'stale', cost: '6 min', costMin: 6, runsOn: 'cluster', note: 'rebuilds 1,629 images', ticked: true, skippable: false },
  { id: '05', label: 'Train model', status: 'new', cost: '2 h 40', costMin: 160, runsOn: 'cluster · GPU', note: 'EfficientNet-B0 · 30 epochs', ticked: true, skippable: false },
]

/** The cost of one trial run: only the ticked stages, because that is what the tick is for (§6.7). */
export const trialMinutes = (ticked: StageRow[]) => ticked.reduce((s, r) => s + r.costMin, 0)

export const LABEL_SOURCES = [
  { value: 'cluster', title: 'cluster classes', description: '6 classes from 03 · all 543 windows' },
  { value: 'manual', title: 'manual verdicts', description: 'binary · 131 reviewed windows only' },
  { value: 'both', title: 'both, paired', description: 'same split and test set — runs in Models' },
]

export const TRAINING_PARAMS = {
  architecture: 'EfficientNet-B0',
  input: 'GASF + GADF + RP · 224',
  epochs: '30 · early stop',
  stopOn: 'val balanced acc.',
  learningRate: '3e-4 · cosine',
  batchSeed: '32 · 17',
  classBalance: 'inverse-frequency weights',
  augmentation: 'time shift ± 10 %',
  heldOut: 'held out: M4_aug · locked in Settings › Datasets',
}

export const PRE_TRAIN_CHECKS = [
  { id: 'split', label: 'split is blocked by time with a 10 min gap (01)', state: 'pass' as const },
  { id: 'label-derived', label: 'label-derived CNN features excluded from 02 → 03', state: 'pass' as const },
  { id: 'held-out', label: 'held-out recording locked · linked fs1 / fs2 never split', state: 'pass' as const },
  { id: 'images', label: '1,629 images — well under the ~10,000 a CNN on encodings usually needs', state: 'warn' as const },
  { id: 'small-classes', label: 'C5 and C6 have under 20 windows per split — merge or raise the cut', state: 'warn' as const },
  { id: 'manual-arm', label: 'manual-verdict arm has only 131 windows — 412 still unreviewed', state: 'warn' as const },
]

export const TRIAL = {
  title: 'Trial job · this channel only',
  subtitle: 'stages 04 → 05 · one GPU task',
  template: 'guided · uob-bc4',
  returns: 'results return via Jobs › Manifest inbox',
}

export function trialScript(fromStage: string, toStage: string): string {
  return `#SBATCH --job-name=ub_train_${NAME}  --gres=gpu:1  --time=04:00:00  --mem=32G
python -m pipeline.run --recipe ${TRIAL_RECIPE} --from-stage ${fromStage} --to-stage ${toStage} \\
    --artifacts ./artifacts --manifest cluster_out/manifest.json`
}

/* ------------------------------------------------------------------ 0b: the illustrative source ------------------------------------------------------------------ */
export const HUMAN_SOURCE = {
  id: 'ws_human_labelled_mixed',
  channel: CHANNEL,
  windows: 412,
  interestingPct: 0.38,
  sampled: 160,
  labels: 'interesting / not',
  images: 1236,
  caption: 'one tick per window · green interesting · grey not_interesting · sampled 160 of 412',
  handoff: { title: 'Every window already has a manual label — no review backlog', sub: 'clusters are compared against verdicts the windows already carry · spans many channels, so it trains in Models' },
  b7: {
    title: 'No sliding-windows stage, so no split stage — where does the blocked split go?',
    body: 'Open implementation question (backlog B7). Candidate: a split filter applied to the source windows themselves — blocked by recording and time, gap ≥ one window length, adjacent or overlapping labelled windows dropped at block edges.',
    tag: 'backlog B7',
  },
  footer: { fact: '412 windows · labels on every window', sub: 'illustrative only · noted in the backlog as a future source type' },
}

/** The 412 verdict ticks (sampled to 160 for the strip). */
export const HUMAN_TICKS: boolean[] = (() => {
  const rnd = seeded(5150)
  return Array.from({ length: HUMAN_SOURCE.sampled }, () => rnd() < HUMAN_SOURCE.interestingPct)
})()

/* ------------------------------------------------------------------ sources & history ------------------------------------------------------------------ */
export const SOURCE_CHOICES = [
  { value: 'signal', label: `Signal span · ${CHANNEL} · 0–${SPAN_H} h`, description: 'one channel from Explore — sliding windows make the WindowSet', kind: 'Signal' },
  { value: 'human-windows', label: `${HUMAN_SOURCE.id} · 412 windows`, description: 'a window set humans have already labelled — illustrative, not built (P13)', kind: 'WindowSet', illustrative: true },
]

export const HISTORY_RUNS = [
  { id: 140, label: '#140 F-03 slope interrogation', template: 'sharkfin_slope_v1', terminal: 'Features', disabled: true, reason: 'terminal Features · this is a training chain' },
  { id: 131, label: '#131 drop_motifs9 · 6σ floor', template: 'drop_motifs9', terminal: 'SpanSet', disabled: true, reason: 'terminal SpanSet · this is a training chain' },
  { id: 128, label: '#128 drop_motifs9', template: 'drop_motifs9', terminal: 'SpanSet', disabled: true, reason: 'terminal SpanSet · this is a training chain' },
  { id: 97, label: '#97 banded_sax_lp', template: 'banded_sax_lp', terminal: 'SpanSet', disabled: true, reason: 'terminal SpanSet · this is a training chain' },
]

export const IMPORT_TEMPLATES = [
  { value: 'cnn_windows_v3', label: 'cnn_windows_v3', description: 'training template · terminal Model · the chain in hand' },
  { value: 'cnn_windowset_v1', label: 'cnn_windowset_v1', description: 'training template · source WindowSet', disabled: true, reason: 'source WindowSet · a saved window set spans 3 channels · Analyse is single-channel (P3) · launch it in Models' },
  { value: 'drop_motifs9', label: 'drop_motifs9', description: 'detection template · terminal SpanSet → opens the detection chain' },
]

export const CANON_TEMPLATES = ['drop_motifs9', 'sharkfin_v2', 'mp_discord_v3', 'spike_shape_v1', 'cnn_detect_cluster_v1', 'drop_cnn_v1', 'sharkfin_cnn_v2', 'cnn_windows_v3', 'cnn_windowset_v1']

/* ------------------------------------------------------------------ formatting ------------------------------------------------------------------ */
export const fmtGB = (bytes: number) => `${(bytes / 1024 ** 3).toFixed(1)} GB`
export const fmtMin = (m: number) => (m < 60 ? `≈ ${Math.round(m)} min` : `≈ ${Math.floor(m / 60)} h ${String(Math.round(m % 60)).padStart(2, '0')}`)
