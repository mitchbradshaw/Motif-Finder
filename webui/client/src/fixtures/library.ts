/* Library fixtures (frames library-1 … library-7, inventory webui/pages/inventory/library.md).
 * Demo data only: the §0 canon supplies recordings, channels, families, window set, models and templates;
 * everything else here is the frame's placeholder numbers. Traces are synthetic, in mV, never normalised. */
import { ACTOR, CLASSES, FAMILY_COLOURS, RECORDINGS, WINDOW_SET, seeded } from './canon'

/* ================================================================ shapes ================================================================ */
export type ShapeKind = 'drop' | 'burst' | 'sharkfin' | 'spiketrain' | 'ripple' | 'plateau' | 'drift' | 'fall' | 'peak' | 'notch'
const g = (u: number, c: number, w: number) => Math.exp(-((u - c) ** 2) / (2 * w * w))

/** A synthetic motif waveform in mV (detrended, never normalised). `amp` is the stated depth/amplitude in mV. */
export function motifShape(kind: ShapeKind, amp: number, seed: number, opts: { n?: number; jitter?: number; noise?: number } = {}): number[] {
  const n = opts.n ?? 120, rnd = seeded(seed * 7919 + 13), jit = opts.jitter ?? 0.03, noise = opts.noise ?? 0.012
  const sh = (rnd() - 0.5) * jit, sc = 1 + (rnd() - 0.5) * jit * 3
  const a = Math.abs(amp) * sc, sign = amp < 0 ? -1 : 1
  const out: number[] = []
  for (let i = 0; i < n; i++) {
    const u = i / (n - 1) - sh
    let v = 0
    switch (kind) {
      case 'drop': v = sign * a * g(u, 0.52, 0.1) + 0.02 * u; break
      case 'burst': v = a * Math.sin(2 * Math.PI * 3 * (u - 0.08)) * g(u, 0.5, 0.2); break
      case 'sharkfin': v = a * (g(u, 0.42, 0.085) - g(u, 0.63, 0.065)); break
      case 'spiketrain': v = -a * [0.2, 0.4, 0.6, 0.8].reduce((s, c) => s + g(u, c, 0.03), 0) + 0.02; break
      case 'ripple': v = a * 0.92 * g(u, 0.45, 0.2) * (1 + 0.08 * Math.sin(u * 14)); break
      case 'plateau': v = a * (g(u, 0.36, 0.06) + g(u, 0.64, 0.06)) * 0.95; break
      case 'drift': v = a * Math.tanh((u - 0.5) * 3) - 0.02; break
      case 'fall': v = u < 0.3 ? a * 0.08 * g(u, 0.2, 0.05) : -a * Math.exp(-(u - 0.3) * 7) * Math.min(1, (u - 0.3) * 40) + a * 0.12 * (u - 0.3); break
      case 'peak': v = a * g(u, 0.5, 0.025) - 0.03; break
      case 'notch': v = -a * 0.5 * g(u, 0.44, 0.04) + a * g(u, 0.55, 0.03) - 0.04 * (u - 0.5); break
    }
    out.push(+(v + (rnd() - 0.5) * noise).toFixed(4))
  }
  return out
}

/** A nice symmetric mV domain with headroom: max |v| → ±ceil to 0.1 mV. Shared by every plot on a page (D5). */
export function niceMvDomain(series: number[][], step = 0.1): [number, number] {
  let m = 0
  for (const s of series) for (const v of s) if (Math.abs(v) > m) m = Math.abs(v)
  const top = Math.ceil((m + 0.05) / step - 1e-6) * step
  return [-+top.toFixed(3), +top.toFixed(3)]
}

/* ================================================================ library, groupings ================================================================ */
export const LIBRARY_COUNTS = { motifs: 1402, windowSets: 6, templates: 14, spikeTrains: 16, sequences: 350 }

export type Unit = 'motifs' | 'sequences' | 'spike-trains'
export const UNIT_LABEL: Record<Unit, string> = { motifs: 'single motifs', sequences: 'sequences', 'spike-trains': 'spike trains' }
export type BasisKind = 'shape-distance' | 'sequence-similarity' | 'amplitude' | 'timescale' | 'frequency-content' | 'polarity' | 'tag' | 'provenance' | 'custom'

export interface Grouping {
  id: string; unit: Unit; basis: BasisKind; basisLabel: string; params: string; chip: [string, string]
  computed: string; motifs: number; families: number; omitted: number; handEditsKept: number; note?: string
}
export const GROUPINGS: Grouping[] = [
  { id: 'g-07', unit: 'motifs', basis: 'shape-distance', basisLabel: 'shape distance · Ward', params: 'cut 0.42', chip: ['shape distance', 'Ward · cut 0.42'], computed: '14 Sep 2026', motifs: 1402, families: 10, omitted: 38, handEditsKept: 14 },
  { id: 'g-08', unit: 'sequences', basis: 'sequence-similarity', basisLabel: 'sequence similarity', params: 'cut 0.50', chip: ['cut 0.50', 'sequence similarity'], computed: '14 Sep 2026', motifs: 1402, families: 6, omitted: 1035, handEditsKept: 1 },
  { id: 'g-01', unit: 'motifs', basis: 'shape-distance', basisLabel: 'shape distance · Ward', params: 'cut 0.42', chip: ['shape distance', 'Ward · cut 0.42'], computed: '2 Sep 2026', motifs: 410, families: 7, omitted: 12, handEditsKept: 0, note: 'first import' },
]
/** What the grouping editor saves when applied from the frame-4 settings (frequency content, log-spaced, 6 bins). */
export const GROUPING_G09: Grouping = { id: 'g-09', unit: 'motifs', basis: 'frequency-content', basisLabel: 'frequency content · log-spaced', params: '6 bins · 0.002–0.5 Hz', chip: ['frequency content', 'log · 6 bins'], computed: '16 Sep 2026', motifs: 1402, families: 5, omitted: 21, handEditsKept: 14 }

/* ================================================================ recordings / recurrence ================================================================ */
export interface RecGroup { key: string; label: string; hours: number; reviewedPct: number; channels: string[]; hiddenChannels: number; fsNote?: string; heldOut?: boolean; resampleOf?: string }
const rec = (k: string) => RECORDINGS.find(r => r.key === k)!
export const RECURRENCE_RECORDINGS: RecGroup[] = [
  { key: 'M2_aug_fs1', label: rec('M2_aug_fs1').label, hours: 721, reviewedPct: 31, channels: rec('M2_aug_fs1').channels.slice(0, 6), hiddenChannels: 10 },
  { key: 'M3_jul', label: rec('M3_jul').label, hours: 280, reviewedPct: 18, channels: rec('M3_jul').channels.slice(0, 4), hiddenChannels: 4 },
  { key: 'L_LM_Jul26_J', label: rec('L_LM_Jul26_J').label, hours: 22.4, reviewedPct: 5, channels: rec('L_LM_Jul26_J').channels, hiddenChannels: 0, fsNote: '10 Hz inferred' },
  { key: 'M2_aug_fs2', label: rec('M2_aug_fs2').label, hours: 721, reviewedPct: 31, channels: rec('M2_aug_fs2').channels.slice(0, 6), hiddenChannels: 10, resampleOf: 'M2_aug_fs1' },
  { key: 'M4_aug', label: rec('M4_aug').label, hours: 300, reviewedPct: 0, channels: [], hiddenChannels: 16, heldOut: true },
]

export interface Cell { perHour: number | null; count: number; artifact?: boolean; noCoverage?: boolean }
/* frame-1 cells, members / h; `–` reviewed none; `?` no reviewed coverage; `!` cross-channel artifact */
const CELL_ROWS: Record<string, string> = {
  'F-01': '.70 .94 .21 .60 .65 .71 | – – – .17 | ? ? – – –',
  'F-02': '– – .18 .21 .21 .16 | .26 .68 .23 .88 | ? ? – – –',
  'F-03': '– – !.61 !.61 – – | .82 .80 .56 .23 | .54 .83 .76 .23 .94',
  'F-04': '.38 .65 .36 .43 .37 .94 | – .25 .24 – | ? ? – – –',
  'F-05': '.88 .55 .35 .70 .79 .38 | – – – .20 | ? ? – – –',
  'F-06': '– – .21 .14 – .16 | – – – – | ? ? – – –',
  'F-07': '.88 .60 .79 .75 .94 .30 | .20 – – .19 | .55 .67 .29 .97 .41',
  'F-08': '– .15 – .16 – – | – .25 .24 – | ? ? – – –',
  'F-09': '.63 .78 .47 .82 .35 .72 | .92 .67 .66 .28 | ? ? – – –',
  'F-10': '.53 .89 .90 .21 .73 .90 | – – – – | ? ? – – –',
}
export const COVERAGE: Record<string, number> = {
  ...Object.fromEntries(rec('M2_aug_fs1').channels.slice(0, 6).map(c => [`M2_aug_fs1:${c}`, 0.31])),
  ...Object.fromEntries(rec('M2_aug_fs2').channels.slice(0, 6).map(c => [`M2_aug_fs2:${c}`, 0.31])),
  'M3_jul:CH1': 0.2, 'M3_jul:CH2': 0.25, 'M3_jul:CH3': 0.1, 'M3_jul:CH4': 0.18,
  'L_LM_Jul26_J:CH1': 0, 'L_LM_Jul26_J:CH2': 0, 'L_LM_Jul26_J:CH3': 0.08, 'L_LM_Jul26_J:CH4': 0.08, 'L_LM_Jul26_J:CH5': 0.08,
}
/** The canon demo selection (frame 1) — and the atlas scope (frame 2). */
export const CANON_SELECTION = ['M2_aug_fs1:CH3_A2', 'M2_aug_fs1:CH4_A2', 'M3_jul:CH2']
export const SHARED_GROUND: { pair: [string, string]; family: string }[] = [{ pair: ['M2_aug_fs1:CH3_A2', 'M2_aug_fs1:CH4_A2'], family: 'F-03' }]
export const recHours = (key: string) => RECURRENCE_RECORDINGS.find(r => r.key === key)?.hours ?? 0

/* ================================================================ motif families (g-07) ================================================================ */
export interface MotifFamily {
  id: string; name: string; colour: string; shape: ShapeKind; members: number; inScope: number; recordings: number; hand: number; artifact: number
  durationS: number; durationSd: number; depthMv: number | null; depthLabel: string; judgedPct: number; judged: number
  exemplar: string; medoid: string; exemplarMedoidD: number; meanMemberD: number; snrDb: number
  artifactChannels: number; propChannels: number; indChannels: number; edges: string
  cells: Record<string, Cell>; exemplarTrace: number[]; medoidTrace: number[]; ampBins: number[]
  /** fixup-b: the unit the traces are in (null: the recordings declare none) and, when some members' recordings
   *  declare no unit, which and where to fix it. Absent on the fixture: mV. */
  unit?: 'mV' | null; unitNote?: string | null; undeclaredMembers?: number
}
const FAM_ROWS: [string, string, ShapeKind, number, number, number, number, number, number, number, number, string, number][] = [
  // id, name, shape, inScope, members, recordings, hand, artifact, duration s, depth mV, judged %, depth label, dur sd
  ['F-01', 'single drop', 'drop', 61, 140, 2, 0, 0, 1.2, -0.34, 52, '−0.34 mV', 0.2],
  ['F-02', 'fast burst', 'burst', 22, 42, 2, 0, 0, 0.8, 0.45, 31, '±0.45 mV', 0.1],
  ['F-03', 'sharkfin', 'sharkfin', 44, 112, 3, 3, 2, 21, 0.21, 39, '±0.21 mV', 4],
  ['F-04', 'spike train', 'spiketrain', 37, 58, 2, 0, 0, 4.2, -0.11, 62, '−0.11 mV', 0.6],
  ['F-05', 'slow ripple', 'ripple', 31, 49, 2, 0, 0, 3.8, 0.65, 20, '+0.65 mV', 0.7],
  ['F-06', 'plateau', 'plateau', 12, 26, 1, 0, 0, 4.6, 0.31, 75, '+0.31 mV', 0.8],
  ['F-07', 'slow drift', 'drift', 58, 212, 3, 1, 0, 38, 0.08, 12, '±0.08 mV', 9],
  ['F-08', 'long fall', 'fall', 19, 22, 2, 0, 0, 44, -0.52, 45, '−0.52 mV', 6],
  ['F-09', 'sharp peak', 'peak', 71, 96, 2, 0, 0, 0.9, 0.48, 66, '+0.48 mV', 0.1],
  ['F-10', 'notch', 'notch', 57, 81, 1, 0, 0, 2.1, -0.27, 8, '−0.27 mV', 0.4],
]

function parseCells(id: string): Record<string, Cell> {
  const groups = CELL_ROWS[id].split('|').map(s => s.trim().split(/\s+/))
  const out: Record<string, Cell> = {}
  RECURRENCE_RECORDINGS.slice(0, 3).forEach((r, gi) => r.channels.forEach((ch, ci) => {
    const tok = groups[gi][ci]
    const k = `${r.key}:${ch}`
    if (tok === '?') out[k] = { perHour: null, count: 0, noCoverage: true }
    else if (tok === '–') out[k] = { perHour: null, count: 0 }
    else out[k] = { perHour: Number(tok.replace('!', '')), count: 0, artifact: tok.startsWith('!') }
  }))
  // fs2 is a resample of fs1: same cells
  RECURRENCE_RECORDINGS[0].channels.forEach((ch, i) => { out[`M2_aug_fs2:${RECURRENCE_RECORDINGS[3].channels[i]}`] = { ...out[`M2_aug_fs1:${ch}`] } })
  return out
}
/** Integer split of `total` over weights, exact sum (largest remainder). */
function split(total: number, weights: number[]): number[] {
  const W = weights.reduce((a, b) => a + b, 0)
  if (!W) return weights.map(() => 0)
  const raw = weights.map(w => (total * w) / W), fl = raw.map(Math.floor)
  let left = total - fl.reduce((a, b) => a + b, 0)
  raw.map((v, i) => [v - fl[i], i] as const).sort((a, b) => b[0] - a[0]).forEach(([, i]) => { if (left > 0 && weights[i] > 0) { fl[i]++; left-- } })
  return fl
}
function ampBins(center: number, seed: number): number[] {
  const rnd = seeded(seed)
  return Array.from({ length: 12 }, (_, i) => Math.round(24 * Math.exp(-((i - center) ** 2) / 6) + rnd() * 3 + 1))
}

export const MOTIF_FAMILIES: MotifFamily[] = FAM_ROWS.map(([id, name, shape, inScope, members, recordings, hand, artifact, durationS, depthMv, judgedPct, depthLabel, durationSd], i) => {
  const cells = parseCells(id)
  const scopeKeys = CANON_SELECTION, otherKeys = Object.keys(cells).filter(k => !scopeKeys.includes(k) && !k.startsWith('M2_aug_fs2'))
  split(inScope, scopeKeys.map(k => cells[k]?.perHour ?? 0)).forEach((c, j) => { cells[scopeKeys[j]].count = c })
  split(members - inScope, otherKeys.map(k => cells[k].perHour ?? 0)).forEach((c, j) => { cells[otherKeys[j]].count = c })
  RECURRENCE_RECORDINGS[0].channels.forEach((ch, j) => { cells[`M2_aug_fs2:${RECURRENCE_RECORDINGS[3].channels[j]}`].count = cells[`M2_aug_fs1:${ch}`].count })
  const isF03 = id === 'F-03'
  return {
    id, name, colour: FAMILY_COLOURS[id], shape, members, inScope, recordings, hand, artifact, durationS, durationSd, depthMv, depthLabel, judgedPct,
    judged: isF03 ? 44 : Math.round((members * judgedPct) / 100),
    exemplar: isF03 ? 'E-0102' : `E-01${String(10 + i * 7).padStart(2, '0')}`, medoid: isF03 ? 'm-1846' : `m-${1200 + i * 97}`,
    exemplarMedoidD: isF03 ? 0.07 : +(0.05 + i * 0.013).toFixed(2), meanMemberD: isF03 ? 0.24 : +(0.18 + (i % 4) * 0.03).toFixed(2), snrDb: isF03 ? 18.4 : +(12 + (i * 3.7) % 9).toFixed(1),
    artifactChannels: artifact, propChannels: isF03 ? 4 : (i % 3), indChannels: isF03 ? 1 : 1 + (i % 2), edges: `z-norm Euclid · cut 0.42 · ${isF03 ? 'a7f3…9c' : `${(0x3a1 + i * 1301).toString(16)}…${(i * 37 + 16).toString(16)}`}`,
    cells, exemplarTrace: motifShape(shape, depthMv, 100 + i, { jitter: 0.02 }), medoidTrace: motifShape(shape, depthMv * 0.94, 200 + i, { jitter: 0.06 }),
    ampBins: ampBins(isF03 ? 5 : 3 + (i % 6), 300 + i),
  }
})
export const AMP_DOMAIN: [number, number] = [0.1, 0.4]

/* ================================================================ sequence families (g-08) ================================================================ */
export interface SequenceFamily {
  id: string; name: string; colour: string; sequences: number; composition: string[]; compositionLabel: string; recordings: number; hand: number
  durationLabel: string; gapLabel: string; judgedPct: number; exemplar: string; motifs: number; exemplarMedoidD: number; orderKept: number
  meanMemberD: number; judgedMotifs: number; gapS: string; exemplarTrace: number[]; medoidTrace: number[]
  unit?: 'mV' | null; unitNote?: string | null
}
const famBy = (id: string) => MOTIF_FAMILIES.find(f => f.id === id)!
function seqTrace(comp: string[], gapFrac: number, seed: number, scale = 1): number[] {
  const n = 160, out = new Array(n).fill(0).map((_, i) => 0.01 * Math.sin(i / 9 + seed))
  const each = Math.floor((n - gapFrac * n * (comp.length - 1)) / comp.length)
  comp.forEach((fid, k) => {
    const f = famBy(fid), start = Math.round(k * (each + gapFrac * n))
    const s = motifShape(f.shape, (f.depthMv ?? 0) * scale, seed + k * 11, { n: each, noise: 0.008 })
    s.forEach((v, j) => { if (start + j < n) out[start + j] += v })
  })
  return out.map(v => +v.toFixed(4))
}
const SEQ_ROWS: [string, string, number, string[], string, number, number, string, string, number, number][] = [
  ['S-01', 'drop triplet', 34, ['F-01', 'F-01', 'F-01'], 'F-01 · F-01 · F-01', 3, 0, '~38 s', 'gaps 12 s ± 3', 41, 0.18],
  ['S-02', 'sharkfin → peak', 21, ['F-03', 'F-09'], 'F-03 · F-09', 2, 0, '~22 s', 'gap 14 s ± 2', 52, 0.3],
  ['S-03', 'burst run', 18, ['F-02', 'F-02', 'F-02', 'F-02'], 'F-02 × 4', 2, 1, '~30 s', 'gaps 6 s ± 1', 28, 0.08],
  ['S-04', 'ripple then fall', 10, ['F-05', 'F-08'], 'F-05 · F-08', 1, 0, '~70 s', 'gap 31 s ± 9', 67, 0.1],
  ['S-05', 'peak pair', 27, ['F-09', 'F-09'], 'F-09 · F-09', 2, 0, '~11 s', 'gap 8 s ± 1', 59, 0.3],
  ['S-06', 'notch train', 12, ['F-10', 'F-10', 'F-10', 'F-10', 'F-10'], 'F-10 × 5', 1, 0, '~52 s', 'gaps 10 s ± 4', 17, 0.05],
]
export const SEQUENCE_FAMILIES: SequenceFamily[] = SEQ_ROWS.map(([id, name, sequences, composition, compositionLabel, recordings, hand, durationLabel, gapLabel, judgedPct, gapFrac], i) => {
  const isS02 = id === 'S-02'
  const motifs = sequences * composition.length
  return {
    id, name, colour: FAMILY_COLOURS[`F-0${i + 1}`], sequences, composition, compositionLabel, recordings, hand, durationLabel, gapLabel, judgedPct,
    exemplar: isS02 ? 'E-0311' : `E-03${String(i * 4 + 1).padStart(2, '0')}`, motifs, exemplarMedoidD: isS02 ? 0.11 : +(0.08 + i * 0.02).toFixed(2),
    orderKept: isS02 ? 19 : Math.round(sequences * 0.9), meanMemberD: isS02 ? 0.31 : +(0.22 + i * 0.02).toFixed(2), judgedMotifs: isS02 ? 23 : Math.round((motifs * judgedPct) / 100),
    gapS: gapLabel.replace(/^gaps? /, ''),
    exemplarTrace: seqTrace(composition, gapFrac, 500 + i), medoidTrace: seqTrace(composition, gapFrac, 600 + i, 0.9),
  }
})

/* ================================================================ omitted ================================================================ */
export interface OmittedEntry { id: string; kind: 'motif' | 'sequence'; nearest: string; d: number; recording: string; channel: string; onsetH: number; shape: ShapeKind; amp: number | null; seed: number }
function omitted(n: number, kind: 'motif' | 'sequence', prefix: string, seed0: number, seqNearest = false): OmittedEntry[] {
  const rnd = seeded(seed0)
  const recs = [['M2_aug fs1', ['CH3_A2', 'CH4_A2', 'CH1_A1', 'CH6_B1']], ['M3_jul', ['CH1', 'CH2', 'CH4']], ['L_LM_Jul26_J', ['CH3', 'CH5']]] as const
  return Array.from({ length: n }, (_, i) => {
    const f = MOTIF_FAMILIES[Math.floor(rnd() * 10)], r = recs[Math.floor(rnd() * 3)]
    const hours = r[0] === 'L_LM_Jul26_J' ? 22.4 : r[0] === 'M3_jul' ? 280 : 721
    return {
      id: `${prefix}${String(2000 + i * 3 + Math.floor(rnd() * 2)).padStart(4, '0')}`, kind, nearest: seqNearest ? SEQUENCE_FAMILIES[i % 6].id : f.id,
      d: +(0.51 + rnd() * 0.36).toFixed(2), recording: r[0], channel: r[1][Math.floor(rnd() * r[1].length)], onsetH: +(rnd() * hours).toFixed(2),
      shape: f.shape, amp: Math.max(-0.4, Math.min(0.4, f.depthMv ?? 0)) * (0.7 + rnd() * 0.5), seed: seed0 + i,
    }
  })
}
export const OMITTED_G07 = omitted(38, 'motif', 'm-', 71)
export const OMITTED_G08_SINGLES = omitted(1018, 'motif', 'm-', 910)
export const OMITTED_G08_SEQUENCES = omitted(17, 'sequence', 'sq-', 1210, true)

/* ================================================================ family detail (F-03) ================================================================ */
export type Verdict = 'unjudged' | 'seed' | 'interesting' | 'not interesting' | 'artifact'
export interface Revision { rev: number; spanId: string; origin: 'machine' | 'human edit'; run: string; role: string }
export interface Member {
  id: string; role?: 'exemplar' | 'medoid'; addedByHand?: boolean; d: number; recording: string; channel: string; onsetH: number; durationS: number; amplitudeMv: number | null
  verdict: Verdict; verdictAt?: string; foundBy: string; revisions: Revision[]; tags: string[]; cls?: string; note?: string; seed: number
  handRecord?: string
}
export interface RemovedMember { id: string; d: number; channel: string; recording: string; removedAt: string; note: string; seed: number }
export interface FamilyDetail {
  family: MotifFamily; cut: number; members: Member[]; removed: RemovedMember[]; channels: number; depthLabel: string; handAdded: number
}

const P1: [string, number, string, number, Verdict, string?][] = [
  ['m-1846', 0.0, 'CH4_A2', 121.4, 'unjudged', 'medoid'], ['E-0102', 0.07, 'CH3_A2', 112.0, 'seed', 'exemplar'], ['m-1843', 0.12, 'CH3_A2', 130.8, 'unjudged'],
  ['m-1844', 0.14, 'CH3_A2', 140.2, 'interesting'], ['m-1845', 0.16, 'CH4_A2', 149.6, 'unjudged'], ['m-1847', 0.21, 'CH3_A2', 168.4, 'artifact'],
  ['m-1848', 0.23, 'CH4_A2', 177.8, 'unjudged'], ['m-1849', 0.25, 'CH4_A2', 187.2, 'interesting'], ['m-1852', 0.31, 'CH3_A2', 215.4, 'not interesting'],
]
function f03Members(): Member[] {
  const out: Member[] = P1.map(([id, d, ch, onset, verdict, role], i) => ({
    id, d, channel: ch, recording: 'M2_aug fs1', onsetH: onset, durationS: +(19.5 + (i % 5) * 0.8).toFixed(1), amplitudeMv: +(0.19 + (i % 4) * 0.015).toFixed(3),
    verdict, verdictAt: verdict === 'unjudged' ? undefined : `${9 + (i % 4)} Sep`, role: role as Member['role'], foundBy: id === 'E-0102' ? 'Review seed (S) · q-12' : 'run #128 drop_motifs9',
    revisions: id === 'm-1846'
      ? [{ rev: 1, spanId: 'd-0412', origin: 'machine', run: '#128', role: 'what re-runs match' }, { rev: 2, spanId: 'a-2077', origin: 'human edit', run: '—', role: 'current' }]
      : [{ rev: 1, spanId: `d-${88300 + i * 11}`, origin: 'machine', run: '#128', role: 'current' }],
    tags: i % 3 === 0 ? ['sharkfin'] : [], cls: verdict === 'artifact' ? 'electrode artifact' : undefined, seed: 400 + i,
  }))
  out.push({
    id: 'm-1850', addedByHand: true, d: 0.47, channel: 'CH4_A2', recording: 'M2_aug fs1', onsetH: 196.6, durationS: 21.6, amplitudeMv: 0.23, verdict: 'interesting', verdictAt: '12 Sep',
    foundBy: 'r-0415 seed search', revisions: [{ rev: 1, spanId: 'd-88402', origin: 'machine', run: 'r-0415', role: 'what re-runs match' }, { rev: 2, spanId: 'a-2091', origin: 'human edit', run: '—', role: 'current' }],
    tags: ['sharkfin', 'clean'], cls: 'burst', note: 'rise starts before the window does', seed: 499, handRecord: 'added to F-03 · this installation · 14 Sep',
  })
  // the remaining 102 (pages 2–12): 38 judged (1 artifact), 64 unjudged; spread over the three recordings
  const rnd = seeded(8081)
  const spread: [string, string, number][] = [['M2_aug fs1', 'CH3_A2', 721], ['M2_aug fs1', 'CH4_A2', 721], ...['CH1', 'CH2', 'CH3', 'CH4'].map(c => ['M3_jul', c, 280] as [string, string, number]), ...['CH1', 'CH2', 'CH3', 'CH4', 'CH5'].map(c => ['L_LM_Jul26_J', c, 22.4] as [string, string, number])]
  const verdicts: Verdict[] = [...Array(1).fill('artifact'), ...Array(20).fill('interesting'), ...Array(17).fill('not interesting'), ...Array(64).fill('unjudged')]
  for (let i = verdicts.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [verdicts[i], verdicts[j]] = [verdicts[j], verdicts[i]] }
  for (let i = 0; i < 102; i++) {
    const [r, ch, hours] = spread[i % spread.length]
    const id = i === 60 ? 'm-1971' : `m-${1853 + i + (i >= 49 ? 1 : 0)}`
    out.push({
      id, addedByHand: id === 'm-1971' || undefined, d: +(0.31 + (i / 101) * 0.11).toFixed(2), recording: r, channel: ch, onsetH: +(rnd() * hours).toFixed(1),
      durationS: +(17 + rnd() * 8).toFixed(1), amplitudeMv: +(0.16 + rnd() * 0.1).toFixed(3), verdict: verdicts[i], verdictAt: verdicts[i] === 'unjudged' ? undefined : `${5 + Math.floor(rnd() * 9)} Sep`,
      foundBy: i % 4 === 0 ? 'r-0415 seed search' : 'run #128 drop_motifs9', revisions: [{ rev: 1, spanId: `d-${89000 + i * 7}`, origin: 'machine', run: i % 4 === 0 ? 'r-0415' : '#128', role: 'current' }],
      tags: [], cls: verdicts[i] === 'artifact' ? 'electrode artifact' : undefined, seed: 600 + i,
      handRecord: id === 'm-1971' ? 'added to F-03 · this installation · 13 Sep' : undefined,
    })
  }
  return out
}
export const F03_DETAIL: FamilyDetail = {
  family: famBy('F-03'), cut: 0.42, members: f03Members(), channels: 5, depthLabel: '0.21 mV ± 0.05', handAdded: 2,
  removed: [{ id: 'm-1902', d: 0.39, channel: 'CH3_A2', recording: 'M2_aug fs1', removedAt: '13 Sep', note: 'propagated copy', seed: 902 }],
}
/** Generic member list for the other g-07 families (not drawn in any frame): seeded, verdict totals match the card. */
export function genericFamilyMembers(f: MotifFamily): Member[] {
  const rnd = seeded(f.id.charCodeAt(3) * 131)
  const recs: [string, string[], number][] = [['M2_aug fs1', ['CH1_A1', 'CH2_A1', 'CH3_A2', 'CH4_A2', 'CH5_B1', 'CH6_B1'], 721], ['M3_jul', ['CH1', 'CH2', 'CH3', 'CH4'], 280], ['L_LM_Jul26_J', ['CH1', 'CH2', 'CH3', 'CH4', 'CH5'], 22.4]]
  return Array.from({ length: f.members }, (_, i) => {
    const [r, chs, hours] = recs[i % f.recordings]
    const verdict: Verdict = i === 1 ? 'seed' : i < f.judged ? (i % 3 === 0 ? 'not interesting' : 'interesting') : 'unjudged'
    return {
      id: i === 0 ? f.medoid : i === 1 ? f.exemplar : `m-${f.id.slice(2)}${String(i).padStart(3, '0')}`, role: i === 0 ? 'medoid' : i === 1 ? 'exemplar' : undefined,
      d: i === 0 ? 0 : i === 1 ? f.exemplarMedoidD : +(0.08 + (i / f.members) * 0.33).toFixed(2), recording: r, channel: chs[Math.floor(rnd() * chs.length)], onsetH: +(rnd() * hours).toFixed(1),
      durationS: +(f.durationS + (rnd() - 0.5) * f.durationSd * 2).toFixed(1), amplitudeMv: +Math.abs((f.depthMv ?? 0) * (0.8 + rnd() * 0.4)).toFixed(3), verdict,
      verdictAt: verdict === 'unjudged' ? undefined : `${4 + Math.floor(rnd() * 10)} Sep`, foundBy: 'run #128 drop_motifs9',
      revisions: [{ rev: 1, spanId: `d-${70000 + i * 13}`, origin: 'machine', run: '#128', role: 'current' }], tags: [], seed: f.id.charCodeAt(3) * 1000 + i,
    }
  })
}

export const CLASS_OPTIONS = CLASSES.map(c => ({ key: c.key, name: c.name, colour: c.colour }))
export const TAG_VOCABULARY = ['sharkfin', 'biphasic', 'plateau-top', 'ramp', 'notched', 'spike-doublet', 'clean', 'noisy']
export const TAG_RULE = /^[a-z0-9][a-z0-9-]{1,31}$/

/* ================================================================ grouping editor ================================================================ */
export interface UnitOption { unit: Unit; caption: string; count: number }
export const UNIT_OPTIONS: UnitOption[] = [
  { unit: 'motifs', caption: 'one event each', count: 1402 },
  { unit: 'sequences', caption: 'events in order, with gaps', count: 350 },
  { unit: 'spike-trains', caption: 'a whole train as one entry', count: 16 },
]
export interface BasisOption { kind: BasisKind; group: 'distance' | 'feature bins · no distance' | 'labels'; title: string; caption: string; units: Unit[]; reason?: string }
export const BASIS_OPTIONS: BasisOption[] = [
  { kind: 'shape-distance', group: 'distance', title: 'shape distance', caption: 'z-norm, scale-invariant, Ward cut', units: ['motifs', 'sequences'], reason: 'a spike train is a whole train, not one shape' },
  { kind: 'sequence-similarity', group: 'distance', title: 'sequence similarity', caption: 'sequences only', units: ['sequences'], reason: 'sequences only' },
  { kind: 'amplitude', group: 'feature bins · no distance', title: 'amplitude', caption: 'peak-to-peak mV', units: ['motifs', 'sequences', 'spike-trains'] },
  { kind: 'timescale', group: 'feature bins · no distance', title: 'timescale', caption: 'duration', units: ['motifs', 'sequences', 'spike-trains'] },
  { kind: 'frequency-content', group: 'feature bins · no distance', title: 'frequency content', caption: 'dominant frequency', units: ['motifs', 'sequences', 'spike-trains'] },
  { kind: 'polarity', group: 'feature bins · no distance', title: 'polarity', caption: 'up / down / biphasic', units: ['motifs', 'sequences', 'spike-trains'] },
  { kind: 'tag', group: 'labels', title: 'tag', caption: 'morphology tags', units: ['motifs', 'sequences', 'spike-trains'] },
  { kind: 'provenance', group: 'labels', title: 'provenance', caption: 'recording · run · spike train', units: ['motifs', 'sequences', 'spike-trains'] },
  { kind: 'custom', group: 'labels', title: 'custom', caption: 'clustering from Analyse', units: ['motifs'], reason: 'the exported clustering grouped single motifs' },
]
export interface FeatureBin { lo: number; hi: number; n: number }
/** Dominant-frequency distribution (Welch PSD), log-spaced display bins; the last two sit above 0.5 Hz (14 motifs outside range). */
export const FREQ_DISTRIBUTION: FeatureBin[] = (() => {
  const counts = [16, 30, 52, 94, 126, 150, 140, 118, 102, 88, 76, 60, 48, 44, 36, 26, 18, 8, 6]
  const edges: number[] = []
  for (let i = 0; i <= 17; i++) edges.push(0.002 * Math.pow(0.5 / 0.002, i / 17))
  edges.push(edges[17] * Math.pow(0.5 / 0.002, 1 / 17), edges[17] * Math.pow(0.5 / 0.002, 2 / 17))
  // scale the in-range bins so the total is exactly 1,402 (1,388 inside + 14 outside)
  const inside = counts.slice(0, 17), s = inside.reduce((a, b) => a + b, 0)
  const scaled = split(1388, inside)
  void s
  return [...scaled, 8, 6].map((n, i) => ({ lo: +edges[i].toPrecision(3), hi: +edges[i + 1].toPrecision(3), n }))
})()
export const AMPLITUDE_DISTRIBUTION: FeatureBin[] = Array.from({ length: 16 }, (_, i) => ({ lo: +(0.05 + i * 0.05).toFixed(2), hi: +(0.1 + i * 0.05).toFixed(2), n: [60, 142, 210, 198, 170, 140, 118, 96, 80, 62, 48, 32, 22, 12, 8, 4][i] }))
export const TIMESCALE_DISTRIBUTION: FeatureBin[] = Array.from({ length: 16 }, (_, i) => ({ lo: +(0.5 * Math.pow(120, i / 16)).toPrecision(3), hi: +(0.5 * Math.pow(120, (i + 1) / 16)).toPrecision(3), n: [40, 88, 150, 170, 142, 120, 96, 90, 110, 128, 96, 70, 48, 30, 16, 8][i] }))
export const MERGE_HEIGHTS: FeatureBin[] = Array.from({ length: 20 }, (_, i) => ({ lo: +(i * 0.05).toFixed(2), hi: +((i + 1) * 0.05).toFixed(2), n: [2, 14, 40, 88, 130, 150, 138, 120, 96, 70, 52, 38, 28, 18, 12, 8, 5, 3, 2, 1][i] }))
export const CUSTOM_CLUSTERINGS = [{ value: 'a-0098', label: 'a-0098 · k = 6 · M2_aug fs1 CH4_A2 0–48 h', scope: 'scope: M2_aug fs1 · CH4_A2 · 0–48 h · 1,211 unassigned outside it' }]
export const HAND_EDITS_ORPHANED = ['m-1850', 'm-2011', 'm-2012']

/* ================================================================ import ================================================================ */
export interface ImportCheck { status: 'ok' | 'warn' | 'fail'; title: string; detail: string; items?: string[]; link?: { label: string; to: string } }
export interface ImportSample { id: number; recording: string; channel: string; onsetH: number; durationS: number; shape: ShapeKind; amp: number; seed: number; provisional: boolean }
export interface ImportBundle {
  path: string; provenanceFound: boolean; counts: { motifs: number; spikeTrains: number; recordings: number; channels: number }
  checks: ImportCheck[]; creates: string[]; sample: ImportSample[]; blockedReason?: string; heldOut?: boolean
}
function importSample(n: number): ImportSample[] {
  const rnd = seeded(4101), shapes: ShapeKind[] = ['drop', 'burst', 'sharkfin', 'spiketrain', 'drift', 'plateau', 'ripple', 'fall', 'peak', 'notch']
  const chans: [string, string, number][] = [['M2_aug fs1', 'CH3_A2', 721], ['M2_aug fs1', 'CH4_A2', 721], ...['CH1', 'CH2', 'CH3', 'CH4', 'CH5'].map(c => ['L_LM_Jul26_J', c, 22.4] as [string, string, number])]
  return Array.from({ length: n }, (_, i) => {
    const [r, c, h] = chans[Math.floor(rnd() * chans.length)]
    const shape = shapes[i % shapes.length]
    return { id: i + 1, recording: r, channel: c, onsetH: +(rnd() * h).toFixed(1), durationS: +(1 + rnd() * 30).toFixed(1), shape, amp: (shape === 'drop' || shape === 'fall' || shape === 'spiketrain' ? -1 : 1) * (0.12 + rnd() * 0.18), seed: 7000 + i, provisional: r === 'L_LM_Jul26_J' }
  })
}
const SAMPLE_410 = importSample(410)
export const IMPORT_BUNDLES: Record<string, ImportBundle> = {
  'DATA/library_seed/drop_motifs5': {
    path: 'DATA/library_seed/drop_motifs5', provenanceFound: true, counts: { motifs: 410, spikeTrains: 16, recordings: 2, channels: 7 },
    checks: [
      { status: 'ok', title: 'provenance complete', detail: '410 of 410 carry spike train, recording, channel, sample range' },
      { status: 'ok', title: 'sample ranges inside their recordings', detail: '410 of 410' },
      { status: 'ok', title: 'safe to run twice', detail: 'content hash per motif · 0 already in the library · re-import skips' },
      { status: 'ok', title: '3 overlap an existing annotation', detail: 'linked to it, not duplicated', items: ['a-2077 ↔ motif 118', 'a-2102 ↔ motif 240', 'a-2140 ↔ motif 377'] },
      { status: 'warn', title: 'sampling rate inferred for L_LM_Jul26_J', detail: '10 Hz, not read from the file · durations provisional', link: { label: 'confirm in Settings › Datasets', to: 'settings/datasets?recording=L_LM_Jul26_J' } },
    ],
    creates: ['410 single-motif entries, unjudged — imports are not verdicts', '16 spike-train entries, each linked to its motifs', 'first grouping g-01 · single motifs · shape distance · cut 0.42 · editable after'],
    sample: SAMPLE_410,
  },
  'DATA/library_seed/untitled_bundle': {
    path: 'DATA/library_seed/untitled_bundle', provenanceFound: false, counts: { motifs: 410, spikeTrains: 0, recordings: 2, channels: 7 },
    checks: [
      { status: 'fail', title: 'provenance incomplete', detail: 'no PROVENANCE.md · 410 motifs lack a sample range' },
      { status: 'fail', title: 'sample ranges inside their recordings', detail: 'cannot check without sample ranges' },
      { status: 'ok', title: 'safe to run twice', detail: 'content hash per motif · 0 already in the library' },
      { status: 'warn', title: 'overlaps with existing annotations', detail: 'cannot check without sample ranges' },
    ],
    creates: ['nothing — the bundle cannot be placed on a recording'], sample: SAMPLE_410, blockedReason: 'provenance incomplete: 410 motifs lack a sample range',
  },
  'DATA/library_seed/M4_aug_holdout': {
    path: 'DATA/library_seed/M4_aug_holdout', provenanceFound: true, heldOut: true, counts: { motifs: 96, spikeTrains: 4, recordings: 1, channels: 3 },
    checks: [
      { status: 'ok', title: 'provenance complete', detail: '96 of 96 carry spike train, recording, channel, sample range' },
      { status: 'fail', title: 'recording is held out', detail: 'M4_aug_concat_fs1.mat is held out and locked (D6) · refused', link: { label: 'Settings › Datasets', to: 'settings/datasets' } },
    ],
    creates: ['nothing — M4_aug is held out'], sample: SAMPLE_410.slice(0, 20), blockedReason: 'M4_aug is held out and locked (D6) — refused everywhere',
  },
}
export const IMPORT_STEPS = ['hash 410 motifs', 'link 3 annotations', 'write 410 + 16 entries', 'compute grouping g-01']
export const IMPORT_FAIL_ERROR = 'sample range 0:88,100 outside L_LM_Jul26_J CH4 (806,400 samples)'

/* ================================================================ window sets ================================================================ */
export type SetCheck = 'train-safe' | 'test sample' | 'not train-safe' | 'gap < window' | 'fs inferred'
export interface SplitBlock { split: 'train' | 'validation' | 'test' | 'gap'; fromH: number; toH: number; windows: number }
export interface WindowSetRow {
  id: string; version: number; saved: string; savedBy: string; source: string; recording: string; recordingKeys: string[]; channels: string[]
  spacing: string; windowS: number | null; gapS: number | null; windows: number; split: { train: number; validation: number; test: number } | null; splitLabel: 'blocked' | 'test only' | 'no split'
  labelledPct: number; labelledWindows: number; usedBy: { label: string; to: string; kind: string }[]; usedLabel: string | null
  check: SetCheck; checkReason: string; madeBy: string; recipeHash: string; lastUsed: string
  splitPlan: Record<string, SplitBlock[]>; planHours: number; dropped: number; spacingChecks: { label: string; ok: boolean }[]
  classCounts: { now: Record<string, number>; atSave: Record<string, number>; atSaveLabelled: number }
}
const plan = (hours: number, fr: [number, number, number, number], gapH: number): SplitBlock[] => {
  const [a, b, c] = [fr[0] * hours, (fr[0] + fr[1]) * hours, (fr[0] + fr[1] + fr[2]) * hours]
  return [
    { split: 'train', fromH: 0, toH: a - gapH / 2, windows: 0 }, { split: 'gap', fromH: a - gapH / 2, toH: a + gapH / 2, windows: 0 },
    { split: 'validation', fromH: a + gapH / 2, toH: b - gapH / 2, windows: 0 }, { split: 'gap', fromH: b - gapH / 2, toH: b + gapH / 2, windows: 0 },
    { split: 'test', fromH: b + gapH / 2, toH: c - gapH / 2, windows: 0 }, { split: 'gap', fromH: c - gapH / 2, toH: c + gapH / 2, windows: 0 },
    { split: 'train', fromH: c + gapH / 2, toH: hours, windows: 0 },
  ]
}
const withWindows = (blocks: SplitBlock[], windowsPerH: number) => blocks.map(b => ({ ...b, windows: b.split === 'gap' ? 0 : Math.round((b.toH - b.fromH) * windowsPerH) }))
const classes = (spike: number, burst: number, slow: number, plateau: number, art: number) => ({ 'spike-train': spike, burst, 'slow-drift': slow, plateau, artifact: art })
export const WINDOW_SETS: WindowSetRow[] = [
  {
    id: WINDOW_SET.id, version: WINDOW_SET.version, saved: '12 Sep', savedBy: ACTOR, source: 'M2_aug fs1 · 3 ch', recording: 'M2_aug fs1', recordingKeys: ['M2_aug_fs1'], channels: WINDOW_SET.channels,
    spacing: '600 · 300 · 600 s', windowS: 600, gapS: 600, windows: WINDOW_SET.windows, split: { train: 0.62, validation: 0.1, test: 0.28 }, splitLabel: 'blocked',
    labelledPct: 14, labelledWindows: WINDOW_SET.labelled_every_arm, usedBy: [{ label: 'Models · job j-0212 (paired arms)', to: 'jobs/cluster/j-0212', kind: 'Models' }, { label: 'Models · candidate cnn_windows_v3 · manual', to: 'models/registry?candidate=cnn_windows_v3_manual', kind: 'Models' }],
    usedLabel: '2 · Models', check: 'train-safe', checkReason: 'blocked split, gap 600 s ≥ 600 s window on every boundary', madeBy: 'cnn_windows_v3 · sliding windows', recipeHash: '5c1e…a07b', lastUsed: '13 Sep 21:40',
    splitPlan: Object.fromEntries(WINDOW_SET.channels.map(c => [c, withWindows(plan(721, [0.56, 0.08, 0.2, 0.16], 8), 5.43)])), planHours: 721, dropped: 18,
    spacingChecks: [{ label: 'gap ≥ window on every boundary', ok: true }, { label: 'no test window within 600 s of training', ok: true }, { label: 'test windows unseen by any job', ok: true }],
    classCounts: { now: classes(612, 568, 492, 430, 38), atSave: classes(590, 551, 470, 401, 38), atSaveLabelled: 2050 },
  },
  {
    id: 'ws_M2aug_fs2_300s', version: 1, saved: '11 Sep', savedBy: ACTOR, source: 'M2_aug fs2 · CH1_A1–CH4_A2', recording: 'M2_aug fs2', recordingKeys: ['M2_aug_fs2'], channels: ['CH1_A1', 'CH2_A1', 'CH3_A2', 'CH4_A2'],
    spacing: '300 · 150 · 300 s', windowS: 300, gapS: 300, windows: 4880, split: { train: 0.62, validation: 0.1, test: 0.28 }, splitLabel: 'blocked', labelledPct: 12, labelledWindows: 586,
    usedBy: [{ label: 'Analyse · training chain source', to: 'analyse/training?source=windowset:ws_M2aug_fs2_300s', kind: 'Analyse' }], usedLabel: '1 · Analyse', check: 'train-safe', checkReason: 'blocked split, gap 300 s ≥ 300 s window',
    madeBy: 'cnn_windowset_v1 · sliding windows', recipeHash: '81d0…33c2', lastUsed: '12 Sep 10:12',
    splitPlan: Object.fromEntries(['CH1_A1', 'CH2_A1', 'CH3_A2', 'CH4_A2'].map(c => [c, withWindows(plan(721, [0.56, 0.08, 0.2, 0.16], 6), 1.7)])), planHours: 721, dropped: 9,
    spacingChecks: [{ label: 'gap ≥ window on every boundary', ok: true }, { label: 'no test window within 300 s of training', ok: true }, { label: 'test windows unseen by any job', ok: true }],
    classCounts: { now: classes(180, 150, 120, 118, 18), atSave: classes(170, 150, 110, 110, 18), atSaveLabelled: 558 },
  },
  {
    id: 'ws_LLM_5ch_600s', version: 1, saved: '9 Sep', savedBy: ACTOR, source: 'L_LM_Jul26_J · 5 ch', recording: 'L_LM_Jul26_J', recordingKeys: ['L_LM_Jul26_J'], channels: ['CH1', 'CH2', 'CH3', 'CH4', 'CH5'],
    spacing: '600 · 600 · 600 s', windowS: 600, gapS: 600, windows: 670, split: { train: 0.62, validation: 0.1, test: 0.28 }, splitLabel: 'blocked', labelledPct: 0, labelledWindows: 0,
    usedBy: [], usedLabel: null, check: 'fs inferred', checkReason: 'L_LM_Jul26_J fs 10 Hz is inferred — confirm it in Settings › Datasets before training', madeBy: 'cnn_windowset_v1 · sliding windows', recipeHash: '0be4…9f15', lastUsed: '9 Sep 16:30',
    splitPlan: Object.fromEntries(['CH1', 'CH2', 'CH3', 'CH4', 'CH5'].map(c => [c, withWindows(plan(22.4, [0.56, 0.1, 0.24, 0.1], 0.4), 6)])), planHours: 22.4, dropped: 4,
    spacingChecks: [{ label: 'gap ≥ window on every boundary', ok: true }, { label: 'no test window within 600 s of training', ok: true }, { label: 'sampling rate read from the file', ok: false }],
    classCounts: { now: classes(0, 0, 0, 0, 0), atSave: classes(0, 0, 0, 0, 0), atSaveLabelled: 0 },
  },
  {
    id: 'ws_verif_cnn_cluster_v1', version: 1, saved: '14 Sep', savedBy: 'Models', source: 'test block · ws_M2aug_3ch', recording: 'M2_aug fs1', recordingKeys: ['M2_aug_fs1'], channels: ['CH2_A1', 'CH4_A2', 'CH7_B2'],
    spacing: '600 s', windowS: 600, gapS: null, windows: 40, split: { train: 0, validation: 0, test: 1 }, splitLabel: 'test only', labelledPct: 100, labelledWindows: 40,
    usedBy: [{ label: 'Registry · cnn_cluster_v1 verification sample', to: 'models/registry?model=cnn_cluster_v1', kind: 'Registry' }], usedLabel: '1 · Registry', check: 'test sample', checkReason: 'the verification sample of cnn_cluster_v1 — a test sample is never trained on',
    madeBy: 'Models · verification sample (40 of 432 test-block windows)', recipeHash: 'c77a…5d20', lastUsed: '15 Sep 09:02',
    splitPlan: Object.fromEntries(['CH2_A1', 'CH4_A2', 'CH7_B2'].map(c => [c, [{ split: 'gap' as const, fromH: 0, toH: 472, windows: 0 }, { split: 'test' as const, fromH: 472, toH: 616, windows: 13 }, { split: 'gap' as const, fromH: 616, toH: 721, windows: 0 }]])), planHours: 721, dropped: 0,
    spacingChecks: [{ label: 'every window inside the test block', ok: true }, { label: 'blind verification: 33 of 40 judged', ok: true }],
    classCounts: { now: classes(11, 10, 9, 8, 2), atSave: classes(0, 0, 0, 0, 0), atSaveLabelled: 0 },
  },
  {
    id: 'ws_human_labelled_mixed', version: 1, saved: '8 Sep', savedBy: ACTOR, source: 'Review verdicts · 3 rec', recording: 'Review verdicts', recordingKeys: ['M2_aug_fs1', 'M3_jul', 'L_LM_Jul26_J'], channels: ['M2_aug fs1 CH3_A2', 'M2_aug fs1 CH4_A2', 'M3_jul CH2', 'L_LM_Jul26_J CH3'],
    spacing: 'supplied', windowS: null, gapS: null, windows: 1312, split: null, splitLabel: 'no split', labelledPct: 100, labelledWindows: 1312,
    usedBy: [], usedLabel: null, check: 'not train-safe', checkReason: 'supplied Review windows, overlapping, no split: fine for Review and interrogation, leaks if trained on (B7)', madeBy: 'Review · supplied windows (human verdicts)', recipeHash: '—', lastUsed: '8 Sep 12:00',
    splitPlan: {}, planHours: 721, dropped: 0,
    spacingChecks: [{ label: 'windows overlap (supplied, not spaced)', ok: false }, { label: 'no split assigned', ok: false }],
    classCounts: { now: classes(402, 330, 280, 262, 38), atSave: classes(402, 330, 280, 262, 38), atSaveLabelled: 1312 },
  },
  {
    id: 'ws_M2aug_1ch_60s', version: 1, saved: '6 Sep', savedBy: ACTOR, source: 'M2_aug fs1 · CH4_A2', recording: 'M2_aug fs1', recordingKeys: ['M2_aug_fs1'], channels: ['CH4_A2'],
    spacing: '60 · 30 · 30 s', windowS: 60, gapS: 30, windows: 18400, split: { train: 0.62, validation: 0.1, test: 0.28 }, splitLabel: 'blocked', labelledPct: 3, labelledWindows: 552,
    usedBy: [{ label: 'Review · q-18 training windows', to: 'review/queue/q-18', kind: 'Review' }], usedLabel: '1 · Review', check: 'gap < window', checkReason: 'gap 30 s is shorter than the 60 s window, so neighbouring windows share samples across the split', madeBy: 'sliding windows (a-0081)', recipeHash: '4e02…b118', lastUsed: '10 Sep 18:45',
    splitPlan: { CH4_A2: withWindows(plan(721, [0.56, 0.08, 0.2, 0.16], 1), 25.5) }, planHours: 721, dropped: 0,
    spacingChecks: [{ label: 'gap 30 s < 60 s window on every boundary', ok: false }, { label: 'no test window within 60 s of training', ok: false }, { label: 'test windows unseen by any job', ok: true }],
    classCounts: { now: classes(160, 140, 120, 108, 24), atSave: classes(150, 130, 110, 100, 24), atSaveLabelled: 514 },
  },
]
export const CLASS_COLOURS: Record<string, string> = { ...Object.fromEntries(CLASSES.map(c => [c.name, c.colour])), artifact: '#E5484D' }
export const REVIEW_QUEUE_CAP = 20000

/* ================================================================ templates ================================================================ */
export type TemplateKind = 'detection' | 'seed search' | 'training' | 'interrogation'
export interface TemplateStage { glyph: string; name: string; params: string }
export interface TemplateVersion { v: number; change: string; date: string; diff?: { param: string; from: string; to: string }[] }
export interface TemplateScore { run: string; scope: string; scopeFull: string; prec: number | null; recall: number | null; xNull: number | null }
export interface Template {
  name: string; version: number; kind: TemplateKind; signature: string; badges: { label: string; tone: 'purple' | 'blue' | 'grey' }[]
  stages: TemplateStage[]; recipe: string; nullModel: string; containsModel: boolean; latest: { text: string; scope: string } | null; latestMuted?: string
  runs: string; runCount: number; lastRun: string; versions: TemplateVersion[]; scores: TemplateScore[]; scoreHeader?: [string, string, string]
}
const S = (glyph: string, name: string, params: string): TemplateStage => ({ glyph, name, params })
const SRC = S('source', 'Source', 'one channel · any recording')
export const TEMPLATE_LIST: Template[] = [
  {
    name: 'mp_drops_v3', version: 3, kind: 'detection', signature: 'Signal → SpanSet', badges: [], containsModel: false, recipe: '9b24…e1f0', nullModel: 'circular shift 200×',
    stages: [SRC, S('bandpass', 'Bandpass filter', '0.005 – 0.1 Hz · order 4'), S('matrix_profile', 'Matrix profile', 'm = 120 s · exclusion m/2'), S('threshold', 'Threshold to spans', '0.62 · min 20 s · merge 5 s')],
    latest: { text: 'precision 0.78 · recall 0.61', scope: 'over 14 h · run r-0412' }, runs: '4 runs', runCount: 4, lastRun: '15 Sep',
    versions: [
      { v: 3, change: 'threshold 0.60 → 0.62', date: '12 Sep', diff: [{ param: 'Threshold to spans · threshold', from: '0.60', to: '0.62' }] },
      { v: 2, change: 'bandpass added', date: '9 Sep', diff: [{ param: 'stage 01', from: '—', to: 'Bandpass filter 0.005 – 0.1 Hz · order 4' }] },
      { v: 1, change: 'matrix profile only', date: '2 Sep' },
    ],
    scores: [
      { run: 'r-0412', scope: 'fs1 · 3 ch · 721 h', scopeFull: 'M2_aug fs1 · CH2_A1, CH4_A2, CH7_B2 · 721 h', prec: 0.78, recall: 0.61, xNull: 6.1 },
      { run: 'r-0398', scope: 'M3_jul · 280 h', scopeFull: 'M3_jul · 8 ch · 280 h', prec: 0.71, recall: 0.55, xNull: 4.8 },
      { run: 'r-0377', scope: 'LLM · 5 ch · 22 h', scopeFull: 'L_LM_Jul26_J · 5 ch · 22.4 h', prec: 0.52, recall: null, xNull: 2.2 },
      { run: 'r-0360', scope: 'fs1 CH4_A2 · 4 h', scopeFull: 'M2_aug fs1 · CH4_A2 · 4 h', prec: 0.9, recall: 0.4, xNull: 7.9 },
    ],
  },
  {
    name: 'drop_motifs9', version: 2, kind: 'detection', signature: 'Signal → SpanSet', badges: [], containsModel: false, recipe: '3f8a…0c11', nullModel: 'circular shift 200×',
    stages: [SRC, S('baseline', '01 Baseline', 'rolling mean · 600 s'), S('sax', '03 Encoding', 'SAX · 4 symbols · floor-cut'), S('drop_detection', '04 Detection', 'drops ≥ 3 symbols · min 8 s')],
    latest: { text: 'precision 0.64 · recall 0.70', scope: 'over 14 h · run r-0398' }, runs: '2 runs', runCount: 2, lastRun: '14 Sep',
    versions: [{ v: 2, change: 'noise floor 5σ → 6σ', date: '11 Sep', diff: [{ param: '02 Noise floor · k', from: '5σ', to: '6σ' }] }, { v: 1, change: 'first save from run #128', date: '3 Sep' }],
    scores: [{ run: '#131', scope: 'fs1 CH4_A2 · 14 h', scopeFull: 'M2_aug fs1 · CH4_A2 · 14 h', prec: 0.64, recall: 0.7, xNull: 3.9 }, { run: '#128', scope: 'fs1 CH4_A2 · 14 h', scopeFull: 'M2_aug fs1 · CH4_A2 · 14 h', prec: 0.58, recall: 0.72, xNull: 3.1 }],
  },
  {
    name: 'seed_E-0102', version: 1, kind: 'seed search', signature: 'Signal → SpanSet', badges: [{ label: 'seed · carry', tone: 'purple' }], containsModel: false, recipe: 'e102…7a3d', nullModel: 'phase-randomised 100×',
    stages: [SRC, S('seeded_search', 'Seeded search', 'seed E-0102 carried · z-norm · 21 s'), S('threshold', 'Threshold to spans', 'd ≤ 0.42 · merge 5 s')],
    latest: { text: 'precision 0.83', scope: 'recall: no reviewed overlap' }, runs: '1 run', runCount: 1, lastRun: '13 Sep',
    versions: [{ v: 1, change: 'saved from Review seed E-0102', date: '12 Sep' }],
    scores: [{ run: 'r-0415', scope: 'fs1 · 3 ch · 721 h', scopeFull: 'M2_aug fs1 · CH2_A1, CH4_A2, CH7_B2 · 721 h', prec: 0.83, recall: null, xNull: 5.2 }],
  },
  {
    name: 'seed_family_medoid', version: 1, kind: 'seed search', signature: 'Signal → SpanSet', badges: [{ label: 'seed · rebind', tone: 'purple' }], containsModel: false, recipe: '6d11…c0e2', nullModel: 'phase-randomised 100×',
    stages: [SRC, S('seeded_search', 'Seeded search', 'seed = family medoid (rebound at apply)')],
    latest: null, latestMuted: 'not yet scored', runs: '0 runs', runCount: 0, lastRun: '—', versions: [{ v: 1, change: 'first save', date: '14 Sep' }], scores: [],
  },
  {
    name: 'cnn_detect_cluster_v1', version: 1, kind: 'detection', signature: 'Signal → SpanSet', badges: [{ label: 'model cnn_cluster_v1', tone: 'blue' }], containsModel: true, recipe: '2a90…d4f7', nullModel: 'label shuffle 50×',
    stages: [SRC, S('sliding_windows', 'Sliding windows', '600 · 300 s'), S('image_encode', 'Encode', 'GASF + MTF · 64 px'), S('model_stage', 'Model stage', 'cnn_cluster_v1 v1 · locked'), S('threshold', 'Threshold to spans', 'p ≥ 0.7 · merge 1 window')],
    latest: null, latestMuted: 'not yet run', runs: '0 runs', runCount: 0, lastRun: '—', versions: [{ v: 1, change: 'saved from Models registry · cnn_cluster_v1', date: '14 Sep' }], scores: [],
  },
  {
    name: 'cnn_windows_v3', version: 3, kind: 'training', signature: 'Signal → Model', badges: [{ label: 'training', tone: 'grey' }], containsModel: false, recipe: 'b3c4…8e21', nullModel: 'label shuffle 50× · 5 model nulls',
    stages: [SRC, S('sliding_windows', '01 Sliding windows', '600 · 300 · gap 600 s · blocked split'), S('window_matrix', '02 Window matrix', '42 features'), S('cluster', '03 Cluster', 'k-means · k = 6'), S('image_encode', '04 Encode', 'GASF · 64 px'), S('model', '05 Model', 'CNN · 3 conv · 20 epochs')],
    latest: { text: 'macro F1 0.71', scope: 'test block · job j-0212' }, runs: '1 job', runCount: 1, lastRun: '13 Sep',
    versions: [{ v: 3, change: 'paired label arms (manual · cluster)', date: '12 Sep', diff: [{ param: 'label arms', from: 'manual', to: 'manual · cluster' }] }, { v: 2, change: 'blocked split with gap ≥ window', date: '8 Sep', diff: [{ param: '01 Sliding windows · gap', from: '0 s', to: '600 s' }] }, { v: 1, change: 'first save', date: '1 Sep' }],
    scores: [{ run: 'j-0212', scope: 'test block · 432 windows', scopeFull: 'ws_M2aug_3ch_600s v1 · test block · 432 windows', prec: 0.74, recall: 0.69, xNull: 3.4 }], scoreHeader: ['job', 'macro prec', 'macro recall'],
  },
  {
    name: 'slope_interrogation', version: 1, kind: 'interrogation', signature: 'SpanSet → Features', badges: [{ label: 'interrogation', tone: 'grey' }], containsModel: false, recipe: '5f03…a9b8', nullModel: 'member shuffle 100×',
    stages: [S('source', 'Source', 'a family (SpanSet)'), S('baseline', '01 Slope', 'rise and fall slope per member'), S('surrogate', '02 Aggregate', 'distribution · fit + null')],
    latest: { text: 'used on F-03', scope: '112 events' }, runs: '3 uses', runCount: 3, lastRun: '12 Sep', versions: [{ v: 1, change: 'saved from #140 F-03 slope interrogation', date: '10 Sep' }],
    scores: [],
  },
  ...(['sharkfin_v2', 'mp_discord_v3', 'spike_shape_v1', 'drop_cnn_v1', 'sharkfin_cnn_v2', 'cnn_windowset_v1', 'banded_sax_lp'] as const).map((name, i): Template => {
    const model = name === 'drop_cnn_v1' || name === 'sharkfin_cnn_v2'
    const training = name === 'cnn_windowset_v1'
    const stages = training ? [SRC, S('sliding_windows', '01 Sliding windows', '300 · 150 · gap 300 s'), S('window_matrix', '02 Window matrix', '42 features')]
      : model ? [SRC, S('sliding_windows', 'Sliding windows', '120 · 60 s'), S('model_stage', 'Model stage', 'cnn_windows_v2 · manual v2 · locked'), S('threshold', 'Threshold to spans', 'p ≥ 0.6')]
        : name === 'banded_sax_lp' ? [SRC, S('lowpass', 'Lowpass', '0.05 Hz'), S('sax', 'Banded SAX', '6 bands'), S('drop_detection', 'Detection', 'min 10 s')]
          : name === 'mp_discord_v3' ? [SRC, S('matrix_profile', 'Matrix profile', 'm = 300 s'), S('threshold', 'Discords', 'top 1 %')]
            : [SRC, S('baseline', 'Baseline', 'rolling mean · 300 s'), S(name === 'spike_shape_v1' ? 'spike' : 'seeded_search', name === 'spike_shape_v1' ? 'Spike detector' : 'Shape match', name === 'spike_shape_v1' ? 'k = 5σ' : 'F-03 exemplar'), S('threshold', 'Threshold to spans', 'd ≤ 0.4')]
    return {
      name, version: [2, 3, 1, 1, 2, 1, 1][i], kind: training ? 'training' : 'detection', signature: training ? 'Signal → WindowSet' : 'Signal → SpanSet',
      badges: model ? [{ label: 'model cnn_windows_v2 · manual', tone: 'blue' }] : training ? [{ label: 'training', tone: 'grey' }] : [], containsModel: model,
      recipe: `${(0x7a1 + i * 911).toString(16)}…${(0x1c3 + i * 77).toString(16)}`, nullModel: 'circular shift 200×', stages,
      latest: i === 5 ? null : { text: `precision ${(0.6 + i * 0.03).toFixed(2)} · recall ${(0.5 + i * 0.04).toFixed(2)}`, scope: `over ${[14, 22, 8, 14, 14, 0, 280][i]} h · run r-0${340 - i * 9}` },
      latestMuted: i === 5 ? 'not yet run' : undefined, runs: `${[3, 5, 2, 2, 1, 0, 1][i]} run${[3, 5, 2, 2, 1, 0, 1][i] === 1 ? '' : 's'}`, runCount: [3, 5, 2, 2, 1, 0, 1][i], lastRun: `${10 - i} Sep`,
      versions: [{ v: [2, 3, 1, 1, 2, 1, 1][i], change: 'saved', date: `${9 - i} Sep` }],
      scores: i === 5 ? [] : [{ run: `r-0${340 - i * 9}`, scope: 'fs1 CH4_A2 · 14 h', scopeFull: 'M2_aug fs1 · CH4_A2 · 14 h', prec: +(0.6 + i * 0.03).toFixed(2), recall: +(0.5 + i * 0.04).toFixed(2), xNull: +(2 + i * 0.6).toFixed(1) }],
    }
  }),
]
