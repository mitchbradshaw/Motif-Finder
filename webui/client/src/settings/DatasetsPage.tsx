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
import { getDatasets, metaKey, type ExcerptOf, type MetaField } from '../api/settings'
import { DatasetName } from '../naming'
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

  /* A display name is optional: with none, the dataset is called by its source file everywhere. What it may
     not be is another dataset's name OR another dataset's file — that is the confusion the name exists to end.
     The bridge refuses the same things (Working/database/datasets.py); this only says so before the save. */
  const nameError = (() => {
    if (!current) return null
    const v = meta('display_name').trim()
    if (!v) return null
    if (v.length > 60) return 'At most 60 characters'
    const clash = rows.find(r => r.id !== current.id && [r.name.toLowerCase(), r.file.toLowerCase()].includes(v.toLowerCase()))
    return clash ? `${clash.file} already answers to that` : null
  })()
  const dateError = (() => {
    const v = meta('experiment_date').trim()
    if (!v) return null
    const ok = /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(`${v}T00:00:00Z`)) && new Date(`${v}T00:00:00Z`).toISOString().slice(0, 10) === v
    return ok ? null : 'Use YYYY-MM-DD'
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
    s.markInvalid(field('experiment_date'), locked ? null : dateError)
    s.markInvalid(field('start'), locked ? null : startError)
    s.markInvalid(field('noise_floor'), locked ? null : floorError)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nameError, dateError, startError, floorError, current?.id, locked])

  /* "the same mushroom, three weeks apart": the other datasets carrying this organism id */
  const organism = meta('organism_id').trim().toLowerCase()
  const sameOrganism = organism && current ? rows.filter(r => r.id !== current.id && s.str(metaKey(r.id, 'organism_id')).trim().toLowerCase() === organism) : []

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
              /* one column says both: what the dataset is CALLED (the naming seam, so it changes the moment a name
                 is saved) and, under it, the source file it is — always, named or not */
              {
                key: 'name', header: 'dataset · source file', width: '25%', render: r => (
                  /* a file name has no spaces to break at: it wraps anywhere rather than push the status and the
                     actions off the card (they were clipped before this prompt, too) */
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0, overflowWrap: 'anywhere' }}>
                    <DatasetName file={r.file} className="mono s-ds-name" testid={`name-${r.id}`} />
                    {r.named ? <span className="mono small muted" data-testid={`file-${r.id}`}>{r.file}</span>
                      : <span className="small muted" data-testid={`unnamed-${r.id}`}>not named · called by its file</span>}
                  </span>
                ),
              },
              {
                /* who it is: species, then the organism and the date under it — the three things that tell two
                   similarly named files apart at a glance */
                key: 'identity', header: 'species · organism · date', width: '18%', render: r => {
                  const [sp, org, date] = [s.str(metaKey(r.id, 'species')), s.str(metaKey(r.id, 'organism_id')), s.str(metaKey(r.id, 'experiment_date'))]
                  return (
                    <span style={{ display: 'flex', flexDirection: 'column', gap: 1 }} data-testid={`identity-${r.id}`}>
                      <span>{sp || <span className="muted">species not set</span>}</span>
                      <span className="small muted">{[org ? `organism ${org}` : null, date || null].filter(Boolean).join(' · ') || '—'}</span>
                    </span>
                  )
                },
              },
              {
                key: 'unit', header: 'stored in', width: '8%', render: r => r.units
                  ? <Badge tone="green" testid={`unit-${r.id}`} title={r.units_note ?? undefined}>{r.units}</Badge>
                  : <Badge tone="amber" testid={`unit-${r.id}`} title={r.units_note ?? 'no unit declared: its numbers are shown as stored, never labelled mV'}>undeclared</Badge>,
              },
              {
                key: 'shape', header: 'channels · length · rate', width: '15%', render: r => (
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span>{r.n_channels} ch · {r.duration_h} h</span>
                    <span>{fmtFsHz(r.fs_hz)} Hz <Badge tone={r.fs_source === 'read' ? 'green' : r.fs_source === 'inferred' ? 'amber' : 'grey'}>{r.fs_source === 'unrecorded' ? 'not recorded' : r.fs_source}</Badge></span>
                  </span>
                ),
              },
              {
                key: 'linked', header: 'excerpt of', width: '16%', render: r => r.excerpt_of
                  ? <Button variant="link" size="sm" icon="link" testid={`linked-${r.id}`} onClick={e => { e.stopPropagation(); setRec(r.excerpt_of!.name) }}>
                    <span title={excerptTitle(r.excerpt_of)} style={{ whiteSpace: 'normal', overflowWrap: 'anywhere', textAlign: 'left' }}>{excerptName(r.excerpt_of)}{r.excerpt_of.decimation ? ` · ${r.excerpt_of.decimation}:1` : ''}</span></Button>
                  : <span className="muted">—</span>,
              },
              {
                key: 'status', header: 'status', width: '11%', render: r => {
                  const st = r.id === lockRec ? (lockOn ? 'held out · locked' : 'available') : r.status
                  return <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Badge tone={st === 'in use' ? 'green' : st === 'provisional' ? 'amber' : 'grey'}>{st}</Badge>
                    {r.warnings.length > 0 && <Badge tone="amber" testid={`warnings-${r.id}`} title={r.warnings.join('\n')}>{r.warnings.length} ⚠</Badge>}
                    {!r.npy_exists && <Badge tone="red" testid={`missing-${r.id}`}>files missing</Badge>}
                  </span>
                },
              },
              {
                key: 'actions', header: '', width: '7%', render: r => r.id === lockRec
                  ? <span className="muted small">locked</span>
                  : <Button variant="link" size="sm" testid={`unregister-${r.id}`} onClick={e => { e.stopPropagation(); void unregister(r) }}>unregister</Button>,
              },
            ]} />
        ) : <Callout tone="amber" testid="no-recordings">No recording is registered. Import a recording… lists what is on disk.</Callout>}
      </SectionCard>

      {current && (
        <SectionCard title={<DatasetName file={current.file} className="mono" testid="metadata-name" />}
          subtitle={<span className="mono" data-testid="metadata-file">{current.file} · identity and conditions · travels with every export</span>} testid="metadata-card">
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
              excerpt of <b title={excerptTitle(current.excerpt_of)}>{excerptName(current.excerpt_of)}</b>
              {current.excerpt_of.offset != null ? ` at sample ${current.excerpt_of.offset.toLocaleString('en-US')}` : ''}
              {current.excerpt_of.decimation ? ` · ${current.excerpt_of.decimation}:1 block mean` : ''} · a subset of a registered recording, kept as its own row (id {current.ids[0]}) because runs reference it
            </Callout>
          )}

          {/* ---- identity: what the dataset IS. Saved to the `datasets` table, keyed by the source file (fixup-f). */}
          <SubHead testid="identity-head" title="Identity" caption="what this dataset is, and what every page calls it · one row per source file, audited" />
          <div className="s-grid">
            <GridField label="display name" info="What every workspace calls this dataset — headers, queues, cards, menus. Leave it empty and the dataset is called by its source file. The file is never renamed and stays one hover away wherever the name is printed; nothing keys on the name." {...mark('display_name')} testid="f-display-name">
              <TextField {...ro('display_name')} block invalid={!!nameError && !locked} placeholder={current.file} testid="display-name" />
              {nameError && !locked
                ? <div className="small" style={{ color: 'var(--red)' }} data-testid="display-name-error">{nameError}</div>
                : <div className="small muted" data-testid="display-name-hint">{meta('display_name').trim() ? `the file stays ${current.file}` : 'empty · called by its file'}</div>}
            </GridField>
            <GridField label="species" info="Free text. The species already used on other datasets are offered below — click one to use it — but nothing is locked: type a new one." {...mark('species')} testid="f-species">
              <TextField {...ro('species')} block placeholder="not set" testid="species" />
              {!locked && data.speciesValues.filter(v => v !== meta('species')).length > 0 && (
                <div className="s-suggest" data-testid="species-suggestions">
                  {data.speciesValues.filter(v => v !== meta('species')).map(v => <button key={v} type="button" onClick={() => setMeta('species', v)}>{v}</button>)}
                </div>
              )}
            </GridField>
            <GridField label="organism id" info="Identifies the individual organism across recordings. Give two datasets the same organism id and they are the same mushroom — three weeks apart, or resampled, or an excerpt of one another." {...mark('organism_id')} testid="f-organism">
              <TextField {...ro('organism_id')} block placeholder="not set" testid="organism-id" />
              {sameOrganism.length > 0 && <div className="small muted" data-testid="same-organism">same organism: {sameOrganism.map(r => r.name).join(' · ')}</div>}
            </GridField>
            <GridField label="experiment date" {...mark('experiment_date')} testid="f-experiment-date">
              <TextField {...ro('experiment_date')} block invalid={!!dateError && !locked} placeholder="YYYY-MM-DD" testid="experiment-date" />
              {dateError && !locked && <div className="small" style={{ color: 'var(--red)' }} data-testid="experiment-date-error">{dateError}</div>}
            </GridField>
            <GridField label="condition" info="The experimental condition this dataset was recorded under — baseline, a stimulus, a treatment." {...mark('condition')} testid="f-condition">
              <TextField {...ro('condition')} block placeholder="not set" testid="condition" />
            </GridField>
            <div style={{ gridColumn: 'span 3' }}>
              <GridField label="dataset notes" info="About the dataset as a whole. This is NOT the per-channel text written at registration (recordings.notes) — that is shown read-only below, under “read from the data”, and is never copied here." {...mark('notes')} testid="f-notes">
                <TextField {...ro('notes')} block placeholder="about the whole dataset · timed events go in Channels & events" testid="notes"
                  suffix={<IconButton icon="external" label="open Channels & events" testid="notes-events-link"
                    onClick={() => navigate(`settings/channels-events?rec=${current.id}`)} />} />
              </GridField>
            </div>
          </div>

          {/* ---- derived: read from the data and the registration. Shown, never edited here. */}
          <SubHead testid="derived-head" title="Read from the data" caption="derived at registration · shown, not editable here" />
          <div className="s-grid">
            <GridField label="source file">
              <LockedField reason="the file on disk: what the channel directory, every key and every log line use. A display name never renames it" width="100%" testid="source-file">{current.file}</LockedField>
            </GridField>
            <GridField label="channels">
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span className="mono small" data-testid="channel-count">{current.n_channels} · rows {current.ids[0]}–{current.ids[current.ids.length - 1]}</span>
                <Button variant="link" size="sm" iconRight="arrow-right" testid="to-channels" onClick={() => navigate(`settings/channels-events?rec=${current.id}`)}>Channels &amp; events</Button>
              </div>
            </GridField>
            <GridField label="sampling rate">
              {current.fs_source === 'inferred'
                ? <LockedField reason="inferred at registration (recorded on the row as fs_source = inferred); re-register to change it" width="100%" testid="fs-inferred">{fmtFsHz(current.fs_hz)} Hz · inferred</LockedField>
                : <LockedField reason={current.fs_source === 'read' ? 'read from the file — cannot be edited' : 'registered before this standard: the row carries fs but not where it came from'} width="100%" testid="fs-locked">{fmtFsHz(current.fs_hz)} Hz · {current.fs_source === 'read' ? 'read from the file' : 'source not recorded'}</LockedField>}
            </GridField>
            <GridField label="duration">
              <LockedField reason="samples ÷ sampling rate" width="100%" testid="duration">{current.duration_h} h</LockedField>
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
            <GridField label="registered">
              <LockedField reason="registration provenance: when the rows were written and by whom. Rows that predate the registry carry neither" width="100%" testid="provenance">
                {current.registered_at ? `${current.registered_at.slice(0, 10)} · ${current.registered_by ?? 'unknown'}` : 'before the registry · not recorded'}
              </LockedField>
            </GridField>
            <GridField label="higher-resolution parent" info="When this dataset is a decimated excerpt of a registered recording, Review draws event shape from the parent at its own rate.">
              <LockedField reason="found by the excerpt check at registration (cross-correlation against every comparable registered channel)" width="100%" testid="parent">
                {current.excerpt_of ? `${excerptName(current.excerpt_of)}${current.excerpt_of.decimation ? ` · ${current.excerpt_of.decimation}:1` : ''}` : 'none'}
              </LockedField>
            </GridField>
            <GridField label="channel notes" info="Per-channel text written when the channels were registered (recordings.notes). It belongs to the channel rows, not to the dataset, and is not editable here.">
              <span className="small muted" data-testid="channel-notes">{current.channel_notes.length ? current.channel_notes.join(' · ') : 'none'}</span>
            </GridField>
          </div>

          {/* ---- conditions: the settings table, as before. */}
          <SubHead testid="conditions-head" title="Recording conditions" caption="project settings · every detector reads the noise floor from here" />
          <div className="s-grid">
            <GridField label="substrate" {...mark('substrate')}><TextField {...ro('substrate')} block placeholder="not set" /></GridField>
            <GridField label="electrode config" {...mark('electrode_config')}><TextField {...ro('electrode_config')} block placeholder="not set" /></GridField>
            <GridField label="start time" {...mark('start')}>
              <TextField {...ro('start')} block invalid={!!startError} placeholder="YYYY-MM-DD HH:MM" testid="start-time" />
            </GridField>
            <GridField label="time zone" {...mark('time_zone')}>
              <SelectField value={meta('time_zone') || 'Europe/London'} onChange={v => setMeta('time_zone', v)} disabled={locked}
                disabledReason={locked ? 'held out · locked' : undefined} options={data.timeZones.map(z => ({ value: z, label: z }))} width="100%" />
            </GridField>
            <GridField label="noise floor" info="Every detector reads the noise floor from here; a channel can override it in Channels & events. Empty means detectors estimate it." {...mark('noise_floor')} testid="f-noise-floor">
              <TextField {...ro('noise_floor')} suffix="mV" block placeholder="estimated" invalid={!!floorError && !locked} testid="noise-floor" />
              {floorError && !locked && <div className="small" style={{ color: 'var(--red)' }} data-testid="noise-floor-error">{floorError}</div>}
            </GridField>
            <GridField label="temperature" {...mark('temperature')}><TextField {...ro('temperature')} suffix="°C" block placeholder="not set" /></GridField>
            <GridField label="humidity" {...mark('humidity')}><TextField {...ro('humidity')} suffix="% RH" block placeholder="not set" /></GridField>
          </div>
        </SectionCard>
      )}

      <HeldOut store={s} rows={rows} />

      <ImportModal open={modal === 'import'} onClose={() => setModal('')} candidates={data.candidates} rawCandidates={data.rawCandidates} mode={data.mode}
        onRegistered={name => { reload(); setRec(name) }} />
      <UnlockModal open={modal === 'unlock'} onClose={() => setModal('')} name={data.heldOut.recording === lockRec ? data.heldOut.name : lockRec}
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
            {cand?.name} is a {report.excerpt_of.decimation}:1 excerpt of <b title={report.excerpt_of.channel_note}>{report.excerpt_of.display_name ?? report.excerpt_of.name} {report.excerpt_of.channel_name}</b> at sample {report.excerpt_of.offset.toLocaleString('en-US')} (r = {report.excerpt_of.r}).
            A subset of a registered recording is an excerpt, not a new recording — tick “register even if it is an excerpt” to register it linked to its parent.
          </Callout>}
          {report && report.excerpts.length > 0 && <Callout tone="blue" icon="link" testid="excerpts-note">
            {report.excerpts.map(e => <div key={e.recording_id} className="small">registered <b title={`${e.source_file} · ${e.channel_note ?? ''}`}>{e.display_name ?? e.source_file} {e.channel_name}</b> (id {e.recording_id}) is a {e.decimation}:1 excerpt of this recording’s {e.candidate_channel_name} at sample {e.offset.toLocaleString('en-US')} (r = {e.r}) — it will be linked, its id kept</div>)}
          </Callout>}
          {error && <div className="small" style={{ color: 'var(--red)', marginTop: 6 }} data-testid="import-error">{error}</div>}
        </SubCard>
      </div>
    </Modal>
  )
}

/** An excerpt's parent, by the one name and the one channel convention (both resolved by the bridge). */
const excerptName = (x: ExcerptOf) => `${x.display_name ?? x.source_file} ${x.channel_name ?? ''}`.trim()
/** …with the file and the stored index one hover away. */
const excerptTitle = (x: ExcerptOf) => `source file ${x.source_file}${x.channel_note ? ` · ${x.channel_note}` : ''}`
/** 7.246376815848827 Hz is a measured rate, not a label: three significant decimals on the page, the stored value in the registry. */
const fmtFsHz = (fs: number) => (Number.isInteger(fs) ? String(fs) : fs.toFixed(3).replace(/0+$/, ''))

function SubHead({ title, caption, testid }: { title: string; caption: string; testid?: string }) {
  return <div className="s-subhead" data-testid={testid}><b>{title}</b><span>{caption}</span></div>
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
