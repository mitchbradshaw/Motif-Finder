/* Signal page model: the detections picker state, the runs it lists (demo canon on the canon channel, live
   runs elsewhere), and the motif list the span tier and ‹ N / M › walk (live annotations + live detections +
   demo detections from checked runs). Pure functions only. */
import type { DbRun, Spans } from '../api'
import type { DetectionRow, SignalDemo } from '../api/explore'
import { toMotifs, type Motif } from './util'

export interface PickerRun { id: string; name: string; method: string; template: string; surrogate: boolean; colour: string; count: number; liveRunId?: number }
export interface PickerState { checked: string[]; colourByRun: boolean; hideSurrogates: boolean; unadjudicatedOnly: boolean; group: 'run' | 'method' | 'template' }

const LIVE_PALETTE = ['#0A84FF', '#64D2FF', '#BF5AF2', '#FF9F0A', '#30B0C7', '#A2845E', '#8E9C3A']

export function pickerRuns(demo: SignalDemo | null, live: DbRun[] | null): PickerRun[] {
  if (demo) return demo.runs.map(r => ({ ...r }))
  return (live ?? []).filter(r => (r.n_detections ?? 0) > 0).map((r, i) => {
    const last = (r.steps ?? []).map(s => s.split('.').pop() ?? s).pop() ?? 'unknown method'
    return { id: `#${r.id}`, name: r.name ?? `run ${r.id}`, method: last, template: r.name ?? '—', surrogate: !!(r as DbRun & { surrogate_of_run_id?: number | null }).surrogate_of_run_id, colour: LIVE_PALETTE[i % LIVE_PALETTE.length], count: r.n_detections, liveRunId: r.id }
  })
}

export function defaultPicker(demo: SignalDemo | null, runs: PickerRun[]): PickerState {
  return { checked: demo ? demo.defaultRuns : runs.map(r => r.id), colourByRun: !!demo, hideSurrogates: true, unadjudicatedOnly: false, group: 'run' }
}

/** Which runs actually draw: checked, and not hidden as a surrogate. */
export function visibleRunIds(runs: PickerRun[], st: PickerState): Set<string> {
  return new Set(runs.filter(r => st.checked.includes(r.id) && !(st.hideSurrogates && r.surrogate)).map(r => r.id))
}

export function chipLabel(runs: PickerRun[], st: PickerState): string {
  if (!runs.length) return 'no runs'
  const vis = runs.filter(r => st.checked.includes(r.id) && !(st.hideSurrogates && r.surrogate))
  const methods = new Set(vis.map(r => r.method)).size
  const n = vis.length
  return `${n === runs.length ? n : `${n} of ${runs.length}`} run${runs.length === 1 ? '' : 's'} · ${methods} method${methods === 1 ? '' : 's'}`
}

export function demoDetectionMotif(d: DetectionRow, fs: number): Motif {
  return {
    key: `f:${d.id}`, kind: 'detected', id: d.id, start_s: d.start / fs, end_s: d.end / fs, score: d.score, runKey: d.runId, demo: true,
    adjudication: d.adjudication, family: d.family, tag: d.tag ?? null,
  }
}

/** Live annotations + live detections (filtered to visible live runs) + demo detections from visible runs. */
export function buildMotifs(all: Spans | null, demo: SignalDemo | null, runs: PickerRun[], st: PickerState, fs: number): Motif[] {
  const vis = visibleRunIds(runs, st)
  const liveVis = new Set(runs.filter(r => vis.has(r.id) && r.liveRunId != null).map(r => r.liveRunId!))
  const live = all ? toMotifs(all).filter(m => m.kind === 'annotated' || demo !== null || !runs.length || liveVis.has(m.run_id ?? -1)) : []
  const fixture = demo ? demo.detections.filter(d => vis.has(d.runId) && !(st.unadjudicatedOnly && d.adjudication !== 'unadjudicated')).map(d => demoDetectionMotif(d, fs)) : []
  const out = [...live, ...fixture]
  out.sort((p, q) => p.start_s - q.start_s || p.end_s - q.end_s || p.key.localeCompare(q.key))
  return out
}

export function hexA(hex: string, a: number): string {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`
}
