/* The Signal drawer (frames explore-2b annotations, 2c detections, 2d shortcuts; spec §5.3): tabs, ten filter
   fields with a match count, CSV/JSON export of the filtered rows, a sortable selectable table (6 rows a page),
   bulk actions and Send selected to Review. On the canon channel the rows are demo canon (708 / 1,284); on any
   other channel they are the live spans of the channel, and the filters the database cannot answer are
   disabled with that reason. Detections are machine-only: no tagging or staging on that tab (§4.1). */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Spans } from '../api'
import { useSourced } from '../api/seam'
import { FILTER_VOCAB, getShortcuts, type AnnotationRow, type DetectionRow, type SignalDemo } from '../api/explore'
import { Badge, Button, Dropdown, Icon, IconButton, InfoTip, Kbd, Pager, Popover, Table, Tabs, TextField, fmtInt, recordDemoWrite, useDemoState, useNotWired, useQueryState, type Column, type MenuItem, type SortState } from '../kit'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { DemoTag } from './bits'
import type { DrawerTab } from './Ribbons'
import { VERDICT_COLOUR } from './util'

type ARow = AnnotationRow & { live?: boolean }
type DRow = DetectionRow & { live?: boolean }
interface AFilters { verdict: string; source: string; element: string; quality: string; structure: string; status: string; stl: string; duration: string; ids: string; text: string }
interface DFilters { run: string; method: string; score: string; adjudication: string; family: string; duration: string; overlaps: string; channel: string; ids: string; scope: string }
const A_ANY: AFilters = { verdict: 'any', source: 'any', element: 'any', quality: 'any', structure: 'any', status: 'any', stl: 'any', duration: 'any', ids: '', text: '' }
const D_ANY: DFilters = { run: 'any', method: 'any', score: '', adjudication: 'any', family: 'any', duration: 'any', overlaps: 'either', channel: 'this', ids: '', scope: 'channel' }
const PAGE = 6
const ID_RULE = /^\s*\d+(\s*,\s*\d+)*\s*$/
const ADJ_COLOUR: Record<string, string> = { ...VERDICT_COLOUR, unadjudicated: 'var(--amber)' }

const opts = (xs: readonly string[], any = 'any'): MenuItem[] => [{ value: 'any', label: any }, ...xs.map(x => ({ value: x, label: x }))]
function durBand(s: number) { return s < 60 ? 'short' : s <= 900 ? 'medium' : 'long' }
function parseIds(s: string): Set<number> | null { return s.trim() && ID_RULE.test(s) ? new Set(s.split(',').map(x => Number(x.trim()))) : null }
function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
const csvCell = (v: unknown) => { const s = Array.isArray(v) ? v.join('; ') : v && typeof v === 'object' ? JSON.stringify(v) : String(v ?? ''); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s }

export function SignalDrawer({ channelKey, channelName, fs, demo, live, tab, setTab, onClose, view, onOpenRow, focusSignal }: {
  channelKey: string; channelName: string; fs: number; demo: SignalDemo | null; live: Spans | null
  tab: DrawerTab; setTab: (t: DrawerTab) => void; onClose: () => void; view: [number, number]
  onOpenRow: (r: { id: number; start_s: number; end_s: number; kind: 'annotated' | 'detected'; row: ARow | DRow }) => void; focusSignal: number
}) {
  const toast = useToast()
  const notWired = useNotWired()
  const [filtersOpen, setFiltersOpenQ] = useQueryState<string>('filters', 'open')
  const [aF, setAF] = useDemoState<AFilters>(`explore.signal.af.${channelKey}`, () => (demo ? { ...A_ANY, verdict: 'interesting', duration: 'medium', text: 'sharkfin' } : A_ANY))
  const [dF, setDF] = useDemoState<DFilters>(`explore.signal.df.${channelKey}`, () => (demo ? { ...D_ANY, method: 'matrix profile', score: '0.60' } : D_ANY))
  const [extraTags, setExtraTags] = useDemoState<Record<number, string[]>>(`explore.signal.extraTags.${channelKey}`, () => ({}))
  const [selA, setSelA] = useDemoState<string[]>(`explore.signal.selA.${channelKey}`, () => (demo ? demo.defaultSelectedAnnotations.map(String) : []))
  const [selD, setSelD] = useDemoState<string[]>(`explore.signal.selD.${channelKey}`, () => (demo ? demo.defaultSelectedDetections.map(String) : []))
  const [sortA, setSortA] = useState<SortState>({ key: 'start', dir: 'asc' })
  const [sortD, setSortD] = useState<SortState>({ key: 'score', dir: 'desc' })
  const [page, setPage] = useState(1)
  const bodyRef = useRef<HTMLDivElement>(null)

  const annotations: ARow[] = useMemo(() => {
    const base: ARow[] = demo ? demo.annotations : (live?.annotations ?? []).map(a => ({
      id: a.id, start: Math.round(a.start_s * fs), end: Math.round(a.end_s * fs), verdict: a.verdict as ARow['verdict'], tags: a.tag ? [a.tag] : [], source: a.source as ARow['source'], note: a.note ?? '',
      element: '', quality: '', structure: '', status: '', spikeTrainLength: '', live: true,
    }))
    return Object.keys(extraTags).length ? base.map(r => (extraTags[r.id] ? { ...r, tags: [...r.tags, ...extraTags[r.id].filter(t => !r.tags.includes(t))] } : r)) : base
  }, [demo, live, fs, extraTags])
  const detections: DRow[] = useMemo(() => demo ? demo.detections : (live?.detections ?? []).map(d => ({
    id: d.id, runId: `#${d.run_id}`, runName: `run ${d.run_id}`, method: '', start: Math.round(d.start_s * fs), end: Math.round(d.end_s * fs), score: d.score ?? NaN,
    adjudication: 'unadjudicated' as const, family: null, live: true,
  })), [demo, live, fs])
  const isLive = !demo
  const liveReason = 'not in this database'

  // ---- filtering ----
  const aIdsBad = !!aF.ids.trim() && !ID_RULE.test(aF.ids)
  const dIdsBad = !!dF.ids.trim() && !ID_RULE.test(dF.ids)
  const scoreN = dF.score.trim() === '' ? null : Number(dF.score)
  const scoreBad = scoreN !== null && !(scoreN >= 0 && scoreN <= 1)
  const aRows = useMemo(() => {
    const ids = parseIds(aF.ids), q = aF.text.trim().toLowerCase()
    return annotations.filter(r =>
      (aF.verdict === 'any' || r.verdict === aF.verdict) && (aF.source === 'any' || r.source === aF.source) &&
      (aF.element === 'any' || r.element === aF.element) && (aF.quality === 'any' || r.quality === aF.quality) &&
      (aF.structure === 'any' || r.structure === aF.structure) && (aF.status === 'any' || r.status === aF.status) &&
      (aF.stl === 'any' || r.spikeTrainLength === aF.stl) && (aF.duration === 'any' || durBand((r.end - r.start) / fs) === aF.duration) &&
      (!ids || ids.has(r.id)) && (!q || r.note.toLowerCase().includes(q) || r.tags.some(t => t.includes(q))))
  }, [annotations, aF, fs])
  const annIntervals = useMemo(() => [...annotations].sort((p, q) => p.start - q.start).map(a => [a.start, a.end] as const), [annotations])
  const overlapsAnn = (s: number, e: number) => {
    let lo = 0, hi = annIntervals.length
    while (lo < hi) { const m = (lo + hi) >> 1; if (annIntervals[m][0] < e) lo = m + 1; else hi = m }
    for (let i = lo - 1; i >= 0 && i >= lo - 40; i--) if (annIntervals[i][1] > s) return true
    return false
  }
  const dRows = useMemo(() => {
    const ids = parseIds(dF.ids)
    const [v0, v1] = [view[0] * fs, view[1] * fs]
    return detections.filter(r =>
      (dF.run === 'any' || r.runId === dF.run) && (dF.method === 'any' || r.method === dF.method) &&
      (scoreN === null || scoreBad || r.score >= scoreN) && (dF.adjudication === 'any' || r.adjudication === dF.adjudication) &&
      (dF.family === 'any' || (dF.family === 'none' ? !r.family : r.family?.id === dF.family)) &&
      (dF.duration === 'any' || durBand((r.end - r.start) / fs) === dF.duration) &&
      (dF.overlaps === 'either' || overlapsAnn(r.start, r.end) === (dF.overlaps === 'yes')) &&
      (!ids || ids.has(r.id)) && (dF.scope === 'channel' || (r.end > v0 && r.start < v1)))
  }, [detections, dF, scoreN, scoreBad, view, fs, annIntervals])  // eslint-disable-line react-hooks/exhaustive-deps
  const aActive = (Object.keys(A_ANY) as (keyof AFilters)[]).filter(k => aF[k] !== A_ANY[k]).length
  const dActive = (Object.keys(D_ANY) as (keyof DFilters)[]).filter(k => dF[k] !== D_ANY[k]).length

  const sortRows = <T extends ARow | DRow>(rows: T[], st: SortState, cols: Column<T>[]) => {
    if (!st) return rows
    const f = cols.find(c => c.key === st.key)?.sortValue
    if (!f) return rows
    const m = st.dir === 'asc' ? 1 : -1
    return [...rows].sort((p, q) => { const a = f(p), b = f(q); return (typeof a === 'number' && typeof b === 'number' ? a - b : String(a ?? '').localeCompare(String(b ?? ''))) * m })
  }

  const aCols: Column<ARow>[] = [
    { key: 'id', header: 'id', sortValue: r => r.id, render: r => fmtInt(r.id), width: 70 },
    { key: 'start', header: 'start · sample', sortValue: r => r.start, render: r => fmtInt(r.start) },
    { key: 'end', header: 'end · sample', sortValue: r => r.end, render: r => fmtInt(r.end) },
    { key: 'duration', header: 'duration', sortValue: r => r.end - r.start, render: r => `${fmtInt((r.end - r.start) / fs)} s` },
    { key: 'verdict', header: 'verdict', sortValue: r => r.verdict, render: r => <span style={{ color: VERDICT_COLOUR[r.verdict] ?? 'inherit' }}>{r.verdict}</span> },
    { key: 'tags', header: 'tags', sortValue: r => r.tags.join(','), render: r => r.tags.length ? r.tags.join(', ') : '—' },
    { key: 'source', header: 'source', sortValue: r => r.source, render: r => r.source },
    { key: 'note', header: 'note', sortValue: r => r.note, render: r => r.note },
  ]
  const dCols: Column<DRow>[] = [
    { key: 'id', header: 'id', sortValue: r => r.id, render: r => fmtInt(r.id), width: 70 },
    { key: 'run', header: 'run', sortValue: r => r.runId, render: r => `${r.runName} · ${r.runId}` },
    { key: 'method', header: 'method', sortValue: r => r.method, render: r => r.method || '—' },
    { key: 'start', header: 'start · sample', sortValue: r => r.start, render: r => fmtInt(r.start) },
    { key: 'end', header: 'end · sample', sortValue: r => r.end, render: r => fmtInt(r.end) },
    { key: 'score', header: 'score', sortValue: r => (Number.isFinite(r.score) ? r.score : -1), render: r => (Number.isFinite(r.score) ? r.score.toFixed(2) : '—') },
    { key: 'adjudication', header: 'adjudication', sortValue: r => r.adjudication, render: r => (r.live ? <span className="muted">—</span> : <span style={{ color: ADJ_COLOUR[r.adjudication] ?? 'inherit' }}>{r.adjudication}</span>) },
    { key: 'family', header: 'family', sortValue: r => r.family?.id ?? '', render: r => (r.family ? `${r.family.id} · d ${r.family.d.toFixed(2)}` : '—') },
  ]
  const sortedA = useMemo(() => sortRows(aRows, sortA, aCols), [aRows, sortA])  // eslint-disable-line react-hooks/exhaustive-deps
  const sortedD = useMemo(() => sortRows(dRows, sortD, dCols), [dRows, sortD])  // eslint-disable-line react-hooks/exhaustive-deps
  const cur = tab === 'annotations' ? sortedA : sortedD
  const pageCount = Math.max(1, Math.ceil(cur.length / PAGE))
  useEffect(() => { setPage(1) }, [tab, aF, dF, sortA, sortD])
  const p = Math.min(page, pageCount)
  const pageRows = cur.slice((p - 1) * PAGE, p * PAGE)

  useEffect(() => {
    if (!focusSignal) return
    if (filtersOpen === 'closed') setFiltersOpenQ(null)
    const id = window.setTimeout(() => bodyRef.current?.querySelector<HTMLElement>('.ex-fgrid button:not([disabled]), .ex-fgrid input:not([disabled])')?.focus(), 60)
    return () => window.clearTimeout(id)
  }, [focusSignal])  // eslint-disable-line react-hooks/exhaustive-deps

  const sel = tab === 'annotations' ? selA : selD
  const setSel = tab === 'annotations' ? setSelA : setSelD
  const nSel = sel.length
  const noSel = 'select rows first'
  const exportRows = (kind: 'csv' | 'json') => {
    const rows = tab === 'annotations' ? sortedA : sortedD
    const name = `${channelName}_${tab}.${kind}`
    if (kind === 'json') download(name, JSON.stringify(rows, null, 1), 'application/json')
    else {
      const keys = Object.keys(rows[0] ?? {}).filter(k => k !== 'live')
      download(name, [keys.join(','), ...rows.map(r => keys.map(k => csvCell((r as unknown as Record<string, unknown>)[k])).join(','))].join('\n'), 'text/csv')
    }
    toast.push({ text: `exported ${fmtInt(rows.length)} filtered ${tab} to ${name}` })
  }
  const sendToReview = () => {
    recordDemoWrite('explore', 'send-to-review', { queue: 'Explore spans', kind: tab, ids: sel.map(Number), channel: channelName })
    toast.push({ text: tab === 'annotations' ? `${nSel} spans sent to Review · Explore spans queue` : `${nSel} detections sent to Review`, action: { label: 'Open Review →', onClick: () => navigate('review') } })
    setSel([])
  }
  const [tagOpen, setTagOpen] = useState(false)
  const [tagText, setTagText] = useState('')
  const tagRef = useRef<HTMLButtonElement>(null)
  const tagBad = !!tagText.trim() && !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(tagText.trim())
  const applyTag = () => {
    const t = tagText.trim(); if (!t || tagBad) return
    setExtraTags(m => { const next = { ...m }; for (const id of selA.map(Number)) next[id] = [...new Set([...(next[id] ?? []), t])]; return next })
    recordDemoWrite('explore', 'tag-annotations', { ids: selA.map(Number), tag: t })
    toast.push({ text: `tagged ${nSel} annotation${nSel === 1 ? '' : 's'} ${t}` }); setTagText(''); setTagOpen(false)
  }

  const aCell = (label: string, info: string, control: ReactNode, active = false) => <div className={`cell${active ? ' active' : ''}`}><span className="lbl">{label}<InfoTip title={label} size={11}>{info}</InfoTip></span>{control}</div>
  const dd = (label: string, info: string, value: string, onChange: (v: string) => void, options: MenuItem[], def: string, liveOk = true, testid?: string) =>
    aCell(label, info, <Dropdown block size="sm" value={value} onChange={onChange} options={options} active={value !== def} disabled={isLive && !liveOk} disabledReason={liveReason} testid={testid ?? `filter-${label.replace(/[^a-z]+/gi, '-')}`} ariaLabel={label} />)

  const header = (
    <div className="ex-drawer-head">
      <IconButton icon="chevron-down" label="collapse the drawer (D)" onClick={onClose} testid="drawer-collapse-icon" />
      <Tabs variant="soft" value={tab} onChange={v => setTab(v as DrawerTab)} ariaLabel="drawer tabs" testid="drawer-tabs"
        items={[{ value: 'annotations', label: 'Annotations', count: fmtInt(annotations.length) }, { value: 'detections', label: 'Detections', count: fmtInt(detections.length) }, { value: 'shortcuts', label: 'Shortcuts' }]} />
      {demo && tab !== 'shortcuts' && <DemoTag title="these rows are §0 demo canon for CH4_A2, not your database" />}
      <span className="grow" />
      {tab !== 'shortcuts' && <>
        <Button icon="download" size="sm" onClick={() => exportRows('csv')} disabled={!cur.length} disabledReason="no rows match the filters" testid="export-csv">Export CSV</Button>
        <Button icon="download" size="sm" onClick={() => exportRows('json')} disabled={!cur.length} disabledReason="no rows match the filters" testid="export-json">Export JSON</Button>
      </>}
      <button type="button" className="ex-link" onClick={onClose} data-testid="drawer-collapse">collapse</button>
    </div>
  )

  if (tab === 'shortcuts') {
    return <Shortcuts header={header} />
  }

  const active = tab === 'annotations' ? aActive : dActive
  const clear = () => (tab === 'annotations' ? setAF(A_ANY) : setDF(D_ANY))
  return (
    <div className="card ex-drawer" ref={bodyRef} data-testid="signal-drawer" data-tab={tab}>
      {header}
      <div className="ex-filters-head">
        <button type="button" className="ex-disclosure" aria-expanded={filtersOpen !== 'closed'} onClick={() => setFiltersOpenQ(filtersOpen === 'closed' ? null : 'closed')} data-testid="filters-toggle">
          <Icon name="chevron-down" size={13} className={filtersOpen === 'closed' ? 'rot' : ''} /><b>Filters</b>
        </button>
        {active > 0 && <Badge tone="blue" testid="filters-active">{active} active</Badge>}
        <button type="button" className="ex-link" onClick={clear} data-testid="filters-clear">clear</button>
        <span className="grow" />
        <span className="mono muted small" data-testid="match-count">{fmtInt(cur.length)} of {fmtInt(tab === 'annotations' ? annotations.length : detections.length)} {tab} match</span>
      </div>
      {filtersOpen !== 'closed' && (tab === 'annotations' ? (
        <div className="ex-fgrid" data-testid="filter-grid">
          {dd('verdict', 'Human verdicts from Review.', aF.verdict, v => setAF({ ...aF, verdict: v }), opts(['seed', 'interesting', 'not_interesting', 'artifact', 'unsure']), 'any')}
          {dd('source', 'Where the annotation came from.', aF.source, v => setAF({ ...aF, source: v }), opts(FILTER_VOCAB.source), 'any')}
          {dd('element', 'Element vocabulary (proposed; Settings › Vocabulary).', aF.element, v => setAF({ ...aF, element: v }), opts(FILTER_VOCAB.element), 'any', false)}
          {dd('quality', 'Recording quality at the span (proposed).', aF.quality, v => setAF({ ...aF, quality: v }), opts(FILTER_VOCAB.quality), 'any', false)}
          {dd('structure', 'Isolated, repeating or nested (proposed).', aF.structure, v => setAF({ ...aF, structure: v }), opts(FILTER_VOCAB.structure), 'any', false)}
          {dd('status', 'Annotation workflow status (proposed).', aF.status, v => setAF({ ...aF, status: v }), opts(FILTER_VOCAB.status), 'any', false)}
          {dd('spike-train length', 'Spikes in the train (proposed).', aF.stl, v => setAF({ ...aF, stl: v }), opts(FILTER_VOCAB.spikeTrainLength), 'any', false)}
          {dd('duration band', 'short < 60 s · medium 60–900 s · long > 900 s (proposed bands).', aF.duration, v => setAF({ ...aF, duration: v }), [{ value: 'any', label: 'any' }, ...FILTER_VOCAB.durationBand], 'any')}
          {aCell('id', 'Whole numbers separated by commas.', <span className="ex-fcol"><TextField size="sm" block value={aF.ids} onChange={v => setAF({ ...aF, ids: v })} placeholder="e.g. 42, 108" invalid={aIdsBad} testid="filter-id" />{aIdsBad && <span className="k-field-error" role="alert">ids are whole numbers separated by commas</span>}</span>, !!aF.ids)}
          {aCell('note / tags', 'Substring over the note and the tags.', <TextField size="sm" block value={aF.text} onChange={v => setAF({ ...aF, text: v })} placeholder="any" testid="filter-text" />, !!aF.text)}
        </div>
      ) : (
        <div className="ex-fgrid" data-testid="filter-grid">
          {dd('run', 'Runs that wrote detections on this channel.', dF.run, v => setDF({ ...dF, run: v }), [{ value: 'any', label: `all · ${new Set(detections.map(d => d.runId)).size}` }, ...[...new Set(detections.map(d => d.runId))].map(r => ({ value: r, label: r }))], 'any')}
          {dd('method', 'Detection method of the run.', dF.method, v => setDF({ ...dF, method: v }), opts([...new Set(detections.map(d => d.method).filter(Boolean))]), 'any', false)}
          {aCell('score ≥', 'Detector score between 0 and 1.', <span className="ex-fcol"><TextField size="sm" block value={dF.score} onChange={v => setDF({ ...dF, score: v })} placeholder="any" invalid={scoreBad} testid="filter-score" />{scoreBad && <span className="k-field-error" role="alert">score is between 0 and 1</span>}</span>, !!dF.score)}
          {dd('adjudication', 'A human verdict on the detection, from Review.', dF.adjudication, v => setDF({ ...dF, adjudication: v }), opts(['unadjudicated', 'seed', 'interesting', 'not_interesting', 'artifact', 'unsure']), 'any', false)}
          {dd('nearest family', 'Closest Library family and its distance.', dF.family, v => setDF({ ...dF, family: v }), [{ value: 'any', label: 'any' }, { value: 'none', label: 'none' }, ...FILTER_VOCAB.families.map(f => ({ value: f, label: f }))], 'any', false)}
          {dd('duration band', 'short < 60 s · medium 60–900 s · long > 900 s.', dF.duration, v => setDF({ ...dF, duration: v }), [{ value: 'any', label: 'any' }, ...FILTER_VOCAB.durationBand], 'any')}
          {dd('overlaps annotation', 'Whether a human annotation overlaps the detection.', dF.overlaps, v => setDF({ ...dF, overlaps: v }), [{ value: 'either', label: 'either' }, { value: 'yes', label: 'yes' }, { value: 'no', label: 'no' }], 'either')}
          {dd('channel', 'Rows of this channel only; other channels open from their own page.', dF.channel, v => setDF({ ...dF, channel: v }), [{ value: 'this', label: `${channelName} only` }, { value: 'all', label: 'all channels', disabled: true, reason: 'other channels load on their own Signal page' }], 'this')}
          {aCell('id', 'Whole numbers separated by commas.', <span className="ex-fcol"><TextField size="sm" block value={dF.ids} onChange={v => setDF({ ...dF, ids: v })} placeholder="e.g. 412" invalid={dIdsBad} testid="filter-id" />{dIdsBad && <span className="k-field-error" role="alert">ids are whole numbers separated by commas</span>}</span>, !!dF.ids)}
          {dd('scope', 'The whole channel, or only the span in view.', dF.scope, v => setDF({ ...dF, scope: v }), [{ value: 'channel', label: 'whole channel' }, { value: 'span', label: 'visible span' }], 'channel')}
        </div>
      ))}
      <div className="ex-drawer-table">
        {tab === 'annotations'
          ? <Table<ARow> columns={aCols} rows={pageRows as ARow[]} rowKey={r => String(r.id)} selection="multi" selected={selA} onSelectionChange={k => setSelA(mergePage(selA, pageRows.map(r => String(r.id)), k))} dense
            sort={sortA} onSortChange={setSortA} onRowClick={r => onOpenRow({ id: r.id, start_s: r.start / fs, end_s: r.end / fs, kind: 'annotated', row: r })} testid="drawer-table"
            empty={<span className="muted mono small">no annotation matches these filters · <button type="button" className="ex-link" onClick={clear}>clear</button></span>} />
          : <Table<DRow> columns={dCols} rows={pageRows as DRow[]} rowKey={r => String(r.id)} selection="multi" selected={selD} onSelectionChange={k => setSelD(mergePage(selD, pageRows.map(r => String(r.id)), k))} dense
            sort={sortD} onSortChange={setSortD} onRowClick={r => onOpenRow({ id: r.id, start_s: r.start / fs, end_s: r.end / fs, kind: 'detected', row: r })} testid="drawer-table"
            empty={<span className="muted mono small">no detection matches these filters · <button type="button" className="ex-link" onClick={clear}>clear</button></span>} />}
      </div>
      <div className="ex-drawer-foot">
        <span className="mono small" data-testid="selected-count">{nSel} selected</span>
        {tab === 'annotations' ? <>
          <Button ref={tagRef} size="sm" iconRight="tag" disabled={!nSel} disabledReason={noSel} onClick={() => setTagOpen(o => !o)} testid="add-tag-bulk">Add tag</Button>
          <Button size="sm" iconRight="layers" disabled={!nSel} disabledReason={noSel} testid="stage-analyse"
            onClick={() => { recordDemoWrite('explore', 'stage-for-analyse', { ids: selA.map(Number), channel: channelName }); toast.push({ text: `${nSel} annotation${nSel === 1 ? '' : 's'} staged for Analyse` }) }}>Stage for Analyse</Button>
        </> : <>
          <Button size="sm" iconRight="arrow-right" disabled={!nSel} disabledReason={noSel} onClick={() => notWired(`send ${nSel} detections to Analyse as a SpanSet source (POST /api/chain/source)`)} testid="analyse-events">Analyse events</Button>
          <span className="muted mono small"><Icon name="info" size={11} /> machine detections · indices are samples into the whole recording</span>
        </>}
        <span className="grow" />
        <Pager format="range" page={p} pageCount={pageCount} total={cur.length} pageSize={PAGE} onPage={setPage} label="page" testid="drawer-pager" />
        <Button variant="primary" size="sm" iconRight="arrow-right" disabled={!nSel} disabledReason={noSel} onClick={sendToReview} testid="send-to-review">Send selected to Review</Button>
      </div>
      <Popover open={tagOpen} onClose={() => setTagOpen(false)} anchorRef={tagRef} width={260} title={`Tag ${nSel} annotation${nSel === 1 ? '' : 's'}`} testid="bulk-tag-popover">
        <div className="col" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <TextField value={tagText} onChange={v => setTagText(v.toLowerCase())} placeholder="e.g. burst" onEnter={applyTag} invalid={tagBad} testid="bulk-tag-input" autoFocus />
          {tagBad && <span className="k-field-error" role="alert">tags are lower-case words joined by -</span>}
          <Button variant="primary" size="sm" onClick={applyTag} disabled={!tagText.trim() || tagBad} disabledReason={tagBad ? 'fix the tag first' : 'type a tag'} testid="bulk-tag-apply">Apply to {nSel}</Button>
        </div>
      </Popover>
    </div>
  )
}

/** Table selection is per page: merge the page's new selection into the full selection. */
function mergePage(all: string[], pageKeys: string[], next: string[]): string[] {
  return [...all.filter(k => !pageKeys.includes(k)), ...next]
}

function Shortcuts({ header }: { header: ReactNode }) {
  const read = useSourced(getShortcuts, [])
  const rows = read.data ?? []
  return (
    <div className="card ex-drawer" data-testid="signal-drawer" data-tab="shortcuts">
      {header}
      <div className="ex-short-top">
        <span className="muted mono small"><Icon name="info" size={11} /> verdict keys live in Settings › Vocabulary and apply in Review</span>
        <button type="button" className="ex-link" onClick={() => navigate('settings/keyboard')} data-testid="edit-shortcuts">Edit shortcuts in Settings › Keyboard &amp; behaviour →</button>
      </div>
      {read.error && <div className="error-card" role="alert">shortcut list failed: {read.error.message}</div>}
      <div className="ex-short-grid" data-testid="shortcuts-grid">
        {rows.map(c => (
          <div key={c.column} className="colm">
            <h4>{c.column}</h4>
            {c.rows.map(r => <div key={r.label} className="kr"><span className="keys">{r.keys.map(k => <Kbd key={k}>{k}</Kbd>)}</span><span>{r.label}</span></div>)}
          </div>
        ))}
      </div>
    </div>
  )
}

