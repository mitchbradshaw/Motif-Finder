/* Settings › Channels & events (frame settings-02 · spec §9.2).
 * Per-channel metadata and the timed-event log. Excluded spans are skipped by every new run. */
import { useRef, useState } from 'react'
import {
  BandStrip, Badge, Button, Callout, Chip, EmptyState, InfoTip, Popover, SectionCard, Seg, SelectField, Table,
  TextField, NumberField, useQueryState, useDemoState, recordDemoWrite,
} from '../kit'
import { useSourced } from '../api/seam'
import { getChannels, effectKey, floorKey, gainKey, type EventEffect, type TimedEvent } from '../api/settings'
import { LoadFailed, Loading, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

const RECS = [
  { value: 'M2_aug_fs1', label: 'M2_aug fs1' }, { value: 'M2_aug_fs2', label: 'M2_aug fs2' }, { value: 'M3_jul', label: 'M3_jul' },
  { value: 'L_LM_Jul26_J', label: 'L_LM_Jul26_J' }, { value: 'M4_aug', label: 'M4_aug' },
]

export function ChannelsEventsPage() {
  const [rec, setRec] = useQueryState('rec', 'M2_aug_fs1')
  const rd = useSourced(() => getChannels(rec), [rec])
  return (
    <SettingsShell slug="channels-events" demo={rd.source === 'demo'}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Seg label="recording" options={RECS} value={rec} onChange={setRec} testid="rec-seg" />
      </div>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what={`channels of ${rec}`} error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body rec={rec} data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getChannels>>['data']

function Body({ rec, data }: { rec: string; data: Data }) {
  const s = useSettingsPage('channels-events')
  const [rows, setRows] = useQueryState('rows', '')
  const [modal, setModal] = useQueryState('modal', '')
  const [sel, setSel] = useState<string | null>(null)
  const [extraKinds, setExtraKinds] = useDemoState<{ name: string; colour: string }[]>('settings.eventKinds', () => [])
  const [added, setAdded] = useDemoState<TimedEvent[]>(`settings.events.${rec}`, () => [])
  const locked = rec === 'M4_aug'
  const all = rows === 'all'
  const channels = all ? data.channels : data.channels.slice(0, 8)
  const kinds = [...data.kinds, ...extraKinds]
  const events = [...data.events, ...added]

  /* a point event is a solid tick; an excluded span is translucent, so a "→ end" exclusion does not
     hide the events under it (the domain is the whole recording, 0 → duration) */
  const segments = events.map(e => {
    const effect = String(s.value(effectKey(e.id)) ?? e.effect)
    const colour = kinds.find(k => k.name === e.kind)?.colour ?? '#9CA3AF'
    const span = e.open_end || e.t1_h != null
    return {
      start: e.t0_h * 3600,
      end: (e.open_end ? data.duration_h : (e.t1_h ?? e.t0_h + Math.max(0.4, data.duration_h / 300))) * 3600,
      colour: span && effect !== 'show on plots' ? `${colour}44` : colour,
      label: `${e.open_end ? `${e.t0_h} h → end` : e.t1_h ? `${e.t0_h} – ${e.t1_h} h` : `${e.t0_h} h`} · ${e.kind} · ${e.channels} · ${effect}`,
    }
  })

  return (
    <>
      {locked && <Callout tone="amber" icon="lock" testid="rec-locked">M4_aug is held out · locked — channels and events are read-only (D6).</Callout>}

      <SectionCard title="Channels" subtitle={`${rec} · ${data.channels.length} channels`} testid="channels-card"
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
            { key: 'name', header: 'name', width: '12%' },
            { key: 'electrode', header: 'electrode · position', width: '16%', render: c => <span className="muted small">{c.electrode}</span> },
            {
              key: 'gain', header: 'gain', width: '14%', render: c => (
                <span className={s.dirty(gainKey(rec, c.ch)) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                  <NumberField value={Number(s.value(gainKey(rec, c.ch)) ?? c.gain)} min={0.01} max={100} step={0.01} unit="mV / u" width={130}
                    disabled={locked} disabledReason={locked ? 'held out · locked' : undefined} testid={`gain-${c.ch}`}
                    onValid={n => { s.set(gainKey(rec, c.ch), n); s.markInvalid(gainKey(rec, c.ch), null) }}
                    onChange={(_raw, reason) => s.markInvalid(gainKey(rec, c.ch), reason ? 'Gain must be a positive number' : null)} />
                </span>
              ),
            },
            {
              key: 'ground', header: 'shared ground', width: '12%', render: c => c.shared_ground
                ? <Chip tone="amber" icon="link" testid={`ground-${c.ch}`}>{c.shared_ground}</Chip>
                : <span className="muted">—</span>,
            },
            { key: 'status', header: 'status', width: '12%', render: c => <Badge tone={c.status === 'ok' ? 'green' : 'red'}>{c.status}</Badge> },
            { key: 'spans', header: 'excluded spans', width: '14%', render: c => <span className="small">{c.spans}</span> },
            {
              key: 'floor', header: 'noise floor', width: '10%', render: c => (
                <TextField value={String(s.value(floorKey(rec, c.ch)) ?? '')} onChange={v => s.set(floorKey(rec, c.ch), v)} placeholder="recording"
                  size="sm" width={92} disabled={locked} disabledReason={locked ? 'held out · locked' : undefined} testid={`floor-${c.ch}`} />
              ),
            },
          ]} />
      </SectionCard>

      <SectionCard title="Event log" subtitle={`${rec} · ${events.length} events`} testid="events-card"
        actions={<Button icon="plus" testid="add-event" disabled={locked} disabledReason={locked ? 'held out · locked' : undefined}
          onClick={() => setModal(modal === 'add-event' ? '' : 'add-event')}>Add event</Button>}>
        <div className="s-timeline-caption">shaded = excluded from analysis</div>
        <BandStrip domain={[0, data.duration_h * 3600]} timeUnit="h" testid="event-timeline"
          rows={[{ label: rec, segments: segments.length ? segments : [{ start: 0, end: 0, colour: '#fff', label: 'no events' }] }]} />

        {modal === 'add-event' && <AddEventRow rec={rec} kinds={kinds} duration={data.duration_h}
          onCancel={() => setModal('')} onAdd={e => { setAdded(x => [...x, e]); setModal(''); recordDemoWrite('settings', 'add-event', { rec, id: e.id }) }} />}

        {events.length ? (
          <Table rows={events} rowKey={e => e.id} testid="events-table" highlighted={sel} onRowClick={e => setSel(e.id)} dense
            columns={[
              { key: 'time', header: 'time', width: '16%', render: e => <span className="mono">{e.open_end ? `${e.t0_h} h → end` : e.t1_h ? `${e.t0_h} – ${e.t1_h} h` : `${e.t0_h} h`}</span> },
              { key: 'kind', header: 'kind', width: '14%', render: e => <><span className="s-swatch" style={{ background: kinds.find(k => k.name === e.kind)?.colour }} /> {e.kind}</> },
              { key: 'channels', header: 'channels', width: '12%', render: e => <span className="mono small">{e.channels}</span> },
              {
                key: 'effect', header: 'effect', width: '22%', render: e => (
                  <span className={s.dirty(effectKey(e.id)) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                    <SelectField value={String(s.value(effectKey(e.id)) ?? e.effect)} onChange={v => s.set(effectKey(e.id), v as EventEffect)}
                      options={data.effects.map(x => ({ value: x, label: x }))} size="sm" width={190} disabled={locked}
                      disabledReason={locked ? 'held out · locked' : undefined} testid={`effect-${e.id}`} />
                  </span>
                ),
              },
              { key: 'note', header: 'note', width: '28%', render: e => <span className="small">{e.note}</span> },
              { key: 'added', header: 'added', width: '8%', render: e => <span className="muted small">{e.added}</span> },
            ]} />
        ) : <EmptyState size="sm" title={`No events on ${rec}`} caption="Add event records a watering, a door opening, a detached electrode" testid="events-empty" />}

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
          <span className="s-label mono">kinds</span>
          {kinds.map(k => <Chip key={k.name} tone="outline" dot={k.colour}>{k.name}</Chip>)}
          <AddKind onAdd={k => setExtraKinds(x => [...x, k])} existing={kinds.map(k => k.name)} />
        </div>
      </SectionCard>
    </>
  )
}

function AddKind({ onAdd, existing }: { onAdd: (k: { name: string; colour: string }) => void; existing: string[] }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [colour, setColour] = useState('#30B0C7')
  const ref = useRef<HTMLButtonElement>(null)
  const err = !name ? 'name the kind' : existing.includes(name.toLowerCase()) ? 'Kind already exists' : !/^[a-z-]{2,20}$/.test(name) ? 'lowercase letters, 2–20' : null
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
    const m = time.trim().match(/^(\d+(?:\.\d+)?)(?:\s*(?:–|-|to)\s*(\d+(?:\.\d+)?))?(\s*(?:→|->)\s*end)?$/)
    if (!m) return null
    const t0 = Number(m[1]); const t1 = m[2] ? Number(m[2]) : null
    if (t0 < 0 || t0 > duration || (t1 != null && (t1 <= t0 || t1 > duration))) return null
    return { t0, t1, open: !!m[3] }
  })()
  const err = !time ? 'enter a time' : !parsed ? `Time must be inside 0–${duration} h` : !note ? 'a note is required' : note.length > 120 ? 'at most 120 characters' : null
  return (
    <div className="s-inline-edit" data-testid="add-event-row">
      <TextField value={time} onChange={setTime} placeholder="12.5 h  ·  28.9 – 29.1 h  ·  40.1 h → end" width={230} invalid={!!time && !parsed} testid="event-time" />
      <SelectField value={kind} onChange={setKind} options={kinds.map(k => ({ value: k.name, label: k.name }))} width={130} testid="event-kind" />
      <TextField value={channels} onChange={setChannels} width={110} testid="event-channels" />
      <SelectField value={effect} onChange={v => setEffect(v as EventEffect)} width={190} testid="event-effect"
        options={['show on plots', 'exclude span', 'exclude · mark channel bad'].map(x => ({ value: x, label: x }))} />
      <TextField value={note} onChange={setNote} placeholder="what happened" width={240} testid="event-note" />
      <Button size="sm" onClick={onCancel}>Cancel</Button>
      <Button size="sm" variant="primary" disabled={!!err} disabledReason={err ?? undefined} testid="event-save"
        onClick={() => onAdd({
          id: `e-new-${Date.now()}`, recording: rec, t0_h: parsed!.t0, t1_h: parsed!.t1, open_end: parsed!.open,
          kind, channels, effect, note, added: '16 Sep',
        })}>Save row</Button>
    </div>
  )
}
