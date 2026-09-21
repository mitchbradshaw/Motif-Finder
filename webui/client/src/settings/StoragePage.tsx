/* Settings › Storage & backups (frame settings-11 · spec §9.11, B26) — LIVE (Prompt 02).
 * The real roots with their sizes (GET /api/storage), the naming convention with a live preview, the
 * backups the --project mode writes on every start (and Back up now → POST /api/backups), and the free-space
 * warning. A root's "scan" opens the registry for that kind (GET /api/registry/<kind>) in a modal. */
import { useState } from 'react'
import {
  Badge, Button, Callout, Checklist, Chip, Modal, NumberField, Popover, ProgressBar, SectionCard, SelectField, Table, TextField, Toggle, useQueryState,
} from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { ApiError, checkCandidate, getRegistry, postBackup, registerCandidate, type Candidate, type CheckReport, type RegisteredArtifact, type RegisteredRecording } from '../api'
import { backupRow, getStorage, namingPreview, type StorageRoot } from '../api/settings'
import { useToast } from '../shell/Toast'
import { LoadFailed, Loading, LockedField, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'
import { useRef } from 'react'

export function StoragePage() {
  const rd = useSourced(getStorage, [])
  return (
    <SettingsShell slug="storage-backups" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the storage roots" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} reload={rd.reload} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getStorage>>['data']

/** Which registry kind a root's "scan" opens. */
const KIND_OF: Record<string, string> = {
  recordings: 'raw', channels: 'recording', window_matrices: 'window_matrix', legacy_matrices: 'window_matrix', matrix_profiles: 'matrix_profile',
  models: 'model', classifiers: 'model', window_sets: 'window_set', encodings: 'encoding', library_seed: 'drop_motif_store', catalogue: 'catalogue_spreadsheet', hpc_results: 'hpc_result',
}

function Body({ data, reload }: { data: Data; reload: () => void }) {
  const s = useSettingsPage('storage-backups')
  const { push } = useToast()
  const [state] = useQueryState('state', '')
  const [modal, setModal] = useQueryState('modal', '')
  const [scan, setScan] = useQueryState('scan', '')
  const [backingUp, setBackingUp] = useState(false)
  const [history, setHistory] = useState(data.history)
  const tokens = s.list('tokens')
  const freeGb = state === 'low-disk' ? 38 : data.freeGb
  const lowDisk = freeGb < s.num('warn_gb')

  const backupNow = async () => {
    setBackingUp(true)
    try {
      const r = await postBackup()
      setHistory(h => [backupRow({ name: r.path.split(/[\\/]/).pop() ?? r.path, path: r.path, bytes: r.bytes, mtime: Date.now() / 1000, current: false }), ...h])
      push({ text: `Backed up · ${r.path} · ${r.mode === 'sandbox' ? 'sandbox: a copy of the copy, under the runtime dir' : 'DATA/db/backups'}` })
    } catch (e) { push({ text: `Backup failed · ${e instanceof ApiError ? e.message : String(e)}`, kind: 'error' }) } finally { setBackingUp(false) }
  }

  return (
    <>
      {lowDisk && <Callout tone="amber" icon="alert-triangle" testid="low-disk">
        {freeGb} GB free is below the {s.num('warn_gb')} GB warning — a warning is shown in the header and before any large job.
      </Callout>}

      <SectionCard title="Roots" subtitle={`${freeGb} GB free on this disk · ${data.mode === 'sandbox' ? 'sandbox: the database and results roots are the runtime copies' : 'project mode: the real roots'}`} testid="roots-card"
        footer={<span className="s-note">scan lists what a root holds, registered or not (docs/DATA_REGISTRATION.md) · pull copies finished results from the cluster's return path
          (<button type="button" className="k-link" onClick={() => navigate('settings/compute-hpc')}>Compute &amp; HPC</button>) into HPC/results</span>}>
        <Table rows={data.roots} rowKey={r => r.id} testid="roots-table" dense
          columns={[
            { key: 'root', header: 'root', width: '17%', render: r => <span className="mono" style={{ fontWeight: 600 }}>{r.root}</span> },
            {
              key: 'path', header: 'path', width: '35%', render: r => r.locked
                ? <LockedField reason="the open database; chosen by the mode, not a setting" width="100%">{r.path}</LockedField>
                : (
                  <span className={s.dirty(`root.${r.id}`) ? 'unsaved' : undefined} style={{ display: 'block' }} id={r.id === 'hpc_results' ? 'f-manifest-inbox' : undefined}>
                    <TextField value={s.str(`root.${r.id}`)} onChange={v => s.set(`root.${r.id}`, v)} size="sm" block testid={`root-${r.id}`} />
                  </span>
                ),
            },
            { key: 'inuse', header: 'in use', width: '16%', render: r => <span className={`mono small${r.in_use === 'absent' ? ' muted' : ''}`}>{r.in_use}</span> },
            {
              key: 'actions', header: 'actions', width: '16%', render: r => (
                <span style={{ display: 'flex', gap: 8 }}>
                  {r.actions.map(a => (
                    <Button key={a} variant="link" size="sm" testid={`action-${r.id}-${a.replace(/\s/g, '-')}`}
                      onClick={() => {
                        if (a === 'scan') setScan(r.id)
                        else if (a === 'clear') navigate('settings/analysis-defaults?modal=clear-cache')
                        else if (a === 'back up') void backupNow()
                        else push({ text: `${a}: open ${r.path} in your file manager · the web UI cannot open a folder`, ttlMs: 3000 })
                      }}>{a}</Button>
                  ))}
                </span>
              ),
            },
            { key: 'note', header: '', width: '16%', render: r => <span className="muted small">{r.note ?? ''}</span> },
          ]} />
      </SectionCard>

      <SectionCard title="Naming convention" subtitle="for files written by stages" testid="naming-card">
        <Row label="tokens" dot={s.differs('tokens')} unsaved={s.dirty('tokens')} testid="tokens-row" wide>
          <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            {tokens.map(t => (
              <Chip key={t} tone="blue" onRemove={tokens.length > 1 ? () => s.set('tokens', tokens.filter(x => x !== t)) : undefined}
                removeLabel={`remove ${t}`} testid={`token-${t.replace(/[<>]/g, '')}`}>{t}</Chip>
            ))}
            <AddToken available={[...data.tokens, ...data.extraTokens].filter(t => !tokens.includes(t))} onAdd={t => s.set('tokens', [...tokens, t])} />
          </span>
        </Row>
        <Row label="preview" testid="preview-row" wide caption="">
          <code className="k-code-inline mono" data-testid="naming-preview" style={{ background: '#1f2937', color: '#e5e7eb', padding: '6px 10px', borderRadius: 6 }}>{namingPreview(tokens)}</code>
          <span className="s-note">the hash is the recipe prefix, so a file name says which settings made it · the real names in use today are in docs/DATA_REGISTRATION.md</span>
        </Row>
      </SectionCard>

      <SectionCard title="Backups" subtitle={`the database, settings and hand edits · ${data.backupsDir}`} testid="backups-card"
        actions={<Badge tone={history[0]?.state === 'ok' ? 'green' : 'amber'} testid="last-backup">{history[0] ? `last backup ${history[0].when} · ${history[0].state}` : 'no backup yet'}</Badge>}>
        <Row label="back up the database" dot={s.differs('backup_on')} unsaved={s.dirty('backup_on') || s.dirty('backup_every') || s.dirty('backup_at')} testid="schedule-row"
          caption="the database is small; bulk arrays are not copied · a scheduled backup is a setting only: nothing runs while the bridge is down">
          <Toggle checked={s.bool('backup_on')} onChange={v => s.set('backup_on', v)} testid="backup-on" />
          <SelectField value={s.str('backup_every')} onChange={v => s.set('backup_every', v)} width={120} testid="backup-every"
            disabled={!s.bool('backup_on')} disabledReason={!s.bool('backup_on') ? 'turn backups on to set a schedule' : undefined}
            options={['hourly', 'daily', 'weekly'].map(o => ({ value: o, label: o }))} />
          <span className="mono small">at</span>
          <TextField value={s.str('backup_at')} onChange={v => s.set('backup_at', v)} width={90} testid="backup-at"
            disabled={!s.bool('backup_on')} disabledReason={!s.bool('backup_on') ? 'turn backups on to set a time' : undefined} />
        </Row>
        <Row label="to" dot={s.differs('backup_to')} unsaved={s.dirty('backup_to')} testid="backup-to-row" caption="a path on this machine · the --project start always writes to DATA/db/backups first">
          <TextField value={s.str('backup_to')} onChange={v => s.set('backup_to', v)} width={260} testid="backup-to" />
        </Row>
        <Row label="keep" id="f-keep" dot={s.differs('keep')} unsaved={s.dirty('keep')} testid="keep-row"
          caption="recordings and bulk arrays are not copied — back those up with the lab's storage">
          <NumberField value={s.num('keep')} min={1} max={365} integer unit="backups" width={130} onValid={v => s.set('keep', v)} testid="keep" />
        </Row>
        <Row label="include project settings" dot={s.differs('include_settings')} unsaved={s.dirty('include_settings')} testid="include-settings-row"
          caption="the settings table is in the database file, so a restore brings this page back too">
          <Toggle checked={s.bool('include_settings')} onChange={v => s.set('include_settings', v)} testid="include-settings" />
        </Row>
        <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
          <Button icon="download" testid="backup-now" loading={backingUp} disabled={backingUp} disabledReason={backingUp ? 'backing up…' : undefined} onClick={() => void backupNow()}>Back up now</Button>
          <Button icon="undo" testid="open-restore" onClick={() => setModal('restore')}>Restore…</Button>
          {backingUp && <ProgressBar indeterminate width={220} testid="backup-progress" label="sqlite backup API…" />}
        </div>
      </SectionCard>

      <SectionCard title="Disk" testid="disk-card">
        <Row label="warn when free space falls below" dot={s.differs('warn_gb')} unsaved={s.dirty('warn_gb')} testid="warn-gb-row"
          caption="a warning in the header and before any large job">
          <NumberField value={s.num('warn_gb')} min={1} max={1000} integer unit="GB" width={110} onValid={v => s.set('warn_gb', v)} testid="warn-gb" />
        </Row>
      </SectionCard>

      <Modal open={modal === 'restore'} onClose={() => setModal('')} title="Restore a backup" size="md" testid="restore-modal"
        footerNote="a restore replaces the database file while the bridge is stopped: copy the backup over DATA/db/annotations.sqlite by hand · bulk arrays are untouched"
        footer={<Button onClick={() => setModal('')}>Close</Button>}>
        {history.length ? (
          <Table rows={history} rowKey={h => h.path} dense testid="restore-table"
            columns={[
              { key: 'when', header: 'when', width: '22%', render: h => <span className="mono">{h.when}{h.current && <span style={{ marginLeft: 6 }}><Badge tone="blue">this start</Badge></span>}</span> },
              { key: 'path', header: 'path', width: '48%', render: h => <span className="mono small">{h.path}</span> },
              { key: 'size', header: 'size', width: '15%' },
              { key: 'state', header: 'state', width: '15%', render: h => <Badge tone={h.state === 'ok' ? 'green' : 'red'}>{h.state}</Badge> },
            ]} />
        ) : <span className="muted small" data-testid="restore-empty">No backup in {data.backupsDir} yet · a --project start writes one; Back up now writes one here.</span>}
      </Modal>

      <ScanModal rootId={scan} roots={data.roots} onClose={() => setScan('')} onChanged={reload} />
    </>
  )
}

function ScanModal({ rootId, roots, onClose, onChanged }: { rootId: string; roots: StorageRoot[]; onClose: () => void; onChanged: () => void }) {
  const kind = KIND_OF[rootId]
  const root = roots.find(r => r.id === rootId)
  const { push } = useToast()
  const rd = useSourced(async () => ({ data: kind ? await getRegistry<RegisteredRecording | RegisteredArtifact>(kind) : null, source: 'live' as const }), [kind])
  const open = Boolean(rootId)
  const reg = rd.data?.registered ?? []
  const cands = (rd.data?.candidates ?? []).filter((c: Candidate) => !c.registered)
  const [busy, setBusy] = useState<string | null>(null)
  /* one check result per candidate, so checking a second file never hides the first's verdict (critic P1) */
  const [reports, setReports] = useState<Record<string, CheckReport>>({})
  const [checked, setChecked] = useState<string>('')
  const report = checked ? reports[checked] ?? null : null
  /* recordings and raw files register on Datasets (they need fs / layout answers); everything else registers here */
  const registersHere = Boolean(kind) && kind !== 'recording' && kind !== 'raw'
  const runCheck = async (c: Candidate) => {
    setBusy(c.path); setChecked(c.path)
    try { const r = await checkCandidate(kind, c.path); setReports(x => ({ ...x, [c.path]: r })) } catch (e) { push({ text: e instanceof ApiError ? e.message : String(e), kind: 'error' }) } finally { setBusy(null) }
  }
  const doRegister = async (c: Candidate) => {
    setBusy(c.path)
    try {
      const r = await registerCandidate(kind, c.path)
      push({ text: `Registered ${r.name} · ${r.table} id ${r.id}${r.warnings.length ? ` · ${r.warnings.length} warning${r.warnings.length === 1 ? '' : 's'}` : ''} · ${r.note}` })
      setReports(x => { const y = { ...x }; delete y[c.path]; return y }); setChecked(''); rd.reload(); onChanged()
    } catch (e) { push({ text: e instanceof ApiError ? e.message : String(e), kind: 'error' }) } finally { setBusy(null) }
  }
  const factsOf = (c: Candidate) => Object.entries(c.facts)
    .filter(([k, v]) => ['fs', 'n_channels', 'n_samples', 'format', 'stem', 'channel', 'window_min', 'bytes', 'n_motifs', 'recipe_hash'].includes(k) && v != null)
    .map(([k, v]) => `${k} ${String(v)}`).join(' · ')
  return (
    <Modal open={open} onClose={onClose} title={root ? `${root.root} · ${root.path}` : 'scan'} size="lg" testid="scan-modal"
      footerNote={kind ? (registersHere ? `registry kind ${kind} · check, then register — the same POST /api/registry/${kind}/register a script would call (docs/DATA_REGISTRATION.md)` : `registry kind ${kind} · recordings and raw files register on Datasets › Import a recording`) : 'this root has no registry kind'}
      footer={<><Button onClick={onClose}>Close</Button><Button onClick={() => { rd.reload(); onChanged() }} icon="refresh">Rescan</Button></>}>
      {!kind && <span className="muted small">nothing to scan here</span>}
      {kind && rd.loading && <ProgressBar indeterminate label="scanning…" testid="scan-progress" />}
      {kind && rd.error && <span className="small" style={{ color: 'var(--red)' }}>{rd.error.message}</span>}
      {kind && rd.data && (
        <>
          <div className="s-card-sub" style={{ marginBottom: 6 }}>{reg.length} registered · {cands.length} on disk, not registered · scanned in {rd.data.scan_ms.toFixed(0)} ms</div>
          {cands.length > 0 && <Table rows={cands} rowKey={(c: Candidate) => c.path} dense testid="scan-candidates" highlighted={checked}
            columns={[
              { key: 'name', header: 'not registered', width: '34%', render: (c: Candidate) => <span className="mono">{c.name}</span> },
              { key: 'facts', header: 'facts', width: '30%', render: (c: Candidate) => <span className="small muted">{factsOf(c)}</span> },
              {
                key: 'warn', header: 'check', width: '16%', render: (c: Candidate) => reports[c.path]
                  ? <Badge tone={reports[c.path].ok ? 'green' : 'red'} testid={`scan-verdict-${c.name}`}>{reports[c.path].ok ? `passes${reports[c.path].warnings.length ? ` · ${reports[c.path].warnings.length} ⚠` : ''}` : `${reports[c.path].checks.filter(x => !x.ok).length} fail`}</Badge>
                  : c.warnings.length ? <span className="small" style={{ color: 'var(--amber)' }} title={c.warnings.join('\n')}>{c.warnings.length} warning{c.warnings.length === 1 ? '' : 's'}</span> : null,
              },
              {
                key: 'actions', header: '', width: '20%', render: (c: Candidate) => registersHere ? <span style={{ display: 'flex', gap: 8 }}>
                  <Button variant="link" size="sm" testid={`scan-check-${c.name}`} loading={busy === c.path} onClick={() => void runCheck(c)}>{reports[c.path] ? 'show' : 'check'}</Button>
                  <Button variant="link" size="sm" testid={`scan-register-${c.name}`} disabled={!reports[c.path]?.ok || busy === c.path}
                    disabledReason={reports[c.path] && !reports[c.path].ok ? 'a check fails' : 'run the check first'} onClick={() => void doRegister(c)}>register</Button>
                </span> : <span className="muted small">register on Datasets</span>,
              },
            ]} />}
          {report && <div style={{ marginTop: 8 }} data-testid="scan-checks">
            <Checklist items={[...report.checks.map(c => ({ label: `${c.name} · ${c.detail}`, state: c.ok ? 'pass' as const : 'fail' as const })), ...report.warnings.map(w => ({ label: w, state: 'warn' as const }))]} />
          </div>}
          {reg.length > 0 && <Table rows={reg} rowKey={(r: RegisteredRecording | RegisteredArtifact) => String(r.id)} dense testid="scan-registered"
            columns={[
              { key: 'name', header: 'registered', width: '40%', render: r => <span className="mono">{r.name}</span> },
              { key: 'id', header: 'id', width: '10%', render: r => <span className="mono small">{r.id}</span> },
              { key: 'path', header: 'path', width: '50%', render: r => <span className="mono small muted">{'path' in r ? r.path : r.dir}</span> },
            ]} />}
        </>
      )}
    </Modal>
  )
}

function AddToken({ available, onAdd }: { available: string[]; onAdd: (t: string) => void }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button ref={ref} variant="link" size="sm" testid="add-token" disabled={!available.length}
        disabledReason={!available.length ? 'every token is already in the name' : undefined} onClick={() => setOpen(o => !o)}>+ token</Button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} title="Add a token" width={220} testid="add-token-popover">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {available.map(t => <button key={t} type="button" className="s-hit mono" onClick={() => { onAdd(t); setOpen(false) }} data-testid={`token-option-${t.replace(/[<>]/g, '')}`}>{t}</button>)}
        </div>
      </Popover>
    </>
  )
}

export type { StorageRoot }
