/* The in-memory training draft (kit `useDemoState`): the name, the source in hand, and one
 * `{ applied, pending }` parameter set per block. Survives navigation between the six pages, not a
 * reload — brief: writes go to the demo store. The source lives in the URL (`?source=human-windows`)
 * so every state is deep-linkable. */
import { useDemoState, useQueryState } from '../kit'
import { CLUSTER, ENCODE, ENCODINGS, FEATURE_GROUPS, MATRIX, MODEL_STAGES, NAME, WINDOWS } from '../fixtures/training'
import type { SourceKind } from '../api/training'

/** A block's parameters: what the last run used, and an unapplied edit on top (the frames' amber state). */
export interface Editable<T> { applied: T; pending: T | null }
const edit = <T,>(applied: T): Editable<T> => ({ applied, pending: null })

export interface WindowParams {
  from: string; length_min: number; stride_min: number; gap_min: number
  split: string; blocks: string; seed: string; splitKind: 'blocked' | 'random'
}
export interface MatrixParams { groups: Record<string, boolean>; normalise: string; clip: string }
export interface ClusterParams { criterion: string; linkage: string; distance: string; cut: number; merged: string[] }
export interface EncodeParams { included: Record<string, boolean>; encoder: string; size: string; paa: string; epsilon: number; fusion: string; writeTo: string }
export interface ModelParams { stages: Record<string, boolean>; labelsFrom: string }

export interface TrainingDraft {
  name: string
  saved: boolean
  windows: Editable<WindowParams>
  matrix: Editable<MatrixParams>
  cluster: Editable<ClusterParams>
  encode: Editable<EncodeParams>
  model: Editable<ModelParams>
  /** first stale stage number (1-based), or null */
  staleFrom: number | null
  /** windows queued to Review this session (P13) */
  queuedToReview: number
  /** a stage deleted on the chain page makes the junction invalid until it is put back */
  deletedStage: string | null
  /** the choose-k criterion has been locked before looking (B4) */
  criterionLocked: boolean
  savedWindowSets: string[]
  savedGroupings: string[]
}

export const SEED_DRAFT: TrainingDraft = {
  name: NAME,
  saved: false,
  windows: edit({
    from: 'sliding signal span', length_min: WINDOWS.params.length_min, stride_min: WINDOWS.params.stride_min,
    gap_min: WINDOWS.params.gap_min, split: WINDOWS.params.split, blocks: WINDOWS.params.blocks,
    seed: WINDOWS.params.seed, splitKind: 'blocked',
  }),
  matrix: edit({
    groups: Object.fromEntries(FEATURE_GROUPS.map(g => [g.id, g.included])),
    normalise: MATRIX.normalise, clip: MATRIX.clip,
  }),
  cluster: edit({ criterion: CLUSTER.params.criterion, linkage: CLUSTER.params.linkage, distance: CLUSTER.params.distance, cut: CLUSTER.params.cut, merged: [] }),
  encode: edit({
    included: Object.fromEntries(ENCODINGS.map(e => [e.id, e.included])),
    encoder: ENCODE.params.encoder, size: ENCODE.params.size, paa: ENCODE.params.paa,
    epsilon: ENCODE.params.epsilon, fusion: ENCODE.params.fusion, writeTo: ENCODE.params.writeTo,
  }),
  model: edit({ stages: Object.fromEntries(MODEL_STAGES.map(s => [s.id, s.ticked])), labelsFrom: 'cluster' }),
  staleFrom: 4,
  queuedToReview: 0,
  deletedStage: null,
  criterionLocked: false,
  savedWindowSets: [],
  savedGroupings: [],
}

export function useTrainingDraft() {
  return useDemoState<TrainingDraft>('analyse.training.draft', () => SEED_DRAFT)
}

export function useSourceQuery() { return useQueryState<SourceKind>('source', 'signal') }

/** The values on screen: the pending edit if there is one, otherwise what the last run used. */
export const live = <T,>(e: Editable<T>): T => e.pending ?? e.applied

/** Does this block hold an unapplied change? (`pending` is cleared, not just equal, when reverted.) */
export const isPending = <T,>(e: Editable<T>): boolean => e.pending != null && JSON.stringify(e.pending) !== JSON.stringify(e.applied)

/* `?state=running` / `?state=failed` force the shared run simulation into that state. The sim lives in the
 * kit store, so without this flag a forced run would still look busy on the next page (and in the next
 * smoke state, which navigates by hash without reloading). Every page clears it on arrival. */
let simForced = false
export const markSimForced = (v: boolean) => { simForced = v }
export const wasSimForced = () => simForced
