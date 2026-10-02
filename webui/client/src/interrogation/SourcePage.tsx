/* analyse.interrogation — the source block (frames interrogation-1, interrogation-1b).
 * §6.2: a chain starts from a source block; this one emits a SpanSet from a Library family, with
 * per-member include/exclude that scopes the run and leaves the Library entry alone. */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Badge, Button, Callout, Checkbox, ColourDot, Dropdown, EmptyState, EventSlideshow, Field, Icon, InfoTip, LineChart, Page,
  SectionCard, fmtInt, recordDemoWrite, useNotWired, useQueryState, useSim, type BadgeStatus, type SlideEvent, type SlideSort,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, setQuery } from '../state'
import { useSourced } from '../api/seam'
import { eventWindow, getSourceBlock, liveEventPoints, liveYDomain, paddingLabel, sequenceWindow, sequenceWindowOver, windowOver, type SourceBlock } from '../api/interrogation'
import {
  ALIGNMENTS, FAMILY_Y_DOMAIN, RUN_STEPS, UPSTREAMS, VERDICT_COLOUR, VERDICT_ORDER, eventCurve,
  type InterrogationMember,
} from '../fixtures/interrogation'
import { AddStagePopover, ChainCard, EmptyScope, InterrogationToolbar, LoadFailed, Loading, RunVeil, SaveTemplateModal } from './chrome'
import { SourcePicker } from './SourcePicker'
import { inScopeIds, interrogationHref, markSimForced, useFamilyQuery, useInterrogationDraft, useUpstreamQuery, wasSimForced } from './draft'

export function SourcePage() {
  const [familyId] = useFamilyQuery()
  const [upstream] = useUpstreamQuery()
  const [draft] = useInterrogationDraft()
  const [scopeQ] = useQueryState('scope', 'all')
  const block = useSourced(() => getSourceBlock(familyId, upstream), [familyId, upstream])
  const fam = block.data?.family
  const nScope = !block.data ? 0 : scopeQ === 'none' ? 0 : inScopeIds(block.data.members, draft, fam!.id, true).size
  return (
    <>
      <Header workspace="Analyse" page="Library family" search="Search spans, runs, families" demo={block.source === 'demo'}
        subtitle={fam ? `${fam.id} ${fam.name} · ${nScope} of ${fam.within} members in scope` : 'source block'}
        extra={<button className="btn ghost" onClick={() => navigate('analyse/interrogation/sequence')} data-testid="open-sequences" title="the steepest-slope rose across the events of one stored sequence">Sequences · slope rose →</button>} />
      <Page testid="interrogation-source">
        {block.error ? <LoadFailed what="the source block" error={block.error} onRetry={block.reload} />
          : !block.data ? <Loading what="the family" /> : <SourceBody block={block.data} />}
      </Page>
    </>
  )
}

function SourceBody({ block }: { block: SourceBlock }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [familyId, setFamilyId] = useFamilyQuery()
  const [upstream] = useUpstreamQuery()
  const [draft, setDraft] = useInterrogationDraft()
  const [popover, setPopover] = useQueryState('popover', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [excludeArtifacts, setExcludeArtifacts] = useQueryState('artifacts', 'out')
  const [adjOnly, setAdjOnly] = useQueryState('adjudicated', '')
  const [recordingQ, setRecordingQ] = useQueryState('recording', 'all')
  const [channelQ, setChannelQ] = useQueryState('channel', 'all')
  const [alignQ, setAlignQ] = useQueryState('align', 'onset')
  const [distanceQ, setDistanceQ] = useQueryState('distance', block.family.threshold.toFixed(2))
  const [scopeQ, setScopeQ] = useQueryState('scope', 'all')
  const [frameQ, setFrameQ] = useQueryState('frame', 'padding')
  const [overlaySeed, setOverlaySeed] = useState(0)
  const [saveOpen, setSaveOpen] = useState(false)

  const sourceRef = useRef<HTMLButtonElement>(null)
  const stageRef = useRef<HTMLButtonElement>(null)

  const fam = block.family
  const hidesArtifacts = excludeArtifacts === 'out'
  const href = (page: 'source' | 'block1' | 'block2', extra?: Record<string, string | null | undefined>) => interrogationHref(page, familyId, upstream, extra)
  const handExcluded = draft.excluded[fam.id] ?? []
  const scope = scopeQ === 'none' ? new Set<string>() : inScopeIds(block.members, draft, fam.id, hidesArtifacts)

  /* ---- filters. Sorting and paging are the slideshow's own (P8: ten cards at once). ---- */
  const visible = useMemo(() => {
    let xs = block.members.filter(m => m.d <= Number(distanceQ))
    if (adjOnly === '1') xs = xs.filter(m => m.verdict !== 'unadjudicated')
    if (recordingQ !== 'all') xs = xs.filter(m => m.recording === recordingQ)
    if (channelQ !== 'all') xs = xs.filter(m => m.channel === channelQ)
    return xs
  }, [block.members, distanceQ, adjOnly, recordingQ, channelQ])
  const setPage = (_n: number) => {}

  /* fixup-h: every member is a slideshow card drawn from its STORED SAMPLES at their own times — the grid used to
     resample each snippet to one value per second by linear interpolation and put every tile on one shared y.
     The window follows Source settings › context padding (the stored context by default, U11); each card is on a
     y measured from its own trace with a scale bar (Q15); a window the store counted more than one fall in is
     red and says so; and an edge the detector's fall-multiple cap set, rather than the event's own morphology,
     is dashed where the card reaches it (Q18). */
  const padding = draft.settings.padding
  const slides = useMemo<SlideEvent[]>(() => visible.map(m => {
    const sn = m.snippet
    const onset = sn && m.onset_offset_s !== undefined ? sn.t_s[0] + m.onset_offset_s : null
    const w = eventWindow(m, padding)
    const whole = padding === 'snippet'
    return {
      id: m.id, title: m.id,
      onset, extremum: onset === null ? null : onset + m.duration_s,
      window: onset === null ? null : [onset - w.pre, onset + m.duration_s + w.post],
      count: m.purity ?? null, countOf: 'falls',
      // an edge is only on the card when the card draws the whole stored extent
      leftCapped: whole && !!m.left_capped, rightCapped: whole && !!m.right_capped,
      facts: `${m.depth_mV.toFixed(Math.abs(m.depth_mV) >= 10 ? 1 : 3)} mV · ${m.duration_s >= 10 ? m.duration_s.toFixed(0) : m.duration_s.toFixed(1)} s · ${m.channel} · ${m.onset_h.toFixed(1)} h`,
      sort: { onset: m.onset_h, depth: m.depth_mV, duration: m.duration_s, falls: m.purity ?? null },
      trace: sn ? { t: sn.t_s, v: sn.v, decimated: !!sn.decimated, nSource: sn.n ?? sn.t_s.length, mismatch: sn.mismatch ?? null }
        : { t: [], v: [], decimated: false, nSource: 0, error: 'the store holds no snippet for this event' },
    }
  }), [visible, padding])
  const SLIDE_SORTS: SlideSort[] = [
    { value: 'onset', label: 'onset time' }, { value: 'depth', label: 'depth', descending: true },
    { value: 'duration', label: 'fall duration', descending: true }, { value: 'falls', label: 'falls in window', descending: true },
  ]

  /* ---- the run ---- */
  const sim = useSim('analyse.interrogation.run')
  useEffect(() => {
    if (stateQ === 'running') { sim.force({ status: 'running', steps: RUN_STEPS, step: 1, fraction: 0.42, startedAt: Date.now() }); markSimForced(true) }
    else if (stateQ === 'failed') { sim.force({ status: 'failed', steps: RUN_STEPS, step: 1, fraction: 0.4, finishedAt: Date.now(), error: 'resolve from original recording failed (simulated): M2_aug_concat_fs1.mat could not be opened for member s-0344 · on missing source = fail the run' }); markSimForced(true) }
    else if (wasSimForced()) { sim.reset(); markSimForced(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const staleFrom = draft.staleFrom
  const status: Record<string, BadgeStatus> = {
    source: sim.status === 'running' && sim.step === 0 ? 'running' : 'cached',
    block1: sim.status === 'running' && sim.step >= 1 ? 'running' : sim.status === 'failed' ? 'failed' : staleFrom ? 'stale' : 'cached',
    block2: sim.status === 'running' && sim.step >= 2 ? 'running' : staleFrom ? 'stale' : 'cached',
  }

  const markStale = () => setDraft(d => ({ ...d, staleFrom: 'block1' }))
  const toggleMember = (id: string, on: boolean) => {
    setDraft(d => {
      const cur = d.excluded[fam.id] ?? []
      return { ...d, staleFrom: 'block1', excluded: { ...d.excluded, [fam.id]: on ? cur.filter(x => x !== id) : [...cur, id] } }
    })
    recordDemoWrite('analyse', 'scope-member', { family: fam.id, member: id, in_scope: on })
  }
  const setAll = (mode: 'all' | 'none' | 'invert') => {
    setScopeQ(null)
    setDraft(d => {
      const cur = new Set(d.excluded[fam.id] ?? [])
      const next = mode === 'all' ? [] : mode === 'none' ? visible.map(m => m.id)
        : visible.filter(m => !cur.has(m.id)).map(m => m.id)
      return { ...d, staleFrom: 'block1', excluded: { ...d.excluded, [fam.id]: next } }
    })
  }

  const runChain = () => { setStateQ(null); setDraft(d => ({ ...d, staleFrom: null })); sim.start({ steps: RUN_STEPS, stepMs: 800 }) }

  const nScope = scope.size
  const nVisibleScope = visible.filter(m => scope.has(m.id)).length
  const runReason = nScope === 0 ? 'no members in scope · nothing to measure'
    : fam.disabledReason ? fam.disabledReason : sim.busy ? 'the chain is already running' : undefined

  /* ---- scope matrix ---- */
  const channels = useMemo(() => [...new Set(block.members.map(m => m.channel))].sort(), [block.members])
  const matrix = useMemo(() => {
    const recs = [...new Set(block.members.map(m => m.recording))]
    const rows = recs.map(rec => ({
      rec,
      cells: channels.map(ch => block.members.filter(m => m.recording === rec && m.channel === ch && scope.has(m.id)).length),
    }))
    const excludedCells = channels.map(ch => block.members.filter(m => m.channel === ch && !scope.has(m.id)).length)
    return { rows, excludedCells }
  }, [block.members, channels, scope])

  /* ---- overlay: a seeded random 10 of the members in scope (P8) ----
     Drawn from the stored samples over the padding window, aligned on the onset or the trough (both are the
     store's own indices). The synthetic "medoid" curve that used to be drawn in black over the real members
     is gone: it was a fixture shape, not a measurement of this family. */
  const overlayMembers = useMemo(() => {
    const inScope = block.members.filter(m => scope.has(m.id))
    const step = Math.max(1, Math.floor(inScope.length / 10))
    return Array.from({ length: Math.min(10, inScope.length) }, (_, i) => inScope[(i * step + overlaySeed * 3) % inScope.length])
  }, [block.members, scope, overlaySeed])
  /* Which frame the overlay draws (fixup-h, Q19). The stored window is right for ONE event; a sequence or an
     overlay of many wants each event framed back to the previous event's trough (capped at 14 falls), or a
     sharkfin's slow rise — most of what makes the shape — is a shoulder at the left edge. The frame is the
     core's (`extent.sequence_frames`); E's context-padding default stays, and this sits beside it. */
  const sequenceFrame = frameQ === 'sequence'
  const overlayWindow = useMemo(() => (sequenceFrame ? sequenceWindowOver(overlayMembers) : windowOver(overlayMembers, padding)), [overlayMembers, padding, sequenceFrame])
  const overlayDomain = useMemo(() => liveYDomain(overlayMembers) ?? FAMILY_Y_DOMAIN, [overlayMembers])
  const alignShift = (m: InterrogationMember) => (alignQ === 'trough' ? m.duration_s : 0)
  const overlayPoints = (m: InterrogationMember): [number, number][] => {
    const own = sequenceFrame ? sequenceWindow(m) : overlayWindow
    const pts = liveEventPoints(m, own.pre, own.post)
      ?? eventCurve(m, 20, 30).map((v, i) => [i - 20, v] as [number, number]).filter(pt => pt[0] <= 40)
    const shift = alignShift(m)
    return shift ? pts.map(([a, b]) => [a - shift, b] as [number, number]) : pts
  }
  const alignOptions = ALIGNMENTS.map(o => o.value === 'steepest' ? { ...o, disabled: true, reason: 'the steepest sample is not served per member yet · align on onset or trough' } : o)

  return (
    <>
      <InterrogationToolbar
        backDisabledReason="this is the full chain · the source block is the chain root"
        sourceLabel={<>Library family · {fam.id} {fam.name}</>}
        sourceOpen={popover === 'source'} sourceRef={sourceRef} arrived
        onSourceToggle={() => setPopover(popover === 'source' ? null : 'source')}
        onSaveTemplate={() => setSaveOpen(true)}
        stale={!!staleFrom}
        primary={sim.busy
          ? <Button icon="stop" onClick={() => { sim.cancel(); setStateQ(null) }} testid="cancel-run">Cancel</Button>
          : <Button variant="primary" icon={staleFrom ? 'refresh' : 'play'} disabled={!!runReason} disabledReason={runReason} onClick={runChain} testid="run-chain">
            {staleFrom ? 'Re-run from 01' : 'Run chain'}
          </Button>}>
        <SourcePicker open={popover === 'source'} onClose={() => setPopover(null)} anchorRef={sourceRef} familyId={familyId}
          onPickFamily={id => { setQuery({ family: id === 'F-03' ? null : id, popover: null, tab: null }, false); setFamilyId(id); setPage(1) }} />
      </InterrogationToolbar>

      <ChainCard chain={block.chain} current="source" status={status} onAddStage={() => setPopover(popover === 'stage' ? null : 'stage')}
        onSelect={id => { if (id === 'block1') navigate(href('block1')); else if (id === 'block2') navigate(href('block2')) }} />
      <span ref={stageRef} style={{ display: 'none' }} />
      <AddStagePopover open={popover === 'stage'} onClose={() => setPopover(null)} anchorRef={sourceRef}
        onPick={kind => { setQuery({ upstream: kind === 'slope' ? null : kind }, false); push({ text: `01 is now ${UPSTREAMS[kind].block} · 02 Aggregate re-wires from its Features` }) }} />

      {sim.status === 'failed' && (
        <Callout tone="red" title="The run failed at 01 Resolve spans" testid="run-failed"
          action={<Button size="sm" icon="refresh" onClick={runChain}>Retry</Button>}>{sim.error}</Callout>
      )}
      {sim.status === 'done' && (
        <Callout tone="green" icon="check-circle" testid="run-done" action={<Button size="sm" variant="primary" icon="bar-chart" onClick={() => navigate(href('block2'))}>Open 02 Aggregate</Button>}>
          ran {RUN_STEPS.length} stages over {nScope} members · results are the fixture results (demo)
        </Callout>
      )}

      <div className="ig-cols">
        {/* ------------------------------------------------ the family ------------------------------------------------ */}
        <div className="ig-stack">
          <SectionCard testid="source-block" title={<span>● Library family <span className="ig-muted mono ig-small">— → SpanSet</span></span>}
            info="A source block does not measure anything; it decides which spans the chain runs over. Excluding a member scopes this run only — the Library entry is untouched."
            actions={<Dropdown testid="clustering" value="v3" onChange={() => notWired('change the clustering the family came from')}
              options={[{ value: 'v3', label: `clustering ${block.clustering.method} · t ${block.clustering.t} · ${block.clustering.version}` }, { value: 'v2', label: 'clustering Ward · t 8.4 · v2', description: 'the family had 94 members under v2' }]} />}>
            <div className="ig-fact" data-testid="family-facts" style={{ marginBottom: 8 }}>
              {fam.id} {fam.name} · {fmtInt(fam.members)} members · {fam.within} within d ≤ {fam.threshold.toFixed(2)} · {fam.recordings.length} recordings · {fam.channels.length} channels · {fam.adjudicated} adjudicated
            </div>

            <div className="ig-row" style={{ marginBottom: 8 }} data-testid="member-filters">
              <Checkbox checked={adjOnly === '1'} onChange={v => { setAdjOnly(v ? '1' : null); setPage(1) }} label="adjudicated only" testid="filter-adjudicated" />
              <Checkbox checked={hidesArtifacts} onChange={v => { setExcludeArtifacts(v ? null : 'in'); setPage(1); markStale() }} label="exclude artifacts" testid="filter-artifacts" />
              <Dropdown size="sm" testid="filter-distance" prefix="distance ≤" value={distanceQ} onChange={v => { setDistanceQ(v); setPage(1); markStale() }} active
                options={['0.25', '0.30', '0.35', '0.40', '0.50'].map(v => ({ value: v, label: v }))} />
              <Dropdown size="sm" testid="filter-recording" prefix="recording" value={recordingQ} onChange={v => { setRecordingQ(v); setPage(1) }}
                options={[{ value: 'all', label: 'all' }, ...fam.recordings.map(r => ({ value: r, label: r })),
                  { value: 'M4_aug', label: 'M4_aug', disabled: true, reason: 'M4_aug_concat_fs1.mat is held out (D6) · every workspace refuses it' }]} />
              <Dropdown size="sm" testid="filter-channel" prefix="channel" value={channelQ} onChange={v => { setChannelQ(v); setPage(1) }}
                options={[{ value: 'all', label: 'all' }, ...channels.map(ch => ({ value: ch, label: ch }))]} />
            </div>

            <div className="ig-row" style={{ marginBottom: 8 }} data-testid="scope-row">
              <b style={{ fontSize: 12.5 }}>{nScope} of {fam.within} in scope</b>
              <Button size="sm" variant="link" onClick={() => setAll('all')} testid="select-all">select all</Button>
              <Button size="sm" variant="link" onClick={() => setAll('none')} testid="select-none">none</Button>
              <Button size="sm" variant="link" onClick={() => setAll('invert')} testid="select-invert">invert</Button>
              <span className="k-spacer" />
              <span className="ig-foot"><Icon name="link" size={11} />window: context padding {paddingLabel(padding)} · the stored samples, never resampled</span>
            </div>

            <div className="ig-rel" data-testid="member-grid">
              {sim.busy && <RunVeil label={`${sim.steps[sim.step] ?? 'queued'} · ${Math.round(sim.fraction * 100)} %`} fraction={sim.fraction} />}
              {nScope === 0 && <EmptyScope onSelectAll={() => setAll('all')} />}
              {visible.length === 0
                ? <EmptyState testid="no-member-match" size="sm" icon="filter" title="no member matches these filters"
                  caption={`${fam.within} members are within d ≤ ${fam.threshold.toFixed(2)} · widen the distance, recording or channel filter`}
                  action={<Button onClick={() => { setDistanceQ(null); setRecordingQ(null); setChannelQ(null); setAdjOnly(null); setPage(1) }} testid="clear-filters">Clear filters</Button>} />
                : (
                  <EventSlideshow testid="event-slideshow" events={slides} sorts={SLIDE_SORTS} cap={10} columns={5} colour={fam.colour} unit="mV"
                    title={`${visible.length} members · ${nVisibleScope} in scope`} selected={null}
                    onSelect={id => navigate(href('block1', { event: id }))}
                    capRule={block.capped ? `${block.capped.cap_mult} × fall` : undefined}
                    frameNote={padding === 'snippet' ? 'the whole stored window — the extent the detector kept, which is also what the Library hashes' : `context padding ${paddingLabel(padding)} around the fall, inside the stored window`}
                    cardExtra={e => {
                      const m = visible.find(x => x.id === e.id)
                      if (!m) return null
                      const on = scope.has(m.id)
                      return (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }} data-testid={`member-${m.id}`}>
                          {(handExcluded.includes(m.id) || (m.verdict === 'artifact' && hidesArtifacts)) && <span style={{ color: '#a05e00' }}>excluded</span>}
                          <ColourDot colour={VERDICT_COLOUR[m.verdict]} title={m.verdict} />
                          <Checkbox checked={on} onChange={v => toggleMember(m.id, v)} ariaLabel={`${m.id} in scope`} testid={`member-check-${m.id}`}
                            disabled={m.verdict === 'artifact' && hidesArtifacts} disabledReason={m.verdict === 'artifact' && hidesArtifacts ? 'artifacts are excluded by the filter above' : undefined} />
                        </span>
                      )
                    }} />
                )}
            </div>

            <div className="ig-row" style={{ marginTop: 8 }}>
              <span className="ig-foot" data-testid="verdict-legend">
                {VERDICT_ORDER.map(v => <span key={v} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginRight: 10 }}>
                  <ColourDot colour={VERDICT_COLOUR[v]} />{v}
                </span>)}
              </span>
              <span className="k-spacer" />
              <span className="ig-foot">click a card to open the event in {UPSTREAMS[upstream].block} · the tick scopes it in or out of this run</span>
            </div>
          </SectionCard>

          <SectionCard testid="members-overlaid" title="Members overlaid"
            info="A seeded random sample, never all of them: families run to hundreds of members (P8). Traces are the store's detrended mV samples over the context-padding window, on a y axis measured from the traces drawn — not normalised (D5). The window follows Source settings › context padding: the stored context by default, so a slow precursor (a sharkfin's rise) is on the plot."
            subtitle={`random ${overlayMembers.length} of ${nScope} in scope · aligned on ${alignQ} · window −${Math.round(overlayWindow.pre)} … +${Math.round(overlayWindow.post)} s`}
            actions={<>
              <Dropdown testid="overlay-frame" prefix="frame" value={frameQ} onChange={setFrameQ}
                options={[{ value: 'padding', label: 'context padding', description: 'one window for every event, from Source settings' }, { value: 'sequence', label: 'sequence frame', description: 'each event back to the previous event\'s trough, capped at 14 falls; 1.8 falls after the trough' }]} />
              <Button size="sm" icon="shuffle" onClick={() => setOverlaySeed(s => s + 1)} testid="overlay-resample">resample</Button>
              <Dropdown testid="overlay-align" prefix="align" value={alignQ} onChange={setAlignQ} options={alignOptions} />
            </>}>
            {nScope === 0
              ? <EmptyState testid="overlay-empty" size="sm" icon="wave" title="nothing in scope to overlay" caption="tick a member above" />
              : <><LineChart testid="overlay-plot" height={340} xLabel={`seconds from ${alignQ}`} yLabel="mV" yDomain={overlayDomain}
              xFormat={v => `${v > 0 ? '+' : ''}${Math.round(v)} s`}
              series={overlayMembers.map(m => ({ label: m.id, colour: fam.colour, points: overlayPoints(m), width: 1 }))} legend={false} />
              <div className="ig-foot" style={{ marginTop: 4 }} data-testid="overlay-window-note">
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><span style={{ width: 14, height: 2, background: fam.colour }} />member · the stored samples, nothing held past a snippet's end</span>
                <span className="k-spacer" />
                <span data-testid="overlay-frame-note">{sequenceFrame
                  ? `sequence frame · each event back to the previous trough · ${overlayMembers.filter(m => m.sequence?.capped).length} of ${overlayMembers.length} capped at 14 falls, ${overlayMembers.filter(m => m.sequence?.clipped).length} clipped by the stored snippet`
                  : `context padding ${paddingLabel(padding)}`} · y {overlayDomain[0].toFixed(2)} to {overlayDomain[1].toFixed(2)} mV, measured from the traces drawn</span>
              </div></>}
          </SectionCard>
        </div>

        {/* ------------------------------------------------ rails ------------------------------------------------ */}
        <div className="ig-stack">
          <SectionCard testid="scope-card" title="Scope" info="How the members in scope fall across recordings and channels. A family that lives on one channel measures one electrode, not one organism."
            subtitle="members in scope by recording × channel">
            <div className="ig-scope-wrap"><table className="ig-scope">
              <thead><tr><th>recording</th>{channels.map(ch => <th key={ch}>{ch}</th>)}<th>Σ</th></tr></thead>
              <tbody>
                {matrix.rows.map(r => (
                  <tr key={r.rec} data-testid={`scope-row-${r.rec}`}>
                    <td>{r.rec}</td>
                    {r.cells.map((n, i) => <td key={i} className={n ? undefined : 'z'}>{n || '—'}</td>)}
                    <td className="sum">{r.cells.reduce((a, b) => a + b, 0)}</td>
                  </tr>
                ))}
                <tr className="ex" data-testid="scope-excluded">
                  <td>excluded</td>
                  {matrix.excludedCells.map((n, i) => <td key={i}>{n || ''}</td>)}
                  <td className="sum" style={{ color: '#c4282d' }}>{matrix.excludedCells.reduce((a, b) => a + b, 0) || ''}</td>
                </tr>
              </tbody>
            </table></div>
          </SectionCard>

          <SectionCard testid="source-settings" title="Source settings">
            <Field inline label="members" info="Which of the family's members this run resolves." labelWidth={120}>
              <Dropdown testid="setting-members" value={draft.settings.members} onChange={v => { setDraft(d => ({ ...d, staleFrom: 'block1', settings: { ...d.settings, members: v } })) }}
                options={block.settings.members.map(o => ({ ...o, label: o.value === 'in-scope' ? `all in scope (${nScope})` : o.label }))} />
            </Field>
            <Field inline label="resolve from" info="Where the samples come from. The original recording is the only source with full resolution." labelWidth={120}>
              <Dropdown testid="setting-resolve" value={draft.settings.resolveFrom} onChange={v => setDraft(d => ({ ...d, staleFrom: 'block1', settings: { ...d.settings, resolveFrom: v } }))} options={block.settings.resolveFrom} />
            </Field>
            <Field inline label="context padding" info="The window drawn around every event on these three pages, before the onset and after the trough. The stored context is what the store kept (about a minute each side, up to 46 min); a proportional padding cannot show a slow precursor to a fast event." labelWidth={120}>
              <Dropdown testid="setting-padding" value={draft.settings.padding} onChange={v => setDraft(d => ({ ...d, settings: { ...d.settings, padding: v } }))} options={block.settings.padding} />
            </Field>
            <Field inline label="on missing source" info="What happens when a member's recording is not on this installation." labelWidth={120}>
              <Dropdown testid="setting-missing" value={draft.settings.onMissing} onChange={v => setDraft(d => ({ ...d, staleFrom: 'block1', settings: { ...d.settings, onMissing: v } }))} options={block.settings.onMissing} />
            </Field>
            <div className="ig-foot" style={{ marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
              <Icon name="link" size={12} />members keep identity by file · channel · sample range
              <InfoTip title="Identity across the hand-off">Members are matched by content (file, channel, sample range), not by row id, so measurements write back per member and re-running the recipe is idempotent (§6.2).</InfoTip>
            </div>
          </SectionCard>

          <SectionCard testid="provenance-card" title="Where this family came from"
            actions={<Button variant="link" icon="external" onClick={() => navigate(`library/family?family=${fam.id}`)} testid="open-in-library">Open in Library →</Button>}>
            <div className="ig-prov">
              <div><Icon name="branch" size={13} />promoted from {fam.promotedFrom} · {fam.promotedOn}</div>
              {fam.exemplar && <div><Icon name="flag" size={13} />seeded by exemplar {fam.exemplar}</div>}
              <div><Icon name="link" size={13} />edges: scale-invariant distance · threshold {fam.threshold.toFixed(2)}</div>
              <div><Icon name="terminal" size={13} />recipe {fam.recipe} · clustering {block.clustering.version}</div>
              <div><Icon name="info" size={13} />exclusions scope this run only · Library unchanged</div>
            </div>
          </SectionCard>

          {staleFrom && (
            <Callout tone="amber" icon="alert-triangle" testid="stale-callout"
              action={<Button size="sm" variant="primary" icon="refresh" onClick={runChain} disabled={!!runReason} disabledReason={runReason}>Re-run from 01</Button>}>
              the source changed · 01 and 02 show the last run until you re-run
            </Callout>
          )}
          {fam.disabledReason && <Callout tone="amber" icon="alert-circle" testid="family-blocked">{fam.disabledReason}</Callout>}
          {fam.adjudicated === 0 && <Callout tone="amber" icon="alert-circle" testid="none-adjudicated">no member of {fam.id} has a human verdict yet · every number below is machine-only <Badge tone="blue">machine</Badge></Callout>}
        </div>
      </div>

      <SaveTemplateModal open={saveOpen} onClose={() => setSaveOpen(false)}
        defaultName={upstream === 'event-shape' ? 'event_shape_v1' : 'sharkfin_slope_v1'}
        stages={block.chain.map(b => (b.index ? `${String(b.index).padStart(2, '0')} ${b.label}` : b.label))} />
    </>
  )
}
