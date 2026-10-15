/* The y geometry of the Cross-channel stack, split out of CrossChannelPage because the one decision
   that governs whether a trace is visible at all deserves to be readable on its own.

   The problem it solves, measured against the bridge on M2_aug_concat_fs1 (fs 1 Hz, the 640 s window
   at 3.33 h): the sixteen channels sit at DC baselines from −0.10 V to −3.79 V, while each channel's
   own signal *inside* the window spans 1–30 mV. One absolute mV domain across the stack is
   therefore ~3.9 V tall, and a typical channel's entire waveform occupies 0.07 px of a 48 px row.
   Every trace draws as a flat line — which is exactly what the page did before this module existed.
   (This paragraph first recorded those numbers 1000x too small — "−0.10 mV", "0.001–0.03 mV" — because
   the bridge printed stored volts as mV until fixup-b. The ratios, and so every conclusion here, stand.)

   The governing rule is docs/PIPELINE_PRD.md:523: figures draw *detrended* millivolts, unnormalised,
   on a shared y-scale so relative depth is real. The harm it names, restated in the decision log at
   :604, is *amplitude* normalisation — "normalisation of amplitude destroys the evidence of scaling
   laws for depolarisation events". Subtracting a per-row constant is additive, not multiplicative, so
   it leaves every amplitude relationship intact: with one shared gain, a 32 mV row still draws 19×
   the depth of a 1.7 mV row. Note which way that cuts — an *absolute* domain is the mode that
   departs from :523, because the per-electrode DC offset it renders as vertical position is precisely
   what "detrended" removes. The old comment on this page ("§3: never normalised per row") is how the
   opposite reading survived review.

     'absolute'    one absolute mV domain across every row. Inter-electrode DC offset shows as vertical
                   position — real information, and the only place a reader sees it as geometry — but
                   it cannot show the waveforms, so it is not the default.
     'centred'     DEFAULT. One *gain* (mV per row) across every row, each row drawn about the middle
                   of its own range. Only the DC offset moves; no value and no span changes. The gain is
                   the widest drawn row's own range (fixup-AQ, crossModel.ts::centredStack): centring on
                   the MEDIAN, as this mode first did, needs a half-scale of the largest median-to-extreme
                   distance, which for an asymmetric transient or a drift is nearly the whole range — the
                   gain doubled and every row used a quarter of its height ("20.74 mV per row" over rows
                   of 5–10 mV, 2026-10-13). The median is still drawn, as the dashed baseline line with its
                   value (library/chrome.tsx::centreTrace's choice of a baseline), just not used to centre.
     'per-channel' each row autoscaled to its own extent. This is the amplitude normalisation :523
                   forbids; it is kept reachable because a 1.7 mV channel is otherwise unreadable,
                   and every row that is drawn this way says so on the row, not just in the card head.

   No mode can clip. 'absolute' covers every row by construction; 'per-channel' fits each row exactly;
   'centred' takes its gain from the widest drawn row's range and centres each row on the middle of its
   own, so the row that set it just touches its bounds and every other row sits inside them. Keep that property
   — polylinePath has no clamp and `.panel{overflow:hidden}` would cut a trace flat with nothing said,
   which is the harm library/FamilyPage.tsx records ("a real 17.6 µV drop rendered as a dead-flat line
   and nothing said so"). A fit-to-data gain is also the PRD's own adjudication of this trade-off
   (:527, stories 52/53): the inter-quartile fence is legitimate but belongs behind an option, because
   for a drop motif the transient it clips is the evidence. */
import { makeY, type XScale } from '../charts/scale'
import { centredStack, rowStat } from './crossModel'
import { mvDigits } from './util'

export { rowStat }

export type YMode = 'absolute' | 'centred' | 'per-channel'
export const Y_MODES: YMode[] = ['absolute', 'centred', 'per-channel']
export const isYMode = (s: string): s is YMode => (Y_MODES as string[]).includes(s)

export interface RowGeom {
  /** the row's own absolute extent inside the window, or null when it carries no finite sample */
  extent: [number, number] | null
  /** the mV value at the row's drawing origin: the middle of its own range in 'centred', the row/stack mid otherwise */
  centre: number
  /** the row's measured baseline (its median), drawn as a dashed line with its value — 'centred' only */
  baseline: number | null
  /** decimals that keep *this* row's own extent legible — a 1.7 mV row needs more than a 30 mV one */
  places: number
  /** mV → px within one row panel */
  y: XScale
}

export interface StackGeom {
  mode: YMode
  rows: RowGeom[]
  /** the drawn height of one row in mV — one number in 'absolute' and 'centred', null in 'per-channel'. In
   *  'centred' it is the widest drawn row's own range, exactly (the drawing pads it by charts/domain's pad) */
  fullScaleMv: number | null
  /** 'centred': the index of the row whose range set the gain */
  setBy: number
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
  // decimals come from the row's own extent, never from the stack's: taking them from a 3.6 V stack
  // span prints a 1.7 mV row's two bounds as the same number, in the mode added to make it readable
  const placesOf = (s: { extent: [number, number] } | null) => mvDigits(0, s ? s.extent[1] - s.extent[0] : Math.abs(hi - lo))

  if (mode === 'per-channel') {
    return {
      mode,
      rows: stats.map(s => {
        const [a, b] = s?.extent ?? [lo, hi]
        return { extent: s?.extent ?? null, centre: (a + b) / 2, baseline: null, places: placesOf(s), y: makeY(a, b, height) }
      }),
      fullScaleMv: null,
      sharedDomain: null,
      setBy: -1,
    }
  }

  if (mode === 'absolute') {
    const y = makeY(lo, hi, height)
    return {
      mode,
      rows: stats.map(s => ({ extent: s?.extent ?? null, centre: mid, baseline: null, places: placesOf(s), y })),
      fullScaleMv: span(y),
      sharedDomain: [lo, hi],
      setBy: -1,
    }
  }

  // 'centred': one gain for the stack — the widest drawn row's range — each row about the middle of its own
  // range (crossModel.ts::centredStack). A stack with nothing finite falls back to the read's own domain.
  const c = centredStack(stats)
  const gain = c && c.gainMv > 0 ? c.gainMv : Math.max(Math.abs(hi - lo), 1e-4)
  const rows = stats.map((s, i) => {
    const r = c?.rows[i]
    const centre = r ? r.centre : mid
    return { extent: s?.extent ?? null, centre, baseline: s ? s.median : null, places: placesOf(s), y: makeY(centre - gain / 2, centre + gain / 2, height) }
  })
  return { mode, rows, fullScaleMv: gain, sharedDomain: null, setBy: c?.setBy ?? -1 }
}

export const fmtMvSpan = (mv: number) => `${mv.toFixed(mvDigits(0, mv))} mV`
export const fmtMvAt = (v: number, places: number) => `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(places)}`

/** The card-header readout. Every mode states its own gain — and every mode that is *not* normalised
 *  says so, because saying it of only one implies the others are. */
export function scaleNote(g: StackGeom, setByName?: string): string {
  if (g.mode === 'absolute' && g.sharedDomain) {
    const [a, b] = g.sharedDomain
    const p = mvDigits(0, Math.abs(b - a))
    return `absolute mV · ${fmtMvAt(a, p)} – ${fmtMvAt(b, p)} mV across the stack · unnormalised`
  }
  if (g.mode === 'centred') {
    // with one drawn row the gain IS that row's own range, which is per-channel autoscale under another
    // name. The gain is also taken from the drawn rows, so a selection change rescales the stack; both
    // facts belong in the readout rather than in a reader's assumptions.
    const live = g.rows.filter(r => r.extent).length
    const gainMv = g.fullScaleMv ?? 0
    return `shared gain · ${fmtMvSpan(gainMv)} per row = the widest drawn row's range · each row centred on its own range · unnormalised`
      + (live < 2 ? ' · one row, so the gain is its own' : ` · ${live} rows drawn${setByName ? `, set by ${setByName}` : ''}`)
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
  centred: 'one mV-per-row for every row (the widest row fills its height), each drawn about the middle of its own range; amplitude still comparable',
  'per-channel': 'each row autoscaled to itself; normalised, so amplitude no longer compares between rows',
}
