/* Analyse › Interrogation fixtures (frames prototyping/imgs/analyse-interrogation/*.pdf; spec §0, §6.2, §6.6,
 * §6.8 `SpanSet → SpanSet + Features` and `Features → views`, P7, P8, P10).
 *
 * TIMESCALE (inventory "the one timescale decision"): the frames draw ~1 s falls and ~−0.7 mV/s slopes,
 * which cannot exist at the canon's 1 Hz. Every frame time is multiplied by 10 and every frame slope
 * divided by 10, so a fall is 7–11 s, recovery 10–14 s (fall + recovery ≈ the canon's 21 s F-03), and
 * −45° on the rose is −0.1 mV/s. Every angle, depth and shape stays exactly as drawn.
 *
 * Demo data only. Traces are synthetic (canon `syntheticTrace`/`seeded`), mV, never normalised. */
import { FAMILY_COLOURS, HELD_OUT_KEY, REVIEW_QUEUES, seeded } from './canon'

/* ---------------------------------------------------------------- verdicts ---------------------------------------------------------------- */
export type MemberVerdict = 'seed' | 'interesting' | 'unadjudicated' | 'artifact'
/** §3: human verdicts are green (seed is the stronger green), unadjudicated amber, artifact red.
 *  The frame draws `seed` blue — blue is machine-origin in §3, so the two greens are used instead (fog). */
export const VERDICT_COLOUR: Record<MemberVerdict, string> = {
  seed: '#14804A', interesting: '#22A06B', unadjudicated: '#E8900C', artifact: '#E5484D',
}
export const VERDICT_ORDER: MemberVerdict[] = ['seed', 'interesting', 'unadjudicated', 'artifact']

/* ---------------------------------------------------------------- members ---------------------------------------------------------------- */
export interface InterrogationMember {
  id: string
  family: string
  recording: string          // canon recording label
  channel: string
  onset_h: number            // hours since recording start (§0)
  d: number                  // scale-invariant distance to the family medoid
  verdict: MemberVerdict
  excluded: boolean          // scoped out of this run (does not touch the Library entry)
  fs_hz: number
  /* features declared by 01 Resolve spans (slope analysis) */
  depth_mV: number
  max_slope: number          // mV/s, negative
  peakedness: number
  duration_s: number         // onset → trough
  recovery_s: number         // trough → baseline
  flags: string[]
  /* live (seed store) only: the stored detrended snippet and where the onset sits in it */
  snippet?: { t_s: number[]; v: number[] }
  onset_offset_s?: number
}

/** −45° on the rose is −0.1 mV/s (frame −45° = −1 mV/s, ÷10). */
export const ROSE_REF_SLOPE = 0.1
export const angleOf = (slope: number) => -(Math.atan(Math.abs(slope) / ROSE_REF_SLOPE) * 180) / Math.PI

type Row = [string, string, string, number, number, MemberVerdict, number, number, number, number, number, string[]]
//          id      rec     ch      onset  d      verdict         depth  slope  peak   dur    rec    flags

const F03_ROWS: Row[] = [
  ['s-0341', 'M2_aug fs1', 'CH4_A2', 336.9, 0.08, 'interesting', 0.152, -0.0402, 1.69, 6.4, 14.2, []],
  ['s-0342', 'M2_aug fs1', 'CH4_A2', 337.3, 0.12, 'interesting', 0.188, -0.0469, 1.90, 7.6, 13.1, []],
  ['s-0343', 'M2_aug fs1', 'CH4_A2', 337.8, 0.15, 'interesting', 0.326, -0.0672, 1.77, 7.0, 13.4, []],
  ['s-0344', 'M2_aug fs1', 'CH4_A2', 338.2, 0.10, 'seed', 0.378, -0.0725, 1.92, 10.0, 11.0, []],
  ['s-0346', 'M2_aug fs1', 'CH3_A2', 339.1, 0.19, 'unadjudicated', 0.214, -0.0590, 1.60, 9.0, 12.1, ['two troughs']],
  ['s-0348', 'M2_aug fs1', 'CH4_A2', 340.0, 0.28, 'artifact', 0.098, -0.0181, 1.18, 6.4, 15.0, ['electrode artifact']],
  ['s-0350', 'M2_aug fs1', 'CH3_A2', 340.9, 0.14, 'unadjudicated', 0.171, -0.0430, 1.71, 6.8, 14.0, []],
  ['s-0352', 'M2_aug fs1', 'CH3_A2', 341.4, 0.30, 'unadjudicated', 0.133, -0.0331, 1.47, 5.9, 15.0, []],
  ['s-0355', 'M2_aug fs1', 'CH4_A2', 342.0, 0.34, 'interesting', 0.199, -0.0487, 1.76, 7.2, 13.6, []],
  ['s-0356', 'M2_aug fs1', 'CH4_A2', 342.4, 0.35, 'unadjudicated', 0.121, -0.0308, 1.40, 5.5, 15.4, []],
  ['m-0112', 'M3_jul', 'CH2', 61.4, 0.17, 'interesting', 0.164, -0.0413, 1.66, 6.6, 14.1, []],
  ['m-0121', 'M3_jul', 'CH2', 62.7, 0.29, 'interesting', 0.207, -0.0503, 1.80, 7.4, 13.3, []],
  ['m-0124', 'M3_jul', 'CH2', 63.1, 0.32, 'interesting', 0.143, -0.0361, 1.54, 6.1, 14.7, []],
  ['m-0127', 'M3_jul', 'CH2', 63.8, 0.34, 'seed', 0.178, -0.0444, 1.72, 6.9, 13.9, []],
  ['m-0118', 'M3_jul', 'CH2', 64.0, 0.22, 'interesting', 0.361, -0.0702, 1.81, 11.0, 10.2, []],
  ['l-0007', 'L_LM_Jul26_J', 'CH1', 12.2, 0.27, 'unadjudicated', 0.196, -0.0483, 1.75, 7.1, 13.5, []],
  ['l-0009', 'L_LM_Jul26_J', 'CH1', 12.9, 0.33, 'unadjudicated', 0.158, -0.0396, 1.58, 6.3, 14.5, []],
]

const FS_OF: Record<string, number> = { 'M2_aug fs1': 1, 'M2_aug fs2': 2, M3_jul: 1, L_LM_Jul26_J: 10 }

function toMember(family: string, r: Row): InterrogationMember {
  return {
    id: r[0], family, recording: r[1], channel: r[2], onset_h: r[3], d: r[4], verdict: r[5],
    excluded: r[5] === 'artifact', fs_hz: FS_OF[r[1]] ?? 1,
    depth_mV: r[6], max_slope: r[7], peakedness: r[8], duration_s: r[9], recovery_s: r[10], flags: r[11],
  }
}

const F03_MEMBERS: InterrogationMember[] = F03_ROWS.map(r => toMember('F-03', r))

/* F-07 slow drift — 212 members, the "large family" of frame 2b (P8: shown 10 at a time). */
function genF07(): InterrogationMember[] {
  const rnd = seeded(4417)
  const spec: { rec: string; prefix: string; start: number; chs: string[]; n: number; t0: number; span: number }[] = [
    { rec: 'M2_aug fs1', prefix: 's-1', start: 300, chs: ['CH3_A2', 'CH4_A2', 'CH7_B2'], n: 96, t0: 300, span: 118 },
    { rec: 'M2_aug fs2', prefix: 's2-0', start: 40, chs: ['CH2_A1', 'CH4_A2'], n: 44, t0: 180, span: 88 },
    { rec: 'M3_jul', prefix: 'm-0', chs: ['CH2', 'CH5'], start: 400, n: 52, t0: 40, span: 68 },
    { rec: 'L_LM_Jul26_J', prefix: 'l-0', chs: ['CH1', 'CH3'], start: 20, n: 20, t0: 8, span: 11 },
  ]
  const out: InterrogationMember[] = []
  for (const s of spec) {
    for (let i = 0; i < s.n; i++) {
      const depth = +(0.10 + rnd() * 0.26).toFixed(3)
      const peak = +(1.25 + rnd() * 0.7).toFixed(2)
      const dur = +(5.2 + rnd() * 6.2).toFixed(1)
      const verdict: MemberVerdict = rnd() < 0.06 ? 'seed' : rnd() < 0.24 ? 'interesting' : rnd() < 0.05 ? 'artifact' : 'unadjudicated'
      out.push({
        id: `${s.prefix}${s.start + i}`, family: 'F-07', recording: s.rec, channel: s.chs[i % s.chs.length],
        onset_h: +(s.t0 + (i / s.n) * s.span + rnd() * 0.4).toFixed(1), d: +(0.04 + rnd() * 0.31).toFixed(2),
        verdict, excluded: false, fs_hz: FS_OF[s.rec] ?? 1,
        depth_mV: depth, max_slope: -+((depth / dur) * peak).toFixed(4), peakedness: peak,
        duration_s: dur, recovery_s: +(21 - dur + rnd() * 2).toFixed(1),
        flags: rnd() < 0.043 ? ['two troughs'] : [],
      })
    }
  }
  /* The four rows frame 2b names, at the strip positions it draws (event 45 is current). The generated ids
     start well clear of these four so no id is used twice. */
  const named: [number, string, number, number, number, number, number, string[]][] = [
    [44, 's-1203', 0.378, -0.0725, 1.92, 10.0, 11.0, []],
    [45, 'm-0231', 0.361, -0.0702, 1.81, 11.0, 10.2, []],
    [46, 's-1204', 0.326, -0.0688, 1.77, 7.0, 13.4, []],
    [47, 's-1207', 0.214, -0.0590, 1.60, 9.0, 12.1, ['two troughs']],
  ]
  for (const [i, id, depth, slope, peak, dur, rec, flags] of named) {
    out[i] = { ...out[i], id, depth_mV: depth, max_slope: slope, peakedness: peak, duration_s: dur, recovery_s: rec, flags }
  }
  return out
}
const F07_MEMBERS = genF07()

/* F-04 spike train — 9 members, none adjudicated: the "too few to fit" state of Aggregate. */
const F04_MEMBERS: InterrogationMember[] = Array.from({ length: 9 }, (_, i) => {
  const rnd = seeded(91 + i)
  const depth = +(0.09 + rnd() * 0.08).toFixed(3), dur = +(4.0 + rnd() * 2.4).toFixed(1), peak = +(1.3 + rnd() * 0.5).toFixed(2)
  return {
    id: `m-03${30 + i}`, family: 'F-04', recording: 'M3_jul', channel: i % 2 ? 'CH5' : 'CH2',
    onset_h: +(150 + i * 3.4).toFixed(1), d: +(0.06 + i * 0.03).toFixed(2), verdict: 'unadjudicated' as MemberVerdict,
    excluded: false, fs_hz: 1, depth_mV: depth, max_slope: -+((depth / dur) * peak).toFixed(4), peakedness: peak,
    duration_s: dur, recovery_s: +(21 - dur).toFixed(1), flags: [],
  }
})

export const MEMBERS_BY_FAMILY: Record<string, InterrogationMember[]> = {
  'F-03': F03_MEMBERS, 'F-07': F07_MEMBERS, 'F-04': F04_MEMBERS,
}

/* ---------------------------------------------------------------- families ---------------------------------------------------------------- */
export interface InterrogationFamily {
  id: string; name: string; colour: string
  members: number            // whole family (§0: F-03 has 112)
  within: number             // members within the distance threshold — what the source block scopes
  recordings: string[]; channels: string[]
  adjudicated: number
  threshold: number
  medoid: string; exemplar?: string
  promotedFrom: string; promotedOn: string; recipe: string
  crossRecording: boolean
  disabledReason?: string
}

export const CLUSTERING = { method: 'Ward', t: 10.1, version: 'v3' }

export const FAMILIES: InterrogationFamily[] = [
  {
    id: 'F-03', name: 'sharkfin', colour: FAMILY_COLOURS['F-03'], members: 112, within: 17,
    recordings: ['M2_aug fs1', 'M3_jul', 'L_LM_Jul26_J'], channels: ['CH1', 'CH2', 'CH3_A2', 'CH4_A2'], adjudicated: 11,
    threshold: 0.35, medoid: 'm-1846', exemplar: 'E-0102', promotedFrom: 'run 114', promotedOn: '2 Sept', recipe: 'a7f39c', crossRecording: true,
  },
  {
    id: 'F-07', name: 'slow drift', colour: FAMILY_COLOURS['F-07'], members: 212, within: 212,
    recordings: ['M2_aug fs1', 'M2_aug fs2', 'M3_jul', 'L_LM_Jul26_J'], channels: ['CH1', 'CH2', 'CH3', 'CH5', 'CH2_A1', 'CH3_A2', 'CH4_A2', 'CH7_B2'], adjudicated: 48,
    threshold: 0.40, medoid: 's-1188', promotedFrom: 'run 118', promotedOn: '5 Sept', recipe: 'c1d804', crossRecording: true,
  },
  {
    id: 'F-01', name: 'single drop', colour: FAMILY_COLOURS['F-01'], members: 64, within: 64,
    recordings: ['M2_aug fs1', 'M3_jul'], channels: ['CH2', 'CH4_A2'], adjudicated: 60,
    threshold: 0.30, medoid: 's-0902', promotedFrom: 'run 109', promotedOn: '28 Aug', recipe: '4b2e77', crossRecording: true,
  },
  {
    id: 'F-04', name: 'spike train', colour: FAMILY_COLOURS['F-04'], members: 9, within: 9,
    recordings: ['M3_jul'], channels: ['CH2', 'CH5'], adjudicated: 0,
    threshold: 0.35, medoid: 'm-0334', promotedFrom: 'run 121', promotedOn: '9 Sept', recipe: '77aa10', crossRecording: false,
  },
  {
    id: 'F-11', name: 'burst', colour: FAMILY_COLOURS['F-11'], members: 31, within: 31,
    recordings: ['M2_aug fs1', 'M3_jul', 'L_LM_Jul26_J'], channels: ['CH1', 'CH2', 'CH4_A2'], adjudicated: 12,
    threshold: 0.35, medoid: 's-0771', promotedFrom: 'run 116', promotedOn: '3 Sept', recipe: '9f30c2', crossRecording: true,
    disabledReason: 'not resolved yet · 31 members, no measurements cached',
  },
]

/** D6: the held-out recording is refused as a source everywhere, with the reason. */
export const HELD_OUT_FAMILY: InterrogationFamily = {
  id: 'F-09', name: 'M4 drop set', colour: FAMILY_COLOURS['F-09'], members: 88, within: 88,
  recordings: ['M4_aug'], channels: ['CH4_A2'], adjudicated: 0, threshold: 0.35, medoid: 'x-0001',
  promotedFrom: 'run 103', promotedOn: '21 Aug', recipe: 'held', crossRecording: false,
  disabledReason: `${HELD_OUT_KEY}_concat_fs1.mat is held out (D6) · every workspace refuses it`,
}

/* ---------------------------------------------------------------- source settings ---------------------------------------------------------------- */
export const SOURCE_SETTINGS = {
  members: [
    { value: 'in-scope', label: 'all in scope' },
    { value: 'adjudicated', label: 'adjudicated only' },
    { value: 'seeds', label: 'human seeds only' },
  ],
  resolveFrom: [
    { value: 'original', label: 'original recording' },
    { value: 'cached', label: 'cached span windows' },
    { value: 'library', label: 'Library thumbnails', disabled: true, reason: 'thumbnails are decimated · geometry needs the samples' },
  ],
  padding: [
    { value: '0.5', label: '± 0.5 × span' },
    { value: '1', label: '± 1 × span' },
    { value: '2', label: '± 2 × span' },
  ],
  onMissing: [
    { value: 'fail', label: 'fail the run' },
    { value: 'skip', label: 'skip the member, flag it' },
  ],
}

export const SORTS = [
  { value: 'distance', label: 'distance to medoid' },
  { value: 'onset', label: 'onset time' },
  { value: 'depth', label: 'depth' },
  { value: 'verdict', label: 'verdict' },
]

export const ALIGNMENTS = [
  { value: 'onset', label: 'onset' },
  { value: 'trough', label: 'trough' },
  { value: 'steepest', label: 'steepest sample' },
]

/* ---------------------------------------------------------------- other source kinds (picker tabs) ---------------------------------------------------------------- */
export interface PriorRunOption { id: string; label: string; template: string; terminal: 'SpanSet' | 'Features'; spans: number; when: string; disabledReason?: string }
export const PRIOR_RUNS: PriorRunOption[] = [
  { id: '140', label: '#140 F-03 slope interrogation', template: 'sharkfin_slope_v1', terminal: 'Features', spans: 16, when: '14 Sep 09:12' },
  { id: '128', label: '#128 drop_motifs9', template: 'drop_motifs9', terminal: 'SpanSet', spans: 343, when: '11 Sep 16:40' },
  { id: '131', label: '#131 drop_motifs9 · 6σ floor', template: 'drop_motifs9', terminal: 'SpanSet', spans: 118, when: '12 Sep 10:02' },
  { id: '97', label: '#97 banded_sax_lp', template: 'banded_sax_lp', terminal: 'SpanSet', spans: 0, when: '2 Sep 14:20', disabledReason: 'the run emitted no spans · nothing to interrogate' },
]

export interface ReviewSelectionOption { id: string; source: string; kind: string; judged: number; total: number; blind?: boolean; disabledReason?: string }
export const REVIEW_SELECTIONS: ReviewSelectionOption[] = REVIEW_QUEUES.map((q, i) => ({
  id: q.id, source: q.source, kind: q.kind, judged: [41, 12, 0, 33][i] ?? 0, total: [120, 64, 412, 40][i] ?? 0,
  blind: 'blind' in q ? Boolean((q as { blind?: boolean }).blind) : false,
  disabledReason: q.kind === 'training windows' ? 'training windows are a WindowSet, not a SpanSet' : undefined,
}))

export interface ExploreSpanOption { id: string; recording: string; channel: string; from_h: number; to_h: number; spans: number }
export const EXPLORE_SPANS: ExploreSpanOption[] = [
  { id: 'x-0044', recording: 'M2_aug fs1', channel: 'CH4_A2', from_h: 336.0, to_h: 343.0, spans: 21 },
  { id: 'x-0045', recording: 'M3_jul', channel: 'CH2', from_h: 58.0, to_h: 68.0, spans: 9 },
]

/* ---------------------------------------------------------------- the chain ---------------------------------------------------------------- */
export type BlockStatus = 'cached' | 'stale' | 'running' | 'failed' | 'new'
export interface ChainBlock { id: string; index: number | null; label: string; glyph: string; signature: string }

export const CHAIN_SLOPE: ChainBlock[] = [
  { id: 'source', index: null, label: 'Library family', glyph: 'source', signature: '— → SpanSet' },
  { id: 'block1', index: 1, label: 'Resolve spans', glyph: 'drop_detection', signature: 'SpanSet → Features' },
  { id: 'block2', index: 2, label: 'Aggregate', glyph: 'window_matrix', signature: 'Features → View' },
]
export const CHAIN_SPIKE: ChainBlock[] = [
  CHAIN_SLOPE[0],
  { id: 'block1', index: 1, label: 'Spike shape', glyph: 'spike', signature: 'SpanSet → Features' },
  CHAIN_SLOPE[2],
]

export const ESTIMATE = { cached: '≈ 6 s', cachedNote: '3 of 3 cached', stale: '≈ 2 s', staleNote: 're-runs 01 → 02' }
export const NULL_SPEC = {
  label: 'matched random windows', repeats: '200×',
  detail: 'Every number on an interrogation page carries a null (P10). Windows of the same length are drawn at matched positions in the same channel, 200 times; interval statistics use shuffled onsets instead.',
}
export const RUN_STEPS = ['Library family', '01 Resolve spans', '02 Aggregate']

/* ---------------------------------------------------------------- 01 rules ---------------------------------------------------------------- */
export const RULES = {
  onset: [
    { value: 'walk-back', label: 'walk back from steepest while descending' },
    { value: 'baseline-cross', label: 'last crossing of the baseline band' },
    { value: 'fixed', label: 'fixed −5 s before the steepest sample' },
  ],
  trough: [
    { value: 'run3', label: 'first run of 3 exceeding +0.5 σ' },
    { value: 'minimum', label: 'global minimum inside the span' },
    { value: 'run5', label: 'first run of 5 exceeding +0.5 σ' },
  ],
  sigma: [
    { value: 'mad', label: 'MAD · 0.000958 mV/s' },
    { value: 'sd', label: 'SD · 0.00141 mV/s' },
    { value: 'manual', label: 'set by hand' },
  ],
  steepestWindow: { min: 1, max: 11, step: 2, recommended: 3, unit: 'samples' },
}
export const STALE_PREVIEW = 'preview on cached spans: mean angle −28° → −25° · 3 of 16 events shift > 10 % · depth unchanged'
export const UNITS = [
  { value: 'mv-10s', label: 'mV · 10 s' },
  { value: 'mv-s', label: 'mV · s' },
  { value: 'z', label: 'z · 10 s', disabled: true, reason: 'waveforms are never normalised on screen (D5)' },
]
/** What a unit choice actually changes (fix r1: the control used to rewrite a caption and nothing else).
 *  `mV · 10 s` is the canon-corrected scale this page is built on — plotted seconds are recording seconds
 *  and −45° on the rose is −0.1 mV/s. `mV · s` is the frame's own compressed convention: one plotted
 *  second is ten seconds of recording, so every time divides by 10 and every slope multiplies by 10.
 *  The angle is unchanged under either, because the slope and the −45° reference scale together. */
export interface UnitScale { time: number; slope: number; note: string }
export const UNIT_SCALES: Record<string, UnitScale> = {
  'mv-10s': { time: 1, slope: 1, note: 'plotted seconds are recording seconds' },
  'mv-s': { time: 0.1, slope: 10, note: '1 plotted s = 10 s of recording (the frame convention)' },
  z: { time: 1, slope: 1, note: 'normalised — refused on screen (D5)' },
}
export const unitScale = (v: string): UnitScale => UNIT_SCALES[v] ?? UNIT_SCALES['mv-10s']

export const MARKS = [
  { value: 'minimal', label: 'minimal' },
  { value: 'all', label: 'all marks' },
  { value: 'none', label: 'none' },
]

/* ---------------------------------------------------------------- 02 Aggregate ---------------------------------------------------------------- */
export interface FeatureSpec { key: string; label: string; unit: string; kind: 'measure' | 'time' }
export interface HistSpec {
  feature: string; title: string; unit: string; colour: string; nullColour: string; domain: [number, number]
  verdict: string; verdictTone?: 'amber' | 'muted'
  /** the same verdict against the shuffled-onset null — the `null` parameter switches between the two */
  verdictShuffled: string; verdictShuffledTone?: 'amber' | 'muted'
}
export interface PairSpec {
  key: string; label: string; x: string; y: string; xLabel: string; yLabel: string
  beta: number; ci: [number, number]; r2: number; nullBeta: number; nullCi: [number, number]
  /** the same fit against the shuffled-onset null */
  nullShuffled: { beta: number; ci: [number, number] }
  relation: string; pooled?: boolean
  byRecording?: { recording: string; beta: number | null; ci?: [number, number]; n: number; note?: string }[]
}
export interface UpstreamSpec {
  key: 'slope' | 'spike-shape'
  block: string; blockTitle: string; subtitle: string
  features: FeatureSpec[]
  hists: HistSpec[]
  pairs: PairSpec[]
  purity: string
  tiles: { label: string; value: string; tone?: 'blue' | 'green' }[]
  timelineHeight: string
}

/** Feature-identity palette: a categorical hue per feature that avoids the §3 verdict/origin hues. */
export const FEATURE_COLOURS = ['#2F6FED', '#8B5CF6', '#0E9AA8']
export const NULL_GREY = '#d1d5db'

export const UPSTREAMS: Record<'slope' | 'spike-shape', UpstreamSpec> = {
  slope: {
    key: 'slope', block: '01 Resolve spans', blockTitle: 'Resolve spans — slope analysis', subtitle: 'distributions and scaling',
    features: [
      { key: 'depth_mV', label: 'depth_mV', unit: 'mV', kind: 'measure' },
      { key: 'duration_s', label: 'duration_s', unit: 's', kind: 'measure' },
      { key: 'max_slope', label: 'max_slope', unit: 'mV/s', kind: 'measure' },
      { key: 'peakedness', label: 'peakedness', unit: '—', kind: 'measure' },
      { key: 'recovery_s', label: 'recovery_s', unit: 's', kind: 'measure' },
      { key: 'onset_h', label: 'onset_h', unit: 'h', kind: 'time' },
    ],
    hists: [
      { feature: 'depth_mV', title: 'Drop depth', unit: 'mV', colour: FEATURE_COLOURS[0], nullColour: NULL_GREY, domain: [0.10, 0.40], verdict: 'dip test p 0.21 · n too small to call modes', verdictTone: 'amber', verdictShuffled: 'dip test p 0.19 · n too small to call modes', verdictShuffledTone: 'amber' },
      { feature: 'interval_h', title: 'Inter-event interval', unit: 'h', colour: FEATURE_COLOURS[1], nullColour: NULL_GREY, domain: [0, 2.0], verdict: 'CV 0.31 · null CV 0.98 [0.71–1.22] · p < 0.01', verdictShuffled: 'CV 0.31 · shuffled-onset CV 1.04 [0.78–1.31] · p < 0.01' },
      { feature: 'max_slope', title: 'Max slope', unit: 'mV/s', colour: FEATURE_COLOURS[2], nullColour: NULL_GREY, domain: [0.028, 0.076], verdict: 'median 0.066 · null median 0.021 · p < 0.01', verdictShuffled: 'median 0.066 · shuffled-onset median 0.043 · p 0.02' },
    ],
    pairs: [
      {
        key: 'depth-duration', label: 'depth ~ duration', x: 'duration_s', y: 'depth_mV', xLabel: 'duration →', yLabel: 'depth mV',
        beta: 1.42, ci: [1.18, 1.66], r2: 0.81, nullBeta: 0.12, nullCi: [-0.31, 0.52], nullShuffled: { beta: 0.28, ci: [-0.19, 0.74] }, relation: 'depth ∝ duration^β',
      },
      {
        key: 'depth-maxslope', label: 'depth ~ max slope', x: 'max_slope', y: 'depth_mV', xLabel: 'max slope mV/s', yLabel: 'depth mV',
        beta: 1.95, ci: [1.52, 2.38], r2: 0.74, nullBeta: 0.08, nullCi: [-0.29, 0.44], nullShuffled: { beta: 0.21, ci: [-0.24, 0.66] }, relation: 'depth ∝ |slope|^β', pooled: true,
        byRecording: [
          { recording: 'M2_aug fs1', beta: 2.04, ci: [1.49, 2.59], n: 9 },
          { recording: 'M3_jul', beta: 1.71, ci: [0.62, 2.80], n: 5 },
          { recording: 'L_LM_Jul26_J', beta: null, n: 2, note: 'not fitted' },
        ],
      },
      {
        key: 'interval-depth', label: 'interval ~ depth', x: 'depth_mV', y: 'interval_h', xLabel: 'depth mV', yLabel: 'interval h',
        beta: 0.42, ci: [0.05, 0.79], r2: 0.21, nullBeta: 0.03, nullCi: [-0.30, 0.36], nullShuffled: { beta: 0.09, ci: [-0.28, 0.45] }, relation: 'interval ∝ depth^β',
      },
    ],
    purity: 'one fall per window',
    tiles: [
      { label: 'events', value: '16' },
      { label: 'β depth~dur', value: '1.42', tone: 'blue' },
      { label: 'interval CV', value: '0.31', tone: 'blue' },
      { label: 'one fall / window', value: '100 %', tone: 'green' },
    ],
    timelineHeight: 'depth',
  },
  'spike-shape': {
    key: 'spike-shape', block: '01 Spike shape', blockTitle: 'Spike shape', subtitle: 'features from 01 Spike shape',
    features: [
      { key: 'amplitude_mV', label: 'amplitude_mV', unit: 'mV', kind: 'measure' },
      { key: 'half_width_s', label: 'half_width_s', unit: 's', kind: 'measure' },
      { key: 'rise_s', label: 'rise_s', unit: 's', kind: 'measure' },
      { key: 'decay_s', label: 'decay_s', unit: 's', kind: 'measure' },
      { key: 'isi_s', label: 'isi_s', unit: 's', kind: 'measure' },
      { key: 'onset_h', label: 'onset_h', unit: 'h', kind: 'time' },
    ],
    hists: [
      { feature: 'amplitude_mV', title: 'Amplitude', unit: 'mV', colour: FEATURE_COLOURS[0], nullColour: NULL_GREY, domain: [0.10, 0.40], verdict: 'dip test p 0.34 · n too small to call modes', verdictTone: 'amber', verdictShuffled: 'dip test p 0.29 · n too small to call modes', verdictShuffledTone: 'amber' },
      { feature: 'half_width_s', title: 'Half-width', unit: 's', colour: FEATURE_COLOURS[1], nullColour: NULL_GREY, domain: [0, 9.0], verdict: 'median 8.4 s · null median 5.1 s · p < 0.01', verdictShuffled: 'median 8.4 s · shuffled-onset median 6.2 s · p 0.04' },
      { feature: 'rise_s', title: 'Rise time', unit: 's', colour: FEATURE_COLOURS[2], nullColour: NULL_GREY, domain: [0, 9.0], verdict: 'median 3.1 s · null median 4.4 s · p 0.03', verdictShuffled: 'median 3.1 s · shuffled-onset median 3.6 s · p 0.21' },
    ],
    pairs: [
      { key: 'amp-hw', label: 'amplitude ~ half-width', x: 'half_width_s', y: 'amplitude_mV', xLabel: 'half-width →', yLabel: 'amplitude mV', beta: 0.88, ci: [0.61, 1.15], r2: 0.62, nullBeta: 0.05, nullCi: [-0.40, 0.49], nullShuffled: { beta: 0.14, ci: [-0.33, 0.60] }, relation: 'amplitude ∝ half-width^β' },
      { key: 'rise-decay', label: 'rise ~ decay', x: 'decay_s', y: 'rise_s', xLabel: 'decay s', yLabel: 'rise s', beta: 0.54, ci: [0.21, 0.87], r2: 0.38, nullBeta: 0.02, nullCi: [-0.35, 0.39], nullShuffled: { beta: 0.11, ci: [-0.31, 0.52] }, relation: 'rise ∝ decay^β' },
      { key: 'amp-isi', label: 'amplitude ~ ISI', x: 'isi_s', y: 'amplitude_mV', xLabel: 'ISI s', yLabel: 'amplitude mV', beta: 0.31, ci: [-0.04, 0.66], r2: 0.14, nullBeta: 0.01, nullCi: [-0.33, 0.35], nullShuffled: { beta: 0.04, ci: [-0.30, 0.38] }, relation: 'amplitude ∝ ISI^β' },
    ],
    purity: 'one spike per window',
    tiles: [
      { label: 'events', value: '16' },
      { label: 'β amp~hw', value: '0.88', tone: 'blue' },
      { label: 'half-width med', value: '8.4 s', tone: 'blue' },
      { label: 'one spike / window', value: '100 %', tone: 'green' },
    ],
    timelineHeight: 'amplitude',
  },
}

export const AGGREGATE_PARAMS = {
  colourBy: [
    { value: 'none', label: 'none' },
    { value: 'recording', label: 'recording' },
    { value: 'channel', label: 'channel' },
    { value: 'verdict', label: 'verdict' },
  ],
  nulls: [
    { value: 'matched', label: 'matched random windows · 200×' },
    { value: 'shuffled', label: 'shuffled onsets · 200×' },
    { value: 'none', label: 'no null', disabled: true, reason: 'every interrogation result carries a null (P10) · change the method in Settings › Nulls' },
  ],
  binning: [
    { value: 'fd', label: 'Freedman–Diaconis' },
    { value: 'sturges', label: 'Sturges' },
    { value: 'fixed', label: 'fixed · 20 bins' },
  ],
  interval: [
    { value: 'onset-onset', label: 'onset → onset' },
    { value: 'trough-trough', label: 'trough → trough' },
    { value: 'onset-trough', label: 'onset → trough' },
  ],
  outliers: [
    { value: 'kept', label: 'kept, flagged' },
    { value: 'excluded', label: 'excluded from fits' },
    { value: 'winsorised', label: 'winsorised at 5 / 95' },
  ],
  axes: [
    { value: 'log-log', label: 'log–log' },
    { value: 'linear', label: 'linear' },
  ],
}

/** τ per recording for the occurrence timeline ("When events happened"). */
export const TIMELINE_TREND: Record<string, { tau: number | null; p: number | null; note?: string }> = {
  'M2_aug fs1': { tau: 0.52, p: 0.006 },
  'M2_aug fs2': { tau: 0.18, p: 0.31 },
  M3_jul: { tau: -0.20, p: 0.62 },
  L_LM_Jul26_J: { tau: null, p: null, note: 'n 2 · no trend test' },
}

/* ---------------------------------------------------------------- traces ---------------------------------------------------------------- */
const hash = (s: string) => { let h = 7; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0; return h }

/** The event curve, mV, at 1 sample/s: `pre` s of baseline, a smooth fall of `duration_s` (steepest at
 *  half of it), then an exponential recovery. Never normalised. */
export function eventCurve(m: InterrogationMember, pre = 10, post = 24): number[] {
  const rnd = seeded(hash(m.id))
  const n = pre + Math.round(m.duration_s) + post
  const out: number[] = []
  for (let i = 0; i < n; i++) {
    const t = i - pre
    let v = (rnd() - 0.5) * 0.014
    if (t > 0 && t <= m.duration_s) { const u = t / m.duration_s; v -= m.depth_mV * (u * u * (3 - 2 * u)) }
    else if (t > m.duration_s) { const u = (t - m.duration_s) / Math.max(1, m.recovery_s); v -= m.depth_mV * Math.exp(-2.1 * u) }
    out.push(+v.toFixed(5))
  }
  return out
}

/** Sample index of the steepest sample, the onset and the trough, in seconds relative to onset. */
export const eventMarks = (m: InterrogationMember) => ({ onset: 0, steepest: +(m.duration_s / 2).toFixed(1), trough: m.duration_s })

export const FAMILY_Y_DOMAIN: [number, number] = [-0.45, 0.05]

/* ---------------------------------------------------------------- 02 Aggregate: what a parameter does ----------------------------------------------------------------
 * Every control on the Parameters card recomputes something here. Nothing below invents a number the
 * points cannot carry: `MIN_FIT_N` is the floor under which the scaling card refuses to fit at all. */

/** A power-law fit needs more than a handful of points; below this the scaling card says so instead. */
export const MIN_FIT_N = 12

export interface FitResult { beta: number; ci: [number, number]; r2: number; n: number }

/** Ordinary least squares on log10 axes: exponent, 95 % CI (t ≈ 2.12) and R². */
export function fitLogLog(pts: { x: number; y: number }[]): FitResult | null {
  const ok = pts.filter(p => p.x > 0 && p.y > 0 && Number.isFinite(p.x) && Number.isFinite(p.y))
  const n = ok.length
  if (n < 3) return null
  const xs = ok.map(p => Math.log10(p.x)), ys = ok.map(p => Math.log10(p.y))
  const mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n
  const sxx = xs.reduce((s, x) => s + (x - mx) ** 2, 0)
  if (sxx <= 1e-12) return null
  const beta = xs.reduce((s, x, i) => s + (x - mx) * (ys[i] - my), 0) / sxx
  const a = my - beta * mx
  const ss = ys.reduce((s, y, i) => s + (y - (a + beta * xs[i])) ** 2, 0)
  const st = ys.reduce((s, y) => s + (y - my) ** 2, 0)
  const se = Math.sqrt(ss / Math.max(1, n - 2) / sxx)
  return { beta, ci: [beta - 2.12 * se, beta + 2.12 * se], r2: st > 0 ? 1 - ss / st : 0, n }
}

/** The fit the page shows: the recorded fit (what the frame draws for the default parameter set) moved by
 *  whatever the current parameters actually change about the points. Dropping or winsorising points moves
 *  β, widens or narrows its CI and moves R² by the amount they really move — while the default set still
 *  reads exactly as recorded. Returns null when there are too few points to fit at all. */
export function adjustedFit(spec: { beta: number; ci: [number, number]; r2: number }, all: { x: number; y: number }[], used: { x: number; y: number }[]): FitResult | null {
  if (used.length < MIN_FIT_N) return null
  const fa = fitLogLog(all), fu = fitLogLog(used)
  if (!fa || !fu) return null
  const beta = +(spec.beta + (fu.beta - fa.beta)).toFixed(3)
  const halfA = (spec.ci[1] - spec.ci[0]) / 2
  const half = halfA * ((fu.ci[1] - fu.ci[0]) / Math.max(1e-6, fa.ci[1] - fa.ci[0]))
  const r2 = Math.max(0, Math.min(1, spec.r2 + (fu.r2 - fa.r2)))
  return { beta, ci: [beta - half, beta + half], r2, n: used.length }
}

/** Bin count per rule: Freedman–Diaconis (2·IQR·n^−1/3), Sturges (log2 n + 1), or a fixed 20. */
export function binCount(values: number[], mode: string): number {
  const n = values.length
  if (!n) return 1
  if (mode === 'fixed') return 20
  if (mode === 'sturges') return Math.max(2, Math.ceil(Math.log2(n) + 1))
  const s = [...values].sort((a, b) => a - b)
  const q = (p: number) => s[Math.min(s.length - 1, Math.floor(p * (s.length - 1)))]
  const iqr = q(0.75) - q(0.25), lo = s[0], hi = s[s.length - 1]
  if (iqr <= 0 || hi <= lo) return Math.max(2, Math.ceil(Math.sqrt(n)))
  /* FD is capped at 2√n bins, the usual practical guard: a few long gaps make the range wide next to
     the IQR, and without it the interval histogram shatters into a comb. */
  return Math.max(3, Math.min(Math.ceil(2 * Math.sqrt(n)), Math.ceil((hi - lo) / (2 * iqr * Math.pow(n, -1 / 3)))))
}

/** Where an interval starts and ends, in hours since that recording's start (§0). The three definitions
 *  differ by the fall itself (6–11 s ≈ 0.002 h), so the distribution moves only a little — the page says
 *  so rather than pretending the choice is dramatic. */
export const INTERVAL_ENDS: Record<string, { from: (m: InterrogationMember) => number; to: (m: InterrogationMember) => number; label: string }> = {
  'onset-onset': { from: m => m.onset_h, to: m => m.onset_h, label: 'onset → onset' },
  'trough-trough': { from: m => m.onset_h + m.duration_s / 3600, to: m => m.onset_h + m.duration_s / 3600, label: 'trough → trough' },
  'onset-trough': { from: m => m.onset_h, to: m => m.onset_h + m.duration_s / 3600, label: 'onset → trough' },
}

/** The percentile p of a sample (nearest rank), used by the winsorising outlier rule. */
export function percentile(values: number[], p: number): number {
  if (!values.length) return 0
  const s = [...values].sort((a, b) => a - b)
  return s[Math.max(0, Math.min(s.length - 1, Math.round(p * (s.length - 1))))]
}
