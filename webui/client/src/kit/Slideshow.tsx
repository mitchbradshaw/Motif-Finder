/* The span slideshow (fixup-h, U8): one card per event, on `SmallMultiples`.
 *
 * Small multiples rather than an overlay, for the reason the researcher wrote down about their own data
 * (figures5.py): "an overlay hid the defect — a window holding three spikes drawn on top of four others that
 * also hold three looks like a busy family; it takes seeing the panels side by side to notice that every one of
 * them is a train."
 *
 * What a card carries, and the rule behind each:
 *  - the event's OWN samples at their own times. Nothing is resampled or interpolated; when the samples
 *    outnumber the pixels the trace is a min/max envelope and the card says so; when they are 3 px or more
 *    apart each one is dotted, so drawn resolution cannot pass for real resolution;
 *  - a y domain measured from the card's own trace, and a scale bar (Q15) — never a shared y;
 *  - the IMPURITY FLAG of the matplotlib contact sheets: a window holding more than one event turns red and its
 *    title says `[2 falls]`. It is the fastest "this detection is suspect" marker on the sheet;
 *  - a DASHED EDGE where the stored extent was set by the detector's fall-multiple cap rather than by the
 *    event's morphology (Q18): a capped edge and a measured edge are otherwise identical on screen;
 *  - a snippet whose stored array is not the length its indices claim says so instead of drawing a one-sample
 *    "fall" that reads as a bad detection.
 *
 * The slideshow is READ-ONLY. Selection is the only state; the one action a caller may pass is a hand-off to
 * Review. The moment this writes a verdict it IS Review, and there are two tools that disagree. */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ScaleBar } from '../charts/ScaleBar'
import { measuredDomain } from '../charts/domain'
import { useSize } from '../charts/useSize'
import { Chip } from './display'
import { fmtInt } from './hooks'
import { SmallMultiples } from './plots'
import { Dropdown, InfoTip } from './surfaces'

export interface SlideTrace {
  /** seconds, one per point — the samples' own times */
  t: number[]; v: (number | null)[]
  /** true when `t`/`v` are a min/max envelope of `nSource` samples rather than every sample */
  decimated: boolean; nSource: number
  /** the stored array is not the length its indices claim */
  mismatch?: { stored: number; claimed: number } | null
  error?: string
}
export interface SlideEvent {
  id: string
  title?: string
  chip?: { text: string; colour?: string }
  /** the event's own extent inside the window, in the trace's seconds */
  band?: [number, number] | null
  onset?: number | null; extremum?: number | null
  /** the window drawn, when it is narrower than the trace (a sequence frame inside a stored snippet) */
  window?: [number, number] | null
  /** how many events the window holds (by sample range); more than one is impure */
  count?: number | null; countOf?: string
  leftCapped?: boolean; rightCapped?: boolean
  /** one short line under the trace: "0.42 mV · 12 s" */
  facts?: string
  state?: { text: string; tone: 'green' | 'amber' | 'muted' }
  /** the values the sort options read */
  sort: Record<string, number | null | undefined>
  trace?: SlideTrace
}
export interface SlideSort { value: string; label: string; descending?: boolean }

const single = (word: string) => word.replace(/s$/, '')

/** One event's trace: real samples, its own domain, its marks. */
export function EventTrace({ trace, domain, event, height = 56, colour = 'var(--trace)', impure }: {
  trace: SlideTrace; domain: [number, number]; event: SlideEvent; height?: number; colour?: string; impure?: boolean
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width)
  const [w0, w1] = event.window ?? [trace.t[0] ?? 0, trace.t[trace.t.length - 1] ?? 1]
  const span = w1 > w0 ? w1 - w0 : 1
  const X = (t: number) => ((t - w0) / span) * w
  const Y = (v: number) => height - 2 - ((v - domain[0]) / ((domain[1] - domain[0]) || 1)) * (height - 4)
  const inWin = (i: number) => trace.t[i] >= w0 - 1e-9 && trace.t[i] <= w1 + 1e-9
  let d = '', pen = false, n = 0
  const pts: [number, number][] = []
  for (let i = 0; i < trace.t.length; i++) {
    const v = trace.v[i]
    if (v === null || v === undefined || !Number.isFinite(v) || !inWin(i)) { pen = false; continue }
    const px = X(trace.t[i]), py = Y(v)
    d += `${pen ? 'L' : 'M'}${px.toFixed(1)} ${py.toFixed(1)}`
    pen = true; n++; pts.push([px, py])
  }
  const dots = !trace.decimated && n > 1 && w / (n - 1) >= 3
  const edge = (x: number, key: string) => <line key={key} x1={x} x2={x} y1={0} y2={height} stroke="var(--amber)" strokeWidth={2} strokeDasharray="3 3" data-capped-edge={key} />
  return (
    <div ref={ref} style={{ height, flex: 1, minWidth: 0, background: impure ? 'var(--red-100, #fdeaea)' : '#f5f6f8', borderRadius: 5, overflow: 'hidden' }}>
      {size.width > 0 && (
        <svg width={w} height={height} role="img" aria-label={`${event.title ?? event.id}: ${n} points`} data-plot-box data-rule9="event" data-flat={pts.every(q => Math.abs(q[1] - pts[0][1]) < 0.5) ? "1" : "0"}
          data-points={n} data-decimated={trace.decimated ? '1' : '0'} data-domain={`${domain[0]},${domain[1]}`} style={{ display: 'block' }}>
          {event.band && <rect x={X(event.band[0])} width={Math.max(1, X(event.band[1]) - X(event.band[0]))} y={0} height={height} fill="var(--band-detected)" />}
          {event.onset != null && <line x1={X(event.onset)} x2={X(event.onset)} y1={0} y2={height} stroke="var(--blue)" strokeOpacity={0.7} />}
          {event.extremum != null && <line x1={X(event.extremum)} x2={X(event.extremum)} y1={0} y2={height} stroke="var(--red)" strokeOpacity={0.6} />}
          <g data-trace><path d={d} fill="none" stroke={impure ? 'var(--red)' : colour} strokeWidth={1.2} strokeLinejoin="round" /></g>
          {dots && <g data-sample-dots pointerEvents="none">{pts.map(([px, py], i) => <circle key={i} cx={px} cy={py} r={1.5} fill={impure ? 'var(--red)' : colour} />)}</g>}
          {event.leftCapped && edge(1, 'left')}
          {event.rightCapped && edge(w - 1, 'right')}
        </svg>
      )}
    </div>
  )
}

function Card({ event, trace, domain, colour, unit, selected, extra }: { event: SlideEvent; trace: SlideTrace | 'loading'; domain: [number, number] | null; colour: string; unit: string; selected: boolean; extra?: ReactNode }) {
  const impure = (event.count ?? 1) > 1
  const of = event.countOf ?? 'events'
  const H = 56
  return (
    <div className={`k-slide${impure ? ' impure' : ''}`} data-testid={`slide-${event.id}`} data-impure={impure ? '1' : '0'} data-selected={selected ? '1' : '0'}>
      <div className="r1">
        <b title={event.title ?? event.id}>{event.title ?? event.id}</b>
        {impure && <span className="flag" data-testid="impurity-flag" title={`this window holds ${event.count} ${of}, counted by sample range — depth and duration of a window with more than one are not one event's`}>[{event.count} {of}]</span>}
        {event.chip && <Chip size="sm" tone="outline" dot={event.chip.colour}>{event.chip.text}</Chip>}
        {extra && <span style={{ marginLeft: 'auto', flex: 'none' }} onClick={e => e.stopPropagation()} onKeyDown={e => e.stopPropagation()}>{extra}</span>}
      </div>
      <div style={{ display: 'flex', gap: 2, alignItems: 'stretch' }}>
        {trace === 'loading' ? <div className="skeleton" style={{ height: H, flex: 1, borderRadius: 5 }} />
          : trace.error ? <div className="k-slide-note" style={{ height: H }}>{trace.error}</div>
            : trace.mismatch ? <div className="k-slide-note" style={{ height: H }} data-testid="snippet-mismatch">stored array is {trace.mismatch.stored} samples, its indices claim {trace.mismatch.claimed} · not drawn: sliced by the indices this would be a 1-sample “fall”</div>
              : !domain ? <div className="k-slide-note" style={{ height: H }}>no finite samples in this window</div>
                : <><EventTrace trace={trace} domain={domain} event={event} height={H} colour={colour} impure={impure} /><ScaleBar domain={domain} height={H} unit={unit} /></>}
      </div>
      {event.facts && <div className="facts">{event.facts}</div>}
      {trace !== 'loading' && !trace.error && !trace.mismatch && (
        <div className="res" title={trace.decimated ? `${fmtInt(trace.nSource)} samples drawn as a min/max envelope: each column carries the true minimum and maximum of its samples` : 'every stored sample is drawn at its own time; nothing is interpolated'}>
          {trace.decimated ? `${fmtInt(trace.nSource)} samples · min/max envelope` : `${fmtInt(trace.nSource)} samples · every one drawn`}
        </div>
      )}
      {event.state && <div className={`state ${event.state.tone}`}>● {event.state.text}</div>}
    </div>
  )
}

export function EventSlideshow({ events, load, sorts, selected, onSelect, cap = 10, columns = 5, colour = 'var(--trace)', unit = 'mV', title = 'Each event', capRule, action, frameNote, cardExtra, testid = 'event-slideshow' }: {
  events: SlideEvent[]
  /** fetch an event's samples when the event does not carry them; cached per event id for the component's life */
  load?: (e: SlideEvent) => Promise<SlideTrace>
  sorts: SlideSort[]
  selected: string | null; onSelect: (id: string) => void
  cap?: number; columns?: number; colour?: string; unit?: string; title?: ReactNode
  /** how the detector capped an extent, for the count behind the info icon: "6 × fall" */
  capRule?: string
  /** the one action: a hand-off to Review */
  action?: ReactNode
  /** which extent the cards draw, in a few words: "the stored window" */
  frameNote?: string
  /** a control of the PAGE's own on each card (a scope tick). Never a verdict: the slideshow writes nothing. */
  cardExtra?: (e: SlideEvent) => ReactNode
  testid?: string
}) {
  const [sortKey, setSortKey] = useState(sorts[0]?.value ?? '')
  const sort = sorts.find(s => s.value === sortKey) ?? sorts[0]
  const sorted = useMemo(() => {
    if (!sort) return events
    const val = (e: SlideEvent) => { const v = e.sort[sort.value]; return v === null || v === undefined || !Number.isFinite(v) ? null : v }
    return [...events].sort((a, b) => {
      const x = val(a), y = val(b)
      if (x === null || y === null) return x === y ? 0 : x === null ? 1 : -1     // unmeasured last, either direction
      return sort.descending ? y - x : x - y
    })
  }, [events, sort])
  // a new event list (another run, another family) starts with an empty cache; a request still in flight for
  // the old list resolves into the old map and is never read
  const listKey = events.length ? `${events[0].id}:${events.length}` : ''
  const cache = useRef({ key: listKey, got: new Map<string, SlideTrace>(), asked: new Set<string>() })
  if (cache.current.key !== listKey) cache.current = { key: listKey, got: new Map(), asked: new Set() }
  const [, bump] = useState(0)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const traceOf = (e: SlideEvent): SlideTrace | 'loading' => {
    if (e.trace) return e.trace
    const c = cache.current
    const hit = c.got.get(e.id)
    if (hit) return hit
    if (!load) return { t: [], v: [], decimated: false, nSource: 0, error: 'no samples served for this event' }
    if (!c.asked.has(e.id)) {
      c.asked.add(e.id)
      load(e).then(tr => c.got.set(e.id, tr), err => c.got.set(e.id, { t: [], v: [], decimated: false, nSource: 0, error: String(err?.message ?? err) }))
        .finally(() => { if (alive.current) bump(k => k + 1) })
    }
    return 'loading'
  }

  const impure = events.filter(e => (e.count ?? 1) > 1).length
  const of = events.find(e => e.countOf)?.countOf ?? 'events'
  const capL = events.filter(e => e.leftCapped).length, capR = events.filter(e => e.rightCapped).length
  const capAny = events.filter(e => e.leftCapped || e.rightCapped).length
  const selectedIndex = selected === null ? null : sorted.findIndex(e => e.id === selected)
  return (
    <div data-testid={testid} data-n={events.length} data-impure={impure} data-capped={capAny}>
      <SmallMultiples testid={`${testid}-grid`} items={sorted} cap={cap} columns={columns} domain="per-panel" title={title}
        defaultSampled={events.length > 3 * cap}
        selectedIndex={selectedIndex !== null && selectedIndex >= 0 ? selectedIndex : null} onSelect={e => onSelect(e.id)}
        cellClass={e => ((e.count ?? 1) > 1 ? 'impure' : undefined)}
        headExtra={<>
          {sorts.length > 1 && <Dropdown size="sm" prefix="sort" value={sort?.value ?? ''} onChange={setSortKey} options={sorts.map(s => ({ value: s.value, label: s.label }))} testid={`${testid}-sort`} />}
          <InfoTip title="Reading the cards">
            Each card is one event on a y axis measured from its own trace; the bar at its right is a round size in {unit}, so compare sizes by the bars. Samples are drawn at their own times and never interpolated; where they outnumber the pixels the card says “min/max envelope”.
            {frameNote && <div style={{ marginTop: 6 }}>Extent drawn: {frameNote}.</div>}
            {capRule && <div style={{ marginTop: 6 }} data-testid="capped-count">
              <b>{capAny} of {events.length} events have an edge at the {capRule} cap</b> ({capL} left, {capR} right), drawn as a dashed amber edge. There the detector's fall-multiple backstop set the extent, not the event's own morphology — the card shows what was stored, which may be less than the event.
            </div>}
            <div style={{ marginTop: 6 }}>Click a card, or use ← →, to mark the event on the plot above. Nothing here writes a verdict.</div>
          </InfoTip>
        </>}
        render={(e, { yDomain: _ignored }) => {
          const tr = traceOf(e)
          const vals = tr === 'loading' ? [] : e.window ? tr.v.filter((_, i) => tr.t[i] >= e.window![0] && tr.t[i] <= e.window![1]) : tr.v
          const dom = tr === 'loading' ? null : measuredDomain(vals)
          return <Card event={e} trace={tr} domain={dom} colour={colour} unit={unit} selected={e.id === selected} extra={cardExtra?.(e)} />
        }} />
      <div className="k-slide-foot">
        {/* an absence or a defect is a RESULT and stays on the face (Q21); the explanation is behind the icon */}
        {impure > 0
          ? <span className="bad" data-testid="impure-count">{impure} of {events.length} windows hold more than one {single(of)} · drawn red</span>
          : events.length > 0 && <span data-testid="impure-count">every window holds one {single(of)}</span>}
        {capRule && capAny > 0 && <span data-testid="capped-face">{capAny} of {events.length} capped at {capRule} · dashed edge</span>}
        <span className="k-spacer" />
        {action}
      </div>
    </div>
  )
}
