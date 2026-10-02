/* SpanSet view (fixup-h). Thumbnail: every span marked on the full trace. Settings page: that, with the spans
 * clickable, plus the SLIDESHOW of the spans (U8) and a duration distribution.
 *
 * Three findings this view exists to respect (QUESTIONS.md Round 7):
 *  - a span's events are found by SAMPLE RANGE, never by a window index (the bridge counts them, serialize.py);
 *  - overlapping windows are shared context, not double-counting, so overlapping bands are drawn as they are and
 *    never deduplicated — where the detector names its falls, the fall is drawn darker inside its window;
 *  - too many spans to draw one by one are bucketed into a density ribbon (the Explore overview's answer), and
 *    the plot says that is what it did. */
import { useMemo, type ReactNode } from 'react'
import type { SpansetPayload } from '../../api'
import { EnvelopePath } from '../../charts/primitives'
import { makeY } from '../../charts/scale'
import { EventSlideshow, Histogram, type SlideEvent, type SlideSort, type SlideTrace } from '../../kit'
import { fmtDuration, fmtHours } from '../../state'
import { Empty, finiteRange, fmtN, type ViewCtx } from './common'

/** spans closer together than this many pixels on average are drawn as a density ribbon */
const DENSE_PX = 3

function chipOf(label: string | null | undefined): string | null {
  if (!label) return null
  // a detector may pack provenance into its label ("onset=…;trough=…;sharkfin"): the chip is the last plain word
  const parts = label.split(';').filter(s => !s.includes('='))
  const text = parts.length ? parts[parts.length - 1] : label.includes('=') ? null : label
  return text && text.length <= 18 ? text : null
}

export function SpanSetView({ p, ctx, selected, onSelect }: { p: SpansetPayload; ctx: ViewCtx; selected?: number | null; onSelect?: (i: number) => void }) {
  const n = p.start_s.length
  const dense = n > ctx.width / DENSE_PX
  const gr = ctx.ghost && ctx.ghost.t.length ? finiteRange(ctx.ghost.v) : null
  const yG = gr ? makeY(gr[0], gr[1], ctx.height) : null
  const [r0, r1] = ctx.x.range()
  const density = useMemo(() => {
    if (!dense) return null
    const cols = Math.max(1, Math.floor((r1 - r0) / 3))
    const counts = new Array(cols).fill(0)
    const t0 = ctx.x.invert(r0), t1 = ctx.x.invert(r1)
    for (let i = 0; i < n; i++) {
      const a = Math.max(0, Math.floor(((p.start_s[i] - t0) / (t1 - t0)) * cols)), b = Math.min(cols - 1, Math.floor(((p.end_s[i] - t0) / (t1 - t0)) * cols))
      for (let k = a; k <= b; k++) counts[k]++
    }
    return { cols, counts, max: Math.max(1, ...counts) }
  }, [dense, n, p.start_s, p.end_s, r0, r1, ctx.x])
  const band = (i: number) => {
    const x0 = Math.max(r0, ctx.x(p.start_s[i])), x1 = Math.min(r1, ctx.x(p.end_s[i]))
    if (x1 < r0 || x0 > r1) return null
    const on = selected === i
    const impure = (p.window_counts?.[i] ?? 1) > 1
    const core = p.marks ? [ctx.x(p.marks.onset_s[i]), ctx.x(p.marks.extremum_s[i])] : null
    return (
      <g key={i} onClick={onSelect ? () => onSelect(i) : undefined} style={onSelect ? { cursor: 'pointer' } : undefined} data-span={i} data-testid={onSelect ? `span-band-${i}` : undefined}>
        <rect x={x0} y={0} width={Math.max(2, x1 - x0)} height={ctx.height} fill={impure ? 'var(--band-artifact)' : 'var(--band-detected)'} stroke={on ? 'var(--amber)' : 'none'} strokeWidth={on ? 2 : 0}>
          <title>{`#${i + 1} · ${(p.end_s[i] - p.start_s[i]).toFixed(1)} s${p.scores?.[i] != null ? ` · score ${p.scores[i]!.toFixed(3)}` : ''}${impure ? ` · holds ${p.window_counts![i]} ${p.window_count_of ?? 'events'}` : ''}`}</title>
        </rect>
        <rect x={x0} y={0} width={Math.max(2, x1 - x0)} height={3} rx={2} fill={on ? 'var(--amber)' : impure ? 'var(--red)' : 'var(--blue)'} />
        {core && <rect x={Math.min(core[0], core[1])} y={3} width={Math.max(1.5, Math.abs(core[1] - core[0]))} height={ctx.height - 3} fill={impure ? 'var(--red)' : 'var(--blue)'} fillOpacity={0.22} pointerEvents="none" />}
      </g>
    )
  }
  const selX = selected != null && selected >= 0 && selected < n ? ctx.x((p.start_s[selected] + p.end_s[selected]) / 2) : null
  return (
    <>
      <svg width={ctx.width} height={ctx.height} data-render="spanset" data-dense={dense ? '1' : '0'} data-plot-box data-rule9="ghost">
        {density && density.counts.map((c, k) => c ? <rect key={k} x={r0 + k * 3} y={0} width={3} height={ctx.height} fill="var(--blue)" fillOpacity={0.12 + 0.6 * (c / density.max)} /> : null)}
        {ctx.ghost && yG && <g data-trace><EnvelopePath t={ctx.ghost.t} v={ctx.ghost.v} x={ctx.x} y={yG} stroke="var(--trace-ghost)" testid="ghost" /></g>}
        {!dense && <g className="span-bands" data-testid="span-bands">{p.start_s.map((_, i) => band(i))}</g>}
        {dense && selected != null && band(selected)}
        {selX !== null && <path d={`M${selX - 5} ${ctx.height} L${selX + 5} ${ctx.height} L${selX} ${ctx.height - 7} Z`} fill="var(--amber)" data-testid="span-selected-caret" />}
        <text x={ctx.width - 6} y={ctx.height - 5} textAnchor="end" fill="var(--muted-2)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>
          {p.n} span{p.n === 1 ? '' : 's'}{p.capped ? ` · the first ${n.toLocaleString()} drawn` : ''}{dense ? ` · density, up to ${density!.max} per 3 px` : ''}
        </text>
      </svg>
      {p.n === 0 && <Empty text="0 spans — this block found nothing on this span" />}
    </>
  )
}

/** The duration distribution of the spans drawn. */
export function DurationHistogram({ p }: { p: SpansetPayload }) {
  const dur = useMemo(() => p.start_s.map((s, i) => p.end_s[i] - s), [p.start_s, p.end_s])
  if (dur.length < 2) return <div className="muted mono small" data-testid="duration-histogram">{dur.length === 1 ? `one span · ${fmtDuration(dur[0])}` : 'no spans to distribute'}</div>
  const sorted = [...dur].sort((a, b) => a - b)
  const med = sorted[Math.floor(sorted.length / 2)]
  return (
    <div data-testid="duration-histogram">
      <Histogram values={dur} nBins={Math.min(24, Math.max(6, Math.round(Math.sqrt(dur.length))))} height={120} colour="var(--blue-200)" xLabel="span duration · s" format={v => String(+v.toPrecision(3))} label="span durations"
        markers={[{ x: med, label: `median ${fmtN(med)} s`, colour: 'var(--text-2)' }]} />
      <div className="muted mono small">{dur.length.toLocaleString()} spans · {fmtN(sorted[0])} – {fmtN(sorted[sorted.length - 1])} s{p.capped ? ` · of ${p.n.toLocaleString()} (the payload caps the list)` : ''}</div>
    </div>
  )
}

/** a bare span is drawn with at least this many samples of the channel either side */
const MIN_CONTEXT_SAMPLES = 20

export const SPAN_SORTS: SlideSort[] = [
  { value: 'score', label: 'score', descending: true },
  { value: 'time', label: 'time' },
  { value: 'duration', label: 'duration', descending: true },
]

/** The payload's spans as slideshow events. A span that is already a window around its event (the detector named
 *  an onset and an extremum inside it) is drawn as it is; a bare span gets half its own length of context each
 *  side, clipped to the run's span, because a fall cropped to onset→trough is not a picture of the event. */
export function spanEvents(p: SpansetPayload, t0: number, t1: number): SlideEvent[] {
  const of = p.window_count_of === 'falls' ? 'falls' : 'spans'
  return p.start_s.map((s, i) => {
    const e = p.end_s[i]
    const pad = p.marks ? 0 : Math.max(MIN_CONTEXT_SAMPLES / p.fs, 0.5 * (e - s))
    const chip = chipOf(p.labels?.[i])
    const score = p.scores?.[i] ?? null
    return {
      id: String(i), title: `#${i + 1}`, chip: chip ? { text: chip } : undefined,
      band: p.marks ? null : [s, e], onset: p.marks?.onset_s[i] ?? null, extremum: p.marks?.extremum_s[i] ?? null,
      window: [Math.max(t0, s - pad), Math.min(t1, e + pad)],
      count: p.window_counts?.[i] ?? null, countOf: of,
      facts: `${fmtHours(s, 3)} · ${fmtDuration(e - s)}${score !== null ? ` · score ${fmtN(score)}` : ''}`,
      sort: { score, time: s, duration: e - s },
    }
  })
}

export function SpanSlideshow({ p, t0, t1, load, selected, onSelect, action, unit }: {
  p: SpansetPayload; t0: number; t1: number; load: (e: SlideEvent) => Promise<SlideTrace>
  selected: number | null; onSelect: (i: number) => void; action?: ReactNode; unit: string
}) {
  const events = useMemo(() => spanEvents(p, t0, t1), [p, t0, t1])
  const sorts = p.scores && p.scores.some(v => v !== null) ? SPAN_SORTS : SPAN_SORTS.filter(s => s.value !== 'score')
  if (!events.length) return null
  return (
    <EventSlideshow testid="event-slideshow" events={events} load={load} sorts={sorts} cap={10} columns={5} unit={unit}
      title={`Each of the ${p.capped ? `first ${events.length.toLocaleString()}` : events.length.toLocaleString()} spans`}
      selected={selected === null ? null : String(selected)} onSelect={id => onSelect(Number(id))} action={action}
      frameNote={p.marks ? 'the span as the block emitted it — its own window around the event; the onset is the blue mark and the extremum the red' : `the span (tinted) with half its own length of the source channel either side, and never fewer than ${MIN_CONTEXT_SAMPLES} samples`} />
  )
}
