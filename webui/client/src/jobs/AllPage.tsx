/* jobs.all — `#/jobs` (frame jobs-1, spec §7c.1, P24): every job across workspaces in one place,
 * sorted by what needs you first. Needs-you cards, one grouped table, a rail for the selected job,
 * the manifest-inbox drawer and the New-script / Cancel-run modals. */
import { Fragment, useMemo, type ReactNode } from 'react'
import {
  Badge, Button, Chip, Drawer, Dropdown, EmptyState, Icon, InfoTip, Menu, PageTitle, ProgressBar, Seg,
  fmtInt, useQueryFlag, useQueryState, type IconName,
} from '../kit'
import { Page } from '../kit'
import { useSourced } from '../api/seam'
import { getJobsOverview, getManifestInbox, getProfiles, type ClusterJob, type QueueJob, type Workspace } from '../api/jobs'
import { navigate } from '../state'
import { Header } from '../shell/Header'
import { DEMO_JOBS_ACTIVE } from '../fixtures/canon'
import { CancelRunModal, ClusterBadge, Loading, LoadFailed, LockedPath, ManifestInbox, NewScriptModal, StagePill, WsTag, wsIcon } from './chrome'
import {
  cancelLocal, cancelRun, continueRun, isOverdue, markCluster, overrunLabel, useInboxPending, useMergedJobs, type MergedJobs, type RunView,
} from './store'

type Filter = 'all' | 'needs-you' | 'paused' | 'cluster' | 'local' | 'queues' | 'finished'
type Grp = 'paused' | 'cluster' | 'local' | 'queues' | 'finished'

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'all' }, { value: 'needs-you', label: 'needs you' }, { value: 'paused', label: 'paused' },
  { value: 'cluster', label: 'cluster' }, { value: 'local', label: 'local' }, { value: 'queues', label: 'review queues' },
  { value: 'finished', label: 'finished' },
]
const GROUP_TITLE: Record<Grp, string> = {
  paused: 'Paused · waiting on cluster results', cluster: 'Cluster jobs · status marked by hand',
  local: 'Running locally', queues: 'Review queues', finished: 'Finished and cancelled today',
}
const GROUP_ICON: Record<Grp, IconName> = { paused: 'pause', cluster: 'server', local: 'cpu', queues: 'checklist', finished: 'check-circle' }

interface Row {
  id: string; grp: Grp; ws: Workspace; title: string; sub: string; where: string
  status: ReactNode; time: string; action: ReactNode; needsYou?: boolean; tone?: 'amber' | 'dim'
}

export function AllPage() {
  const ov = useSourced(getJobsOverview, [])
  const inbox = useSourced(getManifestInbox, [])
  const profiles = useSourced(getProfiles, [])
  const merged = useMergedJobs(ov.data)
  const [pending] = useInboxPending()

  const [kindAlias] = useQueryState('kind', '')            // Models links in as ?kind=cluster
  const [filterQ, setFilter] = useQueryState<Filter>('filter', 'all')
  const filter: Filter = filterQ !== 'all' ? filterQ : (kindAlias === 'cluster' ? 'cluster' : 'all')
  const [ws, setWs] = useQueryState('ws', 'all')
  const [sel, setSel] = useQueryState('sel', 'r-0431')
  const [drawer, setDrawer] = useQueryState('drawer', '')
  const [modal, setModal] = useQueryState('modal', '')
  const [modalJob, setModalJob] = useQueryState('job', '')
  const [finishedOpen, setFinishedOpen] = useQueryFlag('finished')

  const rows = useMemo(() => (merged ? buildRows(merged) : []), [merged])
  const wsOptions = useMemo(() => ['all', ...Array.from(new Set(rows.map(r => r.ws)))], [rows])
  const shown = rows.filter(r =>
    (ws === 'all' || r.ws === ws)
    && (filter === 'all' ? true
      : filter === 'needs-you' ? r.needsYou
        : filter === 'finished' ? r.grp === 'finished'
          : r.grp === filter))

  const needYou = rows.filter(r => r.needsYou)
  const localCount = merged?.local.filter(l => !l.cancelledAt).length ?? 0
  const clusterRunning = merged?.cluster.filter(c => c.status === 'running').length ?? 0
  const queueCount = merged?.queues.length ?? 0
  const idleQueues = merged?.queues.filter(q => q.idle).length ?? 0
  const inboxWaiting = pending === 'arrived' ? 1 : 0
  const importedCount = (inbox.data?.manifests.filter(m => m.imported).length ?? 0) + (pending === 'imported' ? 1 : 0)

  const selRow = rows.find(r => r.id === sel) ?? null
  const subtitle = `${needYou.length || DEMO_JOBS_ACTIVE} need you · ${localCount} local · ${clusterRunning} on hpc-1 · ${queueCount} queues`

  return (
    <>
      <Header workspace="Jobs" page="All jobs" subtitle={subtitle} search="Search jobs, runs, queues" demo={ov.source === 'demo'} />
      <Page maxWidth={1420}>
        {ov.error && <LoadFailed what="the job list" error={ov.error} onRetry={ov.reload} />}
        {ov.loading && <Loading />}
        {merged && (
          <>
            <PageTitle title="Jobs"
              actions={<Button icon="inbox" testid="open-inbox" onClick={() => setDrawer('inbox')}>Manifest inbox · {importedCount + inboxWaiting}</Button>}>
              <Chip tone="amber" dot="var(--amber)" testid="chip-need-you" onClick={() => setFilter('needs-you')} title="filter to the jobs that need you">{needYou.length} need you</Chip>
              <Chip tone="blue" testid="chip-local" onClick={() => setFilter('local')}>{localCount} running locally</Chip>
              <Chip tone="purple" testid="chip-cluster" onClick={() => setFilter('cluster')}>{clusterRunning} on hpc-1</Chip>
              <Chip tone="grey" testid="chip-queues" onClick={() => setFilter('queues')}>{queueCount} review queues · {idleQueues} idle</Chip>
            </PageTitle>

            <div className="jb-filter-row" data-testid="jobs-filters">
              <Seg options={FILTERS} value={filter} onChange={v => setFilter(v === 'all' ? null : v)} testid="jobs-filter" ariaLabel="filter jobs" />
              <span className="jb-spacer" />
              <Dropdown value={ws} onChange={v => setWs(v === 'all' ? null : v)} testid="jobs-workspace"
                options={wsOptions.map(w => ({ value: w, label: w === 'all' ? 'all workspaces' : w }))} />
            </div>

            <div className="jb-all">
              <div className="jb-main">
                {filter !== 'finished' && <NeedsYouCards rows={needYou} merged={merged} inboxWaiting={inboxWaiting} onSelect={setSel} onInbox={() => setDrawer('inbox')} />}
                <div className="jb-table-card" data-testid="jobs-table-card">
                  <div className="head">
                    <h3>{filter === 'all' ? 'All jobs' : FILTERS.find(f => f.value === filter)!.label}</h3>
                    <span className="jb-spacer" />
                    <span className="jb-mono jb-small jb-muted">sorted by what needs you first</span>
                  </div>
                  <JobsTable rows={shown} sel={sel} onSelect={setSel} finishedOpen={finishedOpen} onFinished={setFinishedOpen}
                    counts={{ finished: merged.finished.filter(f => f.status === 'finished').length, cancelled: merged.finished.filter(f => f.status === 'cancelled').length }} />
                  {!shown.length && (
                    <EmptyState size="sm" bordered testid="jobs-empty" icon="filter" title="No jobs match these filters"
                      caption={`${FILTERS.find(f => f.value === filter)!.label}${ws === 'all' ? '' : ` · ${ws}`} has nothing today`}
                      action={<Button size="sm" onClick={() => { setFilter(null); setWs(null) }}>Clear filters</Button>} />
                  )}
                </div>
              </div>
              <JobRail row={selRow} merged={merged} onModal={(m, j) => { setModal(m); setModalJob(j) }} />
            </div>

            <Drawer open={drawer === 'inbox'} onClose={() => setDrawer(null)} title="Manifest inbox" side="right" width={480} testid="inbox-drawer"
              subtitle={inbox.data ? `${importedCount} imported · watching ${inbox.data.watching}` : undefined}>
              {inbox.error && <LoadFailed what="the manifest inbox" error={inbox.error} onRetry={inbox.reload} />}
              {inbox.loading && <Loading height={160} testid="inbox-loading" />}
              {inbox.data && <ManifestInbox data={inbox.data} testid="inbox-drawer-body" runs={merged.runs.map(r => ({ id: r.run.id, stage: r.run.pausedAt, label: r.result !== 'arrived' ? 'not in its root yet' : r.run.clusterJob ? `result arrived ${r.run.result.foundAt}` : 'result in place' }))} />}
            </Drawer>

            <NewScriptModal open={modal === 'new-script'} onClose={() => { setModal(null); setModalJob(null) }}
              job={merged.cluster.find(c => c.id === modalJob) ?? null} forRun={merged.cluster.find(c => c.id === modalJob)?.forRun}
              profiles={profiles.data ?? []} knownIds={merged.allIds} />

            <CancelRunModal open={modal === 'cancel'} onClose={() => { setModal(null); setModalJob(null) }}
              runId={modalJob || 'the run'} kept="1–2"
              onConfirm={() => { const r = merged.runs.find(x => x.run.id === modalJob); if (r) cancelRun(r.run) }} />
          </>
        )}
      </Page>
    </>
  )
}

/* ------------------------------------------------------------------ rows */

function buildRows(m: MergedJobs): Row[] {
  const out: Row[] = []

  for (const rv of m.runs) {
    const r = rv.run
    const arrived = rv.result === 'arrived'
    const cancelled = rv.phase === 'cancelled'
    const finished = rv.phase === 'finished'
    const continuing = rv.phase === 'continuing'
    if (cancelled || finished) {
      out.push({
        id: r.id, grp: 'finished', ws: r.workspace, title: `${r.template} · ${r.recording} ${r.channelsLabel}`,
        sub: `${r.kindLabel} · ${cancelled ? `cancelled at stage ${r.pausedAt}` : `finished from stage ${r.pausedAt + 1}`}`,
        where: 'this machine', status: <Badge status={cancelled ? 'cancelled' : 'finished'} />, time: rv.ov.at ?? '—',
        action: <Button size="sm" variant="link" onClick={e => { e.stopPropagation(); navigate(`jobs/run/${r.id}`) }}>Open</Button>,
      })
      continue
    }
    out.push({
      id: r.id, grp: 'paused', ws: r.workspace, title: `${r.template} · ${r.recording} ${r.channelsLabel}`,
      sub: `${r.kindLabel} · paused at ${r.pausedAt}/${r.stageCount} ${r.stageName}`,
      where: r.where,
      status: continuing ? <Badge status="running">continuing from stage {r.pausedAt + 1}</Badge>
        : arrived ? <Badge status="cached">results in place</Badge>
          : <Badge status="waiting">waiting on {r.clusterJob ?? 'the cluster'}</Badge>,
      time: r.since, needsYou: true, tone: 'amber',
      action: continuing ? <span className="jb-mono jb-small jb-muted">running…</span>
        : arrived
          ? <Button size="sm" variant="primary" icon="play" testid={`continue-${r.id}`} onClick={e => { e.stopPropagation(); continueRun(r) }}>Continue</Button>
          : <Button size="sm" variant="link" icon="upload" testid={`upload-${r.id}`} onClick={e => { e.stopPropagation(); navigate(`jobs/run/${r.id}/upload`) }}>Upload results</Button>,
    })
  }

  for (const j of m.cluster) {
    const overdue = isOverdue(j)
    out.push({
      id: j.id, grp: 'cluster', ws: j.workspace, title: j.title, sub: j.sub, where: j.profile,
      status: <ClusterBadge job={j} overdue={overdue} />,
      time: j.status === 'running' && j.runningForH != null ? `${j.runningForH} h` : '—',
      needsYou: overdue, tone: overdue ? 'amber' : undefined,
      action: j.status === 'failed'
        ? <Button size="sm" variant="link" icon="terminal" onClick={e => { e.stopPropagation(); navigate(`jobs/cluster/${j.id}?modal=new-script`) }}>New script</Button>
        : j.status === 'finished'
          ? <Button size="sm" variant="link" icon="external" onClick={e => { e.stopPropagation(); navigate(j.openIn.route) }}>Open in {j.workspace}</Button>
          : <MarkMenu job={j} />,
    })
  }

  for (const l of m.local) {
    out.push({
      id: l.id, grp: l.cancelledAt ? 'finished' : 'local', ws: l.workspace, title: l.title, sub: l.sub, where: 'this machine',
      status: l.cancelledAt ? <Badge status="cancelled" /> : <span className="jb-prog"><ProgressBar value={l.progress} width={110} size="sm" labelPosition="none" /><span className="jb-muted">{Math.round(l.progress * 100)} %</span></span>,
      time: l.cancelledAt ?? l.left,
      action: l.cancelledAt
        ? <Button size="sm" variant="link" onClick={e => { e.stopPropagation(); navigate(l.route) }}>Open</Button>
        : <Button size="sm" variant="link" testid={`cancel-${l.id}`} onClick={e => { e.stopPropagation(); cancelLocal(l.id) }}>Cancel</Button>,
    })
  }

  for (const q of m.queues) {
    const done = (q.total - q.left) / q.total
    out.push({
      id: q.id, grp: 'queues', ws: 'Review', title: q.title,
      sub: `${fmtInt(q.left)} left of ${fmtInt(q.total)}${q.pace ? ` · ${q.pace}` : ''}${q.forWhat ? ` · ${q.forWhat}` : ''}`,
      where: 'Review',
      status: <span className="jb-prog"><ProgressBar value={done} width={110} size="sm" tone="green" labelPosition="none" /><span className="jb-muted">{Math.round(done * 100)} %</span></span>,
      time: q.eta,
      action: <Button size="sm" variant="link" testid={`open-${q.id}`} onClick={e => { e.stopPropagation(); navigate(`review/queue/${q.id}`) }}>Open</Button>,
    })
  }

  for (const f of m.finished) {
    out.push({
      id: f.id, grp: 'finished', ws: f.workspace, title: f.title, sub: f.sub, where: f.where,
      status: <Badge status={f.status} />, time: `${f.at} · ${f.took}`, tone: 'dim',
      action: <Button size="sm" variant="link" onClick={e => { e.stopPropagation(); navigate(f.route) }}>Open</Button>,
    })
  }
  return out
}

function MarkMenu({ job }: { job: ClusterJob }) {
  return (
    <span onClick={e => e.stopPropagation()}>
      <Menu trigger={p => <Button {...p} size="sm" variant="link" icon="flag" testid={`mark-${job.id}`}>Mark…</Button>}
        items={[
          { value: 'submitted', label: 'Mark submitted', description: 'the script is in the cluster queue' },
          { value: 'running', label: 'Mark running', description: 'the cluster started it' },
          { value: 'finished', label: 'Mark finished', description: 'also set when the manifest is imported' },
          { value: 'failed', label: 'Mark failed', danger: true, description: 'the cluster log says it died' },
        ]}
        onSelect={v => markCluster(job.id, v as ClusterJob['status'])} />
    </span>
  )
}

/* ------------------------------------------------------------------ needs-you cards */

function NeedsYouCards({ rows, merged, inboxWaiting, onSelect, onInbox }: {
  rows: Row[]; merged: MergedJobs; inboxWaiting: number; onSelect: (id: string) => void; onInbox: () => void
}) {
  const cards: ReactNode[] = []
  for (const r of rows) {
    const rv = merged.runs.find(x => x.run.id === r.id)
    if (rv) { cards.push(<RunCard key={r.id} rv={rv} onSelect={onSelect} />); continue }
    const cj = merged.cluster.find(c => c.id === r.id)
    if (cj) cards.push(<OverdueCard key={r.id} job={cj} onSelect={onSelect} />)
  }
  if (inboxWaiting) cards.push(
    <div className="jb-card amber" key="inbox" data-testid="card-inbox">
      <div className="jb-card-head"><Icon name="inbox" size={14} />A manifest is waiting<WsTag ws="Models" /></div>
      <div className="jb-card-line">a cluster result arrived in ./cluster_out</div>
      <div className="jb-card-sub">import checks run before anything is stored</div>
      <div className="jb-card-acts"><Button size="sm" variant="primary" icon="download" onClick={onInbox}>Open the inbox</Button></div>
    </div>,
  )
  if (!cards.length) return <EmptyState size="sm" bordered testid="needs-you-empty" icon="check-circle" title="Nothing needs you" caption="every run has what it was waiting for" />
  return <div className={`jb-cards ${cards.length === 1 ? 'n1' : cards.length === 2 ? 'n2' : ''}`} data-testid="needs-you-cards">{cards}</div>
}

function RunCard({ rv, onSelect }: { rv: RunView; onSelect: (id: string) => void }) {
  const r = rv.run
  const arrived = rv.result === 'arrived'
  return (
    <div className={`jb-card ${arrived ? 'green' : 'amber'}`} data-testid={`card-${r.id}`}>
      <div className="jb-card-head">
        <Icon name={arrived ? 'check-circle' : 'hourglass'} size={14} className={arrived ? 'jb-green' : 'jb-amber'} />
        <button type="button" className="id" onClick={() => onSelect(r.id)}>{r.id} {arrived ? 'results in place' : 'paused'}</button>
        <WsTag ws={r.workspace} />
      </div>
      {arrived ? (
        <>
          <div className="jb-card-line">{r.stageName.toLowerCase()} for {r.channelsLabel} found in {r.result.root}</div>
          <div className="jb-card-sub">import checks passed · {r.stageCount - r.pausedAt} stages left, {r.remaining} locally</div>
          <div className="jb-card-acts">
            <Button size="sm" variant="primary" icon="play" testid={`card-continue-${r.id}`} onClick={() => continueRun(r)}>Continue</Button>
            <Button size="sm" variant="link" onClick={() => navigate(`jobs/run/${r.id}`)}>Open run detail</Button>
          </div>
        </>
      ) : (
        <>
          <div className="jb-card-line">stage {r.pausedAt} of {r.stageCount} · {r.stageName} · on the cluster</div>
          <div className="jb-card-sub">{r.clusterJob} marked running {r.since} ago · estimate 6 h</div>
          <div className="jb-card-acts">
            <Button size="sm" icon="upload" testid={`card-upload-${r.id}`} onClick={() => navigate(`jobs/run/${r.id}/upload`)}>Upload results and continue</Button>
          </div>
        </>
      )}
    </div>
  )
}

function OverdueCard({ job, onSelect }: { job: ClusterJob; onSelect: (id: string) => void }) {
  return (
    <div className="jb-card amber" data-testid={`card-${job.id}`}>
      <div className="jb-card-head">
        <Icon name="clock" size={14} className="jb-amber" />
        <button type="button" className="id" onClick={() => onSelect(job.id)}>{job.id} at {overrunLabel(job)} estimate</button>
        <WsTag ws={job.workspace} />
      </div>
      <div className="jb-card-line">{job.title.split('·').slice(-1)[0].trim()} marked running for {job.runningForH} h</div>
      <div className="jb-card-sub">the site cannot see the queue — check the cluster</div>
      <div className="jb-card-acts">
        <Button size="sm" icon="check-circle" testid={`card-finish-${job.id}`} onClick={() => markCluster(job.id, 'finished')}>Mark finished</Button>
        <Button size="sm" icon="x-circle" testid={`card-fail-${job.id}`} onClick={() => markCluster(job.id, 'failed')}>Mark failed</Button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ the table */

function JobsTable({ rows, sel, onSelect, finishedOpen, onFinished, counts }: {
  rows: Row[]; sel: string; onSelect: (id: string) => void
  finishedOpen: boolean; onFinished: (v: boolean) => void; counts: { finished: number; cancelled: number }
}) {
  const groups: Grp[] = ['paused', 'cluster', 'local', 'queues', 'finished']
  return (
    <table className="jb-table" data-testid="jobs-table">
      <colgroup><col style={{ width: 84 }} /><col /><col style={{ width: 132 }} /><col style={{ width: 168 }} /><col style={{ width: 86 }} /><col style={{ width: 132 }} /></colgroup>
      <thead><tr><th>id</th><th>job</th><th>where</th><th>status</th><th>time</th><th /></tr></thead>
      <tbody>
        {groups.map(g => {
          const rs = rows.filter(r => r.grp === g)
          if (!rs.length) return null
          const collapsible = g === 'finished'
          const open = !collapsible || finishedOpen
          return (
            <Fragment key={`g-${g}`}>
              <tr className="group">
                <td colSpan={6}>
                  {collapsible ? (
                    <button type="button" className="jb-group-bar" aria-expanded={open} data-testid={`group-${g}`} onClick={() => onFinished(!open)}>
                      <Icon name="chevron-down" size={12} className="chev" />
                      <Icon name={GROUP_ICON[g]} size={13} />
                      {GROUP_TITLE[g]}
                      <span className="n">{counts.finished} finished · {counts.cancelled} cancelled</span>
                    </button>
                  ) : (
                    <span className="jb-group-bar" data-testid={`group-${g}`}>
                      <Icon name={GROUP_ICON[g]} size={13} />{GROUP_TITLE[g]}<span className="n">{rs.length}</span>
                    </span>
                  )}
                </td>
              </tr>
              {open && rs.map(r => (
                <tr key={r.id} className={`row ${sel === r.id ? 'sel' : ''} ${r.tone === 'amber' ? 'amber' : ''} ${r.tone === 'dim' ? 'dim' : ''}`}
                  data-testid={`job-row-${r.id}`} tabIndex={0} onClick={() => onSelect(r.id)}
                  onKeyDown={e => { if (e.key === 'Enter') onSelect(r.id) }}>
                  <td><span className="jb-id">{r.id}</span></td>
                  <td>
                    <span className="jb-job">
                      <Icon name={wsIcon(r.ws)} size={13} className="ic" />
                      <span className="txt"><div className="t">{r.title}</div><div className="s">{r.sub}</div></span>
                    </span>
                  </td>
                  <td><span className="jb-where">{r.where}</span></td>
                  <td>{r.status}</td>
                  <td><span className="jb-time">{r.time}</span></td>
                  <td className="jb-act">{r.action}</td>
                </tr>
              ))}
            </Fragment>
          )
        })}
      </tbody>
    </table>
  )
}

/* ------------------------------------------------------------------ the rail */

function JobRail({ row, merged, onModal }: { row: Row | null; merged: MergedJobs; onModal: (modal: string, job: string) => void }) {
  if (!row) return (
    <div className="jb-rail" data-testid="job-rail">
      <EmptyState size="sm" icon="list" title="Pick a job" caption="the rail shows where it stopped and what you can do next" />
    </div>
  )
  const rv = merged.runs.find(r => r.run.id === row.id)
  if (rv) return <PausedRail rv={rv} onModal={onModal} clusterJob={merged.cluster.find(c => c.id === rv.run.clusterJob) ?? null} />
  const cj = merged.cluster.find(c => c.id === row.id)
  if (cj) return <ClusterRail job={cj} onModal={onModal} />
  const q = merged.queues.find(x => x.id === row.id)
  if (q) return <QueueRail q={q} />
  const l = merged.local.find(x => x.id === row.id)
  if (l) return (
    <div className="jb-rail" data-testid="job-rail">
      <div className="jb-rail-head"><h3>{l.id}</h3><WsTag ws={l.workspace} /></div>
      <div className="jb-rail-meta">{l.title} · {l.sub}</div>
      {l.cancelledAt ? <Badge status="cancelled">cancelled {l.cancelledAt}</Badge> : <ProgressBar value={l.progress} label={`${Math.round(l.progress * 100)} %`} eta={l.left} />}
      <div className="jb-rail-acts">
        <Button size="sm" icon="external" onClick={() => navigate(l.route)}>Open in {l.workspace}</Button>
        {!l.cancelledAt && <Button size="sm" variant="danger" icon="x" onClick={() => cancelLocal(l.id)}>Cancel</Button>}
      </div>
      <div className="jb-mono jb-small jb-muted">runs on this machine under the {l.workspace} local limit; nothing goes to the cluster.</div>
    </div>
  )
  const f = merged.finished.find(x => x.id === row.id)
  return (
    <div className="jb-rail" data-testid="job-rail">
      <div className="jb-rail-head"><h3>{row.id}</h3><WsTag ws={row.ws} /></div>
      <div className="jb-rail-meta">{row.title}</div>
      <div className="jb-mono jb-small jb-muted">{row.sub}</div>
      <div>{row.status}</div>
      {f && <div className="jb-mono jb-small jb-muted">{f.at} · took {f.took} · on {f.where}</div>}
      <div className="jb-rail-acts">{row.action}</div>
    </div>
  )
}

function PausedRail({ rv, onModal, clusterJob }: { rv: RunView; onModal: (modal: string, job: string) => void; clusterJob: ClusterJob | null }) {
  const r = rv.run
  const arrived = rv.result === 'arrived'
  const over = rv.phase === 'cancelled' || rv.phase === 'finished'
  return (
    <div className="jb-rail" data-testid="job-rail">
      <div className="jb-rail-head">
        <h3>{r.id}</h3>
        <Badge status={over ? (rv.phase === 'cancelled' ? 'cancelled' : 'finished') : rv.phase === 'continuing' ? 'running' : 'paused'} />
        <WsTag ws={r.workspace} />
      </div>
      <div className="jb-rail-meta">{r.template} v{r.version ?? 1} · {r.recording} {r.channelsLabel} · started {r.started.split(' ').slice(-1)[0]}</div>
      <div className="jb-rail-label">stages</div>
      <div className="jb-stage-pills" data-testid="rail-stages">
        {r.stages.map(s => (
          <StagePill key={s.n} n={s.n} name={s.name}
            state={s.n === r.pausedAt && arrived ? 'arrived' : s.state}
            note={s.state === 'cached' ? 'cached' : s.n === r.pausedAt ? (arrived ? 'result arrived' : 'sent to cluster') : s.state === 'waits' ? 'waits' : undefined} />
        ))}
      </div>
      <div className={`jb-wait-box ${arrived ? 'green' : ''}`} data-testid="rail-wait">
        <div className="t">{arrived ? `Stage ${r.pausedAt} result found ${r.result.foundAt}` : `Waiting for the result of stage ${r.pausedAt}`}</div>
        <div>{clusterJob ? `${clusterJob.id} · hpc-1 · marked ${clusterJob.status} ${clusterJob.marks.running ?? clusterJob.marks.created}` : 'SLURM script run by hand on hpc-1'}</div>
        <div className="jb-label">expected at</div>
        <LockedPath path={r.result.shortPath} icon="folder" testid="rail-path" />
        <div className="jb-row"><Icon name="clock" size={11} />looked {r.lookedAgo} · {arrived ? `${r.result.size} in place` : 'not there yet'}</div>
      </div>
      <Button size="sm" variant="primary" icon="panel-right" testid="rail-open-run" onClick={() => navigate(`jobs/run/${r.id}`)}>Open run detail →</Button>
      <div className="jb-rail-acts">
        <Button size="sm" icon="refresh" testid="rail-look-again" onClick={() => navigate(`jobs/run/${r.id}?state=arrived`)}>Look again</Button>
        <Button size="sm" icon="upload" testid="rail-upload" onClick={() => navigate(`jobs/run/${r.id}/upload`)}>Upload results and continue</Button>
      </div>
      <Button size="sm" icon="cpu" block disabled testid="rail-run-locally"
        disabledReason={`${r.localEstimate} · over the ${r.limit} limit`}>Run stage {r.pausedAt} locally</Button>
      <span className="jb-mono jb-small jb-muted">{r.localEstimate} · over the {r.limit} limit</span>
      <hr className="jb-rail-sep" />
      <Button size="sm" variant="danger" icon="x" testid="rail-cancel" disabled={over} disabledReason={over ? 'the run is already over' : undefined}
        onClick={() => onModal('cancel', r.id)}>Cancel run</Button>
    </div>
  )
}

function ClusterRail({ job, onModal }: { job: ClusterJob; onModal: (modal: string, j: string) => void }) {
  const overdue = isOverdue(job)
  return (
    <div className="jb-rail" data-testid="job-rail">
      <div className="jb-rail-head"><h3>{job.id}</h3><ClusterBadge job={job} overdue={overdue} /><WsTag ws={job.workspace} /></div>
      <div className="jb-rail-meta">{job.title} · {job.sub}</div>
      <div className="jb-rail-label">marked by hand <InfoTip title="Marked by hand">The site cannot see the cluster queue (§7c.4). Every status here is one you set; nothing changes on its own — except <i>finished</i>, which is also set when the job's manifest is imported.</InfoTip></div>
      <div className="jb-stage-pills">
        <span className={`jb-stage-pill ${job.marks.submitted ? 'done' : 'waits'}`}><Icon name={job.marks.submitted ? 'check-circle' : 'circle-dashed'} size={12} />submitted {job.marks.submitted ?? '—'}</span>
        <span className={`jb-stage-pill ${job.marks.running ? (overdue ? 'cluster' : 'running') : 'waits'}`}><Icon name={job.marks.running ? 'play' : 'circle-dashed'} size={12} />running {job.marks.running ?? '—'}</span>
        <span className={`jb-stage-pill ${job.marks.finished ? 'done' : job.marks.failed ? 'cluster' : 'waits'}`}><Icon name={job.marks.finished ? 'check-circle' : job.marks.failed ? 'x-circle' : 'circle-dashed'} size={12} />{job.marks.failed ? `failed ${job.marks.failed}` : `finished ${job.marks.finished ?? '—'}`}</span>
      </div>
      {overdue && <div className="jb-wait-box" data-testid="rail-overdue"><div className="t">{overrunLabel(job)} its {job.estimateLabel.split(' · ')[0]} estimate</div><div>Check the cluster. The site never changes a cluster job's status on its own.</div></div>}
      <div className="jb-rail-acts">
        <Button size="sm" variant="cluster" icon="external" testid="rail-open-job" onClick={() => navigate(`jobs/cluster/${job.id}`)}>Open job →</Button>
      </div>
      <div className="jb-rail-acts">
        <Button size="sm" icon="check-circle" disabled={job.status === 'finished'} disabledReason={job.status === 'finished' ? 'already finished' : undefined} onClick={() => markCluster(job.id, 'finished')}>Mark finished</Button>
        <Button size="sm" icon="x-circle" disabled={job.status === 'failed'} disabledReason={job.status === 'failed' ? 'already failed' : undefined} onClick={() => markCluster(job.id, 'failed')}>Mark failed</Button>
      </div>
      {job.status === 'failed' && <Button size="sm" icon="terminal" testid="rail-new-script" onClick={() => onModal('new-script', job.id)}>New SLURM script</Button>}
      <span className="jb-mono jb-small jb-muted">results return from {job.returnFrom} → {job.returnTo}</span>
    </div>
  )
}

function QueueRail({ q }: { q: QueueJob }) {
  const done = (q.total - q.left) / q.total
  return (
    <div className="jb-rail" data-testid="job-rail">
      <div className="jb-rail-head"><h3>{q.id}</h3>{q.blind && <Badge status="blind" />}<WsTag ws="Review" /></div>
      <div className="jb-rail-meta">{q.title} · {q.sub}</div>
      <ProgressBar value={done} tone="green" label={`${fmtInt(q.total - q.left)} / ${fmtInt(q.total)}`} eta={q.eta} />
      <div className="jb-mono jb-small jb-muted">{fmtInt(q.left)} left{q.pace ? ` · ${q.pace}` : ''}{q.idle ? ' · idle, nothing judged today' : ''}</div>
      {q.blind && <div className="jb-mono jb-small jb-muted">blind: the machine's score and family are hidden until the verdict (§10.6).</div>}
      <div className="jb-rail-acts"><Button size="sm" variant="primary" icon="checklist" onClick={() => navigate(`review/queue/${q.id}`)}>Open in Review</Button></div>
    </div>
  )
}
