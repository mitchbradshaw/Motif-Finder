/* jobs.cluster — `#/jobs/cluster/<jobId>` (frame jobs-4, spec §7c.4, §9.6): a cluster job whose
 * status is marked by hand, the reminder past 3× its estimate, the SLURM script, and the manifest
 * inbox beside it. The site never changes a cluster job's status on its own. */
import { useEffect, type ReactNode } from 'react'
import { Badge, Button, CodeBlock, EmptyState, Icon, InfoTip, Page, SelectField, TextField, useDemoState, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { getJobsOverview, getManifestInbox, getProfiles, type ClusterJob } from '../api/jobs'
import { navigate } from '../state'
import { Header } from '../shell/Header'
import { BackToAll, ClusterBadge, LoadFailed, Loading, ManifestInbox, NewScriptModal, Section, WsTag } from './chrome'
import { isOverdue, markCluster, overrunLabel, patchCluster, useMergedJobs, useInboxPending } from './store'

const STEPS: { key: 'created' | 'submitted' | 'running' | 'finished'; label: string }[] = [
  { key: 'created', label: 'script created' }, { key: 'submitted', label: 'submitted' },
  { key: 'running', label: 'running' }, { key: 'finished', label: 'finished' },
]

export function ClusterPage({ jobId }: { jobId: string }) {
  const ov = useSourced(getJobsOverview, [])
  const inbox = useSourced(getManifestInbox, [])
  const profiles = useSourced(getProfiles, [])
  const merged = useMergedJobs(ov.data)
  const [modal, setModal] = useQueryState('modal', '')
  const [pending, setPending] = useInboxPending()
  const [inboxQ] = useQueryState('inbox', '')
  const [snoozed, setSnoozed] = useDemoState<Record<string, boolean>>('jobs.snoozed', () => ({}))

  // deep link: ?inbox=pending shows the manifest that would arrive for this job
  useEffect(() => { if (inboxQ === 'pending' && pending === 'none') setPending('arrived') }, [inboxQ, pending, setPending])

  if (ov.error) return <Shell id={jobId} sub="could not read"><LoadFailed what={`cluster job ${jobId}`} error={ov.error} onRetry={ov.reload} /></Shell>
  if (!merged) return <Shell id={jobId} sub="reading…"><Loading /></Shell>

  const job = merged.cluster.find(j => j.id === jobId) as (ClusterJob & { snoozedUntil?: string; replacedBy?: string; note?: string }) | undefined
  if (!job) return (
    <Shell id={jobId} sub="not a cluster job">
      <EmptyState bordered icon="alert-triangle" testid="cluster-unknown" title={`No cluster job called “${jobId}”`}
        caption="Cluster jobs have ids like j-0214. A job created elsewhere in this session appears here as soon as its script is made."
        action={<><Button onClick={() => navigate('jobs/cluster/j-0214')}>Open j-0214</Button> <Button onClick={() => navigate('jobs?filter=cluster')}>All cluster jobs</Button></>} />
    </Shell>
  )

  const overdue = isOverdue(job) && !snoozed[job.id]
  const stepIndex = job.status === 'finished' ? 3 : job.status === 'running' ? 2 : job.status === 'submitted' ? 1 : 0
  const failed = job.status === 'failed'
  const runs = merged.runs.map(r => ({ id: r.run.id, stage: r.run.pausedAt, label: r.result !== 'arrived' ? 'not in its root yet' : r.run.clusterJob ? `result arrived ${r.run.result.foundAt}` : 'result in place' }))

  return (
    <>
      <Header workspace="Jobs" page={job.id} subtitle={`${job.sub} · ${job.profile.split(' · ')[0]}`} search="Search jobs, runs, queues" demo={ov.source === 'demo'} />
      <Page maxWidth={1420}>
        <BackToAll />
        <div className="jb-run-title" data-testid="cluster-title">
          <h1>{job.id}</h1>
          <ClusterBadge job={job} overdue={overdue} />
          <span className="jb-mono jb-small jb-muted" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <WsTag ws={job.workspace} />· {job.title}
          </span>
          {job.isNew && <Badge status="new">new · this session</Badge>}
          <span className="jb-spacer" />
          <Button icon="external" testid="cluster-open-workspace" onClick={() => navigate(job.openIn.route)}>{job.openIn.label}</Button>
        </div>

        <div className="jb-cluster-grid">
          <Section testid="cluster-status" tone={failed ? 'red' : undefined}
            title={<>Status<span className="jb-mono jb-small jb-muted" style={{ fontWeight: 400 }}>marked by hand · the site cannot see the cluster queue</span>
              <InfoTip title="Marked by hand">There is no live connection to SLURM. Each step is a note you make here; <i>finished</i> is also set when the job's manifest is imported (§7c.4).</InfoTip></>}>
            <div className="jb-status-pills" data-testid="status-pills">
              {STEPS.map((s, i) => {
                const done = i < stepIndex || (i === 3 && job.status === 'finished')
                const current = i === stepIndex && !done
                return (
                  <span key={s.key} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <span className={`jb-status-pill ${done ? 'done' : current ? (overdue ? 'current' : 'current blue') : ''} ${failed && i === 3 ? 'failed' : ''}`} data-testid={`pill-${s.key}`}>
                      {done && <Icon name="check" size={11} />}{failed && i === 3 ? 'failed' : s.label}
                    </span>
                    {i < 3 && <Icon name="chevron-right" size={12} className="jb-muted" />}
                  </span>
                )
              })}
            </div>
            <div className="jb-status-times">
              <span>{job.marks.created} · automatic</span>
              <span>{job.marks.submitted ? `${job.marks.submitted} · marked` : 'not submitted yet'}</span>
              <span>{job.marks.running ? `${job.marks.running} · marked` : 'not running yet'}</span>
              <span>{job.marks.failed ? `${job.marks.failed} · marked failed` : job.marks.finished ? `${job.marks.finished} · marked` : 'set when the manifest arrives'}</span>
            </div>

            {overdue && (
              <div className="jb-reminder" data-testid="overdue-reminder" role="status">
                <div className="t"><Icon name="clock" size={14} />Marked running for {job.runningForH} h — {overrunLabel(job)} the {job.estimateLabel.split(' · ')[0]} estimate</div>
                <div className="d">Check the cluster. The site never changes a cluster job's status on its own.</div>
                <div className="jb-row" style={{ marginTop: 4 }}>
                  <Button icon="check-circle" testid="mark-finished" onClick={() => markCluster(job.id, 'finished')}>Mark finished</Button>
                  <Button icon="x-circle" testid="mark-failed" onClick={() => markCluster(job.id, 'failed')}>Mark failed</Button>
                  <Button variant="link" testid="snooze" onClick={() => setSnoozed({ ...snoozed, [job.id]: true })}>Still running · remind me in 3 h</Button>
                </div>
              </div>
            )}
            {!overdue && snoozed[job.id] && (
              <div className="jb-reminder grey" data-testid="snoozed-reminder">
                <div className="t"><Icon name="clock" size={14} />Reminder snoozed · it comes back in 3 h</div>
                <div className="d">{job.id} is still marked running at {overrunLabel(job)} its estimate. Nothing changed on the cluster.</div>
                <div className="jb-row" style={{ marginTop: 4 }}>
                  <Button size="sm" icon="check-circle" testid="mark-finished" onClick={() => markCluster(job.id, 'finished')}>Mark finished</Button>
                  <Button size="sm" icon="x-circle" testid="mark-failed" onClick={() => markCluster(job.id, 'failed')}>Mark failed</Button>
                  <Button size="sm" variant="link" onClick={() => setSnoozed({ ...snoozed, [job.id]: false })}>Bring it back now</Button>
                </div>
              </div>
            )}
            {failed && (
              <div className="jb-reminder red" data-testid="failed-reminder" role="alert">
                <div className="t"><Icon name="x-circle" size={14} />Marked failed {job.marks.failed}</div>
                <div className="d">{job.error ?? 'marked failed by hand'}</div>
                <div className="jb-row" style={{ marginTop: 4 }}>
                  <Button icon="terminal" variant="cluster" testid="new-script" onClick={() => setModal('new-script')}>New SLURM script</Button>
                  {job.replacedBy && <Button variant="link" onClick={() => navigate(`jobs/cluster/${job.replacedBy}`)}>replaced by {job.replacedBy} →</Button>}
                  {job.forRun && <Button variant="link" icon="external" onClick={() => navigate(`jobs/run/${job.forRun}`)}>Open {job.forRun}</Button>}
                </div>
              </div>
            )}
            {job.status === 'finished' && (
              <div className="jb-reminder grey" data-testid="finished-note">
                <div className="t"><Icon name="check-circle" size={14} className="jb-green" />Finished · {job.importedAt ? `manifest imported ${job.importedAt}` : `marked ${job.marks.finished}`}</div>
                <div className="d">Results are in {job.openIn.label.replace('Open in ', '')}. Importing a manifest also marks the job finished.</div>
              </div>
            )}
            {(job.status === 'queue' || job.status === 'submitted') && (
              <div className="jb-reminder grey" data-testid="next-step-note">
                <div className="t"><Icon name="terminal" size={14} />{job.status === 'queue' ? 'The script exists; nothing is submitted' : 'Marked submitted — waiting for the cluster to start it'}</div>
                <div className="d">Run it on the cluster by hand, then mark the next step here.</div>
                <div className="jb-row" style={{ marginTop: 4 }}>
                  <Button size="sm" icon="check" testid="mark-submitted" disabled={job.status === 'submitted'} disabledReason="already marked submitted" onClick={() => markCluster(job.id, 'submitted')}>Mark submitted</Button>
                  <Button size="sm" icon="play" testid="mark-running" onClick={() => markCluster(job.id, 'running')}>Mark running</Button>
                </div>
              </div>
            )}

            <div className="jb-form" data-testid="cluster-form">
              <span className="k">cluster job id</span>
              <TextField value={job.clusterJobId} onChange={v => patchCluster(job.id, { clusterJobId: v })} placeholder="the SLURM job id, e.g. 4418093" block testid="cluster-job-id" />
              <span className="k">profile</span>
              <SelectField value={job.profile} onChange={v => patchCluster(job.id, { profile: v })} testid="cluster-profile"
                options={(profiles.data ?? [job.profile]).map(p => ({ value: p, label: p }))} />
              <span className="k">results return from</span>
              <span className="jb-locked" data-testid="cluster-return"><Icon name="lock" size={12} /><span>{job.returnFrom} → {job.returnTo}</span></span>
              <span className="k">estimate</span>
              <span className="jb-locked" data-testid="cluster-estimate"><Icon name="lock" size={12} /><span>{job.estimateLabel}</span></span>
            </div>
            <div className="jb-script-head"><span className="jb-label">script</span></div>
            <CodeBlock code={job.script} filename={job.scriptName} testid="cluster-script" maxHeight={200} />
          </Section>

          <Section testid="cluster-inbox"
            title={<><Icon name="inbox" size={15} />Manifest inbox<span className="jb-spacer" />
              <Badge status="imported">{(inbox.data?.manifests.filter(m => m.imported).length ?? 0) + (pending === 'imported' ? 1 : 0)} imported</Badge></>}>
            {inbox.error && <LoadFailed what="the manifest inbox" error={inbox.error} onRetry={inbox.reload} />}
            {inbox.loading && <Loading height={200} testid="cluster-inbox-loading" />}
            {inbox.data && <ManifestInbox data={inbox.data} runs={runs} testid="cluster-inbox-body" />}
          </Section>
        </div>

        <NewScriptModal open={modal === 'new-script'} onClose={() => setModal(null)} job={job} forRun={job.forRun} profiles={profiles.data ?? []} knownIds={merged.allIds} />
      </Page>
    </>
  )
}

function Shell({ id, sub, children }: { id: string; sub: string; children: ReactNode }) {
  return (
    <>
      <Header workspace="Jobs" page={id} subtitle={sub} search="Search jobs, runs, queues" />
      <Page maxWidth={1420}><BackToAll />{children}</Page>
    </>
  )
}
