/* models.results (frame models-3; spec §7b.3). One arm of one training job on the test block: headline metrics, the
 * arm against its RF baseline and the label-shuffle null, confusion + per-class, calibration with suggested
 * thresholds, training curves and the held-out checks that gate registration. */
import { useRef } from 'react'
import {
  Badge, Button, Chip, Checklist, DisabledReason, EmptyState, Histogram, Icon, InfoTip, Legend, LineChart, Page, Popover, ProgressBar,
  SectionCard, Seg, StatTile, useDemoWrites, useQueryState, type CheckState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, useApp } from '../state'
import { useSourced } from '../api/seam'
import {
  CAL_TARGETS, CLASS_COLOUR, CLASS_SHORT, MODEL_CLASSES, getJobResults, getResultJobs, suggestionFor,
  type ArmKey, type ArmResult, type CalTarget, type JobResults, type ModelClass, type ResultsJob,
} from '../api/models'
import { JobLink, Loading, LoadFailed, ModelsTabs, NullChip, f2 } from './chrome'

const ARM_OPTIONS: { value: ArmKey; label: string }[] = [
  { value: 'a', label: 'A · manual labels' },
  { value: 'b', label: 'B · cluster labels' },
  { value: 'rf', label: 'RF baseline' },
]
const ARM_LETTER: Record<ArmKey, 'A' | 'B' | 'RF'> = { a: 'A', b: 'B', rf: 'RF' }
const ARM_COLOUR_VAR: Record<ArmKey, string> = { a: 'var(--green)', b: 'var(--purple)', rf: '#4b5563' }

export function ResultsPage() {
  const { route } = useApp()
  const jobId = route.parts[1] || 'j-0212'
  const [stateQ] = useQueryState('state', '')
  const [arm, setArm] = useQueryState<ArmKey>('arm', 'a')
  const jobs = useSourced(getResultJobs, [])
  const res = useSourced(() => getJobResults(jobId), [jobId])
  const empty = stateQ === 'empty'
  const listed = jobs.data?.find(j => j.id === jobId)
  // a rejected read keeps the previous job's data in the hook — never show it beside another job's id
  const data = res.error ? null : res.data
  const job = data?.job ?? listed
  const subtitle = empty ? 'no training results imported yet' : job ? `${job.template} · ${job.id} · ${job.session}` : jobId
  const demo = res.source === 'demo' || jobs.source === 'demo'

  return (
    <>
      <Header workspace="Models" page="Results" subtitle={subtitle} demo={demo} />
      <Page testid="models-results">
        <Toolbar job={job} jobs={jobs.data ?? []} jobId={jobId} arm={arm} results={data} empty={empty} />
        <ModelsTabs current="results"
          middle={<Seg testid="arm-seg" ariaLabel="label arm" options={ARM_OPTIONS} value={arm} onChange={v => setArm(v === 'a' ? null : v)} />}
          jobsLink={<JobLink id={jobId} status={job?.status ?? 'unknown'} />} />
        {empty ? (
          <EmptyState icon="inbox" bordered testid="results-empty" title="No training results imported yet"
            caption="a finished cluster job returns through Jobs › Manifest inbox; import it there and it appears here"
            action={<><Button icon="rocket" onClick={() => navigate('models/launch')}>Open Launch</Button>
              <Button icon="external" onClick={() => navigate('jobs?kind=cluster')}>Open Jobs</Button></>} />
        ) : res.error ? (
          <LoadFailed what={`the results of ${jobId}`} error={res.error} onRetry={res.reload}
            action={<Button size="sm" icon="external" onClick={() => navigate(`jobs/cluster/${jobId}`)}>Open {jobId} in Jobs</Button>} />
        ) : !data || res.loading ? <Loading />
          : data.arms == null ? <RunningBody job={data.job} />
            : <ResultsBody data={data} arm={arm} />}
      </Page>
    </>
  )
}

/* ---------------------------------------------------------------- toolbar ---------------------------------------------------------------- */
function Toolbar({ job, jobs, jobId, arm, results, empty }: { job?: ResultsJob; jobs: ResultsJob[]; jobId: string; arm: ArmKey; results: JobResults | null; empty: boolean }) {
  const { push } = useToast()
  const [popover, setPopover] = useQueryState('popover', '')
  const jobRef = useRef<HTMLButtonElement>(null)
  const launched = useDemoWrites('models').filter(w => w.kind === 'add-training-job')
  const armResult = results?.arms?.[arm] ?? null
  const finished = job?.status === 'finished'
  const registryId = armResult?.registryId ?? null

  return (
    <div className="m-toolbar" data-testid="results-toolbar">
      <span className="m-tool-chip strong" data-testid="model-chip">
        <Icon name="cpu" size={13} />{job?.template ?? 'training job'} · arm {ARM_LETTER[arm]}
      </span>
      <button ref={jobRef} type="button" className="m-tool-chip btn blue" data-testid="job-chip" aria-expanded={popover === 'job'}
        onClick={() => setPopover(popover === 'job' ? null : 'job')} title="pick another training job">
        {jobId} · test block · {armResult ? `${armResult.testWindows} windows` : job?.status ?? 'no results'}
        <Icon name="chevron-down" size={13} />
      </button>
      <Popover open={popover === 'job'} onClose={() => setPopover(null)} anchorRef={jobRef} title="Training jobs" width={360} testid="job-popover">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {jobs.map(j => (
            <button key={j.id} type="button" className="m-usedby" data-testid={`job-option-${j.id}`} style={{ cursor: 'pointer', textAlign: 'left', border: 0, width: '100%' }}
              onClick={() => { setPopover(null); navigate(`models/results/${j.id}`) }}>
              <span><span className="t">{j.id}</span> <span className="s">{j.title}</span><div className="s">{j.detail}</div></span>
              <span className="r"><Badge status={j.status} size="sm" /></span>
            </button>
          ))}
          {launched.map(w => (
            <DisabledReason key={w.seq} reason="a SLURM script was created for this job but nothing has been submitted or imported yet" block>
              <div className="m-usedby" data-testid={`job-option-${String(w.detail.id)}`}>
                <span><span className="t">{String(w.detail.id)}</span> <span className="s">{String(w.detail.template ?? '')} · this session</span></span>
                <span className="r"><Badge status="queued" size="sm" /></span>
              </div>
            </DisabledReason>
          ))}
        </div>
      </Popover>
      <span className="k-spacer" />
      <NullChip />
      <Button icon="compare" testid="compare-arms" disabled={!finished || empty}
        disabledReason={empty ? 'nothing imported yet — there are no arms to compare' : finished ? undefined : `${jobId} has no finished arms to compare`}
        onClick={() => navigate(`models/compare?a=cnn_windows_v3.${arm === 'b' ? 'cluster' : 'manual'}&b=cnn_windows_v3.${arm === 'b' ? 'manual' : 'cluster'}`)}>Compare arms</Button>
      <Button variant="primary" icon="arrow-right" testid="send-to-registry" disabled={!registryId || empty}
        disabledReason={arm === 'rf' ? 'the RF baseline is a reference, not a registrable model'
          : empty ? 'nothing imported yet — there is no trained model to send'
            : !finished ? `${jobId} has no finished model to register` : undefined}
        onClick={() => { push({ text: `${registryId} opened in the registry` }); navigate(`models/registry/${registryId}`) }}>Send to registry</Button>
    </div>
  )
}

/* ---------------------------------------------------------------- running ---------------------------------------------------------------- */
function RunningBody({ job }: { job: ResultsJob }) {
  return (
    <SectionCard title={`${job.id} is still running`} icon="hourglass" testid="results-running"
      subtitle={job.detail} actions={<Badge status="running" />}>
      <ProgressBar indeterminate label={`${job.session} · started ${job.since ?? 'today'}`} eta={job.overrun ? `${job.overrun} its estimate` : undefined} />
      <p className="m-mono m-small m-muted" style={{ marginTop: 10 }}>
        Results arrive through Jobs › Manifest inbox. Nothing is scored here until the manifest is imported — the test block is scored once, after training.
      </p>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <Button icon="external" onClick={() => navigate(`jobs/cluster/${job.id}`)} testid="running-open-jobs">Open {job.id} in Jobs</Button>
        <Button onClick={() => navigate('models/results/j-0212')}>Open the finished job instead</Button>
      </div>
    </SectionCard>
  )
}

/* ---------------------------------------------------------------- body ---------------------------------------------------------------- */
function ResultsBody({ data, arm }: { data: JobResults; arm: ArmKey }) {
  const r = data.arms![arm]
  return (
    <>
      <div className="m-stats" data-testid="results-stats">
        <StatTile variant="flat" label="macro F1 · test" value={f2(r.macroF1)} tone={arm === 'rf' ? undefined : 'green'} caption={`${f2(r.ci[0])}–${f2(r.ci[1])} · bootstrap over test blocks`} testid="stat-macro-f1" />
        <StatTile variant="flat" label="balanced accuracy" value={f2(r.balancedAcc)} caption={`${MODEL_CLASSES.length} classes`} />
        <StatTile variant="flat" label="RF baseline F1" value={f2(r.rfF1)} caption="same labels · same windows" />
        <StatTile variant="flat" label="label-shuffle null F1" value={f2(r.nullF1)} caption={`RF 200× · ${r.nullP}`} />
        <StatTile variant="flat" label="full-model shuffles" value={r.shuffles.length ? `${f2(r.shuffles[0])}–${f2(r.shuffles[r.shuffles.length - 1])}` : 'unavailable'}
          caption={r.shuffles.length ? '5×, within the RF null' : 'the RF baseline is its own null'} />
        <StatTile variant="flat" label="test windows" value={String(r.testWindows)} caption="scored once" />
      </div>

      <div className="m-grid2">
        <NullCard r={r} />
        <ConfusionCard r={r} />
      </div>

      <CalibrationCard r={r} />

      <div className="m-grid2">
        <CurvesCard r={r} />
        <ChecksCard r={r} />
      </div>
    </>
  )
}

/* ------------------------------- against baseline and null ------------------------------- */
function NullCard({ r }: { r: ArmResult }) {
  const letter = ARM_LETTER[r.arm]
  const colour = ARM_COLOUR_VAR[r.arm]
  return (
    <SectionCard title="Against baseline and null" subtitle="macro F1 on the test block" testid="null-card"
      info="The grey histogram is the RF baseline trained 200× on shuffled labels — what this task looks like with no signal in the labels. The dark dots are five full-model shuffles (each one a full retrain). The arm's own score sits to the right with its bootstrap CI.">
      <Histogram testid="null-plot" values={r.nullDist} domain={[0, 1]} nBins={26} height={200} colour="#d1d5db" showCounts={false}
        markers={r.arm === 'rf'
          ? [{ x: r.macroF1, label: `RF baseline ${f2(r.macroF1)}`, colour, band: r.ci }]
          : [
            { x: r.rfF1, label: `RF ${f2(r.rfF1)}`, colour: 'var(--text)' },
            { x: r.macroF1, label: `${letter} ${f2(r.macroF1)}`, colour, band: r.ci },
          ]}
        dots={r.shuffles.map(s => ({ x: s, colour: '#4b5563' }))} format={v => v.toFixed(1)} />
      <Legend items={[
        { label: 'RF label-shuffle null · 200×', colour: '#d1d5db' },
        { label: 'full-model shuffle · 5×', colour: '#4b5563', shape: 'dot' },
        { label: `arm ${letter} with 95 % CI`, colour },
      ]} />
      {!r.shuffles.length && <p className="m-mono m-small m-muted" style={{ marginTop: 6 }}>full-model shuffles: unavailable — the RF baseline is the thing being shuffled</p>}
    </SectionCard>
  )
}

/* ------------------------------- confusion ------------------------------- */
function ConfusionCard({ r }: { r: ArmResult }) {
  const rows = r.confusion
  const low = r.perClass.filter(p => p.n < 50).map(p => p.cls)
  return (
    <SectionCard title="Confusion" subtitle="rows = label · normalised per row" testid="confusion-card"
      info="Each row is one true class, coloured by the share of that row (counts printed). The diagonal is right; everything off it is where the model swaps one class for another.">
      <div className="m-grid2" style={{ gap: 18 }}>
        <div>
          <div className="m-conf" style={{ gridTemplateColumns: '78px repeat(4, minmax(0, 1fr))' }} data-testid="confusion-grid">
            <span />
            {MODEL_CLASSES.map(c => <span key={c} className="cl">{CLASS_SHORT[c]}</span>)}
            {MODEL_CLASSES.map((cls, i) => {
              const total = rows[i].reduce((a, b) => a + b, 0)
              return (
                <ConfusionRow key={cls} cls={cls} counts={rows[i]} total={total} />
              )
            })}
          </div>
          <div className="m-mono m-small m-muted" style={{ marginTop: 6, textAlign: 'right' }}>predicted →</div>
        </div>
        <div>
          <table className="m-table" data-testid="per-class-table">
            <thead><tr><th>class</th><th className="num">precision</th><th className="num">recall</th><th className="num">F1</th><th className="num">n</th></tr></thead>
            <tbody>
              {r.perClass.map(p => (
                <tr key={p.cls}>
                  <td style={{ fontWeight: 600 }}><span className="m-dot" style={{ background: CLASS_COLOUR[p.cls], marginRight: 6 }} />{p.cls}</td>
                  <td className="num">{f2(p.precision)}</td>
                  <td className="num">{f2(p.recall)}</td>
                  <td className="num">{f2(p.f1)}</td>
                  <td className={`num ${p.n < 50 ? 'm-amber-text' : ''}`}>{p.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {low.length > 0 && <div style={{ marginTop: 8 }}><Chip tone="amber" testid="few-windows-chip">{low.join(', ')}: few test windows · wide CI</Chip></div>}
        </div>
      </div>
    </SectionCard>
  )
}

function ConfusionRow({ cls, counts, total }: { cls: ModelClass; counts: number[]; total: number }) {
  return (
    <>
      <span className="rl">{cls}</span>
      {counts.map((v, j) => {
        const p = total ? v / total : 0
        const diagonal = MODEL_CLASSES[j] === cls
        const bg = diagonal ? `rgba(58,168,116,${(0.15 + 0.85 * p).toFixed(3)})` : `rgba(232,144,12,${(0.05 + 0.45 * p).toFixed(3)})`
        const colour = diagonal && p > 0.45 ? '#fff' : 'var(--text)'
        return (
          <span key={j} className="cell" style={{ background: bg, color: colour }} title={`${cls} predicted ${MODEL_CLASSES[j]}: ${v} of ${total} · ${Math.round(p * 100)} %`}>{v}</span>
        )
      })}
    </>
  )
}

/* ------------------------------- calibration ------------------------------- */
function CalibrationCard({ r }: { r: ArmResult }) {
  const { push } = useToast()
  const [target, setTarget] = useQueryState<CalTarget>('target', '0.8')
  if (!r.calibration) {
    return (
      <SectionCard title="Calibration and suggested thresholds" subtitle="validation block · one class at a time" testid="calibration-card">
        <EmptyState size="sm" bordered icon="circle-dashed" testid="calibration-unavailable" title="unavailable for the RF baseline"
          caption="the RF baseline is scored as a reference; no calibration was fitted and no threshold is recommended from it" />
      </SectionCard>
    )
  }
  return (
    <SectionCard title="Calibration and suggested thresholds" subtitle="validation block · one class at a time" testid="calibration-card"
      info="Reliability on the validation block: the green line is the observed rate at each score, the grey diagonal is perfect calibration. The amber line is the score that reaches the target precision — the value Analyse's Threshold to spans offers as its recommended threshold."
      actions={<>
        <Seg size="sm" label="target precision" testid="target-precision" options={CAL_TARGETS.map(t => ({ value: t, label: t }))} value={target} onChange={v => setTarget(v === '0.8' ? null : v)} />
        <Button variant="link" icon="link" testid="threshold-link"
          onClick={() => { push({ text: 'not wired yet: hand these thresholds to Analyse › Threshold to spans' }); navigate('analyse/chain') }}>
          used as the recommended value in Threshold to spans
        </Button>
      </>}>
      <div className="m-cal" data-testid="calibration-grid">
        {r.calibration.map(c => {
          const s = suggestionFor(r.arm, c.cls, target)
          return (
            <div key={c.cls} className="m-cal-item" data-testid={`calibration-${c.cls}`}>
              <div className="ttl">{c.cls}</div>
              <LineChart height={140} xDomain={[0, 1]} yDomain={[0, 1]} diagonal legend={false} xLabel="score" yLabel="observed"
                series={[{ label: 'observed', colour: 'var(--green)', points: c.curve, dots: true }]}
                markers={s ? [{ x: s.thr, label: s.thr.toFixed(2), colour: 'var(--amber)' }] : []} />
              <div className="m-cal-num">
                <span className="m-muted">suggested</span>
                <span className="big">{s ? s.thr.toFixed(2) : '—'}</span>
                <span>precision {s ? s.precision.toFixed(2) : '—'}</span>
                <span>recall {s ? s.recall.toFixed(2) : '—'}</span>
                <span className={c.ece > 0.10 ? 'm-amber-text' : ''}>ECE {c.ece.toFixed(2)}</span>
                <span className="m-muted">target precision {target}</span>
              </div>
            </div>
          )
        })}
      </div>
    </SectionCard>
  )
}

/* ------------------------------- training curves ------------------------------- */
function CurvesCard({ r }: { r: ArmResult }) {
  return (
    <SectionCard title="Training curves" subtitle="loss per epoch" testid="curves-card"
      info="Validation loss decides when training stops: the run keeps the weights from the marked epoch, so the epochs after it never reach the test block.">
      {!r.curves ? (
        <EmptyState size="sm" bordered icon="circle-dashed" testid="curves-unavailable" title="unavailable for the RF baseline"
          caption="a random forest is fitted in one pass — it has no epochs and no early stopping" />
      ) : (
        <LineChart testid="curves-plot" height={210} xDomain={[1, 30]} xLabel="epoch" yLabel="loss"
          series={[
            { label: 'train', colour: 'var(--blue)', points: r.curves.train },
            { label: 'validation', colour: 'var(--amber)', points: r.curves.val },
          ]}
          markers={r.earlyStop ? [{ x: r.earlyStop, label: `early stop · epoch ${r.earlyStop}`, colour: 'var(--muted)' }] : []} />
      )}
    </SectionCard>
  )
}

/* ------------------------------- held-out checks ------------------------------- */
function ChecksCard({ r }: { r: ArmResult }) {
  const checks = r.checks
  const count = (s: CheckState) => (checks ?? []).filter(c => c.state === s).length
  const summary = checks ? [
    count('pass') ? `${count('pass')} pass` : '',
    count('warn') ? `${count('warn')} warning` : '',
    count('fail') ? `${count('fail')} failed` : '',
    count('pending') ? `${count('pending')} pending` : '',
  ].filter(Boolean).join(' · ') : ''
  return (
    <SectionCard title="Held-out checks" subtitle="needed before registering" testid="checks-card"
      info="The automatic half of the registration gate (§7b.5). A failure blocks registration; a warning needs a written reason; human verification is judged in Review and finished in the Registry."
      actions={checks ? <Chip tone={count('fail') ? 'red' : count('warn') || count('pending') ? 'amber' : 'green'} testid="checks-summary">{summary}</Chip> : undefined}>
      {!checks ? (
        <EmptyState size="sm" bordered icon="circle-dashed" testid="checks-unavailable" title="unavailable for the RF baseline"
          caption="the RF baseline is not registrable — it is the reference the CNN arms are measured against" />
      ) : (
        <Checklist testid="checks-list" columns={2} items={checks.map(c => ({
          state: c.state,
          label: c.to
            ? <button type="button" className="m-jobs-link" style={{ fontSize: 'inherit' }} data-testid="check-to-registry" onClick={() => navigate(c.to!)}>{c.label}<Icon name="arrow-right" size={12} /></button>
            : c.label,
        }))} />
      )}
      {checks && (
        <div className="m-foot-line" style={{ marginTop: 10 }}>
          <InfoTip title="What happens next">Registration is decided in the Registry tab: the checks above, a judged verification sample and a written sign-off.</InfoTip>
          <span>the registry repeats these checks and adds human verification</span>
          <Button variant="link" size="sm" icon="arrow-right" testid="checks-open-registry"
            onClick={() => navigate(r.registryId ? `models/registry/${r.registryId}` : 'models/registry')}>Open in Registry</Button>
        </div>
      )}
    </SectionCard>
  )
}
