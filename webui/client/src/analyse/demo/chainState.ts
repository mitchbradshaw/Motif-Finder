/* Demo chain state (brief: writes go to the in-memory store; runs move queued → running → done on useSim).
 * One store entry per demo template (`analyse.demo.chain.<template>`), shared by the chain page and the block pages, so
 * an edit on a block page survives Chain ↔ Block navigation but not a reload. Deep-link states (?state=running|failed|…)
 * are applied onto the scenario fixture by `applyState`. */
import { useCallback, useEffect } from 'react'
import {
  blockByName, demoCaption, demoStepError, validateDemoChain,
  type DemoChainBundle, type DemoPayload, type DemoRowStatus, type DemoScenario, type DemoStep, type DemoValidation,
} from '../../api/analyse'
import { forceSim, getSim, recordDemoWrite, setDemo, useDemoState, useSim, cancelSim, startSim } from '../../kit'
import { DEMO_SCENARIOS } from '../../fixtures/analyse'

export const pad2 = (n: number) => String(n).padStart(2, '0')
export const simIdFor = (template: string) => `analyse.demo.run.${template}`
export const chainKey = (template: string) => `analyse.demo.chain.${template}`

export interface DemoChainState {
  template: string
  name: string; note: string; saved: boolean
  steps: DemoStep[]
  status: Record<string, DemoRowStatus>
  captions: Record<string, string>
  failure: { uid: string; message: string; after: string; run: string } | null
  runNo: number; lastRun: string
  surrogate: boolean
  run: { uids: string[]; from: number; sim: number } | null
  hpcJob: string | null
  uploaded: boolean
  footer: { headline: string; sub: string } | null
  seq: number
}

let uidSeq = 100
export const newUid = () => `u${uidSeq++}`

export function fromScenario(sc: DemoScenario): DemoChainState {
  const steps: DemoStep[] = sc.steps.map((s, i) => ({ uid: `s${i + 1}`, block: s.block, params: { ...(s.params ?? blockByName(s.block)?.params ?? {}) } }))
  return {
    template: sc.template, name: sc.name, note: sc.note, saved: sc.note.includes('saved') && !sc.note.includes('unsaved'),
    steps, status: Object.fromEntries(steps.map((st, i) => [st.uid, sc.steps[i].status])),
    captions: Object.fromEntries(steps.flatMap((st, i) => sc.steps[i].caption ? [[st.uid, sc.steps[i].caption!]] : [])),
    failure: null, runNo: 134, lastRun: sc.runId, surrogate: true, run: null, hpcJob: null, uploaded: false, footer: null, seq: 0,
  }
}

export type DeepState = 'default' | 'empty' | 'running' | 'invalid' | 'failed' | 'hpc' | 'paused' | 'stale' | 'fresh'

/** Build the frame's state from the scenario fixture. Returns the state and, for `running`, the sim to force. */
export function applyState(sc: DemoScenario, name: string): { state: DemoChainState; forceRunning?: { from: number }; deleted?: { step: DemoStep; index: number } } {
  const base = fromScenario(sc)
  switch (name as DeepState) {
    case 'empty': return { state: { ...base, name: 'untitled chain', note: 'unsaved', saved: false, steps: [], status: {}, captions: {} } }
    case 'running': {
      if (base.steps.length < 2) return { state: base }
      const from = Math.min(1, base.steps.length - 1)
      const status = { ...base.status }
      base.steps.forEach((s, i) => { if (i >= from) status[s.uid] = 'stale' })
      return { state: { ...base, status }, forceRunning: { from } }
    }
    case 'invalid': {
      const idx = base.steps.findIndex(s => s.block === 'demo.symbolic_encoding')
      const i = idx >= 0 ? idx : Math.max(0, base.steps.length - 2)
      const step = base.steps[i]
      if (!step) return { state: base }
      const steps = base.steps.filter((_, k) => k !== i)
      return { state: { ...base, steps }, deleted: { step, index: i } }
    }
    case 'failed': {
      const last = base.steps[base.steps.length - 1]
      if (!last) return { state: base }
      const status = Object.fromEntries(base.steps.map(s => [s.uid, s === last ? 'failed' : 'cached'])) as Record<string, DemoRowStatus>
      const message = demoStepError(last) ?? `RuntimeError: ${blockByName(last.block)?.page_name ?? last.block} failed (simulated)`
      return { state: { ...base, status, note: '#134 failed', failure: { uid: last.uid, message, after: '0.3 s', run: '#134' }, runNo: 135 } }
    }
    case 'fresh': {   // imported onto this source: nothing has run yet
      const status = Object.fromEntries(base.steps.map(s => [s.uid, 'new'])) as Record<string, DemoRowStatus>
      return { state: { ...base, status, note: 'unsaved', saved: false, lastRun: '—' } }
    }
    case 'stale': {
      const status = Object.fromEntries(base.steps.map((s, i) => [s.uid, i === 0 ? 'cached' : 'stale'])) as Record<string, DemoRowStatus>
      return { state: { ...base, status } }
    }
    default: return { state: base }
  }
}

/* ------------------------------------------------------------------ derivations ---- */
export type ViewStatus = DemoRowStatus | 'running' | 'waiting' | 'queued' | 'invalid'
export interface RowView { step: DemoStep; index: number; status: ViewStatus; stored: DemoRowStatus; payload: DemoPayload | null; caption: string; progress: { pct: number; left: number } | null; waitsFor: number | null }

type Sim = ReturnType<typeof useSim>
export function deriveRows(st: DemoChainState, bundle: DemoChainBundle, sim: Sim, v: DemoValidation, stepMs = STEP_MS): RowView[] {
  const running = st.run && sim.runs === st.run.sim && (sim.status === 'running' || sim.status === 'queued')
  return st.steps.map((step, i) => {
    const stored = st.status[step.uid] ?? 'new'
    let status: ViewStatus = stored
    let progress: RowView['progress'] = null
    let waitsFor: number | null = null
    if (running && st.run!.uids.includes(step.uid)) {
      const k = st.run!.uids.indexOf(step.uid)
      if (sim.status === 'queued') { status = k === 0 ? 'queued' : 'waiting'; waitsFor = k === 0 ? null : i }
      else if (k < sim.step) status = 'cached'
      else if (k === sim.step) {
        status = 'running'
        const within = Math.max(0, Math.min(0.999, sim.fraction * st.run!.uids.length - sim.step))
        progress = { pct: Math.round(within * 100), left: +((1 - within) * stepMs / 1000).toFixed(1) }
      } else { status = 'waiting'; waitsFor = i }
    } else if (v.junctions[i] && !v.junctions[i].ok) status = 'invalid'
    const payload = hasResult(status, stored) ? payloadFor(bundle, st.steps, i) : null
    const caption = status === 'waiting' ? '—' : payload && (stored === 'cached' || stored === 'stale' || status === 'invalid') && !st.captions[step.uid] ? payload.summary : st.captions[step.uid] ?? demoCaption(step)
    return { step, index: i, status, stored, payload, caption, progress, waitsFor }
  })
}
const hasResult = (status: ViewStatus, stored: DemoRowStatus) => status === 'cached' || status === 'running' || status === 'invalid' || stored === 'cached' || stored === 'stale' || stored === 'paused'

/** The last-run payload a demo row draws: the scenario's own for this block, then any scenario on the same source, then
 *  the nearest upstream result of the same kind (a pass-through demo block), else a text card that says there is none. */
export function payloadFor(bundle: DemoChainBundle, steps: DemoStep[], i: number): DemoPayload | null {
  const step = steps[i]; const b = blockByName(step.block)
  const sc = bundle.scenario
  if (sc.payloads[step.block]) return withParams(sc.payloads[step.block], step)
  for (const other of Object.values(DEMO_SCENARIOS)) if (other.source === sc.source && other.payloads[step.block]) return withParams(other.payloads[step.block], step)
  if (!b) return null
  for (let k = i - 1; k >= -1; k--) {
    const up = k < 0 ? sc.sourcePayload : payloadFor(bundle, steps, k)
    const upKind = k < 0 ? 'signal' : blockByName(steps[k].block)?.output
    if (up && upKind === b.output && up.type !== 'demo.text') return { ...up, summary: `${b.page_name} · ${up.summary}` } as DemoPayload
  }
  return { type: 'demo.text', lines: [`${b.page_name} · ${b.signature}`, 'this demo block has no preview payload · its block page shows the process'], summary: `${b.page_name} · no preview` }
}
function withParams(p: DemoPayload, step: DemoStep): DemoPayload {
  if (p.type === 'demo.slope' || p.type === 'demo.strips') return p
  if (p.type === 'demo.signal' && step.block === 'demo.baseline_removal') return { ...p, summary: `${step.params.window_s ?? 7} s ${String(step.params.method ?? 'rolling median')} subtracted` }
  return p
}

export const STEP_MS = 700

/* ------------------------------------------------------------------ the hook ---- */
export function useDemoChain(bundle: DemoChainBundle | null, template: string) {
  const [st, setSt] = useDemoState<DemoChainState | null>(chainKey(template), () => null)
  const sim = useSim(simIdFor(template))
  useEffect(() => { if (bundle && !st) setSt(fromScenario(bundle.scenario)) }, [bundle, st, setSt])

  /* commit a finished simulated run into the stored statuses (once per sim run) */
  useEffect(() => {
    if (!st?.run || sim.runs !== st.run.sim) return
    if (sim.status !== 'done' && sim.status !== 'failed' && sim.status !== 'cancelled') return
    const run = st.run
    setSt(prev => {
      if (!prev || !prev.run || prev.run.sim !== run.sim) return prev
      const status = { ...prev.status }
      let failure = prev.failure; let note = prev.note; let footer = prev.footer; let lastRun = prev.lastRun
      const runLabel = `#${prev.runNo}`
      if (sim.status === 'done') {
        run.uids.forEach(u => { status[u] = 'cached' }); failure = null; lastRun = runLabel
        note = prev.saved ? note : 'unsaved'; footer = null
        recordDemoWrite('analyse', 'run-finished', { template, run: runLabel, stages: run.uids.length })
      } else if (sim.status === 'failed') {
        run.uids.forEach((u, k) => { if (k < sim.step) status[u] = 'cached'; else if (k === sim.step) status[u] = 'failed' })
        const uid = run.uids[sim.step]; const step = prev.steps.find(s => s.uid === uid)
        failure = { uid, message: sim.error ?? (step ? demoStepError(step) : null) ?? 'failed (simulated)', after: '0.3 s', run: runLabel }
        note = `${runLabel} failed`
        recordDemoWrite('analyse', 'run-failed', { template, run: runLabel, at: uid })
      } else {
        run.uids.forEach((u, k) => { if (k < sim.step) status[u] = 'cached' })
        footer = { headline: 'Cancelled', sub: `run ${runLabel} stopped before ${pad2(prev.steps.findIndex(s => s.uid === run.uids[Math.max(0, sim.step)]) + 1)} · cancel is checked between stages · finished stages stay cached` }
      }
      return { ...prev, status, failure, note, footer, lastRun, run: null, runNo: prev.runNo + 1 }
    })
  }, [sim.status, sim.runs, sim.step, sim.error, st?.run, setSt, template])

  const v = validateDemoChain(st?.steps ?? [])
  const busy = !!st?.run && sim.runs === st.run.sim && sim.busy

  const actions = useDemoActions(template, setSt)
  return { st, setSt, sim, v, busy, actions }
}

type Setter = (next: DemoChainState | null | ((prev: DemoChainState | null) => DemoChainState | null)) => void
function markStaleFrom(prev: DemoChainState, from: number, steps = prev.steps): Record<string, DemoRowStatus> {
  const status = { ...prev.status }
  steps.forEach((s, k) => {
    if (k < from) return
    const cur = status[s.uid] ?? 'new'
    status[s.uid] = cur === 'cached' ? 'stale' : cur === 'failed' ? 'new' : cur
  })
  return status
}

export function useDemoActions(template: string, setSt: Setter) {
  const upd = useCallback((fn: (s: DemoChainState) => DemoChainState) => setSt(prev => (prev ? fn(prev) : prev)), [setSt])
  return {
    /** Start a simulated run from step `from` (the first step that is not cached). Fails where demoStepError says so. */
    run: (from: number) => upd(s => {
      const steps = s.steps.slice(from).filter(x => !x.bypass)
      if (!steps.length) return s
      const failAt = steps.findIndex(x => demoStepError(x) !== null)
      const id = simIdFor(template)
      const runs = getSim(id).runs + 1
      startSim(id, { steps: steps.map(x => blockByName(x.block)?.page_name ?? x.block), stepMs: STEP_MS, queuedMs: 350, failAt: failAt >= 0 ? failAt : null, error: failAt >= 0 ? demoStepError(steps[failAt]) ?? undefined : undefined })
      recordDemoWrite('analyse', 'run-start', { template, from: pad2(from + 1), stages: steps.length })
      return { ...s, run: { uids: steps.map(x => x.uid), from, sim: runs }, failure: null, footer: null, note: s.saved ? s.note : 'unsaved' }
    }),
    /** Deep link ?state=running: a run frozen at 64 % of stage `from` (Cancel still works). */
    forceRunning: (from: number) => upd(s => {
      const steps = s.steps.slice(from)
      const id = simIdFor(template)
      const runs = getSim(id).runs + 1
      forceSim(id, { status: 'running', steps: steps.map(x => blockByName(x.block)?.page_name ?? x.block), step: 0, fraction: 0.64 / steps.length, startedAt: Date.now(), finishedAt: null, error: null, runs, elapsedMs: 800 })
      return { ...s, run: { uids: steps.map(x => x.uid), from, sim: runs } }
    }),
    cancel: () => cancelSim(simIdFor(template)),
    setParam: (uid: string, name: string, value: unknown) => upd(s => {
      const i = s.steps.findIndex(x => x.uid === uid); if (i < 0) return s
      const steps = s.steps.map(x => x.uid === uid ? { ...x, params: { ...x.params, [name]: value } } : x)
      const failure = s.failure && s.steps.findIndex(x => x.uid === s.failure!.uid) >= i ? null : s.failure
      return { ...s, steps, status: markStaleFrom(s, i, steps), saved: false, note: failure ? s.note : 'unsaved', failure }
    }),
    setParams: (uid: string, params: Record<string, unknown>) => upd(s => {
      const i = s.steps.findIndex(x => x.uid === uid); if (i < 0) return s
      const steps = s.steps.map(x => x.uid === uid ? { ...x, params: { ...params } } : x)
      return { ...s, steps, status: markStaleFrom(s, i, steps), saved: false, note: 'unsaved', failure: null }
    }),
    remove: (i: number) => upd(s => {
      const steps = s.steps.filter((_, k) => k !== i)
      recordDemoWrite('analyse', 'delete-stage', { template, stage: pad2(i + 1) })
      return { ...s, steps, status: markStaleFrom(s, i, steps), saved: false, note: 'unsaved' }
    }),
    restore: (step: DemoStep, index: number, status: DemoRowStatus) => upd(s => {
      if (s.steps.some(x => x.uid === step.uid)) return s
      const steps = [...s.steps.slice(0, index), step, ...s.steps.slice(index)]
      return { ...s, steps, status: { ...s.status, [step.uid]: status } }
    }),
    insert: (pos: number, block: string) => {
      const uid = newUid()
      upd(s => {
        const b = blockByName(block)
        const step: DemoStep = { uid, block, params: { ...(b?.params ?? {}) } }
        const steps = [...s.steps.slice(0, pos), step, ...s.steps.slice(pos)]
        const status = markStaleFrom(s, pos + 1, steps); status[uid] = 'new'
        recordDemoWrite('analyse', 'insert-stage', { template, block, at: pad2(pos + 1) })
        return { ...s, steps, status, saved: false, note: 'unsaved' }
      })
      return uid
    },
    bypass: (i: number) => upd(s => {
      const steps = s.steps.map((x, k) => k === i ? { ...x, bypass: !x.bypass } : x)
      return { ...s, steps, status: markStaleFrom(s, i + 1, steps), saved: false, note: 'unsaved' }
    }),
    duplicate: (i: number) => upd(s => {
      const src = s.steps[i]; if (!src) return s
      const copy: DemoStep = { ...src, uid: newUid(), params: { ...src.params }, bypass: false }
      const steps = [...s.steps.slice(0, i + 1), copy, ...s.steps.slice(i + 1)]
      const status = markStaleFrom(s, i + 2, steps); status[copy.uid] = 'new'
      return { ...s, steps, status, saved: false, note: 'unsaved' }
    }),
    rename: (name: string) => upd(s => ({ ...s, name, saved: false, note: 'unsaved' })),
    save: (name: string, version: string) => upd(s => {
      recordDemoWrite('analyse', 'save-template', { template: name, version, stages: s.steps.map(x => x.block) })
      setDemo<{ name: string; version: string; steps: string[]; at: number }[]>('analyse.savedTemplates', prev => [...(prev ?? []), { name, version, steps: s.steps.map(x => x.block), at: Date.now() }])
      return { ...s, name, saved: true, note: `${version} · saved` }
    }),
    toggleSurrogate: () => upd(s => ({ ...s, surrogate: !s.surrogate })),
    replaceAll: (next: DemoChainState) => setSt(next),
    patch: (patch: Partial<DemoChainState>) => upd(s => ({ ...s, ...patch })),
  }
}
export type DemoActions = ReturnType<typeof useDemoActions>
