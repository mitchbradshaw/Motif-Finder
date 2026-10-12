/* discovery.map — the detection map (2026-10-12): where each detection algorithm fires, at three zoom levels.
 *
 * Rows are algorithms (the human reference first), read across EVERY Discovery session. Level 3 is every
 * dataset with a finished run, its channels as columns; level 2 is one dataset's channels, each optionally in
 * 2 · 4 · 8 equal time slices; level 1 is one channel over the WHOLE recording in time bins. Click down, crumb up.
 *
 * What is drawn is honest about what it does not know: a cell the algorithm never covered is hatched "not run",
 * a covered cell with nothing found is white, and a cell is shaded by detections per COVERED hour with the
 * covered share drawn as a bar along its foot — so a 6 h section run never looks like a 700 h one. The page
 * never writes: the Runs browser is session-scoped, so a level-1 click opens it only for a row whose newest run
 * is in the open session on the session's recording; otherwise the readout says where the row came from.
 *
 * URL keys are `dataset` / `channel` / `bin` / `chunks` / `norm` — `recording` and `channels` are the
 * session's own deep-link keys (session.ts) and must not be touched by this page. */
import { Fragment, useEffect, useMemo, useState } from 'react'
import { Breadcrumb, Button, EmptyState, Icon, InfoTip, Seg, cx, useQueryState } from '../kit'
import { Header } from '../shell/Header'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getMap, getMapChannel, getMapDataset } from '../api/discovery'
import type { DiscMapCell, DiscMapRow, DiscMapSession, DiscMapState } from '../api'
import { LoadFailed, Loading } from './chrome'

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

const fmtH = (h: number) => h === 0 ? '0 h' : h >= 100 ? `${Math.round(h)} h` : h >= 10 ? `${h.toFixed(1)} h` : `${h.toFixed(2)} h`
const rateOf = (c: DiscMapCell) => c.hours > 0 ? c.count / c.hours : null

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
      if (v == null) return 0
      const max = norm === 'map' && key !== 'human' ? mapMax : rowMax[key]
      return max > 0 ? v / max : 0
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, cellsOf, norm])
}

function cellTitle(row: DiscMapRow, where: string, cell: DiscMapCell): string {
  const rate = rateOf(cell)
  if (row.kind === 'human') {
    return cell.state === 'covered'
      ? `human · ${where} · ${cell.count} marked (${cell.interesting ?? 0} interesting, ${cell.seed ?? 0} seed) · ${fmtH(cell.hours)} looked at (${fmtH(cell.reviewedH ?? 0)} reviewed) · ${rate!.toFixed(2)} per h`
      : `human · ${where} · not reviewed: no verdict and no reviewed span here`
  }
  if (cell.state !== 'covered') return `${row.label} · ${where} · ${STATE_WORDS[cell.state]}`
  return `${row.label} · ${where} · ${cell.count} detection${cell.count === 1 ? '' : 's'} · ${fmtH(cell.hours)} covered · ${rate!.toFixed(2)} per h`
}

function rowTitle(row: DiscMapRow): string {
  if (row.kind === 'human') return 'human annotations · interesting and seed verdicts · the fixed reference'
  const bits = [row.kind === 'seed' ? `seed ${row.seedId ?? ''}${row.cut != null ? ` · cut ${row.cut}` : ''}` : `template ${row.template ?? ''}${row.version != null ? ` v${row.version}` : ''}`]
  if (row.band) bits.push(`band ${row.band}`)
  bits.push(`from session${row.sessionNames.length === 1 ? '' : 's'} ${row.sessionNames.join(', ') || '—'}`)
  bits.push(`${row.runs} channel run${row.runs === 1 ? '' : 's'}`)
  if (row.detail) bits.push(row.detail)
  return bits.join(' · ')
}

export function MapPage() {
  const [dataset, setDataset] = useQueryState('dataset', '')
  const [channel, setChannel] = useQueryState('channel', '')
  const [norm, setNorm] = useQueryState<Norm>('norm', 'row')
  const [chunksQ, setChunksQ] = useQueryState('chunks', '1')
  const [binQ, setBinQ] = useQueryState('bin', '3')
  const level = dataset && channel ? 1 : dataset ? 2 : 3
  const chunks = CHUNK_OPTIONS.includes(chunksQ) ? parseInt(chunksQ, 10) : 1
  const binH = BIN_OPTIONS.some(b => b.value === binQ) ? parseFloat(binQ) : 3
  const [crumbNames, setCrumbNames] = useState<Record<string, string>>({})
  const crumbs = [{ label: 'All datasets', onClick: level === 3 ? undefined : () => { setDataset(null); setChannel(null) } }]
  if (dataset) crumbs.push({ label: crumbNames[dataset] ?? dataset, onClick: level === 2 ? undefined : () => setChannel(null) })
  if (dataset && channel) crumbs.push({ label: channel, onClick: undefined })
  return (
    <>
      <Header workspace="Discovery" page="Map" subtitle="where each algorithm fires · every session · read-only" />
      <div className="k-page dsc-page" data-testid="discovery-map-page">
        <div className="k-page-inner" style={{ maxWidth: 1600, gap: 12 }}>
          <section className="k-card dsc-map" data-testid="map-card" data-level={level} aria-label="Detection map">
            <div className="dsc-card-head dsc-map-head">
              <h3>Detection map</h3>
              <InfoTip title="Detection map">
                Rows are algorithms, one per set of executed steps, read across every Discovery session; the human reference is first.
                A cell is shaded by detections per covered hour and carries a bar along its foot for the share of the column it covered.
                Hatched means the algorithm never ran there (for the human row: nobody looked there); white means it ran and found nothing.
                Click a dataset, then a channel, to zoom; the crumbs go back up. The page never writes.
              </InfoTip>
              <Breadcrumb items={crumbs} links testid="map-crumbs" />
              <span className="k-spacer" />
              {level !== 1 && <Seg size="sm" value={norm} onChange={v => setNorm(v)} label="shade" options={[{ value: 'row', label: 'per row', title: 'each row\'s busiest cell is 1' }, { value: 'map', label: 'whole map', title: 'the busiest machine cell on the map is 1; the human row stays per row' }]} testid="map-norm" />}
              {level === 2 && <Seg size="sm" value={String(chunks)} onChange={v => setChunksQ(v)} label="time chunks" options={CHUNK_OPTIONS.map(v => ({ value: v, label: v }))} testid="map-chunks" />}
              {level === 1 && <BinSeg value={String(binH)} onChange={v => setBinQ(v)} hours={crumbHours(crumbNames, dataset)} />}
              <Button size="sm" variant="link" icon="arrow-left" onClick={() => navigate('discovery/runs')} testid="map-to-runs">Runs</Button>
            </div>
            {level === 3 && <DatasetsLevel norm={norm} onDataset={(key, name) => { setCrumbNames(n => ({ ...n, [key]: name })); setDataset(key) }} />}
            {level === 2 && <DatasetLevel dataset={dataset} chunks={chunks} norm={norm} onName={(name, hours) => setCrumbNames(n => n[dataset] === name && n[`${dataset}:h`] === String(hours) ? n : { ...n, [dataset]: name, [`${dataset}:h`]: String(hours) })} onChannel={ch => setChannel(ch)} />}
            {level === 1 && <ChannelLevel dataset={dataset} channel={channel} binH={binH} onName={(name, hours) => setCrumbNames(n => n[dataset] === name && n[`${dataset}:h`] === String(hours) ? n : { ...n, [dataset]: name, [`${dataset}:h`]: String(hours) })} />}
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
  return <Seg size="sm" value={value} onChange={onChange} label="bin" options={options} testid="map-bin" />
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
  return (
    <button type="button" className={cx('dsc-map-cell', cell.state, wide && 'wide')} style={{ background: fill(row, cell, shade) }} title={cellTitle(row, where, cell)}
      data-testid="map-cell" data-state={cell.state} data-count={cell.count} data-hours={cell.hours} data-row={row.key} onClick={onClick} aria-label={cellTitle(row, where, cell)}>
      {/* partial coverage is a white track along the foot with a dark fill for the covered share — a 4 h run on a
          721 h channel is half a percent, so the fill keeps a minimum width and the track makes the gap visible */}
      {cell.state === 'covered' && share < 0.999 && <i className="cover-track"><i className="cover" style={{ width: `${Math.min(100, share * 100)}%` }} /></i>}
      {cell.state === 'discarded' && <span className="glyph">×</span>}
    </button>
  )
}

function RowLabel({ row }: { row: DiscMapRow }) {
  return <th scope="row" className="dsc-map-rowlabel" title={rowTitle(row)} data-testid={`map-row-${row.key}`}><i className="sw" style={{ background: row.colour }} />{row.label}</th>
}

/* ------------------------------------------------------------------ level 3: datasets × channels */
function DatasetsLevel({ norm, onDataset }: { norm: Norm; onDataset: (key: string, name: string) => void }) {
  const m = useSourced(getMap, [])
  const data = m.data
  const cellsOf = useMemo(() => (key: string) => data ? data.datasets.flatMap(d => Object.values(d.cells[key] ?? {})) : [], [data])
  const shade = useShades(data?.rows ?? [], cellsOf, norm)
  if (m.error) return <LoadFailed what="the detection map" error={m.error} onRetry={m.reload} />
  if (!data) return <Loading height={320} label="counting every session's runs" />
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
  return (
    <>
      <div className="dsc-map-wrap">
        <table className="dsc-map-table" data-testid="map-table">
          <thead>
            <tr>
              <th />
              {data.datasets.map(d => <Fragment key={d.file}><th className="ds" colSpan={d.channels.length} onClick={() => onDataset(d.key, d.name)} data-testid={`map-dataset-${d.key}`} title={`${d.name} · ${d.channels.length} channels · ${fmtH(d.hours)} — open its channels`}>{d.name} <span className="muted">· {d.channels.length} ch · {fmtH(d.hours)}</span></th><th className="gap" /></Fragment>)}
            </tr>
            <tr>
              <th className="corner">{norm === 'map' ? 'shade · whole map' : 'shade · per row'}</th>
              {data.datasets.map(d => <Fragment key={d.file}>{d.channels.map(c => <th key={c.name} className="ch"><span>{c.name}</span></th>)}<th className="gap" /></Fragment>)}
            </tr>
          </thead>
          <tbody>
            {data.rows.map(row => (
              <tr key={row.key} data-testid="map-row">
                <RowLabel row={row} />
                {data.datasets.map(d => <Fragment key={d.file}>
                  {d.channels.map(c => { const cell = d.cells[row.key]?.[c.name] ?? { count: 0, hours: 0, state: 'not_run' as const }; return <td key={c.name}><Cell row={row} cell={cell} where={`${d.name} ${c.name}`} shade={shade(row.key, cell)} share={c.hours > 0 ? cell.hours / c.hours : 0} onClick={() => onDataset(d.key, d.name)} /></td> })}
                  <td className="gap" />
                </Fragment>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Legend level={3} />
      {foot}
    </>
  )
}

/* ------------------------------------------------------------------ level 2: one dataset's channels, in chunks */
function DatasetLevel({ dataset, chunks, norm, onName, onChannel }: { dataset: string; chunks: number; norm: Norm; onName: (name: string, hours: number) => void; onChannel: (ch: string) => void }) {
  const m = useSourced(() => getMapDataset(dataset, chunks), [dataset, chunks])
  const data = m.data
  const cellsOf = useMemo(() => (key: string) => data ? Object.values(data.cells[key] ?? {}).flat() : [], [data])
  const shade = useShades(data?.rows ?? [], cellsOf, norm)
  // the crumb learns the dataset's name after the fact, in an effect: a parent setState during this render is a console error
  useEffect(() => { if (data) onName(data.name, data.hours) }, [data?.name, data?.hours]) // eslint-disable-line react-hooks/exhaustive-deps
  if (m.error) return <LoadFailed what={`the map of ${dataset}`} error={m.error} onRetry={m.reload} />
  if (!data) return <Loading height={320} label={`counting the runs on ${dataset}`} />
  const sliceH = (chHours: number) => chHours / chunks
  return (
    <>
      <div className="dsc-map-wrap">
        <table className="dsc-map-table" data-testid="map-table">
          <thead>
            <tr>
              <th className="corner">{data.name} · {fmtH(data.hours)} · {chunks === 1 ? 'one cell per channel' : `${chunks} equal time slices per channel`}</th>
              {data.channels.map(c => <th key={c.name} className="ch link" colSpan={chunks} onClick={() => onChannel(c.name)} data-testid={`map-channel-${c.name}`} title={`${c.name} · ${fmtH(c.hours)} — open its timeline`}><span>{c.name}</span></th>)}
            </tr>
          </thead>
          <tbody>
            {data.rows.map(row => (
              <tr key={row.key} data-testid="map-row">
                <RowLabel row={row} />
                {data.channels.map(c => (data.cells[row.key]?.[c.name] ?? []).map((cell, i) => {
                  const where = chunks === 1 ? c.name : `${c.name} · slice ${i + 1} of ${chunks} (${fmtH(i * sliceH(c.hours))}–${fmtH((i + 1) * sliceH(c.hours))})`
                  return <td key={`${c.name}-${i}`} className={cx(i === 0 && 'first', i === chunks - 1 && 'last')}><Cell row={row} cell={cell} where={where} shade={shade(row.key, cell)} share={sliceH(c.hours) > 0 ? cell.hours / sliceH(c.hours) : 0} wide={chunks === 1} onClick={() => onChannel(c.name)} /></td>
                }))}
              </tr>
            ))}
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

function ChannelLevel({ dataset, channel, binH, onName }: { dataset: string; channel: string; binH: number; onName: (name: string, hours: number) => void }) {
  const m = useSourced(() => getMapChannel(dataset, channel, binH), [dataset, channel, binH])
  const [hover, setHover] = useState<{ key: string; bin: number } | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const data = m.data
  useEffect(() => { if (data) onName(data.name, data.hours) }, [data?.name, data?.hours]) // eslint-disable-line react-hooks/exhaustive-deps
  if (m.error) return <LoadFailed what={`the timeline of ${channel}`} error={m.error} onRetry={m.reload} />
  if (!data) return <Loading height={320} label={`binning ${channel} over the whole recording`} />
  const n = data.nBins
  const ticks = ticksFor(data.hours)
  const openable = (row: DiscMapRow) => row.kind !== 'human' && row.latestSession === data.session.id && data.key === data.session.recording && !!row.latestRunKey
  const readout = (() => {
    if (!hover) return `${data.name} · ${channel} · ${fmtH(data.hours)} in ${n} bins of ${binH} h — move over a row to read a bin; click a bin to open it in Runs`
    const row = data.rows.find(r => r.key === hover.key)!
    const cell = data.cells[row.key]
    const t0 = hover.bin * binH, t1 = Math.min(data.hours, (hover.bin + 1) * binH)
    const cov = cell.covered[hover.bin]
    const what = row.kind === 'human' ? `${cell.counts[hover.bin]} marked` : `${cell.counts[hover.bin]} detection${cell.counts[hover.bin] === 1 ? '' : 's'}`
    const covText = cov >= 0.999 ? (row.kind === 'human' ? 'looked at throughout' : 'covered') : cov <= 0 ? (row.kind === 'human' ? 'not reviewed' : STATE_WORDS[cell.state === 'covered' ? 'not_run' : cell.state]) : `${Math.round(cov * 100)} % ${row.kind === 'human' ? 'looked at' : 'covered'}`
    const from = row.kind === 'human' ? '' : openable(row) ? ' · click to open in Runs' : ` · from session ${row.sessionNames.join(', ') || '?'} — not the open session, Runs cannot show it`
    return `${channel} · ${row.label} · ${fmtH(t0)}–${fmtH(t1)} · ${what} · ${covText}${from}`
  })()
  return (
    <>
      <svg width={0} height={0} style={{ position: 'absolute' }} aria-hidden><defs><pattern id="dsc-map-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#fff" /><rect width="2.5" height="6" fill="#e5e7eb" /></pattern></defs></svg>
      <div className="dsc-map-timeline" data-testid="map-timeline">
        {data.rows.map(row => {
          const cell = data.cells[row.key]
          const max = Math.max(0, ...cell.counts)
          const colour = row.kind === 'human' ? '#22a06b' : row.colour
          // one hatch rect per contiguous uncovered stretch, not one per bin: a mostly-unrun 721-bin row stays light
          const gaps: [number, number][] = []
          for (let i = 0; i < n; i++) { if (cell.covered[i] <= 0) { if (gaps.length && gaps[gaps.length - 1][1] === i) gaps[gaps.length - 1][1] = i + 1; else gaps.push([i, i + 1]) } }
          return (
            <div key={row.key} className="dsc-map-trow" data-testid="map-timeline-row" data-row={row.key} data-state={cell.state}>
              <span className="dsc-map-tlabel" title={rowTitle(row)}><i className="sw" style={{ background: row.colour }} />{row.label}<span className="muted small"> · {cell.counts.reduce((a, b) => a + b, 0)}</span></span>
              <svg className="dsc-map-tsvg" viewBox={`0 0 ${n * 10} 10`} preserveAspectRatio="none" width="100%" height={14} role="img" aria-label={`${row.label} on ${channel} per ${binH} h`}
                onMouseMove={e => { const r = e.currentTarget.getBoundingClientRect(); setHover({ key: row.key, bin: Math.max(0, Math.min(n - 1, Math.floor((e.clientX - r.left) / r.width * n))) }) }}
                onMouseLeave={() => setHover(h => (h?.key === row.key ? null : h))}
                onClick={e => {
                  const r = e.currentTarget.getBoundingClientRect(); const bin = Math.max(0, Math.min(n - 1, Math.floor((e.clientX - r.left) / r.width * n)))
                  if (openable(row)) navigate(`discovery/runs?run=${encodeURIComponent(row.latestRunKey!)}&ch=${encodeURIComponent(channel)}&at=${bin * binH}`)
                  else setNote(row.kind === 'human' ? 'the human row has no detections to browse' : `${row.label} came from session ${row.sessionNames.join(', ') || '?'}${data.key !== data.session.recording ? ` on ${data.name}` : ''} — the open session's Runs page cannot show it`)
                }}>
                <rect x={0} y={0} width={n * 10} height={10} fill="#f3f4f6" />
                {gaps.map(([a, b]) => <rect key={`g${a}`} x={a * 10} y={0} width={(b - a) * 10} height={10} fill="url(#dsc-map-hatch)" data-testid="map-gap" />)}
                {cell.counts.map((c, i) => c > 0 ? <rect key={i} x={i * 10 + 0.3} y={0} width={9.4} height={10} fill={colour} opacity={opacityFor(c, max)} data-testid="map-bin" /> : null)}
              </svg>
            </div>
          )
        })}
        <div className="dsc-map-axis mono">{ticks.map((t, i) => <span key={i} style={{ left: `${(t.h / data.hours) * 100}%` }} className={cx(i === 0 && 'first', t.h >= data.hours - 1e-9 && 'last')}>{t.label}</span>)}</div>
      </div>
      <div className="dsc-map-readout" data-testid="map-readout"><Icon name="eye" size={12} /> {readout}</div>
      {note && <div className="dsc-map-readout muted" data-testid="map-note">{note}</div>}
      <Legend level={1} />
    </>
  )
}
