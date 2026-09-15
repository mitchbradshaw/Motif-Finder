/* Discovery fixtures (frames discovery-1 … discovery-3b). Demo data only: the placeholder canon (§0) plus
 * Discovery-local numbers the frames draw — a session, its runs, fires bins, scoreboard rows, detections,
 * the template picker, the seed draft, and one compare pair (drop_motifs9 × seed_F03_native). Traces are
 * synthetic mV, deterministic, never normalised. Components never import this file: read through api/discovery.ts. */
import { FAMILIES, JOBS, LOCAL_LIMITS, RECORDINGS, REVIEW_QUEUES, seeded, syntheticTrace } from './canon'

/* ------------------------------------------------------------------ helpers */
export function strHash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) }
  return h >>> 0
}
/** A deterministic generator for (key, index): the same bin of the same run always gets the same count. */
export function rng(key: string, i = 0) {
  const r = seeded((strHash(key) ^ Math.imul(i + 1, 2654435761)) >>> 0 || 1)
  r(); r()
  return r
}
/** A smooth slow-varying mV trace (overview strips, section signals). */
export function smoothTrace(n: number, key: string, amp = 0.22, noise = 0.012): number[] {
  const r = rng(key, 7)
  const comps = Array.from({ length: 6 }, (_, k) => ({ f: (k + 1) * (1.2 + r() * 1.8), ph: r() * Math.PI * 2, a: amp / (k + 1.3) }))
  const out: number[] = []
  for (let i = 0; i < n; i++) {
    let v = 0
    for (const c of comps) v += c.a * Math.sin(2 * Math.PI * c.f * (i / n) + c.ph)
    v += (r() - 0.5) * noise
    out.push(+v.toFixed(4))
  }
  return out
}

/* ------------------------------------------------------------------ session */
export const DISCOVERY_LIMIT_MIN = parseInt(LOCAL_LIMITS.discovery, 10)   // 20
const M2 = RECORDINGS.find(r => r.key === 'M2_aug_fs1')!

export interface DiscoverySession {
  name: string; recording: string; channels: string[]; section: [number, number]
  null: { method: string; n: number }; localLimitMin: number; savedAt: string
}
export const SESSION: DiscoverySession = {
  name: 'ch_screen_sep14', recording: M2.key, channels: ['CH2_A1', 'CH4_A2', 'CH7_B2'], section: [112, 286],
  null: { method: 'circular shift', n: 200 }, localLimitMin: DISCOVERY_LIMIT_MIN, savedAt: '11:44',
}

export interface RecordingOption { key: string; label: string; file: string; stem: string; hours: number; channels: string[]; heldOut: boolean; fs: number }
export const RECORDING_OPTIONS: RecordingOption[] = RECORDINGS.map(r => ({
  key: r.key, label: r.label, file: r.source_file, stem: r.source_file.replace(/\.(mat|csv)$/, ''), hours: r.duration_h, channels: r.channels, heldOut: r.held_out, fs: r.fs_hz,
}))

/* ------------------------------------------------------------------ runs */
export type RunKind = 'reference' | 'template' | 'seed' | 'draft'
export type RunStatus = 'reference' | 'done' | 'on cluster' | 'running' | 'queued' | 'new' | 'paused' | 'draft' | 'superseded' | 'failed'
export type GlyphKind = 'human' | 'drop' | 'sax' | 'seed' | 'mp' | 'spike' | 'model' | 'threshold' | 'baseline' | 'noise' | 'source'

export interface DiscoveryRun {
  key: string; id?: string; label: string; kind: RunKind; colour: string; glyph: GlyphKind
  detail: string                   // 'v9 · 4 stages' · 'F-03 medoid · MASS'
  version?: number; stageCount?: number; template?: string
  status: RunStatus; progress?: number; doneAt?: string
  reviewedH?: number               // human reference only
  perChannelMin?: number           // compute estimate per channel, for runs not yet run
  job?: string; pausedAt?: { stage: number; of: number }
  error?: string; addedThisSession?: boolean
}

export const RUN_COLOURS = { human: '#22A06B', drop_motifs9: '#0A84FF', sharkfin_v2: '#14B8A6', seed_F03_native: '#AF52DE', seed_E0102_bank: '#E2557E', mp_drops_v3: '#E8900C' }
/** Categorical colours for runs added in this session (non-semantic: no pure red/green/blue, not a family colour). */
export const EXTRA_RUN_COLOURS = ['#5E7CE2', '#B7791F', '#0E7490', '#9D4EDD', '#65A30D', '#C2410C']

const pausedJob = JOBS.find(j => j.id === 'r-0431')!
export const RUNS: DiscoveryRun[] = [
  { key: 'human', label: 'human annotations', kind: 'reference', colour: RUN_COLOURS.human, glyph: 'human', detail: '41 h reviewed', status: 'reference', reviewedH: 41 },
  { key: 'drop_motifs9', label: 'drop_motifs9', kind: 'template', colour: RUN_COLOURS.drop_motifs9, glyph: 'drop', detail: 'v9 · 4 stages', version: 9, stageCount: 4, template: 'drop_motifs9', status: 'done', doneAt: '11:02' },
  { key: 'sharkfin_v2', label: 'sharkfin_v2', kind: 'template', colour: RUN_COLOURS.sharkfin_v2, glyph: 'sax', detail: 'v2 · 4 stages', version: 2, stageCount: 4, template: 'sharkfin_v2', status: 'on cluster', progress: 0.64, job: 'j-0221' },
  { key: 'seed_F03_native', label: 'seed_F03_native', kind: 'seed', colour: RUN_COLOURS.seed_F03_native, glyph: 'seed', detail: 'F-03 medoid · MASS', template: 'seed_F03_native', status: 'done', doneAt: '11:40' },
  { key: 'seed_E0102_bank', label: 'seed_E0102_bank', kind: 'seed', colour: RUN_COLOURS.seed_E0102_bank, glyph: 'seed', detail: 'E-0102 · 3 lengths', template: 'seed_E0102_bank', status: 'new', perChannelMin: 12.7 },
  { key: 'mp_drops_v3', id: pausedJob.id, label: 'mp_drops_v3 · r-0431', kind: 'template', colour: RUN_COLOURS.mp_drops_v3, glyph: 'sax', detail: 'v3 · 4 stages', version: 3, stageCount: 4, template: 'mp_drops_v3', status: 'paused', progress: 0.75, pausedAt: { stage: 3, of: 4 }, job: 'j-0217' },
]

/** Past Discovery runs on this recording (History popover, P2). */
export interface HistoryEntry { id: string; label: string; when: string; status: string; runKey: string; inSession: boolean; detail: string }
export const HISTORY: HistoryEntry[] = [
  { id: 'r-0431', label: 'mp_drops_v3', when: '14 Sep 11:40', status: 'paused 3/4', runKey: 'mp_drops_v3', inSession: true, detail: 'waiting on j-0217' },
  { id: 'r-0415', label: 'seed search E-0102', when: '13 Sep 16:12', status: 'done · 58 found', runKey: 'seed_E0102_r0415', inSession: false, detail: `review queue ${REVIEW_QUEUES[1].id}` },
  { id: 'r-0412', label: 'mp_drops_v3', when: '12 Sep 09:30', status: 'done · 212 found', runKey: 'mp_drops_v3_r0412', inSession: false, detail: `review queue ${REVIEW_QUEUES[0].id}` },
  { id: 'r-0398', label: 'drop_motifs8', when: '9 Sep 18:05', status: 'superseded', runKey: 'drop_motifs8', inSession: false, detail: 'superseded by drop_motifs9' },
]

/* ------------------------------------------------------------------ overview + fires */
export function overviewTrace(recording: string, channel: string, hours: number): number[] {
  return smoothTrace(Math.round(hours), `${recording}:${channel}:overview`, 0.24, 0.02)
}

/** Reviewed hour ranges per channel (human reference). Recall is computed only over these. */
export const REVIEWED_RANGES: Record<string, [number, number][]> = {
  CH4_A2: [[184, 198]],
  CH7_B2: [[226, 232]],
  CH1_A1: [[40, 48]], CH3_A2: [[300, 312]],
}

/** Detections per 3 h bin for (channel, run, absolute bin index). */
export function fireCount(channel: string, run: string, bin: number): number {
  if (run === 'human') {
    const h0 = bin * 3, h1 = h0 + 3
    const inside = (REVIEWED_RANGES[channel] ?? []).some(([a, b]) => h1 > a && h0 < b)
    if (!inside) return 0
    const r = rng(`${channel}|human`, bin)
    return r() < 0.6 ? 1 + Math.floor(r() * 3) : 0
  }
  const base: Record<string, number> = { drop_motifs9: 0.62, sharkfin_v2: 0.42, seed_F03_native: 0.4 }
  const r = rng(`${channel}|${run}`, bin)
  const zone = 0.5 + 0.5 * Math.sin(bin * 0.19 + (strHash(channel) % 11) + (strHash(run) % 3))
  const p = (base[run] ?? 0.35) * (0.35 + zone)
  if (r() > p) return 0
  return 1 + Math.floor(r() * 4 * zone)
}
export function reviewedHoursInBin(channel: string, bin: number): number {
  const h0 = bin * 3, h1 = h0 + 3
  return (REVIEWED_RANGES[channel] ?? []).reduce((s, [a, b]) => s + Math.max(0, Math.min(b, h1) - Math.max(a, h0)), 0)
}
export function reviewedHoursIn(channel: string, section: [number, number]): number {
  return (REVIEWED_RANGES[channel] ?? []).reduce((s, [a, b]) => s + Math.max(0, Math.min(b, section[1]) - Math.max(a, section[0])), 0)
}

/* ------------------------------------------------------------------ scoreboard */
export type Recall = { value: number; overH: number } | { none: true } | { tooFewH: number }
export interface ScoreCells { found: number; judged: number; reviewed: number; interesting: number; recall: Recall; nullExpects: number }
/** Per-channel score rows as the frame draws them (drop_motifs9, seed_F03_native on the canonical three channels). */
export const SCORE_FIXTURE: Record<string, Record<string, ScoreCells>> = {
  drop_motifs9: {
    CH2_A1: { found: 41, judged: 2, reviewed: 12, interesting: 3, recall: { none: true }, nullExpects: 7 },
    CH4_A2: { found: 72, judged: 5, reviewed: 30, interesting: 8, recall: { value: 0.71, overH: 14 }, nullExpects: 11 },
    CH7_B2: { found: 47, judged: 1, reviewed: 8, interesting: 1, recall: { tooFewH: 6 }, nullExpects: 8 },
  },
  seed_F03_native: {
    CH2_A1: { found: 14, judged: 5, reviewed: 12, interesting: 2, recall: { none: true }, nullExpects: 3 },
    CH4_A2: { found: 31, judged: 10, reviewed: 20, interesting: 4, recall: { value: 0.52, overH: 14 }, nullExpects: 4 },
    CH7_B2: { found: 18, judged: 4, reviewed: 8, interesting: 1, recall: { tooFewH: 6 }, nullExpects: 2 },
  },
}
/** A channel no frame gives numbers for (1c: CH8_B2, CH9_C1, CH11_C2): generated, and labelled as demo like everything else. */
export function generatedScore(run: string, channel: string, section: [number, number]): ScoreCells {
  const r = rng(`${run}|${channel}|score`)
  const found = Math.round((run === 'drop_motifs9' ? 38 : 16) + r() * 30)
  const reviewedH = reviewedHoursIn(channel, section)
  const reviewed = reviewedH ? Math.round(found * 0.3) : Math.round(found * r() * 0.15)
  const interesting = Math.round(reviewed * (0.1 + r() * 0.15))
  return {
    found, judged: Math.round(found * r() * 0.08), reviewed, interesting,
    recall: reviewedH === 0 ? { none: true } : reviewedH < 10 ? { tooFewH: reviewedH } : { value: +(0.4 + r() * 0.35).toFixed(2), overH: reviewedH },
    nullExpects: Math.max(1, Math.round(found / (5 + r() * 2.5))),
  }
}
export const POOLED_RECALL: Record<string, Recall> = { drop_motifs9: { value: 0.71, overH: 14 }, seed_F03_native: { value: 0.52, overH: 14 } }
export const SCORES_REFRESHED_AT = '11:40'

/* ------------------------------------------------------------------ detections */
export interface Detection {
  id: string; index: number; of: number; run: string; channel: string; atH: number; durationS: number
  depthMv: number; score: number; priorVerdict: string | null; alsoFoundBy: string[]; nearMiss?: { run: string; d: number }
}
export function detectionsFor(run: string, channel: string, n: number, section: [number, number]): Detection[] {
  const [a, b] = section
  const out: Detection[] = []
  const special = run === 'drop_motifs9' && channel === 'CH4_A2'
  const base = special ? 401 : 1000 + (strHash(run + channel) % 8000)
  for (let i = 0; i < n; i++) {
    const r = rng(`${run}|${channel}|det`, i)
    let at: number
    if (special && n >= 12) {
      at = i < 11 ? a + ((i + 0.5) / 11) * (192.2 - a) : i === 11 ? 192.4 : 192.6 + ((i - 12 + 0.5) / (n - 12)) * (b - 192.6)
    } else at = a + ((i + 0.3 + r() * 0.4) / n) * (b - a)
    const also = r() < 0.34 ? ['seed_F03_native'] : []
    out.push({
      id: `d-${String(base + i).padStart(4, '0')}`, index: i + 1, of: n, run, channel, atH: +at.toFixed(2), durationS: Math.round(18 + r() * 30),
      depthMv: +(0.12 + r() * 0.4).toFixed(2), score: +(0.55 + r() * 0.43).toFixed(2),
      priorVerdict: r() < 0.05 ? 'interesting' : null, alsoFoundBy: run === 'seed_F03_native' ? (r() < 0.8 ? ['drop_motifs9'] : []) : also,
    })
  }
  if (special && n >= 12) {
    // d-0412: frame 1 (browser 12 / 72) and frame 3 (step 7 / 106, only A fired, B near miss d 3.6)
    out[11] = { ...out[11], id: 'd-0412', atH: 192.4, durationS: 36, depthMv: 0.38, score: 0.88, priorVerdict: null, alsoFoundBy: [], nearMiss: { run: 'seed_F03_native', d: 3.6 } }
  }
  return out
}
/** The browser's view: 0.8 h of signal around a detection, 1 Hz, with the drop drawn in. */
export function detectionWindow(det: Detection): { t0H: number; values: number[] } {
  const t0H = Math.floor(det.atH * 10) / 10 - (det.atH === 192.4 ? 0.4 : 0.4)
  const n = 2880
  const at = Math.round((det.atH - t0H) * 3600)
  const slow = smoothTrace(n, `${det.id}:win`, 0.16, 0.0)
  const drop = syntheticTrace({ n, seed: strHash(det.id) % 997 + 1, noise: 0.018, events: [{ at: at - 10, depth: det.depthMv, width: Math.max(det.durationS, 24) * 8, shape: 'sharkfin' }] })
  return { t0H, values: slow.map((v, i) => +(v + drop[i]).toFixed(4)) }
}

/* ------------------------------------------------------------------ template picker (1b) */
export interface TemplateStage { index: string; name: string; signature: string; locked?: string; glyph: GlyphKind }
export interface DiscoveryTemplate {
  name: string; kind: 'template' | 'seed'; signature: string; fits: boolean; lastScore: string; savedAt: string; lastUsed: number
  stages: TemplateStage[]; perChannelMin: number; complexity: string; diskGB: number
  preview: { spans: number; hours: number; channel: string; nullGives: number }
  bind?: 'carry' | 'rebind'; inSession?: string; precision?: number; hasModel?: boolean
}
const src: TemplateStage = { index: '●', name: 'Source', signature: '— → Signal', glyph: 'source' }
export const TEMPLATES: DiscoveryTemplate[] = [
  { name: 'mp_discord_v3', kind: 'template', signature: 'Signal → Scores → SpanSet', fits: true, lastScore: 'not yet scored · saved 12 Sep', savedAt: '12 Sep', lastUsed: 1,
    stages: [src, { index: '01', name: 'Baseline removal', signature: 'Signal → Signal', locked: 'window 3 h', glyph: 'baseline' }, { index: '02', name: 'Matrix profile', signature: 'Signal → Scores', locked: 'm 600 s · STUMP', glyph: 'mp' }, { index: '03', name: 'Threshold to spans', signature: 'Scores → SpanSet', locked: 'below p5 of null', glyph: 'threshold' }],
    perChannelMin: 128, complexity: 'O(n²) per channel', diskGB: 0.6, preview: { spans: 11, hours: 4, channel: 'CH4_A2', nullGives: 2 } },
  { name: 'spike_shape_v1', kind: 'template', signature: 'Signal → SpanSet', fits: true, lastScore: 'precision 31 % over 88 reviewed', savedAt: '10 Sep', lastUsed: 2, precision: 0.31,
    stages: [src, { index: '01', name: 'Gaussian shape', signature: 'Signal → Signal', locked: 'σ 4 s', glyph: 'baseline' }, { index: '02', name: 'Spike mark', signature: 'Signal → Scores', locked: 'prominence 0.05 mV', glyph: 'spike' }, { index: '03', name: 'Band detect', signature: 'Scores → SpanSet', locked: '± 6 s', glyph: 'threshold' }],
    perChannelMin: 2, complexity: 'O(n) per channel', diskGB: 0.05, preview: { spans: 6, hours: 4, channel: 'CH4_A2', nullGives: 3 } },
  { name: 'drop_motifs9', kind: 'template', signature: 'Signal → SpanSet', fits: true, lastScore: 'in this session', savedAt: '11 Sep', lastUsed: 3, inSession: 'in this session',
    stages: [src, { index: '01', name: 'Baseline', signature: 'Signal → Signal', locked: 'window 3 h', glyph: 'baseline' }, { index: '02', name: 'Noise floor', signature: 'Signal → Signal + estimate', locked: 'cut 8σ', glyph: 'noise' }, { index: '03', name: 'Symbolic encoding', signature: 'Signal → Encoding', locked: 'SAX · 6 symbols', glyph: 'sax' }, { index: '04', name: 'Drop detection', signature: 'Encoding → SpanSet', locked: 'min slope', glyph: 'drop' }],
    perChannelMin: 4, complexity: 'O(n) per channel', diskGB: 0.1, preview: { spans: 4, hours: 4, channel: 'CH4_A2', nullGives: 1 } },
  { name: 'sharkfin_v2', kind: 'template', signature: 'Signal → SpanSet', fits: true, lastScore: 'in this session', savedAt: '8 Sep', lastUsed: 4, inSession: 'in this session',
    stages: [src, { index: '01', name: 'Gaussian shape', signature: 'Signal → Signal', locked: 'σ 6 s', glyph: 'baseline' }, { index: '02', name: 'Symbolic encoding', signature: 'Signal → Encoding', locked: 'SAX · 5 symbols', glyph: 'sax' }, { index: '03', name: 'Spike mark', signature: 'Encoding → Scores', locked: 'rise 0.1 mV', glyph: 'spike' }, { index: '04', name: 'Drop detection', signature: 'Scores → SpanSet', locked: 'min depth 0.2 mV', glyph: 'drop' }],
    perChannelMin: 45, complexity: 'O(n log n) per channel', diskGB: 0.3, preview: { spans: 5, hours: 4, channel: 'CH4_A2', nullGives: 1 } },
  { name: 'seed_F03_native', kind: 'seed', signature: 'Signal + exemplar → SpanSet', fits: true, lastScore: 'already in this session · runs from medoid m-1846', savedAt: '14 Sep', lastUsed: 5, inSession: 'already in this session · runs from medoid m-1846', bind: 'carry',
    stages: [src, { index: '01', name: 'Seeded search', signature: 'Signal + exemplar → Scores', locked: 'm-1846 · MASS', glyph: 'seed' }, { index: '02', name: 'Threshold', signature: 'Scores → SpanSet', locked: 'd ≤ 3.1', glyph: 'threshold' }],
    perChannelMin: 0.05, complexity: 'O(n) per channel', diskGB: 0.02, preview: { spans: 2, hours: 4, channel: 'CH4_A2', nullGives: 0 } },
  { name: 'seed_sharkfin_rebind', kind: 'seed', signature: 'Signal + exemplar → SpanSet', fits: true, lastScore: 'rebind · asks for an exemplar', savedAt: '13 Sep', lastUsed: 6, bind: 'rebind',
    stages: [src, { index: '01', name: 'Seeded search', signature: 'Signal + exemplar → Scores', locked: 'exemplar asked on apply · MASS', glyph: 'seed' }, { index: '02', name: 'Threshold', signature: 'Scores → SpanSet', locked: 'd ≤ 2.8', glyph: 'threshold' }],
    perChannelMin: 0.05, complexity: 'O(n) per channel', diskGB: 0.02, preview: { spans: 2, hours: 4, channel: 'CH4_A2', nullGives: 0 } },
  { name: 'drop_cnn_v1', kind: 'template', signature: 'Signal → Scores → SpanSet', fits: true, lastScore: 'precision 44 % over 61 reviewed · model cnn_windows_v2 v2', savedAt: '7 Sep', lastUsed: 7, precision: 0.44, hasModel: true,
    stages: [src, { index: '01', name: 'Sliding windows', signature: 'Signal → WindowSet', locked: '600 s · hop 60 s', glyph: 'baseline' }, { index: '02', name: 'Model stage', signature: 'Model + WindowSet → Scores', locked: 'cnn_windows_v2 · manual v2', glyph: 'model' }, { index: '03', name: 'Threshold to spans', signature: 'Scores → SpanSet', locked: 'p ≥ 0.7', glyph: 'threshold' }],
    perChannelMin: 9, complexity: 'O(n) per channel · CPU inference', diskGB: 0.2, preview: { spans: 7, hours: 4, channel: 'CH4_A2', nullGives: 1 } },
  { name: 'sharkfin_cnn_v2', kind: 'template', signature: 'Signal → Scores → SpanSet', fits: true, lastScore: 'not yet scored · model cnn_windows_v2 v2', savedAt: '6 Sep', lastUsed: 8, hasModel: true,
    stages: [src, { index: '01', name: 'Sliding windows', signature: 'Signal → WindowSet', locked: '120 s · hop 20 s', glyph: 'baseline' }, { index: '02', name: 'Model stage', signature: 'Model + WindowSet → Scores', locked: 'cnn_windows_v2 · manual v2', glyph: 'model' }, { index: '03', name: 'Threshold to spans', signature: 'Scores → SpanSet', locked: 'p ≥ 0.8', glyph: 'threshold' }],
    perChannelMin: 14, complexity: 'O(n) per channel · CPU inference', diskGB: 0.3, preview: { spans: 5, hours: 4, channel: 'CH4_A2', nullGives: 1 } },
  { name: 'cnn_windows_v3', kind: 'template', signature: 'Signal → WindowSet → Model', fits: false, lastScore: 'training template · Models › Launch', savedAt: '13 Sep', lastUsed: 9,
    stages: [src, { index: '01', name: 'Sliding windows', signature: 'Signal → WindowSet', locked: '600 s', glyph: 'baseline' }, { index: '02', name: 'Classifier', signature: 'WindowSet → Model', locked: 'CNN', glyph: 'model' }],
    perChannelMin: 0, complexity: '—', diskGB: 0, preview: { spans: 0, hours: 4, channel: 'CH4_A2', nullGives: 0 } },
  { name: 'cnn_windowset_v1', kind: 'template', signature: 'WindowSet → Model', fits: false, lastScore: 'training template · Models › Launch', savedAt: '12 Sep', lastUsed: 10,
    stages: [{ index: '●', name: 'Window set', signature: '— → WindowSet', glyph: 'source' }, { index: '01', name: 'Classifier', signature: 'WindowSet → Model', locked: 'CNN', glyph: 'model' }],
    perChannelMin: 0, complexity: '—', diskGB: 0, preview: { spans: 0, hours: 4, channel: 'CH4_A2', nullGives: 0 } },
]
export const REBIND_EXEMPLARS = [
  { value: 'E-0102', label: 'E-0102 · exemplar of F-03 · 21 s' },
  { value: 'm-1846', label: 'm-1846 · medoid of F-03 · 21 s' },
  { value: 'E-0231', label: 'E-0231 · exemplar of F-07 · 64 s' },
]

/* ------------------------------------------------------------------ seed search (2) */
const F03 = FAMILIES.find(f => f.id === 'F-03')!
export type SeedSource = 'library' | 'explore' | 'medoid'
export interface SeedInfo { id: string; role: string; title: string; family: string; familyLine: string; recording: string; channel: string; startH: number; samples: number; lengthS: number; hash: string; trace: number[] }
export const SEED_OPTIONS: SeedInfo[] = [
  { id: 'E-0102', role: 'exemplar', title: `E-0102 · exemplar of ${F03.id}`, family: F03.id, familyLine: `${F03.name} family · ${F03.members} members`, recording: 'M2_aug_concat_fs1', channel: 'CH4_A2', startH: 0.23, samples: 21, lengthS: 21, hash: '3b91e0',
    trace: syntheticTrace({ n: 21, seed: 102, noise: 0.012, events: [{ at: 3, depth: 0.34, width: 16, shape: 'sharkfin' }] }) },
  { id: 'm-1846', role: 'medoid', title: `m-1846 · medoid of ${F03.id}`, family: F03.id, familyLine: `${F03.name} family · ${F03.members} members`, recording: 'M2_aug_concat_fs1', channel: 'CH7_B2', startH: 204.61, samples: 21, lengthS: 21, hash: 'a4c27f',
    trace: syntheticTrace({ n: 21, seed: 1846, noise: 0.01, events: [{ at: 4, depth: 0.31, width: 15, shape: 'sharkfin' }] }) },
  { id: 'E-0231', role: 'exemplar', title: 'E-0231 · exemplar of F-07', family: 'F-07', familyLine: 'slow drift family · 212 members', recording: 'M2_aug_concat_fs1', channel: 'CH2_A1', startH: 57.10, samples: 64, lengthS: 64, hash: '7e0d19',
    trace: syntheticTrace({ n: 64, seed: 231, noise: 0.01, events: [{ at: 10, depth: 0.22, width: 44, shape: 'plateau' }] }) },
]
export interface SeedParams { algorithm: string; windowSamples: number; scaleBank: string; exclusionS: number; threshold: number; overlap: string }
export const SEED_RECOMMENDED: SeedParams = { algorithm: 'mass', windowSamples: 21, scaleBank: 'none', exclusionS: 10, threshold: 2.8, overlap: 'lowest' }
export interface SeedDraft { key: string; label: string; seedId: string; source: SeedSource; bind: 'carry' | 'rebind'; params: SeedParams; applied: SeedParams; estimateS: number }
export const SEED_DRAFT: SeedDraft = {
  key: 'seed_F03_native_2', label: 'seed_F03_native_2', seedId: 'E-0102', source: 'library', bind: 'carry',
  params: { ...SEED_RECOMMENDED, threshold: 3.1 }, applied: { ...SEED_RECOMMENDED }, estimateS: 3,
}

export interface SeedMatch { id: string; d: number; channel: string; atH: number; judged: boolean; trace: number[] }
const FIRST_MATCHES: [number, string, number, boolean][] = [
  [1.84, 'CH4_A2', 192.6, false], [1.92, 'CH7_B2', 140.2, false], [2.05, 'CH4_A2', 192.1, true], [2.21, 'CH2_A1', 231.7, false],
  [2.34, 'CH4_A2', 193.6, false], [2.47, 'CH7_B2', 118.9, true], [2.61, 'CH2_A1', 266.0, false], [2.80, 'CH4_A2', 250.3, false],
]
/** Every candidate MASS returns under d ≤ 8 (the threshold picks how many are kept). The first 8 are the frame's cards. */
export function seedCandidates(seedId: string, channels: string[]): SeedMatch[] {
  const seed = SEED_OPTIONS.find(s => s.id === seedId) ?? SEED_OPTIONS[0]
  const out: SeedMatch[] = []
  const chs = channels.length ? channels : ['CH4_A2']
  const mk = (i: number, d: number, channel: string, atH: number, judged: boolean): SeedMatch => {
    const r = rng(`${seedId}|match`, i)
    const trace = seed.trace.map((v, k) => +(v * (0.75 + r() * 0.45) + (rng(`${seedId}|m${i}`, k)() - 0.5) * 0.05 * d).toFixed(4))
    return { id: `m-${101 + i}`, d, channel, atH, judged, trace }
  }
  const base = seedId === 'E-0102' ? FIRST_MATCHES.filter(m => chs.includes(m[1])) : []
  base.forEach((m, i) => out.push(mk(i, m[0], m[1], m[2], m[3])))
  const r = rng(`${seedId}|cands|${chs.join(',')}`)
  let i = out.length
  // 33 more under 3.1 (41 kept at the frame's threshold on three channels), then the long tail the histogram shows
  const nearCount = Math.round(33 * chs.length / 3)
  for (let k = 0; k < nearCount; k++, i++) out.push(mk(i, +(2.81 + r() * 0.29).toFixed(2), chs[Math.floor(r() * chs.length)], +(112 + r() * 174).toFixed(1), r() < 0.12))
  const tailCount = Math.round(780 * chs.length / 3)
  for (let k = 0; k < tailCount; k++, i++) {
    const g = (r() + r() + r() + r()) / 4       // bell around 0.5
    out.push(mk(i, +Math.max(3.11, 3.1 + g * 5.2 + (r() - 0.5) * 0.4).toFixed(2),chs[Math.floor(r() * chs.length)], +(112 + r() * 174).toFixed(1), r() < 0.05))
  }
  return out.filter(m => m.d <= 8).sort((a, b) => a.d - b.d)
}
/** Null (circular shift 200×) distances pooled: 1 under 2.8, 6 under 3.1 at three channels. */
export function seedNull(channels: string[]): number[] {
  const scale = Math.max(1, channels.length) / 3
  const out = [2.66, 2.88, 2.95, 3.02, 3.06, 3.09]
  const r = rng(`null|${channels.join(',')}`)
  for (let k = 0; k < Math.round(900 * scale); k++) { const g = (r() + r() + r()) / 3; out.push(+(3.12 + g * 5.4).toFixed(2)) }
  return out.filter(d => d <= 8)
}
/** Distance profile view: signal (1 Hz), MASS distance, on one channel. */
export function seedProfile(seedId: string, channel: string, view: [number, number], candidates: SeedMatch[]): { t0H: number; signal: number[]; distance: number[] } {
  const n = Math.max(60, Math.round((view[1] - view[0]) * 3600))
  const step = Math.max(1, Math.floor(n / 1400))
  const m = Math.ceil(n / step)
  const signal = smoothTrace(m, `${channel}:${view[0].toFixed(2)}:prof`, 0.14, 0.02)
  const r = rng(`${seedId}|${channel}|dist`)
  const distance: number[] = []
  const inView = candidates.filter(c => c.channel === channel && c.atH >= view[0] && c.atH <= view[1] && c.d < 3.4)
  for (let i = 0; i < m; i++) {
    const h = view[0] + (i * step) / 3600
    let d = 5 + Math.sin(i * 0.05) * 0.4 + (r() - 0.5) * 0.9
    for (const c of inView) { const dist = Math.abs(h - c.atH) * 3600; if (dist < 600) d = Math.min(d, c.d + (dist / 600) * 2.6) }
    distance.push(+d.toFixed(3))
  }
  return { t0H: view[0], signal, distance }
}

/* ------------------------------------------------------------------ compare (3, 3b) */
export type Role = 'Source' | 'Preprocess' | 'Score / estimate' | 'Encode' | 'Detect'
export const ROLES: Role[] = ['Source', 'Preprocess', 'Score / estimate', 'Encode', 'Detect']
export interface RoleCell { index?: string; name: string; short?: string; param: string; signature: string; glyph: GlyphKind }
export const RUN_CHAINS: Record<string, { subtitle: string; cells: Record<Role, RoleCell | null> }> = {
  drop_motifs9: { subtitle: 'template · v9', cells: {
    Source: { name: 'Source', param: 'CH4_A2 · CH2_A1 · CH7_B2', signature: '— → Signal', glyph: 'source' },
    Preprocess: { index: '01', name: 'Baseline removal', param: 'window 3 h', signature: 'Signal → Signal', glyph: 'baseline' },
    'Score / estimate': { index: '02', name: 'Noise floor', param: 'cut 8σ', signature: 'Signal → Signal + estimate', glyph: 'noise' },
    Encode: { index: '03', name: 'Symbolic encoding', short: 'Symbolic enc.', param: 'SAX · 6 symbols', signature: 'Signal → Encoding', glyph: 'sax' },
    Detect: { index: '04', name: 'Drop detection', param: 'min slope', signature: 'Encoding → SpanSet', glyph: 'drop' },
  } },
  seed_F03_native: { subtitle: 'seed · E-0102', cells: {
    Source: { name: 'Source', param: 'CH4_A2 · CH2_A1 · CH7_B2', signature: '— → Signal', glyph: 'source' },
    Preprocess: { index: '01', name: 'Baseline removal', param: 'window 3 h', signature: 'Signal → Signal', glyph: 'baseline' },
    'Score / estimate': { index: '02', name: 'Seeded search', param: 'E-0102 · MASS', signature: 'Signal + exemplar → Scores', glyph: 'seed' },
    Encode: null,
    Detect: { index: '03', name: 'Threshold', param: 'd ≤ 3.1', signature: 'Scores → SpanSet', glyph: 'threshold' },
  } },
  sharkfin_v2: { subtitle: 'template · v2', cells: {
    Source: { name: 'Source', param: 'CH4_A2 · CH2_A1 · CH7_B2', signature: '— → Signal', glyph: 'source' },
    Preprocess: { index: '01', name: 'Gaussian shape', param: 'σ 6 s', signature: 'Signal → Signal', glyph: 'baseline' },
    'Score / estimate': { index: '03', name: 'Spike mark', param: 'rise 0.1 mV', signature: 'Encoding → Scores', glyph: 'spike' },
    Encode: { index: '02', name: 'Symbolic encoding', short: 'Symbolic enc.', param: 'SAX · 5 symbols', signature: 'Signal → Encoding', glyph: 'sax' },
    Detect: { index: '04', name: 'Drop detection', param: 'min depth 0.2 mV', signature: 'Scores → SpanSet', glyph: 'drop' },
  } },
}
export interface OverlapRow { channel: string; onlyA: number; both: number; onlyB: number }
export const PAIR_OVERLAP: OverlapRow[] = [
  { channel: 'CH2_A1', onlyA: 30, both: 11, onlyB: 3 },
  { channel: 'CH4_A2', onlyA: 44, both: 28, onlyB: 3 },
  { channel: 'CH7_B2', onlyA: 32, both: 15, onlyB: 3 },
]
export const PAIR_TILES = { aPrecision: 0.24, aReviewed: 50, bPrecision: 0.18, bReviewed: 40, aXNull: 6.2, bXNull: 7.0 }

export interface Disagreement { kind: 'only A' | 'only B'; channel: string; atH: number; detection: string; score: number; otherNearest: number; otherThreshold: number; otherIsSeed: boolean }

/* ------------------------------------------------------------------ everything else Discovery reads */
export const ANALYSE_ROUTE = 'analyse/chain'
export const JOBS_ROUTE = (id: string) => `jobs/run/${id}`
export const REVIEW_ROUTE = (q: string) => `review/queue/${q}`
