/* analyse.interrogation.slope — 01 Resolve spans (frames interrogation-2, 2b, 2c).
 * §6.8 `SpanSet → SpanSet + Features`: the anatomy of one event with the rules that define every number,
 * a per-event table, a sliding strip (P8) and — for a large family — a sampled overlay. */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Badge, Button, Callout, Chip, ColourDot, Dropdown, Icon, IconButton, InfoTip, LineChart, MiniTrace, Page, Rose, Seg, SectionCard,
  Slider, Table, fmtInt, recordDemoWrite, useNotWired, useQueryState, useSim, type BadgeStatus, type Column, type SortState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { eventWindow, getSlopeBlock, liveEventPoints, liveYDomain, paddingLabel, windowOver, type SlopeBlock } from '../api/interrogation'
import { measuredDomain } from '../charts/domain'
import {
  FAMILY_Y_DOMAIN, MARKS, RULES, RUN_STEPS, STALE_PREVIEW, UNITS, UPSTREAMS, VERDICT_COLOUR,
  eventCurve, unitScale, type InterrogationMember,
} from '../fixtures/interrogation'
import { AddStagePopover, ChainCard, InterrogationToolbar, LoadFailed, Loading, RunVeil, SaveTemplateModal } from './chrome'
import { SourcePicker } from './SourcePicker'
import { inScopeIds, interrogationHref, markSimForced, useFamilyQuery, useInterrogationDraft, useUpstreamQuery, wasSimForced } from './draft'
import { fmtMeasure } from './features'

const STRIP = 10
const TABLE_PAGE = 4
/** Why a parameter control is dead while the chain runs (the shared convention). */
const BUSY = 'wait for the run'
/** Why the four rule selectors are dead on a live family (fixup-e, symptom I4): the seed store's numbers were
 *  measured with the rules printed above them, and no re-run exists yet that could apply different ones. A
 *  selector that changed nothing but a caption claimed otherwise. */
const FIXED_RULES = "the seed store's rules are fixed · the numbers on this page were measured with the rules listed above; nothing here re-runs them yet"
/** How far the drawn tangent reaches either side of the steepest sample, as a fraction of the fall — and never
 *  less than one sample. The slope itself is a central difference AT that sample; the line is only long enough
 *  to read, the reach the researcher's own anatomy figure uses (Pipelines/drop_motifs/casestudy9.py). */
const TANGENT_REACH = 0.16
const finite = (v: number | null | undefined): v is number => v != null && Number.isFinite(v)
/** Clip a synthetic (fixture) curve to the plotted window so a long recovery never draws past the axis. */
const clip = (vs: number[], pre = 10, hi = 24) => vs.map((v, i) => [i - pre, v] as [number, number]).filter(pt => pt[0] <= hi)

const ROSE_PALETTE = ['#2F6FED', '#E8900C', '#7446E0', '#1E6F7A', '#C97B63', '#059669']

export function SlopePage() {
  const [familyId] = useFamilyQuery()
  const [upstream] = useUpstreamQuery()
  const block = useSourced(() => getSlopeBlock(familyId, upstream), [familyId, upstream])
  const b = block.data
  return (
    <>
      <Header workspace="Analyse" page={b?.upstream.block ?? '01 Resolve spans'} search="Search spans, runs, families" demo={block.source === 'demo'}
        subtitle={b ? `${upstream === 'slope' ? 'slope analysis' : 'per-event measures · interrogation.event_shape'} · ${b.family.id} ${b.family.name}` : 'slope analysis'} />
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

  /* live members carry their stored snippet: draw that; fixtures keep the synthetic curve. The window around
     every event follows Source settings › context padding (fixup-e, U11): the stored context by default, so a
     slow precursor to a fast event is on the plot rather than off its left edge. */
  const padding = draft.settings.padding
  const win = useMemo(() => windowOver(events, padding), [events, padding])
  /* a strip thumbnail is the event's stored samples at their own times (fixup-h: it used to be the snippet
     resampled to one value per second by interpolation); a fixture member with no snippet keeps its synthetic curve */
  const stripTrace = (m: InterrogationMember): { values: number[]; t?: number[] } => {
    const pts = liveEventPoints(m, win.pre, win.post)
    return pts && pts.length > 1 ? { values: pts.map(q => q[1]), t: pts.map(q => q[0]) } : { values: eventCurve(m, Math.min(win.pre, 10), Math.min(win.post, 24)) }
  }
  /* the angle of an event is the core's (`gradients.rose_data`, served per member); the page derives none */
  const fmtAngle = (m: InterrogationMember, digits = 1) => (m.angle_deg == null ? '—' : `${m.angle_deg.toFixed(digits).replace('-', '−')}°`)
  const rose = block.rose
  const memberIndex = useMemo(() => new Map(block.members.map((m, i) => [m.id, i])), [block.members])
  const depths = events.map(e => e.depth_mV)
  const dLo = Math.min(...depths), dHi = Math.max(...depths)
  const recordings = [...new Set(block.members.map(e => e.recording))]
  const roseColour = (i: number): string => {
    const e = block.members[i]
    if (!e) return 'var(--blue)'
    if (colourQ === 'recording') return ROSE_PALETTE[recordings.indexOf(e.recording) % ROSE_PALETTE.length]
    if (colourQ === 'verdict') return VERDICT_COLOUR[e.verdict]
    const u01 = dHi > dLo ? (e.depth_mV - dLo) / (dHi - dLo) : 0.5
    return `rgb(${Math.round(88 + (232 - 88) * u01)}, ${Math.round(86 + (144 - 86) * u01)}, ${Math.round(214 + (12 - 214) * u01)})`
  }
  const roseLegend = colourQ === 'depth' ? `dot colour = depth, ${dLo.toFixed(2)} (violet) to ${dHi.toFixed(2)} mV (amber)` : colourQ === 'recording' ? `dot colour = recording: ${recordings.join(', ')}` : 'dot colour = verdict'
  const theRose = (
    <Rose rose={rose} testid="rose" highlight={event ? memberIndex.get(event.id) ?? null : null} colourOf={roseColour} legend={roseLegend}
      labelOf={i => block.members[i]?.id ?? `event ${i + 1}`} onSelect={i => { const m = block.members[i]; if (m) pick(m.id) }} />
  )
  const storeRules = block.storeRules
  const href = (page: 'source' | 'block1' | 'block2', extra?: Record<string, string | null | undefined>) => interrogationHref(page, familyId, upstream, extra)
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

  /* ---- the anatomy figure (fixup-k) ----
     The trace is the event's stored samples inside the context-padding window (Source settings), and every mark
     on it is the store's: the detector's onset and trough samples, the sample `gradients.fall_gradients` found
     steepest, and the snippet's own height at each (GET …/families/{key}/slope). Nothing is placed by a constant.
     A mark the store did not measure is NOT drawn, and `absent` names it on the face of the card. */
  const uTime = unitScale(unitsQ).time
  const anatomy = useMemo(() => {
    if (!event) return null
    const w = eventWindow(event, padding)
    const raw = liveEventPoints(event, w.pre, w.post)
    if (!raw || raw.length < 2) return { trace: null, why: 'the store holds no snippet for this event, so there is no trace to draw and nothing to mark' } as const
    const sc = (xs: [number, number][]) => xs.map(([x, y]) => [+(x * uTime).toFixed(3), y] as [number, number])
    const yDomain = measuredDomain(raw.map(p => p[1])) ?? FAMILY_Y_DOMAIN
    const a = event.anatomy
    const absent: string[] = []
    const fall = a && a.trough_s > 0 && finite(a.onset_mV) && finite(a.trough_mV)
      ? { trough_s: a.trough_s, onset_mV: a.onset_mV, trough_mV: a.trough_mV } : null
    const steep = a && finite(a.steepest_s) && finite(a.steepest_mV) && Number.isFinite(event.max_slope)
      ? { s: a.steepest_s, mV: a.steepest_mV } : null
    if (!a) absent.push('trough, steepest, chord, tangent and depth · the store served no slope measurement for this event')
    else {
      if (!fall) absent.push("trough, chord and depth · the store's trough is not after its onset, so there is no fall between the marks")
      if (!steep) absent.push('steepest and its tangent · no steepest sample was measured')
    }
    /* the tangent: through the steepest sample at the measured slope. Each end is shortened (never bent) where
       it would leave the trace's own y range, so the plot's domain is still measured from the trace alone — on
       a sharkfin the steepest sample is at the top of the trace and the line runs mostly forward from it */
    let tangent: [number, number][] | null = null
    if (a && steep) {
      const reach = Math.max(TANGENT_REACH * (fall?.trough_s ?? 0), a.sample_s)
      const k = Math.abs(event.max_slope)
      const above = Math.max(0, yDomain[1] - steep.mV), below = Math.max(0, steep.mV - yDomain[0])
      const end = (room: number) => (k * reach > room ? room / k : reach)
      const before = end(event.max_slope < 0 ? above : below), after = end(event.max_slope < 0 ? below : above)
      tangent = sc([[steep.s - before, steep.mV - event.max_slope * before], [steep.s + after, steep.mV + event.max_slope * after]])
    }
    /* marker labels: marks closer than 8 % of the plotted window share one label at the first of them, so two
       names are never printed on top of each other (the lines themselves are still drawn where they are) */
    const span = (event.duration_s + w.post + w.pre) * uTime
    const named: { x: number; label: string; colour: string }[] = []
    for (const m of [
      { x: 0, label: 'onset', colour: 'var(--blue)' },
      ...(steep ? [{ x: +(steep.s * uTime).toFixed(3), label: 'steepest', colour: '#7446E0' }] : []),
      ...(fall ? [{ x: +(fall.trough_s * uTime).toFixed(3), label: 'trough', colour: 'var(--red)' }] : []),
    ].sort((p, q) => p.x - q.x)) {
      const host = [...named].reverse().find(n => n.label)
      if (host && m.x - host.x < 0.08 * span) { host.label += ` · ${m.label}`; named.push({ ...m, label: '' }) }
      else named.push(m)
    }
    return {
      trace: sc(raw), yDomain, absent, window: w, nDrawn: raw.length, nStored: event.snippet?.n ?? null,
      dom: [+(-w.pre * uTime).toFixed(3), +((event.duration_s + w.post) * uTime).toFixed(3)] as [number, number],
      /* seconds from the onset, real (unscaled), for the readout */
      steepest_s: steep?.s ?? null, trough_s: fall?.trough_s ?? null,
      markers: named,
      chord: fall ? sc([[0, fall.onset_mV], [fall.trough_s, fall.trough_mV]]) : null,
      tangent,
      depthLine: fall ? sc([[fall.trough_s, fall.onset_mV], [fall.trough_s, fall.trough_mV]]) : null,
    } as const
  }, [event, padding, uTime])

  /* ---- units (fix r1: the control used to rewrite a caption and recompute nothing) ----
     `mV · s` is the frame's compressed convention: every time divides by 10 and every slope multiplies
     by 10. The angle is the same under either, because the slope and the −45° reference scale together. */
  const unitLabel = UNITS.find(o => o.value === unitsQ)?.label ?? 'mV · 10 s'
  const u = unitScale(unitsQ)
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
  /* THE plot-domain rule (charts/domain.ts): each card's y is measured from what that card draws */
  const drawnOverlay = useMemo(() => (event && !sample.some(e => e.id === event.id) ? [...sample, event] : sample), [sample, event])
  const overlayDomain = useMemo(() => liveYDomain(drawnOverlay) ?? FAMILY_Y_DOMAIN, [drawnOverlay])
  const stripDomain = useMemo(() => liveYDomain(strip) ?? FAMILY_Y_DOMAIN, [strip])
  /** a member's stored samples inside the shared window, in the plotted unit; a fixture member's synthetic curve */
  const overlayPoints = (m: InterrogationMember): [number, number][] =>
    (liveEventPoints(m, win.pre, win.post) ?? clip(eventCurve(m, 10, 24), 10, 24)).map(([a, b]) => [t(a), b] as [number, number])

  /* ---- table ----
     Recovery is the core's (fixup-e): null = not recovered inside the rule's bound, printed as such, never 0.
     Under Event shape the columns are that block's measures (FWHM, rise time — null for a drop — duration). */
  const notMeasured = (why: string) => <span className="ig-amber-text" title={why}>—</span>
  const shapeCols: Column<InterrogationMember>[] = upstream === 'event-shape' ? [
    { key: 'fwhm', header: 'FWHM s', align: 'right', render: r => r.measures?.fwhm_s == null ? notMeasured('no full width at half maximum: the half level was not re-crossed inside the bound') : fmtSec(r.measures.fwhm_s), sortValue: r => r.measures?.fwhm_s ?? null },
    { key: 'rise', header: 'rise s', align: 'right', render: r => r.measures?.rise_time_s == null ? notMeasured('a drop has no rise (null, not 0 — Q19)') : fmtSec(r.measures.rise_time_s), sortValue: r => r.measures?.rise_time_s ?? null },
    { key: 'edur', header: 'onset→recovery s', align: 'right', render: r => r.measures?.event_duration_s == null ? notMeasured('not recovered, so no duration') : fmtSec(r.measures.event_duration_s), sortValue: r => r.measures?.event_duration_s ?? null },
  ] : []
  const columns: Column<InterrogationMember>[] = [
    { key: 'id', header: 'span', render: r => <span className="primary-text">{r.id}</span>, sortValue: r => r.id },
    { key: 'recording', header: 'recording', sortValue: r => r.recording },
    { key: 'channel', header: 'ch', sortValue: r => r.channel },
    { key: 'onset', header: 'onset h', align: 'right', render: r => r.onset_h.toFixed(2), sortValue: r => r.onset_h },
    { key: 'depth', header: upstream === 'event-shape' ? 'amplitude mV' : 'depth mV', align: 'right',
      render: r => upstream === 'event-shape' ? fmtMeasure(r.measures?.amplitude_mV, 3) : r.depth_mV.toFixed(3), sortValue: r => upstream === 'event-shape' ? r.measures?.amplitude_mV ?? null : r.depth_mV },
    { key: 'slope', header: 'max slope mV/s', align: 'right', render: r => fmtSlope(upstream === 'event-shape' ? r.measures?.max_slope ?? r.max_slope : r.max_slope), sortValue: r => upstream === 'event-shape' ? r.measures?.max_slope ?? null : r.max_slope },
    { key: 'angle', header: 'angle', align: 'right', render: r => fmtAngle(r, 0), sortValue: r => r.angle_deg ?? 0 },
    { key: 'peak', header: 'peakedness', align: 'right', render: r => upstream === 'event-shape' ? fmtMeasure(r.measures?.peakedness) : r.peakedness.toFixed(2), sortValue: r => upstream === 'event-shape' ? r.measures?.peakedness ?? null : r.peakedness },
    { key: 'duration', header: upstream === 'event-shape' ? 'width s' : 'duration s', align: 'right', render: r => fmtSec(r.duration_s), sortValue: r => r.duration_s },
    ...shapeCols,
    { key: 'recovery', header: 'recovery s', align: 'right',
      render: r => r.recovery_s == null ? <span className="ig-amber-text" title="did not return to half the amplitude within 10 event widths, or before the next event — not measured, not 0 s" data-testid="not-recovered">not recovered</span> : fmtSec(r.recovery_s),
      sortValue: r => r.recovery_s ?? null },
    { key: 'flags', header: 'flags', render: r => r.flags.length ? <span className="ig-amber-text"><Icon name="alert-triangle" size={11} /> {r.flags.join(' · ')}</span> : null },
  ]
  const nNotRecovered = events.filter(e => e.recovery_s == null).length
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
        onSelect={id => navigate(id === 'source' ? href('source') : id === 'block2' ? href('block2') : href('block1'))} />
      <AddStagePopover open={popover === 'stage'} onClose={() => setPopover(null)} anchorRef={sourceRef}
        onPick={kind => { navigate(interrogationHref('block1', familyId, kind)); push({ text: `01 is now ${UPSTREAMS[kind].block}` }) }} />

      <div className={large ? 'ig-cols even' : 'ig-cols wide-right'}>
        {/* ------------------------------------------------ anatomy ------------------------------------------------ */}
        <SectionCard testid="anatomy-card" number="01" title={block.upstream.blockTitle}
          info="One event at a time, with the store's own marks drawn on it: the detector's onset and trough samples and the steepest sample between them. Every number on this page is measured from those three."
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
                {anatomy.trace ? (
                  <div data-testid="anatomy-figure" data-family={fam.id} data-event={event.id}>
                    <LineChart testid="anatomy-plot" height={210} yLabel="mV" xDomain={anatomy.dom} yDomain={anatomy.yDomain}
                      xFormat={fmtT} legend={false}
                      markers={showMarks ? anatomy.markers.map(m => ({ x: m.x, colour: m.colour, ...(m.label ? { label: m.label } : {}) })) : []}
                      series={[
                        { label: 'event', colour: '#111827', points: anatomy.trace, width: 1.6 },
                        ...(showMarks && anatomy.chord ? [{ label: 'chord', colour: '#9ca3af', points: anatomy.chord, dashed: true, width: 1.2 }] : []),
                        ...(showMarks && anatomy.tangent ? [{ label: 'steepest slope', colour: '#7446E0', points: anatomy.tangent, width: 1.8 }] : []),
                        ...(showMarks && anatomy.depthLine ? [{ label: 'depth', colour: 'var(--green)', points: anatomy.depthLine, width: 2.4 }] : []),
                      ]} />
                  </div>
                ) : <Callout tone="amber" icon="alert-triangle" testid="anatomy-no-trace">{anatomy.why}</Callout>}
                <div className="ig-row" style={{ marginTop: 4 }}>
                  <span className="ig-foot" data-testid="mark-legend">
                    <span><ColourDot colour="var(--blue)" /> onset</span>
                    <span><ColourDot colour="#7446E0" /> steepest</span>
                    <span><ColourDot colour="var(--red)" /> trough</span>
                    <span><span style={{ display: 'inline-block', width: 3, height: 10, background: 'var(--green)', verticalAlign: 'middle' }} /> depth</span>
                    <span><span style={{ display: 'inline-block', width: 14, height: 1, background: '#9ca3af', verticalAlign: 'middle' }} /> chord</span>
                    <InfoTip title="Where the marks come from" testid="marks-info">
                      Every mark is the store's measurement, drawn at the sample it was measured at — none is placed by the page.
                      <ul style={{ margin: '6px 0', paddingLeft: 16 }}>
                        {(storeRules ?? []).map((r: { name: string; rule: string }) => <li key={r.name}><b>{r.name}</b> · {r.rule}</li>)}
                        <li><b>depth</b> · from the trace at the onset down to the trace at the trough, drawn at the trough</li>
                      </ul>
                      The tangent passes through the steepest sample at the measured slope ({fmtSlope(event.max_slope)} mV/s). It is drawn up to {TANGENT_REACH * 100} % of the fall either side (at least one sample; an end is cut short where it would leave the plot) so it can be read; the slope itself is the difference one sample either side.
                      {anatomy.trace && anatomy.nStored != null && anatomy.nStored > (event.snippet?.t_s.length ?? 0) && <> The trace is {fmtInt(event.snippet?.t_s.length ?? 0)} of the {fmtInt(anatomy.nStored)} stored samples; the marks sit at the full-resolution samples, so one can stand a little off the drawn line.</>}
                    </InfoTip>
                  </span>
                  <span className="k-spacer" />
                  {event.flags.length
                    ? <Chip tone="amber" icon="alert-triangle" testid="rules-verdict">{event.flags.join(' · ')}</Chip>
                    : <Chip tone="green" icon="check" testid="rules-verdict">rules resolved cleanly</Chip>}
                </div>
                {anatomy.trace && showMarks && (anatomy.absent.length > 0 || allMarks) && (
                  <div className="ig-foot ig-amber-text" style={{ marginTop: 4 }} data-testid="anatomy-absent">
                    <span><Icon name="alert-triangle" size={11} /> not drawn: {[...anatomy.absent, ...(allMarks ? ['baseline band · the store serves no noise band for an event, so there is none to draw'] : [])].join(' ; ')}</span>
                  </div>
                )}
                {anatomy.trace && (
                  <div className="ig-foot" style={{ marginTop: 2 }} data-testid="anatomy-window-note" data-padding={padding}>
                    <span><Icon name="info" size={11} /> window {fmtT(t(-anatomy.window.pre))} … {fmtT(t(event.duration_s + anatomy.window.post))} from onset · context padding {paddingLabel(padding)} (Source settings) · the stored samples · y measured from the trace drawn</span>
                  </div>
                )}

                <div className="ig-readout" style={{ marginTop: 8 }} data-testid="event-readout">
                  <span>event <b>{event.id}</b> · {event.channel} · {event.onset_h.toFixed(2)} h</span>
                  <span>depth <b>{event.depth_mV.toFixed(3)} mV</b></span>
                  <span>duration <b>{fmtSec(event.duration_s)} s</b></span>
                  <span>recovery <b data-testid="readout-recovery">{event.recovery_s == null ? 'not recovered' : `${fmtSec(event.recovery_s)} s`}</b></span>
                  {upstream === 'event-shape' && <span>FWHM <b>{event.measures?.fwhm_s == null ? '—' : `${fmtSec(event.measures.fwhm_s)} s`}</b></span>}
                  {upstream === 'event-shape' && <span>rise <b>{event.measures?.rise_time_s == null ? '— (a drop has no rise)' : `${fmtSec(event.measures.rise_time_s)} s`}</b></span>}
                  <span>max slope <b>{fmtSlope(event.max_slope)} mV/s</b></span>
                  <span>steepest at <b data-testid="readout-steepest">{anatomy.trace && anatomy.steepest_s != null
                    ? `${fmtT(t(anatomy.steepest_s))}${anatomy.trough_s ? ` · ${Math.round(100 * anatomy.steepest_s / anatomy.trough_s)} % of the fall` : ''}`
                    : 'not measured'}</b></span>
                  <span>angle <b>{fmtAngle(event)}</b></span>
                  <span>peakedness <b>{event.peakedness.toFixed(2)}</b></span>
                </div>
                <div className="ig-foot" style={{ marginTop: 4 }} data-testid="units-note">
                  units {unitLabel} · {u.note} · the angle is the core's: {rose.caption || 'arctan of the steepest slope over the stated reference'}
                </div>

                <div className="ig-strip" style={{ marginTop: 10 }} data-testid="event-strip">
                  <IconButton icon="chevron-left" label="previous ten events" testid="strip-prev" bordered
                    disabled={stripPage <= 1} disabledReason="at the first event" onClick={() => setStripPage(s => Math.max(1, s - 1))} />
                  <div className="cells">
                    {strip.map((e, i) => (
                      <button key={e.id} type="button" className={`ig-cell ${e.id === event.id ? 'on' : ''}`} onClick={() => pick(e.id)}
                        data-testid={`strip-${stripFrom + i + 1}`} title={`${e.id} · ${e.depth_mV.toFixed(3)} mV`}>
                        <MiniTrace {...stripTrace(e)} yDomain={stripDomain} width="100%" height={40} ground="none"
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
              ? theRose
              : (
                <>
                  <LineChart testid="overlay-plot" height={340} yLabel="mV" xDomain={[t(-win.pre), t(win.post)]} yDomain={overlayDomain}
                    xFormat={fmtT} legend={false}
                    series={[
                      ...sample.filter(e => e.id !== event?.id).map(e => ({ label: e.id, colour: '#9ca3af', points: overlayPoints(e), width: 1 })),
                      ...(event ? [{ label: `event ${selectedIdx + 1}`, colour: 'var(--blue)', points: overlayPoints(event), width: 2 }] : []),
                    ]} />
                  <div className="ig-foot" style={{ marginTop: 4 }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><span style={{ width: 14, height: 2, background: 'var(--blue)' }} />current event {selectedIdx + 1} · drawn if in sample, else added</span>
                    <span className="k-spacer" /><span>seed {overlaySeed}</span>
                  </div>
                  <div className="ig-foot" style={{ marginTop: 2 }} data-testid="overlay-window-note">
                    <Icon name="info" size={11} /> window {fmtT(t(-win.pre))} … {fmtT(t(win.post))} from onset · context padding {paddingLabel(padding)} (Source settings) · the stored samples, nothing held past a snippet's end · y measured from the traces drawn
                  </div>
                </>
              )}
          </SectionCard>
        ) : (
          <SectionCard testid="rose-card" title="Each fall as one angle"
            info="Every fall becomes one angle: the arctangent of its steepest slope over a stated reference. The angles, the 18 bins and the circular statistics are the core's (gradients.rose_data) — the page draws them and derives none. A wedge's length is the number of events in its bin; each event is a dot at its own angle."
            actions={<Dropdown testid="rose-colour" prefix="colour" value={colourQ} onChange={setColour}
              options={[{ value: 'depth', label: 'depth' }, { value: 'recording', label: 'recording' }, { value: 'verdict', label: 'verdict' }]} />}>
            {theRose}
          </SectionCard>
        )}
      </div>

      {/* ------------------------------------------------ rules ------------------------------------------------ */}
      <SectionCard testid="rules-card" title="Rules" style={pending != null ? { borderColor: 'var(--amber)' } : undefined}
        info="Three rules turn a span into numbers: where the fall starts, where it ends, and over how many samples the slope is measured. Everything on this page is downstream of them."
        subtitle={storeRules ? 'the store\'s numbers were measured with the rules listed below; the selectors are disabled: nothing on this page re-runs them yet (I4)' : 'these three rules define every number on this page'}
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
            <Dropdown block testid="rule-onset" disabled={sim.busy || !!storeRules} disabledReason={storeRules ? FIXED_RULES : BUSY} value={draft.rules.onset} onChange={v => { setDraft(d => ({ ...d, rules: { ...d.rules, onset: v }, staleFrom: 'block1' })) }} options={RULES.onset} />
          </div>
          <div>
            <div className="lb">trough rule <InfoTip title="Trough rule">Where the fall is taken to end. A run of samples above the noise band avoids stopping on a single noisy sample.</InfoTip></div>
            <Dropdown block testid="rule-trough" disabled={sim.busy || !!storeRules} disabledReason={storeRules ? FIXED_RULES : BUSY} value={draft.rules.trough} onChange={v => { setDraft(d => ({ ...d, rules: { ...d.rules, trough: v }, staleFrom: 'block1' })) }} options={RULES.trough} />
          </div>
          <div>
            <div className="lb">steepest window <InfoTip title="Steepest window">The slope is the steepest difference over this many consecutive samples. Wider windows are less noisy and shallower.</InfoTip></div>
            <div className="ig-row">
              <Slider testid="rule-window" disabled={sim.busy || !!storeRules} disabledReason={storeRules ? FIXED_RULES : BUSY} value={showWindow} min={RULES.steepestWindow.min} max={RULES.steepestWindow.max} step={RULES.steepestWindow.step}
                onChange={v => setDraft(d => ({ ...d, pendingWindow: v === d.rules.steepestWindow ? null : v, staleFrom: v === d.rules.steepestWindow ? d.staleFrom : 'block1' }))}
                format={v => `${v} samples`} ariaLabel="steepest window" width={150} />
              {pending != null && <span className="ig-muted ig-small mono" data-testid="window-was">(was {appliedWindow})</span>}
            </div>
          </div>
          <div>
            <div className="lb">slope noise σ <InfoTip title="Slope noise σ">The dispersion the trough rule compares against. MAD is robust to the fall itself.</InfoTip></div>
            <Dropdown block testid="rule-sigma" disabled={sim.busy || !!storeRules} disabledReason={storeRules ? FIXED_RULES : BUSY} value={draft.rules.sigma} onChange={v => setDraft(d => ({ ...d, rules: { ...d.rules, sigma: v }, staleFrom: 'block1' }))} options={RULES.sigma} />
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
        {nNotRecovered > 0 && (
          <div className="ig-foot" style={{ marginBottom: 6 }} data-testid="table-not-recovered">
            <Icon name="alert-triangle" size={11} /> {nNotRecovered} of {events.length} events did not return to {block.shape.recovery.frac * 100} % of their amplitude within {block.shape.recovery.max_mult} event widths (or before the next event) — their recovery is not measured, which is not 0 s
          </div>
        )}
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
        <span className="ig-foot" data-testid={`upstream-${upstream}`}>
          <b>{block.upstream.block}</b> declares {block.upstream.features.map(f => f.label).join(' · ')} — 02 Aggregate is wired from this list (P7)
        </span>
        <span className="k-spacer" />
        <Button variant="link" icon="arrow-right" onClick={() => navigate(href('block2'))} testid="to-aggregate">02 Aggregate →</Button>
      </div>

      <SaveTemplateModal open={saveOpen} onClose={() => setSaveOpen(false)}
        defaultName={upstream === 'event-shape' ? 'event_shape_v1' : 'sharkfin_slope_v1'}
        stages={block.chain.map(b => (b.index ? `${String(b.index).padStart(2, '0')} ${b.label}` : b.label))} />
    </>
  )
}
