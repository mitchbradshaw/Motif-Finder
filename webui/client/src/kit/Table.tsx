/* Table: render-fn columns, sortable headers, single/multi selection with checkboxes, row click, highlighted row,
 * group rows (jobs-1 "Paused · waiting on cluster results 2"), empty row, sticky header, dense mode. */
import { useMemo, useState, type CSSProperties, type Key, type ReactNode } from 'react'
import { Icon, type IconName } from './icons'
import { cx, tid, type TestIdProps } from './portal'

export interface Column<T> {
  key: string; header: ReactNode
  /** Cell content; default `String(row[key])`. */
  render?: (row: T, index: number) => ReactNode
  /** Enables sorting on this column; return a number or string. */
  sortValue?: (row: T) => number | string | null | undefined
  width?: number | string; align?: 'left' | 'right' | 'center'; className?: string; title?: string
}
export type SortState = { key: string; dir: 'asc' | 'desc' } | null

export interface TableProps<T> extends TestIdProps {
  columns: Column<T>[]; rows: T[]; rowKey: (row: T) => string
  selection?: 'none' | 'single' | 'multi'; selected?: string[]; onSelectionChange?: (keys: string[]) => void
  onRowClick?: (row: T) => void; highlighted?: string | null
  rowTone?: (row: T) => 'amber' | 'red' | 'dim' | undefined
  groupBy?: (row: T) => string; groupLabel?: (group: string, rows: T[]) => ReactNode; groupIcon?: (group: string) => IconName | undefined; collapsibleGroups?: boolean
  sort?: SortState; onSortChange?: (s: SortState) => void; defaultSort?: SortState
  empty?: ReactNode; stickyHeader?: boolean; dense?: boolean; maxHeight?: number | string; footer?: ReactNode; style?: CSSProperties; ariaLabel?: string
}

export function Table<T>({ columns, rows, rowKey, selection = 'none', selected = [], onSelectionChange, onRowClick, highlighted, rowTone, groupBy, groupLabel, groupIcon, collapsibleGroups = true,
  sort, onSortChange, defaultSort = null, empty = 'nothing to show', stickyHeader = true, dense, maxHeight, footer, style, ariaLabel, ...t }: TableProps<T>) {
  const [innerSort, setInnerSort] = useState<SortState>(defaultSort)
  const sortState = sort !== undefined ? sort : innerSort
  const setSort = (s: SortState) => { if (sort === undefined) setInnerSort(s); onSortChange?.(s) }
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const sel = useMemo(() => new Set(selected), [selected])

  const sorted = useMemo(() => {
    if (!sortState) return rows
    const col = columns.find(c => c.key === sortState.key)
    if (!col?.sortValue) return rows
    const f = col.sortValue, m = sortState.dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const va = f(a), vb = f(b)
      if (va == null && vb == null) return 0
      if (va == null) return 1
      if (vb == null) return -1
      return (typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb))) * m
    })
  }, [rows, sortState, columns])

  const toggleRow = (k: string) => {
    if (!onSelectionChange) return
    if (selection === 'single') onSelectionChange(sel.has(k) ? [] : [k])
    else onSelectionChange(sel.has(k) ? selected.filter(x => x !== k) : [...selected, k])
  }
  const allKeys = rows.map(rowKey)
  const nSel = allKeys.filter(k => sel.has(k)).length
  const headerSort = (c: Column<T>) => {
    if (!c.sortValue) return
    setSort(sortState?.key !== c.key ? { key: c.key, dir: 'asc' } : sortState.dir === 'asc' ? { key: c.key, dir: 'desc' } : null)
  }
  const nCols = columns.length + (selection === 'multi' || selection === 'single' ? 1 : 0)

  const groups: [string | null, T[]][] = useMemo(() => {
    if (!groupBy) return [[null, sorted]]
    const m = new Map<string, T[]>()
    for (const r of sorted) { const g = groupBy(r); if (!m.has(g)) m.set(g, []); m.get(g)!.push(r) }
    return [...m.entries()]
  }, [sorted, groupBy])

  const renderRow = (r: T, i: number) => {
    const k = rowKey(r)
    const isSel = sel.has(k)
    const tone = rowTone?.(r)
    const clickable = !!onRowClick || selection !== 'none'
    const activate = () => { if (onRowClick) onRowClick(r); else if (selection !== 'none') toggleRow(k) }
    return (
      <tr key={k as Key} className={cx(clickable && 'clickable', isSel && 'sel', highlighted === k && 'hl', tone && (tone === 'dim' ? 'dim' : `tone-${tone}`))}
        aria-selected={selection !== 'none' ? isSel : undefined} tabIndex={clickable ? 0 : undefined} data-row-key={k}
        onClick={clickable ? activate : undefined} onKeyDown={clickable ? e => { if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) { e.preventDefault(); activate() } } : undefined}>
        {selection !== 'none' && (
          <td className="k-cb" onClick={e => e.stopPropagation()}>
            <label className="k-check" style={{ padding: 0 }}>
              <input type={selection === 'single' ? 'checkbox' : 'checkbox'} checked={isSel} onChange={() => toggleRow(k)} aria-label={`select row ${k}`} />
            </label>
          </td>
        )}
        {columns.map(c => <td key={c.key} className={cx(c.align === 'right' && 'num', c.align === 'center' && 'center', c.className)}>{c.render ? c.render(r, i) : String((r as Record<string, unknown>)[c.key] ?? '—')}</td>)}
      </tr>
    )
  }

  return (
    <div className="k-table-wrap" style={{ maxHeight, ...style }} data-testid={tid(t)}>
      <table className={cx('k-table', stickyHeader && 'sticky', dense && 'dense')} aria-label={ariaLabel} aria-multiselectable={selection === 'multi' || undefined}>
        <thead>
          <tr>
            {selection !== 'none' && (
              <th className="k-cb">
                {selection === 'multi' && (
                  <label className="k-check" style={{ padding: 0 }}>
                    <input type="checkbox" checked={rows.length > 0 && nSel === rows.length} ref={el => { if (el) el.indeterminate = nSel > 0 && nSel < rows.length }}
                      onChange={() => onSelectionChange?.(nSel === rows.length ? [] : allKeys)} aria-label="select all rows" disabled={!rows.length} title={rows.length ? 'select all' : 'no rows to select'} />
                  </label>
                )}
              </th>
            )}
            {columns.map(c => {
              const on = sortState?.key === c.key
              return (
                <th key={c.key} style={{ width: c.width, textAlign: c.align }} className={cx(c.sortValue && 'sortable', on && 'sorted', c.align === 'right' && 'num')} title={c.title}
                  aria-sort={on ? (sortState!.dir === 'asc' ? 'ascending' : 'descending') : c.sortValue ? 'none' : undefined}>
                  {c.sortValue
                    ? <button type="button" onClick={() => headerSort(c)} style={{ justifyContent: c.align === 'right' ? 'flex-end' : c.align === 'center' ? 'center' : 'flex-start' }}>{c.header}<Icon name={on ? (sortState!.dir === 'asc' ? 'arrow-up' : 'arrow-down') : 'chevron-down'} size={10} className="sort-ic" /></button>
                    : c.header}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {!rows.length && <tr className="empty"><td colSpan={nCols}>{empty}</td></tr>}
          {groups.map(([g, rs]) => {
            if (g === null) return rs.map(renderRow)
            const isCol = collapsed.has(g)
            const ic = groupIcon?.(g)
            return [
              <tr key={`group-${g}`} className="group">
                <td colSpan={nCols}>
                  <button type="button" className={cx('group-bar', isCol && 'collapsed')} aria-expanded={!isCol} disabled={!collapsibleGroups}
                    onClick={() => setCollapsed(s => { const n = new Set(s); if (n.has(g)) n.delete(g); else n.add(g); return n })} data-testid={`group-${g}`}>
                    {collapsibleGroups && <Icon name="chevron-down" size={12} className="chev" />}{ic && <Icon name={ic} size={13} />}
                    <span>{groupLabel ? groupLabel(g, rs) : g}</span><span className="n">{rs.length}</span>
                  </button>
                </td>
              </tr>,
              ...(isCol ? [] : rs.map(renderRow)),
            ]
          })}
        </tbody>
      </table>
      {footer && <div className="k-table-foot">{footer}</div>}
    </div>
  )
}
