/* night-analyse (the researcher, 2026-10-20: "too many histograms"): the Event shape page as pictures, top to
 * bottom —
 *   1. the events' motifs overlaid: every event's waveform z-scored on its own and aligned on its steepest-slope
 *      sample (the slope the rose reads), coloured early → late; at most MOTIF_CAP drawn, evenly sampled, said so;
 *   2. the rose (handed in, as before);
 *   3. the block's input signal over the span with every event on it, and beneath it on the SAME time axis
 *      3b. a scatter of the measures that used to be histograms, one series each, show / hide by checkbox;
 *      hovering or clicking a point marks that event on the signal.
 * The histograms, the table and the rules stay behind the page's "more" toggle (registry.tsx).
 *
 * The waveforms are read from the recording (the same window route the slideshow reads): one read of the whole
 * span when it is short enough to come back sample for sample (≤ 16,000 samples), else one read per drawn event,
 * four at a time, at most MOTIF_CAP_PER_EVENT of them. The measures are the payload's feature table; nothing is
 * re-derived here. */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { SpansetPayload } from '../../api'
import { extentOf } from '../../charts/domain'
import { clamp, makeX, makeY, polylinePath, type XScale } from '../../charts/scale'
import { useSize } from '../../charts/useSize'
import { InfoTip, type SlideTrace } from '../../kit'
import { fmtHours } from '../../state'
import { labelOf, unitOf } from '../EventFeatures'
import { alignOnSteepest, evenSample, rampColour, type Aligned } from './eventFigures'
import { MultiScatter, SERIES_COLOURS, useMarkedEvent, useSeriesToggle, type ScatterSeries } from './MultiScatter'
import { SpanSetView } from './SpanSetView'
import { Surface, fmtN, loadWindow, type ProcessProps } from './common'

export const MOTIF_CAP = 300
export const MOTIF_CAP_PER_EVENT = 100
/** the window route returns every sample up to 2 × 8000 */
const ONE_READ_SAMPLES = 16000

/** feature columns that are bookkeeping, not a measure to plot */
const NOT_A_MEASURE = (c: string) => c.endsWith('_idx') || c === 'polarity' || c === 'group' || c === 'family'
const DEFAULT_SHOWN = ['event_amplitude_mv', 'duration_s', 'max_slope_mv_s']

/** the measure scatter's legend and tip: three significant figures, no trailing zeros (0.5, not fmtN's 0.500) */
const short = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : String(+v.toPrecision(3)))

/** The time an event sits at on the shared axis: its onset where the bridge names one, else its span's start. */
const eventTime = (p: SpansetPayload, i: number) => p.marks?.onset_s[i] ?? p.start_s[i]

type Motifs = { state: 'loading'; done: number; of: number } | { state: 'error'; message: string } | { state: 'ready'; rows: { i: number; a: Aligned }[]; perEvent: boolean; decimated: number }

/** Read and align the drawn events' waveforms. */
function useMotifs(p: SpansetPayload, rec: number, t0: number, t1: number, flip: boolean): { motifs: Motifs; picks: number[]; order: number[] } {
  const n = p.start_s.length
  const order = useMemo(() => Array.from({ length: n }, (_, i) => i).sort((a, b) => p.start_s[a] - p.start_s[b] || a - b), [p, n])
  const oneRead = (t1 - t0) * p.fs <= ONE_READ_SAMPLES
  const picks = useMemo(() => evenSample(n, oneRead ? MOTIF_CAP : MOTIF_CAP_PER_EVENT).map(k => order[k]), [n, order, oneRead])
  const [motifs, setMotifs] = useState<Motifs>({ state: 'loading', done: 0, of: picks.length })
  useEffect(() => {
    let live = true
    const range = (i: number): [number, number] | null => (p.marks ? [p.marks.onset_s[i], p.marks.extremum_s[i]] : null)
    const cut = (tr: SlideTrace, i: number) => {
      const s = p.start_s[i], e = p.end_s[i]
      const t: number[] = [], v: (number | null)[] = []
      for (let k = 0; k < tr.t.length; k++) if (tr.t[k] >= s - 1e-9 && tr.t[k] <= e + 1e-9) { const y = tr.v[k]; t.push(tr.t[k]); v.push(flip && y !== null ? -y : y) }
      return alignOnSteepest(t, v, range(i))
    }
    setMotifs({ state: 'loading', done: 0, of: picks.length })
    if (!picks.length) { setMotifs({ state: 'ready', rows: [], perEvent: false, decimated: 0 }); return }
    const perEvent = async () => {
      const rows: { i: number; a: Aligned }[] = []
      let next = 0, done = 0, decimated = 0
      const worker = async () => {
        while (live && next < picks.length) {
          const i = picks[next++]
          const tr = await loadWindow(rec, p.start_s[i], Math.max(p.end_s[i], p.start_s[i] + 1 / p.fs), 2000)
          if (tr.decimated) decimated++
          const a = cut(tr, i)
          if (a) rows.push({ i, a })
          done++
          if (live && done % 10 === 0) setMotifs({ state: 'loading', done, of: picks.length })
        }
      }
      await Promise.all([worker(), worker(), worker(), worker()])
      return { rows, decimated }
    }
    const run = async () => {
      if (oneRead) {
        const tr = await loadWindow(rec, t0, t1, 8000)
        if (!tr.decimated) {
          const rows = picks.map(i => ({ i, a: cut(tr, i) })).filter((r): r is { i: number; a: Aligned } => r.a !== null)
          return { rows, perEvent: false, decimated: 0 }
        }
      }
      return { ...(await perEvent()), perEvent: true }
    }
    run().then(r => { if (live) setMotifs({ state: 'ready', ...r }) },
      e => { if (live) setMotifs({ state: 'error', message: e instanceof Error ? e.message : String(e) }) })
    return () => { live = false }
  }, [p, rec, t0, t1, picks, oneRead, flip])
  return { motifs, picks, order }
}

/** 1. The motif overlay. */
function MotifOverlay({ p, rec, t0, t1, mark, flip }: { p: SpansetPayload; rec: number; t0: number; t1: number; mark: number | null; flip: boolean }) {
  const { motifs, picks, order } = useMotifs(p, rec, t0, t1, flip)
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width), h = 170
  const n = p.start_s.length
  const drawn = motifs.state === 'ready' ? motifs.rows : []
  const geom = useMemo(() => {
    // each `dt` runs earliest → latest, so the x extent is that of the first and last offsets
    const t = extentOf(drawn.map(({ a }) => a.dt[0]), drawn.map(({ a }) => a.dt[a.dt.length - 1]))
    const z = extentOf(...drawn.map(({ a }) => a.z)) ?? [Infinity, -Infinity]
    return t && t[0] < t[1] ? { lo: t[0], hi: t[1], zlo: Math.max(-6, z[0]), zhi: Math.min(6, z[1]) } : null
  }, [drawn])
  // the colour is the event's place in time over the whole set (earliest → latest), not its place among the drawn
  const rank = useMemo(() => new Map(order.map((i, k) => [i, n > 1 ? k / (n - 1) : 0])), [order, n])
  const path = (a: Aligned, x: XScale, y: XScale) => polylinePath(a.dt, a.z.map(z => (z === null ? null : clamp(z, -6, 6))), x, y)
  const words = motifs.state === 'ready'
    ? `${drawn.length.toLocaleString()} of ${n.toLocaleString()} event${n === 1 ? '' : 's'} drawn${picks.length < n ? `, evenly sampled through time (at most ${motifs.perEvent ? MOTIF_CAP_PER_EVENT : MOTIF_CAP})` : ''}${picks.length > drawn.length ? ` · ${picks.length - drawn.length} with no finite samples, not drawn` : ''}${motifs.decimated ? ` · ${motifs.decimated} long enough to come back as a min/max envelope` : ''}`
    : ''
  const marked = mark !== null ? drawn.find(r => r.i === mark) ?? null : null
  return (
    <div data-testid="motif-overlay" data-state={motifs.state} data-drawn={drawn.length}>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>The events' shapes, overlaid</h3>
        <span className="sg row" style={{ gap: 4, alignItems: 'center' }}>each z-scored, aligned on its steepest slope
          <InfoTip title="How the shapes are drawn">
            Every event's waveform is read from the recording over its own span, scaled on its own (z-score: its mean
            subtracted, divided by its standard deviation) so a small event and a big one can be compared by shape,
            and slid in time so that the sample where it changes fastest (its steepest slope, the one the rose below
            measures) sits at 0. Colour is the event's place in time over the whole span: earliest blue, latest amber.
            With many events, at most {MOTIF_CAP} are drawn, picked evenly through time.
          </InfoTip>
        </span>
      </div>
      <div className="plot-surface" ref={ref} style={{ height: h + 18, position: 'relative' }}>
        {motifs.state === 'loading' && <div className="an-plot-empty" data-testid="motif-overlay-loading">reading the events' waveforms{motifs.of > 10 ? ` · ${motifs.done} of ${motifs.of}` : ''}…</div>}
        {motifs.state === 'error' && <div className="callout warn small" data-testid="motif-overlay-error" style={{ margin: 8 }}>the waveforms could not be read: {motifs.message}</div>}
        {motifs.state === 'ready' && !geom && <div className="an-plot-empty" data-testid="motif-overlay-empty">{n ? 'no event has finite samples to draw' : 'no events: the step before found none on this span'}</div>}
        {motifs.state === 'ready' && geom && size.width > 0 && (() => {
          const x = makeX(geom.lo, geom.hi, w, 46, 10)
          const y = makeY(geom.zlo, geom.zhi, h, 6, 6)
          return (
            <svg width={w} height={h + 18} data-plot-box data-rule9="overlay" style={{ display: 'block' }}>
              <line x1={x(0)} x2={x(0)} y1={0} y2={h} stroke="var(--muted-2)" strokeDasharray="3 3" />
              <text x={x(0) + 4} y={11} style={{ fontSize: 9.5, fill: 'var(--muted)' }}>steepest slope</text>
              {drawn.map(({ i, a }) => <path key={i} d={path(a, x, y)} fill="none" stroke={rampColour(rank.get(i) ?? 0)} strokeOpacity={drawn.length > 60 ? 0.35 : 0.65} strokeWidth={1} data-testid="motif-line" />)}
              {marked && <path d={path(marked.a, x, y)} fill="none" stroke="var(--text)" strokeWidth={2.2} data-testid="motif-marked" />}
              <text x={42} y={y(geom.zhi) + 8} textAnchor="end" style={{ fontSize: 9.5, fill: 'var(--muted)' }}>{fmtN(geom.zhi)}σ</text>
              <text x={42} y={y(geom.zlo)} textAnchor="end" style={{ fontSize: 9.5, fill: 'var(--muted)' }}>{fmtN(geom.zlo)}σ</text>
              <text x={46} y={h + 14} style={{ fontSize: 9.5, fill: 'var(--muted-2)' }}>{fmtN(geom.lo)} s</text>
              <text x={w - 10} y={h + 14} textAnchor="end" style={{ fontSize: 9.5, fill: 'var(--muted-2)' }}>+{fmtN(geom.hi)} s from the steepest slope</text>
            </svg>
          )
        })()}
      </div>
      <div className="row mono small" style={{ gap: 8, alignItems: 'center', flexWrap: 'wrap' }} data-testid="motif-overlay-key">
        <span className="row" style={{ gap: 4, alignItems: 'center' }}>early
          <span style={{ display: 'inline-block', width: 90, height: 8, borderRadius: 2, background: `linear-gradient(90deg, ${[0, 0.33, 0.67, 1].map(rampColour).join(', ')})` }} />
          late</span>
        {n > 0 && <span className="muted">{fmtHours(p.start_s[0], 2)} → {fmtHours(p.start_s[n - 1], 2)}</span>}
        <span className="muted">{words}</span>
        {flip && <span data-testid="motif-overlay-flipped">drawn upside down from the recording, as the inverted signal below (this block is told the chain inverted it)</span>}
        {marked && <span>black = the event marked below (#{marked.i + 1})</span>}
      </div>
    </div>
  )
}

/** The measure series of a feature table: one per numeric measure column, in the table's order. */
export function measureSeries(p: SpansetPayload): ScatterSeries[] {
  const f = p.features
  if (!f || !f.matrix) return []
  const n = Math.min(p.start_s.length, f.matrix.length)
  const idx = Array.from({ length: n }, (_, i) => i)
  const t = idx.map(i => eventTime(p, i))
  return f.columns.map((c, k) => ({ c, k })).filter(({ c }) => !NOT_A_MEASURE(c))
    .map(({ c, k }) => ({ c, k, v: idx.map(i => f.matrix![i][k]) }))
    .filter(s => s.v.some(v => v !== null))
    .map((s, j) => ({ key: s.c, label: labelOf(s.c), colour: SERIES_COLOURS[j % SERIES_COLOURS.length], unit: unitOf(s.c), fmt: short, idx, t, v: s.v }))
}

/** The Event shape page's figures; `rose` is the rose card as the page already draws it. */
export function EventShapeFigures({ q, p, rose }: { q: ProcessProps; p: SpansetPayload; rose: ReactNode }) {
  const { mark, hover, picked, setHover, pick } = useMarkedEvent()
  const series = useMemo(() => measureSeries(p), [p])
  const [keys, defaults] = useMemo(() => {
    const k = series.map(s => s.key), d = k.filter(c => DEFAULT_SHOWN.includes(c))
    return [k, d.length ? d : k.slice(0, 3)]
  }, [series])
  const { shown, toggle } = useSeriesToggle(keys, defaults)
  const { t0, t1 } = q.ctx
  return (
    <div className="stack" style={{ gap: 10 }} data-testid="event-shape-figures">
      <MotifOverlay p={p} rec={q.source.recording_id} t0={t0} t1={t1} mark={mark} flip={q.step.params.upstream_inverted === true} />
      {rose ?? (
        <div className="callout warn small" data-testid="rose-missing" style={{ padding: '6px 10px', background: '#fff7e6', borderRadius: 6 }}>
          No rose: this step's result was restored from the cache without the block's printed record (the rose and the
          rules live there, and this machine does not hold it for this run). Re-run this step to draw the rose; the
          shapes above and the measures below are from the result itself.
        </div>
      )}
      <div>
        <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Where the events are, and what each measured</h3>
          <span className="sg">the block's input signal; beneath it each event's measures on the same time axis</span></div>
        <Surface height={120} t0={t0} t1={t1} testid="event-shape-signal" axis={false}>
          {(x, w) => <SpanSetView p={p} ctx={{ ...q.ctx, x, width: w, height: 120, interactive: true }} selected={mark} onSelect={pick} />}
        </Surface>
        {series.length === 0
          ? <div className="muted mono small" data-testid="measure-scatter-none">{p.features ? `${p.features.n_columns} measures per event · the table is too large to ship, so there is nothing to plot here` : 'this block returned its spans with no measures attached'}</div>
          : <MultiScatter series={series} t0={t0} t1={t1} shown={shown} onToggle={toggle} hover={mark} onHover={setHover} onPick={pick}
              testid="measure-scatter" what="one event's measure" />}
        {mark !== null && <div className="mono small" data-testid="event-shape-marked">event #{mark + 1} at {fmtHours(eventTime(p, mark), 3)} marked on the signal{picked !== null && hover === null ? ' · click it again to let go' : ''}</div>}
      </div>
    </div>
  )
}
