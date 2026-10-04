/* Discovery reads (spec §7, frames discovery-1 … discovery-3b), wired to the bridge's 29 routes
 * (webui/server/discovery.py). Every read returns Sourced<T> and now says `source: 'live'`.
 *
 * This module is the adapter: the pages keep their fixture-era shapes, and where the server's payload
 * differs it is translated HERE rather than in a page. Three things are deliberately NOT translated,
 * because the server declined to give a number and inventing one would be a lie the page would then
 * draw: a template's `preview` / `perChannelMin` / `diskGB` (null until a real Preview has run), a
 * disagreement's `otherNearest` (a per-window computation — /compare/window returns it as `bScore`),
 * and `recall` (a value with its hours, or the server's own words for having none). Those types widen
 * and their pages branch.
 *
 * Writes (add run, discard, send to Review, save template, SLURM script) still go to the in-memory demo
 * store from the pages; their live routes are typed in api.ts and are Prompt 05's to call.
 * M4_aug (held out, D6) is refused by the bridge on every route that names it. */
import {
  ApiError, getDiscoveryCompare, getDiscoveryCompareStages, getDiscoveryCompareWindow, getDiscoveryDetectionWindow, getDiscoveryDetections,
  getDiscoveryBands, getDiscoveryFires, getDiscoveryHistory, getDiscoveryOverview, getDiscoveryRuns, getDiscoveryScoreboard, getDiscoverySeedProfile,
  getDiscoverySeedPage, getDiscoverySeedSetupFor, getDiscoverySeeds, getDiscoverySession, putDiscoverySeedDraft, getDiscoverySignal, getDiscoveryTemplates, pollDiscoverySeedResults,
  postDiscoveryPlan, postDiscoveryPreview, startDiscoverySeedResults,
  type CutRule, type DivBreakdown, type PrecisionFigures, type DiscBand, type DiscBandsPayload, type DiscLikeForLike, type DiscPerBand, type DiscSetMember, type DiscVerdictSplit, type DiscSeedPageQuery, type DiscPlan, type DiscPlanBody, type DiscPreview, type DiscRecordingOption, type DiscSeedParams, type DiscSeedQuery, type DiscSeedResults,
} from '../api'
import { pollDiscoverySeedResultsBanked, type DiscSeedBank } from '../api'
import { live, type Sourced } from './seam'
import type { GlyphKind, Role } from '../fixtures/discovery'

export type { GlyphKind, Role, RunKind, SeedSource } from '../fixtures/discovery'
export { ROLES, EXTRA_RUN_COLOURS, REBIND_EXEMPLARS } from '../fixtures/discovery'

/** The bridge sends `null` for a sample that is not finite. NaN is exactly that; substituting a number
 *  would invent data the recording does not carry. */
const nums = (xs: (number | null)[] | null | undefined): number[] => (xs ?? []).map(v => (v == null ? NaN : v))
/** A field the fixture type has as optional: the server's explicit null means "no value here". */
const opt = <T,>(v: T | null | undefined): T | undefined => (v == null ? undefined : v)

/* ------------------------------------------------------------------ session, runs, templates */
export interface SessionNull { method: string | null; n: number; requested?: string | null; supported?: boolean; reason?: string | null; explicit?: boolean; blockS?: number | null }
export interface DiscoverySession {
  id: number; name: string; recording: string; channels: string[]; section: [number, number]; sectionSamples: [number, number]
  null: SessionNull
  /** fixup-T (Q35): one null per run KIND, each with its own draw count — what the NEXT run of that kind draws */
  nulls?: { template: SessionNull; seed: SessionNull }
  localLimitMin: number; savedAt: string; matchingRule: { criterion: string; iou: number; onset: number }
}
export interface RecordingOption { key: string; label: string; file: string; stem: string; hours: number; channels: string[]; heldOut: boolean; fs: number; heldOutReason: string | null }
export interface SessionData { session: DiscoverySession; recordings: RecordingOption[] }

/** The local ceiling is the session's own (`localLimitMin`); this is the fallback for the first render. */
export const DISCOVERY_LIMIT_MIN = 20

export type RunStatus = 'reference' | 'done' | 'on cluster' | 'running' | 'queued' | 'new' | 'paused' | 'draft' | 'superseded' | 'failed' | 'cancelled' | 'completed'
export interface DiscoveryRun {
  key: string; id?: string; label: string; kind: 'reference' | 'template' | 'seed' | 'draft'; colour: string; glyph: GlyphKind
  detail: string
  version?: number; stageCount?: number; template?: string
  status: RunStatus; progress?: number; doneAt?: string
  reviewedH?: number
  perChannelMin?: number
  job?: string; pausedAt?: { stage: number; of: number }
  error?: string; addedThisSession?: boolean
  runGroupId?: number; channelsDone?: string; found?: number
  /** fixup-y: a seed run's seed and cut — what the Seed page finds its own run by, never the label */
  seedId?: string; cut?: number | null; entryId?: number | null
  /** fixup-v: the scale bank a seed run searched (null: the native length only) */
  scales?: number[] | null
  /** fixup-z: one band of a band-scoped *Apply template*; the band runs of one application share `bandSet`,
   *  which Compare takes as one side (`set:<bandSet>`) */
  band?: DiscBand | null; bandSet?: string | null; bandIndex?: number | null
}

export interface TemplateStage { index: string; name: string; signature: string; locked?: string; glyph: GlyphKind }
export interface DiscoveryTemplate {
  name: string; kind: 'template' | 'seed'; signature: string; fits: boolean; fitsReason?: string | null
  lastScore: string; savedAt: string; lastUsed: number; stages: TemplateStage[]
  /* null until a real Preview has been run on a sample — `previewNote` is the server's reason */
  perChannelMin: number | null; complexity: string; diskGB: number | null
  preview: { spans: number; hours: number; channel: string; nullGives: number } | null
  previewNote?: string | null
  bind?: string | null; inSession?: string | null; precision?: number; hasModel?: boolean
  version?: number | null; builtin?: boolean; description?: string | null
}
export interface HistoryEntry { id: string; label: string; when: string; status: string; runKey: string; inSession: boolean; detail: string }

/** The scope every scoped read needs, and the held-out list `isHeldOut` answers from. Filled by
 *  getSession; never trusted to be warm (see heldOutReason below). */
let SCOPE: { channels: string[]; section: [number, number] } | null = null
let RECORDINGS: RecordingOption[] | null = null

/** Held out (spec §0 D6) before the first session read has landed. The bridge refuses this file on every
 *  route; the cache only ever adds to what is refused here, so a cold cache cannot report a held-out
 *  recording as free. */
const HELD_OUT_FALLBACK = 'M4_aug_concat_fs1.mat'
const heldOutOptions = () => (RECORDINGS ?? []).filter(r => r.heldOut)

export const heldOutReason = (label = heldOutOptions()[0]?.file ?? HELD_OUT_FALLBACK) => {
  const known = (RECORDINGS ?? []).find(r => r.file === label || r.key === label || r.stem === label)
  return known?.heldOutReason
    ?? `${label} is held out (D6): locked for the final evaluation — Discovery will not scope, run or plot it`
}
export const isHeldOut = (recording: string) =>
  recording === HELD_OUT_FALLBACK || recording === HELD_OUT_FALLBACK.replace(/\.mat$/, '')
  /* by identifier only: `label` is what the dataset is CALLED and nothing may key on it (fixup-f) */
  || heldOutOptions().some(r => r.key === recording || r.file === recording || r.stem === recording)

const toRecording = (r: DiscRecordingOption): RecordingOption => ({ ...r })

export async function getSession(): Promise<Sourced<SessionData>> {
  return live(getDiscoverySession().then(p => {
    const recordings = p.recordings.map(toRecording)
    RECORDINGS = recordings
    SCOPE = { channels: p.session.channels, section: p.session.section }
    return { session: p.session, recordings }
  }))
}

/** The session's channels and section, for a read whose fixture signature does not carry them. */
async function scope(): Promise<{ channels: string[]; section: [number, number] }> {
  if (SCOPE) return SCOPE
  const p = await getDiscoverySession()
  RECORDINGS = p.recordings.map(toRecording)
  SCOPE = { channels: p.session.channels, section: p.session.section }
  return SCOPE
}

export const getRuns = (): Promise<Sourced<DiscoveryRun[]>> => live(getDiscoveryRuns().then(rows => rows.map(r => ({
  key: r.key, id: opt(r.id), label: r.label, kind: r.kind as DiscoveryRun['kind'], colour: r.colour,
  glyph: r.glyph as GlyphKind, detail: r.detail, status: r.status as RunStatus,
  template: opt(r.template), stageCount: opt(r.stageCount), version: opt(r.version),
  perChannelMin: opt(r.perChannelMin), job: opt(r.job), progress: r.progress, doneAt: r.doneAt, error: r.error,
  reviewedH: r.reviewedH, runGroupId: opt(r.runGroupId), channelsDone: opt(r.channelsDone), found: opt(r.found),
  seedId: opt(r.seedId), cut: r.cut ?? null, entryId: r.entryId ?? null, scales: r.scales ?? null,
  band: r.band ?? null, bandSet: r.bandSet ?? null, bandIndex: r.bandIndex ?? null,
}))))

export const getTemplates = (): Promise<Sourced<DiscoveryTemplate[]>> => live(getDiscoveryTemplates().then(rows => rows.map(t => ({
  ...t, kind: t.kind === 'seed' ? 'seed' as const : 'template' as const,
  stages: t.stages.map(s => ({ ...s, glyph: s.glyph as GlyphKind })),
}))))

export const getHistory = (): Promise<Sourced<HistoryEntry[]>> => live(getDiscoveryHistory())

/** fixup-z: the project's band list (Settings › Analysis defaults, Q43) — what *Apply template*'s band scope
 *  offers. `nyquistHz` is the session recording's; a band reaching it cannot be filtered. */
export const getBands = (): Promise<Sourced<DiscBandsPayload>> => live(getDiscoveryBands())
/** fixup-ac: the same list with the wavelet levels for another of the wavelet-bands block's wavelets. */
export const getBandsFor = (wavelet: string): Promise<Sourced<DiscBandsPayload>> => live(getDiscoveryBands(wavelet))

/** The exemplars a `rebind` template can be bound to: the bridge's seed list, as dropdown options. */
export const getRebindExemplars = (): Promise<Sourced<{ value: string; label: string }[]>> =>
  live(getDiscoverySeeds().then(p => p.seeds.map(s => ({ value: s.id, label: `${s.title} · ${s.lengthS.toFixed(0)} s` }))))

/* ------------------------------------------------------------------ scope */
export type Refusable<T> = { refused: string } | { refused?: undefined; data: T }
export function getOverview(recording: string, channels: string[]): Promise<Sourced<Refusable<Record<string, number[]>>>> {
  /* A held-out recording is a 423 from the bridge, like every other route that
   * would serve its samples. It is a refusal, not a failure: it becomes the
   * scope strip's red "Held out" callout rather than a red load-failed card,
   * and the reason shown is the server's own. */
  return live(getDiscoveryOverview(recording, channels)
    .then(r => r.refused !== undefined
      ? { refused: r.refused }
      : { data: Object.fromEntries(Object.entries(r.data ?? {}).map(([ch, vals]) => [ch, nums(vals)])) })
    .catch(e => {
      if (e instanceof ApiError && e.status === 423) return { refused: e.message }
      throw e
    }))
}

/* ------------------------------------------------------------------ where each run fires */
export interface FiresRow { run: string; counts: number[]; unfinishedFrom?: number }
export interface FiresChannel { channel: string; reviewedH: number; reviewed: number[]; rows: FiresRow[] }
export interface FiresData { binH: number; firstBin: number; nBins: number; channels: FiresChannel[] }
export function getFires(channels: string[], section: [number, number], runs: DiscoveryRun[]): Promise<Sourced<FiresData>> {
  return live(getDiscoveryFires(channels, section[0], section[1], runs.map(r => r.key)))
}

/* ------------------------------------------------------------------ scoreboard */
/** §7.3: a recall value carries the hours it was computed over, or the server's own words for having
 *  none. Exactly one variant's keys are present — the UI branches on key presence, not on null. */
export type Recall = { value: number; overH: number } | { none: true; note?: string | null } | { tooFewH: number }
export interface ScoreCells { found: number; judged: number; reviewed: number; interesting: number; recall: Recall; nullExpects: number }
export interface ScoreRow extends ScoreCells {
  precision: number | null; xNull: number | null
  nullRun?: boolean; nullDraws?: number | null; nullDrawsMax?: number | null; xNullNote?: string | null
  note?: string | null; precisionNote?: string | null; reviewedH?: number; status?: string | null
  /** fixup-X: Q-D2's two figures, each with its rule; `precision` / `reviewed` / `interesting` are the containment one */
  precisions?: PrecisionFigures
}
export interface ScoreRun { run: string; total: ScoreRow; channels: (ScoreRow & { channel: string })[]; pooledH: number; rule?: { criterion: string; iou: number; onset: number }; reviewedCriterion?: string }
export function getScoreboard(runKeys: string[], channels: string[], section: [number, number]): Promise<Sourced<ScoreRun[]>> {
  return live(getDiscoveryScoreboard(runKeys.filter(k => k !== 'human'), channels, section[0], section[1]))
}

/* ------------------------------------------------------------------ browse detections */
export interface Detection {
  id: string; detectionId?: number; index: number; of: number; run: string; channel: string; atH: number; durationS: number
  depthMv: number | null; score: number | null; priorVerdict: string | null; alsoFoundBy: string[]; nearMiss?: { run: string; d: number }
}
export function getDetections(run: string, channel: string, section: [number, number]): Promise<Sourced<Detection[]>> {
  return live(getDiscoveryDetections(run, channel, section[0], section[1]))
}
export function getDetectionWindow(det: Detection): Promise<Sourced<{ t0H: number; stepS: number; values: number[]; spanS: [number, number] }>> {
  const id = det.detectionId ?? Number(det.id.replace(/^d-/, ''))
  return live(getDiscoveryDetectionWindow(id).then(w => ({ ...w, values: nums(w.values) })))
}

/* ------------------------------------------------------------------ seed search */
/** §7.6's parameter card. The window is locked to the exemplar's native length; `threshold` is the cut,
 *  and it is null until one is chosen or the search has returned a `recommendedCut` — the recommended
 *  cut is computed from the null distribution, so there is none before the null is drawn. */
export interface SeedParams {
  algorithm: string; windowSamples: number; windowS?: number; windowLocked?: boolean
  scaleBank: string; exclusionSamples?: number; exclusionS: number; overlap: string
  specExclusionS?: number; exclusionSettable?: boolean
  threshold: number | null; exclusionNote?: string
  /** fixup-v: the bank Settings › Analysis defaults offers (`seed.scale_bank`), in words */
  bank?: DiscSeedBank
}
export interface SeedInfo {
  id: string; role: string; source: string; title: string; family: string | null; familyLine: string | null
  recording: string; channel: string; startH: number; samples: number; lengthS: number; hash: string; trace: number[]
  /** fixup-f: what the seed's dataset is called, and the file behind the name */
  recordingLabel?: string; recordingFile?: string
  /** fixup-b: 'mV', or null when the seed's recording declares no unit */
  unit?: 'mV' | null
  /** fixup-y: the Library entry a library seed is (null for a span not in the Library), how it got there
   *  (`review` · `annotation` · `event_store`), and the annotation an Explore selection is */
  entryId?: number | null; sourceKind?: string | null; annotationId?: number | null
}
export interface SeedDraft {
  key: string; label: string; seedId: string; source: string; bind: 'carry' | 'rebind'
  params: SeedParams; applied: SeedParams | null; estimateS: number | null
}
/** `seed` is the draft's own seed, which need not be on any page of the picker (fixup-y). */
export interface SeedSetup { draft: SeedDraft; seed: SeedInfo; seeds: SeedInfo[]; recommended: SeedParams }
export interface SeedMatch { id: string; d: number; channel: string; atH: number; judged: boolean; verdict?: string | null; trace: number[]
  /** fixup-v: the factor of the seed's length this match was found at, and its length in samples */
  scale?: number; length?: number }
export interface SeedResults {
  candidates: SeedMatch[]; nullDistances: number[]
  recommendedCut: number | null; cutRule: CutRule | null
  nullDraws: number; nullMethod: string | null; nullSupported: boolean; nullReason: string | null
  exclusionNote?: string; m?: number
  /** fixup-v: the bank searched, and the null drawn per length (distances pooled over channels, draws per channel) */
  scales?: number[] | null; nullByScale?: Record<string, { distances: number[]; draws: number }> | null
}

const toParams = (p: DiscSeedParams): SeedParams => ({
  algorithm: p.algorithm, windowSamples: p.windowSamples, windowS: p.windowS, windowLocked: p.windowLocked,
  scaleBank: p.scaleBank, exclusionSamples: p.exclusionSamples, exclusionS: p.exclusionS, overlap: p.overlap,
  specExclusionS: p.specExclusionS, exclusionSettable: p.exclusionSettable,
  threshold: p.threshold ?? null, exclusionNote: p.exclusion_note, bank: p.bank,
})
const toSeed = (s: { trace: (number | null)[] } & Omit<SeedInfo, 'trace'>): SeedInfo => ({ ...s, trace: nums(s.trace) })

/** `?seed=` or `?entry=` opens that seed and makes it the draft — the link Review's *Seed search in
 *  Discovery →* and Explore's toast follow (fixup-y). */
export const getSeedSetup = (o: { seed?: string; entry?: number } = {}): Promise<Sourced<SeedSetup>> => live(getDiscoverySeedSetupFor(o).then(p => ({
  draft: {
    key: p.draft.key, label: p.draft.label, seedId: p.draft.seedId, source: p.draft.source,
    bind: p.draft.bind === 'rebind' ? 'rebind' as const : 'carry' as const,
    params: toParams(p.draft.params), applied: p.draft.applied ? toParams(p.draft.applied) : null,
    estimateS: p.draft.estimateS,
  },
  seed: toSeed(p.draft.seed),
  seeds: p.seeds.map(toSeed),
  recommended: toParams(p.recommended),
})))

/** The seed picker: one page of one source, filtered, with the total under the filters (fixup-y). */
export interface SeedPage { seeds: SeedInfo[]; total: number; offset: number; limit: number; counts: Record<string, number>; kinds: Record<string, number>; families: string[]; note: string | null }
export const getSeedPage = (q: DiscSeedPageQuery): Promise<Sourced<SeedPage>> =>
  live(getDiscoverySeedPage(q).then(p => ({ ...p, seeds: p.seeds.map(toSeed) })))

/** The draft lives on the session row, so a dragged cut survives a reload (fixup-y). */
export const saveSeedDraft = (seedId: string, params: SeedParams) =>
  putDiscoverySeedDraft({ seedId, params: { ...params, exclusion_note: params.exclusionNote } as Record<string, unknown> })

const POLL_MS = 1500
const GIVE_UP_MS = 4 * 60 * 1000
const sleep = (ms: number) => new Promise(r => window.setTimeout(r, ms))

/** A seeded search over a section is a job (§7.6): POST starts it, the GET form of the same query
 *  answers once it is done. The polling lives here so the page still awaits one promise. A 500 on
 *  either call throws ApiError with the server's message and traceback — never an empty result. */
async function seedResults(q: DiscSeedQuery): Promise<DiscSeedResults> {
  const first = await startDiscoverySeedResults(q)
  if (first.ready) return first
  const giveUpAt = Date.now() + GIVE_UP_MS
  for (;;) {
    await sleep(POLL_MS)
    const r = await (q.scales?.length ? pollDiscoverySeedResultsBanked(q) : pollDiscoverySeedResults(q))
    if (r.ready) return r
    if (Date.now() > giveUpAt) {
      throw new ApiError(504, r.note ?? `the seeded search for ${q.seedId} is still running after ${GIVE_UP_MS / 60000} minutes`, r)
    }
  }
}

export async function getSeedResults(seedId: string, channels: string[], bank?: { scales: number[]; overlap?: string } | null): Promise<Sourced<SeedResults>> {
  const s = await scope()
  const r = await seedResults({ seedId, channels: channels.length ? channels : s.channels, t0: s.section[0], t1: s.section[1],
    ...(bank?.scales.length ? { scales: bank.scales, overlap: bank.overlap ?? 'lowest' } : {}) })
  return {
    source: 'live',
    data: {
      candidates: r.candidates.map(c => ({ id: c.id, d: c.d, channel: c.channel, atH: c.atH, judged: c.judged, verdict: c.verdict, trace: nums(c.trace), scale: c.scale, length: c.length })),
      nullDistances: r.nullDistances ?? [],
      recommendedCut: r.recommendedCut, cutRule: r.cutRule ?? null,
      nullDraws: r.null?.draws ?? 0, nullMethod: r.null?.method ?? null,
      nullSupported: r.null?.supported ?? true, nullReason: r.null?.reason ?? null,
      exclusionNote: r.exclusionNote, m: r.m,
      scales: r.scales ?? null, nullByScale: r.null?.byScale ?? null,
    },
  }
}

export function getSeedProfile(seedId: string, channel: string, view: [number, number], _candidates: SeedMatch[]): Promise<Sourced<{ t0H: number; stepS: number; signal: number[]; distance: number[] }>> {
  return live(getDiscoverySeedProfile(seedId, channel, view[0], view[1]).then(p => ({
    t0H: p.t0H, stepS: p.stepS, signal: nums(p.signal), distance: nums(p.distance),
  })))
}

/* ------------------------------------------------------------------ compare */
export interface RoleCell { index?: string; name: string; short?: string; param: string; signature: string; glyph: GlyphKind
  /** fixup-z: how many stages the chain has in this role; the cell draws the last */
  n_stages?: number }
export interface OverlapRow { channel: string; onlyA: number; both: number; onlyB: number }
export interface CompareSide {
  run: string; label: string; subtitle: string; isSeed: boolean; cells: Record<Role, RoleCell | null>
  precision: number | null; reviewed: number; xNull: number | null; threshold: number | null; found?: number
  /** fixup-t: the surrogate draws per channel this side's × null is over */
  nullDraws?: number | null
  /** fixup-z: a band set as one side — the union of its band runs */
  isSet?: boolean; members?: DiscSetMember[]; template?: string; cellsNote?: string; precisionNote?: string
  /** fixup-X: Q-D2's two figures; `precision` is the containment one */
  precisions?: PrecisionFigures | null
}
/** `otherNearest` is null in the list on purpose: the other side's score at a place is a per-window
 *  computation, and /compare/window returns it as `bScore` when you step to it. `sortedBy` is the
 *  server's own account of the order. */
export interface Disagreement {
  kind: 'only A' | 'only B'; channel: string; atH: number; detection: string
  score: number | null; otherNearest: number | null; otherThreshold: number | null; otherIsSeed: boolean
  index?: number; end?: number
  /** fixup-z: on a band set's side, the bands that fired this region and their run keys */
  bands?: string[] | null; bandRuns?: string[] | null
}
export interface CompareData {
  a: CompareSide; b: CompareSide
  differing: Role[]
  overlap: OverlapRow[]; total: OverlapRow
  disagreements: Disagreement[]
  disagreementsTotal?: number; disagreementsCapped?: boolean; sortedBy?: string
  attributable?: boolean; attributionNote?: string | null
  both: { channel: string; atH: number }[]
  /** fixup-z: the overlap split by verdict (live from `adjudications`), the per-band counts under a band set's
   *  union, and the like-for-like twin a band set should be compared against */
  verdicts?: { onlyA: DiscVerdictSplit | null; both: DiscVerdictSplit; onlyB: DiscVerdictSplit | null }
  perBand?: DiscPerBand[]; perBandSide?: 'A' | 'B' | null; likeForLike?: DiscLikeForLike | null
  /** fixup-X: with human annotations as a side the overlap is paired by the divergence, and its breakdown comes too */
  pairedBy?: 'divergence' | 'reciprocal_iou_onset'; divergence?: DivBreakdown | null
}

const toSide = (s: { cells: Record<string, { glyph: string } & Omit<RoleCell, 'glyph'> | null> } & Omit<CompareSide, 'cells'>): CompareSide => ({
  ...s, cells: s.cells as Record<Role, RoleCell | null>,
})

export function getCompare(a: string, b: string, channels: string[], section: [number, number]): Promise<Sourced<CompareData>> {
  return live(getDiscoveryCompare(a, b, channels, section[0], section[1]).then(d => ({
    a: toSide(d.a), b: toSide(d.b),
    differing: d.differing as Role[],
    overlap: d.overlap, total: d.total,
    disagreements: d.disagreements,
    disagreementsTotal: d.disagreementsTotal, disagreementsCapped: d.disagreementsCapped, sortedBy: d.sortedBy,
    attributable: d.attributable, attributionNote: d.attributionNote,
    both: d.both,
    verdicts: d.verdicts, perBand: d.perBand ?? [], perBandSide: d.perBandSide ?? null, likeForLike: d.likeForLike ?? null,
    pairedBy: d.pairedBy, divergence: d.divergence ?? null,
  })))
}

/** The window a disagreement sits in: clean signal, the firing run's span track, and the other run's own
 *  score against its own threshold. `minAt` is null when the other run produced no score here
 *  (`scoreNote` says why — a chain with no scoring stage decides straight from the signal). */
export interface DisagreementWindow {
  t0H: number; values: number[]; aSpan: [number, number] | null; bSpan: [number, number] | null
  aScore: number[]; bScore: number[]; windowS: number; minAt: number | null
  otherThreshold: number | null; scoreNote: string | null
}
export function getDisagreementWindow(a: string, b: string, d: Disagreement): Promise<Sourced<DisagreementWindow>> {
  return live(getDiscoveryCompareWindow(a, b, d.channel, d.atH, d.kind, 240, d.detection).then(w => ({
    t0H: w.t0H, values: nums(w.values), aSpan: w.aSpan, bSpan: w.bSpan,
    aScore: nums(w.aScore), bScore: nums(w.bScore), windowS: w.windowS, minAt: w.minAt,
    otherThreshold: w.otherThreshold, scoreNote: w.scoreNote,
  })))
}

export function getChannelSignal(channel: string, view: [number, number]): Promise<Sourced<{ t0H: number; stepS: number; values: number[]; unit?: 'mV' | null }>> {
  return live(getDiscoverySignal(channel, view[0], view[1]).then(s => ({ t0H: s.t0H, stepS: s.stepS, values: nums(s.values), unit: s.unit })))
}

/* ------------------------------------------------------------------ compare every stage (3b) */
export type StageBadge = 'identical' | 'differs' | 'A only' | 'B only' | 'absent'
export type StageThumb =
  | { kind: 'trace'; values: number[]; ghost?: number[]; stroke?: string; span?: [number, number]; emptyTrack?: boolean }
  | { kind: 'segments'; values: number[]; cut: number }
  | { kind: 'distance'; values: number[]; threshold: number | null; minIndex: number; minValue: number | null; isSeed: boolean }
  | { kind: 'symbols'; values: number[]; lowRun: [number, number] | null }
  | { kind: 'absent' }
export interface StageCell { role: Role; cell: RoleCell | null; badge: StageBadge; thumb: StageThumb; caption: string; decided: string; absentNote?: string; error?: string }
export interface StagesWindow {
  d: { kind: 'only A' | 'only B'; channel: string; atH: number; detection: string | null }
  index: number; of: number; firstDiffering: Role | null; a: StageCell[]; b: StageCell[]; aSubtitle: string; bSubtitle: string
  windowS?: number; note?: string
}

const toThumb = (t: { kind: string } & Record<string, unknown>): StageThumb => {
  switch (t.kind) {
    case 'trace': return { kind: 'trace', values: nums(t.values as (number | null)[]), ghost: t.ghost ? nums(t.ghost as (number | null)[]) : undefined, stroke: t.stroke as string | undefined, span: opt(t.span as [number, number] | null), emptyTrack: t.emptyTrack as boolean | undefined }
    case 'distance': return { kind: 'distance', values: nums(t.values as (number | null)[]), threshold: (t.threshold as number | null) ?? null, minIndex: (t.minIndex as number) ?? 0, minValue: (t.minValue as number | null) ?? null, isSeed: !!t.isSeed }
    case 'symbols': return { kind: 'symbols', values: (t.values as number[]) ?? [], lowRun: (t.lowRun as [number, number] | null) ?? null }
    case 'segments': return { kind: 'segments', values: nums(t.values as (number | null)[]), cut: t.cut as number }
    default: return { kind: 'absent' }
  }
}
const toCells = (cells: { role: string; cell: unknown; badge: string; thumb: { kind: string }; caption: string; decided: string; absentNote?: string | null; error?: string }[]): StageCell[] =>
  cells.map(c => ({
    role: c.role as Role, cell: c.cell as RoleCell | null, badge: c.badge as StageBadge,
    thumb: toThumb(c.thumb as { kind: string } & Record<string, unknown>),
    caption: c.caption, decided: c.decided, absentNote: opt(c.absentNote), error: c.error,
  }))

export function getStagesWindow(a: string, b: string, d: Disagreement, index: number, of: number): Promise<Sourced<StagesWindow>> {
  return live(getDiscoveryCompareStages(a, b, d.channel, d.atH, d.kind, index, of, 240, d.detection).then(w => ({
    d: w.d, index: w.index, of: w.of, firstDiffering: (w.firstDiffering as Role | null) ?? null,
    a: toCells(w.a), b: toCells(w.b), aSubtitle: w.aSubtitle, bSubtitle: w.bSubtitle,
    windowS: w.windowS, note: w.note,
  })))
}

/* ------------------------------------------------------------------ estimates */
/** What a run would cost over the scope. `plan` is the blocks' own declared estimate (with the local
 *  ceiling and anything uncosted); `preview` is a MEASURED number — the chain run on a sample of one
 *  channel and extrapolated. Both are the server's. */
export const planRun = (body: DiscPlanBody): Promise<Sourced<DiscPlan>> => live(postDiscoveryPlan(body))

/** `/preview` returns `fanout.preview()`'s whole dict; api.ts's `DiscPreview` names only the fields the
 *  apply routes share. These are the measured ones §7.1's tiles print: `measured_s` is a real elapsed
 *  time on a real sample of one channel, and the rest is that time and that hit count scaled to the
 *  scope. Nothing here is modelled, so nothing here needs a fallback. */
export interface MeasuredPreview extends DiscPreview {
  channel: string; sample_hours: number; sample_samples: number
  measured_s: number; per_channel_s: number; spans_in_sample: number; extrapolated_spans: number; scale: number
}
export const previewRun = (body: DiscPlanBody): Promise<Sourced<MeasuredPreview>> =>
  live(postDiscoveryPreview(body) as Promise<MeasuredPreview>)

/** @deprecated fixture-era arithmetic over a hard-coded 174 h session; it invents the denominator and
 *  the per-channel minutes. Use planRun (declared estimate + ceiling) or previewRun (measured). */
export const runEstimateMin = (perChannelMin: number, channels: number, sectionH: number, sessionH = 174) => perChannelMin * channels * (sectionH / sessionH)
/** A measured cost, in the unit that carries it. Sub-second measurements used to
 *  be clamped up to "≈ 1 s" — a five-fold overstatement of a 0.2 s preview, and a
 *  number where the honest answer is that the measurement is below the
 *  resolution the card reports in. */
export const fmtMin = (min: number) => {
  const s = min * 60
  if (s <= 0) return '0 s'
  if (s < 1) return '< 1 s'
  return min < 1 ? `≈ ${Math.round(s)} s` : min < 60 ? `≈ ${Math.round(min)} min` : `≈ ${(min / 60).toFixed(1)} h`
}
