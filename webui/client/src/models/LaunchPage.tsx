/* models.launch (spec §7b.1, P11, P18, P19; fixup-ab). Train ONE paired job over the core's paired training job
 * (`Working/training/`): a window set pooled across the channels of one recording, saved with its blocked split; arm A
 * the human labels, arm B one clustering of the pooled training windows at a cut the researcher chooses and a
 * translation table written before any test score; one random forest for both; the label-shuffle null; three exams
 * reported separately — the held-out recording a slot that stays locked. Every number on this page is read from the
 * bridge (`/api/models/*`); nothing here is a fixture. */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BandStrip, Button, Callout, Checkbox, Checklist, CodeBlock, Dropdown, Icon, InfoTip, NumberField, Page, Popover, ProgressBar,
  SectionCard, Seg, StatRow, StatTile, TextField, fmtInt, useQueryState, type CheckState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, setQuery } from '../state'
import { useSourced } from '../api/seam'
import { getJob, type JobRow } from '../api'
import {
  checkPairedJob, getModelsSetup, proposeCut, savePooledWindowSet, slurmPairedJob, trainPairedJob,
  type ChecksResult, type ModelsSetup, type PooledSetRow, type Proposal, type RecipeBody, type SlurmResult,
} from '../api/models'
import { ArmBadge, Loading, LoadFailed, ModelsTabs, JobsPageLink } from './chrome'

const NAME_RE = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/
type Role = 'train' | 'exam' | 'off'

export function LaunchPage() {
  const setup = useSourced(getModelsSetup, [])
  return (
    <>
      <Header workspace="Models" page="Launch" subtitle="one paired job · arm A manual labels vs arm B cluster labels" />
      <Page testid="models-launch">
        {setup.error ? <LoadFailed what="the training setup" error={setup.error} onRetry={setup.reload} />
          : !setup.data ? <Loading /> : <LaunchBody setup={setup.data} reload={setup.reload} />}
      </Page>
    </>
  )
}

function fmtDur(s: number) {
  if (!isFinite(s)) return '—'
  if (s < 90) return `${Math.round(s)} s`
  if (s < 5400) return `${Math.round(s / 60)} min`
  return `${(s / 3600).toFixed(1)} h`
}

/** Poll one job until it ends. */
function useJob(jobId: number | null, onEnd?: (j: JobRow) => void) {
  const [job, setJob] = useState<JobRow | null>(null)
  const endRef = useRef(onEnd); endRef.current = onEnd
  useEffect(() => {
    if (jobId == null) { setJob(null); return }
    let alive = true
    const tick = () => getJob(jobId).then(j => {
      if (!alive) return
      setJob(j)
      if (['completed', 'failed', 'cancelled'].includes(j.status)) endRef.current?.(j)
      else window.setTimeout(tick, 800)
    }, e => { if (alive) { console.error('job poll failed', e); window.setTimeout(tick, 2000) } })
    tick()
    return () => { alive = false }
  }, [jobId])
  return job
}

function LaunchBody({ setup, reload }: { setup: ModelsSetup; reload: () => void }) {
  const { push } = useToast()
  const d = setup.defaults
  /* ---------------- template ---------------- */
  const onGrid = setup.templates.filter(t => t.on_label_grid)
  const [templateQ, setTemplateQ] = useQueryState('template', (onGrid[0] ?? setup.templates[0])?.name ?? '')
  const template = setup.templates.find(t => t.name === templateQ) ?? setup.templates[0]

  /* ---------------- sources ---------------- */
  const [recQ, setRecQ] = useQueryState('rec', setup.recordings[0]?.source_file ?? '')
  const rec = setup.recordings.find(r => r.source_file === recQ) ?? setup.recordings[0]
  const defaultRoles = useMemo<Record<number, Role>>(() => {
    const out: Record<number, Role> = {}
    const chans = (rec?.channels ?? []).filter(c => c.verdicts > 0)
    chans.forEach((c, i) => { out[c.channel] = chans.length >= 8 && i >= chans.length - 4 ? 'exam' : 'train' })
    return out
  }, [rec])
  const [roles, setRoles] = useState<Record<number, Role>>(defaultRoles)
  useEffect(() => setRoles(defaultRoles), [defaultRoles])
  const trainCh = Object.entries(roles).filter(([, r]) => r === 'train').map(([c]) => Number(c)).sort((a, b) => a - b)
  const examCh = Object.entries(roles).filter(([, r]) => r === 'exam').map(([c]) => Number(c)).sort((a, b) => a - b)

  /* ---------------- split (saved WITH the set) ---------------- */
  const [testPct, setTestPct] = useState(String(Math.round(d.split.test_frac * 100)))
  const [valPct, setValPct] = useState(String(Math.round(d.split.validation_frac * 100)))
  const [gapW, setGapW] = useState(String(d.split.gap_windows))
  const stem = (rec?.source_file ?? 'rec').replace(/\.mat$/i, '').replace(/[^A-Za-z0-9_]/g, '_')
  const [wsName, setWsName] = useState(`ws_${stem}_${trainCh.length}tr${examCh.length}ex`)
  useEffect(() => setWsName(`ws_${stem}_${trainCh.length}tr${examCh.length}ex`), [stem, trainCh.length, examCh.length])
  const wsNameError = !NAME_RE.test(wsName) ? 'letters, digits, _ . - only (no spaces), up to 64' : null

  /* ---------------- the chosen saved set ---------------- */
  const [setQ, setSetQ] = useQueryState('set', setup.window_sets[0] ? String(setup.window_sets[0].id) : '')
  const chosen: PooledSetRow | undefined = setup.window_sets.find(w => String(w.id) === setQ)
  const [saveJobId, setSaveJobId] = useState<number | null>(null)
  const saveJob = useJob(saveJobId, j => {
    setSaveJobId(null)
    if (j.status === 'completed') {
      const r = j.result as { window_set_id: number; name: string; version: number; n_windows: number }
      push({ text: `${r.name} v${r.version} saved · ${fmtInt(r.n_windows)} windows across ${trainCh.length + examCh.length} channels` })
      setQuery({ set: String(r.window_set_id), k: null }, true)
      reload()
    } else push({ text: `saving the window set ${j.status}: ${j.error?.message ?? ''}`, kind: 'error' })
  })
  const saveSet = () => {
    if (!rec) return
    savePooledWindowSet({
      name: wsName, source_file: rec.source_file, channels: trainCh, exam_channels: examCh,
      length: template?.length ?? d.length, grid: template?.grid ?? d.grid, stages: template?.stages?.length ? template.stages : d.stages,
      split: { n_blocks: d.split.n_blocks, test_frac: Number(testPct) / 100, validation_frac: Number(valPct) / 100, gap_windows: Number(gapW) },
      template: template?.name,
    }).then(j => setSaveJobId(j.job_id), e => push({ text: `could not save: ${e.message}`, kind: 'error' }))
  }

  /* ---------------- arm B: the cut ---------------- */
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [proposing, setProposing] = useState(false)
  const [proposeError, setProposeError] = useState<string | null>(null)
  const [kQ, setKQ] = useQueryState('k', '')
  const [translation, setTranslation] = useState<Record<string, string> | null>(null)
  useEffect(() => { setProposal(null); setTranslation(null); setProposeError(null) }, [chosen?.id])
  const propose = () => {
    if (!chosen) return
    setProposing(true); setProposeError(null)
    proposeCut(chosen.id, 2, 8).then(p => {
      setProposal(p); setProposing(false)
      const k = kQ ? Number(kQ) : p.suggested_k
      if (k) { setKQ(String(k)); setTranslation(p.by_k.find(r => r.k === k)?.translation ?? null) }
    }, e => { setProposing(false); setProposeError(e.message) })
  }
  const k = kQ ? Number(kQ) : null
  const cut = proposal?.by_k.find(r => r.k === k) ?? null
  const chooseK = (v: number) => { setKQ(String(v)); setTranslation(proposal?.by_k.find(r => r.k === v)?.translation ?? null) }
  const frozen = chosen?.runs.find(r => r.status === 'completed')

  /* ---------------- options ---------------- */
  const [shuffles, setShuffles] = useState(d.rf_shuffles)
  const [boot, setBoot] = useState(d.bootstrap_n)
  const [trees, setTrees] = useState(template?.n_estimators ?? d.n_estimators)
  const [reference, setReference] = useState(false)

  const body: RecipeBody | null = chosen ? {
    window_set_id: chosen.id, k, translation: translation ?? undefined, n_estimators: trees, rf_shuffles: shuffles,
    bootstrap_n: boot, full_shuffles: d.full_shuffles, block_hours: d.block_hours, reference,
  } : null

  /* ---------------- checks + estimate (from the bridge) ---------------- */
  const [checks, setChecks] = useState<ChecksResult | null>(null)
  const [checksError, setChecksError] = useState<string | null>(null)
  const bodyKey = JSON.stringify(body)
  useEffect(() => {
    if (!body) { setChecks(null); return }
    let alive = true
    const t = window.setTimeout(() => checkPairedJob(body).then(r => { if (alive) { setChecks(r); setChecksError(null) } },
      e => { if (alive) setChecksError(e.message) }), 250)
    return () => { alive = false; window.clearTimeout(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bodyKey])

  /* ---------------- train / script ---------------- */
  const [trainJobId, setTrainJobId] = useQueryState('job', '')
  const trainJob = useJob(trainJobId ? Number(trainJobId) : null, j => { if (j.status === 'completed') reload() })
  const [slurm, setSlurm] = useState<SlurmResult | null>(null)
  const errors = checks?.checks.filter(c => c.level === 'error') ?? []
  const launchReason = !chosen ? 'save or pick a window set first' : k == null ? "choose arm B's cut (Propose cuts)" : errors.length ? `fix first: ${errors[0].name}` : !checks ? 'checking…' : null
  const overLimit = checks?.estimate.where === 'slurm'
  const busy = !!trainJob && ['queued', 'running'].includes(trainJob.status)
  const localReason = launchReason ?? (overLimit ? `over the ${fmtDur(setup.local_limit_s)} local limit · ≈ ${fmtDur(checks!.estimate.seconds)}` : busy ? 'already training' : null)
  const train = () => { if (body) trainPairedJob(body).then(j => setTrainJobId(String(j.job_id)), e => push({ text: `training refused: ${e.message}`, kind: 'error' })) }
  const makeScript = () => { if (body) slurmPairedJob(body).then(setSlurm, e => push({ text: `no script: ${e.message}`, kind: 'error' })) }
  const m4Ref = useRef<HTMLButtonElement>(null)
  const [m4Open, setM4Open] = useState(false)

  const checkItems = (checks?.checks ?? []).map(c => ({ id: c.name, label: `${c.name} · ${c.detail}`, state: (c.level === 'error' ? 'fail' : c.level) as CheckState }))
  const byRole = chosen?.coverage.by_role ?? checks?.by_role
  const warnBelow = d.test_warn_below

  return (
    <>
      <div className="m-toolbar" data-testid="launch-toolbar">
        <span className="m-tool-chip strong"><Icon name="cpu" size={14} />{chosen ? `${chosen.name} v${chosen.version}` : 'no window set yet'}</span>
        <span className="k-spacer" />
        <span className="m-tool-chip" data-testid="null-chip"><span className="m-dot" style={{ background: 'var(--green)' }} /><span className="muted">null</span> label shuffle · RF {shuffles}×
          <InfoTip title="Null">Each arm's training labels are shuffled and the forest refitted, {shuffles} times; the arm's macro F1 is set against that spread. The arm's full model is the random forest (Q42), so these are also its full-model shuffles; the 5 full-model shuffles of spec §9.4 apply when the CNN arm exists.</InfoTip></span>
        <span className={`m-tool-chip ${overLimit ? 'amber' : 'grey'}`} data-testid="estimate-chip"><Icon name="hourglass" size={13} />{checks ? `≈ ${fmtDur(checks.estimate.seconds)} ${overLimit ? `above the ${fmtDur(setup.local_limit_s)} limit` : 'local'}` : 'estimate after a set is chosen'}</span>
        {busy && trainJob ? (
          <span className="row" style={{ gap: 8, display: 'inline-flex', alignItems: 'center' }} data-testid="train-progress">
            <ProgressBar value={((trainJob.progress as any)?.done ?? 0) / Math.max(1, (trainJob.progress as any)?.total ?? 6)} width={180}
              label={`${(trainJob.meta as any)?.stage ?? 'running'} · ${(trainJob.progress as any)?.message ?? ''}`} />
          </span>
        ) : (
          <Button icon="play" variant={overLimit ? 'default' : 'primary'} disabled={!!localReason} disabledReason={localReason ?? undefined} onClick={train} testid="train-locally">Train locally</Button>
        )}
        <Button icon="file" variant={overLimit ? 'cluster' : 'default'} disabled={!!launchReason} disabledReason={launchReason ?? undefined} onClick={makeScript} testid="create-slurm">Create SLURM script</Button>
      </div>

      <ModelsTabs current="launch" jobsLink={<JobsPageLink />} />

      {trainJob?.status === 'failed' && <Callout tone="red" title={`Training job ${trainJob.job_id} failed`} testid="train-failed">{trainJob.error?.message}</Callout>}
      {trainJob?.status === 'completed' && (
        <Callout tone="green" title={`Training job ${trainJob.job_id} finished`} testid="train-done"
          action={<Button size="sm" variant="primary" icon="bar-chart" onClick={() => navigate(`models/results/${(trainJob.result as any)?.run_id}`)} testid="open-results">Open Results</Button>}>
          run {(trainJob.result as any)?.run_id} · macro F1 on exam (i): A {(trainJob.result as any)?.macro_f1?.A?.toFixed(3) ?? '—'} · B {(trainJob.result as any)?.macro_f1?.B?.toFixed(3) ?? '—'}
        </Callout>)}

      <div className="m-cols">
        <div className="m-stack">
          <SectionCard number={1} title="Training template" subtitle="its window matrix sets the windows and features" testid="launch-template"
            info="A training template from Analyse. The paired job takes the window length, step and feature stages of its window-matrix step; both arms then train the same random forest (Q42)."
            actions={<Button variant="link" icon="external" onClick={() => navigate('analyse/chain')} testid="open-in-analyse">Open in Analyse</Button>}>
            <div className="m-foot-line" style={{ marginBottom: 8 }}>
              <Dropdown value={template?.name ?? ''} onChange={v => setTemplateQ(v)} active width={240} testid="template-select" ariaLabel="training template"
                options={setup.templates.map(t => ({ value: t.name, label: t.name, description: t.on_label_grid ? `${t.length}/${t.grid} · ${t.stages.join(' + ')}` : 'off the labels’ grid' }))} />
              {template && <span className={`k-chip sm ${template.on_label_grid ? 'green' : 'red'}`} data-testid="grid-chip">{template.on_label_grid ? `on the labels' grid · ${template.length} samples, step ${template.grid}` : 'off the labels’ grid'}</span>}
            </div>
            {template && <div className="m-foot-line" data-testid="template-steps">{template.steps.join(' → ')} · features {template.stages.join(', ') || '—'}</div>}
            {template && !template.on_label_grid && <Callout tone="red" testid="template-off-grid">{template.reason}</Callout>}
          </SectionCard>

          <SectionCard number={2} title="Sources · channels" testid="launch-sources"
            subtitle="train = split by time within the channel · exam = never trained on (exam ii)"
            info="One window set pooled across these channels: the labels' grid, labelled-first non-overlap, labelled windows only. A training channel is cut into blocks by time; the last blocks are its test block (exam i). An exam channel is scored, never trained on (exam ii).">
            <div className="m-foot-line" style={{ marginBottom: 8 }}>
              <Dropdown prefix="recording" value={rec?.source_file ?? ''} onChange={v => setRecQ(v)} width={300} testid="recording-select"
                options={setup.recordings.map(r => ({ value: r.source_file, label: r.name, description: r.source_file }))} />
              <button ref={m4Ref} type="button" className="m-lock-toggle" role="switch" aria-checked={false} aria-disabled onClick={() => setM4Open(o => !o)} data-testid="m4-toggle" title={`${setup.held_out.name} is held out`}>
                <span className="sw" />{setup.held_out.name} locked · {setup.held_out.where}
              </button>
              <Popover open={m4Open} onClose={() => setM4Open(false)} anchorRef={m4Ref} placement="bottom-end" title={`${setup.held_out.name} is held out`} width={320} testid="m4-popover">
                <div className="m-small" style={{ lineHeight: 1.45 }}>{setup.held_out.reason}</div>
                <div style={{ marginTop: 8 }}><Button size="sm" icon="lock" onClick={() => navigate('settings/datasets')}>Settings › Datasets</Button></div>
              </Popover>
            </div>
            {!rec ? <Callout tone="amber" testid="no-recordings">No recording has human verdicts yet: Review or import labels first.</Callout> : (
              <table className="m-table" data-testid="source-channels">
                <thead><tr><th>channel</th><th>role</th><th>hours</th><th>human verdicts</th><th>interesting / not</th><th>artifact</th></tr></thead>
                <tbody>
                  {rec.channels.map(c => (
                    <tr key={c.channel} className={c.verdicts ? undefined : 'dim'} data-testid={`source-row-${c.channel}`}>
                      <td style={{ color: 'var(--text)' }}>{c.name}</td>
                      <td><Seg size="sm" value={roles[c.channel] ?? 'off'} onChange={v => setRoles(r => ({ ...r, [c.channel]: v }))} testid={`role-${c.channel}`} ariaLabel={`${c.name} role`}
                        options={[{ value: 'train', label: 'train', disabled: !c.verdicts, reason: 'no human verdicts on this channel' }, { value: 'exam', label: 'exam', disabled: !c.verdicts, reason: 'no human verdicts on this channel' }, { value: 'off', label: 'off' }]} /></td>
                      <td>{c.hours} h</td>
                      <td>{fmtInt(c.verdicts)}</td>
                      <td>{fmtInt(c.interesting)} / {fmtInt(c.not_interesting)}</td>
                      <td>{fmtInt(c.artifact)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="m-foot-line" style={{ marginTop: 8, flexWrap: 'wrap' }}>
              <Dropdown prefix="test" value={testPct} onChange={setTestPct} testid="test-pct" options={['10', '20', '30'].map(v => ({ value: v, label: `${v} %` }))} />
              <Dropdown prefix="validation" value={valPct} onChange={setValPct} testid="val-pct" options={['0', '10', '20'].map(v => ({ value: v, label: `${v} %` }))} />
              <Dropdown prefix="gap" value={gapW} onChange={setGapW} testid="gap-select" options={[{ value: '1', label: '≥ 1 window' }, { value: '2', label: '≥ 2 windows' }]} />
              <span className="m-muted">of {d.split.n_blocks} blocks per channel, the last ones held out</span>
            </div>
            <div className="m-foot-line" style={{ marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
              <span style={{ display: 'inline-flex', flexDirection: 'column', gap: 2 }}>
                <TextField value={wsName} onChange={setWsName} icon="save" width={260} invalid={!!wsNameError} testid="ws-name" ariaLabel="window-set name" />
                {wsNameError && <span className="k-field-error" role="alert"><Icon name="alert-circle" size={11} />{wsNameError}</span>}
              </span>
              <Button icon="save" variant={chosen ? 'default' : 'primary'} onClick={saveSet} testid="save-ws"
                disabled={!!wsNameError || !trainCh.length || !template?.on_label_grid || saveJobId != null}
                disabledReason={!trainCh.length ? 'mark at least one channel train' : !template?.on_label_grid ? 'the template is off the labels’ grid' : wsNameError ?? (saveJobId != null ? 'saving…' : undefined)}>Save window set</Button>
              <span>{trainCh.length} train · {examCh.length} exam · split and gap saved with the set</span>
            </div>
            {saveJob && ['queued', 'running'].includes(saveJob.status) && (
              <div style={{ marginTop: 6 }} data-testid="save-progress"><ProgressBar value={((saveJob.progress as any)?.done ?? 0) / Math.max(1, (saveJob.progress as any)?.total ?? 1)} width={320} label={(saveJob.progress as any)?.message ?? 'measuring'} /></div>
            )}
            {setup.window_sets.length > 0 && (
              <table className="m-table" style={{ marginTop: 10 }} data-testid="source-windowsets">
                <thead><tr><th style={{ width: 24 }} /><th>saved set</th><th>channels</th><th>windows · train / val / test / exam</th><th>runs</th></tr></thead>
                <tbody>
                  {setup.window_sets.map(w => {
                    const on = String(w.id) === setQ
                    const br = w.coverage.by_role
                    return (
                      <tr key={w.id} className="m-row-click" onClick={() => setQuery({ set: String(w.id), k: null }, true)} data-testid={`ws-row-${w.name}`}>
                        <td><input type="radio" name="launch-windowset" checked={on} onChange={() => setQuery({ set: String(w.id), k: null }, true)} aria-label={`${w.name} v${w.version}`} /></td>
                        <td style={{ color: 'var(--text)' }}>{w.name} · v{w.version}</td>
                        <td>{w.members.filter(m => m.role === 'train').length} train · {w.members.filter(m => m.role === 'exam').length} exam</td>
                        <td>{fmtInt(w.n_windows)} · {fmtInt(br.train?.n ?? 0)} / {fmtInt(br.validation?.n ?? 0)} / {fmtInt(br.test?.n ?? 0)} / {fmtInt(br.exam?.n ?? 0)}</td>
                        <td>{w.runs.length ? `${w.runs.length} · k = ${w.runs[0].k}` : '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </SectionCard>

          <SectionCard number={3} title="Label arms" subtitle="paired — same windows, same forest, same seed; only the labels differ" testid="launch-arms"
            info="Arm A: the human verdicts by containment (catalogue.manual_labels). Arm B: one Ward clustering of the pooled TRAINING windows of every training channel, cut at k; test windows take no part. Both train a random forest on the windows labelled in every arm.">
            <div className="m-stack" style={{ gap: 6 }}>
              <div className="m-arm-row" data-testid="arm-row-a"><ArmBadge letter="A" /><span className="nm">manual labels</span><span className="src">human verdicts · interesting vs not_interesting</span>
                <span className="cnt">{byRole ? `${fmtInt(byRole.train?.n ?? 0)} training windows` : '—'}</span></div>
              <div className="m-arm-row" data-testid="arm-row-b"><ArmBadge letter="B" /><span className="nm">cluster labels</span>
                <span className="src">{k ? `Ward · k = ${k}${cut ? ` · ${cut.effective_k} real cluster(s)` : ''}` : 'choose a cut'}</span>
                <Button size="sm" icon="layers" onClick={propose} disabled={!chosen || proposing} disabledReason={!chosen ? 'save or pick a window set first' : 'clustering…'} testid="propose-cuts">{proposing ? 'Clustering…' : 'Propose cuts'}</Button></div>
              <div className="m-arm-row" data-testid="arm-row-rf"><ArmBadge letter="RF" /><span className="nm">random forest</span><span className="src">the classifier of both arms (Q42) — so it is also each arm's baseline</span>
                <span className="cnt" title="the CNN arm is a later cluster job">CNN arm: later</span></div>
              {frozen && <Callout tone="blue" icon="lock" testid="cut-frozen">Run {frozen.run_id} scored this set's test block at k = {frozen.k}. The cut is frozen on this set: another k is refused (that would be tuning on the test block).</Callout>}
              {proposeError && <Callout tone="red" testid="propose-error">{proposeError}</Callout>}
              {proposal && (
                <div data-testid="cut-table">
                  <div className="m-foot-line" style={{ marginBottom: 4 }}>{fmtInt(proposal.n_windows_clustered)} training windows clustered · {proposal.suggestion_rule}</div>
                  <table className="m-table">
                    <thead><tr><th /><th>k</th><th>silhouette</th><th>sizes</th><th>real clusters</th></tr></thead>
                    <tbody>{proposal.by_k.map(r => (
                      <tr key={r.k} className="m-row-click" onClick={() => chooseK(r.k)} data-testid={`cut-${r.k}`}>
                        <td><input type="radio" name="launch-k" checked={r.k === k} onChange={() => chooseK(r.k)} aria-label={`k = ${r.k}`} /></td>
                        <td>{r.k}{r.k === proposal.suggested_k && <span className="k-chip sm blue" style={{ marginLeft: 6 }}>draft</span>}</td>
                        <td>{r.silhouette == null ? '—' : r.silhouette.toFixed(3)}</td>
                        <td className="m-mono">{Object.values(r.sizes).join(' / ')}</td>
                        <td>{r.effective_k}{r.small_clusters.length ? <span className="m-muted"> + {r.small_clusters.length} speck(s)</span> : null}</td>
                      </tr>))}</tbody>
                  </table>
                </div>
              )}
              {cut && translation && (
                <div data-testid="translation-table">
                  <div className="m-foot-line" style={{ margin: '6px 0 4px' }}>
                    translation table — written into the recipe before any test score <InfoTip title="Translation">Yardstick (A) scores arm B against the human verdicts through this table. Majority on the training windows is the draft; change it now — once a run has a test score the cut and table are frozen on this set.</InfoTip>
                  </div>
                  <table className="m-table">
                    <thead><tr><th>cluster</th><th>windows</th><th>not_interesting</th><th>interesting</th><th>purity</th><th>translated to</th></tr></thead>
                    <tbody>{cut.purity.map(p => (
                      <tr key={p.cluster} data-testid={`map-${p.cluster}`}>
                        <td>{p.cluster}{cut.small_clusters.includes(p.cluster) && <span className="m-muted"> speck</span>}</td>
                        <td>{fmtInt(p.n)}</td>
                        <td>{fmtInt(cut.contingency[p.cluster - 1][0])}</td>
                        <td>{fmtInt(cut.contingency[p.cluster - 1][1])}</td>
                        <td>{p.purity == null ? '—' : `${Math.round(p.purity * 100)} %`}{p.impure && <span className="k-chip amber sm" style={{ marginLeft: 6 }} data-testid="impure-chip">impure</span>}</td>
                        <td><Dropdown size="sm" value={translation[String(p.cluster)]} onChange={v => setTranslation(t => ({ ...(t ?? {}), [String(p.cluster)]: v }))} testid={`translate-${p.cluster}`}
                          options={[{ value: 'interesting', label: 'interesting' }, { value: 'not_interesting', label: 'not_interesting' }]} /></td>
                      </tr>))}</tbody>
                  </table>
                </div>
              )}
            </div>
          </SectionCard>

          <SectionCard number={4} title="Evaluation" testid="launch-evaluation"
            subtitle="blocked by time within each channel · scored once, after training"
            info="Three exams, never pooled: (i) the later time block of each training channel, (ii) channels never trained on, (iii) the held-out recording — locked until the researcher unlocks it after the freeze.">
            {chosen ? (
              <>
                <SplitStrip set={chosen} />
                <div className="m-counts" style={{ marginTop: 10 }} data-testid="class-counts">
                  <span className="h">windows</span><span className="h">interesting</span><span className="h">not_interesting</span><span />
                  {(['train', 'validation', 'test', 'exam'] as const).map(r => {
                    const c = byRole?.[r]; const low = (r === 'test' || r === 'exam') && c && c.n > 0 && Math.min(c.interesting, c.not_interesting) < warnBelow
                    return (
                      <div key={r} style={{ display: 'contents' }}>
                        <span style={{ textAlign: 'right', paddingRight: 16 }}>{r}</span>
                        <span className={low && (c?.interesting ?? 0) < warnBelow ? 'm-amber-text' : undefined}>{fmtInt(c?.interesting ?? 0)}</span>
                        <span className={low && (c?.not_interesting ?? 0) < warnBelow ? 'm-amber-text' : undefined}>{fmtInt(c?.not_interesting ?? 0)}</span>
                        <span>{low && <span className="k-chip amber sm" data-testid={`low-${r}`}>&lt; {warnBelow} in a class</span>}</span>
                      </div>
                    )
                  })}
                </div>
                <div className="m-foot-line" style={{ marginTop: 8 }} data-testid="exam-iii">exam (iii) · {setup.held_out.name}: locked — {setup.held_out.where}</div>
              </>
            ) : <div className="m-foot-line" data-testid="split-strip-empty">save or pick a window set to see its split</div>}
          </SectionCard>

          <SectionCard number={5} title="Options" testid="launch-options" info="The forest's size and seed are shared by both arms. The null and the bootstrap only change how precisely the numbers are known, not the numbers themselves.">
            <div className="m-foot-line" style={{ flexWrap: 'wrap' }}>
              <NumberField value={trees} onValid={setTrees} min={10} max={2000} integer unit="trees" width={120} testid="n-trees" ariaLabel="trees per forest" />
              <NumberField value={shuffles} onValid={setShuffles} min={0} max={5000} integer unit="shuffles" width={140} testid="rf-shuffles" ariaLabel="label shuffles" />
              <NumberField value={boot} onValid={setBoot} min={100} max={20000} integer unit="bootstrap" width={150} testid="bootstrap-n" ariaLabel="bootstrap draws" />
              <Checkbox checked={reference} onChange={setReference} label="score the existing MODELS/ as a reference line (slow: CNNs on CPU)" testid="reference-toggle" />
            </div>
          </SectionCard>
        </div>

        <div className="k-card m-rcard" data-testid="launch-right">
          <h4>Before launch <InfoTip title="Before launch">Read from the bridge: the same checks the job runs before it starts. An error disables both launch buttons and names itself.</InfoTip></h4>
          {checksError ? <Callout tone="red" testid="checks-error">{checksError}</Callout>
            : checkItems.length ? <Checklist items={checkItems} testid="before-launch" />
              : <div className="m-foot-line" data-testid="before-launch-empty">save or pick a window set, then choose a cut</div>}
          <hr />
          <h4>Estimate</h4>
          {checks ? (
            <>
              <StatRow columns={3}>
                <StatTile label="here" value={`≈ ${fmtDur(checks.estimate.seconds)}`} caption={`${checks.estimate.n_fits} forest fits`} tone={overLimit ? 'amber' : undefined} testid="est-local" />
                <StatTile label="per fit" value={`${checks.estimate.seconds_per_fit.toFixed(2)} s`} caption="measured here" testid="est-fit" />
                <StatTile label="recipe" value={checks.recipe_hash} caption="reproducible from it" testid="est-hash" />
              </StatRow>
              {overLimit
                ? <Callout tone="amber" icon="hourglass" testid="over-limit">over the {fmtDur(setup.local_limit_s)} local limit · Train locally is off — create the SLURM script</Callout>
                : <Callout tone="green" icon="check-circle" testid="within-limit">within the {fmtDur(setup.local_limit_s)} local limit · Train locally is available</Callout>}
            </>
          ) : <div className="m-foot-line">—</div>}
          {slurm && (
            <>
              <CodeBlock title="SLURM script (CPU)" code={slurm.script} filename={slurm.script_path.split(/[\\/]/).pop()} testid="slurm-script" />
              {slurm.warnings.map(w => <Callout key={w} tone="amber" testid="slurm-warning">{w}</Callout>)}
            </>
          )}
          <Callout tone="blue" icon="info" testid="hpc-note">{setup.hpc_note}</Callout>
          <h4 style={{ marginTop: 4 }}>Runs</h4>
          {setup.runs.length ? (
            <table className="m-table" data-testid="runs-table">
              <thead><tr><th>run</th><th>set</th><th>k</th><th>status</th><th>F1 A / B</th></tr></thead>
              <tbody>{setup.runs.slice(0, 8).map(r => (
                <tr key={r.run_id} className="m-row-click" onClick={() => navigate(`models/results/${r.run_id}`)} data-testid={`run-row-${r.run_id}`}>
                  <td>{r.run_id}</td><td>{r.window_set?.name}</td><td>{r.k}</td><td>{r.status}</td>
                  <td>{r.macro_f1 ? `${r.macro_f1.A.toFixed(3)} / ${r.macro_f1.B.toFixed(3)}` : '—'}</td>
                </tr>))}</tbody>
            </table>
          ) : <div className="m-foot-line" data-testid="runs-empty">no paired run yet</div>}
        </div>
      </div>
    </>
  )
}

/* ------------------------------------------------ split strip: each channel's blocks ------------------------------------------------ */
function SplitStrip({ set }: { set: PooledSetRow }) {
  const s = set.split as { n_blocks: number; test_frac: number; validation_frac: number }
  const nB = s.n_blocks || 10
  const nT = Math.max(1, Math.round(nB * (s.test_frac ?? 0.2)))
  const nV = Math.round(nB * (s.validation_frac ?? 0))
  const rows = set.members.slice(0, 16).map(m => {
    const hours = Number(m.counts?.hours ?? 0) || 1
    const blockS = hours * 3600 / nB
    const name = String(m.counts?.channel ?? m.channel)
    return {
      label: `CH${name}${m.role === 'exam' ? ' ·exam' : ''}`,
      segments: m.role === 'exam'
        ? [{ start: 0, end: hours * 3600, kind: 'test' as const, label: `CH${name} · exam (ii): every window, never trained on` }]
        : Array.from({ length: nB }, (_, b) => {
          const kind = b >= nB - nT ? 'test' as const : b >= nB - nT - nV ? 'validation' as const : 'train' as const
          return { start: b * blockS, end: (b + 1) * blockS, kind, label: `CH${name} · block ${b + 1} · ${kind}` }
        }),
    }
  })
  const maxH = Math.max(1, ...set.members.map(m => Number(m.counts?.hours ?? 0)))
  return (
    <div data-testid="split-strip">
      <BandStrip rows={rows} domain={[0, maxH * 3600]} rowHeight={10} gap={4} labelWidth={84} segmentGap={2}
        legend={[{ label: 'train', colour: '#a8c1ec' }, { label: 'validation', colour: '#fdc77e' }, { label: 'test / exam — scored once', colour: '#86d69e' }]} />
    </div>
  )
}
