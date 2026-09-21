/* library.atlas — frames library-2 (single motifs) and library-2b (sequences).
 * The density test: the family cards × exemplar + medoid, the rail's exemplar-vs-medoid and the amplitude
 * histogram, all on ONE shared mV domain (D5), unnormalised.
 *
 * Live notes (stage-3 wiring):
 *  - No grouping is named here. Which atlas is drawn follows the resolved grouping's `unit`; `g-07`/`g-08` were
 *    fixture ids and gating on them meant a live grouping always fell to "undrawn".
 *  - `exemplarTrace` / `medoidTrace` are real decimated mV off the memmap and are drawn as they arrive, on the
 *    page's shared domain. Nothing is normalised: PRD Part 2 is explicit that normalising the cards destroys the
 *    evidence of the scaling laws, which is the reason the cards exist.
 *  - The member overlay is gone. It used to synthesise ten waveforms with `motifShape` and draw them over a real
 *    medoid; a synthesised trace beside a real one is a finding that is not there. This read carries two traces
 *    per family and says so.
 *  - The amplitude histogram's axis comes from the family's own `ampDomain` and the length of `ampBins`, so it
 *    cannot claim 0.1–0.4 mV over some other range.
 *  - Scope chips are labelled from the recordings payload, and the omitted counts show a loading state rather
 *    than a fabricated number.
 */
import { useMemo, type KeyboardEvent } from 'react'
import {
  Button, Chip, Dropdown, EmptyState, Histogram, Icon, InfoTip, KeyValue, Page, fmtInt, useQueryState,
} from '../kit'
import { Header } from '../shell/Header'
import { navigate, setQuery } from '../state'
import { useSourced } from '../api/seam'
import { live } from '../api/seam'
import { AMP_DOMAIN, FAMILY_COLOURS, UNIT_LABEL, getMotifFamilies, getOmitted, getRecordingGroups, getSequenceFamilies, type Grouping, type MotifFamily, type RecGroup, type SequenceFamily, type Unit } from '../api/library'
import { useToast } from '../shell/Toast'
import {
  GroupingBar, LoadFailed, Loading, MotifPlot, MotifsActions, OMITTED_SKETCH_NOTE, OmittedDrawer, OmittedThumb, SectionBar, centreTrace, fmtMv, fmtMvSigned,
  omittedReasonSummary, sharedMvDomain, tracePeak, useAllGroupings, useEmptyLibrary, useFilters,
  useMotifGroupingId, useQueueToast, useRememberMotifsRoute, useSelection, useSequenceGroupingId,
} from './chrome'
import { EmptyMotifsPage } from './EmptyLibrary'

/** The exemplar and medoid of one family, DC offset removed and their own peak measured. Nothing is scaled;
 *  see `centreTrace`. `peak` is what the card prints when the family runs past the shared domain. */
export interface FamilyTraces { ex: number[]; me: number[]; peak: number }
export function centredTraces(fs: { id: string; exemplarTrace: number[]; medoidTrace: number[] }[]): Map<string, FamilyTraces> {
  const out = new Map<string, FamilyTraces>()
  for (const f of fs) {
    const ex = centreTrace(f.exemplarTrace ?? []), me = centreTrace(f.medoidTrace ?? [])
    out.set(f.id, { ex, me, peak: Math.max(tracePeak(ex), tracePeak(me)) })
  }
  return out
}
/** `{orderKept, orderKeptOf, orderKeptNote, judgedOf}` — measured by the bridge, and ABSENT when it could not
 *  measure them. The rail used to print `orderKept` over `sequences`, two unrelated quantities, which is how
 *  "order kept 14 of 10" happened. The fixture type predates the fields. */
type SeqMeasured = { orderKept?: number; orderKeptOf?: number; orderKeptNote?: string; judgedOf?: number }
const measured = (f: SequenceFamily) => f as unknown as SequenceFamily & SeqMeasured
/** An id printed once when the bridge has no distinct name for it (`{id:"F-03", name:"F-03"}` read "F-03 F-03"
 *  on the card, the crumb, the subtitle and the rail's aria-label). */
export const familyName = (id: string, name: string) => (name && name !== id ? name : '')

/** `recKey:channel` → `label · channel`. The labels come from the recordings payload; with none in hand the raw
 *  key is shown rather than a fixture's name for some other corpus. */
export const scopeLabel = (k: string, labels?: Record<string, string>) => { const [r, c] = k.split(':'); return `${labels?.[r] ?? r} · ${c}` }
export const inScopeOf = (f: MotifFamily, sel: string[]) => (sel.length ? sel.reduce((s, k) => s + (f.cells[k]?.count ?? 0), 0) : f.members)
/** The bridge echoes the extent its `ampBins` were counted over; the fixture type predates the field. */
const ampDomainOf = (f: MotifFamily): [number, number] => (f as unknown as { ampDomain?: [number, number] }).ampDomain ?? AMP_DOMAIN

type SortKey = 'id' | 'scope' | 'judged' | 'duration' | 'hand'

export function AtlasPage({ inert, backdrop }: { inert?: boolean; backdrop?: boolean }) {
  useRememberMotifsRoute()
  const [empty] = useEmptyLibrary()
  const [unitQ, setUnitQ] = useQueryState<string>('unit', 'motifs')
  const unit: Unit = unitQ === 'sequences' ? 'sequences' : 'motifs'
  const [motifGid] = useMotifGroupingId()
  const [seqGid] = useSequenceGroupingId()
  const groupings = useAllGroupings()
  const gid = unit === 'sequences' ? seqGid : motifGid
  const grouping = groupings.all.find(g => g.id === gid) ?? null
  // The grouping id starts `''` and resolves in an effect, so every read here used to fire once with
  // `grouping=undefined` and again with the resolved id — three heavy reads done twice on every cold open,
  // serialised behind one sqlite connection. They are held until the id has resolved (or until the groupings
  // read says this library holds none of that unit, which resolves to "no grouping" rather than to an id).
  const motifsReady = !groupings.loading && (!!motifGid || !groupings.all.some(g => g.unit === 'motifs'))
  const seqsReady = !groupings.loading && (!!seqGid || !groupings.all.some(g => g.unit === 'sequences'))
  const motifs = useSourced(() => (motifsReady ? getMotifFamilies(motifGid || undefined) : live(Promise.resolve<MotifFamily[]>([]))), [motifsReady, motifGid])
  const seqs = useSourced(() => (seqsReady ? getSequenceFamilies(seqGid || undefined) : live(Promise.resolve<SequenceFamily[]>([]))), [seqsReady, seqGid])
  const recs = useSourced(() => (motifsReady ? getRecordingGroups(motifGid || undefined) : live(Promise.resolve<RecGroup[]>([]))), [motifsReady, motifGid])
  const labels = useMemo(() => Object.fromEntries((recs.data ?? []).map(r => [r.key, r.label])), [recs.data])
  if (empty) return <EmptyMotifsPage />
  const demo = motifs.source === 'demo' || seqs.source === 'demo'
  const subtitle = backdrop ? 'atlas · editing grouping' : unit === 'sequences' ? `atlas · grouping ${gid} · sequences` : undefined
  const error = groupings.error ?? motifs.error ?? seqs.error ?? recs.error
  const loading = motifs.loading || seqs.loading || groupings.loading || !motifsReady || !seqsReady
  const noneOfUnit = !groupings.loading && !groupings.error && !groupings.all.some(g => g.unit === unit)
  return (
    <>
      <MotifsHeader subtitle={subtitle} gid={gid} demo={demo} />
      <Page testid="atlas-page" style={inert ? { pointerEvents: 'none' } : undefined}>
        <SectionBar section="motifs" crumbs={[{ label: 'Recurrence', onClick: () => navigate('library/recurrence') }, { label: 'Atlas' }]} actions={<MotifsActions />} />
        <GroupingBar unit={unit} grouping={grouping} from="atlas" inert={inert}
          onUnit={u => { setQuery({ unit: u === 'motifs' ? null : u, family: null }, true); setUnitQ(u === 'motifs' ? null : u) }} />
        {error && <LoadFailed what="the atlas" error={error} onRetry={() => { motifs.reload(); seqs.reload(); groupings.reload(); recs.reload() }} />}
        {loading && !error && <Loading height={600} testid="atlas-loading" />}
        {!loading && !error && !grouping && (
          <EmptyState icon="grid" bordered title={noneOfUnit ? `No grouping of ${UNIT_LABEL[unit]} yet` : `No grouping ${gid}`}
            caption={noneOfUnit ? 'nothing has been grouped at this unit — compute one from Edit grouping' : 'it is not among the saved groupings'} />
        )}
        {!loading && !error && grouping && motifs.data && seqs.data && (unit === 'sequences'
          ? <SequenceAtlas families={seqs.data} motifFamilies={motifs.data} grouping={grouping} />
          : <MotifAtlas families={motifs.data} grouping={grouping} labels={labels} />)}
      </Page>
      {!inert && grouping && <OmittedDrawer groupingId={grouping.id} unit={unit} />}
    </>
  )
}

function MotifsHeader({ subtitle, gid, demo }: { subtitle?: string; gid: string; demo: boolean }) {
  const [sel] = useSelection()
  const [scopeQ] = useQueryState('scope', '')
  const n = scopeQ === 'all' ? 0 : sel.length
  return <Header workspace="Library" page="Motifs" subtitle={subtitle ?? `atlas${gid ? ` · grouping ${gid}` : ''} · ${n ? `${n} channel${n === 1 ? '' : 's'}` : 'all channels'}`} search="Search spans, runs, families" demo={demo} />
}

/* ================================================================ single motifs (frame 2) ================================================================ */
function MotifAtlas({ families, grouping, labels }: { families: MotifFamily[]; grouping: Grouping; labels: Record<string, string> }) {
  const [sel, setSel] = useSelection()
  const [scopeQ] = useQueryState('scope', '')
  const scope = scopeQ === 'all' ? [] : sel
  const [familyQ, setFamilyQ] = useQueryState('family', '')
  const [sort, setSort] = useQueryState<SortKey>('sort', 'id')
  const [filters] = useFilters()
  /* ONE shared, unnormalised mV domain — but set at the 75th percentile of the per-family peak rather than at
     the maximum, and after each trace's own DC offset is removed. Before: the global extent was −3.67…+0.0004
     mV (one family's baseline), so the domain was ±3.8 while the median family peaks at 0.0009 mV — 97 of 149
     cards drew as a straight line under a caption asserting that the amplitudes compare. Normalising per card
     is forbidden (PRD Part 2: it destroys the evidence of the scaling laws), so instead the outliers no longer
     set the scale for everyone and the families past the domain are marked with their own measured peak. */
  const traces = useMemo(() => centredTraces(families), [families])
  const yDomain = useMemo(() => sharedMvDomain([...traces.values()].map(t => t.peak)), [traces])
  const clippedCount = useMemo(() => [...traces.values()].filter(t => t.peak > yDomain[1]).length, [traces, yDomain])
  const peakOf = (id: string) => traces.get(id)?.peak ?? 0
  const clipOf = (id: string) => (peakOf(id) > yDomain[1] ? peakOf(id) : null)
  const withScope = families.map(f => ({ f, inScope: inScopeOf(f, scope) }))
  const visible = withScope.filter(x => x.f.members >= filters.minMembers)
  const hidden = withScope.length - visible.length
  const sorted = [...visible].sort((a, b) => sort === 'scope' ? b.inScope - a.inScope : sort === 'judged' ? b.f.judgedPct - a.f.judgedPct : sort === 'duration' ? b.f.durationS - a.f.durationS : sort === 'hand' ? b.f.hand - a.f.hand : a.f.id.localeCompare(b.f.id))
  const selected = sorted.find(x => x.f.id === familyQ) ?? sorted[0]
  const total = sorted.reduce((s, x) => s + x.inScope, 0)
  const onKey = (e: KeyboardEvent) => {
    const i = sorted.findIndex(x => x.f.id === selected?.f.id)
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowDown' ? 4 : e.key === 'ArrowUp' ? -4 : 0
    if (d) { e.preventDefault(); const j = Math.max(0, Math.min(sorted.length - 1, i + d)); setFamilyQ(sorted[j].f.id) }
    else if (e.key === 'Enter' && selected) navigate(`library/family/${selected.f.id}`)
  }
  const removeScope = (k: string) => { if (scopeQ === 'all') return; setSel(s => s.filter(x => x !== k)) }
  const legendSpan = 4 - (sorted.length % 4 || 4) || 4
  return (
    <div className="lib-split">
      <div className="stack" style={{ gap: 10, minWidth: 0 }}>
        <div className="lib-scope" data-testid="atlas-scope">
          <span className="lib-muted-label">scope</span>
          {scope.length ? scope.map(k => <Chip key={k} tone="blue" size="sm" testid={`scope-chip-${k}`} onRemove={() => removeScope(k)} removeLabel={`remove ${scopeLabel(k, labels)} from scope`}>{scopeLabel(k, labels)}</Chip>)
            : <Chip tone="grey" testid="scope-all">all recordings</Chip>}
          <Button variant="link" testid="back-to-recurrence" onClick={() => navigate('library/recurrence')}>‹ back to recurrence</Button>
          <span className="lib-cap" style={{ fontSize: 11 }} data-testid="scope-caption">{sorted.length} families · {fmtInt(total)} members {scope.length ? 'in scope' : 'in every recording'}{hidden ? ` · ${hidden} hidden by ≥ ${filters.minMembers} members` : ''}</span>
          <span style={{ marginLeft: 'auto' }}>
            <Dropdown variant="outline" size="sm" prefix="sort:" testid="atlas-sort" value={sort} onChange={v => setSort(v)} menuWidth={220}
              options={[{ value: 'id', label: 'family id' }, { value: 'scope', label: scope.length ? 'members in scope' : 'members' }, { value: 'judged', label: 'judged fraction' }, { value: 'duration', label: 'duration' }, { value: 'hand', label: 'hand edits' }]} />
          </span>
        </div>
        <div className="lib-grid c4" data-testid="atlas-grid" role="listbox" aria-label="families" tabIndex={0} onKeyDown={onKey}>
          {sorted.map(({ f, inScope }) => (
            <div key={f.id} role="option" aria-selected={f.id === selected?.f.id} tabIndex={-1} className={`k-card lib-fcard${f.id === selected?.f.id ? ' selected' : ''}`} style={{ cursor: 'pointer', ...(f.id === selected?.f.id ? { borderWidth: 1 } : null) }}
              data-testid={`family-card-${f.id}`} onClick={() => setFamilyQ(f.id)} onDoubleClick={() => navigate(`library/family/${f.id}`)}>
              <div className="lib-fcard-head"><span className="id" style={{ color: f.colour }}>{f.id}</span><span className="nm">{familyName(f.id, f.name)}</span><span className="ct">{scope.length ? `${inScope} of ${f.members}` : `${f.members}`}</span></div>
              <div className="lib-badges">
                <span className={`k-badge ${f.recordings > 1 ? 't-blue' : 't-grey'}`} title={`spans ${f.recordings} recording${f.recordings === 1 ? '' : 's'}`}>{f.recordings} rec</span>
                {f.hand > 0 && <button type="button" className="k-badge t-purple lib-badge-btn" data-testid={`hand-badge-${f.id}`} title="open the family's hand edits" onClick={e => { e.stopPropagation(); navigate(`library/family/${f.id}?hand=1`) }}>{f.hand} hand</button>}
                {f.artifact > 0 && <span className="k-badge t-red" title={`${f.artifact} channels where ${f.id} is a cross-channel artifact (flagged, kept visible)`}>artifact {f.artifact}</span>}
              </div>
              <MotifPlot exemplar={traces.get(f.id)?.ex} medoid={traces.get(f.id)?.me} colour={f.colour} yDomain={yDomain} height={92} testid={`family-plot-${f.id}`} clippedPeak={clipOf(f.id)} />
              <div className="lib-foot"><span title="duration">{f.durationS < 10 ? f.durationS.toFixed(1) : f.durationS} s</span>
                <span title={`peak-to-baseline of the exemplar and medoid traces, measured: ${fmtMv(peakOf(f.id))} mV · mean member depth ${f.depthLabel}`}>peak {fmtMv(peakOf(f.id))} mV</span>
                <span className="lib-judged" title={`${f.judged} of ${f.members} judged`}><span className="bar"><i style={{ width: `${f.judgedPct}%` }} /></span>{f.judgedPct}% judged</span></div>
            </div>
          ))}
          <div className="lib-legend" style={{ gridColumn: `span ${legendSpan}`, alignSelf: 'start', paddingTop: 4 }} data-testid="atlas-legend">
            <span><i style={{ background: '#1f2937' }} />exemplar (human seed)</span>
            <span><i style={{ background: 'var(--muted-2)' }} />medoid (computed, family colour)</span>
            <span data-testid="atlas-scale-note">shared mV scale on every card · {fmtMvSigned(yDomain[0])}…{fmtMvSigned(yDomain[1])} mV{clippedCount ? ` · ${clippedCount} clipped` : ''}
              <InfoTip title="shared scale">Each trace has its own DC offset (its median) removed and nothing else done to it — no card is normalised (D5), so amplitudes compare across the whole atlas.
                The shared domain is the 75th percentile of the per-family peak, not the maximum: family peaks in this grouping span four decades, and setting the domain by the largest one drew almost every card as a flat line.
                {clippedCount ? ` ${clippedCount} of ${families.length} families run past it; each is marked "clipped" and prints its own measured peak.` : ''} Every card prints its measured peak, so a family far below the domain is still readable as a number.</InfoTip></span>
          </div>
        </div>
        {!sorted.length && <EmptyState title="No families match" caption={`every family has fewer than ${filters.minMembers} members`} bordered />}
      </div>
      {selected ? <MotifRail f={selected.f} inScope={selected.inScope} scoped={scope.length > 0} yDomain={yDomain} grouping={grouping} traces={traces.get(selected.f.id)} clippedPeak={clipOf(selected.f.id)} /> : <div />}
    </div>
  )
}

function MotifRail({ f, inScope, scoped, yDomain, grouping, traces, clippedPeak }: { f: MotifFamily; inScope: number; scoped: boolean; yDomain: [number, number]; grouping: Grouping; traces?: FamilyTraces; clippedPeak?: number | null }) {
  const queue = useQueueToast()
  const pool = scoped ? inScope : f.members
  const unjudged = f.members - f.judged
  const ampDomain = ampDomainOf(f)
  const nBins = Math.max(1, f.ampBins.length)
  const span = ampDomain[1] - ampDomain[0]
  const bins = f.ampBins.map((n, i) => ({ x0: ampDomain[0] + (i * span) / nBins, x1: ampDomain[0] + ((i + 1) * span) / nBins, count: n }))
  const modal = bins.reduce((m, b, i) => (b.count > bins[m].count ? i : m), 0)
  return (
    <aside className="k-card lib-rail" data-testid="atlas-rail" aria-label={`${f.id}${familyName(f.id, f.name) ? ` ${f.name}` : ''}`}>
      <div className="row"><span className="mono b" style={{ color: f.colour, fontSize: 15 }}>{f.id}</span><span style={{ fontWeight: 700, fontSize: 15 }}>{familyName(f.id, f.name)}</span><span className="k-chip blue sm" style={{ marginLeft: 'auto' }}>{f.recordings} recordings</span></div>
      <div className="lib-cap" style={{ fontSize: 11, marginTop: -6 }}>{f.members} members · {scoped ? `${inScope} in scope · ` : ''}{f.hand} hand edits</div>
      <div>
        <MotifPlot exemplar={traces?.ex} medoid={traces?.me} colour={f.colour} yDomain={yDomain} height={88} testid="rail-exemplar-medoid" clippedPeak={clippedPeak} />
        <div className="row lib-cap" style={{ justifyContent: 'space-between', paddingLeft: 30 }}><span>0</span><span>{f.durationS < 10 ? f.durationS.toFixed(1) : f.durationS} s</span></div>
      </div>
      <div className="row lib-cap" style={{ fontSize: 10.5 }}>
        <span><i style={{ display: 'inline-block', width: 12, height: 2, background: '#1f2937', verticalAlign: 'middle', marginRight: 4 }} />exemplar {f.exemplar}</span>
        <span><i style={{ display: 'inline-block', width: 12, height: 2, background: f.colour, verticalAlign: 'middle', marginRight: 4 }} />medoid {f.medoid}</span>
        <span className="k-chip green sm" style={{ marginLeft: 'auto' }} title="distance between exemplar and medoid">d {f.exemplarMedoidD.toFixed(2)}</span>
      </div>
      <div className="lib-cap" style={{ fontSize: 10.5 }} data-testid="rail-members-not-drawn">
        the other {Math.max(0, pool - 2)} member{pool - 2 === 1 ? '' : 's'} of this family {pool - 2 === 1 ? 'is' : 'are'} not drawn: this read carries the exemplar and the medoid
        as real mV, and no waveform for the rest. <Button variant="link" size="sm" style={{ padding: 0 }} testid="rail-open-members" onClick={() => navigate(`library/family/${f.id}`)}>Open the family</Button> to list them.
      </div>
      <div className="row lib-cap" style={{ fontSize: 10.5 }}><span>peak-to-peak amplitude · mV</span><span style={{ marginLeft: 'auto' }}>n per bin</span></div>
      <Histogram bins={bins} height={66} showCounts={false} colour="#dcc6f1" highlightBin={(_, i) => i === modal} highlightColour={f.colour}
        format={v => String(+v.toFixed(2))} label={`${f.id} peak-to-peak amplitude histogram, ${nBins} bins, ${+ampDomain[0].toFixed(3)}–${+ampDomain[1].toFixed(3)} mV`} testid="rail-amplitude-histogram" />
      <KeyValue align="right" dense items={[
        { k: 'duration', v: `${f.durationS < 10 ? f.durationS.toFixed(1) : f.durationS} s ± ${f.durationSd}` },
        { k: 'mean member d', v: f.meanMemberD.toFixed(2) },
        { k: 'SNR', v: `${f.snrDb} dB` },
        { k: 'judged', v: `${f.judged} of ${f.members}`, tone: 'amber' },
        { k: 'channels', v: <span className="row" style={{ gap: 4, justifyContent: 'flex-end' }}><span className="k-badge t-red">artifact {f.artifactChannels}</span><span className="k-badge t-amber">prop. {f.propChannels}</span><span className="k-badge t-green">ind. {f.indChannels}</span></span>, info: <InfoTip title="cross-channel counts">artifact = channels where the family is a cross-channel artifact (flagged, kept) · prop. = propagated copies on a neighbouring channel · ind. = independent occurrences</InfoTip> },
        { k: 'edges', v: f.edges },
      ]} testid="rail-stats" />
      <div className="lib-rail-actions">
        <Button variant="primary" iconRight="arrow-right" testid="open-family" onClick={() => navigate(`library/family/${f.id}`)}>Open all {f.members} members</Button>
        <Button icon="target" iconRight="arrow-right" testid="seed-search" onClick={() => navigate(`discovery/seed?seed=${encodeURIComponent(f.exemplar)}&family=${encodeURIComponent(f.id)}`)}>Seed search in Discovery</Button>
        <Button icon="link" iconRight="arrow-right" testid="interrogate" onClick={() => navigate(`analyse/interrogation?source=family:${encodeURIComponent(f.id)}`)}>Interrogate in Analyse</Button>
        <Button icon="checklist" iconRight="arrow-right" testid="send-unjudged" disabled={!unjudged} disabledReason="every member is judged" onClick={() => queue(`Library · ${f.id} unjudged`, unjudged)}>Send {unjudged} unjudged to Review</Button>
        <ExportEntry id={f.id} grouping={grouping.id} />
      </div>
    </aside>
  )
}
function ExportEntry({ id, grouping }: { id: string; grouping: string }) {
  const queue = useToastOnly()
  return <Button variant="link" icon="upload" testid="export-entry" onClick={() => queue(`not wired yet: export library entry ${id} (${grouping}: exemplar, medoid, members CSV, provenance)`)}>Export entry</Button>
}
function useToastOnly() { const { push } = useToast(); return (text: string) => push({ text }) }
export function hexA(hex: string, a: number) {
  const h = hex.replace('#', ''); const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`
}

/* ================================================================ sequences (frame 2b) ================================================================ */
function SequenceAtlas({ families, motifFamilies, grouping }: { families: SequenceFamily[]; motifFamilies: MotifFamily[]; grouping: Grouping }) {
  const [familyQ, setFamilyQ] = useQueryState('family', '')
  const [, setDrawer] = useQueryState('drawer', '')
  const [filters] = useFilters()
  const omitted = useSourced(() => getOmitted(grouping.id), [grouping.id])
  const queue = useQueueToast()
  // same rule as the motif atlas: DC offset removed per trace, nothing normalised, the shared domain set at a
  // high percentile of the per-family peak and the families past it marked
  const traces = useMemo(() => centredTraces(families), [families])
  const yDomain = useMemo(() => sharedMvDomain([...traces.values()].map(t => t.peak)), [traces])
  const clipOf = (id: string) => { const p = traces.get(id)?.peak ?? 0; return p > yDomain[1] ? p : null }
  const visible = families.filter(f => f.sequences >= filters.minMembers)
  const selected = visible.find(f => f.id === familyQ) ?? visible[0]
  const onKey = (e: KeyboardEvent) => {
    const i = visible.findIndex(x => x.id === selected?.id)
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowDown' ? 3 : e.key === 'ArrowUp' ? -3 : 0
    if (d) { e.preventDefault(); setFamilyQ(visible[Math.max(0, Math.min(visible.length - 1, i + d))].id) }
  }
  const [, setUnit] = useQueryState('unit', 'motifs')
  const thumbDomain: [number, number] = [-0.45, 0.45]
  const singles = omitted.data ? fmtInt(omitted.data.singles.length) : null
  const omittedSeqs = omitted.data ? fmtInt(omitted.data.sequences.length) : null
  /* "motifs in no sequence" is a CATALOGUE count (members with no `sequence_members` row) and the bridge
     carries it as `motifsInNoSequence`. The banner used to render `singles.length`, which counts what THIS
     grouping omitted — 0 here, against 1,957 members that really are in no sequence, read as "every motif is
     accounted for in a sequence". Where the bridge does not carry the count, the banner says so. */
  const inNoSequence = omitted.data?.motifsInNoSequence ?? null
  return (
    <div className="lib-split">
      <div className="stack" style={{ gap: 10, minWidth: 0 }}>
        <div className="lib-banner" data-testid="sequences-banner">
          <Icon name="flag" size={13} className="ic" />
          {omitted.data
            ? <span data-testid="sequences-banner-text">Sequences only: {grouping.id} left out {singles} single motifs and {omittedSeqs} sequences that fit no family — flagged, not deleted.
              {' '}{inNoSequence == null ? 'How many catalogue motifs belong to no sequence at all is not carried by this read.' : `Separately, ${fmtInt(inNoSequence)} motifs in the catalogue belong to no sequence at all.`}</span>
            : <span data-testid="sequences-banner-loading">Sequences only: counting what {grouping.id} left out…</span>}
          <Button variant="link" style={{ marginLeft: 'auto' }} testid="show-omitted" onClick={() => setDrawer('omitted')}>Show omitted</Button>
        </div>
        <div className="lib-grid c3" data-testid="atlas-grid" role="listbox" aria-label="sequence families" tabIndex={0} onKeyDown={onKey}>
          {visible.map(f => (
            <div key={f.id} role="option" aria-selected={f.id === selected?.id} tabIndex={-1} className={`k-card lib-fcard${f.id === selected?.id ? ' selected' : ''}`} style={{ cursor: 'pointer' }}
              data-testid={`family-card-${f.id}`} onClick={() => setFamilyQ(f.id)} onDoubleClick={() => navigate(`library/family/${f.id}`)}>
              <div className="lib-fcard-head"><span className="id" style={{ color: f.colour }}>{f.id}</span><span className="nm">{familyName(f.id, f.name)}</span><span className="ct">{f.sequences} sequences</span></div>
              <div className="lib-badges">
                <span className="k-badge t-purple" title="composition: family of each event, in order">{f.compositionLabel}</span>
                <span className={`k-badge ${f.recordings > 1 ? 't-blue' : 't-grey'}`}>{f.recordings} rec</span>
                {f.hand > 0 && <span className="k-badge t-purple">{f.hand} hand</span>}
              </div>
              <MotifPlot exemplar={traces.get(f.id)?.ex} medoid={traces.get(f.id)?.me} colour={f.colour} yDomain={yDomain} height={105} testid={`family-plot-${f.id}`} clippedPeak={clipOf(f.id)} />
              <div className="lib-foot"><span>{f.durationLabel}</span><span>{f.gapLabel}</span>
                <span className="lib-judged"><span className="bar"><i style={{ width: `${f.judgedPct}%` }} /></span>{f.judgedPct}% judged</span></div>
            </div>
          ))}
        </div>
        {!visible.length && <EmptyState title="No sequence families match" caption={`every family has fewer than ${filters.minMembers} sequences`} bordered />}
        <div className="k-card" style={{ padding: '12px 14px' }} data-testid="sequences-omitted">
          <div className="row"><Icon name="flag" size={14} style={{ color: 'var(--amber)' }} /><span className="lib-h">Omitted from this round</span>
            <Button variant="link" style={{ marginLeft: 'auto' }} testid="send-omitted" disabled={!omitted.data} disabledReason="still counting what this grouping left out"
              onClick={() => omitted.data && queue(`Library · ${grouping.id} omitted`, omitted.data.singles.length + omitted.data.sequences.length)}>Send omitted to Review as a queue</Button></div>
          {omitted.error && <LoadFailed what="omitted entries" error={omitted.error} onRetry={omitted.reload} />}
          {omitted.loading && !omitted.error && <Loading height={140} testid="sequences-omitted-loading" />}
          {omitted.data && (
            <div className="lib-grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 20, marginTop: 8 }}>
              <div className="stack" style={{ gap: 8 }}>
                <span className="lib-cap" style={{ color: 'var(--text-2)' }} data-testid="omitted-singles-label">{singles} single motifs omitted by the current motif grouping</span>
                <button type="button" className="lib-thumbrow lib-plain" onClick={() => setDrawer('omitted')} title={`show omitted single motifs · ${OMITTED_SKETCH_NOTE}`}>{omitted.data.singles.slice(0, 7).map(e => <OmittedThumb key={e.id} e={e} yDomain={thumbDomain} />)}</button>
                <span className="lib-cap">switch the unit to <Button variant="link" size="sm" testid="switch-to-singles" onClick={() => setUnit(null)}>single motifs</Button> to group these</span>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <span className="lib-cap" style={{ color: 'var(--text-2)' }}>{omittedSeqs} sequences omitted by {grouping.id}</span>
                <button type="button" className="lib-thumbrow lib-plain" onClick={() => setDrawer('omitted')} title={`show omitted sequences · ${OMITTED_SKETCH_NOTE}`}>{omitted.data.sequences.slice(0, 5).map(e => <OmittedThumb key={e.id} e={e} yDomain={thumbDomain} width={86} />)}</button>
                <span className="lib-cap" data-testid="omitted-sequences-reason">{omittedReasonSummary(omitted.data.sequences)}</span>
              </div>
            </div>
          )}
        </div>
      </div>
      {selected ? <SequenceRail f={selected} yDomain={yDomain} grouping={grouping} motifFamilies={motifFamilies} traces={traces.get(selected.id)} clippedPeak={clipOf(selected.id)} /> : <div />}
    </div>
  )
}

function SequenceRail({ f, yDomain, grouping, motifFamilies, traces, clippedPeak }: { f: SequenceFamily; yDomain: [number, number]; grouping: Grouping; motifFamilies: MotifFamily[]; traces?: FamilyTraces; clippedPeak?: number | null }) {
  const queue = useQueueToast()
  const m = measured(f)
  // `judgedOf` is the motif count the bridge actually counted verdicts over; `f.motifs` is a different total
  const judgedOf = m.judgedOf ?? f.motifs
  const unjudged = Math.max(0, judgedOf - f.judgedMotifs)
  const colourOf = (id: string) => motifFamilies.find(m2 => m2.id === id)?.colour ?? FAMILY_COLOURS[id] ?? '#999'
  return (
    <aside className="k-card lib-rail" data-testid="atlas-rail" aria-label={`${f.id}${familyName(f.id, f.name) ? ` ${f.name}` : ''}`}>
      <div className="row"><span className="mono b" style={{ color: f.colour, fontSize: 15 }}>{f.id}</span><span style={{ fontWeight: 700, fontSize: 15 }}>{familyName(f.id, f.name)}</span><span className="k-chip blue sm" style={{ marginLeft: 'auto' }}>{f.recordings} recordings</span></div>
      <div className="lib-cap" style={{ fontSize: 11, marginTop: -6 }}>{f.sequences} sequences · {f.motifs} motifs · exemplar {f.exemplar}</div>
      <div>
        <MotifPlot exemplar={traces?.ex} medoid={traces?.me} colour={f.colour} yDomain={yDomain} height={88} testid="rail-exemplar-medoid" clippedPeak={clippedPeak} />
        <div className="row lib-cap" style={{ justifyContent: 'space-between', paddingLeft: 30 }}><span>0</span><span>{f.durationLabel.replace('~', '')}</span></div>
      </div>
      <div className="row lib-cap" style={{ fontSize: 10.5 }}>
        <span><i style={{ display: 'inline-block', width: 12, height: 2, background: '#1f2937', verticalAlign: 'middle', marginRight: 4 }} />exemplar</span>
        <span><i style={{ display: 'inline-block', width: 12, height: 2, background: f.colour, verticalAlign: 'middle', marginRight: 4 }} />medoid</span>
        <span className="k-chip green sm" style={{ marginLeft: 'auto' }}>d {f.exemplarMedoidD.toFixed(2)}</span>
      </div>
      <div className="lib-cap" style={{ fontSize: 10.5 }}>composition</div>
      <div className="lib-comp" data-testid="composition-strip" style={{ background: hexA(f.colour, 0.35) }}>
        {f.composition.map((id, i) => (
          <span key={i} style={{ display: 'contents' }}>
            {i > 0 && <span className="gap">{i === 1 && <span>{f.gapS}</span>}</span>}
            <span className="box" style={{ background: colourOf(id) }} title={`${id} · ${motifFamilies.find(m => m.id === id)?.name ?? ''}`}>{id}</span>
          </span>
        ))}
      </div>
      <KeyValue align="right" dense items={[
        // "order kept" is the count of member sequences that preserve the exemplar's order, over the member
        // sequences that could be compared — both from the bridge, and BOTH ABSENT when it could not measure
        // them. It used to print the exemplar's event count over the member count ("14 of 10").
        m.orderKept != null && m.orderKeptOf != null
          ? { k: 'order kept', v: `${m.orderKept} of ${m.orderKeptOf}`, info: <InfoTip title="order kept">member sequences whose events resolve to the same families, in the same order, as the exemplar — out of the member sequences whose events all resolved to a family</InfoTip> }
          : { k: 'order kept', v: <span className="muted">not computed</span>, info: <InfoTip title="not computed">{m.orderKeptNote ?? 'the bridge did not measure order preservation for this family'}</InfoTip> },
        { k: 'exemplar composition', v: `${f.composition.length} events` },
        { k: 'gap between events', v: f.gapS },
        { k: 'mean member d', v: f.meanMemberD.toFixed(2) },
        { k: 'judged', v: `${f.judgedMotifs} of ${judgedOf} motifs`, tone: 'amber' },
      ]} testid="rail-stats" />
      <div className="lib-cap" style={{ fontSize: 10.5 }} data-testid="rail-members-not-drawn">
        the other {Math.max(0, f.sequences - 2)} member{f.sequences - 2 === 1 ? '' : 's'} are not drawn: this read carries the exemplar and the medoid as real mV,
        and no waveform for the rest.
      </div>
      <div className="lib-rail-actions">
        <Button variant="primary" iconRight="arrow-right" testid="open-family" onClick={() => navigate(`library/family/${f.id}`)}>Open all {f.sequences} sequences</Button>
        <span className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
          <Button icon="target" disabled disabledReason="needs multi-seed — no seed-search algorithm takes several seeds yet (§7.6)" testid="seed-search">Seed search in Discovery</Button>
          <InfoTip title="needs multi-seed">A sequence family has several events; no seed-search algorithm takes several seeds yet (§7.6), so Discovery cannot search for it.</InfoTip><span className="lib-cap" style={{ whiteSpace: 'nowrap' }}>needs multi-seed</span>
        </span>
        <Button icon="link" iconRight="arrow-right" testid="interrogate" onClick={() => navigate(`analyse/interrogation?source=family:${encodeURIComponent(f.id)}`)}>Interrogate in Analyse</Button>
        <Button icon="checklist" iconRight="arrow-right" testid="send-unjudged" disabled={!unjudged} disabledReason={judgedOf ? 'every motif is judged' : 'this read counted no motifs to judge'} onClick={() => queue(`Library · ${f.id} unjudged motifs`, unjudged)}>Send {unjudged} unjudged motifs to Review</Button>
        <ExportEntry id={f.id} grouping={grouping.id} />
      </div>
    </aside>
  )
}
