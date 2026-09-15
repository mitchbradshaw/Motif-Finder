/* Analyse demo reads (brief: every read goes through typed async functions returning Sourced<T>). The live chain,
 * block page, runs and templates stay in ../api.ts against the bridge; everything here is `demo` — the B24 detection
 * chain and the other concept-frame chains built from `demo.*` blocks, which the bridge never sees. A later ticket
 * swaps a body for a bridge call without touching the components. */
import { demo, type Sourced } from './seam'
import {
  DEMO_BLOCKS, DEMO_KIND_LABEL, DEMO_SCENARIOS, DEMO_SOURCES, DEMO_TEMPLATES, DETECTION_TRACE, DOWNSTREAM_PREVIEW, GLYPH_GROUPS, KEPT_DROPS, DROPPED_DROPS,
  MODEL_BLOCK, MP_BLOCK, NOISE_FLOOR, REMOVED, RUN_HISTORY, SEGMENT_SLOPES, SIGMA, SEG_S, SWEEP, THRESHOLD_BLOCK, TRY_WINDOWS,
  type DemoBlock, type DemoHistoryRun, type DemoKind, type DemoPayload, type DemoScenario, type DemoSource, type DemoTemplate,
} from '../fixtures/analyse'

export type { DemoBlock, DemoHistoryRun, DemoKind, DemoPayload, DemoScenario, DemoSource, DemoTemplate }
export type { DemoRowStatus, DemoSignalPayload, DemoSlopePayload, DemoStripsPayload, DemoSpansPayload, DemoScoresPayload, DemoWindowsPayload, DemoTextPayload, Env } from '../fixtures/analyse'
export { DEMO_KIND_LABEL, quantise5, toK3 } from '../fixtures/analyse'

/** The chain templates that open in demo mode (`#/analyse/chain?template=<name>`). */
export const DEMO_CHAIN_TEMPLATES = Object.keys(DEMO_SCENARIOS)
export const isDemoTemplate = (name: string | undefined | null) => !!name && (name === 'untitled' || DEMO_CHAIN_TEMPLATES.includes(name) || DEMO_TEMPLATES.some(t => t.name === name))
export const isDemoBlockName = (name: string) => name.startsWith('demo.')

/* ---- reads ---- */
export const getDemoBlocks = (): Promise<Sourced<DemoBlock[]>> => demo(DEMO_BLOCKS)
export const getDemoTemplates = (): Promise<Sourced<DemoTemplate[]>> => demo(DEMO_TEMPLATES)
export const getRunHistory = (): Promise<Sourced<DemoHistoryRun[]>> => demo(RUN_HISTORY)

export interface DemoChainBundle { scenario: DemoScenario; source: DemoSource; blocks: DemoBlock[] }
/** A demo chain: the scenario (frame state), its source and the block registry. Templates without a scenario of their
 *  own (sharkfin_v2, banded_sax_lp, …) open on the 50 s detection span with their steps as `new`. */
export function getDemoChain(template: string): Promise<Sourced<DemoChainBundle>> {
  const sc = DEMO_SCENARIOS[template] ?? scenarioFromTemplate(template)
  if (!sc) return Promise.reject(new Error(`no demo chain named "${template}" · demo chains: ${DEMO_CHAIN_TEMPLATES.join(', ')}`))
  return demo({ scenario: sc, source: DEMO_SOURCES[sc.source], blocks: DEMO_BLOCKS }, 40)
}
function scenarioFromTemplate(name: string): DemoScenario | null {
  if (name === 'untitled') return { ...DEMO_SCENARIOS.drop_motifs9, template: 'untitled', name: 'untitled chain', note: 'unsaved', runId: '—', steps: [], footer: { headline: 'No blocks yet', sub: 'add the first block or import a template' } }
  const t = DEMO_TEMPLATES.find(x => x.name === name)
  if (!t) return null
  const base = DEMO_SCENARIOS.drop_motifs9
  return { ...base, template: t.name, name: t.name, note: 'unsaved', runId: '—', steps: t.steps.map(s => ({ block: s.block, params: s.params ?? blockByName(s.block)?.params ?? {}, status: 'new' })), footer: { headline: 'No result yet', sub: 'imported · run the chain to see every intermediate' } }
}
export const blockByName = (name: string) => DEMO_BLOCKS.find(b => b.name === name)

/* ---- block page fixtures ---- */
export interface BlockFixtures {
  sweep: typeof SWEEP; tryWindows: typeof TRY_WINDOWS; downstream: typeof DOWNSTREAM_PREVIEW; noise: typeof NOISE_FLOOR; removed: typeof REMOVED
  detection: typeof DETECTION_TRACE; kept: typeof KEPT_DROPS; dropped: typeof DROPPED_DROPS; slopes: number[]; sigma: number; segS: number
  mp: typeof MP_BLOCK; threshold: typeof THRESHOLD_BLOCK; model: typeof MODEL_BLOCK
}
export const getBlockFixtures = (): Promise<Sourced<BlockFixtures>> => demo({
  sweep: SWEEP, tryWindows: TRY_WINDOWS, downstream: DOWNSTREAM_PREVIEW, noise: NOISE_FLOOR, removed: REMOVED, detection: DETECTION_TRACE,
  kept: KEPT_DROPS, dropped: DROPPED_DROPS, slopes: SEGMENT_SLOPES, sigma: SIGMA, segS: SEG_S, mp: MP_BLOCK, threshold: THRESHOLD_BLOCK, model: MODEL_BLOCK,
}, 40)

export interface GlyphRegistry { groups: typeof GLYPH_GROUPS; blocks: DemoBlock[] }
/** The glyph registry page (frame chain-6b): the 21 algorithms the frame shows (Span dedupe draws its signature glyph). */
export const getGlyphRegistry = (): Promise<Sourced<GlyphRegistry>> => demo({ groups: GLYPH_GROUPS, blocks: DEMO_BLOCKS.filter(b => !['demo.span_dedupe', 'demo.topk_pairs', 'demo.peak_picker'].includes(b.name)) })

/* ---- local validation for demo chains (the bridge validates live chains) ---- */
export interface DemoStep { uid: string; block: string; params: Record<string, unknown>; bypass?: boolean }
export interface DemoJunction { index: number; ok: boolean; needs: DemoKind; here: DemoKind; reason: string }
export interface DemoValidation { junctions: DemoJunction[]; terminal: DemoKind; invalid: number; outputs: DemoKind[] }

export function validateDemoChain(steps: DemoStep[]): DemoValidation {
  let producing: DemoKind = 'signal'
  const junctions: DemoJunction[] = []; const outputs: DemoKind[] = []
  steps.forEach((s, i) => {
    const b = blockByName(s.block)
    if (!b) { junctions.push({ index: i, ok: false, needs: producing, here: producing, reason: `unknown block ${s.block}` }); outputs.push(producing); return }
    if (s.bypass) { junctions.push({ index: i, ok: true, needs: producing, here: producing, reason: 'bypassed · passes its input through' }); outputs.push(producing); return }
    const ok = b.input === producing
    junctions.push({ index: i, ok, needs: b.input, here: producing, reason: ok ? '' : `needs ${DEMO_KIND_LABEL[b.input]} · here: ${DEMO_KIND_LABEL[producing]}` })
    producing = b.output; outputs.push(producing)
  })
  return { junctions, terminal: producing, invalid: junctions.filter(j => !j.ok).length, outputs }
}

export interface DemoFit { block: DemoBlock; ok: boolean; reason: string }
/** Which blocks fit at `position` (0 = right after the source): input must accept what arrives, output must satisfy the next stage. */
export function demoCompatibleAt(steps: DemoStep[], position: number): { producing: DemoKind; nextRequires: DemoKind | null; fits: DemoFit[] } {
  const v = validateDemoChain(steps.slice(0, position))
  const producing = position === 0 ? 'signal' : v.outputs[position - 1] ?? 'signal'
  const next = steps[position]
  const nextRequires = next && !next.bypass ? blockByName(next.block)?.input ?? null : null
  const pad = (n: number) => String(n).padStart(2, '0')
  const fits = DEMO_BLOCKS.map(b => {
    if (b.refuse) return { block: b, ok: false, reason: b.refuse }
    if (b.input !== producing) return { block: b, ok: false, reason: `needs ${DEMO_KIND_LABEL[b.input]} · here: ${DEMO_KIND_LABEL[producing]}` }
    if (nextRequires && b.output !== nextRequires) return { block: b, ok: false, reason: `emits ${DEMO_KIND_LABEL[b.output]} · ${pad(position + 1)} needs ${DEMO_KIND_LABEL[nextRequires]}` }
    return { block: b, ok: true, reason: 'fits here' }
  })
  return { producing, nextRequires, fits }
}

/** A step's failure rule for the simulated run (frame chain-1f): drop detection refuses a merge window shorter than
 *  one trough-tolerance window. Returns the error message or null. */
export function demoStepError(step: DemoStep): string | null {
  if (step.block === 'demo.drop_detection') {
    const merge = Number(step.params.merge_window_s ?? 2)
    const tol = Number(step.params.trough_tol_sigma ?? 0.5)
    const trough = +(1.2 / tol).toFixed(1)
    if (merge < trough) return `ValueError: merge_window ${merge.toFixed(1)} s is shorter than one trough-tolerance window (${trough.toFixed(1)} s at ${tol} σ)`
  }
  return null
}

/** One line of the parameters that define the output (chain row caption before a run). */
export function demoCaption(step: DemoStep): string {
  const p = step.params
  switch (step.block) {
    case 'demo.baseline_removal': return `${p.window_s ?? 7} s ${String(p.method ?? 'rolling median')} subtracted`
    case 'demo.noise_floor': return 'slope noise σ · d starts at 8σ'
    case 'demo.symbolic_encoding': return `${p.segment_s ?? 0.2} s segments → dSAX letters`
    case 'demo.drop_detection': return `depth ≥ ${Number(p.min_depth_mv ?? 0.1).toFixed(2)} mV · merge ${p.merge_window_s ?? 2} s`
    case 'demo.matrix_profile': return `m ${p.m_s ?? 600} s · exclusion ${p.exclusion ?? 'm/2'} · z-normalised · STUMP`
    case 'demo.threshold': return p.cut != null ? `cut ${p.cut} · from calibration` : `cut ${p.cut_sigma ?? 2.5} σ · min ${p.min_duration_s ?? 60} s · merge ${p.merge_gap_s ?? 30} s`
    case 'demo.span_dedupe': return `IoU ≥ ${p.iou ?? 0.5} merge · keep best`
    case 'demo.sliding_windows': return `${p.length_s ?? 600} s windows · stride ${p.stride_s ?? 300} s`
    case 'demo.model_stage': return `${String(p.model ?? 'cnn_windows_v2')} · batch ${p.batch ?? 64}`
    default: { const b = blockByName(step.block); return b ? b.defaults.map(([k, v]) => `${k} ${v}`).slice(0, 2).join(' · ') : step.block }
  }
}
