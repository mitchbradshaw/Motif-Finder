/* models.results (spec §7b.3; fixup-ab). One paired run at a time, one arm at a time (A manual · B cluster), one exam at a
 * time — never pooled: macro F1 with its block-bootstrap CI, balanced accuracy, the label-shuffle null, the confusion
 * matrix, per-class P/R/F1 with n, per channel, calibration on the validation block, the reference line ("trained
 * differently") and the yardstick-(B) row. Read from `/api/models/runs/{id}`; nothing here is a fixture. */
import { Button, Callout, Dropdown, EmptyState, Heatmap, Histogram, InfoTip, Page, SectionCard, Seg, StatRow, StatTile, fmtInt, useQueryState } from '../kit'
import { Header } from '../shell/Header'
import { navigate } from '../state'
import { useApp } from '../state'
import { useSourced } from '../api/seam'
import {
  CLASS_NAMES, EXAM_TITLES, getPairedRun, getPairedRuns,
  type ArmScore, type ExamKey, type PairedArm, type PairedResults, type PairedRunRow,
} from '../api/models'
import { ArmBadge, Loading, LoadFailed, ModelsTabs, JobsPageLink } from './chrome'
import { B2BlindResults, B2RunsStrip } from './B2Blind'

const EXAMS: ExamKey[] = ['i_later_block', 'ii_unseen_channels', 'iii_held_out']
const ci = (c: [number | null, number | null] | undefined) => (!c || c[0] == null || c[1] == null ? '—' : `${c[0].toFixed(3)} – ${c[1].toFixed(3)}`)
const f3 = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(3))

export function ResultsPage() {
  const { route } = useApp()
  const runs = useSourced(getPairedRuns, [])
  const idPart = route.parts[1]
  // fixup-ah: a B.2 run is read "against a blind human" (Results' paired views read paired runs only)
  if (idPart === 'b2' && route.parts[2]) return (
    <>
      <Header workspace="Models" page="Results" subtitle="B.2 · against a blind human, per exam, never pooled" />
      <Page testid="models-results-b2"><B2BlindResults runId={Number(route.parts[2])} /></Page>
    </>
  )
  const list: PairedRunRow[] = runs.data?.runs ?? []
  const runId = idPart ? Number(idPart) : list.find(r => r.status === 'completed')?.run_id ?? null
  return (
    <>
      <Header workspace="Models" page="Results" subtitle="one paired run · one arm · one exam at a time" />
      <Page testid="models-results">
        {runs.error ? <LoadFailed what="the training runs" error={runs.error} onRetry={runs.reload} />
          : !runs.data ? <Loading />
            : runId == null ? (
              <>
                <ModelsTabs current="results" jobsLink={<JobsPageLink />} />
                <EmptyState icon="bar-chart" bordered testid="results-empty" title="No paired run yet"
                  caption="Train one on Models › Launch: a window set across channels, arm B's cut, Train locally."
                  action={<Button variant="primary" icon="rocket" onClick={() => navigate('models/launch')}>Open Launch</Button>} />
                <B2RunsStrip />
              </>
            ) : <><RunResults runId={runId} runs={list} /><B2RunsStrip /></>}
      </Page>
    </>
  )
}

function RunResults({ runId, runs }: { runId: number; runs: PairedRunRow[] }) {
  const run = useSourced(() => getPairedRun(runId), [runId])
  const [armQ, setArm] = useQueryState<'a' | 'b'>('arm', 'a')
  const [examQ, setExam] = useQueryState<ExamKey>('exam', 'i_later_block')
  const arm: PairedArm = armQ === 'b' ? 'B' : 'A'
  const picker = (
    <Dropdown prefix="run" value={String(runId)} onChange={v => navigate(`models/results/${v}`)} testid="run-select" width={280}
      options={runs.map(r => ({ value: String(r.run_id), label: `${r.run_id} · ${r.window_set?.name ?? '?'} · k = ${r.k}`, description: `${r.status}${r.macro_f1 ? ` · F1 A ${r.macro_f1.A.toFixed(3)} B ${r.macro_f1.B.toFixed(3)}` : ''}` }))} />
  )
  const armSeg = <Seg value={armQ} onChange={v => setArm(v)} testid="arm-seg" ariaLabel="arm" options={[{ value: 'a', label: 'A · manual' }, { value: 'b', label: 'B · cluster' }]} />
  if (run.error) return <><ModelsTabs current="results" jobsLink={<JobsPageLink />} middle={picker} /><LoadFailed what={`run ${runId}`} error={run.error} onRetry={run.reload} /></>
  if (!run.data) return <><ModelsTabs current="results" jobsLink={<JobsPageLink />} middle={picker} /><Loading /></>
  const r = run.data
  if (!r.results) return (
    <>
      <ModelsTabs current="results" jobsLink={<JobsPageLink />} middle={picker} />
      {r.status === 'running'
        ? <Callout tone="blue" icon="hourglass" testid="results-running" title={`Run ${runId} is still training`}>Follow it on Launch; this page fills when it finishes.</Callout>
        : <Callout tone="red" testid="results-failed" title={`Run ${runId} ${r.status}`}><pre className="m-mono m-small" style={{ whiteSpace: 'pre-wrap' }}>{r.error}</pre></Callout>}
    </>
  )
  const res = r.results
  const ex = res.exams[examQ]
  return (
    <>
      <ModelsTabs current="results" jobsLink={<JobsPageLink />} middle={<>{picker}{armSeg}</>} />
      <div className="m-foot-line" data-testid="run-line">
        <ArmBadge letter={arm} /> run {runId} · recipe {res.recipe_hash} · {res.window_set.name} v{res.window_set.version} · {fmtInt(res.window_set.n_windows)} windows
        · {res.window_set.source_file} · train ch {res.window_set.channels.join(', ')} · exam ch {res.window_set.exam_channels.join(', ') || '—'}
        · split {res.window_set.split.n_blocks} blocks, test {Math.round(res.window_set.split.test_frac * 100)} %, gap ≥ {res.window_set.split.gap_windows} window
      </div>
      <Callout tone="blue" icon="info" testid="tilt-note">{res.notes[0]}</Callout>
      <Seg value={examQ} onChange={v => setExam(v)} testid="exam-seg" ariaLabel="exam"
        options={EXAMS.map(e => ({ value: e, label: EXAM_TITLES[e].split(' · ')[0], disabled: res.exams[e].status !== 'scored', reason: res.exams[e].reason ?? res.exams[e].status }))} />
      <div className="m-foot-line">{EXAM_TITLES[examQ]}</div>
      {ex.status !== 'scored' || !ex.arms ? (
        <Callout tone={ex.status === 'locked' ? 'blue' : 'amber'} icon={ex.status === 'locked' ? 'lock' : 'info'} testid={`exam-${ex.status}`}>{ex.reason}</Callout>
      ) : <ArmExam res={res} examKey={examQ} arm={arm} a={ex.arms[arm]} />}
      <Training res={res} arm={arm} />
      <Reference res={res} />
      <SectionCard title="Yardstick (B)" testid="yardstick-b" subtitle="blind hand-labelling of test windows in the cluster vocabulary">
        <div className="m-foot-line"><span className="k-chip sm grey">{res.yardstick_b.status}</span> {res.yardstick_b.note}</div>
      </SectionCard>
    </>
  )
}

function ArmExam({ res, examKey, arm, a }: { res: PairedResults; examKey: ExamKey; arm: PairedArm; a: ArmScore }) {
  const ex = res.exams[examKey]
  const rowSums = a.confusion.map(r => r.reduce((x, y) => x + y, 0) || 1)
  const norm = a.confusion.map((r, i) => r.map(v => v / rowSums[i]))
  const warn = 50
  return (
    <>
      <StatRow columns={5}>
        <StatTile label="macro F1" value={f3(a.macro_f1)} caption={`95 % CI ${ci(a.macro_f1_ci)} · ${ex.n_units} units of ${ex.unit}`} testid="results-stats" />
        <StatTile label="balanced accuracy" value={f3(a.balanced_accuracy)} caption={`accuracy ${f3(a.accuracy)}`} />
        <StatTile label="label-shuffle null" value={`${f3(a.null.mean)} · q95 ${f3(a.null.q95)}`} caption={`p ${a.null.p == null ? '—' : a.null.p.toFixed(4)} · ${a.null.draws.length} shuffles`} tone={a.null.p != null && a.null.p <= 0.05 ? 'green' : 'amber'} />
        <StatTile label="test windows" value={fmtInt(a.n)} caption={`interesting ${fmtInt(ex.class_counts?.interesting ?? 0)} · not ${fmtInt(ex.class_counts?.not_interesting ?? 0)}`} />
        <StatTile label="the other arm" value={f3(ex.arms?.[arm === 'A' ? 'B' : 'A'].macro_f1)} caption={`ΔF1 A − B ${f3(ex.paired?.delta_f1)}`} />
      </StatRow>
      <div className="m-cols" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <SectionCard title="Against the null" testid="null-card" info="The arm's macro F1 (blue, with its CI band) over the macro F1s of the same forest trained on shuffled labels.">
          <Histogram values={a.null.draws} nBins={24} testid="null-plot" xLabel="macro F1" height={170}
            markers={[{ x: a.macro_f1, label: `arm ${arm}`, colour: 'var(--blue)', band: (a.macro_f1_ci[0] != null && a.macro_f1_ci[1] != null ? [a.macro_f1_ci[0], a.macro_f1_ci[1]] : undefined) as [number, number] | undefined }]}
            domain={[Math.min(0.3, ...a.null.draws, a.macro_f1_ci[0] ?? a.macro_f1) - 0.02, Math.max(a.macro_f1_ci[1] ?? a.macro_f1, ...a.null.draws) + 0.02]} />
          <div className="m-foot-line m-small">{a.null.full_model}</div>
        </SectionCard>
        <SectionCard title="Confusion" testid="confusion-card" info="Rows: the human verdict. Columns: the arm's prediction. Row-normalised; counts below.">
          <Heatmap rows={[...CLASS_NAMES]} cols={CLASS_NAMES.map(c => `→ ${c}`)} values={norm} testid="confusion-grid" format={v => `${Math.round(v * 100)} %`} />
          <div className="m-foot-line m-mono m-small">counts {a.confusion.map(r => r.join(' / ')).join(' · ')}</div>
        </SectionCard>
      </div>
      <SectionCard title="Per class" testid="per-class">
        <table className="m-table">
          <thead><tr><th>class</th><th>precision</th><th>recall</th><th>F1 (95 % CI)</th><th>test n</th><th>predicted</th></tr></thead>
          <tbody>{CLASS_NAMES.map(c => { const p = a.per_class[c]; return (
            <tr key={c} data-testid={`class-row-${c}`}><td>{c}</td><td>{f3(p.precision)}</td><td>{f3(p.recall)}</td><td>{f3(p.f1)} ({ci(p.f1_ci)})</td>
              <td>{fmtInt(p.n)}{p.n < warn && <span className="k-chip amber sm" style={{ marginLeft: 6 }}>few</span>}</td><td>{fmtInt(p.n_predicted)}</td></tr>) })}</tbody>
        </table>
      </SectionCard>
      <SectionCard title="Per channel" testid="per-channel" subtitle="macro F1 of both arms on each channel's windows of this exam">
        <table className="m-table">
          <thead><tr><th>channel</th><th>windows</th><th>interesting</th><th>A</th><th>B</th></tr></thead>
          <tbody>{(ex.per_channel ?? []).map(r => <tr key={r.channel}><td>{r.name ?? `CH${r.channel}`}</td><td>{fmtInt(r.n)}</td><td>{fmtInt(r.interesting)}</td>{r.one_class
            ? <td colSpan={2} className="m-muted" data-testid={`one-class-${r.channel}`}>one class only — no macro F1 · accuracy A {f3(r.accuracy_A)} · B {f3(r.accuracy_B)}</td>
            : <><td>{f3(r.A)}</td><td>{f3(r.B)}</td></>}</tr>)}</tbody>
        </table>
      </SectionCard>
      <Calibration res={res} arm={arm} />
    </>
  )
}

function Calibration({ res, arm }: { res: PairedResults; arm: PairedArm }) {
  const c = res.calibration[arm]
  return (
    <SectionCard title="Calibration · validation block" testid="calibration-card"
      info="Reliability of P(interesting) on the validation block, and the lowest threshold that reaches the target precision there — the value Analyse's threshold stage would recommend when this model feeds it.">
      {!c.n ? <div className="m-foot-line" data-testid="calibration-unavailable">{c.reason}</div> : (
        <>
          <div className="m-foot-line" data-testid="calibration-grid">
            {fmtInt(c.n)} validation windows · {fmtInt(c.n_positive ?? 0)} interesting · ECE {f3(c.ece)} ·
            {c.suggested ? ` threshold ${c.suggested.threshold.toFixed(3)} reaches precision ${c.suggested.precision.toFixed(3)} (target ${c.target_precision}) at recall ${c.suggested.recall.toFixed(3)}` : ` ${c.suggested_reason}`}
          </div>
          <table className="m-table">
            <thead><tr><th>P(interesting)</th><th>windows</th><th>mean P</th><th>fraction interesting</th></tr></thead>
            <tbody>{(c.bins ?? []).map(b => <tr key={b.lo}><td>{b.lo.toFixed(1)}–{b.hi.toFixed(1)}</td><td>{fmtInt(b.n)}</td><td>{b.mean_p.toFixed(3)}</td><td>{b.fraction_positive.toFixed(3)}</td></tr>)}</tbody>
          </table>
        </>
      )}
      <div className="m-foot-line m-small" data-testid="curves-unavailable">training curves: none — a random forest has no epochs; early stopping applies to the CNN arm.</div>
    </SectionCard>
  )
}

function Training({ res, arm }: { res: PairedResults; arm: PairedArm }) {
  const t = res.training[arm]
  return (
    <SectionCard title={`Arm ${arm} · what it was trained on`} testid="training-card">
      <div className="m-foot-line">{fmtInt(t.n_train)} training windows (the same for both arms) · {t.label_source} labels · {t.n_classes} classes
        {arm === 'B' && <> · clusters {Object.entries(res.cluster.sizes).map(([c, n]) => `${c}: ${n}`).join(', ')} · translation {Object.entries(res.cluster.translation).map(([c, v]) => `${c}→${v === 'interesting' ? 'int' : 'not'}`).join(' ')} ({res.cluster.translation_source})</>}
        · forest {t.classifier.n_estimators} trees, seed {t.classifier.random_state}</div>
      <div className="m-foot-line m-small">most important features: {t.feature_importance.slice(0, 6).map(f => `${f.feature} ${f.importance.toFixed(3)}`).join(' · ')}</div>
      <div className="m-foot-line m-small">features kept: {res.features.kept.length} · dropped {Object.entries(res.features.removed).filter(([, v]) => v.length).map(([k, v]) => `${k}: ${v.join(', ')}`).join(' · ') || 'none'}</div>
    </SectionCard>
  )
}

function Reference({ res }: { res: PairedResults }) {
  return (
    <SectionCard title="Reference line · the existing MODELS/" testid="reference-card" subtitle="trained differently — not an arm"
      info="Scored on the same exams where their inputs allow. Their training data and split were never recorded; they were very likely trained on the same 10-minute labels, so an exam window may have been one of their training windows.">
      <table className="m-table">
        <thead><tr><th>model</th><th>exam (i)</th><th>exam (ii)</th><th>exam (iii)</th><th>note</th></tr></thead>
        <tbody>{res.reference.map(r => (
          <tr key={r.name} data-testid={`reference-${r.name}`}>
            <td>{r.name}</td>
            {EXAMS.map(e => { const x = r.exams?.[e]; return <td key={e}>{x?.status === 'scored' ? `${f3(x.macro_f1)} (n ${fmtInt(x.n ?? 0)})` : x?.status ?? r.status}</td> })}
            <td className="m-small">{r.status === 'scored' ? <InfoTip title="Trained differently">{r.trained_differently}</InfoTip> : r.reason}</td>
          </tr>))}</tbody>
      </table>
    </SectionCard>
  )
}
