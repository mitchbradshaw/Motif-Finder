/* The Jobs board's cards — every one of them live (fixup-aj built the first three parts; fixup-jobs made the
 * page whole and retired its fixture half):
 *  · In progress here — the bridge's own job table (training, chain runs that build trees, window sets, blind-queue
 *    work, sweeps, imports): state, stage, progress, started, duration, the error with its traceback; finished and
 *    failed rows stay in the same table, behind a status filter;
 *  · Waiting on the cluster — every job the site wrote for the cluster, whatever wrote it (the CNN and Ward job
 *    directories, Discovery's seed searches, the flat recipe scripts), with what to copy, its state, and how its
 *    results come back: the Manifest inbox for a job directory, the seed import for a result file, or not through
 *    the site at all — the row says so;
 *  · Waiting in review — the open review queues, how much of each is still to judge, and the pace;
 *  · the Manifest inbox — a returned job directory imported through `hpc_import.import_results`, the function
 *    `python -m Working.training import-results` calls.
 * The site never logs in to the cluster or submits anything: you copy, `sbatch`, and bring the results back. */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Badge, Button, Chip, EmptyState, Icon, InfoTip, ProgressBar, Seg, TextField } from '../kit'
import { useSourced, type Sourced, type SourcedState } from '../api/seam'
import { getJob, cancelJob, type JobRow } from '../api'
import {
  importReturnedJob, importSeedResult, isActive, WORKSPACE_ICON, wsOf,
  type ClusterJob, type ClusterList, type ClusterState, type ImportAttempt, type LiveJob,
} from '../api/jobs'
import type { ReviewQueue } from '../api/review'
import { fmtBytes } from '../api/cnn'
import { navigate } from '../state'
import { Loading, LoadFailed } from './chrome'

/* ------------------------------------------------------------------ helpers */
const pad = (n: number) => String(n).padStart(2, '0')
export function fmtWhen(d: Date | null): string {
  if (!d) return '—'
  const now = new Date()
  const hms = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  return d.toDateString() === now.toDateString() ? hms : `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${hms}`
}
export function fmtDur(s: number | null): string {
  if (s == null || !Number.isFinite(s)) return '—'
  if (s < 60) return `${Math.max(0, Math.round(s))} s`
  if (s < 3600) return `${Math.floor(s / 60)} min ${pad(Math.round(s % 60))} s`
  return `${Math.floor(s / 3600)} h ${pad(Math.floor((s % 3600) / 60))} min`
}
export const isoWhen = (v: string | number | null | undefined) => fmtWhen(v == null ? null : typeof v === 'number' ? new Date(v * 1000) : new Date(v))

/** Re-run `reload` every `ms` (and pause while the tab is hidden). */
function usePoll(reload: () => void, ms: number) {
  const ref = useRef(reload)
  ref.current = reload
  useEffect(() => {
    const t = window.setInterval(() => { if (document.visibilityState !== 'hidden') ref.current() }, ms)
    return () => window.clearInterval(t)
  }, [ms])
}

/** Keep the last good data while a poll reloads, so a table does not flash. */
function useSticky<T>(data: T | null): T | null {
  const [kept, setKept] = useState<T | null>(data)
  useEffect(() => { if (data != null) setKept(data) }, [data])
  return data ?? kept
}

export interface LiveRead<T> extends SourcedState<T> { data: T | null }
/** A live read the board polls: `useSourced`, sticky across reloads, re-read every `ms(data)` milliseconds. */
export function useLiveRead<T>(fn: () => Promise<Sourced<T>>, deps: unknown[], ms: (data: T | null) => number): LiveRead<T> {
  const q = useSourced(fn, deps)
  const data = useSticky(q.data)
  usePoll(q.reload, ms(data))
  return { ...q, data }
}

export const WsTag = ({ ws }: { ws: string | null | undefined }) => {
  const w = wsOf(ws)
  return <span className="jb-ws" title={`${w} reads this job's result`}><Icon name={WORKSPACE_ICON[w]} size={11} />{w}</span>
}

/* ------------------------------------------------------------------ in progress here */
type KindFilter = 'all' | 'training' | 'chain_run' | 'import' | 'other'
const KIND_FILTERS: { value: KindFilter; label: string }[] = [
  { value: 'all', label: 'every kind' }, { value: 'training', label: 'training · window sets · blind' },
  { value: 'chain_run', label: 'chain runs' }, { value: 'import', label: 'imports' }, { value: 'other', label: 'other' },
]
type StatusFilter = 'all' | 'active' | 'failed' | 'finished'
const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'all' }, { value: 'active', label: 'in progress' }, { value: 'failed', label: 'failed' }, { value: 'finished', label: 'finished' },
]
const STATUS_BADGE: Record<LiveJob['status'], 'running' | 'queued' | 'finished' | 'failed' | 'cancelled'> = {
  running: 'running', queued: 'queued', completed: 'finished', failed: 'failed', cancelled: 'cancelled',
}

export function LocalJobsCard({ q, limit, onMore }: { q: LiveRead<LiveJob[]>; limit: number; onMore: () => void }) {
  const data = q.data
  const running = data?.filter(isActive).length ?? 0
  const failed = data?.filter(j => j.status === 'failed').length ?? 0
  const [kind, setKind] = useState<KindFilter>('all')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [open, setOpen] = useState<number | null>(null)
  // in progress first, then newest first: the rows a researcher waits on sit at the top whatever their id
  const shown = useMemo(() => (data ?? [])
    .filter(j => kind === 'all' ? true : kind === 'other' ? !['training', 'chain_run', 'import'].includes(j.kind) : j.kind === kind)
    .filter(j => status === 'all' ? true : status === 'active' ? isActive(j) : status === 'failed' ? j.status === 'failed' : j.status === 'completed')
    .sort((a, b) => Number(isActive(b)) - Number(isActive(a)) || b.id - a.id), [data, kind, status])
  return (
    <section className="jb-live-card" data-testid="live-local-jobs" id="jobs-live-local">
      <div className="head">
        <Icon name="cpu" size={14} />
        <h3>In progress here · this bridge's jobs</h3>
        <Chip tone="green" size="sm" testid="live-chip-local">live</Chip>
        <span className="jb-mono jb-small jb-muted" data-testid="live-local-summary">{running} in progress{failed ? ` · ${failed} failed` : ''}{data ? ` · ${data.length} listed` : ''}</span>
        <span className="jb-spacer" />
        <Seg options={STATUS_FILTERS} value={status} onChange={v => setStatus(v as StatusFilter)} testid="local-status-filter" ariaLabel="filter local jobs by state" size="sm" />
        <Seg options={KIND_FILTERS} value={kind} onChange={v => setKind(v as KindFilter)} testid="live-kind-filter" ariaLabel="filter local jobs by kind" size="sm" />
      </div>
      {q.error && !data && <LoadFailed what="the bridge's jobs" error={q.error} onRetry={q.reload} />}
      {!data && q.loading && <Loading height={120} testid="live-local-loading" />}
      {data && !shown.length && <EmptyState size="sm" bordered testid="live-local-empty" icon="cpu"
        title={data.length ? (status === 'active' ? 'Nothing is in progress here' : 'No job matches these filters') : 'No jobs have run on this bridge'}
        caption="training a model, building a window set or a tree, labelling work, sweeps and imports are listed here as they run" />}
      {data && !!shown.length && (
        <table className="jb-table jb-live" data-testid="live-local-table">
          <colgroup><col style={{ width: 56 }} /><col /><col style={{ width: 210 }} /><col style={{ width: 150 }} /><col style={{ width: 96 }} /><col style={{ width: 132 }} /></colgroup>
          <thead><tr><th>id</th><th>job · stage</th><th>state · progress</th><th>started</th><th>took</th><th /></tr></thead>
          <tbody>
            {shown.map(j => (
              <LocalRow key={j.id} j={j} open={open === j.id} onToggle={() => setOpen(open === j.id ? null : j.id)} onCancelled={q.reload} />
            ))}
          </tbody>
        </table>
      )}
      {data && data.length >= limit && <Button size="sm" variant="link" testid="live-local-more" onClick={onMore}>show older jobs</Button>}
    </section>
  )
}

function LocalRow({ j, open, onToggle, onCancelled }: { j: LiveJob; open: boolean; onToggle: () => void; onCancelled: () => void }) {
  const active = isActive(j)
  return (
    <>
      <tr className={`jb-tr ${open ? 'sel' : ''} ${j.status === 'failed' ? 'bad' : ''}`} data-testid={`live-job-row-${j.id}`} data-status={j.status} data-kind={j.kind}
        tabIndex={0} onClick={onToggle} onKeyDown={e => { if (e.key === 'Enter') onToggle() }}>
        <td><span className="jb-id">{j.id}</span></td>
        <td>
          <span className="jb-job">
            <Icon name={j.kind === 'chain_run' ? 'branch' : j.kind === 'import' ? 'download' : j.kind === 'sweep' ? 'target' : 'cpu'} size={13} className="ic" />
            <span className="txt">
              <div className="t" title={j.stage}>{j.stage}</div>
              <div className="s">{j.kindLabel} · {j.where}{j.restored ? ' · from the job table' : ''}</div>
            </span>
          </span>
        </td>
        <td data-testid={`live-job-status-${j.id}`} data-status={j.status}>
          {active ? (
            <span className="jb-prog">
              {j.fraction != null ? <ProgressBar value={j.fraction} width={86} size="sm" labelPosition="none" /> : <ProgressBar indeterminate width={86} size="sm" labelPosition="none" />}
              <span className="jb-muted">{j.fraction != null ? `${Math.round(j.fraction * 100)} %` : j.status}</span>
            </span>
          ) : <Badge status={STATUS_BADGE[j.status]} />}
          {j.message && <div className="jb-live-msg" title={j.message}>{j.message}</div>}
          {j.status === 'failed' && j.error && <div className="jb-live-msg jb-red" title={j.error.message}>{j.error.message}</div>}
        </td>
        <td><span className="jb-time">{fmtWhen(j.started)}</span></td>
        <td><span className="jb-time">{fmtDur(j.durationS)}</span></td>
        <td className="jb-act" onClick={e => e.stopPropagation()}>
          {active && j.kind !== 'chain_run' && <Button size="sm" variant="link" testid={`live-job-cancel-${j.id}`} onClick={() => { void cancelJob(j.id).then(onCancelled, onCancelled) }}>Cancel</Button>}
          {j.route && <Button size="sm" variant="link" icon="external" testid={`live-job-open-${j.id}`} onClick={() => navigate(j.route!)}>{j.routeLabel}</Button>}
        </td>
      </tr>
      {open && (
        <tr className="jb-live-detail"><td colSpan={6} data-testid={`live-job-detail-${j.id}`}>
          <div className="jb-row wrap jb-small jb-mono">
            <span>job {j.id} · {j.kindLabel} · {j.status}</span><span>started {fmtWhen(j.started)}</span>
            <span>{j.finished ? `finished ${fmtWhen(j.finished)}` : 'not finished'}</span><span>took {fmtDur(j.durationS)}</span>
            {j.jobDir && <span>directory {j.jobDir}</span>}
          </div>
          {j.message && <div className="jb-small jb-mono">last message: {j.message}</div>}
          {j.error ? (
            <div className="error-card" data-testid={`live-job-error-${j.id}`}>
              <h3>{j.error.type}: {j.error.message}</h3>
              {j.error.traceback
                ? <pre className="jb-trace" data-testid={`live-job-traceback-${j.id}`}>{j.error.traceback}</pre>
                : <div className="jb-small jb-muted">no traceback was kept for this error</div>}
            </div>
          ) : <div className="jb-small jb-muted">no error</div>}
        </td></tr>
      )}
    </>
  )
}

/* ------------------------------------------------------------------ the inbox import (one follower for row + inbox) */
export interface ImportFollow {
  path: string; jobId: number | null; status: 'starting' | 'running' | 'completed' | 'failed' | 'cancelled' | 'error'
  message: string; errorType?: string; traceback?: string; result?: { kind?: string; run_id?: number; created?: boolean; message?: string } | null
}

/** Start an inbox import and follow its job until it ends; `onEnd` reloads whatever lists depend on it. */
export function useImport(onEnd: () => void) {
  const [cur, setCur] = useState<ImportFollow | null>(null)
  const timer = useRef<number | null>(null)
  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current) }, [])
  const follow = useCallback((path: string, id: number) => {
    const tick = () => {
      getJob(id).then((j: JobRow) => {
        const err = j.error
        const prog = (j.progress ?? {}) as { message?: string }
        const done = j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled'
        setCur({ path, jobId: id, status: j.status === 'queued' ? 'running' : j.status, message: err ? err.message.replace(/^\w+: /, '') : prog.message ?? '',
          errorType: err?.type, traceback: err?.traceback, result: (j.result ?? null) as ImportFollow['result'] })
        if (done) onEnd(); else timer.current = window.setTimeout(tick, 600)
      }, (e: unknown) => setCur({ path, jobId: id, status: 'error', message: e instanceof Error ? e.message : String(e) }))
    }
    tick()
  }, [onEnd])
  const start = useCallback((path: string) => {
    setCur({ path, jobId: null, status: 'starting', message: 'starting the import…' })
    importReturnedJob(path).then(s => follow(path, s.job_id),
      (e: unknown) => setCur({ path, jobId: null, status: 'error', message: e instanceof Error ? e.message : String(e) }))
  }, [follow])
  return { cur, start, clear: () => setCur(null) }
}

/* ------------------------------------------------------------------ the seed-result import (a result file, by path) */
export interface SeedImportFollow { path: string; status: 'running' | 'done' | 'refused'; message: string; runKey?: string; jobId?: number | null }

/** Import a seed job's result file through the Seed page's own import; a refusal is the message, nothing is stored. */
export function useSeedImport(onEnd: () => void) {
  const [cur, setCur] = useState<SeedImportFollow | null>(null)
  const start = useCallback((path: string) => {
    setCur({ path, status: 'running', message: 'checking the result against the session and its spec…' })
    importSeedResult(path).then(
      ack => { setCur({ path, status: 'done', message: ack.note ?? `imported as ${ack.label}`, runKey: ack.run_key, jobId: ack.job_id }); onEnd() },
      (e: unknown) => { setCur({ path, status: 'refused', message: (e instanceof Error ? e.message : String(e)).replace(/^\d{3} /, '') }); onEnd() })
  }, [onEnd])
  return { cur, start, clear: () => setCur(null) }
}

/* ------------------------------------------------------------------ waiting on the cluster */
const STATE_LABEL: Record<ClusterState, string> = {
  written: 'written · waiting for results', partial: 'running on the cluster · checkpoint back', returned: 'results back · not imported',
  importing: 'importing…', imported: 'results imported', refused: 'import refused', failed: 'import failed', unreadable: 'unreadable',
}
const STATE_TONE: Record<ClusterState, 'green' | 'amber' | 'blue' | 'grey' | 'red'> = {
  written: 'grey', partial: 'blue', returned: 'amber', importing: 'blue', imported: 'green', refused: 'red', failed: 'red', unreadable: 'red',
}
export function StateBadge({ row }: { row: ClusterJob }) {
  const s = row.state
  return (
    <Badge tone={STATE_TONE[s]} testid={`exported-state-${row.name}`} icon={s === 'imported' ? 'check-circle' : s === 'refused' || s === 'failed' || s === 'unreadable' ? 'x-circle' : s === 'partial' ? 'play' : undefined}>
      <span data-state={s}>{STATE_LABEL[s]}{s === 'imported' && row.imported?.run_id ? ` · run ${row.imported.run_id}` : ''}</span>
    </Badge>
  )
}

type ClusterFilter = 'all' | 'waiting' | 'to-import' | 'imported'
const CLUSTER_FILTERS: { value: ClusterFilter; label: string }[] = [
  { value: 'all', label: 'all' }, { value: 'waiting', label: 'waiting for results' }, { value: 'to-import', label: 'results back' }, { value: 'imported', label: 'imported' },
]
const inFilter = (r: ClusterJob, f: ClusterFilter) =>
  f === 'all' ? true : f === 'waiting' ? r.state === 'written' || r.state === 'partial'
    : f === 'to-import' ? r.state === 'returned' || r.state === 'refused' || r.state === 'failed' || r.state === 'importing'
      : r.state === 'imported'

export function ClusterJobsCard({ q, imp, seedImp }: { q: LiveRead<ClusterList>; imp: ReturnType<typeof useImport>; seedImp: ReturnType<typeof useSeedImport> }) {
  const data = q.data
  const [open, setOpen] = useState<string | null>(null)
  const [filter, setFilter] = useState<ClusterFilter>('all')
  const rows = useMemo(() => (data?.jobs ?? []).filter(r => inFilter(r, filter)), [data, filter])
  const c = data?.counts
  return (
    <section className="jb-live-card" data-testid="exported-jobs" id="jobs-cluster">
      <div className="head">
        <Icon name="server" size={14} />
        <h3>Waiting on the cluster · scripts the site wrote</h3>
        <Chip tone="green" size="sm" testid="live-chip-exported">live</Chip>
        <InfoTip title="Written here, run by you" testid="exported-info">
          The site writes a job directory or a script and never logs in to the cluster or submits anything: copy what a row
          lists, <code>sbatch</code> the script, bring the results back, then import them — from the row or the Manifest inbox.
          Three things write scripts: Models › Launch (the B.2 CNN, paired training), the Shape clustering page (Ward over every
          training window) and the Discovery Seed page (a seed search over the ceiling). A row's state is read from its folder,
          its result file and the database: <i>written</i>, <i>running on the cluster</i> (a seed job's checkpoint is back),
          <i> results back</i>, <i>results imported</i> (with the run) or <i>import refused</i> with the reason. A script whose
          results cannot come back through the site says so instead of offering an import.
        </InfoTip>
        <span className="jb-mono jb-small jb-muted" data-testid="cluster-summary" title={data?.roots.join('\n')}>
          {c ? `${c.waiting} waiting for results · ${c.to_import} back, to import · ${c.imported} imported` : ''}
        </span>
        <span className="jb-spacer" />
        <Seg options={CLUSTER_FILTERS} value={filter} onChange={v => setFilter(v as ClusterFilter)} testid="cluster-filter" ariaLabel="filter cluster jobs by state" size="sm" />
        <Button size="sm" variant="link" icon="refresh" testid="exported-refresh" onClick={q.reload}>Look again</Button>
      </div>
      {q.error && !data && <LoadFailed what="the jobs the site wrote for the cluster" error={q.error} onRetry={q.reload} />}
      {!data && q.loading && <Loading height={100} testid="exported-loading" />}
      {data && !rows.length && <EmptyState size="sm" bordered testid="exported-empty" icon="server"
        title={data.jobs.length ? 'No cluster job in this state' : 'Nothing is waiting on the cluster'}
        caption="Models › Launch (model: CNN) · Create SLURM script, the Shape clustering page's Ward over every training window, or the Seed page over the ceiling writes one"
        action={<Button size="sm" icon="external" onClick={() => navigate('models/launch')}>Models › Launch</Button>} />}
      {!!rows.length && (
        <table className="jb-table jb-live" data-testid="exported-table">
          <colgroup><col /><col style={{ width: 92 }} /><col style={{ width: 150 }} /><col style={{ width: 120 }} /><col style={{ width: 230 }} /><col style={{ width: 150 }} /></colgroup>
          <thead><tr><th>job</th><th>recipe</th><th>written</th><th>to copy</th><th>state</th><th /></tr></thead>
          <tbody>
            {rows.map(r => (
              <ClusterRow key={`${r.source}:${r.name}`} r={r} open={open === r.name} onToggle={() => setOpen(open === r.name ? null : r.name)}
                importing={(imp.cur?.path === r.import_path && (imp.cur.status === 'starting' || imp.cur.status === 'running'))
                  || (seedImp.cur?.path === r.import_path && seedImp.cur.status === 'running')}
                seedOutcome={r.import_how === 'seed' && seedImp.cur?.path === r.import_path ? seedImp.cur : null}
                onImport={() => { if (r.import_how === 'inbox' && r.import_path) imp.start(r.import_path); else if (r.import_how === 'seed' && r.import_path) seedImp.start(r.import_path) }} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function ClusterRow({ r, open, onToggle, importing, seedOutcome, onImport }: {
  r: ClusterJob; open: boolean; onToggle: () => void; importing: boolean; seedOutcome: SeedImportFollow | null; onImport: () => void
}) {
  const canImport = !!r.import_how && (r.state === 'returned' || r.state === 'refused' || r.state === 'failed')
  const why = !r.import_how ? (r.import_note ?? 'not imported through the site')
    : r.state === 'written' ? (r.import_how === 'seed' ? 'no result here yet: bring the seed job\'s …result.json back to where the row expects it first' : 'no results here yet: copy the job\'s out/ back from the cluster first')
      : r.state === 'partial' ? 'the job is still running on the cluster: only a checkpoint is back'
        : r.state === 'imported' ? 'already imported' : r.state === 'unreadable' ? 'the job cannot be read' : undefined
  const channels = r.copy.filter(c => c.what === 'channel array').length
  const title = r.source === 'seed' ? `${r.label ?? r.name}` : `${r.kind_label ?? 'unknown job'}${r.smoke ? ' · local smoke' : ''}`
  const sub = r.source === 'seed' ? `${r.kind_label} · ${r.name}` : `${r.name}${r.model ? ` · ${r.model}` : ''}`
  const openLabel = r.open ? (r.kind === 'shape_tree_full' ? 'Open in Analyse' : r.source === 'seed' ? 'Open in Discovery' : 'Open in Results') : ''
  return (
    <>
      <tr className={`jb-tr ${open ? 'sel' : ''}`} data-testid={`exported-row-${r.name}`} data-state={r.state} data-kind={r.kind ?? ''} data-source={r.source}
        tabIndex={0} onClick={onToggle} onKeyDown={e => { if (e.key === 'Enter') onToggle() }}>
        <td>
          <span className="jb-job">
            <Icon name={r.kind === 'shape_tree_full' ? 'branch' : r.source === 'seed' ? 'target' : r.kind === 'detection_chain' ? 'target' : 'cpu'} size={13} className="ic" />
            <span className="txt">
              <div className="t" title={r.job_dir ?? r.scripts[0]?.path ?? r.name}>{title}<WsTag ws={r.workspace} /></div>
              <div className="s" title={r.job_dir ?? r.scripts[0]?.path ?? ''}>{sub}</div>
            </span>
          </span>
        </td>
        <td><span className="jb-mono" title={r.recipe_ok === false ? 'recipe.json no longer matches the hash it was written with' : 'the hash the import checks'}>{r.recipe_hash ?? '—'}{r.recipe_ok === false && <span className="jb-red"> ✕</span>}</span></td>
        <td><span className="jb-time">{isoWhen(r.written_at)}</span></td>
        <td data-testid={`exported-copy-size-${r.name}`}>{r.copy.length ? <><span className="jb-mono">{fmtBytes(r.total_bytes)}</span><div className="jb-live-msg">{r.source === 'job_dir' ? `job folder${channels ? ` + ${channels} channel arrays` : ''}` : r.source === 'seed' ? 'spec + script' : 'recipe + script'}</div></> : <span className="jb-muted">—</span>}</td>
        <td>
          <StateBadge row={r} />
          {r.state === 'partial' && r.progress && <div className="jb-live-msg" data-testid={`exported-progress-${r.name}`}>{r.progress.channels_done} of {r.progress.channels ?? '?'} channels in the checkpoint</div>}
          {r.reason && <div className="jb-live-msg jb-red" data-testid={`exported-reason-${r.name}`} title={r.reason}>{r.reason}</div>}
          {r.error && <div className="jb-live-msg jb-red" title={r.error}>{r.error}</div>}
          {seedOutcome && seedOutcome.status !== 'running' && (
            <div className={`jb-live-msg ${seedOutcome.status === 'done' ? 'jb-green' : 'jb-red'}`} data-testid={`seed-outcome-${r.name}`} data-outcome={seedOutcome.status} title={seedOutcome.message}>{seedOutcome.message}</div>
          )}
        </td>
        <td className="jb-act" onClick={e => e.stopPropagation()}>
          {r.open
            ? <Button size="sm" variant="link" icon="external" testid={`exported-open-${r.name}`} title={r.open.label} onClick={() => navigate(r.open!.route)}>{openLabel}</Button>
            : <Button size="sm" variant={canImport ? 'primary' : 'default'} icon="download" loading={importing} disabled={!canImport} disabledReason={why}
                testid={r.import_how === 'seed' ? `seed-import-${r.name}` : `exported-import-${r.name}`} onClick={onImport}>{r.import_how === 'seed' ? 'Import result' : 'Import results'}</Button>}
        </td>
      </tr>
      {open && (
        <tr className="jb-live-detail"><td colSpan={6} data-testid={`exported-detail-${r.name}`}>
          {r.reason && <div className="jb-inbox-outcome red" data-testid={`exported-reason-full-${r.name}`}><div className="t">{r.state === 'refused' ? 'Import refused — nothing was recorded' : r.state === 'failed' ? 'The import failed' : 'Not this job\'s result'}</div><div className="jb-small">{r.reason}</div></div>}
          {r.open && r.imported && <div className="jb-small" data-testid={`exported-imported-${r.name}`}>imported{r.imported.run_id != null ? <> as run <b>{r.imported.run_id}</b></> : ''}{r.imported.name ? ` · ${r.imported.name}` : ''}{r.imported.at ? ` · ${isoWhen(r.imported.at)}` : ''}</div>}
          {r.source === 'seed' && (
            <div className="jb-small jb-mono" data-testid={`exported-seed-${r.name}`}>
              seed search <b>{r.label}</b> · run <b>{r.run_key}</b>{r.session ? ` · session ${r.session}` : ''}{r.run_status ? ` · row ${r.run_status}` : ''}
              {r.draws != null ? ` · ${r.draws} null draws` : ''}{r.estimate_s != null ? ` · about ${fmtDur(r.estimate_s)} on the cluster` : ''}
            </div>
          )}
          {r.job_repo && <div className="jb-small jb-mono">folder <b>{r.job_repo}</b>{r.job_repo !== r.job_dir && <> · on this machine {r.job_dir}</>}</div>}
          {r.sbatch_command
            ? <div className="jb-small jb-mono" data-testid={`exported-sbatch-${r.name}`}>on the cluster, from the repository root: <b>{r.sbatch_command}</b>{r.scripts.length > 1 && <> · also {r.scripts.filter(s => !r.sbatch_command!.endsWith(s.repo)).map(s => s.name).join(', ')}</>}</div>
            : <div className="jb-small jb-muted">no script: {r.smoke ? 'the local smoke ran here, on this CPU' : r.source === 'seed' ? 'none is recorded on this row — its result file was imported on the Seed page' : 'none was written for this job'}</div>}
          {!!r.copy.length && <>
            <div className="jb-label" style={{ marginTop: 6 }}>what to copy to the cluster — {fmtBytes(r.total_bytes)} in all, to the same repository-relative paths</div>
            <table className="jb-copy" data-testid={`exported-copy-${r.name}`}>
              <tbody>
                {r.copy.map(c => (
                  <tr key={c.what + c.path}><td>{c.what}</td><td className="p">{c.path}</td><td className="b">{fmtBytes(c.bytes)}</td><td className="n">{c.note ?? ''}</td></tr>
                ))}
              </tbody>
            </table>
          </>}
          {r.source === 'job_dir' && <div className="jb-small jb-muted">never copied: <code>cache/</code> (built on the cluster) and <code>out/</code> (what comes back)</div>}
          {r.source === 'seed' && r.result_path && <div className="jb-small jb-mono" data-testid={`exported-result-${r.name}`}>the result comes back to <b>{r.result_path}</b>{r.state === 'written' ? ' — nothing there yet' : ''}; the script checkpoints into it after every channel and resubmits itself while it reads incomplete</div>}
          {r.returned && <div className="jb-small jb-mono">{r.source === 'seed' ? 'result file' : 'out/done.json'}: {r.returned.status} · {r.source === 'seed' ? 'spec' : 'recipe'} {r.returned.recipe_hash ?? '?'}{r.returned.finished_at ? ` · finished ${isoWhen(r.returned.finished_at)}` : ''}</div>}
          {r.import_note && <div className="jb-small jb-muted" data-testid={`exported-no-import-${r.name}`}>{r.import_note}</div>}
          {r.last_attempt && <div className="jb-small jb-mono">last import: job {r.last_attempt.job_id} · {r.last_attempt.outcome}{r.last_attempt.message ? ` · ${r.last_attempt.message}` : ''}</div>}
          {r.last_attempt?.traceback && <pre className="jb-trace">{r.last_attempt.traceback}</pre>}
          {r.open?.note && <div className="jb-small" data-testid={`exported-open-note-${r.name}`}>{r.open.note}</div>}
        </td></tr>
      )}
    </>
  )
}

/* ------------------------------------------------------------------ waiting in review */
export function ReviewQueuesCard({ q }: { q: LiveRead<ReviewQueue[]> }) {
  const data = q.data
  const queues = useMemo(() => [...(data ?? [])].sort((a, b) => (b.total - b.judged) - (a.total - a.judged) || Number(b.id) - Number(a.id)), [data])
  const left = queues.reduce((n, x) => n + Math.max(0, x.total - x.judged), 0)
  return (
    <section className="jb-live-card" data-testid="review-queues" id="jobs-review">
      <div className="head">
        <Icon name="checklist" size={14} />
        <h3>Waiting in review · open queues</h3>
        <Chip tone="green" size="sm" testid="live-chip-review">live</Chip>
        <span className="jb-mono jb-small jb-muted" data-testid="review-summary">{data ? `${queues.length} open queue${queues.length === 1 ? '' : 's'} · ${left} still to judge` : ''}</span>
        <span className="jb-spacer" />
        <Button size="sm" variant="link" icon="external" testid="review-open-workspace" onClick={() => navigate('review')}>Open Review</Button>
      </div>
      {q.error && !data && <LoadFailed what="the review queues" error={q.error} onRetry={q.reload} />}
      {!data && q.loading && <Loading height={100} testid="review-loading" />}
      {data && !queues.length && <EmptyState size="sm" bordered testid="review-queues-empty" icon="checklist" title="No open review queue"
        caption="a run's detections, a training set's windows or a family's members are sent to Review from their own page; the queue then waits here until it is judged" />}
      {!!queues.length && (
        <table className="jb-table jb-live" data-testid="review-table">
          <colgroup><col style={{ width: 56 }} /><col /><col style={{ width: 200 }} /><col style={{ width: 110 }} /><col style={{ width: 150 }} /><col style={{ width: 132 }} /></colgroup>
          <thead><tr><th>queue</th><th>what is judged</th><th>judged</th><th>left</th><th>pace</th><th /></tr></thead>
          <tbody>
            {queues.map(x => {
              const remaining = Math.max(0, x.total - x.judged)
              const frac = x.total ? x.judged / x.total : 0
              const eta = x.paceS != null && remaining ? remaining * x.paceS : null
              return (
                <tr key={x.id} className="jb-tr" data-testid={`review-queue-row-${x.id}`} data-remaining={remaining} tabIndex={0}
                  onClick={() => navigate(`review/queue/${x.id}`)} onKeyDown={e => { if (e.key === 'Enter') navigate(`review/queue/${x.id}`) }}>
                  <td><span className="jb-id">q-{x.id}</span></td>
                  <td>
                    <span className="jb-job">
                      <Icon name="checklist" size={13} className="ic" />
                      <span className="txt">
                        <div className="t" title={x.title}>{x.title}{x.blind && <Badge status="blind" />}</div>
                        <div className="s" title={x.subtitle}>{x.source.replace(/-/g, ' ')} · {x.subtitle}</div>
                      </span>
                    </span>
                  </td>
                  <td>
                    <span className="jb-prog"><ProgressBar value={frac} width={96} size="sm" tone="green" labelPosition="none" /><span className="jb-muted">{x.judged} / {x.total}</span></span>
                  </td>
                  <td><span className={`jb-mono ${remaining ? '' : 'jb-green'}`}>{remaining ? `${remaining} left` : 'all judged'}</span></td>
                  <td><span className="jb-time">{x.judged === 0 ? 'nothing judged yet' : x.paceS == null ? 'no pace yet' : `~${x.paceS < 1 ? '< 1 s' : fmtDur(x.paceS)} each${eta != null ? ` · ${fmtDur(eta)} left` : ''}`}</span></td>
                  <td className="jb-act" onClick={e => e.stopPropagation()}>
                    <Button size="sm" variant={remaining ? 'primary' : 'link'} icon="checklist" testid={`review-open-${x.id}`} onClick={() => navigate(`review/queue/${x.id}`)}>{remaining ? 'Judge' : 'Open'}</Button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </section>
  )
}

/* ------------------------------------------------------------------ the Manifest inbox */
export function InboxLive({ imp, cluster, attempts }: { imp: ReturnType<typeof useImport>; cluster: ClusterList | null; attempts: LiveRead<{ attempts: ImportAttempt[]; roots: string[] }> }) {
  const [path, setPath] = useState('')
  const waiting = useMemo(() => (cluster?.jobs ?? []).filter(j => j.state === 'returned' && j.import_how === 'inbox'), [cluster])
  const seedsBack = useMemo(() => (cluster?.jobs ?? []).filter(j => j.state === 'returned' && j.import_how === 'seed'), [cluster])
  const cur = imp.cur
  const busy = cur?.status === 'starting' || cur?.status === 'running'
  const openRoute = cur?.status === 'completed'
    ? (cur.result?.kind === 'shape_cluster_cnn' && cur.result.run_id ? `models/results/b2/${cur.result.run_id}`
      : (cluster?.jobs ?? []).find(j => j.job_dir === cur.path)?.open?.route ?? null)
    : null
  return (
    <div className="jb-col" data-testid="inbox-live">
      <div className="jb-row"><Chip tone="green" size="sm">live</Chip><span className="jb-small jb-muted">import a job directory the cluster's results were copied back into</span></div>
      <div className="jb-small jb-muted">
        Checked before anything is stored, by the same function as <code>python -m Working.training import-results</code>:
        the recipe hash (recipe.json = job.json = out/done.json), the windows, the pool in this database, one prediction
        per predicted window, and a cut not changed on a scored pool. A mismatch is refused with the reason.
      </div>
      <div className="jb-row">
        <TextField value={path} onChange={setPath} placeholder="the returned job folder, e.g. HPC/Training/generated/b2cnn_fusion_…" block
          testid="inbox-path" ariaLabel="returned job directory" onEnter={() => { if (path.trim() && !busy) imp.start(path.trim()) }} />
        <Button variant="primary" icon="download" testid="inbox-import" loading={busy} disabled={!path.trim()} disabledReason="name the folder first"
          onClick={() => imp.start(path.trim())}>Import</Button>
      </div>
      {!!waiting.length && (
        <div className="jb-col" data-testid="inbox-waiting">
          <div className="jb-label">results copied back, not imported yet</div>
          {waiting.map(w => (
            <div key={w.job_dir} className="jb-row jb-small jb-mono">
              <Icon name="folder" size={12} /><span className="jb-ellipsis" title={w.job_dir ?? ''}>{w.name}</span><span className="jb-spacer" />
              <Button size="sm" variant="link" testid={`inbox-pick-${w.name}`} onClick={() => setPath(w.job_dir ?? '')}>use this folder</Button>
            </div>
          ))}
        </div>
      )}
      {!!seedsBack.length && (
        <div className="jb-small jb-muted" data-testid="inbox-seeds-back">
          {seedsBack.length} seed-search result{seedsBack.length === 1 ? ' is' : 's are'} back as well — a result file, not a folder: import {seedsBack.length === 1 ? 'it' : 'each'} from its row under <i>Waiting on the cluster</i>.
        </div>
      )}
      {cur && (
        <div className={`jb-inbox-outcome ${cur.status === 'completed' ? 'green' : busy ? 'blue' : 'red'}`} data-testid="inbox-outcome" data-outcome={busy ? 'importing' : cur.status === 'completed' ? 'imported' : cur.errorType === 'ImportRefused' || cur.errorType === 'CutFrozen' ? 'refused' : 'failed'}>
          <div className="t">
            {busy ? 'Importing…' : cur.status === 'completed' ? (cur.result?.created === false ? 'Already imported' : 'Results imported')
              : cur.errorType === 'ImportRefused' || cur.errorType === 'CutFrozen' ? 'Import refused — nothing was recorded' : 'The import failed'}
            {cur.jobId != null && <span className="jb-muted jb-small"> · job {cur.jobId}</span>}
          </div>
          <div className="jb-small jb-mono jb-ellipsis" title={cur.path}>{cur.path}</div>
          <div className="jb-small" data-testid="inbox-outcome-message">{cur.message}</div>
          {cur.status === 'failed' && cur.errorType !== 'ImportRefused' && cur.errorType !== 'CutFrozen' && cur.traceback && <pre className="jb-trace">{cur.traceback}</pre>}
          {openRoute && <Button size="sm" variant="primary" icon="external" testid="inbox-open" onClick={() => navigate(openRoute)}>Open {openRoute.startsWith('models') ? 'in Models › Results' : 'in Analyse'}</Button>}
        </div>
      )}
      <div className="jb-label">import attempts</div>
      {attempts.error && !attempts.data && <LoadFailed what="the import attempts" error={attempts.error} onRetry={attempts.reload} />}
      {attempts.data && !attempts.data.attempts.length && <div className="jb-small jb-muted" data-testid="inbox-attempts-empty">none yet</div>}
      {attempts.data && !!attempts.data.attempts.length && (
        <div className="jb-col" data-testid="inbox-attempts">
          {attempts.data.attempts.slice(0, 12).map(a => <Attempt key={a.job_id} a={a} />)}
        </div>
      )}
    </div>
  )
}

function Attempt({ a }: { a: ImportAttempt }) {
  const tone = a.outcome === 'imported' ? 'green' : a.outcome === 'importing' ? 'blue' : 'red'
  return (
    <div className={`jb-attempt ${tone}`} data-testid={`inbox-attempt-${a.job_id}`} data-outcome={a.outcome}>
      <div className="jb-row jb-small"><b>{a.outcome}</b><span className="jb-muted">job {a.job_id} · {isoWhen(a.started_at)}</span></div>
      <div className="jb-small jb-mono jb-ellipsis" title={a.job_dir ?? ''}>{a.job_dir}</div>
      {a.message && <div className="jb-small">{a.message}</div>}
    </div>
  )
}

