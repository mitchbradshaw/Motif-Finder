/* Settings › Storage & backups (frame settings-11 · spec §9.11, B26).
 * Roots and their actions, the naming convention with a live preview, backups of the database,
 * settings and hand edits (bulk arrays are not copied), and the free-space warning. */
import { useState } from 'react'
import {
  Badge, Button, Callout, Chip, InfoTip, Modal, NumberField, Popover, ProgressBar, SectionCard, SelectField, Table,
  TextField, Toggle, useDemoState, useNotWired, useQueryState, useSim,
} from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getStorage, namingPreview, type StorageRoot } from '../api/settings'
import { LoadFailed, Loading, LockedField, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'
import { useRef } from 'react'

export function StoragePage() {
  const rd = useSourced(getStorage, [])
  return (
    <SettingsShell slug="storage-backups" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the storage roots" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getStorage>>['data']

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('storage-backups')
  const notWired = useNotWired()
  const [state, setState] = useQueryState('state', '')
  const [modal, setModal] = useQueryState('modal', '')
  const [scanning, setScanning] = useState<string | null>(null)
  const backup = useSim('settings.backup')
  const [history, setHistory] = useDemoState('settings.backupHistory', () => data.history)
  const tokens = s.list('tokens')
  const freeGb = state === 'low-disk' ? 38 : data.freeGb
  const lowDisk = freeGb < s.num('warn_gb')

  const runScan = (id: string) => { setScanning(id); window.setTimeout(() => setScanning(null), 1400) }

  return (
    <>
      {lowDisk && <Callout tone="amber" icon="alert-triangle" testid="low-disk">
        {freeGb} GB free is below the {s.num('warn_gb')} GB warning — a warning is shown in the header and before any large job.
      </Callout>}

      <SectionCard title="Roots" subtitle={`${freeGb} GB free on this disk`} testid="roots-card"
        footer={<span className="s-note">pull copies finished results from the cluster's return path
          (<button type="button" className="k-link" onClick={() => navigate('settings/compute-hpc')}>Compute &amp; HPC</button>) into the root</span>}>
        <Table rows={data.roots} rowKey={r => r.id} testid="roots-table" dense highlighted={scanning}
          columns={[
            { key: 'root', header: 'root', width: '17%', render: r => <span className="mono" style={{ fontWeight: 600 }}>{r.root}</span> },
            {
              key: 'path', header: 'path', width: '33%', render: r => r.locked
                ? <LockedField reason="templates live in the database, not on disk" width="100%">{r.path}</LockedField>
                : (
                  <span className={s.dirty(`root.${r.id}`) ? 'unsaved' : undefined} style={{ display: 'block' }} id={r.id === 'inbox' ? 'f-manifest-inbox' : undefined}>
                    <TextField value={s.str(`root.${r.id}`)} onChange={v => s.set(`root.${r.id}`, v)} size="sm" block testid={`root-${r.id}`} />
                  </span>
                ),
            },
            { key: 'inuse', header: 'in use', width: '10%', render: r => r.in_use },
            {
              key: 'actions', header: 'actions', width: '22%', render: r => (
                <span style={{ display: 'flex', gap: 8 }}>
                  {r.actions.map(a => (
                    <Button key={a} variant="link" size="sm" testid={`action-${r.id}-${a.replace(/\s/g, '-')}`}
                      onClick={() => {
                        if (a === 'scan') runScan(r.id)
                        else if (a === 'clear') navigate('settings/analysis-defaults?modal=clear-cache')
                        else notWired(`${a} ${s.str(`root.${r.id}`) || r.path}`)
                      }}>{a}</Button>
                  ))}
                </span>
              ),
            },
            { key: 'note', header: '', width: '18%', render: r => r.id === scanning ? <ProgressBar indeterminate size="sm" label="scanning…" testid="scan-progress" /> : <span className="muted small">{r.note ?? ''}</span> },
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
        <Row label="preview" testid="preview-row" wide
          caption="">
          <code className="k-code-inline mono" data-testid="naming-preview" style={{ background: '#1f2937', color: '#e5e7eb', padding: '6px 10px', borderRadius: 6 }}>{namingPreview(tokens)}</code>
          <span className="s-note">the hash is the recipe prefix, so a file name says which settings made it</span>
        </Row>
      </SectionCard>

      <SectionCard title="Backups" subtitle="the database, settings and hand edits" testid="backups-card"
        actions={<Badge tone={history[0]?.state === 'ok' ? 'green' : 'amber'} testid="last-backup">last backup {history[0]?.when} · {history[0]?.state}</Badge>}>
        <Row label="back up the database" dot={s.differs('backup_on')} unsaved={s.dirty('backup_on') || s.dirty('backup_every') || s.dirty('backup_at')} testid="schedule-row"
          caption="the database is small; bulk arrays are not copied">
          <Toggle checked={s.bool('backup_on')} onChange={v => s.set('backup_on', v)} testid="backup-on" />
          <SelectField value={s.str('backup_every')} onChange={v => s.set('backup_every', v)} width={120} testid="backup-every"
            disabled={!s.bool('backup_on')} disabledReason={!s.bool('backup_on') ? 'turn backups on to set a schedule' : undefined}
            options={['hourly', 'daily', 'weekly'].map(o => ({ value: o, label: o }))} />
          <span className="mono small">at</span>
          <TextField value={s.str('backup_at')} onChange={v => s.set('backup_at', v)} width={90} testid="backup-at"
            disabled={!s.bool('backup_on')} disabledReason={!s.bool('backup_on') ? 'turn backups on to set a time' : undefined} />
        </Row>
        <Row label="to" dot={s.differs('backup_to')} unsaved={s.dirty('backup_to')} testid="backup-to-row" caption="a path on this machine">
          <TextField value={s.str('backup_to')} onChange={v => s.set('backup_to', v)} width={260} testid="backup-to" />
        </Row>
        <Row label="keep" id="f-keep" dot={s.differs('keep')} unsaved={s.dirty('keep')} testid="keep-row"
          caption="recordings and bulk arrays are not copied — back those up with the lab's storage">
          <NumberField value={s.num('keep')} min={1} max={365} integer unit="backups" width={130} onValid={v => s.set('keep', v)} testid="keep" />
        </Row>
        <Row label="include project settings" dot={s.differs('include_settings')} unsaved={s.dirty('include_settings')} testid="include-settings-row"
          caption="a restore then brings back this page too">
          <Toggle checked={s.bool('include_settings')} onChange={v => s.set('include_settings', v)} testid="include-settings" />
        </Row>
        <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
          <Button icon="download" testid="backup-now" loading={backup.status === 'running' || backup.status === 'queued'}
            disabled={backup.status === 'running' || backup.status === 'queued'} disabledReason={backup.status === 'running' ? 'backing up…' : undefined}
            onClick={() => {
              setState('backup')
              backup.start({ steps: ['database', 'settings', 'hand edits'], stepMs: 500 })
              window.setTimeout(() => setHistory(h => [{ when: '16 Sep 12:04', size: '2.1 GB', state: 'ok' }, ...h]), 1700)
            }}>Back up now</Button>
          <Button icon="undo" testid="open-restore" onClick={() => setModal('restore')}>Restore…</Button>
          {(backup.status === 'running' || backup.status === 'queued') && <ProgressBar value={backup.fraction} width={220} testid="backup-progress" label={backup.steps[Math.max(0, backup.step)] ?? 'starting…'} />}
          {backup.status === 'done' && <span className="small" style={{ color: 'var(--green)' }} data-testid="backup-done">backed up (demo) · not wired yet: POST /api/backups</span>}
        </div>
      </SectionCard>

      <SectionCard title="Disk" testid="disk-card">
        <Row label="warn when free space falls below" dot={s.differs('warn_gb')} unsaved={s.dirty('warn_gb')} testid="warn-gb-row"
          caption="a warning in the header and before any large job">
          <NumberField value={s.num('warn_gb')} min={1} max={1000} integer unit="GB" width={110} onValid={v => s.set('warn_gb', v)} testid="warn-gb" />
        </Row>
      </SectionCard>

      <Modal open={modal === 'restore'} onClose={() => setModal('')} title="Restore a backup" size="md" testid="restore-modal"
        footerNote="a restore replaces the database, settings and hand edits · bulk arrays are untouched"
        footer={<>
          <Button onClick={() => setModal('')}>Cancel</Button>
          <Button variant="danger" testid="restore-confirm" onClick={() => { notWired('POST /api/backups/restore'); setModal('') }}>Restore</Button>
        </>}>
        <Table rows={history} rowKey={h => h.when} dense testid="restore-table"
          columns={[
            { key: 'when', header: 'when', width: '40%', render: h => <span className="mono">{h.when}</span> },
            { key: 'size', header: 'size', width: '30%' },
            { key: 'state', header: 'state', width: '30%', render: h => <Badge tone={h.state === 'ok' ? 'green' : 'red'}>{h.state}</Badge> },
          ]} />
      </Modal>
    </>
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
