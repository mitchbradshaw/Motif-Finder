/* library-family-actions: the rose reference LINE every rose draws — the median steepest slope over the
 * human-accepted Library motifs (interesting or seed), with its n, from `GET /api/library/rose-reference?unit=motifs`.
 * The bridge computes it and caches it by the adjudication fingerprint, so a verdict moves it on the next read; the
 * browser only places it. A failed read is not a blank: the rose prints the error where the line's label would be
 * (and `useSourced` logs it). */
import { getRoseReferenceLine } from '../api'
import { live, useSourced } from '../api/seam'
import type { RoseReferenceLine } from '../kit'

export function useRoseReferenceLine(): RoseReferenceLine | null {
  const r = useSourced(() => live(getRoseReferenceLine('motifs')), [])
  if (r.error) return { median_slope: null, n: 0, computed_from: '', error: r.error.message }
  return r.data ?? null
}
