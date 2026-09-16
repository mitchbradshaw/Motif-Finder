/* Jobs shared chrome: the pieces all four Jobs pages draw — loading and loud-failure cards, the
 * "‹ All jobs" link, workspace icons, the stage/status pills, the checks list, the manifest inbox
 * body (frame jobs-4, also shown in the All-jobs drawer) and the New SLURM script modal. */
import type { ReactNode } from 'react'
import {
  Badge, Button, CodeBlock, Icon, InfoTip, Modal, SelectField, TextField, useDemoState, useNotWired, type IconName,
} from '../kit'
import { navigate } from '../state'
import { WORKSPACE_ICON, type CheckState, type ClusterJob, type InboxData, type ResultCheck, type StageState, type Workspace } from '../api/jobs'
import { markCluster, nextJobId, nowHM, patchCluster, setInboxPending, useInboxPending } from './store'
import { recordDemoWrite } from '../kit'

/* ------------------------------------------------------------------ small shared atoms */

export const Loading = ({ height = 320, testid = 'jobs-loading' }: { height?: number; testid?: string }) => (
  <div className="jb-loading" style={{ minHeight: height }} data-testid={testid} aria-label="loading">reading jobs…</div>
)

/** Loud failure (brief): a read that throws renders the error, never a blank. */
export function LoadFailed({ what, error, onRetry }: { what: string; error: Error; onRetry?: () => void }) {
  return (
    <div className="error-card" role="alert" data-testid="jobs-load-failed">
      <h3>Could not read {what}</h3>
      <div className="mono small" style={{ color: 'var(--red)' }}>{error.message}</div>
      {onRetry && <div style={{ marginTop: 8 }}><Button size="sm" icon="refresh" onClick={onRetry}>Retry</Button></div>}
    </div>
  )
}

export function BackToAll({ testid = 'back-to-all' }: { testid?: string }) {
  return <button type="button" className="jb-back" data-testid={testid} onClick={() => navigate('jobs')}>‹ All jobs</button>
}

/** "stage 4" for one, "stages 3–5" for several — never "stages 4–4". */
export const rangeLabel = (a: number, b: number, word = 'stage') => (a >= b ? `${word} ${a}` : `${word}s ${a}–${b}`)

export const wsIcon = (w: Workspace): IconName => WORKSPACE_ICON[w] ?? 'branch'

/** Id prefix → the workspace that owns it (§0: j- cluster · a- Analyse · r- Discovery · l- Library · q- Review). */
export function idKind(id: string): 'cluster' | 'analyse' | 'discovery' | 'library' | 'queue' {
  const c = id[0]
  return c === 'j' ? 'cluster' : c === 'a' ? 'analyse' : c === 'r' ? 'discovery' : c === 'l' ? 'library' : 'queue'
}

export function WsTag({ ws, testid }: { ws: Workspace; testid?: string }) {
  return <span className="ws" data-testid={testid}><Icon name={wsIcon(ws)} size={12} />{ws}</span>
}

/** One stage pill in the All-jobs rail (frame 1: "2 Bandpass filter · cached"). */
export function StagePill({ n, name, state, note }: { n: number; name: string; state: StageState | 'arrived' | 'running'; note?: string }) {
  const icon: IconName = state === 'done' || state === 'cached' || state === 'arrived' ? 'check-circle' : state === 'cluster' ? 'hourglass' : state === 'running' ? 'play' : 'circle-dashed'
  return (
    <span className={`jb-stage-pill ${state}`} data-testid={`stage-pill-${n}`}>
      <Icon name={icon} size={12} />{n} {name}{note ? ` · ${note}` : ''}
    </span>
  )
}

const CHECK_ICON: Record<CheckState, IconName> = { pass: 'check-circle', fail: 'x-circle', warn: 'alert-triangle', pending: 'circle-dashed' }

/** "checks before the run can continue" (frames 2 and 3): label left, evidence right-aligned. */
export function Checks({ checks, testid }: { checks: ResultCheck[]; testid?: string }) {
  return (
    <div className="jb-checks" data-testid={testid}>
      {checks.map(c => (
        <div key={c.key} className={`jb-check ${c.state}`} data-testid={`check-${c.key}`} data-state={c.state}>
          <Icon name={CHECK_ICON[c.state]} size={14} className="ic" />
          <span className="lbl">{c.label}</span>
          <span className="det">{c.detail}</span>
        </div>
      ))}
    </div>
  )
}

export function LockedPath({ path, testid, icon = 'lock' }: { path: string; testid?: string; icon?: IconName }) {
  return <span className="jb-path" data-testid={testid} title={path}><Icon name={icon} size={12} /><span>{path}</span></span>
}

/* ------------------------------------------------------------------ manifest inbox (§7c.4, §9.6) */

/** The inbox body: watched folder, each arrived manifest with its contents and import checks, then
 *  the stage results waiting for a paused run. Rendered in frame 4's right card and in the All-jobs drawer. */
export function ManifestInbox({ data, runs, testid = 'manifest-inbox' }: {
  data: InboxData
  runs: { id: string; stage: number; label: string }[]
  testid?: string
}) {
  const [pending, setPending] = useInboxPending()
  const [lastLooked, setLastLooked] = useDemoState<string>('jobs.inbox.looked', () => data.lastLooked)
  const notWired = useNotWired()
  const imported = data.manifests.filter(m => m.imported).length + (pending === 'imported' ? 1 : 0)
  const shown = pending === 'none' ? data.manifests : [{ ...data.pending, imported: pending === 'imported' }, ...data.manifests]

  return (
    <div data-testid={testid}>
      <div className="jb-row">
        <span className="jb-mono jb-small jb-muted">watching {data.watching} every {data.every} · last looked {lastLooked}</span>
        <span className="jb-spacer" />
        <Button size="sm" variant="link" icon="refresh" testid="inbox-look-again"
          onClick={() => { setLastLooked('just now'); if (pending === 'none') setPending('arrived') }}>Look again</Button>
      </div>
      {shown.map(m => (
        <div key={m.jobId} className={`jb-inbox-manifest ${m.imported ? 'green' : 'amber'}`} data-testid={`manifest-${m.jobId}`}>
          <div className="h">
            <b>{m.jobId}</b> {m.title}<span className="at">{m.at}</span>
          </div>
          <div className="jb-label">contains</div>
          {m.contains.map(c => <div key={c} className="jb-inbox-item"><Icon name="file" size={12} className="ic" />{c}</div>)}
          <div className="jb-label" style={{ marginTop: 4 }}>import checks</div>
          {m.checks.map(c => <div key={c} className="jb-inbox-item check"><Icon name="check-circle" size={12} className="ic" />{c}</div>)}
          <div className="jb-row" style={{ marginTop: 6 }}>
            {m.imported ? (
              <>
                <Button size="sm" icon="check" disabled disabledReason="already imported — a manifest is imported once" testid={`import-${m.jobId}`}>Imported</Button>
                <span className="jb-mono jb-small jb-muted">imported · results in {m.resultsLabel}</span>
                <span className="jb-spacer" />
                <Button size="sm" variant="link" icon="external" onClick={() => navigate(m.resultsRoute)}>Open {m.resultsLabel}</Button>
              </>
            ) : (
              <>
                <Button size="sm" variant="primary" icon="download" loading={pending === 'importing'} testid={`import-${m.jobId}`}
                  onClick={() => {
                    setPending('importing')
                    window.setTimeout(() => { setPending('imported'); markCluster(m.jobId, 'finished', 'manifest imported'); patchCluster(m.jobId, { importedAt: nowHM() }) }, 1200)
                  }}>Import results</Button>
                <span className="jb-mono jb-small jb-muted">{pending === 'importing' ? 'running import checks…' : `arrived ${m.at} · not imported`}</span>
              </>
            )}
          </div>
        </div>
      ))}
      <div className="jb-label" style={{ marginTop: 12 }}>stage results for paused runs</div>
      <div className="jb-mono jb-small jb-muted">found in the inbox or already in their root (./PROFILES), then offered as Continue</div>
      {runs.map(r => (
        <div key={r.id} className="jb-stage-result" data-testid={`inbox-run-${r.id}`}>
          <Icon name="clock" size={13} className="ic" />
          <span><b>{r.id}</b> · stage {r.stage} · {r.label}</span>
          <Button size="sm" variant="link" testid={`inbox-open-${r.id}`} onClick={() => navigate(`jobs/run/${r.id}`)}>Open</Button>
        </div>
      ))}
      {!runs.length && <div className="jb-mono jb-small jb-muted" style={{ padding: '8px 0' }}>no stage result is waiting</div>}
      <div className="jb-row" style={{ marginTop: 10 }}>
        <span className="jb-mono jb-small jb-muted">{imported} imported</span>
        <span className="jb-spacer" />
        <Button size="sm" variant="link" icon="settings" onClick={() => notWired('Settings › Compute & HPC (inbox folder and interval)')}>Inbox settings</Button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ New SLURM script (frames 1, 2) */

/** "Create the script again" — a failed or cancelled cluster job is replaced by a new one, which Jobs then lists. */
export function NewScriptModal({ open, onClose, job, forRun, profiles, knownIds }: {
  open: boolean; onClose: () => void
  job: ClusterJob | null; forRun?: string; profiles: string[]; knownIds: string[]
}) {
  const [profile, setProfile] = useDemoState<string>('jobs.newscript.profile', () => job?.profile ?? profiles[0] ?? 'hpc-1 · cpu-array')
  const [note, setNote] = useDemoState<string>('jobs.newscript.note', () => '')
  const newId = nextJobId(knownIds)
  const script = job?.script ?? '#SBATCH --account=a_myco --partition=cpu_long\n#SBATCH --cpus-per-task=16 --mem=64G --time=12:00:00\nmodule load python/3.11 && conda activate cnn\npython -m pipeline.stage --out /scratch/$USER/cnn/out/' + newId

  const create = () => {
    recordDemoWrite('jobs', 'add-job', {
      id: newId, kind: forRun ? (forRun.startsWith('r-') ? 'discovery' : 'analyse') : 'cluster',
      title: job?.title ?? 'new cluster job', status: 'queue', detail: `script created ${nowHM()}${note ? ` · ${note}` : ''}`,
      for: forRun, profile, replaces: job?.id, script,
    })
    if (job) patchCluster(job.id, { replacedBy: newId })
    onClose()
    navigate(`jobs/cluster/${newId}`)
  }

  return (
    <Modal open={open} onClose={onClose} size="lg" testid="new-script-modal"
      title={<><Icon name="terminal" size={15} /> New SLURM script</>}
      subtitle={job ? `${job.id} ${job.title} · ${job.status}${forRun ? ` · for ${forRun}` : ''}` : 'a fresh cluster job for this stage'}
      footerNote={`the new job ${newId} replaces ${job?.id ?? 'the old one'}; the old job keeps its record`}
      footer={<><Button onClick={onClose} testid="new-script-cancel">Cancel</Button><Button variant="cluster" icon="terminal" onClick={create} testid="new-script-create">Create {newId}</Button></>}>
      <div className="jb-form" style={{ marginTop: 0 }}>
        <span className="k">new cluster job</span>
        <span className="jb-locked" data-testid="new-script-id"><Icon name="lock" size={12} /><span>{newId} · status “script created”, marked by hand from here on</span></span>
        <span className="k">profile</span>
        <SelectField value={profile} onChange={setProfile} options={profiles.map(p => ({ value: p, label: p }))} testid="new-script-profile" />
        <span className="k">note <InfoTip title="note">Kept with the job so you know why the script was made again — it is not sent to the cluster.</InfoTip></span>
        <TextField value={note} onChange={setNote} placeholder="why the script was made again…" block testid="new-script-note" />
      </div>
      <div className="jb-script-head"><span className="jb-label">script</span></div>
      <CodeBlock code={script} filename={`${newId}.sh`} maxHeight={170} testid="new-script-code" />
      <div className="jb-info-strip"><Icon name="info" size={13} />Creating the script does not submit it. Run it on the cluster by hand, then mark the job submitted here.</div>
    </Modal>
  )
}

/** Cancel a paused run (frame 1/2: cached stages are kept). */
export function CancelRunModal({ open, onClose, runId, kept, onConfirm }: {
  open: boolean; onClose: () => void; runId: string; kept: string; onConfirm: () => void
}) {
  return (
    <Modal open={open} onClose={onClose} size="sm" testid="cancel-run-modal"
      title={<><Icon name="x-circle" size={15} /> Cancel {runId}?</>}
      subtitle="the run stops where it is; nothing already computed is thrown away"
      footer={<><Button onClick={onClose} testid="cancel-run-keep">Keep the run</Button><Button variant="danger-solid" icon="x" onClick={() => { onConfirm(); onClose() }} testid="cancel-run-confirm">Cancel run</Button></>}>
      <div className="jb-mono" style={{ fontSize: 12, lineHeight: 1.6 }}>
        <div>Cached stages {kept} are kept for the next run of this template.</div>
        <div className="jb-muted" style={{ marginTop: 6 }}>Its cluster job is not cancelled on the cluster — the site cannot reach the queue. Cancel it there too if it is still running.</div>
      </div>
    </Modal>
  )
}

/** Status badge for a cluster job, coloured by §3 semantics. */
export function ClusterBadge({ job, overdue }: { job: ClusterJob; overdue?: boolean }) {
  if (job.status === 'failed') return <Badge status="failed" testid="cluster-status">failed · marked {job.marks.failed}</Badge>
  if (job.status === 'finished') return <Badge status="finished" testid="cluster-status">finished · imported {job.importedAt ?? job.marks.finished}</Badge>
  if (job.status === 'running') return <Badge status={overdue ? 'stale' : 'running'} testid="cluster-status">{overdue ? `running · ${(job.runningForH! / job.estimateH).toFixed(1)}× estimate` : `running · marked ${job.marks.running}`}</Badge>
  if (job.status === 'submitted') return <Badge status="queued" testid="cluster-status">submitted · marked {job.marks.submitted}</Badge>
  if (job.status === 'cancelled') return <Badge status="cancelled" testid="cluster-status">cancelled</Badge>
  return <Badge status="new" testid="cluster-status">script created {job.marks.created}</Badge>
}

export function Section({ title, extra, children, tone, testid }: { title: ReactNode; extra?: ReactNode; children: ReactNode; tone?: 'green' | 'amber' | 'red' | 'blue'; testid?: string }) {
  return (
    <div className={`jb-panel ${tone ?? ''}`} data-testid={testid}>
      <h3>{title}{extra}</h3>
      {children}
    </div>
  )
}
