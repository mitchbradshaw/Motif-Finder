/* ig-pages: the intervals timeline (the researcher, 2026-10-18). Every event on the channel as a tick on the time
 * axis, the distance to the previous one WRITTEN ON THE GAP, and a colour-by-similarity control: the family when
 * every event has one, else the depth in thirds of its range (small / medium / large). An "intervals within"
 * selector restricts the written distances, and the statistics table beneath, to one colour class — between purple
 * smalls, then between green larges — or shows all.
 *
 * Every number here is the bridge's (`serialize.py::_interval_classes`, through the intervals block's own timing
 * and the core's statistics); the page only places them. One lane per group, because an interval is only meaningful
 * inside one group (the intervals block's rule). */
import { useMemo, useState } from 'react'
import type { IntervalClasses, IntervalStats } from '../../api'
import { TimeAxis } from '../../charts/primitives'
import { makeX } from '../../charts/scale'
import { useSize } from '../../charts/useSize'
import { Histogram, InfoTip } from '../../kit'
import { IntervalStatsTable } from '../EventFeatures'

/** The researcher's example: small drops purple, big drops green; medium between them in amber. */
const DEPTH_COLOUR: Record<string, string> = { small: '#8e5cf7', medium: '#e8900c', large: '#22a06b', unmeasured: '#9ca3af', all: '#4b5563' }
const FAMILY_COLOURS = ['#8e5cf7', '#22a06b', '#0a84ff', '#e8900c', '#d6336c', '#0f766e', '#a16207', '#6b21a8']
export function classColour(ic: IntervalClasses, key: string): string {
  if (ic.rule !== 'family') return DEPTH_COLOUR[key] ?? '#4b5563'
  const i = ic.classes.findIndex(c => c.key === key)
  return FAMILY_COLOURS[(i < 0 ? 0 : i) % FAMILY_COLOURS.length]
}

/** seconds or minutes (or hours), whichever reads */
export function fmtGap(s: number): string {
  if (!Number.isFinite(s)) return '—'
  if (s < 120) return `${s < 10 ? s.toFixed(1) : Math.round(s)} s`
  if (s < 7200) return `${(s / 60).toFixed(s < 600 ? 1 : 0)} min`
  return `${(s / 3600).toFixed(1)} h`
}

const LANE = 30, LABEL_PX = 6.2, MAX_LANES = 6

export function IntervalTimeline({ ic, t0, t1, within, onWithin, coloured, onColoured, stats }: {
  ic: IntervalClasses; t0: number; t1: number
  /** 'all' or one class key */
  within: string; onWithin: (w: string) => void
  coloured: boolean; onColoured: (c: boolean) => void
  /** the block's own per-group statistics, shown when `within` is 'all' */
  stats?: Record<string, IntervalStats>
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width)
  const x = makeX(t0, t1, w, 8, 8)
  const groups = useMemo(() => ic.event_group ? Array.from(new Set(ic.event_group)) : ['all'], [ic])
  // one lane per group up to MAX_LANES; past that (e.g. Trains wrote one group per train) one shared lane, the
  // distances still measured inside each group
  const shared = groups.length > MAX_LANES
  const groupOf = (i: number) => ic.event_group ? ic.event_group[i] : 'all'
  // the events of each lane in time order, and for each event the one its written distance is measured from
  const lanes = useMemo(() => (shared ? ['all groups'] : groups).map(g => {
    const idx = ic.event_t_s.map((_, i) => i).filter(i => shared || groupOf(i) === g)
      .sort((a, b) => ic.event_t_s[a] - ic.event_t_s[b])
    const gaps: { from: number; to: number; s: number }[] = []
    for (const gg of shared ? groups : [g]) {
      const inG = idx.filter(i => groupOf(i) === gg)
      const mine = within === 'all' ? inG : inG.filter(i => ic.event_class[i] === within)
      const from = within === 'all' ? ic.gap_s : ic.within_gap_s
      for (let k = 1; k < mine.length; k++) { const s = from[mine[k]]; if (s !== null) gaps.push({ from: mine[k - 1], to: mine[k], s }) }
    }
    return { g, idx, gaps }
  }), [ic, groups, within, shared])   // eslint-disable-line react-hooks/exhaustive-deps
  const histValues = lanes.flatMap(L => L.gaps.map(g => g.s))
  const h = lanes.length * LANE + 6
  let unwritten = 0
  const colour = (i: number) => coloured ? classColour(ic, ic.event_class[i]) : '#4b5563'
  const shownStats = within === 'all' ? stats : ic.stats[within]
  return (
    <div className="stack" style={{ gap: 6 }} data-testid="interval-timeline" data-within={within} data-rule={ic.rule} data-coloured={coloured ? '1' : '0'}>
      <div className="row small" style={{ gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <label className="row" style={{ gap: 4, alignItems: 'center' }}>
          <input type="checkbox" checked={coloured} onChange={e => onColoured(e.target.checked)} data-testid="interval-colour-toggle" disabled={ic.rule === 'none'} />
          colour events by similarity
        </label>
        <span className="muted">·</span>
        <span>intervals within</span>
        <div className="row" style={{ gap: 4, flexWrap: 'wrap' }} data-testid="interval-within">
          {[{ key: 'all', label: 'all events', n: ic.event_class.length }, ...ic.classes].map(c => (
            <button key={c.key} type="button" className={`btn sm${within === c.key ? ' on' : ''}`} onClick={() => onWithin(c.key)}
              data-testid={`interval-within-${c.key.replace(/\s+/g, '-')}`} aria-pressed={within === c.key}
              disabled={c.key !== 'all' && ic.rule === 'none'}>
              {c.key !== 'all' && <i style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 2, marginRight: 4, background: classColour(ic, c.key) }} />}
              {c.key === 'all' ? 'all' : `${c.label} to ${c.label}`}
            </button>
          ))}
        </div>
        <InfoTip title="What the distances are">
          Each number written on a gap is the time from one event's onset to the next event's, in the same group (the
          Intervals block's rule). With a class chosen, it is the time to the next event of THAT class, skipping the
          others, and the table beneath is computed over those distances only.
        </InfoTip>
      </div>
      <div className="plot-surface" ref={ref} style={{ height: h + 20, position: 'relative' }}>
        {size.width > 0 && <svg width={w} height={h + 20} data-testid="interval-timeline-plot">
          {lanes.map((L, li) => {
            const y0 = li * LANE + 4, mid = y0 + LANE / 2
            return (
              <g key={L.g} data-lane={L.g}>
                {lanes.length > 1 && <text x={2} y={y0 + 9} style={{ fontSize: 9.5, fill: 'var(--muted)' }}>{L.g}</text>}
                <line x1={x(t0)} x2={x(t1)} y1={mid + 6} y2={mid + 6} stroke="var(--grey-200, #e5e7eb)" />
                {L.gaps.map(gp => {
                  const xa = x(ic.event_t_s[gp.from]), xb = x(ic.event_t_s[gp.to])
                  const text = fmtGap(gp.s)
                  const fits = xb - xa >= text.length * LABEL_PX + 4
                  if (!fits) unwritten++
                  return (
                    <g key={`${gp.from}-${gp.to}`} data-testid="interval-gap">
                      <rect x={xa} y={mid - 6} width={Math.max(1, xb - xa)} height={14} fill="transparent"><title>{`${text} between these two events`}</title></rect>
                      {within !== 'all' && <line x1={xa} x2={xb} y1={mid + 6} y2={mid + 6} stroke={colour(gp.to)} strokeWidth={2} opacity={0.6} />}
                      {fits && <text x={(xa + xb) / 2} y={mid + 2} textAnchor="middle" data-testid="interval-gap-label" style={{ fontSize: 10, fill: 'var(--text-2, #374151)' }}>{text}</text>}
                    </g>
                  )
                })}
                {L.idx.map(i => {
                  const dim = within !== 'all' && ic.event_class[i] !== within
                  return <line key={i} x1={x(ic.event_t_s[i])} x2={x(ic.event_t_s[i])} y1={mid + 1} y2={mid + 12} stroke={colour(i)} strokeWidth={2} opacity={dim ? 0.2 : 1} data-class={ic.event_class[i]}><title>{`${ic.event_class[i]} · ${fmtGap(ic.event_t_s[i] - t0)} into the span`}</title></line>
                })}
              </g>
            )
          })}
          <TimeAxis x={x} y={h + 2} t0={t0} t1={t1} n={7} ends />
        </svg>}
      </div>
      <div className="bp-legend" style={{ paddingLeft: 0 }} data-testid="interval-legend">
        {coloured && ic.rule !== 'none' && ic.classes.map(c => (
          <span key={c.key}><i style={{ background: classColour(ic, c.key) }} />{c.label} · {c.n} event{c.n === 1 ? '' : 's'}</span>
        ))}
        <span className="muted" data-testid="interval-legend-rule">{ic.rule_words}{ic.rule === 'depth' && ic.edges ? ` (cuts at ${ic.edges[1].toPrecision(3)} and ${ic.edges[2].toPrecision(3)})` : ''}</span>
        {unwritten > 0 && <span className="muted" data-testid="interval-unwritten">{unwritten} distance{unwritten === 1 ? '' : 's'} too narrow to write here · hover the gap</span>}
      </div>
      <div>
        <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Inter-event intervals{within === 'all' ? '' : `, ${within} to ${within}`}</h3><span className="sg">per group, never pooled{within === 'all' ? '' : ' · only the distances between events of this class'}</span></div>
        {shownStats && Object.keys(shownStats).length > 0
          ? <IntervalStatsTable stats={shownStats} testid={within === 'all' ? 'interval-stats' : 'interval-stats-within'} />
          : <div className="muted mono small" data-testid="interval-stats-empty">no interval statistics for this selection</div>}
      </div>
      <div>
        <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>The distances, as a histogram</h3><span className="sg">{histValues.length} interval{histValues.length === 1 ? '' : 's'}{within === 'all' ? '' : ` · ${within} to ${within}`}{shared ? ` · ${groups.length} groups drawn on one lane` : ''}</span></div>
        {histValues.length > 1
          ? <Histogram values={histValues} nBins={Math.min(30, Math.max(6, Math.round(Math.sqrt(histValues.length))))} height={130} xLabel="seconds between events" colour={within === 'all' ? '#9ca3af' : classColour(ic, within)} testid="interval-histogram" />
          : <div className="muted mono small" data-testid="interval-histogram-empty">{histValues.length === 0 ? 'no interval to draw' : `one interval: ${fmtGap(histValues[0])}`}</div>}
      </div>
    </div>
  )
}

/** The timeline with its own state (which class, coloured or not), for a page that just hands over the payload. */
export function IntervalTimelinePanel({ ic, t0, t1, stats }: { ic: IntervalClasses; t0: number; t1: number; stats?: Record<string, IntervalStats> }) {
  const [within, setWithin] = useState('all')
  const [coloured, setColoured] = useState(ic.rule !== 'none')
  return <IntervalTimeline ic={ic} t0={t0} t1={t1} within={within} onWithin={setWithin} coloured={coloured} onColoured={setColoured} stats={stats} />
}
