/* fixup-ag seam (iii) — Models › Launch, arm **B.2 cluster labels · trace shape**, opened PREFILLED by Analyse's
 * *Train model*: the template, the pool as the sources (its recordings, channels and roles shown, not re-entered),
 * section 3 *Label arms* set to B.2 with the cut and the mapping read-only (they are edited in Analyse, where the
 * dendrogram is). *Open in Analyse* opens that chain on that pool. Nothing trains until *Train locally* is pressed.
 * The pool is unlabelled: there is no arm A; the manual-label comparison is AH's reference line. */
import { useEffect, useRef, useState } from 'react'
import { ApiError, getJob, type JobRow } from '../api'
import { getB2Setup, trainB2, type B2Run, type B2Setup } from '../api/shape'
import { createCnnSlurm, fmtBytes, fmtSecs, runCnnSmoke, type CnnSetup, type CnnSlurm, type CnnSmoke, type Encoding } from '../api/cnn'
import { Button, Callout, NumberField, ProgressBar, SectionCard, useQueryState } from '../kit'
import { CopyList, ScriptBlock, Steps } from './HpcScript'
import { ErrorBoundary } from '../shell/ErrorBoundary'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'

const errText = (e: unknown) => e instanceof ApiError ? e.message : String(e)
const ROLES = ['train', 'validation', 'test', 'exam'] as const

export function B2Launch({ template, pool }: { template: number; pool: number }) {
  const [setup, setSetup] = useState<B2Setup | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [nTrees, setNTrees] = useState(300)
  const [jobId, setJobId] = useState<number | null>(null)
  const [job, setJob] = useState<JobRow | null>(null)
  const [busy, setBusy] = useState(false)
  // fixup-ai: the model — the forest (trains here in minutes) or the CNN (a local smoke here, the real run on the cluster)
  const [modelQ, setModelQ] = useQueryState<'forest' | 'cnn'>('model', 'forest')
  const model = modelQ === 'cnn' ? 'cnn' : 'forest'
  const setModel = (m: 'forest' | 'cnn') => setModelQ(m)
  const [enc, setEnc] = useState<Encoding>('fusion')
  const [epochs, setEpochs] = useState<number | null>(null)
  const [withNull, setWithNull] = useState(false)
  const [jobKind, setJobKind] = useState<'forest' | 'smoke' | 'slurm' | null>(null)
  const [slurmOut, setSlurmOut] = useState<CnnSlurm | null>(null)
  const [smokeDone, setSmokeDone] = useState<CnnSmoke | null>(null)
  const toast = useToast()
  const load = () => getB2Setup(template, pool).then(s => { setSetup(s); setErr(null) }).catch(e => setErr(errText(e)))
  useEffect(() => { void load() }, [template, pool])   // eslint-disable-line react-hooks/exhaustive-deps
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])
  useEffect(() => {
    if (jobId === null) return
    const tick = () => getJob(jobId).then(j => {
      if (!alive.current) return
      setJob(j)
      if (['completed', 'failed', 'cancelled'].includes(j.status)) {
        if (j.status === 'completed' && jobKind === 'slurm') setSlurmOut(j.result as unknown as CnnSlurm)
        if (j.status === 'completed' && jobKind === 'smoke') setSmokeDone(j.result as unknown as CnnSmoke)
        void load()
      } else window.setTimeout(tick, 900)
    }, e => { console.error('job poll failed', e); window.setTimeout(tick, 2000) })
    tick()
  }, [jobId])   // eslint-disable-line react-hooks/exhaustive-deps

  if (err) return <div className="error-card" data-testid="b2-error"><h3>arm B.2 could not be set up</h3><div className="mono small">{err}</div><Button size="sm" onClick={() => navigate('analyse/chain')}>Open Analyse › Chain</Button></div>
  if (!setup) return <div className="muted mono small" data-testid="b2-loading">reading the template and the pool…</div>
  const errors = setup.checks.filter(c => c.level === 'error')
  const train = async () => {
    setBusy(true)
    try { const r = await trainB2({ template, pool, n_estimators: nTrees }); setJobKind('forest'); setJobId(r.job_id); toast.push({ text: `B.2 forest started · job ${r.job_id}` }) }
    catch (e) { toast.push({ kind: 'error', text: errText(e) }) } finally { setBusy(false) }
  }
  const cnn: CnnSetup | undefined = setup.cnn
  const cnnBody = () => ({ template, pool, encoding: enc, null: withNull, ...(epochs ? { cnn: { epochs } } : {}) })
  const smoke = async () => {
    setBusy(true); setSmokeDone(null)
    try { const r = await runCnnSmoke({ template, pool, encoding: enc, smoke: {} }); setJobKind('smoke'); setJobId(r.job_id); toast.push({ text: `B.2 CNN local smoke started · job ${r.job_id}` }) }
    catch (e) { toast.push({ kind: 'error', text: errText(e) }) } finally { setBusy(false) }
  }
  const slurm = async () => {
    setBusy(true); setSlurmOut(null)
    try { const r = await createCnnSlurm(cnnBody()); setJobKind('slurm'); setJobId(r.job_id); toast.push({ text: `writing the SLURM script · job ${r.job_id}` }) }
    catch (e) { toast.push({ kind: 'error', text: errText(e) }) } finally { setBusy(false) }
  }
  const running = job && !['completed', 'failed', 'cancelled'].includes(job.status)
  const p = setup.pool
  return (
    <div className="stack" style={{ gap: 12 }} data-testid="b2-launch">
      <Callout tone="blue" title="Prefilled from Analyse · arm B.2 cluster labels · trace shape">
        The template <b>{setup.template.name}</b> (#{setup.template.id}) on the saved pool <b>{p.name} v{p.version}</b>. The cut and the mapping are
        read-only here — they are edited on the Shape clustering page. The pool is unlabelled: there is no arm A.{' '}
        <Button variant="link" size="sm" icon="external" testid="open-in-analyse" onClick={() => navigate(`analyse/chain?template=${setup.template.id}&poolId=${p.id}`)}>Open in Analyse</Button>
      </Callout>

      <SectionCard title="1 · Template" testid="b2-template">
        <div className="mono small">{setup.template.steps.map(s => `${s.stage}.${s.algorithm}`).join(' → ')}</div>
        <div className="muted small">shapes: align {setup.shape.align} · detrend {setup.shape.detrend} · {setup.shape.resample_length} points · noise floor {setup.shape.noise_floor ? 'on' : 'off'} · Ward on {setup.cluster.sample.toLocaleString()} training windows, seed {setup.cluster.seed}</div>
      </SectionCard>

      <SectionCard title="2 · Sources · the pool" testid="b2-sources">
        <div className="mono small">{p.n_windows.toLocaleString()} windows · {ROLES.map(r => `${r} ${(p.by_role[r] ?? 0).toLocaleString()}`).join(' · ')} · key {p.key} · rule {p.rule} · {p.plan.hold_out_pack ? `pack ${p.plan.hold_out_pack} held out` : 'no pack held out'}</div>
        {p.recordings.map(r => (
          <div key={r.source_file} style={{ marginTop: 6 }} data-testid={`b2-recording-${r.source_file}`}>
            <div className="small"><b>{r.name}</b> <span className="muted mono">{r.source_file}</span></div>
            <div className="row" style={{ gap: 4, flexWrap: 'wrap' }}>
              {r.channels.map(ch => <span key={ch.channel} className={`chip ${ch.role === 'exam' ? 'amber' : 'blue'}`} style={{ height: 20, fontSize: 10 }} title={`${ch.n.toLocaleString()} windows`} data-testid={`b2-channel-${ch.role}`}>{ch.name} · {ch.role}</span>)}
            </div>
          </div>
        ))}
      </SectionCard>

      <SectionCard title="3 · Label arms" testid="b2-arms">
        <div className="row" style={{ gap: 8, alignItems: 'baseline' }}><span className="chip blue" data-testid="b2-arm-label">{setup.arm.label}</span><span className="muted small">arm A: none — the pool carries no manual labels</span></div>
        <div className="mono small" style={{ marginTop: 4 }} data-testid="b2-cut">cut k = {setup.arm.k} · Ward · read-only · {setup.arm.where}</div>
        <table className="sh-table" style={{ marginTop: 6 }} data-testid="b2-mapping">
          <thead><tr><th>cluster</th><th>name</th><th>class</th></tr></thead>
          <tbody>{Array.from({ length: setup.arm.k }, (_, i) => String(i + 1)).map(c => { const e = setup.arm.mapping.clusters[c]; return <tr key={c}><td>{c}</td><td>{e?.name || '—'}</td><td>{e?.class ? e.class.replace('_', ' ') : <span style={{ color: 'var(--red)' }}>not mapped</span>}</td></tr> })}</tbody>
        </table>
        {setup.frozen && <div className="error-card" style={{ marginTop: 6, padding: '6px 10px' }} data-testid="b2-frozen"><h3>frozen</h3><div className="small">run {setup.frozen.run_id} has a test score on this pool at k = {setup.frozen.k}: a different cut or mapping is refused.</div></div>}
      </SectionCard>

      <SectionCard title="4 · The model" testid="b2-model">
        <div className="row" style={{ gap: 6, marginBottom: 6 }}>
          <button className={`btn sm ${model === 'forest' ? 'primary' : ''}`} onClick={() => setModel('forest')} data-testid="b2-model-forest" aria-pressed={model === 'forest'}>Random forest</button>
          <button className={`btn sm ${model === 'cnn' ? 'primary' : ''}`} onClick={() => setModel('cnn')} disabled={!cnn} title={cnn ? undefined : 'the bridge offered no CNN arm'} data-testid="b2-model-cnn" aria-pressed={model === 'cnn'}>CNN (fusion / GASF / GADF / recurrence)</button>
        </div>
        {model === 'forest' ? <>
          <div className="small"><b>Random forest</b> on the cluster categories of every training window · inputs: <b>{setup.inputs.features}</b> ({setup.inputs.stages.join(' + ')})</div>
          <div className="muted small" data-testid="b2-inputs-rule">{setup.inputs.rule}</div>
          <div className="row" style={{ gap: 8, alignItems: 'center', marginTop: 6 }}>
            <span className="small">trees</span><NumberField value={nTrees} integer min={10} onValid={v => setNTrees(Math.max(10, Math.round(Number(v) || 300)))} testid="b2-trees" />
            <span className="muted small">class weight {setup.defaults.class_weight} · seed {setup.defaults.random_state}</span>
          </div>
        </> : cnn && <ErrorBoundary label="the CNN settings"><CnnSettings cnn={cnn} enc={enc} setEnc={setEnc} epochs={epochs} setEpochs={setEpochs} withNull={withNull} setWithNull={setWithNull} /></ErrorBoundary>}
      </SectionCard>

      <SectionCard title="Before launch" testid="b2-checks">
        {setup.checks.map(c => <div key={c.name} className="small" style={{ color: c.level === 'error' ? 'var(--red)' : undefined }}>{c.level === 'error' ? '✗' : '✓'} <b>{c.name}</b> — {c.detail}</div>)}
        <div className="row" style={{ gap: 8, marginTop: 8 }}>
          {model === 'forest'
            ? <Button variant="primary" icon="play" onClick={train} disabled={!!errors.length || busy || !!running} disabledReason={errors[0]?.detail ?? 'a job is running'} loading={busy} testid="b2-train-locally">Train locally</Button>
            : <Button variant="primary" icon="play" onClick={smoke} disabled={!!errors.length || busy || !!running} disabledReason={errors[0]?.detail ?? 'a job is running'} loading={busy} testid="b2-cnn-smoke">Run the local smoke ({cnn?.smoke_defaults.n_train} + {(cnn?.smoke_defaults.n_predict ?? 0) * 2} windows · 1 epoch · this CPU)</Button>}
          <Button icon="file" onClick={slurm} disabled={model === 'forest' || !!errors.length || busy || !!running} disabledReason={model === 'forest' ? setup.slurm : (errors[0]?.detail ?? 'a job is running')} testid="b2-slurm">Create SLURM script</Button>
        </div>
        {model === 'cnn' && cnn && <div className="muted small" style={{ marginTop: 6 }} data-testid="b2-cnn-returns">{cnn.returns}</div>}
        {job && (() => { const pr = (job.progress ?? {}) as { done?: number; total?: number | null; message?: string }; return <div style={{ marginTop: 8 }} data-testid="b2-job" data-status={job.status}><ProgressBar value={(pr.done ?? 0) / Math.max(1, pr.total ?? 1)} />
          <div className="mono small">{job.status} · {pr.message ?? ''}{job.status === 'failed' ? ` · ${(job.error as { message?: string } | null)?.message ?? ''}` : ''}</div></div> })()}
        {smokeDone && <div className="small" style={{ marginTop: 6 }} data-testid="b2-cnn-smoke-done">local smoke → run #{smokeDone.run_id} ({smokeDone.n_windows} windows, {fmtSecs(smokeDone.total_s)} in all: encode {fmtSecs(smokeDone.timings?.encode)}, diagnostic {fmtSecs(smokeDone.timings?.diagnostic)}, final {fmtSecs(smokeDone.timings?.final)}, predict {fmtSecs(smokeDone.timings?.predict)}) · listed below and in Models › Results{' '}
          <Button variant="link" size="sm" onClick={() => navigate(`models/results/b2/${smokeDone.run_id}`)} testid="b2-cnn-smoke-open">open it</Button></div>}
      </SectionCard>

      {slurmOut && <ErrorBoundary label="the SLURM script"><CnnSlurmPanel s={slurmOut} /></ErrorBoundary>}

      <ErrorBoundary label="the B.2 runs"><B2Runs runs={setup.runs} /></ErrorBoundary>
    </div>
  )
}

function B2Runs({ runs }: { runs: B2Run[] }) {
  if (!runs.length) return <div className="muted small" data-testid="b2-runs-none">no B.2 run on this pool yet</div>
  return (
    <SectionCard title="B.2 runs on this pool" testid="b2-runs">
      <table className="sh-table">
        <thead><tr><th>run</th><th>model</th><th>status</th><th className="r">k</th><th>diagnostic · reproduces its own clusters</th><th>exam (i) later block</th><th>exam (ii) unseen channels</th><th>blind check</th></tr></thead>
        <tbody>{runs.map(r => (
          <tr key={r.run_id} data-testid={`b2-run-${r.run_id}`} data-model={r.kind === 'shape_cluster_cnn' ? 'cnn' : 'forest'}>
            <td className="mono">#{r.run_id}</td><td className="small">{r.model ?? 'random forest'}</td><td>{r.status}{r.error ? ` · ${r.error}` : ''}</td><td className="r">{r.k}</td>
            <td title={r.diagnostic?.note}>{r.diagnostic ? `diagnostic · accuracy ${r.diagnostic.accuracy.toFixed(2)} · macro F1 ${r.diagnostic.macro_f1.toFixed(2)} (largest cluster ${r.diagnostic.chance_largest_cluster.toFixed(2)})` : '—'}</td>
            {['i_later_block', 'ii_unseen_channels'].map(e => { const x = r.exams[e]; return <td key={e} className="small">{x ? `${x.n.toLocaleString()} windows · interesting ${x.by_class.interesting?.toLocaleString() ?? 0} · ${x.status}` : '—'}</td> })}
            <td className="small">{r.scored ? 'labelling / scored' : 'not yet labelled'}{r.status === 'completed' && <> · <Button variant="link" size="sm" testid={`b2-blind-link-${r.run_id}`} onClick={() => navigate(`models/results/b2/${r.run_id}`)}>against a blind human</Button></>}</td>
          </tr>))}</tbody>
      </table>
      <div className="muted small">the diagnostic is how well the model (forest or CNN) imitates its own answer key on training windows it did not fit — not evidence; the result is the blind human check (Models › Results › against a blind human)</div>
    </SectionCard>
  )
}

/* fixup-ai: the CNN's settings — the encoding (fusion first), epochs, the label-shuffle null (off by default) */
function CnnSettings({ cnn, enc, setEnc, epochs, setEpochs, withNull, setWithNull }: {
  cnn: CnnSetup; enc: Encoding; setEnc: (e: Encoding) => void; epochs: number | null; setEpochs: (n: number | null) => void
  withNull: boolean; setWithNull: (b: boolean) => void
}) {
  const d = cnn.defaults
  const m = cnn.measured[enc]
  return (
    <div className="stack" style={{ gap: 6 }} data-testid="b2-cnn-settings">
      <div className="small"><b>CNN</b> (EfficientNet-B0, ImageNet weights — the manual-label CNNs' own network) on the cluster categories of every training window, the same windows, cut and mapping as the forest</div>
      <div className="row" style={{ gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="small">encoding</span>
        <select value={enc} onChange={e => setEnc(e.target.value as Encoding)} data-testid="b2-cnn-encoding">
          {cnn.encodings.map(e => <option key={e} value={e}>{e}{e === 'fusion' ? ' (GASF + GADF + recurrence as RGB)' : ''}</option>)}
        </select>
        <span className="small">epochs</span><NumberField value={epochs ?? d.epochs} integer min={1} onValid={v => setEpochs(Math.max(1, Math.round(Number(v) || d.epochs)))} testid="b2-cnn-epochs" />
        <span className="muted small">batch {d.batch_size} · Adam lr {d.lr} · cosine · class weight {d.class_weight} · seed {d.random_state} · {d.img_size} px · refit on every training window</span>
      </div>
      <div className="muted small" data-testid="b2-cnn-images-rule">{cnn.images_rule}</div>
      <div className="muted small">{cnn.augmentation}</div>
      <div className="muted small" data-testid="b2-cnn-fusion-note">{cnn.fusion_note}</div>
      <label className="small row" style={{ gap: 6, alignItems: 'center' }}>
        <input type="checkbox" checked={withNull} onChange={e => setWithNull(e.target.checked)} data-testid="b2-cnn-null" />
        also write the label-shuffle null's script — {cnn.null.note}
      </label>
      <div className="muted small" data-testid="b2-cnn-measured">measured for the estimate: {m?.local ? `this CPU (run #${m.local.run_id}): ${Object.entries(m.local.encode_ms_by_scale ?? {}).map(([s, v]) => `${s} min ${Math.round(v)} ms`).join(' · ')} per window to encode, ${m.local.train_img_per_s ?? '—'} images / s to train` : 'nothing yet — run the local smoke first, so the SLURM script carries a measured estimate'}{m?.cluster ? ` · the cluster (run #${m.cluster.run_id}): ${m.cluster.train_img_per_s} images / s` : ''}</div>
    </div>
  )
}

function CnnSlurmPanel({ s }: { s: CnnSlurm }) {
  const e = s.estimate
  return (
    <SectionCard title="SLURM script · B.2 CNN on the cluster" testid="b2-slurm-out">
      <div className="small"><b>{s.model}</b> · recipe <span className="mono" data-testid="b2-slurm-hash">{s.recipe_hash}</span> · {s.n_windows.toLocaleString()} windows ({s.n_train.toLocaleString()} train · {s.n_predict.toLocaleString()} predicted) · {Object.entries(s.by_scale).map(([k, v]) => `${k} min ${v.toLocaleString()}`).join(' · ')}</div>
      <div className="small" style={{ marginTop: 6 }} data-testid="b2-slurm-estimate"><b>{e.label}:</b> {e.seconds == null ? 'not measured yet (run the local smoke first)' : `about ${fmtSecs(e.seconds)} of work`} — encode {fmtSecs(e.parts.encode_s)}{e.parts.encode_cpu_s != null ? ` (${fmtSecs(e.parts.encode_cpu_s)} of CPU)` : ''}, train {fmtSecs(e.parts.train_s)} ({e.images.fit.toLocaleString()} images over {e.images.epochs} epochs, twice: the diagnostic and the refit), predict {fmtSecs(e.parts.predict_s)} · image cache {fmtBytes(e.cache_bytes)} on the cluster{e.this_cpu_train_s ? ` · on this CPU the training alone would take ${fmtSecs(e.this_cpu_train_s)}` : ''} · --time {s.slurm_time} per job, {s.jobs_needed ?? '?'} job(s) expected, the chain capped at {s.chain_jobs}</div>
      <ul className="muted small" style={{ margin: '2px 0 0 18px' }}>{e.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
      {s.warnings.map((w, i) => <div key={i} className="small" style={{ color: 'var(--red)' }}>{w}</div>)}
      <h4 style={{ margin: '10px 0 2px' }}>On the cluster, step by step</h4>
      <Steps steps={s.steps} testid="b2-slurm-steps" />
      <h4 style={{ margin: '10px 0 2px' }}>What to copy, and how big it is</h4>
      <CopyList rows={s.copy} total={s.total_bytes} testid="b2-slurm-copy" />
      <h4 style={{ margin: '10px 0 2px' }}>The script, as written</h4>
      <ScriptBlock script={s.script} path={s.script_path} testid="b2-slurm-script" />
      {s.null_script && <><h4 style={{ margin: '10px 0 2px' }}>The label-shuffle null (array job, {s.null.n} tasks)</h4>
        <div className="muted small">{s.null.note}{s.null.gpu_hours != null ? ` · about ${s.null.gpu_hours.toFixed(1)} GPU-hours in all (an estimate)` : ''}</div>
        <ScriptBlock script={s.null_script} path={s.null_script_path ?? ''} testid="b2-slurm-null-script" /></>}
      <div className="small" style={{ marginTop: 8 }} data-testid="b2-slurm-returns"><b>How results return:</b> {s.returns}</div>
    </SectionCard>
  )
}
