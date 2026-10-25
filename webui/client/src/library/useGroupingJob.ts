/* tq-grouping (2026-10-25): the grouping editor's regroup job — start it, follow it, cancel it. Split out of
 * GroupingPage.tsx. One AbortController per `start()` is the whole cancellation: `cancel`, `reset`, a newer `start`
 * and unmount all abort it, an abort cancels the job on the bridge if its id has arrived, and an id that arrives
 * after its controller was aborted is cancelled at once (night-review F2: the automatic tree build was left running
 * on browser back, a nav link or a hash change). It replaces four records of the same thing (`alive`, `gen`,
 * `liveJob`, `view.jobId`). */
import { useEffect, useRef, useState } from 'react'
import { ApiError, cancelJob, getJob, runLibraryGrouping, subscribeJob, type LibFamilyFlags, type LibFitSummary, type LibGroupingAssignment, type LibGroupingRefusal } from '../api'

export interface RunRecompute { seconds: number; minutes: number; where: 'local' | 'cluster' }
interface RunHandEdits { total: number; applies: number; orphaned: number; orphan_group_label: string | null; orphan_labels: string[] }
interface RunPreview {
  groups: number; members: number; omitted: number; omittedByReason: Record<string, number>
  recompute: RunRecompute; handEdits: RunHandEdits
}
export interface RunResult {
  unit: string; basis: string; method: string; params: Record<string, unknown>; recipeHash: string
  preview: RunPreview; mergeHeights: number[]; assignments: LibGroupingAssignment[]
  /** w2-b: the method's account of the fit (its null, the k rule), sent back unchanged on save */
  fitSummary?: LibFitSummary | null
  families?: { id: number; label: string; size: number; medoid: unknown; flags: LibFamilyFlags }[]
  /** fixup-an: the kept tree (Ward), and the job's words for whether it was built or reused */
  tree?: { key: string; path: string | null; reused: boolean; replaced?: string | null } | null
  treeNote?: string | null
}
type Phase = 'idle' | 'running' | 'done' | 'failed' | 'cancelled'
export interface JobView {
  phase: Phase; jobId: number | null; sig: string
  progress: { done: number; total: number | null; message: string }
  result: RunResult | null; error: string | null; forced?: boolean
  /** w2-b: the bridge refused the run before starting it (422 over the local limit) — its estimate and cheaper settings */
  refusal?: LibGroupingRefusal | null; refusalSig?: string
}
const IDLE: JobView = { phase: 'idle', jobId: null, sig: '', progress: { done: 0, total: null, message: '' }, result: null, error: null }

export const errText = (e: unknown): string => {
  if (e && typeof e === 'object' && 'message' in e && typeof (e as { message: unknown }).message === 'string') return (e as { message: string }).message
  return e ? String(e) : 'the grouping job failed'
}

/** Start a `regroup` job and follow it. The SSE stream is the fast path; a stream error falls back to polling
 *  `GET /api/jobs/{id}`, the same shape `analyse/store.ts` uses, so a dropped socket never leaves the panel
 *  computing forever. */
export function useGroupingJob() {
  const [view, setView] = useState<JobView>(IDLE)
  const run = useRef<AbortController | null>(null)
  const abort = () => { run.current?.abort(); run.current = null }
  useEffect(() => abort, [])

  /** Follow job `jobId` until it ends or `signal` aborts; an abort before the end cancels it on the bridge. It settles
   *  once — the after-callback is a write, and two overlapping polls both answering `completed` saved two rows. */
  const follow = (jobId: number, signal: AbortSignal, after?: (r: RunResult) => void) => {
    let stream: { close: () => void } | null = null
    let poll: number | null = null
    let polling = false
    let settled = false
    const stop = () => { stream?.close(); stream = null; if (poll) { window.clearInterval(poll); poll = null } }
    const onAbort = () => { stop(); void cancelJob(jobId).catch(() => undefined) }
    signal.addEventListener('abort', onAbort, { once: true })
    const settle = (status: string, result: unknown, error: unknown) => {
      if (settled) return; settled = true
      signal.removeEventListener('abort', onAbort)
      stop()
      if (signal.aborted) return
      if (status === 'completed' && result) {
        const r = result as RunResult
        setView(v => ({ ...v, phase: 'done', result: r, error: null }))
        after?.(r)
        return
      }
      if (status === 'cancelled') { setView(v => ({ ...v, phase: 'cancelled', error: null })); return }
      setView(v => ({ ...v, phase: 'failed', error: errText(error) || 'the grouping job produced no result' }))
    }
    stream = subscribeJob(jobId, raw => {
      if (signal.aborted) return
      // `subscribeJob` also relays the generic-job frames (`job_start`, `progress`, `job_end`), which the
      // chain-run `RunEvent` union does not name
      const e = raw as unknown as { event: string; done?: number; total?: number | null; message?: string; status?: string; result?: unknown; error?: unknown }
      if (e.event === 'progress') {
        setView(v => (v.jobId === jobId ? { ...v, progress: { done: Number(e.done ?? 0), total: e.total ?? null, message: String(e.message ?? '') } } : v))
      } else if (e.event === 'job_end') {
        settle(String(e.status ?? 'failed'), e.result, e.error)
      }
    }, () => {
      // the stream dropped: keep the job, watch it by polling instead
      stream?.close(); stream = null
      if (poll || signal.aborted) return
      poll = window.setInterval(() => {
        // one poll in flight: on a bridge slower than the interval the next tick waits rather than overlapping
        if (polling) return; polling = true
        getJob(jobId).then(row => {
          if (row.status === 'running' || row.status === 'queued') {
            const p = row.progress as { done?: number; total?: number | null; message?: string } | undefined
            setView(v => (v.jobId === jobId ? { ...v, progress: { done: Number(p?.done ?? 0), total: p?.total ?? null, message: String(p?.message ?? 'running') } } : v))
            return
          }
          settle(row.status, row.result, row.error)
        }).catch(err => settle('failed', null, err)).finally(() => { polling = false })
      }, 2000)
    })
  }

  const start = (sig: string, body: { unit: string; basis: string; method: string; params: Record<string, unknown> }, after?: (r: RunResult) => void) => {
    abort()
    const ac = new AbortController()
    run.current = ac
    const { signal } = ac
    setView({ ...IDLE, phase: 'running', sig, progress: { done: 0, total: 4, message: 'starting' } })
    runLibraryGrouping(body).then(j => {
      if (signal.aborted) { void cancelJob(j.job_id).catch(() => undefined); return }
      setView(v => ({ ...v, jobId: j.job_id }))
      follow(j.job_id, signal, after)
    }).catch(err => {
      if (signal.aborted) return
      // a 422 with `cheaper` is the cost refusal: nothing started, and there is no cluster script for a grouping
      const d = err instanceof ApiError && err.status === 422 ? err.detail as LibGroupingRefusal | null : null
      if (d && typeof d === 'object' && Array.isArray(d.cheaper)) { setView(v => ({ ...v, phase: 'idle', refusal: d, refusalSig: sig, error: null })); return }
      setView(v => ({ ...v, phase: 'failed', error: err instanceof ApiError ? err.message : String(err) }))
    })
  }

  const cancel = () => { abort(); setView(v => ({ ...v, phase: 'cancelled' })) }
  const reset = () => { abort(); setView(IDLE) }
  const clearRefusal = () => setView(v => ({ ...v, refusal: null, refusalSig: undefined }))
  /** the two `?state=` deep links: a display state for the screenshot pass, never a result */
  const force = (v: Partial<JobView>) => setView(x => ({ ...x, ...v, forced: true }))
  return { view, start, cancel, reset, force, clearRefusal }
}
