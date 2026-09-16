/* The in-memory Jobs store: every hand mark, continue, cancel, place and import made on the Jobs pages. Module-level
 * (survives navigation between the four Jobs routes and the other workspaces) and never persisted (a reload returns
 * to the fixtures). Fixture rows are read through api/jobs.ts; this file only holds what the user changed. */
import { useMemo } from 'react'
import { getSim, recordDemoWrite, setDemo, startSim, useDemoState, useDemoWrites, useSim } from '../kit'
import type { ClusterJob, ClusterStatus, JobsOverview, PausedRun, ResultState } from '../api/jobs'

export const nowHM = () => { const d = new Date(); return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}` }

/* ------------------------------------------------------------------ paused runs */
export type RunPhase = 'paused' | 'continuing' | 'finished' | 'cancelled' | 'null-cluster'
export interface RunOverride { result?: ResultState; phase?: RunPhase; nullJob?: string; placedFile?: string; at?: string }
const RUNS = 'jobs.runs'
export const useRunOverrides = () => useDemoState<Record<string, RunOverride>>(RUNS, () => ({}))
export const patchRun = (id: string, p: RunOverride) => setDemo<Record<string, RunOverride>>(RUNS, prev => ({ ...(prev ?? {}), [id]: { ...(prev ?? {})[id], ...p } }))

export const runSimId = (id: string) => `jobs.run.${id}`

export interface RunView { run: PausedRun; result: ResultState; phase: RunPhase; ov: RunOverride }
/** The effective state of a paused run: fixture default ← stored override ← a finished continue simulation. */
export function viewRun(run: PausedRun, ov: RunOverride | undefined): RunView {
  const o = ov ?? {}
  let phase: RunPhase = o.phase ?? 'paused'
  if (phase === 'continuing' && getSim(runSimId(run.id)).status === 'done') phase = 'finished'
  return { run, result: o.result ?? run.defaultResult, phase, ov: o }
}
/** Subscribe to one run's continue simulation, so a component re-renders as it ticks. */
export const useRunSim = (id: string) => useSim(runSimId(id))

export function continueRun(run: PausedRun) {
  const left = run.stages.filter(s => s.n > run.pausedAt).map(s => `${s.n} ${s.name}`)
  patchRun(run.id, { phase: 'continuing', result: 'arrived', at: nowHM() })
  if (run.clusterJob) markCluster(run.clusterJob, 'finished', `stage ${run.pausedAt} result stored as ${run.id}'s artifact`)
  startSim(runSimId(run.id), { steps: left, stepMs: 1400, queuedMs: 500 })
  recordDemoWrite('jobs', 'continue-run', { run: run.id, from: run.pausedAt + 1, artifact: run.result.path })
}

export function cancelRun(run: PausedRun) {
  patchRun(run.id, { phase: 'cancelled', at: nowHM() })
  recordDemoWrite('jobs', 'cancel-run', { run: run.id, kept: run.stages.filter(s => s.state === 'cached' || s.state === 'done').map(s => s.n) })
}

/* ------------------------------------------------------------------ cluster jobs */
export interface ClusterOverride { status?: ClusterStatus; marks?: Partial<ClusterJob['marks']>; snoozedUntil?: string; clusterJobId?: string; profile?: string; replacedBy?: string; importedAt?: string; note?: string }
const CLUSTER = 'jobs.cluster'
export const useClusterOverrides = () => useDemoState<Record<string, ClusterOverride>>(CLUSTER, () => ({}))
export const patchCluster = (id: string, p: ClusterOverride) =>
  setDemo<Record<string, ClusterOverride>>(CLUSTER, prev => {
    const cur = (prev ?? {})[id] ?? {}
    return { ...(prev ?? {}), [id]: { ...cur, ...p, marks: { ...cur.marks, ...p.marks } } }
  })

export function markCluster(id: string, status: ClusterStatus, note?: string) {
  const at = nowHM()
  const marks: Partial<ClusterJob['marks']> = status === 'submitted' ? { submitted: at } : status === 'running' ? { running: at } : status === 'finished' ? { finished: at } : status === 'failed' ? { failed: at } : {}
  patchCluster(id, { status, marks, note, snoozedUntil: undefined })
  recordDemoWrite('jobs', 'mark-cluster-job', { job: id, status, at, by: 'hand' })
}

export function mergeCluster(base: ClusterJob, ov: ClusterOverride | undefined): ClusterJob & { snoozedUntil?: string; replacedBy?: string; note?: string } {
  if (!ov) return base
  return { ...base, ...ov, marks: { ...base.marks, ...ov.marks }, status: ov.status ?? base.status, profile: ov.profile ?? base.profile, clusterJobId: ov.clusterJobId ?? base.clusterJobId, importedAt: ov.importedAt ?? base.importedAt }
}

/** Past 3× its estimate while marked running, and not snoozed (§7c.4). */
export const isOverdue = (j: ClusterJob & { snoozedUntil?: string }) => j.status === 'running' && j.runningForH != null && j.runningForH >= 3 * j.estimateH
export const overrunLabel = (j: ClusterJob) => j.runningForH != null ? `${(j.runningForH / j.estimateH).toFixed(1)}×` : '—'

/** Jobs created by other workspaces (Analyse chain-1g, Discovery, Models) or by New SLURM script here. */
export function useAddedJobs(): ClusterJob[] {
  const writes = useDemoWrites('jobs')
  return useMemo(() => {
    const seen = new Set<string>()
    const out: ClusterJob[] = []
    for (const w of [...writes].reverse()) {
      if (w.kind !== 'add-job') continue
      const d = w.detail as { id?: string; kind?: string; title?: string; status?: string; detail?: string; for?: string; profile?: string; replaces?: string; script?: string }
      if (!d.id || seen.has(d.id)) continue
      seen.add(d.id)
      const at = new Date(w.at)
      const hm = `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`
      const ws = d.kind === 'analyse' ? 'Analyse' : d.kind === 'discovery' ? 'Discovery' : d.kind === 'library' ? 'Library' : d.kind === 'review' ? 'Review' : 'Models'
      out.push({
        id: d.id, title: d.title ?? d.id, sub: d.for ? `for ${d.for} · ${ws}` : `${ws} · ${d.detail ?? 'SLURM script created'}`, workspace: ws, forRun: d.for,
        profile: d.profile ?? (ws === 'Models' ? 'hpc-1 · gpu-single' : 'hpc-1 · cpu-array'), status: 'queue', marks: { created: hm }, estimateH: 6,
        estimateLabel: 'not calibrated yet · from the stage estimate', clusterJobId: '', returnFrom: `/scratch/$USER/cnn/out/${d.id}`, returnTo: ws === 'Models' ? './cluster_out' : './PROFILES',
        scriptName: `${d.id}.sh`, script: d.script ?? `#SBATCH --account=a_myco --partition=cpu_long\n#SBATCH --cpus-per-task=16 --mem=64G --time=12:00:00\nmodule load python/3.11 && conda activate cnn\npython -m pipeline.stage --job ${d.id} --out /scratch/$USER/cnn/out/${d.id}`,
        openIn: ws === 'Analyse' ? { label: 'Open in Analyse', route: 'analyse/chain' } : ws === 'Discovery' ? { label: 'Open in Discovery', route: 'discovery/runs' } : { label: 'Open in Models', route: 'models/launch' },
        isNew: true,
      })
    }
    return out
  }, [writes])
}

export function nextJobId(known: string[]) {
  const n = Math.max(217, ...known.filter(k => /^j-\d+$/.test(k)).map(k => Number(k.slice(2))))
  return `j-${String(n + 1).padStart(4, '0')}`
}

/* ------------------------------------------------------------------ local jobs */
const LOCAL = 'jobs.local'
export const useLocalCancelled = () => useDemoState<Record<string, string>>(LOCAL, () => ({}))
export function cancelLocal(id: string) {
  setDemo<Record<string, string>>(LOCAL, prev => ({ ...(prev ?? {}), [id]: nowHM() }))
  recordDemoWrite('jobs', 'cancel-local-job', { job: id })
}

/* ------------------------------------------------------------------ manifest inbox */
export type InboxPending = 'none' | 'arrived' | 'importing' | 'imported'
const INBOX = 'jobs.inbox'
export const useInboxPending = () => useDemoState<InboxPending>(INBOX, () => 'none')
export const setInboxPending = (v: InboxPending) => setDemo<InboxPending>(INBOX, v)

/* ------------------------------------------------------------------ the merged view every page uses */
export interface MergedJobs {
  runs: RunView[]; cluster: (ClusterJob & { snoozedUntil?: string; replacedBy?: string; note?: string })[]
  local: (JobsOverview['local'][number] & { cancelledAt?: string })[]; queues: JobsOverview['queues']; finished: JobsOverview['finished']
  allIds: string[]
}
export function useMergedJobs(data: JobsOverview | null): MergedJobs | null {
  const [runs] = useRunOverrides()
  const [cluster] = useClusterOverrides()
  const [local] = useLocalCancelled()
  const added = useAddedJobs()
  // re-render while any continue simulation ticks
  useSim(runSimId('r-0431')); useSim(runSimId('a-0098'))
  return useMemo(() => {
    if (!data) return null
    const clusterAll = [...added.filter(a => !data.cluster.some(c => c.id === a.id)), ...data.cluster].map(j => mergeCluster(j, cluster[j.id]))
    return {
      runs: data.paused.map(r => viewRun(r, runs[r.id])),
      cluster: clusterAll,
      local: data.local.map(l => ({ ...l, cancelledAt: local[l.id] })),
      queues: data.queues, finished: data.finished,
      allIds: [...data.paused.map(r => r.id), ...clusterAll.map(c => c.id), ...data.local.map(l => l.id), ...data.queues.map(q => q.id), ...data.finished.map(f => f.id)],
    }
    // getSim is read inside viewRun; the useSim subscriptions above trigger the re-render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, runs, cluster, local, added, getSim(runSimId('r-0431')), getSim(runSimId('a-0098'))])
}
