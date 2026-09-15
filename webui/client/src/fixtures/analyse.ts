/* Analyse › Chain demo fixtures (spec §0 placeholder canon, B24 detection chain). Demo data only: the traces are
 * synthetic, the numbers are the concept frames' numbers (prototyping/imgs/analyse-chain). Nothing here is read from
 * the database; components reach it only through api/analyse.ts. Demo blocks are named `demo.*` so they can never be
 * confused with a registered adapter and are never sent to the bridge. */
import { ANALYSE_RUNS, FAMILY_COLOURS, RECORDINGS, seeded, syntheticTrace } from './canon'

/* ------------------------------------------------------------------ type system ---- */
export type DemoKind = 'signal' | 'encoding' | 'scores' | 'spanset' | 'windowset' | 'grouping' | 'model' | 'features' | 'views'
export const DEMO_KIND_LABEL: Record<DemoKind, string> = {
  signal: 'Signal', encoding: 'Encoding', scores: 'Scores', spanset: 'SpanSet', windowset: 'WindowSet', grouping: 'Grouping', model: 'Model', features: 'Features', views: 'views',
}
export type DemoCategory = 'preprocess' | 'encode' | 'detect' | 'cluster' | 'model' | 'control'

export interface DemoBlock {
  name: string; page_name: string; short: string
  glyph: string                     // analyse/glyphs.tsx registry name
  input: DemoKind; output: DemoKind; side?: string
  signature: string; category: DemoCategory
  cost: string; cost_s: number; has_null: boolean
  refuse?: string                   // a block that never fits a chain, with the reason
  description: string
  defaults: [string, string][]      // insert-modal detail panel
  params: Record<string, unknown>   // step params on insert
  ceiling_note?: string
  glyph_group: 'preprocess' | 'encode' | 'scores' | 'interrogate'
}

const B = (b: DemoBlock) => b
export const DEMO_BLOCKS: DemoBlock[] = [
  B({ name: 'demo.baseline_removal', page_name: 'Baseline removal', short: 'Baseline', glyph: 'preprocessing.detrend', input: 'signal', output: 'signal', signature: 'Signal → Signal', category: 'preprocess', cost: '≈ 0.1 s', cost_s: 0.1, has_null: true, glyph_group: 'preprocess',
    description: 'Subtracts a slow baseline (rolling median) so drops are measured from a flat floor.', defaults: [['method', 'rolling median'], ['window', '7 s'], ['edges', 'reflect']], params: { method: 'rolling median', window_s: 7, edges: 'reflect' } }),
  B({ name: 'demo.bandpass', page_name: 'Bandpass filter', short: 'Bandpass', glyph: 'preprocessing.bandpass', input: 'signal', output: 'signal', signature: 'Signal → Signal', category: 'preprocess', cost: '≈ 0.1 s', cost_s: 0.1, has_null: true, glyph_group: 'preprocess',
    description: 'Keeps the band between two cut-offs; zero-phase Butterworth.', defaults: [['low', '0.01 Hz'], ['high', '0.1 Hz'], ['order', '4']], params: { low_hz: 0.01, high_hz: 0.1, order: 4 } }),
  B({ name: 'demo.noise_floor', page_name: 'Noise floor', short: 'Noise floor', glyph: 'preprocessing.noise_floor', input: 'signal', output: 'signal', signature: 'Signal → Signal + estimate', category: 'preprocess', cost: '≈ 0.1 s', cost_s: 0.1, has_null: true, glyph_group: 'preprocess',
    description: 'Estimates the slope noise σ of the span; the encoding\'s cutlines are set in multiples of it.', defaults: [['estimator', 'MAD × 1.4826'], ['scope', 'whole span'], ['exclude', 'detected spans · iterate 2×']], params: { estimator: 'MAD × 1.4826', scope: 'whole span', exclude: 'detected spans · iterate 2×', floor_from: 'this span' } }),
  B({ name: 'demo.surrogate', page_name: 'Surrogate generator', short: 'Surrogate', glyph: 'preprocessing.surrogate', input: 'signal', output: 'signal', signature: 'Signal → Signal', category: 'preprocess', cost: '≈ 0.3 s', cost_s: 0.3, has_null: false, glyph_group: 'preprocess',
    description: 'Phase-randomised copy with the same spectrum — the null every other block is judged against.', defaults: [['method', 'phase-rand'], ['copies', '200'], ['seed', 'from template']], params: { method: 'phase-rand', copies: 200 } }),
  B({ name: 'demo.symbolic_encoding', page_name: 'Symbolic encoding', short: 'Symbolic encoding', glyph: 'detection.sax_dsax', input: 'signal', output: 'encoding', signature: 'Signal → Encoding', category: 'encode', cost: '≈ 0.2 s', cost_s: 0.2, has_null: true, glyph_group: 'encode',
    description: 'Cuts the signal into short segments and writes each segment\'s slope as a letter: d D S U u.', defaults: [['alphabet k', '3'], ['segment', '0.2 s'], ['noise floor', '8 σ']], params: { alphabet: 3, split: 'd/D · U/u', segment_s: 0.2, same_fraction: 0.6, noise_k: 8, edges: 'reflect' } }),
  B({ name: 'demo.symbol_smoothing', page_name: 'Symbol smoothing', short: 'Smoothing', glyph: 'encoding.smoothing', input: 'encoding', output: 'encoding', signature: 'Encoding → Encoding', category: 'encode', cost: '≈ 0.1 s', cost_s: 0.1, has_null: true, glyph_group: 'encode',
    description: 'Replaces isolated one-segment letters with their neighbours\' majority.', defaults: [['window', '3 segments'], ['ties', 'keep']], params: { window: 3 } }),
  B({ name: 'demo.run_length', page_name: 'Run-length collapse', short: 'Run-length', glyph: 'encoding.run_length', input: 'encoding', output: 'encoding', signature: 'Encoding → Encoding', category: 'encode', cost: '≈ 0.2 s', cost_s: 0.2, has_null: true, glyph_group: 'encode',
    description: 'Collapses repeated letters into runs: DDDDSSUU → D×4 S×2 U×2.', defaults: [['minimum run', '2 segments'], ['keep SAME runs', 'yes'], ['emit', 'run lengths + letters']], params: { min_run: 2, keep_same: true } }),
  B({ name: 'demo.alphabet_remap', page_name: 'Alphabet remap', short: 'Remap', glyph: 'encoding.alphabet_remap', input: 'encoding', output: 'encoding', signature: 'Encoding → Encoding', category: 'encode', cost: '≈ 0.1 s', cost_s: 0.1, has_null: false, glyph_group: 'encode',
    description: 'Maps one alphabet onto another, e.g. k 5 → k 3 by merging d/D and U/u.', defaults: [['from', 'k 5'], ['to', 'k 3']], params: { from_k: 5, to_k: 3 } }),
  B({ name: 'demo.word_filter', page_name: 'Word filter', short: 'Word filter', glyph: 'encoding.word_filter', input: 'encoding', output: 'encoding', signature: 'Encoding → Encoding', category: 'encode', cost: '≈ 0.1 s', cost_s: 0.1, has_null: true, glyph_group: 'encode',
    description: 'Keeps only segments inside words that match a pattern, e.g. d+ S* U+.', defaults: [['pattern', 'd+ S* U+'], ['min length', '3']], params: { pattern: 'd+ S* U+' } }),
  B({ name: 'demo.gramian', page_name: 'Gramian encoding', short: 'Gramian', glyph: 'catalogue.gramian_fusion', input: 'windowset', output: 'encoding', signature: 'WindowSet → Encoding', category: 'encode', cost: '≈ 3 min', cost_s: 180, has_null: false, glyph_group: 'encode',
    description: 'Turns each window into a 2-D image (GASF / GADF / recurrence).', defaults: [['size', '64 px'], ['fields', 'gasf + gadf']], params: { size: 64 } }),
  B({ name: 'demo.matrix_profile', page_name: 'Matrix profile', short: 'Matrix profile', glyph: 'detection.matrix_profile', input: 'signal', output: 'scores', signature: 'Signal → Scores', category: 'detect', cost: '≈ 6.4 h*', cost_s: 0.2, has_null: true, glyph_group: 'scores', ceiling_note: '* whole channel · this span ≈ 0.2 s',
    description: 'Distance from every subsequence to its nearest neighbour: dips are motifs, peaks are discords.', defaults: [['m', '600 s'], ['exclusion', 'm / 2'], ['algorithm', 'STUMP · exact']], params: { m_s: 600, exclusion: 'm / 2', algorithm: 'STUMP · exact', normalise: 'z-norm' } }),
  B({ name: 'demo.seeded_search', page_name: 'Seeded search', short: 'Seeded search', glyph: 'detection.seeded_search', input: 'signal', output: 'scores', side: 'exemplar', signature: 'Signal + exemplar → Scores', category: 'detect', cost: '≈ 1.1 s', cost_s: 1.1, has_null: true, glyph_group: 'scores', refuse: 'a Discovery mode · not a chain block',
    description: 'Distance from one exemplar to every subsequence. Runs from Discovery › Seed search.', defaults: [['exemplar', 'E-0102'], ['metric', 'z-norm Euclidean']], params: {} }),
  B({ name: 'demo.threshold', page_name: 'Threshold to spans', short: 'Threshold', glyph: 'detection.threshold', input: 'scores', output: 'spanset', signature: 'Scores → SpanSet', category: 'detect', cost: '≈ 0.1 s', cost_s: 0.1, has_null: false, glyph_group: 'scores',
    description: 'Keeps the stretches where the score crosses a cut, after a minimum duration and a merge gap.', defaults: [['cut', '2.5 σ'], ['min duration', '60 s'], ['merge gap', '30 s']], params: { cut_sigma: 2.5, min_duration_s: 60, merge_gap_s: 30, keep: 'above the cut' } }),
  B({ name: 'demo.topk_pairs', page_name: 'Top-k motif pairs', short: 'Top-k pairs', glyph: 'scores.topk', input: 'scores', output: 'spanset', signature: 'Scores → SpanSet', category: 'detect', cost: '≈ 0.1 s', cost_s: 0.1, has_null: true, glyph_group: 'scores',
    description: 'Keeps the k lowest profile values as motif pairs, with the exclusion zone between them.', defaults: [['k', '3'], ['exclusion', 'm / 2']], params: { k: 3 } }),
  B({ name: 'demo.peak_picker', page_name: 'Peak picker', short: 'Peaks', glyph: 'scores.peaks', input: 'scores', output: 'spanset', signature: 'Scores → SpanSet', category: 'detect', cost: '≈ 0.1 s', cost_s: 0.1, has_null: false, glyph_group: 'scores',
    description: 'Picks local maxima above a prominence, one span of width m around each.', defaults: [['prominence', '2 σ'], ['width', 'm']], params: { prominence_sigma: 2 } }),
  B({ name: 'demo.drop_detection', page_name: 'Drop detection', short: 'Drop detection', glyph: 'detection.drop', input: 'encoding', output: 'spanset', signature: 'Encoding → SpanSet', category: 'detect', cost: '≈ 0.1 s', cost_s: 0.1, has_null: true, glyph_group: 'scores',
    description: 'Finds d-runs followed by a recovery, frames each drop, and dedupes overlapping copies.', defaults: [['minimum depth', '0.10 mV'], ['merge window', '2.0 s'], ['dedupe', 'keep best-framed']], params: { min_depth_mv: 0.1, min_duration_s: 0.6, merge_window_s: 2.0, trough_tol_sigma: 0.5, dedupe: 'keep best-framed', onset: 'walk back from steepest' } }),
  B({ name: 'demo.span_dedupe', page_name: 'Span dedupe', short: 'Span dedupe', glyph: 'spanset.dedupe', input: 'spanset', output: 'spanset', signature: 'SpanSet → SpanSet', category: 'detect', cost: '≈ 0.1 s', cost_s: 0.1, has_null: false, glyph_group: 'scores',
    description: 'Merges spans that overlap by IoU and keeps the best-scoring copy.', defaults: [['IoU', '≥ 0.5'], ['keep', 'best']], params: { iou: 0.5, keep: 'best' } }),
  B({ name: 'demo.model_stage', page_name: 'Model stage', short: 'Model stage', glyph: 'model.stage', input: 'windowset', output: 'scores', side: 'Model', signature: 'Model + WindowSet → Scores', category: 'model', cost: '≈ 2 min', cost_s: 120, has_null: false, glyph_group: 'scores',
    description: 'A registered model scores every window; its calibration becomes the next stage\'s recommended cut.', defaults: [['model', 'cnn_windows_v2 · manual · v2'], ['batch', '64']], params: { model: 'cnn_windows_v2 · manual · v2', batch: 64, pass_class: 'spike-train' } }),
  B({ name: 'demo.resolve_slope', page_name: 'Resolve spans · slope', short: 'Slope', glyph: 'interrogation.slope', input: 'spanset', output: 'features', signature: 'SpanSet → + Features', category: 'control', cost: '≈ 1 s', cost_s: 1, has_null: true, glyph_group: 'interrogate',
    description: 'Resolves each span\'s onset and trough and measures its slopes; declares each Feature.', defaults: [['onset', 'walk back from steepest'], ['features', 'slope · depth · duration']], params: {} }),
  B({ name: 'demo.aggregate', page_name: 'Aggregate', short: 'Aggregate', glyph: 'interrogation.aggregate', input: 'features', output: 'views', signature: 'Features → views', category: 'control', cost: '≈ 0.1 s', cost_s: 0.1, has_null: true, glyph_group: 'interrogate',
    description: 'Histograms and scaling relationships over the declared Features, each against its null.', defaults: [['views', 'histogram · scaling'], ['colour by', 'recording']], params: {} }),
  B({ name: 'demo.sliding_windows', page_name: 'Sliding windows', short: 'Windows', glyph: 'preprocessing.sliding_windows', input: 'signal', output: 'windowset', signature: 'Signal → WindowSet', category: 'preprocess', cost: '≈ 0.1 s', cost_s: 0.1, has_null: false, glyph_group: 'interrogate',
    description: 'Fixed-length windows with a stride and a blocked train / validation / test split.', defaults: [['length', '600 s'], ['stride', '300 s']], params: { length_s: 600, stride_s: 300 } }),
  B({ name: 'demo.window_matrix', page_name: 'Window matrix', short: 'Window matrix', glyph: 'preprocessing.window_matrix', input: 'windowset', output: 'windowset', signature: 'WindowSet → WindowSet', category: 'preprocess', cost: '≈ 40 s', cost_s: 40, has_null: false, glyph_group: 'interrogate',
    description: 'Computes a feature row per window (catch22, entropies).', defaults: [['groups', 'catch22 + entropy']], params: {} }),
  B({ name: 'demo.hier_cluster', page_name: 'Hierarchical cluster', short: 'Cluster', glyph: 'catalogue.cluster', input: 'windowset', output: 'grouping', signature: 'WindowSet → Grouping', category: 'cluster', cost: '≈ 40 s', cost_s: 40, has_null: false, glyph_group: 'interrogate',
    description: 'Ward linkage over the window matrix, cut into k clusters.', defaults: [['linkage', 'ward'], ['k', '3']], params: { linkage: 'ward', k: 3 } }),
  B({ name: 'demo.model', page_name: 'Model', short: 'Model', glyph: 'model.template', input: 'encoding', output: 'model', side: 'labels', signature: 'Encoding + labels → Model', category: 'model', cost: '≈ 2 h', cost_s: 7200, has_null: false, glyph_group: 'interrogate',
    description: 'A training template: trains in Models, never here.', defaults: [['labels', 'window verdicts'], ['arch', 'cnn']], params: {} }),
]

/* ------------------------------------------------------------------ sources ---- */
export interface DemoSource { key: string; recording: string; channel: string; t0_s: number; t1_s: number; fs: number; whole: boolean; chip: string; caption: string }
const H = 3600
export const DEMO_SOURCES: Record<string, DemoSource> = {
  span50: { key: 'span50', recording: RECORDINGS[0].label, channel: 'CH4_A2', t0_s: 192.4 * H, t1_s: 192.4 * H + 50, fs: 1, whole: false, chip: 'Signal span · CH4_A2 · 192.400–192.414 h', caption: 'signal span from Explore · 50 s' },
  span6h: { key: 'span6h', recording: RECORDINGS[0].label, channel: 'CH4_A2', t0_s: 6 * H, t1_s: 12 * H, fs: 1, whole: false, chip: 'Signal · CH4_A2 · 6.0–12.0 h · 6 h', caption: 'span 6.0–12.0 h · 6 h · 1 Hz' },
  whole: { key: 'whole', recording: RECORDINGS[0].label, channel: 'CH4_A2', t0_s: 0, t1_s: 721 * H, fs: 1, whole: true, chip: 'Signal · CH4_A2 · whole channel · 721 h', caption: 'whole channel · 721 h' },
}

/* ------------------------------------------------------------------ synthetic payloads ---- */
export interface Env { t: number[]; v: (number | null)[]; n_source: number; n_points: number; decimated: boolean }
const env = (t: number[], v: number[], n_source = t.length): Env => ({ t, v: v.map(x => +x.toFixed(5)), n_source, n_points: t.length, decimated: n_source > t.length })
const lin = (t0: number, t1: number, n: number) => Array.from({ length: n }, (_, i) => t0 + (t1 - t0) * i / (n - 1))

/** Kept drops on the 50 s span: [start offset s, duration s, depth mV, family, score, adjudication]. */
export const KEPT_DROPS: { id: string; at: number; dur: number; depth: number; family: string | null; score: number; judged: string | null }[] = [
  { id: 'M12', at: 7.2, dur: 1.4, depth: 0.31, family: 'F-03', score: 0.91, judged: null },
  { id: 'M13', at: 14.1, dur: 1.6, depth: 0.36, family: 'F-07', score: 0.87, judged: null },
  { id: 'M14', at: 22.0, dur: 1.5, depth: 0.40, family: 'F-03', score: 0.83, judged: 'already judged · run #114' },
  { id: 'M15', at: 28.6, dur: 1.1, depth: 0.22, family: null, score: 0.79, judged: null },
  { id: 'M16', at: 37.2, dur: 1.7, depth: 0.37, family: 'F-07', score: 0.75, judged: null },
  { id: 'M17', at: 44.4, dur: 1.2, depth: 0.25, family: 'F-03', score: 0.71, judged: null },
]
/** The 17 raw detections dedupe / floors removed (offset s, duration s). */
export const DROPPED_DROPS: [number, number][] = [[4.0, 1.2], [6.8, 1.9], [9.8, 1.0], [13.6, 2.2], [17.2, 1.4], [21.4, 2.4], [25.2, 0.5], [27.9, 2.0], [31.6, 1.3], [33.9, 0.4], [36.6, 2.3], [40.1, 1.1], [43.7, 2.2], [46.6, 0.9], [11.6, 0.8], [19.4, 0.7], [48.2, 0.6]]

function spanTraces() {
  const src = DEMO_SOURCES.span50
  const n = 251; const t = lin(src.t0_s, src.t1_s, n)
  const rnd = seeded(128)
  const out: number[] = []; const base: number[] = []; const raw: number[] = []
  for (let i = 0; i < n; i++) {
    const s = (t[i] - src.t0_s)
    let o = 0.05 * Math.sin(s / 1.3) + 0.03 * Math.sin(s / 0.47 + 1) + (rnd() - 0.5) * 0.02
    for (const d of KEPT_DROPS) { const u = (s - d.at) / d.dur; if (u > -0.4 && u < 1.6) o -= d.depth * Math.exp(-((u - 0.55) ** 2) / 0.09) }
    const b = 0.36 * Math.sin(s / 7.5 + 0.4) + 0.12 * Math.sin(s / 2.9)
    out.push(o); base.push(b); raw.push(b + o - 0.62)
  }
  return { t, out, base, raw }
}
const ST = spanTraces()
export const SIGMA = 0.00958
export const SEG_S = 0.2
/** Segment slopes (mV/s) on the 50 s span, 250 segments of 0.2 s, with the drops' onsets and recoveries. */
export const SEGMENT_SLOPES: number[] = (() => {
  const rnd = seeded(31)
  const out: number[] = []
  for (let k = 0; k < 250; k++) {
    const s = (k + 0.5) * SEG_S
    let v = (rnd() + rnd() + rnd() - 1.5) * 2.2 * SIGMA + (rnd() < 0.1 ? (rnd() - 0.5) * 9 * SIGMA : 0)
    for (const d of KEPT_DROPS) { const u = (s - d.at) / d.dur; if (u > 0 && u < 0.5) v -= (0.09 + d.depth * 0.08) * (1 - Math.abs(u - 0.25) * 2.2); if (u >= 0.5 && u < 1.05) v += (0.075 + d.depth * 0.08) * (1 - Math.abs(u - 0.78) * 2.5) }
    out.push(+v.toFixed(5))
  }
  return out
})()

export interface DemoSignalPayload { type: 'demo.signal'; t0_s: number; t1_s: number; envelope: Env; ghost?: Env; baseline?: Env; y_range: [number, number]; summary: string }
export interface DemoSlopePayload { type: 'demo.slope'; t0_s: number; seg_s: number; slopes: number[]; sigma: number; k: number; summary: string }
export interface DemoStripsPayload { type: 'demo.strips'; t0_s: number; seg_s: number; strips: { label: string; alphabet: 3 | 5; symbols: number[] }[]; summary: string }
export interface DemoSpansPayload { type: 'demo.spans'; t0_s: number; t1_s: number; ghost: Env; spans: { start_s: number; end_s: number; label?: string }[]; n_raw: number; summary: string }
export interface DemoScoresPayload { type: 'demo.scores'; t0_s: number; t1_s: number; envelope: Env; marks: { t_s: number; v: number; label: string; kind: 'motif' | 'discord' }[]; p5?: number; p95?: number; y_max: number; unit: string; summary: string }
export interface DemoWindowsPayload { type: 'demo.windows'; t0_s: number; t1_s: number; ghost: Env; starts_s: number[]; length_s: number; summary: string }
export interface DemoTextPayload { type: 'demo.text'; lines: string[]; summary: string }
export type DemoPayload = DemoSignalPayload | DemoSlopePayload | DemoStripsPayload | DemoSpansPayload | DemoScoresPayload | DemoWindowsPayload | DemoTextPayload

/** Quantise a slope into k 5 (0 d · 1 D · 2 S · 3 U · 4 u) and k 3 (0 down · 1 same · 2 up). */
export function quantise5(v: number, k: number, sigma = SIGMA) { return v <= -k * sigma ? 0 : v <= -3 * sigma ? 1 : v < 3 * sigma ? 2 : v < k * sigma ? 3 : 4 }
export const toK3 = (q5: number) => (q5 <= 1 ? 0 : q5 === 2 ? 1 : 2)

const SPAN_SOURCE: DemoSignalPayload = { type: 'demo.signal', t0_s: ST.t[0], t1_s: ST.t[ST.t.length - 1], envelope: env(ST.t, ST.raw), y_range: [-1.25, 0.1], summary: 'signal span from Explore · 50 s' }
const SPAN_BASELINE: DemoSignalPayload = { type: 'demo.signal', t0_s: ST.t[0], t1_s: ST.t[ST.t.length - 1], envelope: env(ST.t, ST.out), ghost: env(ST.t, ST.raw.map(v => v + 0.62)), baseline: env(ST.t, ST.base), y_range: [-0.55, 0.5], summary: '7 s rolling median subtracted' }
const SPAN_SLOPE: DemoSlopePayload = { type: 'demo.slope', t0_s: ST.t[0], seg_s: SEG_S, slopes: SEGMENT_SLOPES, sigma: SIGMA, k: 8, summary: 'slope noise σ · d starts at 8σ' }
const SPAN_STRIPS: DemoStripsPayload = { type: 'demo.strips', t0_s: ST.t[0], seg_s: SEG_S, summary: '0.2 s segments → dSAX letters',
  strips: [{ label: 'quantised k 5', alphabet: 5, symbols: SEGMENT_SLOPES.map(v => quantise5(v, 8)) }, { label: 'dSAX k 3', alphabet: 3, symbols: SEGMENT_SLOPES.map(v => toK3(quantise5(v, 8))) }] }
const SPAN_DROPS: DemoSpansPayload = { type: 'demo.spans', t0_s: ST.t[0], t1_s: ST.t[ST.t.length - 1], ghost: env(ST.t, ST.out), n_raw: 23, summary: '23 raw · 6 kept after dedupe',
  spans: KEPT_DROPS.map(d => ({ start_s: ST.t[0] + d.at, end_s: ST.t[0] + d.at + d.dur, label: d.id })) }

/* 6 h span at 1 Hz, drawn at 720 points (P8: decimated for display, n_source kept) */
function hourTraces(seed: number, t0: number, t1: number, n = 720) {
  const t = lin(t0, t1, n)
  const v = syntheticTrace({ n, seed, baseline: 0, noise: 0.05, events: [{ at: 144, depth: 0.35, width: 10 }, { at: 490, depth: 0.32, width: 11 }, { at: 624, depth: 0.2, width: 9 }] }).map((x, i) => x + 0.12 * Math.sin(i / 23) + 0.08 * Math.sin(i / 7.1))
  return { t, v }
}
const H6 = hourTraces(14, 6 * H, 12 * H)
const profile = (() => {
  const rnd = seeded(77)
  const n = 720; const t = lin(6 * H, 12 * H, n)
  const dip = (h: number, c: number, w: number, d: number) => d * Math.exp(-(((h - c) / w) ** 2))
  const v = t.map(s => { const h = s / H; return 8.1 + (rnd() - 0.5) * 0.9 - dip(h, 7.2, 0.05, 5.8) - dip(h, 10.1, 0.05, 5.7) - dip(h, 11.2, 0.04, 3.4) + dip(h, 8.9, 0.05, 6.2) })
  return { t, v }
})()
const MP_SCORES: DemoScoresPayload = { type: 'demo.scores', t0_s: 6 * H, t1_s: 12 * H, envelope: env(profile.t, profile.v, 21600), p5: 5, p95: 12, y_max: 15, unit: 'z-norm distance', summary: 'm 600 s · exclusion m/2 · z-normalised · STUMP',
  marks: [{ t_s: 7.2 * H, v: 2.4, label: 'M1a', kind: 'motif' }, { t_s: 8.9 * H, v: 14.2, label: 'D1', kind: 'discord' }, { t_s: 10.1 * H, v: 2.4, label: 'M1b', kind: 'motif' }, { t_s: 11.2 * H, v: 4.6, label: 'M2', kind: 'motif' }] }
const MP_SOURCE_6H: DemoSignalPayload = { type: 'demo.signal', t0_s: 6 * H, t1_s: 12 * H, envelope: env(H6.t, H6.v, 21600), y_range: [-0.6, 0.45], summary: 'span 6.0–12.0 h · 6 h · 1 Hz' }
export const THRESHOLD_SCORES = (() => {
  const rnd = seeded(5)
  const n = 360; const t = lin(6 * H, 12 * H, n)
  const peaks = [6.75, 7.72, 9.62, 11.1]
  const v = t.map(s => { const h = s / H; let x = 0.9 + (rnd() - 0.5) * 0.9; for (const p of peaks) x += 2.2 * Math.exp(-(((h - p) / 0.02) ** 2)); return +x.toFixed(3) })
  return { t, v, peaks }
})()
const THRESHOLD_SPANS: DemoSpansPayload = { type: 'demo.spans', t0_s: 6 * H, t1_s: 12 * H, ghost: env(THRESHOLD_SCORES.t, THRESHOLD_SCORES.v), n_raw: 5, summary: 'cut 2.5 σ · 5 spans',
  spans: [[6.73, 6.77], [7.70, 7.74], [9.60, 9.64], [9.66, 9.68], [11.08, 11.12]].map(([a, b]) => ({ start_s: a * H, end_s: b * H })) }

const W = hourTraces(9, 0, 721 * H, 900)
const WHOLE_SOURCE: DemoSignalPayload = { type: 'demo.signal', t0_s: 0, t1_s: 721 * H, envelope: env(W.t, W.v, 2_595_600), y_range: [-0.6, 0.45], summary: 'whole channel · 721 h' }
const WHOLE_BASELINE: DemoSignalPayload = { type: 'demo.signal', t0_s: 0, t1_s: 721 * H, envelope: env(W.t, W.v.map((x, i) => x - 0.1 * Math.sin(i / 60))), ghost: env(W.t, W.v), baseline: env(W.t, W.v.map((_, i) => 0.1 * Math.sin(i / 60))), y_range: [-0.6, 0.45], summary: '7 s rolling median subtracted' }

const WIN_STARTS = Array.from({ length: 71 }, (_, i) => 6 * H + i * 300)
const WINDOWS: DemoWindowsPayload = { type: 'demo.windows', t0_s: 6 * H, t1_s: 12 * H, ghost: env(H6.t, H6.v, 21600), starts_s: WIN_STARTS, length_s: 600, summary: '72 windows · 600 s · stride 300 s' }

/* ------------------------------------------------------------------ templates & scenarios ---- */
export type DemoRowStatus = 'cached' | 'stale' | 'new' | 'failed' | 'on cluster' | 'paused'
export interface DemoStepFixture { block: string; params?: Record<string, unknown>; status: DemoRowStatus; caption?: string }
export interface DemoScenario {
  template: string; name: string; note: string; subtitle: string; source: string
  null: { kind: 'toggle' | 'chip'; label: string }
  steps: DemoStepFixture[]
  payloads: Record<string, DemoPayload>                  // block name → last-run payload
  sourcePayload: DemoSignalPayload
  runId: string
  footer: { headline: string; sub: string; surrogateOff?: string }
  hpc?: { stage: number; estimate: string; detail: string; script: string }
  paused?: { runId: string; stage: number; found: string; checks: string; log: [string, string][]; continueNote: string }
}

const DETECTION_STEPS: DemoStepFixture[] = [
  { block: 'demo.baseline_removal', params: { method: 'rolling median', window_s: 7, edges: 'reflect' }, status: 'cached' },
  { block: 'demo.noise_floor', params: { estimator: 'MAD × 1.4826', scope: 'whole span', exclude: 'detected spans · iterate 2×', floor_from: 'this span' }, status: 'cached' },
  { block: 'demo.symbolic_encoding', params: { alphabet: 3, split: 'd/D · U/u', segment_s: 0.2, same_fraction: 0.6, noise_k: 8, edges: 'reflect' }, status: 'stale' },
  { block: 'demo.drop_detection', params: { min_depth_mv: 0.1, min_duration_s: 0.6, merge_window_s: 2.0, trough_tol_sigma: 0.5, dedupe: 'keep best-framed', onset: 'walk back from steepest' }, status: 'stale' },
]

const SLURM = `#SBATCH --job-name=ub_mp_CH4_a7f3  --cpus-per-task=16  --mem=64G  --time=08:00:00
python -m pipeline.run --recipe a7f39c --from-stage 02 --to-stage 02 \\
    --artifacts ./artifacts --manifest cluster_out/manifest.json`

export const DEMO_SCENARIOS: Record<string, DemoScenario> = {
  drop_motifs9: {
    template: 'drop_motifs9', name: 'drop_motifs9', note: 'unsaved', subtitle: 'build here · open a block to tune it · drop_motifs is an illustrative example', source: 'span50',
    null: { kind: 'toggle', label: 'surrogate 200×' }, steps: DETECTION_STEPS, runId: '#128',
    payloads: { 'demo.baseline_removal': SPAN_BASELINE, 'demo.noise_floor': SPAN_SLOPE, 'demo.symbolic_encoding': SPAN_STRIPS, 'demo.drop_detection': SPAN_DROPS },
    sourcePayload: SPAN_SOURCE,
    footer: { headline: 'last run · 6 detections kept', sub: '23 raw · surrogate 2.1 [0–5] per run over 200 · 2.9× above chance', surrogateOff: '23 raw · surrogate off · no chance comparison for this run' },
  },
  mp_span_CH4: {
    template: 'mp_span_CH4', name: 'mp_span_CH4', note: 'run 14 · saved', subtitle: 'single span · a Scores block ends the chain · add a threshold to get spans', source: 'span6h',
    null: { kind: 'chip', label: 'null IAAFT 200×' }, runId: 'run 14',
    steps: [{ block: 'demo.matrix_profile', params: { m_s: 600, exclusion: 'm / 2', algorithm: 'STUMP · exact', normalise: 'z-norm' }, status: 'cached' }],
    payloads: { 'demo.matrix_profile': MP_SCORES, 'demo.threshold': THRESHOLD_SPANS }, sourcePayload: MP_SOURCE_6H,
    footer: { headline: '21,600 values · one per second · 0.2 MB on disk', sub: '3 motif pairs and 1 discord below / above the surrogate p5 · no spans yet — add a threshold' },
  },
  mp_full_channel_CH4: {
    template: 'mp_full_channel_CH4', name: 'mp_full_channel_CH4', note: 'unsaved', subtitle: 'single channel, full length · heavy stages route to the cluster', source: 'whole',
    null: { kind: 'toggle', label: 'surrogate 200×' }, runId: '—',
    steps: [
      { block: 'demo.baseline_removal', params: { method: 'rolling median', window_s: 7, edges: 'reflect' }, status: 'cached' },
      { block: 'demo.matrix_profile', params: { m_s: 600, algorithm: 'STUMPY' }, status: 'on cluster', caption: 'm 600 · STUMPY' },
      { block: 'demo.threshold', params: { cut_sigma: 2.5 }, status: 'new', caption: 'cut discords above 2.5 σ' },
      { block: 'demo.span_dedupe', params: { iou: 0.5 }, status: 'new', caption: 'IoU ≥ 0.5 merge · keep best' },
    ],
    payloads: { 'demo.baseline_removal': WHOLE_BASELINE }, sourcePayload: WHOLE_SOURCE,
    footer: { headline: 'No result yet', sub: 'stage 02 is over the local ceiling · 03 → 04 wait for its profile' },
    hpc: { stage: 1, estimate: '≈ 6.4 h', detail: 'estimate 2,595,600 samples × m 600 · local limit 20 min (Settings › Compute & HPC) · no fan-out', script: SLURM },
  },
  sax_vs_mp: {
    template: 'sax_vs_mp', name: 'sax_vs_mp', note: 'a-0098 · paused', subtitle: 'single channel, full length · heavy stages route to the cluster', source: 'whole',
    null: { kind: 'toggle', label: 'surrogate 200×' }, runId: 'a-0098',
    steps: [
      { block: 'demo.baseline_removal', params: { method: 'rolling median', window_s: 7, edges: 'reflect' }, status: 'cached' },
      { block: 'demo.matrix_profile', params: { m_s: 600, algorithm: 'STUMPY' }, status: 'paused', caption: 'm 600 · STUMPY' },
      { block: 'demo.threshold', params: { cut_sigma: 2.5 }, status: 'new', caption: 'cut discords above 2.5 σ' },
      { block: 'demo.span_dedupe', params: { iou: 0.5 }, status: 'new', caption: 'IoU ≥ 0.5 merge · keep best' },
    ],
    payloads: { 'demo.baseline_removal': WHOLE_BASELINE, 'demo.matrix_profile': { ...MP_SCORES, t0_s: 0, t1_s: 721 * H, envelope: env(W.t, W.v.map((x, i) => 8 + x * 3 + (i % 97 === 0 ? -5 : 0)), 2_595_481), marks: [], summary: 'profile from the cluster · 2,595,481 values' }, 'demo.threshold': { ...THRESHOLD_SPANS, t0_s: 0, t1_s: 721 * H, ghost: env(W.t, W.v), spans: [[40, 41], [188, 189], [402, 403.5], [611, 612]].map(([a, b]) => ({ start_s: a * H, end_s: b * H })), summary: '4 spans above 2.5 σ' }, 'demo.span_dedupe': { ...THRESHOLD_SPANS, t0_s: 0, t1_s: 721 * H, ghost: env(W.t, W.v), spans: [[40, 41], [188, 189], [402, 403.5]].map(([a, b]) => ({ start_s: a * H, end_s: b * H })), summary: '3 spans kept after IoU ≥ 0.5 merge' } },
    sourcePayload: WHOLE_SOURCE,
    footer: { headline: 'Paused at 02', sub: 'result in place · continue from 03' },
    paused: { runId: 'a-0098', stage: 1, found: 'Result found in ./PROFILES · 1.9 GB · 14:31', checks: "recipe hash a7f39c2e ✓ · length 2,595,481 ✓ · values finite ✓ · made with this run's m = 600 ✓",
      log: [['14 Sep 08:05', 'paused · SLURM script created'], ['14 Sep 09:10', 'marked submitted · 11:40 marked running'], ['14 Sep 14:31', 'result found in ./PROFILES · checks passed']], continueNote: 'Continue runs 03 → 04 locally (≈ 40 s)' },
  },
  spiketrain_cnn_CH4: {
    template: 'spiketrain_cnn_CH4', name: 'spiketrain_cnn_CH4', note: 'run 14 · saved', subtitle: 'a registered model scores each window · its calibration becomes the next stage\'s recommended cut', source: 'span6h',
    null: { kind: 'chip', label: 'null label shuffle 200×' }, runId: 'run 14',
    steps: [
      { block: 'demo.sliding_windows', params: { length_s: 600, stride_s: 300 }, status: 'cached' },
      { block: 'demo.model_stage', params: { model: 'cnn_windows_v2 · manual · v2', batch: 64, pass_class: 'spike-train' }, status: 'new' },
      { block: 'demo.threshold', params: { cut: 0.62 }, status: 'new', caption: 'cut 0.62 · from calibration' },
    ],
    payloads: { 'demo.sliding_windows': WINDOWS, 'demo.threshold': THRESHOLD_SPANS }, sourcePayload: MP_SOURCE_6H,
    footer: { headline: 'No result yet', sub: '02 has not run on this span · ≈ 40 s local' },
  },
}

/* Templates for the Import modal (frame chain-1c) — steps reference demo blocks. */
export interface DemoTemplate {
  name: string; kind: 'detection' | 'interrogation' | 'training'; version: string; date: string; needs: 'Signal' | 'SpanSet'; blocks: number
  note: string; noteTone: 'green' | 'grey' | 'amber'; fits: boolean; reason?: string; recipe: string; code: string
  steps: { block: string; params?: Record<string, unknown>; summary: string }[]; sideInputs: string; wholeChannel?: boolean
}
export const DEMO_TEMPLATES: DemoTemplate[] = [
  { name: 'drop_motifs9', kind: 'detection', version: 'v3', date: '2 Sept', needs: 'Signal', blocks: 4, note: 'exported from run #128', noteTone: 'green', fits: true, recipe: 'a7f39c', code: '834c200', sideInputs: 'none in this template',
    steps: DETECTION_STEPS.map((s, i) => ({ block: s.block, params: s.params, summary: ['rolling median 7 s', 'cut 8σ', 'k 3 · segment 0.2 s', 'depth ≥ 0.10 mV · merge 2 s'][i] })) },
  { name: 'sharkfin_v2', kind: 'detection', version: 'v1', date: '9 Sept', needs: 'Signal', blocks: 3, note: 'exemplar: rebind on apply', noteTone: 'green', fits: true, recipe: '3be1d0', code: '834c200', sideInputs: 'exemplar E-0102 · rebind on apply',
    steps: [{ block: 'demo.baseline_removal', summary: 'rolling median 7 s' }, { block: 'demo.matrix_profile', params: { m_s: 21 }, summary: 'm 21 s · exemplar E-0102' }, { block: 'demo.threshold', summary: 'cut 2.5 σ' }] },
  { name: 'banded_sax_lp', kind: 'detection', version: 'v2', date: '28 Aug', needs: 'Signal', blocks: 5, note: 'bandpass 0.01–0.1 Hz first', noteTone: 'green', fits: true, recipe: '0be4a1', code: '7d21f0e', sideInputs: 'none in this template',
    steps: [{ block: 'demo.bandpass', summary: '0.01–0.1 Hz · order 4' }, { block: 'demo.baseline_removal', summary: 'rolling median 7 s' }, { block: 'demo.noise_floor', summary: 'cut 8σ' }, { block: 'demo.symbolic_encoding', summary: 'k 3 · segment 0.2 s' }, { block: 'demo.drop_detection', summary: 'depth ≥ 0.10 mV' }] },
  { name: 'slope_interrogation', kind: 'interrogation', version: 'v4', date: '12 Sept', needs: 'SpanSet', blocks: 2, note: 'needs a SpanSet source', noteTone: 'grey', fits: false, reason: 'needs a SpanSet source · this source is a Signal span', recipe: '5d0c9f', code: '834c200', sideInputs: 'none',
    steps: [{ block: 'demo.resolve_slope', summary: 'onset: walk back from steepest' }, { block: 'demo.aggregate', summary: 'histogram · scaling' }] },
  { name: 'cnn_windows_v2', kind: 'training', version: 'v2', date: '20 Aug', needs: 'Signal', blocks: 5, note: 'expects a whole channel · this span is 50 s', noteTone: 'amber', fits: true, wholeChannel: true, recipe: '91ac02', code: '834c200', sideInputs: 'window verdicts (labels)',
    steps: [{ block: 'demo.sliding_windows', summary: '600 s · stride 300 s' }, { block: 'demo.window_matrix', summary: 'catch22 + entropy' }, { block: 'demo.hier_cluster', summary: 'ward · k 3' }, { block: 'demo.gramian', summary: 'gasf + gadf · 64 px' }, { block: 'demo.model', summary: 'cnn · labels from clusters' }] },
]

/* ------------------------------------------------------------------ run history (frame chain-1b) ---- */
export interface DemoHistoryRun {
  id: number; name: string; hash: string; chain: { label: string; tone?: 'amber' | 'purple' }[]; source: string; when: string
  sourceKind: 'Signal' | 'SpanSet' | 'surrogate'; terminal: 'SpanSet' | 'Scores' | 'Features' | 'Model'; status: 'completed' | 'running' | 'failed'
  recording: string; applyReason?: string; diff?: { text: string; detail: string; source: string }; open: string; template?: string
  params?: Record<string, Record<string, unknown>>
}
const HIST_HEAD: DemoHistoryRun[] = [
  { id: 128, name: 'drop_motifs9', hash: 'a7f39c', chain: [{ label: '01' }, { label: '02' }, { label: '03' }, { label: '04' }], source: 'Signal span · CH4', when: '2 Sept', sourceKind: 'Signal', terminal: 'SpanSet', status: 'completed', recording: 'M2_aug fs1', open: 'analyse/chain?template=drop_motifs9&state=default', template: 'drop_motifs9' },
  { id: 131, name: 'drop_motifs9 · 6σ floor', hash: 'c21e08', chain: [{ label: '01' }, { label: '02' }, { label: '03', tone: 'amber' }, { label: '04' }], source: 'Signal span · CH4', when: '3 Sept', sourceKind: 'Signal', terminal: 'SpanSet', status: 'completed', recording: 'M2_aug fs1', open: 'analyse/chain?template=drop_motifs9&state=default', template: 'drop_motifs9',
    diff: { text: 'differs from the current chain in 1 parameter', detail: '02 Noise floor · cut 8σ → 6σ', source: 'source differs: none — same span' }, params: { 'demo.symbolic_encoding': { noise_k: 6 } } },
  { id: 129, name: 'drop_motifs9 · surrogate', hash: 'a7f39c-s', chain: [{ label: 'S', tone: 'purple' }, { label: '01' }, { label: '02' }, { label: '03' }, { label: '04' }], source: 'surrogate of #128', when: '2 Sept', sourceKind: 'surrogate', terminal: 'SpanSet', status: 'completed', recording: 'M2_aug fs1', open: 'analyse/chain?template=drop_motifs9&state=default', template: 'drop_motifs9' },
  { id: 97, name: 'banded_sax_lp', hash: '0be4a1', chain: [{ label: 'BP', tone: 'amber' }, { label: '01' }, { label: '02' }, { label: '04' }], source: 'Signal span · CH3', when: '28 Aug', sourceKind: 'Signal', terminal: 'SpanSet', status: 'completed', recording: 'M2_aug fs1', open: 'analyse/chain?template=banded_sax_lp', template: 'banded_sax_lp' },
  { id: 140, name: 'F-03 slope interrogation', hash: '5d0c9f', chain: [{ label: '01' }, { label: '02' }], source: 'Library family', when: '12 Sept', sourceKind: 'SpanSet', terminal: 'Features', status: 'completed', recording: 'M2_aug fs1', applyReason: 'needs a SpanSet source · this chain starts from Signal', open: 'analyse/interrogation' },
  { id: 133, name: 'mp_full_channel_CH4', hash: '9e7722', chain: [{ label: '01' }, { label: 'MP' }, { label: 'TH' }], source: 'whole channel · CH4', when: '10 Sept', sourceKind: 'Signal', terminal: 'SpanSet', status: 'running', recording: 'M2_aug fs1', applyReason: 'still on the cluster · import its manifest first', open: 'analyse/chain?template=mp_full_channel_CH4&state=default' },
]
const TAIL_NAMES = ['drop_motifs9 · k 5', 'sharkfin_v2', 'mp_discord_v3', 'drop_motifs9 · 0.4 s segments', 'banded_sax_lp · order 2', 'spike_shape_v1', 'mp_span_CH4', 'drop_motifs9 · merge 2.4 s']
export const RUN_HISTORY: DemoHistoryRun[] = [
  ...HIST_HEAD,
  ...Array.from({ length: 28 }, (_, i): DemoHistoryRun => {
    const nm = TAIL_NAMES[i % TAIL_NAMES.length]; const rec = i % 5 === 3 ? 'M3_jul' : 'M2_aug fs1'
    const detection = !nm.startsWith('spike_shape') && !nm.startsWith('mp_span')
    return { id: 127 - i, name: nm, hash: (0xa1b2c3 - i * 4099).toString(16).slice(0, 6), chain: detection ? [{ label: '01' }, { label: '02' }, { label: '03' }, { label: '04' }] : [{ label: '01' }], source: rec === 'M3_jul' ? 'Signal span · CH2' : `Signal span · CH${(i % 8) + 1}`,
      when: `${Math.max(1, 30 - i)} Aug`, sourceKind: 'Signal', terminal: detection ? 'SpanSet' : 'Scores', status: i % 9 === 4 ? 'failed' : 'completed', recording: rec, open: 'analyse/chain?template=drop_motifs9&state=default', template: detection ? 'drop_motifs9' : undefined,
      applyReason: i % 9 === 4 ? 'failed at 04 · nothing to apply' : undefined }
  }),
]

/* ------------------------------------------------------------------ block page fixtures ---- */
export const SWEEP = [
  { k: 2, observed: 118, null: 96, ci: [66, 124], ratio: '1.2×' }, { k: 4, observed: 64, null: 40, ci: [28, 52], ratio: '1.6×' },
  { k: 6, observed: 38, null: 14, ci: [9, 19], ratio: '2.7×' }, { k: 8, observed: 23, null: 3, ci: [1, 5], ratio: '7.7×' },
  { k: 10, observed: 14, null: 1, ci: [0, 2], ratio: '14.0×' }, { k: 12, observed: 9, null: 0.5, ci: [0, 1], ratio: '18.0×' },
  { k: 16, observed: 4, null: 0, ci: [0, 0], ratio: 'no null hits' }, { k: 20, observed: 2, null: 0, ci: [0, 0], ratio: 'no null hits' },
]
export const TRY_WINDOWS = [
  { window: 3, caption: 'depth kept 62 %' }, { window: 7, caption: 'depth kept 97 %' }, { window: 15, caption: 'drift left 0.9 µV/s' },
]
export const DOWNSTREAM_PREVIEW = [
  { stage: '02 Noise floor', metric: 'slope noise σ', before: '0.0112', after: '0.00958 mV/s', better: true },
  { stage: '04 Drop detection', metric: 'raw detections', before: '21', after: '23', better: false },
  { stage: '04 Drop detection', metric: 'kept after dedupe', before: '6', after: '6', better: false },
  { stage: '04 Drop detection', metric: 'mean depth', before: '0.27', after: '0.31 mV', better: true },
]
export const NOISE_FLOOR = {
  sigma: SIGMA, ci: [0.00911, 0.01004] as [number, number], bootstrap: 500, drift_pct: 11, recording_floor: 0.0101, surrogate: { mean: 0.00963, lo: 0.0089, hi: 0.0104, n: 200 },
  rolling: Array.from({ length: 80 }, (_, i) => +(SIGMA * (1 + 0.11 * Math.sin(i / 3.3) * (seeded(i + 3)() - 0.2))).toFixed(5)),
}
export const REMOVED = [{ label: '6 kept', n: 6, colour: 'var(--blue)' }, { label: '11 duplicates of a better-framed copy (dedupe)', n: 11, colour: 'var(--amber)' }, { label: '4 below 0.10 mV floor', n: 4, colour: '#a3a3a3' }, { label: '2 shorter than 0.6 s', n: 2, colour: '#d4d4d4' }]
export const DETECTION_TRACE = { t: ST.t, out: ST.out, raw: ST.raw, base: ST.base }
export const MP_BLOCK = {
  signal: H6, profile, top: [
    { id: 'M1', at: '7.20 h ↔ 10.10 h', t_h: 7.2, nn_h: 10.1, d: 2.4, p: 'p < 0.01', sig: true },
    { id: 'M2', at: '10.83 h ↔ 6.52 h', t_h: 10.83, nn_h: 6.52, d: 4.6, p: 'p 0.04', sig: true },
    { id: 'M3', at: '8.28 h ↔ 11.37 h', t_h: 8.28, nn_h: 11.37, d: 5.3, p: 'n.s. 0.21', sig: false },
    { id: 'D1', at: '8.90 h', t_h: 8.9, nn_h: null, d: 14.2, p: 'p < 0.01', sig: true },
  ],
  mSweep: [{ m: 60, real: 1, null: 0.6 }, { m: 120, real: 2, null: 0.5 }, { m: 300, real: 3, null: 0.5 }, { m: 600, real: 3, null: 0.4 }, { m: 1200, real: 2, null: 0.4 }, { m: 1800, real: 1, null: 0.3 }],
  below_p5: '8.4 % below p5 · 5 % expected',
}
export const THRESHOLD_BLOCK = {
  scores: THRESHOLD_SCORES,
  spans: [
    { start: '6.74 h', duration: '140 s', peak: '3.41σ', merged: 2 }, { start: '7.72 h', duration: '80 s', peak: '3.02σ', merged: 1 },
    { start: '9.61 h', duration: '150 s', peak: '3.55σ', merged: 3 }, { start: '9.67 h', duration: '60 s', peak: '2.61σ', merged: 1 },
    { start: '11.10 h', duration: '90 s', peak: '2.96σ', merged: 1 },
  ],
  nullPerRun: '0.4 [0–2]',
}
export const MODEL_BLOCK = {
  classes: [{ name: 'spike-train', colour: '#5856D6' }, { name: 'burst', colour: '#E85AAD' }, { name: 'slow-drift', colour: '#30B0C7' }, { name: 'plateau', colour: '#A2845E' }],
  tracks: (() => { const out: number[][] = []; for (let c = 0; c < 4; c++) { const r = seeded(40 + c); out.push(Array.from({ length: 72 }, (_, i) => +(0.08 + r() * 0.08 + ([[14, 15, 43, 44], [30], [52, 53, 54], []][c].includes(i) ? 0.62 + r() * 0.2 : 0)).toFixed(3))) } return out })(),
  card: [['name', 'cnn_windows_v2 · manual · v2'], ['registered', '30 Aug · Models › Registry'], ['classes', 'spike-train · burst · slow-drift · plateau'], ['test F1', '0.66 on its held-out test block'], ['trained on', 'M2_aug fs1 · 3 ch · never these windows'], ['calibration', 's-train 0.62 · burst 0.71 · s-drift 0.40 · plat 0.55']] as [string, string][],
  top: [['w-15', '7.25 h', 'spike-train', '0.91', 'burst 0.06'], ['w-44', '9.67 h', 'spike-train', '0.88', 'slow-drift 0.07'], ['w-14', '7.17 h', 'spike-train', '0.79', 'burst 0.12'], ['w-43', '9.58 h', 'spike-train', '0.72', 'plateau 0.14'], ['w-30', '8.50 h', 'burst', '0.84', 'spike-train 0.10']],
  hist: [42, 34, 22, 12, 7, 5, 4, 3, 3, 3, 2, 2, 3, 4, 6, 5, 5, 4, 6],
  nullHist: [45, 36, 20, 11, 6, 4, 3, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1],
}
export const FAMILY_COLOUR = FAMILY_COLOURS
export const HELD_OUT_SOURCE = 'M4_aug · CH4_A2'
export const DEMO_RUN_IDS = ANALYSE_RUNS

/* ------------------------------------------------------------------ glyph registry (frame chain-6b) ---- */
export const GLYPH_GROUPS: { key: DemoBlock['glyph_group']; title: string }[] = [
  { key: 'preprocess', title: 'preprocess · Signal → Signal' },
  { key: 'encode', title: 'encode · → Encoding' },
  { key: 'scores', title: 'scores & detect · → Scores / SpanSet' },
  { key: 'interrogate', title: 'interrogate · windows · cluster · model' },
]
