/* discovery.map.DatasetLevel — level 2: one dataset's channels, each optionally in 2 · 4 · 8 equal time slices.
 * tq-mappage (2026-10-25): moved out of MapPage.tsx; its column order and headers go through hideSort.tsx. */
import { useEffect, useMemo } from 'react'
import { useSourced } from '../../api/seam'
import { getMapDataset } from '../../api/discovery'
import type { DiscMapRow } from '../../api'
import { LoadFailed, Loading, Refreshing } from '../chrome'
import { Cell, Legend, MutedCell, NOT_RUN, fmtH, rateOf, useMapRefresh, useShades, type Norm } from './common'
import { HideableHeader, TableRows, arrangeColumns, colId, orderRows, type MapView } from './hideSort'

export function DatasetLevel({ dataset, chunks, norm, view, onName, onChannel }: { dataset: string; chunks: number; norm: Norm; view: MapView; onName: (name: string, hours: number) => void; onChannel: (ch: string) => void }) {
  const m = useSourced(() => getMapDataset(dataset, chunks), [dataset, chunks])
  const data = m.data
  const cellsOf = useMemo(() => (key: string) => data ? Object.values(data.cells[key] ?? {}).flat() : [], [data])
  const shade = useShades(data?.rows ?? [], cellsOf, norm)
  const running = !!data && data.rows.some(row => cellsOf(row.key).some(c => c.state === 'running'))
  useMapRefresh(m, running || !!data?.stale)
  // the crumb learns the dataset's name after the fact, in an effect: a parent setState during this render is a console error
  useEffect(() => { if (data) onName(data.name, data.hours) }, [data?.name, data?.hours]) // eslint-disable-line react-hooks/exhaustive-deps
  // site-map: a channel's slices move as one; hidden channels go to the right, hidden rows to the bottom
  const layout = useMemo(() => {
    if (!data) return null
    const key = data.key || dataset
    const sl = (rowKey: string, ch: string) => data.cells[rowKey]?.[ch] ?? []
    const cols = arrangeColumns(data.channels, key, data.rows, sl, view)
    const shownCells = (r: DiscMapRow) => cols.shown.flatMap(c => sl(r.key, c.name))
    const rows = orderRows(data.rows, view, r => shownCells(r).map(rateOf), r => shownCells(r).reduce((s, c) => s + c.count, 0))
    return { key, cols, rows, sl }
  }, [data, view, dataset])
  if (m.error) return <LoadFailed what={`the map of ${dataset}`} error={m.error} onRetry={m.reload} />
  if (!data || !layout) return <Loading height={320} label={`counting the runs on ${dataset}`} />
  // the payload's own chunk count, not the prop: while the next read is in flight the old payload is still drawn
  const n = data.chunks
  const sliceH = (chHours: number) => chHours / n
  const { key, cols, rows, sl } = layout
  return (
    <>
      <Refreshing on={m.loading || !!data.stale} testid="map-refreshing" label={chunks !== n ? `re-slicing ${data.name} into ${chunks} chunk${chunks === 1 ? '' : 's'} per channel…` : running ? 're-counting · a run is still going' : data.stale ? 're-counting · this map is from before the last change' : `re-counting the runs on ${data.name}`} />
      <div className="dsc-map-wrap" data-testid="map-dataset-level" data-stale={m.loading || data.stale ? '1' : '0'} style={{ opacity: m.loading ? 0.55 : 1, transition: 'opacity 140ms' }}>
        <table className="dsc-map-table" data-testid="map-table">
          <thead>
            <tr>
              <th className="corner">{data.name} · {fmtH(data.hours)} · {n === 1 ? 'one cell per channel' : `${n} equal time slices per channel`}</th>
              {cols.shown.map(c => <HideableHeader key={c.name} id={colId(key, c.name)} name={c.name} what={c.name} view={view} className="link" colSpan={n}
                onClick={() => onChannel(c.name)} data-testid={`map-channel-${c.name}`} title={`${c.name} · ${fmtH(c.hours)} — open its timeline`} />)}
              {cols.hidden.map(c => <HideableHeader key={c.name} hidden id={colId(key, c.name)} name={c.name} what={c.name} view={view} />)}
            </tr>
          </thead>
          <tbody>
            <TableRows rows={rows} view={view} cells={(row, hidden) => <>
              {cols.shown.map(c => sl(row.key, c.name).map((cell, i) => {
                const where = n === 1 ? c.name : `${c.name} · slice ${i + 1} of ${n} (${fmtH(i * sliceH(c.hours))}–${fmtH((i + 1) * sliceH(c.hours))})`
                return <td key={`${c.name}-${i}`}><Cell muted={hidden} row={row} cell={cell} where={where} shade={shade(row.key, cell)} share={sliceH(c.hours) > 0 ? cell.hours / sliceH(c.hours) : 0} wide={n === 1} onClick={() => onChannel(c.name)} /></td>
              }))}
              {cols.hidden.map(c => { const cell = sl(row.key, c.name)[0] ?? NOT_RUN; return <td key={c.name} className="dsc-map-hiddencol"><MutedCell row={row} cell={cell} shade={shade(row.key, cell)} as="col" /></td> })}
            </>} />
          </tbody>
        </table>
      </div>
      <Legend level={2} />
    </>
  )
}
