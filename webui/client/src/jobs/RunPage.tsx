/* jobs.paused — `#/jobs/run/<runId>` (frame jobs-2, spec §7c.2, P24): where the run stopped, the
 * stage result and its checks, Continue from the next stage, and the other ways forward. The upload
 * modal (jobs.upload) is rendered on top of this page from `#/jobs/run/<id>/upload`. */
import type { ReactNode } from 'react'
import { Badge, Button, Callout, EmptyState, Icon, InfoTip, Page, ProgressBar, Stepper, useNotWired, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { getJobsOverview, getPausedRun, getProfiles, type PausedRun, type StageState } from '../api/jobs'
import { navigate } from '../state'
import { Header } from '../shell/Header'
import { BackToAll, CancelRunModal, Checks, LoadFailed, Loading, LockedPath, NewScriptModal, Section, rangeLabel } from './chrome'
import { cancelRun, continueRun, patchRun, useMergedJobs, useRunSim, useRunOverrides, viewRun, type RunPhase } from './store'
import { UploadModal } from './UploadModal'

export function RunPage({ runId, upload }: { runId: string; upload: boolean }) {
  const run = useSourced(() => getPausedRun(runId), [runId])
  const ov = useSourced(getJobsOverview, [])
  const profiles = useSourced(getProfiles, [])
  const merged = useMergedJobs(ov.data)
  const [overrides] = useRunOverrides()
  const sim = useRunSim(runId)
  const notWired = useNotWired()
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [modal, setModal] = useQueryState('modal', '')

  if (run.error) return <Shell id={runId} sub="could not read"><LoadFailed what={`run ${runId}`} error={run.error} onRetry={run.reload} /></Shell>
  if (run.loading || !ov.data) return <Shell id={runId} sub="reading…"><Loading /></Shell>
  if (!run.data) return (
    <Shell id={runId} sub="not a paused run">
      <EmptyState bordered icon="alert-triangle" testid="run-unknown" title={`No paused run called “${runId}”`}
        caption="Jobs knows two paused runs in the demo: r-0431 (Discovery) and a-0098 (Analyse)."
        action={<><Button onClick={() => navigate('jobs/run/r-0431')}>Open r-0431</Button> <Button onClick={() => navigate('jobs')}>All jobs</Button></>} />
    </Shell>
  )

  const r = run.data
  const view = viewRun(r, overrides[r.id])
  // ?state= is the deep link into a state the frame draws; a stored override wins once you act on the page.
  const forced = stateQ === 'arrived' || stateQ === 'waiting' ? stateQ : null
  const result = overrides[r.id]?.result ?? forced ?? r.defaultResult
  const phase: RunPhase = view.phase
  const arrived = result === 'arrived' && phase !== 'cancelled'
  const cluster = merged?.cluster.find(c => c.id === r.clusterJob) ?? null

  const remaining = r.stages.filter(s => s.n > r.pausedAt)
  const statusBadge = phase === 'cancelled' ? <Badge status="cancelled" testid="run-phase">cancelled</Badge>
    : phase === 'finished' ? <Badge status="finished" testid="run-phase">finished · all {r.stageCount} stages</Badge>
      : phase === 'continuing' ? <Badge status="running" testid="run-phase">continuing from stage {r.pausedAt + 1}</Badge>
        : <Badge status="paused" testid="run-phase">paused at stage {r.pausedAt} of {r.stageCount}</Badge>

  return (
    <>
      <Header workspace="Jobs" page={r.id} subtitle={`${r.kindLabel} · paused at stage ${r.pausedAt} of ${r.stageCount}`} search="Search jobs, runs, queues" demo={run.source === 'demo'} />
      <Page maxWidth={1420}>
        <BackToAll />
        <div className="jb-run-title" data-testid="run-title">
          <h1>{r.id}</h1>
          {statusBadge}
          {phase === 'paused' && (arrived
            ? <Badge status="cached" testid="run-result-state">result arrived</Badge>
            : <Badge status="waiting" testid="run-result-state">waiting on {r.clusterJob ?? 'the cluster'}</Badge>)}
          <span className="jb-spacer" />
          <Button icon="external" testid="run-open-workspace" onClick={() => navigate(r.openIn.route)}>{r.openIn.label}</Button>
        </div>
        <div className="jb-run-meta" data-testid="run-meta">
          {r.kindLabel} · {r.template}{r.version ? ` v${r.version}` : ''} · {r.recording} {r.channelsLabel} · {r.durationH} h · started {r.started}
        </div>

        <Section title="Where the run stopped" testid="where-stopped">
          <div className="jb-stages" data-testid="run-stages">
            {r.stages.map((s, i) => {
              const state = stageState(s.n, s.state, r.pausedAt, arrived, phase, sim.status === 'running' || sim.status === 'queued' ? r.pausedAt + 1 + sim.step : null)
              return (
                <Fragmentish key={s.n} withChevron={i < r.stages.length - 1}>
                  <div className={`jb-stage ${state.cls}`} data-testid={`stage-${s.n}`} data-state={state.cls}>
                    <div className="h"><span className="n">{s.n}</span><span className="nm">{s.name}</span><Badge status={state.badge}>{state.label}</Badge></div>
                    <div className="l" title={s.lines[0]}>{s.lines[0]}</div>
                    <div className="l" title={s.lines[1]}>{s.lines[1]}</div>
                  </div>
                </Fragmentish>
              )
            })}
          </div>
          <Timeline points={timeline(r, arrived, phase)} />
        </Section>

        {phase === 'cancelled' ? (
          <Section title={<><Icon name="x-circle" size={15} className="jb-red" /> Run cancelled</>} tone="red" testid="run-cancelled">
            <div className="jb-mono" style={{ fontSize: 12 }}>Cached {rangeLabel(1, r.pausedAt - 1)} kept for the next run of this template. {r.clusterJob ? `${r.clusterJob} is still on the cluster — cancel it there too.` : ''}</div>
            <div className="jb-rail-acts" style={{ marginTop: 10 }}>
              <Button icon="undo" testid="run-uncancel" onClick={() => patchRun(r.id, { phase: 'paused' })}>Put it back to paused</Button>
              <Button variant="link" icon="external" onClick={() => navigate(r.openIn.route)}>{r.openIn.label}</Button>
            </div>
          </Section>
        ) : (
          <div className="jb-run-grid">
            <Section tone={phase === 'finished' ? 'green' : arrived ? 'green' : 'amber'} testid="stage-result"
              title={<>
                <Icon name={arrived ? 'check-circle' : 'hourglass'} size={15} className={arrived ? 'jb-green' : 'jb-amber'} />
                Stage {r.pausedAt} result
                <span className="jb-spacer" />
                {arrived
                  ? <Badge status="cached" testid="found-badge">found {r.result.foundAt} · {r.result.size}</Badge>
                  : <Badge status="waiting" testid="found-badge">looked {r.lookedAgo} · not there yet</Badge>}
              </>}>
              <div className="jb-path-row">
                <span className="jb-label">expected at</span>
                <LockedPath path={r.result.path} icon="folder" testid="result-path" />
                <Button variant="link" size="sm" testid="show-in-folder" onClick={() => notWired(`show ${r.result.path} in the file manager`)}>Show in folder</Button>
              </div>

              {phase === 'continuing' || phase === 'finished' ? (
                <ContinueProgress r={r} sim={sim} phase={phase} remaining={remaining.map(s => `${s.n} ${s.name}`)} />
              ) : (
                <>
                  <div className="jb-label" style={{ margin: '4px 0 2px' }}>checks before the run can continue</div>
                  <Checks testid="run-checks" checks={arrived ? r.checks : r.checks.map(c => ({ ...c, state: 'pending' as const, detail: 'waits for the file' }))} />
                  <div className="jb-info-strip" data-testid="continue-note"><Icon name="info" size={13} />{r.continueNote}</div>
                  <div className="jb-rail-acts">
                    <Button variant="primary" icon="play" testid="continue-btn" disabled={!arrived}
                      disabledReason={arrived ? undefined : `the stage ${r.pausedAt} result is not in ${r.result.root} yet — look again, or upload it by hand`}
                      onClick={() => { continueRun(r); setStateQ(null) }}>Continue from stage {r.pausedAt + 1}</Button>
                    <Button icon="refresh" testid="look-again" onClick={() => { patchRun(r.id, { result: 'arrived' }); setStateQ('arrived') }}>Look again</Button>
                  </div>
                </>
              )}
            </Section>

            <Section title="Other ways forward" testid="other-ways">
              <Way icon="upload" title="Upload results and continue" sub="for a result copied off the cluster by hand · checked, then placed">
                <Button testid="open-upload" onClick={() => navigate(`jobs/run/${r.id}/upload`)}>Upload results…</Button>
              </Way>
              <Way icon="terminal" title="Create the script again" sub={`if ${r.clusterJob ?? 'the job'} failed or was cancelled; the new job replaces it`}>
                <Button testid="open-new-script" onClick={() => setModal('new-script')}>New SLURM script</Button>
              </Way>
              <Way icon="cpu" title={`Run stage ${r.pausedAt} on this machine`} sub={`${r.localEstimate}, over the ${r.limit} ${r.workspace} limit`}>
                <Button disabled testid="run-locally" disabledReason={`${r.localEstimate} · over the ${r.limit} ${r.workspace} limit (Settings › Compute & HPC)`}>Run locally</Button>
              </Way>
              <Way icon="x" title="Cancel the run" sub={`cached ${rangeLabel(1, Math.max(1, r.pausedAt - 1))} kept for the next run of this template`}>
                <Button variant="danger" testid="cancel-run" disabled={phase === 'finished'} disabledReason={phase === 'finished' ? 'the run already finished' : undefined}
                  onClick={() => setModal('cancel')}>Cancel run</Button>
              </Way>
            </Section>
          </div>
        )}

        {cluster && (
          <Callout tone={cluster.status === 'failed' ? 'red' : 'grey'} icon="server" testid="run-cluster-note"
            action={<Button size="sm" variant="cluster" icon="external" onClick={() => navigate(`jobs/cluster/${cluster.id}`)}>Open {cluster.id}</Button>}>
            Stage {r.pausedAt} went to the cluster as <b>{cluster.id}</b> · {cluster.profile} · marked {cluster.status}
            {cluster.marks.running ? ` ${cluster.marks.running}` : ''}. Status is marked by hand — the site cannot see the queue.
          </Callout>
        )}

        <UploadModal open={upload} run={r} onClose={() => navigate(`jobs/run/${r.id}`)} />
        <NewScriptModal open={modal === 'new-script'} onClose={() => setModal(null)} job={cluster} forRun={r.id} profiles={profiles.data ?? []} knownIds={merged?.allIds ?? []} />
        <CancelRunModal open={modal === 'cancel'} onClose={() => setModal(null)} runId={r.id} kept={rangeLabel(1, Math.max(1, r.pausedAt - 1))} onConfirm={() => cancelRun(r)} />
      </Page>
    </>
  )
}

/* ------------------------------------------------------------------ pieces */

function Shell({ id, sub, children }: { id: string; sub: string; children: ReactNode }) {
  return (
    <>
      <Header workspace="Jobs" page={id} subtitle={sub} search="Search jobs, runs, queues" />
      <Page maxWidth={1420}><BackToAll />{children}</Page>
    </>
  )
}

const Fragmentish = ({ children, withChevron }: { children: ReactNode; withChevron: boolean }) => (
  <>{children}{withChevron && <Icon name="chevron-right" size={14} className="jb-stage-chev" />}</>
)

function stageState(n: number, state: StageState, pausedAt: number, arrived: boolean, phase: RunPhase, runningStage: number | null) {
  if (phase === 'finished') return { cls: n <= pausedAt ? 'done' : 'arrived', badge: 'done' as const, label: n === pausedAt ? 'stored' : 'done' }
  if (runningStage != null && n === runningStage) return { cls: 'running', badge: 'running' as const, label: 'running' }
  if (phase === 'continuing' && n <= pausedAt) return { cls: 'done', badge: 'done' as const, label: n === pausedAt ? 'stored' : 'done' }
  if (n === pausedAt && state === 'cluster') return arrived
    ? { cls: 'arrived', badge: 'cached' as const, label: 'result arrived' }
    : { cls: 'cluster', badge: 'on cluster' as const, label: 'on the cluster' }
  if (state === 'done') return { cls: 'done', badge: 'done' as const, label: 'done' }
  if (state === 'cached') return { cls: 'done', badge: 'cached' as const, label: 'cached' }
  return { cls: 'waits', badge: 'pending' as const, label: 'waits' }
}

function timeline(r: PausedRun, arrived: boolean, phase: RunPhase) {
  const pts = r.timeline.filter(p => arrived || !p.label.startsWith('result found'))
  if (!arrived && phase === 'paused') return [...pts, { t: r.lookedAgo, label: `looked for the result · not there yet`, tone: 'amber' as const }]
  if (phase === 'finished') return [...pts, { t: 'now', label: `continued · stages ${r.pausedAt + 1}–${r.stageCount} ran locally`, tone: 'green' as const }]
  return pts
}

function Timeline({ points }: { points: { t: string; label: string; tone: 'grey' | 'amber' | 'green' }[] }) {
  return (
    <div className="jb-timeline" data-testid="run-timeline">
      <span className="line" />
      {points.map((p, i) => {
        const last = i === points.length - 1
        const pct = points.length === 1 ? 0 : (i / (points.length - 1)) * 74
        return (
          <span key={p.label} className={`pt ${p.tone} ${last ? 'last' : ''}`} style={last ? { right: 0 } : { left: `${pct}%` }}>
            <span className="dot" />
            <span className="lab"><b className="jb-muted">{p.t}</b>{p.label}</span>
          </span>
        )
      })}
    </div>
  )
}

function Way({ icon, title, sub, children }: { icon: 'upload' | 'terminal' | 'cpu' | 'x'; title: string; sub: string; children: ReactNode }) {
  return (
    <div className="jb-way" data-testid={`way-${title.split(' ')[0].toLowerCase()}`}>
      <div className="t"><Icon name={icon} size={13} />{title}</div>
      <div className="s">{sub}</div>
      {children}
    </div>
  )
}

function ContinueProgress({ r, sim, phase, remaining }: {
  r: PausedRun; sim: ReturnType<typeof useRunSim>; phase: RunPhase; remaining: string[]
}) {
  const done = phase === 'finished'
  return (
    <div data-testid="continue-progress">
      <div className="jb-info-strip"><Icon name={done ? 'check-circle' : 'play'} size={13} className={done ? 'jb-green' : 'jb-blue'} />
        {done
          ? `Stage ${r.pausedAt}'s file is stored as the artifact${r.clusterJob ? `, ${r.clusterJob} is marked finished` : ''}, and ${rangeLabel(r.pausedAt + 1, r.stageCount)} ran locally.`
          : r.continueNote}
      </div>
      <ProgressBar value={done ? 1 : sim.fraction} tone={done ? 'green' : 'blue'} label={done ? 'done' : (remaining[sim.step] ?? 'starting…')} eta={done ? r.remaining : undefined} testid="continue-bar" />
      <Stepper variant="numbered" orientation="horizontal" testid="continue-stepper"
        steps={remaining.map((s, i) => ({ label: s, state: done || i < sim.step ? 'done' : i === sim.step ? 'running' : 'todo' }))} />
      <div className="jb-rail-acts" style={{ marginTop: 10 }}>
        {done
          ? <Button variant="primary" icon="external" testid="open-finished" onClick={() => navigate(r.openIn.route)}>{r.openIn.label} →</Button>
          : <Button icon="stop" testid="continue-cancel" onClick={() => { sim.cancel(); patchRun(r.id, { phase: 'paused' }) }}>Stop and stay paused</Button>}
        <span className="jb-mono jb-small jb-muted">{done ? 'the run appears in its workspace as if it had never paused' : 'stages run under the usual local limits'}</span>
      </div>
      {done && <div className="jb-row" style={{ marginTop: 8 }}><span className="jb-mono jb-small jb-muted">what Continue stored</span><InfoTip title="What Continue stored">The uploaded or found file became stage {r.pausedAt}'s artifact, referenced by path — bulk arrays never enter the database (repo rule 4).</InfoTip></div>}
    </div>
  )
}
