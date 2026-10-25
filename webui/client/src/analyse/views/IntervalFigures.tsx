/* night-analyse (the researcher, 2026-10-20): the Intervals page, top to bottom —
 *   1. the block's input signal over the span, the detected regions on it coloured by interval class, each class
 *      shown / hidden by its checkbox (the same switches as the scatter's legend);
 *   2. the interactive interval timeline (IntervalTimeline);
 *   3. in place of the histogram, one scatter series per class: x = the event's time, y = the time until the next
 *      event of the SAME class in its group (the bridge's `next_within_gap_s`), each series drawn 0..1 over its own
 *      range, the real value on hover; hovering or clicking a point marks the event on the signal;
 *   4. how the classes follow one another: a transition matrix (for each class, the class of the next event), as
 *      counts and row percentages, heat-shaded.
 * All four share one time axis with the timeline (the same 8 px margins). Every interval is the bridge's; the
 * matrix only counts the order of the classes the bridge assigned. */
import { useMemo, type CSSProperties } from 'react'
import type { IntervalClasses, IntervalStats, SpansetPayload } from '../../api'
import { EnvelopePath } from '../../charts/primitives'
import { extentOf } from '../../charts/domain'
import { makeX, makeY } from '../../charts/scale'
import { useSize } from '../../charts/useSize'
import { InfoTip } from '../../kit'
import { fmtHours } from '../../state'
import { IntervalTimelinePanel, classColour, fmtGap } from './IntervalTimeline'
import { MultiScatter, SeriesLegend, useMarkedEvent, useSeriesToggle, type ScatterSeries } from './MultiScatter'
import type { ProcessProps } from './common'
import { transitionMatrix } from './eventFigures'

const PAD = 8   // IntervalTimeline's x margins, so every figure here lines up with it

/** 1. The signal with the detected regions coloured by class. */
function IntervalSignal({ q, p, ic, shown, mark, onPick }: { q: ProcessProps; p: SpansetPayload; ic: IntervalClasses; shown: ReadonlySet<string>; mark: number | null; onPick: (i: number) => void }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width), h = 120
  const { t0, t1, ghost } = q.ctx
  const x = makeX(t0, t1, w, PAD, PAD)
  const gr = ghost && ghost.t.length ? extentOf(ghost.v) : null
  const n = Math.min(p.start_s.length, ic.event_class.length)
  return (
    <div className="plot-surface" ref={ref} style={{ height: h, position: 'relative' }} data-testid="interval-signal" data-shown={[...shown].join('|')}>
      {size.width > 0 && (
        <svg width={w} height={h} data-plot-box data-rule9="ghost" style={{ display: 'block' }}>
          {Array.from({ length: n }, (_, i) => i).filter(i => shown.has(ic.event_class[i])).map(i => {
            const x0 = x(p.start_s[i]), x1 = x(p.end_s[i])
            return (
              <rect key={i} x={x0} y={0} width={Math.max(2, x1 - x0)} height={h} fill={classColour(ic, ic.event_class[i])} fillOpacity={mark === i ? 0.55 : 0.28}
                stroke={mark === i ? 'var(--amber)' : 'none'} strokeWidth={2} data-class={ic.event_class[i]} data-testid="interval-region" style={{ cursor: 'pointer' }} onClick={() => onPick(i)}>
                <title>{`event #${i + 1} · ${ic.event_class[i]} · ${fmtHours(p.start_s[i], 3)}`}</title>
              </rect>
            )
          })}
          {ghost && gr && <g data-trace pointerEvents="none"><EnvelopePath t={ghost.t} v={ghost.v} x={x} y={makeY(gr[0], gr[1], h)} stroke="var(--trace)" opacity={0.85} testid="ghost" /></g>}
          {!ghost && <text x={PAD + 4} y={14} style={{ fontSize: 10, fill: 'var(--muted)' }}>no signal from the steps before to draw the regions on</text>}
        </svg>
      )}
    </div>
  )
}

/** 3. One series per class: the time until the next event of that class. */
function classSeries(ic: IntervalClasses): { series: ScatterSeries[]; next: boolean } {
  const next = Array.isArray(ic.next_within_gap_s)
  const gaps = next ? ic.next_within_gap_s! : ic.within_gap_s
  return {
    next,
    series: ic.classes.map(c => {
      const idx = ic.event_class.map((k, i) => (k === c.key && ic.event_t_s[i] !== null ? i : -1)).filter(i => i >= 0)
      return {
        key: c.key, label: c.key === 'all' ? 'all events' : c.label, colour: classColour(ic, c.key), unit: '', fmt: fmtGap,
        idx, t: idx.map(i => ic.event_t_s[i]), v: idx.map(i => gaps[i]),
      }
    }),
  }
}

/** 4. The class transition matrix. */
function ClassTransitions({ ic }: { ic: IntervalClasses }) {
  const keys = ic.classes.map(c => c.key)
  const m = useMemo(() => transitionMatrix(ic.event_class, ic.event_t_s, keys, ic.event_group), [ic])   // eslint-disable-line react-hooks/exhaustive-deps
  const total = m.rowTotal.reduce((a, b) => a + b, 0)
  // the InfoTip's example is the busiest row's most common successor, in the page's own numbers
  const r = m.rowTotal.indexOf(Math.max(...m.rowTotal))
  const c = r >= 0 ? m.counts[r].indexOf(Math.max(...m.counts[r])) : -1
  const example = r >= 0 && c >= 0 && m.rowTotal[r] > 0 ? `after a ${keys[r]} event, the next one is ${keys[c]} ${Math.round(m.rowPct[r][c]!)} % of the time` : null
  const th: CSSProperties = { padding: '3px 8px', textAlign: 'left', fontWeight: 600, borderBottom: '1px solid var(--grey-200, #e5e7eb)' }
  return (
    <div data-testid="class-transitions" data-total={total}>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Which class comes next</h3>
        <span className="sg row" style={{ gap: 4, alignItems: 'center' }}>{total} step{total === 1 ? '' : 's'} from one event to the next, inside each group
          <InfoTip title="How to read the table" testid="class-transitions-info">
            Each row is the class of an event; each column the class of the event right after it (in time, in the same
            group). A cell holds how many times that happened and what share of the row it is, shaded by that share.
            {example ? <> Here, for example: {example}.</> : null} A row with no count is a class whose events are each the
            last of their group.
          </InfoTip>
        </span>
      </div>
      {total === 0
        ? <div className="muted mono small" data-testid="class-transitions-empty">no event is followed by another in its group, so there is nothing to count</div>
        : (
          <table className="mono" style={{ borderCollapse: 'collapse', fontSize: 11.5 }}>
            <thead><tr><th style={th}>after a … event</th>{keys.map(k => <th key={k} style={th}><i style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, marginRight: 4, background: classColour(ic, k) }} />next is {k}</th>)}<th style={th}>n</th></tr></thead>
            <tbody>
              {keys.map((k, i) => (
                <tr key={k} data-from={k}>
                  <td style={{ padding: '3px 8px' }}><i style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, marginRight: 4, background: classColour(ic, k) }} />{k}</td>
                  {keys.map((k2, j) => {
                    const pct = m.rowPct[i][j]
                    return (
                      <td key={k2} data-to={k2} data-count={m.counts[i][j]} style={{ padding: '3px 8px', textAlign: 'right', background: pct === null ? undefined : `rgba(37, 99, 235, ${(0.06 + 0.5 * pct / 100).toFixed(3)})` }}>
                        {m.counts[i][j]}{pct === null ? '' : <span className="muted"> · {Math.round(pct)} %</span>}
                      </td>
                    )
                  })}
                  <td style={{ padding: '3px 8px', textAlign: 'right' }} className="muted">{m.rowTotal[i]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
    </div>
  )
}

export function IntervalFigures({ q, p, ic, stats }: { q: ProcessProps; p: SpansetPayload; ic: IntervalClasses; stats?: Record<string, IntervalStats> }) {
  const { mark, setHover, pick } = useMarkedEvent()
  const keys = useMemo(() => ic.classes.map(c => c.key), [ic])
  const { shown, toggle } = useSeriesToggle(keys)
  const { series, next } = useMemo(() => classSeries(ic), [ic])
  const { t0, t1 } = q.ctx
  return (
    <div className="stack" style={{ gap: 10 }} data-testid="interval-figures">
      <div>
        <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>The events on the signal, by class</h3><span className="sg">the block's input signal · each detected region coloured by its class · tick a class to show or hide it</span></div>
        <IntervalSignal q={q} p={p} ic={ic} shown={shown} mark={mark} onPick={pick} />
        <SeriesLegend testid="interval-class-legend" shown={shown} onToggle={toggle}
          series={ic.classes.map(c => ({ key: c.key, label: c.key === 'all' ? 'all events' : c.label, colour: classColour(ic, c.key), n: c.n }))}
          note={<span className="muted">events per class · the rule is under the timeline</span>} />
      </div>
      <IntervalTimelinePanel ic={ic} t0={t0} t1={t1} stats={stats} />
      <div>
        <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>{next ? 'Time until the next event of the same class' : 'Time since the previous event of the same class'}</h3>
          <span className="sg">one series per class, on the time axis above · hover a point for its interval, click to mark the event</span></div>
        <MultiScatter series={series} t0={t0} t1={t1} shown={shown} onToggle={toggle} hover={mark} onHover={setHover} onPick={pick}
          padL={PAD} padR={PAD} testid="interval-scatter" what={next ? "one event, at the height of the time until the next event of its class (in its group)" : "one event, at the height of the time since the previous event of its class (in its group)"} />
        {mark !== null && <div className="mono small" data-testid="interval-marked">event #{mark + 1} ({ic.event_class[mark]}) at {fmtHours(p.start_s[mark], 3)} marked on the signal{ic.next_within_gap_s?.[mark] != null ? ` · next ${ic.event_class[mark]} in ${fmtGap(ic.next_within_gap_s![mark]!)}` : ''}</div>}
      </div>
      {ic.classes.length > 1 && <ClassTransitions ic={ic} />}
    </div>
  )
}
