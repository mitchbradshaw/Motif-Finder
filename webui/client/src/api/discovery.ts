/* Discovery reads (spec §7, frames discovery-1 … discovery-3b). Every read returns Sourced<T>; until the bridge
 * serves Discovery sessions these resolve the fixtures in fixtures/discovery.ts and say `source: 'demo'`.
 * Writes (add run, discard, send to Review, save template, SLURM script) do not come through here: they go to the
 * in-memory demo store from the pages. M4_aug (held out, D6) is refused by every read that would touch its data. */
import { demo, type Sourced } from './seam'
import {
  DISCOVERY_LIMIT_MIN, HISTORY, PAIR_OVERLAP, PAIR_TILES, POOLED_RECALL, RECORDING_OPTIONS, REBIND_EXEMPLARS, ROLES, RUNS, RUN_CHAINS, SCORE_FIXTURE, SEED_DRAFT,
  SEED_OPTIONS, SEED_RECOMMENDED, SESSION, TEMPLATES, detectionWindow, detectionsFor, fireCount, generatedScore, overviewTrace, reviewedHoursInBin, reviewedHoursIn,
  rng, seedCandidates, seedNull, seedProfile, smoothTrace, strHash,
  type Detection, type DiscoveryRun, type DiscoverySession, type DiscoveryTemplate, type Disagreement, type GlyphKind, type HistoryEntry, type OverlapRow, type Recall,
  type RecordingOption, type Role, type RoleCell, type ScoreCells, type SeedDraft, type SeedInfo, type SeedMatch, type SeedParams,
} from '../fixtures/discovery'

export type {
  Detection, DiscoveryRun, DiscoverySession, DiscoveryTemplate, Disagreement, GlyphKind, HistoryEntry, OverlapRow, Recall, RecordingOption, Role, RoleCell, ScoreCells,
  SeedDraft, SeedInfo, SeedMatch, SeedParams,
}
export type { RunKind, RunStatus, SeedSource, TemplateStage } from '../fixtures/discovery'
export { DISCOVERY_LIMIT_MIN, ROLES, SEED_RECOMMENDED, EXTRA_RUN_COLOURS, REBIND_EXEMPLARS } from '../fixtures/discovery'

const HELD_OUT = RECORDING_OPTIONS.filter(r => r.heldOut)
export const heldOutReason = (label = HELD_OUT[0]?.file ?? 'M4_aug_concat_fs1.mat') =>
  `${label} is held out (D6): locked for the final evaluation — Discovery will not scope, run or plot it`
export const isHeldOut = (recording: string) => HELD_OUT.some(r => r.key === recording || r.file === recording || r.label === recording)

/* ------------------------------------------------------------------ session, runs, templates */
export interface SessionData { session: DiscoverySession; recordings: RecordingOption[] }
export const getSession = (): Promise<Sourced<SessionData>> => demo({ session: SESSION, recordings: RECORDING_OPTIONS })
export const getRuns = (): Promise<Sourced<DiscoveryRun[]>> => demo(RUNS)
export const getTemplates = (): Promise<Sourced<DiscoveryTemplate[]>> => demo(TEMPLATES)
export const getHistory = (): Promise<Sourced<HistoryEntry[]>> => demo(HISTORY)
export const getRebindExemplars = () => demo(REBIND_EXEMPLARS)

/* ------------------------------------------------------------------ scope */
export type Refusable<T> = { refused: string } | { refused?: undefined; data: T }
export function getOverview(recording: string, channels: string[]): Promise<Sourced<Refusable<Record<string, number[]>>>> {
  const rec = RECORDING_OPTIONS.find(r => r.key === recording)
  if (!rec || rec.heldOut) return demo({ refused: heldOutReason(rec?.file) })
  return demo({ data: Object.fromEntries(channels.map(ch => [ch, overviewTrace(recording, ch, rec.hours)])) }, 40)
}

/* ------------------------------------------------------------------ where each run fires */
export interface FiresRow { run: string; counts: number[]; unfinishedFrom?: number /* bin index where the run's unfinished part starts */ }
export interface FiresChannel { channel: string; reviewedH: number; reviewed: number[]; rows: FiresRow[] }
export interface FiresData { binH: number; firstBin: number; nBins: number; channels: FiresChannel[] }
export function getFires(channels: string[], section: [number, number], runs: DiscoveryRun[]): Promise<Sourced<FiresData>> {
  const binH = 3
  const firstBin = Math.floor(section[0] / binH)
  const nBins = Math.max(1, Math.ceil(section[1] / binH) - firstBin)
  const bins = Array.from({ length: nBins }, (_, i) => firstBin + i)
  const data: FiresData = {
    binH, firstBin, nBins,
    channels: channels.map(ch => ({
      channel: ch, reviewedH: reviewedHoursIn(ch, section), reviewed: bins.map(b => reviewedHoursInBin(ch, b)),
      rows: runs.map(r => ({
        run: r.key,
        counts: bins.map(b => fireCount(ch, r.template === 'seed_F03_native_2' ? 'seed_F03_native' : r.key === 'human' ? 'human' : (r.template ?? r.key), b)),
        unfinishedFrom: r.status === 'on cluster' || r.status === 'running' ? Math.floor(nBins * (r.progress ?? 0)) : undefined,
      })),
    })),
  }
  return demo(data, 50)
}

/* ------------------------------------------------------------------ scoreboard */
export interface ScoreRow extends ScoreCells { precision: number | null; xNull: number | null }
export interface ScoreRun { run: string; total: ScoreRow; channels: (ScoreRow & { channel: string })[]; pooledH: number }
const withRatios = (c: ScoreCells): ScoreRow => ({ ...c, precision: c.reviewed ? c.interesting / c.reviewed : null, xNull: c.nullExpects ? c.found / c.nullExpects : null })
export function scoreFor(run: string, channel: string, section: [number, number]): ScoreCells {
  return SCORE_FIXTURE[run]?.[channel] ?? generatedScore(run, channel, section)
}
export function getScoreboard(runKeys: string[], channels: string[], section: [number, number]): Promise<Sourced<ScoreRun[]>> {
  const canonical = channels.join(',') === SESSION.channels.join(',') && section[0] === SESSION.section[0] && section[1] === SESSION.section[1]
  const out = runKeys.map(run => {
    const rows = channels.map(ch => ({ channel: ch, ...withRatios(scoreFor(run, ch, section)) }))
    const sum = (k: 'found' | 'judged' | 'reviewed' | 'interesting' | 'nullExpects') => rows.reduce((s, r) => s + r[k], 0)
    const recallRows = rows.filter(r => 'value' in r.recall) as (ScoreRow & { channel: string; recall: { value: number; overH: number } })[]
    const pooledH = recallRows.reduce((s, r) => s + r.recall.overH, 0)
    const pooled: Recall = canonical && POOLED_RECALL[run] ? POOLED_RECALL[run]
      : recallRows.length ? { value: +(recallRows.reduce((s, r) => s + r.recall.value * r.recall.overH, 0) / pooledH).toFixed(2), overH: pooledH } : { none: true }
    return { run, pooledH, channels: rows, total: withRatios({ found: sum('found'), judged: sum('judged'), reviewed: sum('reviewed'), interesting: sum('interesting'), nullExpects: sum('nullExpects'), recall: pooled }) }
  })
  return demo(out, 50)
}

/* ------------------------------------------------------------------ browse detections */
export function getDetections(run: string, channel: string, section: [number, number]): Promise<Sourced<Detection[]>> {
  const n = scoreFor(run, channel, section).found
  return demo(detectionsFor(run, channel, n, section), 40)
}
export const getDetectionWindow = (det: Detection) => demo(detectionWindow(det), 30)

/* ------------------------------------------------------------------ seed search */
export interface SeedSetup { draft: SeedDraft; seeds: SeedInfo[]; recommended: SeedParams }
export const getSeedSetup = (): Promise<Sourced<SeedSetup>> => demo({ draft: SEED_DRAFT, seeds: SEED_OPTIONS, recommended: SEED_RECOMMENDED })
export interface SeedResults { candidates: SeedMatch[]; nullDistances: number[] }
export function getSeedResults(seedId: string, channels: string[]): Promise<Sourced<SeedResults>> {
  return demo({ candidates: seedCandidates(seedId, channels), nullDistances: seedNull(channels) }, 50)
}
export function getSeedProfile(seedId: string, channel: string, view: [number, number], candidates: SeedMatch[]) {
  return demo(seedProfile(seedId, channel, view, candidates), 30)
}

/* ------------------------------------------------------------------ compare */
export interface CompareSide { run: string; label: string; subtitle: string; isSeed: boolean; cells: Record<Role, RoleCell | null>; precision: number | null; reviewed: number; xNull: number | null; threshold: number }
export interface CompareData {
  a: CompareSide; b: CompareSide
  differing: Role[]
  overlap: OverlapRow[]; total: OverlapRow
  disagreements: Disagreement[]      // every disagreement, sorted: closest call first
  both: { channel: string; atH: number }[]
}
const HUMAN_CHAIN: Record<Role, RoleCell | null> = {
  Source: { name: 'Source', param: 'reviewed hours', signature: '— → Signal', glyph: 'source' },
  Preprocess: null, 'Score / estimate': null, Encode: null,
  Detect: { name: 'human verdicts', param: '41 h reviewed', signature: 'Review → SpanSet', glyph: 'human' },
}
function chainOf(run: string): { subtitle: string; cells: Record<Role, RoleCell | null> } {
  if (run === 'human') return { subtitle: 'reference', cells: HUMAN_CHAIN }
  if (RUN_CHAINS[run]) return RUN_CHAINS[run]
  const t = TEMPLATES.find(x => x.name === run)
  if (!t) return { subtitle: 'run', cells: { Source: RUN_CHAINS.drop_motifs9.cells.Source, Preprocess: null, 'Score / estimate': null, Encode: null, Detect: null } }
  const byGlyph = (g: GlyphKind[]) => { const s = t.stages.find(st => g.includes(st.glyph)); return s ? { index: s.index, name: s.name, param: s.locked ?? '', signature: s.signature, glyph: s.glyph } : null }
  return { subtitle: `${t.kind}`, cells: { Source: RUN_CHAINS.drop_motifs9.cells.Source, Preprocess: byGlyph(['baseline']), 'Score / estimate': byGlyph(['mp', 'seed', 'model', 'spike', 'noise']), Encode: byGlyph(['sax']), Detect: byGlyph(['threshold', 'drop']) } }
}
const sameCell = (x: RoleCell | null, y: RoleCell | null) => (x === null && y === null) || (!!x && !!y && x.name === y.name && x.param === y.param)

function overlapFor(a: string, b: string, channels: string[], section: [number, number]): OverlapRow[] {
  const frame = (a === 'drop_motifs9' && b === 'seed_F03_native') || (a === 'seed_F03_native' && b === 'drop_motifs9')
  return channels.map(ch => {
    const fx = frame ? PAIR_OVERLAP.find(p => p.channel === ch) : undefined
    if (fx) return a === 'drop_motifs9' ? fx : { channel: ch, onlyA: fx.onlyB, both: fx.both, onlyB: fx.onlyA }
    const fa = a === 'human' ? Math.round(reviewedHoursIn(ch, section) * 0.9) : scoreFor(a, ch, section).found
    const fb = b === 'human' ? Math.round(reviewedHoursIn(ch, section) * 0.9) : scoreFor(b, ch, section).found
    const r = rng([a, b].sort().join('|') + ch)
    const both = Math.round(Math.min(fa, fb) * (0.2 + r() * 0.35))
    return { channel: ch, onlyA: fa - both, both, onlyB: fb - both }
  })
}

export function getCompare(a: string, b: string, channels: string[], section: [number, number]): Promise<Sourced<CompareData>> {
  const ca = chainOf(a), cb = chainOf(b)
  const differing = ROLES.filter(r => !sameCell(ca.cells[r], cb.cells[r]))
  const overlap = overlapFor(a, b, channels, section)
  const total = overlap.reduce((s, r) => ({ channel: 'all channels', onlyA: s.onlyA + r.onlyA, both: s.both + r.both, onlyB: s.onlyB + r.onlyB }), { channel: 'all channels', onlyA: 0, both: 0, onlyB: 0 })
  const isSeed = (k: string) => k.startsWith('seed')
  const disagreements: Disagreement[] = []
  const both: { channel: string; atH: number }[] = []
  for (const row of overlap) {
    const push = (kind: 'only A' | 'only B', n: number) => {
      const other = kind === 'only A' ? b : a
      const self = kind === 'only A' ? a : b
      for (let i = 0; i < n; i++) {
        const r = rng(`${self}|${other}|${row.channel}|${kind}`, i)
        const seedOther = isSeed(other)
        const thr = seedOther ? 3.1 : 0.5
        const near = seedOther ? +(3.2 + r() * r() * 2.6).toFixed(1) : +(0.45 - r() * r() * 0.4).toFixed(2)
        disagreements.push({ kind, channel: row.channel, atH: +(section[0] + ((i + 0.2 + r() * 0.6) / n) * (section[1] - section[0])).toFixed(2), detection: `d-${String(2000 + (strHash(self + row.channel) % 5000) + i).padStart(4, '0')}`, score: +(0.55 + r() * 0.4).toFixed(2), otherNearest: near, otherThreshold: thr, otherIsSeed: seedOther })
      }
    }
    push('only A', row.onlyA)
    push('only B', row.onlyB)
    for (let i = 0; i < row.both; i++) { const r = rng(`${a}|${b}|${row.channel}|both`, i); both.push({ channel: row.channel, atH: +(section[0] + ((i + r()) / row.both) * (section[1] - section[0])).toFixed(2) }) }
  }
  const margin = (d: Disagreement) => Math.abs(d.otherNearest - d.otherThreshold) / (d.otherIsSeed ? 3.1 : 0.5)
  disagreements.sort((x, y) => margin(x) - margin(y))
  // frame 3: step 7 of "only A" is d-0412 at 192.4 h on CH4_A2, B's nearest d 3.6 (a near miss)
  if (a === 'drop_motifs9' && b === 'seed_F03_native' && channels.includes('CH4_A2')) {
    const onlyA = disagreements.filter(d => d.kind === 'only A')
    const target = onlyA.find(d => d.channel === 'CH4_A2')
    if (target && onlyA.length >= 7) {
      Object.assign(target, { atH: 192.4, detection: 'd-0412', score: 0.88, otherNearest: 3.6, otherThreshold: 3.1 })
      disagreements.splice(disagreements.indexOf(target), 1)
      disagreements.splice(disagreements.indexOf(onlyA.filter(d => d !== target)[5]) + 1, 0, target)
    }
  }
  const side = (run: string, c: typeof ca, fallbackPrecision: number | null, reviewed: number, xNull: number | null): CompareSide =>
    ({ run, label: run === 'human' ? 'human annotations' : run, subtitle: c.subtitle, isSeed: isSeed(run), cells: c.cells, precision: fallbackPrecision, reviewed, xNull, threshold: isSeed(run) ? 3.1 : 0.5 })
  const stats = (run: string) => {
    if (run === 'drop_motifs9') return [PAIR_TILES.aPrecision, PAIR_TILES.aReviewed, PAIR_TILES.aXNull] as const
    if (run === 'seed_F03_native') return [PAIR_TILES.bPrecision, PAIR_TILES.bReviewed, PAIR_TILES.bXNull] as const
    if (run === 'human') return [null, 0, null] as const
    const rows = channels.map(ch => scoreFor(run, ch, section))
    const rev = rows.reduce((s, r) => s + r.reviewed, 0), int = rows.reduce((s, r) => s + r.interesting, 0), f = rows.reduce((s, r) => s + r.found, 0), nl = rows.reduce((s, r) => s + r.nullExpects, 0)
    return [rev ? int / rev : null, rev, nl ? +(f / nl).toFixed(1) : null] as const
  }
  const [pa, ra, xa] = stats(a), [pb, rb, xb] = stats(b)
  return demo({ a: side(a, ca, pa, ra, xa), b: side(b, cb, pb, rb, xb), differing, overlap, total, disagreements, both }, 60)
}

/** The window a disagreement sits in: clean signal, A's span track, B's own score against its threshold. */
export interface DisagreementWindow { t0H: number; values: number[]; aSpan: [number, number] | null; bSpan: [number, number] | null; aScore: number[]; bScore: number[]; windowS: number; minAt: number }
export function windowFor(d: Disagreement): DisagreementWindow {
  const windowS = 40
  const t0H = d.atH - windowS / 2 / 3600
  const key = `${d.detection}|win`
  const base = syntheticTrace40(key, d)
  const mid = windowS / 2
  const span: [number, number] = [mid - 4, mid + 4]
  const r = rng(key)
  const profile = (nearest: number, isSeed: boolean) => Array.from({ length: windowS }, (_, i) => {
    const u = Math.min(1, Math.abs(i - mid) / 6)
    const noise = i === mid ? 0 : (r() - 0.5) * (isSeed ? 0.35 : 0.05)
    return isSeed ? +(nearest + u * 1.6 + noise).toFixed(3) : +(nearest * (1 - u * 0.7) + noise).toFixed(3)
  })
  const bScore = profile(d.otherNearest, d.otherIsSeed)
  return { t0H, values: base, windowS, minAt: mid, aSpan: d.kind === 'only A' ? span : null, bSpan: d.kind === 'only B' ? span : null, aScore: [], bScore }
}
function syntheticTrace40(key: string, d: Disagreement): number[] {
  const slow = smoothTrace(40, key, 0.05, 0.01)
  return slow.map((v, i) => { const u = (i - 17) / 6; return +(v - 0.38 * Math.exp(-u * u) * (d.detection === 'd-0412' ? 1 : 0.7)).toFixed(4) })
}
export const getDisagreementWindow = (d: Disagreement) => demo(windowFor(d), 30)

export function getChannelSignal(channel: string, view: [number, number]): Promise<Sourced<{ t0H: number; stepS: number; values: number[] }>> {
  const n = 1200
  const stepS = ((view[1] - view[0]) * 3600) / n
  return demo({ t0H: view[0], stepS, values: smoothTrace(n, `${channel}:section:${view[0]}:${view[1]}`, 0.2, 0.03) }, 30)
}

/* ------------------------------------------------------------------ compare every stage (3b) */
export type StageBadge = 'identical' | 'differs' | 'A only' | 'B only' | 'absent'
export type StageThumb =
  | { kind: 'trace'; values: number[]; ghost?: number[]; stroke?: string; span?: [number, number]; emptyTrack?: boolean }
  | { kind: 'segments'; values: number[]; cut: number }
  | { kind: 'distance'; values: number[]; threshold: number; minIndex: number; minValue: number; isSeed: boolean }
  | { kind: 'symbols'; values: number[]; lowRun: [number, number] }
  | { kind: 'absent' }
export interface StageCell { role: Role; cell: RoleCell | null; badge: StageBadge; thumb: StageThumb; caption: string; decided: string; absentNote?: string }
export interface StagesWindow { d: Disagreement; index: number; of: number; firstDiffering: Role | null; a: StageCell[]; b: StageCell[]; aSubtitle: string; bSubtitle: string }

export function getStagesWindow(a: string, b: string, d: Disagreement, index: number, of: number): Promise<Sourced<StagesWindow>> {
  const ca = chainOf(a), cb = chainOf(b)
  const w = windowFor(d)
  const signal = w.values
  const r = rng(`${d.detection}|stages`)
  const detrended = signal.map((v, i) => +(v - (i - 20) * 0.0022).toFixed(4))
  const segs = Array.from({ length: 30 }, (_, i) => +((r() - 0.5) * 0.09 - (i === 16 ? 0.16 : i === 19 ? 0.12 : 0)).toFixed(3))
  const sax = Array.from({ length: 36 }, (_, i) => (i >= 15 && i < 20 ? 0 : Math.max(1, Math.min(5, Math.round(2.6 + Math.sin(i * 0.6) * 1.6 + (r() - 0.5) * 1.4)))))
  const firedA = d.kind === 'only A', firedB = d.kind === 'only B'
  const cellFor = (side: 'A' | 'B', role: Role): StageCell => {
    const mine = (side === 'A' ? ca : cb).cells[role], theirs = (side === 'A' ? cb : ca).cells[role]
    const otherLabel = side === 'A' ? b : a
    const fired = side === 'A' ? firedA : firedB
    const badge: StageBadge = !mine ? 'absent' : !theirs ? (side === 'A' ? 'A only' : 'B only') : sameCell(mine, theirs) ? 'identical' : 'differs'
    if (!mine) {
      const theirCell = theirs
      return { role, cell: null, badge, thumb: { kind: 'absent' }, caption: `${otherLabel === 'human' ? 'human annotations' : 'the other run'} ${theirCell ? `runs ${theirCell.name.toLowerCase()} here` : 'has no stage here either'}`, decided: '— no stage',
        absentNote: role === 'Encode' && (side === 'B' ? cb : ca).cells['Score / estimate']?.glyph === 'seed' ? 'Seeded search reads the preprocessed signal directly' : `${side === 'A' ? a : b} has no ${role} stage` }
    }
    switch (mine.glyph) {
      case 'source': return { role, cell: mine, badge, thumb: { kind: 'trace', values: signal }, caption: `the same ${w.windowS} s in both runs`, decided: 'the same window' }
      case 'baseline': return { role, cell: mine, badge, thumb: { kind: 'trace', values: detrended, ghost: signal, stroke: 'var(--trace-blue)' }, caption: `${mine.param} · slow rise removed`, decided: `slow rise removed${badge === 'identical' ? ' (identical)' : ''}` }
      case 'noise': { const n = segs.filter(s => Math.abs(s) > 0.077).length; return { role, cell: mine, badge, thumb: { kind: 'segments', values: segs, cut: 0.077 }, caption: `σ 0.0096 mV · cut ±0.077 mV · ${n} segments qualify`, decided: `${n} segments beyond ±0.077 mV` } }
      case 'sax': return { role, cell: mine, badge, thumb: { kind: 'symbols', values: sax, lowRun: [15, 20] }, caption: `${mine.param} · one long low run at the fall`, decided: 'one long low run at the fall' }
      case 'seed': case 'mp': case 'model': case 'spike': {
        const isSeed = mine.glyph === 'seed' || mine.glyph === 'mp'
        const nearest = fired ? +(d.otherThreshold - 0.9).toFixed(1) : d.otherNearest
        const vals = w.bScore.map(v => +(v - d.otherNearest + nearest).toFixed(3))
        return { role, cell: mine, badge, thumb: { kind: 'distance', values: vals, threshold: isSeed ? 3.1 : 0.5, minIndex: w.minAt, minValue: nearest, isSeed },
          caption: isSeed ? `nearest d ${nearest.toFixed(1)} at ${(d.atH + 0.002).toFixed(3)} h · threshold 3.1` : `peak score ${nearest.toFixed(2)} · threshold 0.5`,
          decided: isSeed ? `nearest d ${nearest.toFixed(1)} · threshold 3.1` : `peak ${nearest.toFixed(2)} · threshold 0.5` }
      }
      case 'drop': case 'threshold': case 'human': {
        return { role, cell: mine, badge, thumb: { kind: 'trace', values: signal, span: fired ? [16, 24] : undefined, emptyTrack: !fired },
          caption: fired ? `1 span · depth ${d.detection === 'd-0412' ? '0.38' : (0.2 + r() * 0.2).toFixed(2)} mV · score ${d.score.toFixed(2)}` : mine.glyph === 'threshold' ? `0 spans · d never reaches ${mine.param.replace(/^d ≤ /, '')} in this window` : '0 spans · no drop steep enough in this window',
          decided: fired ? `1 span · score ${d.score.toFixed(2)}` : '0 spans' }
      }
      default: return { role, cell: mine, badge, thumb: { kind: 'trace', values: signal }, caption: mine.param, decided: mine.param }
    }
  }
  const A = ROLES.map(role => cellFor('A', role)), B = ROLES.map(role => cellFor('B', role))
  const firstDiffering = ROLES.find((role, i) => A[i].badge !== 'identical' || B[i].badge !== 'identical') ?? null
  return demo({ d, index, of, firstDiffering, a: A, b: B, aSubtitle: ca.subtitle, bSubtitle: cb.subtitle }, 60)
}

/* ------------------------------------------------------------------ estimates */
/** Minutes a run would take over the scope (runs not yet run). */
export const runEstimateMin = (perChannelMin: number, channels: number, sectionH: number, sessionH = 174) => perChannelMin * channels * (sectionH / sessionH)
export const fmtMin = (min: number) => min < 1 ? `≈ ${Math.max(1, Math.round(min * 60))} s` : min < 60 ? `≈ ${Math.round(min)} min` : `≈ ${(min / 60).toFixed(1)} h`
