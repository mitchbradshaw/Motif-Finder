/* discovery.map.common — what the map's three levels share: a cell's words, shade and drawing, the legend, and the
 * level's re-read. tq-mappage (2026-10-25): split out of MapPage.tsx (675 lines, three levels in one file) unchanged. */
import { useEffect, useMemo, useRef } from 'react'
import { cx } from '../../kit'
import type { SourcedState } from '../../api/seam'
import type { DiscMapCell, DiscMapRow, DiscMapState } from '../../api'

/* ux-1018: a level answered only its first read. A run finishing or a verdict landing changed nothing on screen,
 * and a new slice count drew the OLD payload until the next read landed, with nothing to say a read was out — which
 * read as "the time chunks are not showing changes" (the researcher, 2026-10-18). Now a read in flight shows the
 * refreshing line and dims the table; the level re-reads when the window comes back into focus; and while any cell
 * is still running it re-reads every few seconds until none is. The server computes levels 1 and 2 on every read, so
 * the poll is tied to running cells, not left on. Level 3 (map-overview-cache) is the bridge's last computed answer:
 * it polls while that answer says it is pending or stale, and a poll then costs the bridge milliseconds. */
const MAP_POLL_MS = 5000
export function useMapRefresh<T>(m: SourcedState<T>, running: boolean) {
  const reload = useRef(m.reload)
  reload.current = m.reload
  useEffect(() => {
    const onFocus = () => { if (document.visibilityState === 'visible') reload.current() }
    window.addEventListener('focus', onFocus); document.addEventListener('visibilitychange', onFocus)
    return () => { window.removeEventListener('focus', onFocus); document.removeEventListener('visibilitychange', onFocus) }
  }, [])
  useEffect(() => {
    if (!running) return
    const t = window.setInterval(() => reload.current(), MAP_POLL_MS)
    return () => window.clearInterval(t)
  }, [running])
}

export type Norm = 'row' | 'map'
export const STATE_WORDS: Record<DiscMapState, string> = {
  covered: 'covered', not_run: 'not run here', running: 'still running here', failed: 'failed here', discarded: 'discarded (superseded) here', not_reviewed: 'not reviewed',
}
export const NOT_RUN: DiscMapCell = { count: 0, hours: 0, state: 'not_run' }

export const fmtH = (h: number) => h === 0 ? '0 h' : h >= 100 ? `${Math.round(h)} h` : h >= 10 ? `${h.toFixed(1)} h` : `${h.toFixed(2)} h`
export const rateOf = (c: DiscMapCell) => c.hours > 0 ? c.count / c.hours : null
/** the rate in words; a counted cell whose coverage rounds to nothing says so rather than dividing by it */
const perH = (c: DiscMapCell) => { const r = rateOf(c); return r == null ? 'under 0.001 h covered' : `${r.toFixed(2)} per h` }

/** The ramp: one hue for machine rows, the reference green for the human row; a covered cell that found nothing stays white. */
function fill(row: DiscMapRow, cell: DiscMapCell, shade: number): string | undefined {
  if (cell.state !== 'covered' || cell.count === 0) return undefined
  const a = 0.14 + 0.84 * Math.max(0, Math.min(1, shade))
  return row.kind === 'human' ? `rgba(34, 160, 107, ${a.toFixed(3)})` : `rgba(10, 132, 255, ${a.toFixed(3)})`
}

/** Row and map maxima of detections per covered hour. The human row is always its own yardstick: window
 *  labels over a few reviewed hours would otherwise set the map's maximum and wash every algorithm out. */
export function useShades(rows: DiscMapRow[], cellsOf: (key: string) => DiscMapCell[], norm: Norm) {
  return useMemo(() => {
    const rowMax: Record<string, number> = {}
    let mapMax = 0
    for (const r of rows) {
      let m = 0
      for (const c of cellsOf(r.key)) { const v = rateOf(c); if (v != null && v > m) m = v }
      rowMax[r.key] = m
      if (r.kind !== 'human' && m > mapMax) mapMax = m
    }
    return (key: string, cell: DiscMapCell) => {
      const v = rateOf(cell)
      if (v == null) return 1          // a count over coverage that rounds to nothing: as dark as the row gets
      const max = norm === 'map' && key !== 'human' ? mapMax : rowMax[key]
      return max > 0 ? v / max : 0
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, cellsOf, norm])
}

function cellTitle(row: DiscMapRow, where: string, cell: DiscMapCell): string {
  if (row.kind === 'human') {
    return cell.state === 'covered'
      ? `human · ${where} · ${cell.count} marked (${cell.interesting ?? 0} interesting, ${cell.seed ?? 0} seed) · ${fmtH(cell.hours)} looked at (${fmtH(cell.reviewedH ?? 0)} reviewed) · ${perH(cell)}`
      : `human · ${where} · not reviewed: no verdict and no reviewed span here`
  }
  if (cell.state !== 'covered') return `${row.label} · ${where} · ${STATE_WORDS[cell.state]}`
  return `${row.label} · ${where} · ${cell.count} detection${cell.count === 1 ? '' : 's'} · ${fmtH(cell.hours)} covered · ${perH(cell)}`
}

export function rowTitle(row: DiscMapRow): string {
  if (row.kind === 'human') return 'human annotations · interesting and seed verdicts · the fixed reference'
  const bits = [row.kind === 'seed' ? `seed ${row.seedId ?? ''}${row.cut != null ? ` · cut ${row.cut}` : ''}` : `template ${row.template ?? ''}${row.version != null ? ` v${row.version}` : ''}`]
  if (row.band) bits.push(`band ${row.band}`)
  // round A_2 · P3: a windowed application is its own row; say its scale and that its windows are stitched
  if (row.windows) bits.push(`${row.windows.label} · each window its own scale, stitched`)
  bits.push(`from session${row.sessionNames.length === 1 ? '' : 's'} ${row.sessionNames.join(', ') || '—'}`)
  bits.push(`${row.runs} channel run${row.runs === 1 ? '' : 's'}`)
  if (row.detail) bits.push(row.detail)
  return bits.join(' · ')
}

export function Legend({ level }: { level: 1 | 2 | 3 }) {
  return (
    <div className="dsc-map-legend" data-testid="map-legend" aria-label="legend">
      <span><i className="sw" style={{ background: 'rgba(10,132,255,0.14)' }} /><i className="sw" style={{ background: 'rgba(10,132,255,0.5)' }} /><i className="sw" style={{ background: 'rgba(10,132,255,0.98)' }} /> {level === 1 ? 'detections per bin, by row' : 'detections per covered hour'}</span>
      <span><i className="sw" style={{ background: 'rgba(34,160,107,0.6)' }} /> human row (always per row)</span>
      <span><i className="sw" /> ran · found nothing</span>
      <span><i className="sw hatch" /> not run here · human: not reviewed</span>
      <span><i className="sw running" /> running</span>
      <span><i className="sw failed" /> failed</span>
      <span><i className="sw discarded" /> discarded</span>
      {level !== 1 && <span><i className="sw bar" /> foot bar = share of the column covered</span>}
    </div>
  )
}

/** One shaded cell at levels 2 and 3. `share` is the covered fraction of the column, drawn as the foot bar. A cell of
 *  a hidden row (`muted`) keeps its shade, drawn small and dimmed, not clickable. */
export function Cell({ row, cell, where, shade, share, onClick, wide, muted }: { row: DiscMapRow; cell: DiscMapCell; where: string; shade: number; share: number; onClick?: () => void; wide?: boolean; muted?: boolean }) {
  if (muted) return <MutedCell row={row} cell={cell} shade={shade} as="row" />
  const title = cellTitle(row, where, cell)
  return (
    <button type="button" className={cx('dsc-map-cell', cell.state, wide && 'wide')} style={{ background: fill(row, cell, shade) }} title={title}
      data-testid="map-cell" data-state={cell.state} data-count={cell.count} data-hours={cell.hours} data-row={row.key} onClick={onClick} aria-label={title}>
      {/* partial coverage is a white track along the foot with a dark fill for the covered share — a 4 h run on a
          721 h channel is half a percent, so the fill keeps a minimum width and the track makes the gap visible */}
      {cell.state === 'covered' && share < 0.999 && <i className="cover-track"><i className="cover" style={{ width: `${Math.min(100, share * 100)}%` }} /></i>}
      {cell.state === 'discarded' && <span className="glyph">×</span>}
    </button>
  )
}

/** A cell of a hidden row or column: its shade kept, drawn small and dimmed, not clickable. */
export function MutedCell({ row, cell, shade, as }: { row: DiscMapRow; cell: DiscMapCell; shade: number; as: 'row' | 'col' }) {
  return <i className={cx('dsc-map-mcell', as, cell.state)} style={{ background: fill(row, cell, shade) }} data-testid="map-cell-muted" />
}
