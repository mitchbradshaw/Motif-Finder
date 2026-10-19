/* The rose: the app's one polar plot (fixup-h). It draws `gradients.rose_data` exactly as the core computed it —
 * 18 bins over the falling quadrant (0° … −90°), each a wedge whose length is its count; every event a dot at
 * its own angle; the circular mean as an arrow — and never derives an angle in the browser. Two roses used to
 * exist: this one (then `RoseFan`, in analyse/EventFeatures.tsx, fed by a block's `meta["rose"]`) and a
 * fixture-era one on the Slope page that computed `arctan(slope / a constant)` itself and set the radius by
 * event order. This is the survivor; the Analyse block page, the Sequence page and the Slope page all draw it. */
import type { ReactNode } from 'react'

/** `Working/interrogation/event_shape.py::rose_payload` — structural, so the kit imports no api type. */
export interface RoseData {
  n: number; counts: number[]; bin_centres_deg: number[]; bin_width_deg: number; angles_deg: number[]; event_index: number[]
  slopes_mv_s?: number[]; groups: Record<string, { n: number; mean_deg: number | null; resultant_length: number | null }>
  scale: string; caption: string
  mean_deg: number | null; resultant_length: number | null; circular_sd_deg: number | null; uniformity_p: number | null; note?: string
  /** fixup-ae: what 45° is and the population it came from (`Working/library/rose_reference.py`) — printed on
   *  every rose that carries it */
  reference?: RoseReference | null
  /** the measure the angles are of (`rose_payload`'s `field`); the reference line is a steepest slope, so it is only
   *  drawn on a rose of `max_slope_mv_s` */
  field?: string
}
export interface RoseReference { value_mv_s: number | null; population: string | null; n: number | null; computed_at: string | null; stored: boolean; text: string }
/** library-family-actions: the reference LINE (`GET /api/library/rose-reference?unit=motifs`) — the median steepest
 *  slope over the human-accepted Library motifs (interesting or seed) and its n. `median_slope: null` / `n: 0`: none
 *  accepted, no line. `error`: the read failed, and the rose says so in place of the label. */
export interface RoseReferenceLine { median_slope: number | null; n: number; computed_from: string; error?: string | null }

/** The slope that sits at 45° on THIS rose, read off the rose's own events (each angle is `arctan(slope / ref)`, so
 *  `ref = |slope| / tan|angle|`): one value when every event shares it (the raw and pooled scales), `null` when the
 *  reference differs event by event (the recording and event scales) — then no single angle stands for a slope.
 *  With no event to read it from, a raw rose's stated reference. Placement only: the slope itself is the bridge's. */
function fortyFiveOf(rose: RoseData): number | null {
  if (rose.field && rose.field !== 'max_slope_mv_s') return null
  const refs: number[] = []
  rose.angles_deg.forEach((a, k) => {
    const s = rose.slopes_mv_s?.[k]; const r = Math.abs(a) * Math.PI / 180
    if (s !== undefined && Number.isFinite(s) && s !== 0 && r > 1e-6 && r < Math.PI / 2 - 1e-6) refs.push(Math.abs(s) / Math.tan(r))
  })
  if (!refs.length) return rose.scale === 'raw' && rose.reference?.value_mv_s ? rose.reference.value_mv_s : null
  const lo = Math.min(...refs), hi = Math.max(...refs)
  return hi - lo <= 1e-3 * hi ? (lo + hi) / 2 : null
}
const fmtSlope = (v: number) => (v >= 100 ? v.toFixed(0) : v.toPrecision(3))

const B = '#0a84ff', BL = '#bfdcff', G = '#9ca3af', AM = '#e8900c', PU = '#7c3aed'

export function Rose({ rose, highlight, onSelect, colourOf, labelOf, legend, reference, testid = 'rose' }: {
  rose: RoseData
  /** library-family-actions: the accepted-motif reference line, labelled with its value and n */
  reference?: RoseReferenceLine | null
  /** the event (by `event_index`) drawn large */
  highlight?: number | null
  onSelect?: (eventIndex: number) => void
  /** a dot's colour by event index; default blue */
  colourOf?: (eventIndex: number) => string
  /** a dot's tooltip name by event index; default "event N" */
  labelOf?: (eventIndex: number) => string
  /** what the dots' colours mean, when `colourOf` is given */
  legend?: ReactNode
  testid?: string
}) {
  const W = 300, H = 230, cx = 24, cy = 20, R = 190
  const max = Math.max(1, ...rose.counts)
  const at = (deg: number, r: number) => { const a = (deg * Math.PI) / 180; return [cx + r * Math.cos(a), cy - r * Math.sin(a)] as const }
  const half = rose.bin_width_deg / 2
  const stats = rose.n ? [
    ['events', String(rose.n)],
    ['mean direction', rose.mean_deg !== null ? `${rose.mean_deg.toFixed(1)}°` : '—'],
    ['resultant R', rose.resultant_length !== null ? rose.resultant_length.toFixed(3) : '—'],
    ['circular sd', rose.circular_sd_deg !== null ? `${rose.circular_sd_deg.toFixed(1)}°` : '—'],
    ['uniform over the quadrant, KS p', rose.uniformity_p !== null ? rose.uniformity_p.toPrecision(2) : '— (n < 3)'],
  ] : []
  const sel = highlight !== undefined && highlight !== null ? rose.event_index.indexOf(highlight) : -1
  // the reference line: where the accepted median slope falls on this rose's own 45° — or why it is not drawn
  const ref45 = reference && reference.median_slope !== null ? fortyFiveOf(rose) : null
  const refDeg = reference && reference.median_slope !== null && ref45 ? -(Math.atan(reference.median_slope / ref45) * 180) / Math.PI : null
  const refText = !reference ? null
    : reference.error ? `reference line not read: ${reference.error}`
    : reference.median_slope === null ? 'no reference line: no human-accepted Library motif (interesting or seed) has a measured slope yet (n = 0)'
    : `reference line · accepted median ${fmtSlope(reference.median_slope)} mV/s · n = ${reference.n}${refDeg === null
      ? ` · not drawn: ${rose.field && rose.field !== 'max_slope_mv_s' ? `this rose is of ${rose.field}, not a slope` : `this rose's scale (${rose.scale}) has no single 45°`}`
      : ` · at ${refDeg.toFixed(1).replace('-', '−')}°`}`
  return (
    <div data-testid={testid} style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`rose of ${rose.n} steepest-slope angles`} data-render="rose">
        <path d={`M ${at(0, R).join(' ')} A ${R} ${R} 0 0 1 ${at(-90, R).join(' ')}`} fill="none" stroke="#e5e7eb" />
        {[0, -15, -30, -45, -60, -75, -90].map(s => {
          const [x2, y2] = at(s, R); const [lx, ly] = at(s, R + 12)
          return <g key={s}><line x1={cx} y1={cy} x2={x2} y2={y2} stroke={s === -45 ? '#c8ccd4' : '#f0f1f3'} /><text x={lx} y={ly + 3} fontSize={9} fill={G} textAnchor={s <= -75 ? 'middle' : 'start'}>{s === 0 ? '0°' : `−${-s}°`}</text></g>
        })}
        {rose.counts.map((c, i) => {
          if (!c) return null
          const mid = rose.bin_centres_deg[i]; const r = R * (c / max)
          const [x1, y1] = at(mid + half, r); const [x2, y2] = at(mid - half, r)
          return <path key={i} d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2} Z`} fill={BL} stroke={B} strokeWidth={0.8} data-rose-bin={i}><title>{`${(mid + half).toFixed(0)}° … ${(mid - half).toFixed(0)}° · ${c} event${c === 1 ? '' : 's'}`}</title></path>
        })}
        {rose.angles_deg.map((a, k) => {
          const ei = rose.event_index[k]
          const [x, y] = at(a, R - 6); const on = k === sel
          const name = labelOf ? labelOf(ei) : `event ${ei + 1}`
          return (
            <circle key={k} cx={x} cy={y} r={on ? 4.5 : 2.6} fill={on ? AM : colourOf ? colourOf(ei) : B} fillOpacity={on ? 1 : 0.7}
              stroke={on ? '#fff' : 'none'} style={onSelect ? { cursor: 'pointer' } : undefined} onClick={onSelect ? () => onSelect(ei) : undefined}
              data-rose-event={ei} data-testid={onSelect ? `rose-point-${ei}` : undefined}>
              <title>{`${name} · ${a.toFixed(1)}°${rose.slopes_mv_s ? ` · ${rose.slopes_mv_s[k].toFixed(3)} mV/s` : ''}`}</title>
            </circle>
          )
        })}
        {rose.mean_deg !== null && (() => { const [x, y] = at(rose.mean_deg, R * 0.9); return <line x1={cx} y1={cy} x2={x} y2={y} stroke={AM} strokeWidth={2} data-testid="rose-mean" /> })()}
        {refDeg !== null && reference && reference.median_slope !== null && (() => {
          const [x, y] = at(refDeg, R + 4); const [lx, ly] = at(refDeg, R * 0.55)
          return <g data-testid="rose-reference-mark" data-angle={refDeg.toFixed(2)}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke={PU} strokeWidth={1.4} strokeDasharray="5 3" />
            <text x={lx + 4} y={ly - 4} fontSize={9.5} fill={PU} style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{`${fmtSlope(reference.median_slope)} mV/s · n ${reference.n}`}</text>
            <title>{refText}</title>
          </g>
        })()}
      </svg>
      <div style={{ fontSize: 12, minWidth: 200, maxWidth: 320 }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{rose.caption || 'no events with a measured fall'}</div>
        {rose.reference && <div className="small" style={{ marginBottom: 6, color: rose.reference.population === 'accepted' ? undefined : '#b56b00' }} data-testid="rose-reference" data-population={rose.reference.population ?? ''}>{rose.reference.text}</div>}
        {refText && <div className="small" style={{ marginBottom: 6, color: reference?.error ? 'var(--red, #c0392b)' : refDeg !== null ? PU : undefined }} data-testid="rose-reference-line"
          data-n={reference?.n ?? 0} data-drawn={refDeg !== null ? '1' : '0'}>{refText}</div>}
        {stats.map(([k, v]) => <div key={k} className="mono" style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><span className="muted">{k}</span><span>{v}</span></div>)}
        {sel >= 0 && <div className="mono" style={{ marginTop: 4, color: AM }} data-testid="rose-selected">{labelOf ? labelOf(highlight as number) : `event ${(highlight as number) + 1}`} · {rose.angles_deg[sel].toFixed(1).replace('-', '−')}°</div>}
        {Object.keys(rose.groups).length > 1 && (
          <div style={{ marginTop: 6 }}>
            {Object.entries(rose.groups).map(([k, g]) => <div key={k} className="mono small">{k}: n {g.n} · mean {g.mean_deg?.toFixed(1) ?? '—'}° · R {g.resultant_length?.toFixed(2) ?? '—'}</div>)}
          </div>
        )}
        {legend && <div className="muted small" style={{ marginTop: 6 }}>{legend}</div>}
        {rose.note && <div className="muted small" style={{ marginTop: 6 }}>{rose.note}</div>}
        <details className="muted small" style={{ marginTop: 4 }}>
          <summary style={{ cursor: 'pointer' }}>how the angle is defined</summary>
          angle = arctan(steepest slope / reference) · scale {rose.scale} · bins {rose.bin_width_deg.toFixed(0)}° · wedge length = events in the bin · KS against uniform over the quadrant, not Rayleigh (a Rayleigh test is significant by construction when every angle is in one quadrant)
        </details>
      </div>
    </div>
  )
}
