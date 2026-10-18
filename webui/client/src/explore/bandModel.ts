/* span-plot (2026-10-18): what the Signal page's span bands ARE, in one dependency-free module — the six kinds a
   reader can switch, their colours, how an annotation's verdict picks its kind, which live detections draw, and
   where a band lands on the x axis. No imports, so it can be checked under plain `node` (type stripping) without
   the bundler: see the span-plot report for the check that a detection at 1000 s draws at x(1000) on [900, 1100]. */

/** The kinds the legend switches. An annotation draws as its verdict (interesting and not-interesting were one
 *  green 'annotated' kind until 2026-10-18); a detection is `detected`. */
export type ToggleKind = 'detected' | 'interesting' | 'not_interesting' | 'unsure' | 'artifact' | 'seed'
/** A drawn band: a toggle kind, or the selected motif (amber) whatever its kind. */
export type SpanKind = ToggleKind | 'selected'

export interface BandKindDef { key: ToggleKind; label: string; cap: string; fill: string; tip: string }

/** Legend order, colours (caps) and tinted fills. Colours come from the theme tokens (theme.css). */
export const BAND_KINDS: BandKindDef[] = [
  { key: 'detected', label: 'detected', cap: 'var(--blue)', fill: 'var(--band-detected)', tip: 'a machine detection from a checked run; colour follows the run when ‘colour by run’ is on' },
  { key: 'interesting', label: 'interesting', cap: 'var(--green)', fill: 'var(--band-annotated)', tip: 'a human span judged interesting' },
  { key: 'not_interesting', label: 'not interesting', cap: 'var(--purple)', fill: 'rgba(142, 92, 247, 0.14)', tip: 'a human span judged not interesting' },
  { key: 'unsure', label: 'unsure', cap: 'var(--muted-2)', fill: 'rgba(107, 114, 128, 0.14)', tip: 'a human span marked unsure (or a verdict this page does not know)' },
  { key: 'artifact', label: 'artifact', cap: 'var(--red)', fill: 'var(--band-artifact)', tip: 'a human span marked artifact (not the organism)' },
  { key: 'seed', label: 'seed', cap: 'var(--teal)', fill: 'rgba(13, 148, 136, 0.14)', tip: 'a span taken for Review as a seed (an example to search for)' },
]
export const TOGGLE_KEYS: ToggleKind[] = BAND_KINDS.map(k => k.key)

/** The kind an annotation draws as: its verdict, or `unsure` for one this page does not know. */
export function annotationKind(verdict: string | null | undefined): ToggleKind {
  return verdict === 'interesting' || verdict === 'not_interesting' || verdict === 'artifact' || verdict === 'seed' || verdict === 'unsure' ? verdict : 'unsure'
}

export type Toggles = Record<ToggleKind, boolean>
export const ALL_ON: Toggles = { detected: true, interesting: true, not_interesting: true, unsure: true, artifact: true, seed: true }

/** Read remembered toggles (a JSON object of booleans); anything missing or malformed is on. */
export function parseToggles(raw: string | null): Toggles {
  const out: Toggles = { ...ALL_ON }
  if (!raw) return out
  try {
    const v = JSON.parse(raw) as Record<string, unknown>
    for (const k of TOGGLE_KEYS) if (typeof v?.[k] === 'boolean') out[k] = v[k] as boolean
  } catch { /* a bad value is no value: everything on */ }
  return out
}

/** Live detections that draw: those from a checked run (`#<run_id>` in `visible`) — the picker's filter applies
 *  on every channel (it was skipped whenever the live read stood in for the old demo canon). With no runs listed
 *  yet there is nothing to filter by, and every detection draws. */
export function visibleDetections<D extends { run_id: number }>(dets: D[], visible: Set<string>, nRuns: number): D[] {
  return nRuns ? dets.filter(d => visible.has(`#${d.run_id}`)) : dets
}

/** Where a band of [start_s, end_s] lands on a plot of `width` px showing [a, b] seconds: left edge and width
 *  (never under `minPx`). The same linear map as `charts/scale.ts::makeX` with no padding. */
export function bandGeometry(start_s: number, end_s: number, a: number, b: number, width: number, minPx = 2): { x: number; w: number } {
  const k = width / (b - a)
  const x0 = (start_s - a) * k, x1 = (end_s - a) * k
  return { x: x0, w: Math.max(minPx, x1 - x0) }
}

/** Seconds typed into an edge field: a number, or the reason it is not one the view can take. */
export function parseEdge(text: string, side: 'left' | 'right', other: number, dur: number, minSpan: number): number | string {
  const t = text.trim().replace(/s$/i, '').trim().replace('−', '-')
  if (!/^-?\d+(\.\d*)?$|^-?\.\d+$/.test(t)) return 'type seconds, e.g. 1234.567'
  const v = Number(t)
  if (!Number.isFinite(v)) return 'type seconds, e.g. 1234.567'
  if (side === 'left') {
    if (v < 0) return 'the left edge cannot be before 0 s'
    if (v > other - minSpan) return `the left edge must be at least ${minSpan} s before the right (${other.toFixed(3)} s)`
  } else {
    if (v > dur) return `the right edge cannot be past the channel's end (${dur.toFixed(3)} s)`
    if (v < other + minSpan) return `the right edge must be at least ${minSpan} s after the left (${other.toFixed(3)} s)`
  }
  return v
}

/** One arrow-key step of an edge field: by the last digit typed (3 decimals → 0.001, none → 1). */
export function stepEdge(text: string, dir: 1 | -1): string | null {
  const t = text.trim()
  if (!/^-?\d+(\.\d*)?$/.test(t)) return null
  const dec = t.includes('.') ? t.split('.')[1].length : 0
  const v = Number(t) + dir * Math.pow(10, -dec)
  return v.toFixed(dec)
}
