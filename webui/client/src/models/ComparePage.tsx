/* models.compare (spec §7b.4; fixup-ab). Arm A (manual labels) against arm B (cluster labels) of ONE paired run: what
 * differs between them (the label source, and nothing else — so the difference is attributable), per exam the paired
 * ΔF1 with its bootstrap CI, McNemar, the 2 × 2 agreement, per class and per channel, the cluster → class contingency
 * with the translation and purity, and a step through the windows only A, only B or neither got right. Read from
 * `/api/models/runs/{id}/compare` and `/disagreements`; nothing here is a fixture. */
import { useEffect, useState } from 'react'
import { Button, Callout, Dropdown, EmptyState, Heatmap, Histogram, Icon, Page, SectionCard, Seg, StatRow, StatTile, Trace, fmtInt, useQueryState } from '../kit'
import { Header } from '../shell/Header'
import { navigate, useApp } from '../state'
import { useSourced } from '../api/seam'
import {
  CLASS_NAMES, EXAM_TITLES, getPairedCompare, getPairedDisagreement, getPairedRuns,
  type CompareExam, type DisagreeFilter, type DisagreementLive, type ExamKey, type PairedCompare, type PairedRunRow,
} from '../api/models'
import { ArmBadge, Loading, LoadFailed, ModelsTabs, JobsPageLink } from './chrome'

const EXAMS: ExamKey[] = ['i_later_block', 'ii_unseen_channels', 'iii_held_out']
const f3 = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(3))
const ci = (c: [number | null, number | null] | undefined) => (!c || c[0] == null || c[1] == null ? '—' : `${c[0].toFixed(3)} – ${c[1].toFixed(3)}`)
const crossesZero = (c: [number | null, number | null] | undefined) => !c || c[0] == null || c[1] == null || (c[0] <= 0 && c[1] >= 0)

export function ComparePage() {
  const { route } = useApp()
  const runs = useSourced(getPairedRuns, [])
  const list: PairedRunRow[] = (runs.data?.runs ?? []).filter(r => r.status === 'completed')
  const runId = route.parts[1] ? Number(route.parts[1]) : list[0]?.run_id ?? null
  return (
    <>
      <Header workspace="Models" page="Compare" subtitle="A manual vs B cluster · one paired run" />
      <Page testid="models-compare">
        {runs.error ? <LoadFailed what="the training runs" error={runs.error} onRetry={runs.reload} />
          : !runs.data ? <Loading />
            : runId == null ? (
              <>
                <ModelsTabs current="compare" jobsLink={<JobsPageLink />} />
                <EmptyState icon="compare" bordered testid="compare-empty" title="Nothing to compare yet"
                  caption="A paired run trains arm A and arm B on the same windows; train one on Models › Launch."
                  action={<Button variant="primary" icon="rocket" onClick={() => navigate('models/launch')}>Open Launch</Button>} />
              </>
            ) : <CompareRun runId={runId} runs={list} />}
      </Page>
    </>
  )
}

function CompareRun({ runId, runs }: { runId: number; runs: PairedRunRow[] }) {
  const cmp = useSourced(() => getPairedCompare(runId), [runId])
  const [examQ, setExam] = useQueryState<ExamKey>('exam', 'i_later_block')
  const picker = (
    <Dropdown prefix="run" value={String(runId)} onChange={v => navigate(`models/compare/${v}`)} testid="run-select" width={280}
      options={runs.map(r => ({ value: String(r.run_id), label: `${r.run_id} · ${r.window_set?.name ?? '?'} · k = ${r.k}` }))} />
  )
  if (cmp.error) return <><ModelsTabs current="compare" jobsLink={<JobsPageLink />} middle={picker} /><LoadFailed what={`the comparison of run ${runId}`} error={cmp.error} onRetry={cmp.reload} /></>
  if (!cmp.data) return <><ModelsTabs current="compare" jobsLink={<JobsPageLink />} middle={picker} /><Loading /></>
  const c = cmp.data
  const ex = c.exams[examQ]
  return (
    <>
      <ModelsTabs current="compare" jobsLink={<JobsPageLink />} middle={picker} />
      <div className="m-foot-line" data-testid="pair-chip"><ArmBadge letter="A" /> manual labels <span className="m-muted">vs</span> <ArmBadge letter="B" /> cluster labels · run {runId} · recipe {c.recipe_hash}</div>
      <div className="m-foot-line" style={{ flexWrap: 'wrap', gap: 6 }} data-testid="differs">
        {c.differs.map(d => <span key={d.name} className={`k-chip sm ${d.same ? 'grey' : 'purple'}`} title={d.same ? `${d.name}: equal (${d.a})` : `${d.name}: A ${d.a} · B ${d.b}`}>{d.same ? '=' : '≠'} {d.name}</span>)}
        <span className={`k-chip sm ${c.attributable ? 'green' : 'amber'}`} data-testid="attribution-note">{c.attributable ? 'one difference — the label source — so the difference is attributable to it' : 'more than one difference — not attributable'}</span>
      </div>
      <Callout tone="blue" icon="info" testid="tilt-note">{c.notes[0]}</Callout>
      <Seg value={examQ} onChange={v => setExam(v)} testid="exam-seg" ariaLabel="exam"
        options={EXAMS.map(e => ({ value: e, label: EXAM_TITLES[e].split(' · ')[0], disabled: c.exams[e].status !== 'scored', reason: c.exams[e].reason ?? c.exams[e].status }))} />
      <div className="m-foot-line">{EXAM_TITLES[examQ]} · reported on its own, never pooled with the others</div>
      {ex.status !== 'scored' ? <Callout tone={ex.status === 'locked' ? 'blue' : 'amber'} icon={ex.status === 'locked' ? 'lock' : 'info'} testid="paired-unavailable">{ex.reason}</Callout>
        : <PairedExam c={c} ex={ex} runId={runId} exam={examQ} />}
      <ClusterMap c={c} />
      <SectionCard title="Yardstick (B)" testid="yardstick-b"><div className="m-foot-line"><span className="k-chip sm grey">{c.yardstick_b.status}</span> {c.yardstick_b.note}</div></SectionCard>
    </>
  )
}

function PairedExam({ c, ex, runId, exam }: { c: PairedCompare; ex: CompareExam; runId: number; exam: ExamKey }) {
  const a = ex.arms!.A, b = ex.arms!.B
  const ag = ex.agreement!
  const [filterQ, setFilter] = useQueryState<DisagreeFilter>('filter', 'only_a')
  const grid: { key: DisagreeFilter | 'both_right'; label: string; n: number }[] = [
    { key: 'both_right', label: 'both right', n: ag.both_right }, { key: 'only_a', label: 'only A right', n: ag.only_a },
    { key: 'only_b', label: 'only B right', n: ag.only_b }, { key: 'both_wrong', label: 'both wrong', n: ag.both_wrong },
  ]
  return (
    <>
      <StatRow columns={4}>
        <StatTile label="macro F1 · A manual" value={f3(a.macro_f1)} caption={`CI ${ci(a.macro_f1_ci)} · null 5–95 % ${a.null_band.map(v => v.toFixed(3)).join('–')}`} testid="macro-a" />
        <StatTile label="macro F1 · B cluster" value={f3(b.macro_f1)} caption={`CI ${ci(b.macro_f1_ci)} · null 5–95 % ${b.null_band.map(v => v.toFixed(3)).join('–')}`} testid="macro-b" />
        <StatTile label="ΔF1 = A − B" value={f3(ex.delta_f1)} caption={`95 % CI ${ci(ex.delta_f1_ci)} · ${ex.n_units} units of ${ex.unit}`} tone={crossesZero(ex.delta_f1_ci) ? 'muted' : 'green'} testid="macro-forest" />
        <StatTile label="McNemar" value={`p ${ex.mcnemar!.p.toFixed(4)}`} caption={`only A right ${ex.mcnemar!.b} · only B right ${ex.mcnemar!.c} · ${ex.mcnemar!.method}`} testid="mcnemar" />
      </StatRow>
      <div className="m-cols" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <SectionCard title="Paired difference" testid="paired-diff" info="ΔF1 under the same block-bootstrap resamples for both arms; the line at zero is no difference.">
          <Histogram values={ex.delta_draws_sample ?? []} nBins={30} height={160} xLabel="ΔF1 (A − B)" testid="delta-hist"
            markers={[{ x: 0, label: '0', colour: 'var(--muted)' }, { x: ex.delta_f1!, label: 'ΔF1', colour: 'var(--purple)' }]} />
          <table className="m-table" data-testid="per-class-delta">
            <thead><tr><th>class</th><th>F1 A</th><th>F1 B</th><th>ΔF1 (95 % CI)</th></tr></thead>
            <tbody>{CLASS_NAMES.map(n => { const d = ex.per_class_delta![n]; return (
              <tr key={n} style={crossesZero(d.ci) ? { color: 'var(--muted)' } : undefined}><td>{n}</td><td>{f3(a.per_class[n].f1)}</td><td>{f3(b.per_class[n].f1)}</td><td>{f3(d.delta)} ({ci(d.ci)})</td></tr>) })}</tbody>
          </table>
        </SectionCard>
        <SectionCard title="Agreement, window by window" testid="agreement-card" info="Each test window: did A get the human verdict, did B? Click a cell to step through its windows.">
          <div className="m-agree" data-testid="agreement-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {grid.map(g => (
              <button key={g.key} type="button" className={`k-card m-row-click${g.key === filterQ ? ' selected' : ''}`} style={{ padding: 10, textAlign: 'left' }}
                data-testid={`cell-${g.key.replace('_', '-')}`} disabled={g.key === 'both_right'} onClick={() => g.key !== 'both_right' && setFilter(g.key)}>
                <div className="m-small m-muted">{g.label}</div><div style={{ fontSize: 20, fontWeight: 600 }}>{fmtInt(g.n)}</div>
              </button>))}
          </div>
          <table className="m-table" style={{ marginTop: 8 }} data-testid="per-channel">
            <thead><tr><th>channel</th><th>windows</th><th>A</th><th>B</th></tr></thead>
            <tbody>{(ex.per_channel ?? []).map(r => <tr key={r.channel}><td>{r.name ?? `CH${r.channel}`}</td><td>{fmtInt(r.n)}</td>{r.one_class
              ? <td colSpan={2} className="m-muted">one class only · accuracy {f3(r.accuracy_A)} / {f3(r.accuracy_B)}</td>
              : <><td>{f3(r.A)}</td><td>{f3(r.B)}</td></>}</tr>)}</tbody>
          </table>
        </SectionCard>
      </div>
      <StepThrough runId={runId} exam={exam} filter={filterQ === ('both_right' as any) ? 'only_a' : filterQ} counts={{ only_a: ag.only_a, only_b: ag.only_b, both_wrong: ag.both_wrong }} setFilter={setFilter} />
      <ReferenceRows c={c} exam={exam} />
    </>
  )
}

function StepThrough({ runId, exam, filter, counts, setFilter }: { runId: number; exam: ExamKey; filter: DisagreeFilter; counts: Record<DisagreeFilter, number>; setFilter: (f: DisagreeFilter) => void }) {
  const [iQ, setI] = useQueryState('i', '1')
  const i = Math.max(1, Number(iQ) || 1)
  const [w, setW] = useState<DisagreementLive | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    if (!counts[filter]) { setW(null); setErr(null); return }
    let alive = true
    getPairedDisagreement(runId, filter, Math.min(i, counts[filter]), exam).then(d => { if (alive) { setW(d); setErr(null) } }, e => { if (alive) setErr(e.message) })
    return () => { alive = false }
  }, [runId, exam, filter, i, counts])
  const n = counts[filter]
  return (
    <SectionCard title="Step through the disagreements" testid="step-through"
      actions={<Seg size="sm" value={filter} onChange={v => { setFilter(v); setI(null) }} testid="filter-seg"
        options={[{ value: 'only_a', label: `only A right · ${counts.only_a}` }, { value: 'only_b', label: `only B right · ${counts.only_b}` }, { value: 'both_wrong', label: `both wrong · ${counts.both_wrong}` }]} />}>
      {err ? <Callout tone="red" testid="step-error">{err}</Callout> : !n ? <div className="m-foot-line" data-testid="step-empty">no window here</div> : !w ? <Loading height={160} /> : (
        <>
          <div className="m-foot-line" data-testid="window-id">
            {w.window.channel_name} · {(w.window.start / w.window.fs / 3600).toFixed(2)}–{(w.window.end / w.window.fs / 3600).toFixed(2)} h ·
            human <span className="k-chip sm grey">{w.human}</span> · A <span className={`k-chip sm ${w.a === w.human ? 'green' : 'red'}`} data-testid="pred-a">{w.a}</span>
            · B <span className={`k-chip sm ${w.b === w.human ? 'green' : 'red'}`} data-testid="pred-b">{w.b}</span>
          </div>
          <Trace values={w.trace} fs={w.trace.length / Math.max(1, (w.window.end - w.window.start) / w.window.fs)} timeUnit="s" height={150} testid="step-trace" unitLabel />
          <div className="m-foot-line" data-testid="step-pager">
            <Button size="sm" icon="chevron-left" disabled={i <= 1} disabledReason="the first window" onClick={() => setI(String(i - 1))}>Prev</Button>
            <span>{Math.min(i, n)} of {fmtInt(n)}</span>
            <Button size="sm" iconRight="chevron-right" disabled={i >= n} disabledReason="the last window" onClick={() => setI(String(i + 1))}>Next</Button>
            <span className="k-spacer" />
            <Button size="sm" variant="link" icon="external" onClick={() => navigate(`explore/signal/${w.window.recording_id}`)} testid="open-in-explore">Open the channel in Explore</Button>
            <span className="m-muted m-small"><Icon name="info" size={11} /> re-checking a verdict goes through Review</span>
          </div>
        </>
      )}
    </SectionCard>
  )
}

function ReferenceRows({ c, exam }: { c: PairedCompare; exam: ExamKey }) {
  const rows = c.reference.filter(r => r.exams?.[exam]?.status === 'scored')
  if (!rows.length) return <div className="m-foot-line m-small" data-testid="reference-none">reference line: {c.reference[0]?.reason ?? 'not scored on this exam'}</div>
  return (
    <div className="m-foot-line m-small" data-testid="reference-line">reference line, trained differently (not an arm): {rows.map(r => `${r.name} ${f3(r.exams![exam].macro_f1)}`).join(' · ')}</div>
  )
}

function ClusterMap({ c }: { c: PairedCompare }) {
  const cl = c.cluster
  const rows = cl.contingency.map((_, i) => `cluster ${i + 1} → ${cl.translation[String(i + 1)]}`)
  const shares = cl.contingency.map(r => { const s = r[0] + r[1] || 1; return [r[0] / s, r[1] / s] })
  return (
    <SectionCard title="Cluster → class" testid="cluster-mapping" subtitle={`Ward · k = ${cl.k} · on ${fmtInt(cl.n_windows)} training windows · translation: ${cl.translation_source}`}
      info="How arm B's clusters fall against the human verdicts on the TRAINING windows, and the translation table the recipe fixed. A cluster whose majority class is under 75 % is flagged impure.">
      <Heatmap rows={rows} cols={[...cl.contingency_columns]} values={shares} format={v => `${Math.round(v * 100)} %`} testid="cluster-heatmap" rowLabelWidth={220}
        flagged={(r) => !!cl.purity[r]?.impure} />
      <div className="m-foot-line m-small">
        {cl.purity.map(p => <span key={p.cluster} style={{ marginRight: 10 }}>{p.cluster}: {fmtInt(p.n)} windows{p.impure && <span className="k-chip amber sm" style={{ marginLeft: 4 }} data-testid="impure-chip">impure</span>}</span>)}
        {cl.silhouette != null && <span>· silhouette {cl.silhouette.toFixed(3)}</span>}
      </div>
    </SectionCard>
  )
}
