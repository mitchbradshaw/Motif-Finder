/* fixup-aj — the parts of Jobs that are real (ticket `docs/prompts/fixup/AJ-jobs-usable-for-rq1.md`):
 *  · Running here — the bridge's own job table (training, chain runs that build trees, window sets, blind-queue work,
 *    imports): state, stage, progress, started, duration, the error with its traceback;
 *  · SLURM scripts written — every job directory the site wrote for the cluster (fixup-AI's B.2 CNN and the
 *    full-pool Ward, and the local smoke's directory), its recipe hash, when, what to copy and how big, and its state:
 *    written · results copied back · results imported (opens the run) · import refused (why);
 *  · the Manifest inbox — a returned job directory imported through `hpc_import.import_results`, the function
 *    `python -m Working.training import-results` calls.
 * The site never logs in to the cluster or submits anything: you copy, `sbatch`, and copy `out/` back. */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Badge, Button, Chip, EmptyState, Icon, InfoTip, ProgressBar, Seg, TextField } from '../kit'
import { useSourced } from '../api/seam'
import { getJob, cancelJob, type JobRow } from '../api'
import {
  getExportedJobs, getInboxAttempts, getLocalJobs, importReturnedJob,
  type ExportedJob, type ExportedState, type ImportAttempt, type LiveJob,
} from '../api/jobs'
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
const isoWhen = (v: string | number | null | undefined) => fmtWhen(v == null ? null : typeof v === 'number' ? new Date(v * 1000) : new Date(v))

/** Re-run `reload` every `ms` (and pause while the tab is hidden). */
function usePoll(reload: () => void, ms: number) {
  const ref = useRef(reload)
  ref.current = reload
  useEffect(() => {
    const t = window.setInterval(() => { if (document.visibilityState !== 'hidden') ref.current() }, ms)
    return () => window.clearInterval(t)
  }, [ms])
}

/** Keep the last good data while a poll reloads, so the table does not flash. */
function useSticky<T>(data: T | null): T | null {
  const [kept, setKept] = useState<T | null>(data)
  useEffect(() => { if (data != null) setKept(data) }, [data])
  return data ?? kept
}

/* ------------------------------------------------------------------ running here */
type KindFilter = 'all' | 'training' | 'chain_run' | 'import' | 'other'
const KIND_FILTERS: { value: KindFilter; label: string }[] = [
  { value: 'all', label: 'all' }, { value: 'training', label: 'training · window sets · blind' },
  { value: 'chain_run', label: 'chain runs (trees)' }, { value: 'import', label: 'imports' }, { value: 'other', label: 'other' },
]
const STATUS_BADGE: Record<LiveJob['status'], 'running' | 'queued' | 'finished' | 'failed' | 'cancelled'> = {
  running: 'running', queued: 'queued', completed: 'finished', failed: 'failed', cancelled: 'cancelled',
}

export function LocalJobsCard({ onCount }: { onCount?: (running: number) => void }) {
  const [limit, setLimit] = useState(25)
  const q = useSourced(() => getLocalJobs(limit), [limit])
  const data = useSticky(q.data)
  const anyRunning = !!data?.some(j => j.status === 'running' || j.status === 'queued')
  usePoll(q.reload, anyRunning ? 2000 : 8000)
  const running = data?.filter(j => j.status === 'running' || j.status === 'queued').length ?? 0
  useEffect(() => { onCount?.(running) }, [running, onCount])
  const [filter, setFilter] = useState<KindFilter>('all')
  const [open, setOpen] = useState<number | null>(null)
  const shown = (data ?? []).filter(j => filter === 'all' ? true : filter === 'other'
    ? !['training', 'chain_run', 'import'].includes(j.kind) : j.kind === filter)
  return (
    <section className="jb-live-card" data-testid="live-local-jobs" id="jobs-live-local">
      <div className="head">
        <Icon name="cpu" size={14} />
        <h3>Running here · this bridge's jobs</h3>
        <Chip tone="green" size="sm" testid="live-chip-local">live</Chip>
        <span className="jb-mono jb-small jb-muted">{running} running · newest first · {data ? `${data.length} shown` : ''}</span>
        <span className="jb-spacer" />
        <Seg options={KIND_FILTERS} value={filter} onChange={v => setFilter(v as KindFilter)} testid="live-kind-filter" ariaLabel="filter local jobs by kind" size="sm" />
      </div>
      {q.error && !data && <LoadFailed what="the bridge's jobs" error={q.error} onRetry={q.reload} />}
      {!data && q.loading && <Loading height={120} testid="live-local-loading" />}
      {data && !shown.length && <EmptyState size="sm" bordered testid="live-local-empty" icon="cpu" title={data.length ? 'No job of this kind' : 'No jobs have run on this bridge'}
        caption="training a model, building a window set or a tree, labelling work and imports are listed here as they run" />}
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
      {data && data.length >= limit && <Button size="sm" variant="link" testid="live-local-more" onClick={() => setLimit(l => l + 100)}>show older jobs</Button>}
    </section>
  )
}

function LocalRow({ j, open, onToggle, onCancelled }: { j: LiveJob; open: boolean; onToggle: () => void; onCancelled: () => void }) {
  const active = j.status === 'running' || j.status === 'queued'
  return (
    <>
      <tr className={`jb-tr ${open ? 'sel' : ''} ${j.status === 'failed' ? 'bad' : ''}`} data-testid={`live-job-row-${j.id}`} data-status={j.status} data-kind={j.kind}
        tabIndex={0} onClick={onToggle} onKeyDown={e => { if (e.key === 'Enter') onToggle() }}>
        <td><span className="jb-id">{j.id}</span></td>
        <td>
          <span className="jb-job">
            <Icon name={j.kind === 'chain_run' ? 'branch' : j.kind === 'import' ? 'download' : 'cpu'} size={13} className="ic" />
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
              <span className="jb-muted">{j.fraction != null ? `${Math.round(j.fraction * 100)} %` : 'running'}</span>
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

/* ------------------------------------------------------------------ the import (one follower for row + inbox) */
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

/* ------------------------------------------------------------------ SLURM scripts written */
const STATE_LABEL: Record<ExportedState, string> = {
  written: 'written', returned: 'results copied back · not imported', importing: 'importing…', imported: 'results imported',
  refused: 'import refused', failed: 'import failed', unreadable: 'unreadable',
}
export function ExportedBadge({ row }: { row: ExportedJob }) {
  const s = row.state
  const tone = s === 'imported' ? 'green' : s === 'returned' ? 'amber' : s === 'importing' ? 'blue' : s === 'written' ? 'grey' : 'red'
  return (
    <Badge tone={tone} testid={`exported-state-${row.name}`} icon={s === 'imported' ? 'check-circle' : s === 'refused' || s === 'failed' || s === 'unreadable' ? 'x-circle' : undefined}>
      <span data-state={s}>{STATE_LABEL[s]}{s === 'imported' && row.imported ? ` · run ${row.imported.run_id}` : ''}</span>
    </Badge>
  )
}

export function ExportedJobsCard({ imp, reloadKey }: { imp: ReturnType<typeof useImport>; reloadKey: number }) {
  const q = useSourced(getExportedJobs, [reloadKey])
  const data = useSticky(q.data)
  usePoll(q.reload, data?.jobs.some(j => j.state === 'importing') ? 1500 : 10000)
  const [open, setOpen] = useState<string | null>(null)
  const rows = data?.jobs ?? []
  return (
    <section className="jb-live-card" data-testid="exported-jobs">
      <div className="head">
        <Icon name="server" size={14} />
        <h3>SLURM scripts written · for the cluster</h3>
        <Chip tone="green" size="sm" testid="live-chip-exported">live</Chip>
        <InfoTip title="Written here, run by you" testid="exported-info">
          The site writes a job directory and its script (Models › Launch · <i>Create SLURM script</i> for the B.2 CNN; the
          Shape clustering page for Ward over every training window). It never logs in to the cluster or submits anything:
          copy what is listed, <code>sbatch</code> the script, copy the job's <code>out/</code> back into the same folder here,
          then import it — from this row or the Manifest inbox. The state is read from the folder and the database:
          <i> written</i>, <i>results copied back</i>, <i>results imported</i> (the run), or <i>import refused</i> with the reason.
        </InfoTip>
        <span className="jb-spacer" />
        <span className="jb-mono jb-small jb-muted" title={data?.roots.join('\n')}>{rows.length} job folder{rows.length === 1 ? '' : 's'} · {data?.mode ?? ''}</span>
        <Button size="sm" variant="link" icon="refresh" testid="exported-refresh" onClick={q.reload}>Look again</Button>
      </div>
      {q.error && !data && <LoadFailed what="the job directories the site wrote" error={q.error} onRetry={q.reload} />}
      {!data && q.loading && <Loading height={100} testid="exported-loading" />}
      {data && !rows.length && <EmptyState size="sm" bordered testid="exported-empty" icon="server" title="No SLURM script written yet"
        caption="Models › Launch (model: CNN) · Create SLURM script, or the Shape clustering page's Ward over every training window, writes one"
        action={<Button size="sm" icon="external" onClick={() => navigate('models/launch')}>Models › Launch</Button>} />}
      {!!rows.length && (
        <table className="jb-table jb-live" data-testid="exported-table">
          <colgroup><col /><col style={{ width: 92 }} /><col style={{ width: 150 }} /><col style={{ width: 150 }} /><col style={{ width: 210 }} /><col style={{ width: 150 }} /></colgroup>
          <thead><tr><th>job</th><th>recipe</th><th>written</th><th>to copy</th><th>state</th><th /></tr></thead>
          <tbody>
            {rows.map(r => (
              <ExportedRow key={r.job_dir} r={r} open={open === r.name} onToggle={() => setOpen(open === r.name ? null : r.name)}
                importing={imp.cur?.path === r.job_dir && (imp.cur.status === 'starting' || imp.cur.status === 'running')} onImport={() => imp.start(r.job_dir)} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function ExportedRow({ r, open, onToggle, importing, onImport }: { r: ExportedJob; open: boolean; onToggle: () => void; importing: boolean; onImport: () => void }) {
  const canImport = r.state === 'returned' || r.state === 'refused' || r.state === 'failed'
  const why = r.state === 'written' ? 'no results here yet: copy the job\'s out/ back from the cluster first'
    : r.state === 'imported' ? 'already imported' : r.state === 'unreadable' ? 'the job directory cannot be read' : undefined
  const channels = r.copy.filter(c => c.what === 'channel array').length
  return (
    <>
      <tr className={`jb-tr ${open ? 'sel' : ''}`} data-testid={`exported-row-${r.name}`} data-state={r.state} data-kind={r.kind ?? ''}
        tabIndex={0} onClick={onToggle} onKeyDown={e => { if (e.key === 'Enter') onToggle() }}>
        <td>
          <span className="jb-job">
            <Icon name={r.kind === 'shape_tree_full' ? 'branch' : 'cpu'} size={13} className="ic" />
            <span className="txt">
              <div className="t" title={r.job_dir}>{r.kind_label ?? 'unknown job'}{r.smoke ? ' · local smoke' : ''}</div>
              <div className="s" title={r.job_dir}>{r.name}{r.model ? ` · ${r.model}` : ''}</div>
            </span>
          </span>
        </td>
        <td><span className="jb-mono" title={r.recipe_ok === false ? 'recipe.json no longer matches the hash it was written with' : 'the recipe hash the import checks'}>{r.recipe_hash ?? '—'}{r.recipe_ok === false && <span className="jb-red"> ✕</span>}</span></td>
        <td><span className="jb-time">{isoWhen(r.written_at)}</span></td>
        <td data-testid={`exported-copy-size-${r.name}`}><span className="jb-mono">{fmtBytes(r.total_bytes)}</span><div className="jb-live-msg">job folder{channels ? ` + ${channels} channel arrays` : ''}</div></td>
        <td>
          <ExportedBadge row={r} />
          {r.reason && <div className="jb-live-msg jb-red" data-testid={`exported-reason-${r.name}`} title={r.reason}>{r.reason}</div>}
          {r.error && <div className="jb-live-msg jb-red" title={r.error}>{r.error}</div>}
        </td>
        <td className="jb-act" onClick={e => e.stopPropagation()}>
          {r.open
            ? <Button size="sm" variant="link" icon="external" testid={`exported-open-${r.name}`} onClick={() => navigate(r.open!.route)}>{r.open.label.replace(/^Open /, 'Open ')}</Button>
            : <Button size="sm" variant={canImport ? 'primary' : 'default'} icon="download" loading={importing} disabled={!canImport} disabledReason={why}
                testid={`exported-import-${r.name}`} onClick={onImport}>Import results</Button>}
        </td>
      </tr>
      {open && (
        <tr className="jb-live-detail"><td colSpan={6} data-testid={`exported-detail-${r.name}`}>
          {r.reason && <div className="jb-inbox-outcome red" data-testid={`exported-reason-full-${r.name}`}><div className="t">{r.state === 'refused' ? 'Import refused — nothing was recorded' : 'The import failed'}</div><div className="jb-small">{r.reason}</div></div>}
          {r.open && r.imported && <div className="jb-small" data-testid={`exported-imported-${r.name}`}>imported as run <b>{r.imported.run_id}</b>{r.imported.name ? ` · ${r.imported.name}` : ''}</div>}
          <div className="jb-small jb-mono">folder <b>{r.job_repo}</b>{r.job_repo !== r.job_dir && <> · on this machine {r.job_dir}</>}</div>
          {r.sbatch_command
            ? <div className="jb-small jb-mono" data-testid={`exported-sbatch-${r.name}`}>on the cluster, from the repository root: <b>{r.sbatch_command}</b>{r.scripts.length > 1 && <> · also {r.scripts.filter(s => !r.sbatch_command!.endsWith(s.repo)).map(s => s.name).join(', ')}</>}</div>
            : <div className="jb-small jb-muted">no script: {r.smoke ? 'the local smoke ran here, on this CPU' : 'none was written in this folder'}</div>}
          <div className="jb-label" style={{ marginTop: 6 }}>what to copy to the cluster — {fmtBytes(r.total_bytes)} in all, to the same repository-relative paths</div>
          <table className="jb-copy" data-testid={`exported-copy-${r.name}`}>
            <tbody>
              {r.copy.map(c => (
                <tr key={c.what + c.path}><td>{c.what}</td><td className="p">{c.path}</td><td className="b">{fmtBytes(c.bytes)}</td><td className="n">{c.note ?? ''}</td></tr>
              ))}
            </tbody>
          </table>
          <div className="jb-small jb-muted">never copied: <code>cache/</code> (built on the cluster) and <code>out/</code> (what comes back)</div>
          {r.returned && <div className="jb-small jb-mono">out/done.json: {r.returned.status} · recipe {r.returned.recipe_hash ?? '?'}{r.returned.finished_at ? ` · finished ${isoWhen(r.returned.finished_at)}` : ''}</div>}
          {r.last_attempt && <div className="jb-small jb-mono">last import: job {r.last_attempt.job_id} · {r.last_attempt.outcome}{r.last_attempt.message ? ` · ${r.last_attempt.message}` : ''}</div>}
          {r.last_attempt?.traceback && <pre className="jb-trace">{r.last_attempt.traceback}</pre>}
          {r.open?.note && <div className="jb-small" data-testid={`exported-open-note-${r.name}`}>{r.open.note}</div>}
        </td></tr>
      )}
    </>
  )
}

/* ------------------------------------------------------------------ the Manifest inbox */
export function InboxLive({ imp, reloadKey }: { imp: ReturnType<typeof useImport>; reloadKey: number }) {
  const [path, setPath] = useState('')
  const att = useSourced(getInboxAttempts, [reloadKey])
  const exp = useSourced(getExportedJobs, [reloadKey])
  const waiting = useMemo(() => (exp.data?.jobs ?? []).filter(j => j.state === 'returned'), [exp.data])
  const cur = imp.cur
  const busy = cur?.status === 'starting' || cur?.status === 'running'
  const openRoute = cur?.status === 'completed'
    ? (cur.result?.kind === 'shape_cluster_cnn' && cur.result.run_id ? `models/results/b2/${cur.result.run_id}`
      : (exp.data?.jobs ?? []).find(j => j.job_dir === cur.path)?.open?.route ?? null)
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
              <Icon name="folder" size={12} /><span className="jb-ellipsis" title={w.job_dir}>{w.name}</span><span className="jb-spacer" />
              <Button size="sm" variant="link" testid={`inbox-pick-${w.name}`} onClick={() => setPath(w.job_dir)}>use this folder</Button>
            </div>
          ))}
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
      {att.error && <LoadFailed what="the import attempts" error={att.error} onRetry={att.reload} />}
      {att.data && !att.data.attempts.length && <div className="jb-small jb-muted" data-testid="inbox-attempts-empty">none yet</div>}
      {att.data && !!att.data.attempts.length && (
        <div className="jb-col" data-testid="inbox-attempts">
          {att.data.attempts.slice(0, 12).map(a => <Attempt key={a.job_id} a={a} />)}
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
