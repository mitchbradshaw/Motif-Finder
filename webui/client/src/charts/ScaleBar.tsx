/* The scale bar (fixup-h, QUESTIONS.md Q15): what keeps "legible" and "comparable" from being a trade-off on
 * small multiples. Every panel is drawn on a y domain measured from its own trace (charts/domain.ts), so a
 * 0.014 mV motif and a 0.39 mV sibling are both a shape and not a flat line — and each panel carries a bar of
 * a ROUND size in its own units, drawn to that panel's scale, so the eye reads the size off the bar instead of
 * off a shared axis. A shared y was tried on the researcher's own figures and rejected (figures12b_s3.py):
 * clustering is scale-invariant, so one axis draws most of a family flat. */

/** The largest 1 / 2 / 5 × 10^k that is at most `frac` of the span. 0 for a span with no extent. */
export function niceBar(span: number, frac = 0.5): number {
  if (!(span > 0) || !Number.isFinite(span)) return 0
  const target = span * frac
  const k = Math.pow(10, Math.floor(Math.log10(target)))
  const m = target / k
  return (m >= 5 ? 5 : m >= 2 ? 2 : 1) * k
}

export function fmtBar(v: number): string {
  if (v === 0) return '0'
  const a = Math.abs(v)
  return a >= 100 ? String(Math.round(v)) : String(+v.toPrecision(2))
}

/** A vertical bar `size` units tall on a panel whose y `domain` is drawn over `height` px (with `pad` px of
 *  inset top and bottom, as `MiniTrace` draws). Sits beside the panel; the label is the bar's size. */
export function ScaleBar({ domain, height, unit = 'mV', pad = 2, testid = 'scale-bar' }: {
  domain: [number, number]; height: number; unit?: string; pad?: number; testid?: string
}) {
  const span = domain[1] - domain[0]
  const size = niceBar(span)
  const px = span > 0 ? (size / span) * (height - 2 * pad) : 0
  const W = 34
  return (
    <svg className="k-scalebar" width={W} height={height} viewBox={`0 0 ${W} ${height}`} role="img" data-testid={testid}
      data-size={size} data-px={px.toFixed(1)} aria-label={`scale bar: ${fmtBar(size)} ${unit}`} style={{ flex: 'none', display: 'block' }}>
      <title>{`this panel's own scale: the bar is ${fmtBar(size)} ${unit} tall. Each panel is drawn on a y measured from its own trace, so read sizes off the bars, not off the heights.`}</title>
      {px > 0 && <line x1={3} x2={3} y1={height - pad - px} y2={height - pad} stroke="var(--text-2)" strokeWidth={2} />}
      <text x={7} y={height - pad - Math.max(0, px / 2) + 3} style={{ fontFamily: 'var(--font-mono)', fontSize: 9, fill: 'var(--muted)' }}>{px > 0 ? fmtBar(size) : '—'}</text>
    </svg>
  )
}
