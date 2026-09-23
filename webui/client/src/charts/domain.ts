/* THE plot-domain rule (fixup-c). Every y domain a trace is drawn on in Review, the Library and Explore is
 * decided here, and nowhere else.
 *
 * It replaces PRD D5 (one shared unnormalised mV domain per page). The researcher's call, 2026-09-23
 * (docs/prompts/fixup/QUESTIONS.md Q-X2.1): **a per-card domain measured from the card's own trace, with the
 * page's shared scale drawn as a reference bar.** D5 existed for a real reason — family peaks span four decades,
 * and one family being micro-volts and another millivolts is evidence of scaling laws — and the reference bar
 * keeps that evidence: the comparison moves from the axis to the bar, and nothing is normalised.
 *
 * Three pieces, and why each is shaped the way it is:
 *
 *  - `measuredDomain` — the extent of every finite sample of every series drawn on the card (the trace AND its
 *    overlays: a medoid drawn over a candidate must not be clipped either), padded by ONE pad. A card's own
 *    domain therefore contains its own trace, always: no motif is clipped in its own thumbnail.
 *  - `padDomain` — the pad, and the floor for a trace that is genuinely flat. The floor only applies to a
 *    zero-width extent (it must not divide by zero or draw a degenerate axis). It is NOT a minimum domain: a
 *    0.005 mV `drop_motifs10` event is drawn at its own size, large and legible, because hiding that population
 *    inside a display rule would bury a research finding (prompt C, "a thing you will see").
 *  - `referenceScale` / `referencePosition` — the page's shared scale, computed ONCE per page from the peak of
 *    every card on it and passed to every card, which draws it as a bar with itself marked on it. The bar is
 *    logarithmic: on a linear bar every sub-mV family of a page whose largest family is 100 mV sits at zero,
 *    which is D5's flat line moved into the bar. On a log bar equal ratios are equal steps, which is also the
 *    axis a scaling law is read on.
 *
 * Pure TypeScript with no imports, so the headless suite can run it under Node
 * (tests/test_webui_plot_domain.py). */

/** The one pad, as a fraction of the extent, on each side. It is the 6 % `makeY` has always used, so Explore's
 *  axes do not move. */
export const DOMAIN_PAD = 0.06

/** A flat trace's half-width: this fraction of its level, or `FLAT_ABS` when its level is zero. Small on
 *  purpose — it exists so a flat line is drawn as a flat line in the middle of a real axis, not to invent a
 *  scale. */
const FLAT_REL = 0.01
const FLAT_ABS = 1e-3

type Series = ReadonlyArray<number | null | undefined>

/** The pad, and the flat floor. Every measured extent in the app goes through this. */
export function padDomain(lo: number, hi: number, pad: number = DOMAIN_PAD): [number, number] {
  if (!(hi > lo)) {
    const c = Number.isFinite(lo) ? lo : Number.isFinite(hi) ? hi : 0
    const half = Math.abs(c) * FLAT_REL || FLAT_ABS
    return [c - half, c + half]
  }
  const m = (hi - lo) * pad
  return [lo - m, hi + m]
}

/** min/max over every finite value of every series; null when there is none. */
export function extentOf(...series: Series[]): [number, number] | null {
  let lo = Infinity, hi = -Infinity
  for (const s of series) {
    if (!s) continue
    for (const v of s) {
      if (v === null || v === undefined || !Number.isFinite(v)) continue
      if (v < lo) lo = v
      if (v > hi) hi = v
    }
  }
  return lo <= hi ? [lo, hi] : null
}

/** THE rule: a card's y domain, measured from everything drawn on it. `null` when nothing finite is drawn —
 *  a caller draws an empty plot then, never a made-up axis. */
export function measuredDomain(...series: Series[]): [number, number] | null {
  const e = extentOf(...series)
  return e ? padDomain(e[0], e[1]) : null
}

/* ---------------------------------------------------------------- amplitude ---------------------------------------------------------------- */

/** The trace with its OWN DC offset (its median) removed. Nothing is scaled: the mV span of the trace stays
 *  exactly what the recording held. Library traces carry baselines down to −3.67 V under millivolt motifs; a
 *  card draws the motif, not the baseline. */
export function centreTrace(values: ReadonlyArray<number>): number[] {
  if (!values || values.length === 0) return values ? [...values] : []
  const s = [...values].filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (!s.length) return [...values]
  const mid = s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2
  return values.map(v => v - mid)
}

/** Largest |v| of an already-centred trace: its peak deviation from its own baseline. */
export function tracePeak(values: ReadonlyArray<number | null | undefined>): number {
  let m = 0
  for (const v of values ?? []) if (v !== null && v !== undefined && Number.isFinite(v) && Math.abs(v) > m) m = Math.abs(v)
  return m
}

/** A raw trace's peak deviation from its own median — the one amplitude every reference bar is drawn from, so
 *  a Review candidate and a Library family are placed on their bars by the same measure. */
export function baselinePeak(values: ReadonlyArray<number | null | undefined>): number {
  const finite = (values ?? []).filter((v): v is number => v !== null && v !== undefined && Number.isFinite(v))
  return tracePeak(centreTrace(finite))
}

/* ---------------------------------------------------------------- reference scale ---------------------------------------------------------------- */

/** The page's shared scale: whole decades spanning every card's peak. */
export interface ReferenceScale {
  /** mV, a power of ten at or below the smallest positive peak */
  lo: number
  /** mV, a power of ten at or above the largest peak, and above `lo` */
  hi: number
  /** the powers of ten from `lo` to `hi`, for the bar's ticks */
  decades: number[]
}

/** The page's shared reference scale, from the peak of every card on it. Computed ONCE per page and passed to
 *  every card. Non-positive and non-finite peaks (a card with nothing drawn, a unit undeclared) are not on it;
 *  `null` when no card has a positive peak. */
export function referenceScale(peaks: ReadonlyArray<number | null | undefined>): ReferenceScale | null {
  const p = (peaks ?? []).filter((v): v is number => v !== null && v !== undefined && Number.isFinite(v) && v > 0)
  if (!p.length) return null
  let a = Math.floor(Math.log10(Math.min(...p)))
  let b = Math.ceil(Math.log10(Math.max(...p)))
  if (b <= a) b = a + 1
  // guard against a peak sitting a rounding error past a decade
  if (Math.pow(10, a) > Math.min(...p)) a -= 1
  if (Math.pow(10, b) < Math.max(...p)) b += 1
  const decades: number[] = []
  for (let k = a; k <= b; k++) decades.push(+Math.pow(10, k).toPrecision(12))
  return { lo: decades[0], hi: decades[decades.length - 1], decades }
}

/** Where a peak sits on the page's shared scale, 0 (bottom) … 1 (top), logarithmically. `null` for a peak that
 *  is not on the scale (≤ 0 or not finite) — drawn as no marker, never as a marker at zero. */
export function referencePosition(scale: ReferenceScale | null, value: number | null | undefined): number | null {
  if (!scale || value === null || value === undefined || !Number.isFinite(value) || value <= 0) return null
  const f = (Math.log10(value) - Math.log10(scale.lo)) / (Math.log10(scale.hi) - Math.log10(scale.lo))
  return Math.max(0, Math.min(1, f))
}
