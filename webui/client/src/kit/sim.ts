/* Simulated jobs for controls that would run analysis (brief: "move through a plausible
 * queued → running → done state on a timer, ending in fixture results").
 *
 * A simulation is registered under a stable id in a module-level registry, so leaving the page and
 * coming back shows it still running (or finished) — like a real job — but a reload forgets it.
 *
 *   const run = useSim('discovery.run.r-0431')
 *   run.start({ steps: ['01 Baseline', '02 Noise floor', '03 Encoding'], stepMs: 900 })
 *   run.status   // 'idle' | 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'paused'
 *   run.step, run.fraction, run.elapsedMs, run.cancel(), run.reset()
 */
import { useCallback, useSyncExternalStore } from 'react'

export type SimStatus = 'idle' | 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'paused'

export interface SimOptions {
  steps?: string[]          // labels, one per stage; default a single step
  stepMs?: number           // time per step (default 900 ms)
  queuedMs?: number         // time in 'queued' before running (default 400 ms)
  failAt?: number | null    // step index that fails (simulated error), default none
  pauseAt?: number | null   // step index where the run pauses (e.g. over the local ceiling)
  error?: string            // message used when failAt triggers
}

export interface SimState {
  id: string; status: SimStatus; steps: string[]; step: number; fraction: number
  startedAt: number | null; finishedAt: number | null; elapsedMs: number; error: string | null; runs: number
}

const IDLE = (id: string): SimState => ({ id, status: 'idle', steps: [], step: -1, fraction: 0, startedAt: null, finishedAt: null, elapsedMs: 0, error: null, runs: 0 })
const sims = new Map<string, SimState>()
const timers = new Map<string, number>()
const subs = new Map<string, Set<() => void>>()

function put(id: string, s: SimState) { sims.set(id, s); subs.get(id)?.forEach(f => f()) }
// cache the idle state: useSyncExternalStore needs a stable snapshot, a fresh IDLE object per call loops forever (kit agent fix)
export function getSim(id: string): SimState { let s = sims.get(id); if (!s) { s = IDLE(id); sims.set(id, s) } return s }

export function startSim(id: string, o: SimOptions = {}) {
  stopTimer(id)
  const steps = o.steps?.length ? o.steps : ['run']
  const stepMs = o.stepMs ?? 900, queuedMs = o.queuedMs ?? 400
  const prev = getSim(id)
  const t0 = Date.now()
  put(id, { ...IDLE(id), status: 'queued', steps, startedAt: t0, runs: prev.runs + 1 })
  const tick = () => {
    const s = getSim(id)
    if (s.status !== 'queued' && s.status !== 'running') { stopTimer(id); return }
    const now = Date.now(), el = now - t0
    if (el < queuedMs) { put(id, { ...s, elapsedMs: el }); return }
    const runEl = el - queuedMs
    const step = Math.min(steps.length - 1, Math.floor(runEl / stepMs))
    const fraction = Math.min(1, runEl / (stepMs * steps.length))
    if (o.failAt != null && step >= o.failAt) { stopTimer(id); put(id, { ...s, status: 'failed', step: o.failAt, fraction, elapsedMs: el, finishedAt: now, error: o.error ?? `${steps[o.failAt]} failed (simulated)` }); return }
    if (o.pauseAt != null && step >= o.pauseAt) { stopTimer(id); put(id, { ...s, status: 'paused', step: o.pauseAt, fraction, elapsedMs: el }); return }
    if (runEl >= stepMs * steps.length) { stopTimer(id); put(id, { ...s, status: 'done', step: steps.length - 1, fraction: 1, elapsedMs: el, finishedAt: now }); return }
    put(id, { ...s, status: 'running', step, fraction, elapsedMs: el })
  }
  timers.set(id, window.setInterval(tick, 100))
}

function stopTimer(id: string) { const t = timers.get(id); if (t) { window.clearInterval(t); timers.delete(id) } }
export function cancelSim(id: string) { const s = getSim(id); if (s.status === 'queued' || s.status === 'running') { stopTimer(id); put(id, { ...s, status: 'cancelled', finishedAt: Date.now() }) } }
export function resetSim(id: string) { stopTimer(id); put(id, { ...IDLE(id), runs: getSim(id).runs }) }
/** Put a simulation straight into a state (deep links such as ?state=running or ?state=failed). */
export function forceSim(id: string, patch: Partial<SimState>) { put(id, { ...getSim(id), ...patch, id }) }

export function useSim(id: string) {
  const state = useSyncExternalStore(
    useCallback((f: () => void) => { let s = subs.get(id); if (!s) { s = new Set(); subs.set(id, s) } s.add(f); return () => { s!.delete(f) } }, [id]),
    () => getSim(id),
  )
  return {
    ...state,
    busy: state.status === 'queued' || state.status === 'running',
    start: useCallback((o?: SimOptions) => startSim(id, o), [id]),
    cancel: useCallback(() => cancelSim(id), [id]),
    reset: useCallback(() => resetSim(id), [id]),
    force: useCallback((p: Partial<SimState>) => forceSim(id, p), [id]),
  }
}
