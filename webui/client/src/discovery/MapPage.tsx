/* discovery.map — the detection map (2026-10-12): where each detection algorithm fires, at three zoom levels.
 *
 * Rows are algorithms (the human reference first), read across EVERY Discovery session. Level 3 is every
 * dataset with a Discovery run, its channels as columns; level 2 is one dataset's channels, each optionally in
 * 2 · 4 · 8 equal time slices; level 1 is one channel over the WHOLE recording in time bins. Click down, crumb up.
 *
 * What is drawn is honest about what it does not know: a cell the algorithm never covered is hatched "not run",
 * a covered cell with nothing found is white, a cell is shaded by detections per COVERED hour with the covered
 * share drawn as a bar along its foot — so a 6 h section run never looks like a 700 h one — and a stretch that
 * is still running, failed or discarded carries that state at every level. The page never writes: the Runs
 * browser is session-scoped, so a level-1 click opens it only for a bin whose owning run is in the open session,
 * on the session's recording, on one of its channels and inside its section; otherwise the readout says why not.
 *
 * URL keys are `dataset` / `channel` / `bin` / `chunks` / `norm` — `recording` and `channels` are the
 * session's own deep-link keys (session.ts) and must not be touched by this page.
 *
 * site-map (2026-10-20): every row and column can be hidden from its label — `hide=` (row keys) and `hidecols=`
 * (`<dataset key>` or `<dataset key>/<channel>`) — and a hidden one is not removed: it sinks to the bottom (a row)
 * or to the right of its dataset (a column), drawn thin and dimmed with a button that brings it back to where the
 * current order puts it (the researcher, 2026-10-20). `rsort=` / `csort=` order the shown rows and columns as listed,
 * by name, by most detections or by clustering (`mapOrder.ts`); hidden ones are left out of the ordering. The table
 * scrolls inside the card with its row labels and header rows sticky. Level 1 draws the channel's own signal above
 * its rows (`signal=0` turns it off) from the scope strip's hourly-mean read. */
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { Breadcrumb, Button, EmptyState, Icon, InfoTip, Seg, cx, useQueryState } from '../kit'
import { Header } from '../shell/Header'
import { navigate } from '../state'
import { useSourced, type SourcedState } from '../api/seam'
import { getMap, getMapChannel, getMapDataset, getOverview } from '../api/discovery'
import type { DiscMapCell, DiscMapRow, DiscMapState, DiscMapTimeline } from '../api'
import { LoadFailed, Loading, Refreshing } from './chrome'
import { arrange, splitKeys, toggleKey, type SortMode } from './mapOrder'
import { extentOf, maxOf } from '../charts/domain'

/* ux-1018: a level answered only its first read. A run finishing or a verdict landing changed nothing on screen,
 * and a new slice count drew the OLD payload until the next read landed, with nothing to say a read was out — which
 * read as "the time chunks are not showing changes" (the researcher, 2026-10-18). Now a read in flight shows the
 * refreshing line and dims the table; the level re-reads when the window comes back into focus; and while any cell
 * is still running it re-reads every few seconds until none is. The server computes levels 1 and 2 on every read, so
 * the poll is tied to running cells, not left on. Level 3 (map-overview-cache) is the bridge's last computed answer:
 * it polls while that answer says it is pending or stale, and a poll then costs the bridge milliseconds. */
const MAP_POLL_MS = 5000
function useMapRefresh<T>(m: SourcedState<T>, running: boolean) {
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

type Norm = 'row' | 'map'
const BIN_OPTIONS: { value: string; label: string }[] = [
  { value: '1', label: '1 h' }, { value: '3', label: '3 h' }, { value: '6', label: '6 h' }, { value: '12', label: '12 h' }, { value: '24', label: '1 d' }, { value: '168', label: '1 w' },
]
const CHUNK_OPTIONS = ['1', '2', '4', '8']
/** past this many bins a cell is under a pixel at the page's width, so the option is refused with its reason */
const MAX_BINS = 1400
const STATE_WORDS: Record<DiscMapState, string> = {
  covered: 'covered', not_run: 'not run here', running: 'still running here', failed: 'failed here', discarded: 'discarded (superseded) here', not_reviewed: 'not reviewed',
}
/** the fill of an uncovered stretch at level 1, by its state (hatch for the never-run ones) */
const GAP_FILL: Record<DiscMapState, string> = {
  covered: 'none', not_run: 'url(#dsc-map-hatch)', not_reviewed: 'url(#dsc-map-hatch)', running: 'rgba(217, 119, 6, 0.35)', failed: 'rgba(239, 68, 68, 0.35)', discarded: '#d1d5db',
}

const fmtH = (h: number) => h === 0 ? '0 h' : h >= 100 ? `${Math.round(h)} h` : h >= 10 ? `${h.toFixed(1)} h` : `${h.toFixed(2)} h`
const rateOf = (c: DiscMapCell) => c.hours > 0 ? c.count / c.hours : null
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
function useShades(rows: DiscMapRow[], cellsOf: (key: string) => DiscMapCell[], norm: Norm) {
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

function rowTitle(row: DiscMapRow): string {
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

/* ------------------------------------------------------------------ hide / sort (site-map) */
const ROW_SORTS: { value: SortMode; label: string; title: string }[] = [
  { value: 'listed', label: 'as listed', title: 'templates, then seed searches, by name — the order the bridge lists them' },
  { value: 'name', label: 'name', title: 'alphabetical, numbers compared as numbers' },
  { value: 'count', label: 'most detections', title: 'most detections over the shown cells first' },
  { value: 'cluster', label: 'cluster', title: 'rows that fire alike side by side: average-linkage clustering on the correlation of their shaded rates over the shown cells' },
]
const COL_SORTS: { value: SortMode; label: string; title: string }[] = [
  { value: 'listed', label: 'as recorded', title: 'channel order as recorded' }, ROW_SORTS[1], ROW_SORTS[2],
  { value: 'cluster', label: 'cluster', title: 'channels that light up alike side by side: average-linkage clustering on the correlation of their shaded rates over the shown rows' },
]
const SORT_VALUES: SortMode[] = ['listed', 'name', 'count', 'cluster']
interface MapView {
  hiddenRows: ReadonlySet<string>; hiddenCols: ReadonlySet<string>
  toggleRow: (key: string) => void; toggleCol: (id: string) => void
  rsort: SortMode; csort: SortMode
}
const colId = (datasetKey: string, channel: string) => `${datasetKey}/${channel}`
const NOT_RUN: DiscMapCell = { count: 0, hours: 0, state: 'not_run' }

/** The shown rows in the chosen order (the human row first), then the hidden ones in their listed order. */
function orderRows(rows: DiscMapRow[], view: MapView, valuesOf: (r: DiscMapRow) => (number | null)[], countOf: (r: DiscMapRow) => number) {
  const items = rows.map(r => ({ key: r.key, label: r.label, values: view.rsort === 'cluster' && !view.hiddenRows.has(r.key) ? valuesOf(r) : [], count: view.rsort === 'count' && !view.hiddenRows.has(r.key) ? countOf(r) : 0 }))
  const a = arrange(items, view.rsort, view.hiddenRows, 'human')
  const by = new Map(rows.map(r => [r.key, r]))
  return { shown: a.shown.map(k => by.get(k)!), hidden: a.hidden.map(k => by.get(k)!) }
}

/** One line above the table naming what is hidden, with a button that shows it all again. */
function HiddenLine({ rows, cols, onShowAll }: { rows: string[]; cols: string[]; onShowAll: () => void }) {
  if (!rows.length && !cols.length) return null
  const bits = [rows.length ? `${rows.length} row${rows.length === 1 ? '' : 's'} (at the bottom)` : '', cols.length ? `${cols.length} column${cols.length === 1 ? '' : 's'} (at the right)` : ''].filter(Boolean)
  return (
    <div className="dsc-map-hidden" data-testid="map-hidden-line">
      <Icon name="eye-off" size={12} /> hidden: {bits.join(' · ')} — each has a button on it to bring it back ·
      <Button size="sm" variant="link" onClick={onShowAll} testid="map-show-all">show all</Button>
    </div>
  )
}

export function MapPage() {
  const [hideQ, setHideQ] = useQueryState('hide', '')
  const [hideColsQ, setHideColsQ] = useQueryState('hidecols', '')
  const [rsortQ, setRsort] = useQueryState<SortMode>('rsort', 'listed')
  const [csortQ, setCsort] = useQueryState<SortMode>('csort', 'listed')
  const [signalQ, setSignalQ] = useQueryState('signal', '1')
  const view: MapView = useMemo(() => ({
    hiddenRows: new Set(splitKeys(hideQ)), hiddenCols: new Set(splitKeys(hideColsQ)),
    toggleRow: (key: string) => setHideQ(toggleKey(hideQ, key)), toggleCol: (id: string) => setHideColsQ(toggleKey(hideColsQ, id)),
    rsort: SORT_VALUES.includes(rsortQ) ? rsortQ : 'listed', csort: SORT_VALUES.includes(csortQ) ? csortQ : 'listed',
  }), [hideQ, hideColsQ, rsortQ, csortQ, setHideQ, setHideColsQ])
  const showAll = () => { setHideQ(null); setHideColsQ(null) }
  const [dataset, setDataset] = useQueryState('dataset', '')
  const [channel, setChannel] = useQueryState('channel', '')
  const [norm, setNorm] = useQueryState<Norm>('norm', 'row')
  const [chunksQ, setChunksQ] = useQueryState('chunks', '1')
  const [binQ, setBinQ] = useQueryState('bin', '3')
  const level = dataset && channel ? 1 : dataset ? 2 : 3
  const chunks = CHUNK_OPTIONS.includes(chunksQ) ? parseInt(chunksQ, 10) : 1
  const binH = BIN_OPTIONS.some(b => b.value === binQ) ? parseFloat(binQ) : 3
  const [crumbNames, setCrumbNames] = useState<Record<string, string>>({})
  const learn = (name: string, hours: number) => setCrumbNames(n => n[dataset] === name && n[`${dataset}:h`] === String(hours) ? n : { ...n, [dataset]: name, [`${dataset}:h`]: String(hours) })
  const crumbs = [{ label: 'All datasets', onClick: level === 3 ? undefined : () => { setDataset(null); setChannel(null) } }]
  if (dataset) crumbs.push({ label: crumbNames[dataset] ?? dataset, onClick: level === 2 ? undefined : () => setChannel(null) })
  if (dataset && channel) crumbs.push({ label: channel, onClick: undefined })
  return (
    <>
      <Header workspace="Discovery" page="Map" subtitle="where each algorithm fires · every session · read-only" />
      <div className="k-page dsc-page" data-testid="discovery-map-page">
        <div className="k-page-inner" style={{ maxWidth: 'none', gap: 12 }}>
          <section className="k-card dsc-map" data-testid="map-card" data-level={level} aria-label="Detection map">
            <div className="dsc-card-head dsc-map-head">
              <h3>Detection map</h3>
              <InfoTip title="Detection map">
                Rows are algorithms, one per set of executed steps, read across every Discovery session; the human reference is first.
                A cell is shaded by detections per covered hour and carries a bar along its foot for the share of the column it covered.
                Hatched means the algorithm never ran there (for the human row: nobody looked there); white means it ran and found nothing;
                amber, red and grey mean running, failed and discarded. Click a dataset, then a channel, to zoom; the crumbs go back up. The page never writes.
              </InfoTip>
              <Breadcrumb items={crumbs} links testid="map-crumbs" />
              <span className="k-spacer" />
              {level !== 1 && <Seg size="sm" value={norm} onChange={v => setNorm(v)} label="shade" options={[{ value: 'row', label: 'per row', title: 'each row\'s busiest cell is 1' }, { value: 'map', label: 'whole map', title: 'the busiest machine cell on the map is 1; the human row stays per row' }]} testid="map-norm" />}
              {level === 2 && <Seg size="sm" value={String(chunks)} onChange={v => setChunksQ(v)} label="time chunks" options={CHUNK_OPTIONS.map(v => ({ value: v, label: v }))} testid="map-chunks" />}
              {level === 1 && <BinSeg value={String(binH)} onChange={v => setBinQ(v)} hours={crumbHours(crumbNames, dataset)} />}
              {level === 1 && <Seg size="sm" value={signalQ === '0' ? '0' : '1'} onChange={v => setSignalQ(v)} label="signal" options={[{ value: '1', label: 'on', title: 'the channel\'s own trace (hourly means) above the rows, on their time axis' }, { value: '0', label: 'off' }]} testid="map-signal" />}
              <Button size="sm" variant="link" icon="arrow-left" onClick={() => navigate('discovery/runs')} testid="map-to-runs">Runs</Button>
            </div>
            <div className="dsc-card-head dsc-map-head dsc-map-orderbar">
              <Seg size="sm" value={view.rsort} onChange={v => setRsort(v)} label="rows" options={ROW_SORTS} testid="map-rsort" />
              {level !== 1 && <Seg size="sm" value={view.csort} onChange={v => setCsort(v)} label="columns" options={COL_SORTS} testid="map-csort" />}
              <InfoTip title="Order and hide">
                Rows: as listed, by name, most detections first, or clustered — rows that fire alike side by side (average-linkage clustering on
                the correlation of their shaded rates). Columns sort the same way{level === 3 ? ', each dataset\'s channels within the dataset' : level === 2 ? ', a channel\'s time slices moving as one' : ''};
                level 1's columns are time and do not sort. The human row stays first. Hover a row or column label for its × to hide it: it sinks
                to the bottom (a row) or the right (a column), thin and dimmed, with a button to bring it back. Orders read only the shown cells. All of it is in the link.
              </InfoTip>
              <HiddenLine rows={[...view.hiddenRows]} cols={[...view.hiddenCols]} onShowAll={showAll} />
            </div>
            {level === 3 && <DatasetsLevel norm={norm} view={view} onDataset={(key, name) => { setCrumbNames(n => ({ ...n, [key]: name })); setDataset(key) }} />}
            {level === 2 && <DatasetLevel dataset={dataset} chunks={chunks} norm={norm} view={view} onName={learn} onChannel={ch => setChannel(ch)} />}
            {level === 1 && <ChannelLevel dataset={dataset} channel={channel} binH={binH} view={view} signal={signalQ !== '0'} onName={learn} />}
          </section>
        </div>
      </div>
    </>
  )
}
const crumbHours = (names: Record<string, string>, dataset: string) => { const h = parseFloat(names[`${dataset}:h`] ?? ''); return Number.isFinite(h) ? h : null }

/** The bin picker: an option whose bins would be under a pixel is refused with its reason, not drawn as mush. */
function BinSeg({ value, onChange, hours }: { value: string; onChange: (v: string) => void; hours: number | null }) {
  const options = BIN_OPTIONS.map(b => {
    const n = hours != null ? Math.ceil(hours / parseFloat(b.value)) : 0
    const tooMany = n > MAX_BINS
    return { ...b, disabled: tooMany, reason: tooMany ? `${n} bins: cells under a pixel at this width — use ${BIN_OPTIONS.find(o => Math.ceil(hours! / parseFloat(o.value)) <= MAX_BINS)?.label ?? 'a wider bin'}` : undefined }
  })
  return <Seg size="sm" value={value} onChange={onChange} label="bin" options={options} testid="map-binsize" />
}

function Legend({ level }: { level: 1 | 2 | 3 }) {
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

/** One shaded cell at levels 2 and 3. `share` is the covered fraction of the column, drawn as the foot bar. */
function Cell({ row, cell, where, shade, share, onClick, wide }: { row: DiscMapRow; cell: DiscMapCell; where: string; shade: number; share: number; onClick?: () => void; wide?: boolean }) {
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

function HideButton({ hidden, what, kind, testid, onClick }: { hidden?: boolean; what: string; kind: 'row' | 'column' | 'dataset'; testid: string; onClick: () => void }) {
  const title = hidden ? `show ${what} again, back in its place` : `hide ${what} — it moves to the ${kind === 'row' ? 'bottom' : 'right'}, thin and dimmed`
  return (
    <button type="button" className={cx('dsc-map-x', hidden && 'show')} title={title} aria-label={title} data-testid={testid}
      onClick={e => { e.stopPropagation(); onClick() }}>{hidden ? (kind === 'row' ? 'show' : '+') : '×'}</button>
  )
}

/** A cell of a hidden row or column: its shade kept, drawn small and dimmed, not clickable. */
function MutedCell({ row, cell, shade, as }: { row: DiscMapRow; cell: DiscMapCell; shade: number; as: 'row' | 'col' }) {
  return <i className={cx('dsc-map-mcell', as, cell.state)} style={{ background: fill(row, cell, shade) }} data-testid="map-cell-muted" />
}

/* ------------------------------------------------------------------ level 3's top scrollbar */
/** night-disc item 4: a thin horizontal scrollbar ABOVE the level-3 table (the researcher: the table's own bar is at the
 *  bottom of a tall block, out of sight), synced both ways with the table's horizontal scroll. Its inner width is chosen
 *  so the two have the same scroll range (the table's vertical scrollbar narrows its client width); a ResizeObserver
 *  keeps it in step when datasets or rows are hidden or the window changes. The row labels stay sticky on the left. */
function TopScrollbar({ target }: { target: React.RefObject<HTMLDivElement | null> }) {
  const bar = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ inner: 0, overflow: false })
  useEffect(() => {
    const t = target.current, b = bar.current
    if (!t || !b) return
    const measure = () => setSize({ inner: t.scrollWidth - t.clientWidth + b.clientWidth, overflow: t.scrollWidth > t.clientWidth + 1 })
    const fromTable = () => { if (Math.abs(b.scrollLeft - t.scrollLeft) > 1) b.scrollLeft = t.scrollLeft }
    const fromBar = () => { if (Math.abs(t.scrollLeft - b.scrollLeft) > 1) t.scrollLeft = b.scrollLeft }
    t.addEventListener('scroll', fromTable, { passive: true })
    b.addEventListener('scroll', fromBar, { passive: true })
    const ro = new ResizeObserver(measure)
    ro.observe(t)
    if (t.firstElementChild) ro.observe(t.firstElementChild)
    measure()
    return () => { t.removeEventListener('scroll', fromTable); b.removeEventListener('scroll', fromBar); ro.disconnect() }
  }, [target])
  return (
    <div ref={bar} className={cx('dsc-map-topscroll', !size.overflow && 'fits')} data-testid="map-top-scroll" data-overflow={size.overflow ? '1' : '0'} aria-hidden>
      <div style={{ width: size.inner }} />
    </div>
  )
}

/* ------------------------------------------------------------------ level 3: datasets × channels */
function DatasetsLevel({ norm, view, onDataset }: { norm: Norm; view: MapView; onDataset: (key: string, name: string) => void }) {
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
    const shownRowKeys = data.rows.filter(r => !view.hiddenRows.has(r.key)).map(r => r.key)
    const cols = new Map(shownDs.map(d => {
      const items = d.channels.map(c => ({
        key: colId(d.key, c.name), label: c.name,
        values: view.csort === 'cluster' ? shownRowKeys.map(k => rateOf(cellOf(d, k, c.name))) : [],
        count: shownRowKeys.reduce((s, k) => s + cellOf(d, k, c.name).count, 0),
      }))
      const a = arrange(items, view.csort, view.hiddenCols)
      const byId = new Map(d.channels.map(c => [colId(d.key, c.name), c]))
      return [d.key, { shown: a.shown.map(k => byId.get(k)!), hidden: a.hidden.map(k => byId.get(k)!) }] as const
    }))
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
  const line = (row: DiscMapRow, hidden: boolean) => (
    <tr key={row.key} data-testid={hidden ? 'map-row-hidden' : 'map-row'} className={cx(hidden && 'dsc-map-hiddenrow')}>
      <RowLabel row={row} hidden={hidden} onToggle={() => view.toggleRow(row.key)} />
      {shownDs.map(d => { const cs = cols.get(d.key)!; return <Fragment key={d.file}>
        {cs.shown.map(c => {
          const cell = cellOf(d, row.key, c.name)
          return <td key={c.name}>{hidden
            ? <MutedCell row={row} cell={cell} shade={shade(row.key, cell)} as="row" />
            : <Cell row={row} cell={cell} where={`${d.name} ${c.name}`} shade={shade(row.key, cell)} share={c.hours > 0 ? cell.hours / c.hours : 0} onClick={() => onDataset(d.key, d.name)} />}</td>
        })}
        {cs.hidden.map(c => { const cell = cellOf(d, row.key, c.name); return <td key={c.name} className="dsc-map-hiddencol"><MutedCell row={row} cell={cell} shade={shade(row.key, cell)} as="col" /></td> })}
        <td className="gap" />
      </Fragment> })}
      {hiddenDs.map(d => <td key={d.file} className="dsc-map-hiddencol"><i className="dsc-map-mcell col" /></td>)}
    </tr>
  )
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
                {cs.shown.map(c => <th key={c.name} className="ch"><HideButton what={`${d.name} ${c.name}`} kind="column" testid={`map-col-hide-${colId(d.key, c.name)}`} onClick={() => view.toggleCol(colId(d.key, c.name))} /><span>{c.name}</span></th>)}
                {cs.hidden.map(c => <th key={c.name} className="ch hidden" title={`${c.name} is hidden`}><HideButton hidden what={`${d.name} ${c.name}`} kind="column" testid={`map-col-show-${colId(d.key, c.name)}`} onClick={() => view.toggleCol(colId(d.key, c.name))} /><span>{c.name}</span></th>)}
                <th className="gap" />
              </Fragment> })}
            </tr>
          </thead>
          <tbody>
            {rows.shown.map(row => line(row, false))}
            {rows.hidden.map(row => line(row, true))}
          </tbody>
        </table>
      </div>
      <Legend level={3} />
      {foot}
    </>
  )
}

/* ------------------------------------------------------------------ level 2: one dataset's channels, in chunks */
function DatasetLevel({ dataset, chunks, norm, view, onName, onChannel }: { dataset: string; chunks: number; norm: Norm; view: MapView; onName: (name: string, hours: number) => void; onChannel: (ch: string) => void }) {
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
    const shownRowKeys = data.rows.filter(r => !view.hiddenRows.has(r.key)).map(r => r.key)
    const items = data.channels.map(c => ({
      key: colId(key, c.name), label: c.name,
      values: view.csort === 'cluster' ? shownRowKeys.flatMap(k => sl(k, c.name).map(rateOf)) : [],
      count: shownRowKeys.reduce((s, k) => s + sl(k, c.name).reduce((t, x) => t + x.count, 0), 0),
    }))
    const a = arrange(items, view.csort, view.hiddenCols)
    const byId = new Map(data.channels.map(c => [colId(key, c.name), c]))
    const shownCh = a.shown.map(k => byId.get(k)!), hiddenCh = a.hidden.map(k => byId.get(k)!)
    const shownCells = (r: DiscMapRow) => shownCh.flatMap(c => sl(r.key, c.name))
    const rows = orderRows(data.rows, view, r => shownCells(r).map(rateOf), r => shownCells(r).reduce((s, c) => s + c.count, 0))
    return { key, shownCh, hiddenCh, rows, sl }
  }, [data, view, dataset])
  if (m.error) return <LoadFailed what={`the map of ${dataset}`} error={m.error} onRetry={m.reload} />
  if (!data || !layout) return <Loading height={320} label={`counting the runs on ${dataset}`} />
  // the payload's own chunk count, not the prop: while the next read is in flight the old payload is still drawn
  const n = data.chunks
  const sliceH = (chHours: number) => chHours / n
  const { key, shownCh, hiddenCh, rows, sl } = layout
  const line = (row: DiscMapRow, hidden: boolean) => (
    <tr key={row.key} data-testid={hidden ? 'map-row-hidden' : 'map-row'} className={cx(hidden && 'dsc-map-hiddenrow')}>
      <RowLabel row={row} hidden={hidden} onToggle={() => view.toggleRow(row.key)} />
      {shownCh.map(c => sl(row.key, c.name).map((cell, i) => {
        if (hidden) return <td key={`${c.name}-${i}`}><MutedCell row={row} cell={cell} shade={shade(row.key, cell)} as="row" /></td>
        const where = n === 1 ? c.name : `${c.name} · slice ${i + 1} of ${n} (${fmtH(i * sliceH(c.hours))}–${fmtH((i + 1) * sliceH(c.hours))})`
        return <td key={`${c.name}-${i}`} className={cx(i === 0 && 'first', i === n - 1 && 'last')}><Cell row={row} cell={cell} where={where} shade={shade(row.key, cell)} share={sliceH(c.hours) > 0 ? cell.hours / sliceH(c.hours) : 0} wide={n === 1} onClick={() => onChannel(c.name)} /></td>
      }))}
      {hiddenCh.map(c => { const cell = sl(row.key, c.name)[0] ?? NOT_RUN; return <td key={c.name} className="dsc-map-hiddencol"><MutedCell row={row} cell={cell} shade={shade(row.key, cell)} as="col" /></td> })}
    </tr>
  )
  return (
    <>
      <Refreshing on={m.loading || !!data.stale} testid="map-refreshing" label={chunks !== n ? `re-slicing ${data.name} into ${chunks} chunk${chunks === 1 ? '' : 's'} per channel…` : running ? 're-counting · a run is still going' : data.stale ? 're-counting · this map is from before the last change' : `re-counting the runs on ${data.name}`} />
      <div className="dsc-map-wrap" data-testid="map-dataset-level" data-stale={m.loading || data.stale ? '1' : '0'} style={{ opacity: m.loading ? 0.55 : 1, transition: 'opacity 140ms' }}>
        <table className="dsc-map-table" data-testid="map-table">
          <thead>
            <tr>
              <th className="corner">{data.name} · {fmtH(data.hours)} · {n === 1 ? 'one cell per channel' : `${n} equal time slices per channel`}</th>
              {shownCh.map(c => <th key={c.name} className="ch link" colSpan={n} onClick={() => onChannel(c.name)} data-testid={`map-channel-${c.name}`} title={`${c.name} · ${fmtH(c.hours)} — open its timeline`}>
                <HideButton what={c.name} kind="column" testid={`map-col-hide-${colId(key, c.name)}`} onClick={() => view.toggleCol(colId(key, c.name))} /><span>{c.name}</span>
              </th>)}
              {hiddenCh.map(c => <th key={c.name} className="ch hidden" title={`${c.name} is hidden`}>
                <HideButton hidden what={c.name} kind="column" testid={`map-col-show-${colId(key, c.name)}`} onClick={() => view.toggleCol(colId(key, c.name))} /><span>{c.name}</span>
              </th>)}
            </tr>
          </thead>
          <tbody>
            {rows.shown.map(row => line(row, false))}
            {rows.hidden.map(row => line(row, true))}
          </tbody>
        </table>
      </div>
      <Legend level={2} />
    </>
  )
}

/* ------------------------------------------------------------------ level 1: one channel over the whole recording */
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

/** The signal strip's height: the height Explore › Signal draws its main trace at (SpanView's `H`), so structure reads
 *  the same here as there (the researcher, 2026-10-20). */
const SIGNAL_H = 150

/** The overview route's points as hours: one value per whole hour, or `n` points spread over them past its cap. */
function signalHours(values: number[], hours: number): number[] {
  const nFull = Math.max(1, Math.floor(hours))
  return values.length >= nFull ? values.map((_, i) => i + 0.5) : values.map((_, i) => values.length === 1 ? nFull / 2 : (i / (values.length - 1)) * (nFull - 1) + 0.5)
}

/** The channel's own trace (the scope strip's hourly means, `getOverview`) on the rows' time axis, above them. */
function SignalStrip({ dataset, channel, hours, units, binH, onHover, onLeave, onRange }: {
  dataset: string; channel: string; hours: number; units: number; binH: number
  onHover: (bin: number) => void; onLeave: () => void; onRange: (r: ((t0: number, t1: number) => [number, number] | null) | null) => void
}) {
  const ov = useSourced(() => getOverview(dataset, [channel]), [dataset, channel])
  const values = ov.data && 'data' in ov.data && ov.data.data ? ov.data.data[channel] ?? [] : null
  const refused = ov.data && 'refused' in ov.data && ov.data.refused ? ov.data.refused : null
  const at = useMemo(() => values ? signalHours(values, hours) : [], [values, hours])
  useEffect(() => {
    if (!values) { onRange(null); return }
    onRange((t0: number, t1: number): [number, number] | null => {
      let lo = Infinity, hi = -Infinity
      at.forEach((h, i) => { const v = values[i]; if (h >= t0 && h < t1 && Number.isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v) } })
      return Number.isFinite(lo) ? [lo, hi] : null
    })
    return () => onRange(null)
  }, [values, at]) // eslint-disable-line react-hooks/exhaustive-deps
  const label = <span className="dsc-map-tlabel" title="the channel's own signal: one mean per hour, from the scope strip's read"><i className="sw" style={{ background: '#374151' }} />signal<span className="muted small"> · hourly mean</span></span>
  if (ov.error) return <div className="dsc-map-trow dsc-map-signal" data-testid="map-signal-strip" data-state="failed">{label}<LoadFailed what={`the signal of ${channel}`} error={ov.error} onRetry={ov.reload} /></div>
  if (refused) return <div className="dsc-map-trow dsc-map-signal note" data-testid="map-signal-strip" data-state="refused">{label}<span className="dsc-map-signal-note">signal not drawn: {refused}</span></div>
  if (!values) return <div className="dsc-map-trow dsc-map-signal note" data-testid="map-signal-strip" data-state="loading">{label}<span className="dsc-map-signal-note">reading {channel}'s hourly means…</span></div>
  const extent = extentOf(values)
  if (!extent) return <div className="dsc-map-trow dsc-map-signal note" data-testid="map-signal-strip" data-state="empty">{label}<span className="dsc-map-signal-note">signal not drawn: {channel} has no finite sample to average</span></div>
  let [lo, hi] = extent
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

function ChannelLevel({ dataset, channel, binH, view, signal, onName }: { dataset: string; channel: string; binH: number; view: MapView; signal: boolean; onName: (name: string, hours: number) => void }) {
  const m = useSourced(() => getMapChannel(dataset, channel, binH), [dataset, channel, binH])
  const [hover, setHover] = useState<{ key: string; bin: number } | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [range, setRange] = useState<((t0: number, t1: number) => [number, number] | null) | null>(null)
  const data = m.data
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
    if (hover.key === '__signal') {
      const r = range ? range(t0, t1) : null
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
          onMouseMove={hidden ? undefined : e => setHover({ key: row.key, bin: binAt(e) })}
          onMouseLeave={hidden ? undefined : () => setHover(h => (h?.key === row.key ? null : h))}
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
        {signal && <SignalStrip dataset={dataset} channel={channel} hours={data.hours} units={units} binH={bh}
          onHover={bin => setHover({ key: '__signal', bin: Math.min(n - 1, bin) })} onLeave={() => setHover(h => (h?.key === '__signal' ? null : h))} onRange={r => setRange(() => r)} />}
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
