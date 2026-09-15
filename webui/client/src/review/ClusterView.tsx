/* review.cluster — a cluster judged as one batch (frame 2) and the batch undone (frame 7). §10.5: the member strip
 * shows every member (paged at 10, P8) with an include box, shape on one shared mV scale, distance to the medoid and
 * prior verdict; members beyond the cohesion limit are excluded by default; one Ctrl Z reverses the whole batch.
 * Deep links: ?member=c-0373 · ?include=all · ?state=undone|promoted · rails and popovers as the inspector. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { navigate, setQuery } from '../state'
import { Button, Checkbox, Chip, DisabledReason, Icon, InfoTip, Kbd, MiniTrace, Pager, ProgressBar, cx, recordDemoWrite, useDemoState, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { useToast } from '../shell/Toast'
import { VOCABULARY, getCluster, type ClusterDetail, type ItemDetail, type QueueData, type Verdict } from '../api/review'
import { Shell, THUMB_Y, useBlind, useRails, type MicroStat } from './Shell'
import { useReviewKeys } from './keys'
import { goUnit, nextUnjudgedAfter, relTime, step, type UnitRef } from './queue'
import { AnnotateCard, ArtifactPill, ContextCard, EvidenceRail, Pill, PromotionPanel, VerdictCard, editInExplore, useNow, type PreviousLine } from './parts'
import { Loading, NotFound, previousLines } from './common'
import {
  VERDICT_LABEL, amendWrite, applyWrite, effective, getRecords, key, lastLive, mintExemplar, nextRedo, patchRecord, rawRecord, redoWrite, releaseExemplar,
  seedUndoneBatch, undoWrite, useAutoAdvance, useDrafts, usePad, useRecords, useStack, writeLabel, type Draft, type SessionWrite, type VerdictRecord,
} from './store'

const BATCH_CAP = 50
const PAGE = 10
const STAGGER_MS = 60

export function ClusterPage({ data, no }: { data: QueueData; no: number }) {
  if (!data.clusters.some(c => c.no === no)) return <NotFound data={data} what={`cluster ${no}`} />
  return <ClusterInner data={data} no={no} />
}

function ClusterInner({ data, no }: { data: QueueData; no: number }) {
  const { queue } = data
  const q = queue.id
  const cl = data.clusters.find(c => c.no === no)!
  const det = useSourced(() => getCluster(q, no), [q, no])
  const records = useRecords()
  const stack = useStack()
  const toast = useToast()
  const rails = useRails()
  const now = useNow(1000)
  const [blind, setBlind] = useBlind(q, queue.blind)
  const [auto] = useAutoAdvance()
  const [pad, setPad] = usePad()
  const [state] = useQueryState<string>('state', '')
  const [memberQ, setMemberQ] = useQueryState<string>('member', cl.defaultMember)
  const [includeQ, setIncludeQ] = useQueryState<string>('include', '')
  const [drafts, setDrafts] = useDrafts()
  const [batchOn, setBatchOn] = useState(true)
  const [writing, setWriting] = useState<{ total: number; done: number; verdict: Verdict } | null>(null)
  const [page, setPage] = useState(1)
  const confirmRef = useRef<(() => void) | null>(null)
  const timers = useRef<number[]>([])
  useEffect(() => () => { timers.current.forEach(t => window.clearTimeout(t)) }, [])
  const later = (fn: () => void, ms: number) => { timers.current.push(window.setTimeout(fn, ms)) }
  const say = (text: string) => toast.push({ text })

  const rows = cl.members.map(id => data.rows.find(r => r.id === id)!)
  const sorted = [...rows].sort((a, b) => (a.d ?? 0) - (b.d ?? 0))
  const defaultInclude = (id: string) => { const r = data.rows.find(x => x.id === id)!; return (r.d ?? 0) <= cl.cohesionLimit && !effective(getRecords(), r) }
  const [inc, setInc] = useDemoState<Record<string, boolean>>(`review.include.${q}.${no}`, () => Object.fromEntries(cl.members.map(id => [id, defaultInclude(id)])))
  useEffect(() => { if (includeQ === 'all') setInc(Object.fromEntries(cl.members.map(id => [id, true]))) }, [includeQ, cl.members, setInc])
  const included = sorted.filter(r => inc[r.id])
  const excluded = sorted.filter(r => !inc[r.id])
  const flagged = sorted.filter(r => (r.d ?? 0) > cl.cohesionLimit)
  const allIncluded = excluded.length === 0

  const shownId = cl.members.includes(memberQ) ? memberQ : cl.defaultMember
  const d: ClusterDetail | null = det.data && det.data.cluster.no === no && det.data.queue.id === q ? det.data : null
  const shown: ItemDetail | undefined = d?.members.find(m => m.entry.id === shownId)
  const shownRow = rows.find(r => r.id === shownId)!
  const shownRec = effective(records, shownRow)
  const recs = rows.map(r => effective(records, r))
  const judgedCount = recs.filter(Boolean).length
  const binary = queue.verdictKeys === 'binary+classes'
  const masked = blind && judgedCount === 0
  const unit: UnitRef = { kind: 'cluster', no, members: cl.members }
  const dk = key(q, shownId)
  const draft: Draft = drafts[`${q}/cluster/${no}`] ?? { tags: shownRec?.tags ?? shownRow.tags, note: shownRec?.note ?? '' }
  const setDraft = (next: Draft) => { setDrafts(prev => ({ ...prev, [`${q}/cluster/${no}`]: next })); if (shownRec) patchRecord(q, shownId, shownRec, { tags: next.tags, note: next.note }) }

  const clusterWrites = stack.filter(w => w.queueId === q && w.kind === 'batch' && w.clusterNo === no)
  const lastBatch = clusterWrites[clusterWrites.length - 1]
  const undoneBanner = state === 'undone' && lastBatch?.undone ? lastBatch : null
  const promo = state === 'promoted' ? [...clusterWrites].reverse().find(w => !w.undone && w.verdict === 'seed') : undefined
  const promoId = promo ? promo.items.find(id => (promo.after[key(q, id)] as VerdictRecord | null)?.verdict === 'seed') : undefined
  const promoRec = promoId ? effective(records, data.rows.find(r => r.id === promoId)!) : null
  const promoDetail = promoId ? d?.members.find(m => m.entry.id === promoId) : undefined
  const paused = !!undoneBanner || !!promo || !!writing

  const mean = included.length ? included.reduce((a, r) => a + (r.d ?? 0), 0) / included.length : 0
  const worst = Math.max(...rows.map(r => r.d ?? 0))

  // deep link ?state=undone renders frame 7 without a keypress: the batch of 6 × interesting, already undone 2 s ago
  useEffect(() => {
    if (state !== 'undone' || lastBatch?.undone) return
    const members = sorted.filter(r => inc[r.id])
    const after: Record<string, VerdictRecord> = {}
    const before: Record<string, VerdictRecord | null | undefined> = {}
    for (const r of members) { before[key(q, r.id)] = rawRecord(q, r.id); after[key(q, r.id)] = { verdict: 'interesting', blind, at: Date.now() - 4000, tags: draft.tags, note: draft.note } }
    if (members.some(r => effective(getRecords(), r))) return
    seedUndoneBatch({ queueId: q, items: members.map(r => r.id), kind: 'batch', clusterNo: no, verdict: 'interesting', count: members.length, label: `Cluster ${no} · ${members.length} × interesting`, before, after }, 2000)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, no])

  const advanceAfterCluster = () => goUnit(q, nextUnjudgedAfter(data, getRecords(), unit))

  function batchWrite(v: Verdict, className?: string) {
    if (promo) return say('confirm or undo the promotion first (Enter / Ctrl Z)')
    if (writing) return say('the batch is still writing · auto-advance waits for the whole batch')
    if (binary && (v === 'seed' || v === 'artifact' || v === 'unsure') && !className) return say('this queue takes binary verdicts and classes')
    const targets = batchOn ? included : [shownRow]
    if (!targets.length) return say('a batch needs at least one member')
    if (batchOn && targets.length > BATCH_CAP) return say(`batches are capped at ${BATCH_CAP} members — split the cluster or judge members singly`)
    const seedId = v === 'seed' ? (targets.find(r => r.id === cl.nearestMember) ?? targets[0]).id : null
    const before: Record<string, VerdictRecord | null | undefined> = {}
    const after: Record<string, VerdictRecord> = {}
    let exemplar: string | undefined
    for (const r of targets) {
      const k = key(q, r.id)
      before[k] = rawRecord(q, r.id)
      const prev = effective(getRecords(), r)
      const rv: Verdict = v === 'seed' ? (r.id === seedId ? 'seed' : 'interesting') : v
      after[k] = { verdict: rv, className: className ?? prev?.className, blind, at: Date.now(), tags: draft.tags, note: draft.note }
      if (r.id === seedId) { exemplar = mintExemplar(); after[k].exemplarId = exemplar; after[k].family = cl.family.d <= 0.3 ? cl.family.id : null }
    }
    const label = v === 'seed' ? `Cluster ${no} · seed ${exemplar} + ${targets.length - 1} × interesting` : className ? `Cluster ${no} · ${targets.length} × ${className} (class)` : `Cluster ${no} · ${targets.length} × ${VERDICT_LABEL[v]}`
    applyWrite({ queueId: q, items: targets.map(r => r.id), kind: 'batch', clusterNo: no, verdict: v, className, count: targets.length, label, before, after })
    if (undoneBanner) setQuery({ state: null }, true)
    if (v === 'seed') {
      setQuery({ state: 'promoted' }, true)
      return say(targets.length > 1 ? `seed promotes one exemplar (${seedId} → ${exemplar}); ${targets.length - 1} others marked interesting` : `seed · exemplar ${exemplar} created in the Library`)
    }
    // the batch writes member by member; auto-advance waits for the whole batch (§10.5)
    setWriting({ total: targets.length, done: 0, verdict: v })
    targets.forEach((_, i) => later(() => setWriting(w => w ? { ...w, done: i + 1 } : w), STAGGER_MS * (i + 1)))
    later(() => { setWriting(null); if (auto) advanceAfterCluster() }, STAGGER_MS * (targets.length + 1) + 250)
  }

  const klass = (ck: string) => {
    const c = VOCABULARY.classes.find(x => x.key === ck)
    if (!c) return
    batchWrite(c.informative ? 'interesting' : 'artifact', c.name)
    say(`class ${c.name} · implies ${c.informative ? 'interesting' : 'artifact'} for ${batchOn ? `${included.length} members` : shownId}`)
  }

  const undo = () => {
    const w = lastLive(q)
    if (!w) return say('nothing to undo in this queue')
    undoWrite(w)
    if (w.kind === 'batch') {
      if (w.verdict === 'seed') { const ex = Object.values(w.after).find(r => r?.exemplarId)?.exemplarId; if (ex) releaseExemplar(ex); say(`promotion undone · exemplar ${ex} removed with the batch`) }
      if (w.clusterNo === no) setQuery({ state: 'undone' }, true)
      else navigate(`review/queue/${q}/cluster/${w.clusterNo}?state=undone`)
      return
    }
    say(`undone · ${w.label}`)
    if (!cl.members.includes(w.items[0])) navigate(`review/queue/${q}/${w.items[0]}`)
  }
  const redo = () => {
    const w = nextRedo(q)
    if (!w) return say('nothing to redo')
    redoWrite(w)
    say(`redone · ${w.label}`)
    if (w.kind === 'batch' && w.clusterNo === no) setQuery({ state: w.verdict === 'seed' ? 'promoted' : null }, true)
    else navigate(w.kind === 'batch' ? `review/queue/${q}/cluster/${w.clusterNo}` : `review/queue/${q}/${w.items[0]}`)
  }

  const confirmPromotion = (family: string | null, familyName?: string) => {
    if (!promo || !promoId || !promoRec) return
    const k = key(q, promoId)
    amendWrite(promo.id, { [k]: { ...promoRec, family, familyName } }, { item: promoId, family, familyName })
    const r = data.rows.find(x => x.id === promoId)!
    recordDemoWrite('library', 'exemplar', { id: promoRec.exemplarId, family: family === 'new' ? `new: ${familyName}` : family, span: [r.startH, +(r.startH + r.durationS / 3600).toFixed(4)], recording: r.recording, channel: r.channel, recipeHash: promoDetail?.evidence.origin.recipeHash, blind })
    say(`exemplar ${promoRec.exemplarId} confirmed`)
    setQuery({ state: null }, true)
    advanceAfterCluster()
  }

  const moveMember = (dir: 1 | -1) => {
    const i = sorted.findIndex(r => r.id === shownId)
    const j = i + dir
    if (j >= 0 && j < sorted.length) { setMemberQ(sorted[j].id); setPage(Math.floor(j / PAGE) + 1); return }
    const u = step(data, unit, dir)
    if (u) goUnit(q, u); else say(dir > 0 ? 'this is the last unit in the demo fixture' : 'this is the first unit in the queue fixture')
  }

  useReviewKeys({
    verdict: v => batchWrite(v), klass, undo, redo,
    skip: () => goUnit(q, step(data, unit, 1)),
    enter: () => { if (promo && confirmRef.current) { confirmRef.current(); return true } return false },
    next: () => moveMember(1), prev: () => moveMember(-1),
    edit: () => shown && editInExplore(shown),
    rails: rails.toggleBoth,
  })

  const toggleInclude = (id: string, v: boolean) => { setInc(prev => ({ ...prev, [id]: v })); recordDemoWrite('review', 'batch.include', { cluster: no, member: id, included: v }) }
  const channelsTxt = useMemo(() => Object.entries(rows.reduce<Record<string, number>>((a, r) => ({ ...a, [r.channel]: (a[r.channel] ?? 0) + 1 }), {})).sort((a, b) => b[1] - a[1]).map(([c, n]) => `${c} ×${n}`).join(', '), [rows])
  const shownIdx = sorted.findIndex(r => r.id === shownId)
  const pageItems = sorted.slice((page - 1) * PAGE, page * PAGE)
  const pageCount = Math.ceil(sorted.length / PAGE)
  useEffect(() => { setPage(Math.floor(Math.max(0, shownIdx) / PAGE) + 1) }, [no])   // eslint-disable-line react-hooks/exhaustive-deps

  const statusValue = undoneBanner ? `${rows.length} unadjudicated · batch undone`
    : judgedCount === 0 ? `${rows.length} unadjudicated`
      : recs.some(r => !r) ? `${judgedCount} judged · ${rows.length - judgedCount} unadjudicated` : summarise(recs)
  const micro: MicroStat[] = [
    masked ? { value: '', label: 'mean d', icon: 'eye-off', tone: 'purple' } : { value: mean.toFixed(2), label: 'mean d', title: `mean distance of the ${included.length} included members` },
    masked ? { value: '', label: 'worst d', icon: 'eye-off', tone: 'purple' } : { value: worst.toFixed(2), label: 'worst d', tone: worst > cl.cohesionLimit ? 'amber' : undefined },
    masked ? { value: '', label: 'family d', icon: 'eye-off', tone: 'purple', section: 'family' } : { value: cl.family.d.toFixed(2), label: `${cl.family.id} d`, section: 'family' },
    { value: shown?.artifact.level ?? '…', label: 'artifact', tone: shown?.artifact.level === 'low' ? 'green' : 'amber', section: 'artifact' },
    { value: String(rows.length), label: 'members' },
  ]

  const prev: PreviousLine[] = [
    ...(undoneBanner ? [{ prefix: 'undone', text: `${writeLabel(undoneBanner)} · ${relTime(undoneBanner.undoneAt ?? undoneBanner.at, now)}`, go: undefined }] : []),
    ...previousLines(data, stack, now).map(p => p.text === cl.previousLine ? { ...p, text: p.text } : p),
  ]
  const narrow = rails.left || rails.right
  const historyText = stack.filter(w => !w.undone && w.items.includes(shownId)).map(w => `${w.label} · ${relTime(w.at, now)}`).reverse().join('; ') || 'none'

  return (
    <Shell data={data} unit={unit} blind={blind} setBlind={setBlind} paused={paused} micro={micro}
      evidence={shown ? <EvidenceRail d={shown} blind={blind} judged={!!shownRec} historyVerdicts={historyText} /> : <Loading />}
      evidenceTitle={`${shownId}${shownRow.detectionId ? ` · ${shownRow.detectionId}` : ''} · cluster ${no}`}>
      {det.error && <div className="error-card" data-testid="cluster-error"><h3>Cluster {no} failed to load</h3><p className="mono">{det.error.message}</p></div>}
      {!d && !det.error && <Loading />}
      {d && shown && (
        <div className={cx('rv-stack', det.loading && 'stale')} data-testid="cluster-page" data-cluster={no}>
          <div className="rv-title" data-testid="title-row">
            <h1>Cluster {no}</h1>
            <Chip size="sm" tone="purple">cluster</Chip><Chip size="sm" tone="grey">{cl.badge}</Chip>
            <span className="grow" />
            {undoneBanner
              ? <Pill icon="undo" label="status" value={statusValue} tone="blue" shrink testid="pill-status" />
              : <Pill dot={judgedCount ? 'var(--green)' : 'var(--muted-2)'} label="status" value={statusValue} title={`status: ${summarise(recs)}`} shrink testid="pill-status" />}
            {masked ? <Pill icon="eye-off" label="cohesion" value="hidden until verdict" tone="purple" testid="pill-cohesion" />
              : <Pill dot={worst > cl.cohesionLimit ? 'var(--amber)' : 'var(--green)'} label="cohesion" value={`mean d ${mean.toFixed(2)} (${included.length} included) · worst ${worst.toFixed(2)}`} tone={worst > cl.cohesionLimit ? 'amber' : undefined} testid="pill-cohesion" />}
            {masked ? <Pill icon="eye-off" label="family" value="hidden until verdict" tone="purple" testid="pill-family" />
              : <Pill dot={d.members[0].nearest[0].colour} label="family" value={`${cl.family.id} d ${cl.family.d.toFixed(2)}`} testid="pill-family" />}
            <ArtifactPill a={{ level: cl.artifact }} short={narrow} />
          </div>
          <div className="rv-meta mono" data-testid="meta-line">
            {cl.recording} · {channelsTxt} · {cl.kind === 'family set' ? `run ${cl.runId} seed search, exemplar ${cl.exemplar}` : `run ${cl.runId} · sequence within 6 min`} · showing member {shownId}
          </div>

          <ContextCard d={shown} title="Member in context" pad={pad} setPad={setPad} canEdit testid="context-card"
            bandLabel={`${shownId} · ${shownRow.durationS.toFixed(1)} s · member ${shownIdx + 1} of ${rows.length}`} />

          {promo && promoRec && promoDetail && <PromotionPanel d={promoDetail} rec={promoRec} onUndo={undo} onConfirm={confirmPromotion} confirmRef={confirmRef} />}

          <section className="rv-card" data-testid="members-card">
            <div className="rv-card-head">
              <h3>Members</h3>
              <span className="mono muted sm">{rows.length} · {cl.stripCaption} · shared y · mV</span>
              <InfoTip title="Members">Shapes on one shared mV scale, never normalised. A member farther than {cl.cohesionLimit.toFixed(2)} from the medoid is excluded from the batch by default (Settings › Review queues); Include all overrides.</InfoTip>
              <span className="grow" />
              {pageCount > 1 && <Pager page={page} pageCount={pageCount} onPage={setPage} format="range" total={sorted.length} pageSize={PAGE} testid="members-pager" />}
              <span className="mono muted sm">sorted by distance to medoid</span>
              {allIncluded
                ? <Button variant="link" disabled={flagged.length === 0} disabledReason="no member is above the cohesion limit" onClick={() => { setInc(Object.fromEntries(cl.members.map(id => [id, defaultInclude(id)]))); setIncludeQ(null) }} testid="exclude-flagged">Exclude flagged</Button>
                : <Button variant="link" onClick={() => { setInc(Object.fromEntries(cl.members.map(id => [id, true]))); recordDemoWrite('review', 'batch.include', { cluster: no, all: true }) }} testid="include-all">Include all</Button>}
            </div>
            <div className="rv-members" style={{ gridTemplateColumns: `repeat(${Math.min(PAGE, Math.max(pageItems.length, 7))}, minmax(0, 1fr))` }}>
              {pageItems.map((r, i) => {
                const rec = effective(records, r)
                const isShown = r.id === shownId
                const far = (r.d ?? 0) > cl.cohesionLimit
                const on = !!inc[r.id]
                const onlyOne = on && included.length === 1
                const idxInBatch = included.findIndex(x => x.id === r.id)
                const pending = writing && on && idxInBatch >= writing.done
                const m = d.members.find(x => x.entry.id === r.id)!
                return (
                  <div key={r.id} role="button" tabIndex={0} className={cx('rv-member', isShown && 'on', far && 'far', !on && 'off')} data-testid={`member-${r.id}`}
                    onClick={() => setMemberQ(r.id)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); setMemberQ(r.id) } }} aria-label={`show ${r.id}`} aria-pressed={isShown}>
                    <div className="top" onClick={e => e.stopPropagation()}>
                      {onlyOne
                        ? <DisabledReason reason="a batch needs at least one member"><Checkbox checked disabled onChange={() => {}} ariaLabel={`include ${r.id}`} testid={`include-${r.id}`} /></DisabledReason>
                        : <Checkbox checked={on} onChange={v => toggleInclude(r.id, v)} ariaLabel={`include ${r.id}`} testid={`include-${r.id}`} />}
                      <b className="mono">{r.id}</b>
                      {i === 0 && page === 1 && r.id === cl.nearestMember && <span className="mono muted sm" title="nearest to the medoid">nearest</span>}
                    </div>
                    <MiniTrace values={m.shape} yDomain={THUMB_Y} width="100%" height={54} ground={isShown ? 'white' : 'grey'} stroke={far ? 'var(--amber)' : 'var(--text)'} strokeWidth={1.4} zeroLine={false} />
                    <div className="dline mono">{masked ? <span className="muted"><Icon name="eye-off" size={11} /> d hidden</span> : <b className={far ? 'rv-amber' : ''}>d {(r.d ?? 0).toFixed(2)}</b>}{far && !masked && r.d === worst && <span className="rv-amber sm">least similar</span>}</div>
                    <span className={cx('rv-status-chip mono', pending ? 'pending' : rec ? `v-${rec.verdict}` : '')} data-testid={`member-status-${r.id}`}>{pending ? 'writing…' : rec ? (rec.verdict === 'seed' ? `seed · ${rec.exemplarId}` : VERDICT_LABEL[rec.verdict]) : 'unadjudicated'}</span>
                  </div>
                )
              })}
            </div>
          </section>

          <VerdictCard selected={shownRec?.verdict ?? null} flash={null} binary={binary} onVerdict={v => batchWrite(v)} onSkip={() => goUnit(q, step(data, unit, 1))}
            previous={prev} undo={{ can: !!lastLive(q), run: undo }} undoCaption="undo · reverses the whole batch" testid="verdict-card">
            {undoneBanner ? (
              <div className="rv-banner" data-testid="batch-undone-banner">
                <Icon name="undo" size={14} />
                <span>Batch undone · {undoneBanner.count ?? undoneBanner.items.length} verdicts on Cluster {no} reversed in one step · members back to unadjudicated</span>
                <span className="grow" />
                <span className="rv-amber row" style={{ gap: 5 }}><Icon name="pause" size={13} />auto-advance paused</span>
                <span className="k-divider-v" />
                <Button variant="link" icon="refresh" onClick={redo} testid="redo-button">Redo</Button><Kbd size="sm">Ctrl Shift Z</Kbd>
              </div>
            ) : writing ? (
              <div className="rv-batch" data-testid="batch-writing">
                <span className="mono">writing {VERDICT_LABEL[writing.verdict]} · {writing.done} / {writing.total}</span>
                <ProgressBar value={writing.done / writing.total} size="sm" labelPosition="none" width={200} ariaLabel="batch write" />
                <span className="grow" /><span className="mono muted sm">auto-advance waits for the whole batch</span>
              </div>
            ) : (
              <div className="rv-batch" data-testid="batch-line">
                {included.length > BATCH_CAP
                  ? <DisabledReason reason={`batches are capped at ${BATCH_CAP} members — split the cluster or judge members singly`}><Checkbox checked={false} disabled onChange={() => {}} label={`Verdict for the ${included.length} included members`} /></DisabledReason>
                  : <Checkbox checked={batchOn} onChange={setBatchOn} label={batchOn ? `Verdict for the ${included.length} included members${pageCount > 1 ? ` (${pageCount} pages)` : ''}` : `Verdict for ${shownId} only · batch off`} testid="batch-checkbox" />}
                {batchOn && excluded.length > 0 && <span className="mono sm rv-amber" data-testid="excluded-note">{excluded.length} excluded · {excluded.map(r => `${r.id} d ${(r.d ?? 0).toFixed(2)}`).join(', ')}{excluded.every(r => (r.d ?? 0) > cl.cohesionLimit) ? `, above the ${cl.cohesionLimit.toFixed(2)} limit` : ''}</span>}
                <span className="grow" /><span className="mono muted sm">auto-advance waits for the whole batch</span>
              </div>
            )}
          </VerdictCard>
          <AnnotateCard draft={draft} setDraft={setDraft} className={shownRec?.className} onClass={klass} />
          <span hidden data-testid="cluster-shown-key">{dk}</span>
        </div>
      )}
    </Shell>
  )
}

function summarise(recs: (VerdictRecord | null)[]) {
  const n: Record<string, number> = {}
  for (const r of recs) { const k = r ? (r.verdict === 'seed' ? 'seed' : VERDICT_LABEL[r.verdict]) : 'unadjudicated'; n[k] = (n[k] ?? 0) + 1 }
  return Object.entries(n).map(([k, v]) => `${v} ${k}`).join(' · ')
}

export type { SessionWrite }
