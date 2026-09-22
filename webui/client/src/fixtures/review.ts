/* Review fixtures (spec §0 placeholder canon, §10). Demo data only — nothing is read from a database; traces
 * are synthetic mV, never normalised. Shared facts (recordings, channels, classes, families, queues, window set,
 * models, actor) come from canon.ts; what is Review-local (items, clusters, evidence) lives here.
 * Components never import this file: they read through src/api/review.ts. */
import { ACTOR, CLASSES, FAMILIES, FAMILY_COLOURS, MODELS, RECORDINGS, REVIEW_QUEUES, WINDOW_SET, seeded, syntheticTrace } from './canon'

export type Verdict = 'seed' | 'interesting' | 'not_interesting' | 'artifact' | 'unsure'
export type QueueSource = 'discovery-run' | 'seed-search' | 'explore-spans' | 'training-windows' | 'model-verification'
export type Unit = 'detection' | 'human span' | 'window'

export interface ReviewQueue {
  id: string; source: QueueSource; icon: 'target' | 'scan' | 'wave' | 'grid' | 'flask'
  title: string; subtitle: string; toolbarLabel: string; headerSubtitle: string
  runId?: string; template?: string; exemplar?: string; model?: string
  unit: Unit; blind: boolean; verdictKeys: 'full' | 'binary+classes' | 'full+classes'
  writes: 'adjudications' | 'annotations' | 'window verdicts'
  order: string; total: number; judged: number; paceS: number | null
  channels: string[]; scoreFloor: number | null
  previousLine: string | null; rankKind: 'score' | 'distance' | 'time' | 'stratified'
}

const q = (id: string) => REVIEW_QUEUES.find(x => x.id === id)
const verification = REVIEW_QUEUES.find(x => x.id === 'q-19')!

export const QUEUES: ReviewQueue[] = [
  { id: 'q-12', source: 'discovery-run', icon: 'target', title: 'Discovery · r-0412', subtitle: 'mp_drops_v3 · 3 channels · adjudications', toolbarLabel: 'Discovery · r-0412 mp_drops_v3',
    headerSubtitle: `queue ${q('q-12')!.source.replace(' ', ' · ')}`, runId: 'r-0412', template: 'mp_drops_v3', unit: 'detection', blind: false, verdictKeys: 'full', writes: 'adjudications',
    order: 'sorted by score', total: 1284, judged: 342, paceS: 1.9, channels: ['CH1_A1', 'CH4_A2', 'CH6_B1'], scoreFloor: 0.62, previousLine: 'c-0342 · interesting · 4 s ago', rankKind: 'score' },
  { id: 'q-15', source: 'seed-search', icon: 'scan', title: 'Seed search · r-0415', subtitle: 'exemplar E-0102 · clustered · adjudications', toolbarLabel: 'Seed search · r-0415 E-0102',
    headerSubtitle: 'queue r-0415 · seed search E-0102', runId: 'r-0415', exemplar: 'E-0102', unit: 'detection', blind: false, verdictKeys: 'full', writes: 'adjudications',
    order: 'sorted by distance', total: 118, judged: 61, paceS: 3.4, channels: ['CH2_A1', 'CH4_A2'], scoreFloor: null, previousLine: 'cluster 11 · 5 × interesting · 1 min ago', rankKind: 'distance' },
  { id: 'q-16', source: 'explore-spans', icon: 'wave', title: 'Explore spans', subtitle: 'taken for Review · annotations', toolbarLabel: 'Explore spans · taken for Review',
    headerSubtitle: 'queue explore spans · taken for Review', unit: 'human span', blind: false, verdictKeys: 'full', writes: 'annotations',
    order: 'sorted by time', total: 12, judged: 0, paceS: null, channels: ['CH4_A2', 'CH3', 'CH2'], scoreFloor: null, previousLine: null, rankKind: 'time' },
  { id: 'q-18', source: 'training-windows', icon: 'grid', title: 'Training windows', subtitle: 'cnn_windows_v3 · binary · cap 20,000', toolbarLabel: 'Training windows · cnn_windows_v3',
    headerSubtitle: 'queue training windows · cnn_windows_v3', template: 'cnn_windows_v3', unit: 'window', blind: true, verdictKeys: 'binary+classes', writes: 'window verdicts',
    order: 'stratified by channel', total: 20000, judged: 1600, paceS: 6, channels: [...WINDOW_SET.channels], scoreFloor: null, previousLine: 'w-01600 · not interesting · 12 s ago', rankKind: 'stratified' },
  { id: 'q-19', source: 'model-verification', icon: 'flask', title: 'Model verification', subtitle: 'cnn_windows_v3 · manual · test sample', toolbarLabel: 'Model verification · cnn_windows_v3 · manual',
    headerSubtitle: 'queue model verification · cnn_windows_v3 · manual', model: MODELS.candidates[0].name, unit: 'window', blind: true, verdictKeys: 'full+classes', writes: 'window verdicts',
    order: 'stratified by class', total: verification.total!, judged: MODELS.verification.judged, paceS: 6, channels: [...WINDOW_SET.channels], scoreFloor: null, previousLine: 'w-40210 · burst (class) · 7 s ago', rankKind: 'stratified' },
]

/* ---------------- items ---------------- */
export interface NearestFamily { id: string; name: string; members: number | null; d: number; colour: string }
export interface ArtifactFactors { level: 'low' | 'medium' | 'high'; p: number; coherence: number; clipping: string; stepChange: string; electrodeFlag: string }

export interface QueueEntry {
  id: string; queueId: string; unit: Unit; recording: string; channel: string
  startH: number; durationS: number; score?: number; d?: number; rank?: number
  /** The run that wrote this detection. Absent on a unit that has no run behind it. */
  runId?: string
  baseVerdict?: Verdict; baseClass?: string; clusterNo?: number
  shape: 'doublet' | 'slow' | 'burst' | 'window'; seed: number
  detectionId?: string; block?: 'test' | 'train'; sampleIndex?: number; modelCall?: { className: string; p: number }
  tags: string[]
}

const DOUBLET_TAGS = ['spike-train']
const e = (x: Partial<QueueEntry> & Pick<QueueEntry, 'id' | 'queueId' | 'channel' | 'startH' | 'durationS' | 'seed'>): QueueEntry =>
  ({ unit: 'detection', recording: 'M2_aug fs1', shape: 'doublet', tags: DOUBLET_TAGS, ...x })

const Q12: QueueEntry[] = [
  e({ id: 'c-0341', queueId: 'q-12', channel: 'CH4_A2', startH: 188.214, durationS: 33, score: 0.87, rank: 35, baseVerdict: 'interesting', seed: 341, detectionId: 'd-88192' }),
  e({ id: 'c-0342', queueId: 'q-12', channel: 'CH4_A2', startH: 190.052, durationS: 36, score: 0.86, rank: 36, baseVerdict: 'interesting', seed: 342, detectionId: 'd-88201' }),
  e({ id: 'c-0343', queueId: 'q-12', channel: 'CH4_A2', startH: 192.371, durationS: 35, score: 0.84, rank: 37, seed: 343, detectionId: 'd-88213' }),
  e({ id: 'c-0350', queueId: 'q-12', channel: 'CH4_A2', startH: 193.020, durationS: 31, score: 0.83, rank: 38, clusterNo: 13, seed: 350, detectionId: 'd-88240', d: 0.14 }),
  e({ id: 'c-0351', queueId: 'q-12', channel: 'CH4_A2', startH: 193.051, durationS: 34, score: 0.83, rank: 39, clusterNo: 13, seed: 351, detectionId: 'd-88241', d: 0.17 }),
  e({ id: 'c-0352', queueId: 'q-12', channel: 'CH4_A2', startH: 193.090, durationS: 30, score: 0.82, rank: 40, clusterNo: 13, seed: 352, detectionId: 'd-88243', d: 0.22 }),
  e({ id: 'c-0344', queueId: 'q-12', channel: 'CH4_A2', startH: 195.640, durationS: 38, score: 0.82, rank: 41, seed: 344, detectionId: 'd-88257' }),
  e({ id: 'c-0345', queueId: 'q-12', channel: 'CH6_B1', startH: 197.118, durationS: 29, score: 0.81, rank: 42, seed: 345, detectionId: 'd-88266', shape: 'burst', tags: [] }),
  e({ id: 'c-0346', queueId: 'q-12', channel: 'CH4_A2', startH: 199.402, durationS: 35, score: 0.81, rank: 43, seed: 346, detectionId: 'd-88270' }),
  e({ id: 'c-0347', queueId: 'q-12', channel: 'CH1_A1', startH: 201.775, durationS: 41, score: 0.80, rank: 44, seed: 347, detectionId: 'd-88281', shape: 'slow', tags: [] }),
  e({ id: 'c-0348', queueId: 'q-12', channel: 'CH4_A2', startH: 204.006, durationS: 32, score: 0.80, rank: 45, seed: 348, detectionId: 'd-88290' }),
  e({ id: 'c-0349', queueId: 'q-12', channel: 'CH6_B1', startH: 206.331, durationS: 37, score: 0.79, rank: 46, seed: 349, detectionId: 'd-88302', shape: 'burst', tags: [] }),
  e({ id: 'c-0353', queueId: 'q-12', channel: 'CH4_A2', startH: 208.940, durationS: 34, score: 0.79, rank: 47, seed: 353, detectionId: 'd-88315' }),
  e({ id: 'c-0354', queueId: 'q-12', channel: 'CH4_A2', startH: 211.207, durationS: 36, score: 0.78, rank: 48, seed: 354, detectionId: 'd-88329' }),
  e({ id: 'c-0355', queueId: 'q-12', channel: 'CH6_B1', startH: 213.588, durationS: 30, score: 0.78, rank: 49, seed: 355, detectionId: 'd-88333', shape: 'slow', tags: [] }),
  e({ id: 'c-0356', queueId: 'q-12', channel: 'CH4_A2', startH: 216.013, durationS: 33, score: 0.77, rank: 50, seed: 356, detectionId: 'd-88348' }),
]

const Q15: QueueEntry[] = [
  e({ id: 'c-0369', queueId: 'q-15', channel: 'CH4_A2', startH: 198.402, durationS: 32, d: 0.10, baseVerdict: 'interesting', seed: 369, detectionId: 'd-91004' }),
  e({ id: 'c-0370', queueId: 'q-15', channel: 'CH2_A1', startH: 200.117, durationS: 34, d: 0.11, baseVerdict: 'interesting', seed: 370, detectionId: 'd-91007' }),
  e({ id: 'c-0371', queueId: 'q-15', channel: 'CH4_A2', startH: 203.412, durationS: 31, d: 0.12, clusterNo: 12, seed: 371, detectionId: 'd-91011' }),
  e({ id: 'c-0372', queueId: 'q-15', channel: 'CH2_A1', startH: 203.655, durationS: 34, d: 0.15, clusterNo: 12, seed: 372, detectionId: 'd-91012' }),
  e({ id: 'c-0373', queueId: 'q-15', channel: 'CH4_A2', startH: 204.183, durationS: 33, d: 0.19, clusterNo: 12, seed: 373, detectionId: 'd-91014' }),
  e({ id: 'c-0374', queueId: 'q-15', channel: 'CH4_A2', startH: 206.020, durationS: 30, d: 0.22, clusterNo: 12, seed: 374, detectionId: 'd-91019' }),
  e({ id: 'c-0375', queueId: 'q-15', channel: 'CH2_A1', startH: 207.941, durationS: 36, d: 0.26, clusterNo: 12, seed: 375, detectionId: 'd-91022' }),
  e({ id: 'c-0376', queueId: 'q-15', channel: 'CH4_A2', startH: 210.118, durationS: 29, d: 0.31, clusterNo: 12, seed: 376, detectionId: 'd-91026' }),
  e({ id: 'c-0377', queueId: 'q-15', channel: 'CH4_A2', startH: 212.506, durationS: 41, d: 0.61, clusterNo: 12, seed: 377, detectionId: 'd-91031', shape: 'slow', tags: [] }),
  e({ id: 'c-0378', queueId: 'q-15', channel: 'CH4_A2', startH: 214.880, durationS: 33, d: 0.33, seed: 378, detectionId: 'd-91035' }),
  e({ id: 'c-0379', queueId: 'q-15', channel: 'CH2_A1', startH: 217.305, durationS: 35, d: 0.36, seed: 379, detectionId: 'd-91040' }),
  e({ id: 'c-0380', queueId: 'q-15', channel: 'CH4_A2', startH: 219.644, durationS: 31, d: 0.39, seed: 380, detectionId: 'd-91046' }),
  e({ id: 'c-0381', queueId: 'q-15', channel: 'CH4_A2', startH: 222.012, durationS: 34, d: 0.42, seed: 381, detectionId: 'd-91051', shape: 'burst', tags: [] }),
]

const Q16: QueueEntry[] = Array.from({ length: 12 }, (_, i) => {
  const rec = i % 3 === 0 ? { recording: 'M2_aug fs1', channel: 'CH4_A2' } : i % 3 === 1 ? { recording: 'M3_jul', channel: 'CH3' } : { recording: 'L_LM_Jul26_J', channel: 'CH2' }
  return e({ id: `a-${2101 + i}`, queueId: 'q-16', unit: 'human span', ...rec, startH: +(12.4 + i * 14.35).toFixed(3), durationS: 24 + (i * 7) % 18, seed: 2101 + i, shape: i % 4 === 3 ? 'slow' : 'doublet', tags: [] })
})

const WIN_CHANNELS = WINDOW_SET.channels
const CLASS_NAMES = CLASSES.map(c => c.name)
const Q18: QueueEntry[] = Array.from({ length: 14 }, (_, i) => {
  const n = 1599 + i
  return e({ id: `w-${String(n).padStart(5, '0')}`, queueId: 'q-18', unit: 'window', channel: WIN_CHANNELS[i % 3], startH: +(i * 0.1667 + 40.0).toFixed(2), durationS: 600, seed: n, shape: 'window', block: 'train', tags: [],
    baseVerdict: i === 0 ? 'interesting' : i === 1 ? 'not_interesting' : undefined, baseClass: i === 0 ? 'slow-drift' : undefined })
})

const Q19_CALLS: { className: string; p: number }[] = [
  { className: 'slow-drift', p: 0.72 }, { className: 'burst', p: 0.81 }, { className: 'slow-drift', p: 0.64 }, { className: 'spike-train', p: 0.77 },
  { className: 'plateau', p: 0.58 }, { className: 'burst', p: 0.69 }, { className: 'electrode artifact', p: 0.91 }, { className: 'spike-train', p: 0.55 }, { className: 'slow-drift', p: 0.83 },
]
const Q19: QueueEntry[] = Array.from({ length: 9 }, (_, i) => {
  const n = 40209 + i
  const startH = i === 2 ? 3.166 : +(2.83 + i * 0.17 + (i > 2 ? 4.1 : 0)).toFixed(2)
  return e({ id: `w-${n}`, queueId: 'q-19', unit: 'window', channel: i === 2 ? 'CH2_A1' : WIN_CHANNELS[(i + 1) % 3], startH, durationS: 600, seed: n, shape: 'window', block: 'test',
    sampleIndex: 32 + i, modelCall: Q19_CALLS[i], tags: [],
    baseVerdict: i < 2 ? 'interesting' : undefined, baseClass: i === 0 ? 'slow-drift' : i === 1 ? 'burst' : undefined })
})

export const QUEUE_ENTRIES: Record<string, QueueEntry[]> = { 'q-12': Q12, 'q-15': Q15, 'q-16': Q16, 'q-18': Q18, 'q-19': Q19 }

/* ---------------- clusters ---------------- */
export interface ReviewCluster {
  no: number; queueId: string; kind: 'family set' | 'sequence'; badge: string; recording: string; runId: string; exemplar?: string
  family: { id: string; d: number }; artifact: 'low' | 'medium' | 'high'; cohesionLimit: number; members: string[]; defaultMember: string
  stripCaption: string; previousLine: string | null; nearestMember: string
}
export const CLUSTERS: ReviewCluster[] = [
  { no: 12, queueId: 'q-15', kind: 'family set', badge: 'seed-search matches', recording: 'M2_aug fs1', runId: 'r-0415', exemplar: 'E-0102', family: { id: 'F-03', d: 0.19 }, artifact: 'low',
    cohesionLimit: 0.45, members: ['c-0371', 'c-0372', 'c-0373', 'c-0374', 'c-0375', 'c-0376', 'c-0377'], defaultMember: 'c-0373', nearestMember: 'c-0371',
    stripCaption: 'seed-search matches of exemplar E-0102', previousLine: 'cluster 11 · 5 × interesting · 1 min ago' },
  { no: 13, queueId: 'q-12', kind: 'sequence', badge: 'sequence', recording: 'M2_aug fs1', runId: 'r-0412', family: { id: 'F-03', d: 0.21 }, artifact: 'low',
    cohesionLimit: 0.45, members: ['c-0350', 'c-0351', 'c-0352'], defaultMember: 'c-0350', nearestMember: 'c-0350',
    stripCaption: 'detections within 6 min on CH4_A2', previousLine: null },
]

/* ---------------- traces (synthetic, mV) ---------------- */
const gauss = (u: number, mu: number, s: number) => Math.exp(-((u - mu) ** 2) / (2 * s * s))

/** The motif itself, `n` samples, mV. */
export function motif(shape: QueueEntry['shape'], n: number, seed: number, shift = 0, amp = 1): number[] {
  const rnd = seeded(seed * 7 + 3)
  const jitter = (rnd() - 0.5) * 0.03
  return Array.from({ length: n }, (_, i) => {
    const u = i / Math.max(1, n - 1) - shift
    let v = 0
    if (shape === 'doublet') v = -0.36 * gauss(u, 0.12 + jitter, 0.05) + 0.40 * gauss(u, 0.30 + jitter, 0.045) - 0.38 * gauss(u, 0.46, 0.05) + 0.40 * gauss(u, 0.64 + jitter, 0.045) - 0.34 * gauss(u, 0.82, 0.05)
    else if (shape === 'slow') v = -0.26 * gauss(u, 0.28, 0.1) + 0.22 * gauss(u, 0.66, 0.14)
    else if (shape === 'burst') v = 0.3 * Math.sin(u * Math.PI * 9) * gauss(u, 0.5, 0.2)
    else v = -0.32 * gauss(u, 0.24, 0.035) + 0.28 * gauss(u, 0.36, 0.03) - 0.36 * gauss(u, 0.5, 0.04) + 0.3 * gauss(u, 0.64, 0.035) - 0.3 * gauss(u, 0.8, 0.04) + 0.12 * gauss(u, 0.12, 0.02)
    return +(v * amp).toFixed(4)
  })
}

export const CONTEXT_PAD_MAX = 300

/** Context around an entry at 1 Hz: `CONTEXT_PAD_MAX` s either side, the motif added in place. */
export function contextTrace(entry: QueueEntry): { values: number[]; t0_s: number } {
  const n = entry.durationS + 2 * CONTEXT_PAD_MAX
  const base = syntheticTrace({ n, seed: entry.seed, noise: 0.03 })
  const mean = base.reduce((a, b) => a + b, 0) / n
  const m = motif(entry.shape, entry.durationS, entry.seed)
  const values = base.map((v, i) => {
    const j = i - CONTEXT_PAD_MAX
    const wobble = 0.07 * Math.sin(i / 48 + entry.seed) + 0.035 * Math.sin(i / 17 + entry.seed * 2) + 0.02 * Math.sin(i / 7.3 + entry.seed)
    return +((v - mean) + wobble + (j >= 0 && j < m.length ? m[j] : 0)).toFixed(4)
  })
  return { values, t0_s: entry.startH * 3600 - CONTEXT_PAD_MAX }
}

export function shapeTrace(entry: QueueEntry): number[] {
  const n = entry.durationS
  const rnd = seeded(entry.seed + 11)
  return motif(entry.shape, n, entry.seed).map(v => +(v + (rnd() - 0.5) * 0.02).toFixed(4))
}

/** Thumbnail (48 samples, same mV scale as every other thumbnail in the queue). */
export function thumb(entry: QueueEntry): number[] {
  const rnd = seeded(entry.seed + 5)
  return motif(entry.shape, 48, entry.seed).map(v => +(v + (rnd() - 0.5) * 0.03).toFixed(4))
}

export function medoidTrace(familyId: string, n: number): number[] {
  if (familyId === 'F-03') return motif('doublet', n, 1846, 0.03, 0.95)
  if (familyId === 'F-11') return motif('burst', n, 1101)
  return motif('slow', n, 1107)
}

/* ---------------- nearest families, artifact, evidence ---------------- */
const fam = (id: string) => FAMILIES.find(f => f.id === id)!
/** F-11's member count is not in the §0 canon; the frame prints 17 (fog: review F24). */
const FRAME_MEMBER_COUNTS: Record<string, number> = { 'F-11': 17 }
export function nearestFamilies(entry: QueueEntry): NearestFamily[] {
  const r = seeded(entry.seed)
  const base = entry.shape === 'doublet' || entry.shape === 'window' ? [['F-03', 0.19], ['F-11', 0.37], ['F-07', 0.52]] : entry.shape === 'burst' ? [['F-11', 0.24], ['F-03', 0.41], ['F-07', 0.58]] : [['F-07', 0.22], ['F-03', 0.47], ['F-11', 0.55]]
  return base.map(([id, d], i) => {
    const f = fam(id as string)
    const dd = entry.id === 'c-0343' || i > 0 ? (d as number) : +Math.min(0.99, (d as number) + (r() - 0.5) * 0.08).toFixed(2)
    return { id: f.id, name: f.name, members: f.members ?? FRAME_MEMBER_COUNTS[f.id] ?? null, d: entry.d != null && i === 0 && entry.queueId === 'q-15' ? 0.19 : dd, colour: FAMILY_COLOURS[f.id] }
  })
}

export function artifactFactors(entry: QueueEntry): ArtifactFactors {
  const r = seeded(entry.seed + 99)
  const p = entry.id === 'c-0377' ? 0.28 : entry.modelCall?.className === 'electrode artifact' ? 0.71 : entry.id === 'c-0343' ? 0.12 : +(0.06 + r() * 0.2).toFixed(2)
  return { level: p < 0.33 ? 'low' : p < 0.66 ? 'medium' : 'high', p, coherence: entry.id === 'c-0343' ? 0.08 : +(0.03 + r() * 0.12).toFixed(2), clipping: 'none', stepChange: p >= 0.66 ? 'at 41 s' : 'none', electrodeFlag: p >= 0.66 ? 'CH7_B2 impedance' : 'none' }
}

/** Per-channel coherence in the span for Other channels (frame 1b: CH1_A1 0.06, CH2_A1 0.11, CH3_A2 0.04, CH5_B1 0.09, CH6_B1 0.02). */
const R_FRAME: Record<string, number> = { CH1_A1: 0.06, CH2_A1: 0.11, CH3_A2: 0.04, CH5_B1: 0.09, CH6_B1: 0.02 }
export function otherChannels(entry: QueueEntry): { channel: string; r: number | null; values: number[]; current: boolean }[] {
  const rec = RECORDINGS.find(x => x.label === entry.recording)
  const chans = rec ? rec.channels : [entry.channel]
  const ctx = contextTrace(entry)
  return chans.map((ch, i) => {
    if (ch === entry.channel) return { channel: ch, r: null, values: ctx.values, current: true }
    const base = syntheticTrace({ n: ctx.values.length, seed: entry.seed * 31 + i, noise: 0.03 })
    const mean = base.reduce((a, b) => a + b, 0) / base.length
    const r = seeded(entry.seed + i * 13)
    const faint = motif(entry.shape, entry.durationS, entry.seed).map(v => v * 0.12)
    const values = base.map((v, k) => { const j = k - CONTEXT_PAD_MAX; return +((v - mean) + 0.07 * Math.sin(k / 45 + i) + 0.03 * Math.sin(k / 13 + i * 2) + (j >= 0 && j < faint.length ? faint[j] : 0)).toFixed(4) })
    return { channel: ch, r: R_FRAME[ch] ?? +(0.01 + r() * 0.14).toFixed(2), values, current: false }
  })
}

export interface Evidence {
  origin: { runKind: string; runId: string | null; template: string | null; stages: { label: string; full: string }[]; recipeHash: string | null; ran: string; by: string; scope: string; windowSet?: string; block?: string; sample?: string }
  detection: { score: number | null; threshold: number | null; recommended: number | null; rank: string | null; nullExpects: string | null; samples: string; fs: string } | null
  alsoFoundBy: { runs: { run: string; kind: string; badge: string; match: string }[]; human: string; prior: string }
  history: { revisions: string; queues: string }
  writeTarget: string
}

export function evidence(entry: QueueEntry, queue: ReviewQueue): Evidence {
  const rec = RECORDINGS.find(r => r.label === entry.recording)
  const fs = rec?.fs_hz ?? 1
  const s0 = Math.round(entry.startH * 3600 * fs), s1 = s0 + Math.round(entry.durationS * fs)
  const samples = `${s0.toLocaleString('en-US')} → ${s1.toLocaleString('en-US')}`
  const fsTxt = `fs ${fs} Hz${rec?.fs_note ? ` (${rec.fs_note})` : ''}`
  if (entry.unit === 'window') {
    return {
      origin: { runKind: queue.source === 'model-verification' ? 'verification sample' : 'training windows', runId: null, template: queue.template ?? 'cnn_windows_v3', stages: [], recipeHash: null, ran: '13 Sep 2026', by: ACTOR,
        scope: `${WINDOW_SET.recording} · ${WINDOW_SET.channels.length} channels · ${WINDOW_SET.length_s} s windows`, windowSet: `${WINDOW_SET.id} v${WINDOW_SET.version}`, block: entry.block === 'test' ? 'test block' : 'train block',
        sample: entry.sampleIndex ? `${entry.sampleIndex} of ${queue.total}` : undefined },
      detection: null,
      alsoFoundBy: { runs: [], human: 'none overlapping', prior: 'none' },
      history: { revisions: 'n/a · windows are fixed', queues: queue.title },
      writeTarget: `Writes one window verdict on ${WINDOW_SET.id} · window ${entry.id.slice(2)}.`,
    }
  }
  if (entry.unit === 'human span') {
    return {
      origin: { runKind: 'human span', runId: null, template: null, stages: [], recipeHash: null, ran: 'taken for Review 15 Sep 2026', by: ACTOR, scope: `${entry.recording} · ${entry.channel}` },
      detection: null,
      alsoFoundBy: { runs: [], human: `annotation ${entry.id}`, prior: 'none' },
      history: { revisions: 'rev 1 · human', queues: queue.title },
      writeTarget: `Writes one annotation verdict on ${entry.id}.`,
    }
  }
  const isSeed = queue.source === 'seed-search'
  return {
    origin: {
      runKind: isSeed ? 'seed search' : 'template', runId: queue.runId ?? null, template: isSeed ? `seed search · exemplar ${queue.exemplar}` : 'mp_drops_v3 · v3',
      stages: isSeed ? [{ label: 'Source', full: 'Source' }, { label: 'Seed', full: 'Seeded search' }, { label: 'Threshold', full: 'Threshold to spans' }]
        : [{ label: 'Source', full: 'Source' }, { label: 'Bandpass', full: 'Bandpass filter' }, { label: 'Matrix profile', full: 'Matrix profile' }, { label: 'Threshold', full: 'Threshold to spans' }],
      recipeHash: isSeed ? '5c27…e41b' : 'a91f…3c0e', ran: isSeed ? '14 Sep 2026' : '12 Sep 2026', by: ACTOR, scope: `${entry.recording} · 3 channels · 721 h`,
    },
    detection: {
      score: entry.score ?? null, threshold: isSeed ? null : 0.62, recommended: isSeed ? null : 0.62,
      rank: entry.rank ? `${entry.rank} of ${queue.total.toLocaleString('en-US')}` : null, nullExpects: isSeed ? null : '210 on scope · run 6.1×',
      samples: entry.id === 'c-0343' ? '51,726 → 51,761' : samples, fs: fsTxt,
    },
    alsoFoundBy: {
      runs: entry.id === 'c-0343' ? [{ run: 'r-0415 seed search', kind: 'seed search', badge: 'seed', match: 'match d 2.9' }] : isSeed ? [{ run: 'r-0412 mp_drops_v3', kind: 'template', badge: 'template', match: 'score 0.79' }] : [],
      human: 'none overlapping', prior: 'none · not a rediscovery',
    },
    history: { revisions: 'none', queues: entry.id === 'c-0343' ? 'Discovery r-0412 · Seed r-0415' : queue.title.replace(' · ', ' ') },
    writeTarget: `Writes one adjudication row on ${entry.detectionId}.`,
  }
}

export const REVIEW_TAG_SUGGESTIONS = ['spike-train', 'regular', 'decaying']
