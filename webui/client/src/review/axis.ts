/* Review's context slice — pure, so `tests/test_webui_review_axis.py` runs it under Node (fixup-g).
 *
 * The defect this replaces (QUESTIONS.md Round 4, U1/U2/U3): the bridge served a decimated envelope's VALUES
 * and discarded its `t`; the client drew point `i` at `t0 + i` seconds while the highlight band was drawn in
 * true seconds, so band and trace were on two different x axes — detection 102's drop was drawn at 0.629 h
 * and is at 0.662 h, inside the band. The padding control sliced envelope POINTS as though they were seconds,
 * which is why ±120 s looked one-sided. Everything here is in ONE coordinate system: absolute seconds. */
import { drawable, nearestIndex, sliceWindow } from '../charts/timeAxis.ts'

export { nearestIndex, drawable }

/** What the slice needs of a served trace (structurally `api/review.ts`'s `TimeTrace`). */
export interface ContextLike { t: ReadonlyArray<number>; v: ReadonlyArray<number | null>; t0_s: number; t1_s: number }
export interface BandLike { start_s: number; end_s: number }

export interface ContextSlice {
  /** The points inside the window, each at its OWN time. `v` is drawable (nulls are NaN). */
  t: number[]; v: number[]
  /** The x extent drawn: the band padded by `pad` on both sides, clipped to what the recording has. */
  t0: number; t1: number
  bandStart: number; bandEnd: number
}

/** The context trace trimmed to `pad` seconds either side of the band, by TIME. A recording that starts inside
 *  the left pad is honestly asymmetric (the window is clipped at 0, the band stays where the event is) rather
 *  than shifted to look even. */
export function sliceContext(ctx: ContextLike, band: BandLike, pad: number): ContextSlice {
  const bandStart = band.start_s, bandEnd = band.end_s
  const p = Math.max(0, pad)
  const t0 = Math.max(ctx.t0_s, bandStart - p)
  const t1 = Math.min(ctx.t1_s, bandEnd + p)
  const w = sliceWindow(ctx.t, ctx.v, t0, t1)
  return { t: w.t, v: drawable(w.v), t0, t1: t1 > t0 ? t1 : t0 + 1, bandStart, bandEnd }
}

/** The pixel budget to ask the bridge for, from the width of the column that will draw the plot: at least
 *  one point per device pixel across the plot, quantised to 64 px so a resize by a few pixels does not
 *  refetch, bounded to what the bridge serves. 0 until the column has been measured — nothing is fetched at
 *  a guessed width. */
export function plotPx(columnWidth: number, dpr = 1, maxWidth = 1400): number {
  if (!(columnWidth > 0)) return 0
  const plot = Math.min(columnWidth, maxWidth) - 60          // card padding and the y-axis gutter
  const px = Math.ceil((plot * (dpr > 0 ? dpr : 1)) / 64) * 64
  return Math.max(320, Math.min(4096, px))
}
