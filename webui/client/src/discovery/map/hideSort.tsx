/* discovery.map.hideSort — the map's hide and sort controls and layout, written once for every level (site-map,
 * 2026-10-20). A hidden row sinks to the bottom and a hidden column to the right, drawn thin and dimmed with a button
 * that brings it back; the order (`../mapOrder.ts`) reads only the shown cells.
 *
 * tq-mappage (2026-10-25): level 3 and level 2 each built their column items, called `arrange`, and looked the keys
 * back up by key, and each drew its own shown/hidden header pair; now `arrange` hands back the items,
 * `arrangeColumns` builds them once, and `HideableHeader` / `TableRows` draw the header and the row lines. */
import type { ReactNode, ThHTMLAttributes } from 'react'
import { Button, Icon, cx } from '../../kit'
import type { DiscMapCell, DiscMapRow } from '../../api'
import { arrange, type SortMode } from '../mapOrder'
import { rateOf, rowTitle } from './common'

export const ROW_SORTS: { value: SortMode; label: string; title: string }[] = [
  { value: 'listed', label: 'as listed', title: 'templates, then seed searches, by name — the order the bridge lists them' },
  { value: 'name', label: 'name', title: 'alphabetical, numbers compared as numbers' },
  { value: 'count', label: 'most detections', title: 'most detections over the shown cells first' },
  { value: 'cluster', label: 'cluster', title: 'rows that fire alike side by side: average-linkage clustering on the correlation of their shaded rates over the shown cells' },
]
export const COL_SORTS: { value: SortMode; label: string; title: string }[] = [
  { value: 'listed', label: 'as recorded', title: 'channel order as recorded' }, ROW_SORTS[1], ROW_SORTS[2],
  { value: 'cluster', label: 'cluster', title: 'channels that light up alike side by side: average-linkage clustering on the correlation of their shaded rates over the shown rows' },
]
export const SORT_VALUES: SortMode[] = ['listed', 'name', 'count', 'cluster']

export interface MapView {
  hiddenRows: ReadonlySet<string>; hiddenCols: ReadonlySet<string>
  toggleRow: (key: string) => void; toggleCol: (id: string) => void
  rsort: SortMode; csort: SortMode
}
export const colId = (datasetKey: string, channel: string) => `${datasetKey}/${channel}`
export type Arranged<T> = { shown: T[]; hidden: T[] }

/** The shown rows in the chosen order (the human row first), then the hidden ones in their listed order. */
export function orderRows(rows: DiscMapRow[], view: MapView, valuesOf: (r: DiscMapRow) => (number | null)[], countOf: (r: DiscMapRow) => number): Arranged<DiscMapRow> {
  return arrange(rows.map(r => {
    const on = !view.hiddenRows.has(r.key)
    return { ...r, values: view.rsort === 'cluster' && on ? valuesOf(r) : [], count: view.rsort === 'count' && on ? countOf(r) : 0 }
  }), view.rsort, view.hiddenRows, 'human')
}

/** One dataset's channels: the shown ones in the chosen order, then the hidden ones. A channel's order reads its cells
 *  (`cellsOf` — one cell at level 3, a channel's time slices at level 2, which move as one) over the SHOWN rows only. */
export function arrangeColumns<C extends { name: string }>(channels: C[], datasetKey: string, rows: DiscMapRow[], cellsOf: (rowKey: string, channel: string) => DiscMapCell[], view: MapView): Arranged<C> {
  const shownRowKeys = rows.filter(r => !view.hiddenRows.has(r.key)).map(r => r.key)
  return arrange(channels.map(c => {
    const cells = () => shownRowKeys.flatMap(k => cellsOf(k, c.name))
    return {
      ...c, key: colId(datasetKey, c.name), label: c.name,
      values: view.csort === 'cluster' ? cells().map(rateOf) : [],
      count: view.csort === 'count' ? cells().reduce((s, x) => s + x.count, 0) : 0,
    }
  }), view.csort, view.hiddenCols)
}

/** One line above the table naming what is hidden, with a button that shows it all again. */
export function HiddenLine({ rows, cols, onShowAll }: { rows: string[]; cols: string[]; onShowAll: () => void }) {
  if (!rows.length && !cols.length) return null
  const bits = [rows.length ? `${rows.length} row${rows.length === 1 ? '' : 's'} (at the bottom)` : '', cols.length ? `${cols.length} column${cols.length === 1 ? '' : 's'} (at the right)` : ''].filter(Boolean)
  return (
    <div className="dsc-map-hidden" data-testid="map-hidden-line">
      <Icon name="eye-off" size={12} /> hidden: {bits.join(' · ')} — each has a button on it to bring it back ·
      <Button size="sm" variant="link" onClick={onShowAll} testid="map-show-all">show all</Button>
    </div>
  )
}

export function HideButton({ hidden, what, kind, testid, onClick }: { hidden?: boolean; what: string; kind: 'row' | 'column' | 'dataset'; testid: string; onClick: () => void }) {
  const title = hidden ? `show ${what} again, back in its place` : `hide ${what} — it moves to the ${kind === 'row' ? 'bottom' : 'right'}, thin and dimmed`
  return (
    <button type="button" className={cx('dsc-map-x', hidden && 'show')} title={title} aria-label={title} data-testid={testid}
      onClick={e => { e.stopPropagation(); onClick() }}>{hidden ? (kind === 'row' ? 'show' : '+') : '×'}</button>
  )
}

/** A channel's column header: its × hides the column (it moves to the right), a hidden one's + brings it back. */
export function HideableHeader({ id, name, what, hidden, view, className, title, ...th }: { id: string; name: string; what: string; hidden?: boolean; view: MapView } & ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th {...th} className={cx('ch', className, hidden && 'hidden')} title={hidden ? `${name} is hidden` : title}>
      <HideButton hidden={hidden} what={what} kind="column" testid={hidden ? `map-col-show-${id}` : `map-col-hide-${id}`} onClick={() => view.toggleCol(id)} /><span>{name}</span>
    </th>
  )
}

/** A row's label, sticky at the left; its × hides the row (it sinks to the bottom), a hidden row's `show` brings it back. */
function RowLabel({ row, hidden, onToggle }: { row: DiscMapRow; hidden?: boolean; onToggle: () => void }) {
  return (
    <th scope="row" className={cx('dsc-map-rowlabel', hidden && 'hidden')} title={rowTitle(row)} data-testid={`map-row-${row.key}`}>
      <span className="dsc-map-rowin">
        <span className="dsc-map-rowtext"><i className="sw" style={{ background: row.colour }} />{row.label}</span>
        <HideButton hidden={hidden} what={row.label} kind="row" testid={hidden ? `map-row-show-${row.key}` : `map-row-hide-${row.key}`} onClick={onToggle} />
      </span>
    </th>
  )
}

/** The table body at levels 3 and 2: the shown rows, then the hidden ones thin and dimmed, each with its label. */
export function TableRows({ rows, view, cells }: { rows: Arranged<DiscMapRow>; view: MapView; cells: (row: DiscMapRow, hidden: boolean) => ReactNode }) {
  const line = (row: DiscMapRow, hidden: boolean) => (
    <tr key={row.key} data-testid={hidden ? 'map-row-hidden' : 'map-row'} className={cx(hidden && 'dsc-map-hiddenrow')}>
      <RowLabel row={row} hidden={hidden} onToggle={() => view.toggleRow(row.key)} />
      {cells(row, hidden)}
    </tr>
  )
  return <>{rows.shown.map(row => line(row, false))}{rows.hidden.map(row => line(row, true))}</>
}
