/* fixup-ah — Models › Results for a B.2 run: *Label test windows blind* and *against a blind human*.
 *
 * In plain words: the B.2 forest learned piles a clustering made, with no human labels. Whether what it calls
 * interesting is what you call interesting is answered here: you label a sample of its test windows blind in Review,
 * and this page sets your answers against its calls — per exam, never pooled — beside how often you agree with
 * yourself on the windows shown twice (no model can be expected to beat that), and beside the manual-label CNNs
 * scored on the same windows at each scale (the comparison line). Read from `/api/models/b2/runs/{id}/blind`. */
import { useEffect, useRef, useState } from 'react'
import { ApiError, getJob, type JobRow } from '../api'
import {
  BLIND_EXAMS, getBlindScores, getBlindShowing, getDisagreements, makeBlindQueue, scoreReference,
  type BlindExam, type BlindScores, type BlindShowing, type Disagreement, type DisagreementKind, type ExamKey, type RefRow, type Small,
} from '../api/blind'
import { getB2Runs, type B2Run } from '../api/shape'
import { Button, Callout, Dropdown, Heatmap, Histogram, InfoTip, NumberField, ProgressBar, SectionCard, Seg, StatRow, StatTile, fmtInt, useQueryState } from '../kit'
import { useSize } from '../charts/useSize'
import { ErrorBoundary } from '../shell/ErrorBoundary'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { BlindTracePlot } from '../review/BlindTest'
import { JobsPageLink, LoadFailed, Loading, ModelsTabs } from './chrome'

const errText = (e: unknown) => (e instanceof ApiError ? e.message : String(e))
const f3 = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(3))
const pct = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v * 100)} %`)
const ci = (c?: [number | null, number | null]) => (!c || c[0] == null || c[1] == null ? '—' : `${c[0].toFixed(3)} – ${c[1].toFixed(3)}`)
const SHORT: Record<ExamKey, string> = { i_later_block: 'exam (i) · later block', ii_unseen_channels: 'exam (ii) · unseen channels' }

function minutes(s: number) { return `${Number.isInteger(s) ? s : s.toFixed(1)} min` }

/** On Results: the B.2 runs, each opening its blind view (Results / Compare read paired runs; a B.2 run is read here). */
export function B2RunsStrip() {
  const runs = useSourced(() => getB2Runs().then(r => ({ data: r, source: 'live' as const })), [])
  const list: B2Run[] = runs.data?.runs ?? []
  if (runs.error) return <LoadFailed what="the B.2 runs" error={runs.error} onRetry={runs.reload} />
  if (!runs.data) return null
  return (
    <SectionCard title="B.2 · cluster labels · trace shape" testid="b2-results-strip"
      subtitle="a B.2 run has no human labels to be scored against until you label its test windows blind">
      {!list.length ? <div className="m-foot-line" data-testid="b2-results-none">no B.2 run yet — train one from Analyse (Shape clustering › Train model)</div> : (
        <table className="m-table">
          <thead><tr><th>run</th><th>model</th><th>pool</th><th>k</th><th>status</th><th>blind check</th><th /></tr></thead>
          <tbody>{list.map(r => (
            <tr key={r.run_id} data-testid={`b2-results-run-${r.run_id}`} data-model={r.kind === 'shape_cluster_cnn' ? 'cnn' : 'forest'}>
              <td className="mono">#{r.run_id}</td><td className="small">{r.model ?? 'random forest'}</td><td>{r.pool?.name} v{r.pool?.version}</td><td>{r.k}</td><td>{r.status}</td>
              <td>{r.scored ? 'labelling / scored' : 'not yet labelled'}</td>
              <td>{r.status === 'completed' && <Button size="sm" icon="eye" testid={`open-b2-blind-${r.run_id}`} onClick={() => navigate(`models/results/b2/${r.run_id}`)}>against a blind human</Button>}
                {/* fixup-ai: the same template and pool on Launch, the CNN chosen — same windows, same cut, another model */}
                {r.template?.id != null && r.pool?.id != null && <Button size="sm" variant="link" testid={`b2-launch-cnn-${r.run_id}`} onClick={() => navigate(`models/launch?arm=b2&template=${r.template.id}&pool=${r.pool.id}&model=cnn`)}>train a CNN on this</Button>}</td>
            </tr>))}</tbody>
        </table>
      )}
    </SectionCard>
  )
}

export function B2BlindResults({ runId }: { runId: number }) {
  const [data, setData] = useState<BlindScores | null>(null)
  const [err, setErr] = useState<Error | null>(null)
  const runs = useSourced(() => getB2Runs().then(r => ({ data: r, source: 'live' as const })), [])
  const load = () => getBlindScores(runId).then(d => { setData(d); setErr(null) }).catch(e => { console.error('blind scores failed', e); setErr(e instanceof Error ? e : new Error(String(e))) })
  useEffect(() => { setData(null); void load() }, [runId])   // eslint-disable-line react-hooks/exhaustive-deps
  const list = (runs.data?.runs ?? []).filter(r => r.status === 'completed')
  const picker = list.length ? (
    <Dropdown prefix="B.2 run" value={String(runId)} onChange={v => navigate(`models/results/b2/${v}`)} testid="b2-run-select" width={300}
      options={list.map(r => ({ value: String(r.run_id), label: `${r.run_id} · ${r.pool?.name ?? '?'} · k = ${r.k}`, description: r.scored ? 'labelling / scored' : 'not yet labelled' }))} />
  ) : null
  return (
    <>
      <ModelsTabs current="results" jobsLink={<JobsPageLink />} middle={<>{picker}<Button size="sm" variant="link" onClick={() => navigate('models/results')}>paired runs</Button></>} />
      {err ? <LoadFailed what={`B.2 run ${runId}'s blind check`} error={err} onRetry={load} />
        : !data ? <Loading /> : (
          <div className="stack" style={{ gap: 12 }} data-testid="b2-blind" data-run={runId} data-queue={data.queue_id ?? ''}>
            <div className="m-foot-line" data-testid="b2-blind-line">
              B.2 run {runId} · {data.arm?.label ?? 'B.2'} · pool {data.pool?.name} v{data.pool?.version} (key {data.pool?.key}) · cut k = {data.k}
              {' · '}mapping: {Object.entries(data.mapping?.clusters ?? {}).map(([c, v]) => `${c}${v.name ? ` ${v.name}` : ''} → ${v.class === 'interesting' ? 'int' : 'not'}`).join(' · ')}
            </div>
            <ErrorBoundary label="the blind labelling"><MakeQueue data={data} runId={runId} onMade={load} /></ErrorBoundary>
            {data.queue_id != null && <>
              <ErrorBoundary label="against a blind human"><AgainstBlind data={data} /></ErrorBoundary>
              <ErrorBoundary label="the comparison line"><Reference data={data} runId={runId} onDone={load} /></ErrorBoundary>
              <ErrorBoundary label="the disagreements"><Disagreements runId={runId} queueId={data.queue_id} /></ErrorBoundary>
            </>}
          </div>
        )}
    </>
  )
}

function MakeQueue({ data, runId, onMade }: { data: BlindScores; runId: number; onMade: () => void }) {
  const [n, setN] = useState(1000)
  const [rep, setRep] = useState(10)
  const [seed, setSeed] = useState(0)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const totalPred = BLIND_EXAMS.reduce((a, e) => a + (data.predicted[e]?.n ?? 0), 0)
  const make = async () => {
    setBusy(true)
    try {
      const r = await makeBlindQueue(runId, { n, repeat_frac: rep / 100, seed })
      toast.push({ text: `blind queue ${r.queue_id} ${r.created ? 'made' : 'opened'} · opening Review` })
      onMade()
      navigate(`review/queue/${r.queue_id}`)
    } catch (e) { toast.push({ kind: 'error', text: errText(e) }) } finally { setBusy(false) }
  }
  const s = data.sample?.summary
  return (
    <SectionCard title="Label test windows blind" testid="blind-make"
      info="A seeded sample of the run's test and exam windows, drawn evenly per predicted cluster (so a rare cluster is not swamped), some shown twice for self-agreement. In Review you answer interesting / not without seeing the model's answer; each answer is an ordinary human label. The sample is fixed once drawn — the same sample for every model.">
      {data.queue_id == null ? (
        <>
          <div className="small" style={{ marginBottom: 8 }}>
            The run predicted {fmtInt(totalPred)} test and exam windows ({BLIND_EXAMS.map(e => `${SHORT[e]} ${fmtInt(data.predicted[e]?.n ?? 0)}`).join(' · ')}).
            At about five seconds a window, 1,000 windows is about an hour and a half; you can stop and resume.
          </div>
          <div className="row" style={{ gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <span className="small">windows</span><NumberField value={n} integer min={1} max={2000} onValid={v => setN(Math.round(Number(v) || 1000))} testid="blind-n" />
            <span className="small">shown twice</span><NumberField value={rep} integer min={0} max={50} unit="%" onValid={v => setRep(Math.round(Number(v) || 0))} testid="blind-repeat" />
            <span className="small">seed</span><NumberField value={seed} integer min={0} onValid={v => setSeed(Math.round(Number(v) || 0))} testid="blind-seed" width={80} />
            <Button variant="primary" icon="eye-off" onClick={make} loading={busy} testid="label-blind">Label test windows blind</Button>
          </div>
        </>
      ) : (
        <div className="row" style={{ gap: 12, alignItems: 'center', flexWrap: 'wrap' }} data-testid="blind-queue-progress">
          <span className="mono">queue {data.queue_id}</span>
          <div style={{ width: 240 }}><ProgressBar value={data.progress ? data.progress.judged / Math.max(1, data.progress.total) : 0}
            label={data.progress ? `${fmtInt(data.progress.judged)} / ${fmtInt(data.progress.total)} labelled` : ''} /></div>
          {data.progress?.pace_s != null && <span className="mono small muted">{data.progress.pace_s < 1 ? 'under 1' : data.progress.pace_s.toFixed(1)} s a window</span>}
          <Button variant="primary" icon="external" testid="open-blind-queue" onClick={() => navigate(`review/queue/${data.queue_id}`)}>{data.progress?.remaining ? 'Open the queue in Review' : 'Review the answers'}</Button>
          {data.verdicts && <span className="mono small">{Object.entries(data.verdicts).filter(([, v]) => v).map(([k, v]) => `${k.replace('_', ' ')} ${v}`).join(' · ')}</span>}
        </div>
      )}
      {s && (
        <div style={{ marginTop: 10 }} data-testid="blind-sample">
          <div className="m-foot-line">sample: {fmtInt(s.n)} windows, {fmtInt(s.n_repeats)} shown twice (closest pair {s.min_gap ?? '—'} showings apart) · {fmtInt(s.n_showings)} showings · seed {data.sample?.params.seed} · drawn {data.sample?.drawn_at}
            <InfoTip title="How the sample was drawn">{s.rule}</InfoTip></div>
          <table className="m-table" data-testid="blind-sample-strata">
            <thead><tr><th>exam</th><th>predicted cluster</th><th>maps to</th><th>windows predicted</th><th>drawn</th><th>weight</th></tr></thead>
            <tbody>{s.strata.map(r => (
              <tr key={`${r.exam}-${r.cluster}`}><td>{SHORT[r.exam]}</td><td>{r.cluster}{r.name ? ` · ${r.name}` : ''}</td><td>{r.class?.replace('_', ' ')}</td>
                <td>{fmtInt(r.population)}</td><td>{fmtInt(r.drawn)}</td><td>{r.weight.toFixed(2)}</td></tr>))}</tbody>
          </table>
          <div className="m-foot-line m-small">by scale: {s.by_scale.map(r => `${SHORT[r.exam].split(' · ')[0]} ${minutes(r.scale_min)} ${r.drawn}`).join(' · ')}</div>
        </div>
      )}
    </SectionCard>
  )
}

function AgainstBlind({ data }: { data: BlindScores }) {
  const [examQ, setExam] = useQueryState<ExamKey>('exam', 'ii_unseen_channels')
  const ex = data.exams[examQ]
  const sa = data.self_agreement
  return (
    <SectionCard title="Against a blind human" testid="against-blind"
      info="Per exam, never pooled. Rows of the confusion: your blind answer; columns: the model's call (its predicted cluster through the frozen interesting / not mapping). can't tell and artifact answers are left out and counted. The block bootstrap resamples whole 24-hour stretches of one channel.">
      <Seg value={examQ} onChange={v => setExam(v)} testid="blind-exam-seg" ariaLabel="exam"
        options={BLIND_EXAMS.map(e => ({ value: e, label: SHORT[e], disabled: !data.exams[e], reason: 'no window of this exam in the sample' }))} />
      <div className="m-foot-line">{data.exam_titles[examQ]}</div>
      {!ex ? <Callout tone="amber">no window of this exam is in the sample</Callout> : ex.n_scored === 0 ? (
        <Callout tone="blue" icon="info" testid="blind-exam-unlabelled">{ex.status}: {fmtInt(ex.n_labelled)} of {fmtInt(ex.n_sample)} labelled · none interesting / not yet</Callout>
      ) : <ExamView ex={ex} />}
      {sa && <div className="m-foot-line" data-testid="blind-self-agreement-all">self-agreement, every exam: {sa.n_scored_pairs} of {sa.n_pairs} repeated windows answered interesting / not both times · same answer {pct(sa.share)} · kappa {f3(sa.kappa)}</div>}
    </SectionCard>
  )
}

function SelfLine({ ex }: { ex: BlindExam }) {
  const s = ex.self_agreement
  return <span>{s.n_scored_pairs ? `you agree with yourself ${pct(s.share)} (kappa ${f3(s.kappa)}, ${s.n_scored_pairs} pairs)` : `self-agreement: no repeated window of this exam answered twice yet (${s.n_pairs} in the sample)`}</span>
}

function ExamView({ ex }: { ex: BlindExam }) {
  const sums = ex.confusion.map(r => r.reduce((a, b) => a + b, 0) || 1)
  const norm = ex.confusion.map((r, i) => r.map(v => v / sums[i]))
  const sa = ex.self_agreement
  return (
    <>
      <StatRow columns={5}>
        <StatTile label="macro F1 · model vs you" value={f3(ex.macro_f1)} caption={`95 % CI ${ci(ex.macro_f1_ci)} · ${ex.n_units} units of ${ex.unit}`} testid="blind-macro-f1" />
        <StatTile label="the model's interesting" value={`P ${f3(ex.interesting.precision)} · R ${f3(ex.interesting.recall)}`} caption={`F1 ${f3(ex.interesting.f1)} (${ci(ex.interesting.f1_ci)})`} testid="blind-interesting" />
        <StatTile label="Cohen's kappa" value={f3(ex.kappa)} caption={`95 % CI ${ci(ex.kappa_ci)}`} testid="blind-kappa" />
        <StatTile label="you against yourself" value={sa.n_scored_pairs ? pct(sa.share) : '—'} caption={sa.n_scored_pairs ? `kappa ${f3(sa.kappa)} · ${sa.n_scored_pairs} pairs` : `${sa.n_pairs} repeats in the sample, none answered twice yet`} testid="blind-self-agreement" tone="blue"
          info={sa.note} />
        <StatTile label="label-shuffle null" value={`${f3(ex.null.mean)} · q95 ${f3(ex.null.q95)}`} caption={`p ${ex.null.p == null ? '—' : ex.null.p.toFixed(4)} · ${ex.null.n} shuffles`} tone={ex.null.p != null && ex.null.p <= 0.05 ? 'green' : 'amber'} testid="blind-null" info={ex.null.rule} />
      </StatRow>
      <div className="m-foot-line" data-testid="blind-counts">{fmtInt(ex.n_scored)} windows answered interesting / not (of {fmtInt(ex.n_sample)} in this exam's sample) · left out: can't tell {ex.excluded.unsure} · artifact {ex.excluded.artifact} · not yet labelled {ex.excluded.not_yet_labelled}</div>
      <div className="m-cols" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <SectionCard title="Confusion" testid="blind-confusion" info={ex.confusion_note}>
          <Heatmap rows={ex.confusion_labels.map(c => `you: ${c.replace('_', ' ')}`)} cols={ex.confusion_labels.map(c => `model: ${c.replace('_', ' ')}`)} values={norm} testid="blind-confusion-grid" format={v => `${Math.round(v * 100)} %`} rowLabelWidth={150} />
          <div className="m-foot-line m-mono m-small">counts {ex.confusion.map(r => r.join(' / ')).join(' · ')} · <SelfLine ex={ex} /></div>
        </SectionCard>
        <SectionCard title="Against the null" testid="blind-null-card" info="The model's macro F1 (blue, with its CI band) over the macro F1s of your answers shuffled against its fixed calls.">
          {ex.macro_f1 != null && ex.null.draws.length > 0
            ? <Histogram values={ex.null.draws} nBins={24} testid="blind-null-plot" xLabel="macro F1" height={160}
              markers={[{ x: ex.macro_f1, label: 'model', colour: 'var(--blue)', band: (ex.macro_f1_ci[0] != null && ex.macro_f1_ci[1] != null ? [ex.macro_f1_ci[0], ex.macro_f1_ci[1]] : undefined) as [number, number] | undefined }]}
              domain={[Math.min(0.2, ...ex.null.draws, ex.macro_f1_ci[0] ?? ex.macro_f1) - 0.02, Math.max(ex.macro_f1_ci[1] ?? ex.macro_f1, ...ex.null.draws) + 0.02]} />
            : <div className="m-foot-line">no null yet</div>}
          <div className="m-foot-line m-small"><SelfLine ex={ex} /></div>
        </SectionCard>
      </div>
      <SectionCard title="Per predicted cluster — the check on the mapping" testid="blind-per-cluster"
        info="How many of the windows the model put in each cluster you called interesting. A cluster mapped 'interesting' that you mostly call not (or the reverse) is where the mapping and your eye disagree.">
        <table className="m-table">
          <thead><tr><th>cluster</th><th>mapped to</th><th>answered</th><th>you: interesting</th><th>share</th><th>agrees with the mapping</th><th>windows predicted</th></tr></thead>
          <tbody>{ex.per_cluster.map(r => (
            <tr key={r.cluster} data-testid={`blind-cluster-${r.cluster}`}><td>{r.cluster}{r.name ? ` · ${r.name}` : ''}</td><td>{r.class?.replace('_', ' ') ?? '—'}</td><td>{fmtInt(r.n)}</td>
              <td>{fmtInt(r.human_interesting)}</td><td>{pct(r.share_interesting)}</td><td>{pct(r.agrees_with_mapping)}</td><td>{fmtInt(r.population)}</td></tr>))}</tbody>
        </table>
        <div className="m-foot-line m-small"><SelfLine ex={ex} /></div>
      </SectionCard>
      <div className="m-cols" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <SliceTable title="Per scale" testid="blind-per-scale" rows={ex.per_scale.map(r => ({ key: minutes(r.scale_min), r }))} />
        <SliceTable title="Per recording" testid="blind-per-recording" rows={ex.per_recording.map(r => ({ key: r.name ?? r.recording, r }))} />
      </div>
      <div className="m-foot-line" data-testid="blind-reweighted">reweighted to every predicted window of this exam: precision {f3(ex.reweighted.precision)} · recall {f3(ex.reweighted.recall)} · F1 {f3(ex.reweighted.f1)} · accuracy {f3(ex.reweighted.accuracy)}
        <InfoTip title="Reweighted">{ex.reweighted.note}</InfoTip> · <SelfLine ex={ex} /></div>
    </>
  )
}

function SliceTable({ title, testid, rows }: { title: string; testid: string; rows: { key: string; r: Small }[] }) {
  return (
    <SectionCard title={title} testid={testid}>
      <table className="m-table">
        <thead><tr><th /><th>answered</th><th>you: int</th><th>model: int</th><th>agree</th><th>macro F1</th><th>kappa</th><th>P · R</th></tr></thead>
        <tbody>{rows.map(({ key, r }) => (
          <tr key={key}><td>{key}</td><td>{fmtInt(r.n)}</td><td>{fmtInt(r.human_interesting)}</td><td>{fmtInt(r.model_interesting)}</td><td>{pct(r.agreement)}</td>
            {r.one_class ? <td colSpan={3} className="m-muted">one class only — no macro F1</td>
              : <><td>{f3(r.macro_f1)}</td><td>{f3(r.kappa)}</td><td>{f3(r.precision)} · {f3(r.recall)}</td></>}</tr>))}</tbody>
      </table>
    </SectionCard>
  )
}

function Reference({ data, runId, onDone }: { data: BlindScores; runId: number; onDone: () => void }) {
  const ref = data.reference
  const [jobId, setJobId] = useState<number | null>(null)
  const [job, setJob] = useState<JobRow | null>(null)
  const toast = useToast()
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])
  useEffect(() => {
    if (jobId === null) return
    const tick = () => getJob(jobId).then(j => {
      if (!alive.current) return
      setJob(j)
      if (['completed', 'failed', 'cancelled'].includes(j.status)) onDone(); else window.setTimeout(tick, 1000)
    }, e => { console.error('job poll failed', e); window.setTimeout(tick, 2000) })
    tick()
  }, [jobId])   // eslint-disable-line react-hooks/exhaustive-deps
  const start = async () => {
    try { const r = await scoreReference(runId); setJobId(r.job_id); toast.push({ text: `comparison line · job ${r.job_id}` }) }
    catch (e) { toast.push({ kind: 'error', text: errText(e) }) }
  }
  const running = job && !['completed', 'failed', 'cancelled'].includes(job.status)
  const pr = (job?.progress ?? {}) as { done?: number; total?: number | null; message?: string }
  const cell = (r: RefRow, e: ExamKey, which: 'all' | 'no_earlier_label') => {
    const x = r.exams[e]?.[which]
    if (!x || !x.n) return <span className="m-muted">—</span>
    return <span title={`n ${x.n} · you: interesting ${x.human_interesting} · model: interesting ${x.model_interesting} · agree ${pct(x.agreement)}`}>
      {x.one_class ? `one class · agree ${pct(x.agreement)}` : `F1 ${f3(x.macro_f1)} · κ ${f3(x.kappa)}`} <span className="m-muted">(n {x.n})</span></span>
  }
  return (
    <SectionCard title="Comparison line · the manual-label models at every scale" testid="blind-reference"
      subtitle="one row per model per scale, never pooled — trained on 10-minute windows of manual labels"
      info="Each model sees the raw window AS IT IS: its n samples become an n × n image that the network's transform resizes to 224 × 224; nothing is resampled. Whether a confidence means anything away from the 10-minute windows they were trained on is what the 1- and 30-minute rows ask.">
      <div className="row" style={{ gap: 8, alignItems: 'center', marginBottom: 6 }}>
        <Button icon="play" onClick={start} disabled={!!running} disabledReason="scoring" testid="score-reference">{ref.status === 'computed' ? 'Score again' : 'Score the comparison line'}</Button>
        {running && <div style={{ width: 260 }}><ProgressBar value={(pr.done ?? 0) / Math.max(1, pr.total ?? 1)} label={pr.message ?? job?.status} /></div>}
        {job?.status === 'failed' && <span className="mono small" style={{ color: 'var(--red)' }}>{(job.error as { message?: string } | null)?.message}</span>}
        {ref.status === 'computed' && <span className="mono small muted">computed {ref.computed_at} · {ref.n_overlapping_earlier_label ?? 0} of {ref.n_labelled ?? 0} answered windows overlap an earlier human label</span>}
      </div>
      <Callout tone="amber" icon="alert-triangle" testid="blind-contamination">{ref.contamination ?? 'Contamination: the manual-label models were very likely trained on M2_aug\'s 2025–26 labels; a window overlapping one of them is not unseen for them, so each is scored on every window and on the windows with no earlier label.'}</Callout>
      {ref.status !== 'computed' ? (
        <div className="m-foot-line" data-testid="blind-reference-not-computed">not computed yet · {(ref.models ?? []).map(m => m.model).join(' · ')}</div>
      ) : (
        <table className="m-table" data-testid="blind-reference-table">
          <thead><tr><th>model</th><th>scale</th><th>{SHORT.i_later_block}<br /><span className="m-muted">all · no earlier label</span></th><th>{SHORT.ii_unseen_channels}<br /><span className="m-muted">all · no earlier label</span></th><th>how it was fed</th></tr></thead>
          <tbody>{ref.rows.map(r => (
            <tr key={`${r.model}-${r.scale_min}`} data-testid={`ref-${r.model}-${r.scale_min}`}>
              <td className="mono">{r.model}</td>
              <td>{minutes(r.scale_min)}{r.outside_training_scale && <span className="k-chip amber sm" style={{ marginLeft: 6 }} data-testid="outside-training-scale">outside its training scale</span>}</td>
              {r.status !== 'scored' ? <td colSpan={2} className="m-small" style={{ color: 'var(--red)' }}>not scored — {r.reason}</td> : BLIND_EXAMS.map(e => (
                <td key={e} className="m-small">{cell(r, e, 'all')}<br />{cell(r, e, 'no_earlier_label')}</td>))}
              <td className="m-small"><InfoTip title={`${r.model} · how the window reached it`}>{r.how_fed}. {r.embedding}. {r.contamination}.</InfoTip> <span className="m-muted">{r.embedding.split(':')[0]}</span></td>
            </tr>))}</tbody>
        </table>
      )}
    </SectionCard>
  )
}

function Disagreements({ runId, queueId }: { runId: number; queueId: number }) {
  const [exam, setExam] = useState<ExamKey>('ii_unseen_channels')
  const [kind, setKind] = useState<DisagreementKind>('model_yes_human_no')
  const [rows, setRows] = useState<Disagreement[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [i, setI] = useState(0)
  useEffect(() => {
    setRows(null); setI(0)
    getDisagreements(runId, exam, kind).then(r => { setRows(r.windows); setErr(null) }).catch(e => { console.error('disagreements failed', e); setErr(errText(e)) })
  }, [runId, exam, kind])
  const cur = rows && rows.length ? rows[Math.min(i, rows.length - 1)] : null
  return (
    <SectionCard title="Step through the disagreements" testid="blind-disagreements" info="Windows where the model and your blind answer differ, one direction at a time; first showings only. The model's call is shown here, after the labelling.">
      <div className="row" style={{ gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <Seg value={exam} onChange={v => setExam(v)} ariaLabel="exam" testid="dis-exam" options={BLIND_EXAMS.map(e => ({ value: e, label: SHORT[e] }))} />
        <Seg value={kind} onChange={v => setKind(v)} ariaLabel="direction" testid="dis-kind" options={[{ value: 'model_yes_human_no', label: 'model yes · you no' }, { value: 'model_no_human_yes', label: 'model no · you yes' }]} />
        {rows && <span className="mono small">{rows.length ? `${Math.min(i, rows.length - 1) + 1} of ${rows.length}` : 'none'}</span>}
        <Button size="sm" onClick={() => setI(Math.max(0, i - 1))} disabled={!rows || i <= 0} disabledReason="the first" testid="dis-prev">← previous</Button>
        <Button size="sm" onClick={() => setI(i + 1)} disabled={!rows || i + 1 >= rows.length} disabledReason="the last" testid="dis-next">next →</Button>
      </div>
      {err && <div className="error-card"><h3>The disagreements failed to load</h3><p className="mono">{err}</p></div>}
      {rows && !rows.length && <div className="m-foot-line" data-testid="dis-none">no window of this exam disagrees this way (among the answered ones)</div>}
      {cur && <DisagreementWindow queueId={queueId} d={cur} />}
    </SectionCard>
  )
}

function DisagreementWindow({ queueId, d }: { queueId: number; d: Disagreement }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const width = Math.max(360, Math.round(size.width || 900))
  const [w, setW] = useState<BlindShowing | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    setW(null)
    getBlindShowing(queueId, d.showing, width).then(x => { if (alive) setW(x) }).catch(e => { console.error('showing failed', e); if (alive) setErr(errText(e)) })
    return () => { alive = false }
  }, [queueId, d.showing])   // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div style={{ marginTop: 8 }} data-testid="dis-window" data-showing={d.showing}>
      <div className="m-foot-line mono">{d.recording} · {d.channel_name} · {(d.start / d.fs / 3600).toFixed(2)} h · {minutes(d.scale_min)} · cluster {d.cluster}
        {' · '}<b>model: {d.model_class.replace('_', ' ')}</b> (P(interesting) {d.p_interesting.toFixed(2)}) · <b>you: {d.human.replace('_', ' ')}</b>
        {' · '}<Button size="sm" variant="link" onClick={() => navigate(`explore/signal/${d.recording_id}`)}>open the channel in Explore</Button></div>
      <div ref={ref}>{err ? <div className="error-card"><h3>failed</h3><p className="mono">{err}</p></div> : w ? <BlindTracePlot w={w} width={width} testid="dis-plot" /> : <div className="skeleton" style={{ height: 300 }} />}</div>
    </div>
  )
}

