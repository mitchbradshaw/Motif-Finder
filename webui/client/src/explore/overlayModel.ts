/* The drawing decisions of Explore › Cross-channel's overlay (and one of its stack) that a test should be able to
   run (site-x, 2026-10-20), kept free of imports so Node can execute this file as it stands
   (tests/test_webui_site_x_cross.py, as tests/test_webui_cross_page.py does for crossModel.ts).

   Both come from the researcher's screenshot of CO_fs2.mat CH1, window #1, overlay, four channels:

   overlayGains — the overlay draws every channel at ONE gain, set so the median channel's range spans GAIN_LANES
   lanes. CH2 drifted 35 mV while the other three spanned 0.15–0.25 mV, so at that gain CH2 was 145 lanes tall: the
   block clipped everything but the moment it crossed its own mean, a near-vertical stroke. A channel whose range
   cannot fit the BLOCK at the shared gain is now drawn at its own gain (its range spans GAIN_LANES lanes, like the
   median's) and the overlay prints the factor beside its name — normalised, and saying so, which is the stack's
   'per-channel' rule applied to the one row that needs it.

   mergeDetectionMarks — detections that span the whole window (CNN windows of 128–7860 s, 235 of them on CH2) were
   each drawn as a solid bar in the trace's colour, which read as "a straight line at the top of every band". They
   are merged into one mark per run of overlap, clipped to the window, carrying how many detections it stands for
   and whether it runs past either edge.

   drawnRowPx — the stack's 'centred' gain is the widest row's range; on the same window CH2's 35 mV draws every
   other row 0.2 px tall. A row flatter than FLAT_PX says so on the row. */

export interface LaneGain {
  /** px per display unit this channel is drawn at */
  pxPerUnit: number
  /** true when the channel cannot fit the block at the shared gain and is drawn at its own (never for one channel) */
  ownScale: boolean
  /** how many times smaller than the shared gain it is drawn (1 = the shared gain) */
  factor: number
  /** how tall its own range draws, in px (0 = no range) */
  px: number
  /** drawn flatter than FLAT_PX — the lane says "flat at this gain" (fix round F3) */
  flat: boolean
}

/** One gain per channel. `spans` are each channel's own range over the window (hi − lo, null = nothing finite).
 *  Fix round (the critic): the shared gain comes from the LOWER median — with two channels, one 0.2 mV and one
 *  35 mV, the upper median set the gain from the wide one and drew the narrow one ~1.8 px flat — and is capped so
 *  the median channel never runs past the block (one channel at 1.6 lanes was taller than the block, marked ÷1.0). */
export function overlayGains(spans: (number | null)[], lane: number, blockPx: number, gainLanes: number): { shared: number; medianSpan: number; rows: LaneGain[] } {
  const live = spans.filter((s): s is number => s !== null && Number.isFinite(s) && s > 0).sort((a, b) => a - b)
  const medianSpan = live.length ? live[Math.floor((live.length - 1) / 2)] : 1
  const shared = Math.min(gainLanes * lane, 0.9 * blockPx) / medianSpan
  const many = spans.length > 1
  const rows = spans.map(s => {
    const span = s !== null && Number.isFinite(s) && s > 0 ? s : 0
    if (!many || !span || span * shared <= blockPx) {
      const px = span * shared
      return { pxPerUnit: shared, ownScale: false, factor: 1, px, flat: span > 0 && px < FLAT_PX }
    }
    const own = Math.min(gainLanes * lane, 0.9 * blockPx) / span
    const factor = shared / own
    return { pxPerUnit: own, ownScale: factor > 1, factor, px: span * own, flat: false }
  })
  return { shared, medianSpan, rows }
}

/** Gate G2: the drawing origin for one lane, nudged so the channel's whole drawn extent — `up` units above its mean
 *  and `down` below, at `pxPerUnit` — stays inside [0, blockPx]. A channel that fits the block at the shared gain but
 *  sits in an edge lane (CO CH4 ran 46 px below the block) moves toward the middle instead of leaving it; the gain,
 *  and so how its height compares with the others', is unchanged. A lane that fits keeps its centre. */
export function fitCentre(centre: number, up: number, down: number, pxPerUnit: number, blockPx: number): number {
  const top = up * pxPerUnit, bottom = down * pxPerUnit
  if (top + bottom >= blockPx) return (blockPx - bottom + top) / 2     // cannot fit (never for a shared- or own-gain lane)
  return Math.min(Math.max(centre, top), blockPx - bottom)
}

export interface DetectionMark { t0: number; t1: number; n: number; openLeft: boolean; openRight: boolean }

/** Overlapping (or touching) detections as one mark each, clipped to [w0, w1], in time order. */
export function mergeDetectionMarks(ds: { t0: number; t1: number }[], w0: number, w1: number): DetectionMark[] {
  const live = ds.filter(d => d.t1 > w0 && d.t0 < w1).map(d => ({ t0: d.t0, t1: d.t1 })).sort((a, b) => a.t0 - b.t0 || a.t1 - b.t1)
  const out: { t0: number; t1: number; n: number }[] = []
  for (const d of live) {
    const last = out[out.length - 1]
    if (last && d.t0 <= last.t1) { last.t1 = Math.max(last.t1, d.t1); last.n++ }
    else out.push({ t0: d.t0, t1: d.t1, n: 1 })
  }
  return out.map(m => ({ t0: Math.max(w0, m.t0), t1: Math.min(w1, m.t1), n: m.n, openLeft: m.t0 < w0, openRight: m.t1 > w1 }))
}

/** A stacked row drawn flatter than this many px reads as a dead-flat line; it says so instead. */
export const FLAT_PX = 2

/** How tall (px) a row's own extent draws at `gain` units per `heightPx`; null when it has no extent. */
export function drawnRowPx(extent: [number, number] | null, gain: number | null, heightPx: number): number | null {
  if (!extent || gain === null || !(gain > 0)) return null
  return ((extent[1] - extent[0]) / gain) * heightPx
}
