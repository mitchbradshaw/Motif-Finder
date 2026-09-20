/* Settings › Channels & events (frame settings-02 · spec §9.2).
 * Per-channel metadata and the timed-event log. Excluded spans are skipped by every new run.
 *
 * Everything on this page is a DRAFT: gains, noise-floor overrides, channel status, event effects and
 * whole event rows (added and staged for removal) all live in the settings store, so the save bar
 * counts them, the consequence sentence says what each one does, and Discard puts every one of them
 * back (fix round 1: an added row used to live outside the draft and survived Discard). */
import { useEffect, useRef, useState } from 'react'
import {
  BandStrip, Badge, Button, Callout, Chip, EmptyState, Icon, IconButton, InfoTip, Popover, SectionCard, Seg,
  SelectField, Table, TextField, useQueryState, useDemoState, recordDemoWrite,
} from '../kit'
import { useSourced } from '../api/seam'
import {
  badFromHours, effectKey, getChannels, eventEffectSentence, eventsAddedKey, eventsRemovedKey, floorKey, gainKey, spanLabel,
  statusKey, type EventEffect, type TimedEvent,
} from '../api/settings'
import { LoadFailed, Loading, SettingsShell } from './chrome'
import { useSettingsPage, type SettingsPageStore } from './store'

const RECS = [
  { value: 'M2_aug_fs1', label: 'M2_aug fs1' }, { value: 'M2_aug_fs2', label: 'M2_aug fs2' }, { value: 'M3_jul', label: 'M3_jul' },
  { value: 'L_LM_Jul26_J', label: 'L_LM_Jul26_J' }, { value: 'M4_aug', label: 'M4_aug' },
]
const GAIN_ERROR = 'Gain must be a positive number'
const FLOOR_ERROR = 'Enter a floor between 0.01 and 5 mV'

export function ChannelsEventsPage() {
  const [rec, setRec] = useQueryState('rec', 'M2_aug_fs1')
  const rd = useSourced(() => getChannels(rec), [rec])
  const seg = <Seg label="recording" options={RECS} value={rec} onChange={setRec} testid="rec-seg" />
  return (
    <SettingsShell slug="channels-events" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {/* the picker has to survive a failed read, or an unknown ?rec is a dead end */}
      {rd.error && <><div style={{ display: 'flex', justifyContent: 'flex-end' }}>{seg}</div>
        <LoadFailed what={`channels of ${rec}`} error={rd.error} onRetry={rd.reload} /></>}
      {rd.data && <Body rec={rec} data={rd.data} seg={seg} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getChannels>>['data']

function Body({ rec, data, seg }: { rec: string; data: Data; seg: React.ReactNode }) {
  const s = useSettingsPage('channels-events')
  const [rows, setRows] = useQueryState('rows', '')
  const [modal, setModal] = useQueryState('modal', '')
  const [view, setView] = useQueryState('view', 'events')
  const [sel, setSel] = useQueryState('event', '')
  /* every popover on this page is a URL state (?pop=status:CH7_B2 | spans:CH2_A1 | kind), so each one is
     reachable by click AND by query parameter, and no two of them can be open at once */
  const [pop, setPop] = useQueryState('pop', '')
  const [extraKinds, setExtraKinds] = useDemoState<{ name: string; colour: string }[]>('settings.eventKinds', () => [])
  const locked = rec === 'M4_aug'
  const lockReason = locked ? 'held out · locked' : undefined
  const all = rows === 'all'
  const channels = all ? data.channels : data.channels.slice(0, 8)
  const kinds = [...data.kinds, ...extraKinds]

  /* ---- staged event rows: added and removed both live in the draft (one key each) */
  const addedKey = eventsAddedKey(rec), removedKey = eventsRemovedKey(rec)
  const added = (s.value(addedKey) as TimedEvent[] | undefined) ?? []
  const removed = (s.value(removedKey) as string[] | undefined) ?? []
  const setAdded = (f: (x: TimedEvent[]) => TimedEvent[]) => s.set(addedKey, f(added))
  const isAdded = (e: TimedEvent) => added.some(a => a.id === e.id)
  const isRemoved = (e: TimedEvent) => removed.includes(e.id)
  const events = [...data.events, ...added].sort((a, b) => a.t0_h - b.t0_h)
  const effectOf = (e: TimedEvent): EventEffect => (isAdded(e) ? e.effect : (s.value(effectKey(e.id)) as EventEffect | undefined) ?? e.effect)
  const setEffect = (e: TimedEvent, v: EventEffect) => {
    if (isAdded(e)) setAdded(list => list.map(x => (x.id === e.id ? { ...x, effect: v } : x)))
    else s.set(effectKey(e.id), v)
    /* "exclude · mark channel bad" is the same fact as the channel's status cell (fog F8: the event
       is the source of truth), so it stages the status too */
    if (v === 'exclude · mark channel bad' && e.channels !== 'all') s.set(statusKey(rec, e.channels), String(e.t0_h))
  }
  const removeEvent = (e: TimedEvent) => {
    if (isAdded(e)) setAdded(list => list.filter(x => x.id !== e.id))
    else s.set(removedKey, [...removed, e.id])
  }
  const keepEvent = (e: TimedEvent) => s.set(removedKey, removed.filter(x => x !== e.id))

  const live = events.filter(e => !isRemoved(e))
  const excluding = (e: TimedEvent) => effectOf(e) !== 'show on plots'
  const spansFor = (ch: string) => live.filter(e => excluding(e) && (e.channels === 'all' || e.channels === ch))
  const spansText = (ch: string) => {
    const l = spansFor(ch)
    if (!l.length) return 'none'
    const own = l.filter(e => e.channels !== 'all')
    return `${l.length} · ${own.length ? `${own.map(spanLabel).join(' + ')} + all` : 'all channels'}`
  }

  /* ---- the timeline. The recording is 721 h and the events sit in its first 50, so at full scale the
     four markers are hairlines and a "→ end" exclusion paints the whole strip (fix round 1). Default to
     the window that holds every event, with the whole recording one click (or ?view=all) away. */
  const lastEventEnd = live.reduce((m, e) => Math.max(m, e.open_end ? e.t0_h + 2 : e.t1_h ?? e.t0_h), 0)
  const windowEnd = Math.min(data.duration_h, Math.max(10, Math.ceil((lastEventEnd * 1.15) / 10) * 10))
  const zoomable = live.length > 0 && windowEnd < data.duration_h
  const t1 = zoomable && view !== 'all' ? windowEnd : data.duration_h
  const tick = Math.max(0.15, t1 / 150)
  const segments = live.map(e => {
    const effect = effectOf(e)
    const colour = kinds.find(k => k.name === e.kind)?.colour ?? '#9CA3AF'
    const span = e.open_end || e.t1_h != null
    /* a short span still has to be visible: never thinner than a point marker */
    const end = Math.max(e.open_end ? data.duration_h : e.t1_h ?? e.t0_h, e.t0_h + tick)
    return {
      start: e.t0_h * 3600,
      end: Math.min(end, t1) * 3600,
      colour: span && effect !== 'show on plots' ? `${colour}66` : colour,
      label: `${spanLabel(e)} · ${e.kind} · ${e.channels} · ${effect}`,
    }
  })

  return (
    <>
      {locked && <Callout tone="amber" icon="lock" testid="rec-locked">M4_aug is held out · locked — channels and events are read-only (D6).</Callout>}

      <SectionCard title="Channels" subtitle={`${data.label} · ${data.channels.length} channels`} testid="channels-card" actions={seg}
        footer={
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {data.channels.length > 8 && (
              <Button variant="link" size="sm" icon={all ? 'chevron-up' : 'chevron-down'} testid="more-channels"
                onClick={() => setRows(all ? '' : 'all')}>{all ? `show 8 channels` : `${data.channels.length - 8} more channels`}</Button>
            )}
            <span className="k-spacer" />
            <span className="s-note">shared-ground pairs drive the Library's double-count warning
              <InfoTip>Channels on one ground see the same events; the Library warns before counting them twice.</InfoTip></span>
          </div>
        }>
        <Table rows={channels} rowKey={c => c.ch} testid="channels-table" dense
          columns={[
            { key: 'ch', header: 'ch', width: '10%', render: c => <span className="mono" style={{ fontWeight: 600 }}>{c.ch}</span> },
            { key: 'name', header: 'name', width: '11%' },
            { key: 'electrode', header: 'electrode · position', width: '15%', render: c => <span className="muted small">{c.electrode}</span> },
            {
              key: 'gain', header: 'gain', width: '14%', render: c => (
                <span className={s.dirty(gainKey(rec, c.ch)) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                  <NumberCell value={s.value(gainKey(rec, c.ch)) ?? c.gain} min={0.01} max={100} unit="mV / u" width={124}
                    error={GAIN_ERROR} disabled={locked} disabledReason={lockReason} testid={`gain-${c.ch}`}
                    onCommit={v => s.set(gainKey(rec, c.ch), v)} onReason={r => s.markInvalid(gainKey(rec, c.ch), r)} />
                </span>
              ),
            },
            {
              key: 'ground', header: 'shared ground', width: '11%', render: c => c.shared_ground
                ? <Chip tone="amber" icon="link" testid={`ground-${c.ch}`}>{c.shared_ground}</Chip>
                : <span className="muted">—</span>,
            },
            {
              key: 'status', header: 'status', width: '13%', render: c => (
                <StatusCell rec={rec} ch={c.ch} store={s} duration={data.duration_h} fallback={badFromHours(c.status)}
                  locked={locked} lockReason={lockReason}
                  open={pop === `status:${c.ch}`} onOpen={o => setPop(o ? `status:${c.ch}` : '')}
                  onBadFrom={t => setAdded(list => [
                    ...list.filter(x => x.id !== `e-bad-${c.ch}`),
                    {
                      id: `e-bad-${c.ch}`, recording: rec, t0_h: t, t1_h: null, open_end: true, kind: 'electrode',
                      channels: c.ch, effect: 'exclude · mark channel bad', note: `${c.ch} marked bad from the status cell`, added: '16 Sep',
                    },
                  ])}
                  onOk={() => {
                    /* the event is the record (fog F8): reading the channel ok again has to drop the
                       event that marked it bad, or the cell and the log would disagree */
                    setAdded(list => list.filter(x => x.id !== `e-bad-${c.ch}`))
                    const marked = data.events.filter(e => e.channels === c.ch && effectOf(e) === 'exclude · mark channel bad' && !isRemoved(e))
                    if (marked.length) s.set(removedKey, [...removed, ...marked.map(e => e.id)])
                  }} />
              ),
            },
            {
              key: 'spans', header: 'excluded spans', width: '16%', render: c => (
                <SpansCell ch={c.ch} text={spansText(c.ch)} spans={spansFor(c.ch)} kinds={kinds}
                  open={pop === `spans:${c.ch}`} onOpen={o => setPop(o ? `spans:${c.ch}` : '')}
                  onGo={id => { setSel(id); setPop('') }} />
              ),
            },
            {
              key: 'floor', header: 'noise floor', width: '10%', render: c => (
                <span className={s.dirty(floorKey(rec, c.ch)) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                  <NumberCell value={s.value(floorKey(rec, c.ch)) ?? ''} min={0.01} max={5} unit="mV" width={96} allowEmpty
                    placeholder="recording" error={FLOOR_ERROR} disabled={locked} disabledReason={lockReason} testid={`floor-${c.ch}`}
                    onCommit={v => s.set(floorKey(rec, c.ch), v)} onReason={r => s.markInvalid(floorKey(rec, c.ch), r)} />
                </span>
              ),
            },
          ]} />
      </SectionCard>

      <SectionCard title="Event log" subtitle={`${data.label} · ${live.length} events`} testid="events-card"
        actions={<Button icon="plus" testid="add-event" disabled={locked} disabledReason={lockReason}
          onClick={() => setModal(modal === 'add-event' ? '' : 'add-event')}>Add event</Button>}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
          <span className="s-note mono" data-testid="timeline-window">
            {zoomable && view !== 'all' ? `0 – ${windowEnd} h of ${data.duration_h} h · all ${live.length} events` : `0 – ${data.duration_h} h · whole recording`}
          </span>
          {zoomable && (
            <Seg size="sm" testid="timeline-view" value={view === 'all' ? 'all' : 'events'} onChange={setView}
              options={[{ value: 'events', label: `0 – ${windowEnd} h` }, { value: 'all', label: 'whole recording' }]} />
          )}
          <span className="k-spacer" />
          <span className="s-timeline-caption">shaded = excluded from analysis</span>
        </div>
        <BandStrip domain={[0, t1 * 3600]} timeUnit="h" testid="event-timeline"
          rows={[{ label: data.label, segments: segments.length ? segments : [{ start: 0, end: 0, colour: '#fff', label: 'no events' }] }]} />

        {modal === 'add-event' && <AddEventRow rec={rec} kinds={kinds} duration={data.duration_h}
          onCancel={() => setModal('')}
          onAdd={e => { setAdded(x => [...x, e]); setModal(''); recordDemoWrite('settings', 'add-event', { rec, id: e.id }) }} />}

        {events.length ? (
          <Table rows={events} rowKey={e => e.id} testid="events-table" highlighted={sel || null} onRowClick={e => setSel(e.id)} dense
            rowTone={e => (isRemoved(e) ? 'dim' : isAdded(e) ? 'amber' : undefined)}
            columns={[
              {
                key: 'time', header: 'time', width: '16%', render: e => (
                  <span className="mono" style={isRemoved(e) ? { textDecoration: 'line-through' } : undefined}>{spanLabel(e)}</span>
                ),
              },
              { key: 'kind', header: 'kind', width: '13%', render: e => <><span className="s-swatch" style={{ background: kinds.find(k => k.name === e.kind)?.colour }} /> {e.kind}</> },
              { key: 'channels', header: 'channels', width: '11%', render: e => <span className="mono small">{e.channels}</span> },
              {
                key: 'effect', header: 'effect', width: '21%', render: e => (
                  <span className={s.dirty(effectKey(e.id)) || isAdded(e) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                    <SelectField value={effectOf(e)} onChange={v => setEffect(e, v as EventEffect)}
                      options={data.effects.map(x => ({ value: x, label: x }))} size="sm" width={186}
                      disabled={locked || isRemoved(e)}
                      disabledReason={locked ? lockReason : isRemoved(e) ? 'staged for removal · undo to edit it' : undefined}
                      testid={`effect-${e.id}`} />
                  </span>
                ),
              },
              { key: 'note', header: 'note', width: '25%', render: e => <span className="small">{e.note}</span> },
              { key: 'added', header: 'added', width: '8%', render: e => <span className="muted small">{e.added}</span> },
              {
                key: 'remove', header: '', width: '6%', render: e => locked
                  ? <IconButton icon="x" label="remove event" disabled disabledReason={lockReason} testid={`remove-${e.id}`} />
                  : isRemoved(e)
                    ? <IconButton icon="undo" label={`keep ${spanLabel(e)}`} testid={`undo-${e.id}`} onClick={() => keepEvent(e)} />
                    : <IconButton icon="x" label={`remove ${spanLabel(e)}`} testid={`remove-${e.id}`} onClick={() => removeEvent(e)} />,
              },
            ]} />
        ) : <EmptyState size="sm" title={`No events on ${data.label}`} caption="Add event records a watering, a door opening, a detached electrode" testid="events-empty" />}

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
          <span className="s-label mono">kinds</span>
          {kinds.map(k => <Chip key={k.name} tone="outline" dot={k.colour}>{k.name}</Chip>)}
          <AddKind onAdd={k => setExtraKinds(x => [...x, k])} existing={kinds.map(k => k.name)}
            open={pop === 'kind'} onOpen={o => setPop(o ? 'kind' : '')} />
        </div>
      </SectionCard>
    </>
  )
}

/* ------------------------------------------------------------------ cells */

/** A numeric cell that keeps its decimals ("1.00"), states one rule when it is broken, and never
 *  commits a value outside it — the kit's NumberField has neither a placeholder nor fixed decimals
 *  (see webui/pages/requests/settings.md). */
function NumberCell({ value, dp = 2, unit, placeholder, allowEmpty, min, max, error, width, disabled, disabledReason, testid, onCommit, onReason }: {
  value: unknown; dp?: number; unit?: string; placeholder?: string; allowEmpty?: boolean
  min: number; max: number; error: string; width?: number; disabled?: boolean; disabledReason?: string; testid: string
  onCommit: (v: number | '') => void; onReason: (reason: string | null) => void
}) {
  const [raw, setRaw] = useState<string | null>(null)
  const reasonRef = useRef(onReason)
  reasonRef.current = onReason
  useEffect(() => () => reasonRef.current(null), [])
  const shown = raw ?? (value === '' || value == null ? '' : Number(value).toFixed(dp))
  const reasonOf = (t: string): string | null => {
    const v = t.trim()
    if (!v) return allowEmpty ? null : error
    if (!/^\d*\.?\d+$/.test(v)) return error
    const n = Number(v)
    return n < min || n > max ? error : null
  }
  const reason = disabled ? null : reasonOf(shown)
  return (
    <span style={{ display: 'inline-flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
      <TextField value={shown} size="sm" width={width} suffix={unit} placeholder={placeholder} invalid={!!reason}
        disabled={disabled} disabledReason={disabledReason} testid={testid}
        onChange={v => {
          setRaw(v)
          const r = reasonOf(v)
          onReason(r)
          if (!r) onCommit(v.trim() === '' ? '' : Number(v.trim()))
        }} />
      {reason && <span className="k-field-error" role="alert" data-testid={`${testid}-error`}><Icon name="alert-circle" size={11} />{reason}</span>}
    </span>
  )
}

/** status Badge → Popover: ok / bad from t. Setting "bad from" stages the linked electrode event too. */
function StatusCell({ rec, ch, store, duration, fallback, locked, lockReason, open, onOpen, onBadFrom, onOk }: {
  rec: string; ch: string; store: SettingsPageStore; duration: number; fallback: string
  locked: boolean; lockReason?: string; open: boolean; onOpen: (open: boolean) => void
  onBadFrom: (t: number) => void; onOk: () => void
}) {
  const ref = useRef<HTMLButtonElement>(null)
  const setOpen = (v: boolean | ((o: boolean) => boolean)) => onOpen(typeof v === 'function' ? v(open) : v)
  const cur = String(store.value(statusKey(rec, ch)) ?? fallback)
  const bad = cur !== ''
  const [draft, setDraft] = useState<string>(cur || '')
  const [mode, setMode] = useState<'ok' | 'bad'>(bad ? 'bad' : 'ok')
  const t = Number(draft)
  const badReason = !draft.trim() ? 'enter the hour it goes bad from'
    : !/^\d*\.?\d+$/.test(draft.trim()) || t < 0 || t > duration ? `Time must be inside 0–${duration} h` : null
  return (
    <>
      <button type="button" ref={ref} className="s-cell-btn" data-testid={`status-${ch}`} disabled={locked}
        title={locked ? lockReason : `${ch} status · click to change`}
        onClick={() => { setMode(bad ? 'bad' : 'ok'); setDraft(cur || ''); setOpen(o => !o) }}>
        <Badge tone={bad ? 'red' : 'green'}>{bad ? `bad from ${cur} h` : 'ok'}</Badge>
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} title={`${ch} status`} width={280} testid={`status-popover-${ch}`}>
        <Seg size="sm" testid={`status-seg-${ch}`} value={mode} options={[{ value: 'ok', label: 'ok' }, { value: 'bad', label: 'bad from' }]}
          onChange={v => {
            setMode(v as 'ok' | 'bad')
            if (v === 'ok') { store.set(statusKey(rec, ch), ''); onOk(); setOpen(false) }
          }} />
        {mode === 'bad' && (
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <TextField value={draft} onChange={setDraft} size="sm" width={120} suffix="h" placeholder="40.1" invalid={!!badReason} testid={`status-time-${ch}`} />
            {badReason && <span className="k-field-error" role="alert"><Icon name="alert-circle" size={11} />{badReason}</span>}
            <span className="s-note">a linked <b>electrode</b> event is staged with it — the event is the record, this cell reads it back</span>
            <Button size="sm" variant="primary" block disabled={!!badReason} disabledReason={badReason ?? undefined} testid={`status-apply-${ch}`}
              onClick={() => { store.set(statusKey(rec, ch), String(t)); onBadFrom(t); setOpen(false) }}>Set bad from {draft.trim() || '—'} h</Button>
          </div>
        )}
      </Popover>
    </>
  )
}

/** excluded-spans cell → Popover listing the spans that touch this channel, each a link to its row. */
function SpansCell({ ch, text, spans, kinds, open, onOpen, onGo }: {
  ch: string; text: string; spans: TimedEvent[]; kinds: { name: string; colour: string }[]
  open: boolean; onOpen: (open: boolean) => void; onGo: (id: string) => void
}) {
  const ref = useRef<HTMLButtonElement>(null)
  const setOpen = (v: boolean | ((o: boolean) => boolean)) => onOpen(typeof v === 'function' ? v(open) : v)
  return (
    <>
      <button type="button" ref={ref} className="s-cell-btn small" data-testid={`spans-${ch}`}
        title={spans.length ? `${ch} · the spans new runs skip` : `${ch} · nothing excluded`}
        onClick={() => setOpen(o => !o)}>{text}</button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} title={`${ch} · excluded spans`} width={320} testid={`spans-popover-${ch}`}>
        {spans.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {spans.map(e => (
              <Button key={e.id} variant="link" size="sm" testid={`span-go-${ch}-${e.id}`} onClick={() => { onGo(e.id); setOpen(false) }}>
                <span className="s-swatch" style={{ background: kinds.find(k => k.name === e.kind)?.colour }} />
                {spanLabel(e)} · {e.kind} · {e.channels === 'all' ? 'all channels' : e.channels}
              </Button>
            ))}
            <span className="s-note">new runs skip these spans on {ch}</span>
          </div>
        ) : <span className="s-note">no event excludes anything on {ch}</span>}
      </Popover>
    </>
  )
}

/* ------------------------------------------------------------------ editors */

function AddKind({ onAdd, existing, open, onOpen }: {
  onAdd: (k: { name: string; colour: string }) => void; existing: string[]
  open: boolean; onOpen: (open: boolean) => void
}) {
  const setOpen = (v: boolean | ((o: boolean) => boolean)) => onOpen(typeof v === 'function' ? v(open) : v)
  const [name, setName] = useState('')
  const [colour, setColour] = useState('#30B0C7')
  const ref = useRef<HTMLButtonElement>(null)
  /* lowercase, digits and hyphens: "co2-pulse" is the placeholder's own example (fix round 1) */
  const err = !name ? 'name the kind' : existing.includes(name.toLowerCase()) ? 'Kind already exists'
    : !/^[a-z][a-z0-9-]{1,19}$/.test(name) ? 'lowercase letters, digits and -, 2–20, starting with a letter' : null
  return (
    <>
      <button type="button" ref={ref} className="chip" onClick={() => setOpen(o => !o)} data-testid="add-kind">+ kind</button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} title="Add an event kind" width={280} testid="add-kind-popover">
        <TextField value={name} onChange={v => setName(v.toLowerCase())} block placeholder="e.g. co2-pulse" testid="kind-name" invalid={!!name && !!err} />
        <div style={{ display: 'flex', gap: 6, margin: '8px 0' }}>
          {['#30B0C7', '#A2845E', '#5856D6', '#E85AAD'].map(c => (
            <button key={c} type="button" className="s-swatch" style={{ background: c, outline: colour === c ? '2px solid var(--blue)' : undefined, width: 20, height: 20, cursor: 'pointer' }}
              aria-label={`colour ${c}`} onClick={() => setColour(c)} />
          ))}
        </div>
        <Button size="sm" variant="primary" block disabled={!!err} disabledReason={err ?? undefined} testid="kind-add"
          onClick={() => { onAdd({ name, colour }); setName(''); setOpen(false) }}>Add kind</Button>
      </Popover>
    </>
  )
}

function AddEventRow({ rec, kinds, duration, onAdd, onCancel }: {
  rec: string; kinds: { name: string; colour: string }[]; duration: number
  onAdd: (e: TimedEvent) => void; onCancel: () => void
}) {
  const [time, setTime] = useState('')
  const [kind, setKind] = useState(kinds[0].name)
  const [channels, setChannels] = useState('all')
  const [effect, setEffect] = useState<EventEffect>('show on plots')
  const [note, setNote] = useState('')
  const parsed = (() => {
    const m = time.trim().match(/^(\d+(?:\.\d+)?)\s*(?:h)?(?:\s*(?:–|-|to)\s*(\d+(?:\.\d+)?)\s*(?:h)?)?(\s*(?:→|->)\s*end)?$/i)
    if (!m) return null
    const t0 = Number(m[1]); const t1 = m[2] ? Number(m[2]) : null
    if (t0 < 0 || t0 > duration || (t1 != null && (t1 <= t0 || t1 > duration))) return null
    return { t0, t1, open: !!m[3] }
  })()
  const err = !time ? 'enter a time' : !parsed ? `Time must be inside 0–${duration} h` : !note ? 'a note is required' : note.length > 120 ? 'at most 120 characters' : null
  const draft: TimedEvent | null = parsed ? {
    id: `e-new-${Math.round(parsed.t0 * 10)}`, recording: rec, t0_h: parsed.t0, t1_h: parsed.t1, open_end: parsed.open,
    kind, channels, effect, note, added: '16 Sep',
  } : null
  return (
    <>
      <div className="s-inline-edit" data-testid="add-event-row">
        <TextField value={time} onChange={setTime} placeholder="12.5 h  ·  28.9 – 29.1 h  ·  40.1 h → end" width={230} invalid={!!time && !parsed} testid="event-time" />
        <SelectField value={kind} onChange={setKind} options={kinds.map(k => ({ value: k.name, label: k.name }))} width={130} testid="event-kind" />
        <TextField value={channels} onChange={setChannels} width={110} testid="event-channels" />
        <SelectField value={effect} onChange={v => setEffect(v as EventEffect)} width={190} testid="event-effect"
          options={['show on plots', 'exclude span', 'exclude · mark channel bad'].map(x => ({ value: x, label: x }))} />
        <TextField value={note} onChange={setNote} placeholder="what happened" width={240} testid="event-note" />
        <Button size="sm" onClick={onCancel}>Cancel</Button>
        <Button size="sm" variant="primary" disabled={!!err} disabledReason={err ?? undefined} testid="event-save"
          onClick={() => onAdd(draft!)}>Save row</Button>
      </div>
      {draft && <div className="s-note mono" data-testid="add-event-consequence" style={{ margin: '4px 0 0 10px' }}>
        {draft.effect === 'show on plots' ? `${spanLabel(draft)} · ${draft.kind} will be marked on plots · no run is marked stale` : eventEffectSentence(draft, draft.effect)}
      </div>}
    </>
  )
}
