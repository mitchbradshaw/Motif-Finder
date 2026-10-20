/* night-review: which saved grouping the grouping editor opens on, so the Ward tree is there by default.
 *
 * The editor used to seed from the unit's current grouping, which is the NEWEST one unless another was picked — on
 * the real database g-09, amplitude bins, which builds no tree, so the tree panel was not on the page at all. A
 * grouping editor opened without a basis in the address now opens on the current grouping when it is a tree
 * grouping (Ward on a distance basis), else on the newest tree grouping of the same unit, else on the current one.
 * Pure, no imports: `tests/test_night_review.py` runs it under Node. `newestGrouping` (chrome.tsx) is the near
 * sibling; it does not ask whether a grouping has a tree. */
export interface GroupingLike { id: string; unit: string; basis: string; method?: string | null }

/** The bases whose method draws a tree to cut (GroupingPage's DISTANCE_BASES). */
export const TREE_BASES = ['shape-distance', 'sequence-similarity']

/** Ward on a distance basis: the one method whose fit is a tree (a grouping with no `method` field is Ward, as the
 *  editor reads it). */
export function isTreeGrouping(g: GroupingLike | null | undefined): boolean {
  return !!g && TREE_BASES.includes(g.basis) && (g.method ?? 'ward') === 'ward'
}

const num = (id: string) => { const m = /^g-0*(\d+)$/.exec(String(id ?? '')); return m ? Number(m[1]) : NaN }

export function treeSource<G extends GroupingLike>(all: G[], unit: string, current: G | null | undefined): G | null {
  if (current && current.unit === unit && isTreeGrouping(current)) return current
  let best: G | null = null
  for (const g of all) {
    if (g.unit !== unit || !isTreeGrouping(g)) continue
    if (!best || num(g.id) > num(best.id) || (Number.isNaN(num(best.id)) && !Number.isNaN(num(g.id)))) best = g
  }
  return best ?? (current && current.unit === unit ? current : null)
}
