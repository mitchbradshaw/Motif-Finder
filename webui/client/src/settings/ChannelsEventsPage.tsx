/* Settings › Channels & events (frame settings-02 · spec §9.2).
 * Per-channel metadata and the timed-event log. Excluded spans are skipped by every new run.
 *
 * Everything on this page is a DRAFT: gains, noise-floor overrides, channel status, event effects and
 * whole event rows (added and staged for removal) all live in the settings store, so the save bar
 * counts them, the consequence sentence says what each one does, and Discard puts every one of them
 * back (fix round 1: an added row used to live outside the draft and survived Discard). */
import { useEffect, useRef, useState } from 'react'
import {
  Badge, Button, Callout, Chip, EmptyState, Icon, IconButton, InfoTip, Popover, SectionCard, Seg,
  SelectField, Table, TextField, useQueryState, recordDemoWrite,
} from '../kit'
import { TimeAxis } from '../charts/primitives'
import { makeX } from '../charts/scale'
import { useSize } from '../charts/useSize'
import { useSourced } from '../api/seam'
import {
  EVENT_KINDS_KEY, effectKey, getChannels, eventEffectSentence, eventsAddedKey, eventsRemovedKey, floorKey, gainKey,
  groundKey, removedRefs, spanLabel, type EventEffect, type RemovedRef, type TimedEvent,
} from '../api/settings'
import { LoadFailed, Loading, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

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
  /* a new kind is a DRAFT like every other edit on this page (fix round 2: it used to commit on click) */
  const extraKinds = (s.value(EVENT_KINDS_KEY) as { name: string; colour: string }[] | undefined) ?? []
  const locked = rec === 'M4_aug'
  const lockReason = locked ? 'held out · locked' : undefined
  const all = rows === 'all'
  const channels = all ? data.channels : data.channels.slice(0, 8)
  const kinds = [...data.kinds, ...extraKinds]

  /* ---- staged event rows: added and removed both live in the draft (one key each) */
  const addedKey = eventsAddedKey(rec), removedKey = eventsRemovedKey(rec)
  const added = (s.value(addedKey) as TimedEvent[] | undefined) ?? []
  const removed: RemovedRef[] = removedRefs(s.value(removedKey))
  const setAdded = (f: (x: TimedEvent[]) => TimedEvent[]) => s.set(addedKey, f(added))
  const isAdded = (e: TimedEvent) => added.some(a => a.id === e.id)
  const isRemoved = (e: TimedEvent) => removed.some(r => r.id === e.id)
  const events = [...data.events, ...added].sort((a, b) => a.t0_h - b.t0_h)
  const effectOf = (e: TimedEvent): EventEffect => (isAdded(e) ? e.effect : (s.value(effectKey(e.id)) as EventEffect | undefined) ?? e.effect)
  const setEffect = (e: TimedEvent, v: EventEffect) => {
    if (isAdded(e)) setAdded(list => list.map(x => (x.id === e.id ? { ...x, effect: v } : x)))
    else s.set(effectKey(e.id), v)
    /* no status is written: the event IS the channel's status (fog F8) and the cell reads it back */
  }
  const removeEvent = (e: TimedEvent) => {
    if (isAdded(e)) setAdded(list => list.filter(x => x.id !== e.id))
    else s.set(removedKey, [...removed, { id: e.id, effect: effectOf(e) }])
  }
  const keepEvent = (e: TimedEvent) => s.set(removedKey, removed.filter(r => r.id !== e.id))

  const live = events.filter(e => !isRemoved(e))
  const excluding = (e: TimedEvent) => effectOf(e) !== 'show on plots'
  const spansFor = (ch: string) => live.filter(e => excluding(e) && (e.channels === 'all' || e.channels === ch))
  const spansText = (ch: string) => {
    const l = spansFor(ch)
    if (!l.length) return 'none'
    const own = l.filter(e => e.channels !== 'all')
    if (!own.length) return `${l.length} · all channels`
    /* "+ all" only when an all-channels span really is one of them (fix round 2) */
    return `${l.length} · ${own.map(spanLabel).join(' + ')}${own.length < l.length ? ' + all' : ''}`
  }

  /* ---- channel status is READ BACK from the mark-bad events (fog F8, fix round 2). There is no second
     store for it, so the badge and the event log can never disagree in either direction: an event set to
     "exclude · mark channel bad" makes its channels bad, and taking that effect off makes them ok again. */
  const marksBad = (ch: string) => live.filter(e => effectOf(e) === 'exclude · mark channel bad' && (e.channels === 'all' || e.channels === ch))
  const badFrom = (ch: string) => { const l = marksBad(ch); return l.length ? String(Math.min(...l.map(e => e.t0_h))) : '' }

  /* ---- shared ground: a Select in the cell, written on BOTH channels so the pair stays symmetric
     (and the channel that lost its partner is cleared with it). */
  const groundOf = (ch: string) => String(s.value(groundKey(rec, ch)) ?? '')
  const setGround = (ch: string, v: string) => {
    const prev = groundOf(ch)
    if (prev === v) return
    if (prev) s.set(groundKey(rec, prev), '')
    if (v) {
      const old = groundOf(v)
      if (old && old !== ch) s.set(groundKey(rec, old), '')
      s.set(groundKey(rec, v), ch)
    }
    s.set(groundKey(rec, ch), v) // last, so the save bar states THIS channel's consequence
  }

  /* ---- the timeline. The recording is 721 h and the events sit in its first 50, so at full scale the
     four markers are hairlines and a "→ end" exclusion paints the whole strip (fix round 1). Default to
     the window that holds every event, with the whole recording one click (or ?view=all) away. */
  const lastEventEnd = live.reduce((m, e) => Math.max(m, e.open_end ? e.t0_h + 2 : e.t1_h ?? e.t0_h), 0)
  const windowEnd = Math.min(data.duration_h, Math.max(10, Math.ceil((lastEventEnd * 1.15) / 10) * 10))
  const zoomable = live.length > 0 && windowEnd < data.duration_h
  const t1 = zoomable && view !== 'all' ? windowEnd : data.duration_h
  const marks = live.map(e => {
    const effect = effectOf(e)
    const colour = kinds.find(k => k.name === e.kind)?.colour ?? '#9CA3AF'
    const span = e.open_end || e.t1_h != null
    const end = e.open_end ? data.duration_h : e.t1_h ?? e.t0_h
    return {
      id: e.id, colour, excluded: effect !== 'show on plots',
      t0: e.t0_h * 3600, t1: span ? Math.min(end, t1) * 3600 : null,
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
              key: 'ground', header: 'shared ground', width: '11%', render: c => (
                <GroundCell ch={c.ch} value={groundOf(c.ch)} dirty={s.dirty(groundKey(rec, c.ch))}
                  options={data.channels.map(x => x.ch).filter(x => x !== c.ch)}
                  locked={locked} lockReason={lockReason}
                  open={pop === `ground:${c.ch}`} onOpen={o => setPop(o ? `ground:${c.ch}` : '')}
                  onSet={v => { setGround(c.ch, v); setPop('') }} />
              ),
            },
            {
              key: 'status', header: 'status', width: '13%', render: c => (
                <StatusCell ch={c.ch} badFrom={badFrom(c.ch)} sources={marksBad(c.ch)} duration={data.duration_h}
                  locked={locked} lockReason={lockReason} onGo={id => { setSel(id); setPop('') }}
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
                    if (marked.length) s.set(removedKey, [...removed, ...marked.map(e => ({ id: e.id, effect: effectOf(e) }))])
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
        <EventStrip label={data.label} domain={[0, t1 * 3600]} marks={marks} selected={sel}
          onSelect={id => setSel(sel === id ? '' : id)} />

        {modal === 'add-event' && <AddEventRow rec={rec} kinds={kinds} duration={data.duration_h}
          onCancel={() => setModal('')}
          onAdd={e => { setAdded(x => [...x, e]); setModal(''); recordDemoWrite('settings', 'add-event', { rec, id: e.id }) }} />}

        {events.length ? (
          <Table rows={events} rowKey={e => e.id} testid="events-table" highlighted={sel || null} onRowClick={e => setSel(e.id)} dense
            rowTone={e => (isRemoved(e) ? 'dim' : isAdded(e) ? 'amber' : undefined)}
            columns={[
              {
                key: 'time', header: 'time', width: '14%', render: e => (
                  <span className="mono" style={isRemoved(e) ? { textDecoration: 'line-through' } : undefined}>{spanLabel(e)}</span>
                ),
              },
              { key: 'kind', header: 'kind', width: '12%', render: e => <><span className="s-swatch" style={{ background: kinds.find(k => k.name === e.kind)?.colour }} /> {e.kind}</> },
              { key: 'channels', header: 'channels', width: '11%', render: e => <span className="mono small">{e.channels}</span> },
              {
                key: 'effect', header: 'effect', width: '25%', render: e => (
                  <span className={s.dirty(effectKey(e.id)) || isAdded(e) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                    <SelectField value={effectOf(e)} onChange={v => setEffect(e, v as EventEffect)}
                      options={data.effects.map(x => ({ value: x, label: x }))} size="sm" width={224}
                      disabled={locked || isRemoved(e)}
                      disabledReason={locked ? lockReason : isRemoved(e) ? 'staged for removal · undo to edit it' : undefined}
                      testid={`effect-${e.id}`} />
                  </span>
                ),
              },
              { key: 'note', header: 'note', width: '25%', render: e => <span className="small">{e.note}</span> },
              { key: 'added', header: 'added', width: '7%', render: e => <span className="muted small">{e.added}</span> },
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
          {kinds.map(k => <Chip key={k.name} tone={extraKinds.some(x => x.name === k.name) ? 'amber' : 'outline'} dot={k.colour}
            title={extraKinds.some(x => x.name === k.name) ? 'staged · nothing is written until you save' : undefined}>{k.name}</Chip>)}
          <AddKind onAdd={k => s.set(EVENT_KINDS_KEY, [...extraKinds, k])} existing={kinds.map(k => k.name)}
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

/** status Badge → Popover: ok / bad from t. The badge is READ BACK from the mark-bad events, so setting
 *  "bad from" stages the linked electrode event and nothing else, and "ok" drops the event that marked it. */
function StatusCell({ ch, badFrom, sources, duration, locked, lockReason, open, onOpen, onBadFrom, onOk, onGo }: {
  ch: string; badFrom: string; sources: TimedEvent[]; duration: number
  locked: boolean; lockReason?: string; open: boolean; onOpen: (open: boolean) => void
  onBadFrom: (t: number) => void; onOk: () => void; onGo: (id: string) => void
}) {
  const ref = useRef<HTMLButtonElement>(null)
  const setOpen = (v: boolean | ((o: boolean) => boolean)) => onOpen(typeof v === 'function' ? v(open) : v)
  const cur = badFrom
  const bad = cur !== ''
  /* one channel cannot be read ok while an all-channels event marks it bad — that fact lives on the event */
  const blocking = sources.find(e => e.channels === 'all')
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
        <Seg size="sm" testid={`status-seg-${ch}`} value={mode} onChange={v => {
          if (v === 'ok' && blocking) return
          setMode(v as 'ok' | 'bad')
          if (v === 'ok') { onOk(); setOpen(false) }
        }}
          options={[
            { value: 'ok', label: 'ok', disabled: !!blocking, reason: blocking ? `the ${spanLabel(blocking)} event marks all channels bad · change its effect in the event log` : undefined },
            { value: 'bad', label: 'bad from' },
          ]} />
        {sources.length > 0 && (
          <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span className="s-note">read back from</span>
            {sources.map(e => (
              <Button key={e.id} variant="link" size="sm" testid={`status-go-${ch}-${e.id}`} onClick={() => { onGo(e.id); setOpen(false) }}>
                {spanLabel(e)} · {e.kind} · {e.channels === 'all' ? 'all channels' : e.channels}
              </Button>
            ))}
          </div>
        )}
        {mode === 'bad' && (
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <TextField value={draft} onChange={setDraft} size="sm" width={120} suffix="h" placeholder="40.1" invalid={!!badReason} testid={`status-time-${ch}`} />
            {badReason && <span className="k-field-error" role="alert"><Icon name="alert-circle" size={11} />{badReason}</span>}
            <span className="s-note">a linked <b>electrode</b> event is staged with it — the event is the record, this cell reads it back</span>
            <Button size="sm" variant="primary" block disabled={!!badReason} disabledReason={badReason ?? undefined} testid={`status-apply-${ch}`}
              onClick={() => { onBadFrom(t); setOpen(false) }}>Set bad from {draft.trim() || '—'} h</Button>
          </div>
        )}
      </Popover>
    </>
  )
}

/** shared-ground cell: the amber Chip (or the dash) IS the control — click it and it becomes a Select of
 *  the other channels of this recording. The write is symmetric (see setGround): both cells move together. */
function GroundCell({ ch, value, options, dirty, locked, lockReason, open, onOpen, onSet }: {
  ch: string; value: string; options: string[]; dirty: boolean
  locked: boolean; lockReason?: string; open: boolean; onOpen: (open: boolean) => void; onSet: (v: string) => void
}) {
  if (locked) {
    return value
      ? <Chip tone="amber" icon="link" title={lockReason} testid={`ground-${ch}`}>{value}</Chip>
      : <span className="muted" title={lockReason} data-testid={`ground-${ch}`}>—</span>
  }
  if (open) {
    return (
      <span className={dirty ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
        <SelectField value={value} size="sm" width={120} testid={`ground-select-${ch}`} ariaLabel={`shared ground of ${ch}`}
          options={[{ value: '', label: '—' }, ...options.map(o => ({ value: o, label: o }))]}
          onChange={onSet} />
      </span>
    )
  }
  return (
    <span className={dirty ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
      {value
        ? <Chip tone="amber" icon="link" testid={`ground-${ch}`} onClick={() => onOpen(true)}
          title={`${ch} and ${value} share a ground · click to change`}>{value}</Chip>
        : <button type="button" className="s-cell-btn muted" data-testid={`ground-${ch}`} onClick={() => onOpen(true)}
          title={`${ch} shares no ground · click to pair it`}>—</button>}
    </span>
  )
}

/** The event timeline (frame 02). A BandStrip cannot select, be clicked or draw point markers (kit is
 *  read-only — see webui/pages/requests/settings.md), so the strip is drawn here: hours since start on a
 *  light ground, an 8 px circle at every event start in its kind's colour, excluded spans as translucent
 *  bands behind them, round-hour ticks, and a blue ring on the selected event. */
const NICE_H = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000]
function EventStrip({ label, domain, marks, selected, onSelect }: {
  label: string; domain: [number, number]
  marks: { id: string; t0: number; t1: number | null; colour: string; excluded: boolean; label: string }[]
  selected: string; onSelect: (id: string) => void
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = size.width
  const rowH = 18, gap = 6, axisH = 20, labelW = 70
  const x = makeX(domain[0], domain[1], w, labelW, 10)
  const spanH = (domain[1] - domain[0]) / 3600
  const step = NICE_H.find(v => spanH / v <= 6) ?? 2000
  const ticks: number[] = []
  for (let t = 0; t <= spanH + 1e-6; t += step) ticks.push(Math.round(t * 100) / 100)
  const [r0, r1] = x.range()
  return (
    <div ref={ref} className="k-plot" data-testid="event-timeline">
      {w > 0 && (
        <svg width={w} height={rowH + gap + axisH} role="img" aria-label={`event timeline · ${marks.length} events`}>
          <text x={0} y={rowH / 2 + 3} style={{ fill: 'var(--text-2)' }}>{label}</text>
          {!marks.length && <text x={labelW} y={rowH / 2 + 3} style={{ fill: 'var(--muted)' }}>no events</text>}
          {/* bands first, so a marker is never hidden behind its own span */}
          {marks.filter(m => m.t1 != null).map(m => {
            const x0 = x(m.t0), x1 = Math.max(x0 + 2, x(m.t1 as number))
            return <rect key={`b-${m.id}`} x={x0} y={0} width={x1 - x0} height={rowH} rx={2}
              fill={`${m.colour}${m.excluded ? '59' : '26'}`} stroke={m.excluded ? `${m.colour}99` : 'none'} strokeWidth={m.excluded ? 1 : 0} />
          })}
          {marks.map(m => {
            const cx = x(m.t0), on = selected === m.id
            const x1 = m.t1 != null ? Math.max(cx + 2, x(m.t1)) : cx
            return (
              <g key={m.id}>
                {on && m.t1 != null && <rect x={cx - 3} y={-3} width={x1 - cx + 6} height={rowH + 6} rx={4} fill="none" stroke="var(--blue)" strokeWidth={1.5} />}
                <circle cx={cx} cy={rowH / 2} r={4} fill={m.colour} stroke={on ? 'var(--blue)' : '#fff'} strokeWidth={on ? 2 : 1} />
                {on && <circle cx={cx} cy={rowH / 2} r={7.5} fill="none" stroke="var(--blue)" strokeWidth={1.5} />}
                <rect x={Math.min(cx - 9, (cx + x1) / 2 - 9)} y={-4} width={Math.max(18, x1 - cx)} height={rowH + 8} fill="transparent"
                  role="button" tabIndex={0} aria-label={m.label} data-testid={`marker-${m.id}`} style={{ cursor: 'pointer' }}
                  onClick={() => onSelect(m.id)}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(m.id) } }}>
                  <title>{m.label}</title>
                </rect>
              </g>
            )
          })}
          <g className="time-axis">
            <line x1={r0} x2={r1} y1={rowH + gap} y2={rowH + gap} stroke="var(--border)" />
            {ticks.map(t => {
              const px = x(t * 3600)
              const anchor = px - r0 < 12 ? 'start' : r1 - px < 12 ? 'end' : 'middle'
              return <g key={t} transform={`translate(${px},${rowH + gap})`}><line y2={3} stroke="var(--border-strong)" /><text y={13} textAnchor={anchor}>{t} h</text></g>
            })}
          </g>
        </svg>
      )}
    </div>
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
  /* one reason per broken rule (fix round 2): a reversed span and a typo used to give the same sentence */
  const m = time.trim().match(/^(\d+(?:\.\d+)?)\s*(?:h)?(?:\s*(?:–|-|to)\s*(\d+(?:\.\d+)?)\s*(?:h)?)?(\s*(?:→|->)\s*end)?$/i)
  const t0 = m ? Number(m[1]) : NaN, tEnd = m && m[2] ? Number(m[2]) : null
  const timeErr = !time.trim() ? 'enter a time'
    : !m ? 'Write a time like 12.5 h, 28.9 – 29.1 h or 40.1 h → end'
      : t0 < 0 || t0 > duration || (tEnd != null && tEnd > duration) ? `Time must be inside 0–${duration} h`
        : tEnd != null && tEnd <= t0 ? 'The span must end after it starts'
          : null
  const parsed = m && !timeErr ? { t0, t1: tEnd, open: !!m[3] } : null
  const err = timeErr ?? (!note ? 'a note is required' : note.length > 120 ? 'at most 120 characters' : null)
  const draft: TimedEvent | null = parsed ? {
    id: `e-new-${Math.round(parsed.t0 * 10)}`, recording: rec, t0_h: parsed.t0, t1_h: parsed.t1, open_end: parsed.open,
    kind, channels, effect, note, added: '16 Sep',
  } : null
  /* Escape closes the row, like every popover on this page (shell rule) */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])
  return (
    <>
      <div className="s-inline-edit" data-testid="add-event-row">
        <TextField value={time} onChange={setTime} placeholder="12.5 h  ·  28.9 – 29.1 h  ·  40.1 h → end" width={230} invalid={!!time.trim() && !!timeErr} testid="event-time" />
        <SelectField value={kind} onChange={setKind} options={kinds.map(k => ({ value: k.name, label: k.name }))} width={130} testid="event-kind" />
        <TextField value={channels} onChange={setChannels} width={110} testid="event-channels" />
        <SelectField value={effect} onChange={v => setEffect(v as EventEffect)} width={190} testid="event-effect"
          options={['show on plots', 'exclude span', 'exclude · mark channel bad'].map(x => ({ value: x, label: x }))} />
        <TextField value={note} onChange={setNote} placeholder="what happened" width={240} testid="event-note" />
        <Button size="sm" onClick={onCancel}>Cancel</Button>
        <Button size="sm" variant="primary" disabled={!!err} disabledReason={err ?? undefined} testid="event-save"
          onClick={() => onAdd(draft!)}>Save row</Button>
      </div>
      {!!time.trim() && !!err && <div className="k-field-error" role="alert" data-testid="add-event-error" style={{ margin: '4px 0 0 10px' }}>
        <Icon name="alert-circle" size={11} />{err}</div>}
      {draft && <div className="s-note mono" data-testid="add-event-consequence" style={{ margin: '4px 0 0 10px' }}>
        {draft.effect === 'show on plots' ? `${spanLabel(draft)} · ${draft.kind} will be marked on plots · no run is marked stale` : eventEffectSentence(draft, draft.effect)}
      </div>}
    </>
  )
}
