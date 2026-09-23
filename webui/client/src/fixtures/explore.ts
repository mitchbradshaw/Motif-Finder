/* Explore fixtures — the spec §0 placeholder canon as the Explore frames draw it (inventory
 * webui/pages/inventory/explore.md). Demo data only: nothing here is read from the database, traces are
 * synthetic, every generator is seeded so screenshots are stable. Components never import this file —
 * they read it through src/api/explore.ts (demo(...) → Sourced<T>). */
import { FAMILY_COLOURS, HELD_OUT_KEY, RECORDINGS, seeded, syntheticTrace } from './canon'

/* ------------------------------------------------------------------ shared vocab ---- */
export type Verdict = 'seed' | 'interesting' | 'not_interesting' | 'artifact' | 'unsure'
export const VERDICT_KEYS: Verdict[] = ['seed', 'interesting', 'not_interesting', 'artifact', 'unsure']
/** §5.1 rail list (frame explore-1). Differs from canon MORPHOLOGY_TAGS on purpose — see fog F5. */
export const RAIL_TAGS = ['sharkfin', 'spike-train', 'slow-drift', 'burst', 'plateau', 'biphasic']
export const METHODS = ['matrix profile', 'SAX + threshold', 'MASS seed', 'drop detector', 'CNN classifier', 'spike detector', 'change-point']

/** Canon channel ids, mirroring the live bridge order where it overlaps (fs1 1–16, fs2 17–32, M4 49–64). */
export interface CanonChannelRef { id: number; name: string; recordingKey: string; file: string }
const M_CH = RECORDINGS[0].channels
export const CANON_CHANNELS: CanonChannelRef[] = [
  ...M_CH.map((name, i) => ({ id: i + 1, name, recordingKey: 'M2_aug_fs1', file: 'M2_aug_concat_fs1.mat' })),
  ...M_CH.map((name, i) => ({ id: i + 17, name, recordingKey: 'M2_aug_fs2', file: 'M2_aug_concat_fs2.mat' })),
  ...RECORDINGS[2].channels.map((name, i) => ({ id: i + 33, name, recordingKey: 'M3_jul', file: 'M3_jul.mat' })),
  ...RECORDINGS[3].channels.map((name, i) => ({ id: i + 41, name, recordingKey: 'L_LM_Jul26_J', file: 'L_LM_Jul_26_J.csv' })),
  ...M_CH.map((name, i) => ({ id: i + 49, name, recordingKey: HELD_OUT_KEY, file: 'M4_aug_concat_fs1.mat' })),
]
export const HELD_OUT_REASON = 'M4_aug_concat_fs1.mat is held out and locked (D6): every workspace refuses it — nothing from it is drawn, trained on or scored.'

/* ------------------------------------------------------------------ corpus ---- */
export interface CorpusChannelDemo { name: string; tagCounts: Record<string, number>; reviewed: boolean[]; reviewedPct: number }
export interface CorpusRunRef { id: string; name: string; method: string }
export interface CorpusDemo { runs: CorpusRunRef[]; methods: string[]; tags: string[]; channels: CorpusChannelDemo[] }

/** sharkfin across the 16 M2_aug channels: 412 spans on 11 of 16 channels (frame explore-1 foot). */
const SHARKFIN_16 = [48, 0, 61, 64, 0, 35, 22, 8, 41, 0, 38, 30, 0, 29, 36, 0]

const RUN_NAMES = ['drop_motifs9', 'drop_motifs9 · surrogate', 'drop_motifs9 · 6σ floor', 'seed search E-0102', 'mp_drops_v3', 'banded_sax_lp', 'F-03 slope interrogation', 'sharkfin_v2', 'mp_discord_v3', 'spike_shape_v1', 'drop_cnn_v1', 'sharkfin_cnn_v2']
export function corpusDemo(fileKey: string, channelNames: string[], bins: number): CorpusDemo {
  const rnd = seeded(fileKey.length * 131 + bins)
  const runs: CorpusRunRef[] = [
    { id: '#128', name: 'drop_motifs9', method: 'matrix profile' }, { id: '#129', name: 'drop_motifs9 · surrogate', method: 'matrix profile' },
    { id: '#131', name: 'drop_motifs9 · 6σ floor', method: 'SAX + threshold' }, { id: 'r-0415', name: 'seed search E-0102', method: 'MASS seed' },
    { id: 'r-0412', name: 'mp_drops_v3', method: 'drop detector' }, { id: '#97', name: 'banded_sax_lp', method: 'CNN classifier' },
  ]
  for (let i = runs.length; i < 34; i++) runs.push({ id: i % 2 ? `#${140 + i}` : `r-04${20 + i}`, name: RUN_NAMES[i % RUN_NAMES.length], method: METHODS[i % METHODS.length] })
  const channels = channelNames.map((name, ci) => {
    const tagCounts: Record<string, number> = {}
    for (const t of RAIL_TAGS) tagCounts[t] = t === 'sharkfin' && channelNames.length === 16 ? SHARKFIN_16[ci] : rnd() < 0.35 ? 0 : Math.round(rnd() * 70)
    let run = rnd() < 0.5
    const reviewed = Array.from({ length: bins }, () => { if (rnd() < 0.12) run = !run; return run })
    const reviewedPct = Math.round((reviewed.filter(Boolean).length / Math.max(1, bins)) * 100)
    return { name, tagCounts, reviewed, reviewedPct }
  })
  return { runs, methods: METHODS, tags: RAIL_TAGS, channels }
}

/* ------------------------------------------------------------------ signal ---- */
export interface DemoRun { id: string; name: string; method: string; template: string; surrogate: boolean; colour: string; count: number }
export interface AnnotationRow {
  id: number; start: number; end: number; verdict: Verdict; tags: string[]; source: 'manual_ui' | 'imported_10min'; note: string
  element: string; quality: string; structure: string; status: string; spikeTrainLength: string
}
export interface DetectionRow {
  id: number; runId: string; runName: string; method: string; start: number; end: number; score: number
  adjudication: Verdict | 'unadjudicated'; family: { id: string; d: number } | null; tag?: string
}
export interface SignalDemo {
  channelId: number; channelName: string; file: string; fs: number; viewport: [number, number]
  runs: DemoRun[]; defaultRuns: string[]; annotations: AnnotationRow[]; detections: DetectionRow[]
  motifDetectionId: number; spanTags: string[]; spanNote: string; medoid: number[]; defaultSelectedAnnotations: number[]; defaultSelectedDetections: number[]
}

export const SIGNAL_RUNS: DemoRun[] = [
  { id: '#128', name: 'drop_motifs9', method: 'matrix profile', template: 'drop_motifs9', surrogate: false, colour: '#0A84FF', count: 412 },
  { id: '#129', name: 'drop_motifs9 · surrogate', method: 'matrix profile', template: 'drop_motifs9', surrogate: true, colour: '#8E8E93', count: 38 },
  { id: '#131', name: 'drop_motifs9 · 6σ floor', method: 'SAX + threshold', template: 'drop_motifs9', surrogate: false, colour: '#64D2FF', count: 306 },
  { id: 'r-0415', name: 'seed search E-0102', method: 'MASS seed', template: 'seeded search', surrogate: false, colour: '#BF5AF2', count: 92 },
  { id: 'r-0412', name: 'mp_drops_v3', method: 'drop detector', template: 'mp_drops_v3', surrogate: false, colour: '#FF9F0A', count: 410 },
  { id: '#97', name: 'banded_sax_lp', method: 'CNN classifier', template: 'banded_sax_lp', surrogate: false, colour: '#8E8E93', count: 26 },
]

export const FILTER_VOCAB = {
  source: ['manual_ui', 'imported_10min'],
  element: ['single spike', 'spike train', 'drop', 'oscillation'],
  quality: ['clean', 'noisy', 'clipped'],
  structure: ['isolated', 'repeating', 'nested'],
  status: ['draft', 'reviewed', 'exported'],
  spikeTrainLength: ['1', '2–5', '6+'],
  durationBand: [{ value: 'short', label: 'short (< 60 s)' }, { value: 'medium', label: 'medium (60–900 s)' }, { value: 'long', label: 'long (> 900 s)' }],
  families: ['F-03', 'F-04', 'F-07', 'F-11'],
}

const NOTES = ['clean onset', 'exemplar for F-03', 'shared ground w/ CH3', 'double notch', 'slow recovery', 'check ground', 'recurs after 12 h', '']
function pick<T>(r: () => number, xs: readonly T[]): T { return xs[Math.floor(r() * xs.length) % xs.length] }

function buildAnnotations(): AnnotationRow[] {
  const r = seeded(708)
  const base = (id: number, start: number, dur: number, verdict: Verdict, tags: string[], source: AnnotationRow['source'], note: string): AnnotationRow => ({
    id, start, end: start + dur, verdict, tags, source, note,
    element: pick(r, FILTER_VOCAB.element), quality: pick(r, FILTER_VOCAB.quality), structure: pick(r, FILTER_VOCAB.structure),
    status: pick(r, FILTER_VOCAB.status), spikeTrainLength: pick(r, FILTER_VOCAB.spikeTrainLength),
  })
  // frame explore-2b rows (sample indices at 1 Hz), the six smallest starts
  const rows: AnnotationRow[] = [
    base(1835, 50400, 600, 'interesting', ['sharkfin'], 'manual_ui', 'clean onset'),
    base(1578, 53400, 600, 'interesting', ['sharkfin', 'burst'], 'manual_ui', ''),
    base(328, 56600, 600, 'seed', ['sharkfin'], 'manual_ui', 'exemplar for F-03'),
    base(84, 58200, 600, 'interesting', [], 'imported_10min', ''),
    base(9753, 61000, 600, 'not_interesting', [], 'imported_10min', ''),
    base(7102, 63600, 600, 'artifact', [], 'imported_10min', 'shared ground w/ CH3'),
  ]
  // 702 more; exactly 410 of them match verdict=interesting · duration medium · tags ∋ sharkfin → 412 of 708
  const n = 702
  const matching = new Set<number>()
  const order = Array.from({ length: n }, (_, i) => i)
  for (let i = n - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [order[i], order[j]] = [order[j], order[i]] }
  order.slice(0, 410).forEach(i => matching.add(i))
  const used = new Set(rows.map(x => x.id))
  let nextId = 20
  for (let i = 0; i < n; i++) {
    while (used.has(nextId)) nextId++
    const id = nextId; used.add(id); nextId += 1 + Math.floor(r() * 23)
    const start = 65000 + Math.round(i * 3590 + r() * 1800)
    if (matching.has(i)) {
      const manual = r() < 0.55
      rows.push(base(id, start, manual ? 120 + Math.round(r() * 700) : 600, 'interesting', r() < 0.3 ? ['sharkfin', 'burst'] : ['sharkfin'], manual ? 'manual_ui' : 'imported_10min', manual ? pick(r, NOTES) : ''))
    } else {
      const breakKind = Math.floor(r() * 3)
      const verdict: Verdict = breakKind === 0 ? pick(r, ['seed', 'not_interesting', 'artifact', 'unsure'] as Verdict[]) : 'interesting'
      const dur = breakKind === 1 ? pick(r, [30, 45, 1200, 1800]) : 600
      const tags = breakKind === 2 ? pick(r, [[], ['burst'], ['biphasic'], ['slow-drift']]) : pick(r, [['sharkfin'], [], ['burst']])
      const manual = r() < 0.3
      rows.push(base(id, start, dur, verdict, tags, manual ? 'manual_ui' : 'imported_10min', manual ? pick(r, NOTES) : ''))
    }
  }
  return rows
}

function buildDetections(): DetectionRow[] {
  const r = seeded(1284)
  const run = (id: string) => SIGNAL_RUNS.find(x => x.id === id)!
  const det = (id: number, runId: string, start: number, end: number, score: number, adjudication: DetectionRow['adjudication'], family: DetectionRow['family'], tag?: string): DetectionRow =>
    ({ id, runId, runName: run(runId).name, method: run(runId).method, start, end, score, adjudication, family, tag })
  // frame explore-2c rows + the motif the frames open (MOTIF_233) + one band per other run inside the frame's span
  const rows: DetectionRow[] = [
    det(412, '#128', 995112, 995134, 0.91, 'unadjudicated', { id: 'F-03', d: 0.19 }),
    det(413, '#128', 995410, 995436, 0.88, 'interesting', { id: 'F-03', d: 0.22 }),
    det(418, '#128', 996020, 996041, 0.84, 'unadjudicated', null),
    det(421, '#131', 996300, 996318, 0.77, 'artifact', { id: 'F-07', d: 0.41 }),
    det(430, '#131', 997005, 997027, 0.71, 'unadjudicated', { id: 'F-03', d: 0.30 }),
    det(433, '#128', 997440, 997466, 0.66, 'not_interesting', null),
    det(437, '#128', 998323, 998345, 0.64, 'unadjudicated', { id: 'F-03', d: 0.19 }, 'sharkfin'),
    det(439, '#129', 999100, 999124, 0.41, 'unadjudicated', null),
    det(440, 'r-0415', 1000300, 1000322, 0.58, 'unadjudicated', { id: 'F-03', d: 0.27 }),
    det(441, 'r-0412', 999500, 999530, 0.52, 'unadjudicated', null),
  ]
  // the rest, outside the frame's span; every score < 0.66 so cleared filters sorted by score show the frame's six rows first.
  // #128 carries 91 more matrix-profile rows with score in [0.60, 0.655] → 96 of 1,284 match method=matrix profile · score ≥ 0.60
  const remaining: Record<string, number> = { '#128': 412 - 5, '#129': 38 - 1, '#131': 306 - 2, 'r-0415': 92 - 1, 'r-0412': 410 - 1, '#97': 26 }
  const pool: string[] = []
  for (const [k, c] of Object.entries(remaining)) for (let i = 0; i < c; i++) pool.push(k)
  for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [pool[i], pool[j]] = [pool[j], pool[i]] }
  let highMp = 91
  const used = new Set(rows.map(x => x.id))
  let nextId = 1000
  pool.forEach((runId, i) => {
    let start = Math.round((i / pool.length) * 2560000 + r() * 1500) + 2000
    if (start > 985000 && start < 1012000) start += 30000
    const dur = 18 + Math.floor(r() * 13)
    let score: number
    if (runId === '#128' && highMp > 0 && r() < 0.35) { score = 0.60 + r() * 0.055; highMp-- }
    else score = 0.2 + r() * 0.39
    const u = r()
    const adjudication: DetectionRow['adjudication'] = u < 0.6 ? 'unadjudicated' : u < 0.75 ? 'interesting' : u < 0.87 ? 'not_interesting' : u < 0.95 ? 'artifact' : 'unsure'
    const f = r()
    const family = f < 0.45 ? { id: 'F-03', d: +(0.15 + r() * 0.3).toFixed(2) } : f < 0.55 ? { id: 'F-07', d: +(0.3 + r() * 0.3).toFixed(2) } : f < 0.6 ? { id: 'F-11', d: +(0.35 + r() * 0.25).toFixed(2) } : null
    while (used.has(nextId)) nextId++
    rows.push(det(nextId, runId, start, start + dur, +score.toFixed(3), adjudication, family))
    used.add(nextId); nextId++
  })
  // top up any #128 high-score rows the random pass left unassigned (deterministic, keeps the count exact)
  for (const d of rows) { if (highMp <= 0) break; if (d.runId === '#128' && d.id >= 1000 && d.score < 0.6) { d.score = +(0.6 + (d.id % 50) / 1000).toFixed(3); highMp-- } }
  return rows
}

let signalCache: SignalDemo | null = null
/** Fixture for the canon channel CH4_A2 of M2_aug fs1 (id 4); null for any other channel. */
export function signalDemo(channelId: number): SignalDemo | null {
  if (channelId !== 4) return null
  if (!signalCache) {
    signalCache = {
      channelId: 4, channelName: 'CH4_A2', file: 'M2_aug_concat_fs1.mat', fs: 1, viewport: [995040, 1002240],
      runs: SIGNAL_RUNS, defaultRuns: ['#128', '#131', 'r-0415'], annotations: buildAnnotations(), detections: buildDetections(),
      motifDetectionId: 437, spanTags: ['sharkfin', 'burst'], spanNote: 'recurs on CH3 at similar amplitude — check ground',
      medoid: syntheticTrace({ n: 22, seed: 303, baseline: 0, noise: 0.012, events: [{ at: 0, depth: 0.34, width: 21, shape: 'sharkfin' }] }),
      defaultSelectedAnnotations: [1835, 1578], defaultSelectedDetections: [412, 413],
    }
  }
  return signalCache
}

export const SHORTCUTS: { column: string; rows: { keys: string[]; label: string }[] }[] = [
  { column: 'Navigate', rows: [{ keys: ['← →'], label: 'pan the span' }, { keys: ['+', '−'], label: 'zoom in / out' }, { keys: ['F'], label: 'fit span to view' }, { keys: ['[', ']'], label: 'previous / next motif' }, { keys: ['Home'], label: 'back to corpus' }] },
  { column: 'Select', rows: [{ keys: ['drag'], label: 'move the span on the channel' }, { keys: ['Shift + drag'], label: 'resize from nearest handle' }, { keys: ['Alt + click'], label: 'select a motif marker' }, { keys: ['Ctrl + A'], label: 'select all motifs in view' }, { keys: ['Esc'], label: 'clear selection' }] },
  { column: 'Hand off', rows: [{ keys: ['R'], label: 'take span for Review' }, { keys: ['Shift + R'], label: 'review selected motif' }, { keys: ['A'], label: 'send span to Analyse' }, { keys: ['T'], label: 'add tag' }, { keys: ['C'], label: 'cross-channel from this span' }] },
  { column: 'Panels', rows: [{ keys: ['D'], label: 'toggle this drawer' }, { keys: ['/'], label: 'focus filters' }, { keys: ['L'], label: 'legend' }, { keys: ['1', '2', '3'], label: 'Annotations · Detections · Shortcuts' }, { keys: ['?'], label: 'show this tab' }] },
]

/* ------------------------------------------------------------------ cross-channel ---- */
export type XBin = 'reference' | 'artifact' | 'propagation' | 'independent' | 'no match'
/** One channel's window. `t` / `v` are the bridge's peak-preserving envelope verbatim — `t` in the same
 *  absolute seconds as `window.t0S`, `v` with a null wherever a bucket was entirely NaN, so the x mapping
 *  survives decimation (where `t` is neither uniform nor `t0 + i / fs`) and a gap breaks the line instead
 *  of poisoning the whole SVG path. `error` is the bridge's own message for a channel it could not read. */
export interface XRow {
  channelId: number; name: string; lagS: number | null; r: number | null; sharedGroundWith?: string
  t: number[]; v: (number | null)[]; classification?: string; error?: string
}
export interface CrossDemo {
  recording: string; file: string; referenceId: number; referenceName: string
  /** every time here is absolute seconds from the start of the recording — `motifStartS` / `motifEndS`
   *  included, so one x scale over [t0S, t0S + durS] places the traces, the ticks and the band alike. */
  window: { label: string; startH: number; endH: number; durS: number; t0S: number; fs: number; motifStartS: number; motifEndS: number }
  channels: { id: number; name: string }[]; rows: XRow[]; defaultSelected: number[]; sharedGround: [string, string][]; openQuestions: string[]
  yDomain: [number, number]
  /** fixup-b: the unit the rows are drawn in; `null` = the recording declares none (absent on the demo: mV) */
  unit?: 'mV' | null
}
/** A smooth synthetic "channel" in mV with the MOTIF_233 drop at 0–21 s; channels are lagged copies of it. */
function baseSignal(t: number, seed: number): number {
  const p = seed * 0.37
  let v = 0.11 * Math.sin(t / 4.1 + p) + 0.06 * Math.sin(t / 1.7 + 1 + p * 2) + 0.05 * Math.sin(t / 9 + 2 - p) + 0.08
  if (t >= 0 && t < 21) { const u = t / 21; v -= 0.34 * (u < 0.25 ? u / 0.25 : Math.exp(-(u - 0.25) * 3.2)) }
  return v
}
const FIXED_LAGS: Record<string, [number | null, number | null]> = { CH3_A2: [0.04, 0.98], CH1_A1: [1.2, 0.71], CH2_A1: [2.85, 0.64], CH5_B1: [-18.4, 0.31], CH6_B1: [null, null] }
export function crossDemo(referenceId: number, pad = 20): CrossDemo | null {
  const ref = CANON_CHANNELS.find(c => c.id === referenceId)
  if (!ref || ref.recordingKey !== 'M2_aug_fs1') return null
  const fs = 10, t0S = -pad, n = Math.round((21 + 2 * pad - 0.4 + 1) * fs)
  const channels = CANON_CHANNELS.filter(c => c.recordingKey === 'M2_aug_fs1').map(c => ({ id: c.id, name: c.name }))
  const r = seeded(referenceId * 97)
  const rows: XRow[] = channels.map((c, ci) => {
    let lag: number | null, corr: number | null
    if (c.id === referenceId) { lag = 0; corr = null }
    else if (referenceId === 4 && FIXED_LAGS[c.name]) [lag, corr] = FIXED_LAGS[c.name]
    else if ((ref.name === 'CH3_A2' && c.name === 'CH4_A2') || (ref.name === 'CH4_A2' && c.name === 'CH3_A2')) { lag = 0.04; corr = 0.98 }
    else { const u = r(); lag = u < 0.12 ? null : +((r() - 0.5) * 50).toFixed(2); corr = lag === null ? null : +(0.2 + r() * 0.7).toFixed(2) }
    const trace: number[] = []
    const ts: number[] = []
    for (let i = 0; i < n; i++) {
      const t = t0S + i / fs
      ts.push(t)
      const noise = (Math.sin(i * 12.9898 + ci * 78.233) * 43758.5453) % 1 * 0.012
      const v = c.id === referenceId ? baseSignal(t, 0)
        : lag === null ? baseSignal(t + 17, ci + 3) * 0.9
          : (corr ?? 0) >= 0.95 ? baseSignal(t - lag, 0) * 0.97 + noise
            : baseSignal(t - lag, ci * ((corr ?? 0) > 0.6 ? 0.15 : 1.4)) * (0.55 + (corr ?? 0) * 0.45) + noise
      trace.push(+v.toFixed(4))
    }
    const shared = (c.name === 'CH3_A2' && ref.name === 'CH4_A2') || (c.name === 'CH4_A2' && ref.name === 'CH3_A2') ? ref.name : undefined
    return { channelId: c.id, name: c.name, lagS: lag, r: corr, sharedGroundWith: shared, t: ts, v: trace }
  })
  const defaultNames = ['CH4_A2', 'CH3_A2', 'CH1_A1', 'CH2_A1', 'CH5_B1', 'CH6_B1']
  const defaultSelected = [referenceId, ...defaultNames.map(nm => channels.find(c => c.name === nm)!.id).filter(id => id !== referenceId)].slice(0, 6)
  return {
    recording: 'M2_aug fs1', file: 'M2_aug_concat_fs1.mat', referenceId, referenceName: ref.name,
    window: { label: `MOTIF_233 ± ${pad} s`, startH: +(277.3119 - pad / 3600).toFixed(3), endH: +(277.3119 + (21.6 + pad) / 3600).toFixed(3), durS: +(n / fs).toFixed(1), t0S, fs, motifStartS: 0, motifEndS: 21 },
    channels, rows, defaultSelected, sharedGround: [['CH3_A2', 'CH4_A2']], yDomain: [-0.42, 0.42],
    openQuestions: [
      'Is lag measured per window, or per channel pair across the whole recording?',
      'What r separates propagation from an independent match, and should it depend on distance between electrodes?',
      'Should a shared-ground pair be excluded from every count, or only from recurrence?',
      'Is a multivariate motif one span across channels or a set of linked single-channel spans? (parked)',
    ],
  }
}

/* ------------------------------------------------------------------ span edit ---- */
export interface Revision { rev: number; kind: 'detection' | 'annotation'; ref: string; detail: string; origin: 'machine' | 'human'; status: 'kept' | 'current' | 'pending' }
export type SnapRule = 'steepest sample' | 'trough' | 'zero crossing' | 'free'
export interface SpanEditDemo {
  memberId: string; familyId: string; recordingKey: string; recordingLabel: string; file: string; channelId: number; channelName: string
  heldOut: boolean; fs: number; nSamples: number; durationH: number
  original: { start: number; end: number }; edited: { start: number; end: number }
  onsetRule: string; snap: SnapRule; snapCandidates: Record<Exclude<SnapRule, 'free'>, number[]>
  trace: { t0Sample: number; mv: number[] }; overview: number[]
  handoff: { queueId: string; candidate: number; of: number; runLabel: string }
  revisions: Revision[]
}
export function spanEditDemo(memberId: string): SpanEditDemo | null {
  const common = {
    familyId: 'F-03', fs: 1, onsetRule: 'walk back from steepest while descending', snap: 'steepest sample' as SnapRule,
    handoff: { queueId: 'q-12', candidate: 12, of: 50, runLabel: 'drop_motifs9 run 128' },
    revisions: [{ rev: 1, kind: 'detection' as const, ref: 'd-0412', detail: 'run 128 · machine', origin: 'machine' as const, status: 'current' as const }],
  }
  if (memberId === 'm-1846') {
    const t0Sample = 534977 - 125
    return {
      ...common, memberId, recordingKey: 'M2_aug_fs1', recordingLabel: 'M2_aug fs1', file: 'M2_aug_concat_fs1.mat', channelId: 4, channelName: 'CH4_A2',
      heldOut: false, nSamples: 2595600, durationH: 721,
      original: { start: 534971, end: 534983 }, edited: { start: 534967, end: 534985 },
      snapCandidates: {
        'steepest sample': [534955, 534961, 534967, 534971, 534975, 534979, 534983, 534985, 534990, 534996],
        trough: [534948, 534963, 534978, 534988, 535004],
        'zero crossing': [534958, 534969, 534981, 534992, 535001],
      },
      trace: { t0Sample, mv: syntheticTrace({ n: 250, seed: 1846, baseline: 0.05, noise: 0.02, events: [{ at: 60, depth: 0.2, width: 18, shape: 'spike' }, { at: 119, depth: 0.32, width: 21, shape: 'sharkfin' }, { at: 200, depth: 0.22, width: 30, shape: 'plateau' }] }) },
      overview: syntheticTrace({ n: 1442, seed: 721, baseline: 0, noise: 0.004, events: [{ at: 210, depth: 0.05, width: 60, shape: 'spike' }, { at: 700, depth: 0.04, width: 120, shape: 'plateau' }, { at: 1100, depth: 0.06, width: 40, shape: 'spike' }] }),
    }
  }
  if (memberId === 'm-0917') {
    return {
      ...common, memberId, recordingKey: HELD_OUT_KEY, recordingLabel: 'M4_aug', file: 'M4_aug_concat_fs1.mat', channelId: 52, channelName: 'CH4_A2',
      heldOut: true, nSamples: 1080000, durationH: 300, original: { start: 0, end: 0 }, edited: { start: 0, end: 0 },
      snapCandidates: { 'steepest sample': [], trough: [], 'zero crossing': [] }, trace: { t0Sample: 0, mv: [] }, overview: [],
    }
  }
  return null
}

export const FAMILY_TEAL = FAMILY_COLOURS['F-03']
