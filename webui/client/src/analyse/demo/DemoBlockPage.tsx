/* Analyse › block page in demo mode (frames chain-3, 4, 5, 6, 7, 7b, 8): the shared shell (§3, §6.8) — toolbar with
 * ‹ full chain, chain ribbon with every block clickable, the block's process and parameters together, and a footer
 * with unapplied changes. Parameter edits are a draft until "Apply & re-run"; the draft already marks this block and
 * everything downstream stale in the ribbon (frame chain-5). Block bodies live in ./blocks. */
import { useEffect, type ReactNode } from 'react'
import { Header } from '../../shell/Header'
import { useToast } from '../../shell/Toast'
import { navigate, setQuery, useApp } from '../../state'
import { blockByName, getBlockFixtures, getDemoChain, type DemoRowStatus } from '../../api/analyse'
import { useSourced } from '../../api/seam'
import { Badge, Button, EmptyState, Icon, setDemo, useDemoState, useQueryState, type BadgeStatus } from '../../kit'
import { applyState, clearDrafts, deriveRows, draftsKey, pad2, useDemoChain } from './chainState'
import { DemoNameChip, DemoSourceChip, EstimateText, NullControl, SaveTemplateModal } from './parts'
import { BaselineBlock } from './blocks/BaselineBlock'
import { NoiseFloorBlock } from './blocks/NoiseFloorBlock'
import { EncodingBlock } from './blocks/EncodingBlock'
import { DetectionBlock } from './blocks/DetectionBlock'
import { MatrixProfileBlock } from './blocks/MatrixProfileBlock'
import { ThresholdBlock } from './blocks/ThresholdBlock'
import { ModelStageBlock } from './blocks/ModelStageBlock'
import { GenericBlock } from './blocks/GenericBlock'
import type { BlockProps } from './blocks/common'

const META: Record<string, { subtitle: string; recommended?: Record<string, unknown>; body: (p: BlockProps) => ReactNode }> = {
  'demo.baseline_removal': { subtitle: 'transform block · input vs output, and what it does downstream', recommended: { method: 'rolling median', window_s: 7, edges: 'reflect' }, body: p => <BaselineBlock {...p} /> },
  'demo.noise_floor': { subtitle: 'estimator block · value, uncertainty, stationarity', recommended: { estimator: 'MAD × 1.4826', scope: 'whole span', exclude: 'detected spans · iterate 2×', floor_from: 'this span' }, body: p => <NoiseFloorBlock {...p} /> },
  'demo.symbolic_encoding': { subtitle: 'process detail · the chain row shows only the encoding result', recommended: { alphabet: 3, split: 'd/D · U/u', segment_s: 0.2, same_fraction: 0.55, noise_k: 8, edges: 'reflect' }, body: p => <EncodingBlock {...p} /> },
  'demo.drop_detection': { subtitle: 'detections in context · what dedupe removed · hand-offs', recommended: { min_depth_mv: 0.1, min_duration_s: 0.6, merge_window_s: 2.4, trough_tol_sigma: 0.5, dedupe: 'keep best-framed', onset: 'walk back from steepest' }, body: p => <DetectionBlock {...p} /> },
  'demo.matrix_profile': { subtitle: 'judge the profile against its surrogate · then threshold', recommended: { m_s: 540, exclusion: 'm / 2', algorithm: 'STUMP · exact', normalise: 'z-norm' }, body: p => <MatrixProfileBlock {...p} /> },
  'demo.threshold': { subtitle: 'set the cut against the surrogate', recommended: { cut_sigma: 2.5, min_duration_s: 60, merge_gap_s: 30, keep: 'above the cut' }, body: p => <ThresholdBlock {...p} /> },
  'demo.model_stage': { subtitle: 'a registered model scores each window', recommended: { model: 'cnn_windows_v2 · manual · v2', batch: 64, pass_class: 'spike-train' }, body: p => <ModelStageBlock {...p} /> },
}
const fmtV = (v: unknown) => (typeof v === 'number' ? `${+v.toFixed(3)}` : String(v))
const UNIT: Record<string, string> = { window_s: ' s', segment_s: ' s', min_duration_s: ' s', merge_window_s: ' s', min_depth_mv: ' mV', trough_tol_sigma: ' σ', noise_k: ' σ', cut_sigma: ' σ', m_s: ' s', merge_gap_s: ' s' }

export function DemoBlockPage({ template, index }: { template: string; index: number }) {
  const { route } = useApp()
  const toast = useToast()
  const bundleQ = useSourced(() => getDemoChain(template), [template])
  const fxQ = useSourced(getBlockFixtures, [])
  const bundle = bundleQ.data
  const { st, sim, v, busy, actions } = useDemoChain(bundle, template)
  const step = st?.steps[index]
  const [drafts, setDrafts] = useDemoState<Record<string, Record<string, unknown>>>(draftsKey(template), () => ({}))
  const draftState = step ? drafts[step.uid] ?? null : null
  const setDraftState = (next: Record<string, unknown> | null | ((prev: Record<string, unknown> | null) => Record<string, unknown> | null)) => {
    if (!step) return
    setDrafts(all => { const cur = all[step.uid] ?? null; const v = typeof next === 'function' ? next(cur) : next; const out = { ...all }; if (v) out[step.uid] = v; else delete out[step.uid]; return out })
  }
  const [modal, setModal] = useQueryState('modal', '')
  const stateParam = route.query.state
  const withParam = route.query.with

  /* deep links: ?state=default|running|stale|failed|unapplied and ?with=threshold (insert the block this page is about) */
  useEffect(() => {
    if (!bundle || (!stateParam && !withParam)) return
    const base = stateParam ? applyState(bundle.scenario, stateParam === 'unapplied' ? 'default' : stateParam) : null
    let next = base?.state ?? st
    if (!next) return
    if (withParam && !next.steps[index]) {
      const b = `demo.${withParam}`
      if (blockByName(b)) { const uid = `w-${withParam}`; next = { ...next, steps: [...next.steps, { uid, block: b, params: { ...(blockByName(b)?.params ?? {}) } }], status: { ...next.status, [uid]: 'stale' } } }
    }
    if (stateParam) clearDrafts(template)
    if (stateParam === 'unapplied' && next.steps[index]?.block === 'demo.baseline_removal') {
      const s0 = next.steps[index]
      next = { ...next, steps: next.steps.map((s, k) => k === index ? { ...s, params: { ...s.params, window_s: 5 } } : s), status: Object.fromEntries(next.steps.map((s, k) => [s.uid, k >= index ? 'stale' : next!.status[s.uid]])) as Record<string, DemoRowStatus> }
      actions.replaceAll(next)
      window.setTimeout(() => setDraftStateFor(template, s0.uid, { window_s: 7 }), 0)
    } else actions.replaceAll(next)
    if (stateParam === 'running') actions.forceRunning(index)
    setQuery({ state: null, with: null, template }, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bundle, stateParam, withParam])

  const header = (page: string, subtitle: string) => <Header workspace="Analyse" page={page} subtitle={subtitle} search="Search spans, runs, families" demo />
  if (bundleQ.error || fxQ.error) return <>{header('Block', 'demo block')}<div className="page"><div className="page-inner"><div className="error-card"><h3>demo block failed to load</h3><pre>{(bundleQ.error ?? fxQ.error)!.message}</pre></div></div></div></>
  if (!bundle || !st || !fxQ.data) return <>{header('Block', 'loading…')}<div className="page"><div className="page-inner" data-testid="block-page"><div className="skeleton" style={{ height: 420 }} /></div></div></>

  const sc = bundle.scenario
  const rows = deriveRows(st, bundle, sim, v)
  const n = st.steps.length
  if (!step) {
    const fit = n > 0 ? 'threshold' : null
    return (
      <>
        {header(`${pad2(index + 1)} —`, 'there is no such stage in this chain')}
        <div className="page"><div className="page-inner" data-testid="block-page">
          <EmptyState icon="layers" title={`There is no stage ${pad2(index + 1)} in ${st.name}`} caption={`the chain has ${n} stage${n === 1 ? '' : 's'}`} bordered testid="block-missing"
            action={<div className="row" style={{ gap: 8 }}><Button icon="arrow-left" onClick={() => navigate(`analyse/chain?template=${template}`)}>Full chain</Button>{fit && index === n && <Button variant="primary" icon="plus" onClick={() => { actions.insert(n, 'demo.threshold'); toast.push({ text: `inserted Threshold to spans as ${pad2(n + 1)}` }) }} testid="block-insert-here">Insert Threshold to spans here</Button>}</div>} />
        </div></div>
      </>
    )
  }

  const b = blockByName(step.block)
  const meta = META[step.block] ?? { subtitle: 'process detail · the chain row shows only the result', body: (p: BlockProps) => <GenericBlock {...p} /> }
  const draft = { ...step.params, ...(draftState ?? {}) }
  const changes = Object.keys(draft).filter(k => fmtV(draft[k]) !== fmtV(step.params[k]))
  const dirty = changes.length > 0
  const setDraft = (name: string, value: unknown) => setDraftState(prev => ({ ...(prev ?? {}), [name]: value }))
  const clearDraft = () => setDraftState(null)
  const row = rows[index]
  const runningHere = busy && st.run?.uids.includes(step.uid)
  const stale = dirty || row.stored === 'stale' || row.stored === 'new'
  const firstNotCached = rows.findIndex(r => r.stored !== 'cached')
  const cost = st.steps.slice(index).reduce((a, s) => a + (blockByName(s.block)?.cost_s ?? 0.1), 0) * (sc.null.kind === 'toggle' && st.surrogate ? 2 : 1)
  const costText = cost < 60 ? `≈ ${cost < 0.1 ? '<0.1' : cost.toFixed(1)} s` : `≈ ${Math.round(cost / 60)} min`
  const changeText = changes.map(k => `${k.replace(/_(s|mv|sigma|k)$/, '').replace(/_/g, ' ')} ${fmtV(step.params[k])} → ${fmtV(draft[k])}${UNIT[k] ?? ''}`).join(' · ')
  const rerunFrom = firstNotCached >= 0 && firstNotCached < index ? firstNotCached : index

  const apply = () => { actions.setParams(step.uid, draft); clearDraft(); actions.run(index); toast.push({ text: `${changeText} applied · re-running ${pad2(index + 1)} → ${pad2(n)}` }) }
  const rec = meta.recommended
  const atRec = !rec || Object.entries(rec).every(([k, val]) => fmtV(draft[k]) === fmtV(val))
  const revert = () => { if (rec) setDraftState(Object.fromEntries(Object.entries(rec).filter(([k, val]) => fmtV(step.params[k]) !== fmtV(val)))); toast.push({ text: `${pad2(index + 1)} ${b?.page_name} · parameters set to the recommended values (not applied yet)` }) }

  let primary: ReactNode
  if (busy) primary = <Button variant="danger" icon="stop" onClick={actions.cancel} testid="cancel-button">Cancel</Button>
  else if (dirty) primary = <Button variant="primary" icon="refresh" onClick={apply} testid="run-button">Apply & re-run from {pad2(index + 1)}</Button>
  else if (row.stored === 'new' && firstNotCached >= 0) primary = <Button variant="primary" icon="play" onClick={() => actions.run(Math.min(rerunFrom, index))} testid="run-button">Run {pad2(index + 1)}</Button>
  else if (firstNotCached >= 0 && firstNotCached <= index) primary = <Button variant="primary" icon="refresh" onClick={() => actions.run(firstNotCached)} testid="run-button">Re-run from {pad2(firstNotCached + 1)}</Button>
  else primary = <Button icon="refresh" onClick={() => actions.run(index)} testid="run-button">Re-run {pad2(index + 1)}</Button>

  const est = busy ? { text: `${pad2((rows.find(r => r.status === 'running')?.index ?? index) + 1)} running · results land here`, tone: 'blue' as const }
    : dirty ? { text: `${changeText} · re-runs ${pad2(index + 1)} → ${pad2(n)} ${costText}`, tone: 'amber' as const }
    : row.stored === 'failed' ? { text: `failed here · ${st.failure?.run ?? ''}`, tone: 'red' as const }
    : stale ? { text: `retune ${costText} · ${pad2(rerunFrom + 1)} → ${pad2(n)} recompute`, tone: 'amber' as const }
    : { text: `cached · last run ${st.lastRun === '#128' ? '2 Sept' : st.lastRun}`, tone: 'grey' as const }

  const ribbonStatus = (i: number): BadgeStatus => {
    const r = rows[i]
    if (dirty && i >= index) return 'stale'
    const s = r.status
    return s === 'waiting' ? 'new' : s === 'queued' ? 'queued' : s === 'invalid' ? 'invalid' : (s as BadgeStatus)
  }
  const props: BlockProps = { st, bundle, fx: fxQ.data, rows, index, step, draft, setDraft, actions, running: !!runningHere, stale }

  return (
    <>
      {header(`${pad2(index + 1)} ${b?.page_name ?? step.block}`, meta.subtitle)}
      <div className="page"><div className="page-inner" data-testid="block-page" data-mode="block-demo" data-block={step.block}>
        <div className="an-toolbar" data-testid="block-toolbar">
          <Button variant="link" icon="chevron-left" onClick={() => navigate(`analyse/chain?template=${template}`)} testid="back-to-chain">full chain</Button>
          <DemoNameChip st={st} onRename={actions.rename} />
          <DemoSourceChip source={bundle.source} />
          <span className="spacer" />
          <NullControl sc={sc} st={st} onToggle={actions.toggleSurrogate} />
          <EstimateText text={est.text} tone={est.tone} />
          <Button icon="save" onClick={() => setModal('save')} testid="save-template">Save template</Button>
          {primary}
        </div>

        <div className="card bp-ribbon" data-testid="block-ribbon">
          <span className="lbl">chain</span>
          <button className="bp-chip" onClick={() => navigate(`analyse/chain?template=${template}`)} data-testid="ribbon-source"><div className="t"><Icon name="circle-dashed" size={9} /> Source <Badge status="cached" /></div><div className="sg">— → Signal</div></button>
          {st.steps.map((s, i) => {
            const bb = blockByName(s.block)
            return (
              <span key={s.uid} style={{ display: 'contents' }}>
                <span className="sep"><Icon name="chevron-right" size={12} /></span>
                <button className={`bp-chip${i === index ? ' on' : ''}`} onClick={() => navigate(`analyse/block/${i}?template=${template}`)} data-testid={`ribbon-${i}`} aria-current={i === index ? 'step' : undefined}>
                  <div className="t"><span className="num">{pad2(i + 1)}</span> {bb?.page_name ?? s.block} <span data-testid={`ribbon-badge-${i}`}><Badge status={ribbonStatus(i)} /></span></div>
                  <div className="sg">{bb?.signature}</div>
                </button>
              </span>
            )
          })}
          <Button size="sm" icon="plus" onClick={() => navigate(`analyse/chain?template=${template}&modal=insert&at=${n}`)} testid="ribbon-add">stage</Button>
        </div>

        <div className="bx-body" data-running={runningHere ? '1' : undefined}>
          {meta.body(props)}
          {runningHere && (
            <div className="bx-running" data-testid="block-running">
              <div className="an-progress">
                <div className="bar determinate"><i style={{ width: `${Math.round(sim.fraction * 100)}%` }} /></div>
                <div className="txt">running {pad2(index + 1)} → {pad2(n)} · {Math.round(sim.fraction * 100)} % · results land here when the run ends</div>
                <Button size="sm" variant="danger" icon="stop" onClick={actions.cancel}>Cancel</Button>
              </div>
            </div>
          )}
        </div>

        <div className="card bp-foot" data-testid="block-footer">
          {dirty ? <span className="st"><span className="dot" /> {changes.length} unapplied change{changes.length === 1 ? '' : 's'}</span> : <span className="st"><span className="dot" style={{ background: stale ? 'var(--amber)' : 'var(--green)' }} /> No unapplied changes</span>}
          <span className="sub" data-testid="block-footer-sub">{dirty ? `${changeText} · re-runs ${pad2(index + 1)} → ${pad2(n)} ${costText}${(b?.cost_s ?? 1) < 1 ? ` · ${pad2(index + 1)} is cheap, so this would run automatically` : ''}` : row.stored === 'failed' ? `${pad2(index + 1)} failed in ${st.failure?.run ?? 'the last run'} · fix a parameter and re-run` : stale ? `${pad2(Math.max(index, rerunFrom) + 1)} and later are stale from an earlier edit · re-running costs ${costText}` : `${pad2(index + 1)} is cached · changing a parameter here makes ${pad2(index + 1)}${index + 1 < n ? ` → ${pad2(n)}` : ''} stale`}</span>
          <div className="acts">
            <Button icon="undo" onClick={revert} disabled={atRec || busy} disabledReason={busy ? 'wait for the run' : 'already at the recommended values'} testid="revert-defaults">Revert to recommended</Button>
            {dirty && <Button variant="ghost" onClick={clearDraft} testid="discard-draft">Discard</Button>}
            {primary}
          </div>
        </div>
      </div></div>
      <SaveTemplateModal open={modal === 'save'} onClose={() => setModal(null)} st={st} kind={v.terminal === 'spanset' ? 'detection' : 'chain'} onSave={(name, ver) => { actions.save(name, ver); toast.push({ text: `${name} ${ver} saved · in memory for this session (demo)` }) }} />
    </>
  )
}

function setDraftStateFor(template: string, uid: string, draft: Record<string, unknown>) {
  setDemo<Record<string, Record<string, unknown>>>(draftsKey(template), all => ({ ...(all ?? {}), [uid]: draft }))
}
