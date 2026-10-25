/* discovery.map.ChannelLevel — level 1: one channel over the WHOLE recording in time bins, its own signal above the
 * rows. tq-mappage (2026-10-25): moved out of MapPage.tsx; it now owns the signal read (`useSignal`) and the readout
 * computes the hovered bin's range from it, and hover says what it is over instead of a sentinel row key. */
import { useEffect, useMemo, useState } from 'react'
import { Icon, cx } from '../../kit'
import { navigate } from '../../state'
import { useSourced } from '../../api/seam'
import { getMapChannel } from '../../api/discovery'
import type { DiscMapRow, DiscMapState, DiscMapTimeline } from '../../api'
import { extentOf, maxOf } from '../../charts/domain'
import { LoadFailed, Loading, Refreshing } from '../chrome'
import { Legend, STATE_WORDS, fmtH, rowTitle, useMapRefresh } from './common'
import { HideButton, orderRows, type MapView } from './hideSort'
import { SignalStrip, useSignal } from './SignalStrip'

/** the fill of an uncovered stretch at level 1, by its state (hatch for the never-run ones) */
const GAP_FILL: Record<DiscMapState, string> = {
  covered: 'none', not_run: 'url(#dsc-map-hatch)', not_reviewed: 'url(#dsc-map-hatch)', running: 'rgba(217, 119, 6, 0.35)', failed: 'rgba(239, 68, 68, 0.35)', discarded: '#d1d5db',
}
const opacityFor = (count: number, max: number) => count <= 0 ? 0 : 0.18 + 0.82 * Math.min(1, count / Math.max(1, max))

/** Nice tick positions in hours: whole hours up to three days, whole days after that. */
function ticksFor(hours: number): { h: number; label: string }[] {
  const steps = hours > 72 ? [24, 48, 120, 240, 480, 720, 1440] : [1, 2, 3, 6, 12, 24]
  const step = steps.find(s => hours / s <= 8) ?? steps[steps.length - 1]
  const out: { h: number; label: string }[] = []
  for (let h = 0; h <= hours + 1e-9; h += step) out.push({ h, label: hours > 72 ? `day ${Math.round(h / 24)}` : `${h} h` })
  if (out[out.length - 1].h < hours - step * 0.35) out.push({ h: hours, label: hours > 72 ? `day ${(hours / 24).toFixed(1)}` : `${hours.toFixed(1)} h` })
  return out
}

/** Why a level-1 bin can or cannot open the Runs browser: the bin's OWNING run must be in the open session, on the
 *  session's recording, on one of its channels, inside its section — the browser reads only that scope. */
function openability(data: DiscMapTimeline, row: DiscMapRow, bin: number): { ok: true; runKey: string } | { ok: false; why: string } {
  if (row.kind === 'human') return { ok: false, why: 'the human row has no detections to browse' }
  const owner = data.cells[row.key]?.owners[bin]
  const s = data.session
  if (!owner) return { ok: false, why: `nothing of ${row.label} is counted in this bin — there is no run to open` }
  if (owner.sessionId !== s.id) return { ok: false, why: `${row.label} here came from session ${row.sessionNames.join(', ') || '?'} — not the open session, whose Runs page cannot show it` }
  if (data.key !== s.recording) return { ok: false, why: `the open session is scoped to ${s.recording}, not ${data.name} — scope it there on Runs to browse these` }
  if (!s.channels.includes(data.channel)) return { ok: false, why: `${data.channel} is not one of the open session's channels (${s.channels.join(', ')})` }
  const t0 = bin * data.binH, t1 = Math.min(data.hours, (bin + 1) * data.binH)
  if (t1 <= s.section[0] || t0 >= s.section[1]) return { ok: false, why: `outside the open session's section (${fmtH(s.section[0])}–${fmtH(s.section[1])}) — widen it on Runs to browse here` }
  return { ok: true, runKey: owner.runKey }
}

type Hover = { kind: 'signal'; bin: number } | { kind: 'row'; key: string; bin: number }

export function ChannelLevel({ dataset, channel, binH, view, signal, onName }: { dataset: string; channel: string; binH: number; view: MapView; signal: boolean; onName: (name: string, hours: number) => void }) {
  const m = useSourced(() => getMapChannel(dataset, channel, binH), [dataset, channel, binH])
  const [hover, setHover] = useState<Hover | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const data = m.data
  // the signal is read once the timeline has answered, as when the strip read it itself
  const sig = useSignal(dataset, channel, data?.hours ?? 0, signal && !!data)
  const running = !!data && Object.values(data.cells).some(c => c.state === 'running' || c.states.includes('running'))
  useMapRefresh(m, running || !!data?.stale)
  useEffect(() => { if (data) onName(data.name, data.hours) }, [data?.name, data?.hours]) // eslint-disable-line react-hooks/exhaustive-deps
  // site-map: rows ordered by their counts per bin (level 1's columns are time and do not sort); hidden rows at the bottom
  const rows = useMemo(() => data
    ? orderRows(data.rows, view, r => data.cells[r.key]?.counts ?? [], r => (data.cells[r.key]?.counts ?? []).reduce((a, b) => a + b, 0))
    : null, [data, view])
  if (m.error) return <LoadFailed what={`the timeline of ${channel}`} error={m.error} onRetry={m.reload} />
  if (!data || !rows) return <Loading height={320} label={`binning ${channel} over the whole recording`} />
  // the payload's own bin width and count, not the props: the previous payload is drawn while the next loads
  const n = data.nBins, bh = data.binH
  // the drawing is in HOURS, so a last bin shorter than the rest is drawn shorter and the axis lines up with it
  const units = Math.max(1e-6, data.hours / bh)
  const binAt = (e: React.MouseEvent<SVGSVGElement>) => { const r = e.currentTarget.getBoundingClientRect(); return Math.max(0, Math.min(n - 1, Math.floor((e.clientX - r.left) / r.width * units))) }
  const ticks = ticksFor(data.hours)
  const readout = (() => {
    if (!hover) return `${data.name} · ${channel} · ${fmtH(data.hours)} in ${n} bins of ${bh} h — move over a row to read a bin; click a bin to open it in Runs`
    const t0 = hover.bin * bh, t1 = Math.min(data.hours, (hover.bin + 1) * bh)
    if (hover.kind === 'signal') {
      const r = sig.state === 'drawn' ? extentOf(sig.values.filter((_, i) => sig.at[i] >= t0 && sig.at[i] < t1)) : null
      return `${channel} · signal · ${fmtH(t0)}–${fmtH(t1)} · ${r ? `hourly means from ${r[0].toPrecision(4)} to ${r[1].toPrecision(4)}` : 'no whole hour averaged in this bin'}`
    }
    const row = data.rows.find(r => r.key === hover.key)!
    const cell = data.cells[row.key]
    const cov = cell.covered[hover.bin], st = cell.states[hover.bin]
    const what = row.kind === 'human' ? `${cell.counts[hover.bin]} marked` : `${cell.counts[hover.bin]} detection${cell.counts[hover.bin] === 1 ? '' : 's'}`
    const covText = st !== 'covered' ? STATE_WORDS[st] : cov >= 0.999 ? (row.kind === 'human' ? 'looked at throughout' : 'covered') : `${Math.max(1, Math.round(cov * 100))} % ${row.kind === 'human' ? 'looked at' : 'covered'}`
    const open = openability(data, row, hover.bin)
    return `${channel} · ${row.label} · ${fmtH(t0)}–${fmtH(t1)} · ${what} · ${covText}${open.ok ? ' · click to open in Runs' : row.kind === 'human' ? '' : ` · ${open.why}`}`
  })()
  const line = (row: DiscMapRow, hidden: boolean) => {
    const cell = data.cells[row.key]
    const max = Math.max(0, maxOf(cell.counts))
    const colour = row.kind === 'human' ? '#22a06b' : row.colour
    // one rect per contiguous uncovered stretch OF ONE STATE, not one per bin: a mostly-unrun 721-bin row stays light
    const gaps: { a: number; b: number; state: DiscMapState }[] = []
    for (let i = 0; i < n; i++) {
      if (cell.states[i] === 'covered') continue
      const last = gaps[gaps.length - 1]
      if (last && last.b === i && last.state === cell.states[i]) last.b = i + 1
      else gaps.push({ a: i, b: i + 1, state: cell.states[i] })
    }
    const w = (i: number) => Math.max(0, Math.min(10, (units - i) * 10))
    return (
      <div key={row.key} className={cx('dsc-map-trow', hidden && 'hidden')} data-testid={hidden ? 'map-timeline-row-hidden' : 'map-timeline-row'} data-row={row.key} data-state={cell.state}>
        <span className="dsc-map-tlabel" title={rowTitle(row)}>
          <span className="dsc-map-rowtext"><i className="sw" style={{ background: row.colour }} />{row.label}<span className="muted small"> · {cell.counts.reduce((a, b) => a + b, 0)}</span></span>
          <HideButton hidden={hidden} what={row.label} kind="row" testid={hidden ? `map-row-show-${row.key}` : `map-row-hide-${row.key}`} onClick={() => view.toggleRow(row.key)} />
        </span>
        <svg className="dsc-map-tsvg" viewBox={`0 0 ${units * 10} 10`} preserveAspectRatio="none" width="100%" height={hidden ? 5 : 14} role="img" aria-label={`${row.label} on ${channel} per ${bh} h`}
          onMouseMove={hidden ? undefined : e => setHover({ kind: 'row', key: row.key, bin: binAt(e) })}
          onMouseLeave={hidden ? undefined : () => setHover(h => (h?.kind === 'row' && h.key === row.key ? null : h))}
          onClick={hidden ? undefined : e => {
            const bin = binAt(e)
            const open = openability(data, row, bin)
            if (open.ok) navigate(`discovery/runs?run=${encodeURIComponent(open.runKey)}&ch=${encodeURIComponent(channel)}&at=${bin * bh}`)
            else setNote(open.why)
          }}>
          <rect x={0} y={0} width={units * 10} height={10} fill="#f3f4f6" />
          {gaps.map(g => <rect key={`g${g.a}`} x={g.a * 10} y={0} width={Math.max(0, Math.min(units, g.b) - g.a) * 10} height={10} fill={GAP_FILL[g.state]} data-testid="map-gap" data-state={g.state} />)}
          {cell.counts.map((c, i) => c > 0 ? <rect key={i} x={i * 10 + 0.3} y={0} width={Math.max(0.4, w(i) - 0.6)} height={10} fill={colour} opacity={opacityFor(c, max)} data-testid={hidden ? undefined : 'map-bin'} /> : null)}
        </svg>
      </div>
    )
  }
  return (
    <>
      <Refreshing on={m.loading || !!data.stale} testid="map-refreshing" label={binH !== bh ? `re-binning ${channel} at ${binH} h…` : running ? 're-counting · a run is still going' : data.stale ? 're-counting · this timeline is from before the last change' : `re-counting the runs on ${channel}`} />
      <svg width={0} height={0} style={{ position: 'absolute' }} aria-hidden><defs><pattern id="dsc-map-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#fff" /><rect width="2.5" height="6" fill="#e5e7eb" /></pattern></defs></svg>
      <div className="dsc-map-timeline" data-testid="map-timeline">
        {signal && <SignalStrip signal={sig} channel={channel} units={units} binH={bh}
          onHover={bin => setHover({ kind: 'signal', bin: Math.min(n - 1, bin) })} onLeave={() => setHover(h => (h?.kind === 'signal' ? null : h))} />}
        {rows.shown.map(row => line(row, false))}
        {rows.hidden.map(row => line(row, true))}
        <div className="dsc-map-axis mono">{ticks.map((t, i) => <span key={i} style={{ left: `${(t.h / data.hours) * 100}%` }} className={cx(i === 0 && 'first', t.h >= data.hours - 1e-9 && 'last')}>{t.label}</span>)}</div>
      </div>
      <div className="dsc-map-readout" data-testid="map-readout"><Icon name="eye" size={12} /> {readout}</div>
      {note && <div className="dsc-map-readout muted" data-testid="map-note">{note}</div>}
      <Legend level={1} />
    </>
  )
}
