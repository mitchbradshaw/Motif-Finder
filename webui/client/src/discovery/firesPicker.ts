/* site-runs item 2 (2026-10-20): the groups of *Runs drawn: N of M ▾* in "Where each run fires".
 * Pure (no runtime imports) so tests/test_site_runs_scope_link.py runs it under Node.
 *
 * The card used to list every hidden run as an eye-off link under the rows — a wall of ~50 on the researcher's
 * session. The picker groups them instead: templates, seed searches, then each band set folded under its own
 * heading (the band runs of one application). The human row is always drawn and is never offered. */

export interface PickerRun { key: string; label: string; kind: string; template?: string | null; bandSet?: string | null }
export interface PickerGroup<R extends PickerRun> { key: string; label: string; folded: boolean; runs: R[] }

/** The drawable runs in groups, filtered by `query` (case-blind, on the name and the key); empty groups dropped. */
export function pickerGroups<R extends PickerRun>(runs: R[], query: string): PickerGroup<R>[] {
  const q = query.trim().toLowerCase()
  const hit = (r: R) => !q || r.label.toLowerCase().includes(q) || r.key.toLowerCase().includes(q)
  const real = runs.filter(r => r.kind !== 'reference')
  const sets = new Map<string, R[]>()
  for (const r of real) {
    if (!r.bandSet) continue
    const set = sets.get(r.bandSet)
    if (set) set.push(r); else sets.set(r.bandSet, [r])
  }
  const groups: PickerGroup<R>[] = [
    { key: 'templates', label: 'templates', folded: false, runs: real.filter(r => !r.bandSet && r.kind !== 'seed').filter(hit) },
    { key: 'seeds', label: 'seed searches', folded: false, runs: real.filter(r => !r.bandSet && r.kind === 'seed').filter(hit) },
    ...[...sets.entries()].map(([set, ms]) => ({
      key: `band:${set}`, label: `${ms[0].template ?? ms[0].label} · ${ms.length} band${ms.length === 1 ? '' : 's'}`, folded: true, runs: ms.filter(hit),
    })),
  ]
  return groups.filter(g => g.runs.length > 0)
}
