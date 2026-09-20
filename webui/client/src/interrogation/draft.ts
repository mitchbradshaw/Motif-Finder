/* The in-memory interrogation draft (kit `useDemoState`): member exclusions, source settings and the one
 * pending rule edit. Survives navigation between the three pages, not a reload — brief: writes go to the
 * demo store. Family and upstream live in the URL so every state is deep-linkable. */
import { useDemoState, useQueryState } from '../kit'
import { RULES } from '../fixtures/interrogation'
import { DEFAULT_FAMILY } from '../api/interrogation'

export interface InterrogationDraft {
  /** member ids scoped out of this run (the Library entry is unchanged) */
  excluded: Record<string, string[]>
  settings: { members: string; resolveFrom: string; padding: string; onMissing: string }
  rules: { onset: string; trough: string; sigma: string; steepestWindow: number }
  /** an unapplied steepest-window edit (frame 2c) */
  pendingWindow: number | null
  /** the first stale stage after an edit, or null */
  staleFrom: 'block1' | 'block2' | null
  /** 02 Aggregate's feature wiring, slot → feature key or pair key (h1–h3, tl, p1–p3). Empty means
   *  "as the upstream block declares"; it lives here so a walk to 01 and back keeps the rewiring, and
   *  mirrors into `?wire=` so every rewired state is a deep link too. */
  wiring: Record<string, string>
  saved: boolean
}

export const SEED_DRAFT: InterrogationDraft = {
  excluded: {},
  settings: { members: 'in-scope', resolveFrom: 'original', padding: '0.5', onMissing: 'fail' },
  rules: { onset: 'walk-back', trough: 'run3', sigma: 'mad', steepestWindow: RULES.steepestWindow.recommended },
  pendingWindow: null,
  staleFrom: null,
  wiring: {},
  saved: false,
}

export function useInterrogationDraft() {
  return useDemoState<InterrogationDraft>('analyse.interrogation.draft', () => SEED_DRAFT)
}

export function useFamilyQuery() { return useQueryState('family', DEFAULT_FAMILY) }
export function useUpstreamQuery() { return useQueryState<'slope' | 'spike-shape'>('upstream', 'slope') }

/** Members in scope for the run: not an artifact, not excluded by hand, and inside the `members` setting. */
export function inScopeIds(members: { id: string; verdict: string }[], draft: InterrogationDraft, familyId: string, excludeArtifacts: boolean): Set<string> {
  const out = new Set<string>()
  const hand = draft.excluded[familyId] ?? []
  for (const m of members) {
    if (excludeArtifacts && m.verdict === 'artifact') continue
    if (hand.includes(m.id)) continue
    if (draft.settings.members === 'adjudicated' && m.verdict === 'unadjudicated') continue
    if (draft.settings.members === 'seeds' && m.verdict !== 'seed') continue
    out.add(m.id)
  }
  return out
}

/* `?state=running` / `?state=failed` force the shared run simulation into that state. The sim lives in the
 * kit store, so without this flag a forced run would still look busy on the next page (and in the next
 * smoke state, which navigates by hash without reloading). Every page clears it on arrival. */
let simForced = false
export const markSimForced = (v: boolean) => { simForced = v }
export const wasSimForced = () => simForced
