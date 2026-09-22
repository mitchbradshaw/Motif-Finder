/* The y geometry of the Cross-channel stack, split out of CrossChannelPage because the one decision
   that governs whether a trace is visible at all deserves to be readable on its own.

   The problem it solves, measured against the bridge on M2_aug_concat_fs1 (fs 1 Hz, the 640 s window
   at 3.33 h): the sixteen channels sit at DC baselines from −0.10 mV to −3.79 mV, while each channel's
   own signal *inside* the window spans 0.001–0.03 mV. One absolute mV domain across the stack is
   therefore ~3.9 mV tall, and a typical channel's entire waveform occupies 0.07 px of a 48 px row.
   Every trace draws as a flat line — which is exactly what the page did before this module existed.

   The governing rule is docs/PIPELINE_PRD.md:523: figures draw *detrended* millivolts, unnormalised,
   on a shared y-scale so relative depth is real. The harm it names, restated in the decision log at
   :604, is *amplitude* normalisation — "normalisation of amplitude destroys the evidence of scaling
   laws for depolarisation events". Subtracting a per-row constant is additive, not multiplicative, so
   it leaves every amplitude relationship intact: with one shared gain, a 0.032 mV row still draws 19×
   the depth of a 0.0017 mV row. Note which way that cuts — an *absolute* domain is the mode that
   departs from :523, because the per-electrode DC offset it renders as vertical position is precisely
   what "detrended" removes. The old comment on this page ("§3: never normalised per row") is how the
   opposite reading survived review.

     'absolute'    one absolute mV domain across every row. Inter-electrode DC offset shows as vertical
                   position — real information, and the only place a reader sees it as geometry — but
                   it cannot show the waveforms, so it is not the default.
     'centred'     DEFAULT. One *gain* (mV per pixel) across every row, each row drawn about its own
                   median. Only the DC offset moves; no value and no span changes. Library already gives
                   family members this treatment ("centred on its own baseline, not normalised",
                   library/FamilyPage.tsx; the median is what library/chrome.tsx::centreTrace uses, and
                   for an asymmetric drop transient a min/max midpoint is *not* a baseline).
     'per-channel' each row autoscaled to its own extent. This is the amplitude normalisation :523
                   forbids; it is kept reachable because a 0.0017 mV channel is otherwise unreadable,
                   and every row that is drawn this way says so on the row, not just in the card head.

   No mode can clip. 'absolute' covers every row by construction; 'per-channel' fits each row exactly;
   'centred' takes its half-scale from the largest median-to-extreme distance over the drawn rows, so
   the row that set it just touches its bounds and every other row sits inside them. Keep that property
   — polylinePath has no clamp and `.panel{overflow:hidden}` would cut a trace flat with nothing said,
   which is the harm library/FamilyPage.tsx records ("a real 17.6 µV drop rendered as a dead-flat line
   and nothing said so"). A fit-to-data gain is also the PRD's own adjudication of this trade-off
   (:527, stories 52/53): the inter-quartile fence is legitimate but belongs behind an option, because
   for a drop motif the transient it clips is the evidence. */
import { makeY, type XScale } from '../charts/scale'
import { mvDigits } from './util'

export type YMode = 'absolute' | 'centred' | 'per-channel'
export const Y_MODES: YMode[] = ['absolute', 'centred', 'per-channel']
export const isYMode = (s: string): s is YMode => (Y_MODES as string[]).includes(s)

/** A row's own extent and median over the finite samples of its envelope, or null when it has none. */
export function rowStat(v: (number | null)[]): { extent: [number, number]; median: number } | null {
  const f: number[] = []
  for (const x of v) if (x !== null && x !== undefined && !Number.isNaN(x)) f.push(x)
  if (!f.length) return null
  f.sort((a, b) => a - b)
  const n = f.length
  return { extent: [f[0], f[n - 1]], median: n % 2 ? f[(n - 1) / 2] : (f[n / 2 - 1] + f[n / 2]) / 2 }
}

export interface RowGeom {
  /** the row's own absolute extent inside the window, or null when it carries no finite sample */
  extent: [number, number] | null
  /** the mV value at the row's drawing origin: its own median in 'centred', the row/stack mid otherwise */
  centre: number
  /** true when `centre` is this row's measured baseline and may be stated as one */
  centreIsBaseline: boolean
  /** decimals that keep *this* row's own extent legible — a 0.0017 mV row needs more than a 0.03 mV one */
  places: number
  /** mV → px within one row panel */
  y: XScale
}

export interface StackGeom {
  mode: YMode
  rows: RowGeom[]
  /** the drawn height of one row in mV — one number in 'absolute' and 'centred', null in 'per-channel' */
  fullScaleMv: number | null
  /** the absolute domain every row shares, or null when the rows do not share one */
  sharedDomain: [number, number] | null
}

/** One y scale per row for `mode`. `fallback` is used for a row with nothing finite in it, and for a
 *  stack where no row has anything finite (a window of all-NaN buckets still has to draw something). */
export function stackGeom(traces: { v: (number | null)[] }[], mode: YMode, height: number, fallback: [number, number]): StackGeom {
  const stats = traces.map(tr => rowStat(tr.v))
  const live = stats.filter((s): s is NonNullable<typeof s> => s !== null)
  const lo = live.length ? Math.min(...live.map(s => s.extent[0])) : fallback[0]
  const hi = live.length ? Math.max(...live.map(s => s.extent[1])) : fallback[1]
  const mid = (lo + hi) / 2
  const span = (y: XScale) => { const [a, b] = y.domain(); return Math.abs(b - a) }
  // decimals come from the row's own extent, never from the stack's: taking them from a 3.6 mV stack
  // span prints a 0.0017 mV row's two bounds as the same number, in the mode added to make it readable
  const placesOf = (s: { extent: [number, number] } | null) => mvDigits(0, s ? s.extent[1] - s.extent[0] : Math.abs(hi - lo))

  if (mode === 'per-channel') {
    return {
      mode,
      rows: stats.map(s => {
        const [a, b] = s?.extent ?? [lo, hi]
        return { extent: s?.extent ?? null, centre: (a + b) / 2, centreIsBaseline: false, places: placesOf(s), y: makeY(a, b, height) }
      }),
      fullScaleMv: null,
      sharedDomain: null,
    }
  }

  if (mode === 'absolute') {
    const y = makeY(lo, hi, height)
    return {
      mode,
      rows: stats.map(s => ({ extent: s?.extent ?? null, centre: mid, centreIsBaseline: false, places: placesOf(s), y })),
      fullScaleMv: span(y),
      sharedDomain: [lo, hi],
    }
  }

  // 'centred': one gain for the stack, each row about its own median. The half-scale is the largest
  // median-to-extreme distance over the drawn rows, which is what keeps every row inside its bounds —
  // a median is not the midpoint of an asymmetric transient, so half the widest *span* would clip.
  const reach = live.length ? Math.max(...live.map(s => Math.max(s.median - s.extent[0], s.extent[1] - s.median))) : Math.abs(hi - lo) / 2
  const half = reach > 0 ? reach : Math.max(Math.abs(hi - lo) / 2, 1e-4)
  const rows = stats.map(s => {
    const centre = s ? s.median : mid
    return { extent: s?.extent ?? null, centre, centreIsBaseline: !!s, places: placesOf(s), y: makeY(centre - half, centre + half, height) }
  })
  return { mode, rows, fullScaleMv: rows.length ? span(rows[0].y) : half * 2, sharedDomain: null }
}

export const fmtMvSpan = (mv: number) => `${mv.toFixed(mvDigits(0, mv))} mV`
export const fmtMvAt = (v: number, places: number) => `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(places)}`

/** The card-header readout. Every mode states its own gain — and every mode that is *not* normalised
 *  says so, because saying it of only one implies the others are. */
export function scaleNote(g: StackGeom): string {
  if (g.mode === 'absolute' && g.sharedDomain) {
    const [a, b] = g.sharedDomain
    const p = mvDigits(0, Math.abs(b - a))
    return `absolute mV · ${fmtMvAt(a, p)} – ${fmtMvAt(b, p)} mV across the stack · unnormalised`
  }
  if (g.mode === 'centred') {
    // with one drawn row the gain IS that row's own reach, which is per-channel autoscale under another
    // name. The gain is also taken from the drawn rows, so a selection change rescales the stack; both
    // facts belong in the readout rather than in a reader's assumptions.
    const live = g.rows.filter(r => r.extent).length
    return `shared gain · ${fmtMvSpan(g.fullScaleMv ?? 0)} per row · each row on its own baseline · unnormalised`
      + (live < 2 ? ' · one row, so the gain is its own' : ` · set by the ${live} drawn rows`)
  }
  return 'per-channel autoscale · amplitude NOT comparable between rows'
}

export const Y_MODE_LABEL: Record<YMode, string> = {
  absolute: 'absolute mV',
  centred: 'shared gain, centred',
  'per-channel': 'per channel',
}

/* Named for the transform, not the outcome. 'absolute' is deliberately not called "shared" — the specs
   reserve that word for the gain, which 'centred' shares too — nor "as recorded", which is already the
   align Seg's left option on the same control row. */
export const Y_MODE_NOTE: Record<YMode, string> = {
  absolute: 'one absolute mV domain across the stack; the DC offset between electrodes shows as vertical position',
  centred: 'one mV-per-pixel for every row, each drawn about its own median; amplitude still comparable',
  'per-channel': 'each row autoscaled to itself; normalised, so amplitude no longer compares between rows',
}
