/* Settings › Datasets (frames settings-01, settings-01b · spec §9.1, D6, B20) — LIVE (Prompt 02).
 * The recording registry (GET /api/registry/recording through GET /api/settings/datasets), per-recording
 * metadata (the settings table), the held-out lock (typed name, enforced server-side, logged) and the
 * registration flow: scan → check → register with progress, for channel directories already on disk and for
 * raw .mat/.csv files that still need deriving (docs/DATA_REGISTRATION.md). */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Badge, Button, Callout, Checklist, Chip, DisabledReason, IconButton, Modal, ProgressBar, SectionCard, SelectField,
  Table, TextField, Toggle, useQueryState,
} from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { ApiError, checkCandidate, declareRecordingUnits, registerCandidate, unregisterRow, type Candidate, type CheckReport } from '../api'
import { getDatasets, metaKey, type MetaField } from '../api/settings'
import { useToast } from '../shell/Toast'
import { GridField, LoadFailed, Loading, LockedField, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function DatasetsPage() {
  const rd = useSourced(getDatasets, [])
  return (
    <SettingsShell slug="datasets" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the recording registry" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} reload={rd.reload} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getDatasets>>['data']
type Rec = Data['recordings'][number]

function Body({ data, reload }: { data: Data; reload: () => void }) {
  const s = useSettingsPage('datasets')
  const { push } = useToast()
  const rows = data.recordings
  const [rec, setRec] = useQueryState('rec', rows[0]?.id ?? '')
  const [modal, setModal] = useQueryState('modal', '')
  const current = rows.find(r => r.id === rec) ?? rows[0]
  const lockOn = s.bool('heldout.on')
  const lockRec = s.str('heldout.recording')
  const locked = Boolean(current) && current.id === lockRec && lockOn
  const nCandidates = data.candidates.length + data.rawCandidates.length

  const field = (f: MetaField) => metaKey(current?.id ?? '', f)
  const meta = (f: MetaField) => s.str(field(f))
  const setMeta = (f: MetaField, v: string) => s.set(field(f), v)

  const nameError = (() => {
    if (!current) return null
    const v = meta('display_name').trim()
    if (!v) return 'A recording needs a display name'
    if (v.length > 40) return 'At most 40 characters'
    const clash = rows.find(r => r.id !== current.id && r.name.toLowerCase() === v.toLowerCase())
    return clash ? `Another recording is already called ${clash.name}` : null
  })()
  const startError = meta('start') && !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(meta('start')) ? 'Use YYYY-MM-DD HH:MM' : null
  const floorError = (() => {
    if (meta('noise_floor') === '') return null            /* not set: detectors estimate it (Analysis defaults) */
    const n = Number(meta('noise_floor'))
    return Number.isNaN(n) || n < 0.01 || n > 5 ? 'Enter a floor between 0.01 and 5 mV' : null
  })()
  useEffect(() => {
    if (!current) return
    s.markInvalid(field('display_name'), locked ? null : nameError)
    s.markInvalid(field('start'), locked ? null : startError)
    s.markInvalid(field('noise_floor'), locked ? null : floorError)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nameError, startError, floorError, current?.id, locked])

  const ro = (f: MetaField) => ({
    disabled: locked,
    disabledReason: locked ? `${current.name} is held out · metadata is read-only while the lock is on` : undefined,
    value: meta(f), onChange: (v: string) => setMeta(f, v),
  })
  const mark = (f: MetaField) => ({ dot: s.differs(field(f)), unsaved: s.dirty(field(f)) })

  // fixup-b: the unit is a fact about the data, declared once per recording and audited — not a draft setting
  const [unitDraft, setUnitDraft] = useState('')
  useEffect(() => setUnitDraft(''), [current?.id])
  const declareUnit = async (r: Rec, units: string) => {
    try {
      const out = await declareRecordingUnits(r.ids[0], units)
      push({ text: `${r.name}: samples declared ${out.units} on ${out.channels} channel${out.channels === 1 ? '' : 's'} · every page now draws it in mV` })
      reload()
    } catch (e) { push({ text: `Could not declare the unit · ${e instanceof Error ? e.message : String(e)}`, kind: 'error' }) }
  }

  const unregister = async (r: Rec) => {
    try {
      await unregisterRow('recording', r.ids[0])
      push({ text: `${r.name} unregistered · ${r.n_channels} rows kept inactive, files untouched` })
      reload()
    } catch (e) { push({ text: `Could not unregister · ${e instanceof Error ? e.message : String(e)}`, kind: 'error' }) }
  }

  return (
    <>
      <SectionCard title="Recordings" subtitle={data.caption} testid="recordings-card"
        actions={<Button icon="file" testid="open-import" onClick={() => setModal('import')}>
          Import a recording…{nCandidates ? <span style={{ marginLeft: 6 }}><Badge tone="amber" testid="candidate-count">{nCandidates} on disk</Badge></span> : null}
        </Button>}>
        {rows.length ? (
          <Table rows={rows} rowKey={r => r.id} onRowClick={r => setRec(r.id)} highlighted={current?.id} testid="recordings-table"
            columns={[
              { key: 'name', header: 'name', width: '16%', render: r => <span className="mono" style={{ fontWeight: 600 }}>{r.name}</span> },
              { key: 'file', header: 'file', width: '13%', render: r => <span className="mono small">{r.file}</span> },
              {
                key: 'unit', header: 'stored in', width: '7%', render: r => r.units
                  ? <Badge tone="green" testid={`unit-${r.id}`} title={r.units_note ?? undefined}>{r.units}</Badge>
                  : <Badge tone="amber" testid={`unit-${r.id}`} title={r.units_note ?? 'no unit declared: its numbers are shown as stored, never labelled mV'}>undeclared</Badge>,
              },
              { key: 'fs', header: 'sampling rate', width: '12%', render: r => <>{r.fs_hz} Hz <Badge tone={r.fs_source === 'read' ? 'green' : r.fs_source === 'inferred' ? 'amber' : 'grey'}>{r.fs_source === 'unrecorded' ? 'not recorded' : r.fs_source}</Badge></> },
              { key: 'ch', header: 'ch', width: '4%', render: r => r.n_channels },
              { key: 'dur', header: 'duration', width: '8%', render: r => `${r.duration_h} h` },
              { key: 'species', header: 'species', width: '9%', render: r => r.species ?? <span className="muted">not set</span> },
              {
                key: 'linked', header: 'excerpt of', width: '8%', render: r => r.excerpt_of
                  ? <Button variant="link" size="sm" icon="link" testid={`linked-${r.id}`} onClick={e => { e.stopPropagation(); setRec(r.excerpt_of!.name) }}>
                    {r.excerpt_of.name} CH{r.excerpt_of.channel}{r.excerpt_of.decimation ? ` · ${r.excerpt_of.decimation}:1` : ''}</Button>
                  : <span className="muted">—</span>,
              },
              {
                key: 'status', header: 'status', width: '12%', render: r => {
                  const st = r.id === lockRec ? (lockOn ? 'held out · locked' : 'available') : r.status
                  return <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                    <Badge tone={st === 'in use' ? 'green' : st === 'provisional' ? 'amber' : 'grey'}>{st}</Badge>
                    {r.warnings.length > 0 && <Badge tone="amber" testid={`warnings-${r.id}`} title={r.warnings.join('\n')}>{r.warnings.length} ⚠</Badge>}
                    {!r.npy_exists && <Badge tone="red" testid={`missing-${r.id}`}>files missing</Badge>}
                  </span>
                },
              },
              {
                key: 'actions', header: '', width: '11%', render: r => r.id === lockRec
                  ? <span className="muted small">locked</span>
                  : <Button variant="link" size="sm" testid={`unregister-${r.id}`} onClick={e => { e.stopPropagation(); void unregister(r) }}>unregister</Button>,
              },
            ]} />
        ) : <Callout tone="amber" testid="no-recordings">No recording is registered. Import a recording… lists what is on disk.</Callout>}
      </SectionCard>

      {current && (
        <SectionCard title={<span className="mono">{current.name}</span>} subtitle="metadata · travels with every export" testid="metadata-card">
          {locked && (
            <Callout tone="amber" icon="lock" testid="metadata-locked">
              {current.name} is held out · locked — metadata is read-only while the lock is on (D6).
            </Callout>
          )}
          {current.warnings.length > 0 && (
            <Callout tone="amber" icon="alert-triangle" testid="recording-warnings">
              <b>Registered with {current.warnings.length} warning{current.warnings.length === 1 ? '' : 's'}</b>
              <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>{current.warnings.map((w, i) => <li key={i} className="small">{w}</li>)}</ul>
            </Callout>
          )}
          {current.excerpt_of && (
            <Callout tone="blue" icon="link" testid="excerpt-note">
              excerpt of <b>{current.excerpt_of.name}</b> CH{current.excerpt_of.channel}
              {current.excerpt_of.offset != null ? ` at sample ${current.excerpt_of.offset.toLocaleString('en-US')}` : ''}
              {current.excerpt_of.decimation ? ` · ${current.excerpt_of.decimation}:1 block mean` : ''} · a subset of a registered recording, kept as its own row (id {current.ids[0]}) because runs reference it
            </Callout>
          )}
          <div className="s-grid" style={{ marginTop: locked || current.warnings.length ? 10 : 0 }}>
            <GridField label="display name" {...mark('display_name')} testid="f-display-name">
              <TextField {...ro('display_name')} block invalid={!!nameError && !locked} testid="display-name" />
            </GridField>
            <GridField label="species" {...mark('species')}>
              <TextField {...ro('species')} block placeholder="not set" testid="species" />
            </GridField>
            <GridField label="substrate" {...mark('substrate')}><TextField {...ro('substrate')} block placeholder="not set" /></GridField>
            <GridField label="electrode config" {...mark('electrode_config')}><TextField {...ro('electrode_config')} block placeholder="not set" /></GridField>

            <GridField label="start time" {...mark('start')}>
              <TextField {...ro('start')} block invalid={!!startError} placeholder="YYYY-MM-DD HH:MM" testid="start-time" />
            </GridField>
            <GridField label="time zone" {...mark('time_zone')}>
              <SelectField value={meta('time_zone') || 'Europe/London'} onChange={v => setMeta('time_zone', v)} disabled={locked}
                disabledReason={locked ? 'held out · locked' : undefined} options={data.timeZones.map(z => ({ value: z, label: z }))} width="100%" />
            </GridField>
            <GridField label="sampling rate">
              {current.fs_source === 'inferred'
                ? <LockedField reason="inferred at registration (recorded on the row as fs_source = inferred); re-register to change it" width="100%" testid="fs-inferred">{current.fs_hz} Hz · inferred</LockedField>
                : <LockedField reason={current.fs_source === 'read' ? 'read from the file — cannot be edited' : 'registered before this standard: the row carries fs but not where it came from'} width="100%" testid="fs-locked">{current.fs_hz} Hz · {current.fs_source === 'read' ? 'read from the file' : 'source not recorded'}</LockedField>}
            </GridField>
            <GridField label="stored in" info="The unit the channel files hold. Every page converts from it to mV at one place; a recording with no declared unit is drawn as stored and never labelled mV." testid="f-units">
              {current.units
                ? <LockedField reason={current.units_note ?? 'declared'} width="100%" testid="units-declared">{current.units} · drawn in mV</LockedField>
                : <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <SelectField value={unitDraft} onChange={setUnitDraft} disabled={locked} disabledReason={locked ? 'held out · locked' : undefined} width={120} testid="units-select"
                    options={[{ value: '', label: 'undeclared' }, { value: 'V', label: 'V (volts)' }, { value: 'mV', label: 'mV (millivolts)' }, { value: 'uV', label: 'µV (microvolts)' }]} />
                  <Button size="sm" testid="units-declare" disabled={!unitDraft || locked} onClick={() => void declareUnit(current, unitDraft)}>Declare</Button>
                </div>}
              {!current.units && <div className="small muted" data-testid="units-note" style={{ marginTop: 4 }}>{current.units_note ?? 'no unit declared for this recording'}</div>}
            </GridField>
            <GridField label="noise floor" info="Every detector reads the noise floor from here; a channel can override it in Channels & events. Empty means detectors estimate it." {...mark('noise_floor')} testid="f-noise-floor">
              <TextField {...ro('noise_floor')} suffix="mV" block placeholder="estimated" invalid={!!floorError && !locked} testid="noise-floor" />
              {floorError && !locked && <div className="small" style={{ color: 'var(--red)' }} data-testid="noise-floor-error">{floorError}</div>}
            </GridField>

            <GridField label="temperature" {...mark('temperature')}><TextField {...ro('temperature')} suffix="°C" block placeholder="not set" /></GridField>
            <GridField label="humidity" {...mark('humidity')}><TextField {...ro('humidity')} suffix="% RH" block placeholder="not set" /></GridField>
            <GridField label="channels">
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span className="mono small">{current.n_channels} · rows {current.ids[0]}–{current.ids[current.ids.length - 1]}</span>
                <Button variant="link" size="sm" iconRight="arrow-right" testid="to-channels" onClick={() => navigate(`settings/channels-events?rec=${current.id}`)}>Channels &amp; events</Button>
              </div>
            </GridField>
            <GridField label="notes" {...mark('notes')}>
              <TextField {...ro('notes')} block placeholder="timed events → Channels & events" testid="notes"
                suffix={<IconButton icon="external" label="open Channels & events" testid="notes-events-link"
                  onClick={() => navigate(`settings/channels-events?rec=${current.id}`)} />} />
            </GridField>
          </div>
        </SectionCard>
      )}

      <HeldOut store={s} rows={rows} />

      <ImportModal open={modal === 'import'} onClose={() => setModal('')} candidates={data.candidates} rawCandidates={data.rawCandidates} mode={data.mode}
        onRegistered={name => { reload(); setRec(name) }} />
      <UnlockModal open={modal === 'unlock'} onClose={() => setModal('')} name={rows.find(r => r.id === lockRec)?.name ?? lockRec}
        onConfirm={async typed => { await s.applyNow('heldout.on', false, typed); setModal('') }} />
    </>
  )
}

/* ------------------------------------------------------------------ held-out lock */

function HeldOut({ store: s, rows }: { store: ReturnType<typeof useSettingsPage>; rows: Rec[] }) {
  const [, setModal] = useQueryState('modal', '')
  const { push } = useToast()
  const on = s.bool('heldout.on')
  const recId = s.str('heldout.recording')
  const name = rows.find(r => r.id === recId)?.name ?? recId
  return (
    <SectionCard icon="lock" title="Held-out recording" testid="held-out-card"
      actions={<Chip tone={on ? 'blue' : 'grey'} testid="held-out-chip-state">{on ? `on · ${name} held out` : 'off · no recording held out'}</Chip>}>
      <Row id="f-hold-out-a-recording" testid="hold-out-row"
        label="hold out a recording" sub="kept from every workspace"
        info="A held-out recording is kept from every workspace so evaluation on it stays honest (D6). The bridge refuses M4_aug_concat_fs1.mat on every route whatever this says."
        dot={s.differs('heldout.on')} unsaved={s.dirty('heldout.on')}
        caption="when on, every workspace refuses it · turning off needs the name typed · logged">
        <Toggle checked={on} testid="held-out-toggle" ariaLabel="hold out a recording"
          onChange={next => { if (!next) setModal('unlock'); else s.applyNow('heldout.on', true).then(() => push({ text: `Held-out lock on · ${name} held out · logged` })).catch(e => push({ text: String(e instanceof Error ? e.message : e), kind: 'error' })) }} />
        <DisabledReason reason="turn the lock off to choose another recording" disabled={on}>
          <SelectField value={recId} onChange={v => s.set('heldout.recording', v)} disabled={on} width={200} testid="held-out-select"
            options={rows.map(r => ({ value: r.id, label: r.name }))} />
        </DisabledReason>
      </Row>
    </SectionCard>
  )
}

function UnlockModal({ open, onClose, name, onConfirm }: { open: boolean; onClose: () => void; name: string; onConfirm: (typed: string) => Promise<void> }) {
  const [typed, setTyped] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (open) { setTyped(''); setError(null) } }, [open])
  const ok = typed.trim() === name
  return (
    <Modal open={open} onClose={onClose} title="Turn off the held-out lock?" size="md" testid="unlock-modal"
      footerNote="written to the audit log · the name is checked again by the server"
      footer={<>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="danger" testid="confirm-unlock" disabled={!ok || busy} loading={busy} disabledReason="type the recording name exactly"
          onClick={() => { setBusy(true); setError(null); onConfirm(typed.trim()).catch(e => setError(e instanceof ApiError ? e.message : String(e))).finally(() => setBusy(false)) }}>Turn off lock</Button>
      </>}>
      <p className="small" style={{ marginTop: 0, lineHeight: 1.55 }}>
        {name} becomes selectable in every workspace — Explore, Analyse, Discovery, Models, Review, Library.
        Evaluation on it is no longer protected. This is written to the audit log.
      </p>
      <label className="s-label mono" htmlFor="unlock-type">Type {name} to confirm</label>
      <TextField id="unlock-type" value={typed} onChange={setTyped} block placeholder={name} testid="unlock-input" />
      {error && <div className="small" style={{ color: 'var(--red)', marginTop: 6 }} data-testid="unlock-error">{error}</div>}
    </Modal>
  )
}

/* ------------------------------------------------------------------ registration flow */

type Phase = 'pick' | 'checking' | 'checked' | 'registering' | 'done'

function ImportModal({ open, onClose, candidates, rawCandidates, mode, onRegistered }: {
  open: boolean; onClose: () => void; candidates: Candidate[]; rawCandidates: Candidate[]; mode: string; onRegistered: (name: string) => void
}) {
  const { push } = useToast()
  const all = useMemo(() => [...candidates.map(c => ({ ...c, kind: 'recording' })), ...rawCandidates.map(c => ({ ...c, kind: 'raw' }))], [candidates, rawCandidates])
  const [pathQ] = useQueryState('path', '')
  const [path, setPath] = useState('')
  const [phase, setPhase] = useState<Phase>('pick')
  const [report, setReport] = useState<CheckReport | null>(null)
  const [fs, setFs] = useState('')
  const [nChannels, setNChannels] = useState('')
  const [variable, setVariable] = useState('')
  const [allowExcerpt, setAllowExcerpt] = useState(false)
  const [producer, setProducer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!open) return
    const first = all.find(c => c.name === pathQ || c.path === pathQ) ?? null
    setPath(first?.path ?? ''); setPhase('pick'); setReport(null); setFs(''); setNChannels(''); setVariable(''); setAllowExcerpt(false); setProducer(''); setError(null)
  }, [open, pathQ, all])

  useEffect(() => {
    if (phase !== 'checking' && phase !== 'registering') return
    const t0 = Date.now(); setElapsed(0)
    const t = window.setInterval(() => setElapsed((Date.now() - t0) / 1000), 250)
    return () => window.clearInterval(t)
  }, [phase])

  const cand = all.find(c => c.path === path) ?? null
  const overrides = () => {
    const o: Record<string, unknown> = {}
    if (fs.trim()) o.fs = Number(fs)
    if (nChannels.trim()) o.n_channels = Number(nChannels)
    if (variable.trim()) o.variable = variable.trim()
    if (allowExcerpt) o.allow_excerpt = true
    return o
  }
  const runCheck = async () => {
    if (!cand) return
    setPhase('checking'); setError(null)
    try { setReport(await checkCandidate(cand.kind, cand.path, overrides())); setPhase('checked') }
    catch (e) { setError(e instanceof ApiError ? e.message : String(e)); setPhase('pick') }
  }
  const doRegister = async () => {
    if (!cand || !report?.ok) return
    setPhase('registering'); setError(null)
    try {
      const r = await registerCandidate(cand.kind, cand.path, overrides(), producer.trim() ? { producer: producer.trim() } : {})
      setPhase('done')
      push({ text: `Registered ${r.name} · ${r.table} id ${r.id}${r.warnings.length ? ` · ${r.warnings.length} warning${r.warnings.length === 1 ? '' : 's'}` : ''} · ${r.note}` })
      onRegistered(cand.kind === 'raw' ? (r.facts?.derived_dir?.split('/').pop() ?? r.name) : r.name)
      onClose()
    } catch (e) {
      const detail = (e as ApiError)?.detail as { checks?: { name: string; ok: boolean; detail: string }[]; message?: string } | undefined
      if (detail?.checks) setReport({ ...(report as CheckReport), ok: false, checks: detail.checks })
      setError(e instanceof ApiError ? e.message : String(e)); setPhase('checked')
    }
  }

  const fsUnknown = cand ? cand.facts.fs == null : false
  const layoutFlat = cand?.kind === 'raw' && cand.facts.layout?.layout === 'flat'
  const items = (report?.checks ?? []).map(c => ({ label: `${c.name} · ${c.detail}`, state: c.ok ? 'pass' as const : 'fail' as const }))
  const warnItems = (report?.warnings ?? []).map(w => ({ label: w, state: 'warn' as const }))
  const fails = report ? report.checks.filter(c => !c.ok).length : 0

  return (
    <Modal open={open} onClose={onClose} title="Import a recording" size="lg" testid="import-modal"
      headerExtra={<Badge tone={phase === 'done' ? 'green' : 'amber'} testid="dry-run-badge">{report && phase === 'checked' ? `checked · ${fails ? `${fails} check${fails === 1 ? '' : 's'} fail` : 'ready to register'}` : 'dry run · nothing written yet'}</Badge>}
      footerNote={cand ? `will register ${cand.kind === 'raw' ? 'the derived channels of' : ''} ${cand.name} as one recordings row per channel${mode === 'sandbox' ? ' · sandbox: into the database copy' : ' · project: into the real database'} · a sidecar manifest is written · no runs affected` : `${all.length} unregistered on disk · pick one`}
      footer={<>
        <Button onClick={onClose}>Cancel</Button>
        <Button testid="run-check" disabled={!cand || phase === 'checking' || phase === 'registering'} loading={phase === 'checking'} onClick={runCheck}>Check</Button>
        <Button variant="primary" testid="do-import" disabled={!report?.ok || phase !== 'checked'} loading={phase === 'registering'}
          disabledReason={!report ? 'run the checks first' : fails ? `${fails} check${fails === 1 ? '' : 's'} fail` : undefined} onClick={doRegister}>Register</Button>
      </>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <SubCard n={1} title="On disk, not registered" caption={`${candidates.length} channel director${candidates.length === 1 ? 'y' : 'ies'} · ${rawCandidates.length} raw file${rawCandidates.length === 1 ? '' : 's'} (scanned from DATA/derived/channels and DATA/raw)`}>
          {all.length ? (
            <Table rows={all} rowKey={c => c.path} dense testid="import-candidates" onRowClick={c => { setPath(c.path); setReport(null); setPhase('pick') }} highlighted={path}
              columns={[
                { key: 'kind', header: 'kind', width: '11%', render: c => <Badge tone={c.kind === 'raw' ? 'purple' : 'blue'}>{c.kind === 'raw' ? 'raw file' : 'channels'}</Badge> },
                { key: 'name', header: 'name', width: '24%', render: c => <span className="mono" style={{ fontWeight: 600 }}>{c.name}</span> },
                { key: 'facts', header: 'read from the header', width: '40%', render: c => <span className="mono small">{describe(c)}</span> },
                { key: 'warn', header: '', width: '25%', render: c => c.warnings.length ? <span className="small" style={{ color: 'var(--amber)' }} title={c.warnings.join('\n')}>{c.warnings[0].slice(0, 70)}{c.warnings[0].length > 70 ? '…' : ''}</span> : <span className="muted small">no warnings</span> },
              ]} />
          ) : <span className="muted small" data-testid="import-empty">Everything on disk is registered.</span>}
        </SubCard>

        <SubCard n={2} title="What the check needs from you" caption="only what the file cannot say; anything typed here is recorded as inferred">
          <div className="s-grid c3">
            <GridField label="fs (Hz)">
              <TextField value={fs} onChange={setFs} block placeholder={cand ? (cand.facts.fs != null ? `${cand.facts.fs} read` : 'unknown — required') : '—'} disabled={!cand} testid="import-fs" />
              {fsUnknown && cand && <div className="small" style={{ color: 'var(--amber)' }}>the file carries no sampling rate</div>}
            </GridField>
            <GridField label="channels (flat vectors only)">
              <TextField value={nChannels} onChange={setNChannels} block placeholder={layoutFlat ? '16 is this project’s convention' : 'from the layout'} disabled={!layoutFlat} testid="import-n-channels" />
            </GridField>
            <GridField label="variable (.mat with several)">
              <TextField value={variable} onChange={setVariable} block placeholder={cand?.facts.layout?.variable ?? '—'} disabled={cand?.kind !== 'raw'} testid="import-variable" />
            </GridField>
            <GridField label="producer / provenance note">
              <TextField value={producer} onChange={setProducer} block placeholder="e.g. scripts/rederive_channels.py, lab export 2026-07-26" testid="import-producer" />
            </GridField>
            <GridField label="excerpt">
              <label className="small" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <input type="checkbox" checked={allowExcerpt} onChange={e => setAllowExcerpt(e.target.checked)} data-testid="import-allow-excerpt" />
                register even if it is an excerpt of a registered recording (linked to its parent)
              </label>
            </GridField>
          </div>
        </SubCard>

        <SubCard n={3} title="Checks" caption="exists · readable · shape · fs · held out · excerpt · not registered · hash — every one must pass">
          {phase === 'checking' && <ProgressBar indeterminate label={`checking ${cand?.name}… ${elapsed.toFixed(0)} s (the excerpt search cross-correlates against every comparable registered channel)`} testid="check-progress" />}
          {phase === 'registering' && <ProgressBar indeterminate label={`registering ${cand?.name}… ${elapsed.toFixed(0)} s${cand?.kind === 'raw' ? ' (deriving channels to disk first)' : ''}`} testid="import-progress" />}
          {report && phase !== 'checking' && <Checklist items={[...items, ...warnItems]} testid="import-checks" />}
          {!report && phase === 'pick' && <span className="muted small">pick a candidate and press Check</span>}
          {report?.excerpt_of && <Callout tone="amber" icon="link" testid="excerpt-of-note">
            {cand?.name} is a {report.excerpt_of.decimation}:1 excerpt of <b>{report.excerpt_of.name}</b> CH{report.excerpt_of.channel} at sample {report.excerpt_of.offset.toLocaleString('en-US')} (r = {report.excerpt_of.r}).
            A subset of a registered recording is an excerpt, not a new recording — tick “register even if it is an excerpt” to register it linked to its parent.
          </Callout>}
          {report && report.excerpts.length > 0 && <Callout tone="blue" icon="link" testid="excerpts-note">
            {report.excerpts.map(e => <div key={e.recording_id} className="small">registered <b>{e.source_file}</b> CH{e.channel} (id {e.recording_id}) is a {e.decimation}:1 excerpt of this recording’s CH{e.candidate_channel} at sample {e.offset.toLocaleString('en-US')} (r = {e.r}) — it will be linked, its id kept</div>)}
          </Callout>}
          {error && <div className="small" style={{ color: 'var(--red)', marginTop: 6 }} data-testid="import-error">{error}</div>}
        </SubCard>
      </div>
    </Modal>
  )
}

function describe(c: Candidate): string {
  const f = c.facts
  if (c.kind === 'raw') {
    const lay = f.layout
    return [f.format, lay ? `${lay.variable} · ${lay.layout}${lay.n_channels ? ` · ${lay.n_channels} ch` : ''}${lay.n_samples ? ` × ${Number(lay.n_samples).toLocaleString('en-US')}` : ''}` : 'layout unknown',
      f.fs != null ? `${f.fs} Hz` : 'fs ?', f.derived_dir ? `derived at ${f.derived_dir}` : null].filter(Boolean).join(' · ')
  }
  return [`${f.n_channels} ch × ${Number(f.n_samples ?? 0).toLocaleString('en-US')}`, f.fs != null ? `${f.fs} Hz${f.fs_source === 'inferred' ? ' (inferred)' : ''}` : 'fs ?',
    f.duration_h != null ? `${Number(f.duration_h).toFixed(1)} h` : null, f.has_manifest ? 'manifest' : 'no manifest'].filter(Boolean).join(' · ')
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
