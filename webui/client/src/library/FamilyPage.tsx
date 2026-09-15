/* library.family — frame library-3 (F-03 sharkfin, member m-1850 in the rail, 3 selected).
 * Hand edits (add / remove / make exemplar / tags / class / note) live in the in-memory store and survive regrouping. */
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import {
  Badge, Button, Checkbox, Chip, EmptyState, Icon, InfoTip, KeyValue, MiniTrace, Modal, Page, Pager, Popover, Seg, SelectField, TextField,
  fmtInt, recordDemoWrite, useDemoState, useQueryState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, useApp } from '../state'
import { useSourced } from '../api/seam'
import { CLASS_OPTIONS, TAG_RULE, TAG_VOCABULARY, getFamily, motifShape, niceMvDomain, type FamilyDetail, type Member, type MotifFamily, type SequenceFamily, type Verdict } from '../api/library'
import { GroupingBar, LoadFailed, Loading, MotifPlot, SectionBar, useAllGroupings, useEmptyLibrary, useMotifGroupingId, useQueueToast, useRememberMotifsRoute } from './chrome'
import { EmptyMotifsPage } from './EmptyLibrary'
import { hexA } from './AtlasPage'

type RemovedEntry = Member & { removedAt: string; removedNote: string }
interface FamilyEdits { removed: RemovedEntry[]; undone: string[]; exemplar: string; tags: Record<string, string[]>; cls: Record<string, string>; notes: Record<string, string>; queued: boolean; staleEdges: boolean; log: string[] }
type SortKey = 'distance' | 'time' | 'amplitude' | 'unjudged'
const VERDICT_COLOUR: Record<Verdict, string> = { seed: 'var(--green)', interesting: 'var(--green)', 'not interesting': 'var(--muted-2)', artifact: 'var(--red)', unjudged: 'var(--amber)' }
const TODAY = '16 Sep'

export function FamilyPage({ familyId }: { familyId?: string } = {}) {
  useRememberMotifsRoute()
  const { route } = useApp()
  const id = familyId ?? route.parts[1] ?? 'F-03'
  const [empty] = useEmptyLibrary()
  const fam = useSourced(() => getFamily(id), [id])
  const groupings = useAllGroupings()
  const [gid] = useMotifGroupingId()
  if (empty) return <EmptyMotifsPage />
  const grouping = groupings.all.find(g => g.id === gid) ?? null
  const d = fam.data
  const title = d?.kind === 'motif' ? `${d.detail.family.id} ${d.detail.family.name}` : d?.kind === 'sequence' ? `${d.family.id} ${d.family.name}` : id
  return (
    <>
      <Header workspace="Library" page="Motifs" subtitle={`${title} · grouping ${d?.kind === 'sequence' ? 'g-08' : gid}`} search="Search spans, runs, families" demo={fam.source === 'demo'} />
      <Page testid="family-page">
        <SectionBar section="motifs" crumbs={[{ label: 'Recurrence', onClick: () => navigate('library/recurrence') }, { label: 'Atlas', onClick: () => navigate(`library/atlas${d?.kind === 'sequence' ? '?unit=sequences' : ''}`) }, { label: title }]}
          actions={<ExportEntryBtn id={id} />} />
        <GroupingBar unit={d?.kind === 'sequence' ? 'sequences' : 'motifs'} grouping={d?.kind === 'sequence' ? groupings.all.find(g => g.id === 'g-08') ?? null : grouping} from={`family/${id}`} />
        {fam.error && <LoadFailed what={`family ${id}`} error={fam.error} onRetry={fam.reload} />}
        {fam.loading && <Loading height={640} testid="family-loading" />}
        {d?.kind === 'missing' && <EmptyState icon="alert-triangle" title={`No family ${id} in grouping ${gid}`} caption="the id is not in any saved grouping" action={<Button onClick={() => navigate('library/atlas')}>‹ back to atlas</Button>} bordered testid="family-missing" />}
        {d?.kind === 'sequence' && <SequenceFamilyPlaceholder f={d.family} />}
        {d?.kind === 'motif' && (gid !== 'g-07' && d.detail.family.id.startsWith('F-')
          ? <EmptyState icon="grid" title={`${d.detail.family.id} belongs to grouping g-07`} caption={`the current grouping is ${gid}; hand edits to ${d.detail.family.id} are kept either way`} action={<SwitchToG07 />} bordered testid="family-other-grouping" />
          : <MotifFamilyView detail={d.detail} />)}
      </Page>
    </>
  )
}
function SwitchToG07() { const [, set] = useMotifGroupingId(); return <Button onClick={() => set('g-07')}>Switch to g-07</Button> }
function ExportEntryBtn({ id }: { id: string }) {
  const { push } = useToast()
  return <Button icon="upload" testid="export-entry" onClick={() => push({ text: `not wired yet: export library entry ${id} (exemplar, medoid, members CSV, provenance)` })}>Export entry</Button>
}

function SequenceFamilyPlaceholder({ f }: { f: SequenceFamily }) {
  return (
    <div className="k-card" style={{ padding: 20 }} data-testid="sequence-family-placeholder">
      <EmptyState icon="layers" title={`${f.id} ${f.name} · ${f.sequences} sequences · ${f.motifs} motifs`} caption="the sequence family page is not drawn yet — its sequences are listed below; open the atlas for the composition and aligned members"
        action={<Button onClick={() => navigate(`library/atlas?unit=sequences&family=${f.id}`)}>‹ back to atlas</Button>} />
      <div className="row wrap" style={{ gap: 6, marginTop: 12 }}>{Array.from({ length: f.sequences }, (_, i) => <Chip key={i} tone="grey" size="sm">{`sq-${f.id.slice(2)}${String(i + 1).padStart(2, '0')}`}</Chip>)}</div>
    </div>
  )
}

/* ================================================================ motif family ================================================================ */
function memberTrace(m: Member, shape: MotifFamily['shape'], sign: number) { return motifShape(shape, sign * m.amplitudeMv, m.seed, { jitter: 0.07 }) }

function MotifFamilyView({ detail }: { detail: FamilyDetail }) {
  const f = detail.family
  const { push } = useToast()
  const queue = useQueueToast()
  const [edits, setEdits] = useDemoState<FamilyEdits>(`library.family.${f.id}.edits`, () => ({
    removed: detail.removed.map(r => ({ id: r.id, d: r.d, channel: r.channel, recording: r.recording, onsetH: 204.1, durationS: 20.4, amplitudeMv: 0.18, verdict: 'unjudged' as Verdict, foundBy: 'run #128 drop_motifs9', revisions: [{ rev: 1, spanId: 'd-88511', origin: 'machine' as const, run: '#128', role: 'current' }], tags: [], seed: r.seed, removedAt: r.removedAt, removedNote: r.note })),
    undone: [], exemplar: f.exemplar, tags: Object.fromEntries(detail.members.map(m => [m.id, m.tags])), cls: Object.fromEntries(detail.members.filter(m => m.cls).map(m => [m.id, m.cls!])),
    notes: Object.fromEntries(detail.members.filter(m => m.note).map(m => [m.id, m.note!])), queued: false, staleEdges: false, log: [],
  }))
  const [sel, setSel] = useDemoState<string[]>(`library.family.${f.id}.sel`, () => (f.id === 'F-03' ? ['E-0102', 'm-1843', 'm-1850'] : []))
  const { route } = useApp()
  const selQ = route.query.sel
  useEffect(() => { if (selQ !== undefined) setSel(selQ ? selQ.split(',') : []) }, [selQ, setSel])
  const [sort, setSort] = useQueryState<SortKey>('sort', 'distance')
  const [handQ, setHandQ] = useQueryState('hand', '')
  const [pageQ, setPageQ] = useQueryState('page', '1')
  const [memberQ, setMemberQ] = useQueryState('member', f.id === 'F-03' ? 'm-1850' : '')
  const [modal, setModal] = useQueryState('modal', '')
  const [popover, setPopover] = useQueryState('popover', '')
  const [sampleSeed, setSampleSeed] = useState(1)
  const sign = f.depthMv < 0 ? -1 : 1

  const removedIds = new Set(edits.removed.map(r => r.id))
  const members = useMemo(() => detail.members.filter(m => !removedIds.has(m.id) && !edits.undone.includes(m.id)), [detail.members, edits.removed, edits.undone]) // eslint-disable-line react-hooks/exhaustive-deps
  const withEdits = (m: Member): Member => ({ ...m, role: m.id === edits.exemplar ? 'exemplar' : m.role === 'exemplar' ? undefined : m.role, tags: edits.tags[m.id] ?? m.tags, cls: edits.cls[m.id], note: edits.notes[m.id] })
  const handOnly = handQ === '1'
  const ordered = useMemo(() => {
    const list = members.map(withEdits).filter(m => !handOnly || m.addedByHand)
    if (sort === 'time') return [...list].sort((a, b) => a.onsetH - b.onsetH)
    if (sort === 'amplitude') return [...list].sort((a, b) => b.amplitudeMv - a.amplitudeMv)
    if (sort === 'unjudged') return [...list].sort((a, b) => Number(a.verdict !== 'unjudged') - Number(b.verdict !== 'unjudged') || a.d - b.d)
    // distance: members kept past the cut by hand stay on the first page (see InfoTip)
    const pinned = list.filter(m => m.addedByHand && m.d > detail.cut)
    const rest = list.filter(m => !pinned.includes(m)).sort((a, b) => a.d - b.d)
    const k = Math.max(0, Math.min(rest.length, 10 - pinned.length))
    return [...rest.slice(0, k), ...pinned, ...rest.slice(k)]
  }, [members, sort, handOnly, edits]) // eslint-disable-line react-hooks/exhaustive-deps
  const pageCount = Math.max(1, Math.ceil(ordered.length / 10))
  const page = Math.min(pageCount, Math.max(1, Number(pageQ) || 1))
  const pageItems = ordered.slice((page - 1) * 10, page * 10)
  const railMember = ordered.find(m => m.id === memberQ) ?? members.map(withEdits).find(m => m.id === memberQ) ?? pageItems[0] ?? null
  const yDomain = useMemo(() => { const a = Math.max(...detail.members.map(m => m.amplitudeMv), Math.abs(f.depthMv)); return niceMvDomain([[a * 1.05, -a * 1.05]]) }, [detail.members, f.depthMv])
  const judged = members.filter(m => m.verdict !== 'unjudged').length
  const unjudged = members.length - judged
  const added = members.filter(m => m.addedByHand).length
  const exemplarMember = members.find(m => m.id === edits.exemplar)
  const exemplarTrace = edits.exemplar === f.exemplar || !exemplarMember ? f.exemplarTrace : memberTrace(exemplarMember, f.shape, sign)
  const sampled = useMemo(() => Array.from({ length: Math.min(10, members.length) }, (_, k) => members[(k * 11 + sampleSeed * 7) % members.length]).map(m => memberTrace(m, f.shape, sign)), [members, sampleSeed, f.shape, sign])
  const selInList = sel.filter(s => members.some(m => m.id === s))
  const pageIds = pageItems.map(m => m.id)
  const pageTicked = pageIds.filter(x => sel.includes(x)).length

  const log = (kind: string, detailRec: Record<string, unknown>) => recordDemoWrite('library', kind, { family: f.id, ...detailRec })
  const setMember = (mid: string) => setMemberQ(mid)
  const toggle = (mid: string) => setSel(s => (s.includes(mid) ? s.filter(x => x !== mid) : [...s, mid]))
  const removeMembers = (ids: string[]) => {
    const targets = members.filter(m => ids.includes(m.id))
    setEdits(e => ({ ...e, removed: [...e.removed, ...targets.map(m => ({ ...withEdits(m), removedAt: TODAY, removedNote: 'removed by hand' }))] }))
    setSel(s => s.filter(x => !ids.includes(x)))
    log('hand-edit.remove', { members: ids })
    if (railMember && ids.includes(railMember.id)) { const next = ordered.find(m => !ids.includes(m.id)); if (next) setMemberQ(next.id) }
    push({ text: `Removed ${ids.length} from ${f.id} · kept out on every regroup · not wired yet: POST hand edit`, action: { label: 'Undo', onClick: () => restore(ids) } })
  }
  const restore = (ids: string[]) => {
    setEdits(e => ({ ...e, removed: e.removed.filter(r => !ids.includes(r.id)) }))
    log('hand-edit.restore', { members: ids })
  }
  const undoAdd = (mid: string) => {
    setEdits(e => ({ ...e, undone: [...e.undone, mid] }))
    log('hand-edit.undo-add', { member: mid })
    const next = ordered.find(m => m.id !== mid); if (next) setMemberQ(next.id)
    push({ text: `Undone: ${mid} leaves ${f.id} · not wired yet: DELETE hand edit`, action: { label: 'Redo', onClick: () => { setEdits(e => ({ ...e, undone: e.undone.filter(x => x !== mid) })); setMemberQ(mid) } } })
  }
  const onKey = (e: KeyboardEvent) => {
    if (!railMember) return
    const i = ordered.findIndex(m => m.id === railMember.id)
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault()
      const j = Math.max(0, Math.min(ordered.length - 1, i + (e.key === 'ArrowRight' ? 1 : -1)))
      setMemberQ(ordered[j].id); const pg = Math.floor(j / 10) + 1; if (pg !== page) setPageQ(String(pg))
    } else if (e.key === ' ') { e.preventDefault(); toggle(railMember.id) }
    else if (e.key === 'Escape' && sel.length) { e.preventDefault(); setSel([]) }
  }
  const batchTagRef = useRef<HTMLButtonElement>(null), batchClassRef = useRef<HTMLButtonElement>(null)

  return (
    <div className="lib-split" data-testid="family-view">
      <div className="stack" style={{ gap: 10, minWidth: 0 }}>
        {unjudged > 0 ? (
          <div className="lib-ubanner" data-testid="unjudged-banner">
            <span className="dot" />
            <b style={{ fontSize: 13 }}>{unjudged} of {members.length} members have never been judged</b>
            <span className="lib-cap" style={{ color: '#b56b00', fontSize: 11 }}>a family of unjudged members is a proposal, not a finding</span>
            <span style={{ marginLeft: 'auto' }} />
            {edits.queued && <Chip tone="amber" size="sm" icon="check">queued as Library · {f.id} unjudged</Chip>}
            <Button className="lib-amber-btn" icon="checklist" iconRight="arrow-right" testid="send-unjudged-queue" onClick={() => { queue(`Library · ${f.id} unjudged`, unjudged); setEdits(e => ({ ...e, queued: true })) }}>Send {unjudged} to Review as a queue</Button>
          </div>
        ) : <div className="lib-cap" data-testid="all-judged" style={{ padding: '4px 2px' }}><Icon name="check-circle" size={12} style={{ color: 'var(--green)', verticalAlign: -2 }} /> every member of {f.id} is judged</div>}

        <div className="k-card" style={{ padding: 12, display: 'grid', gridTemplateColumns: '300px minmax(0, 1fr) 222px', gap: 14, alignItems: 'start' }} data-testid="family-summary">
          <div>
            <MotifPlot exemplar={exemplarTrace} medoid={f.medoidTrace} colour={f.colour} yDomain={yDomain} height={108} testid="summary-exemplar-medoid" />
            <div className="row lib-cap" style={{ justifyContent: 'space-between', paddingLeft: 30 }}><span>0</span><span>{f.durationS} s</span></div>
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <div className="row lib-cap" style={{ fontSize: 10.5 }}>
              <span><i style={{ display: 'inline-block', width: 12, height: 2, background: '#1f2937', verticalAlign: 'middle', marginRight: 4 }} />exemplar {edits.exemplar}{edits.exemplar === f.exemplar ? ' (seed)' : ' (hand)'}</span>
              <span><i style={{ display: 'inline-block', width: 12, height: 2, background: f.colour, verticalAlign: 'middle', marginRight: 4 }} />medoid {f.medoid}</span>
              <span className="k-chip green sm">d {f.exemplarMedoidD.toFixed(2)}</span>
              {edits.staleEdges && <Badge status="stale" title="the exemplar changed; distances are partially stale until the family is recomputed (§4.2)">edges partially stale</Badge>}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
              <KeyValue align="right" dense items={[
                { k: 'members', v: fmtInt(members.length), strong: true },
                { k: 'recordings', v: `${f.recordings} · ${detail.channels} channels` },
                { k: 'judged', v: `${judged} of ${members.length}`, tone: 'amber' },
                { k: 'hand edits', v: <button type="button" className="lib-plain mono" style={{ color: 'var(--purple)', fontSize: 11 }} data-testid="hand-edits-link" onClick={() => { setHandQ(handOnly ? null : '1'); setPageQ(null) }}>{added} added · {edits.removed.length} removed</button> },
              ]} testid="summary-kv-1" />
              <KeyValue align="right" dense items={[
                { k: 'mean member d', v: f.meanMemberD.toFixed(2) },
                { k: 'duration', v: `${f.durationS} s ± ${f.durationSd}` },
                { k: 'depth', v: detail.depthLabel },
                { k: 'cross-channel', v: `artifact ${f.artifactChannels}` },
              ]} testid="summary-kv-2" />
            </div>
          </div>
          <div>
            <div className="row lib-cap" style={{ fontSize: 10.5 }}><span>{sampled.length} of {members.length} sampled</span><Button variant="link" size="sm" style={{ marginLeft: 'auto' }} testid="summary-resample" onClick={() => setSampleSeed(s => s + 1)}>resample</Button></div>
            <MiniTrace values={f.medoidTrace} yDomain={yDomain} width="100%" height={104} strokeWidth={1.8} overlays={sampled.map(v => ({ values: v, stroke: hexA(f.colour, 0.45), width: 1 }))} testid="summary-overlay" title="10 sampled members over the medoid, shared mV scale" />
          </div>
        </div>

        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }} data-testid="family-sort-row">
          <span className="lib-muted-label">sort</span>
          <Seg size="sm" ariaLabel="sort members" testid="member-sort" value={sort} onChange={v => { setSort(v); setPageQ(null) }}
            options={[{ value: 'distance', label: 'distance to medoid' }, { value: 'time', label: 'time' }, { value: 'amplitude', label: 'amplitude' }, { value: 'unjudged', label: 'unjudged first' }]} />
          {sort === 'distance' && <InfoTip title="members past the cut">members kept in {f.id} by hand past the cut ({detail.cut}) are listed at the end of the first page so they get checked; the rest sort by distance to the medoid</InfoTip>}
          <Button size="sm" icon="user" testid="hand-only" aria-pressed={handOnly} variant={handOnly ? 'subtle' : 'default'} className={handOnly ? 'lib-toggle-on' : undefined} onClick={() => { setHandQ(handOnly ? null : '1'); setPageQ(null) }}>hand edits only</Button>
          <span style={{ marginLeft: 'auto' }} />
          <Checkbox label="select page" testid="select-page" checked={pageIds.length > 0 && pageTicked === pageIds.length} indeterminate={pageTicked > 0 && pageTicked < pageIds.length}
            onChange={v => setSel(s => (v ? [...new Set([...s, ...pageIds])] : s.filter(x => !pageIds.includes(x))))} disabled={!pageIds.length} disabledReason="no members on this page" />
          <Pager format="range" page={page} pageCount={pageCount} total={ordered.length} pageSize={10} onPage={p => setPageQ(p === 1 ? null : String(p))} label="page" testid="member-pager" />
        </div>

        <div className="lib-member-grid" data-testid="member-grid" tabIndex={0} onKeyDown={onKey} aria-label="members, ← → move the rail, Space ticks">
          {pageItems.map(m => {
            const on = railMember?.id === m.id
            return (
              <div key={m.id} className={`k-card lib-mcard${on ? ' on' : ''}`} data-testid={`member-card-${m.id}`} onClick={() => setMember(m.id)} role="button" tabIndex={-1} aria-pressed={on}>
                <div className="lib-mcard-head">
                  <span onClick={e => e.stopPropagation()}><Checkbox checked={sel.includes(m.id)} onChange={() => toggle(m.id)} ariaLabel={`select ${m.id}`} testid={`member-check-${m.id}`} /></span>
                  <b>{m.id}</b><span className={`d${m.d > detail.cut ? ' past' : ''}`} title={m.d > detail.cut ? `past the cut ${detail.cut}` : 'distance to medoid'}>d {m.d.toFixed(2)}</span>
                </div>
                <div style={{ minHeight: 18 }}>
                  {m.role === 'medoid' && <span className="k-badge t-purple">medoid</span>}
                  {m.role === 'exemplar' && <span className="k-badge t-green">exemplar</span>}
                  {m.addedByHand && <span className="k-badge t-purple">added by hand</span>}
                </div>
                <MiniTrace values={memberTrace(m, f.shape, sign)} yDomain={yDomain} width="100%" height={48} ground={on ? 'white' : 'grey'} stroke={m.verdict === 'artifact' ? 'var(--red)' : '#1f2937'} strokeWidth={1.3} title={`${m.id} · ${m.recording} ${m.channel} · ${m.onsetH.toFixed(1)} h`} />
                <span className="lib-cap">{m.channel} · {m.onsetH.toFixed(1)} h</span>
                <VerdictLine v={m.verdict} />
              </div>
            )
          })}
        </div>
        {!pageItems.length && <EmptyState title={handOnly ? 'No hand-edited members' : 'No members'} caption={handOnly ? 'nobody has added a member to this family by hand' : 'every member was removed'} bordered testid="members-empty" />}
        <span className="lib-cap" style={{ marginTop: -4 }}>shared mV scale · ±{yDomain[1].toFixed(1)} mV · {f.durationS} s</span>

        {edits.removed.length > 0 && (
          <div className="k-card" style={{ padding: '10px 14px', display: 'grid', gridTemplateColumns: '240px 1fr', gap: 12, alignItems: 'center' }} data-testid="removed-strip">
            <div><div className="row"><Icon name="user" size={14} /><b style={{ fontSize: 13 }}>Removed by hand · {edits.removed.length}</b></div><div className="lib-cap" style={{ marginLeft: 22 }}>kept out when {f.id} is regrouped</div></div>
            <div className="stack" style={{ gap: 4 }}>
              {edits.removed.slice(0, 3).map(r => (
                <div key={r.id} className="row" style={{ gap: 12 }}>
                  <MiniTrace values={memberTrace(r, f.shape, sign)} yDomain={yDomain} width={62} height={34} ground="white" stroke="#6b7280" style={{ border: '1px solid var(--border)', borderRadius: 4 }} />
                  <span className="lib-cap" style={{ color: 'var(--text-2)', fontSize: 11 }}>{r.id} · d {r.d.toFixed(2)} · {r.channel} · removed {r.removedAt} · “{r.removedNote}”</span>
                  <Button variant="link" icon="undo" style={{ marginLeft: 'auto' }} testid={`restore-${r.id}`} onClick={() => { restore([r.id]); push({ text: `Restored ${r.id} · not wired yet: DELETE hand edit` }) }}>Restore</Button>
                </div>
              ))}
              {edits.removed.length > 3 && <span className="lib-cap">+ {edits.removed.length - 3} more removed by hand</span>}
            </div>
          </div>
        )}

        <div className="k-card lib-batch" data-testid="batch-bar">
          {selInList.length ? <>
            <b style={{ fontSize: 13 }} data-testid="batch-count">{selInList.length} selected</b>
            <InfoTip title="keyboard">← → move the rail member · Space ticks it · Esc clears the selection</InfoTip>
            <span style={{ marginLeft: 'auto' }} />
            <span className="row lib-ui-btn" style={{ gap: 8 }}>
              <Button icon="checklist" testid="batch-send" onClick={() => queue(`Library · ${f.id} selection`, selInList.length)}>Send to Review</Button>
              <Button ref={batchTagRef} icon="tag" testid="batch-tag" onClick={() => setPopover(popover === 'tag' ? null : 'tag')}>Add tag</Button>
              <Button ref={batchClassRef} icon="layers" testid="batch-class" onClick={() => setPopover(popover === 'class' ? null : 'class')}>Assign class</Button>
              <Button icon="minus" testid="batch-remove" onClick={() => setModal('remove')}>Remove from family</Button>
              <Button icon="upload" testid="batch-export" onClick={() => push({ text: `not wired yet: export ${selInList.length} members (CSV + spans)` })}>Export</Button>
            </span>
          </> : <span className="lib-cap" data-testid="batch-hint">tick members to act on several · send to Review, tag, assign class, remove, export</span>}
        </div>
      </div>

      {railMember ? <MemberRail key={railMember.id} m={railMember} f={f} detail={detail} yDomain={yDomain} sign={sign} edits={edits} setEdits={setEdits}
        onUndoAdd={undoAdd} onRemove={() => setModal('remove-member')} onMakeExemplar={() => setModal('make-exemplar')} popover={popover} setPopover={setPopover} />
        : <aside className="k-card lib-rail"><EmptyState title="No member open" caption="click a member card" size="sm" /></aside>}

      <Popover open={popover === 'tag' && selInList.length > 0} onClose={() => setPopover(null)} anchorRef={batchTagRef} title={`Tag ${selInList.length} members`} width={300} testid="batch-tag-popover" placement="top-start">
        <TagInput onApply={t => { setEdits(e => ({ ...e, tags: Object.fromEntries(Object.entries({ ...Object.fromEntries(members.map(m => [m.id, e.tags[m.id] ?? m.tags])) }).map(([k, v]) => [k, selInList.includes(k) && !v.includes(t) ? [...v, t] : v])) })); log('hand-edit.tag', { members: selInList, tag: t }); setPopover(null); push({ text: `Tagged ${selInList.length} members “${t}” · hand edit` }) }} onCancel={() => setPopover(null)} />
      </Popover>
      <Popover open={popover === 'class' && selInList.length > 0} onClose={() => setPopover(null)} anchorRef={batchClassRef} title={`Assign class to ${selInList.length}`} width={260} testid="batch-class-popover" placement="top-start">
        <ClassPicker onApply={c => { setEdits(e => ({ ...e, cls: { ...e.cls, ...Object.fromEntries(selInList.map(x => [x, c])) } })); log('hand-edit.class', { members: selInList, cls: c }); setPopover(null); push({ text: `Class ${c} on ${selInList.length} members · hand edit` }) }} onCancel={() => setPopover(null)} />
      </Popover>

      <Modal open={modal === 'remove' && selInList.length > 0} onClose={() => setModal(null)} title={`Remove ${selInList.length} members from ${f.id}?`} size="sm" testid="remove-modal"
        footer={<><Button onClick={() => setModal(null)}>Cancel</Button><Button variant="danger-solid" testid="remove-confirm" onClick={() => { removeMembers(selInList); setModal(null) }}>Remove {selInList.length}</Button></>}>
        <p style={{ margin: 0 }}>They stay out of {f.id} on every regroup until restored. Verdicts are untouched.</p>
        <div className="row wrap" style={{ gap: 4, marginTop: 10 }}>{selInList.map(x => <Chip key={x} size="sm" tone="grey">{x}</Chip>)}</div>
      </Modal>
      <Modal open={modal === 'remove-member' && !!railMember} onClose={() => setModal(null)} title={`Remove ${railMember?.id} from ${f.id}?`} size="sm" testid="remove-member-modal"
        footer={<><Button onClick={() => setModal(null)}>Cancel</Button><Button variant="danger-solid" testid="remove-member-confirm" onClick={() => { if (railMember) removeMembers([railMember.id]); setModal(null) }}>Remove</Button></>}>
        <p style={{ margin: 0 }}>It stays out of {f.id} on every regroup until restored. Its verdict is untouched.</p>
      </Modal>
      <Modal open={modal === 'make-exemplar' && !!railMember} onClose={() => setModal(null)} title={`Make ${railMember?.id} the exemplar of ${f.id}?`} size="sm" testid="make-exemplar-modal"
        footer={<><Button onClick={() => setModal(null)}>Cancel</Button><Button variant="primary" icon="sparkle" testid="make-exemplar-confirm" disabled={!railMember || railMember.id === edits.exemplar || railMember.verdict === 'artifact'} disabledReason={railMember?.verdict === 'artifact' ? 'artifact verdict — cannot anchor a family' : 'already the exemplar'}
          onClick={() => { if (!railMember) return; setEdits(e => ({ ...e, exemplar: railMember.id, staleEdges: true })); log('hand-edit.exemplar', { member: railMember.id, previous: edits.exemplar }); setModal(null); push({ text: `${railMember.id} is the exemplar of ${f.id} · edges partially stale · not wired yet: POST hand edit` }) }}>Make exemplar</Button></>}>
        <p style={{ margin: 0 }}>{edits.exemplar} {edits.exemplar === f.exemplar ? '(seed) ' : ''}stays a member. The exemplar is the human anchor; the medoid {f.medoid} is still computed.</p>
      </Modal>
    </div>
  )
}

function VerdictLine({ v }: { v: Verdict }) {
  if (v === 'unjudged') return <span className="lib-verdict" style={{ color: '#c27400' }}>unjudged</span>
  return <span className="lib-verdict"><span className="vdot" style={{ background: VERDICT_COLOUR[v] }} />{v}</span>
}

export function TagInput({ onApply, onCancel }: { onApply: (tag: string) => void; onCancel: () => void }) {
  const [t, setT] = useState('')
  const err = t && !TAG_RULE.test(t) ? 'tags are lowercase words, 2–32 characters' : null
  return (
    <div className="stack" style={{ gap: 8 }}>
      <TextField value={t} onChange={v => setT(v)} placeholder="tag" invalid={!!err} onEnter={() => { if (t && !err) onApply(t) }} testid="tag-input" autoFocus block />
      {err && <span className="k-field-error" role="alert" data-testid="tag-error"><Icon name="alert-circle" size={11} />{err}</span>}
      <div className="row wrap" style={{ gap: 4 }}>{TAG_VOCABULARY.filter(x => !t || x.startsWith(t)).slice(0, 6).map(x => <Chip key={x} size="sm" tone="grey" onClick={() => setT(x)}>{x}</Chip>)}</div>
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <Button size="sm" onClick={onCancel}>Cancel</Button>
        <Button size="sm" variant="primary" testid="tag-apply" disabled={!t || !!err} disabledReason={!t ? 'type a tag' : err ?? ''} onClick={() => onApply(t)}>Apply</Button>
      </div>
    </div>
  )
}

function ClassPicker({ onApply, onCancel }: { onApply: (cls: string) => void; onCancel: () => void }) {
  const [c, setC] = useState(CLASS_OPTIONS[0].name)
  return (
    <div className="stack" style={{ gap: 6 }} onKeyDown={e => { const o = CLASS_OPTIONS.find(x => x.key === e.key); if (o) { e.preventDefault(); setC(o.name) } else if (e.key === 'Enter') onApply(c) }}>
      <div className="lib-radio-list" role="radiogroup" aria-label="class">
        {CLASS_OPTIONS.map(o => (
          <button key={o.key} type="button" role="radio" aria-checked={c === o.name} className="lib-radio-row" data-testid={`class-option-${o.key}`} onClick={() => setC(o.name)}>
            <span className="lib-radio" /><span className="k-kbd sm">{o.key}</span><span className="lib-swatch" style={{ background: o.colour, width: 10, height: 10 }} /><span className="mono">{o.name}</span>
          </button>
        ))}
      </div>
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <Button size="sm" onClick={onCancel}>Cancel</Button>
        <Button size="sm" variant="primary" testid="class-apply" onClick={() => onApply(c)}>Apply</Button>
      </div>
    </div>
  )
}

/* ================================================================ member rail ================================================================ */
function MemberRail({ m, f, detail, yDomain, sign, edits, setEdits, onUndoAdd, onRemove, onMakeExemplar, popover, setPopover }: {
  m: Member; f: MotifFamily; detail: FamilyDetail; yDomain: [number, number]; sign: number; edits: FamilyEdits; setEdits: (fn: (e: FamilyEdits) => FamilyEdits) => void
  onUndoAdd: (id: string) => void; onRemove: () => void; onMakeExemplar: () => void; popover: string; setPopover: (v: string | null) => void
}) {
  const { push } = useToast()
  const revRef = useRef<HTMLButtonElement>(null), tagRef = useRef<HTMLButtonElement>(null)
  const [note, setNote] = useState(edits.notes[m.id] ?? '')
  const [saved, setSaved] = useState<string | null>(null)
  const trace = memberTrace(m, f.shape, sign)
  const context = useMemo(() => { const rnd = (i: number) => Math.sin(i * 1.7 + m.seed) * 0.012 + Math.sin(i / 9 + m.seed) * 0.02; const pre = Array.from({ length: 30 }, (_, i) => rnd(i)); const ev = motifShape(f.shape, sign * m.amplitudeMv, m.seed, { n: Math.round(m.durationS) }); const post = Array.from({ length: 30 }, (_, i) => rnd(i + 60)); return [...pre, ...ev, ...post] }, [m, f.shape, sign])
  const tags = edits.tags[m.id] ?? m.tags
  const past = m.d > detail.cut
  const exemplarReason = m.id === edits.exemplar ? 'already the exemplar' : m.verdict === 'artifact' ? 'artifact verdict — cannot anchor a family' : null
  const saveNote = () => { if ((edits.notes[m.id] ?? '') === note) return; if (note.length > 500) return; setEdits(e => ({ ...e, notes: { ...e.notes, [m.id]: note } })); recordDemoWrite('library', 'hand-edit.note', { member: m.id }); setSaved('note saved') }
  const current = m.revisions[m.revisions.length - 1]
  return (
    <aside className="k-card lib-rail" data-testid="member-rail" aria-label={`member ${m.id}`}>
      <div className="row">
        <b className="mono" style={{ fontSize: 14 }}>{m.id}</b>
        {m.addedByHand && <span className="k-badge t-purple">added by hand</span>}
        {m.role === 'exemplar' && <span className="k-badge t-green">exemplar</span>}
        {m.role === 'medoid' && <span className="k-badge t-purple">medoid</span>}
        <span className="mono" style={{ marginLeft: 'auto', color: past ? 'var(--purple)' : 'var(--muted)', fontSize: 12 }}>d {m.d.toFixed(2)}</span>
      </div>
      <div>
        <MotifPlot exemplar={trace} medoid={f.medoidTrace} colour={f.colour} yDomain={yDomain} height={92} testid="rail-member-plot" />
        <div className="row lib-cap" style={{ justifyContent: 'space-between', paddingLeft: 30 }}><span>0</span><span>{f.durationS} s</span></div>
      </div>
      <div>
        <MiniTrace values={context} yDomain={yDomain} width="100%" height={36} band={[30, 30 + Math.round(m.durationS)]} ground="grey" zeroLine={false} testid="rail-context" title={`±30 s of signal around ${m.id}; the span is shaded`} />
        <div className="row lib-cap" style={{ justifyContent: 'space-between' }}><span>−30 s</span><span>+30 s</span></div>
      </div>
      <KeyValue align="right" dense items={[
        { k: 'recording · channel', v: `${m.recording} · ${m.channel}` },
        { k: 'onset · duration', v: `${m.onsetH.toFixed(1)} h · ${m.durationS.toFixed(1)} s` },
        { k: 'found by', v: m.foundBy },
      ]} testid="rail-member-kv" />
      {m.handRecord && (
        <div className="lib-hand-box" data-testid="hand-record">
          <div className="row" style={{ gap: 6 }}><Icon name="user" size={12} /><span>{m.handRecord}</span><Button variant="link" size="sm" style={{ marginLeft: 'auto' }} testid="hand-undo" onClick={() => onUndoAdd(m.id)}>Undo</Button></div>
          <span style={{ color: 'var(--text-2)' }}>{past ? `d ${m.d.toFixed(2)} is past the cut; kept in ${f.id} when regrouped` : `kept in ${f.id} when regrouped`}</span>
        </div>
      )}
      <div className="lib-kvrow"><span className="k">revisions</span>
        <button ref={revRef} type="button" className="lib-plain mono v" data-testid="revisions-link" onClick={() => setPopover(popover === 'revisions' ? null : 'revisions')}>{m.revisions.map(r => `rev ${r.rev} ${r.origin === 'machine' ? `machine ${r.spanId}` : 'edited'}`).join(' · ')}</button></div>
      <div className="lib-kvrow"><span className="k">verdict <InfoTip title="verdicts are read-only here">verdicts are written only in Review and Explore (§4.1, P6)</InfoTip></span>
        <span className="v">{m.verdict === 'unjudged' ? <span style={{ color: '#c27400' }}>unjudged</span> : <><span style={{ width: 7, height: 7, borderRadius: '50%', background: VERDICT_COLOUR[m.verdict], display: 'inline-block', marginRight: 5 }} />{m.verdict}{m.verdictAt ? ` · ${m.verdictAt}` : ''}</>}
          <Button variant="link" size="sm" testid="open-in-review" onClick={() => navigate(`review/queue/q-15?item=${m.id}`)}>Open in Review</Button></span></div>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="lib-cap" style={{ fontSize: 11 }}>tags</span>
        <span className="row" style={{ gap: 4, flexWrap: 'wrap', justifyContent: 'flex-end' }} data-testid="rail-tags">
          {tags.map((t, i) => <Chip key={t} size="sm" tone={i === 0 ? 'blue' : 'grey'} onRemove={() => { setEdits(e => ({ ...e, tags: { ...e.tags, [m.id]: tags.filter(x => x !== t) } })); recordDemoWrite('library', 'hand-edit.untag', { member: m.id, tag: t }) }} removeLabel={`remove tag ${t}`}>{t}</Chip>)}
          <button ref={tagRef} type="button" className="k-chip sm outline k-chip-btn" style={{ borderStyle: 'dashed' }} data-testid="rail-add-tag" onClick={() => setPopover(popover === 'rail-tag' ? null : 'rail-tag')}>+ tag</button>
        </span>
      </div>
      <div className="stack" style={{ gap: 4 }}>
        <span className="lib-cap" style={{ fontSize: 11 }}>class {saved === 'class saved' && <span style={{ color: 'var(--green)' }}>· saved ✓</span>}</span>
        <SelectField value={edits.cls[m.id] ?? ''} testid="rail-class" ariaLabel="class" onChange={v => { setEdits(e => ({ ...e, cls: { ...e.cls, [m.id]: v } })); recordDemoWrite('library', 'hand-edit.class', { member: m.id, cls: v }); setSaved('class saved') }}
          options={[{ value: '', label: '— none' }, ...CLASS_OPTIONS.map(c => ({ value: c.name, label: `${c.key} · ${c.name}` }))]} />
      </div>
      <div onBlur={saveNote} className="stack" style={{ gap: 3 }}>
        <TextField multiline rows={2} value={note} onChange={setNote} placeholder="note" invalid={note.length > 500} testid="rail-note" block />
        {(note.length >= 450 || saved === 'note saved') && <span className="lib-cap" style={{ color: note.length > 500 ? 'var(--red)' : undefined }}>{note.length >= 450 ? `${note.length} / 500${note.length > 500 ? ' — too long, not saved' : ''}` : 'note saved ✓'}</span>}
      </div>
      <div className="lib-rail-actions">
        <span className="row" style={{ gap: 8 }}>
          <Button icon="sparkle" testid="make-exemplar" disabled={!!exemplarReason} disabledReason={exemplarReason ?? undefined} onClick={onMakeExemplar}>Make exemplar</Button>
          <Button icon="pencil" testid="redraw-in-explore" onClick={() => navigate(`explore/span-edit/${m.id}?from=library/family/${f.id}&span=${current.spanId}`)}>Redraw in Explore</Button>
        </span>
        <Button variant="danger" icon="minus" testid="rail-remove" onClick={onRemove}>Remove from family</Button>
      </div>
      <Popover open={popover === 'revisions'} onClose={() => setPopover(null)} anchorRef={revRef} title={`Revisions of ${m.id}`} width={380} placement="left-start" testid="revisions-popover">
        <table className="lib-scores">
          <thead><tr><th>rev</th><th>span</th><th>origin</th><th>run</th><th>role</th></tr></thead>
          <tbody>{m.revisions.map(r => <tr key={r.rev}><td>{r.rev}</td><td>{r.spanId}</td><td style={{ color: r.origin === 'machine' ? 'var(--blue-600)' : 'var(--green)' }}>{r.origin}</td><td>{r.run}</td><td>{r.role}</td></tr>)}</tbody>
        </table>
        <div className="lib-cap" style={{ marginTop: 6 }}>a human edit writes a new annotation; the detection stays on its run (§4.2)</div>
      </Popover>
      <Popover open={popover === 'rail-tag'} onClose={() => setPopover(null)} anchorRef={tagRef} title={`Tag ${m.id}`} width={280} placement="left-start" testid="rail-tag-popover">
        <TagInput onApply={t => { setEdits(e => ({ ...e, tags: { ...e.tags, [m.id]: tags.includes(t) ? tags : [...tags, t] } })); recordDemoWrite('library', 'hand-edit.tag', { member: m.id, tag: t }); setPopover(null); push({ text: `Tagged ${m.id} “${t}” · hand edit` }) }} onCancel={() => setPopover(null)} />
      </Popover>
    </aside>
  )
}
