/* Discovery chrome shared by Runs · Seed search · Compare · Compare every stage: the toolbar (session, scope, null,
 * cost, History), the Scope card (recording, channel chips, section brush across ≤ 3 strips with paging), the Runs
 * card (two ways to add a run, rows with A / B pick boxes), load/fail states and the SLURM script modal. */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  Button, Callout, Checkbox, Chip, CodeBlock, DisabledReason, Dropdown, EmptyState, Icon, IconButton, InfoTip, Modal, NumberField, Popover, ProgressBar,
  RangeSlider, TextField, Tooltip, cx, recordDemoWrite, useNotWired, useQueryState, useSim,
} from '../kit'
import { getHistory, getOverview, heldOutReason, fmtMin, DISCOVERY_LIMIT_MIN, type DiscoveryRun } from '../api/discovery'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { useToast } from '../shell/Toast'
import { RunGlyph } from './glyphs'
import { PAGE_SIZE, hasResults, pickable, type Discovery } from './session'

/* ------------------------------------------------------------------ load / fail */
export function Loading({ height = 200, label = 'loading', testid }: { height?: number; label?: string; testid?: string }) {
  return <div className="dsc-loading k-card" style={{ height }} data-testid={testid ?? 'discovery-loading'}><ProgressBar indeterminate size="sm" width={160} labelPosition="none" /><span>{label}</span></div>
}
export function LoadFailed({ what, error, onRetry }: { what: string; error: Error; onRetry: () => void }) {
  return <Callout tone="red" icon="alert-triangle" title={`Could not load ${what}`} action={<Button size="sm" icon="refresh" onClick={onRetry}>Retry</Button>} testid="discovery-load-failed">{error.message}</Callout>
}

/* ------------------------------------------------------------------ toolbar */
const NAME_RE = /^[A-Za-z0-9_-]{3,40}$/

export function SessionChip({ dx }: { dx: Discovery }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const notWired = useNotWired()
  if (!dx.scope) return null
  const error = draft && !NAME_RE.test(draft) ? 'letters, digits, _ and - only (3–40)' : !draft ? 'a session needs a name' : null
  const commit = () => {
    if (error) return
    dx.setScope({ name: draft, saved: true })
    recordDemoWrite('discovery', 'rename-session', { name: draft })
    setEditing(false)
    notWired('save Discovery session name (PATCH /discovery/sessions)')
  }
  if (editing) return (
    <span className="dsc-session-edit" data-testid="session-rename">
      <TextField value={draft} onChange={setDraft} onEnter={commit} invalid={!!error} width={190} autoFocus ariaLabel="session name" testid="session-name-input" />
      <Button size="sm" variant="primary" onClick={commit} disabled={!!error} disabledReason={error ?? undefined} testid="session-name-save">Save</Button>
      <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
      {error && <span className="dsc-err" data-testid="session-name-error">{error}</span>}
    </span>
  )
  return (
    <button type="button" className="dsc-session" onClick={() => { setDraft(dx.scope!.name); setEditing(true) }} title="rename this session" data-testid="session-chip">
      <Icon name="folder" size={13} /><b>{dx.scope.name}</b><Icon name="pencil" size={11} /><span className={cx('muted', !dx.scope.saved && 'amber')}>{dx.scope.saved ? 'saved' : 'unsaved'}</span>
    </button>
  )
}

export function ScopeSummaryChip({ dx }: { dx: Discovery }) {
  if (!dx.scope || !dx.recording) return null
  const s = dx.scope
  return (
    <Chip tone="blue" icon="layers" size="lg" testid="scope-chip" title="jump to the Scope card"
      onClick={() => { const el = document.querySelector<HTMLElement>('[data-testid="scope-card"]'); el?.scrollIntoView({ behavior: 'smooth', block: 'start' }); el?.querySelector<HTMLElement>('[data-testid="section-chip"]')?.focus() }}>
      {dx.recording.stem} · {s.channels.length} channel{s.channels.length === 1 ? '' : 's'} · {s.section[0]}–{s.section[1]} h <Icon name="chevron-down" size={11} />
    </Chip>
  )
}

export function NullChip({ dx }: { dx: Discovery }) {
  if (!dx.scope) return null
  return (
    <span className="dsc-null" data-testid="null-chip">
      <span className="dot" style={{ background: 'var(--green)' }} /><span className="muted">null</span> <b>{dx.scope.nullMethod} {dx.scope.nullN}×</b>
      <InfoTip title="Null for every run">
        Every run carries a null: {dx.scope.nullMethod}, {dx.scope.nullN}×, on the same scope. “Null expects” and “× null” in the scoreboard come from it.{' '}
        <Button variant="link" size="sm" onClick={() => navigate('settings/nulls')}>Settings › Nulls</Button>
      </InfoTip>
    </span>
  )
}

export function CostChip({ dx, label }: { dx: Discovery; label?: ReactNode }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  if (!dx.scope) return null
  const over = dx.overLimit
  const text = label ?? (dx.pending.length === 0 ? <><b>nothing pending</b> <span className="muted">· every run has results or is queued</span></> : over ? <><b>{fmtMin(dx.estimateMin)}</b> routes to cluster</> : <><b>{fmtMin(dx.estimateMin)}</b> <span className="muted">local</span></>)
  return (
    <>
      <button ref={ref} type="button" className={cx('dsc-cost', over && !label && 'over')} onClick={() => setOpen(o => !o)} data-testid="cost-chip" aria-expanded={open}>
        <Icon name="hourglass" size={12} />{text}
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} title="Cost of pending runs" subtitle={`local limit ${DISCOVERY_LIMIT_MIN} min`} width={320} testid="cost-popover">
        <div className="dsc-pop-list">
          {dx.pending.length === 0 && <span className="muted">No run is waiting to start.</span>}
          {dx.pending.map(r => <div key={r.key} className="row between"><span><span className="dot" style={{ background: r.colour }} /> {r.label}</span><b className="mono">{fmtMin((r.perChannelMin ?? 0) * dx.scope!.channels.length * dx.sectionH / 174)}</b></div>)}
          <div className="row between dsc-pop-total"><span>{dx.scope.channels.length} ch × {dx.sectionH} h</span><b className={cx('mono', dx.overLimit && 'amber')}>{fmtMin(dx.estimateMin)} · {dx.overLimit ? 'cluster' : 'local'}</b></div>
          <Button variant="link" size="sm" icon="external" onClick={() => navigate('settings/compute-hpc')}>Settings › Compute &amp; HPC</Button>
        </div>
      </Popover>
    </>
  )
}

export function HistoryButton({ dx }: { dx: Discovery }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [q, setQ] = useQueryState('popover', '')
  const open = q === 'history'
  const hist = useSourced(getHistory, [])
  const toast = useToast()
  return (
    <>
      <Button ref={ref} icon="clock" onClick={() => setQ(open ? null : 'history')} testid="history-button" aria-expanded={open}>History</Button>
      <Popover open={open} onClose={() => setQ(null)} anchorRef={ref} placement="bottom-end" title="Discovery history" subtitle={dx.recording?.stem} width={380} testid="history-popover">
        {hist.error && <LoadFailed what="history" error={hist.error} onRetry={hist.reload} />}
        {hist.data?.map(h => {
          const inSession = h.inSession || dx.runs.some(r => r.key === h.runKey)
          return (
            <div key={h.id} className="dsc-hist-row" data-testid={`history-${h.id}`}>
              <div><b className="mono">{h.id}</b> {h.label}<div className="muted small">{h.when} · {h.status} · {h.detail}</div></div>
              <Button size="sm" disabled={inSession} disabledReason={inSession ? 'already in this session' : undefined} testid={`history-open-${h.id}`}
                onClick={() => {
                  dx.addRuns([{ key: h.runKey, label: `${h.label} · ${h.id}`, id: h.id, kind: h.label.startsWith('seed') ? 'seed' : 'template', colour: '#7A8FA6', glyph: h.label.startsWith('seed') ? 'seed' : 'sax', detail: h.status, status: h.status === 'superseded' ? 'superseded' : 'done', doneAt: h.when.split(' ').pop(), template: h.label.startsWith('drop') ? 'drop_motifs9' : 'seed_F03_native', addedThisSession: true }])
                  recordDemoWrite('discovery', 'open-history-run', { id: h.id })
                  toast.push({ text: `${h.id} ${h.label} added to this session` })
                }}>Open</Button>
            </div>
          )
        })}
      </Popover>
    </>
  )
}

export function DiscoveryToolbar({ dx, left, right }: { dx: Discovery; left?: ReactNode; right: ReactNode }) {
  return (
    <div className="dsc-toolbar" data-testid="discovery-toolbar">
      {left}
      <SessionChip dx={dx} />
      <ScopeSummaryChip dx={dx} />
      <span className="k-spacer" />
      {right}
    </div>
  )
}

/* ------------------------------------------------------------------ scope card */
export function ScopeCard({ dx, previewable = true }: { dx: Discovery; previewable?: boolean }) {
  const s = dx.scope, rec = dx.recording
  const overview = useSourced(() => s ? getOverview(s.recording, dx.visibleChannels) : Promise.resolve({ data: { data: {} as Record<string, number[]> }, source: 'demo' as const }), [s?.recording, dx.visibleChannels.join(',')])
  const recRef = useRef<HTMLSpanElement>(null)
  const [confirmRec, setConfirmRec] = useState<string | null>(null)
  const addRef = useRef<HTMLButtonElement>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [addSel, setAddSel] = useState<string[]>([])
  const secRef = useRef<HTMLButtonElement>(null)
  const [secOpen, setSecOpen] = useState(false)
  const preview = useSim('discovery.preview')
  const toast = useToast()
  if (!s || !rec) return null
  const hours = rec.hours
  const refused = overview.data && 'refused' in overview.data && overview.data.refused ? overview.data.refused : rec.heldOut ? heldOutReason(rec.file) : null
  const traces = overview.data && 'data' in overview.data ? overview.data.data : null
  const visible = new Set(dx.visibleChannels)
  const sectionH = s.section[1] - s.section[0]
  const runnable = dx.pending
  const changeRecording = (key: string) => {
    const r = dx.recordings.find(x => x.key === key)!
    dx.setScope({ recording: key, channels: r.channels.slice(0, Math.min(3, r.channels.length)), section: [0, Math.min(r.hours, 174)] })
    dx.setStale(true); dx.setChPage(1)
    recordDemoWrite('discovery', 'change-recording', { recording: key })
    toast.push({ text: `recording changed to ${r.stem} · ${dx.runs.filter(hasResults).length} runs marked stale` })
    setConfirmRec(null)
  }
  const runPreview = () => {
    preview.start({ steps: runnable.map(r => `${r.label} on 4 h of CH4_A2`), stepMs: 500 })
    recordDemoWrite('discovery', 'preview-sample', { runs: runnable.map(r => r.key), hours: 4 })
  }
  return (
    <section className="k-card dsc-scope" data-testid="scope-card" aria-label="Scope">
      <div className="dsc-scope-head">
        <h3>Scope</h3>
        <InfoTip title="Scope">One recording, one or more channels and one section. Every run in the session applies to the whole scope; at most three strips show at a time.</InfoTip>
        <span ref={recRef}>
          <Dropdown prefix="recording" value={s.recording} testid="recording-select"
            onChange={v => { if (v !== s.recording) setConfirmRec(v) }}
            options={dx.recordings.map(r => ({ value: r.key, label: r.file, hint: `${r.channels.length} ch · ${r.hours} h`, disabled: r.heldOut, reason: r.heldOut ? 'held out · locked (D6)' : undefined }))} />
        </span>
        <Popover open={!!confirmRec} onClose={() => setConfirmRec(null)} anchorRef={recRef} title="Change the recording?" width={320} testid="recording-confirm">
          <p className="small">Changing the recording clears {s.channels.length} channel{s.channels.length === 1 ? '' : 's'} and marks {dx.runs.filter(hasResults).length} runs stale.</p>
          <div className="row end" style={{ gap: 8 }}><Button size="sm" onClick={() => setConfirmRec(null)}>Cancel</Button><Button size="sm" variant="primary" onClick={() => changeRecording(confirmRec!)} testid="recording-confirm-change">Change</Button></div>
        </Popover>
        <div className="dsc-chips" data-testid="channel-chips">
          {s.channels.map(ch => {
            const last = s.channels.length === 1
            const chip = <Chip key={ch} tone={visible.has(ch) ? 'blue' : 'grey'} testid={`channel-chip-${ch}`} onRemove={last ? undefined : () => {
              const next = s.channels.filter(c => c !== ch)
              dx.setScope({ channels: next }); if (dx.chPage > Math.ceil(next.length / PAGE_SIZE)) dx.setChPage(Math.max(1, Math.ceil(next.length / PAGE_SIZE)))
              recordDemoWrite('discovery', 'remove-channel', { channel: ch })
            }} removeLabel={`remove ${ch} from scope`}>{ch}</Chip>
            return last ? <Tooltip key={ch} content="scope needs at least one channel"><span>{chip}</span></Tooltip> : chip
          })}
          <button ref={addRef} type="button" className="dsc-add-channel" onClick={() => { setAddSel(s.channels); setAddOpen(o => !o) }} data-testid="add-channel" disabled={!!refused} title={refused ?? undefined}><Icon name="plus" size={11} /> channel</button>
          <Popover open={addOpen} onClose={() => setAddOpen(false)} anchorRef={addRef} title="Channels in scope" subtitle={rec.stem} width={300} testid="add-channel-popover">
            <div className="dsc-ch-grid">
              {rec.channels.map(ch => <Checkbox key={ch} checked={addSel.includes(ch)} label={ch} testid={`add-channel-${ch}`} onChange={v => setAddSel(v ? [...addSel, ch] : addSel.filter(c => c !== ch))} />)}
            </div>
            <div className="row between" style={{ marginTop: 10 }}>
              <span className="muted small">{addSel.length} selected · {addSel.length > PAGE_SIZE ? 'strips page three at a time' : 'fits on one page'}</span>
              <Button size="sm" variant="primary" disabled={addSel.length === 0} disabledReason="scope needs at least one channel" testid="add-channel-apply"
                onClick={() => { const ordered = [...s.channels.filter(c => addSel.includes(c)), ...rec.channels.filter(c => addSel.includes(c) && !s.channels.includes(c))]; dx.setScope({ channels: ordered }); setAddOpen(false); recordDemoWrite('discovery', 'set-channels', { channels: ordered }) }}>Apply</Button>
            </div>
          </Popover>
        </div>
        <span className="k-spacer" />
        <button ref={secRef} type="button" className="dsc-section-chip" onClick={() => setSecOpen(o => !o)} data-testid="section-chip" aria-expanded={secOpen}>
          <span className="muted">section</span> {s.section[0]}–{s.section[1]} h · {sectionH} h × {s.channels.length} ch = {fmtH0(sectionH * s.channels.length)} <Icon name="chevron-down" size={11} />
        </button>
        <SectionPopover open={secOpen} onClose={() => setSecOpen(false)} anchorRef={secRef} section={s.section} hours={hours} onApply={sec => { dx.setScope({ section: sec }); recordDemoWrite('discovery', 'set-section', { section: sec }) }} />
        {previewable && (
          <DisabledReason disabled={runnable.length === 0 || !!refused} reason={refused ? 'held out recording' : 'nothing to preview — every run in this session has results'}>
            <Button icon="flask" onClick={runPreview} disabled={runnable.length === 0 || !!refused || preview.busy} disabledReason={refused ? 'held out recording' : runnable.length === 0 ? 'nothing to preview — every run in this session has results' : undefined} loading={preview.busy} testid="preview-sample">Preview on a 4 h sample</Button>
          </DisabledReason>
        )}
      </div>
      {previewable && preview.status !== 'idle' && (
        <div className="dsc-preview-result" data-testid="preview-result">
          {preview.busy && <><ProgressBar value={preview.fraction} size="sm" width={140} labelPosition="none" /><span className="muted">{preview.status} · {preview.steps[preview.step] ?? 'queued'}</span></>}
          {preview.status === 'done' && <><Icon name="flask" size={12} /><span>4 h of CH4_A2 · {runnable.map(r => `${r.label} 3 spans · null gives 1`).join(' · ') || 'no pending run'} → ≈ {Math.round(3 * sectionH * s.channels.length / 4).toLocaleString('en-US')} over {fmtH0(sectionH * s.channels.length)}{dx.overLimit ? <span className="amber"> · above the local ceiling → routes to cluster</span> : null}</span><Button size="sm" variant="ghost" icon="x" onClick={preview.reset}>Dismiss</Button></>}
        </div>
      )}
      {refused ? (
        <Callout tone="red" icon="lock" title="Held out" testid="scope-refused" action={<Button size="sm" onClick={() => { dx.setScope({ recording: 'M2_aug_fs1', channels: ['CH2_A1', 'CH4_A2', 'CH7_B2'], section: [112, 286] }); navigate('discovery/runs') }}>Back to M2_aug fs1</Button>}>{refused}</Callout>
      ) : (
        <div className="dsc-strips-wrap">
          <Strips channels={dx.visibleChannels} traces={traces} hours={hours} section={s.section} onSection={sec => dx.setScope({ section: sec })} />
          <div className="dsc-pager-v" data-testid="channel-pager">
            <IconButton icon="chevron-up" label="previous three channels" bordered disabled={dx.chPage <= 1} disabledReason="already at the first channels" onClick={() => dx.setChPage(dx.chPage - 1)} testid="channel-pager-up" />
            <span className="mono small" data-testid="channel-pager-label">{(dx.chPage - 1) * PAGE_SIZE + 1}–{Math.min(s.channels.length, dx.chPage * PAGE_SIZE)} of {s.channels.length}</span>
            <IconButton icon="chevron-down" label="next three channels" bordered disabled={dx.chPage >= dx.pageCount} disabledReason={s.channels.length <= PAGE_SIZE ? 'every channel fits on one page' : 'already at the last channels'} onClick={() => dx.setChPage(dx.chPage + 1)} testid="channel-pager-down" />
          </div>
        </div>
      )}
    </section>
  )
}
const fmtH0 = (h: number) => `${Math.round(h)} h`

function SectionPopover({ open, onClose, anchorRef, section, hours, onApply }: { open: boolean; onClose: () => void; anchorRef: React.RefObject<HTMLButtonElement | null>; section: [number, number]; hours: number; onApply: (s: [number, number]) => void }) {
  const [v, setV] = useState<[number, number]>(section)
  const [fromRaw, setFromRaw] = useState<string | null>(null)
  const err = v[0] < 0 || v[1] > hours || v[0] >= v[1] ? `section must lie inside 0–${hours} h` : v[1] - v[0] < 1 ? 'section must be at least 1 h' : fromRaw
  return (
    <Popover open={open} onClose={onClose} anchorRef={anchorRef} placement="bottom-end" title="Section" subtitle={`0–${hours} h of the recording`} width={340} testid="section-popover">
      <RangeSlider value={v} onChange={setV} min={0} max={hours} step={1} format={x => `${x} h`} testid="section-range" />
      <div className="row" style={{ gap: 10, marginTop: 10 }}>
        <NumberField value={v[0]} min={0} max={hours} unit="h" width={110} onValid={n => { setV([n, v[1]]); setFromRaw(null) }} onChange={(_, reason) => setFromRaw(reason ?? null)} testid="section-from" ariaLabel="section from" />
        <span className="muted">to</span>
        <NumberField value={v[1]} min={0} max={hours} unit="h" width={110} onValid={n => { setV([v[0], n]); setFromRaw(null) }} onChange={(_, reason) => setFromRaw(reason ?? null)} testid="section-to" ariaLabel="section to" />
      </div>
      {err && <div className="dsc-err" data-testid="section-error">{err}</div>}
      <div className="row end" style={{ gap: 8, marginTop: 10 }}>
        <Button size="sm" onClick={onClose}>Cancel</Button>
        <Button size="sm" variant="primary" disabled={!!err} disabledReason={err ?? undefined} onClick={() => { onApply(v); onClose() }} testid="section-apply">Apply</Button>
      </div>
    </Popover>
  )
}

/** Overview strips with one shared section brush (drag body to move, handles to resize, snaps to 1 h). */
function Strips({ channels, traces, hours, section, onSection }: { channels: string[]; traces: Record<string, number[]> | null; hours: number; section: [number, number]; onSection: (s: [number, number]) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<{ mode: 'move' | 'lo' | 'hi'; x0: number; s0: [number, number] } | null>(null)
  const [live, setLive] = useState<[number, number] | null>(null)
  const sec = live ?? section
  const yDomain = useMemo<[number, number]>(() => {
    const all = channels.flatMap(c => traces?.[c] ?? [])
    if (!all.length) return [-0.4, 0.4]
    const lo = Math.min(...all), hi = Math.max(...all), m = (hi - lo) * 0.1
    return [lo - m, hi + m]
  }, [channels, traces])
  const pct = (h: number) => `${(h / hours) * 100}%`
  const onMove = (e: React.PointerEvent) => {
    if (!drag || !ref.current) return
    const w = ref.current.getBoundingClientRect().width
    const dh = Math.round(((e.clientX - drag.x0) / w) * hours)
    let [a, b] = drag.s0
    if (drag.mode === 'move') { const len = b - a; a = Math.max(0, Math.min(hours - len, a + dh)); b = a + len }
    else if (drag.mode === 'lo') a = Math.max(0, Math.min(b - 1, a + dh))
    else b = Math.min(hours, Math.max(a + 1, b + dh))
    setLive([a, b])
  }
  const end = () => { if (live) onSection(live); setDrag(null); setLive(null) }
  const start = (mode: 'move' | 'lo' | 'hi') => (e: React.PointerEvent) => { e.stopPropagation(); (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); setDrag({ mode, x0: e.clientX, s0: section }) }
  const nudge = (e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 10 : 1
    if (e.key === 'ArrowLeft' && section[0] - step >= 0) { e.preventDefault(); onSection([section[0] - step, section[1] - step]) }
    if (e.key === 'ArrowRight' && section[1] + step <= hours) { e.preventDefault(); onSection([section[0] + step, section[1] + step]) }
  }
  return (
    <div className="dsc-strips" data-testid="scope-strips">
      <div className="dsc-strip-labels">{channels.map(c => <span key={c} className="mono">{c}</span>)}</div>
      <div className="dsc-strip-area" ref={ref} onPointerMove={onMove} onPointerUp={end} onPointerCancel={end}>
        {channels.map(c => (
          <div key={c} className="dsc-strip" data-testid={`strip-${c}`}>
            {traces?.[c] ? <StripLine values={traces[c]} yDomain={yDomain} /> : <span className="muted small">loading</span>}
          </div>
        ))}
        <div className={cx('dsc-brush', drag && 'dragging')} style={{ left: pct(sec[0]), width: pct(sec[1] - sec[0]) }} onPointerDown={start('move')} tabIndex={0} onKeyDown={nudge}
          role="slider" aria-label="section brush" aria-valuemin={0} aria-valuemax={hours} aria-valuenow={sec[0]} aria-valuetext={`${sec[0]}–${sec[1]} h`} data-testid="section-brush" title={`${sec[0]}–${sec[1]} h · drag to move, drag an edge to resize`}>
          <span className="h lo" onPointerDown={start('lo')} data-testid="brush-lo" />
          <span className="h hi" onPointerDown={start('hi')} data-testid="brush-hi" />
          {drag && <span className="dsc-brush-read mono">{sec[0]}–{sec[1]} h</span>}
        </div>
      </div>
    </div>
  )
}
function StripLine({ values, yDomain }: { values: number[]; yDomain: [number, number] }) {
  const W = 1000, H = 30
  const y = (v: number) => H - 2 - ((v - yDomain[0]) / (yDomain[1] - yDomain[0])) * (H - 4)
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${((i / (values.length - 1)) * W).toFixed(1)} ${y(v).toFixed(1)}`).join('')
  return <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height={H} aria-label="overview trace, mV on a shared scale"><path d={d} fill="none" stroke="var(--trace)" strokeWidth={1.1} vectorEffect="non-scaling-stroke" /></svg>
}

/* ------------------------------------------------------------------ runs card */
export type RunsMode = 'runs' | 'seed' | 'compare'

export function RunsCard({ dx, mode, selected, onSelect, draft, compareActive, onAddTemplate }: {
  dx: Discovery; mode: RunsMode; selected?: string | null; onSelect?: (key: string) => void; draft?: ReactNode; compareActive?: boolean; onAddTemplate: () => void
}) {
  const runs = dx.runs
  const pickedLabel = dx.picks.length === 2 ? '2 picked' : `${dx.picks.length} of 2 picked`
  const canCompare = dx.picks.length === 2
  const listed = runs.filter(r => r.status !== 'draft')
  const inSession = listed.filter(r => r.kind !== 'reference').length + (draft ? 1 : 0)
  return (
    <section className="k-card dsc-runs" data-testid="runs-card" aria-label="Runs">
      <div className="dsc-runs-head">
        <h3>Runs</h3>
        <InfoTip title="Runs">A run is a template applied to the scope, or a seed search over it (P17). Pick two to compare. Human annotations are the fixed reference.</InfoTip>
        <span className="muted small">{inSession} in this session</span>
      </div>
      <div className="dsc-runs-add">
        <Button icon="layers" onClick={onAddTemplate} testid="apply-template">Apply template</Button>
        <Button icon="target" onClick={() => navigate('discovery/seed')} testid="seed-search" aria-pressed={mode === 'seed'}>Seed search</Button>
      </div>
      <div className="dsc-runs-list" data-testid="runs-list">
        {listed.length === 0 && <EmptyState size="sm" icon="inbox" title="No runs" caption="add a template or a seed search" />}
        {listed.slice(0, 4).map(r => <RunRow key={r.key} dx={dx} run={r} selected={selected === r.key} onSelect={onSelect} mode={mode} />)}
        {draft}
        {listed.slice(4).map(r => <RunRow key={r.key} dx={dx} run={r} selected={selected === r.key} onSelect={onSelect} mode={mode} />)}
        {listed.length === 1 && listed[0].kind === 'reference' && <EmptyState size="sm" icon="layers" title="Only the human reference" caption="Apply template or Seed search adds the first run" testid="runs-empty" />}
      </div>
      <div className="dsc-runs-foot" data-testid="runs-foot">
        <span className="muted small">{mode === 'seed' ? "drafts can't be compared" : pickedLabel}</span>
        {mode === 'seed' ? (
          <DisabledReason reason="a draft has no results to compare — run it first"><Button icon="compare" disabled disabledReason="a draft has no results to compare — run it first" testid="compare-button">Compare</Button></DisabledReason>
        ) : compareActive ? (
          <Button icon="compare" variant="primary" aria-pressed onClick={() => navigate('discovery/runs')} testid="compare-button" title="comparing — click to go back to all runs">Comparing</Button>
        ) : (
          <DisabledReason disabled={!canCompare} reason="pick two runs to compare">
            <Button icon="compare" disabled={!canCompare} disabledReason={canCompare ? undefined : 'pick two runs to compare'} onClick={() => navigate(`discovery/compare?a=${encodeURIComponent(dx.picks[0])}&b=${encodeURIComponent(dx.picks[1])}`)} testid="compare-button">Compare</Button>
          </DisabledReason>
        )}
      </div>
    </section>
  )
}

function RunRow({ dx, run, selected, onSelect, mode }: { dx: Discovery; run: DiscoveryRun; selected: boolean; onSelect?: (k: string) => void; mode: RunsMode }) {
  const sim = useSim(`discovery.run.${run.key}`)
  const status = run.status === 'running' || run.status === 'queued' ? (sim.status === 'done' ? 'done' : sim.status === 'failed' ? 'failed' : run.status) : run.status
  const pickIdx = dx.picks.indexOf(run.key)
  const found = dx.foundOf(run.key)
  const nCh = dx.scope?.channels.length ?? 0
  const canPick = pickable({ ...run, status })
  const doneLocal = sim.status === 'done' && run.status !== 'done'
  useEffect(() => { if (doneLocal) dx.patchRun(run.key, { status: 'done', doneAt: new Date(sim.finishedAt ?? Date.now()).toTimeString().slice(0, 5) }) }, [doneLocal]) // eslint-disable-line react-hooks/exhaustive-deps
  const kindBadge = run.kind === 'reference' ? <span className="k-badge t-grey">reference</span> : run.kind === 'seed' ? <span className="k-badge t-purple">seed</span> : run.kind === 'draft' ? <span className="k-badge t-amber">draft</span> : <span className="k-badge t-blue">template</span>
  let line: ReactNode = null
  switch (status) {
    case 'done': line = <span>{found ?? '…'} found · {nCh} ch · done {run.doneAt ?? '—'}{dx.stale && <span className="amber"> · stale</span>}</span>; break
    case 'on cluster': line = <span className="dsc-run-progress"><ProgressBar value={run.progress ?? 0} size="sm" labelPosition="none" width={96} /><span className="blue">cluster {Math.round((run.progress ?? 0) * 100)} %</span></span>; break
    case 'running': case 'queued': line = <span className="dsc-run-progress"><ProgressBar value={sim.fraction} size="sm" labelPosition="none" width={96} /><span className="blue">{sim.status === 'queued' ? 'queued · local' : `running · ${sim.steps[sim.step] ?? ''}`}</span></span>; break
    case 'new': line = <span>new · local</span>; break
    case 'paused': line = <span className="dsc-run-progress"><ProgressBar value={run.progress ?? 0} size="sm" tone="amber" labelPosition="none" width={56} /><span className="amber">paused {run.pausedAt?.stage}/{run.pausedAt?.of}</span></span>; break
    case 'superseded': line = <span className="muted">superseded · no verdicts written</span>; break
    case 'failed': line = <span className="red">failed · {run.error ?? sim.error}</span>; break
    case 'reference': break
  }
  return (
    <div className={cx('dsc-run', selected && 'selected', status === 'paused' && 'paused', status === 'superseded' && 'superseded', status === 'failed' && 'failed')} style={{ ['--run' as string]: run.colour }} data-testid={`run-row-${run.key}`} data-status={status}>
      <button type="button" className="dsc-run-body" onClick={() => onSelect ? onSelect(run.key) : navigate(`discovery/runs?run=${encodeURIComponent(run.key)}`)} aria-pressed={selected} title={mode === 'runs' ? `browse ${run.label}` : `open ${run.label} in Runs`}>
        <RunGlyph kind={run.glyph} width={40} height={28} />
        <span className="dsc-run-text">
          <b>{run.label}</b>
          <span className="dsc-run-meta">{kindBadge}<span className="muted">{run.detail}</span></span>
          {line && <span className="dsc-run-line small">{line}</span>}
        </span>
      </button>
      {status === 'paused' && run.id && <Button variant="link" size="sm" icon="external" className="dsc-run-jobs-link" onClick={() => navigate(`jobs/run/${run.id}`)} testid={`open-in-jobs-${run.key}`}>Open in Jobs</Button>}
      {status === 'failed' && <Button size="sm" icon="refresh" className="dsc-run-retry" onClick={() => { dx.patchRun(run.key, { status: 'new', error: undefined }); recordDemoWrite('discovery', 'retry-run', { run: run.key }) }} testid={`retry-${run.key}`}>Retry</Button>}
      {status !== 'paused' && status !== 'superseded' && mode !== 'seed' && (
        pickIdx >= 0
          ? <button type="button" className={cx('dsc-pick', pickIdx === 0 ? 'a' : 'b')} onClick={() => dx.togglePick(run.key)} aria-label={`unpick ${run.label} (${pickIdx === 0 ? 'A' : 'B'})`} data-testid={`pick-${run.key}`}>{pickIdx === 0 ? 'A' : 'B'}</button>
          : <DisabledReason disabled={!canPick} reason={status === 'failed' ? 'a failed run has no results to compare' : 'no results yet to compare'}>
            <button type="button" className="dsc-pick" disabled={!canPick} onClick={() => dx.togglePick(run.key)} aria-label={`pick ${run.label} to compare`} data-testid={`pick-${run.key}`} />
          </DisabledReason>
      )}
      {mode === 'seed' && status !== 'paused' && status !== 'superseded' && <span className="dsc-pick ghost" aria-hidden />}
    </div>
  )
}

/* ------------------------------------------------------------------ SLURM script */
export function slurmScript(runs: { label: string; perChannelMin?: number }[], channels: string[], section: [number, number], session: string, recordingFile: string) {
  const hours = Math.max(1, Math.ceil(runs.reduce((s, r) => s + (r.perChannelMin ?? 1) * channels.length, 0) / 60 * 1.5))
  return [
    '#!/bin/bash',
    `#SBATCH --job-name=discovery_${session}`,
    `#SBATCH --array=0-${runs.length * channels.length - 1}`,
    `#SBATCH --time=${String(hours).padStart(2, '0')}:00:00`,
    '#SBATCH --cpus-per-task=8 --mem=16G',
    '',
    `RUNS=(${runs.map(r => r.label).join(' ')})`,
    `CHANNELS=(${channels.join(' ')})`,
    `RUN=\${RUNS[$((SLURM_ARRAY_TASK_ID / ${channels.length}))]}`,
    `CH=\${CHANNELS[$((SLURM_ARRAY_TASK_ID % ${channels.length}))]}`,
    '',
    `python -m Working.discovery.run --template "$RUN" \\`,
    `  --recording ${recordingFile} --channel "$CH" --section ${section[0]} ${section[1]} \\`,
    '  --null circular_shift:200 --manifest out/manifest_${SLURM_ARRAY_TASK_ID}.json',
  ].join('\n')
}

export function SlurmModal({ open, onClose, dx, runs, onCreated }: { open: boolean; onClose: () => void; dx: Discovery; runs: DiscoveryRun[]; onCreated?: () => void }) {
  const toast = useToast()
  const notWired = useNotWired()
  if (!dx.scope || !dx.recording) return null
  const s = dx.scope
  const script = slurmScript(runs, s.channels, s.section, s.name, dx.recording.file)
  const create = () => {
    runs.forEach((r, i) => {
      const id = `j-${String(231 + i).padStart(4, '0')}`
      dx.patchRun(r.key, { status: 'on cluster', progress: 0, job: id })
      recordDemoWrite('jobs', 'add-job', { id, kind: 'discovery', title: `${r.label} · ${s.channels.length} channels`, status: 'queue', detail: `SLURM script created for Discovery session ${s.name}`, for: r.key })
    })
    recordDemoWrite('discovery', 'create-slurm', { runs: runs.map(r => r.key), channels: s.channels, section: s.section })
    toast.push({ text: `${runs.length} job${runs.length === 1 ? '' : 's'} added to Jobs · results return through Jobs › Manifest inbox`, action: { label: 'Open Jobs', onClick: () => navigate('jobs') } })
    notWired('POST /discovery/runs/slurm')
    onCreated?.()
    onClose()
  }
  return (
    <Modal open={open} onClose={onClose} title="Create SLURM script" subtitle={`${runs.length} run${runs.length === 1 ? '' : 's'} × ${s.channels.length} channels · ${fmtMin(dx.estimateMin || runs.reduce((a, r) => a + (r.perChannelMin ?? 0) * s.channels.length, 0))}`}
      testid="slurm-modal" footerNote={`Creating the script adds ${runs.length} job${runs.length === 1 ? '' : 's'} to Jobs · results return through Jobs › Manifest inbox`}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="cluster" icon="file" onClick={create} disabled={runs.length === 0} disabledReason="no pending run to script" testid="slurm-create">Create</Button></>}>
      {runs.length === 0 ? <EmptyState size="sm" title="Nothing to script" caption="every run in this session has results or is already on the cluster" /> : <CodeBlock title="SLURM script" code={script} filename={`discovery_${s.name}.sh`} lineNumbers testid="slurm-script" />}
    </Modal>
  )
}
