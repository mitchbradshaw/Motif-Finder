/* The decisions of Explore › Cross-channel that a test should be able to run (fixup-AQ), kept free of imports
   so Node can execute this file as it stands (tests/test_webui_cross_page.py, as tests/test_webui_plot_domain.py
   does for charts/domain.ts). Three of them, each one a symptom from the researcher's screenshot of 2026-10-13:

   X1 — the shared gain. 'centred' drew each row about its own MEDIAN with a half-scale of the largest
        median-to-extreme distance, then printed the height of the padded y domain. For a window whose median
        sits near one end (an asymmetric transient, or a drift) that half-scale is nearly the whole range, so the
        printed gain came out up to twice the widest row's range plus the plot pad (6 % a side): "20.74 mV per
        row" over rows printing 5–10 mV, each using a quarter of its height. Now each row is centred on the
        middle of its own range and the gain IS the widest drawn row's range — that row fills its height, every
        other row sits inside it, no row clips (crossScale's header keeps the no-clip property), and the note
        prints the same number. Still one gain for every row: no amplitude is normalised.
   X2 — the window. The page's window is a span of the reference channel plus a pad each side; ?window=motif-<n>
        names the n-th span (1-based) in time order over the channel's annotations and detections together —
        Signal's numbering when every run is shown — and ?t0=&t1= an edge's own window, unpadded, which wins.
        One resolver for the picker, the deep links and the fetch, so they cannot disagree.
   X4 — lag-aligned. A row's own time base slides back by the lag the core measured (lag > 0 means the row
        is later than the reference), so the two waveforms land on top of each other; the reference never
        moves, and a row past max lag stays as recorded. */

/* ------------------------------------------------------------------ X1: the gain ---- */
export interface RowStat { extent: [number, number]; median: number }

/** A row's own extent and median over the finite samples of its envelope, or null when it has none. */
export function rowStat(v: (number | null)[]): RowStat | null {
  const f: number[] = []
  for (const x of v) if (x !== null && x !== undefined && Number.isFinite(x)) f.push(x)
  if (!f.length) return null
  f.sort((a, b) => a - b)
  const n = f.length
  return { extent: [f[0], f[n - 1]], median: n % 2 ? f[(n - 1) / 2] : (f[n / 2 - 1] + f[n / 2]) / 2 }
}

export interface CentredStack {
  /** mV per row: the widest drawn row's own range — the number the note prints */
  gainMv: number
  /** the index of the row that set it */
  setBy: number
  /** per row, the mV bounds it is drawn between (centre ± gain / 2), or null for a row with nothing finite */
  rows: ({ centre: number; lo: number; hi: number } | null)[]
}

/** One gain for the drawn rows, each row about the middle of its own range; null when no row has a sample. */
export function centredStack(stats: (RowStat | null)[]): CentredStack | null {
  let gain = -1, setBy = -1
  stats.forEach((s, i) => { if (s && s.extent[1] - s.extent[0] > gain) { gain = s.extent[1] - s.extent[0]; setBy = i } })
  if (setBy < 0) return null
  const half = gain / 2
  return {
    gainMv: gain, setBy,
    rows: stats.map(s => {
      if (!s) return null
      const centre = (s.extent[0] + s.extent[1]) / 2
      return { centre, lo: centre - half, hi: centre + half }
    }),
  }
}

/* ---------------------------------------------------------------- X2: the window ---- */
export interface SpanLike { id: number; start_s: number; end_s: number; verdict?: string }
export interface CrossSpan { key: string; kind: 'annotated' | 'detected'; id: number; start_s: number; end_s: number; verdict?: string }

/** The channel's spans in time order — annotations and detections together, as explore/util.ts::toMotifs
 *  orders them (that one imports the API layer, which Node cannot load; same comparator). */
export function orderSpans(annotations: SpanLike[], detections: SpanLike[]): CrossSpan[] {
  const out: CrossSpan[] = []
  for (const a of annotations) if (a && typeof a === 'object') out.push({ key: `a:${a.id}`, kind: 'annotated', id: a.id, start_s: a.start_s, end_s: a.end_s, verdict: a.verdict })
  for (const d of detections) if (d && typeof d === 'object') out.push({ key: `d:${d.id}`, kind: 'detected', id: d.id, start_s: d.start_s, end_s: d.end_s })
  out.sort((p, q) => p.start_s - q.start_s || p.end_s - q.end_s || p.id - q.id)
  return out
}

/** Verdicts worth opening a cross-channel comparison on, best first (moved from api/explore.ts). Taking the
 *  first span instead landed the page on a bulk `imported_10min` block with verdict `not_interesting`. A
 *  preference order for anchoring, not the verdict vocabulary — `not_interesting` is absent on purpose. */
export const ANCHOR_RANK = ['seed', 'interesting', 'artifact', 'unsure']

/** The default window: the best-ranked human span (earliest within a rank), else the first detection, else the
 *  first span of any kind; -1 when the channel has none. */
export function anchorIndex(spans: CrossSpan[]): number {
  let best = -1, bestRank = Infinity
  spans.forEach((s, i) => {
    const r = s.kind === 'annotated' ? ANCHOR_RANK.indexOf(s.verdict ?? '') : -1
    if (r >= 0 && r < bestRank) { best = i; bestRank = r }
  })
  if (best >= 0) return best
  const det = spans.findIndex(s => s.kind === 'detected')
  return det >= 0 ? det : spans.length ? 0 : -1
}

/** Cross-channel compares short windows: a span longer than this is opened on its first ten minutes. */
export const CROSS_MAX_SPAN_S = 600

export const windowParam = (index0: number) => `motif-${index0 + 1}`
/** `motif-<n>` → the 0-based index, or null for anything else. */
export function parseWindowParam(q: string): number | null {
  const m = /^motif-(\d+)$/.exec(q ?? '')
  return m && Number(m[1]) >= 1 ? Number(m[1]) - 1 : null
}

const fmtS = (s: number) => `${+s.toFixed(1)} s`
const fmtH = (s: number) => `${(s / 3600).toFixed(2)} h`

/** What a span is called in the picker and the header. */
export function spanLabel(s: CrossSpan, clamped = false): string {
  return `${clamped ? 'first 10 min of the ' : ''}${s.kind === 'annotated' ? `${s.verdict} span` : `detection ${s.id} span`} at ${fmtH(s.start_s)}`
}

export interface CrossWindow {
  t0: number; t1: number
  /** the span the window is built around — absolute seconds; the axis counts from spanS */
  spanS: number; spanE: number
  /** 0-based index into the ordered spans, -1 for an edge window or a channel with none */
  index: number; total: number
  /** the ?window= value that reproduces this window ('' for an edge window or no span) */
  param: string
  clamped: boolean
  /** the pad actually applied each side — less than asked where the recording ends */
  padBefore: number; padAfter: number
  label: string
  /** what the window IS, in one phrase the axis agrees with */
  phrase: string
  /** set when ?window= named a span that does not exist — the page says so and shows the default */
  selError: string | null
}

export function resolveCrossWindow(a: { spans: CrossSpan[]; durationS: number; sel: string; padS: number; explicit: { t0: number; t1: number } | null }): CrossWindow {
  const { spans, durationS } = a
  if (a.explicit) {
    const t0 = Math.max(0, a.explicit.t0), t1 = Math.min(durationS, a.explicit.t1)
    const label = `edge window at ${fmtH(t0)}`
    return { t0, t1, spanS: t0, spanE: t1, index: -1, total: spans.length, param: '', clamped: false, padBefore: 0, padAfter: 0,
      label, phrase: `${label} · ${fmtS(t1 - t0)}, unpadded`, selError: null }
  }
  const asked = parseWindowParam(a.sel)
  let selError: string | null = null
  let index = anchorIndex(spans)
  if (asked !== null && asked < spans.length) index = asked
  else if (a.sel) selError = asked !== null
    ? `window ${a.sel} does not exist — this channel has ${spans.length} span${spans.length === 1 ? '' : 's'}; showing the default`
    : `window "${a.sel}" is not a span (expected motif-<n>); showing the default`
  const s = index >= 0 ? spans[index] : null
  const clamped = !!s && s.end_s - s.start_s > CROSS_MAX_SPAN_S
  const spanS = s ? s.start_s : 0
  const spanE = s ? (clamped ? s.start_s + CROSS_MAX_SPAN_S : s.end_s) : Math.min(CROSS_MAX_SPAN_S, durationS)
  const t0 = Math.max(0, spanS - a.padS), t1 = Math.min(durationS, spanE + a.padS)
  const padBefore = spanS - t0, padAfter = t1 - spanE
  const label = s ? spanLabel(s, clamped) : 'first ten minutes'
  const pads = padBefore === padAfter ? `${fmtS(padBefore)} each side` : `${fmtS(padBefore)} before, ${fmtS(padAfter)} after`
  return { t0, t1, spanS, spanE, index, total: spans.length, param: index >= 0 ? windowParam(index) : '', clamped, padBefore, padAfter,
    label, phrase: `${label} · ${fmtS(spanE - spanS)} span + ${pads} = ${fmtS(t1 - t0)}`, selError }
}

/* ---------------------------------------------------------------- X4: lag-aligned ---- */
/** Seconds to slide a row's time base back by: its lag in lag-aligned mode, 0 for the reference, for a row
 *  with no lag, past max lag, or in 'as recorded'. */
export function lagShift(lagS: number | null, isReference: boolean, align: string, maxLag: number): number {
  if (align !== 'lag' || isReference || lagS === null || !Number.isFinite(lagS) || Math.abs(lagS) > maxLag) return 0
  return lagS
}
