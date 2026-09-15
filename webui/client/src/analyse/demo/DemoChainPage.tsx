/* Analyse › Chain in demo mode (frames chain-1, 1b, 1c, 1d, 1e, 1f, 1g, 1h, 1i, 2). The same vertical rows (P1) and
 * the same Renderer seam as the live chain, over `demo.*` blocks: validated locally, run on a simulated timer, drawn
 * from fixture payloads. Every frame is reachable by clicking and by `?template=…&state=…` (see inventory/chain.md). */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { CrosshairProvider } from '../../charts/primitives'
import { Header } from '../../shell/Header'
import { useToast } from '../../shell/Toast'
import { navigate, setQuery, useApp } from '../../state'
import { getDemoChain, blockByName, DEMO_KIND_LABEL, demoCompatibleAt, type DemoStep, type DemoRowStatus } from '../../api/analyse'
import { useSourced } from '../../api/seam'
import { Button, Chip, CodeBlock, Dropdown, Icon, InfoTip, useNotWired, useQueryState, setDemo } from '../../kit'
import { ChainRow } from '../ChainRow'
import { renderByType } from '../Renderer'
import { applyState, clearDrafts, deriveRows, fromScenario, pad2, useDemoChain, type DemoChainState, type RowView } from './chainState'
import { validateDemoChain } from '../../api/analyse'
import { DemoAxis, DemoNameChip, DemoSourceChip, EstimateText, FooterCard, NullControl, RunLogModal, SaveTemplateModal, writeHpcJob } from './parts'
import { DemoInsertModal } from './DemoInsertModal'
import { ImportTemplateModal } from './ImportTemplateModal'
import { DemoHistoryPopover } from './DemoHistoryPopover'
import { UploadArtifactModal } from './UploadArtifactModal'

const TERMINAL: Record<string, { text: string; tone: 'green' | 'blue' | 'grey' }> = {
  spanset: { text: 'terminal SpanSet → detection template', tone: 'green' },
  scores: { text: 'terminal Scores', tone: 'blue' },
  model: { text: 'terminal Model → training template', tone: 'green' },
  features: { text: 'terminal Features → interrogation', tone: 'green' },
}

export function DemoChainPage({ template }: { template: string }) {
  const { route } = useApp()
  const toast = useToast()
  const notWired = useNotWired()
  const bundleQ = useSourced(() => getDemoChain(template), [template])
  const bundle = bundleQ.data
  const { st, sim, v, busy, actions } = useDemoChain(bundle, template)
  const [modal, setModal] = useQueryState('modal', '')
  const [atParam] = useQueryState('at', '')
  const [popover, setPopover] = useQueryState('popover', '')
  const historyRef = useRef<HTMLButtonElement>(null)
  const undoRef = useRef<{ step: DemoStep; index: number; status: DemoRowStatus } | null>(null)
  const stateParam = route.query.state

  /* deep link: apply ?state= onto the scenario, then drop it from the URL (the store now holds it) */
  useEffect(() => {
    if (!bundle || !stateParam) return
    const r = applyState(bundle.scenario, stateParam)
    clearDrafts(template)
    actions.replaceAll(r.state)
    if (r.forceRunning) actions.forceRunning(r.forceRunning.from)
    if (r.deleted) { undoRef.current = { step: r.deleted.step, index: r.deleted.index, status: 'stale' }; pushUndoToast(r.deleted.index, r.deleted.step) }
    setQuery({ state: null, template }, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bundle, stateParam])

  /* Ctrl/Cmd+Z restores the last deleted stage (frame chain-1e) */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'z') return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      const u = undoRef.current; if (!u) return
      e.preventDefault(); undo()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  })

  if (bundleQ.error) return <><Header workspace="Analyse" page="Chain" subtitle="demo chain" demo /><div className="page"><div className="page-inner"><div className="error-card" data-testid="demo-chain-error"><h3>demo chain failed to load</h3><pre>{bundleQ.error.message}</pre></div></div></div></>
  if (!bundle || !st) return <><Header workspace="Analyse" page="Chain" subtitle="loading the demo chain…" demo /><div className="page"><div className="page-inner" data-testid="chain-page"><div className="skeleton" style={{ height: 400 }} /></div></div></>

  const sc = bundle.scenario; const src = bundle.source
  const t0 = src.t0_s; const t1 = src.t1_s
  const rows = deriveRows(st, bundle, sim, v)
  const n = st.steps.length
  const invalid = v.invalid
  const failed = !busy && st.failure ? rows.find(r => r.step.uid === st.failure!.uid) ?? null : null
  const clusterRow = rows.find(r => r.stored === 'on cluster') ?? null
  const pausedRow = rows.find(r => r.stored === 'paused') ?? null
  const firstStale = rows.findIndex(r => r.stored !== 'cached' && r.stored !== 'on cluster' && r.stored !== 'paused' && !r.step.bypass)
  const runningRow = rows.find(r => r.status === 'running' || r.status === 'queued') ?? null
  const terminal = TERMINAL[v.terminal] ?? { text: `terminal ${DEMO_KIND_LABEL[v.terminal]} — add a stage to reach a template type`, tone: 'grey' as const }
  const allCached = n > 0 && firstStale < 0 && !clusterRow && !pausedRow
  const costFrom = (from: number) => st.steps.slice(from).reduce((a, s) => a + (s.bypass ? 0 : blockByName(s.block)?.cost_s ?? 0.1), 0) * (st.surrogate || sc.null.kind === 'chip' ? 2 : 1)
  const fmtCost = (s: number) => s < 60 ? `≈ ${s < 0.1 ? '<0.1' : s.toFixed(1)} s` : s < 3600 ? `≈ ${Math.round(s / 60)} min` : `≈ ${(s / 3600).toFixed(1)} h`
  const surrogateOff = sc.null.kind === 'toggle' && !st.surrogate

  /* ---- toolbar derivations ---- */
  let est: { text: string; tone: 'amber' | 'blue' | 'red' | 'green' | 'grey' }
  if (busy && runningRow) {
    const left = runningRow.progress ? runningRow.progress.left : null
    est = { text: sim.status === 'queued' ? `${pad2(runningRow.index + 1)} queued` : `${pad2(runningRow.index + 1)} running · ≈ ${left?.toFixed(1) ?? '—'} s left`, tone: 'blue' }
  } else if (!n) est = { text: 'no blocks yet', tone: 'grey' }
  else if (invalid) est = { text: `${invalid} invalid junction${invalid > 1 ? 's' : ''}`, tone: 'red' }
  else if (failed) est = { text: `failed at ${pad2(failed.index + 1)} · ${failed.index > 0 ? `01–${pad2(failed.index)} cached` : 'nothing cached'}`, tone: 'red' }
  else if (clusterRow) est = { text: `${sc.hpc?.estimate ?? '≈ 6.4 h'} · over ceiling`, tone: 'amber' }
  else if (pausedRow) est = { text: `paused at ${pad2(pausedRow.index + 1)} · result in place`, tone: 'amber' }
  else if (allCached) est = { text: '≈ <0.1 s · all cached', tone: 'green' }
  else est = { text: `${fmtCost(costFrom(firstStale))} · ${pad2(firstStale + 1)} → ${pad2(n)}${surrogateOff ? ' · no surrogate' : ''}`, tone: 'amber' }

  const runReason = !n ? 'add a block first' : invalid ? 'fix the red junction first' : undefined
  const run = (from: number) => { actions.run(from) }
  const insertAt = (p: number) => { setModal('insert'); setQuery({ modal: 'insert', at: String(p) }, true) }
  const openBlock = (i: number) => navigate(`analyse/block/${i}?template=${template}`)

  function pushUndoToast(index: number, step: DemoStep) {
    const nm = blockByName(step.block)?.page_name ?? step.block
    toast.push({ text: `${pad2(index + 1)} ${nm} deleted`, action: { label: 'Undo', hint: 'Ctrl Z', onClick: () => undo() }, ttlMs: 10000 })
  }
  function undo() {
    const u = undoRef.current; if (!u) return
    actions.restore(u.step, u.index, u.status); undoRef.current = null
    toast.push({ text: `${pad2(u.index + 1)} ${blockByName(u.step.block)?.page_name ?? u.step.block} restored` })
  }
  const remove = (i: number) => {
    const step = st.steps[i]
    undoRef.current = { step, index: i, status: st.status[step.uid] ?? 'new' }
    actions.remove(i); pushUndoToast(i, step)
  }

  let primary: ReactNode
  if (busy) primary = <Button variant="danger" icon="stop" onClick={() => { actions.cancel(); toast.push({ text: 'cancel requested · takes effect before the next stage' }) }} testid="cancel-button">Cancel</Button>
  else if (clusterRow) primary = <Button variant="primary" icon="server" onClick={() => createSlurm(clusterRow)} testid="run-button">Export HPC job</Button>
  else if (pausedRow) primary = <Button variant="primary" icon="play" onClick={() => continueFrom(pausedRow)} testid="run-button">Continue from {pad2(pausedRow.index + 2)}</Button>
  else if (failed) primary = <Button variant="primary" icon="refresh" disabled={!!runReason} disabledReason={runReason} onClick={() => run(failed.index)} testid="run-button">Retry from {pad2(failed.index + 1)}</Button>
  else if (!allCached && firstStale > 0 && !invalid) primary = <Button variant="primary" icon="refresh" disabled={!!runReason} disabledReason={runReason} onClick={() => run(firstStale)} testid="run-button">Re-run from {pad2(firstStale + 1)}</Button>
  else primary = <Button variant="primary" icon="play" disabled={!!runReason} disabledReason={runReason} onClick={() => run(allCached ? 0 : Math.max(0, firstStale))} testid="run-button">Run chain</Button>

  function createSlurm(row: RowView) {
    if (st!.hpcJob) { navigate('jobs'); return }
    const job = writeHpcJob(template, pad2(row.index + 1))
    actions.patch({ hpcJob: job.id })
    toast.push({ text: `SLURM script created · ${job.id} added to Jobs (queue)`, action: { label: 'Open in Jobs', onClick: () => navigate('jobs') } })
    document.querySelector('[data-testid="generated-job"]')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  function continueFrom(row: RowView) {
    actions.patch({ status: { ...st!.status, [row.step.uid]: 'cached' }, note: `${sc.paused?.runId ?? 'run'} · continued` })
    window.setTimeout(() => actions.run(row.index + 1), 0)
  }

  /* ---- rows ---- */
  const rowNode = (r: RowView): ReactNode => {
    const b = blockByName(r.step.block)
    const title = b?.page_name ?? r.step.block
    const i = r.index
    let overlay: ReactNode = null
    let replace: ReactNode = null
    let plot = (x: Parameters<typeof renderByType>[1]['x'], w: number, h: number): ReactNode => r.payload ? renderByType(r.payload, { x, width: w, height: h, t0, t1 }) : null
    let badge: string = r.status
    let rowClass = ''
    switch (r.status) {
      case 'running':
        overlay = <><div className="an-plot-veil" style={{ background: 'rgba(255,255,255,0.82)' }} /><div className="an-progress" data-testid={`progress-${i + 1}`}><div className="bar determinate"><i style={{ width: `${r.progress?.pct ?? 0}%` }} /></div><div className="txt">{progressVerb(r.step.block)} · {r.progress?.pct ?? 0} % · {r.progress?.left.toFixed(1)} s left</div></div></>
        break
      case 'queued':
        overlay = <><div className="an-plot-veil" /><div className="an-plot-empty">queued · starts in a moment</div></>; badge = 'running'
        break
      case 'waiting':
        plot = (x, w, h) => r.payload ? <div style={{ opacity: 0.3 }}>{renderByType(r.payload, { x, width: w, height: h, t0, t1 })}</div> : null
        overlay = <><div className="an-plot-veil" style={{ background: 'rgba(255,255,255,0.7)' }} /><div className="an-plot-empty" data-testid={`waiting-${i + 1}`}><Icon name="hourglass" size={12} />&nbsp;waits for {pad2(r.waitsFor ?? i)} · last result hidden</div></>
        badge = 'new'
        break
      case 'stale':
        if (r.payload) overlay = <><div className="an-plot-veil" style={{ background: 'rgba(255,255,255,0.35)' }} /><span className="an-stale-pill" data-testid={`stale-pill-${i + 1}`}><Icon name="clock" size={11} /> last run shown · stale</span></>
        else { plot = () => null; overlay = <div className="an-plot-empty">no result yet · run the chain</div> }
        break
      case 'new':
        plot = () => null
        overlay = <div className="an-plot-empty">{r.step.bypass ? 'bypassed · passes its input through' : clusterRow && i > clusterRow.index ? <><Icon name="hourglass" size={12} />&nbsp;waits for {pad2(clusterRow.index + 1)}'s profile · resumes automatically after import</> : pausedRow && i > pausedRow.index ? <><Icon name="hourglass" size={12} />&nbsp;{i === pausedRow.index + 1 ? `waits for ${pad2(pausedRow.index + 1)} · ${sc.paused?.continueNote ?? 'continue to run'}` : `waits for ${pad2(i)}`}</> : 'no result yet · run the chain'}</div>
        break
      case 'invalid':
        rowClass = 'invalid'
        break
      case 'failed': {
        rowClass = 'failed'
        const f = st.failure
        replace = (
          <div className="an-fail" data-testid="error-card">
            <div style={{ color: 'var(--red)' }}><Icon name="alert-circle" size={20} /></div>
            <div style={{ minWidth: 0 }}>
              <div className="t">{pad2(i + 1)} {title} failed after {f?.after ?? '—'}</div>
              <div className="m">{f?.message ?? 'failed (simulated)'}</div>
              <div className="s">adapter {r.step.block.replace('demo.', '')} v3 · recipe a7f39c · traceback in log</div>
            </div>
            <div className="acts">
              <Button icon="file" onClick={() => setModal('log')} testid="view-log">View log</Button>
              <Button icon="sliders" onClick={() => openBlock(i)} testid="open-settings">Open settings</Button>
              <Button variant="primary" icon="refresh" onClick={() => run(i)} disabled={!!runReason} disabledReason={runReason} testid="retry-step">Retry {pad2(i + 1)}</Button>
            </div>
          </div>
        )
        break
      }
      case 'on cluster':
        rowClass = 'invalid'
        replace = (
          <div className="an-hpc cluster" data-testid="hpc-card">
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <Icon name="server" size={20} />
              <div>
                <div className="t">{st.hpcJob ? `SLURM script created · ${st.hpcJob} waits in Jobs` : `Not computed here · ${sc.hpc?.estimate ?? '≈ 6.4 h'} on this machine`}</div>
                <div className="s">{st.hpcJob ? 'submit it on the cluster · the profile re-enters through Jobs › Manifest inbox (P24)' : sc.hpc?.detail}</div>
              </div>
            </div>
            <div className="row" style={{ gap: 8 }}>
              <Button icon="upload" onClick={() => setModal('upload')} testid="upload-artifact">Upload computed profile</Button>
              <Button variant="primary" icon={st.hpcJob ? 'external' : 'file'} onClick={() => createSlurm(r)} testid="create-slurm">{st.hpcJob ? 'Open in Jobs' : 'Create SLURM script'}</Button>
            </div>
          </div>
        )
        badge = 'on cluster'
        break
      case 'paused':
        replace = (
          <div className="an-hpc paused" data-testid="paused-card">
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <Icon name="pause" size={20} />
              <div><div className="t">{sc.paused?.found ?? 'Result found in place'}</div><div className="s">{sc.paused?.checks}</div></div>
            </div>
            <div className="row" style={{ gap: 8 }}>
              <Button icon="external" onClick={() => navigate(`jobs/run/${sc.paused?.runId ?? 'a-0098'}`)} testid="open-in-jobs">Open in Jobs</Button>
              <Button variant="primary" icon="play" onClick={() => continueFrom(r)} testid="continue-button">Continue from {pad2(i + 2)}</Button>
            </div>
          </div>
        )
        break
    }
    if (r.status === 'cached' && r.stored !== 'cached' && busy) badge = 'cached'
    return (
      <ChainRow key={r.step.uid} testIndex={i + 1} rowClass={rowClass} num={pad2(i + 1)} title={title} badge={badge as never} signature={b?.signature ?? '?'} caption={r.step.bypass ? `bypassed · ${r.caption}` : r.caption}
        t0={t0} t1={t1} plot={plot} overlay={overlay} replace={replace} resetKey={`${r.step.uid}-${r.status}`} bypassed={r.step.bypass}
        rowTone={r.status === 'on cluster' ? 'cluster' : r.status === 'paused' ? 'paused' : undefined} plotHeight={r.payload?.type === 'demo.scores' && r.status !== 'paused' ? 150 : undefined}
        onSettings={() => openBlock(i)} onDelete={busy ? undefined : () => remove(i)} deleteReason="wait for the run to finish"
        onMoveUp={busy || i === 0 ? undefined : () => { actions.moveUp(i); toast.push({ text: `${title} moved to ${pad2(i)} · validation re-ran` }) }}
        onBypass={busy ? undefined : () => actions.bypass(i)} onDuplicate={busy ? undefined : () => actions.duplicate(i)} />
    )
  }

  const junctionFor = (i: number): ReactNode => {
    const j = v.junctions[i]
    if (!j || j.ok) return null
    const here = st.steps[i]; const prev = st.steps[i - 1]
    const hereName = `${pad2(i + 1)} ${blockByName(here.block)?.page_name ?? here.block}`
    const prevName = prev ? `${pad2(i)} ${blockByName(prev.block)?.page_name ?? prev.block}${prev.bypass ? ' (bypassed)' : ''}` : 'Source'
    const fit = demoCompatibleAt(st.steps.slice(0, i), i).fits.find(f => f.ok && f.block.output === j.needs)
    return (
      <div className="an-junction" key={`j-${here.uid}`}>
        <div className="an-junction-pill" data-testid="junction-error">
          <Icon name="x-circle" size={13} /><b>{hereName} needs {DEMO_KIND_LABEL[j.needs]}</b><span>· {prevName} emits {DEMO_KIND_LABEL[j.here]}</span>
          {fit && <button className="btn sm" onClick={() => { actions.insert(i, fit.block.name); undoRef.current = null }} data-testid="junction-insert"><Icon name="plus" size={11} /> Insert {fit.block.page_name} here</button>}
          <button className="btn sm" onClick={() => insertAt(i)} data-testid="junction-browse"><Icon name="list" size={11} /> Show blocks that fit</button>
        </div>
      </div>
    )
  }
  const insertPill = (p: number, end = false) => (
    <div className="an-insert-line" key={`ins-${p}`}>
      <button className="an-insert" onClick={() => insertAt(p)} data-testid={`insert-${p}`} disabled={busy} title={busy ? 'wait for the run to finish' : 'insert a stage here'}>+ insert{end ? ' · end of chain' : ''}</button>
    </div>
  )

  /* end-of-chain suggestion (frame 1h): what fits after the terminal */
  const endFits = n > 0 && !invalid && v.terminal === 'scores' ? demoCompatibleAt(st.steps, n).fits.filter(f => f.ok) : []
  const endKinds = Array.from(new Set(endFits.map(f => DEMO_KIND_LABEL[f.block.output])))

  /* ---- footer ---- */
  let headline: string, sub: string
  if (busy && runningRow) { headline = `Running ${pad2(runningRow.index + 1)} of ${pad2(n)}`; sub = `stages land as they finish${st.surrogate && sc.null.kind === 'toggle' ? ` · surrogate run #${st.runNo + 1} queued after` : ''} · cancel is checked between stages` }
  else if (!n) { headline = 'No blocks yet'; sub = 'add the first block or import a template' }
  else if (invalid) { headline = 'Chain is invalid'; sub = 'fix the red junction · validation runs on every edit' }
  else if (failed) { headline = 'No result'; sub = `run ${st.failure?.run ?? '#134'} failed at ${pad2(failed.index + 1)} · nothing was written to detections` }
  else if (st.footer) { headline = st.footer.headline; sub = st.footer.sub }
  else if (clusterRow) { headline = sc.footer.headline; sub = sc.footer.sub }
  else if (firstStale >= 0 && rows.every(r => r.stored === 'new')) { headline = 'No result yet'; sub = 'run the chain to see every intermediate' }
  else if (v.terminal !== validateDemoChain(fromScenario(sc).steps).terminal || n !== sc.steps.length) {
    const last = rows[n - 1]?.payload
    headline = `last run ${st.lastRun} · ${last?.summary ?? 'done'}`
    sub = `${n} stages · ${rows.filter(r => r.stored === 'cached').length} cached${surrogateOff ? ' · surrogate off' : sc.null.kind === 'toggle' ? ' · surrogate 200× queued after' : ` · ${sc.null.label}`}`
  }
  else { headline = sc.footer.headline; sub = surrogateOff && sc.footer.surrogateOff ? sc.footer.surrogateOff : sc.footer.sub }
  const spansN = v.terminal === 'spanset' && !invalid && !failed && !busy && allCached ? (template === 'drop_motifs9' ? 6 : 5) : null
  const lastDone = rows.length > 0 && rows[rows.length - 1].stored !== 'new' && !failed && !invalid && !busy
  const exportReason = busy ? 'wait for the run to finish' : invalid ? 'the chain is invalid' : failed ? 'the last run failed · nothing to export' : !lastDone ? 'no completed run yet' : undefined
  const reviewReason = v.terminal !== 'spanset' ? `needs a SpanSet terminal · this chain ends in ${DEMO_KIND_LABEL[v.terminal]}` : exportReason ?? (spansN === null ? 're-run the stale stages first' : undefined)

  const header = <Header workspace="Analyse" page="Chain" subtitle={sc.subtitle} search="Search spans, runs, families" demo />
  const showImport = modal === 'import'
  const insertPos = modal === 'insert' ? Math.max(0, Math.min(n, Number(atParam || n))) : null

  return (
    <>
      {header}
      <div className="page"><div className="page-inner" data-testid="chain-page" data-mode="demo" data-template={template}>
        {/* toolbar */}
        <div className="an-toolbar" data-testid="chain-toolbar">
          <DemoNameChip st={st} onRename={actions.rename} />
          <DemoSourceChip source={src} />
          <span className="spacer" />
          <NullControl sc={sc} st={st} onToggle={actions.toggleSurrogate} />
          <EstimateText text={est.text} tone={est.tone} />
          <Button ref={historyRef} icon="clock" variant={popover === 'history' ? 'primary' : 'default'} onClick={() => setPopover(popover === 'history' ? null : 'history')} testid="history-button">History</Button>
          {!clusterRow && !pausedRow && <Button icon="download" onClick={() => setModal('import')} testid="import-button">Import</Button>}
          {!clusterRow && !pausedRow && <Button icon="save" onClick={() => setModal('save')} disabled={!n} disabledReason="add a block first" testid="save-template">Save template</Button>}
          {primary}
        </div>

        <CrosshairProvider value={{ t: null, setT: () => {} }}>
          <ChainRow testIndex={0} num={null} title="Source" badge="source-cached" signature="— → Signal" caption={src.caption} t0={t0} t1={t1}
            plot={(x, w, h) => renderByType(sc.sourcePayload, { x, width: w, height: h, t0, t1, sourceStyle: true, throwForTest: route.query.throw === '1' })}
            onSettings={() => navigate('explore/signal/4')} settingsReason="the source is picked in Explore" />
          {st.steps.map((_, i) => <span key={st.steps[i].uid} style={{ display: 'contents' }}>{junctionFor(i) ?? insertPill(i)}{rowNode(rows[i])}</span>)}
          {n === 0 ? (
            <>
              {insertPill(0)}
              <div className="card an-first" data-testid="empty-chain">
                <Icon name="sparkle" size={18} />
                <div><div className="t">Add the first block</div><div className="s">blocks that accept Signal are listed first · or import a template</div></div>
                <div className="row" style={{ gap: 8, marginLeft: 'auto' }}>
                  <Button icon="plus" onClick={() => insertAt(0)} testid="add-first-block">Add a block</Button>
                  <Button variant="primary" icon="download" onClick={() => setModal('import')} testid="empty-import">Import a template</Button>
                </div>
              </div>
            </>
          ) : insertPill(n, true)}
          {endFits.length > 0 && (
            <div className="card an-suggest" data-testid="suggest-card">
              <Icon name="sparkle" size={18} />
              <div>
                <div className="t">{DEMO_KIND_LABEL[v.terminal]} → {endKinds.join(' / ')} fits here</div>
                <div className="s">{endFits.map(f => f.block.page_name).join(' · ')} — {endFits.length} block{endFits.length === 1 ? '' : 's'} accept {DEMO_KIND_LABEL[v.terminal]}</div>
              </div>
              <div className="row" style={{ gap: 8 }}>
                <Button icon="grid" onClick={() => insertAt(n)} testid="browse-compatible">Browse compatible</Button>
                <Button variant="primary" icon="plus" onClick={() => { actions.insert(n, endFits[0].block.name); toast.push({ text: `inserted ${endFits[0].block.page_name} as ${pad2(n + 1)} · terminal becomes ${DEMO_KIND_LABEL[endFits[0].block.output]}` }) }} disabled={busy} disabledReason="wait for the run to finish" testid="insert-suggested">Insert {endFits[0].block.page_name}</Button>
              </div>
            </div>
          )}
          <DemoAxis t0={t0} t1={t1} />
        </CrosshairProvider>

        {clusterRow && sc.hpc ? (
          <div className="card an-bottom" data-testid="generated-job">
            <div style={{ minWidth: 0 }}>
              <div className="row" style={{ gap: 10, alignItems: 'baseline' }}><b style={{ fontSize: 14 }}>Generated job</b><span className="mono muted" style={{ fontSize: 11 }}>stage {pad2(clusterRow.index + 1)} only · 01 resolved from cache by recipe-prefix hash</span>
                <span style={{ marginLeft: 'auto' }}><Dropdown prefix="template" value="guided" onChange={val => toast.push({ text: `script template · ${val}` })} options={[{ value: 'guided', label: 'guided · uob-bc4' }, { value: 'plain', label: 'plain sbatch' }]} /></span></div>
              <CodeBlock code={sc.hpc.script} filename="ub_mp_CH4_a7f3.sh" save={false} style={{ marginTop: 8 }} testid="slurm-script" />
            </div>
            <div className="an-after">
              <b>After it finishes</b>
              <div><Icon name="inbox" size={12} /> copy cluster_out/ back · Jobs › Manifest inbox</div>
              <div><Icon name="refresh" size={12} /> {pad2(clusterRow.index + 1)} turns cached · {pad2(clusterRow.index + 2)} → {pad2(n)} resume here</div>
              <div><Icon name="link" size={12} /> same recipe hash either way — reproducible</div>
              <div className="row" style={{ gap: 8, marginTop: 'auto', justifyContent: 'flex-end' }}>
                <Button icon="copy" onClick={() => { void navigator.clipboard?.writeText(sc.hpc!.script).catch(() => {}); toast.push({ text: 'script copied' }) }} testid="copy-script">Copy script</Button>
                <Button variant="primary" icon="download" onClick={() => { createSlurm(clusterRow); notWired('download the job bundle (script + recipe + manifest stub)') }} testid="download-job">Download job</Button>
              </div>
            </div>
          </div>
        ) : pausedRow && sc.paused ? (
          <div className="card an-bottom" data-testid="paused-run">
            <div style={{ minWidth: 0 }}>
              <div className="row" style={{ gap: 10, alignItems: 'baseline' }}><b style={{ fontSize: 14 }}>Paused run {sc.paused.runId}</b><span className="mono muted" style={{ fontSize: 11 }}>stage {pad2(pausedRow.index + 1)} went to the cluster · 01 stays cached</span></div>
              <div className="an-log" data-testid="paused-log">{sc.paused.log.map(([at, what], k) => <div key={k}><span>{at}</span> {what}</div>)}</div>
            </div>
            <div className="an-after">
              <b>When you continue</b>
              <div><Icon name="inbox" size={12} /> the file is stored as stage {pad2(pausedRow.index + 1)}'s artifact</div>
              <div><Icon name="refresh" size={12} /> {pad2(pausedRow.index + 1)} turns cached · {pad2(pausedRow.index + 2)} → {pad2(n)} run here</div>
              <div><Icon name="link" size={12} /> a file made with other parameters is refused</div>
              <div className="row" style={{ gap: 8, marginTop: 'auto', justifyContent: 'flex-end' }}>
                <Button icon="external" onClick={() => navigate(`jobs/run/${sc.paused!.runId}`)}>Open in Jobs</Button>
                <Button variant="primary" icon="play" onClick={() => continueFrom(pausedRow)} testid="continue-bottom">Continue from {pad2(pausedRow.index + 2)}</Button>
              </div>
            </div>
          </div>
        ) : (
          <FooterCard
            terminal={<Chip tone={invalid || !n ? 'grey' : terminal.tone} testid="footer-terminal">{n ? terminal.text : 'no blocks · the terminal type is the source'}<InfoTip title="Terminal type">Spec §6.1: the terminal type decides what the chain is — a SpanSet terminal saves as a detection template, a Model terminal as a training template.</InfoTip></Chip>}
            headline={headline} sub={sub}
            actions={<>
              <Button icon="upload" disabled={!!exportReason} disabledReason={exportReason} onClick={() => notWired('export the run report (recipe, per-stage hashes, results) to a JSON file')} testid="export-run">Export run</Button>
              {v.terminal === 'scores'
                ? <Button icon="wave" onClick={() => navigate('explore/signal/4')} disabled={!!exportReason} disabledReason={exportReason} testid="explore-track">Show as Explore track</Button>
                : <Button icon="arrow-right" disabled={v.terminal !== 'spanset' || !!exportReason} disabledReason={v.terminal !== 'spanset' ? 'needs a SpanSet terminal' : exportReason} onClick={() => navigate('analyse/interrogation')} testid="analyse-events">Analyse events</Button>}
              <Button variant="primary" icon="arrow-right" disabled={!!reviewReason} disabledReason={reviewReason} onClick={() => navigate('review/queue/q-12')} testid="pass-to-review">Pass {spansN ?? ''} to Review</Button>
            </>} />
        )}
      </div></div>

      {popover === 'history' && <DemoHistoryPopover anchorRef={historyRef} st={st} template={template} onClose={() => setPopover(null)} onApply={next => { actions.replaceAll(next); setPopover(null) }} onSave={() => { setPopover(null); setModal('save') }} />}
      {insertPos !== null && <DemoInsertModal steps={st.steps} position={insertPos} onClose={() => setQuery({ modal: null, at: null }, true)}
        onInsert={(block, open) => { actions.insert(insertPos, block); setQuery({ modal: null, at: null }, true); toast.push({ text: `inserted ${blockByName(block)?.page_name ?? block} as ${pad2(insertPos + 1)}` }); if (open) window.setTimeout(() => openBlock(insertPos), 0) }} />}
      {showImport && <ImportTemplateModal source={src} onClose={() => setModal(null)} onApply={name => { setQuery({ modal: null, template: name, state: 'fresh' }, true) }} />}
      <SaveTemplateModal open={modal === 'save'} onClose={() => setModal(null)} st={st} kind={v.terminal === 'spanset' ? 'detection' : v.terminal === 'model' ? 'training' : 'chain'} onSave={(name, ver) => { actions.save(name, ver); toast.push({ text: `${name} ${ver} saved · in memory for this session (demo)` }) }} />
      <RunLogModal open={modal === 'log'} onClose={() => setModal(null)} title={`Run log · ${st.failure?.run ?? '#134'}`} lines={logFor(st)} />
      {modal === 'upload' && clusterRow && <UploadArtifactModal stage={pad2(clusterRow.index + 1)} onClose={() => setModal(null)} onPlaced={() => { setModal(null); actions.patch({ status: { ...st.status, [clusterRow.step.uid]: 'paused' }, uploaded: true, note: 'result in place' }); toast.push({ text: `profile placed as stage ${pad2(clusterRow.index + 1)}'s artifact · checks passed · continue from ${pad2(clusterRow.index + 2)}` }) }} />}
    </>
  )
}

function progressVerb(block: string) {
  return block === 'demo.noise_floor' ? 'estimating slope noise' : block === 'demo.symbolic_encoding' ? 'encoding segments' : block === 'demo.drop_detection' ? 'detecting drops' : block === 'demo.baseline_removal' ? 'removing the baseline' : block === 'demo.matrix_profile' ? 'computing the profile' : 'computing'
}
function logFor(st: DemoChainState) {
  const f = st.failure
  return `run ${f?.run ?? '#134'} · template ${st.name} · recipe a7f39c · code 834c200
[01] Baseline removal      cached · 0 s
[02] Noise floor           cached · 0 s
[03] Symbolic encoding     cached · 0 s
[04] Drop detection        started
Traceback (most recent call last):
  File "Adapters/detection/drop_detect.py", line 212, in run
    windows = merge_candidates(spans, merge_window_s=params.merge_window_s)
  File "Working/detection/merge.py", line 88, in merge_candidates
    raise ValueError(msg)
${f?.message ?? 'ValueError: (none)'}
nothing was written to detections`
}
