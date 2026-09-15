/* The Review shell (frames 1–7): header, queue toolbar, collapsible queue rail (frame 3), collapsible evidence
 * rail (frame 4) around one main column. Rails and toolbar popovers are deep-linkable: ?rail=queue|evidence|both,
 * ?pop=queues|blind|shortcuts, ?modal=unblind. */
import { useMemo, useRef, useState, type ReactNode } from 'react'
import { Header } from '../shell/Header'
import { navigate } from '../state'
import {
  Button, Checkbox, DisabledReason, EmptyState, Icon, IconButton, InfoTip, Kbd, MiniTrace, Modal, Pager, Popover, ProgressBar, RangeSlider,
  Seg, SelectField, Toggle, cx, fmtInt, usePagedList, useQueryState, type IconName,
} from '../kit'
import { useSourced } from '../api/seam'
import { useToast } from '../shell/Toast'
import { getAllQueues, VOCABULARY, type QueueData, type QueueRow } from '../api/review'
import { SHORTCUTS } from './keys'
import { counts, isJudged, queueCounts, unitHash, unitKey, units, type UnitRef } from './queue'
import { effective, useAutoAdvance, useBlindOverrides, useFilters, useRecords } from './store'

export const THUMB_Y: [number, number] = [-0.45, 0.45]
export const verdictColour = (v: string) => v === 'seed' ? 'var(--green)' : VOCABULARY.verdictColours[v] ?? 'var(--muted-2)'

export interface MicroStat { value: ReactNode; label: string; tone?: 'green' | 'amber' | 'purple' | 'muted'; icon?: IconName; section?: string; title?: string }

export function useBlind(queueId: string, defaultBlind: boolean): [boolean, (v: boolean) => void] {
  const [over, setOver] = useBlindOverrides()
  return [over[queueId] ?? defaultBlind, (v: boolean) => setOver(prev => ({ ...prev, [queueId]: v }))]
}

export function useRails() {
  const [rail, setRail] = useQueryState<string>('rail', '')
  const left = rail === 'queue' || rail === 'both', right = rail === 'evidence' || rail === 'both'
  const set = (l: boolean, r: boolean) => setRail(l && r ? 'both' : l ? 'queue' : r ? 'evidence' : null)
  return { left, right, setLeft: (v: boolean) => set(v, right), setRight: (v: boolean) => set(left, v), toggleBoth: () => (left && right ? set(false, false) : set(true, true)) }
}

const QUEUE_ICON: Record<string, IconName> = { target: 'target', scan: 'scan', wave: 'wave', grid: 'grid', flask: 'flask' }

interface ShellProps {
  data: QueueData; unit: UnitRef | null; blind: boolean; setBlind: (v: boolean) => void
  paused?: boolean; micro: MicroStat[]; evidenceTitle: ReactNode; evidence: ReactNode; forceDone?: boolean
  children: ReactNode
}

export function Shell({ data, unit, blind, setBlind, paused, micro, evidenceTitle, evidence, forceDone, children }: ShellProps) {
  const rails = useRails()
  const records = useRecords()
  const c = counts(data, records)
  const judged = forceDone ? c.total : c.judged
  const left = c.total - judged
  return (
    <>
      <Header workspace="Review" page="Inspector" subtitle={data.queue.headerSubtitle} demo />
      <div className="rv-root" data-testid="review-root">
        <Toolbar data={data} judged={judged} blind={blind} setBlind={setBlind} paused={paused} />
        <div className="rv-body">
          {rails.left
            ? <aside className="rv-rail left open" data-testid="queue-rail"><QueueRailOpen data={data} unit={unit} blind={blind} left={left} onClose={() => rails.setLeft(false)} /></aside>
            : <aside className="rv-rail left" data-testid="queue-rail-collapsed"><QueueRailCollapsed data={data} unit={unit} left={left} onOpen={() => rails.setLeft(true)} /></aside>}
          <main className={cx('rv-main', rails.left && 'narrow-l', rails.right && 'narrow-r')} data-testid="review-main">{children}</main>
          {rails.right
            ? <aside className="rv-rail right open" data-testid="evidence-rail">
                <div className="rv-rail-head"><h4>Evidence</h4><span className="mono muted sm">{evidenceTitle}</span><span className="grow" />
                  <IconButton icon="panel-right" label="close evidence rail" bordered onClick={() => rails.setRight(false)} testid="evidence-rail-toggle" /></div>
                <div className="rv-rail-scroll">{evidence}</div>
              </aside>
            : <aside className="rv-rail right" data-testid="evidence-rail-collapsed">
                <IconButton icon="panel-right" label="open evidence rail" bordered onClick={() => rails.setRight(true)} testid="evidence-rail-toggle" />
                <div className="rv-micro">
                  {micro.map((m, i) => (
                    <button key={i} type="button" className={cx('rv-micro-stat', m.tone)} title={m.title ?? `${m.label} — open the evidence rail`} data-testid={`micro-${m.label.replace(/\W+/g, '-')}`}
                      onClick={() => { rails.setRight(true); if (m.section) window.setTimeout(() => document.getElementById(`ev-${m.section}`)?.scrollIntoView({ block: 'start' }), 80) }}>
                      <b>{m.icon ? <Icon name={m.icon} size={15} /> : m.value}</b><span>{m.label}</span>
                    </button>
                  ))}
                </div>
              </aside>}
        </div>
      </div>
    </>
  )
}

/* ================= toolbar ================= */
function Toolbar({ data, judged, blind, setBlind, paused }: { data: QueueData; judged: number; blind: boolean; setBlind: (v: boolean) => void; paused?: boolean }) {
  const { queue } = data
  const [pop, setPop] = useQueryState<string>('pop', '')
  const [modal, setModal] = useQueryState<string>('modal', '')
  const [auto, setAuto] = useAutoAdvance()
  const toast = useToast()
  const qRef = useRef<HTMLButtonElement>(null), bRef = useRef<HTMLButtonElement>(null), sRef = useRef<HTMLButtonElement>(null)
  const close = () => setPop(null)
  const defaultBlind = queue.source === 'training-windows' || queue.source === 'model-verification'
  const onBlindToggle = (v: boolean) => {
    if (!v && defaultBlind) { setPop(null); setModal('unblind'); return }
    setBlind(v)
  }
  return (
    <div className="rv-toolbar" data-testid="review-toolbar">
      <button ref={qRef} type="button" className="rv-queue-chip" aria-expanded={pop === 'queues'} onClick={() => setPop(pop === 'queues' ? null : 'queues')} data-testid="queue-chip">
        <Icon name={QUEUE_ICON[queue.icon]} size={13} /><span className="pre">queue</span><span className="lbl">{queue.toolbarLabel}</span><Icon name="chevron-down" size={13} />
      </button>
      <Popover open={pop === 'queues'} onClose={close} anchorRef={qRef} title="Queues" subtitle="one source each" width={380} className="rv-pop" testid="queue-picker">
        <QueueList current={queue.id} onPick={id => { close(); navigate(`review/queue/${id}`) }} />
        <div className="rv-pop-foot"><Button variant="link" iconRight="arrow-right" onClick={() => navigate('jobs?filter=queues')}>Open in Jobs</Button></div>
      </Popover>

      <button ref={bRef} type="button" className={cx('rv-tool-chip', blind && 'blind')} aria-expanded={pop === 'blind'} onClick={() => setPop(pop === 'blind' ? null : 'blind')} data-testid="blind-chip">
        <Icon name={blind ? 'eye-off' : 'eye'} size={13} />
        {blind ? <span>blind · hidden until verdict</span> : <span>machine opinion visible</span>}
        <Icon name="info" size={12} className="rv-i" />
      </button>
      <Popover open={pop === 'blind'} onClose={close} anchorRef={bRef} title={blind ? 'Blind queue' : 'Machine opinion visible'} width={360} className="rv-pop" testid="blind-popover">
        <div className="rv-pop-text">
          <p><b>Hidden until the verdict:</b> score and × null, family affinity and nearest families, prior machine calls, the model's prediction, the evidence rail's machine sections.</p>
          <p><b>Never hidden:</b> the signal, other channels, artifact likelihood.</p>
        </div>
        <div className="rv-pop-row"><Toggle checked={blind} onChange={onBlindToggle} label="blind for this queue" tone="blue" testid="blind-toggle" /></div>
        <div className="muted mono sm">stored with every verdict from now on; earlier verdicts keep the state they were given under</div>
      </Popover>
      <Modal open={modal === 'unblind'} onClose={() => setModal(null)} size="sm" title={`See machine opinion in ${queue.title}?`} testid="unblind-modal"
        footer={<><Button onClick={() => { setBlind(false); setModal(null) }} testid="unblind-confirm">Show machine opinion</Button><Button variant="primary" onClick={() => setModal(null)} testid="unblind-keep">Keep blind</Button></>}>
        <p style={{ margin: 0 }}>Verdicts from now on are stored as sighted. {queue.source === 'model-verification' ? 'The registration sample expects blind verdicts.' : 'The manual-label arm expects blind verdicts.'}</p>
      </Modal>

      <span className="rv-tool-chip static" data-testid="writes-chip">
        <Icon name="database" size={13} /><span className="muted">writes</span><span>{queue.writes}</span>
        <InfoTip title="Write target">Each verdict writes one {queue.writes === 'adjudications' ? 'adjudication row on the detection (§4.1)' : queue.writes === 'annotations' ? 'annotation verdict on the human span' : 'window verdict on the window set (B15)'}. Nothing on this page writes a machine row.</InfoTip>
      </span>

      <span className="grow" />
      <div className="rv-progress" data-testid="queue-progress" title={`${fmtInt(judged)} of ${fmtInt(queue.total)} judged`}>
        <div className="row1"><span><b>{fmtInt(judged)}</b> / {fmtInt(queue.total)}</span><span className="muted">{queue.paceS ? `~${queue.paceS} s each` : 'pace not yet measured'}</span></div>
        <ProgressBar value={judged / queue.total} size="sm" labelPosition="none" width={170} ariaLabel="queue progress" />
      </div>
      <span className="k-divider-v" />
      <span className={cx('rv-auto', paused && 'paused')} data-testid="auto-advance">
        <Toggle checked={auto && !paused} onChange={v => paused ? toast.push({ text: 'auto-advance is paused until you confirm (Enter) or undo (Ctrl Z)' }) : setAuto(v)} label="auto-advance" testid="auto-advance-toggle" />
      </span>
      <Button ref={sRef} icon="keyboard" onClick={() => setPop(pop === 'shortcuts' ? null : 'shortcuts')} aria-expanded={pop === 'shortcuts'} testid="shortcuts-button">Shortcuts</Button>
      <Popover open={pop === 'shortcuts'} onClose={close} anchorRef={sRef} placement="bottom-end" title="Shortcuts" subtitle="Review" width={380} className="rv-pop" testid="shortcuts-popover">
        <table className="rv-keys"><tbody>
          {SHORTCUTS.map(s => <tr key={s.action}><td>{s.keys.map(k => <Kbd key={k} size="sm">{k}</Kbd>)}</td><td>{s.action}</td></tr>)}
        </tbody></table>
        <div className="rv-pop-foot"><Button variant="link" iconRight="arrow-right" onClick={() => navigate('settings/keyboard')}>Change keys in Settings › Keyboard & behaviour</Button></div>
      </Popover>
    </div>
  )
}

/* ================= queue list (rail + picker) ================= */
function QueueList({ current, onPick }: { current: string; onPick: (id: string) => void }) {
  const all = useSourced(getAllQueues, [])
  const records = useRecords()
  const [over] = useBlindOverrides()
  if (all.error) return <div className="error-card" data-testid="queues-error">Queues failed to load: {all.error.message}</div>
  if (!all.data) return <div className="skeleton" style={{ height: 180 }} />
  return (
    <div className="rv-queues" data-testid="queue-list">
      {all.data.map(d => {
        const q = d.queue
        const c = queueCounts(q.id, q, d.rows, records)
        const blind = over[q.id] ?? q.blind
        return (
          <button key={q.id} type="button" className={cx('rv-queue-row', q.id === current && 'on')} onClick={() => onPick(q.id)} data-testid={`queue-row-${q.id}`}>
            <Icon name={QUEUE_ICON[q.icon]} size={15} />
            <span className="txt"><b>{q.title}</b><span className="mono muted">{q.subtitle}</span></span>
            <span className="cnt"><b>{q.source === 'model-verification' ? `${c.left} / ${q.total}` : fmtInt(c.left)}</b>{blind && <span className="rv-blind-badge">blind</span>}</span>
          </button>
        )
      })}
    </div>
  )
}

/* ================= queue rail, collapsed ================= */
const RAIL_CAP = 10   // P8: no more than ~10 thumbnails at once

function QueueRailCollapsed({ data, unit, left, onOpen }: { data: QueueData; unit: UnitRef | null; left: number; onOpen: () => void }) {
  const records = useRecords()
  const list = units(data)
  const cur = unit ? list.findIndex(u => unitKey(u) === unitKey(unit)) : -1
  const start = Math.max(0, cur - 2)
  const shown: UnitRef[] = []
  let thumbs = 0
  for (const u of list.slice(start)) {
    const n = u.kind === 'item' ? 1 : u.members.length
    if (thumbs + n > RAIL_CAP && shown.length) break
    shown.push(u); thumbs += n
  }
  const rest = list.length - start - shown.length
  const row = (id: string) => data.rows.find(r => r.id === id)!
  const Thumb = ({ r, current }: { r: QueueRow; current: boolean }) => {
    const rec = effective(records, r)
    return (
      <span className={cx('rv-thumb', current && 'current', rec && !current && 'judged')} title={`${r.id} · ${r.channel}${r.score != null ? ` · ${r.score.toFixed(2)}` : ''}${rec ? ` · ${rec.verdict.replace('_', ' ')}` : ''}`}>
        <MiniTrace values={r.thumb} yDomain={THUMB_Y} width={38} height={28} zeroLine={false} />
        {rec && <i className="dot" style={{ background: verdictColour(rec.verdict) }} />}
      </span>
    )
  }
  return (
    <>
      <IconButton icon="panel-left" label="open queue rail" bordered onClick={onOpen} testid="queue-rail-toggle" />
      <div className="rv-left-count" data-testid="left-count"><b>{fmtInt(left)}</b><span>left</span></div>
      <div className="rv-thumbs">
        {shown.map(u => u.kind === 'item'
          ? <button key={u.id} type="button" className="rv-thumb-btn" onClick={() => navigate(unitHash(data.queue.id, u))} aria-label={`open ${u.id}`} data-testid={`rail-thumb-${u.id}`}><Thumb r={row(u.id)} current={unit?.kind === 'item' && unit.id === u.id} /></button>
          : <button key={u.no} type="button" className="rv-thumb-cluster" onClick={() => navigate(unitHash(data.queue.id, u))} aria-label={`open cluster ${u.no}`} title={`Cluster ${u.no} · ${u.members.length} members`} data-testid={`rail-cluster-${u.no}`}>
              {u.members.map((id, i) => <Thumb key={id} r={row(id)} current={unit?.kind === 'cluster' && unit.no === u.no && i === 0} />)}
            </button>)}
        {rest > 0 && <span className="rv-thumb-more mono" title={`${rest} more units materialised; ${fmtInt(left)} left in the queue`}>+{fmtInt(Math.max(rest, left - thumbs))}</span>}
      </div>
    </>
  )
}

/* ================= queue rail, open (frame 3) ================= */
const GROUP_INFO = 'A sequence is detections from one run and channel within 6 min, at least 2 events; a family set is seed-search matches or members thought to be one family (Settings › Review queues).'

function QueueRailOpen({ data, unit, blind, left, onClose }: { data: QueueData; unit: UnitRef | null; blind: boolean; left: number; onClose: () => void }) {
  const { queue } = data
  const records = useRecords()
  const [f, setF] = useFilters(queue.id, queue.channels, queue.scoreFloor)
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({})
  const [newQ, setNewQ] = useState(false)
  const newRef = useRef<HTMLButtonElement>(null)
  const [shake, setShake] = useState<string | null>(null)
  const isDistance = queue.rankKind === 'distance'
  const hasScore = queue.unit === 'detection'
  const value = (r: QueueRow) => isDistance ? r.d ?? 0 : r.score ?? 0

  const list = units(data, f.group === 'none' ? 'none' : 'sequence')
  const curIdx = unit ? list.findIndex(u => unitKey(u) === unitKey(unit) || (unit.kind === 'cluster' && u.kind === 'item' && unit.members[0] === u.id)) : -1
  const rowOk = (r: QueueRow) => f.channels.includes(r.channel) && (!hasScore || (value(r) >= f.score[0] - 1e-9 && value(r) <= f.score[1] + 1e-9)) && (f.method === 'all' || f.method === 'matrix profile')
  const visible = useMemo(() => list.filter((u, i) => {
    const ids = u.kind === 'item' ? [u.id] : u.members
    const rows = ids.map(id => data.rows.find(r => r.id === id)!)
    if (!rows.some(rowOk)) return false
    const j = isJudged(data, records, u)
    if (f.status === 'unjudged') return !j || i === curIdx - 1 || i === curIdx
    if (f.status === 'judged') return j
    return true
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [list, records, f, curIdx])
  const byFamily = f.group === 'family'
  const paged = usePagedList(visible, 10)
  const sortLabel = queue.order
  const unitRows = (u: UnitRef) => (u.kind === 'item' ? [u.id] : u.members).map(id => data.rows.find(r => r.id === id)!)

  const RowBtn = ({ r, inCluster }: { r: QueueRow; inCluster?: boolean }) => {
    const rec = effective(records, r)
    const current = unit?.kind === 'item' && unit.id === r.id
    return (
      <button type="button" className={cx('rv-next-row', current && 'on', rec && !current && 'judged', inCluster && 'member')} onClick={() => navigate(`review/queue/${queue.id}/${r.id}`)} data-testid={`next-row-${r.id}`}>
        <MiniTrace values={r.thumb} yDomain={THUMB_Y} width={44} height={24} zeroLine={false} />
        <b className="mono">{r.id}</b><span className="mono muted">{r.channel}</span><span className="grow" />
        {hasScore && (blind ? <span className="mono muted" title="hidden in a blind queue"><Icon name="eye-off" size={12} /></span> : <span className="mono">{isDistance ? `d ${value(r).toFixed(2)}` : value(r).toFixed(2)}</span>)}
        {rec && <i className="dot" style={{ background: verdictColour(rec.verdict) }} title={rec.verdict} />}
      </button>
    )
  }

  return (
    <div className="rv-rail-scroll">
      <div className="rv-rail-head">
        <IconButton icon="panel-left" label="close queue rail" bordered onClick={onClose} testid="queue-rail-toggle" />
        <h4>Queues</h4><span className="grow" />
        <Button ref={newRef} variant="link" icon="plus" onClick={() => setNewQ(o => !o)} testid="new-queue">New queue</Button>
        <Popover open={newQ} onClose={() => setNewQ(false)} anchorRef={newRef} placement="bottom-end" title="Queues are made where the items come from" width={340} className="rv-pop" testid="new-queue-popover">
          <div className="rv-links">
            <Button variant="link" iconRight="arrow-right" onClick={() => navigate('discovery/runs')}>Discovery › Send N unjudged to Review</Button>
            <Button variant="link" iconRight="arrow-right" onClick={() => navigate('explore/corpus')}>Explore › Take span for Review</Button>
            <Button variant="link" iconRight="arrow-right" onClick={() => navigate('analyse/training')}>Analyse training › Send unseen windows</Button>
            <Button variant="link" iconRight="arrow-right" onClick={() => navigate('models/registry')}>Models › Registry verification sample</Button>
            <Button variant="link" icon="lock" disabled disabledReason="M4_aug is held out (D6): locked for the final evaluation, it cannot be queued for Review">M4_aug · held out</Button>
          </div>
        </Popover>
      </div>
      <QueueList current={queue.id} onPick={id => navigate(`review/queue/${id}?rail=queue`)} />

      <div className="rv-filters" data-testid="queue-filters">
        <div className="rv-sub-head"><h4>Filters</h4><span className="mono muted sm">{queue.title}</span><span className="grow" /><Button variant="link" onClick={() => setF(null)} testid="filters-reset">Reset</Button></div>
        <div className="rv-two">
          <label><span className="lbl">run</span>
            {queue.runId ? <SelectField value={queue.runId} onChange={() => {}} options={[{ value: queue.runId, label: `${queue.runId} ${queue.template ?? `seed search ${queue.exemplar}`}` }]} testid="filter-run" />
              : <SelectField value="none" onChange={() => {}} disabled disabledReason={`${queue.title} has no run: its items were not produced by one`} options={[{ value: 'none', label: 'no run' }]} testid="filter-run" />}
          </label>
          <label><span className="lbl">method</span>
            <SelectField value={f.method} onChange={v => setF({ method: v })} options={[{ value: 'all', label: 'all methods' }, { value: 'matrix profile', label: 'matrix profile' }, { value: 'threshold', label: 'threshold' }]} testid="filter-method" />
          </label>
        </div>
        <div className="rv-frow"><span className="lbl">channel</span>
          {queue.channels.map(ch => {
            const on = f.channels.includes(ch)
            const last = on && f.channels.length === 1
            return (
              <button key={ch} type="button" className={cx('rv-ch', on && 'on', shake === ch && 'shake')} aria-pressed={on} title={last ? 'at least one channel' : undefined} data-testid={`filter-ch-${ch}`}
                onClick={() => { if (last) { setShake(ch); window.setTimeout(() => setShake(null), 400); return } setF({ channels: on ? f.channels.filter(c => c !== ch) : [...f.channels, ch] }) }}>{ch}</button>
            )
          })}
          {shake && <span className="mono sm rv-amber">at least one channel</span>}
        </div>
        <div className="rv-frow col">
          <div className="row between"><span className="lbl">{isDistance ? 'distance' : 'score'}</span></div>
          {hasScore && !blind
            ? <RangeSlider value={f.score} onChange={v => setF({ score: [+v[0].toFixed(2), +Math.max(v[1], v[0] + 0.01).toFixed(2)] })} min={0} max={1} step={0.01} format={v => v.toFixed(2)} ariaLabel={isDistance ? 'distance' : 'score'} testid="filter-score" />
            : <DisabledReason block reason={blind ? `${isDistance ? 'distance' : 'score'} is hidden in a blind queue` : 'human spans and windows have no score'}>
                <div className="rv-range-off"><RangeSlider value={[0, 1]} onChange={() => {}} min={0} max={1} step={0.01} disabled format={v => v.toFixed(2)} testid="filter-score" /></div>
              </DisabledReason>}
        </div>
        <div className="rv-frow"><span className="lbl">status</span>
          <Seg size="sm" value={f.status} onChange={v => setF({ status: v })} options={[{ value: 'unjudged', label: 'unjudged' }, { value: 'judged', label: 'judged' }, { value: 'all', label: 'all' }]} testid="filter-status" />
        </div>
        <div className="rv-frow"><span className="lbl">group</span>
          <Seg size="sm" value={f.group} onChange={v => setF({ group: v })} testid="filter-group"
            options={[{ value: 'none', label: 'none' }, { value: 'sequence', label: 'sequence' }, { value: 'family', label: 'family', disabled: blind, reason: 'family affinity is hidden in a blind queue' }]} />
          <InfoTip title="Group">{GROUP_INFO}</InfoTip>
        </div>
      </div>

      <div className="rv-upnext" data-testid="up-next">
        <div className="rv-sub-head"><h4>Up next</h4><span className="mono muted sm">{sortLabel}</span><span className="grow" /><span className="mono muted sm">{fmtInt(left)} left</span></div>
        {visible.length === 0
          ? <EmptyState size="sm" icon="filter" title="No items match these filters" action={<Button size="sm" onClick={() => setF(null)} testid="filters-reset-empty">Reset filters</Button>} testid="up-next-empty" />
          : <>
              {(() => {
                let lastFam = ''
                return paged.items.map(u => {
                  const rows = unitRows(u)
                  const famHead = byFamily && rows[0].family !== lastFam ? (lastFam = rows[0].family) : null
                  const head = famHead && <div key={`fam-${famHead}-${unitKey(u)}`} className="rv-fam-head mono"><i className="dot" style={{ background: 'var(--muted-2)' }} />nearest {famHead}</div>
                  if (u.kind === 'item') return <div key={u.id}>{head}<RowBtn r={rows[0]} /></div>
                  const c = data.clusters.find(x => x.no === u.no)
                  const open = !collapsed[u.no]
                  const chans = [...new Set(rows.map(r => r.channel))].join(', ')
                  return (
                    <div key={`c${u.no}`}>{head}
                      <div className={cx('rv-cluster-head', unit?.kind === 'cluster' && unit.no === u.no && 'on')} data-testid={`next-cluster-${u.no}`}>
                        <button type="button" className="chev" aria-expanded={open} aria-label={open ? 'collapse cluster' : 'expand cluster'} onClick={() => setCollapsed(p => ({ ...p, [u.no]: open }))}><Icon name={open ? 'chevron-down' : 'chevron-right'} size={13} /></button>
                        <button type="button" className="lbl" onClick={() => navigate(unitHash(queue.id, u))}><b>Cluster {u.no}</b> <span className="mono">{c?.kind === 'sequence' ? `sequence · ${rows.length} within 6 min · ${chans}` : `${c?.badge ?? 'family set'} · ${rows.length} · ${chans}`}</span></button>
                      </div>
                      {open && rows.map(r => <RowBtn key={r.id} r={r} inCluster />)}
                    </div>
                  )
                })
              })()}
              {paged.pageCount > 1 && <div className="rv-pager"><Pager page={paged.page} pageCount={paged.pageCount} onPage={paged.setPage} format="range" total={paged.total} pageSize={10} testid="up-next-pager" /></div>}
              {data.queue.total > data.rows.length && <div className="mono muted sm rv-more">… {fmtInt(Math.max(0, left - visible.length))} more in the queue, not in the demo fixture</div>}
            </>}
      </div>
    </div>
  )
}
