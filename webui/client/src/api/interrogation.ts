/* Analyse › Interrogation reads. Every read returns Sourced<T> through `demo(FIXTURE)`; a later ticket
 * swaps a body for a bridge call without touching a component (see api/seam.ts). */
import { demo } from './seam'
import {
  AGGREGATE_PARAMS, CHAIN_SLOPE, CHAIN_SPIKE, CLUSTERING, ESTIMATE, EXPLORE_SPANS, FAMILIES, HELD_OUT_FAMILY,
  MEMBERS_BY_FAMILY, PRIOR_RUNS, REVIEW_SELECTIONS, RULES, SOURCE_SETTINGS, TIMELINE_TREND, UPSTREAMS,
  type ChainBlock, type InterrogationFamily, type InterrogationMember, type UpstreamSpec,
} from '../fixtures/interrogation'

export type { InterrogationFamily, InterrogationMember, UpstreamSpec, ChainBlock }

export const DEFAULT_FAMILY = 'F-03'

export function familyOf(id: string): InterrogationFamily {
  return FAMILIES.find(f => f.id === id) ?? FAMILIES[0]
}
export function membersOf(id: string): InterrogationMember[] {
  return MEMBERS_BY_FAMILY[id] ?? MEMBERS_BY_FAMILY[DEFAULT_FAMILY]
}

export interface SourceBlock {
  family: InterrogationFamily
  members: InterrogationMember[]
  clustering: typeof CLUSTERING
  settings: typeof SOURCE_SETTINGS
  estimate: typeof ESTIMATE
  chain: ChainBlock[]
}

/** The source block (frame interrogation-1): the family, its members and how the run resolves them. */
export const getSourceBlock = (familyId: string, upstream: 'slope' | 'spike-shape' = 'slope') =>
  demo<SourceBlock>({
    family: familyOf(familyId),
    members: membersOf(familyId),
    clustering: CLUSTERING,
    settings: SOURCE_SETTINGS,
    estimate: ESTIMATE,
    chain: upstream === 'spike-shape' ? CHAIN_SPIKE : CHAIN_SLOPE,
  })

export interface SourceChoices {
  families: InterrogationFamily[]
  heldOut: InterrogationFamily
  runs: typeof PRIOR_RUNS
  reviewSelections: typeof REVIEW_SELECTIONS
  exploreSpans: typeof EXPLORE_SPANS
  clustering: typeof CLUSTERING
}
/** The four source kinds the picker offers (§6.2: Library family · prior run · Review selection · Explore spans). */
export const getSourceChoices = () =>
  demo<SourceChoices>({ families: FAMILIES, heldOut: HELD_OUT_FAMILY, runs: PRIOR_RUNS, reviewSelections: REVIEW_SELECTIONS, exploreSpans: EXPLORE_SPANS, clustering: CLUSTERING })

export interface SlopeBlock {
  family: InterrogationFamily
  members: InterrogationMember[]
  rules: typeof RULES
  chain: ChainBlock[]
  upstream: UpstreamSpec
}
/** 01 Resolve spans / 01 Spike shape — `SpanSet → SpanSet + Features` (§6.8). */
export const getSlopeBlock = (familyId: string, upstream: 'slope' | 'spike-shape' = 'slope') =>
  demo<SlopeBlock>({
    family: familyOf(familyId),
    members: membersOf(familyId),
    rules: RULES,
    chain: upstream === 'spike-shape' ? CHAIN_SPIKE : CHAIN_SLOPE,
    upstream: UPSTREAMS[upstream],
  })

export interface AggregateBlock {
  family: InterrogationFamily
  members: InterrogationMember[]
  upstream: UpstreamSpec
  params: typeof AGGREGATE_PARAMS
  trend: typeof TIMELINE_TREND
  chain: ChainBlock[]
}
/** 02 Aggregate — `Features → views` (§6.8, P7: generic, wired from whatever the upstream block declares). */
export const getAggregateBlock = (familyId: string, upstream: 'slope' | 'spike-shape' = 'slope') =>
  demo<AggregateBlock>({
    family: familyOf(familyId),
    members: membersOf(familyId),
    upstream: UPSTREAMS[upstream],
    params: AGGREGATE_PARAMS,
    trend: TIMELINE_TREND,
    chain: upstream === 'spike-shape' ? CHAIN_SPIKE : CHAIN_SLOPE,
  })
