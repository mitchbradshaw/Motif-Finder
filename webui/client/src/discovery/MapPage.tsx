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
 * its rows (`signal=0` turns it off) from the scope strip's hourly-mean read.
 *
 * tq-mappage (2026-10-25): this file is the route entry — the URL state, the header and the order bar. Each level, the
 * hide/sort layout they share and the signal strip live in `map/`. */
import { useMemo, useState } from 'react'
import { Breadcrumb, Button, InfoTip, Seg, useQueryState } from '../kit'
import { Header } from '../shell/Header'
import { navigate } from '../state'
import { splitKeys, toggleKey, type SortMode } from './mapOrder'
import type { Norm } from './map/common'
import { COL_SORTS, HiddenLine, ROW_SORTS, SORT_VALUES, type MapView } from './map/hideSort'
import { DatasetsLevel } from './map/DatasetsLevel'
import { DatasetLevel } from './map/DatasetLevel'
import { ChannelLevel } from './map/ChannelLevel'

const BIN_OPTIONS: { value: string; label: string }[] = [
  { value: '1', label: '1 h' }, { value: '3', label: '3 h' }, { value: '6', label: '6 h' }, { value: '12', label: '12 h' }, { value: '24', label: '1 d' }, { value: '168', label: '1 w' },
]
const CHUNK_OPTIONS = ['1', '2', '4', '8']
/** past this many bins a cell is under a pixel at the page's width, so the option is refused with its reason */
const MAX_BINS = 1400

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
