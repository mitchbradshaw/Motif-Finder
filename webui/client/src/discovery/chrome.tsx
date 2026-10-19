/* Discovery chrome shared by Runs · Seed search · Compare · Compare every stage: the toolbar (session, scope, null,
 * cost, History), the Scope card (recording, channel chips, section brush across ≤ 3 strips with paging), the Runs
 * card (two ways to add a run, rows with A / B pick boxes), load/fail states and the SLURM script modal. */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { DatasetName } from '../naming'
import {
  Button, Callout, Checkbox, Chip, CodeBlock, DisabledReason, Dropdown, EmptyState, Icon, IconButton, InfoTip, Modal, NumberField, Popover, ProgressBar,
  RangeSlider, TextField, Tooltip, cx, recordDemoWrite, useNotWired, useQueryState, useSim,
} from '../kit'
import { getHistory, getOverview, heldOutReason, fmtMin, DISCOVERY_LIMIT_MIN, type DiscoveryRun } from '../api/discovery'
import { ApiError, applyDiscoveryTemplates, extendDiscoveryRun, removeDiscoveryRun, runDiscoverySeedSearchOnce } from '../api'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { useToast } from '../shell/Toast'
import { openDiscoveryHistoryRun, putDiscoverySession } from '../api'
import { exportDiscoveryChain, importDiscoveryChain, type DiscChainExport } from '../api'
import { RunGlyph } from './glyphs'
import { PAGE_SIZE, hasResults, pickable, type Discovery } from './session'

/* ------------------------------------------------------------------ load / fail */
export function Loading({ height = 200, label = 'loading', testid }: { height?: number; label?: string; testid?: string }) {
  return <div className="dsc-loading k-card" style={{ height }} data-testid={testid ?? 'discovery-loading'}><ProgressBar indeterminate size="sm" width={160} labelPosition="none" /><span>{label}</span></div>
}
/** The reload indicator. Always in the layout, whatever it is doing: only its
 *  opacity changes, so a reload can never move the content under it. `Loading`
 *  is for a first load -- there is nothing to shove down then. */
export function Refreshing({ on, label = 'refreshing', testid = 'discovery-refreshing' }: { on: boolean; label?: string; testid?: string }) {
  // ux-1019: a second indicator on the same page (the fires card, the map levels) takes its own testid — the smoke's
  // discovery flow counts exactly one `discovery-refreshing`, the page's own
  return (
    <div className="dsc-refreshing" data-testid={testid} data-on={on ? '1' : '0'} aria-hidden={!on}
         style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--muted)', opacity: on ? 1 : 0, transition: 'opacity 140ms' }}>
      <ProgressBar indeterminate size="sm" width={90} labelPosition="none" /><span>{label}</span>
    </div>
  )
}
/** AR (the speed pass): a Discovery page's first paint. It used to be a 600 px "loading the session" card that the
 *  real layout then replaced — the toolbar's icons jumped down and back as it went. This is the real layout in
 *  grey: the reload line where the page keeps it, the toolbar row at its height, the Scope card, the two columns.
 *  The page swaps it for its content without moving the toolbar. The reload line runs indeterminate: the session
 *  and the run list report no progress to show. */
export function DiscoverySkeleton({ label, cols = true, testid = 'discovery-skeleton' }: { label: string; cols?: boolean; testid?: string }) {
  const block = (w: number | string, h: number) => <span className="skeleton" style={{ display: 'block', width: w, height: h }} />
  return (
    <>
      <Refreshing on label={label} />
      <div className="dsc-toolbar" data-testid={testid} aria-busy="true" aria-label={label}>
        {block(170, 30)}{block(300, 32)}<span className="k-spacer" />{block(110, 28)}{block(110, 28)}{block(90, 28)}{block(84, 32)}
      </div>
      <div className="k-card dsc-scope" aria-hidden="true">
        <div className="dsc-scope-head">{block(60, 18)}{block(220, 24)}<span className="k-spacer" />{block(160, 24)}</div>
        {block('100%', 28)}{block('100%', 96)}
      </div>
      {cols && (
        <div className="dsc-cols" aria-hidden="true">
          <div className="k-card" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8, minHeight: 420 }}>
            {block(120, 18)}{[0, 1, 2, 3, 4, 5].map(i => <span key={i}>{block('100%', 44)}</span>)}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
            <div className="k-card" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>{block(180, 18)}{block('100%', 200)}</div>
            <div className="k-card" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>{block(140, 18)}{block('100%', 160)}</div>
          </div>
        </div>
      )}
    </>
  )
}
export function LoadFailed({ what, error, onRetry }: { what: string; error: Error; onRetry: () => void }) {
  return <Callout tone="red" icon="alert-triangle" title={`Could not load ${what}`} action={<Button variant="primary" size="sm" icon="refresh" onClick={onRetry}>Retry</Button>} testid="discovery-load-failed">{error.message}</Callout>
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
    setEditing(false)
    // PUT /api/discovery/session is the same route the scope card writes through
    putDiscoverySession({ name: draft }).then(() => dx.reload())
      .catch(e => console.error('the session name could not be saved', e))
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
      <DatasetName file={dx.recording.file} testid="scope-dataset" /> · {s.channels.length} channel{s.channels.length === 1 ? '' : 's'} · {s.section[0]}–{s.section[1]} h <Icon name="chevron-down" size={11} />
    </Chip>
  )
}

export function NullChip({ dx }: { dx: Discovery }) {
  if (!dx.scope) return null
  const { nullMethod, nullN, nullRequested, nullReason, nullTemplateN, nullTemplateMethod, nullExplicit } = dx.scope
  // no method means no null ran: say the server's reason, not a method and a draw count nothing produced
  if (!nullMethod) return (
    <span className="dsc-null" data-testid="null-chip">
      <span className="dot" style={{ background: 'var(--amber)' }} /><span className="muted">null</span> <b data-testid="null-unsupported">none</b>
      <InfoTip title="No null on this scope">
        {nullReason ?? `${nullRequested ?? 'the method Settings › Nulls names'} is not implemented by preprocessing.surrogate`}
        {' '}Until a null runs there is no “null expects” and no “× null” to compare a run against.{' '}
        <Button variant="link" size="sm" onClick={() => navigate('settings/nulls')}>Settings › Nulls</Button>
      </InfoTip>
    </span>
  )
  return (
    <span className="dsc-null" data-testid="null-chip">
      {/* one count per run KIND (Q35): a template run's draw is the whole sweep again, a seed search's is one
          match. The chip used to print the seed search's 200× over template runs that had drawn one (D4). */}
      <span className="dot" style={{ background: 'var(--green)' }} /><span className="muted">null</span>{' '}
      <b data-testid="null-chip-text">{nullTemplateMethod && nullTemplateMethod !== nullMethod
        ? `template run ${nullTemplateMethod} ${nullTemplateN}× · seed search ${nullMethod} ${nullN}×`
        : `${nullMethod} · template run ${nullTemplateN}× · seed search ${nullN}×`}</b>
      <InfoTip title="Null for every run">
        The next template run is paired with <b>{nullTemplateN}</b> surrogate draws per channel and the next seed search with <b>{nullN}</b>{' '}
        ({nullExplicit ? 'set on this session' : 'Settings › Nulls'}). Each draw is the whole chain again on a {nullMethod} surrogate of the same scope, and it is
        counted in the estimate. “Null expects” in the scoreboard is the mean over a run’s draws, and each row states the count <i>that run</i> drew —
        a run made under an earlier setting keeps the count it has.{' '}
        <Button variant="link" size="sm" onClick={() => navigate('settings/nulls')}>Settings › Nulls</Button>
      </InfoTip>
    </span>
  )
}

export function CostChip({ dx, label, detail }: { dx: Discovery; label?: ReactNode; detail?: ReactNode }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  if (!dx.scope) return null
  const over = dx.overLimit
  const text = label ?? (dx.pending.length === 0 ? <><b>nothing pending</b></> : over ? <><b>{fmtMin(dx.estimateMin)}</b> routes to cluster</> : <><b>{fmtMin(dx.estimateMin)}</b> <span className="muted">local</span></>)
  return (
    <>
      <button ref={ref} type="button" className={cx('dsc-cost', over && !label && 'over')} onClick={() => setOpen(o => !o)} data-testid="cost-chip" aria-expanded={open}>
        <Icon name="hourglass" size={12} />{text}
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} title="Cost of pending runs" subtitle={`local limit ${DISCOVERY_LIMIT_MIN} min`} width={320} testid="cost-popover">
        <div className="dsc-pop-list">
          {detail && <div className="mono small" data-testid="cost-detail">{detail}</div>}
          {dx.pending.length === 0 && <span className="muted">No run is waiting to start: every run has results or is queued.</span>}
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
      <Button variant="primary" ref={ref} icon="clock" onClick={() => setQ(open ? null : 'history')} testid="history-button" aria-expanded={open}>History</Button>
      <Popover open={open} onClose={() => setQ(null)} anchorRef={ref} placement="bottom-end" title="Discovery history" subtitle={dx.recording?.label} width={380} testid="history-popover">
        {hist.error && <LoadFailed what="history" error={hist.error} onRetry={hist.reload} />}
        {hist.data?.map(h => {
          const inSession = h.inSession || dx.runs.some(r => r.key === h.runKey)
          return (
            <div key={h.id} className="dsc-hist-row" data-testid={`history-${h.id}`}>
              <div><b className="mono">{h.id}</b> {h.label}<div className="muted small">{h.when} · {h.status} · {h.detail}</div></div>
              <Button variant="primary" size="sm" disabled={inSession} disabledReason={inSession ? 'already in this session' : undefined} testid={`history-open-${h.id}`}
                onClick={() => {
                  /* Adoption is a real write: the row comes back from /runs on
                   * the reload, carrying the run group it actually ran in. It
                   * used to be invented here — an invented template name and a
                   * guessed kind under the real run key, which then went out in
                   * `runs=` to routes that had never heard of it. */
                  openDiscoveryHistoryRun(h.id)
                    .then(r => { dx.reload(); hist.reload(); toast.push({ text: r.adopted ? `${h.id} ${h.label} added to this session · ${r.note}` : `${h.id} ${r.note}` }) })
                    .catch(e => toast.push({ text: `could not open ${h.id}: ${e.message}` }))
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
  /* A held-out recording is not asked for. The bridge refuses it with a 423 on
   * every route that would serve its samples, and the callout below is drawn
   * from `rec.heldOut`, which the session payload already carries — so making
   * the request anyway would only add a failed fetch to the console for an
   * answer the page already has. */
  const overview = useSourced(() => s && rec && !rec.heldOut
    ? getOverview(s.recording, dx.visibleChannels)
    : Promise.resolve({ data: { data: {} as Record<string, number[]> }, source: 'demo' as const }),
    [s?.recording, rec?.heldOut, dx.visibleChannels.join(',')])
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
    toast.push({ text: `recording changed to ${r.label} · ${dx.runs.filter(hasResults).length} runs marked stale` })
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
        <InfoTip title="Scope">One recording, one or more channels and one section. Every run in the session applies to the whole scope; at most {PAGE_SIZE} strips show at a time.</InfoTip>
        <span ref={recRef}>
          <Dropdown prefix="recording" value={s.recording} testid="recording-select"
            onChange={v => { if (v !== s.recording) setConfirmRec(v) }}
            options={dx.recordings.map(r => ({ value: r.key, label: r.label, hint: `${r.label === r.file ? '' : `${r.file} · `}${r.channels.length} ch · ${r.hours} h`, disabled: r.heldOut, reason: r.heldOut ? 'held out · locked (D6)' : undefined }))} />
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
          <Popover open={addOpen} onClose={() => setAddOpen(false)} anchorRef={addRef} title="Channels in scope" subtitle={rec.label} width={300} testid="add-channel-popover">
            <div className="dsc-ch-grid">
              {rec.channels.map(ch => <Checkbox key={ch} checked={addSel.includes(ch)} label={ch} testid={`add-channel-${ch}`} onChange={v => setAddSel(v ? [...addSel, ch] : addSel.filter(c => c !== ch))} />)}
            </div>
            <div className="row" style={{ gap: 6, marginTop: 8 }}>
              <Button variant="primary" size="sm" onClick={() => setAddSel([...rec.channels])} disabled={addSel.length === rec.channels.length} disabledReason="every channel is selected" testid="add-channel-all">Select all</Button>
              <Button variant="primary" size="sm" onClick={() => setAddSel([])} disabled={addSel.length === 0} disabledReason="nothing is selected" testid="add-channel-none">None</Button>
            </div>
            <div className="row between" style={{ marginTop: 10 }}>
              <span className="muted small">{addSel.length} selected · {addSel.length > PAGE_SIZE ? `strips page ${PAGE_SIZE} at a time` : 'fits on one page'}</span>
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
            <Button variant="primary" icon="flask" onClick={runPreview} disabled={runnable.length === 0 || !!refused || preview.busy} disabledReason={refused ? 'held out recording' : runnable.length === 0 ? 'nothing to preview — every run in this session has results' : undefined} loading={preview.busy} testid="preview-sample">Preview on a 4 h sample</Button>
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
        <Callout tone="red" icon="lock" title="Held out" testid="scope-refused" action={<Button variant="primary" size="sm" onClick={() => { dx.resetScope(); navigate('discovery/runs') }}>Back to the session's recording</Button>}>{refused}</Callout>
      ) : (
        <div className="dsc-strips-wrap">
          <Strips channels={dx.visibleChannels} traces={traces} hours={hours} section={s.section} onSection={sec => dx.setScope({ section: sec })} />
          <div className="dsc-pager-v" data-testid="channel-pager">
            <IconButton icon="chevron-up" label={`previous ${PAGE_SIZE} channels`} bordered disabled={dx.chPage <= 1} disabledReason="already at the first channels" onClick={() => dx.setChPage(dx.chPage - 1)} testid="channel-pager-up" />
            <span className="mono small" data-testid="channel-pager-label">{(dx.chPage - 1) * PAGE_SIZE + 1}–{Math.min(s.channels.length, dx.chPage * PAGE_SIZE)} of {s.channels.length}</span>
            <IconButton icon="chevron-down" label={`next ${PAGE_SIZE} channels`} bordered disabled={dx.chPage >= dx.pageCount} disabledReason={s.channels.length <= PAGE_SIZE ? 'every channel fits on one page' : 'already at the last channels'} onClick={() => dx.setChPage(dx.chPage + 1)} testid="channel-pager-down" />
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

/* fixup-z: the band runs of one *Apply template* with a band scope are one band set, and Compare takes the set as
 * one side -- `set:<bandSet>`, the union of its runs de-duplicated by the matching rule. A set is not a run: it
 * has no row of its own on the server, so the page derives it from its members, in band order. */
export interface BandSet { key: string; bandSet: string; label: string; members: DiscoveryRun[]; done: boolean }
export const SET_PREFIX = 'set:'
export function bandSets(runs: DiscoveryRun[]): BandSet[] {
  const by = new Map<string, DiscoveryRun[]>()
  for (const r of runs) if (r.bandSet && r.status !== 'superseded') by.set(r.bandSet, [...(by.get(r.bandSet) ?? []), r])
  return [...by.entries()].map(([bandSet, ms]) => {
    const members = [...ms].sort((a, b) => (a.bandIndex ?? 0) - (b.bandIndex ?? 0))
    const tpl = members[0].template ?? members[0].label
    return { key: `${SET_PREFIX}${bandSet}`, bandSet, members, done: members.every(m => m.status === 'done'),
      label: `${tpl} · ${members.length} band${members.length === 1 ? '' : 's'}` }
  })
}
/** A Compare side by key: a run, or a band set as a run-shaped stand-in (label, colour of its first band). */
export function sideRun(runs: DiscoveryRun[], key: string): DiscoveryRun | null {
  const r = runs.find(x => x.key === key)
  if (r) return r
  const set = bandSets(runs).find(x => x.key === key)
  return set ? { ...set.members[0], key: set.key, label: `${set.label} (union)`, status: set.done ? 'done' : set.members[0].status } : null
}

export function RunsCard({ dx, mode, selected, onSelect, draft, compareActive, onAddTemplate }: {
  dx: Discovery; mode: RunsMode; selected?: string | null; onSelect?: (key: string) => void; draft?: ReactNode; compareActive?: boolean; onAddTemplate: () => void
}) {
  const runs = dx.runs
  const pickedLabel = dx.picks.length === 2 ? '2 picked' : `${dx.picks.length} of 2 picked`
  const canCompare = dx.picks.length === 2
  const all = runs.filter(r => r.status !== 'draft')
  /* in seed mode the card is the seed searches' (the researcher, 2026-10-09): template runs are on Runs, and
   * the button for the mode you are in reads pressed */
  const listed = mode === 'seed' ? all.filter(r => r.kind === 'seed' || r.kind === 'draft') : all
  const hidden = all.length - listed.length
  const inSession = all.filter(r => r.kind !== 'reference').length + (draft ? 1 : 0)
  return (
    <section className="k-card dsc-runs" data-testid="runs-card" aria-label="Runs">
      <div className="dsc-runs-head">
        <h3>Runs</h3>
        <InfoTip title="Runs">A run is a template applied to the scope, or a seed search over it (P17). Pick two to compare. Human annotations are the fixed reference.</InfoTip>
        <span className="muted small">{inSession} in this session</span>
      </div>
      <div className="dsc-runs-add">
        <Button icon="layers" variant={mode === 'runs' ? 'primary' : 'default'} onClick={onAddTemplate} testid="apply-template" aria-pressed={mode === 'runs'}>Apply template</Button>
        <Button icon="target" variant={mode === 'seed' ? 'primary' : 'default'} onClick={() => navigate('discovery/seed')} testid="seed-search" aria-pressed={mode === 'seed'}>Seed search</Button>
      </div>
      <div className="dsc-runs-list" data-testid="runs-list">
        {listed.length === 0 && <EmptyState size="sm" icon="inbox" title="No runs" caption="add a template or a seed search" />}
        {listed.slice(0, 4).map(r => <RunRow key={r.key} dx={dx} run={r} selected={selected === r.key} onSelect={onSelect} mode={mode} />)}
        {draft}
        {listed.slice(4).map(r => <RunRow key={r.key} dx={dx} run={r} selected={selected === r.key} onSelect={onSelect} mode={mode} />)}
        {mode !== 'seed' && bandSets(listed).map(set => <BandSetRow key={set.key} dx={dx} set={set} />)}
        {mode === 'seed' && hidden > 0 && <button type="button" className="dsc-inline-link muted small" onClick={() => navigate('discovery/runs')} data-testid="runs-hidden">{hidden} other run{hidden === 1 ? '' : 's'} (templates, the reference) on Runs →</button>}
        {listed.length === 1 && listed[0].kind === 'reference' && <EmptyState size="sm" icon="layers" title="Only the human reference" caption="Apply template or Seed search adds the first run" testid="runs-empty" />}
      </div>
      <div className="dsc-runs-foot" data-testid="runs-foot">
        <span className="muted small">{mode === 'seed' ? "drafts can't be compared" : pickedLabel}</span>
        {mode === 'seed' ? (
          <DisabledReason reason="a draft has no results to compare — run it first"><Button variant="primary" icon="compare" disabled disabledReason="a draft has no results to compare — run it first" testid="compare-button">Compare</Button></DisabledReason>
        ) : compareActive ? (
          <Button icon="compare" variant="primary" aria-pressed onClick={() => navigate('discovery/runs')} testid="compare-button" title="comparing — click to go back to all runs">Comparing</Button>
        ) : (
          <DisabledReason disabled={!canCompare} reason="pick two runs to compare">
            <Button variant="primary" icon="compare" disabled={!canCompare} disabledReason={canCompare ? undefined : 'pick two runs to compare'} onClick={() => navigate(`discovery/compare?a=${encodeURIComponent(dx.picks[0])}&b=${encodeURIComponent(dx.picks[1])}`)} testid="compare-button">Compare</Button>
          </DisabledReason>
        )}
      </div>
    </section>
  )
}

function BandSetRow({ dx, set }: { dx: Discovery; set: BandSet }) {
  const pickIdx = dx.picks.indexOf(set.key)
  const found = set.members.map(m => dx.foundOf(m.key) ?? m.found)
  return (
    <div className="dsc-run dsc-band-set" style={{ ['--run' as string]: set.members[0].colour }} data-testid={`band-set-row-${set.bandSet}`} data-status={set.done ? 'done' : 'running'}>
      <span className="dsc-run-body" title="the band runs of one application, compared as their union">
        <Icon name="layers" size={16} />
        <span className="dsc-run-text">
          <b>{set.label}</b>
          <span className="dsc-run-meta"><span className="k-badge t-purple">band set</span><span className="muted">{set.members.map(m => m.band?.label ?? m.key).join(' · ')}</span></span>
          <span className="dsc-run-line small">{set.done ? <span>union of {set.members.length} runs · {found.map(f => f ?? '…').join(' + ')} found before de-duplication</span> : <span className="blue">waiting for every band to finish</span>}</span>
        </span>
      </span>
      {pickIdx >= 0
        ? <button type="button" className={cx('dsc-pick', pickIdx === 0 ? 'a' : 'b')} onClick={() => dx.togglePick(set.key)} aria-label={`unpick ${set.label} (${pickIdx === 0 ? 'A' : 'B'})`} data-testid={`pick-${set.key}`}>{pickIdx === 0 ? 'A' : 'B'}</button>
        : <DisabledReason disabled={!set.done} reason="every band run needs results before the set can be compared">
          <button type="button" className="dsc-pick" disabled={!set.done} onClick={() => dx.togglePick(set.key)} aria-label={`pick ${set.label} to compare`} data-testid={`pick-${set.key}`} />
        </DisabledReason>}
      {/* a band set is not removed as one row; the ghost keeps its badge in the same column as the runs' */}
      <span className="dsc-run-remove ghost" aria-hidden />
    </div>
  )
}

function RunRow({ dx, run, selected, onSelect, mode }: { dx: Discovery; run: DiscoveryRun; selected: boolean; onSelect?: (k: string) => void; mode: RunsMode }) {
  const toast = useToast()
  const [importing, setImporting] = useState(false)
  /* the × (the researcher, 2026-10-06): the run leaves this session. The row is marked, not deleted — its runs
   * and detections stay, nothing human is written, and History lists it as removed and can put it back. */
  const remove = () => {
    removeDiscoveryRun(run.key)
      .then(r => { dx.reload(); toast.push({ text: `${run.label} removed from this session${r.cancelled ? ' · its job was cancelled' : ''} · the runs are kept — History brings it back` }) })
      .catch(e => { console.error('the run could not be removed', e); toast.push({ text: `${run.label} was not removed · ${e instanceof Error ? e.message : String(e)}` }) })
  }
  /* The row used to read a client-side simulator keyed on the run: `add()`
   * started it, it ticked for a fixed number of steps and declared the run
   * done. Now that *Add and run* is a real POST, nothing starts that timer, so
   * a genuinely running run drew an empty bar at 0 % for ever. Progress and the
   * channels-done count come from the server's own run row, and `useDiscovery`
   * re-reads the runs while any of them is running. */
  const status = run.status
  const pickIdx = dx.picks.indexOf(run.key)
  const found = dx.foundOf(run.key)
  const nCh = dx.scope?.channels.length ?? 0
  /* A finished run ran on the channels it ran on. This read the CURRENT scope,
   * so adding a channel rewrote every historical row's "2 ch" into "3 ch" for
   * runs that had never touched the third. The server sends `channelsDone`. */
  const ranOn = run.channelsDone ? run.channelsDone.split('/').pop()!.trim() : String(nCh)
  const canPick = pickable({ ...run, status })
  /* discovery-coverage (the researcher, 2026-10-18): which channels in scope this run has stored results on, one cell
   * each — filled where it ran, hatched where it never did, amber while running, red where it failed — and *run on
   * the missing N*, which EXTENDS this run (same key) when the template is unchanged. */
  const [extending, setExtending] = useState(false)
  const scopeChans = dx.scope?.channels ?? []
  const cov = run.kind !== 'reference' ? run.coverage : undefined
  const missing = cov ? scopeChans.filter(c => cov[c] === 'not_run') : []
  const extendable = run.kind === 'template' && !!run.template && !run.band && !run.windowed
  const extend = () => {
    const s = dx.scope
    if (!s) return
    setExtending(true)
    extendDiscoveryRun(run.key, missing)
      .then(ack => { dx.reload(); toast.push({ text: `${run.label}: ${ack.note}` }) })
      .catch(e => {
        dx.reload()
        const msg = (e instanceof Error ? e.message : String(e)).replace(/^\d{3} /, '')
        const code = e instanceof ApiError ? (e.detail as { code?: string } | undefined)?.code : undefined
        if (code === 'params_differ' && run.template) {
          const tpl = run.template
          toast.push({ text: `${run.label} was not extended · ${msg}`, action: { label: 'Apply as a new run', hint: `${tpl} over ${missing.join(', ')}`, onClick: () => {
            applyDiscoveryTemplates([tpl], missing, s.section[0], s.section[1])
              .then(() => dx.reload())
              .catch(err => toast.push({ text: `${tpl} was not applied · ${err instanceof Error ? err.message : String(err)}` }))
          } } })
        } else toast.push({ text: `${run.label} was not extended · ${msg}` })
      })
      .finally(() => setExtending(false))
  }
  const kindBadge = run.kind === 'reference' ? <span className="k-badge t-grey">reference</span> : run.kind === 'seed' ? <span className="k-badge t-purple">seed</span> : run.kind === 'draft' ? <span className="k-badge t-amber">draft</span> : <span className="k-badge t-blue">template</span>
  let line: ReactNode = null
  switch (status) {
    case 'done': line = <span>{found ?? '…'} found · {ranOn} ch · done {run.doneAt ?? '—'}{run.nullSource === 'preview' ? <span className="muted"> · null from the preview</span> : run.nullSource === 'hpc' ? <span className="muted"> · null from the cluster</span> : run.nullSource === 'off' ? <span className="muted"> · no null</span> : null}{run.hpcImported && <span className="muted" data-testid={`run-from-cluster-${run.key}`}> · computed on the cluster{run.clusterAgrees === true ? ', its counts agree' : ''}</span>}{run.clusterCheck && <span className="amber" title={run.clusterCheck}> · differs from the cluster: {run.clusterCheck}</span>}{dx.stale && <span className="amber"> · stale</span>}</span>; break
    case 'on cluster': line = run.hpc
      ? (run.hpc.kind === 'chain'
        /* round A_2 (P2): a template run's chain job — it comes back as this row, through Import results */
        ? <span className={run.hpcRefused ? 'red' : 'blue'} title={run.hpcRefused ?? undefined} data-testid={`run-on-cluster-${run.key}`}>{run.hpcRefused ? `import refused · ${run.hpcRefused}` : `on the cluster · ${run.hpc.tasks ?? '?'} task${run.hpc.tasks === 1 ? '' : 's'} · bring ${run.hpc.returnPath ?? run.hpc.resultPath} back, then Import results`}</span>
        : <span className="blue">on the cluster · import {run.hpc.resultPath.split('/').pop()} on the Seed page when it is back</span>)
      : <span className="dsc-run-progress"><ProgressBar value={run.progress ?? 0} size="sm" labelPosition="none" width={96} /><span className="blue">cluster {Math.round((run.progress ?? 0) * 100)} %</span></span>; break
    case 'running': case 'queued': line = <span className="dsc-run-progress"><ProgressBar value={run.progress ?? 0} size="sm" labelPosition="none" width={96} /><span className="blue">{status === 'queued' ? 'queued' : `running · ${run.progressText ?? (run.channelsDone ? `${run.channelsDone} channels` : '…')}`}</span></span>; break
    case 'new': line = <span>new · local</span>; break
    case 'paused': line = <span className="dsc-run-progress"><ProgressBar value={run.progress ?? 0} size="sm" tone="amber" labelPosition="none" width={56} /><span className="amber">paused {run.pausedAt?.stage}/{run.pausedAt?.of}</span></span>; break
    case 'superseded': line = <span className="muted">superseded · no verdicts written</span>; break
    case 'failed': line = <span className="red">failed · {run.error ?? 'the server reported no error text — open it in Jobs'}</span>; break
    case 'reference': break
  }
  return (
    <div className={cx('dsc-run', selected && 'selected', status === 'paused' && 'paused', status === 'superseded' && 'superseded', status === 'failed' && 'failed')} style={{ ['--run' as string]: run.colour }} data-testid={`run-row-${run.key}`} data-status={status}>
      <button type="button" className="dsc-run-body" onClick={() => onSelect ? onSelect(run.key) : navigate(`discovery/runs?run=${encodeURIComponent(run.key)}`)} aria-pressed={selected} title={mode === 'runs' ? `browse ${run.label}` : `open ${run.label} in Runs`}>
        <RunGlyph kind={run.glyph} width={40} height={28} />
        <span className="dsc-run-text">
          <b>{run.label}</b>
          <span className="dsc-run-meta">{kindBadge}<span className="k-meta">{run.detail}</span></span>
          {line && <span className="dsc-run-line small">{line}</span>}
          {cov && scopeChans.length > 0 && <CoverageStrip runKey={run.key} channels={scopeChans} coverage={cov} />}
          {run.extendError && <span className="dsc-run-line small" style={{ color: 'var(--red)' }} title={run.extendError} data-testid={`extend-error-${run.key}`}>{run.extendError}</span>}
        </span>
      </button>
      {missing.length > 0 && extendable && (status === 'done' || status === 'failed') && (
        <Button variant="primary" size="sm" icon="play" className="dsc-run-retry" loading={extending} disabled={extending} onClick={extend} testid={`run-missing-${run.key}`}
          title={`run ${run.label} on ${missing.join(', ')} too — the same run gains the channel${missing.length === 1 ? '' : 's'} (its key stays) while the template is unchanged`}>
          {extending ? 'Starting…' : `Run on the missing ${missing.length}`}</Button>
      )}
      {status === 'paused' && run.id && <Button variant="link" size="sm" icon="external" className="dsc-run-jobs-link" onClick={() => navigate('jobs')} testid={`open-in-jobs-${run.key}`}>Open in Jobs</Button>}
      {/* round A_2 (P2): the chain job's results are back — verified, the cache restored, the run written here */}
      {status === 'on cluster' && run.hpc?.kind === 'chain' && <Button variant="primary" size="sm" icon="download" className="dsc-run-retry" loading={importing} disabled={importing} onClick={() => {
        setImporting(true)   // ux-1018: the button shows the import is under way — the POST verifies and restores every task before it answers
        importDiscoveryChain(run.key)
          .then(ack => { dx.reload(); toast.push({ text: `${run.label}: ${ack.note}`, action: { label: 'Open Jobs', onClick: () => navigate('jobs') } }) })
          .catch(e => { dx.reload(); toast.push({ text: `${run.label} was not imported · ${(e instanceof Error ? e.message : String(e)).replace(/^\d{3} /, '')}` }) })
          .finally(() => setImporting(false))
      }} testid={`chain-import-${run.key}`} title="verify the tasks' results against this machine, restore their step cache, and write the run's channels here">{importing ? 'Importing…' : 'Import results'}</Button>}
      {/* a real retry: a seed run is started again from its seed and cut, a template run from its template, over the
          scope. It used to mark the row `new` in the page's memory, which the Seed page then took for a pending run of
          this search and greyed *Run seed search* out. */}
      {status === 'failed' && <Button variant="primary" size="sm" icon="refresh" className="dsc-run-retry" onClick={() => {
        const s = dx.scope
        if (!s) return
        const again = run.kind === 'seed' && run.seedId
          ? runDiscoverySeedSearchOnce({ seedId: run.seedId, channels: s.channels, t0: s.section[0], t1: s.section[1], k: 200, label: run.label,
            ...(run.cut != null ? { cut: run.cut } : {}), ...(run.scales?.length ? { scales: run.scales } : {}) })
          : run.template ? applyDiscoveryTemplates([run.template], s.channels, s.section[0], s.section[1]) : null
        if (!again) return
        again.then(() => dx.reload()).catch(e => console.error('the run could not be retried', e))
      }} testid={`retry-${run.key}`}>Retry</Button>}
      {/* reports (2026-10-19): the run's figures and tables, drawn by the server — a finished run only */}
      {status === 'done' && run.kind !== 'reference' && <Button size="sm" variant="primary" icon="file" style={{ alignSelf: 'center' }} onClick={() => navigate(`reports/detection-run/${encodeURIComponent(run.key)}`)} title={`the report for ${run.label}: the map, the scoreboard, where it fires, twelve examples, the null and its parameters — figures and tables to paste`} testid={`report-${run.key}`}>Report</Button>}
      {status !== 'paused' && status !== 'superseded' && mode !== 'seed' && (
        pickIdx >= 0
          ? <button type="button" className={cx('dsc-pick', pickIdx === 0 ? 'a' : 'b')} onClick={() => dx.togglePick(run.key)} aria-label={`unpick ${run.label} (${pickIdx === 0 ? 'A' : 'B'})`} data-testid={`pick-${run.key}`}>{pickIdx === 0 ? 'A' : 'B'}</button>
          : <DisabledReason disabled={!canPick} reason={status === 'failed' ? 'a failed run has no results to compare' : 'no results yet to compare'}>
            <button type="button" className="dsc-pick" disabled={!canPick} onClick={() => dx.togglePick(run.key)} aria-label={`pick ${run.label} to compare`} data-testid={`pick-${run.key}`} />
          </DisabledReason>
      )}
      {mode === 'seed' && status !== 'paused' && status !== 'superseded' && <span className="dsc-pick ghost" aria-hidden />}
      {/* fixup-unpick: the x is the last item in the row, AFTER the badge — it used to be an absolute overlay on
          the same corner, so it intercepted the click meant for the badge. A reference run has no x; its ghost
          keeps the badges in one column. */}
      {run.kind !== 'reference'
        ? <button type="button" className="dsc-run-remove" onClick={remove} aria-label={`remove ${run.label} from this session`} title="remove from this session · the runs are kept; History brings it back" data-testid={`remove-${run.key}`}>×</button>
        : <span className="dsc-run-remove ghost" aria-hidden />}
    </div>
  )
}

/* ------------------------------------------------------------------ coverage strip */
const COVERAGE_WORDS: Record<string, string> = {
  covered: 'stored results', not_run: 'never ran here', running: 'running now', failed: 'failed here', discarded: 'discarded',
}
/** One small cell per scope channel: what the run is on it (discovery-coverage). The words are in each cell's title. */
function CoverageStrip({ runKey, channels, coverage }: { runKey: string; channels: string[]; coverage: Record<string, string> }) {
  const n = channels.filter(c => coverage[c] === 'covered').length
  return (
    <span className="dsc-cov" data-testid={`coverage-${runKey}`} aria-label={`results on ${n} of ${channels.length} channels in scope`}>
      {channels.map(c => {
        const state = coverage[c] ?? 'not_run'
        return <i key={c} className={`dsc-cov-cell ${state}`} data-state={state} data-channel={c} data-testid={`coverage-${runKey}-${c}`} title={`${c}: ${COVERAGE_WORDS[state] ?? state}`} />
      })}
      <span className="muted">{n} of {channels.length} ch</span>
    </span>
  )
}

/* ------------------------------------------------------------------ SLURM script */
/* The script is the core's, not the page's (round A_2, P2: `Working.discovery.chain_job`). One array job per run, one
 * task per channel, each task running the real chain AND its null draws on a scratch database keyed to this machine's
 * recording ids, resubmitting itself while its result reads incomplete; its results come back as this same run, through
 * Import results. EVERY ticked run is scripted — the modal used to script `runs[0]` alone and mark the others "on
 * cluster" in the browser only. Opening the modal is a dry run per run (the script and the job's numbers, nothing
 * written); Create writes each, and the server marks each run row on cluster. A script assembled in the browser would
 * look right and not run. */
type SlurmPreview = { ok: true; job: DiscChainExport } | { ok: false; reason: string }
const errText = (e: unknown) => (e instanceof Error ? e.message : String(e)).replace(/^\d{3} /, '')

export function SlurmModal({ open, onClose, dx, runs, onCreated }: { open: boolean; onClose: () => void; dx: Discovery; runs: DiscoveryRun[]; onCreated?: () => void }) {
  const toast = useToast()
  const [previews, setPreviews] = useState<Record<string, SlurmPreview>>({})
  const [shown, setShown] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [creating, setCreating] = useState(false)
  const [err, setErr] = useState<Error | null>(null)
  const [again, setAgain] = useState(0)
  const keys = runs.map(r => r.key).join(',')
  const bodyFor = (r: DiscoveryRun, dryRun: boolean) => ({
    template: r.template ?? r.key, channels: dx.scope?.channels ?? [], t0: dx.scope?.section[0] ?? 0, t1: dx.scope?.section[1] ?? 0,
    band: r.band ?? undefined, runKey: r.key, dryRun })
  useEffect(() => {
    if (!open || !dx.scope || !runs.length) return
    let live = true
    setBusy(true); setErr(null)
    Promise.all(runs.map(r => r.kind === 'seed'
      ? Promise.resolve<SlurmPreview>({ ok: false, reason: 'a seed search goes to the cluster from the Seed page, as its own job' })
      : exportDiscoveryChain(bodyFor(r, true)).then((job): SlurmPreview => ({ ok: true, job }), (e): SlurmPreview => ({ ok: false, reason: errText(e) }))))
      .then(list => {
        if (!live) return
        const next = Object.fromEntries(runs.map((r, i) => [r.key, list[i]])) as Record<string, SlurmPreview>
        setPreviews(next)
        setShown(cur => (cur && next[cur] ? cur : runs.find(r => next[r.key]?.ok)?.key ?? runs[0]?.key ?? null))
      })
      .catch(e => { if (live) setErr(e instanceof Error ? e : new Error(String(e))) })
      .finally(() => { if (live) setBusy(false) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, keys, again, dx.scope?.channels.join(','), dx.scope?.section.join(',')])
  if (!dx.scope || !dx.recording) return null
  const s = dx.scope
  const ready = runs.filter(r => previews[r.key]?.ok)
  const cur = shown ? previews[shown] : undefined
  const create = async () => {
    setCreating(true)
    const wrote: string[] = [], failed: string[] = []
    for (const r of ready) {
      try {
        const job = await exportDiscoveryChain(bodyFor(r, false))
        wrote.push(job.sbatch_command)
      } catch (e) {
        failed.push(`${r.label}: ${errText(e)}`)
      }
    }
    setCreating(false)
    await dx.reload()
    toast.push({
      text: wrote.length
        ? `${wrote.length} job${wrote.length === 1 ? '' : 's'} written · copy each run's spec, script and channel arrays to the cluster and sbatch it; when its tasks are complete, bring its …_out/return/ folder back and press Import results on the run (or in Jobs › Waiting on the cluster)${failed.length ? ` · not written: ${failed.join('; ')}` : ''}`
        : `nothing was written · ${failed.join('; ')}`,
      action: { label: 'Open Jobs', onClick: () => navigate('jobs') } })
    onCreated?.()
    onClose()
  }
  const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`
  return (
    <Modal open={open} onClose={onClose} title="Create SLURM script" subtitle={`${plural(runs.length, 'run')} × ${s.channels.length} channels · ${fmtMin(dx.estimateMin || runs.reduce((a, r) => a + (r.perChannelMin ?? 0) * s.channels.length, 0))}`}
      testid="slurm-modal" footerNote={`Create writes ${plural(ready.length, 'job')} (one per run, a task per channel, the null in each task) and marks ${ready.length === 1 ? 'that run' : 'those runs'} on the cluster · the results come back as the same run, through Import results on its row or Jobs › Waiting on the cluster`}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="cluster" icon="file" onClick={create} loading={creating} disabled={ready.length === 0 || busy} disabledReason={busy ? "reading each run's job" : 'no run here can be sent to the cluster'} testid="slurm-create">{ready.length > 1 ? `Create ${ready.length} jobs` : 'Create'}</Button></>}>
      {runs.length === 0 ? <EmptyState size="sm" title="Nothing to script" caption="every run in this session has results or is already on the cluster" testid="slurm-empty" />
        : err ? <LoadFailed what="the SLURM scripts" error={err} onRetry={() => setAgain(n => n + 1)} />
          : busy && !Object.keys(previews).length ? <Loading height={260} label="writing each run's job through Working.discovery.chain_job · a dry run, nothing is saved yet" />
            : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div data-testid="slurm-run-list" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {runs.map(r => {
                    const p = previews[r.key]
                    return (
                      <button type="button" key={r.key} onClick={() => setShown(r.key)} data-testid={`slurm-run-${r.key}`} data-ready={p?.ok ? '1' : '0'} aria-pressed={shown === r.key}
                        style={{ textAlign: 'left', padding: '4px 8px', borderRadius: 6, border: `1px solid ${shown === r.key ? 'var(--blue-400, #60a5fa)' : 'var(--border, #e5e7eb)'}`, background: 'transparent', cursor: 'pointer', fontSize: 12 }}>
                        <b>{r.label}</b>
                        {!p ? <span className="muted"> · …</span> : p.ok
                          ? <span className="muted"> · {plural(p.job.tasks, 'task')} on {p.job.profile.partition}{p.job.profile.gpu ? ' (GPU)' : ''} · {p.job.paired ? `${plural(p.job.draws, 'null draw')} in each` : 'no null'} · wall {p.job.wall_minutes} min{p.job.wall_verified ? '' : ' (unverified)'}{p.job.chunked.length ? ' · the profile in blocks' : ''}</span>
                          : <span className="red" data-testid={`slurm-run-refused-${r.key}`}> · not sent: {p.reason}</span>}
                      </button>
                    )
                  })}
                </div>
                {cur?.ok && (
                  <>
                    <div className="small muted" data-testid="slurm-steps">
                      {cur.job.steps}
                      <InfoTip title="How a chain job comes back">Each task writes its result and its step cache into <code>{cur.job.return_path}</code>. Import results checks the spec, every hash and each recording's content against this machine, restores the cache, then runs the chain here: the heavy steps (a matrix profile) are read from the cache, the cheap ones recomputed, and every row is written exactly as a local run's. A missing or incomplete task is refused by name and nothing is recorded.</InfoTip>
                    </div>
                    {!cur.job.wall_verified && (
                      <Callout tone="amber" icon="alert-triangle" title={`The ${cur.job.profile.partition} partition's wall is not recorded`} testid="slurm-wall-unverified">
                        The job asks for {cur.job.wall_minutes} minutes, the limit measured on a100-test, stops itself after {Math.round(cur.job.budget_s / 60)} and resubmits.
                        Read the real limit on rangpur (<code>sacctmgr show qos format=Name,MaxWall</code>) and record it in Working/config.py (HPC_WALLTIME_MINUTES_BY_PARTITION).
                      </Callout>
                    )}
                    {!!cur.job.warnings.length && <Callout tone="amber" icon="alert-triangle" title="Where the files are" testid="slurm-warnings">{cur.job.warnings.join(' · ')}</Callout>}
                    <CodeBlock title={cur.job.script_path} code={cur.job.script} filename={cur.job.script_path.split(/[\\/]/).pop() ?? 'discovery.sh'} lineNumbers testid="slurm-script" />
                  </>
                )}
                {cur && !cur.ok && <Callout tone="red" icon="alert-triangle" title="This run is not sent to the cluster" testid="slurm-refused">{cur.reason}</Callout>}
              </div>
            )}
    </Modal>
  )
}
