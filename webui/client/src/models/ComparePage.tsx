/* models.compare (frames models-4, models-4b; spec §7b.4). Any two models side by side — the frame's case is the
 * paired j-0212 arms, manual labels vs cluster labels: what differs, macro F1 over the null band, the paired
 * difference, the cluster → manual mapping, per-window agreement, per channel, and a step through the windows the
 * two arms disagree on (4b: the windows both got wrong). */
import { useRef } from 'react'
import {
  Badge, Button, Chip, EmptyState, Histogram, Icon, InfoTip, Legend, Heatmap, Page, Pager, Popover, SectionCard, Seg, Trace,
  useQueryState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, setQuery } from '../state'
import { useSourced } from '../api/seam'
import {
  CLASS_COLOUR, CLASS_SHORT, FILTER_COUNTS, FILTER_FRAME_INDEX, MODEL_CLASSES, getCompare, getDisagreement,
  type CompareData, type CompareModel, type Disagreement, type DisagreementFilter,
} from '../api/models'
import { ArmBadge, JobLink, Loading, LoadFailed, ModelsTabs, NullChip, f2, signed } from './chrome'

const A_COLOUR = 'var(--green)', B_COLOUR = 'var(--purple)'
const FILTERS: { value: DisagreementFilter; label: string }[] = [
  { value: 'only-a', label: 'only A right' },
  { value: 'only-b', label: 'only B right' },
  { value: 'both-wrong', label: 'both wrong' },
]

export function ComparePage() {
  const cmp = useSourced(getCompare, [])
  const [aId] = useQueryState('a', 'cnn_windows_v3.manual')
  const [bId] = useQueryState('b', 'cnn_windows_v3.cluster')
  const a = cmp.data?.models.find(m => m.id === aId), b = cmp.data?.models.find(m => m.id === bId)
  const subtitle = a && b ? `A ${a.short} labels · B ${b.short} labels` : 'A manual labels · B cluster labels'
  return (
    <>
      <Header workspace="Models" page="Compare" subtitle={subtitle} demo={cmp.source === 'demo'} />
      <Page testid="models-compare">
        {cmp.error ? <LoadFailed what="the model comparison" error={cmp.error} onRetry={cmp.reload} />
          : !cmp.data ? <Loading />
            : <CompareBody data={cmp.data} />}
      </Page>
    </>
  )
}

function CompareBody({ data }: { data: CompareData }) {
  const { push } = useToast()
  const [aId, setA] = useQueryState('a', 'cnn_windows_v3.manual')
  const [bId, setB] = useQueryState('b', 'cnn_windows_v3.cluster')
  const [popover, setPopover] = useQueryState('popover', '')
  const [filter, setFilterQ] = useQueryState<DisagreementFilter>('filter', 'only-a')
  const [iQ, setI] = useQueryState('i', String(FILTER_FRAME_INDEX['only-a']))
  const jobRef = useRef<HTMLButtonElement>(null)

  const a = data.models.find(m => m.id === aId) ?? data.models[0]
  const b = data.models.find(m => m.id === bId) ?? data.models[1]
  const paired = a.job === b.job && a.testWindows === b.testWindows
  const clusterArm = a.labelKind === 'cluster' ? a : b.labelKind === 'cluster' ? b : null
  const bothCluster = a.labelKind === 'cluster' && b.labelKind === 'cluster'

  const differs = [
    { key: 'template', label: 'template', av: a.template, bv: b.template },
    { key: 'window set', label: 'window set', av: a.windowSet, bv: b.windowSet },
    { key: 'split', label: 'split + test block', av: a.split, bv: b.split },
    { key: 'classifier', label: 'classifier + options', av: a.classifier, bv: b.classifier },
    { key: 'label source', label: 'label source', av: a.labelSource, bv: b.labelSource },
  ]
  const nDiff = differs.filter(d => d.av !== d.bv).length
  const attributable = nDiff === 1
  const notAttributable = attributable ? null
    : nDiff === 0 ? 'A and B are the same model — nothing to attribute'
      : `${nDiff} differences — a difference in score cannot be attributed to any one of them`
  const notPaired = paired ? null
    : `A and B were scored on different test windows (${a.testWindows} vs ${b.testWindows}) — they are not paired`

  const setFilter = (f: DisagreementFilter) => { setQuery({ filter: f === 'only-a' ? null : f, i: String(FILTER_FRAME_INDEX[f]) }) }
  const i = Math.min(Math.max(1, Number(iQ) || 1), FILTER_COUNTS[filter])

  return (
    <>
      {/* ------------------------------------------------ toolbar ------------------------------------------------ */}
      <div className="m-toolbar" data-testid="compare-toolbar">
        <span className="m-tool-chip strong" data-testid="pair-chip"><Icon name="compare" size={13} />A {a.short} vs B {b.short}</span>
        <button ref={jobRef} type="button" className="m-tool-chip btn blue" data-testid="job-chip" aria-expanded={popover === 'job'}
          onClick={() => setPopover(popover === 'job' ? null : 'job')} title="the job these two models came from">
          {paired ? `${a.job} · paired · ${a.testWindows} test windows` : `${a.job} vs ${b.job} · not paired`}<Icon name="chevron-down" size={13} />
        </button>
        <Popover open={popover === 'job'} onClose={() => setPopover(null)} anchorRef={jobRef} title="Jobs behind this pair" width={340} testid="job-popover">
          <div className="m-mono m-small" style={{ display: 'grid', gap: 6 }}>
            <div><ArmBadge letter="A" /> {a.label} · <strong>{a.job}</strong> · {a.testWindows} test windows</div>
            <div><ArmBadge letter="B" /> {b.label} · <strong>{b.job}</strong> · {b.testWindows} test windows</div>
            <div className="m-muted">j-0214 (running) has no scored test block yet — it cannot be compared.</div>
            <Button size="sm" icon="external" onClick={() => navigate(`jobs/cluster/${a.job}`)}>Open {a.job} in Jobs</Button>
          </div>
        </Popover>
        <span className="k-spacer" />
        <NullChip />
        <Button icon="shuffle" testid="swap-ab" onClick={() => setQuery({ a: b.id === 'cnn_windows_v3.manual' ? null : b.id, b: a.id })}>Swap A / B</Button>
      </div>
      <ModelsTabs current="compare" jobsLink={<JobLink id={a.job} status={a.job === 'j-0212' ? 'finished' : 'imported'} />} />

      {/* ------------------------------------------------ pickers ------------------------------------------------ */}
      <SectionCard title="Two models" subtitle="scored against human verdicts on the same test windows" testid="picker-card"
        info="Pick any two models. The comparison is only attributable when exactly one thing differs between them — the frame's case is one paired job whose two arms differ only in where the labels came from."
        actions={<Button variant="link" icon="list" testid="any-two-models" onClick={() => setPopover(popover === 'models' ? null : 'models')}>any two models</Button>}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <ModelPicker letter="A" model={a} models={data.models} onPick={id => setA(id === 'cnn_windows_v3.manual' ? null : id)} other={b.id} />
          <ModelPicker letter="B" model={b} models={data.models} onPick={id => setB(id === 'cnn_windows_v3.cluster' ? null : id)} other={a.id} />
          {paired ? <Chip tone="green" testid="paired-chip">paired · same test windows</Chip>
            : <Chip tone="amber" testid="paired-chip">not paired · {a.testWindows} vs {b.testWindows} test windows</Chip>}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 10 }} data-testid="what-differs">
          <span className="m-mono m-small m-muted">what differs</span>
          {differs.map(d => (
            <span key={d.key} className={`m-pill ${d.av === d.bv ? '' : 'differs'}`} title={d.av === d.bv ? `both: ${d.av}` : `A: ${d.av} · B: ${d.bv}`}>
              {d.av === d.bv ? (d.av === d.label ? `= ${d.label}` : `= ${d.label} ${d.av}`) : `≠ ${d.label} · ${d.av} vs ${d.bv}`}
            </span>
          ))}
          <span className="k-spacer" />
          <span style={{ marginLeft: 'auto' }}>
            {attributable ? <Chip tone="green" testid="attributable-chip">one difference — attributable</Chip>
              : <Chip tone="amber" testid="attributable-chip">{nDiff} difference{nDiff === 1 ? '' : 's'} — cannot be attributed</Chip>}
          </span>
        </div>
      </SectionCard>
      <AllModelsPopover open={popover === 'models'} onClose={() => setPopover(null)} models={data.models} a={a} b={b}
        onPick={(id, letter) => { letter === 'A' ? setA(id) : setB(id); setPopover(null) }} />

      {/* ------------------------------------------------ metrics ------------------------------------------------ */}
      <div className="m-grid2">
        <SectionCard title="Macro F1 against baseline and null" subtitle="both scored against human verdicts on the test block" testid="forest-card"
          info="Each row is one model's macro F1 with its 95 % bootstrap CI. The grey band is the label-shuffle null — a score inside it is a score with no evidence behind it.">
          <Forest testid="macro-forest" domain={[0, 1]} labelWidth={132} band={{ lo: data.nullBand[0], hi: data.nullBand[1], label: 'label-shuffle null' }}
            rows={[
              { label: `A · ${a.short}`, value: a.macroF1, ci: a.ci, colour: A_COLOUR },
              { label: `B · ${b.short}`, value: b.macroF1, ci: b.ci, colour: B_COLOUR },
              { label: `RF · ${a.labelSource === b.labelSource ? 'A labels' : `${a.short} labels`}`, value: a.rfF1, ci: a.rfCi, colour: '#374151' },
              { label: `RF · ${b.short} labels`, value: b.rfF1, ci: b.rfCi, colour: '#9ca3af' },
            ]} />
        </SectionCard>

        <SectionCard title="Paired difference A − B" subtitle="bootstrap over test blocks" testid="paired-card"
          info="The same test windows scored by both models, so the difference can be bootstrapped as a pair. The shaded band is the 95 % CI; if it covers 0 the difference is not established.">
          {!paired ? <Unavailable testid="paired-unavailable" reason={notPaired!} />
            : (
              <div className="m-grid2" style={{ gap: 14 }}>
                <div>
                  <Histogram testid="paired-density" values={data.pairedDist} domain={[-0.1, 0.3]} nBins={34} height={170} colour="#cfe9db" showCounts={false}
                    format={v => v.toFixed(2)}
                    markers={[
                      { x: 0, label: '0', colour: 'var(--text)' },
                      { x: data.paired.delta, label: `ΔF1 ${signed(data.paired.delta)}`, colour: 'var(--green)', band: data.paired.ci },
                    ]} />
                  <div style={{ marginTop: 4 }}>
                    <span className="m-green-text" style={{ fontSize: 19, fontWeight: 700 }} data-testid="delta-f1">ΔF1 {signed(data.paired.delta)}</span>
                    <span className="m-mono m-small m-muted" style={{ marginLeft: 8 }}>95 % CI {f2(data.paired.ci[0])}–{f2(data.paired.ci[1])} · McNemar p = {data.paired.mcnemarP}</span>
                  </div>
                </div>
                <div>
                  <div className="m-mono m-small m-muted" style={{ marginBottom: 4 }}>per class</div>
                  <Forest testid="per-class-forest" domain={[-0.2, 0.3]} zero labelWidth={78} valueWidth={44}
                    rows={data.perClassDelta.map(d => ({
                      label: d.cls, value: d.d, ci: d.ci,
                      colour: d.ci[0] <= 0 && d.ci[1] >= 0 ? '#9ca3af' : 'var(--green)',
                      format: signed,
                    }))} />
                  <div className="m-mono m-small m-muted" style={{ marginTop: 6 }}>
                    CI crosses 0 for {data.perClassDelta.filter(d => d.ci[0] <= 0 && d.ci[1] >= 0).map(d => d.cls).join(', ')}
                  </div>
                </div>
              </div>
            )}
        </SectionCard>
      </div>

      {/* ------------------------------------------------ three cards ------------------------------------------------ */}
      <div className="m-grid3">
        <ClusterMapCard data={data} available={!!clusterArm} bothCluster={bothCluster} />
        <SectionCard title="Per-window agreement" subtitle={`${a.testWindows} test windows`} testid="agreement-card"
          info="Every test window falls in one of four boxes. The two discordant boxes are what McNemar's test compares — click one to step through its windows.">
          {!paired ? <Unavailable testid="agreement-unavailable" reason={notPaired!} />
            : (
              <>
                <div className="m-agree" data-testid="agreement-grid">
                  <span />
                  <span className="m-muted" style={{ textAlign: 'center' }}>B right</span>
                  <span className="m-muted" style={{ textAlign: 'center' }}>B wrong</span>
                  <span className="m-muted" style={{ alignSelf: 'center' }}>A right</span>
                  <div className="q" style={{ background: '#eaf7f0' }} data-testid="cell-both-right">
                    <span className="n">{data.agreement.bothRight}</span><span className="l">both right</span>
                  </div>
                  <button type="button" className={`q ${filter === 'only-a' ? 'on' : ''}`} style={{ background: '#cdebda' }} data-testid="cell-only-a"
                    onClick={() => setFilter('only-a')} title="step through the windows only A got right">
                    <span className="n">{data.agreement.onlyA}</span><span className="l">only A right</span>
                  </button>
                  <span className="m-muted" style={{ alignSelf: 'center' }}>A wrong</span>
                  <button type="button" className={`q ${filter === 'only-b' ? 'on' : ''}`} style={{ background: '#e7dcfb' }} data-testid="cell-only-b"
                    onClick={() => setFilter('only-b')} title="step through the windows only B got right">
                    <span className="n">{data.agreement.onlyB}</span><span className="l">only B right</span>
                  </button>
                  <button type="button" className={`q ${filter === 'both-wrong' ? 'on' : ''}`} style={{ background: '#eef0f3' }} data-testid="cell-both-wrong"
                    onClick={() => setFilter('both-wrong')} title="step through the windows both got wrong">
                    <span className="n">{data.agreement.bothWrong}</span><span className="l">both wrong</span>
                  </button>
                </div>
                <div className="m-mono m-small m-muted" style={{ marginTop: 8 }}>
                  {data.agreement.onlyA} vs {data.agreement.onlyB} discordant · McNemar p = {data.paired.mcnemarP}
                </div>
              </>
            )}
        </SectionCard>

        <SectionCard title="Per channel" subtitle="macro F1 · test block" testid="per-channel-card"
          info="The same two models split by source channel. A channel where both arms fall is a channel whose windows are hard, not a label problem.">
          {!paired ? <Unavailable testid="per-channel-unavailable" reason={notPaired!} />
            : (
              <>
                <div className="m-chbar" data-testid="per-channel">
                  {data.perChannel.map(c => (
                    <ChannelBars key={c.channel} channel={c.channel} windows={c.windows} a={c.a} b={c.b} />
                  ))}
                </div>
                <Legend items={[{ label: `A ${a.short}`, colour: A_COLOUR }, { label: `B ${b.short}`, colour: B_COLOUR }]} />
              </>
            )}
        </SectionCard>
      </div>

      {/* ------------------------------------------------ step through ------------------------------------------------ */}
      <StepThrough paired={paired} reason={notPaired} filter={filter} i={i} onFilter={setFilter} onIndex={n => setI(String(n))}
        a={a} b={b} onReview={id => { push({ text: `${id} opened in Review · queue q-19 (model verification)` }); navigate('review/queue/q-19') }} />
      {notAttributable && (
        <div className="m-lock-note" data-testid="attribution-note">
          <Icon name="alert-triangle" size={15} />
          <div><div className="t">{notAttributable}</div>
            <div className="m-muted">{differs.filter(d => d.av !== d.bv).map(d => `${d.label}: ${d.av} vs ${d.bv}`).join(' · ') || 'pick two different models'}</div></div>
        </div>
      )}
    </>
  )
}

/* ---------------------------------------------------------------- pickers ---------------------------------------------------------------- */
function ModelPicker({ letter, model, models, onPick, other }: { letter: 'A' | 'B'; model: CompareModel; models: CompareModel[]; onPick: (id: string) => void; other: string }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useQueryState(`pick${letter}`, '')
  const isOpen = open === '1'
  return (
    <>
      <button ref={ref} type="button" className={`m-pick ${letter === 'B' ? 'b' : ''}`} data-testid={`pick-${letter.toLowerCase()}`} aria-expanded={isOpen}
        onClick={() => setOpen(isOpen ? null : '1')} style={{ minWidth: 300 }}>
        <ArmBadge letter={letter} />
        <span className="nm">{model.label}</span>
        <span className="m-muted">{model.template} · {model.job}</span>
        <span className="k-spacer" />
        <Icon name="chevron-down" size={13} />
      </button>
      <Popover open={isOpen} onClose={() => setOpen(null)} anchorRef={ref} title={`Model ${letter}`} width={380} testid={`pick-${letter.toLowerCase()}-popover`}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {models.map(m => (
            <button key={m.id} type="button" className="m-usedby" style={{ cursor: 'pointer', border: 0, textAlign: 'left', opacity: m.id === other ? 0.5 : 1 }}
              data-testid={`pick-${letter.toLowerCase()}-${m.id}`} disabled={m.id === other} title={m.id === other ? `already picked as ${letter === 'A' ? 'B' : 'A'}` : m.id}
              onClick={() => { onPick(m.id); setOpen(null) }}>
              <span><span className="t">{m.label}</span><div className="s">{m.template} · {m.job} · {m.group} · F1 {f2(m.macroF1)}</div></span>
              <span className="r">{m.id === model.id ? <Badge status="done" size="sm">picked</Badge> : null}</span>
            </button>
          ))}
        </div>
      </Popover>
    </>
  )
}

function AllModelsPopover({ open, onClose, models, a, b, onPick }: {
  open: boolean; onClose: () => void; models: CompareModel[]; a: CompareModel; b: CompareModel; onPick: (id: string, letter: 'A' | 'B') => void
}) {
  const groups = [...new Set(models.map(m => m.group))]
  if (!open) return null
  return (
    <SectionCard title="Any two models" subtitle="every scored model in this installation, grouped by job" testid="all-models"
      actions={<Button size="sm" icon="x" onClick={onClose}>Close</Button>}>
      {groups.map(g => (
        <div key={g} style={{ marginBottom: 8 }}>
          <div className="m-mono m-small m-muted" style={{ margin: '4px 0' }}>{g}</div>
          {models.filter(m => m.group === g).map(m => (
            <div key={m.id} className="m-usedby" style={{ marginBottom: 4 }} data-testid={`all-models-${m.id}`}>
              <span><span className="t">{m.label}</span><div className="s">{m.template} · {m.windowSet} · {m.labelSource} · F1 {f2(m.macroF1)} · {m.testWindows} test windows</div></span>
              <span className="r" style={{ display: 'flex', gap: 6 }}>
                <Button size="sm" disabled={m.id === b.id} disabledReason="already picked as B" onClick={() => onPick(m.id, 'A')} testid={`as-a-${m.id}`}>as A</Button>
                <Button size="sm" disabled={m.id === a.id} disabledReason="already picked as A" onClick={() => onPick(m.id, 'B')} testid={`as-b-${m.id}`}>as B</Button>
              </span>
            </div>
          ))}
        </div>
      ))}
    </SectionCard>
  )
}

/* ---------------------------------------------------------------- forest ---------------------------------------------------------------- */
interface ForestRow { label: string; value: number; ci: [number, number]; colour: string; format?: (v: number) => string }
function Forest({ rows, domain, band, zero, labelWidth = 104, valueWidth = 40, testid }: {
  rows: ForestRow[]; domain: [number, number]; band?: { lo: number; hi: number; label: string }; zero?: boolean; labelWidth?: number; valueWidth?: number; testid?: string
}) {
  const pct = (v: number) => ((v - domain[0]) / (domain[1] - domain[0])) * 100
  const ticks = zero ? [domain[0], 0, domain[1]] : [0, 0.2, 0.4, 0.6, 0.8, 1].filter(t => t >= domain[0] && t <= domain[1])
  return (
    <div className="m-forest" data-testid={testid} style={{ gridTemplateColumns: `${labelWidth}px minmax(0, 1fr) ${valueWidth}px` }}>
      {band && (
        <div className="trk" style={{ gridColumn: 2, gridRow: `1 / span ${rows.length}`, height: 'auto', alignSelf: 'stretch' }}>
          <div className="band" style={{ left: `${pct(band.lo)}%`, width: `${pct(band.hi) - pct(band.lo)}%` }}><span>{band.label}</span></div>
        </div>
      )}
      {rows.map((r, i) => (
        <span key={`g${r.label}`} style={{ display: 'contents' }}>
          <span className="lbl" style={{ gridColumn: 1, gridRow: i + 1 }}>{r.label}</span>
          <span className="trk" style={{ gridColumn: 2, gridRow: i + 1 }}>
            {zero && <span className="zero" style={{ left: `${pct(0)}%` }} />}
            <span className="ci" style={{ left: `${pct(r.ci[0])}%`, width: `${Math.max(1, pct(r.ci[1]) - pct(r.ci[0]))}%`, background: r.colour }} />
            <span className="dot" style={{ left: `${pct(r.value)}%`, background: r.colour }} title={`${r.label}: ${r.value.toFixed(2)} · CI ${r.ci[0].toFixed(2)}–${r.ci[1].toFixed(2)}`} />
          </span>
          <span className="val" style={{ gridColumn: 3, gridRow: i + 1, color: r.colour === '#9ca3af' ? 'var(--muted)' : 'var(--text)' }}>
            {(r.format ?? f2)(r.value)}
          </span>
        </span>
      ))}
      <span className="axis" style={{ gridColumn: 2, gridRow: rows.length + 1 }}>
        {ticks.map(t => <i key={t} style={{ left: `${pct(t)}%` }}>{zero ? signed(t) : t.toFixed(1)}</i>)}
      </span>
    </div>
  )
}

/* ---------------------------------------------------------------- cluster map ---------------------------------------------------------------- */
function ClusterMapCard({ data, available, bothCluster }: { data: CompareData; available: boolean; bothCluster: boolean }) {
  const [row, setRow] = useQueryState('cluster', '')
  const sel = data.clusterMap.clusters.indexOf(row)
  return (
    <SectionCard title="Cluster → manual class" subtitle="majority on training windows" testid="cluster-map-card"
      info="A cluster has no class name of its own. Each cluster is given the manual class most of its training windows carry; purity is the share that agrees. A cluster split between two classes cannot be scored cleanly.">
      {!available ? <Unavailable testid="cluster-map-unavailable" reason="neither model takes its labels from a cluster stage — there is no mapping to show" />
        : (
          <>
            <Heatmap testid="cluster-heatmap" rows={data.clusterMap.clusters} cols={MODEL_CLASSES.map(c => CLASS_SHORT[c])}
              values={data.clusterMap.values} domain={[0, 100]} ramp="purple" format={v => String(Math.round(v))} cellHeight={26} rowLabelWidth={30}
              legend={false} selectedRows={sel >= 0 ? [sel] : []} onCellClick={r => setRow(data.clusterMap.clusters[r])} />
            <div className="m-map" style={{ marginTop: 8 }} data-testid="cluster-mapping">
              {data.clusterMap.mapping.map(m => (
                <button key={m.c} type="button" className={`row ${row === m.c ? 'on' : ''}`} data-testid={`mapping-${m.c}`}
                  onClick={() => setRow(row === m.c ? null : m.c)} title={`highlight ${m.c} in the heatmap`}>
                  <span className="c">{m.c}</span><Icon name="arrow-right" size={12} />
                  <span className="m-dot" style={{ background: CLASS_COLOUR[m.cls] }} />{m.cls}
                  <span className={m.purity < 50 ? 'm-amber-text' : 'm-muted'}>{m.purity} %</span>
                </button>
              ))}
            </div>
            {data.clusterMap.mapping.filter(m => m.impure).map(m => (
              <div key={m.c} style={{ marginTop: 6 }}><Chip tone="amber" testid="impure-chip">{m.impure}</Chip></div>
            ))}
            {bothCluster && <div className="m-mono m-small m-muted" style={{ marginTop: 6 }}>both models use cluster labels — the mapping shown is B's</div>}
          </>
        )}
    </SectionCard>
  )
}

function ChannelBars({ channel, windows, a, b }: { channel: string; windows: number; a: number; b: number }) {
  return (
    <>
      <span style={{ gridColumn: 1, gridRow: 'span 2' }}>
        <span style={{ fontWeight: 600, display: 'block', fontFamily: 'var(--font-ui)', fontSize: 12 }}>{channel}</span>
        <span className="m-muted m-small">{windows} windows</span>
      </span>
      <span className="track" title={`A ${f2(a)}`}><span className="fill" style={{ width: `${a * 100}%`, background: A_COLOUR }} /></span>
      <span className="m-green-text">{f2(a)}</span>
      <span className="track" title={`B ${f2(b)}`}><span className="fill" style={{ width: `${b * 100}%`, background: B_COLOUR }} /></span>
      <span className="m-purple-text">{f2(b)}</span>
    </>
  )
}

/* ---------------------------------------------------------------- step through ---------------------------------------------------------------- */
function StepThrough({ paired, reason, filter, i, onFilter, onIndex, a, b, onReview }: {
  paired: boolean; reason: string | null; filter: DisagreementFilter; i: number
  onFilter: (f: DisagreementFilter) => void; onIndex: (n: number) => void; a: CompareModel; b: CompareModel; onReview: (id: string) => void
}) {
  const w = useSourced(() => getDisagreement(filter, i), [filter, i])
  const total = FILTER_COUNTS[filter]
  return (
    <SectionCard title="Step through the disagreements" testid="step-card"
      info="One test window at a time: what it looks like, what a human said in Review, and what each arm predicted with its score. This is where a difference in macro F1 becomes a difference you can see."
      actions={
        <>
          <Seg size="sm" testid="filter-seg" ariaLabel="disagreement filter" value={filter} onChange={onFilter}
            options={FILTERS.map(f => ({ value: f.value, label: `${f.label} ${FILTER_COUNTS[f.value]}` }))} />
          <Pager testid="step-pager" page={i} pageCount={total} onPage={onIndex} format="index" />
          <Button icon="external" testid="open-in-review" disabled={!w.data} disabledReason={w.data ? undefined : 'no window loaded'}
            onClick={() => w.data && onReview(w.data.id)}>Open window in Review</Button>
        </>
      }>
      {!paired ? <Unavailable testid="step-unavailable" reason={reason ?? 'not paired'} />
        : w.error ? <LoadFailed what={`disagreement ${i} of ${filter}`} error={w.error} onRetry={w.reload} />
          : !w.data ? <Loading height={220} testid="step-loading" />
            : <DisagreementBody w={w.data} a={a} b={b} />}
    </SectionCard>
  )
}

function DisagreementBody({ w, a, b }: { w: Disagreement; a: CompareModel; b: CompareModel }) {
  const aRight = w.a.cls === w.verdict, bRight = w.b.cls === w.verdict
  return (
    <>
      <div className="m-mono" style={{ fontSize: 12.5, fontWeight: 600 }} data-testid="window-id">
        {w.id} · {w.channel} · {w.hour.toFixed(2)} h · 600 s
      </div>
      <div className="m-mono m-small m-muted" style={{ marginBottom: 6 }}>test block {w.block}</div>
      <div className="m-step-body">
        <Trace testid="window-trace" values={w.values} fs={1} t0={w.hour * 3600} timeUnit="h" height={150} ground="grey" />
        <div className="m-enc" data-testid="encodings">
          <figure><EncodingTile values={w.values} kind="gasf" /><figcaption>GASF</figcaption></figure>
          <figure><EncodingTile values={w.values} kind="rp" /><figcaption>RP</figcaption></figure>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div className="m-pred" data-testid="human-verdict" style={{ background: '#f2faf6' }}>
            <Icon name="user" size={14} />
            <span className="m-muted">human verdict</span>
            <span className="cls">{w.verdict}</span>
            <span className="m-muted m-small">verified in Review</span>
          </div>
          <div className="m-pred" data-testid="pred-a">
            <ArmBadge letter="A" />
            <span className="cls">{w.a.cls}</span>
            <span className="m-muted">score {f2(w.a.score)} · {w.a.score >= w.a.thr ? 'above' : 'below'} {f2(w.a.thr)}</span>
            <span className="k-spacer" />
            <Icon name={aRight ? 'check-circle' : 'x-circle'} size={16} className={aRight ? 'm-green-text' : 'm-red-text'} title={aRight ? `matches the human verdict (${a.short})` : `disagrees with the human verdict (${a.short})`} />
          </div>
          <div className="m-pred" data-testid="pred-b">
            <ArmBadge letter="B" />
            <span className="cls">{w.b.cls}</span>
            <span className="m-muted">{w.b.cluster} · score {f2(w.b.score)}</span>
            <span className="k-spacer" />
            <Icon name={bRight ? 'check-circle' : 'x-circle'} size={16} className={bRight ? 'm-green-text' : 'm-red-text'} title={bRight ? `matches the human verdict (${b.short})` : `disagrees with the human verdict (${b.short})`} />
          </div>
          <div className="m-mono m-small m-muted" data-testid="b-clusters">
            B’s clusters: {w.bClusters.map(([c, s]) => `${c} ${f2(s)}`).join(' · ')}{w.note ? ` · ${w.note}` : ''}
          </div>
          <InfoTip title="Right and wrong">
            An arm is right when its class equals the human verdict on that window. B’s class comes from its cluster through the
            majority mapping above, so an impure cluster can make B wrong even when its own score is high.
          </InfoTip>
        </div>
      </div>
    </>
  )
}

/** GASF / recurrence tile computed from the window itself (04 Image encode draws the real ones from its cache). */
function EncodingTile({ values, kind, n = 34, size = 96 }: { values: number[]; kind: 'gasf' | 'rp'; n?: number; size?: number }) {
  const step = Math.max(1, Math.floor(values.length / n))
  const xs = Array.from({ length: n }, (_, i) => {
    const block = values.slice(i * step, Math.min(values.length, (i + 1) * step))
    return block.length ? block.reduce((a, v) => a + v, 0) / block.length : values[values.length - 1]
  })
  const lo = Math.min(...xs), hi = Math.max(...xs), span = hi - lo || 1
  const norm = xs.map(v => ((v - lo) / span) * 2 - 1)
  const cell = size / n
  const stops: [number, number, number][] = [[11, 42, 107], [42, 95, 209], [127, 176, 245], [232, 240, 255], [255, 217, 74]]
  const colour = (t: number) => { // t in [-1, 1] → the encoder's blue→yellow ramp, interpolated
    const p = Math.min(0.9999, Math.max(0, (t + 1) / 2)) * (stops.length - 1)
    const i = Math.floor(p), f = p - i, c0 = stops[i], c1 = stops[Math.min(stops.length - 1, i + 1)]
    return `rgb(${Math.round(c0[0] + (c1[0] - c0[0]) * f)},${Math.round(c0[1] + (c1[1] - c0[1]) * f)},${Math.round(c0[2] + (c1[2] - c0[2]) * f)})`
  }
  const cells: { x: number; y: number; c: string }[] = []
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const v = kind === 'gasf'
        ? Math.cos(Math.acos(Math.min(1, Math.max(-1, norm[i]))) + Math.acos(Math.min(1, Math.max(-1, norm[j]))))
        : 1 - Math.abs(norm[i] - norm[j])
      cells.push({ x: j * cell, y: i * cell, c: colour(kind === 'gasf' ? v : v * 2 - 1) })
    }
  }
  return (
    <svg width={size} height={size} role="img" aria-label={kind === 'gasf' ? 'Gramian angular summation field of this window' : 'recurrence plot of this window'}>
      <title>{kind === 'gasf' ? 'GASF · cos(φi + φj) of the window' : 'recurrence plot · |xi − xj|'}</title>
      {cells.map((c, k) => <rect key={k} x={c.x} y={c.y} width={cell + 0.4} height={cell + 0.4} fill={c.c} />)}
    </svg>
  )
}

function Unavailable({ reason, testid }: { reason: string; testid: string }) {
  return <EmptyState size="sm" bordered icon="circle-dashed" testid={testid} title="unavailable" caption={reason} />
}
