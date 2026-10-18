/* Analyse › Chain (frames chain-1, 1b, 1d, 1e, 1f, 1h). Vertical rows (P1), one per block,
   each drawing its result on the shared time axis; validation on every edit; runs streamed
   over SSE; history and templates behind popovers (P2). */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { DatasetName } from '../naming'
import {
  ApiError, compatibleAt, exportRun, getTemplate, saveTemplate, validateParams, TYPE_LABEL,
  type Compatible, type EnvelopeSeries, type SignalPayload, type SlurmWritten, type SpansetPayload, type Step, type Template,
} from '../api'
import { CrosshairProvider, TimeAxis } from '../charts/primitives'
import { makeX, type XScale } from '../charts/scale'
import { useSize } from '../charts/useSize'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { fmtDuration, navigate, setQuery, useApp } from '../state'
import { paramCaption } from './captions'
import { ChainRow, PLOT_H } from './ChainRow'
import { SaveWindowSetButton } from './SaveWindowSet'
import { HistoryPopover } from './HistoryPopover'
import { InsertStageModal } from './InsertStageModal'
import { renderByType } from './Renderer'
import { deriveRows, firstStale, fmtTiming, jobForSource, sameStep, terminalWording } from './rowState'
import { RunLogModal } from './RunLogModal'
import { useSendRunToReview } from './sendToReview'
import { attachRun, cancelCurrent, cancelPending, clearStale, dropUndo, markStale, popUndo, pushUndo, resetRun, startRun, stepElapsed, syncToSource, useAnalyseStore, type UndoEntry } from './store'
import { shortName, TemplatesPopover } from './TemplatesPopover'
import { deleteStepAt } from './deleteStep'
import { EXAMPLE_CHAIN, loadLastChain } from '../state'
import { EstimateChip, EXAMPLE_SOURCE, isHeldOut, isPoolSource, NameChip, POOL_SOURCE, Popwrap, RunErrorCard, SourceChip, SurrogateToggle, nullText, t0Of, t1Of, useSourceEnvelope } from './toolbar'
import { pad2, stepName, useAdapters } from './useAdapters'
import { spanOf, useValidation } from './useValidation'

const errText = (e: unknown) => e instanceof ApiError ? `${e.message}${e.traceback ? '\n' + e.traceback : ''}` : String(e)

export function ChainPage() {
  const { source, setSource, chain, setChain, route } = useApp()
  const toast = useToast()
  const adapters = useAdapters()
  const st = useAnalyseStore()
  const { payloads } = st.run
  const job = jobForSource(st.run.job, source)
  const steps = chain.steps
  const val = useValidation(steps, source)
  const { env, error: envError, status: envStatus } = useSourceEnvelope(source)
  const locked = envStatus === 423 || isHeldOut(source)
  // the bridge refused POST /api/runs (422: invalid chain, a stage over its local ceiling, a recipe that cannot build)
  const [refused, setRefused] = useState<{ message: string; over: { index: number; name: string; max_span_samples: number | null }[]; slurm?: SlurmWritten } | null>(null)
  const [modalPos, setModalPos] = useState<number | null>(route.params.insert !== undefined ? Number(route.params.insert) : null)
  const [pop, setPop] = useState<'history' | 'import' | 'source' | null>(null)
  const [logOpen, setLogOpen] = useState(false)
  const [cross, setCross] = useState<number | null>(null)
  const [suggest, setSuggest] = useState<Compatible | null>(null)
  const [fixes, setFixes] = useState<Record<string, Compatible>>({})
  const [busy, setBusy] = useState(false)

  const t0 = source ? t0Of(source) : 0
  const t1 = source ? t1Of(source) : 1
  const running = job?.status === 'running' || job?.status === 'queued'
  // cancel is checked between steps (and, W3-F, inside a block that checks it), so there can be a whole step of interval in
  // which the click has landed and nothing visible has happened (fixup-a 11)
  const cancelling = cancelPending(st.run)
  const rows = useMemo(() => deriveRows(steps, job, payloads, st.staleFrom, val.v), [steps, job, payloads, st.staleFrom, val.v])
  const invalid = val.v ? val.v.junctions.filter(j => !j.ok).length : 0
  // nothing is "stale" relative to a job that is not this source's (critique r1: the index leaked across sources)
  const stale = job ? firstStale(rows, st.staleFrom) : null
  const failedStep = job?.status === 'failed' ? job.error?.step ?? null : null
  const over = val.v?.over_ceiling ?? []
  const overFirst = over.length ? over[0] : null
  const overAd = overFirst !== null && steps[overFirst] ? adapters.byName.get(stepName(steps[overFirst])) : undefined

  /* a source change forgets a job (and stale index) that belongs to another recording/span */
  const sourceKey = source ? `${source.recording_id}:${source.start_idx}:${source.end_idx}` : ''
  useEffect(() => { syncToSource(source); setRefused(null) }, [sourceKey])   // eslint-disable-line react-hooks/exhaustive-deps

  /* re-attach after a reload (jobs live in server memory; the SSE stream replays) */
  useEffect(() => {
    if (chain.lastRunJobId === null) return
    if (st.run.job && st.run.job.job_id === chain.lastRunJobId) return
    attachRun(chain.lastRunJobId).catch(e => { toast.push({ kind: 'error', text: errText(e) }); setChain(c => ({ ...c, lastRunJobId: null })) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chain.lastRunJobId])

  /* the end-of-chain suggestion and the fix for each invalid junction come from /chain/compatible */
  const stepsKey = JSON.stringify(steps)
  useEffect(() => {
    if (!steps.length) { setSuggest(null); return }
    let alive = true
    compatibleAt(steps, steps.length).then(c => { if (alive) setSuggest(c) }).catch(() => { if (alive) setSuggest(null) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepsKey])
  useEffect(() => {
    if (!val.v) return
    const bad = val.v.junctions.filter(j => !j.ok).map(j => j.index)
    let alive = true
    for (const i of bad) {
      const key = `${i}:${stepsKey}`
      if (fixes[key]) continue
      compatibleAt(steps, i).then(c => { if (alive) setFixes(f => ({ ...f, [key]: c })) }).catch(() => {})
    }
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [val.v, stepsKey])

  /* ---- actions ---- */
  const run = async () => {
    if (!source || busy) return
    setBusy(true)
    try {
      const snap = await startRun(source.recording_id, spanOf(source), steps, 1200)
      setRefused(null)
      setChain(c => ({ ...c, lastRunJobId: snap.job_id }))
    } catch (e) {
      // a 422 carries {message, over_ceiling:[{index,name,max_span_samples}]}: shown as a card, not just a toast
      // over the Analyse limit the bridge also wrote a SLURM job: {slurm: {script_path, sbatch_command, script, …}}
      const d = e instanceof ApiError ? (e.detail as { over_ceiling?: { index: number; name: string; max_span_samples: number | null }[]; slurm?: SlurmWritten } | null) : null
      setRefused({ message: e instanceof ApiError ? e.message : String(e), over: d?.over_ceiling ?? [], slurm: d?.slurm })
      toast.push({ kind: 'error', text: `run refused · ${e instanceof ApiError ? e.message : String(e)}` })
    } finally { setBusy(false) }
  }
  const cancel = async () => { try { const note = await cancelCurrent(); toast.push({ text: `cancel requested · ${note ?? 'no run'}` }) } catch (e) { toast.push({ kind: 'error', text: errText(e) }) } }
  const restore = (u: UndoEntry) => { dropUndo(u); setChain(c => ({ ...c, saved: false, steps: u.steps })); markStale(u.staleIndex) }
  const deleteStep = (i: number) =>
    deleteStepAt({ steps, index: i, name: adapters.byName.get(stepName(steps[i]))?.page_name ?? steps[i].algorithm, setChain, toast })
  // the empty canvas (2026-10-15): the last chain with a block, offered back rather than loaded unasked
  const lastChain = steps.length === 0 ? loadLastChain() : null
  /* Ctrl/Cmd+Z restores the last deleted stage (frame chain-1e); ignored while typing in a field or during a run */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || e.key.toLowerCase() !== 'z') return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return
      if (running) return
      const u = popUndo()
      if (!u) return
      e.preventDefault()
      setChain(c => ({ ...c, saved: false, steps: u.steps })); markStale(u.staleIndex)
      toast.push({ text: `${u.label} restored` })
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [running, setChain, toast])
  const insertStep = (p: number, step: Step, open: boolean) => {
    setChain(c => ({ ...c, saved: false, steps: [...c.steps.slice(0, p), step, ...c.steps.slice(p)] }))
    markStale(p)
    setModalPos(null)
    if (open) navigate(`analyse/block/${p}`)
  }
  const insertByName = async (p: number, name: string) => {
    const ad = adapters.byName.get(name); if (!ad) return
    try { const { params } = await validateParams({ stage: ad.stage, algorithm: ad.algorithm, params: {} }); insertStep(p, { stage: ad.stage, algorithm: ad.algorithm, params }, false) }
    catch (e) { toast.push({ kind: 'error', text: errText(e) }) }
  }
  const importTemplate = (t: Template) => {
    setChain({ name: shortName(t), saved: false, steps: t.steps, lastRunJobId: null }); resetRun(); clearStale(); setPop(null)
    toast.push({ text: `imported ${shortName(t)} · ${t.steps.length} stages` })
  }
  const applyHistory = (s: Step[], name: string) => {
    setChain({ name, saved: false, steps: s, lastRunJobId: null }); resetRun(); clearStale(); setPop(null)
    toast.push({ text: `applied ${name} to the current source` })
  }
  const saveAsTemplate = async () => {
    const name = window.prompt('Template name', chain.name)
    if (!name) return
    try { const r = await saveTemplate(name, steps); toast.push({ text: `${r.name} · saved to the throwaway database copy (id ${r.id})` }); setChain(c => ({ ...c, name, saved: true })) }
    catch (e) { toast.push({ kind: 'error', text: errText(e) }) }
  }
  const doExport = async () => {
    if (!job) return
    try { const r = await exportRun(job.job_id); toast.push({ text: `exported run ${job.job_id} · ${r.path} · ${(r.bytes / 1024).toFixed(0)} kB`, ttlMs: 10000 }) }
    catch (e) { toast.push({ kind: 'error', text: errText(e) }) }
  }
  const useExample = () => { setSource(EXAMPLE_SOURCE); resetRun(); clearStale(); setChain(c => ({ ...c, lastRunJobId: null })); setPop(null) }
  /* fixup-ag: start the chain from saved window sets — the source is the Window pool block, put at 01 if absent */
  const pooled = isPoolSource(source)
  const POOL_CHAIN = ['preprocessing.window_pool', 'preprocessing.trace_shape', 'catalogue.shape_cluster']
  const buildPoolChain = async (): Promise<Step[]> => {
    const fresh: Step[] = []
    for (const name of POOL_CHAIN) {
      const ad = adapters.byName.get(name); if (!ad) throw new Error(`block ${name} is not in the registry`)
      const { params } = await validateParams({ stage: ad.stage, algorithm: ad.algorithm, params: {} })
      fresh.push({ stage: ad.stage, algorithm: ad.algorithm, params })
    }
    return fresh
  }
  const usePool = async () => {
    setSource(POOL_SOURCE); resetRun(); clearStale(); setPop(null)
    if (steps[0] && stepName(steps[0]) === 'preprocessing.window_pool') { setChain(c => ({ ...c, lastRunJobId: null })); return }
    // a span chain does not run on a pool: start RQ1's chain (pool → shape → cluster), the old one kept in Undo
    try {
      const fresh = await buildPoolChain()
      if (steps.length) pushUndo({ steps, staleIndex: 0, label: `the ${chain.name} chain` })
      setChain({ name: 'shape_clusters', saved: false, steps: fresh, lastRunJobId: null })
      toast.push({ text: 'Window pool → Trace shape → Shape clustering · tick the window sets on 01' })
    } catch (e) { toast.push({ kind: 'error', text: errText(e) }) }
  }
  /* fixup-ag seam (iii): the chain opened FROM elsewhere — Library › Window sets (`poolSets`: the ids to tick, empty
   * for none), Models › Launch's *Open in Analyse* (`template` + `poolId`: that template on that saved pool); `open`
   * goes on to a block page. The parameters are consumed once and cleared from the URL. */
  const qp = route.params
  const wantChain = qp.poolSets !== undefined || qp.poolId !== undefined || qp.template !== undefined
  useEffect(() => {
    if (!wantChain || !adapters.byName.size) return
    let alive = true
    ;(async () => {
      try {
        let next: Step[]
        let name = 'shape_clusters'
        if (qp.template) {
          const t = await getTemplate(Number(qp.template))
          next = t.steps.map(st => ({ ...st, params: { ...st.params } }))
          name = t.name
        } else next = await buildPoolChain()
        const i0 = next.findIndex(st => stepName(st) === 'preprocessing.window_pool')
        if (i0 < 0) throw new Error('that template does not start from a Window pool')
        if (qp.poolId) next[i0] = { ...next[i0], params: { ...next[i0].params, pool: String(qp.poolId) } }
        if (qp.poolSets !== undefined) next[i0] = { ...next[i0], params: { ...next[i0].params, window_sets: qp.poolSets, pool: '' } }
        if (!alive) return
        if (steps.length && !(steps[0] && stepName(steps[0]) === 'preprocessing.window_pool')) pushUndo({ steps, staleIndex: 0, label: `the ${chain.name} chain` })
        setSource(POOL_SOURCE); resetRun(); clearStale()
        setChain({ name, saved: !!qp.template, steps: next, lastRunJobId: null })
        const open = qp.open
        setQuery({ poolSets: null, poolId: null, template: null, open: null }, true)
        toast.push({ text: qp.template ? `${name} on saved pool ${qp.poolId ?? ''}` : qp.poolSets ? `Window pool · set ${qp.poolSets} ticked` : 'Window pool · tick the window sets on 01' })
        if (open !== undefined) navigate(`analyse/block/${open}`)
      } catch (e) { toast.push({ kind: 'error', text: errText(e) }) }
    })()
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wantChain, qp.poolSets, qp.poolId, qp.template, adapters.byName.size])

  /* ---- toolbar derivations ---- */
  const n = steps.length
  const perStep = val.v?.estimate?.per_step_s ?? null
  // a step predicted in the prefix cache (with every predecessor cached too) costs nothing (critique r1)
  const prefixCached = (i: number) => { for (let k = 0; k <= i; k++) if (!val.v?.cache?.[k]?.cached) return false; return true }
  const allCachedFrom = (from: number) => n > from && Array.from({ length: n - from }, (_, k) => prefixCached(from + k)).every(Boolean)
  const estFrom = (from: number): number | null => {
    if (!perStep) return null
    let s = 0
    for (let k = from; k < perStep.length; k++) { if (prefixCached(k)) continue; const b = perStep[k]; if (b === null) return null; s += b }
    return s
  }
  const unknownSteps = val.v?.estimate?.unknown ?? []
  const fmtEst = (s: number | null) => s === null ? (unknownSteps.length ? 'unknown cost' : '≈ —') : s < 0.05 ? '≈ <0.1 s' : `≤ ${fmtDuration(s)} core est.`   // estimate_recipe_seconds is a calibrated upper bound, measured 70–230× high on short spans
  let est: { text: string; kind: 'amber' | 'blue' | 'red' | 'green' }
  if (running && job) {
    const cur = job.current_step ?? 0
    const pr = job.steps[cur]?.progress
    est = { text: `${pad2(cur + 1)} running · ${stepElapsed(cur).toFixed(1)} s${pr && pr.fraction !== null ? ` · ${Math.round(pr.fraction * 100)} %` : ''}`, kind: 'blue' }
  } else if (invalid) est = { text: `${invalid} invalid junction${invalid > 1 ? 's' : ''}`, kind: 'red' }
  else if (failedStep !== null && st.staleFrom === null) est = { text: `failed at ${pad2(failedStep + 1)} · ${failedStep > 1 ? `01–${pad2(failedStep)} cached` : failedStep === 1 ? '01 cached' : 'nothing cached'}`, kind: 'red' }
  else if (!source) est = { text: 'no source · nothing to estimate', kind: 'amber' }
  else if (stale !== null) est = allCachedFrom(stale) ? { text: '≈ <0.1 s · all in the step cache', kind: 'green' } : { text: `${fmtEst(estFrom(stale))} · ${pad2(stale + 1)} → ${pad2(n)}`, kind: 'amber' }
  else if (job?.status === 'completed') { const tv = Object.values(job.step_timings ?? {}); const fromCache = tv.filter(v => v === 0).length; est = { text: fromCache === tv.length ? '≈ <0.1 s · all from the step cache' : `${tv.length - fromCache} computed · ${fromCache} from the step cache`, kind: 'green' } }
  else if (allCachedFrom(0)) est = { text: '≈ <0.1 s · all in the step cache', kind: 'green' }
  else est = { text: `${fmtEst(estFrom(0))} · 01 → ${pad2(n)}`, kind: 'amber' }
  // W3-F: why a step has no estimate, in the estimator's own words (W2-ledger decision 24) — "calibrating" while its
  // cost model is being timed on this machine, the estimator's (or the calibration's) error, else uncalibrated
  const calibrating = val.v?.estimate?.calibrating ?? []
  const estErrors = val.v?.estimate?.errors ?? {}
  const whyUnknown = (i: number) => calibrating.includes(i) ? `${pad2(i + 1)} calibrating` : estErrors[String(i)] ? `${pad2(i + 1)}: ${estErrors[String(i)]}` : `${pad2(i + 1)} uncalibrated`
  if (unknownSteps.length && !running && (est.kind === 'amber')) est = { ...est, text: `${est.text} · ${unknownSteps.map(whyUnknown).join(' · ')}` }
  if (over.length && !running) est = { ...est, text: `${est.text} · ${over.length} over the local ceiling`, kind: 'red' }

  const runLabel = failedStep !== null && (st.staleFrom === null || !job) ? `↻ Retry from ${pad2(failedStep + 1)}` : stale !== null ? `↻ Re-run from ${pad2(stale + 1)}` : '▶ Run chain'
  // spec §9.6 / P4: a stage over its local ceiling is never run locally — the button is gated, the row explains
  const overTitle = overFirst !== null ? `stage ${pad2(overFirst + 1)} exceeds its local ceiling (${overAd?.max_span_samples?.toLocaleString() ?? '?'} samples) · shorten the span or use HPC (out of slice scope)` : null
  // W3-F: a step whose cost model is still being timed would route "unknown" and start blind — Run waits for it
  // (validation re-asks every few seconds until the calibration lands)
  const calibratingTitle = calibrating.length && !running ? `the cost model of ${calibrating.map(i => pad2(i + 1)).join(', ')} is being timed on this machine (calibrating) · Run waits until the estimate lands, so a run over the local limit is written as a SLURM job instead of starting here` : null
  const canRun = !!source && !invalid && n > 0 && !busy && !locked && !over.length && !calibratingTitle
  const routed = val.v?.route
  const slurmTitle = routed?.route === 'cluster' && !running
    ? `about ${fmtDuration(routed.estimate_s)} on this machine${routed.slowest ? ` (stage ${pad2(routed.slowest.index + 1)} is the slow one)` : ''} · over the Analyse local limit of ${fmtDuration(routed.ceiling_s)} · Run will write a SLURM job instead of running here`
    : null
  if (slurmTitle) est = { ...est, text: `${est.text} · over the local limit → SLURM`, kind: 'red' }
  const runTitle = !source ? 'no source' : locked ? 'the held-out recording cannot be run' : invalid ? 'fix the red junction first' : !n ? 'add a stage' : overTitle ?? calibratingTitle ?? slurmTitle ?? undefined

  /* ---- footer ---- */
  const term = val.v ? terminalWording(val.v.terminal_kind, val.v.terminal_label, val.v.template_kind) : { chip: val.error ? 'terminal — validation refused' : 'terminal — validating…', kind: 'grey' as const }
  const lastRow = rows[n - 1]
  const terminalPayload = lastRow?.payload ?? null
  const nSpans = terminalPayload?.type === 'spanset' ? (terminalPayload as SpansetPayload).n : null
  // *Pass N to Review* is the slideshow's *Send N to Review* on the same run: one call, two buttons (fixup-L)
  const pass = useSendRunToReview({ chainName: chain.name, dbRunId: job?.status === 'completed' ? (job.db_run_id ?? null) : null, n: nSpans ?? 0, stale: stale !== null })
  const passReason = nSpans === null ? 'needs a completed run with a SpanSet terminal' : pass.reason
  let headline: string, sub: string
  if (running && job && st.nullProgress) {
    // every stage has landed; the paired null is N more runs of the whole chain on a surrogate
    const np = st.nullProgress
    headline = `Drawing the null · draw ${np.draw} of ${np.draws}${np.fraction != null ? ` · ${Math.round(np.fraction * 100)} % of this draw${np.stage ? ` (${np.stage})` : ''}` : ''}`
    sub = 'every stage is done · each draw is the whole chain again on a surrogate of the span · draws already made for this recipe are reused · cancel stops the draw in hand'
  } else if (running && job) {
    const cur = job.current_step ?? 0
    const pr = job.steps[cur]?.progress
    headline = cancelling ? `Cancelling · stage ${pad2(cur + 1)} of ${pad2(job.n_steps)} is still running` : `Running ${pad2(cur + 1)} of ${pad2(job.n_steps)}${pr && pr.fraction !== null ? ` · ${pr.done.toLocaleString()} of ${pr.total.toLocaleString()}${pr.stage ? ` ${pr.stage}` : ''}` : ''}`
    // W3-F: a block that checks cancel inside its own loop (it reports its progress; window matrix, multiscale
    // entropy, the pan matrix profile; cycle shapes checks without reporting) stops within one of its iterations;
    // any other stops when its stage ends
    sub = cancelling
      ? (pr ? 'cancel accepted · this stage checks it as it goes and stops at its next iteration · the stages already done are kept'
        : 'cancel accepted · the run stops inside this stage if its block checks for it, else when the stage ends · the stages already done are kept')
      : pr ? 'stages land as they finish · this stage reports its own progress, and a cancel stops it at its next iteration'
        : 'stages land as they finish · a cancel stops a stage inside it when its block checks for it, else at the next stage'
  }
  else if (invalid) { headline = 'Chain is invalid'; sub = 'fix the red junction · validation runs on every edit' }
  else if (job?.status === 'failed') { headline = 'No result'; sub = `run ${job.db_run_id ? `#${job.db_run_id}` : `job ${job.job_id}`} failed at ${pad2((job.error?.step ?? 0) + 1)} · nothing was written to detections` }
  else if (job?.status === 'cancelled') { const at = job.steps.findIndex(s => s.status === 'cancelled'); const inside = at >= 0 && job.steps[at].progress; headline = 'Cancelled'; sub = `run ${job.db_run_id ? `#${job.db_run_id}` : `job ${job.job_id}`} stopped ${inside ? `inside ${pad2(at + 1)} (at ${job.steps[at].progress!.done.toLocaleString()} of ${job.steps[at].progress!.total.toLocaleString()}) · nothing of it was cached` : `before ${pad2((at >= 0 ? at : (job.error?.step ?? 0)) + 1)}`} · ${job.steps.filter(s => s.status === 'done').length} of ${job.n_steps} stages kept` }
  else if (job?.status === 'completed') {
    headline = `last run · ${terminalPayload?.summary ?? job.steps[job.n_steps - 1]?.summary ?? 'done'}`
    const core = job.step_timings ? Object.values(job.step_timings).reduce((a, b) => a + b, 0) : null
    sub = `job ${job.job_id} · db run #${job.db_run_id ?? '—'} · ${job.detections_written ?? 0} written to detections · ${core !== null ? fmtTiming(core) + ' core' : ''} · ${fmtDuration(job.elapsed_s)} wall · ${nullText(job.null)}${stale !== null ? ` · ${pad2(stale + 1)} → ${pad2(n)} stale` : ''}`
  } else { headline = 'No result yet'; sub = source ? 'run the chain to see every intermediate' : 'send a span from Explore or use the example span' }

  /* ---- Train model (fixup-ag seam iii): the template saved, the pool already saved by its block, Launch prefilled ---- */
  const [training, setTraining] = useState(false)
  const lastTree = terminalPayload && terminalPayload.type === 'grouping' ? (terminalPayload as { tree?: { mapping_state: string; k: number } }).tree : undefined
  const poolPayload = rows[0]?.payload as { pool?: { window_set_id: number } } | null | undefined
  const trainReason: string | null = !pooled ? 'a Window pool chain only'
    : job?.status !== 'completed' ? 'run the chain first'
    : stale !== null ? `${pad2(stale + 1)} → ${pad2(n)} are stale · re-run so the template and the run agree`
    : !lastTree ? 'the chain must end in Shape clustering'
    : lastTree.mapping_state !== 'complete' ? `map every cluster at k = ${lastTree.k} (interesting / not) on the Shape clustering page first`
    : !poolPayload?.pool ? 'the pool was not saved by this run' : null
  const trainModel = async () => {
    if (trainReason || !poolPayload?.pool) return
    setTraining(true)
    try {
      const r = await saveTemplate(chain.name || 'shape_clusters', steps)
      setChain(c => ({ ...c, saved: true }))
      navigate(`models/launch?arm=b2&template=${r.id}&pool=${poolPayload.pool.window_set_id}`)
    } catch (e) { toast.push({ kind: 'error', text: errText(e) }) } finally { setTraining(false) }
  }

  /* ---- rows ---- */
  const sourceEnvelope: EnvelopeSeries | null = env?.envelope ?? null
  const sourcePayload: SignalPayload | null = env ? { type: 'signal', fs: env.fs, n: env.n_samples, t0_s: env.t0_s, t1_s: env.t1_s, y_range: null, envelope: env.envelope, summary: '', unit: env.unit } : null
  const ghostFor = (i: number): EnvelopeSeries | null => {
    for (let j = i - 1; j >= 0; j--) { const p = rows[j]?.payload; if (p && p.type === 'signal') return (p as SignalPayload).envelope }
    return sourceEnvelope
  }
  const throwTest = route.params.throw === '1'

  const rowFor = (i: number): ReactNode => {
    const step = steps[i]; const r = rows[i]
    const ad = adapters.byName.get(stepName(step))
    const title = ad?.page_name ?? step.algorithm
    const sig = ad?.signature ?? `${step.stage}.${step.algorithm}`
    const jstep = job && sameStep(job.recipe.steps[i], step) ? job.steps[i] : undefined
    const caption = r.payload?.summary ?? (r.hasResult ? '' : null) ?? (jstep?.summary && r.status !== 'new' ? jstep.summary : paramCaption(step, ad))
    const timing = (r.status === 'cached' && r.timing !== null && r.timing !== 0) ? fmtTiming(r.timing) : null
    const badgeText = r.status === 'cached' && r.timing === 0 ? 'cached · 0 s' : r.status === 'cached' && r.timing !== null && r.timing !== 0 ? 'computed · now cached' : r.status === 'waiting' ? '⌛ waiting' : undefined
    const badgeTitle = r.status === 'cached' ? (r.timing === 0 ? 'restored from the prefix cache (core step time 0.0 s)' : r.timing !== null ? `core step time ${r.timing.toFixed(3)} s` : 'predicted from the prefix cache · run to load the result') : r.status === 'stale' ? 'a parameter or an upstream stage changed since this result' : undefined
    const ghost = ghostFor(i)
    const elapsed = r.status === 'running' ? stepElapsed(i) : 0

    let overlay: ReactNode = null
    let plot = (x: XScale, w: number, h: number): ReactNode => r.payload ? renderByType(r.payload, { x, width: w, height: h, ghost, t0, t1 }) : null
    switch (r.status) {
      case 'running':
        {
          // W3-F: the block's own fraction when it reports one (real progress, never a simulated bar); otherwise the
          // indeterminate bar and the elapsed time, and the note says this block reports no fraction
          const pr = jstep?.progress
          const frac = pr && pr.fraction !== null ? Math.max(0, Math.min(1, pr.fraction)) : null
          overlay = <>{r.payload && <div className="an-plot-veil" />}<div className="an-progress" data-testid={`progress-${i + 1}`}>
            {frac !== null
              ? <div style={{ width: '40%', height: 5, borderRadius: 999, background: 'var(--grey-200)', overflow: 'hidden' }}><div data-testid={`step-fraction-${i + 1}`} data-fraction={frac.toFixed(3)} style={{ width: `${(frac * 100).toFixed(1)}%`, height: '100%', background: 'var(--blue)', borderRadius: 999 }} /></div>
              : <div className="bar" />}
            <div className="txt">{title} · computing · {elapsed.toFixed(1)} s{frac !== null && pr ? ` · ${pr.done.toLocaleString()} of ${pr.total.toLocaleString()}${pr.stage ? ` ${pr.stage}` : ''} (${Math.round(frac * 100)} %)` : ''}{jstep?.cached_predicted ? ' · predicted cache hit' : ''}</div>
            <div className="note">{frac !== null ? 'the block\'s own progress, from inside the stage · cancel stops it at its next iteration' : 'this block reports no fraction of its own · a cancel stops it inside the stage if it checks for one, else before the next stage'}</div>
          </div></>
        }
        break
      case 'waiting':
        plot = () => null
        overlay = <div className="an-plot-empty">⌛ waits for {pad2((job?.current_step ?? 0) + 1)} · last result hidden</div>
        break
      case 'stale':
        overlay = <><div className="an-plot-veil" /><span className="an-stale-pill" data-testid={`stale-pill-${i + 1}`}>⏱ last run shown · stale</span></>
        break
      case 'new':
        plot = () => null
        overlay = <div className="an-plot-empty">{r.cachedPredicted ? 'result predicted in the step cache · run the chain to load it' : 'no result yet · run the chain'}</div>
        break
      case 'blocked':
        plot = () => null
        overlay = <div className="an-plot-empty">blocked · {pad2((job?.error?.step ?? 0) + 1)} failed upstream</div>
        break
      case 'cancelled':
        plot = () => null
        overlay = <div className="an-plot-empty">cancelled before this stage ran</div>
        break
      case 'invalid':
        overlay = r.payload ? <div className="an-plot-veil" /> : <div className="an-plot-empty">this stage cannot run — see the junction above</div>
        break
      case 'cached':
        if (!r.payload) { plot = () => null; overlay = <div className="an-plot-empty">{jstep?.status === 'done' ? 'loading result…' : 'in the step cache · run the chain to load it'}</div> }
        break
    }
    let replace: ReactNode = null
    if (r.status === 'failed' && job) {
      const err = job.error
      replace = (
        <div className="an-fail" data-testid="error-card">
          <div style={{ color: 'var(--red)', fontSize: 18 }}>ⓘ</div>
          <div style={{ minWidth: 0 }}>
            <div className="t">{pad2(i + 1)} {title} failed after {fmtTiming(jstep?.elapsed_s ?? null) || '—'}</div>
            <div className="m" title={err?.message}>{err?.message ?? 'unknown error'}</div>
            <div className="s">adapter {err?.adapter ?? stepName(step)} · recipe {job.config_hash ?? val.v?.hashes?.config_hash ?? `job ${job.job_id}`} · traceback in log</div>
          </div>
          <div className="acts">
            <button className="btn" onClick={() => setLogOpen(true)} data-testid="view-log">View log</button>
            <button className="btn" onClick={() => navigate(`analyse/block/${i}`)}>Open settings</button>
            <button className="btn primary" onClick={run} disabled={!canRun} title={runTitle}>↻ Retry {pad2(i + 1)}</button>
          </div>
        </div>
      )
    } else if (r.overCeiling && r.status !== 'running') {
      const nSamples = source ? source.end_idx - source.start_idx : 0
      replace = (
        <div className="an-hpc" data-testid="hpc-card">
          <div>
            <div className="t">⛭ this run would fail locally at {pad2(i + 1)} · the span exceeds the local ceiling → HPC</div>
            <div className="s">{nSamples.toLocaleString()} samples · {title} caps local runs at {ad?.max_span_samples?.toLocaleString() ?? '?'} samples · Run is disabled (§9.6) · on the cluster the stage pauses here and its result re-enters through the manifest inbox (P4, P24)</div>
          </div>
          <div className="row"><button className="btn" disabled aria-disabled="true" title="create a SLURM script for this stage · out of slice scope">Create SLURM script</button><button className="btn" disabled aria-disabled="true" title="upload the stage's computed artifact · out of slice scope">Upload computed artifact</button></div>
        </div>
      )
    }
    return (
      <ChainRow key={`step-${i}`} testIndex={i + 1} rowClass={r.status === 'failed' || r.status === 'invalid' ? r.status : ''} num={pad2(i + 1)} title={title} badge={r.status} badgeText={badgeText} badgeTitle={badgeTitle} timingText={timing} resetKey={`${job?.job_id ?? 'none'}-${i}`}
        signature={sig} caption={caption} t0={t0} t1={t1} plot={plot} overlay={overlay} replace={replace}
        onSettings={() => navigate(`analyse/block/${i}`)} onDelete={running ? undefined : () => deleteStep(i)}
        actions={ad?.output_kind === 'windowset' && !pooled ? <SaveWindowSetButton small jobId={job?.status === 'completed' ? job.job_id : null} step={i}
          defaultName={`ws_${(chain.name || 'chain').replace(/[^A-Za-z0-9_.-]+/g, '_')}_${pad2(i + 1)}`.slice(0, 64)}
          disabledReason={r.status === 'stale' ? 'this step is stale · re-run before saving its windows' : r.status !== 'cached' ? 'this step has no result in the last run' : null}
          testid={`save-window-set-${i + 1}`} /> : undefined} />
    )
  }

  const junctionFor = (i: number): ReactNode => {
    const j = val.v?.junctions[i]
    if (!j || j.ok) return null
    const fix = fixes[`${i}:${stepsKey}`]
    const first = fix?.rows.find(r => r.ok)
    const firstName = first ? adapters.byName.get(first.name)?.page_name ?? first.name : null
    const here = steps[i]; const prev = steps[i - 1]
    const hereName = `${pad2(i + 1)} ${adapters.byName.get(stepName(here))?.page_name ?? here.algorithm}`
    const prevName = prev ? `${pad2(i)} ${adapters.byName.get(stepName(prev))?.page_name ?? prev.algorithm}` : 'Source'
    return (
      <div className="an-junction" key={`junction-${i}`}>
        <div className="an-junction-pill" data-testid="junction-error" title={j.core_reason || j.reason}>
          <span>⊗ {hereName} needs {j.expected ? TYPE_LABEL[j.expected] : '?'} · {prevName} emits {TYPE_LABEL[j.producing]}</span>
          {firstName && <button className="btn sm" onClick={() => insertByName(i, first!.name)} data-testid="junction-insert">+ Insert {firstName} here</button>}
          <button className="btn sm" onClick={() => setModalPos(i)} data-testid="junction-browse">☰ Show blocks that fit</button>
        </div>
      </div>
    )
  }

  const insertPill = (p: number, end = false) => (
    <div className="an-insert-line" key={`ins-${p}`}><button className="an-insert" onClick={() => setModalPos(p)} data-testid={`insert-${p}`} disabled={running} title={running ? 'wait for the run' : 'insert a stage here'}>+ insert{end ? ' · end of chain' : ''}</button></div>
  )
  const fitNames = suggest ? suggest.rows.filter(r => r.ok).map(r => adapters.byName.get(r.name)) : []
  const fitOutputs = Array.from(new Set(fitNames.map(a => a?.output_kind).filter(Boolean))).map(k => TYPE_LABEL[k!])

  return (
    <>
      <Header workspace="Analyse" page="Chain" subtitle="build here · open a block to tune it" />
      <div className="page"><div className="page-inner" data-testid="chain-page">
        {steps.length === 0 && !running && (
          <div className="card card-pad" data-testid="chain-empty" style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ minWidth: 0, flex: '1 1 320px' }}>
              <div className="b">Start a chain</div>
              <p className="muted" style={{ margin: '4px 0 0' }}>A chain is the blocks a span of recording goes through, left to right. Pick a saved template, or add the first block yourself.</p>
            </div>
            <button className="btn next" onClick={() => setPop('import')} data-testid="chain-empty-import">Import a template</button>
            <button className="btn" onClick={() => setModalPos(0)} data-testid="chain-empty-add">Add the first block</button>
            {lastChain && <button className="btn" onClick={() => { setChain({ ...lastChain, saved: false, lastRunJobId: null }); resetRun(); clearStale() }} data-testid="chain-empty-restore"
              title="the last chain this browser had, kept across sessions">Restore {lastChain.name} · {lastChain.steps.length} block{lastChain.steps.length === 1 ? '' : 's'}</button>}
            <button className="btn" onClick={() => { setChain({ ...EXAMPLE_CHAIN }); resetRun(); clearStale() }} data-testid="chain-empty-example"
              title="detrend, then a matrix profile, then a threshold: the chain the page used to open on">Example · {EXAMPLE_CHAIN.name}</button>
          </div>
        )}
        {adapters.error && <div className="error-card"><h3>adapter registry failed to load</h3><pre>{adapters.error}</pre></div>}
        {val.error && <div className="error-card"><h3>validation failed</h3><pre>{val.error}</pre></div>}
        {st.run.error && <RunErrorCard error={st.run.error} kind={st.run.errorKind} />}
        {val.v?.recipe_error && <div className="error-card" style={{ padding: '8px 12px' }}><h3>recipe cannot be built</h3><div className="mono small">{val.v.recipe_error}</div></div>}
        {refused && (
          <div className="error-card" style={{ padding: '8px 12px' }} data-testid="run-refused-card">
            <h3>run refused by the bridge (422)</h3>
            <div className="mono small">{refused.message}</div>
            {refused.over.length > 0 && <div className="mono small" style={{ marginTop: 4, color: 'var(--muted)' }}>{refused.over.map(o => `${pad2(o.index + 1)} ${adapters.byName.get(o.name)?.page_name ?? o.name} · ceiling ${o.max_span_samples?.toLocaleString() ?? '?'} samples`).join(' · ')}</div>}
            {refused.slurm && (
              <div style={{ marginTop: 6 }} data-testid="run-refused-slurm">
                <div className="mono small">SLURM job written · <b>{refused.slurm.sbatch_command}</b> · wall time {refused.slurm.slurm_time}</div>
                <div className="mono small" style={{ color: 'var(--muted)' }}>{refused.slurm.script_path} · recipe {refused.slurm.recipe_path}</div>
                {refused.slurm.null_note && <div className="mono small" style={{ color: 'var(--muted)' }}>{refused.slurm.null_note}</div>}
                {(refused.slurm.warnings ?? []).map((w, i) => <div key={i} className="mono small" style={{ color: 'var(--muted)' }}>{w}</div>)}
                <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                  <button className="btn sm" onClick={() => { navigator.clipboard?.writeText(refused.slurm?.script ?? '').then(() => toast.push({ text: 'SLURM script copied' }), err => toast.push({ kind: 'error', text: `copy failed · ${String(err)}` })) }}>Copy script</button>
                </div>
                <details style={{ marginTop: 4 }}><summary className="mono small">the script</summary><pre className="mono small" style={{ maxHeight: 220, overflow: 'auto' }}>{refused.slurm.script}</pre></details>
              </div>
            )}
          </div>
        )}

        {/* toolbar */}
        <div className="an-toolbar">
          <NameChip chain={chain} onRename={name => setChain(c => ({ ...c, name, saved: false }))} extra={job && failedStep !== null ? <span className="chip red" style={{ height: 20, fontSize: 10, padding: '0 6px' }} title={`job ${job.job_id}`}>#{job.db_run_id ?? job.job_id} failed</span> : null} />
          <Popwrap open={pop === 'source'} onClose={() => setPop(null)}>
            <SourceChip source={source} onClick={() => setPop(p => p === 'source' ? null : 'source')} />
            {pop === 'source' && (
              <div className="an-pop left" style={{ width: 380 }} data-testid="source-popover">
                <h4>Source <span>single channel · one span (P3)</span></h4>
                {source ? <div className="an-pop-item"><span className="chip blue" style={{ height: 22 }}>current</span><span><DatasetName file={source.source_file} /> · {source.channel_name} · samples {source.start_idx}–{source.end_idx}{source.label ? ` · ${source.label}` : ''}</span></div> : <div className="an-pop-note">no source yet</div>}
                <div className="an-pop-item btnlike" onClick={useExample} data-testid="use-example">⌇ Use the example span ({EXAMPLE_SOURCE.channel_name} · {(EXAMPLE_SOURCE.start_idx / EXAMPLE_SOURCE.fs / 3600).toFixed(1)}–{(EXAMPLE_SOURCE.end_idx / EXAMPLE_SOURCE.fs / 3600).toFixed(1)} h)</div>
                <div className="an-pop-item btnlike" onClick={() => navigate('explore/corpus')}>→ Pick in Explore</div>
                <div className="an-pop-item btnlike" onClick={usePool} data-testid="use-pool">⌗ Start from a Window pool (saved window sets, in place of a span)</div>
              </div>
            )}
          </Popwrap>
          <SurrogateToggle />
          <EstimateChip text={est.text} kind={est.kind} />
          <span className="spacer" />
          <Popwrap open={pop === 'history'} onClose={() => setPop(null)}>
            <button className={`btn${pop === 'history' ? ' primary' : ''}`} onClick={() => setPop(p => p === 'history' ? null : 'history')} data-testid="history-button">⟲ History</button>
            {pop === 'history' && <HistoryPopover source={source} onApply={applyHistory} onClose={() => setPop(null)} />}
          </Popwrap>
          <Popwrap open={pop === 'import'} onClose={() => setPop(null)}>
            <button className={`btn${pop === 'import' ? ' primary' : ''}`} onClick={() => setPop(p => p === 'import' ? null : 'import')} data-testid="import-button">⤓ Import</button>
            {pop === 'import' && <TemplatesPopover onPick={importTemplate} onClose={() => setPop(null)} />}
          </Popwrap>
          <button className="btn" onClick={saveAsTemplate} data-testid="save-template" disabled={!n}>▢ Save template</button>
          {running ? <button className="btn danger" onClick={cancel} data-testid="cancel-button" disabled={cancelling}
              title={cancelling ? 'cancel accepted · the run stops inside the current stage if its block checks for a cancel, else when the stage ends' : 'stop the run — inside the current stage when its block checks for a cancel, else after it'}>{cancelling ? '■ Cancelling…' : '■ Cancel'}</button>
            : <button className="btn next" onClick={run} disabled={!canRun} data-testid="run-button" title={runTitle}>{runLabel}</button>}
        </div>

        <CrosshairProvider value={{ t: cross, setT: setCross }}>
          {/* source row */}
          {pooled ? (
            <div className="card an-nosource" data-testid="chain-row-0">
              <span className="badge cached">source</span>
              <span className="mono">Window pool · step 01 reads saved window sets in place of a span · tick them on its page</span>
              <span className="spacer" style={{ flex: 1 }} />
              <button className="btn" onClick={() => navigate('analyse/block/0')} data-testid="open-pool-block">Open the Window pool</button>
              <button className="btn" onClick={useExample}>Use the example span instead</button>
            </div>
          ) : source ? (
            <ChainRow testIndex={0} num={null} title="Source" badge={locked ? 'blocked' : 'source-cached'} badgeText={locked ? 'held out' : undefined} badgeTitle={locked ? 'the held-out recording is never loaded (D6)' : "the span is loaded from the channel's .npy on disk"} signature="— → Signal"
              caption={`${source.label === 'example span' ? 'example span' : 'signal span from Explore'} · ${fmtDuration(t1 - t0)} · ${source.fs} Hz`} captionTitle={`${source.source_file} · ${source.channel_name} · samples ${source.start_idx}–${source.end_idx}`} t0={t0} t1={t1}
              plot={(x, w, h) => sourcePayload ? <SourcePlot p={sourcePayload} x={x} w={w} h={h} throwTest={throwTest} /> : null}
              replace={locked ? (
                <div className="an-hpc" data-testid="held-out-card" style={{ background: 'var(--grey-100)', borderColor: 'var(--grey-200)' }}>
                  <div><div className="t" style={{ color: 'var(--text-2)' }}>🔒 {source.source_file} is held out — the bridge refuses it (423) and this page shows none of its data</div><div className="s">D6: while the lock is on, every workspace refuses it · pick a span from another recording, or turn the lock off in Settings › Datasets (type the recording's name)</div></div>
                  <button className="btn" onClick={useExample}>Use the example span</button>
                </div>
              ) : undefined}
              overlay={envError ? <div className="error-card" style={{ position: 'absolute', inset: 4, padding: '6px 10px' }}><h3>source window failed</h3><pre>{envError}</pre></div> : !env ? <div className="skeleton" style={{ position: 'absolute', inset: 6 }} /> : null} />
          ) : (
            <div className="card an-nosource" data-testid="chain-row-0">
              <span className="badge new">no source</span>
              <span className="mono">no source yet — send a span from Explore</span>
              <span className="spacer" style={{ flex: 1 }} />
              <button className="btn" onClick={() => navigate('explore/corpus')}>Go to Explore</button>
              <button className="btn primary" onClick={useExample} data-testid="use-example">Use the example span ({EXAMPLE_SOURCE.channel_name} · {(EXAMPLE_SOURCE.start_idx / EXAMPLE_SOURCE.fs / 3600).toFixed(1)}–{(EXAMPLE_SOURCE.end_idx / EXAMPLE_SOURCE.fs / 3600).toFixed(1)} h)</button>
              <button className="btn" onClick={usePool} data-testid="use-pool-card">Start from a Window pool</button>
            </div>
          )}
          {steps.map((_, i) => (
            <span key={i} style={{ display: 'contents' }}>
              {junctionFor(i) ?? insertPill(i)}
              {rowFor(i)}
            </span>
          ))}
          {insertPill(n, true)}
          {suggest && suggest.n_fit > 0 && n > 0 && (
            <div className="card an-suggest" data-testid="suggest-card">
              <span style={{ color: 'var(--muted)', fontSize: 18 }}>✦</span>
              <div>
                <div className="t">{suggest.producing_label} → {fitOutputs.join(' / ') || '?'} fits here</div>
                <div className="s">{fitNames.slice(0, 6).map(a => a?.page_name ?? '?').join(' · ')}{fitNames.length > 6 ? ' · …' : ''} — {suggest.n_fit} block{suggest.n_fit === 1 ? '' : 's'} accept{suggest.n_fit === 1 ? 's' : ''} {suggest.producing_label}</div>
              </div>
              <div className="row">
                <button className="btn" onClick={() => setModalPos(n)}>☷ Browse compatible</button>
                {fitNames[0] && <button className="btn primary" onClick={() => insertByName(n, fitNames[0]!.name)} disabled={running}>+ Insert {fitNames[0].page_name}</button>}
              </div>
            </div>
          )}
          {/* shared axis */}
          {!pooled && <FooterAxis t0={t0} t1={t1} enabled={!!source} />}
        </CrosshairProvider>

        {/* footer */}
        <div className="card an-footer">
          <span className={`chip ${term.kind}`} data-testid="footer-terminal" title="spec §6.1: the terminal type decides what the chain is">{term.chip}</span>
          <div style={{ minWidth: 0 }}>
            <div className="head" data-testid="footer-headline">{headline}</div>
            <div className="sub" data-testid="footer-sub">{sub}</div>
          </div>
          <div className="acts">
            {pooled && <button className="btn primary" onClick={trainModel} disabled={!!trainReason || training} title={trainReason ?? 'save the template (the pool is saved) and open Models › Launch with arm B.2 filled in'} data-testid="train-model">{training ? 'Saving…' : '⚙ Train model'}</button>}
            <button className="btn" onClick={doExport} disabled={job?.status !== 'completed'} data-testid="export-run" title={job?.status === 'completed' ? 'write a JSON report of this run' : 'needs a completed run'}>⤒ Export run</button>
            <button className="btn" disabled aria-disabled="true" title="sends the terminal SpanSet into a new chain · out of slice scope">→ Analyse events</button>
            <button className="btn primary" onClick={pass.send} disabled={!!passReason || pass.busy} aria-disabled={!!passReason || pass.busy} data-testid="pass-to-review"
              title={passReason ?? `a Review queue over the ${nSpans} spans run #${job?.db_run_id} wrote · verdicts write adjudications`}>→ Pass {nSpans ?? ''} to Review</button>
          </div>
        </div>
      </div></div>

      {modalPos !== null && <InsertStageModal steps={steps} position={modalPos} adapters={adapters} source={source} onClose={() => setModalPos(null)} onInsert={(s, open) => insertStep(modalPos, s, open)} />}
      {logOpen && job && <RunLogModal jobId={job.job_id} onClose={() => setLogOpen(false)} />}
    </>
  )
}

function SourcePlot({ p, x, w, h, throwTest }: { p: SignalPayload; x: XScale; w: number; h: number; throwTest: boolean }) {
  // near-black raw signal (frame chain-1): use the shared renderer with the trace colour overridden
  return <div style={{ ['--trace-blue' as string]: 'var(--trace)' } as React.CSSProperties}>{renderByType(p, { x, width: w, height: h, ghost: null, t0: p.t0_s, t1: p.t1_s, throwForTest: throwTest })}</div>
}

function FooterAxis({ t0, t1, enabled }: { t0: number; t1: number; enabled: boolean }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width)
  const x = makeX(t0, t1, w)
  return (
    <div className="an-axis" data-testid="footer-axis">
      <span className="lbl">all rows share this time axis</span>
      <div ref={ref} style={{ height: 22 }}>{enabled && size.width > 0 && <svg width={w} height={22}><TimeAxis x={x} y={2} t0={t0} t1={t1} n={7} ends /></svg>}</div>
    </div>
  )
}

// keep the type import used (PLOT_H is the shared row height; exported for the block page)
export const ROW_PLOT_H = PLOT_H
