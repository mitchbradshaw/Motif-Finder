/* analyse.interrogation.slope — 01 Resolve spans (frames interrogation-2, 2b, 2c).
 * §6.8 `SpanSet → SpanSet + Features`: the anatomy of one event with the rules that define every number,
 * a per-event table, a sliding strip (P8) and — for a large family — a sampled overlay. */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Badge, Button, Callout, Chip, ColourDot, Dropdown, Icon, IconButton, InfoTip, LineChart, MiniTrace, Page, Seg, SectionCard,
  Slider, Table, fmtInt, recordDemoWrite, useNotWired, useQueryState, useSim, type BadgeStatus, type Column, type SortState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getSlopeBlock, liveEventCurve, liveYDomain, type SlopeBlock } from '../api/interrogation'
import {
  FAMILY_Y_DOMAIN, MARKS, ROSE_REF_SLOPE, RULES, RUN_STEPS, STALE_PREVIEW, UNITS, VERDICT_COLOUR, angleOf,
  eventCurve, eventMarks, unitScale, type InterrogationMember,
} from '../fixtures/interrogation'
import { AddStagePopover, ChainCard, InterrogationToolbar, LoadFailed, Loading, RunVeil, SaveTemplateModal } from './chrome'
import { SourcePicker } from './SourcePicker'
import { inScopeIds, markSimForced, useFamilyQuery, useInterrogationDraft, useUpstreamQuery, wasSimForced } from './draft'
import { Rose } from './Rose'

const STRIP = 10
const TABLE_PAGE = 4
/** Why a parameter control is dead while the chain runs (the shared convention). */
const BUSY = 'wait for the run'
/** Clip a curve to the plotted window so a long recovery never draws past the axis. */
const clip = (vs: number[], pre = 10, hi = 24) => vs.map((v, i) => [i - pre, v] as [number, number]).filter(pt => pt[0] <= hi)

export function SlopePage() {
  const [familyId] = useFamilyQuery()
  const [upstream] = useUpstreamQuery()
  const block = useSourced(() => getSlopeBlock(familyId, upstream), [familyId, upstream])
  const b = block.data
  return (
    <>
      <Header workspace="Analyse" page={b?.upstream.block ?? '01 Resolve spans'} search="Search spans, runs, families" demo={block.source === 'demo'}
        subtitle={b ? `${upstream === 'slope' ? 'slope analysis' : 'spike shape'} · ${b.family.id} ${b.family.name}` : 'slope analysis'} />
      <Page testid="interrogation-slope">
        {block.error ? <LoadFailed what="01 Resolve spans" error={block.error} onRetry={block.reload} />
          : !b ? <Loading what="the events" /> : <SlopeBody block={b} />}
      </Page>
    </>
  )
}

function SlopeBody({ block }: { block: SlopeBlock }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [familyId, setFamilyId] = useFamilyQuery()
  const [upstream] = useUpstreamQuery()
  const [draft, setDraft] = useInterrogationDraft()
  const [popover, setPopover] = useQueryState('popover', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [eventQ, setEventQ] = useQueryState('event', '')
  const [unitsQ, setUnits] = useQueryState('units', 'mv-10s')
  const [marksQ, setMarks] = useQueryState('marks', 'minimal')
  const [colourQ, setColour] = useQueryState('colour', 'depth')
  const [viewQ, setView] = useQueryState<'overlay' | 'rose'>('view', 'overlay')
  const [sampleQ, setSample] = useQueryState('sample', '10')
  const [sel, setSel] = useState<string[]>([])
  const [stripPage, setStripPage] = useState(1)
  const [tablePage, setTablePage] = useState(1)
  const [tableSort, setTableSort] = useState<SortState>({ key: 'depth', dir: 'desc' })
  const [overlaySeed, setOverlaySeed] = useState(4417)
  const [saveOpen, setSaveOpen] = useState(false)
  const sourceRef = useRef<HTMLButtonElement>(null)

  const fam = block.family
  const scope = inScopeIds(block.members, draft, fam.id, true)
  /* Event order: recording, then onset — the order the strip walks (frame 2: event 4 / 16 is s-0344). */
  const events = useMemo(() => {
    const recOrder = fam.recordings
    return block.members.filter(m => scope.has(m.id))
      .sort((a, b) => (recOrder.indexOf(a.recording) - recOrder.indexOf(b.recording)) || (a.onset_h - b.onset_h))
  }, [block.members, scope, fam.recordings])

  const large = events.length > 40
  const defaultIdx = Math.min(large ? 44 : 3, Math.max(0, events.length - 1))
  const selectedIdx = Math.max(0, eventQ ? events.findIndex(e => e.id === eventQ) : defaultIdx)
  const event: InterrogationMember | undefined = events[selectedIdx] ?? events[0]

  /* the strip page follows the selection unless the user pages it */
  useEffect(() => { setStripPage(Math.floor(selectedIdx / STRIP) + 1) }, [selectedIdx])

  const flagged = events.filter(e => e.flags.length)
  const stripFrom = (stripPage - 1) * STRIP
  const strip = events.slice(stripFrom, stripFrom + STRIP)

  /* ---- the pending rule edit (frame 2c) ---- */
  const pending = draft.pendingWindow
  const appliedWindow = draft.rules.steepestWindow
  const showWindow = pending ?? appliedWindow
  useEffect(() => {
    if (stateQ === 'stale' && draft.pendingWindow == null) setDraft(d => ({ ...d, pendingWindow: 5, staleFrom: 'block1' }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const sim = useSim('analyse.interrogation.run')
  useEffect(() => {
    if (stateQ === 'running') { sim.force({ status: 'running', steps: RUN_STEPS, step: 1, fraction: 0.5, startedAt: Date.now() }); markSimForced(true) }
    else if (wasSimForced()) { sim.reset(); markSimForced(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const stale = !!draft.staleFrom || pending != null
  const status: Record<string, BadgeStatus> = {
    source: 'cached',
    block1: sim.status === 'running' ? 'running' : stale ? 'stale' : 'cached',
    block2: sim.status === 'running' && sim.step >= 2 ? 'running' : stale ? 'stale' : 'cached',
  }

  /* live members carry their stored snippet: draw that, on a y domain from the data; fixtures keep the synthetic curve */
  const curveOf = (m: InterrogationMember, pre = 10, post = 24) => liveEventCurve(m, pre, post) ?? eventCurve(m, pre, post)
  const yDomain = useMemo(() => liveYDomain(block.members) ?? FAMILY_Y_DOMAIN, [block.members])
  const storeRules = block.storeRules
  const rerun = () => {
    /* Clear the forced-run flag first: the `[stateQ]` effect below runs after this navigation and would
       otherwise reset the run we are about to start (critique r1: re-run cleared stale with no run). */
    markSimForced(false)
    setStateQ(null)
    setDraft(d => ({ ...d, rules: { ...d.rules, steepestWindow: d.pendingWindow ?? d.rules.steepestWindow }, pendingWindow: null, staleFrom: null }))
    recordDemoWrite('analyse', 'apply-rules', { block: '01', steepest_window: pending ?? appliedWindow })
    sim.start({ steps: RUN_STEPS, stepMs: 700 })
  }
  const discard = () => { setDraft(d => ({ ...d, pendingWindow: null, staleFrom: null })); setStateQ(null) }

  /* ---- the anatomy figure, drawn in the chosen unit convention ---- */
  const uTime = unitScale(unitsQ).time
  const anatomy = useMemo(() => {
    if (!event) return null
    const pre = 10
    const vs = curveOf(event, pre, 24)
    const marks = eventMarks(event)
    const hi = Math.round(event.duration_s) + 14
    const pts = vs.map((v, i) => [i - pre, v] as [number, number]).filter(pt => pt[0] <= hi)
    const troughV = -event.depth_mV
    const steepV = -event.depth_mV / 2
    const tan = 0.5 * (showWindow + 2)
    const sc = (xs: [number, number][]) => xs.map(([a, b]) => [+(a * uTime).toFixed(3), b] as [number, number])
    return {
      pts: sc(pts), troughV, steepV,
      marks: { onset: marks.onset * uTime, steepest: +(marks.steepest * uTime).toFixed(2), trough: +(marks.trough * uTime).toFixed(2) },
      chord: sc([[0, pts[pre][1]], [marks.trough, troughV]]),
      tangent: sc([[marks.steepest - tan, steepV + event.max_slope * -tan], [marks.steepest + tan, steepV + event.max_slope * tan]]),
      depthLine: sc([[marks.trough, 0], [marks.trough, troughV]]),
      dom: [-pre * uTime, +((Math.round(event.duration_s) + 14) * uTime).toFixed(2)] as [number, number],
    }
  }, [event, showWindow, uTime])

  /* ---- units (fix r1: the control used to rewrite a caption and recompute nothing) ----
     `mV · s` is the frame's compressed convention: every time divides by 10 and every slope multiplies
     by 10. The angle is the same under either, because the slope and the −45° reference scale together. */
  const unitLabel = UNITS.find(o => o.value === unitsQ)?.label ?? 'mV · 10 s'
  const u = unitScale(unitsQ)
  const refSlope = +(ROSE_REF_SLOPE * u.slope).toFixed(4)
  const t = (v: number) => +(v * u.time).toFixed(3)
  const fmtT = (v: number) => `${v > 0 ? '+' : ''}${+v.toFixed(u.time === 1 ? 0 : 1)} s`
  const fmtSlope = (v: number) => (v * u.slope).toFixed(u.slope === 1 ? 4 : 3).replace('-', '−')
  const fmtSec = (v: number) => t(v).toFixed(u.time === 1 ? 1 : 2)
  const showMarks = marksQ !== 'none'
  const allMarks = marksQ === 'all'

  /* ---- sampled overlay for a large family (P8) ---- */
  const sampleSize = Number(sampleQ)
  const sample = useMemo(() => {
    const step = Math.max(1, Math.floor(events.length / sampleSize))
    const xs = Array.from({ length: Math.min(sampleSize, events.length) }, (_, i) => events[(i * step + overlaySeed) % events.length])
    return xs
  }, [events, sampleSize, overlaySeed])

  /* ---- table ---- */
  const columns: Column<InterrogationMember>[] = [
    { key: 'id', header: 'span', render: r => <span className="primary-text">{r.id}</span>, sortValue: r => r.id },
    { key: 'recording', header: 'recording', sortValue: r => r.recording },
    { key: 'channel', header: 'ch', sortValue: r => r.channel },
    { key: 'onset', header: 'onset h', align: 'right', render: r => r.onset_h.toFixed(2), sortValue: r => r.onset_h },
    { key: 'depth', header: 'depth mV', align: 'right', render: r => r.depth_mV.toFixed(3), sortValue: r => r.depth_mV },
    { key: 'slope', header: 'max slope mV/s', align: 'right', render: r => fmtSlope(r.max_slope), sortValue: r => r.max_slope },
    { key: 'angle', header: 'angle', align: 'right', render: r => `${Math.round(angleOf(r.max_slope))}°`.replace('-', '−'), sortValue: r => angleOf(r.max_slope) },
    { key: 'peak', header: 'peakedness', align: 'right', render: r => r.peakedness.toFixed(2), sortValue: r => r.peakedness },
    { key: 'duration', header: 'duration s', align: 'right', render: r => fmtSec(r.duration_s), sortValue: r => r.duration_s },
    { key: 'recovery', header: 'recovery s', align: 'right', render: r => fmtSec(r.recovery_s), sortValue: r => r.recovery_s },
    { key: 'flags', header: 'flags', render: r => r.flags.length ? <span className="ig-amber-text"><Icon name="alert-triangle" size={11} /> {r.flags.join(' · ')}</span> : null },
  ]
  /* the whole run is sorted, then paged — so "depth ↓" means the deepest events in the run, not on this page */
  const sortedEvents = useMemo(() => {
    if (!tableSort) return events
    const col = columns.find(c => c.key === tableSort.key)
    if (!col?.sortValue) return events
    const f = col.sortValue, m = tableSort.dir === 'asc' ? 1 : -1
    return [...events].sort((a, b) => {
      const va = f(a), vb = f(b)
      if (va == null || vb == null) return 0
      return (typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb))) * m
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, tableSort])
  const tableFrom = (tablePage - 1) * TABLE_PAGE
  const tableRows = sortedEvents.slice(tableFrom, tableFrom + TABLE_PAGE)

  const pick = (id: string) => setEventQ(id)

  return (
    <>
      <InterrogationToolbar
        sourceLabel={<>Library family · {fam.id} {fam.name}</>}
        sourceOpen={popover === 'source'} sourceRef={sourceRef} arrived={!stale}
        onSourceToggle={() => setPopover(popover === 'source' ? null : 'source')}
        onSaveTemplate={() => setSaveOpen(true)} stale={stale}
        primary={sim.busy
          ? <Button icon="stop" onClick={() => { sim.cancel(); setStateQ(null) }} testid="cancel-run">Cancel</Button>
          : <Button variant="primary" icon={stale ? 'refresh' : 'play'} onClick={rerun} testid="run-chain">{stale ? 'Re-run from 01' : 'Run chain'}</Button>}>
        <SourcePicker open={popover === 'source'} onClose={() => setPopover(null)} anchorRef={sourceRef} familyId={familyId}
          onPickFamily={id => { setFamilyId(id); setEventQ(null); setPopover(null); setStripPage(1) }} />
      </InterrogationToolbar>

      <ChainCard chain={block.chain} current="block1" status={status} onAddStage={() => setPopover(popover === 'stage' ? null : 'stage')}
        onSelect={id => navigate(id === 'source' ? `analyse/interrogation${familyId === 'F-03' ? '' : `?family=${familyId}`}`
          : id === 'block2' ? `analyse/interrogation/block/2${familyId === 'F-03' ? '' : `?family=${familyId}`}` : `analyse/interrogation/block/1`)} />
      <AddStagePopover open={popover === 'stage'} onClose={() => setPopover(null)} anchorRef={sourceRef} onPick={() => push({ text: 'the chain already holds a feature block · swap it from the ribbon chip' })} />

      <div className={large ? 'ig-cols even' : 'ig-cols wide-right'}>
        {/* ------------------------------------------------ anatomy ------------------------------------------------ */}
        <SectionCard testid="anatomy-card" number="01" title={block.upstream.blockTitle}
          info="One event at a time, with the three rules drawn on it. Onset, trough and steepest sample are where every number on this page comes from — change a rule and the numbers change."
          actions={<>
            <Dropdown testid="units" prefix="units" value={unitsQ} onChange={setUnits} options={UNITS} disabled={sim.busy} disabledReason={BUSY} />
            <Dropdown testid="marks" prefix="marks" value={marksQ} onChange={setMarks} options={MARKS} disabled={sim.busy} disabledReason={BUSY} />
          </>}>
          <div className="ig-rel">
            {sim.busy && <RunVeil label={`${sim.steps[sim.step] ?? 'queued'} · ${Math.round(sim.fraction * 100)} %`} fraction={sim.fraction} />}
            {stale && !sim.busy && (
              <Callout tone="amber" icon="alert-triangle" testid="stale-veil" style={{ marginBottom: 8 }}>showing last run · results are stale until re-run</Callout>
            )}
            {anatomy && event ? (
              <>
                <LineChart testid="anatomy-plot" height={210} yLabel="mV" xDomain={anatomy.dom} yDomain={yDomain}
                  xFormat={fmtT} legend={false}
                  markers={showMarks ? [
                    { x: anatomy.marks.onset, label: 'onset', colour: 'var(--blue)' },
                    { x: anatomy.marks.steepest, label: 'steepest', colour: '#7446E0' },
                    { x: anatomy.marks.trough, label: 'trough', colour: 'var(--red)' },
                  ] : []}
                  series={[
                    { label: 'event', colour: '#111827', points: anatomy.pts, width: 1.6 },
                    ...(showMarks ? [{ label: 'chord', colour: '#9ca3af', points: anatomy.chord, dashed: true, width: 1.2 }] : []),
                    ...(showMarks ? [{ label: 'steepest slope', colour: '#7446E0', points: anatomy.tangent, width: 1.8 }] : []),
                    ...(showMarks ? [{ label: 'depth', colour: 'var(--green)', points: anatomy.depthLine, width: 2.4 }] : []),
                    ...(allMarks ? [{ label: 'baseline band', colour: '#d1d5db', points: [[anatomy.dom[0], 0.012], [anatomy.dom[1], 0.012]] as [number, number][], dashed: true, width: 1 }] : []),
                  ]} />
                <div className="ig-row" style={{ marginTop: 4 }}>
                  <span className="ig-foot" data-testid="mark-legend">
                    <span><ColourDot colour="var(--blue)" /> onset</span>
                    <span><ColourDot colour="#7446E0" /> steepest</span>
                    <span><ColourDot colour="var(--red)" /> trough</span>
                    <span><span style={{ display: 'inline-block', width: 3, height: 10, background: 'var(--green)', verticalAlign: 'middle' }} /> depth</span>
                    <span><span style={{ display: 'inline-block', width: 14, height: 1, background: '#9ca3af', verticalAlign: 'middle' }} /> chord</span>
                  </span>
                  <span className="k-spacer" />
                  {event.flags.length
                    ? <Chip tone="amber" icon="alert-triangle" testid="rules-verdict">{event.flags.join(' · ')}</Chip>
                    : <Chip tone="green" icon="check" testid="rules-verdict">rules resolved cleanly</Chip>}
                </div>

                <div className="ig-readout" style={{ marginTop: 8 }} data-testid="event-readout">
                  <span>event <b>{event.id}</b> · {event.channel} · {event.onset_h.toFixed(2)} h</span>
                  <span>depth <b>{event.depth_mV.toFixed(3)} mV</b></span>
                  <span>duration <b>{fmtSec(event.duration_s)} s</b></span>
                  <span>max slope <b>{fmtSlope(event.max_slope)} mV/s</b></span>
                  <span>angle <b>{angleOf(event.max_slope).toFixed(1).replace('-', '−')}°</b></span>
                  <span>peakedness <b>{event.peakedness.toFixed(2)}</b></span>
                </div>
                <div className="ig-foot" style={{ marginTop: 4 }} data-testid="units-note">
                  units {unitLabel} · {u.note} · −45° = −{refSlope} mV/s · the angle is the same under either convention
                </div>

                <div className="ig-strip" style={{ marginTop: 10 }} data-testid="event-strip">
                  <IconButton icon="chevron-left" label="previous ten events" testid="strip-prev" bordered
                    disabled={stripPage <= 1} disabledReason="at the first event" onClick={() => setStripPage(s => Math.max(1, s - 1))} />
                  <div className="cells">
                    {strip.map((e, i) => (
                      <button key={e.id} type="button" className={`ig-cell ${e.id === event.id ? 'on' : ''}`} onClick={() => pick(e.id)}
                        data-testid={`strip-${stripFrom + i + 1}`} title={`${e.id} · ${e.depth_mV.toFixed(3)} mV`}>
                        <MiniTrace values={curveOf(e)} yDomain={yDomain} width="100%" height={40} ground="none"
                          stroke={e.id === event.id ? 'var(--blue-600)' : '#4b5563'} />
                        <span className="n">{stripFrom + i + 1}</span>
                        {e.flags.length > 0 && <span className="flag" />}
                      </button>
                    ))}
                  </div>
                  <IconButton icon="chevron-right" label="next ten events" testid="strip-next" bordered
                    disabled={stripFrom + STRIP >= events.length} disabledReason="at the last event" onClick={() => setStripPage(s => s + 1)} />
                </div>
                <div className="ig-row" style={{ marginTop: 6 }}>
                  <b style={{ fontSize: 12 }}>event {selectedIdx + 1} / {fmtInt(events.length)}</b>
                  <span className="ig-foot">showing {stripFrom + 1}–{Math.min(stripFrom + STRIP, events.length)}{large ? ` of ${fmtInt(events.length)}` : ''} · strip slides with ‹ › · <span className="ig-cell-flag-key"><span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: 3, background: 'var(--amber)' }} /> rule flag</span></span>
                  <span className="k-spacer" />
                  <Button size="sm" variant="link" testid="jump-flagged" disabled={!flagged.length} disabledReason="no event is flagged"
                    onClick={() => pick(flagged[0].id)}>jump to flagged ({flagged.length})</Button>
                </div>
              </>
            ) : <div className="ig-foot" data-testid="anatomy-empty">no event in scope · every member is excluded on the source block</div>}
          </div>
        </SectionCard>

        {/* ------------------------------------------------ rose / overlay ------------------------------------------------ */}
        {large ? (
          <SectionCard testid="overlaid-card" title="Events overlaid"
            info="Families run to hundreds of members, so the overlay draws a seeded random sample (P8). The current event is always drawn, in blue."
            subtitle={<span className="mono">{sample.length} of {fmtInt(events.length)}</span>}
            actions={<>
              <Seg testid="overlay-view" value={viewQ} onChange={setView} options={[{ value: 'overlay', label: 'overlay' }, { value: 'rose', label: 'rose' }]} />
              <Button size="sm" icon="shuffle" onClick={() => setOverlaySeed(s => s + 101)} testid="overlay-resample">resample</Button>
              <Dropdown testid="sample-size" prefix="sample size" value={sampleQ} onChange={setSample} options={['5', '10', '20'].map(v => ({ value: v, label: v }))} />
            </>}>
            {viewQ === 'rose' && event
              ? <Rose events={events} selected={event.id} colourBy={colourQ} onSelect={pick} />
              : (
                <>
                  <LineChart testid="overlay-plot" height={230} yLabel="mV" xDomain={[t(-10), t(24)]} yDomain={yDomain}
                    xFormat={fmtT} legend={false}
                    series={[
                      ...sample.filter(e => e.id !== event?.id).map(e => ({ label: e.id, colour: '#9ca3af', points: clip(curveOf(e)).map(([a, b]) => [t(a), b] as [number, number]), width: 1 })),
                      ...(event ? [{ label: `event ${selectedIdx + 1}`, colour: 'var(--blue)', points: clip(curveOf(event)).map(([a, b]) => [t(a), b] as [number, number]), width: 2 }] : []),
                    ]} />
                  <div className="ig-foot" style={{ marginTop: 4 }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><span style={{ width: 14, height: 2, background: 'var(--blue)' }} />current event {selectedIdx + 1} · drawn if in sample, else added</span>
                    <span className="k-spacer" /><span>seed {overlaySeed}</span>
                  </div>
                </>
              )}
          </SectionCard>
        ) : (
          <SectionCard testid="rose-card" title="Each fall as one angle"
            info={`Every fall becomes one angle: the arctangent of its steepest slope in ${unitLabel}. −45° is −${refSlope} mV/s. The radius is the event's order in the run, so the rose is not a density.`}
            actions={<Dropdown testid="rose-colour" prefix="colour" value={colourQ} onChange={setColour}
              options={[{ value: 'depth', label: 'depth' }, { value: 'recording', label: 'recording' }, { value: 'verdict', label: 'verdict' }]} />}>
            <div className="ig-foot" style={{ marginBottom: 6 }}>angle of max slope in {unitLabel} · −45° = −{refSlope} mV/s · radius = event order</div>
            <Rose events={events} selected={event?.id ?? null} colourBy={colourQ} onSelect={pick} />
          </SectionCard>
        )}
      </div>

      {/* ------------------------------------------------ rules ------------------------------------------------ */}
      <SectionCard testid="rules-card" title="Rules" style={pending != null ? { borderColor: 'var(--amber)' } : undefined}
        info="Three rules turn a span into numbers: where the fall starts, where it ends, and over how many samples the slope is measured. Everything on this page is downstream of them."
        subtitle={storeRules ? 'the store\'s numbers were measured with the rules listed below; the selectors are a preview and do not recompute (the seed store is fixed until Prompt 05 wires a real re-run)' : 'these three rules define every number on this page'}
        actions={pending != null
          ? <>
            <span className="ig-amber-text ig-small mono" data-testid="rules-preview"><Icon name="alert-triangle" size={11} /> {STALE_PREVIEW}</span>
            <Button size="sm" onClick={discard} disabled={sim.busy} disabledReason={BUSY} testid="rules-discard">discard</Button>
          </>
          : flagged.length
            ? <span className="ig-amber-text ig-small mono" data-testid="rules-flagged"><Icon name="alert-triangle" size={11} /> {flagged.length} event{flagged.length === 1 ? '' : 's'} flagged · two troughs within window</span>
            : <span className="ig-foot" data-testid="rules-clean">no event flagged</span>}>
        {storeRules && <ul className="ig-small mono" data-testid="rules-live" style={{ margin: '0 0 8px', paddingLeft: 18 }}>{storeRules.map((r: { name: string; rule: string }) => <li key={r.name}><b>{r.name}</b> · {r.rule}</li>)}</ul>}
        <div className="ig-rules">
          <div>
            <div className="lb">onset rule <InfoTip title="Onset rule">Where the fall is taken to start. "Walk back from steepest while descending" is the recommended rule (Settings › Recommended values).</InfoTip></div>
            <Dropdown block testid="rule-onset" disabled={sim.busy} disabledReason={BUSY} value={draft.rules.onset} onChange={v => { setDraft(d => ({ ...d, rules: { ...d.rules, onset: v }, staleFrom: 'block1' })) }} options={RULES.onset} />
          </div>
          <div>
            <div className="lb">trough rule <InfoTip title="Trough rule">Where the fall is taken to end. A run of samples above the noise band avoids stopping on a single noisy sample.</InfoTip></div>
            <Dropdown block testid="rule-trough" disabled={sim.busy} disabledReason={BUSY} value={draft.rules.trough} onChange={v => { setDraft(d => ({ ...d, rules: { ...d.rules, trough: v }, staleFrom: 'block1' })) }} options={RULES.trough} />
          </div>
          <div>
            <div className="lb">steepest window <InfoTip title="Steepest window">The slope is the steepest difference over this many consecutive samples. Wider windows are less noisy and shallower.</InfoTip></div>
            <div className="ig-row">
              <Slider testid="rule-window" disabled={sim.busy} disabledReason={BUSY} value={showWindow} min={RULES.steepestWindow.min} max={RULES.steepestWindow.max} step={RULES.steepestWindow.step}
                onChange={v => setDraft(d => ({ ...d, pendingWindow: v === d.rules.steepestWindow ? null : v, staleFrom: v === d.rules.steepestWindow ? d.staleFrom : 'block1' }))}
                format={v => `${v} samples`} ariaLabel="steepest window" width={150} />
              {pending != null && <span className="ig-muted ig-small mono" data-testid="window-was">(was {appliedWindow})</span>}
            </div>
          </div>
          <div>
            <div className="lb">slope noise σ <InfoTip title="Slope noise σ">The dispersion the trough rule compares against. MAD is robust to the fall itself.</InfoTip></div>
            <Dropdown block testid="rule-sigma" disabled={sim.busy} disabledReason={BUSY} value={draft.rules.sigma} onChange={v => setDraft(d => ({ ...d, rules: { ...d.rules, sigma: v }, staleFrom: 'block1' }))} options={RULES.sigma} />
          </div>
        </div>
      </SectionCard>

      {/* ------------------------------------------------ per-event output ------------------------------------------------ */}
      <SectionCard testid="per-event-table" title="Per-event output"
        info="One row per member. These are the Features the block declares, so 02 Aggregate can wire its plots to them without knowing what this block is."
        subtitle="one row per member → derived features (span, recipe_hash)"
        actions={<>
          <span className="ig-foot">{fmtInt(events.length)} rows</span>
          <Button size="sm" icon="download" onClick={() => notWired(`export ${events.length} per-event rows as CSV`)} testid="events-csv">CSV</Button>
        </>}>
        <Table rows={tableRows} rowKey={r => r.id} columns={columns} selection="multi" selected={sel} onSelectionChange={setSel}
          highlighted={event?.id ?? null} onRowClick={r => pick(r.id)} sort={tableSort} onSortChange={setTableSort} testid="events-table"
          rowTone={r => (r.flags.length ? 'amber' : undefined)} dense
          empty={<span>no events in scope · every member is excluded on the source block</span>} />
        <div className="ig-row" style={{ marginTop: 6 }}>
          <span className="ig-foot">click a row to open it above</span>
          <span className="k-spacer" />
          <IconButton icon="chevron-left" label="previous rows" testid="table-prev" disabled={tablePage <= 1} disabledReason="at the first rows" onClick={() => setTablePage(p => p - 1)} />
          <span className="ig-foot">{tableFrom + 1}–{Math.min(tableFrom + TABLE_PAGE, events.length)} of {fmtInt(events.length)}</span>
          <IconButton icon="chevron-right" label="next rows" testid="table-next" disabled={tableFrom + TABLE_PAGE >= events.length} disabledReason="at the last rows" onClick={() => setTablePage(p => p + 1)} />
        </div>
      </SectionCard>

      <div className="ig-row">
        <Badge status={stale ? 'stale' : 'cached'} />
        <span className="ig-foot">
          declares {block.upstream.features.map(f => f.label).join(' · ')} — 02 Aggregate is wired from this list (P7)
        </span>
        <span className="k-spacer" />
        <Button variant="link" icon="arrow-right" onClick={() => navigate(`analyse/interrogation/block/2${upstream === 'slope' ? '' : '?upstream=spike-shape'}`)} testid="to-aggregate">02 Aggregate →</Button>
      </div>

      <SaveTemplateModal open={saveOpen} onClose={() => setSaveOpen(false)}
        defaultName={upstream === 'spike-shape' ? 'spike_shape_v1' : 'sharkfin_slope_v1'}
        stages={block.chain.map(b => (b.index ? `${String(b.index).padStart(2, '0')} ${b.label}` : b.label))} />
    </>
  )
}
