/* analyse.training.cluster — 03 Cluster (frames training-2, training-2b). `WindowSet → Grouping`.
 * Two views on one route: the grouping in hand (`default`) and the criterion evidence (`?view=choose-k`).
 * B4 lives here as a control, not prose: the criterion is a choice made *before* looking, so it can be
 * locked, and the page says out loud that an unfixed criterion makes k the finding. */
import { useEffect, useRef, useState } from 'react'
import {
  Badge, BandStrip, Bars, Button, Callout, Chip, Dropdown, Icon, InfoTip, KeyValue, LineChart, Legend, Modal,
  MiniTrace, Page, RadioCards, SectionCard, Seg, Slider, StatTile, fmtInt, fmtPct, recordDemoWrite, useNotWired,
  useQueryState, useSim, type BadgeStatus,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getClusterBlock, type ClusterBlock } from '../api/training'
import {
  CLASS_COLOURS, CLASS_Y, CLUSTER, DENDRO_MAX, ESTIMATES, LINKAGE_COLOURS, LINKAGE_R, RUN_STEPS, SPAN_H, SPAN_S,
  WINDOWS, chainStatuses, type ClusterClass, type DendroNode,
} from '../fixtures/training'
import { BlockFrame, LoadFailed, Loading, RunVeil, SaveTemplateModal, SendToReviewModal, UnappliedBar } from './chrome'
import { isPending, live, markSimForced, useSourceQuery, useTrainingDraft, wasSimForced, type ClusterParams } from './draft'

export function ClusterPage() {
  const [source] = useSourceQuery()
  const [view] = useQueryState('view', '')
  const block = useSourced(() => getClusterBlock(source), [source])
  const chooseK = view === 'choose-k'
  return (
    <>
      <Header workspace="Analyse" page={chooseK ? '03 Cluster · choose k' : '03 Cluster'} demo={block.source === 'demo'}
        search="Search spans, runs, families"
        subtitle={chooseK ? 'selection criterion · agreement with manual labels · stability' : 'windows grouped by feature similarity'} />
      <Page testid={chooseK ? 'training-cluster-choose-k' : 'training-cluster'}>
        {block.error ? <LoadFailed what="the grouping" error={block.error} onRetry={block.reload} />
          : !block.data ? <Loading what="the grouping" /> : <Body data={block.data} chooseK={chooseK} />}
      </Page>
    </>
  )
}

/* ------------------------------------------------------------------ dendrogram ------------------------------------------------------------------ */
/* No kit component draws a dendrogram (webui/pages/requests/training.md). It is drawn here from the
 * fixture tree: heights are linkage distances, colour is the class a subtree falls into under the cut. */
function useBoxWidth(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    setW(el.clientWidth)
    const ro = new ResizeObserver(es => { for (const e of es) setW(e.contentRect.width) })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

const leavesOf = (n: DendroNode): DendroNode[] => (n.children ? [...leavesOf(n.children[0]), ...leavesOf(n.children[1])] : [n])

/** A cut at `h`: every maximal subtree whose merge height is at or below the line is one class. */
function cutClusters(n: DendroNode, h: number): DendroNode[] {
  if (!n.children || n.height <= h) return [n]
  return [...cutClusters(n.children[0], h), ...cutClusters(n.children[1], h)]
}

function Dendrogram({ tree, cut, onCut, merged, height = 248 }: {
  tree: DendroNode; cut: number; onCut: (v: number) => void; merged: string[]; height?: number
}) {
  const [ref, w] = useBoxWidth()
  const padL = 40, padR = 96, padT = 12, padB = 22
  const ls = leavesOf(tree)
  const xOf = (id: string) => padL + ((ls.findIndex(l => l.id === id) + 0.5) / ls.length) * Math.max(1, w - padL - padR)
  const yOf = (h: number) => padT + (1 - h / DENDRO_MAX) * (height - padT - padB)
  const colourOf = (n: DendroNode) => (n.klass ? CLASS_COLOURS[merged.includes(n.klass) ? merged[0] : n.klass] : '#9ca3af')

  const lines: React.ReactNode[] = []
  const walk = (n: DendroNode): number => {
    if (!n.children) return xOf(n.id)
    const [a, b] = n.children
    const xa = walk(a), xb = walk(b)
    const y = yOf(n.height), c = colourOf(n)
    lines.push(
      <path key={n.id} d={`M ${xa} ${yOf(a.height)} V ${y} H ${xb} V ${yOf(b.height)}`} fill="none" stroke={c} strokeWidth={1.3} />,
    )
    return (xa + xb) / 2
  }
  if (w > 0) walk(tree)

  const classLabels = Object.keys(CLASS_COLOURS).map(k => {
    const own = ls.filter(l => l.klass === k)
    if (!own.length) return null
    const xs = own.map(l => xOf(l.id))
    return { k, x: (Math.min(...xs) + Math.max(...xs)) / 2 }
  }).filter(Boolean) as { k: string; x: number }[]

  const drag = (e: React.PointerEvent) => {
    const svg = (e.currentTarget as SVGElement).ownerSVGElement
    if (!svg) return
    const move = (ev: PointerEvent) => {
      const box = svg.getBoundingClientRect()
      const y = ev.clientY - box.top
      const h = (1 - (y - padT) / (height - padT - padB)) * DENDRO_MAX
      onCut(Math.max(1, Math.min(DENDRO_MAX - 0.4, +h.toFixed(1))))
    }
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  const k = w > 0 ? cutClusters(tree, cut).length : 0
  return (
    <div className="tr-dendro" ref={ref} data-testid="dendrogram">
      {w > 0 && (
        <svg width={w} height={height} role="img" aria-label={`dendrogram · cut ${cut} gives ${k} classes`}>
          <rect x={padL} y={padT} width={Math.max(0, w - padL - padR)} height={height - padT - padB} fill="#fff" />
          {[0, 4, 8, 12, 16].map(h => (
            <g key={h}>
              <line x1={padL - 4} x2={padL} y1={yOf(h)} y2={yOf(h)} stroke="var(--border)" />
              <text x={padL - 8} y={yOf(h) + 3} textAnchor="end">{h}</text>
            </g>
          ))}
          <text x={padL} y={padT - 1}>linkage distance</text>
          {lines}
          {classLabels.map(c => <text key={c.k} x={c.x} y={height - 6} textAnchor="middle" fill={CLASS_COLOURS[c.k]}>{c.k}</text>)}
          <line x1={padL} x2={w - padR + 18} y1={yOf(cut)} y2={yOf(cut)} stroke="var(--amber)" strokeWidth={1.6} />
          <text x={w - padR + 14} y={yOf(cut) - 6} textAnchor="end" fill="#b86e00">cut {cut.toFixed(1)} → {k} classes</text>
          <rect className="cutline" x={w - padR + 18} y={yOf(cut) - 8} width={16} height={16} rx={4} fill="#fff" stroke="var(--amber)" strokeWidth={1.6}
            onPointerDown={drag} data-testid="cut-handle">
            <title>drag to move the cut</title>
          </rect>
        </svg>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ body ------------------------------------------------------------------ */
function mergeClasses(classes: ClusterClass[], merged: string[]): ClusterClass[] {
  if (merged.length < 2) return classes
  const parts = classes.filter(c => merged.includes(c.id))
  if (parts.length < 2) return classes
  const head = parts[0]
  const joined: ClusterClass = {
    ...head,
    id: merged.join(' + '),
    windows: parts.reduce((s, c) => s + c.windows, 0),
    reviewed: parts.reduce((s, c) => s + c.reviewed, 0),
    interesting: parts.reduce((s, c) => s + c.interesting, 0),
    train: parts.reduce((s, c) => s + c.train, 0),
    val: parts.reduce((s, c) => s + c.val, 0),
    test: parts.reduce((s, c) => s + c.test, 0),
    tooSmall: parts.reduce((s, c) => s + c.windows, 0) < 20,
    members: [parts[1].medoid],
  }
  return [...classes.filter(c => !merged.includes(c.id)), joined]
}

function Body({ data, chooseK }: { data: ClusterBlock; chooseK: boolean }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [source, setSource] = useSourceQuery()
  const [draft, setDraft] = useTrainingDraft()
  const [view, setView] = useQueryState('view', '')
  const [modal, setModal] = useQueryState('modal', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [mergeQ, setMergeQ] = useQueryState('merge', '')
  const [lockQ] = useQueryState('locked', '')
  const [metric, setMetric] = useQueryState('metric', 'silhouette')
  const [shows, setShows] = useState('features')

  const p = live(draft.cluster)
  const pending = isPending(draft.cluster)
  const setP = (patch: Partial<ClusterParams>) =>
    setDraft(d => ({ ...d, cluster: { ...d.cluster, pending: { ...live(d.cluster), ...patch } }, staleFrom: 4 }))

  /* deep links: ?merge=C5,C6 stages the merge · ?locked=1 opens with the criterion already fixed */
  useEffect(() => {
    if (mergeQ && live(draft.cluster).merged.join(',') !== mergeQ) setP({ merged: mergeQ.split(',') })
    if (lockQ === '1' && !draft.criterionLocked) setDraft(d => ({ ...d, criterionLocked: true }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mergeQ, lockQ])

  const sim = useSim('analyse.training.run')
  useEffect(() => {
    if (stateQ === 'running') { sim.force({ status: 'running', steps: RUN_STEPS, step: 2, fraction: 0.55, startedAt: Date.now() }); markSimForced(true) }
    else if (wasSimForced()) { sim.reset(); markSimForced(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const classes = mergeClasses(data.classes, p.merged)
  const k = cutClusters(data.dendrogram, p.cut).length - (p.merged.length > 1 ? p.merged.length - 1 : 0)
  const chain = data.chain
  const status: Record<string, BadgeStatus> = chainStatuses(draft.staleFrom, chain)
  if (sim.status === 'running') status.cluster = 'running'

  const apply = () => {
    setStateQ(null); setMergeQ(null)
    setDraft(d => ({ ...d, cluster: { applied: live(d.cluster), pending: null }, staleFrom: 4 }))
    recordDemoWrite('analyse', 'apply-block', { block: '03 Cluster', cut: p.cut, k, merged: p.merged })
    sim.start({ steps: RUN_STEPS, stepMs: 600 })
  }
  const revert = () => { setStateQ(null); setMergeQ(null); setDraft(d => ({ ...d, cluster: { ...d.cluster, pending: null } })) }

  const primary = sim.busy
    ? <Button variant="danger" icon="stop" onClick={() => sim.cancel()} testid="cancel-run">Cancel</Button>
    : chooseK
      ? <Button variant="primary" icon="check" testid="apply-k" onClick={() => { setView(null); apply() }}>Apply k = {k}</Button>
      : <Button variant="primary" icon="refresh" testid="apply-rerun-top" onClick={apply}
          disabled={!pending && !draft.staleFrom} disabledReason={!pending && !draft.staleFrom ? 'no unapplied changes' : undefined}>Apply &amp; re-run from 03</Button>

  const estimate = pending
    ? (p.merged.length > 1 ? `merge ${p.merged.join(' + ')} → ${k} classes · 04 → 05 stale` : `cut ${p.cut.toFixed(1)} → ${k} classes · 04 → 05 stale`)
    : chooseK ? ESTIMATES.chooseK : ESTIMATES.cluster

  return (
    <BlockFrame
      chain={chain} current="cluster" status={status} source={source} onSource={s => setSource(s === 'signal' ? null : s)}
      name={draft.name} saved={draft.saved} onRename={v => setDraft(d => ({ ...d, name: v, saved: false }))}
      estimate={estimate} estimateTone={pending ? 'purple' : 'muted'}
      backLabel={chooseK ? 'cluster' : 'full chain'}
      onBack={() => (chooseK ? setView(null) : navigate('analyse/training'))}
      onNavigate={b => b.route && navigate(b.route)}
      onAddStage={() => notWired('insert a stage into the training chain (type-contract modal §6.4)')}
      onSaveTemplate={chooseK ? undefined : () => setModal('save-template')}
      primary={primary}
      footer={chooseK ? undefined : (
        <UnappliedBar pending={pending} stage="03"
          why={pending
            ? (p.merged.length > 1 ? `${p.merged.join(' + ')} merged · 04 and 05 re-run on ${k} classes`
              : `cut ${p.cut.toFixed(1)} → ${k} classes · 04 and 05 re-run on the new labels`)
            : CLUSTER.footerNote}
          staleLabel={!pending && draft.staleFrom ? '04' : null}
          revertReason={!pending ? 'already at the recommended values' : undefined}
          onRevert={revert} onApply={apply} busy={sim.busy} onCancel={() => sim.cancel()} />
      )}
    >
      {chooseK
        ? <ChooseK data={data} metric={metric} setMetric={setMetric} locked={draft.criterionLocked} criterion={p.criterion}
            onCriterion={c => setP({ criterion: c })} k={k}
            onLock={() => { setDraft(d => ({ ...d, criterionLocked: true })); recordDemoWrite('analyse', 'lock-criterion', { criterion: p.criterion }); push({ text: `criterion locked · ${p.criterion} · k is now a consequence, not a choice` }) }}
            onSendReview={() => setModal('send-review')} />
        : <>
          <div className="tr-cols wide-right">
            <SectionCard number={3} title="Cluster" subtitle="WindowSet → Grouping" testid="cluster-card"
              actions={<span className="tr-row-flex"><span className="tr-muted tr-small tr-mono">{CLUSTER.truncation}</span>
                <InfoTip title="What the tree shows">Each leaf is a merge of windows, not a window: the last 40 merges of 543 are drawn, so the shape near the cut is readable. Height is linkage distance in the z-scored feature space from 02.</InfoTip></span>}>
              <div className="tr-rel">
                {sim.busy && <RunVeil label={`${RUN_STEPS[sim.step] ?? 'running'} · ${Math.round(sim.fraction * 100)} %`} fraction={sim.fraction} />}
                <Dendrogram tree={data.dendrogram} cut={p.cut} merged={p.merged} onCut={v => setP({ cut: v })} />
              </div>
            </SectionCard>

            <SectionCard title="Parameters" testid="cluster-params"
              actions={<Button variant="link" iconRight="arrow-right" testid="choose-k" onClick={() => setView('choose-k')}>Choose k</Button>}>
              <div className="tr-grid2">
                <Dropdown prefix="criterion" value={p.criterion} onChange={v => setP({ criterion: v })} block testid="criterion"
                  options={data.criteria.map(c => ({ value: c.value, label: c.title, description: c.description }))} />
                <Dropdown prefix="linkage" value={p.linkage} onChange={v => setP({ linkage: v })} block testid="linkage"
                  options={[
                    { value: 'average', label: 'average', description: `cophenetic r ${LINKAGE_R.average}` },
                    { value: 'ward', label: 'ward', description: `cophenetic r ${LINKAGE_R.ward}` },
                    { value: 'complete', label: 'complete', description: `cophenetic r ${LINKAGE_R.complete}` },
                  ]} />
                <Dropdown prefix="distance" value={p.distance} onChange={v => setP({ distance: v })} block testid="distance"
                  options={[
                    { value: 'z-norm Euclidean', label: 'z-norm Euclidean' },
                    { value: 'Euclidean', label: 'Euclidean', description: 'features keep their own scale — the largest feature wins' },
                    { value: 'correlation', label: 'correlation', description: 'shape over level' },
                  ]} />
                <div>
                  <span className="tr-muted tr-small">cut height</span>
                  <Slider value={p.cut} onChange={v => setP({ cut: v })} min={4} max={17} step={0.1} testid="cut-height"
                    format={v => v.toFixed(1)} ariaLabel="cut height" />
                </div>
              </div>
              <div className="tr-grid3" style={{ marginTop: 10 }}>
                <StatTile variant="flat" label="k" value={k} testid="k-tile" />
                <StatTile variant="flat" label="silhouette" value={CLUSTER.silhouette.toFixed(2)} />
                <StatTile variant="flat" label="cophenetic r" value={LINKAGE_R[p.linkage]?.toFixed(2) ?? CLUSTER.cophenetic.toFixed(2)} tone="green" />
              </div>
              <Callout tone={draft.criterionLocked ? 'green' : 'amber'} icon="lock" testid="criterion-warning">
                {draft.criterionLocked ? `criterion locked · ${p.criterion} · k is a consequence of it` : CLUSTER.criterionWarning}
              </Callout>
            </SectionCard>
          </div>

          <SectionCard title="What each class looks like" subtitle="medoid (white) + 2 sampled members" testid="class-cards"
            actions={
              <span className="tr-row-flex">
                <Button size="sm" icon="shuffle" testid="resample-members" onClick={() => notWired('resample 2 members per class from the grouping')}>resample</Button>
                <Dropdown value={shows} onChange={setShows} width={230} testid="show-features" options={[
                  { value: 'features', label: 'show distinguishing features' },
                  { value: 'splits', label: 'show split counts' },
                  { value: 'verdicts', label: 'show human verdicts' },
                ]} />
              </span>
            }>
            <div className="tr-classes" data-testid="class-grid">
              {classes.map(c => (
                <button type="button" key={c.id} className={`tr-class${c.tooSmall ? ' small' : ''}`} data-testid={`class-${c.id.replace(/\s\+\s/g, '-')}`}
                  title={`open ${c.id} in 04 Encode`} onClick={() => navigate('analyse/training/block/4')}>
                  <span className="hd"><span className="tr-dot" style={{ background: c.colour }} />{c.id}<span className="k-spacer" />
                    <span className="tr-muted">{fmtInt(c.windows)} win</span></span>
                  <span className="bd">
                    <MiniTrace values={c.medoid} yDomain={CLASS_Y} width="100%" height={54} stroke="var(--text)"
                      overlays={c.members.map(m => ({ values: m, stroke: c.colour }))} />
                  </span>
                  <span className="ft">{fmtPct(c.reviewed / c.windows)} reviewed · {c.reviewed ? fmtPct(c.interesting / c.reviewed) : '—'} interesting</span>
                  <span className="ft">
                    {shows === 'features' ? <Chip size="sm" tone="grey">{c.feature}</Chip>
                      : shows === 'splits' ? <span className="tr-mono">train {c.train} · val {c.val} · test {c.test}</span>
                        : <span className="tr-mono">{c.reviewed} reviewed · {c.interesting} interesting · {c.windows - c.reviewed} unseen</span>}
                  </span>
                  {c.tooSmall && <span className="ft flag"><Icon name="alert-triangle" size={10} /> too small to train</span>}
                </button>
              ))}
            </div>
          </SectionCard>

          <div className="tr-cols">
            <SectionCard title="Where classes occur in time" testid="occupancy-card"
              info="One band per stretch of the span, coloured by the class its windows fall in. A class that owns one contiguous stretch may be a regime rather than a motif type."
              actions={<Chip tone="amber" size="sm">{CLUSTER.occupancyNote}</Chip>}>
              {/* BandStrip domains are seconds (kit); the axis then prints hours since recording start. */}
              <BandStrip domain={[0, SPAN_S]} timeUnit="h" rowHeight={22} labelWidth={0} segmentGap={0} testid="occupancy-strip"
                rows={[{ label: '', segments: data.occupancy.map(o => ({ start: o.start_h * 3600, end: o.end_h * 3600, colour: CLASS_COLOURS[p.merged.includes(o.klass) ? p.merged[0] : o.klass], label: `${o.klass} · ${o.start_h}–${o.end_h} h` })) }]} />
              <Legend items={Object.keys(CLASS_COLOURS).map(kk => ({ label: kk, colour: CLASS_COLOURS[kk] }))} />
            </SectionCard>

            <SectionCard title="Windows per class" testid="per-class-bars"
              actions={
                <span className="tr-row-flex">
                  <Button size="sm" variant="cluster" icon="branch" testid="merge-classes"
                    disabled={p.merged.length > 1} disabledReason={p.merged.length > 1 ? 'C5 and C6 are already merged in the pending change' : undefined}
                    onClick={() => { setMergeQ('C5,C6'); setP({ merged: ['C5', 'C6'] }) }}>Merge C5 + C6</Button>
                  <Button size="sm" icon="save" testid="save-grouping" onClick={() => setModal('save-grouping')}>Save grouping</Button>
                </span>
              }>
              <Bars categories={classes.map(c => c.id)} height={168} testid="class-bars"
                series={[{ key: 'windows', label: 'windows', colour: 'var(--blue)', values: classes.map(c => c.windows) }]}
                legend={false} onBarClick={cat => push({ text: `${cat} · ${fmtInt(classes.find(c => c.id === cat)?.windows ?? 0)} windows` })} />
              <span className="tr-muted tr-small tr-mono" data-testid="class-bar-note">
                bars are the D8 categorical palette in the cards — never a verdict colour
              </span>
            </SectionCard>
          </div>
        </>}

      <Modal open={modal === 'save-grouping'} onClose={() => setModal(null)} size="md" title="Save grouping"
        subtitle={`${k} classes · ${p.linkage} linkage · cut ${p.cut.toFixed(1)}`} testid="save-grouping-modal"
        footerNote="a grouping is machine-made: it never carries a human verdict"
        footer={<><Button onClick={() => setModal(null)}>Cancel</Button>
          <Button variant="primary" icon="save" testid="save-grouping-confirm" onClick={() => {
            recordDemoWrite('library', 'save-grouping', { id: `grp_${draft.name}_k${k}`, k, scope: 'whole channel', from: 'Analyse › Training 03' })
            setModal(null)
            push({ text: `saved grouping · ${k} classes · in memory (demo)`, action: { label: 'Open in Library', onClick: () => navigate('library/grouping') } })
          }}>Save grouping</Button></>}>
        <SaveGroupingBody k={k} classes={classes} />
      </Modal>

      <SendToReviewModal open={modal === 'send-review'} onClose={() => setModal(null)} from="training 03 cluster"
        onSent={n => setDraft(d => ({ ...d, queuedToReview: d.queuedToReview + n }))} />
      <SaveTemplateModal open={modal === 'save-template'} onClose={() => setModal(null)} defaultName={draft.name}
        stages={chain.filter(b => b.index != null).map(b => b.label)}
        onSaved={n => setDraft(d => ({ ...d, name: n, saved: true }))} />
    </BlockFrame>
  )
}

function SaveGroupingBody({ k, classes }: { k: number; classes: ClusterClass[] }) {
  const [scope, setScope] = useState('channel')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <Seg label="scope" value={scope} onChange={setScope} testid="grouping-scope" options={[
        { value: 'channel', label: 'whole channel' },
        { value: 'section', label: 'this section only' },
      ]} />
      <KeyValue dense items={[
        { k: 'classes', v: `${k} · ${classes.map(c => `${c.id} ${c.windows}`).join(' · ')}` },
        { k: 'covers', v: scope === 'channel' ? `CH4_A2 · 0–${SPAN_H} h · ${fmtInt(WINDOWS.total)} windows` : 'the span on screen only' },
        { k: 'lands in', v: 'Library › Groupings · marked new · this session' },
      ]} />
    </div>
  )
}

/* ------------------------------------------------------------------ choose k (frame 2b) ------------------------------------------------------------------ */
const METRIC_LABEL: Record<string, string> = { silhouette: 'silhouette', gap: 'gap statistic', 'min-class': 'min class size' }

function ChooseK({ data, metric, setMetric, locked, criterion, onCriterion, onLock, onSendReview, k }: {
  data: ClusterBlock; metric: string; setMetric: (v: string) => void; locked: boolean
  criterion: string; onCriterion: (v: string) => void; onLock: () => void; onSendReview: () => void; k: number
}) {
  const sweep = data.kSweep[metric] ?? data.kSweep.silhouette
  const series = Object.keys(sweep).map(lk => ({
    label: lk, colour: LINKAGE_COLOURS[lk] ?? 'var(--muted)',
    points: data.kRange.map((kk, i) => [kk, sweep[lk][i]] as [number, number]), dots: true,
  }))
  const colTone: Record<string, string> = { interesting: '#2f9e5f', not_interesting: '#6b7280', artifact: '#c4402d', no_verdict: '#c9ccd2' }
  const colMax = (key: 'interesting' | 'not_interesting' | 'artifact' | 'no_verdict') => Math.max(1, ...data.contingency.map(r => r[key]))

  return (
    <>
      <div className="tr-cols wide-right">
        <SectionCard title="How many classes?" testid="k-sweep-card"
          info="Each line is one linkage over k. The metric on the left is a property of the geometry, not of the biology — a peak is a reason to look, never a result."
          actions={<Seg value={metric} onChange={setMetric} testid="k-metric" options={Object.keys(METRIC_LABEL).map(m => ({ value: m, label: METRIC_LABEL[m] }))} />}>
          <LineChart series={series} height={210} xLabel="k" testid="k-sweep"
            xDomain={[data.kRange[0], data.kRange[data.kRange.length - 1]]}
            xFormat={v => `k ${v}`} markers={[{ x: k, label: `current k ${k}`, colour: 'var(--blue-300)' }]} legend={false} />
          <span className="tr-muted tr-small tr-mono" data-testid="k-sweep-note">{CLUSTER.sweepNote}</span>
          <Legend items={[
            { label: `average · cophenetic r ${LINKAGE_R.average}`, colour: LINKAGE_COLOURS.average, shape: 'line' },
            { label: `ward · r ${LINKAGE_R.ward}`, colour: LINKAGE_COLOURS.ward, shape: 'line' },
            { label: `complete · r ${LINKAGE_R.complete}`, colour: LINKAGE_COLOURS.complete, shape: 'line' },
            { label: `current k ${k}`, colour: 'var(--blue-300)' },
          ]} />
        </SectionCard>

        <SectionCard title="Selection criterion" testid="criterion-card"
          info="B4: pick the rule before you look at the sweep. If the rule is chosen after seeing k, then k is the finding — and it is a finding about the rule.">
          <RadioCards columns={1} value={criterion} onChange={onCriterion} testid="criterion-cards"
            options={data.criteria.map(c => ({ value: c.value, title: c.title, description: c.description, disabled: locked, reason: locked ? 'the criterion is locked — unlock in Parameters to change it' : undefined }))} />
          <Callout tone={locked ? 'green' : 'amber'} icon="lock" testid="criterion-lock"
            action={locked ? <Badge status="done">locked</Badge> : <Button size="sm" icon="lock" onClick={onLock} testid="lock-criterion">Lock</Button>}>
            {locked ? `locked · ${criterion} · k follows from it` : 'not locked — lock it before reporting'}
          </Callout>
        </SectionCard>
      </div>

      <div className="tr-cols even">
        <SectionCard title="Clusters against human verdicts" testid="contingency-card"
          info="Rows are machine classes, columns are human verdicts. They are separate tables in the database and stay separate here: a verdict never becomes a class, a class never becomes a verdict."
          actions={<Chip tone="amber" size="sm">ARI {CLUSTER.ari} · NMI {CLUSTER.nmi} · on {CLUSTER.reviewedFor} reviewed</Chip>}>
          <table className="tr-table tr-cont" data-testid="contingency-table">
            <thead><tr><th /><th className="num">interesting</th><th className="num">not_interesting</th><th className="num">artifact</th><th className="num">no verdict</th></tr></thead>
            <tbody>
              {data.contingency.map(r => (
                <tr key={r.id}>
                  <td><span className="tr-dot" style={{ background: CLASS_COLOURS[r.id] }} /> <span className="nm">{r.id}</span></td>
                  {(['interesting', 'not_interesting', 'artifact', 'no_verdict'] as const).map(col => (
                    <td key={col} className="num">
                      <span className="cell" style={{
                        background: col === 'no_verdict' ? 'transparent' : colTone[col],
                        opacity: col === 'no_verdict' ? 1 : 0.14 + 0.72 * (r[col] / colMax(col)),
                        color: 'transparent',
                      }} />
                      <span className={`v${col === 'no_verdict' ? ' dim' : ''}`}>{r[col]}</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>

        <SectionCard title="Stability" testid="stability-card" subtitle={CLUSTER.bootstrap}
          info="Each class is re-clustered on 100 bootstrap resamples of the windows; the bar is the mean Jaccard overlap with the class here. A low bar means the class moves when the windows do.">
          <div className="tr-hbars">
            {data.stability.map(s => (
              <div key={s.id} className="tr-hbar" data-testid={`stability-${s.id}`}>
                <span className="lb tr-mono">{s.id}</span>
                <span className="tk"><i style={{ width: `${s.jaccard * 100}%`, background: s.jaccard < 0.5 ? 'var(--amber)' : CLASS_COLOURS[s.id] }} /></span>
                <span className={`vl tr-mono${s.jaccard < 0.5 ? ' warn' : ''}`}>{s.jaccard.toFixed(2)}</span>
              </div>
            ))}
          </div>
          <Callout tone="blue" icon="checklist" testid="unreviewed-callout"
            action={<Button size="sm" variant="primary" icon="arrow-right" onClick={onSendReview} testid="send-review">Send {fmtInt(WINDOWS.unreviewed)} to Review</Button>}>
            <b>{fmtInt(WINDOWS.unreviewed)} windows have no human verdict</b><br />
            <span className="tr-mono tr-small">queue them in Review · binary interesting / not_interesting</span>
          </Callout>
        </SectionCard>
      </div>
    </>
  )
}
