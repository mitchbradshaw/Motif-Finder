/* ig-pages: the Trains block's three figures (`p.trains`, serialize.py `_trains`): the log-interval density with
 * its cut, the train-size histogram, and the timeline with each train as a bar over its events. The numbers are the
 * adapter's; the page draws them. Which train an event is in comes from the block's own `train_id` column. */
import { useMemo } from 'react'
import type { SpansetPayload, TrainsPayload } from '../../api'
import { TimeAxis } from '../../charts/primitives'
import { makeX } from '../../charts/scale'
import { useSize } from '../../charts/useSize'
import { Histogram, InfoTip, LineChart, type HistBin } from '../../kit'
import { fmtGap } from './IntervalTimeline'

const fmtN = (v: number | null | undefined) => v === null || v === undefined || !Number.isFinite(v) ? '—' : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2)

export function TrainsDensity({ tr }: { tr: TrainsPayload }) {
  const li = tr.log_isi
  const cut = li?.cut ?? null
  return (
    <div data-testid="trains-density" data-has-cut={cut !== null ? '1' : '0'}>
      <div className="bp-card-title">
        <h3 style={{ fontSize: 13 }}>How far apart the events are, on a log scale</h3>
        <span className="sg">{cut !== null ? `cut at ${fmtGap(cut)}: shorter gaps join a train` : li ? 'no valley: one hump, so no trains' : ''}</span>
        <InfoTip title="The log-interval density">If events come in trains, the gaps between them are of two kinds — short inside a train, long between — and this curve of the gaps (on a log scale) has two humps. The block cuts at the valley between them. One hump means no trains, said so rather than invented.</InfoTip>
      </div>
      {li
        ? <LineChart series={[{ label: 'density of log10 gap', colour: 'var(--trace-blue, #0a84ff)', points: li.edges.map((e, i) => [e, li.density[i]] as [number, number]) }]}
            markers={cut !== null && cut > 0 ? [{ x: Math.log10(cut), label: `cut ${fmtGap(cut)}`, colour: 'var(--amber)' }] : []}
            xFormat={v => fmtGap(10 ** v)} xLabel="gap between consecutive events (log scale)" yLabel="density" height={170} legend={false} testid="trains-density-plot" />
        : <div className="muted mono small" data-testid="trains-density-note">{tr.log_isi_note ?? 'no log-interval density'}</div>}
    </div>
  )
}

export function TrainSizes({ tr }: { tr: TrainsPayload }) {
  const bins = useMemo<HistBin[]>(() => {
    if (!tr.sizes.length) return []
    const lo = Math.min(...tr.sizes), hi = Math.max(...tr.sizes)
    return Array.from({ length: hi - lo + 1 }, (_, k) => ({ x0: lo + k - 0.5, x1: lo + k + 0.5, count: tr.sizes.filter(s => s === lo + k).length }))
  }, [tr])
  return (
    <div data-testid="trains-sizes">
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>How many events each train holds</h3><span className="sg">{tr.n_trains} train{tr.n_trains === 1 ? '' : 's'}{tr.lz !== null ? ` · LZ complexity of the sizes ${fmtN(tr.lz)}` : ''}</span></div>
      {bins.length
        ? <Histogram bins={bins} height={130} xLabel="events in the train" xTicks={Math.min(8, bins.length)} format={v => String(Math.round(v))} testid="trains-sizes-plot" />
        : <div className="muted mono small">no trains, so no sizes</div>}
    </div>
  )
}

/** Each train as a bar from its first event to its last, the events as ticks beneath (in no train: grey). */
export function TrainsTimeline({ p, t0, t1 }: { p: SpansetPayload; t0: number; t1: number }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width)
  const x = makeX(t0, t1, w, 8, 8)
  const col = p.features?.columns.indexOf('train_id') ?? -1
  const ids = col >= 0 && p.features?.matrix ? p.features.matrix.map(r => r[col]) : null
  const bars = useMemo(() => {
    if (!ids) return []
    const by = new Map<number, [number, number, number]>()
    ids.forEach((id, i) => {
      if (id === null || id < 0 || i >= p.start_s.length) return
      const b = by.get(id)
      by.set(id, b ? [Math.min(b[0], p.start_s[i]), Math.max(b[1], p.end_s[i]), b[2] + 1] : [p.start_s[i], p.end_s[i], 1])
    })
    return Array.from(by.entries()).sort((a, b) => a[1][0] - b[1][0])
  }, [ids, p])   // eslint-disable-line react-hooks/exhaustive-deps
  const h = 46
  return (
    <div data-testid="trains-timeline" data-n-bars={bars.length}>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Where the trains are</h3><span className="sg">each bar is one train, first event to last · grey ticks are in no train</span></div>
      {!ids
        ? <div className="muted mono small" data-testid="trains-timeline-note">{col < 0 ? 'this result carries no train_id column' : 'the per-event table is too large to ship, so the trains cannot be placed'}</div>
        : <div className="plot-surface" ref={ref} style={{ height: h + 20 }}>
            {size.width > 0 && <svg width={w} height={h + 20}>
              {bars.map(([id, [a, b, n]]) => (
                <rect key={id} x={x(a)} y={6} width={Math.max(2, x(b) - x(a))} height={14} rx={3} fill="#0a84ff" fillOpacity={0.25} stroke="#0a84ff" data-testid="trains-bar">
                  <title>{`train ${id} · ${n} events · ${fmtGap(b - a)} long`}</title>
                </rect>
              ))}
              {p.start_s.map((s, i) => <line key={i} x1={x(s)} x2={x(s)} y1={26} y2={40} stroke={ids[i] !== null && ids[i]! >= 0 ? '#0a84ff' : '#9ca3af'} strokeWidth={1.5} />)}
              <TimeAxis x={x} y={h + 2} t0={t0} t1={t1} n={7} ends />
            </svg>}
          </div>}
    </div>
  )
}

export function TrainsFigures({ p, t0, t1 }: { p: SpansetPayload; t0: number; t1: number }) {
  if (!p.trains) return null
  return (
    <>
      <TrainsDensity tr={p.trains} />
      <TrainSizes tr={p.trains} />
      <TrainsTimeline p={p} t0={t0} t1={t1} />
    </>
  )
}
