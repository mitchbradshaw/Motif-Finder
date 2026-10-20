/* night-analyse (2026-10-20): one scatter for several per-event series on the SAME time axis as the signal above
 * it ("pick what to plot together"). Each series is scaled to 0..1 over its own range for display only, so a mV
 * amplitude and a seconds duration can share a plot; the legend says so, and hovering a point shows the REAL value
 * with its unit and the event's time. Hovering or clicking a point hands the event's index to the page, which marks
 * it on the signal. Every value plotted is the payload's; nothing is derived here.
 *
 * Drawn as one <path> per series (a small square per point), not one element per point, so 5,000 events × several
 * series stays light; the nearest point to the pointer is found by a scan of the shown series. */
import { useMemo, useState, type ReactNode } from 'react'
import { TimeAxis } from '../../charts/primitives'
import { makeX } from '../../charts/scale'
import { useSize } from '../../charts/useSize'
import { InfoTip } from '../../kit'
import { fmtHours } from '../../state'
import { normaliseSeries } from './eventFigures'

export interface ScatterSeries {
  key: string; label: string; colour: string
  /** the unit written after a real value ('' when `fmt` writes its own) */
  unit: string
  fmt: (v: number) => string
  /** one entry per point: the event index (for marking), its time (s, absolute) and its real value */
  idx: number[]; t: (number | null)[]; v: (number | null)[]
}

export const SERIES_COLOURS = ['#2563eb', '#e8900c', '#22a06b', '#d6336c', '#8e5cf7', '#0f766e', '#a16207', '#0891b2', '#6b7280', '#b91c1c']

/** The show / hide legend: a checkbox per series, its colour, and its real range. */
export function SeriesLegend({ series, shown, onToggle, testid, note }: {
  series: { key: string; label: string; colour: string; range?: string; n?: number }[]
  shown: ReadonlySet<string>; onToggle: (key: string) => void; testid: string; note?: ReactNode
}) {
  return (
    <div className="bp-legend" style={{ paddingLeft: 0, flexWrap: 'wrap' }} data-testid={testid}>
      {series.map(s => (
        <label key={s.key} className="row" style={{ gap: 4, alignItems: 'center', cursor: 'pointer' }} data-series={s.key}>
          <input type="checkbox" checked={shown.has(s.key)} onChange={() => onToggle(s.key)} data-testid={`${testid}-toggle-${s.key.replace(/\s+/g, '-')}`} />
          <i style={{ background: s.colour, opacity: shown.has(s.key) ? 1 : 0.3 }} />
          {s.label}{s.n !== undefined ? ` · ${s.n}` : ''}{s.range ? <span className="muted"> · {s.range}</span> : null}
        </label>
      ))}
      {note}
    </div>
  )
}

export function MultiScatter({ series, t0, t1, shown, onToggle, hover, onHover, onPick, height = 150, padL = 0, padR = 0, testid, what }: {
  series: ScatterSeries[]; t0: number; t1: number
  shown: ReadonlySet<string>; onToggle: (key: string) => void
  /** the event marked everywhere (hovered or picked) */
  hover: number | null; onHover: (i: number | null) => void; onPick: (i: number) => void
  height?: number; padL?: number; padR?: number; testid: string
  /** what one point is, for the InfoTip ("one event's measure", "one interval") */
  what: string
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width)
  const x = makeX(t0, t1, w, padL, padR)
  const top = 8, bot = height - 8
  const Y = (u: number) => bot - u * (bot - top)
  const norm = useMemo(() => series.map(s => normaliseSeries(s.v)), [series])
  const [tip, setTip] = useState<{ k: number; j: number; px: number; py: number } | null>(null)
  const shownK = series.map((s, k) => (shown.has(s.key) ? k : -1)).filter(k => k >= 0)
  const paths = useMemo(() => series.map((s, k) => {
    if (!size.width) return ''
    let d = ''
    const y = norm[k].y
    for (let j = 0; j < s.t.length; j++) {
      const t = s.t[j], u = y[j]
      if (t === null || u === null) continue
      const px = x(t), py = Y(u)
      d += `M${(px - 2).toFixed(1)} ${(py - 2).toFixed(1)}h4v4h-4z`
    }
    return d
  }), [series, norm, size.width, t0, t1, padL, padR, height])   // eslint-disable-line react-hooks/exhaustive-deps
  const nearest = (mx: number, my: number) => {
    let best: { k: number; j: number; px: number; py: number } | null = null, bd = 12 * 12
    for (const k of shownK) {
      const s = series[k], y = norm[k].y
      for (let j = 0; j < s.t.length; j++) {
        const t = s.t[j], u = y[j]
        if (t === null || u === null) continue
        const px = x(t), py = Y(u)
        const d = (px - mx) ** 2 + (py - my) ** 2
        if (d < bd) { bd = d; best = { k, j, px, py } }
      }
    }
    return best
  }
  const legend = series.map((s, k) => ({
    key: s.key, label: s.label, colour: s.colour, n: s.v.filter(v => v !== null).length,
    range: norm[k].lo === null ? 'nothing measured' : norm[k].lo === norm[k].hi ? `all ${s.fmt(norm[k].lo!)}${s.unit ? ` ${s.unit}` : ''}` : `${s.fmt(norm[k].lo!)} … ${s.fmt(norm[k].hi!)}${s.unit ? ` ${s.unit}` : ''}`,
  }))
  // the marked event, on every shown series that has it
  const marked = hover === null ? [] : shownK.flatMap(k => {
    const s = series[k], j = s.idx.indexOf(hover)
    const t = j >= 0 ? s.t[j] : null, u = j >= 0 ? norm[k].y[j] : null
    return t === null || u === null ? [] : [{ k, px: x(t), py: Y(u) }]
  })
  const tipSeries = tip ? series[tip.k] : null
  const tipValue = tip && tipSeries ? tipSeries.v[tip.j] : null
  const tipTime = tip && tipSeries ? tipSeries.t[tip.j] : null
  return (
    <div className="stack" style={{ gap: 4 }} data-testid={testid} data-shown={shownK.length}>
      <div className="plot-surface" ref={ref} style={{ height: height + 20, position: 'relative' }}>
        {size.width > 0 && (
          <svg width={w} height={height + 20} data-plot-box data-rule9="scatter" style={{ display: 'block' }}
            onMouseMove={e => {
              const r = e.currentTarget.getBoundingClientRect()
              const b = nearest(e.clientX - r.left, e.clientY - r.top)
              setTip(b)
              const i = b ? series[b.k].idx[b.j] : null
              if (i !== hover) onHover(i)
            }}
            onMouseLeave={() => { setTip(null); onHover(null) }}
            onClick={() => { if (tip) onPick(series[tip.k].idx[tip.j]) }}>
            <line x1={x(t0)} x2={x(t1)} y1={Y(0)} y2={Y(0)} stroke="var(--grey-200, #e5e7eb)" />
            <line x1={x(t0)} x2={x(t1)} y1={Y(1)} y2={Y(1)} stroke="var(--grey-200, #e5e7eb)" strokeDasharray="2 3" />
            <text x={x(t0) + 2} y={Y(1) - 1} style={{ fontSize: 9, fill: 'var(--muted-2)' }}>each series' max</text>
            <text x={x(t0) + 2} y={Y(0) - 2} style={{ fontSize: 9, fill: 'var(--muted-2)' }}>min</text>
            {shownK.map(k => <path key={series[k].key} d={paths[k]} fill={series[k].colour} fillOpacity={0.75} data-series={series[k].key} data-testid={`${testid}-series`} />)}
            {marked.map(m => <circle key={m.k} cx={m.px} cy={m.py} r={5} fill="none" stroke="var(--amber)" strokeWidth={2} data-testid={`${testid}-marked`} />)}
            <TimeAxis x={x} y={height + 2} t0={t0} t1={t1} n={7} ends />
          </svg>
        )}
        {tip && tipSeries && tipValue !== null && (
          <div className="mono small" data-testid={`${testid}-tip`} style={{
            position: 'absolute', left: Math.min(Math.max(0, tip.px + 10), Math.max(0, w - 230)), top: Math.max(0, tip.py - 34), pointerEvents: 'none',
            background: 'var(--surface, #fff)', border: '1px solid var(--grey-200, #e5e7eb)', borderRadius: 4, padding: '2px 6px', whiteSpace: 'nowrap', boxShadow: '0 1px 3px rgba(0,0,0,.12)',
          }}>
            <i style={{ display: 'inline-block', width: 8, height: 8, background: tipSeries.colour, marginRight: 4 }} />
            {tipSeries.label}: <b>{tipSeries.fmt(tipValue)}{tipSeries.unit ? ` ${tipSeries.unit}` : ''}</b>
            {tipTime !== null ? ` · at ${fmtHours(tipTime, 3)}` : ''} · event #{tipSeries.idx[tip.j] + 1}
          </div>
        )}
      </div>
      <SeriesLegend series={legend} shown={shown} onToggle={onToggle} testid={`${testid}-legend`} note={(
        <span className="muted row" style={{ gap: 4, alignItems: 'center' }}>
          each series drawn 0–1 over its own range (shown beside its name)
          <InfoTip title="Reading this plot">
            Each point is {what}, placed at the event's time on the same axis as the signal above. The series have
            different units, so each is stretched to fill the plot from its own smallest value (bottom) to its own
            largest (top): compare the shapes over time, not the heights between series. Hover a point for its real
            value and unit; hover or click it to mark that event on the signal.
          </InfoTip>
        </span>
      )} />
    </div>
  )
}
