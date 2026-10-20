/* discovery.mapOrder — how Discovery › Map orders and hides its rows and columns (site-map, 2026-10-20).
 *
 * Pure, no imports (tests/test_webui_site_map_order.py runs it under Node). It orders keys; it computes no number
 * the page shows. `arrange` is the one entry point the page uses: the shown keys in the chosen order with the pinned
 * key (the human row) first, then the hidden keys in their listed order — hidden rows sink to the bottom and hidden
 * columns to the right (the researcher, 2026-10-20), and a key brought back lands where the current order puts it.
 *
 * `cluster` is average-linkage hierarchical clustering on correlation distance (1 − Pearson r) of the values the
 * page passes — each row's (or column's) shaded rates over the SHOWN cells — in dendrogram leaf order. Naive O(n³),
 * fine for the map's sizes (≤ ~100 rows or columns per group). No near-sibling exists in the client: the library's
 * grouping tree clusters on the server, over shapes, not over these cells. */

export type SortMode = 'listed' | 'name' | 'count' | 'cluster'

export interface OrderItem {
  key: string
  label: string
  /** the values the order reads (the shaded rate per shown cell; null = nothing to shade, read as 0) */
  values: (number | null)[]
  /** detections over the shown cells, for `count` */
  count: number
}

/** 1 − Pearson r. A flat vector has no shape: 0 against another flat one, 1 against anything else. */
export function correlationDistance(a: number[], b: number[]): number {
  const n = Math.min(a.length, b.length)
  if (n === 0) return 1
  let ma = 0, mb = 0
  for (let i = 0; i < n; i++) { ma += a[i]; mb += b[i] }
  ma /= n; mb /= n
  let sab = 0, saa = 0, sbb = 0
  for (let i = 0; i < n; i++) { const x = a[i] - ma, y = b[i] - mb; sab += x * y; saa += x * x; sbb += y * y }
  if (saa <= 1e-24 && sbb <= 1e-24) return 0
  if (saa <= 1e-24 || sbb <= 1e-24) return 1
  const r = sab / Math.sqrt(saa * sbb)
  return 1 - Math.max(-1, Math.min(1, r))
}

/** The leaf order of an average-linkage dendrogram over `vectors`. Deterministic: the closest pair merges first
 *  (ties to the lowest indices), and a merged cluster keeps the one holding the lower original index on the left. */
export function clusterOrder(vectors: number[][]): number[] {
  const n = vectors.length
  if (n <= 2) return vectors.map((_, i) => i)
  const d: number[][] = vectors.map((a, i) => vectors.map((b, j) => (i === j ? 0 : correlationDistance(a, b))))
  type Cl = { leaves: number[]; first: number }
  let clusters: Cl[] = vectors.map((_, i) => ({ leaves: [i], first: i }))
  const dist = (p: Cl, q: Cl) => {
    let s = 0
    for (const i of p.leaves) for (const j of q.leaves) s += d[i][j]
    return s / (p.leaves.length * q.leaves.length)
  }
  while (clusters.length > 1) {
    let bi = 0, bj = 1, best = Infinity
    for (let i = 0; i < clusters.length; i++) {
      for (let j = i + 1; j < clusters.length; j++) {
        const v = dist(clusters[i], clusters[j])
        if (v < best - 1e-12) { best = v; bi = i; bj = j }
      }
    }
    const [p, q] = clusters[bi].first <= clusters[bj].first ? [clusters[bi], clusters[bj]] : [clusters[bj], clusters[bi]]
    const merged: Cl = { leaves: [...p.leaves, ...q.leaves], first: Math.min(p.first, q.first) }
    clusters = clusters.filter((_, k) => k !== bi && k !== bj)
    clusters.splice(Math.min(bi, clusters.length), 0, merged)
  }
  return clusters[0].leaves
}

const byName = (a: OrderItem, b: OrderItem) => a.label.localeCompare(b.label, undefined, { numeric: true, sensitivity: 'base' })

/** `{shown, hidden}` keys: shown in `mode`'s order with `pinned` first, hidden after in their listed order. */
export function arrange(items: OrderItem[], mode: SortMode, hidden: ReadonlySet<string>, pinned?: string): { shown: string[]; hidden: string[] } {
  const hid = items.filter(it => hidden.has(it.key)).map(it => it.key)
  const pin = items.filter(it => it.key === pinned && !hidden.has(it.key))
  const rest = items.filter(it => it.key !== pinned && !hidden.has(it.key))
  let ordered: OrderItem[]
  if (mode === 'name') ordered = [...rest].sort(byName)
  else if (mode === 'count') ordered = rest.map((it, i) => ({ it, i })).sort((a, b) => b.it.count - a.it.count || a.i - b.i).map(x => x.it)
  else if (mode === 'cluster') ordered = clusterOrder(rest.map(it => it.values.map(v => v ?? 0))).map(i => rest[i])
  else ordered = rest
  return { shown: [...pin, ...ordered].map(it => it.key), hidden: hid }
}

/** The URL's comma lists (`hide=`, `hidecols=`). */
export const splitKeys = (csv: string): string[] => csv ? csv.split(',').filter(Boolean) : []

/** `csv` with `key` added, or removed when present; null when the list empties (the key leaves the URL). */
export function toggleKey(csv: string, key: string): string | null {
  const list = splitKeys(csv)
  const next = list.includes(key) ? list.filter(k => k !== key) : [...list, key]
  return next.length ? next.join(',') : null
}
