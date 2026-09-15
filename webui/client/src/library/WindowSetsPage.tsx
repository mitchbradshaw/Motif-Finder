/* library.window-sets — frame library-6 (§8.8, §6.9, P18): every saved window set with its split, labelled share, users
 * and train-safety; the rail shows how it was made, the split plan per channel, spacing checks, class coverage (now and at
 * save), used by, and the hand-offs. Delete is blocked while anything uses the set. */
import { useMemo, useRef, useState } from 'react'
import {
  BandStrip, Button, Callout, Checkbox, Checklist, EmptyState, Icon, InfoTip, KeyValue, Modal, Page, Popover, Seg, SelectField, Table, TextField, fmtInt, recordDemoWrite, useDemoState, useQueryState,
  type Column, type SortState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { CLASS_COLOURS, RECORDING_GROUPS, REVIEW_QUEUE_CAP, getWindowSets, type SetCheck, type WindowSetRow } from '../api/library'
import { LoadFailed, Loading, SectionBar, useExternalNavKey, useQueueToast } from './chrome'

const SPLIT_COLOUR = { train: '#9cc3f7', validation: '#ff9f0a', test: '#34c759', gap: '#e9ebef' }
const CHECK_TONE: Record<SetCheck, string> = { 'train-safe': 't-green', 'fs inferred': 't-amber', 'test sample': 't-blue', 'not train-safe': 't-red', 'gap < window': 't-red' }
const NOT_SAFE: SetCheck[] = ['not train-safe', 'gap < window']
const words = ['no', 'one', 'two', 'three', 'four', 'five', 'six']

export function WindowSetsPage() {
  const sets = useSourced(getWindowSets, [])
  const [deleted, setDeleted] = useDemoState<string[]>('library.windowSets.deleted', () => [])
  const [setsQ] = useQueryState('sets', '')
  const navKey = useExternalNavKey()
  const rows = useMemo(() => (setsQ === 'empty' ? [] : (sets.data ?? []).filter(s => !deleted.includes(s.id))), [sets.data, deleted, setsQ])
  const { push } = useToast()
  const [, setModal] = useQueryState('modal', '')
  return (
    <>
      <Header workspace="Library" page="Window sets" subtitle={`${sets.data ? rows.length : '…'} saved`} search="Search spans, runs, families" demo={sets.source === 'demo'} />
      <Page testid="window-sets-page">
        <SectionBar section="window-sets" windowSetsCount={sets.data ? rows.length : undefined}
          actions={<span className="row lib-ui-btn" style={{ gap: 8 }}>
            <Button icon="link" testid="new-from-analyse" onClick={() => navigate('analyse/training')}>New from Analyse</Button>
            <Button icon="download" testid="window-set-import" onClick={() => setModal('import')}>Import</Button>
          </span>} />
        {sets.error && <LoadFailed what="the window sets" error={sets.error} onRetry={sets.reload} />}
        {sets.loading && <Loading height={620} testid="window-sets-loading" />}
        {sets.data && (rows.length === 0 && setsQ === 'empty'
          ? <div className="k-card" style={{ padding: 30 }}><EmptyState icon="grid" testid="window-sets-none" title="No saved window sets yet" caption="Save one from any block whose output is a WindowSet (e.g. sliding windows in a training chain)"
            action={<Button variant="primary" icon="link" onClick={() => navigate('analyse/training')}>New from Analyse</Button>} /></div>
          : <WindowSets key={navKey} rows={rows} onDelete={id => { setDeleted(d => [...d, id]); recordDemoWrite('library', 'window-set.delete', { id }); push({ text: `Deleted ${id} · not wired yet: DELETE /api/window-sets/${id}`, action: { label: 'Undo', onClick: () => setDeleted(d => d.filter(x => x !== id)) } }) }} />)}
      </Page>
    </>
  )
}

function WindowSets({ rows, onDelete }: { rows: WindowSetRow[]; onDelete: (id: string) => void }) {
  const [safeQ, setSafeQ] = useQueryState<'all' | 'train-safe' | 'not-train-safe'>('safe', 'all')
  const [recQ, setRecQ] = useQueryState('rec', '')
  const [labelledQ, setLabelledQ] = useQueryState<'any' | 'none' | 'some' | 'full'>('labelled', 'any')
  const [usedQ, setUsedQ] = useQueryState<'any' | 'used' | 'unused'>('used', 'any')
  const [setQ, setSetQ] = useQueryState('set', rows[0]?.id ?? '')
  const [modal, setModal] = useQueryState('modal', '')
  const [sortSel, setSortSel] = useState<'last used' | 'name' | 'windows' | 'labelled' | 'saved'>('last used')
  const [sort, setSort] = useState<SortState>(null)
  const recRef = useRef<HTMLButtonElement>(null), labRef = useRef<HTMLButtonElement>(null), usedRef = useRef<HTMLButtonElement>(null)
  const [pop, setPop] = useState<'' | 'rec' | 'lab' | 'used'>('')
  const recs = recQ ? recQ.split(',') : []
  const filtered = rows.filter(r =>
    (safeQ === 'all' || (safeQ === 'train-safe' ? r.check === 'train-safe' : r.check !== 'train-safe'))
    && (!recs.length || r.recordingKeys.some(k => recs.includes(k)) || (recs.includes('review') && r.recording === 'Review verdicts'))
    && (labelledQ === 'any' || (labelledQ === 'none' ? r.labelledPct === 0 : labelledQ === 'full' ? r.labelledPct === 100 : r.labelledPct > 0 && r.labelledPct < 100))
    && (usedQ === 'any' || (usedQ === 'used' ? r.usedBy.length > 0 : r.usedBy.length === 0)))
  const ordered = useMemo(() => {
    const k = sortSel
    const byNum = (f: (r: WindowSetRow) => number) => [...filtered].sort((a, b) => f(b) - f(a))
    return k === 'name' ? [...filtered].sort((a, b) => a.id.localeCompare(b.id)) : k === 'windows' ? byNum(r => r.windows) : k === 'labelled' ? byNum(r => r.labelledPct)
      : k === 'saved' ? byNum(r => Number(r.saved.split(' ')[0])) : filtered
  }, [filtered, sortSel])
  const selected = rows.find(r => r.id === setQ) ?? ordered[0] ?? null
  const clearFilters = () => { setSafeQ(null); setRecQ(null); setLabelledQ(null); setUsedQ(null) }
  const notSafe = rows.filter(r => NOT_SAFE.includes(r.check))

  const columns: Column<WindowSetRow>[] = [
    { key: 'name', header: 'name', width: 176, sortValue: r => r.id, render: r => <span className="stack" style={{ gap: 2 }}><span className="mono b" style={{ fontSize: 12 }}>{r.id} <span className="k-badge t-grey" style={{ height: 15, fontSize: 9.5 }}>v{r.version}</span></span><span className="lib-cap">{r.saved} · {r.savedBy}</span></span> },
    { key: 'source', header: 'source', width: 150, render: r => <span className="mono small">{r.source}</span> },
    { key: 'spacing', header: 'window · stride · gap', width: 144, render: r => <span className="mono small">{r.spacing}</span> },
    { key: 'windows', header: 'windows', width: 68, sortValue: r => r.windows, render: r => <span className="mono b">{fmtInt(r.windows)}</span> },
    { key: 'split', header: 'split', width: 106, render: r => r.split ? <span className="stack" style={{ gap: 3 }}><SplitBar split={r.split} /><span className="lib-cap">{r.splitLabel}</span></span> : <span className="mono small" style={{ color: 'var(--red)' }}>no split</span> },
    { key: 'labelled', header: 'labelled', width: 78, sortValue: r => r.labelledPct, render: r => <span className="stack" style={{ gap: 3 }}><span className="lib-minibar"><i style={{ width: `${r.labelledPct}%` }} /></span><span className="lib-cap">{r.labelledPct} %</span></span> },
    { key: 'used', header: 'used by', width: 92, render: r => r.usedLabel ? <button type="button" className="lib-plain mono small" style={{ color: 'var(--blue)', whiteSpace: 'nowrap' }} data-testid={`used-link-${r.id}`} onClick={e => { e.stopPropagation(); if (r.usedBy.length > 1) setSetQ(r.id); else navigate(r.usedBy[0].to) }}>{r.usedLabel}</button> : <span className="muted">—</span> },
    { key: 'check', header: 'check', render: r => <span className={`k-badge ${CHECK_TONE[r.check]}`} title={r.checkReason} data-testid={`check-badge-${r.id}`}>{r.check}</span> },
  ]

  return (
    <div className="lib-split">
      <div className="stack" style={{ gap: 12, minWidth: 0 }}>
        <div className="k-card lib-filterbar" data-testid="window-set-filters">
          <Seg size="sm" ariaLabel="train-safety" testid="safety-seg" value={safeQ} onChange={v => setSafeQ(v)} options={[{ value: 'all', label: 'all' }, { value: 'train-safe', label: 'train-safe' }, { value: 'not-train-safe', label: 'not train-safe' }]} />
          <button ref={recRef} type="button" className={`k-chip ${recs.length ? 'blue' : 'outline'} k-chip-btn`} data-testid="filter-recording" onClick={() => setPop(p => p === 'rec' ? '' : 'rec')}><span className="pre">recording</span>{recs.length ? recs.map(k => RECORDING_GROUPS.find(r => r.key === k)?.label ?? 'Review verdicts').join(', ') : 'any'}</button>
          <button ref={labRef} type="button" className={`k-chip ${labelledQ !== 'any' ? 'blue' : 'outline'} k-chip-btn`} data-testid="filter-labelled" onClick={() => setPop(p => p === 'lab' ? '' : 'lab')}><span className="pre">labelled</span>{labelledQ === 'full' ? '100 %' : labelledQ}</button>
          <button ref={usedRef} type="button" className={`k-chip ${usedQ !== 'any' ? 'blue' : 'outline'} k-chip-btn`} data-testid="filter-used" onClick={() => setPop(p => p === 'used' ? '' : 'used')}><span className="pre">used</span>{usedQ}</button>
          <span style={{ marginLeft: 'auto' }} className="lib-muted-label">sort</span>
          <SelectField value={sortSel} onChange={v => { setSortSel(v as typeof sortSel); setSort(null) }} width={150} testid="window-set-sort" ariaLabel="sort" options={['last used', 'name', 'windows', 'labelled', 'saved'].map(o => ({ value: o, label: o }))} />
          <Popover open={pop === 'rec'} onClose={() => setPop('')} anchorRef={recRef} title="Recording" width={260} testid="recording-popover">
            <div className="stack" style={{ gap: 4 }}>
              {RECORDING_GROUPS.map(r => <Checkbox key={r.key} label={<span className="mono small">{r.label}</span>} checked={recs.includes(r.key)} disabled={!!r.heldOut} disabledReason="held out and locked (D6)"
                onChange={v => setRecQ((v ? [...recs, r.key] : recs.filter(x => x !== r.key)).join(',') || null)} testid={`rec-filter-${r.key}`} />)}
              <Checkbox label={<span className="mono small">Review verdicts</span>} checked={recs.includes('review')} onChange={v => setRecQ((v ? [...recs, 'review'] : recs.filter(x => x !== 'review')).join(',') || null)} />
            </div>
          </Popover>
          <Popover open={pop === 'lab'} onClose={() => setPop('')} anchorRef={labRef} title="Labelled" width={260} testid="labelled-popover">
            <Seg size="sm" value={labelledQ} onChange={v => { setLabelledQ(v); setPop('') }} options={[{ value: 'any', label: 'any' }, { value: 'none', label: 'none' }, { value: 'some', label: 'some' }, { value: 'full', label: '100 %' }]} />
          </Popover>
          <Popover open={pop === 'used'} onClose={() => setPop('')} anchorRef={usedRef} title="Used" width={220} testid="used-popover">
            <Seg size="sm" value={usedQ} onChange={v => { setUsedQ(v); setPop('') }} options={[{ value: 'any', label: 'any' }, { value: 'used', label: 'used' }, { value: 'unused', label: 'unused' }]} />
          </Popover>
        </div>
        <div className="k-card" style={{ overflow: 'hidden' }} data-testid="window-set-table">
          <Table rows={ordered} rowKey={r => r.id} columns={columns} highlighted={selected?.id} onRowClick={r => setSetQ(r.id)} sort={sort} onSortChange={setSort} stickyHeader={false}
            empty={<EmptyState size="sm" title="No window sets match" caption="the filters exclude every set" action={<Button size="sm" testid="clear-filters" onClick={clearFilters}>Clear filters</Button>} testid="window-sets-filtered-empty" />} />
        </div>
        <div className="lib-legend" data-testid="window-set-legend">
          {(['train', 'validation', 'test'] as const).map(k => <span key={k}><i style={{ background: SPLIT_COLOUR[k], height: 4 }} />{k}</span>)}
          <span className="row" style={{ gap: 4 }}><InfoTip title="train-safe">checked when the set was saved: a blocked split with gap ≥ one window length on every boundary, test windows never seen by a job (§6.9)</InfoTip>train-safe = blocked split with gap ≥ window, checked when saved</span>
        </div>
        {notSafe.length > 0 && (
          <div className="k-card" style={{ padding: '14px 16px' }} data-testid="why-not-train-safe">
            <div className="row" style={{ marginBottom: 8 }}><Icon name="alert-circle" size={16} style={{ color: 'var(--red)' }} /><b style={{ fontSize: 13.5 }}>Why {words[notSafe.length] ?? notSafe.length} set{notSafe.length === 1 ? ' is' : 's are'} not train-safe</b></div>
            <div className="stack" style={{ gap: 6, paddingLeft: 24 }}>
              {notSafe.map(r => <span key={r.id} className="mono small" style={{ color: 'var(--text-2)' }}><button type="button" className="lib-plain mono small b" onClick={() => setSetQ(r.id)}>{r.id}</button> — {r.checkReason}.</span>)}
              <span><Button variant="link" icon="link" iconRight="arrow-right" testid="resplit-in-analyse" onClick={() => navigate(`analyse/training/block/1?source=windowset:${notSafe[notSafe.length - 1].id}`)}>Re-split in Analyse</Button></span>
            </div>
          </div>
        )}
      </div>
      {selected ? <WindowSetRail key={selected.id} ws={selected} onDelete={() => setModal('delete')} /> : <aside className="k-card lib-rail"><EmptyState size="sm" title="No set selected" caption="pick a row" /></aside>}
      <Modal open={modal === 'delete' && !!selected} onClose={() => setModal(null)} size="sm" title={`Delete ${selected?.id}?`} testid="delete-window-set-modal"
        footer={<><Button onClick={() => setModal(null)}>Cancel</Button><Button variant="danger-solid" icon="trash" testid="delete-window-set-confirm" disabled={!!selected?.usedBy.length} disabledReason={`used by ${selected?.usedBy.length} — delete is blocked while anything uses the set`}
          onClick={() => { if (selected) { onDelete(selected.id); setModal(null); setSetQ(null) } }}>Delete</Button></>}>
        {selected?.usedBy.length ? <Callout tone="red" title={`Used by ${selected.usedBy.length}`}>delete is blocked while anything uses the set</Callout>
          : <p style={{ margin: 0 }}>{fmtInt(selected?.windows ?? 0)} window bounds are removed from disk. Runs that used it keep their record.</p>}
      </Modal>
      <ImportWindowSetModal open={modal === 'import'} onClose={() => setModal(null)} />
    </div>
  )
}

function SplitBar({ split }: { split: { train: number; validation: number; test: number } }) {
  return <span className="lib-splitbar" title={`train ${Math.round(split.train * 100)} % · validation ${Math.round(split.validation * 100)} % · test ${Math.round(split.test * 100)} %`}>
    {(['train', 'validation', 'test'] as const).filter(k => split[k] > 0).map(k => <i key={k} style={{ width: `${split[k] * 100}%`, background: SPLIT_COLOUR[k] }} />)}
  </span>
}

function WindowSetRail({ ws, onDelete }: { ws: WindowSetRow; onDelete: () => void }) {
  const [coverage, setCoverage] = useQueryState<'now' | 'save'>('coverage', 'now')
  const queue = useQueueToast()
  const { push } = useToast()
  const channels = Object.keys(ws.splitPlan)
  const [showAll, setShowAll] = useState(false)
  const counts = coverage === 'save' ? ws.classCounts.atSave : ws.classCounts.now
  const labelled = coverage === 'save' ? ws.classCounts.atSaveLabelled : ws.labelledWindows
  const maxCount = Math.max(1, ...Object.values(counts))
  const unlabelled = ws.windows - ws.labelledWindows
  const trainReason = ws.check === 'gap < window' ? `gap ${ws.gapS} s < ${ws.windowS} s window` : ws.check === 'not train-safe' ? 'no split — supplied windows would leak (B7)' : ws.check === 'test sample' ? 'a test sample is never trained on' : ws.check === 'fs inferred' ? 'fs inferred — confirm L_LM_Jul26_J in Settings › Datasets first' : null
  const bandRows = channels.slice(0, showAll ? channels.length : 10).map(ch => ({
    label: ch, segments: ws.splitPlan[ch].map(b => ({ start: b.fromH, end: b.toH, colour: SPLIT_COLOUR[b.split], label: b.split === 'gap' ? `${ch} · gap · ${b.fromH.toFixed(1)}–${b.toH.toFixed(1)} h` : `${ch} · ${b.split} · ${b.fromH.toFixed(1)}–${b.toH.toFixed(1)} h · ${fmtInt(b.windows)} windows` })),
  }))
  return (
    <aside className="k-card lib-rail" data-testid="window-set-rail" aria-label={ws.id}>
      <div className="row"><b className="mono" style={{ fontSize: 13.5 }}>{ws.id}</b><span className="k-badge t-grey">v{ws.version}</span><span className={`k-badge ${CHECK_TONE[ws.check]}`} style={{ marginLeft: 'auto' }}>{ws.check}</span></div>
      <KeyValue align="right" dense items={[
        { k: 'made by', v: ws.madeBy },
        { k: 'recipe hash', v: ws.recipeHash },
        { k: 'windows', v: `${fmtInt(ws.windows)} over ${ws.channels.length} channel${ws.channels.length === 1 ? '' : 's'}` },
      ]} testid="window-set-kv" />
      {ws.check !== 'train-safe' && <Callout tone={NOT_SAFE.includes(ws.check) ? 'red' : ws.check === 'test sample' ? 'blue' : 'amber'} testid="window-set-reason" stacked
        action={NOT_SAFE.includes(ws.check) ? <Button variant="link" size="sm" iconRight="arrow-right" onClick={() => navigate(`analyse/training/block/1?source=windowset:${ws.id}`)}>Re-split in Analyse</Button> : ws.check === 'fs inferred' ? <Button variant="link" size="sm" onClick={() => navigate('settings/datasets?recording=L_LM_Jul26_J')}>Settings › Datasets</Button> : undefined}>{ws.checkReason}</Callout>}
      <span className="lib-cap" style={{ fontSize: 11 }}>split plan · {ws.split ? (ws.splitLabel === 'test only' ? 'test block only' : 'blocked by time') : 'none'}</span>
      {channels.length ? <>
        <BandStrip rows={bandRows} domain={[0, ws.planHours]} rowHeight={16} gap={5} labelWidth={52} testid="split-plan" />
        {channels.length > 10 && <Button variant="link" size="sm" onClick={() => setShowAll(s => !s)}>{showAll ? 'show 10' : `+${channels.length - 10} channels`}</Button>}
        <span className="lib-cap">grey = gap ≥ {ws.gapS ?? ws.windowS} s · {ws.dropped} straddling windows dropped</span>
      </> : <span className="lib-cap" data-testid="split-plan-none">no split plan — these windows were supplied, not cut by a sliding-windows block</span>}
      <Checklist items={ws.spacingChecks.map(c => ({ label: c.label, state: c.ok ? 'pass' : 'fail' }))} testid="spacing-checks" />
      <span className="lib-cap" style={{ fontSize: 11 }}>labels · {fmtInt(labelled)} windows · {Math.round((labelled / ws.windows) * 100)} % labelled</span>
      <div className="row" style={{ justifyContent: 'flex-end', marginTop: -4 }}>
        <span className="lib-cap">coverage</span><InfoTip title="coverage now and at save">verdict coverage is live: “now” counts today's labels, “at save” the labels when the set was saved (§6.9)</InfoTip>
        <Seg size="sm" ariaLabel="coverage" testid="coverage-seg" value={coverage} onChange={v => setCoverage(v)} options={[{ value: 'now', label: 'now' }, { value: 'save', label: 'at save' }]} />
      </div>
      <div className="stack" style={{ gap: 4 }} data-testid="class-bars">
        {Object.entries(counts).map(([cls, n]) => (
          <div key={cls} className="lib-classbar" title={`${cls} · ${fmtInt(n)} windows${cls === 'artifact' ? ' · excluded from training' : ''}`}>
            <span style={{ color: cls === 'artifact' ? 'var(--text-2)' : 'var(--text)' }}>{cls === 'artifact' ? 'artifact · excluded' : cls}</span>
            <span className="track"><i style={{ width: `${(n / maxCount) * 100}%`, background: CLASS_COLOURS[cls] ?? '#999' }} /></span>
            <span style={{ textAlign: 'right' }}>{fmtInt(n)}</span>
          </div>
        ))}
      </div>
      <span className="lib-cap" style={{ fontSize: 11 }}>used by</span>
      {ws.usedBy.length ? ws.usedBy.map(u => <button key={u.label} type="button" className="lib-plain mono small" style={{ color: 'var(--blue)', textAlign: 'left' }} data-testid="used-by-link" onClick={() => navigate(u.to)}><Icon name="external" size={11} style={{ verticalAlign: -1, marginRight: 4 }} />{u.label}</button>) : <span className="lib-cap">— nothing uses this set</span>}
      <div className="lib-rail-actions">
        <Button variant="primary" icon="link" iconRight="arrow-right" testid="use-in-analyse" onClick={() => navigate(`analyse/training?source=windowset:${ws.id}`)}>Use as source in Analyse</Button>
        <Button icon="rocket" iconRight="arrow-right" testid="train-in-models" disabled={!!trainReason} disabledReason={trainReason ?? undefined} onClick={() => navigate(`models/launch?windowSet=${ws.id}`)}>Train in Models</Button>
        <Button icon="checklist" testid="send-unlabelled" disabled={unlabelled <= 0 || unlabelled > REVIEW_QUEUE_CAP} disabledReason={unlabelled <= 0 ? 'every window is labelled' : `queue cap ${fmtInt(REVIEW_QUEUE_CAP)} windows`} onClick={() => queue(`Library · ${ws.id} unlabelled`, unlabelled)}>Send {fmtInt(Math.max(0, unlabelled))} unlabelled to Review</Button>
        <span className="row" style={{ width: '100%' }}>
          <Button variant="link" icon="upload" testid="export-window-set" onClick={() => push({ text: `not wired yet: export window set ${ws.id} (bounds on disk + manifest)` })}>Export</Button>
          <span style={{ marginLeft: 'auto' }} />
          <Button icon="trash" variant={ws.usedBy.length ? 'default' : 'danger'} testid="delete-window-set" disabled={ws.usedBy.length > 0} disabledReason={`used by ${ws.usedBy.length} — delete is blocked while anything uses the set`} onClick={onDelete}>Delete</Button>
          {ws.usedBy.length > 0 && <span className="lib-cap">used by {ws.usedBy.length}</span>}
        </span>
      </div>
    </aside>
  )
}

function ImportWindowSetModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [path, setPath] = useState('')
  const { push } = useToast()
  const heldOut = /M4_aug/i.test(path)
  const shapeOk = /\/windows\.json$/.test(path) || (path.length > 0 && !/\.[a-z0-9]+$/i.test(path))
  const error = !path ? null : heldOut ? 'M4_aug is held out and locked — refused (D6)' : !shapeOk ? 'pick a window-set bundle (a folder, or a path ending /windows.json)' : null
  const checks = path && !error ? [
    { label: 'spacing: gap ≥ window on every boundary', state: 'pass' as const },
    { label: 'split assignment present for every window', state: 'pass' as const },
    { label: 'recordings exist in Settings › Datasets', state: 'pass' as const },
    { label: 'no window on a held-out recording', state: 'pass' as const },
  ] : heldOut ? [{ label: 'M4_aug is held out and locked', state: 'fail' as const }] : []
  return (
    <Modal open={open} onClose={onClose} title="Import window set" subtitle="dry run first · nothing written until Import" size="md" testid="import-window-set-modal"
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon="download" testid="import-window-set-confirm" disabled={!path || !!error} disabledReason={!path ? 'type a bundle path' : error ?? ''}
        onClick={() => { recordDemoWrite('library', 'window-set.import', { path }); push({ text: `not wired yet: POST /api/window-sets/import (${path})` }); onClose() }}>Import</Button></>}>
      <div className="stack" style={{ gap: 10 }}>
        <span className="lib-cap" style={{ fontSize: 11 }}>bundle path</span>
        <TextField value={path} onChange={setPath} placeholder="DATA/window_sets/ws_…/windows.json" invalid={!!error} block testid="window-set-path" autoFocus />
        {error && <span className="k-field-error" role="alert" data-testid="window-set-path-error"><Icon name="alert-circle" size={11} />{error}</span>}
        {checks.length > 0 && <Checklist items={checks} testid="window-set-import-checks" />}
      </div>
    </Modal>
  )
}
