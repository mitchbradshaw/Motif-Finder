/* One histogram with the null behind it, split into per-category bars in front (frames interrogation-3
 * and 3b). The kit's `Histogram` draws exactly two series, so colour-by used to fall back to stacked
 * `Bars` — which dropped the grey null and re-binned the data (critique r1). P10 puts a null behind
 * *every* distribution, so this draws both: the null bars at full bin width behind, the observed bars
 * (one stack per colour-by category, or a single series when colour-by is off) in front.
 * Kit change requested in webui/pages/requests/interrogation.md; this is the local stand-in. */
import { scaleLinear } from 'd3'
import { Legend, fmtInt } from '../kit'
import { useSize } from '../charts/useSize'

export interface HistBar { x0: number; x1: number; count: number }
export interface HistSeries { key: string; label: string; colour: string; counts: number[] }

export function NullHistogram({ bars, nulls, series, height = 150, format, nullLabel = 'null', legend = true, testid }: {
  bars: HistBar[]                 // the bin edges every series is counted into
  nulls: number[] | null          // null counts per bin, or null when the null is switched off
  series: HistSeries[]            // observed counts per bin, stacked in order
  height?: number
  format: (v: number) => string
  nullLabel?: string
  legend?: boolean
  testid?: string
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = size.width
  const padL = 34, padR = 10, padT = 8, padB = 22
  const dom: [number, number] = bars.length ? [bars[0].x0, bars[bars.length - 1].x1] : [0, 1]
  const totals = bars.map((_, i) => series.reduce((s, se) => s + (se.counts[i] ?? 0), 0))
  const maxC = Math.max(1, ...totals, ...(nulls ?? []))
  const x = scaleLinear().domain(dom).range([padL, Math.max(padL + 1, w - padR)])
  const y = scaleLinear().domain([0, maxC]).range([height - padB, padT])
  const bw = bars.length ? Math.max(1, x(bars[0].x1) - x(bars[0].x0)) : 1
  const ticks = y.ticks(3), xt = x.ticks(5)

  return (
    <div ref={ref} className="k-plot" data-testid={testid}>
      {w > 0 && (
        <svg width={w} height={height} role="img" aria-label={`histogram of ${bars.length} bins with its null behind`}>
          {ticks.map(t => <g key={t}><text x={padL - 6} y={y(t) + 3} textAnchor="end">{fmtInt(t)}</text></g>)}
          {/* the null, behind — full bin width */}
          {nulls && bars.map((b, i) => (
            <rect key={`n${i}`} x={x(b.x0) + 0.5} width={Math.max(0.5, bw - 1)} y={y(nulls[i] ?? 0)} height={Math.max(0, y(0) - y(nulls[i] ?? 0))}
              fill="#d1d5db"><title>{`${format(b.x0)}–${format(b.x1)} · ${nullLabel} ${fmtInt(nulls[i] ?? 0)}`}</title></rect>
          ))}
          {/* the observed bars, stacked by category, in front and narrower so the null stays visible */}
          {bars.map((b, i) => {
            let acc = 0
            const iw = Math.max(1, bw * 0.62)
            const bx = x(b.x0) + (bw - iw) / 2
            return (
              <g key={`o${i}`}>
                {series.map(se => {
                  const v = se.counts[i] ?? 0
                  const yTop = y(acc + v), yBot = y(acc)
                  acc += v
                  return v <= 0 ? null : (
                    <rect key={se.key} x={bx} width={iw} y={yTop} height={Math.max(0, yBot - yTop)} fill={se.colour} opacity={0.88}>
                      <title>{`${format(b.x0)}–${format(b.x1)} · ${se.label} ${fmtInt(v)}`}</title>
                    </rect>
                  )
                })}
              </g>
            )
          })}
          <line x1={padL} x2={Math.max(padL + 1, w - padR)} y1={y(0)} y2={y(0)} stroke="var(--border)" />
          {xt.map(t => <text key={t} x={x(t)} y={height - 7} textAnchor="middle">{format(t)}</text>)}
        </svg>
      )}
      {w === 0 && <div style={{ height }} />}
      {legend && <Legend items={[
        ...(nulls ? [{ label: nullLabel, colour: '#d1d5db' }] : []),
        ...series.map(se => ({ label: se.label, colour: se.colour })),
      ]} />}
    </div>
  )
}
