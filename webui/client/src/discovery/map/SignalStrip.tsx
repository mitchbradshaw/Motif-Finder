/* discovery.map.SignalStrip — level 1's own trace of the channel (the scope strip's hourly means, `getOverview`) on
 * the rows' time axis, above them.
 *
 * tq-mappage (2026-10-25): the strip owned the read and handed its parent a range closure, held in state,
 * so the readout could query it. Now `useSignal` is the read, called by the channel level, which hands the strip what
 * to draw and computes the hovered bin's range itself; the strip only draws. */
import { useMemo } from 'react'
import { useSourced } from '../../api/seam'
import { getOverview } from '../../api/discovery'
import { extentOf } from '../../charts/domain'
import { LoadFailed } from '../chrome'

/** The signal strip's height: the height Explore › Signal draws its main trace at (SpanView's `H`), so structure reads
 *  the same here as there (the researcher, 2026-10-20). */
const SIGNAL_H = 150

/** The overview route's points as hours: one value per whole hour, or `n` points spread over them past its cap. */
function signalHours(values: number[], hours: number): number[] {
  const nFull = Math.max(1, Math.floor(hours))
  return values.length >= nFull ? values.map((_, i) => i + 0.5) : values.map((_, i) => values.length === 1 ? nFull / 2 : (i / (values.length - 1)) * (nFull - 1) + 0.5)
}

export type Signal =
  | { state: 'failed'; error: Error; reload: () => void }
  | { state: 'refused'; why: string }
  | { state: 'loading' }
  | { state: 'empty' }
  /** `at[i]` is the hour `values[i]` is drawn at; `extent` is over the finite values */
  | { state: 'drawn'; values: number[]; at: number[]; extent: [number, number] }

/** The channel's hourly means, read only while `on` (the strip is shown and the channel's timeline has answered). */
export function useSignal(dataset: string, channel: string, hours: number, on: boolean): Signal {
  const ov = useSourced(() => on ? getOverview(dataset, [channel]) : Promise.resolve({ data: null, source: 'live' as const }), [dataset, channel, on])
  const values = ov.data && 'data' in ov.data && ov.data.data ? ov.data.data[channel] ?? [] : null
  const at = useMemo(() => values ? signalHours(values, hours) : [], [values, hours])
  if (ov.error) return { state: 'failed', error: ov.error, reload: ov.reload }
  if (ov.data && 'refused' in ov.data && ov.data.refused) return { state: 'refused', why: ov.data.refused }
  if (!values) return { state: 'loading' }
  const extent = extentOf(values)
  return extent ? { state: 'drawn', values, at, extent } : { state: 'empty' }
}

export function SignalStrip({ signal, channel, units, binH, onHover, onLeave }: {
  signal: Signal; channel: string; units: number; binH: number; onHover: (bin: number) => void; onLeave: () => void
}) {
  const label = <span className="dsc-map-tlabel" title="the channel's own signal: one mean per hour, from the scope strip's read"><i className="sw" style={{ background: '#374151' }} />signal<span className="muted small"> · hourly mean</span></span>
  if (signal.state === 'failed') return <div className="dsc-map-trow dsc-map-signal" data-testid="map-signal-strip" data-state="failed">{label}<LoadFailed what={`the signal of ${channel}`} error={signal.error} onRetry={signal.reload} /></div>
  if (signal.state === 'refused') return <div className="dsc-map-trow dsc-map-signal note" data-testid="map-signal-strip" data-state="refused">{label}<span className="dsc-map-signal-note">signal not drawn: {signal.why}</span></div>
  if (signal.state === 'loading') return <div className="dsc-map-trow dsc-map-signal note" data-testid="map-signal-strip" data-state="loading">{label}<span className="dsc-map-signal-note">reading {channel}'s hourly means…</span></div>
  if (signal.state === 'empty') return <div className="dsc-map-trow dsc-map-signal note" data-testid="map-signal-strip" data-state="empty">{label}<span className="dsc-map-signal-note">signal not drawn: {channel} has no finite sample to average</span></div>
  const { values, at } = signal
  let [lo, hi] = signal.extent
  if (hi - lo < 1e-12) { lo -= 1; hi += 1 }
  const pad = (hi - lo) * 0.06, y0 = lo - pad, y1 = hi + pad
  const W = units * 10
  const xOf = (h: number) => (h / binH) * 10
  const yOf = (v: number) => SIGNAL_H - ((v - y0) / (y1 - y0)) * SIGNAL_H
  // a gap (NaN hour) breaks the line rather than being drawn through
  let d = '', pen = false
  at.forEach((h, i) => { const v = values[i]; if (!Number.isFinite(v)) { pen = false; return } d += `${pen ? 'L' : 'M'}${xOf(h).toFixed(2)} ${yOf(v).toFixed(2)}`; pen = true })
  return (
    <div className="dsc-map-trow dsc-map-signal" data-testid="map-signal-strip" data-state="drawn" style={{ height: SIGNAL_H }}>
      {label}
      <svg className="dsc-map-tsvg" viewBox={`0 0 ${W} ${SIGNAL_H}`} preserveAspectRatio="none" width="100%" height={SIGNAL_H} role="img" aria-label={`${channel} hourly means`}
        onMouseMove={e => { const r = e.currentTarget.getBoundingClientRect(); onHover(Math.max(0, Math.floor((e.clientX - r.left) / r.width * units))) }} onMouseLeave={onLeave}>
        <rect x={0} y={0} width={W} height={SIGNAL_H} fill="#fff" />
        <path d={d} fill="none" stroke="#374151" strokeWidth={1.2} vectorEffect="non-scaling-stroke" data-testid="map-signal-path" />
      </svg>
    </div>
  )
}
