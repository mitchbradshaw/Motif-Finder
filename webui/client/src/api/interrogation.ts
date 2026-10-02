/* Analyse › Interrogation reads. Since stage-3 prompt 01 the families and members are LIVE from the bridge's
 * seed store routes (GET /api/interrogation/families…): the 16 spans of DATA/library_seed/drop_motifs5 with
 * their 410 events, the slope features measured by Working.Detection.drop_motifs.gradients. Every payload the
 * bridge sends says `source: "seed"`; the Library import (Prompt 03) will replace the source with motif tables
 * without changing these shapes. The block specs (feature lists, params) stay the fixture constants the pages
 * were built on: they describe the block, not the data.
 *
 * fixup-e: every per-event measure comes from the core. `GET …/families/{key}/shape` serves
 * `interrogation.event_shape`'s measures of every member (read from `motif_features` by content hash where the
 * Library carries them, else measured on the store's own snippet — never written), and `recovery_s` is the
 * core's `recovery_time_s`: `null` when the event did not half-recover inside the rule's bound, never 0 s. The
 * browser computes NO measurement any more; the three constants (`half_width = 0.84 × duration`, `rise = 0.31 ×`,
 * `isi = 4.2 ×`) that used to be drawn as features are gone. */
import {
  getFamilies, getFamilyMembers, getFamilyShape, getFamilySlope, listRuns,
  type DbRun, type FamilyShape, type SeedFamily, type SeedMember, type ShapeMember, type SlopeMember,
} from '../api'
import { measuredDomain } from '../charts/domain'
import { live, type Sourced } from './seam'
import {
  AGGREGATE_PARAMS, CHAIN_EVENT_SHAPE, CHAIN_SLOPE, CLUSTERING, ESTIMATE, FAMILIES, HELD_OUT_FAMILY, MEMBERS_BY_FAMILY, RULES, SOURCE_SETTINGS,
  TIMELINE_TREND, UPSTREAMS, type ChainBlock, type EventMeasures, type InterrogationFamily, type InterrogationMember, type Upstream, type UpstreamSpec,
} from '../fixtures/interrogation'

export type { InterrogationFamily, InterrogationMember, UpstreamSpec, ChainBlock, Upstream }

/** The reference span (the only seed family with an independent human count). */
export const DEFAULT_FAMILY = 'id001'

const PALETTE = ['#2F6FED', '#8B5CF6', '#0E9AA8', '#D97706', '#DB2777', '#059669', '#7C3AED', '#0284C7', '#B45309', '#BE185D', '#047857', '#6D28D9', '#0369A1', '#92400E', '#9D174D', '#065F46']

function familyFrom(f: SeedFamily, i: number): InterrogationFamily {
  return {
    id: f.id, name: `${f.label} · ${f.morphology ?? '?'}`, colour: PALETTE[i % PALETTE.length],
    members: f.n_members, within: f.n_members, recordings: [f.dataset ?? f.source_file], channels: [f.channel_name ?? `channel index ${f.channel}`],
    adjudicated: 0, threshold: 0, medoid: '', exemplar: undefined,
    promotedFrom: 'seed store drop_motifs5 (PROVENANCE.md: not regenerable)', promotedOn: '2026-08-27', recipe: 'detect5 · autoderived per span',
    crossRecording: false,
  }
}

/** The core's measures of one event, renamed to the page's feature keys. Every `null` means NOT MEASURED. */
function measuresFrom(sh: ShapeMember | undefined): EventMeasures | undefined {
  const f = sh?.features
  if (!sh || !f) return undefined
  return {
    stored: sh.stored,
    amplitude_mV: f.event_amplitude_mv, precursor_mV: f.precursor_height_mv,
    width_s: f.event_width_s, event_duration_s: f.duration_s, fwhm_s: f.fwhm_s, recovery_s: f.recovery_time_s,
    rise_time_s: f.rise_time_s,
    max_slope: f.max_slope_mv_s, onset_slope: f.onset_slope_mv_s, chord_slope: f.chord_slope_mv_s, peakedness: f.peakedness,
    span_ptp_mV: f.span_ptp_mv, polarity: f.polarity,
  }
}

function memberFrom(m: SeedMember, s: SlopeMember | undefined, sh: ShapeMember | undefined, family: string): InterrogationMember {
  const snippet = m.snippet
  const measures = measuresFrom(sh)
  return {
    id: m.event_id, family, recording: m.dataset ?? m.source_file, channel: m.channel_name ?? `channel index ${m.channel}`, onset_h: m.onset_h,
    d: 0, verdict: 'seed', excluded: false, fs_hz: m.fs,
    depth_mV: m.drop_depth_mv, max_slope: s?.max_slope_mv_s ?? 0, peakedness: s?.peakedness ?? 0, duration_s: m.fall_duration_s,
    /* the core's recovery (half the amplitude back from the extremum, bounded); null = not recovered, never 0 */
    recovery_s: measures?.recovery_s ?? null,
    flags: [...(m.is_pure ? [] : ['impure window']), ...(m.trigger === 'fall' ? ['fall-triggered'] : [])],
    snippet: snippet ? { t_s: snippet.t_s, v: snippet.detrended_mv, n: snippet.n } : undefined,
    onset_offset_s: snippet ? (m.onset_idx - m.snippet_start_idx) / m.fs : undefined,
    /* fixup-k: the anatomy figure's marks are the slope route's — offsets into the snippet turned into seconds
       from the onset, and the full-resolution snippet's own heights. No slope row, no marks. */
    anatomy: s ? {
      trough_s: (s.trough_offset - s.onset_offset) / m.fs,
      steepest_s: s.steepest_offset == null ? null : (s.steepest_offset - s.onset_offset) / m.fs,
      onset_mV: s.onset_mv, steepest_mV: s.steepest_mv, trough_mV: s.trough_mv,
      chord_slope: s.mean_slope_mv_s, sample_s: 1 / m.fs,
    } : undefined,
    measures,
  }
}

/* ---------------------------------------------------------------- the window around an event (fixup-e, U11) ----------------------------------------------------------------
 * Source settings › context padding used to be `± k × span`, proportional to a fall that is often seconds long,
 * so a slow precursor to a fast event (the sharkfin's rise, most of what makes the shape recognisable) sat off
 * the left edge of every overlay. The default is now the stored context itself — the store kept minutes either
 * side of each event on purpose — with absolute and proportional alternatives. */
export type PaddingSetting = 'snippet' | '60' | '300' | '1000' | '0.5' | '1' | '2'
export const DEFAULT_PADDING: PaddingSetting = 'snippet'
export const PADDING_OPTIONS: { value: PaddingSetting; label: string; description?: string }[] = [
  { value: 'snippet', label: 'the stored context', description: 'everything the store kept around the event (median ≈ 1 min each side, up to 46 min)' },
  { value: '60', label: '± 60 s' },
  { value: '300', label: '± 300 s' },
  { value: '1000', label: '± 1000 s' },
  { value: '0.5', label: '± 0.5 × fall', description: 'proportional: cannot show a slow precursor to a fast event' },
  { value: '1', label: '± 1 × fall', description: 'proportional' },
  { value: '2', label: '± 2 × fall', description: 'proportional' },
]
export const paddingLabel = (v: string) => PADDING_OPTIONS.find(o => o.value === v)?.label ?? v

/** How far the stored snippet reaches before the onset and after the trough, seconds. */
function snippetReach(m: InterrogationMember): { pre: number; post: number } | undefined {
  const s = m.snippet
  if (!s || m.onset_offset_s === undefined || s.t_s.length < 2) return undefined
  const span = s.t_s[s.t_s.length - 1] - s.t_s[0]
  return { pre: Math.max(0, m.onset_offset_s), post: Math.max(0, span - m.onset_offset_s - m.duration_s) }
}

/** The window drawn around one event under a padding setting: seconds before the onset and after the trough.
 *  Never wider than the stored snippet — a flat tail held past the snippet's end would be an invented sample. */
export function eventWindow(m: InterrogationMember, padding: string): { pre: number; post: number } {
  const reach = snippetReach(m) ?? { pre: 10, post: 24 }
  if (padding === 'snippet') return reach
  const k = Number(padding)
  if (!Number.isFinite(k) || k <= 0) return reach
  const secs = k >= 10 ? k : Math.max(10, k * m.duration_s)          // absolute seconds, or a multiple of the fall
  return { pre: Math.min(secs, reach.pre), post: Math.min(secs, reach.post) }
}

/** The widest window any of these members needs under the setting (for a shared x axis). */
export function windowOver(members: InterrogationMember[], padding: string): { pre: number; post: number } {
  let pre = 0, post = 0
  for (const m of members) {
    const w = eventWindow(m, padding)
    pre = Math.max(pre, w.pre); post = Math.max(post, m.duration_s + w.post)
  }
  return { pre: pre || 10, post: post || 24 }
}

/** The stored snippet as `[seconds from onset, mV]` points inside the window — the samples the store kept,
 *  nothing interpolated and nothing held past the snippet's ends. `undefined` for a member with no snippet. */
export function liveEventPoints(m: InterrogationMember, pre: number, post: number): [number, number][] | undefined {
  const s = m.snippet
  if (!s || m.onset_offset_s === undefined || s.t_s.length < 2) return undefined
  const t0 = s.t_s[0] + m.onset_offset_s
  const hi = m.duration_s + post
  const out: [number, number][] = []
  for (let i = 0; i < s.t_s.length; i++) {
    const t = s.t_s[i] - t0
    if (t >= -pre && t <= hi && Number.isFinite(s.v[i])) out.push([t, s.v[i]])
  }
  return out
}

/** The event's curve at one value per second from `pre` s before the onset to `post` s after the trough,
 *  interpolated from the stored snippet (mV, detrended) for a `MiniTrace`, which takes a plain series. The
 *  window is clipped to the snippet — `undefined` for a fixture member with no snippet. */
export function liveEventCurve(m: InterrogationMember, pre = 10, post = 24): number[] | undefined {
  const s = m.snippet
  if (!s || m.onset_offset_s === undefined || s.t_s.length < 2) return undefined
  const reach = snippetReach(m)!
  const p0 = Math.min(pre, reach.pre), p1 = Math.min(post, reach.post)
  const n = Math.max(2, Math.round(p0 + m.duration_s + p1))
  const out: number[] = []
  let j = 0
  for (let i = 0; i < n; i++) {
    const t = s.t_s[0] + m.onset_offset_s + (i - p0)     // t_s is the channel's absolute axis; the offset is from the snippet start
    while (j < s.t_s.length - 2 && s.t_s[j + 1] < t) j++
    const t0 = s.t_s[j], t1 = s.t_s[j + 1]
    const f = t1 > t0 ? Math.max(0, Math.min(1, (t - t0) / (t1 - t0))) : 0
    out.push(t <= s.t_s[0] ? s.v[0] : t >= s.t_s[s.t_s.length - 1] ? s.v[s.v.length - 1] : s.v[j] + f * (s.v[j + 1] - s.v[j]))
  }
  return out
}

/** THE plot-domain rule (charts/domain.ts::measuredDomain) over the snippets that are drawn — no fourth pad
 *  rule on this page. `undefined` when no member carries a snippet. */
export function liveYDomain(members: InterrogationMember[]): [number, number] | undefined {
  return measuredDomain(...members.map(m => m.snippet?.v ?? [])) ?? undefined
}

/** What the shape route said about the family as a whole: the rules, the counts, the bound. */
export interface ShapeSummary {
  rules: { name: string; rule: string }[]
  counts: FamilyShape['counts']
  recovery: { frac: number; max_mult: number }
  riseTimeFrac: number
  measuredOn: string
}

async function familyAndMembers(familyId: string): Promise<{ family: InterrogationFamily; members: InterrogationMember[]; storeRules: { name: string; rule: string }[]; shape: ShapeSummary }> {
  const fams = await getFamilies()
  const i = fams.families.findIndex(f => f.id === familyId)
  const fam = fams.families[i >= 0 ? i : 0]
  const [mem, slope, shape] = await Promise.all([getFamilyMembers(fam.id), getFamilySlope(fam.id), getFamilyShape(fam.id)])
  const byId = new Map(slope.members.map(s => [s.event_id, s]))
  const shapeById = new Map(shape.members.map(s => [s.event_id, s]))
  return {
    family: familyFrom(fam, i >= 0 ? i : 0),
    members: mem.members.map(m => memberFrom(m, byId.get(m.event_id), shapeById.get(m.event_id), fam.id)),
    storeRules: slope.rules,
    shape: { rules: shape.rules, counts: shape.counts, recovery: shape.recovery, riseTimeFrac: shape.rise_time_frac, measuredOn: shape.measured_on },
  }
}

/** Fixture lookups kept for callers that need a synchronous fallback (none of the pages do). */
export function familyOf(id: string): InterrogationFamily { return FAMILIES.find(f => f.id === id) ?? FAMILIES[0] }
export function membersOf(id: string): InterrogationMember[] { return MEMBERS_BY_FAMILY[id] ?? MEMBERS_BY_FAMILY['F-03'] }

const chainFor = (upstream: Upstream) => (upstream === 'event-shape' ? CHAIN_EVENT_SHAPE : CHAIN_SLOPE)

export interface SourceBlock {
  family: InterrogationFamily
  members: InterrogationMember[]
  clustering: typeof CLUSTERING
  settings: Omit<typeof SOURCE_SETTINGS, 'padding'> & { padding: typeof PADDING_OPTIONS }
  estimate: typeof ESTIMATE
  chain: ChainBlock[]
}
/** The source block (frame interrogation-1): the family, its members and how the run resolves them — live (seed). */
export const getSourceBlock = (familyId: string, upstream: Upstream = 'slope') =>
  live<SourceBlock>(familyAndMembers(familyId).then(({ family, members }) => ({
    family, members, clustering: CLUSTERING, settings: { ...SOURCE_SETTINGS, padding: PADDING_OPTIONS }, estimate: ESTIMATE, chain: chainFor(upstream),
  })))

export interface SourceChoices {
  families: InterrogationFamily[]
  heldOut: InterrogationFamily
  runs: typeof import('../fixtures/interrogation').PRIOR_RUNS
  reviewSelections: typeof import('../fixtures/interrogation').REVIEW_SELECTIONS
  exploreSpans: typeof import('../fixtures/interrogation').EXPLORE_SPANS
  clustering: typeof CLUSTERING
}
function priorRun(r: DbRun): SourceChoices['runs'][number] {
  const last = r.steps[r.steps.length - 1] ?? ''
  const terminal = r.n_detections > 0 || /threshold|detection|matches|motifs|search|spikes|rupture/.test(last) ? 'SpanSet' as const : 'Features' as const
  return { id: String(r.id), label: r.name ?? r.steps.map(s => s.split('.')[1]).join(' → ') ?? `run ${r.id}`, template: last.split('.')[1] ?? last,
           terminal, spans: r.n_detections, when: r.finished_at ?? r.started_at,
           disabledReason: r.status !== 'completed' ? `run ${r.status}` : r.n_detections === 0 ? 'no spans' : undefined }
}

/** The four source kinds the picker offers (§6.2). Families (seed) and prior runs (the runs table) are live;
 *  Review selections and Explore spans have no live source until Prompt 05 and are offered empty. */
export const getSourceChoices = () =>
  live<SourceChoices>(Promise.all([getFamilies(), listRuns(undefined, 60)]).then(([f, runs]) => ({
    families: f.families.map(familyFrom), heldOut: HELD_OUT_FAMILY, runs: runs.db_runs.map(priorRun), reviewSelections: [], exploreSpans: [], clustering: CLUSTERING,
  })))

export interface SlopeBlock {
  family: InterrogationFamily
  members: InterrogationMember[]
  rules: typeof RULES
  chain: ChainBlock[]
  upstream: UpstreamSpec
  /** the rules the store's numbers were measured with, verbatim from the bridge (live only) */
  storeRules?: { name: string; rule: string }[]
  /** the shape block's rules and counts (fixup-e) */
  shape: ShapeSummary
}
/** 01 Resolve spans (the store's slope analysis) or 01 Event shape (interrogation.event_shape) — the two
 *  upstreams read the SAME members but their features are measured by different code (U10 resolved: the
 *  labels now name two blocks that really differ). */
export const getSlopeBlock = (familyId: string, upstream: Upstream = 'slope') =>
  live<SlopeBlock>(familyAndMembers(familyId).then(({ family, members, storeRules, shape }) => ({
    family, members, rules: RULES, chain: chainFor(upstream), upstream: UPSTREAMS[upstream], storeRules, shape,
  })))

export interface AggregateBlock {
  family: InterrogationFamily
  members: InterrogationMember[]
  upstream: UpstreamSpec
  params: typeof AGGREGATE_PARAMS
  trend: typeof TIMELINE_TREND
  chain: ChainBlock[]
  /** the shape block's rules and counts (fixup-e): the page prints the rule behind every measure it draws */
  shape: ShapeSummary
}
/** 02 Aggregate — `Features → views` (§6.8, P7) — live (seed). */
export const getAggregateBlock = (familyId: string, upstream: Upstream = 'slope') =>
  live<AggregateBlock>(familyAndMembers(familyId).then(({ family, members, shape }) => ({
    family, members, upstream: UPSTREAMS[upstream], params: AGGREGATE_PARAMS, trend: TIMELINE_TREND, chain: chainFor(upstream), shape,
  })))
