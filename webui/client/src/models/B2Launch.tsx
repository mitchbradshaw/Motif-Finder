/* fixup-ag seam (iii) — Models › Launch, arm **B.2 cluster labels · trace shape**, opened PREFILLED by Analyse's
 * *Train model*: the template, the pool as the sources (its recordings, channels and roles shown, not re-entered),
 * section 3 *Label arms* set to B.2 with the cut and the mapping read-only (they are edited in Analyse, where the
 * dendrogram is). *Open in Analyse* opens that chain on that pool. Nothing trains until *Train locally* is pressed.
 * The pool is unlabelled: there is no arm A; the manual-label comparison is AH's reference line. */
import { useEffect, useRef, useState } from 'react'
import { ApiError, getJob, type JobRow } from '../api'
import { getB2Setup, trainB2, type B2Run, type B2Setup } from '../api/shape'
import { Button, Callout, NumberField, ProgressBar, SectionCard } from '../kit'
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
      if (['completed', 'failed', 'cancelled'].includes(j.status)) { void load() } else window.setTimeout(tick, 900)
    }, e => { console.error('job poll failed', e); window.setTimeout(tick, 2000) })
    tick()
  }, [jobId])   // eslint-disable-line react-hooks/exhaustive-deps

  if (err) return <div className="error-card" data-testid="b2-error"><h3>arm B.2 could not be set up</h3><div className="mono small">{err}</div><Button size="sm" onClick={() => navigate('analyse/chain')}>Open Analyse › Chain</Button></div>
  if (!setup) return <div className="muted mono small" data-testid="b2-loading">reading the template and the pool…</div>
  const errors = setup.checks.filter(c => c.level === 'error')
  const train = async () => {
    setBusy(true)
    try { const r = await trainB2({ template, pool, n_estimators: nTrees }); setJobId(r.job_id); toast.push({ text: `B.2 forest started · job ${r.job_id}` }) }
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
        <div className="small"><b>Random forest</b> on the cluster categories of every training window · inputs: <b>{setup.inputs.features}</b> ({setup.inputs.stages.join(' + ')})</div>
        <div className="muted small" data-testid="b2-inputs-rule">{setup.inputs.rule}</div>
        <div className="row" style={{ gap: 8, alignItems: 'center', marginTop: 6 }}>
          <span className="small">trees</span><NumberField value={nTrees} integer min={10} onValid={v => setNTrees(Math.max(10, Math.round(Number(v) || 300)))} testid="b2-trees" />
          <span className="muted small">class weight {setup.defaults.class_weight} · seed {setup.defaults.random_state}</span>
        </div>
      </SectionCard>

      <SectionCard title="Before launch" testid="b2-checks">
        {setup.checks.map(c => <div key={c.name} className="small" style={{ color: c.level === 'error' ? 'var(--red)' : undefined }}>{c.level === 'error' ? '✗' : '✓'} <b>{c.name}</b> — {c.detail}</div>)}
        <div className="row" style={{ gap: 8, marginTop: 8 }}>
          <Button variant="primary" icon="play" onClick={train} disabled={!!errors.length || busy || !!running} disabledReason={errors[0]?.detail} loading={busy} testid="b2-train-locally">Train locally</Button>
          <Button icon="file" disabled disabledReason={setup.slurm} testid="b2-slurm">Create SLURM script</Button>
        </div>
        {job && (() => { const pr = (job.progress ?? {}) as { done?: number; total?: number | null; message?: string }; return <div style={{ marginTop: 8 }} data-testid="b2-job"><ProgressBar value={(pr.done ?? 0) / Math.max(1, pr.total ?? 1)} />
          <div className="mono small">{job.status} · {pr.message ?? ''}{job.status === 'failed' ? ` · ${(job.error as { message?: string } | null)?.message ?? ''}` : ''}</div></div> })()}
      </SectionCard>

      <ErrorBoundary label="the B.2 runs"><B2Runs runs={setup.runs} /></ErrorBoundary>
    </div>
  )
}

function B2Runs({ runs }: { runs: B2Run[] }) {
  if (!runs.length) return <div className="muted small" data-testid="b2-runs-none">no B.2 run on this pool yet</div>
  return (
    <SectionCard title="B.2 runs on this pool" testid="b2-runs">
      <table className="sh-table">
        <thead><tr><th>run</th><th>status</th><th className="r">k</th><th>diagnostic · reproduces its own clusters</th><th>exam (i) later block</th><th>exam (ii) unseen channels</th><th>blind check</th></tr></thead>
        <tbody>{runs.map(r => (
          <tr key={r.run_id} data-testid={`b2-run-${r.run_id}`}>
            <td className="mono">#{r.run_id}</td><td>{r.status}{r.error ? ` · ${r.error}` : ''}</td><td className="r">{r.k}</td>
            <td title={r.diagnostic?.note}>{r.diagnostic ? `diagnostic · accuracy ${r.diagnostic.accuracy.toFixed(2)} · macro F1 ${r.diagnostic.macro_f1.toFixed(2)} (largest cluster ${r.diagnostic.chance_largest_cluster.toFixed(2)})` : '—'}</td>
            {['i_later_block', 'ii_unseen_channels'].map(e => { const x = r.exams[e]; return <td key={e} className="small">{x ? `${x.n.toLocaleString()} windows · interesting ${x.by_class.interesting?.toLocaleString() ?? 0} · ${x.status}` : '—'}</td> })}
            <td className="small">{r.scored ? 'labelling / scored' : 'not yet labelled'}{r.status === 'completed' && <> · <Button variant="link" size="sm" testid={`b2-blind-link-${r.run_id}`} onClick={() => navigate(`models/results/b2/${r.run_id}`)}>against a blind human</Button></>}</td>
          </tr>))}</tbody>
      </table>
      <div className="muted small">the diagnostic is how well the forest imitates its own answer key on training windows it did not fit — not evidence; the result is the blind human check (Models › Results › against a blind human)</div>
    </SectionCard>
  )
}
