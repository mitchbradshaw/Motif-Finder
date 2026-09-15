/* The placeholder canon (prototyping/UI_FUNCTIONAL_SPEC.md §0, B23): the one set of facts every
 * concept frame draws from. Shared by every workspace's fixtures — import from here rather than
 * re-typing names, ids or counts, so pages agree with each other and with the frames.
 * Demo data only: nothing here is read from the database. Traces are synthetic. */

export interface CanonRecording {
  key: string; label: string; source_file: string; fs_hz: number; fs_note?: string; n_channels: number; duration_h: number
  start: string; held_out: boolean; channels: string[]
}

const M_CHANNELS = ['CH1_A1', 'CH2_A1', 'CH3_A2', 'CH4_A2', 'CH5_B1', 'CH6_B1', 'CH7_B2', 'CH8_B2', 'CH9_C1', 'CH10_C1', 'CH11_C2', 'CH12_C2', 'CH13_D1', 'CH14_D1', 'CH15_D2', 'CH16_D2']
const numbered = (n: number) => Array.from({ length: n }, (_, i) => `CH${i + 1}`)

export const RECORDINGS: CanonRecording[] = [
  { key: 'M2_aug_fs1', label: 'M2_aug fs1', source_file: 'M2_aug_concat_fs1.mat', fs_hz: 1, n_channels: 16, duration_h: 721, start: '2025-08-02 14:00', held_out: false, channels: M_CHANNELS },
  { key: 'M2_aug_fs2', label: 'M2_aug fs2', source_file: 'M2_aug_concat_fs2.mat', fs_hz: 2, n_channels: 16, duration_h: 721, start: '2025-08-02 14:00', held_out: false, channels: M_CHANNELS },
  { key: 'M3_jul', label: 'M3_jul', source_file: 'M3_jul.mat', fs_hz: 1, n_channels: 8, duration_h: 280, start: '2025-07-04 09:00', held_out: false, channels: numbered(8) },
  { key: 'L_LM_Jul26_J', label: 'L_LM_Jul26_J', source_file: 'L_LM_Jul_26_J.csv', fs_hz: 10, fs_note: 'inferred', n_channels: 5, duration_h: 22.4, start: '2026-07-26 10:00', held_out: false, channels: numbered(5) },
  { key: 'M4_aug', label: 'M4_aug', source_file: 'M4_aug_concat_fs1.mat', fs_hz: 1, n_channels: 16, duration_h: 300, start: '2025-08-20 12:00', held_out: true, channels: M_CHANNELS },
]
export const HELD_OUT_KEY = 'M4_aug'
export const TOTAL_CHANNELS = 61

export const CLASSES = [
  { key: '1', name: 'spike-train', colour: '#5856D6', informative: true },
  { key: '2', name: 'burst', colour: '#E85AAD', informative: true },
  { key: '3', name: 'slow-drift', colour: '#30B0C7', informative: true },
  { key: '4', name: 'plateau', colour: '#A2845E', informative: true },
  { key: '9', name: 'electrode artifact', colour: '#E5484D', informative: false },
] as const

export const VERDICTS = [
  { key: 'seed', colour: '#22A06B' },   // human verdict → green (§3); frame review-6
  { key: 'interesting', colour: '#22A06B' },
  { key: 'not_interesting', colour: '#9CA3AF' },
  { key: 'artifact', colour: '#E5484D' },
  { key: 'unsure', colour: '#E8900C' },
] as const

export const MORPHOLOGY_TAGS = ['sharkfin', 'biphasic', 'plateau-top', 'ramp', 'notched', 'spike-doublet']

/** Family identity palette (D8): avoids pure red/green/blue so a family never reads as a verdict. */
export const FAMILY_COLOURS: Record<string, string> = {
  'F-01': '#5856D6', 'F-02': '#E85AAD', 'F-03': '#30B0C7', 'F-04': '#A2845E', 'F-05': '#8E9C3A', 'F-06': '#64D2FF',
  'F-07': '#7A8FA6', 'F-08': '#6D4C41', 'F-09': '#F4A6C8', 'F-10': '#1E6F7A', 'F-11': '#C97B63',
}

export interface CanonFamily { id: string; name: string; members: number | null; recordings: string[]; exemplar?: string; medoid?: string; length_s?: number; colour: string }
export const FAMILIES: CanonFamily[] = [
  { id: 'F-03', name: 'sharkfin', members: 112, recordings: ['M2_aug fs1', 'M3_jul', 'L_LM_Jul26_J'], exemplar: 'E-0102', medoid: 'm-1846', length_s: 21, colour: FAMILY_COLOURS['F-03'] },
  { id: 'F-04', name: 'spike train', members: null, recordings: [], colour: FAMILY_COLOURS['F-04'] },
  { id: 'F-07', name: 'slow drift', members: 212, recordings: [], colour: FAMILY_COLOURS['F-07'] },
  { id: 'F-11', name: 'burst', members: 17, recordings: [], colour: FAMILY_COLOURS['F-11'] },
]

/** Detection chain, canonical order (B24). */
export const DETECTION_CHAIN = [
  { index: 0, label: 'Source', signature: 'Signal' },
  { index: 1, label: '01 Baseline', signature: 'Signal → Signal' },
  { index: 2, label: '02 Noise floor', signature: 'Signal → Signal + estimate' },
  { index: 3, label: '03 Encoding', signature: 'Signal → Encoding' },
  { index: 4, label: '04 Detection', signature: 'Encoding → SpanSet' },
]

export const ANALYSE_RUNS = [
  { id: 128, label: '#128 drop_motifs9', template: 'drop_motifs9' },
  { id: 131, label: '#131 drop_motifs9 · 6σ floor', template: 'drop_motifs9' },
  { id: 97, label: '#97 banded_sax_lp', template: 'banded_sax_lp' },
  { id: 140, label: '#140 F-03 slope interrogation', template: 'spike_shape_v1' },
]

export type JobKind = 'cluster' | 'analyse' | 'discovery' | 'library' | 'review'
export interface CanonJob { id: string; kind: JobKind; title: string; status: 'finished' | 'running' | 'paused' | 'failed' | 'queue'; detail: string; host?: string; since?: string; estimate?: string; overrun?: string; for?: string }
export const JOBS: CanonJob[] = [
  { id: 'j-0212', kind: 'cluster', title: 'cnn_windows_v3 paired arms', status: 'finished', detail: 'imported 13 Sep 21:40' },
  { id: 'j-0214', kind: 'cluster', title: 'cnn_windows_v3 seed repeats', status: 'running', detail: 'running on hpc-1 since 11:05', host: 'hpc-1', since: '11:05', estimate: '1 h', overrun: '3.3×' },
  { id: 'j-0217', kind: 'cluster', title: 'matrix profile, 3 channels', status: 'running', detail: 'running since 11:40 for Discovery run r-0431', since: '11:40', for: 'r-0431' },
  { id: 'r-0431', kind: 'discovery', title: 'mp_drops_v3', status: 'paused', detail: 'paused at stage 3 of 4' },
  { id: 'a-0098', kind: 'analyse', title: 'sax_vs_mp', status: 'paused', detail: 'paused at stage 2 of 5, result found in place' },
  { id: 'j-0209', kind: 'cluster', title: 'j-0209', status: 'failed', detail: 'failed' },
]
export const REVIEW_QUEUES = [
  { id: 'q-12', source: 'r-0412 mp_drops_v3', kind: 'discovery run' },
  { id: 'q-15', source: 'seed search r-0415', kind: 'seed search' },
  { id: 'q-18', source: 'training windows', kind: 'training windows', blind: true },
  { id: 'q-19', source: 'model verification', kind: 'model verification', blind: true, left: 7, total: 40 },
]

export const WINDOW_SET = {
  id: 'ws_M2aug_3ch_600s', version: 1, recording: 'M2_aug fs1', channels: ['CH2_A1', 'CH4_A2', 'CH7_B2'], length_s: 600,
  windows: 15660, labelled_every_arm: 2140, train_safe: true, next_version: 'v2',
}

export const MODELS = {
  registered: [
    { name: 'cnn_windows_v2 · manual', version: 2, used_by: ['drop_cnn_v1', 'sharkfin_cnn_v2'] },
    { name: 'rf_windows_v1 · manual', version: 1, used_by: [] as string[] },
    { name: 'cnn_cluster_v1', version: 1, registered: '14 Sep', used_by: ['cnn_detect_cluster_v1'] },
  ],
  candidates: [
    { name: 'cnn_windows_v3 · manual', registering_as: 'cnn_windows_v3_manual', from: 'j-0212' },
    { name: 'cnn_windows_v3 · cluster', from: 'j-0212' },
  ],
  verification: { judged: 33, of: 40, agree: 28 },
  test_block_windows: 432,
}

export const TEMPLATES = {
  total: 14,
  named: ['drop_motifs9', 'sharkfin_v2', 'mp_discord_v3', 'spike_shape_v1', 'cnn_detect_cluster_v1', 'drop_cnn_v1', 'sharkfin_cnn_v2'],
  training: ['cnn_windows_v3', 'cnn_windowset_v1'],
}

export const ACTOR = 'this installation'
export const LOCAL_LIMITS = { analyse: '20 min', discovery: '20 min', models: '2 h' }
export const STATUS_BADGES = ['cached', 'stale', 'new', 'running', 'paused', 'failed', 'on cluster', 'invalid'] as const

/** Header "N need you" count contributed by demo fixtures (paused runs + failed job + review queue waiting). */
export const DEMO_NEED_YOU = 3
/** Nav-rail "Jobs · N" count contributed by demo fixtures (the canon frames show 3). */
export const DEMO_JOBS_ACTIVE = 3

/* ---- time helpers (spec §0: hours since recording start, e.g. "192.40 h"; event durations in s) ---- */
export const fmtH = (h: number, digits = 2) => `${h.toFixed(digits)} h`
export const fmtS = (s: number) => `${s < 10 ? s.toFixed(1) : Math.round(s)} s`

/** Deterministic pseudo-random generator so fixture traces are stable across renders and screenshots. */
export function seeded(seed: number) {
  let s = seed >>> 0 || 1
  return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 1_000_000) / 1_000_000 }
}

/** A synthetic mV trace (never normalised) — e.g. a sharkfin drop of ~0.35 mV over ~21 s at 1 Hz. */
export function syntheticTrace(opts: { n: number; seed?: number; baseline?: number; noise?: number; events?: { at: number; depth: number; width: number; shape?: 'sharkfin' | 'spike' | 'plateau' }[] }): number[] {
  const rnd = seeded(opts.seed ?? 7)
  const out: number[] = []
  let drift = 0
  for (let i = 0; i < opts.n; i++) {
    drift += (rnd() - 0.5) * 0.004
    let v = (opts.baseline ?? 0) + drift + (rnd() - 0.5) * (opts.noise ?? 0.02)
    for (const e of opts.events ?? []) {
      const d = i - e.at
      if (e.shape === 'plateau') { if (d >= 0 && d < e.width) v -= e.depth }
      else if (e.shape === 'spike') { v -= e.depth * Math.exp(-(d * d) / (2 * (e.width / 4) ** 2)) }
      else if (d >= 0 && d < e.width) { const u = d / e.width; v -= e.depth * (u < 0.25 ? u / 0.25 : Math.exp(-(u - 0.25) * 4)) }
    }
    out.push(+v.toFixed(5))
  }
  return out
}
