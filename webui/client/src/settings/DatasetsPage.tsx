/* Settings › Datasets (frames settings-01, settings-01b · spec §9.1, D6, B20).
 * The recording registry, per-recording metadata, the held-out lock (typed name, logged) and the
 * import dry run. Nothing here is wired: every read is fixture canon, every write stays in memory. */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  Badge, Button, Callout, Checkbox, Checklist, Chip, DisabledReason, IconButton, Modal, ProgressBar, SectionCard, SelectField,
  Table, TextField, Toggle, recordDemoWrite, useDemoState, useNotWired, useQueryState,
} from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getDatasets, IMPORT_PATHS, metaKey, type ImportDryRun, type MetaField, type RecordingRow } from '../api/settings'
import { GridField, LoadFailed, Loading, LockedField, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function DatasetsPage() {
  const rd = useSourced(getDatasets, [])
  return (
    <SettingsShell slug="datasets" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the recording registry" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = NonNullable<ReturnType<typeof useSourced<Awaited<ReturnType<typeof getDatasets>>['data']>>['data']>

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('datasets')
  const notWired = useNotWired()
  const [rec, setRec] = useQueryState('rec', 'M2_aug_fs1')
  const [modal, setModal] = useQueryState('modal', '')
  const [imported, setImported] = useDemoState<RecordingRow[]>('settings.datasets.imported', () => [])

  const rows = useMemo(() => [...data.recordings, ...imported], [data.recordings, imported])
  const current = rows.find(r => r.id === rec) ?? rows[0]
  const lockOn = s.bool('heldout.on')
  const lockRec = s.str('heldout.recording')
  const locked = current.id === lockRec && lockOn
  const caption = `${rows.length} recordings · ${data.recordings.reduce((n, r) => n + r.n_channels, 0)} channels`

  const field = (f: MetaField) => metaKey(current.id, f)
  const meta = (f: MetaField) => s.str(field(f))
  const setMeta = (f: MetaField, v: string) => s.set(field(f), v)

  const nameError = (() => {
    const v = meta('display_name').trim()
    if (!v) return 'A recording needs a display name'
    if (v.length > 40) return 'At most 40 characters'
    const clash = rows.find(r => r.id !== current.id && r.name.toLowerCase() === v.toLowerCase())
    return clash ? `Another recording is already called ${clash.name}` : null
  })()
  const startError = meta('start') && !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(meta('start')) ? 'Use YYYY-MM-DD HH:MM' : null
  const floorError = (() => {
    const n = Number(meta('noise_floor'))
    return meta('noise_floor') === '' || Number.isNaN(n) || n < 0.01 || n > 5 ? 'Enter a floor between 0.01 and 5 mV' : null
  })()
  useEffect(() => {
    s.markInvalid(field('display_name'), locked ? null : nameError)
    s.markInvalid(field('start'), locked ? null : startError)
    s.markInvalid(field('noise_floor'), locked ? null : floorError)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nameError, startError, floorError, current.id, locked])

  const ro = (f: MetaField) => ({
    disabled: locked,
    disabledReason: locked ? `${current.name} is held out · metadata is read-only while the lock is on` : undefined,
    value: meta(f), onChange: (v: string) => setMeta(f, v),
  })
  const mark = (f: MetaField) => ({ dot: s.differs(field(f)), unsaved: s.dirty(field(f)) })

  return (
    <>
      <SectionCard title="Recordings" subtitle={caption} testid="recordings-card"
        actions={<Button icon="file" testid="open-import" onClick={() => setModal('import')}>Import a recording…</Button>}>
        <Table rows={rows} rowKey={r => r.id} onRowClick={r => setRec(r.id)} highlighted={current.id} testid="recordings-table"
          columns={[
            { key: 'name', header: 'name', width: '14%', render: r => <span className="mono" style={{ fontWeight: 600 }}>{r.name}{'isNew' in r && (r as RecordingRow & { isNew?: boolean }).isNew ? <Badge status="new" size="sm" /> : null}</span> },
            { key: 'file', header: 'file', width: '17%', render: r => <span className="mono small">{r.file}</span> },
            { key: 'fs', header: 'sampling rate', width: '12%', render: r => <>{r.fs_hz} Hz <Badge tone={r.fs_source === 'read' ? 'green' : 'amber'}>{r.fs_source}</Badge></> },
            { key: 'ch', header: 'ch', width: '5%', render: r => r.n_channels },
            { key: 'dur', header: 'duration', width: '8%', render: r => `${r.duration_h} h` },
            { key: 'start', header: 'start', width: '13%', render: r => <span className="mono small">{r.start ?? '—'}</span> },
            { key: 'species', header: 'species', width: '10%', render: r => r.species ?? <span className="muted">not set</span> },
            {
              key: 'linked', header: 'linked', width: '8%', render: r => r.linked.length
                ? <Button variant="link" size="sm" icon="link" testid={`linked-${r.id}`} onClick={e => { e.stopPropagation(); setRec(r.linked[0]) }}>{rows.find(x => x.id === r.linked[0])?.name.split(' ').pop()}</Button>
                : <span className="muted">—</span>,
            },
            {
              key: 'status', header: 'status', width: '12%', render: r => {
                const st = r.id === lockRec ? (lockOn ? 'held out · locked' : 'available') : r.status
                return <Badge tone={st === 'in use' ? 'green' : st === 'provisional' ? 'amber' : 'grey'}>{st}</Badge>
              },
            },
          ]} />
      </SectionCard>

      <SectionCard title={<span className="mono">{current.name}</span>} subtitle="metadata · travels with every export" testid="metadata-card">
        {locked && (
          <Callout tone="amber" icon="lock" testid="metadata-locked">
            {current.name} is held out · locked — metadata is read-only while the lock is on (D6).
          </Callout>
        )}
        <div className="s-grid" style={{ marginTop: locked ? 10 : 0 }}>
          <GridField label="display name" {...mark('display_name')} testid="f-display-name">
            <TextField {...ro('display_name')} block invalid={!!nameError && !locked} testid="display-name" />
          </GridField>
          <GridField label="species" {...mark('species')}>
            <TextField {...ro('species')} block placeholder="not set" testid="species" />
          </GridField>
          <GridField label="substrate" {...mark('substrate')}><TextField {...ro('substrate')} block placeholder="not set" /></GridField>
          <GridField label="electrode config" {...mark('electrode_config')}><TextField {...ro('electrode_config')} block placeholder="not set" /></GridField>

          <GridField label="start time" {...mark('start')}>
            <TextField {...ro('start')} block invalid={!!startError} testid="start-time" />
          </GridField>
          <GridField label="time zone" {...mark('time_zone')}>
            <SelectField value={meta('time_zone')} onChange={v => setMeta('time_zone', v)} disabled={locked}
              disabledReason={locked ? 'held out · locked' : undefined} options={data.timeZones.map(z => ({ value: z, label: z }))} width="100%" />
          </GridField>
          <GridField label="sampling rate">
            {current.fs_source === 'read'
              ? <LockedField reason="read from the file header — cannot be edited" width="100%" testid="fs-locked">{current.fs_hz} Hz · read from file header</LockedField>
              : <TextField value={`${current.fs_hz}`} onChange={() => notWired('PUT /api/recordings/' + current.id + ' (fs is inferred)')} block suffix="Hz inferred" testid="fs-inferred" />}
          </GridField>
          <GridField label="noise floor" info="Every detector reads the noise floor from here; a channel can override it in Channels & events." {...mark('noise_floor')} testid="f-noise-floor">
            <TextField {...ro('noise_floor')} suffix="mV" block invalid={!!floorError && !locked} testid="noise-floor" />
            {floorError && !locked && <div className="small" style={{ color: 'var(--red)' }} data-testid="noise-floor-error">{floorError}</div>}
          </GridField>

          <GridField label="temperature" {...mark('temperature')}><TextField {...ro('temperature')} suffix="°C" block placeholder="21.4 ± 0.8" /></GridField>
          <GridField label="humidity" {...mark('humidity')}><TextField {...ro('humidity')} suffix="% RH" block placeholder="88 – 94" /></GridField>
          <GridField label="linked recordings">
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              {current.linked.length
                ? current.linked.map(l => <Chip key={l} tone="blue" icon="link" onClick={() => setRec(l)} testid={`link-chip-${l}`}>{rows.find(r => r.id === l)?.name}</Chip>)
                : <span className="muted small">none</span>}
              {current.linked.length > 0 && <span className="s-note mono" style={{ color: 'var(--amber)' }}>never split train/test</span>}
            </div>
          </GridField>
          <GridField label="notes" {...mark('notes')}>
            <TextField {...ro('notes')} block placeholder="timed events → Channels & events" testid="notes"
              suffix={<IconButton icon="external" label="open Channels & events" testid="notes-events-link"
                onClick={() => navigate(`settings/channels-events?rec=${current.id}`)} />} />
          </GridField>
        </div>
      </SectionCard>

      <HeldOut store={s} rows={rows} />

      <ImportModal open={modal === 'import'} onClose={() => setModal('')} dry={data.dryRun}
        onImported={row => { setImported(x => [...x, row]); setRec(row.id); recordDemoWrite('settings', 'import-recording', { id: row.id }) }} />
      <UnlockModal open={modal === 'unlock'} onClose={() => setModal('')} name={rows.find(r => r.id === lockRec)?.name ?? lockRec}
        onConfirm={() => { s.applyNow('heldout.on', false); setModal('') }} />
    </>
  )
}

/* ------------------------------------------------------------------ held-out lock */

function HeldOut({ store: s, rows }: { store: ReturnType<typeof useSettingsPage>; rows: RecordingRow[] }) {
  const [, setModal] = useQueryState('modal', '')
  const on = s.bool('heldout.on')
  const recId = s.str('heldout.recording')
  const name = rows.find(r => r.id === recId)?.name ?? recId
  return (
    <SectionCard icon="lock" title="Held-out recording" testid="held-out-card"
      actions={<Chip tone={on ? 'blue' : 'grey'} testid="held-out-chip-state">{on ? `on · ${name} held out` : 'off · no recording held out'}</Chip>}>
      <Row id="f-hold-out-a-recording" testid="hold-out-row"
        label="hold out a recording" sub="kept from every workspace"
        info="A held-out recording is kept from every workspace so evaluation on it stays honest (D6)."
        dot={s.differs('heldout.on')} unsaved={s.dirty('heldout.on')}
        caption="when on, every workspace refuses it · turning off needs the name typed · logged">
        <Toggle checked={on} testid="held-out-toggle" ariaLabel="hold out a recording"
          onChange={next => { if (!next) setModal('unlock'); else s.set('heldout.on', true) }} />
        <DisabledReason reason="turn the lock off to choose another recording" disabled={on}>
          <SelectField value={recId} onChange={v => s.set('heldout.recording', v)} disabled={on} width={160} testid="held-out-select"
            options={rows.map(r => ({ value: r.id, label: r.name }))} />
        </DisabledReason>
      </Row>
    </SectionCard>
  )
}

function UnlockModal({ open, onClose, name, onConfirm }: { open: boolean; onClose: () => void; name: string; onConfirm: () => void }) {
  const [typed, setTyped] = useState('')
  useEffect(() => { if (open) setTyped('') }, [open])
  const ok = typed.trim() === name
  return (
    <Modal open={open} onClose={onClose} title="Turn off the held-out lock?" size="md" testid="unlock-modal"
      footerNote="written to the audit log"
      footer={<>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="danger" testid="confirm-unlock" disabled={!ok} disabledReason="type the recording name exactly"
          onClick={() => { recordDemoWrite('settings', 'audit', { kind: 'lock', what: `Held-out lock turned off · ${name} selectable`, where: 'Datasets', route: 'settings/datasets' }); onConfirm() }}>Turn off lock</Button>
      </>}>
      <p className="small" style={{ marginTop: 0, lineHeight: 1.55 }}>
        {name} becomes selectable in every workspace — Explore, Analyse, Discovery, Models, Review, Library.
        Evaluation on it is no longer protected. This is written to the audit log.
      </p>
      <label className="s-label mono" htmlFor="unlock-type">Type {name} to confirm</label>
      <TextField id="unlock-type" value={typed} onChange={setTyped} block placeholder={name} testid="unlock-input" />
    </Modal>
  )
}

/* ------------------------------------------------------------------ import dry run */

type Phase = 'idle' | 'reading' | 'checked' | 'importing' | 'done'

function ImportModal({ open, onClose, dry, onImported }: { open: boolean; onClose: () => void; dry: ImportDryRun; onImported: (r: RecordingRow) => void }) {
  const notWired = useNotWired()
  const [pathQ] = useQueryState('path', '')
  const [path, setPath] = useState(dry.path)
  const [phase, setPhase] = useState<Phase>('checked')
  const [fs, setFs] = useState(String(dry.fs_hz ?? ''))
  const [fsInferred, setFsInferred] = useState(false)
  const [start, setStart] = useState(dry.start)
  const [tz, setTz] = useState(dry.time_zone)
  const [linkTo, setLinkTo] = useState(dry.link_to)
  const [expanded, setExpanded] = useState(false)
  const [map, setMap] = useState(dry.channel_map)
  const [progress, setProgress] = useState(0)
  /* the import timer belongs to the open modal: closing it (or leaving for another deep link) stops the
     run, so a finishing import can no longer navigate to the new recording from under a later state */
  const timer = useRef<number | null>(null)
  const stopTimer = () => { if (timer.current != null) { window.clearInterval(timer.current); timer.current = null } }
  useEffect(() => stopTimer, [])

  useEffect(() => {
    if (!open) { stopTimer(); return }
    const p = pathQ ? `D:/recordings/${pathQ}` : dry.path
    setPath(p); setPhase('checked'); setFs(String(dry.fs_hz ?? '')); setFsInferred(false)
    setStart(dry.start); setTz(dry.time_zone); setLinkTo(dry.link_to); setMap(dry.channel_map); setExpanded(false); setProgress(0)
  }, [open, pathQ, dry])

  const read = (p: string) => {
    setPhase('reading')
    window.setTimeout(() => setPhase('checked'), 400)
    setPath(p)
  }

  const known = IMPORT_PATHS[path]
  const ext = path.slice(path.lastIndexOf('.')).toLowerCase()
  const included = map.filter(m => m.include)
  const fsNum = Number(fs)
  const durationH = fsNum > 0 ? dry.samples_per_channel / fsNum / 3600 : 0
  const dupName = (() => {
    const seen = new Set<string>()
    for (const m of included) { if (seen.has(m.channel)) return m.channel; seen.add(m.channel) }
    return null
  })()

  const checks: { label: string; state: 'pass' | 'warn' | 'fail' }[] = [
    !['.mat', '.csv', '.npy', '.h5'].includes(ext)
      ? { label: `Unsupported format ${ext || '—'} · use .mat .csv .npy or .h5`, state: 'fail' as const }
      : !known
        ? { label: `File not found (demo: try ${dry.path})`, state: 'fail' as const }
        : known.ok
          ? { label: `samples = duration × fs for every channel (${dry.samples_per_channel.toLocaleString('en-US')} = ${durationH.toFixed(0)} h × ${fs} Hz)`, state: 'pass' as const }
          : { label: known.note!, state: 'fail' as const },
    dupName
      ? { label: `Duplicate channel name ${dupName}`, state: 'fail' as const }
      : { label: 'channel names unique and not already used by this recording', state: 'pass' as const },
    included.length ? { label: 'not the held-out recording · M4_aug is locked in this page', state: 'pass' as const } : { label: 'no channel included', state: 'fail' as const },
    { label: 'species not set · allowed, marks the recording provisional', state: 'warn' as const },
  ]
  const fails = checks.filter(c => c.state === 'fail').length

  const doImport = () => {
    setPhase('importing'); setProgress(0)
    let i = 0
    stopTimer()
    timer.current = window.setInterval(() => {
      i += 1; setProgress(i / included.length)
      if (i >= included.length) {
        stopTimer()
        setPhase('done')
        onImported({
          id: 'M5_sep', name: 'M5_sep', file: path.split('/').pop() ?? path, fs_hz: fsNum, fs_source: fsInferred ? 'inferred' : 'read',
          n_channels: included.length, duration_h: Math.round(durationH), start, species: null, linked: linkTo === 'none' ? [] : [linkTo], status: 'provisional',
        })
        notWired('POST /api/recordings/import')
        onClose()
      }
    }, 110)
  }
  const bytes = included.length * dry.samples_per_channel * 8
  const sizeLabel = bytes > 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${Math.round(bytes / 1e6)} MB`

  return (
    <Modal open={open} onClose={onClose} title="Import a recording" size="lg" testid="import-modal"
      headerExtra={<Badge tone="amber" testid="dry-run-badge">dry run · nothing written yet</Badge>}
      footerNote={`will create 1 recording · ${included.length} channels · ${included.length} .npy files · ${sizeLabel} on disk · no runs affected`}
      footer={<>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" testid="do-import" disabled={fails > 0 || phase === 'importing'} loading={phase === 'importing'}
          disabledReason={fails ? `${fails} check${fails === 1 ? '' : 's'} fail` : undefined} onClick={doImport}>Import</Button>
      </>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <SubCard n={1} title="File" caption="read, not copied · stays where it is">
          <div className="s-grid c2">
            <GridField label="path"><TextField value={path} onChange={setPath} onEnter={() => read(path)} block testid="import-path" /></GridField>
            <GridField label="format"><LockedField reason="read from the file header">{phase === 'reading' ? 'reading header…' : dry.format}</LockedField></GridField>
          </div>
        </SubCard>

        <SubCard n={2} title="Sampling rate" caption="read from the file header when present; entered rates are marked inferred">
          <div className="s-grid c3">
            <GridField label="fs">
              <TextField value={fs} onChange={v => { setFs(v); setFsInferred(true) }} suffix={fsInferred ? 'Hz inferred' : 'Hz read'} block testid="import-fs" />
            </GridField>
            <GridField label="samples per channel"><LockedField reason="read from the file header">{dry.samples_per_channel.toLocaleString('en-US')}</LockedField></GridField>
            <GridField label="duration"><LockedField reason="samples ÷ fs">{durationH ? `${durationH.toFixed(0)} h` : '—'}</LockedField></GridField>
          </div>
        </SubCard>

        <SubCard n={3} title="Channel map" caption={`${dry.channel_map.length} variables → ${dry.channel_map.length} channels · names follow CHn_XY`}>
          <Table rows={expanded ? map : map.slice(0, 3)} rowKey={m => m.variable} dense testid="import-channel-map"
            columns={[
              { key: 'variable', header: 'variable', width: '16%', render: m => <span className="mono">{m.variable}</span> },
              {
                key: 'channel', header: 'channel', width: '24%', render: m => (
                  <TextField value={m.channel} size="sm" width={110} invalid={m.include && map.filter(x => x.include && x.channel === m.channel).length > 1}
                    onChange={v => setMap(xs => xs.map(x => x.variable === m.variable ? { ...x, channel: v } : x))} />
                ),
              },
              { key: 'electrode', header: 'electrode · position', width: '24%', render: m => <span className="muted small">{m.electrode}</span> },
              {
                key: 'ground', header: 'shared ground', width: '22%', render: m => (
                  <SelectField value={m.shared_ground ?? '—'} size="sm" width={110}
                    options={[{ value: '—', label: '—' }, ...map.filter(x => x.variable !== m.variable).map(x => ({ value: x.channel, label: x.channel }))]}
                    onChange={v => setMap(xs => xs.map(x => x.variable === m.variable ? { ...x, shared_ground: v === '—' ? null : v } : x.channel === v ? { ...x, shared_ground: m.channel } : x))} />
                ),
              },
              { key: 'include', header: 'include', width: '14%', render: m => <Checkbox checked={m.include} onChange={c => setMap(xs => xs.map(x => x.variable === m.variable ? { ...x, include: c } : x))} ariaLabel={`include ${m.channel}`} /> },
            ]} />
          {map.length > 3 && <Button variant="link" size="sm" icon={expanded ? 'chevron-up' : 'chevron-down'} testid="import-expand"
            onClick={() => setExpanded(e => !e)}>{expanded ? 'show 3' : `… ${map.length - 3} more`}</Button>}
        </SubCard>

        <SubCard n={4} title="Start time and link" caption="a linked recording is the same signal at another rate">
          <div className="s-grid c3">
            <GridField label="start"><TextField value={start} onChange={setStart} block testid="import-start" /></GridField>
            <GridField label="time zone"><SelectField value={tz} onChange={setTz} width="100%" options={['Europe/London', 'UTC', 'Europe/Berlin', 'America/New_York'].map(z => ({ value: z, label: z }))} /></GridField>
            <GridField label="link to existing">
              <SelectField value={linkTo} onChange={setLinkTo} width="100%" testid="import-link"
                options={[{ value: 'none', label: 'none' }, { value: 'M2_aug_fs1', label: 'M2_aug fs1' }, { value: 'M2_aug_fs2', label: 'M2_aug fs2' }, { value: 'M3_jul', label: 'M3_jul' }, { value: 'M4_aug', label: 'M4_aug', disabled: true, reason: 'held out · locked' }]} />
            </GridField>
          </div>
        </SubCard>

        <SubCard n={5} title="Checks" caption="must pass before Import">
          <Checklist items={checks} testid="import-checks" />
          {phase === 'importing' && <div style={{ marginTop: 8 }}><ProgressBar value={progress} label={`writing ${included.length} .npy files… ${Math.round(progress * included.length)} / ${included.length}`} testid="import-progress" /></div>}
        </SubCard>
      </div>
    </Modal>
  )
}

function SubCard({ n, title, caption, children }: { n: number; title: string; caption: string; children: ReactNode }) {
  return (
    <section className="k-card grey pad" data-testid={`import-card-${n}`}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
        <span className="k-section-num">{n}</span><b style={{ fontSize: 12.5 }}>{title}</b>
        <span className="s-card-sub">{caption}</span>
      </div>
      {children}
    </section>
  )
}
