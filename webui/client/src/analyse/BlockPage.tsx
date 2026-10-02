/* Analyse › block page (frames chain-3, chain-7, chain-7b): the PROCESS for one block —
   what it looked at, what it computed, the output — beside a generated parameters panel.
   Editing a parameter marks this block and everything downstream stale (P5, §6.8). */
import { useEffect, useMemo, useState } from 'react'
import { ApiError, saveTemplate, type EncodingSymbolicPayload, type EnvelopeSeries, type Payload, type ScoresPayload, type SignalPayload, type SpansetPayload, type WindowsetPayload, type GroupingPayload, type ModelPayload } from '../api'
import { makeX } from '../charts/scale'
import { axisUnit, unitWords, type DisplayUnit } from '../charts/units'
import { ErrorBoundary } from '../shell/ErrorBoundary'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { fmtDuration, fmtHours, navigate, useApp } from '../state'
import { ParamsPanel, fmtParam } from './ParamsPanel'
import { renderByType } from './Renderer'
import { deriveRows, fmtTiming, isErrorPayload, jobForSource } from './rowState'
import { attachRun, cancelCurrent, cancelPending, markStale, startRun, stepElapsed, syncToSource, useAnalyseStore } from './store'
import { EstimateChip, isHeldOut, NameChip, RunErrorCard, SourceChip, SurrogateToggle, t0Of, t1Of, useSourceEnvelope } from './toolbar'
import { pad2, stepName, useAdapters } from './useAdapters'
import { spanOf, useValidation } from './useValidation'
import { BlockProcess } from './views/registry'

const errText = (e: unknown) => e instanceof ApiError ? `${e.message}${e.traceback ? '\n' + e.traceback : ''}` : String(e)

export function BlockPage({ index }: { index: number }) {
  const { source, chain, setChain } = useApp()
  const toast = useToast()
  const adapters = useAdapters()
  const st = useAnalyseStore()
  const { payloads } = st.run
  const job = jobForSource(st.run.job, source)
  const steps = chain.steps
  const step = steps[index] as typeof steps[number] | undefined
  const val = useValidation(steps, source)
  const { env } = useSourceEnvelope(source)
  const rows = useMemo(() => deriveRows(steps, job, payloads, st.staleFrom, val.v), [steps, job, payloads, st.staleFrom, val.v])
  const [busy, setBusy] = useState(false)
  const [refused, setRefused] = useState<string | null>(null)
  const ad = step ? adapters.byName.get(stepName(step)) : undefined
  const title = ad?.page_name ?? step?.algorithm ?? '?'
  const t0 = source ? t0Of(source) : 0
  const t1 = source ? t1Of(source) : 1
  const running = job?.status === 'running' || job?.status === 'queued'
  // cancel is checked between steps, so there is a whole step of interval in
  // which the click has landed and nothing visible has happened (fixup-a 11)
  const cancelling = cancelPending(st.run)
  const locked = isHeldOut(source)
  const over = val.v?.over_ceiling ?? []
  const overTitle = over.length ? `stage ${pad2(over[0] + 1)} exceeds its local ceiling (${adapters.byName.get(stepName(steps[over[0]]))?.max_span_samples?.toLocaleString() ?? '?'} samples) · shorten the span or use HPC (out of slice scope)` : null
  const canRun = !!source && !running && !busy && !locked && !over.length
  const runTitle = !source ? 'no source' : locked ? 'the held-out recording cannot be run' : running ? 'a run is in progress' : overTitle ?? undefined
  // a source change forgets a job (and stale index) that belongs to another recording/span (critique r1)
  const sourceKey = source ? `${source.recording_id}:${source.start_idx}:${source.end_idx}` : ''
  useEffect(() => { syncToSource(source); setRefused(null) }, [sourceKey])   // eslint-disable-line react-hooks/exhaustive-deps

  const setParam = (name: string, value: unknown) => {
    setChain(c => ({ ...c, saved: false, steps: c.steps.map((s, k) => k === index ? { ...s, params: { ...s.params, [name]: value } } : s) }))
    markStale(index)
  }
  const revert = () => {
    if (!ad) return
    setChain(c => ({ ...c, saved: false, steps: c.steps.map((s, k) => k === index ? { ...s, params: Object.fromEntries(ad.params.map(p => [p.name, p.default])) } : s) }))
    markStale(index)
    toast.push({ text: `${pad2(index + 1)} ${title} reverted to the adapter defaults` })
  }
  // stays on the block page (frames chain-3 / 7b): the ribbon chip and the process card show the run,
  // and the payload refreshes in place when the run ends — the module store keeps streaming (critique r1)
  /* re-attach after a reload / cold deep link (function critic P1-1): the chain page does the same */
  useEffect(() => {
    if (chain.lastRunJobId === null) return
    if (st.run.job && st.run.job.job_id === chain.lastRunJobId) return
    attachRun(chain.lastRunJobId).catch(e => { toast.push({ kind: 'error', text: errText(e) }); setChain(c => ({ ...c, lastRunJobId: null })) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chain.lastRunJobId])

  const rerun = async () => {
    if (!source || busy) return
    setBusy(true)
    try { const snap = await startRun(source.recording_id, spanOf(source), steps, 1200); setRefused(null); setChain(c => ({ ...c, lastRunJobId: snap.job_id })) }
    catch (e) { setRefused(e instanceof ApiError ? e.message : String(e)); toast.push({ kind: 'error', text: `run refused · ${errText(e)}` }) } finally { setBusy(false) }
  }
  const cancel = async () => { try { const note = await cancelCurrent(); toast.push({ text: `cancel requested · ${note ?? 'no run'}` }) } catch (e) { toast.push({ kind: 'error', text: errText(e) }) } }
  const saveAsTemplate = async () => {
    const name = window.prompt('Template name', chain.name)
    if (!name) return
    try { const r = await saveTemplate(name, steps); toast.push({ text: `${r.name} · saved to the throwaway database copy (id ${r.id})` }); setChain(c => ({ ...c, name, saved: true })) }
    catch (e) { toast.push({ kind: 'error', text: errText(e) }) }
  }

  if (!step) {
    return (
      <>
        <Header workspace="Analyse" page={`${pad2(index + 1)} —`} subtitle="process detail · the chain row shows only the result" />
        <div className="page"><div className="page-inner" data-testid="block-page">
          <div className="card card-pad"><div className="b">There is no stage {pad2(index + 1)} in this chain</div><p className="muted">The chain has {steps.length} stage{steps.length === 1 ? '' : 's'}.</p><button className="btn" onClick={() => navigate('analyse/chain')}>‹ full chain</button></div>
        </div></div>
      </>
    )
  }

  const row = rows[index]
  const upstream: Payload | null = index > 0 ? rows[index - 1]?.payload ?? null : null
  const sourceEnvelope: EnvelopeSeries | null = env?.envelope ?? null
  const upstreamSignal: EnvelopeSeries | null = (() => {
    for (let j = index - 1; j >= 0; j--) { const p = rows[j]?.payload; if (p?.type === 'signal') return (p as SignalPayload).envelope }
    return sourceEnvelope
  })()
  // the unit that signal is drawn in: a chain Signal's own, else the source window's (fixup-b)
  const upstreamUnit: DisplayUnit | undefined = (() => {
    for (let j = index - 1; j >= 0; j--) { const p = rows[j]?.payload; if (p?.type === 'signal') return (p as SignalPayload).unit }
    return env?.unit
  })()
  const perStep = val.v?.estimate?.per_step_s ?? null
  const staleFrom = job ? st.staleFrom : null      // nothing is stale relative to another source's job
  const rerunFrom = staleFrom !== null ? staleFrom : index
  const cost = perStep ? perStep.slice(rerunFrom).reduce((a: number, b) => a + (b ?? 0), 0) : null
  const costText = cost === null ? '—' : cost < 0.05 ? '<0.1 s' : cost < 10 ? `${cost.toFixed(1)} s` : fmtDuration(cost)
  const stale = staleFrom !== null && staleFrom <= index
  const stat = statTiles(row.payload)
  const name = stepName(step)
  const curStep = job?.current_step ?? 0
  const runningHere = running && row.status === 'running'
  const runNote = running ? (row.status === 'running' ? `${title} · computing · ${stepElapsed(index).toFixed(1)} s` : row.status === 'waiting' ? `waits for ${pad2(curStep + 1)} · ${pad2(index + 1)} runs after it` : row.status === 'cached' ? `${pad2(index + 1)} done · ${pad2(curStep + 1)} running` : `${pad2(curStep + 1)} running`) : ''

  return (
    <>
      <Header workspace="Analyse" page={`${pad2(index + 1)} ${title}`} subtitle="process detail · the chain row shows only the result" />
      <div className="page"><div className="page-inner" data-testid="block-page">
        <div className="an-toolbar">
          <button className="btn ghost" onClick={() => navigate('analyse/chain')} data-testid="back-to-chain">‹ full chain</button>
          <NameChip chain={chain} onRename={n => setChain(c => ({ ...c, name: n, saved: false }))} />
          <SourceChip source={source} />
          <SurrogateToggle />
          <EstimateChip text={running ? `${pad2(curStep + 1)} running · ${stepElapsed(curStep).toFixed(1)} s` : `≈ ${costText} · ${pad2(rerunFrom + 1)} → ${pad2(steps.length)}${stale ? ' recompute' : ''}${over.length ? ` · ${over.length} over the local ceiling` : ''}`} kind={running ? 'blue' : over.length ? 'red' : 'amber'} />
          <span className="spacer" />
          <button className="btn" onClick={saveAsTemplate} data-testid="save-template">▢ Save template</button>
          {running ? <button className="btn danger" onClick={cancel} data-testid="cancel-button" disabled={cancelling}
              title={cancelling ? 'cancel accepted · the run stops when the current stage ends, because cancel is checked between steps and never mid-step' : 'stop the run after the current stage'}>{cancelling ? '■ Cancelling…' : '■ Cancel'}</button>
            : <button className="btn primary" onClick={rerun} disabled={!canRun} data-testid="run-button" title={runTitle}>{job ? `↻ Re-run from ${pad2(rerunFrom + 1)}` : '▶ Run chain'}</button>}
        </div>
        {st.run.error && <RunErrorCard error={st.run.error} kind={st.run.errorKind} />}
        {refused && <div className="error-card" style={{ padding: '8px 12px' }} data-testid="run-refused-card"><h3>run refused by the bridge (422)</h3><div className="mono small">{refused}</div></div>}

        {/* ribbon */}
        <div className="card bp-ribbon" data-testid="block-ribbon">
          <span className="lbl">chain</span>
          <button className="bp-chip" style={{ flex: 'none', minWidth: 130 }} onClick={() => navigate('analyse/chain')}><div className="t"><span style={{ fontSize: 9 }}>●</span> Source <span className="badge cached">cached</span></div><div className="sg">— → Signal</div></button>
          {steps.map((s, i) => {
            const a = adapters.byName.get(stepName(s)); const r = rows[i]
            return (
              <span key={i} style={{ display: 'contents' }}>
                <span className="sep">›</span>
                <button className={`bp-chip${i === index ? ' on' : ''}`} onClick={() => navigate(`analyse/block/${i}`)} data-testid={`ribbon-${i}`}>
                  <div className="t"><span className="num">{pad2(i + 1)}</span> {a?.page_name ?? s.algorithm} <span className={`badge ${r.status === 'waiting' ? 'pending' : r.status}`} data-testid={`ribbon-badge-${i}`}>{r.status === 'running' ? `running · ${stepElapsed(i).toFixed(1)} s` : r.status}</span></div>
                  <div className="sg">{a?.signature ?? name}</div>
                </button>
              </span>
            )
          })}
          <span className="sep">›</span>
          <button className="bp-chip add" onClick={() => navigate(`analyse/chain?insert=${steps.length}`)} title="insert a stage at the end">+ stage</button>
        </div>

        <div className="bp-main">
          <div className="card card-pad bp-process" data-testid="block-process" data-running={running ? '1' : undefined}>
            {running && (
              <div className="bp-run-veil" data-testid="block-running">
                <div className="an-progress"><div className="bar" /><div className="txt">{runNote}{runningHere && job?.steps[index]?.cached_predicted ? ' · predicted cache hit' : ''}</div><div className="note">the result refreshes here when the run ends · cancel takes effect before the next step</div></div>
              </div>
            )}
            <div className="bp-card-title"><span className="mono muted">{pad2(index + 1)}</span><h3>{title}</h3><span className="sg">{ad?.signature ?? name}</span>
              <span className="sg" style={{ marginLeft: 'auto' }}>{source ? `${fmtHours(t0)}–${fmtHours(t1)} of ${source.channel_name}` : 'no source'}{row.status === 'cached' && row.timing !== null ? ` · ${fmtTiming(row.timing)} core` : ''}</span></div>
            {!source && <div className="muted mono small">no source — the process view needs a span. Use the example span from the chain page.</div>}
            {source && (
              <ErrorBoundary label={`block ${pad2(index + 1)} process`}>
                {/* the drawing standard (fixup-h): the view is the block's output type, the modifier its conversion —
                    read off the catalog card, never off the block's name */}
                <BlockProcess payload={row.payload && !isErrorPayload(row.payload) ? row.payload : null} step={step} card={ad} index={index}
                  ctx={{ x: makeX(t0, t1, 10), width: 10, height: 10, t0, t1, ghost: upstreamSignal, ghostUnit: upstreamUnit, interactive: true }}
                  upstream={upstream && !isErrorPayload(upstream) ? upstream : null} next={steps[index + 1] ?? null} nextCard={steps[index + 1] ? adapters.byName.get(stepName(steps[index + 1])) : undefined}
                  source={source} sourceUnit={env?.unit === null ? '' : 'mV'} stale={stale} setParam={setParam} jobId={job?.job_id ?? null}
                  dbRunId={job?.status === 'completed' ? job.db_run_id ?? null : null} chainName={chain.name} />
                {row.payload && isErrorPayload(row.payload) && renderByType(row.payload, { x: makeX(t0, t1, 10), width: 10, height: 10, t0, t1 })}
              </ErrorBoundary>
            )}
            {row.status === 'failed' && job?.error && <div className="error-card" style={{ marginTop: 10 }}><h3>{pad2(index + 1)} {title} failed</h3><div className="mono small">{job.error.message}</div></div>}
            {row.status === 'new' && !row.payload && <div className="muted mono small" style={{ marginTop: 8 }}>no result for this stage yet · the process strips fill in after a run</div>}
          </div>

          <div className="stack">
            <div className="card card-pad pp" data-testid="params-panel">
              <div className="pp-head"><h3>Parameters</h3><span className="muted mono small">{ad ? `${ad.params.length} declared` : ''}</span>
                {ad?.has_recommend && <span className="muted small" title="this adapter declares a recommend hook · the values it would recommend are not computed in this slice">recommend hook declared · not computed in this slice</span>}</div>
              {ad ? <ParamsPanel adapter={ad} params={step.params} onChange={setParam} disabled={running} /> : <div className="muted mono small">adapter {name} is not in the registry</div>}
              {stat.length > 0 && <div className="bp-tiles" data-testid="stat-tiles">{stat.map(t => <div className="bp-tile" key={t.k}><div className="k" title={t.k}>{t.k}</div><div className={`v${t.red ? ' red' : ''}`}>{t.v}</div></div>)}</div>}
              {row.payload && <div className="bp-info">{row.payload.summary}{stale ? ' · from the last run · stale' : ''}</div>}
            </div>
            <div className="card bp-null" data-testid="null-card">
              <div className="row"><span className="b">This parameter against the null</span><span className="muted mono small" style={{ marginLeft: 'auto' }}>ⓘ</span></div>
              <div className="e">null sweeps are out of slice scope — surrogate runs are not part of this prototype{ad?.input_kind === 'signal' ? '' : ' · this block declares no signal null'}</div>
            </div>
          </div>
        </div>

        <div className="card bp-foot" data-testid="block-footer">
          {running ? <span className="st"><span className="dot" style={{ background: 'var(--blue)' }} /> Running {pad2(curStep + 1)} of {pad2(job?.n_steps ?? steps.length)}</span> : staleFrom !== null ? <span className="st"><span className="dot" /> Unapplied changes</span> : <span className="st">No unapplied changes</span>}
          <span className="sub">{running ? 'stages land as they finish · this page updates in place' : staleFrom !== null ? `${pad2(staleFrom + 1)} and later are stale · re-running costs ≈ ${costText}` : job?.status === 'completed' ? `every stage is cached from job ${job.job_id} · db run #${job.db_run_id ?? '—'} · no null` : job?.status === 'failed' ? `run ${job.db_run_id ? `#${job.db_run_id}` : `job ${job.job_id}`} failed at ${pad2((job.error?.step ?? 0) + 1)}` : 'edit a parameter and the block goes stale'}</span>
          <div className="acts">
            <button className="btn" onClick={revert} disabled={!ad || running} data-testid="revert-defaults" title={running ? 'wait for the run' : 'reset every parameter of this block to the adapter defaults'}>↶ Revert to defaults</button>
            {running ? <button className="btn danger" onClick={cancel} disabled={cancelling}
                title={cancelling ? 'cancel accepted · the run stops when the current stage ends' : 'stop the run after the current stage'}>{cancelling ? '■ Cancelling…' : '■ Cancel'}</button>
              : <button className="btn primary" onClick={rerun} disabled={!canRun} title={runTitle} data-testid="footer-rerun">{job ? `↻ Re-run from ${pad2(rerunFrom + 1)}` : '▶ Run chain'}</button>}
          </div>
        </div>
      </div></div>
    </>
  )
}

/* ---------------- stat tiles from the payload ---------------- */
function statTiles(p: Payload | null): { k: string; v: string; red?: boolean }[] {
  if (!p || 'error' in p) return []
  switch (p.type) {
    case 'spanset': { const s = p as SpansetPayload; const mean = s.n ? s.start_s.reduce((a, x, i) => a + (s.end_s[i] - x), 0) / s.n : 0; return [{ k: 'spans', v: String(s.n) }, { k: 'mean duration', v: s.n ? fmtDuration(mean) : '—' }, { k: 'longest', v: s.n ? fmtDuration(Math.max(...s.start_s.map((x, i) => s.end_s[i] - x))) : '—' }, { k: 'capped', v: s.capped ? 'yes' : 'no', red: s.capped }] }
    case 'scores': { const s = p as ScoresPayload; return [{ k: 'values', v: s.n.toLocaleString() }, { k: 'NaN tail', v: String(s.nan_tail) }, { k: 'min', v: s.value_range ? fmtParam(s.value_range[0]) : '—' }, { k: 'max', v: s.value_range ? fmtParam(s.value_range[1]) : '—' }] }
    case 'signal': { const s = p as SignalPayload; const u = unitWords(s.unit); return [{ k: 'samples', v: s.n.toLocaleString() }, { k: `min ${u}`, v: s.y_range ? fmtParam(s.y_range[0]) : '—' }, { k: `max ${u}`, v: s.y_range ? fmtParam(s.y_range[1]) : '—' }, { k: 'fs', v: `${s.fs} Hz` }] }
    case 'encoding': { const e = p as EncodingSymbolicPayload; if (e.kind !== 'symbolic') return [{ k: 'kind', v: 'image' }]; return [{ k: 'symbols', v: String(e.n_symbols) }, { k: 'alphabet', v: String(e.alphabet_size) }, { k: 's per symbol', v: e.seconds_per_symbol != null ? fmtParam(e.seconds_per_symbol) : '—' }, { k: 'trimmed', v: e.n_trimmed != null ? String(e.n_trimmed) : '—' }] }
    case 'windowset': { const w = p as WindowsetPayload; return [{ k: 'windows', v: String(w.n_windows) }, { k: 'length', v: `${w.length_s} s` }, { k: 'features', v: w.features ? String(w.features.n_columns) : '—' }, { k: 'capped', v: w.capped ? 'yes' : 'no', red: w.capped }] }
    case 'grouping': { const g = p as GroupingPayload; return [{ k: 'clusters', v: String(g.k) }, { k: 'windows', v: String(g.n) }, { k: 'largest', v: String(Math.max(...g.clusters.map(c => c.count))) }, { k: 'linkage', v: g.linkage ?? '—' }] }
    case 'model': { const m = p as ModelPayload; const c = m.card; return [{ k: 'holdout acc.', v: typeof c.holdout_accuracy === 'number' ? (c.holdout_accuracy as number).toFixed(2) : '—' }, { k: 'classes', v: String(c.n_classes ?? '—') }, { k: 'windows', v: String(c.n_windows ?? '—') }, { k: 'features kept', v: `${String(c.n_features_kept ?? '—')} / ${String(c.n_features_in ?? '—')}` }] }
    default: return []
  }
}
