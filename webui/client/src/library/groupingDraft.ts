/* tq-grouping (2026-10-25): the Edit-grouping modal's draft — what the form holds, how a saved grouping seeds it, and
 * how it becomes the engine's `params`. Split out of GroupingPage.tsx, with `isTreeGrouping` and `openingGrouping`
 * (which replace `treeSource.ts`) and the one newest-grouping rule (`groupingNum`, `newestGrouping`, re-exported by
 * chrome.tsx).
 * Pure: type-only imports, so `tests/test_tq_grouping.py` runs it under Node. */
import type { BasisKind, FeatureBin, Grouping, Unit } from '../api/library'
import type { LibGroupingMethod } from '../api'

export type BinMode = 'quantiles' | 'log' | 'fixed'
export interface Draft {
  unit: Unit; basis: BasisKind
  bins: BinMode; nBins: number; range: [number, number] | null; edges: string
  cut: number; nearest: number
  tagMode: 'first' | 'each'; provBy: 'recording' | 'run' | 'spike_train'; clustering: string
  omitSmall: boolean; minMembers: number
  /** w2-f: the registered method for a distance basis (`ward`, `kshape`, `hdbscan`), and each non-Ward method's
   *  own parameter values, keyed by method — so switching away and back keeps what was typed */
  method: string; mparams: Record<string, Record<string, unknown>>
}
/** Spec 9.10's two defaults, and the two the core's own methods declare (`ward.DEFAULT_CUT`, `DEFAULT_OMIT_D`). */
export const BASE: Omit<Draft, 'unit' | 'basis'> = {
  bins: 'quantiles', nBins: 6, range: null, edges: '',
  cut: 0.42, nearest: 0.5, tagMode: 'first', provBy: 'recording', clustering: '',
  omitSmall: true, minMembers: 10, method: 'ward', mparams: {},
}

/** Which registered method serves which basis (`Working/library/grouping/methods/*.applies_to`). */
export const METHOD_FOR: Record<BasisKind, string> = {
  'shape-distance': 'ward', 'sequence-similarity': 'ward',
  amplitude: 'feature_bins', timescale: 'feature_bins', 'frequency-content': 'feature_bins', polarity: 'feature_bins',
  tag: 'labels', provenance: 'labels', custom: 'labels',
}
/** The three bin methods, spelled the way `bases.BIN_METHODS` spells them. */
const BIN_METHOD: Record<BinMode, string> = { quantiles: 'quantiles', log: 'log-spaced', fixed: 'fixed edges' }
/** The bases whose methods read a distance matrix — and so the only ones whose Ward fit is a tree to cut. */
export const DISTANCE_BASES: string[] = ['shape-distance', 'sequence-similarity']
/** The method a draft runs: the picked one on a distance basis, the basis's only method elsewhere. */
export const methodOf = (d: Pick<Draft, 'basis' | 'method'>): string => (DISTANCE_BASES.includes(d.basis) ? d.method || 'ward' : METHOD_FOR[d.basis])
/** The params the section-4 controls own (one rule for every method), so the method's own panel does not repeat them. */
export const SHARED_PARAMS = new Set(['min_group'])

/** night-review: Ward on a distance basis, the one method whose fit is a tree (a grouping with no `method` is Ward,
 *  as the editor reads it). The editor opens on such a grouping by default, and draws its tree. */
export function isTreeGrouping(g: Pick<Grouping, 'basis' | 'method'> | null | undefined): boolean {
  return !!g && DISTANCE_BASES.includes(g.basis) && (g.method ?? 'ward') === 'ward'
}

/** The number in a `g-NN` id, or NaN. The bridge emits `g-` plus a zero-padded integer, but a saved grouping
 *  named anything else must not poison a Math.max into NaN. (Moved here from chrome.tsx, which re-exports it.) */
export const groupingNum = (id: string) => { const m = /^g-0*(\d+)$/.exec(String(id ?? '')); return m ? Number(m[1]) : NaN }
/** The newest grouping of one unit, by id. `undefined` when the library holds none of that unit. */
export function newestGrouping<G extends Pick<Grouping, 'id' | 'unit'>>(all: G[], unit: string): G | undefined {
  const mine = all.filter(g => g.unit === unit)
  if (!mine.length) return undefined
  return mine.reduce((a, b) => (groupingNum(b.id) > groupingNum(a.id) ? b : a))
}
/** night-review: the grouping the editor opens on, so the Ward tree is there by default — the current grouping of
 *  this unit when it has a tree, else the newest tree grouping of the unit, else the current one of this unit. */
export function openingGrouping<G extends Pick<Grouping, 'id' | 'unit' | 'basis' | 'method'>>(all: G[], unit: string, current: G | null | undefined): G | undefined {
  const cur = current?.unit === unit ? current : undefined
  return isTreeGrouping(cur) ? cur : newestGrouping(all.filter(isTreeGrouping), unit) ?? cur
}

/** `params_json` as the bridge renders it for the chip: `"cut 0.6 · min_group 10 · omit_d 0.5"`. That string is
 *  the only carrier the grouping payload has for `min_group`/`omit_d`, so the editor reads it back. A token it
 *  cannot parse is skipped rather than defaulted. */
export function parseParamsText(text: string | null | undefined, strKeys: readonly string[] = []): Record<string, number> & { str?: Record<string, string> } {
  const out: Record<string, number> & { str?: Record<string, string> } = {}
  const str: Record<string, string> = {}
  for (const part of String(text ?? '').split('·')) {
    const m = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s+(-?[0-9.]+(?:e-?[0-9]+)?)\s*$/.exec(part)
    if (m && Number.isFinite(Number(m[2]))) { out[m[1]] = Number(m[2]); continue }
    // fix 1 (critic 7): a method's declared `str` params (HDBSCAN's selection and distance) are read too — they
    // used to reseed silently at their defaults, "from g-NN" opening on somebody else's settings
    const t = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s+(\S+)\s*$/.exec(part)
    if (t && strKeys.includes(t[1])) str[t[1]] = t[2]
  }
  if (Object.keys(str).length) out.str = str
  return out
}
/** The draft the Edit-grouping modal should open on when it announces "from g-NN": g-NN's OWN parameters.
 *  It used to open on the hard-coded `BASE` — cut 0.42 under the subtitle "from g-02", whose cut is 0.60, so
 *  pressing Compute and apply without touching the slider regrouped the whole catalogue at somebody else's
 *  settings while the researcher believed they had re-run the current one. A parameter the grouping does not
 *  record keeps its `BASE` default. */
export function seedFromGrouping(g: Grouping | undefined, methods: Record<string, LibGroupingMethod[]> = {}): Partial<Draft> {
  if (!g) return {}
  const spec = (methods[g.basis] ?? []).find(m => m.name === g.method)
  const strKeys = Object.entries(spec?.params ?? {}).filter(([, ps]) => ps.type === 'str' || ps.type === 'choice').map(([k]) => k)
  const p = parseParamsText(g.params, strKeys)
  const cut = typeof g.cut === 'number' ? g.cut : p.cut
  const seed: Partial<Draft> = { basis: g.basis }
  if (g.method && g.method !== 'ward' && DISTANCE_BASES.includes(g.basis)) {
    seed.method = g.method
    const own: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(p)) if (k !== 'min_group' && k !== 'str') own[k] = v
    Object.assign(own, p.str ?? {})
    seed.mparams = { [g.method]: own }
  }
  if (Number.isFinite(cut) && cut > 0) seed.cut = cut
  if (Number.isFinite(p.omit_d) && p.omit_d > 0) seed.nearest = p.omit_d
  if (Number.isFinite(p.min_group) && p.min_group >= 1) { seed.minMembers = p.min_group; seed.omitSmall = true }
  if (Number.isFinite(p.n_bins) && p.n_bins >= 2) seed.nBins = p.n_bins
  return seed
}

/** A distribution's own span, first bin's lower edge to last bin's upper — the only honest source for a feature's
 *  range. (Not `charts/domain.ts::extentOf`, which is the min/max over samples; this reads bin edges.) */
export function binExtent(dist: FeatureBin[] | undefined): [number, number] | null {
  if (!dist || !dist.length) return null
  const lo = dist[0].lo, hi = dist[dist.length - 1].hi
  return Number.isFinite(lo) && Number.isFinite(hi) && hi > lo ? [lo, hi] : null
}

export function parseEdges(s: string): { edges: number[]; error: string | null } {
  const parts = s.split(',').map(x => x.trim()).filter(Boolean)
  const nums = parts.map(Number)
  if (parts.some(p => !Number.isFinite(Number(p)))) return { edges: [], error: `not a number: ${parts.find(p => !Number.isFinite(Number(p)))}` }
  if (nums.length < 3) return { edges: nums, error: 'at least 3 edges (2 bins)' }
  for (let i = 1; i < nums.length; i++) if (nums[i] <= nums[i - 1]) return { edges: nums, error: `edges must increase: ${nums[i]} ≤ ${nums[i - 1]} at position ${i + 1}` }
  return { edges: nums, error: null }
}

/** Form validation only — whether the draft is a question the core can be asked. It says nothing about the
 *  answer; the answer comes from the job. */
export function validate(d: Draft, extent: [number, number] | null): { field: string; message: string } | null {
  const feature = !DISTANCE_BASES.includes(d.basis) && METHOD_FOR[d.basis] === 'feature_bins'
  if (feature) {
    if (d.bins === 'fixed') { const e = parseEdges(d.edges).error; if (e) return { field: 'edges', message: e } }
    else {
      if (!Number.isInteger(d.nBins) || d.nBins < 2 || d.nBins > 20) return { field: 'number of bins', message: '2 to 20 bins' }
      const [lo, hi] = d.range ?? extent ?? [0, 0]
      if (!(lo < hi)) return { field: 'range', message: 'the lower edge must be below the upper edge' }
      if (d.bins === 'log' && lo <= 0) return { field: 'range', message: 'log-spaced bins need a range above 0' }
      if (extent && (lo < extent[0] * 0.999 || hi > extent[1] * 1.001)) {
        return { field: 'range', message: `outside the measured range: ${extent[0].toPrecision(3)}–${extent[1].toPrecision(3)}` }
      }
    }
  }
  if (DISTANCE_BASES.includes(d.basis) && methodOf(d) === 'ward' && !(d.cut > 0)) return { field: 'cut', message: 'the cut must be above 0' }
  if (d.omitSmall && (!Number.isInteger(d.minMembers) || d.minMembers < 1 || d.minMembers > 1000)) return { field: 'minimum members', message: 'whole number from 1 to 1000' }
  return null
}

/** The draft as the engine's `params` dict. Only keys a registered method actually declares are sent — an
 *  invented key would still land in the recipe hash and make two identical groupings look different. */
export function paramsFor(d: Draft, extent: [number, number] | null, spec?: LibGroupingMethod): Record<string, unknown> {
  const shared: Record<string, unknown> = { min_group: d.minMembers, omit_small: d.omitSmall }
  const method = methodOf(d)
  if (method === 'ward') return { ...shared, cut: d.cut, omit_d: d.nearest }
  if (DISTANCE_BASES.includes(d.basis)) {
    // w2-f: a registered non-Ward method — its declared params at the value typed, else its own default. HDBSCAN's
    // `epsilon` is one of them: the tree cut (`d.cut`) is Ward's and never reaches another method.
    const own = d.mparams[method] ?? {}
    const out: Record<string, unknown> = { ...shared }
    for (const [k, ps] of Object.entries(spec?.params ?? {})) if (!SHARED_PARAMS.has(k)) out[k] = k in own ? own[k] : ps.default
    if (!spec) Object.assign(out, own)
    return out
  }
  if (method === 'feature_bins') {
    const range = d.bins === 'fixed' ? parseEdges(d.edges).edges : (d.range ?? extent ?? null)
    return { ...shared, feature: d.basis, bin_method: BIN_METHOD[d.bins], count: d.nBins, range }
  }
  return { ...shared, provenance_by: d.provBy, tag_mode: d.tagMode }
}
