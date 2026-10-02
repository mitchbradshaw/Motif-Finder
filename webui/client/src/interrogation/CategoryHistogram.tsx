/* One histogram, its bars split into per-category stacks when colour-by is on (frames interrogation-3, 3b).
 * The kit's `Histogram` draws at most two series, so a colour-by split needs this.
 *
 * fixup-h: this used to be `NullHistogram` and drew a grey "null" behind the bars. That null was three uniforms
 * summed and centred on the midpoint of the observed range — a bell curve, labelled with the wording of a null
 * that is specified and has never been built (QUESTIONS.md Q27). It is gone, not relabelled: a grey cloud that
 * looks exactly like a null is worse than no null. `kit/plots.tsx::NullBand` is written for the real one. */
import { scaleLinear } from 'd3'
import { Legend, fmtInt } from '../kit'
import { useSize } from '../charts/useSize'

export interface HistBar { x0: number; x1: number; count: number }
export interface HistSeries { key: string; label: string; colour: string; counts: number[] }

export function CategoryHistogram({ bars, series, height = 150, format, legend = true, testid }: {
  bars: HistBar[]                 // the bin edges every series is counted into
  series: HistSeries[]            // observed counts per bin, stacked in order
  height?: number
  format: (v: number) => string
  legend?: boolean
  testid?: string
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = size.width
  const padL = 34, padR = 10, padT = 8, padB = 22
  const dom: [number, number] = bars.length ? [bars[0].x0, bars[bars.length - 1].x1] : [0, 1]
  const totals = bars.map((_, i) => series.reduce((s, se) => s + (se.counts[i] ?? 0), 0))
  const maxC = Math.max(1, ...totals)
  const x = scaleLinear().domain(dom).range([padL, Math.max(padL + 1, w - padR)])
  const y = scaleLinear().domain([0, maxC]).range([height - padB, padT])
  const bw = bars.length ? Math.max(1, x(bars[0].x1) - x(bars[0].x0)) : 1
  const ticks = y.ticks(3), xt = x.ticks(5)

  return (
    <div ref={ref} className="k-plot" data-testid={testid}>
      {w > 0 && (
        <svg width={w} height={height} role="img" aria-label={`histogram of ${bars.length} bins`}>
          {ticks.map(t => <g key={t}><text x={padL - 6} y={y(t) + 3} textAnchor="end">{fmtInt(t)}</text></g>)}
          {/* the observed bars, stacked by category */}
          {bars.map((b, i) => {
            let acc = 0
            const iw = Math.max(1, bw - 1)
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
      {legend && series.length > 1 && <Legend items={series.map(se => ({ label: se.label, colour: se.colour }))} />}
    </div>
  )
}
