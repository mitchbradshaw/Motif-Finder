/* Analyse › Interrogation reads. Since stage-3 prompt 01 the families and members are LIVE from the bridge's
 * seed store routes (GET /api/interrogation/families…): the 16 spans of DATA/library_seed/drop_motifs5 with
 * their 410 events, the slope features measured by Working.Detection.drop_motifs.gradients. Every payload the
 * bridge sends says `source: "seed"`; the Library import (Prompt 03) will replace the source with motif tables
 * without changing these shapes. The block specs (rules, feature lists, params) stay the fixture constants the
 * pages were built on: they describe the block, not the data. */
import { getFamilies, getFamilyMembers, getFamilySlope, listRuns, type DbRun, type SeedFamily, type SeedMember, type SlopeMember } from '../api'
import { live, type Sourced } from './seam'
import {
  AGGREGATE_PARAMS, CHAIN_SLOPE, CHAIN_SPIKE, CLUSTERING, ESTIMATE, FAMILIES, HELD_OUT_FAMILY, MEMBERS_BY_FAMILY, RULES, SOURCE_SETTINGS,
  TIMELINE_TREND, UPSTREAMS, type ChainBlock, type InterrogationFamily, type InterrogationMember, type UpstreamSpec,
} from '../fixtures/interrogation'

export type { InterrogationFamily, InterrogationMember, UpstreamSpec, ChainBlock }

/** The reference span (the only seed family with an independent human count). */
export const DEFAULT_FAMILY = 'id001'

const PALETTE = ['#2F6FED', '#8B5CF6', '#0E9AA8', '#D97706', '#DB2777', '#059669', '#7C3AED', '#0284C7', '#B45309', '#BE185D', '#047857', '#6D28D9', '#0369A1', '#92400E', '#9D174D', '#065F46']

function familyFrom(f: SeedFamily, i: number): InterrogationFamily {
  return {
    id: f.id, name: `${f.label} · ${f.morphology ?? '?'}`, colour: PALETTE[i % PALETTE.length],
    members: f.n_members, within: f.n_members, recordings: [f.source_file.replace(/\.mat$/, '')], channels: [`CH${f.channel}`],
    adjudicated: 0, threshold: 0, medoid: '', exemplar: undefined,
    promotedFrom: 'seed store drop_motifs5 (PROVENANCE.md: not regenerable)', promotedOn: '2026-08-27', recipe: 'detect5 · autoderived per span',
    crossRecording: false,
  }
}

function memberFrom(m: SeedMember, s: SlopeMember | undefined, family: string): InterrogationMember {
  const snippet = m.snippet
  // recovery: from the trough back to within 10 % of the drop depth of the onset level, on the stored snippet
  let recovery = 0
  if (snippet && snippet.t_s.length) {
    const n = snippet.t_s.length, sn = m.snippet_end_idx - m.snippet_start_idx
    const k = (i: number) => Math.min(n - 1, Math.round((i / Math.max(1, sn)) * (n - 1)))
    const ko = k(m.onset_idx - m.snippet_start_idx), kt = k(m.trough_idx - m.snippet_start_idx)
    const level = snippet.detrended_mv[ko] - 0.1 * m.drop_depth_mv
    let kr = kt
    while (kr < n && snippet.detrended_mv[kr] < level) kr++
    recovery = kr < n ? snippet.t_s[kr] - snippet.t_s[kt] : 0
  }
  return {
    id: m.event_id, family, recording: m.source_file.replace(/\.mat$/, ''), channel: `CH${m.channel}`, onset_h: m.onset_h,
    d: 0, verdict: 'seed', excluded: false, fs_hz: m.fs,
    depth_mV: m.drop_depth_mv, max_slope: s?.max_slope_mv_s ?? 0, peakedness: s?.peakedness ?? 0, duration_s: m.fall_duration_s, recovery_s: recovery,
    flags: [...(m.is_pure ? [] : ['impure window']), ...(m.trigger === 'fall' ? ['fall-triggered'] : [])],
    snippet: snippet ? { t_s: snippet.t_s, v: snippet.detrended_mv } : undefined,
    onset_offset_s: snippet ? (m.onset_idx - m.snippet_start_idx) / m.fs : undefined,
  }
}

/** The event's curve at one value per second from `pre` s before the onset to `post` s after the trough,
 *  interpolated from the stored snippet (mV, detrended) — `undefined` for a fixture member with no snippet. */
export function liveEventCurve(m: InterrogationMember, pre = 10, post = 24): number[] | undefined {
  const s = m.snippet
  if (!s || m.onset_offset_s === undefined || s.t_s.length < 2) return undefined
  const n = pre + Math.round(m.duration_s) + post
  const out: number[] = []
  let j = 0
  for (let i = 0; i < n; i++) {
    const t = m.onset_offset_s + (i - pre)
    while (j < s.t_s.length - 2 && s.t_s[j + 1] < t) j++
    const t0 = s.t_s[j], t1 = s.t_s[j + 1]
    const f = t1 > t0 ? Math.max(0, Math.min(1, (t - t0) / (t1 - t0))) : 0
    // outside the stored snippet hold the edge value: a NaN would make d3's scale return undefined
    out.push(t <= s.t_s[0] ? s.v[0] : t >= s.t_s[s.t_s.length - 1] ? s.v[s.v.length - 1] : s.v[j] + f * (s.v[j + 1] - s.v[j]))
  }
  return out
}

/** A y domain from the live snippets (padded 5 %), or `undefined` when no member carries one. */
export function liveYDomain(members: InterrogationMember[]): [number, number] | undefined {
  let lo = Infinity, hi = -Infinity
  for (const m of members) for (const v of m.snippet?.v ?? []) { if (v < lo) lo = v; if (v > hi) hi = v }
  if (!(lo < hi)) return undefined
  const pad = 0.05 * (hi - lo)
  return [lo - pad, hi + pad]
}

async function familyAndMembers(familyId: string): Promise<{ family: InterrogationFamily; members: InterrogationMember[]; storeRules: { name: string; rule: string }[] }> {
  const fams = await getFamilies()
  const i = fams.families.findIndex(f => f.id === familyId)
  const fam = fams.families[i >= 0 ? i : 0]
  const [mem, slope] = await Promise.all([getFamilyMembers(fam.id), getFamilySlope(fam.id)])
  const byId = new Map(slope.members.map(s => [s.event_id, s]))
  return { family: familyFrom(fam, i >= 0 ? i : 0), members: mem.members.map(m => memberFrom(m, byId.get(m.event_id), fam.id)), storeRules: slope.rules }
}

/** Fixture lookups kept for callers that need a synchronous fallback (none of the pages do). */
export function familyOf(id: string): InterrogationFamily { return FAMILIES.find(f => f.id === id) ?? FAMILIES[0] }
export function membersOf(id: string): InterrogationMember[] { return MEMBERS_BY_FAMILY[id] ?? MEMBERS_BY_FAMILY['F-03'] }

export interface SourceBlock {
  family: InterrogationFamily
  members: InterrogationMember[]
  clustering: typeof CLUSTERING
  settings: typeof SOURCE_SETTINGS
  estimate: typeof ESTIMATE
  chain: ChainBlock[]
}
/** The source block (frame interrogation-1): the family, its members and how the run resolves them — live (seed). */
export const getSourceBlock = (familyId: string, upstream: 'slope' | 'spike-shape' = 'slope') =>
  live<SourceBlock>(familyAndMembers(familyId).then(({ family, members }) => ({
    family, members, clustering: CLUSTERING, settings: SOURCE_SETTINGS, estimate: ESTIMATE, chain: upstream === 'spike-shape' ? CHAIN_SPIKE : CHAIN_SLOPE,
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
}
/** 01 Resolve spans / 01 Spike shape — `SpanSet → SpanSet + Features` (§6.8) — live (seed). */
export const getSlopeBlock = (familyId: string, upstream: 'slope' | 'spike-shape' = 'slope') =>
  live<SlopeBlock>(familyAndMembers(familyId).then(({ family, members, storeRules }) => ({
    family, members, rules: RULES, chain: upstream === 'spike-shape' ? CHAIN_SPIKE : CHAIN_SLOPE, upstream: UPSTREAMS[upstream], storeRules,
  })))

export interface AggregateBlock {
  family: InterrogationFamily
  members: InterrogationMember[]
  upstream: UpstreamSpec
  params: typeof AGGREGATE_PARAMS
  trend: typeof TIMELINE_TREND
  chain: ChainBlock[]
}
/** 02 Aggregate — `Features → views` (§6.8, P7) — live (seed). */
export const getAggregateBlock = (familyId: string, upstream: 'slope' | 'spike-shape' = 'slope') =>
  live<AggregateBlock>(familyAndMembers(familyId).then(({ family, members }) => ({
    family, members, upstream: UPSTREAMS[upstream], params: AGGREGATE_PARAMS, trend: TIMELINE_TREND, chain: upstream === 'spike-shape' ? CHAIN_SPIKE : CHAIN_SLOPE,
  })))
