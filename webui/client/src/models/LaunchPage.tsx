/* models.launch (frames models-1, models-1b; spec §7b.1, P11, P18, P19). Train a template across channels or from a saved
 * window set, with paired label arms, a blocked split set aside before training, and the ≤ 2 h local rule. */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BandStrip, Button, Callout, ChainRibbon, Checkbox, Checklist, CodeBlock, DisabledReason, Dropdown, Icon, InfoTip, NumberField, Popover, ProgressBar,
  SectionCard, Seg, StatRow, StatTile, TextField, Toggle, fmtInt, recordDemoWrite, useDemoState, useDemoWrites, useQueryState, useSim, type CheckState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, setQuery } from '../state'
import { useSourced } from '../api/seam'
import {
  BASE_SPLIT_COUNTS, DEFAULT_CHANNELS, ESTIMATE_MODEL, FRAME_SPLIT_BLOCKS, MODEL_CLASSES, NEXT_JOB_NUMBER, TEST_WARN_BELOW, getLaunchSetup,
  type LaunchSetup, type SourceChannelRow, type TrainingTemplate, type WindowSetRow,
} from '../api/models'
import { seeded } from '../fixtures/canon'
import { ArmBadge, Loading, LoadFailed, ModelsTabs, NullChip, TrainingJobsLink } from './chrome'
import { Page } from '../kit'

const SESSION_RE = /^[A-Za-z0-9_]{3,60}$/
const WS_RE = /^ws_[A-Za-z0-9_]+$/
const TRAIN_STEPS = ['arm A · manual labels', 'arm B · cluster labels', 'RF baseline', 'RF null 200×', 'model null 5×']

export function LaunchPage() {
  const setup = useSourced(getLaunchSetup, [])
  return (
    <>
      <Header workspace="Models" page="Launch" subtitle="train a template across channels · paired label arms" demo={setup.source === 'demo'} />
      <Page testid="models-launch">
        {setup.error ? <LoadFailed what="the training setup" error={setup.error} onRetry={setup.reload} />
          : !setup.data ? <Loading /> : <LaunchBody setup={setup.data} />}
      </Page>
    </>
  )
}

type Check = { id: string; label: string; state: CheckState }

function LaunchBody({ setup }: { setup: LaunchSetup }) {
  const { push } = useToast()
  /* ---------------- deep-linkable form state ---------------- */
  const [templateName, setTemplate] = useQueryState('template', 'cnn_windows_v3')
  const template: TrainingTemplate = setup.templates.find(t => t.name === templateName) ?? setup.templates[0]
  const fromSet = template.source === 'WindowSet'
  const [channelsQ, setChannelsQ] = useQueryState('channels', DEFAULT_CHANNELS.join(','))
  const checked = channelsQ === 'none' ? [] : channelsQ.split(',').filter(Boolean)
  const setChecked = (xs: string[]) => setChannelsQ(xs.length ? xs.join(',') : 'none')
  const [wsQ, setWsQ] = useQueryState('windowset', `${setup.windowSets[0].id}@${setup.windowSets[0].version}`)
  const windowSet: WindowSetRow = setup.windowSets.find(w => `${w.id}@${w.version}` === wsQ && !w.disabledReason) ?? setup.windowSets[0]
  const [armsQ, setArmsQ] = useQueryState('arms', 'a,b')
  const arms = armsQ === 'none' ? [] : armsQ.split(',').filter(a => a === 'a' || a === 'b')
  const [paired, setPaired] = useQueryState<'all' | 'each'>('paired', 'all')
  const [testPct, setTestPct] = useQueryState('test', '20')
  const [valPct, setValPct] = useQueryState('val', '10')
  const [gapQ, setGap] = useQueryState('gap', '600')
  const [seedsQ, setSeedsQ] = useQueryState('seeds', '')
  const [epochs, setEpochs] = useQueryState('epochs', '30')
  const [batch, setBatch] = useQueryState('batch', '64')
  const [nullQ, setNull] = useQueryState<'model5' | 'model0'>('null', 'model5')
  const [saveWsQ, setSaveWs] = useQueryState('savews', '1')
  const [popover, setPopover] = useQueryState('popover', '')
  const [stateQ, setStateQ] = useQueryState('state', '')

  /* ---------------- in-memory drafts ---------------- */
  const [sessions, setSessions] = useDemoState<Record<string, { name: string; saved: boolean }>>('models.launch.sessions', () => ({}))
  const session = sessions[template.name] ?? { name: template.sessionDefault, saved: false }
  const [wsName, setWsName] = useDemoState<string | null>('models.launch.wsName', () => null)
  const [submitted, setSubmitted] = useDemoState<{ jobId: string; session: string } | null>('models.launch.submitted', () => null)
  const addedJobs = useDemoWrites('models').filter(w => w.kind === 'add-training-job').length

  const seedsOn = seedsQ !== ''
  const seeds = seedsOn ? Number(seedsQ) || 3 : 1
  const gapS = fromSet ? windowSet.windowS : Number(gapQ)
  const windowS = fromSet ? windowSet.windowS : 600
  const saveWs = !fromSet && saveWsQ === '1'

  /* ---------------- derived: sources, counts, estimate ---------------- */
  const chosenChannels: SourceChannelRow[] = setup.channels.filter(c => !c.disabledReason && checked.includes(c.channel))
  const sourceLabels = fromSet ? (windowSet.channels === 'all' ? ['all'] : windowSet.channels) : chosenChannels.map(c => c.channel)
  const labelledEvery = fromSet ? windowSet.verdictsNow : chosenChannels.reduce((a, c) => a + c.humanVerdicts, 0)
  const clusterWindows = fromSet ? windowSet.clusterWindows : chosenChannels.reduce((a, c) => a + (c.windows ?? 0), 0)
  const scale = fromSet ? windowSet.windows / 15660 : chosenChannels.length / 3
  const defaultName = `ws_M2aug_${chosenChannels.length}ch_600s`
  const wsDisplayName = wsName ?? defaultName
  const wsVersion = wsDisplayName === setup.windowSets[0].id ? 2 : 1
  const wsNameError = !saveWs ? null : !wsDisplayName.trim() ? 'a window-set name is required' : !WS_RE.test(wsDisplayName) ? 'window-set names start with ws_ (letters, digits and _)' : null

  const tPct = fromSet ? 20 : Number(testPct), vPct = fromSet ? 10 : Number(valPct)
  const counts = useMemo(() => {
    const totals = MODEL_CLASSES.map((_, i) => fromSet
      ? Math.round((BASE_SPLIT_COUNTS.train[i] + BASE_SPLIT_COUNTS.val[i] + BASE_SPLIT_COUNTS.test[i]) * windowSet.verdictsNow / 2140)
      : chosenChannels.reduce((a, c) => a + c.perClass[i], 0))
    return MODEL_CLASSES.map((cls, i) => {
      const base = BASE_SPLIT_COUNTS.train[i] + BASE_SPLIT_COUNTS.val[i] + BASE_SPLIT_COUNTS.test[i]
      const test = Math.round(totals[i] * (BASE_SPLIT_COUNTS.test[i] / base) * (tPct / 20))
      const val = Math.round(totals[i] * (BASE_SPLIT_COUNTS.val[i] / base) * (vPct / 10))
      return { cls, train: Math.max(0, totals[i] - test - val), val, test }
    })
  }, [fromSet, windowSet, chosenChannels, tPct, vPct])
  const lowClasses = counts.filter(c => c.test < TEST_WARN_BELOW)

  const nArms = arms.length
  const localH = (nArms * ESTIMATE_MODEL.perArmH + ESTIMATE_MODEL.rfH + (nullQ === 'model5' ? ESTIMATE_MODEL.modelNullsH : 0)) * scale * (Number(epochs) / 30) * seeds
  const hpcH = localH * ESTIMATE_MODEL.hpcRatio
  const diskGb = ESTIMATE_MODEL.diskGbPer3ch * scale * (saveWs || fromSet ? 1 : 0.92)
  const overLimit = localH > ESTIMATE_MODEL.localLimitH

  /* ---------------- checks ---------------- */
  const hasCh7 = fromSet ? (windowSet.channels !== 'all' && windowSet.channels.includes('CH7_B2')) : checked.includes('CH7_B2')
  const checks: Check[] = []
  if (!fromSet && chosenChannels.length === 0) checks.push({ id: 'sources', label: 'pick at least one source channel', state: 'fail' })
  if (nArms === 0) checks.push({ id: 'arms-none', label: 'add at least one label arm', state: 'fail' })
  if (!SESSION_RE.test(session.name)) checks.push({ id: 'session', label: 'session name: 3–60 letters, digits and _ only', state: 'fail' })
  if (wsNameError) checks.push({ id: 'wsname', label: `Save window set: ${wsNameError}`, state: 'fail' })
  checks.push({ id: 'unseen', label: 'test block never seen in training, validation or early stopping', state: 'pass' })
  checks.push(fromSet
    ? { id: 'gap', label: 'gap between blocks ≥ window length · checked at save', state: 'pass' }
    : gapS < windowS ? { id: 'gap', label: `gap between blocks ≥ window length · ${gapS} s < ${windowS} s`, state: 'fail' } : { id: 'gap', label: 'gap between blocks ≥ window length', state: 'pass' })
  checks.push({ id: 'features', label: `label-derived features off in ${template.matrixStage}`, state: 'pass' })
  if (nArms === 2) checks.push(paired === 'all'
    ? { id: 'paired', label: `every arm trains on the same ${fmtInt(labelledEvery)} windows`, state: 'pass' }
    : { id: 'paired', label: 'arms are not paired · Compare can’t attribute the difference', state: 'warn' })
  else if (nArms === 1) checks.push({ id: 'paired', label: 'one label arm · nothing to pair (Compare needs two)', state: 'pending' })
  if (lowClasses.length) checks.push({
    id: 'classes', state: 'warn',
    label: lowClasses.length === 1 ? `${lowClasses[0].cls} class: ${lowClasses[0].test} test windows (≥ ${TEST_WARN_BELOW} recommended)`
      : `${lowClasses.map(c => c.cls).join(', ')}: ${lowClasses.map(c => c.test).join(', ')} test windows (≥ ${TEST_WARN_BELOW} recommended)`,
  })
  if (hasCh7) checks.push({ id: 'ch7', label: 'CH7 has no plateau verdicts', state: 'warn' })
  if (nullQ === 'model0') checks.push({ id: 'null', label: 'no full-model null · only the RF label shuffle', state: 'warn' })
  const failing = checks.find(c => c.state === 'fail')

  /* ---------------- script ---------------- */
  const hh = String(Math.max(1, Math.ceil(hpcH * 2.5))).padStart(2, '0')
  const script = [
    '#!/bin/bash',
    `#SBATCH --job-name=${session.name}`,
    `#SBATCH --gres=gpu:1  --time=${hh}:00:00`,
    '#SBATCH --mem=32G',
    '',
    'python -m pipeline.train \\',
    `  --template ${template.name}@${template.version} \\`,
    fromSet ? `  --windowset ${windowSet.id}@${windowSet.version} \\` : `  --sources M2_aug_fs1:${chosenChannels.map(c => c.channel).join(',') || '—'} \\`,
    `  --arms ${arms.map(a => (a === 'a' ? 'manual' : 'cluster')).join(',') || '—'} --baseline rf \\`,
    `  --paired-windows ${paired === 'all' ? 'labelled-in-all' : 'each-arm'} \\`,
    fromSet ? '  --split from-windowset \\' : `  --split blocked:test=${tPct / 100},val=${vPct / 100},gap=${gapS} \\`,
    `  --null rf:200,model:${nullQ === 'model5' ? 5 : 0} \\`,
    ...(seedsOn ? [`  --repeats ${seeds} \\`] : []),
    ...(epochs !== '30' || batch !== '64' ? [`  --epochs ${epochs} --batch ${batch} \\`] : []),
    ...(saveWs ? [`  --save-windowset ${wsDisplayName}_v${wsVersion} \\`] : []),
    ...(fromSet ? ['  --verdicts-as-of launch \\'] : []),
    '  --manifest inbox/',
  ].join('\n')

  /* ---------------- local training simulation ---------------- */
  const sim = useSim(`models.train.${session.name}`)
  useEffect(() => {
    if (stateQ === 'running') sim.force({ status: 'running', steps: TRAIN_STEPS, step: 1, fraction: 0.32, startedAt: Date.now() })
    if (stateQ === 'failed') sim.force({ status: 'failed', steps: TRAIN_STEPS, step: 3, fraction: 0.64, error: 'RF null 200× failed (simulated): the local worker ran out of memory at shuffle 118', finishedAt: Date.now() })
    if (stateQ === 'done') sim.force({ status: 'done', steps: TRAIN_STEPS, step: 4, fraction: 1, finishedAt: Date.now() })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])
  const isSubmitted = stateQ === 'submitted' || !!submitted
  const submittedJob = submitted?.jobId ?? `j-0${NEXT_JOB_NUMBER}`

  const trainLocally = () => {
    setSessions(s => ({ ...s, [template.name]: { ...session, saved: true } }))
    recordDemoWrite('models', 'train-local', { session: session.name, template: template.name, arms, estimate_h: +localH.toFixed(2) })
    sim.start({ steps: TRAIN_STEPS, stepMs: 1100 })
    setStateQ(null)
  }
  const scriptRef = useRef<HTMLDivElement>(null)
  const createScript = () => {
    const id = `j-0${NEXT_JOB_NUMBER + addedJobs}`
    recordDemoWrite('jobs', 'add-job', { id, kind: 'cluster', title: `${session.name} paired arms`, status: 'queue', detail: 'script created · not submitted', for: session.name })
    recordDemoWrite('models', 'add-training-job', { id, template: `${template.name}@${template.version}`, arms: arms.map(a => (a === 'a' ? 'manual' : 'cluster')), session: session.name })
    if (saveWs) recordDemoWrite('library', 'save-window-set', { id: wsDisplayName, version: wsVersion, channels: chosenChannels.map(c => c.channel), windows: clusterWindows })
    setSessions(s => ({ ...s, [template.name]: { ...session, saved: true } }))
    setSubmitted({ jobId: id, session: session.name })
    push({ text: `${id} added to Jobs · mark it submitted there${saveWs ? ` · ${wsDisplayName} v${wsVersion} saved to Library` : ''}`, action: { label: 'Open in Jobs', onClick: () => navigate(`jobs/cluster/${id}`) } })
    setScriptOpen(true)
    window.setTimeout(() => { scriptRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); scriptRef.current?.classList.add('m-flash'); window.setTimeout(() => scriptRef.current?.classList.remove('m-flash'), 1300) }, 50)
  }
  const [scriptOpen, setScriptOpen] = useState(false)
  const showScript = overLimit || scriptOpen

  const launchReason = failing ? `fix first: ${failing.label}` : null
  const localReason = launchReason ?? (overLimit ? `over the ${ESTIMATE_MODEL.localLimitH} h local limit · ≈ ${localH.toFixed(1)} h` : sim.busy ? 'already training' : undefined)

  /* ---------------- popover anchors ---------------- */
  const estRef = useRef<HTMLButtonElement>(null)
  const addArmRef = useRef<HTMLButtonElement>(null)
  const m4Ref = useRef<HTMLButtonElement>(null)

  const chooseTemplate = (name: string) => setQuery({ template: name === 'cnn_windows_v3' ? null : name, state: null }, true)

  return (
    <>
      {/* ------------------------------------------------ toolbar ------------------------------------------------ */}
      <div className="m-toolbar" data-testid="launch-toolbar">
        <SessionChip name={session.name} saved={session.saved} onRename={name => setSessions(s => ({ ...s, [template.name]: { name, saved: true } }))} />
        <span className="k-spacer" />
        <NullChip />
        <button ref={estRef} type="button" className={`m-tool-chip btn ${overLimit ? 'amber' : 'grey'}`} onClick={() => setPopover(popover === 'estimate' ? null : 'estimate')} data-testid="estimate-chip"
          aria-expanded={popover === 'estimate'} title="how the estimate adds up">
          <Icon name="hourglass" size={13} />≈ {localH.toFixed(1)} h local{overLimit ? ` above ${ESTIMATE_MODEL.localLimitH} h limit` : ` · within the ${ESTIMATE_MODEL.localLimitH} h limit`}
        </button>
        <Popover open={popover === 'estimate'} onClose={() => setPopover(null)} anchorRef={estRef} placement="bottom-end" title="Estimate" width={320} testid="estimate-popover">
          <div className="m-mono m-small" style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '4px 12px' }}>
            {arms.includes('a') && <><span>arm A · manual labels</span><span>≈ {(ESTIMATE_MODEL.perArmH * scale * seeds * Number(epochs) / 30).toFixed(1)} h</span></>}
            {arms.includes('b') && <><span>arm B · cluster labels</span><span>≈ {(ESTIMATE_MODEL.perArmH * scale * seeds * Number(epochs) / 30).toFixed(1)} h</span></>}
            <span>RF baseline + 200× shuffle</span><span>≈ {(ESTIMATE_MODEL.rfH * scale * seeds * Number(epochs) / 30).toFixed(1)} h</span>
            <span>model nulls {nullQ === 'model5' ? '5×' : '0×'}</span><span>≈ {((nullQ === 'model5' ? ESTIMATE_MODEL.modelNullsH : 0) * scale * seeds * Number(epochs) / 30).toFixed(1)} h</span>
            <span style={{ borderTop: '1px solid var(--border)', paddingTop: 4 }}>local total</span><span style={{ borderTop: '1px solid var(--border)', paddingTop: 4, fontWeight: 600 }}>≈ {localH.toFixed(1)} h</span>
            <span className="m-muted">local limit</span><span className="m-muted">{ESTIMATE_MODEL.localLimitH} h</span>
          </div>
          <div style={{ marginTop: 8 }}><Button variant="link" size="sm" icon="external" onClick={() => navigate('settings/compute-hpc')}>Settings › Compute & HPC</Button></div>
        </Popover>
        {sim.busy ? (
          <span className="row" style={{ gap: 8, display: 'inline-flex', alignItems: 'center' }} data-testid="train-progress">
            <ProgressBar value={sim.fraction} width={160} label={`${sim.status === 'queued' ? 'queued' : sim.steps[sim.step] ?? 'training'} · ${Math.round(sim.fraction * 100)} %`} />
            <Button icon="stop" onClick={() => { sim.cancel(); setStateQ(null) }} testid="train-cancel">Cancel</Button>
          </span>
        ) : (
          <Button icon="play" variant={overLimit ? 'default' : 'primary'} disabled={!!localReason} disabledReason={localReason} onClick={trainLocally} testid="train-locally">Train locally</Button>
        )}
        <Button icon="file" variant={overLimit ? 'cluster' : 'default'} disabled={!!launchReason} disabledReason={launchReason ?? undefined} onClick={createScript} testid="create-slurm">Create SLURM script</Button>
      </div>

      <ModelsTabs current="launch" jobsLink={<TrainingJobsLink base={setup.trainingJobs.length} />} />

      {sim.status === 'failed' && <Callout tone="red" title="Local training failed" testid="train-failed" action={<Button size="sm" icon="refresh" onClick={trainLocally} disabled={!!localReason} disabledReason={localReason}>Retry</Button>}>{sim.error}</Callout>}
      {sim.status === 'done' && <Callout tone="green" title="Training finished (demo)" testid="train-done" action={<Button size="sm" variant="primary" icon="bar-chart" onClick={() => navigate('models/results')}>Open Results</Button>}>{TRAIN_STEPS.length} steps · the Results tab shows the fixture results of j-0212</Callout>}
      {sim.status === 'cancelled' && <Callout tone="blue" icon="info" testid="train-cancelled" action={<Button size="sm" onClick={() => sim.reset()}>Dismiss</Button>}>Local training cancelled at {sim.steps[sim.step] ?? 'queue'} · nothing was kept</Callout>}

      <div className="m-cols">
        {/* ------------------------------------------------ left column ------------------------------------------------ */}
        <div className="m-stack">
          <SectionCard number={1} title="Training template" info="Picked from Analyse templates whose terminal type is Model. The classifier stage decides binary or multi-class." subtitle="from Analyse" testid="launch-template"
            actions={<Button variant="link" icon="external" onClick={() => navigate('analyse/training')} testid="open-in-analyse">Open in Analyse</Button>}>
            <div className="m-foot-line" style={{ marginBottom: 10, color: 'var(--text-2)' }}>
              <Dropdown value={template.name} onChange={chooseTemplate} active width={236} testid="template-select" ariaLabel="training template"
                options={setup.templates.map(t => ({ value: t.name, label: `${t.name} · v${t.version}`, description: `source ${t.source} · ${t.stages.length - 1} stages`, icon: t.source === 'WindowSet' ? 'layers' as const : 'wave' as const }))} />
              <span className="k-chip blue sm">source {template.source}</span>
              <span className="k-chip sm" style={{ background: 'var(--purple-100)', color: '#7446e0', borderColor: 'transparent' }}>{template.multiClass ? 'multi-class' : 'binary'} · {template.classes} classes</span>
              <span>{template.classifier}</span>
            </div>
            <ChainRibbon testid="template-ribbon" blocks={template.stages.map(s => ({ id: s.id, label: s.index ? `${String(s.index).padStart(2, '0')} ${s.label}` : s.label, glyph: s.glyph, signature: undefined }))} />
          </SectionCard>

          <SectionCard number={2} title="Sources" testid="launch-sources"
            info={fromSet ? 'The template starts from WindowSet, so its source is one saved window set; it arrives with its split and spacing check (§6.9).' : 'The template starts from Signal and makes its own window set with sliding windows, so each recording × channel is a source.'}
            subtitle={fromSet ? 'the template starts from WindowSet, so the source is one saved set' : 'the template starts from Signal, so each channel is a source'}
            actions={<Seg testid="sources-mode" value={fromSet ? 'windowset' : 'channels'} onChange={() => undefined}
              options={[{ value: 'channels', label: 'Channels', disabled: fromSet, reason: 'the template starts from WindowSet' }, { value: 'windowset', label: 'Saved window set', disabled: !fromSet, reason: 'the template starts from Signal' }]} />}>
            {!fromSet ? (
              <>
                <table className="m-table" data-testid="source-channels">
                  <thead><tr><th style={{ width: 24 }} /><th>recording · channel</th><th>hours</th><th>windows</th><th>human verdicts</th><th>classes seen</th><th /></tr></thead>
                  <tbody>
                    {setup.channels.map(c => {
                      const on = !c.disabledReason && checked.includes(c.channel)
                      return (
                        <tr key={c.key} className={c.disabledReason ? 'dim' : undefined} data-testid={`source-row-${c.channel}`}>
                          <td><Checkbox checked={on} disabled={!!c.disabledReason} disabledReason={c.disabledReason} ariaLabel={`use ${c.recording} ${c.channel}`} testid={`source-check-${c.channel}`}
                            onChange={v => setChecked(v ? [...checked, c.channel] : checked.filter(x => x !== c.channel))} /></td>
                          <td style={{ color: c.disabledReason ? undefined : 'var(--text)' }}>{c.recording} · {c.channel}</td>
                          <td>{c.hours} h</td>
                          <td>{c.windows == null ? '—' : fmtInt(c.windows)}</td>
                          <td>{fmtInt(c.humanVerdicts)}</td>
                          <td>{c.classesSeen ? `${c.classesSeen[0]} / ${c.classesSeen[1]}` : '—'}</td>
                          <td className="num">{c.flag && <span className="k-chip amber sm">{c.flag}</span>}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                {chosenChannels.length === 0 && <div className="k-field-error" role="alert" style={{ marginTop: 6 }} data-testid="sources-empty"><Icon name="alert-circle" size={11} />pick at least one source channel</div>}
                <div className="m-foot-line" style={{ marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                  <Toggle checked={saveWs} onChange={v => setSaveWs(v ? null : '0')} label={<span style={{ color: 'var(--text)' }}>Save window set</span>} testid="save-ws-toggle" />
                  <span style={{ display: 'inline-flex', flexDirection: 'column', gap: 2 }}>
                    <TextField value={wsDisplayName} onChange={v => setWsName(v)} icon="save" width={220} suffix={`v${wsVersion}`} disabled={!saveWs} disabledReason="Save window set is off" invalid={!!wsNameError} testid="ws-name" ariaLabel="window-set name" />
                    {wsNameError && <span className="k-field-error" role="alert"><Icon name="alert-circle" size={11} />{wsNameError}</span>}
                  </span>
                  <span>{saveWs ? `at ${template.windowsStage} · ${chosenChannels.length} channel${chosenChannels.length === 1 ? '' : 's'} · ${fmtInt(clusterWindows)} windows · split included${wsVersion === 2 ? ` · ${setup.windowSets[0].id} exists, this saves v2` : ''}` : 'the window set is not kept after training'}</span>
                </div>
              </>
            ) : (
              <>
                <table className="m-table" data-testid="source-windowsets">
                  <thead><tr><th style={{ width: 24 }} /><th>window set</th><th>channels</th><th>windows · split</th><th>verdicts now (at save)</th><th /></tr></thead>
                  <tbody>
                    {setup.windowSets.map(w => {
                      const key = `${w.id}@${w.version}`
                      const on = key === `${windowSet.id}@${windowSet.version}`
                      const radio = <input type="radio" name="launch-windowset" checked={on} disabled={!!w.disabledReason} onChange={() => setWsQ(key)} aria-label={`${w.id} v${w.version}`} data-testid={`ws-radio-${w.id}`} />
                      return (
                        <tr key={key} className={w.disabledReason ? 'dim' : 'm-row-click'} onClick={() => { if (!w.disabledReason) setWsQ(key) }} data-testid={`ws-row-${w.id}`}>
                          <td>{w.disabledReason ? <DisabledReason reason={w.disabledReason}>{radio}</DisabledReason> : radio}</td>
                          <td style={{ color: w.disabledReason ? undefined : 'var(--text)' }}>{w.id} · v{w.version}</td>
                          <td>{w.channelsLabel}</td>
                          <td>{fmtInt(w.windows)} · {w.split}</td>
                          <td>{fmtInt(w.verdictsNow)} ({fmtInt(w.verdictsAtSave)})</td>
                          <td className="num"><span className={`k-chip sm ${w.badge === 'train-safe' ? 'green' : w.badge === 'not train-safe' ? 'red' : 'amber'}`} title={w.disabledReason}>{w.badge}</span></td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                <div className="m-foot-line" style={{ marginTop: 6 }}>arrives with its split and spacing check · {windowSet.savedFrom}</div>
              </>
            )}
          </SectionCard>

          <SectionCard number={3} title="Label arms" info="One or more label sources trained as a paired job: same windows, split and test block, so the arms differ only in their labels. The RF baseline is always on." subtitle="paired — same windows, split and test block" testid="launch-arms"
            actions={<>
              <Button ref={addArmRef} icon="plus" onClick={() => setPopover(popover === 'add-arm' ? null : 'add-arm')} aria-expanded={popover === 'add-arm'} testid="add-arm">Add arm</Button>
              <Popover open={popover === 'add-arm'} onClose={() => setPopover(null)} anchorRef={addArmRef} placement="bottom-end" title="Add a label arm" width={320} testid="add-arm-popover">
                <div className="k-menu" role="menu">
                  {[
                    { key: 'a', label: 'manual labels', d: 'Review verdicts · 4 classes', reason: arms.includes('a') ? 'already an arm' : undefined },
                    { key: 'b', label: 'cluster labels', d: `${template.clusterStage} · k = 4`, reason: arms.includes('b') ? 'already an arm' : undefined },
                    { key: 'ws', label: 'labels from a window set', d: 'verdicts frozen in a saved set', reason: 'not built' },
                  ].map(o => (
                    <button key={o.key} type="button" role="menuitem" className="k-menu-item" aria-disabled={!!o.reason || undefined} title={o.reason} data-testid={`add-arm-${o.key}`}
                      onClick={() => { if (o.reason) return; setQuery({ arms: [...arms, o.key].sort().join(',') === 'a,b' ? null : [...arms, o.key].sort().join(','), popover: null }, true) }}>
                      <span className="body"><span>{o.label}</span><span className="desc">{o.d}</span>{o.reason && <span className="reason">⊘ {o.reason}</span>}</span>
                    </button>
                  ))}
                </div>
              </Popover>
            </>}>
            <div className="m-stack" style={{ gap: 5 }}>
              {arms.includes('a') && (
                <div className="m-arm-row" data-testid="arm-row-a"><ArmBadge letter="A" /><span className="nm">manual labels</span><span className="src">Review verdicts · 4 classes</span>
                  <span className="cnt">{fmtInt(labelledEvery)} windows labelled</span>
                  <button type="button" className="k-icon-btn" aria-label="remove arm A" title="remove arm A" onClick={() => setArmsQ(arms.filter(a => a !== 'a').join(',') || 'none')} data-testid="remove-arm-a"><Icon name="x" size={12} /></button></div>
              )}
              {arms.includes('b') && (
                <div className="m-arm-row" data-testid="arm-row-b"><ArmBadge letter="B" /><span className="nm">cluster labels</span><span className="src">{template.clusterStage} · k = 4 · criterion max silhouette</span>
                  <span className="cnt">{fmtInt(clusterWindows)} windows labelled</span>
                  <button type="button" className="k-icon-btn" aria-label="remove arm B" title="remove arm B" onClick={() => setArmsQ(arms.filter(a => a !== 'b').join(',') || 'none')} data-testid="remove-arm-b"><Icon name="x" size={12} /></button></div>
              )}
              <div className="m-arm-row" data-testid="arm-row-rf"><ArmBadge letter="RF" /><span className="nm">random-forest baseline</span><span className="src">{template.matrixStage} features · trained once per arm</span>
                <span className="cnt" title="the RF baseline cannot be removed: every arm is judged against it">always on</span><Icon name="lock" size={12} style={{ color: 'var(--muted)' }} /></div>
              {nArms === 0 && <div className="k-field-error" role="alert" data-testid="arms-empty"><Icon name="alert-circle" size={11} />add at least one label arm</div>}
              {nArms === 1 && <div className="m-foot-line" data-testid="arms-single">a single arm can’t be compared in Compare</div>}
              <div className="m-foot-line" style={{ marginTop: 4 }}>
                <span>train every arm on</span>
                <Dropdown value={paired} onChange={v => setPaired(v)} active testid="paired-select" ariaLabel="train every arm on"
                  options={[{ value: 'all', label: `windows labelled in every arm · ${fmtInt(labelledEvery)}` }, { value: 'each', label: 'every window each arm labels', description: 'arms are not paired' }]} />
                <InfoTip title="Paired">Arms differ only in their labels when they train on the windows labelled in every arm.</InfoTip>
                <span>so the comparison is paired</span>
              </div>
            </div>
          </SectionCard>

          <SectionCard number={4} title="Evaluation" testid="launch-evaluation"
            info="A test block and a validation block are set aside before training, blocked by time within each channel with a gap ≥ one window — never a random sample of windows. The test block is scored once, after training."
            subtitle={fromSet ? 'split comes with the window set · locked here, change it by saving a new version' : 'test block set aside before training · blocked by time'}>
            <div className="m-foot-line" style={{ marginBottom: 10 }}>
              <Dropdown prefix="test" value={String(tPct)} onChange={setTestPct} disabled={fromSet} disabledReason="split comes with the window set" testid="test-pct"
                options={['10', '15', '20', '25'].map(v => ({ value: v, label: `${v} %` }))} />
              <Dropdown prefix="validation" value={String(vPct)} onChange={setValPct} disabled={fromSet} disabledReason="split comes with the window set" testid="val-pct"
                options={['5', '10', '15'].map(v => ({ value: v, label: `${v} %` }))} />
              <span style={{ display: 'inline-flex', flexDirection: 'column', gap: 2 }}>
                <Dropdown prefix="gap" value={String(gapS)} onChange={setGap} disabled={fromSet} disabledReason="split comes with the window set" testid="gap-select"
                  options={fromSet ? [{ value: String(windowSet.windowS), label: `≥ ${windowSet.windowS} s (1 window)` }] : [{ value: '600', label: '≥ 600 s (1 window)' }, { value: '1200', label: '≥ 1,200 s (2 windows)' }, { value: '0', label: '0 s' }]} />
                {!fromSet && gapS < windowS && <span className="k-field-error" role="alert" data-testid="gap-error"><Icon name="alert-circle" size={11} />gap must be ≥ window length ({windowS} s)</span>}
              </span>
              <span className="k-spacer" />
              <button ref={m4Ref} type="button" className="m-lock-toggle" role="switch" aria-checked={false} aria-disabled onClick={() => setPopover(popover === 'm4' ? null : 'm4')} data-testid="m4-toggle" title="M4_aug is held out (D6)">
                <span className="sw" />M4_aug locked · Settings › Datasets <span className="m-muted m-small">held out</span>
              </button>
              <Popover open={popover === 'm4'} onClose={() => setPopover(null)} anchorRef={m4Ref} placement="bottom-end" title="M4_aug is held out" width={320} testid="m4-popover">
                <div className="m-small" style={{ lineHeight: 1.45 }}>{setup.heldOut.reason}</div>
                <div style={{ marginTop: 8 }}><Button size="sm" icon="lock" onClick={() => navigate('settings/datasets')}>Settings › Datasets</Button></div>
              </Popover>
            </div>
            <SplitStrip channels={sourceLabels.filter(c => c !== 'all')} hours={fromSet ? (windowSet.recordingKey === 'M3_jul' ? 280 : 721) : 721} test={tPct} val={vPct} />
            <div className="m-counts" style={{ marginTop: 10 }} data-testid="class-counts">
              <span className="h">windows per class</span>{MODEL_CLASSES.map(c => <span key={c} className="h">{c}</span>)}<span />
              {(['train', 'val', 'test'] as const).map(split => (
                <div key={split} style={{ display: 'contents' }}>
                  <span style={{ textAlign: 'right', paddingRight: 16 }}>{split}</span>
                  {counts.map(c => <span key={c.cls} className={split === 'test' && c.test < TEST_WARN_BELOW ? 'm-amber-text' : undefined} style={{ fontWeight: split === 'test' && c.test < TEST_WARN_BELOW ? 600 : 400 }}>{fmtInt(c[split])}</span>)}
                  <span>{split === 'train' && lowClasses.length > 0 && <span className="k-chip amber sm" data-testid="low-class-chip">{lowClasses.map(c => `${c.cls}: ${c.test}`).join(' · ')} test &lt; {TEST_WARN_BELOW}</span>}</span>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard number={5} title="Options" testid="launch-options" info="Seeds repeat the whole paired job. The null is a label shuffle: 200× on the RF baseline plus a few on the full model, since every full-model shuffle is a full retrain.">
            <div className="m-foot-line">
              <Toggle checked={seedsOn} onChange={v => setSeedsQ(v ? '3' : null)} label={<span style={{ color: 'var(--text)' }}>repeat with different seeds</span>} testid="seeds-toggle" />
              <NumberField value={seedsOn ? seeds : 3} onValid={n => setSeedsQ(String(n))} min={2} max={10} integer unit="seeds" width={96} disabled={!seedsOn} disabledReason="turn on repeat with different seeds" testid="seeds-count" ariaLabel="number of seeds" />
              <Dropdown prefix="epochs" value={epochs} onChange={setEpochs} testid="epochs" options={['10', '20', '30', '50'].map(v => ({ value: v, label: v }))} />
              <Dropdown prefix="batch" value={batch} onChange={setBatch} testid="batch" options={['32', '64', '128'].map(v => ({ value: v, label: v }))} />
              <Dropdown prefix="null" value={nullQ} onChange={v => setNull(v)} testid="null-select" options={[{ value: 'model5', label: 'RF 200× · model 5×' }, { value: 'model0', label: 'RF 200× · model 0×', description: 'no full-model null' }]} />
            </div>
          </SectionCard>
        </div>

        {/* ------------------------------------------------ right column ------------------------------------------------ */}
        <div className="k-card m-rcard" data-testid="launch-right">
          <h4>Before launch <InfoTip title="Before launch">Warnings do not block a launch; a failed check disables both launch buttons and names itself as the reason.</InfoTip></h4>
          <Checklist items={checks.map(c => ({ id: c.id, label: c.label, state: c.state }))} testid="before-launch" />
          <hr />
          <h4>Estimate</h4>
          <StatRow columns={3}>
            <StatTile label="local" value={`≈ ${localH.toFixed(1)} h`} caption={`${nArms + 1} arm${nArms ? 's' : ''} + ${nullQ === 'model5' ? 5 : 0} model nulls`} tone={overLimit ? 'amber' : undefined} testid="est-local" />
            <StatTile label="disk" value={`${diskGb.toFixed(1)} GB`} caption={saveWs || fromSet ? 'images + window set' : 'images'} testid="est-disk" />
            <StatTile label="HPC" value={`≈ ${hpcH.toFixed(1)} h`} caption="1 GPU node" testid="est-hpc" />
          </StatRow>
          {overLimit
            ? <Callout tone="amber" icon="hourglass" testid="over-limit">over the {ESTIMATE_MODEL.localLimitH} h local limit · Train locally is off <InfoTip title="Local limit">Local training is allowed when the estimate is ≤ 2 h (Settings › Compute & HPC › local limits).</InfoTip></Callout>
            : <Callout tone="green" icon="check-circle" testid="within-limit">within the {ESTIMATE_MODEL.localLimitH} h local limit · Train locally is available</Callout>}
          {showScript ? (
            <div ref={scriptRef} style={{ borderRadius: 8 }}>
              <CodeBlock title="SLURM script" code={script} filename={`${session.name}.sh`} testid="slurm-script" />
            </div>
          ) : (
            <Button variant="link" icon="chevron-right" onClick={() => setScriptOpen(true)} testid="show-script">Show SLURM script</Button>
          )}
          <h4 style={{ marginTop: 4 }}>After submitting</h4>
          {isSubmitted && <Callout tone="green" icon="check-circle" testid="submitted" action={<Button size="sm" icon="external" onClick={() => navigate(`jobs/cluster/${submittedJob}`)}>Open in Jobs</Button>}>{submittedJob} added to Jobs · script created, not submitted yet</Callout>}
          <div className="m-after-row"><Icon name={isSubmitted ? 'check-circle' : 'eye-off'} size={15} style={{ color: isSubmitted ? 'var(--green)' : 'var(--muted)' }} />
            <div><div>Creating the script adds the job to Jobs</div><div className="d">mark it submitted / running / finished there</div></div></div>
          <div className="m-after-row"><Icon name="inbox" size={15} style={{ color: 'var(--muted)' }} />
            <div><div>Results return through Jobs › Manifest inbox</div><div className="d">checked against this launch, then imported</div></div></div>
        </div>
      </div>
    </>
  )
}

/* ------------------------------------------------ session name chip (inline rename) ------------------------------------------------ */
function SessionChip({ name, saved, onRename }: { name: string; saved: boolean; onRename: (n: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(name)
  const err = !draft.trim() ? 'a session name is required' : !SESSION_RE.test(draft) ? '3–60 letters, digits and _ only' : null
  if (editing) return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} data-testid="session-edit"
      onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); setEditing(false); setDraft(name) } }}>
      <span style={{ display: 'inline-flex', flexDirection: 'column', gap: 2 }}>
        <TextField value={draft} onChange={setDraft} autoFocus width={260} invalid={!!err} variant="outline" testid="session-name" ariaLabel="session name" onEnter={() => { if (!err) { onRename(draft); setEditing(false) } }} />
        {err && <span className="k-field-error" role="alert" data-testid="session-name-error"><Icon name="alert-circle" size={11} />{err}</span>}
      </span>
      <Button size="sm" variant="primary" disabled={!!err} disabledReason={err ?? undefined} onClick={() => { onRename(draft); setEditing(false) }} testid="session-save">Save</Button>
      <Button size="sm" variant="ghost" onClick={() => { setEditing(false); setDraft(name) }}>Cancel</Button>
    </span>
  )
  return (
    <button type="button" className="m-tool-chip btn strong" onClick={() => { setDraft(name); setEditing(true) }} data-testid="session-chip" title="rename this training session">
      <Icon name="cpu" size={14} />{name}<Icon name="pencil" size={12} style={{ color: 'var(--muted)' }} />{!saved && <span className="m-muted m-small" style={{ fontWeight: 400 }}>unsaved</span>}
    </button>
  )
}

/* ------------------------------------------------ split strip ------------------------------------------------ */
function SplitStrip({ channels, hours, test, val }: { channels: string[]; hours: number; test: number; val: number }) {
  const nBlocks = test % 10 === 0 && val % 10 === 0 ? 10 : 20
  const nTest = Math.round(test / 100 * nBlocks), nVal = Math.round(val / 100 * nBlocks)
  const blockS = hours * 3600 / nBlocks
  const rows = channels.slice(0, 10).map(ch => {
    const frame = nBlocks === 10 && test === 20 && val === 10 ? FRAME_SPLIT_BLOCKS[ch] : undefined
    let testIdx: number[], valIdx: number[]
    if (frame) { testIdx = frame.test.map(b => b - 1); valIdx = frame.val.map(b => b - 1) }
    else {
      const r = seeded([...ch].reduce((a, c) => a * 31 + c.charCodeAt(0), 7) + nBlocks + test * 3 + val)
      const order = Array.from({ length: nBlocks - 2 }, (_, i) => i + 2).sort(() => r() - 0.5)
      testIdx = order.slice(0, nTest); valIdx = order.slice(nTest, nTest + nVal)
    }
    return {
      label: ch,
      segments: Array.from({ length: nBlocks }, (_, b) => {
        const kind = testIdx.includes(b) ? 'test' as const : valIdx.includes(b) ? 'validation' as const : 'train' as const
        return { start: b * blockS, end: (b + 1) * blockS, kind, label: `${ch} · block ${b + 1} · ${(b * blockS / 3600).toFixed(1)}–${((b + 1) * blockS / 3600).toFixed(1)} h · ${kind}` }
      }),
    }
  })
  if (!rows.length) return <div className="m-foot-line" data-testid="split-strip-empty" style={{ padding: '10px 0' }}>no sources · nothing to split</div>
  return (
    <div data-testid="split-strip">
      <BandStrip rows={rows} domain={[0, hours * 3600]} rowHeight={12} gap={5} labelWidth={70} segmentGap={3}
        legend={[{ label: 'train', colour: '#a8c1ec' }, { label: 'validation', colour: '#fdc77e' }, { label: 'test — scored once, after training', colour: '#86d69e' }]} />
      {channels.length > 10 && <div className="m-foot-line">showing 10 of {channels.length} channels</div>}
    </div>
  )
}
