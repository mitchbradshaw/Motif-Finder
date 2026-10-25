/* discovery.map.DatasetsLevel — level 3: every dataset with a Discovery run, its channels as columns. tq-mappage
 * (2026-10-25): moved out of MapPage.tsx; its column order and headers go through hideSort.tsx. */
import { Fragment, useMemo, useRef } from 'react'
import { Button, EmptyState } from '../../kit'
import { navigate } from '../../state'
import { useSourced } from '../../api/seam'
import { getMap } from '../../api/discovery'
import type { DiscMapRow } from '../../api'
import { LoadFailed, Loading, Refreshing } from '../chrome'
import { Cell, Legend, MutedCell, NOT_RUN, fmtH, rateOf, useMapRefresh, useShades, type Norm } from './common'
import { HideButton, HideableHeader, TableRows, arrangeColumns, colId, orderRows, type MapView } from './hideSort'
import { TopScrollbar } from './TopScrollbar'

export function DatasetsLevel({ norm, view, onDataset }: { norm: Norm; view: MapView; onDataset: (key: string, name: string) => void }) {
  const m = useSourced(getMap, [])
  const data = m.data
  const wrapRef = useRef<HTMLDivElement>(null)
  const cellsOf = useMemo(() => (key: string) => data ? data.datasets.flatMap(d => Object.values(d.cells[key] ?? {})) : [], [data])
  const shade = useShades(data?.rows ?? [], cellsOf, norm)
  // map-overview-cache: the overview is the bridge's last answer; while it is behind (none yet, or from before the
  // last change, or a run still going) the chip says so and the level re-reads until the recompute lands
  const behind = !!data && !!(data.pending || data.stale)
  useMapRefresh(m, behind)
  // site-map: the order of rows and of each dataset's channels, reading only the shown cells
  const layout = useMemo(() => {
    if (!data) return null
    const cellOf = (d: typeof data.datasets[number], rowKey: string, ch: string) => d.cells[rowKey]?.[ch] ?? NOT_RUN
    const shownDs = data.datasets.filter(d => !view.hiddenCols.has(d.key))
    const hiddenDs = data.datasets.filter(d => view.hiddenCols.has(d.key))
    const cols = new Map(shownDs.map(d => [d.key, arrangeColumns(d.channels, d.key, data.rows, (k, ch) => [cellOf(d, k, ch)], view)]))
    const shownCells = (r: DiscMapRow) => shownDs.flatMap(d => cols.get(d.key)!.shown.map(c => cellOf(d, r.key, c.name)))
    const rows = orderRows(data.rows, view, r => shownCells(r).map(rateOf), r => shownCells(r).reduce((s, c) => s + c.count, 0))
    return { shownDs, hiddenDs, cols, rows, cellOf }
  }, [data, view])
  if (m.error) return <LoadFailed what="the detection map" error={m.error} onRetry={m.reload} />
  if (!data || !layout) return <Loading height={320} label="counting every session's runs" />
  if (data.pending) return <><Refreshing on testid="map-refreshing" label="counting every session's runs for the first time — the map appears when the count is done" /><Loading height={320} label="counting every session's runs" /></>
  const total = data.datasets.length + data.withoutRuns.length
  const foot = (
    <div className="dsc-map-foot" data-testid="map-foot">
      {data.datasets.length} of {total} registered dataset{total === 1 ? '' : 's'} {data.datasets.length === 1 ? 'has' : 'have'} a finished Discovery run{data.datasets.length ? `: ${data.datasets.map(d => d.name).join(', ')}` : ''}.
      {data.withoutRuns.length > 0 && <> No run yet: {data.withoutRuns.map(d => d.name).join(', ')} — apply a template on Runs with the scope on that dataset to add it.</>}
      {data.heldOutOmitted.length > 0 && <> Held out, never shown: {data.heldOutOmitted.join(', ')}.</>}
    </div>
  )
  if (data.datasets.length === 0) {
    return <><EmptyState icon="grid" title="No Discovery run has finished on any dataset" caption="apply a template or run a seed search on the Runs page; its cells appear here when it finishes" testid="map-empty"
      action={<Button icon="layers" onClick={() => navigate('discovery/runs')}>Open Runs</Button>} />{foot}</>
  }
  const { shownDs, hiddenDs, cols, rows, cellOf } = layout
  return (
    <>
      <Refreshing on={m.loading || behind} testid="map-refreshing" label={data.running ? 're-counting · a run is still going' : data.stale ? `re-counting · this map is from before the last change${data.stale_since ? ` (${new Date(data.stale_since).toLocaleTimeString()})` : ''}` : 're-counting every session’s runs'} />
      <TopScrollbar target={wrapRef} />
      <div ref={wrapRef} className="dsc-map-wrap" data-stale={behind ? '1' : '0'} data-testid="map-wrap">
        <table className="dsc-map-table" data-testid="map-table">
          <thead>
            <tr>
              <th className="corner-pad" />
              {shownDs.map(d => { const cs = cols.get(d.key)!; return <Fragment key={d.file}><th className="ds" colSpan={cs.shown.length + cs.hidden.length} onClick={() => onDataset(d.key, d.name)} data-testid={`map-dataset-${d.key}`} title={`${d.name} · ${d.channels.length} channels · ${fmtH(d.hours)} — open its channels`}>
                {d.name} <span className="muted">· {d.channels.length} ch · {fmtH(d.hours)}</span>
                <HideButton what={d.name} kind="dataset" testid={`map-col-hide-${d.key}`} onClick={() => view.toggleCol(d.key)} />
              </th><th className="gap" /></Fragment> })}
              {hiddenDs.map(d => <th key={d.file} rowSpan={2} className="ch hidden ds-hidden" title={`${d.name} is hidden`} data-testid={`map-dataset-hidden-${d.key}`}>
                <HideButton hidden what={d.name} kind="dataset" testid={`map-col-show-${d.key}`} onClick={() => view.toggleCol(d.key)} /><span>{d.name}</span>
              </th>)}
            </tr>
            <tr>
              <th className="corner">{norm === 'map' ? 'shade · whole map' : 'shade · per row'}</th>
              {shownDs.map(d => { const cs = cols.get(d.key)!; return <Fragment key={d.file}>
                {cs.shown.map(c => <HideableHeader key={c.name} id={colId(d.key, c.name)} name={c.name} what={`${d.name} ${c.name}`} view={view} />)}
                {cs.hidden.map(c => <HideableHeader key={c.name} hidden id={colId(d.key, c.name)} name={c.name} what={`${d.name} ${c.name}`} view={view} />)}
                <th className="gap" />
              </Fragment> })}
            </tr>
          </thead>
          <tbody>
            <TableRows rows={rows} view={view} cells={(row, hidden) => <>
              {shownDs.map(d => { const cs = cols.get(d.key)!; return <Fragment key={d.file}>
                {cs.shown.map(c => {
                  const cell = cellOf(d, row.key, c.name)
                  return <td key={c.name}><Cell muted={hidden} row={row} cell={cell} where={`${d.name} ${c.name}`} shade={shade(row.key, cell)} share={c.hours > 0 ? cell.hours / c.hours : 0} onClick={() => onDataset(d.key, d.name)} /></td>
                })}
                {cs.hidden.map(c => { const cell = cellOf(d, row.key, c.name); return <td key={c.name} className="dsc-map-hiddencol"><MutedCell row={row} cell={cell} shade={shade(row.key, cell)} as="col" /></td> })}
                <td className="gap" />
              </Fragment> })}
              {hiddenDs.map(d => <td key={d.file} className="dsc-map-hiddencol"><i className="dsc-map-mcell col" /></td>)}
            </>} />
          </tbody>
        </table>
      </div>
      <Legend level={3} />
      {foot}
    </>
  )
}
