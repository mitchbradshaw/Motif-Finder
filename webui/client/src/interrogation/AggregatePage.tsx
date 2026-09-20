/* analyse.interrogation.aggregate — 02 Aggregate (frames interrogation-3, 3b, 3c).
 * §6.8 `Features → views`, P7: the block is generic — every plot is wired from the Features the upstream
 * block declares, so the same page serves slope analysis and spike shape. P10: a null behind every plot.
 *
 * Fix round 1: the Parameters card and the feature wiring were decorative. Everything on both now
 * recomputes what it names — binning, the interval definition, outlier handling, the purity check, the
 * null method and every wiring slot — the null stays behind the bars when colour-by splits them, and a
 * family too small to fit says so instead of reprinting F-03's exponent. */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Badge, Button, Callout, Chip, ColourDot, Dropdown, EmptyState, Icon, InfoTip, Legend, LineChart,
  Page, Popover, SectionCard, Seg, StatRow, StatTile, binValues, fmtInt, recordDemoWrite, useNotWired,
  useQueryState, useSim, type BadgeStatus, type HistBin,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, setQuery } from '../state'
import { useSourced } from '../api/seam'
import { getAggregateBlock, type AggregateBlock } from '../api/interrogation'
import { FAMILY_COLOURS, seeded } from '../fixtures/canon'
import {
  INTERVAL_ENDS, MIN_FIT_N, NULL_GREY, RUN_STEPS, VERDICT_COLOUR, adjustedFit, binCount, percentile,
  type FitResult, type InterrogationMember, type PairSpec,
} from '../fixtures/interrogation'
import { AddStagePopover, ChainCard, InterrogationToolbar, LoadFailed, Loading, RunVeil, SaveTemplateModal } from './chrome'
import { NullHistogram, type HistSeries } from './NullHistogram'
import { SourcePicker } from './SourcePicker'
import { EventTimeline } from './EventTimeline'
import { inScopeIds, markSimForced, useFamilyQuery, useInterrogationDraft, useUpstreamQuery, wasSimForced } from './draft'

export function AggregatePage() {
  const [familyId] = useFamilyQuery()
  const [upstream] = useUpstreamQuery()
  const block = useSourced(() => getAggregateBlock(familyId, upstream), [familyId, upstream])
  const b = block.data
  return (
    <>
      <Header workspace="Analyse" page="02 Aggregate" search="Search spans, runs, families" demo={block.source === 'demo'}
        subtitle={b ? `${b.upstream.subtitle} · ${b.family.id} ${b.family.name}` : 'distributions and scaling'} />
      <Page testid="interrogation-aggregate">
        {block.error ? <LoadFailed what="02 Aggregate" error={block.error} onRetry={block.reload} />
          : !b ? <Loading what="the distributions" /> : <AggregateBody block={b} />}
      </Page>
    </>
  )
}

/* ------------------------------------------------------ feature access ------------------------------------------------------ */
/** One drawn value and the member it belongs to, so a colour-by split counts the same values the
 *  histogram bins (before the fix, per-category counts read a different feature from the bars). */
export interface FeatureRow { m: InterrogationMember; v: number }

/** Intervals are taken within a recording × channel — an interval across two recordings is not an
 *  interval — and belong to the later of the two events, which is what a colour-by splits them by. */
function intervalRows(members: InterrogationMember[], definition: string): FeatureRow[] {
  const ends = INTERVAL_ENDS[definition] ?? INTERVAL_ENDS['onset-onset']
  const groups = new Map<string, InterrogationMember[]>()
  for (const m of members) {
    const k = `${m.recording}/${m.channel}`
    groups.set(k, [...(groups.get(k) ?? []), m])
  }
  const out: FeatureRow[] = []
  for (const xs of groups.values()) {
    const s = [...xs].sort((a, b) => a.onset_h - b.onset_h)
    for (let i = 1; i < s.length; i++) out.push({ m: s[i], v: +(ends.to(s[i]) - ends.from(s[i - 1])).toFixed(4) })
  }
  return out
}

function featureOf(m: InterrogationMember, key: string): number {
  switch (key) {
    case 'depth_mV': case 'amplitude_mV': return m.depth_mV
    case 'duration_s': return m.duration_s
    case 'max_slope': return Math.abs(m.max_slope)
    case 'peakedness': return m.peakedness
    case 'recovery_s': case 'decay_s': return m.recovery_s
    case 'half_width_s': return +(m.duration_s * 0.84).toFixed(2)
    case 'rise_s': return +(m.duration_s * 0.31).toFixed(2)
    case 'isi_s': return +(m.duration_s * 4.2).toFixed(2)
    case 'onset_h': return m.onset_h
    default: return m.depth_mV
  }
}

/** A deterministic null sample for a feature. The two methods draw differently on purpose: matched
 *  random windows are wide and flat around the same centre; shuffled onsets keep the marginal spread
 *  but lose the timing, so an interval null is wider still. */
function nullSample(values: number[], key: string, method: string): number[] {
  if (!values.length) return []
  const shuffled = method === 'shuffled'
  const rnd = seeded(key.length * 977 + values.length + (shuffled ? 131 : 0))
  const lo = Math.min(...values), hi = Math.max(...values)
  const mid = (lo + hi) / 2, half = (hi - lo) / 2 || 0.1
  const spread = shuffled ? 2.0 : 1.5
  return Array.from({ length: Math.round(values.length * 1.6) }, () => +(mid + (rnd() + rnd() + rnd() - 1.5) * half * spread).toFixed(4))
}

/** Counts per bin, with the same edge rule `binValues` uses. */
function countsIn(rows: FeatureRow[], bars: HistBin[]): number[] {
  return bars.map((b, i) => rows.filter(r => r.v >= b.x0 && (i === bars.length - 1 ? r.v <= b.x1 : r.v < b.x1)).length)
}

function paddedDomain(values: number[]): [number, number] {
  if (!values.length) return [0, 1]
  const lo = Math.min(...values), hi = Math.max(...values)
  const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.1 || 1
  return [+(lo - pad).toFixed(4), +(hi + pad).toFixed(4)]
}

/* ------------------------------------------------------ body ------------------------------------------------------ */
function AggregateBody({ block }: { block: AggregateBlock }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [familyId, setFamilyId] = useFamilyQuery()
  const [upstream] = useUpstreamQuery()
  const [draft, setDraft] = useInterrogationDraft()
  const [popover, setPopover] = useQueryState('popover', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [colourQ, setColour] = useQueryState('colour', 'none')
  const [axesQ, setAxes] = useQueryState('axes', 'log-log')
  const [nullQ, setNull] = useQueryState('null', 'matched')
  const [binQ, setBin] = useQueryState('binning', 'fd')
  const [intervalQ, setInterval] = useQueryState('interval', 'onset-onset')
  const [outliersQ, setOutliers] = useQueryState('outliers', 'kept')
  const [purityQ, setPurity] = useQueryState('purity', 'one')
  const [wireQ, setWireQ] = useQueryState('wire', '')
  const [saveOpen, setSaveOpen] = useState(false)
  const sourceRef = useRef<HTMLButtonElement>(null)
  const customRef = useRef<HTMLButtonElement>(null)

  const fam = block.family
  const up = block.upstream
  const scope = inScopeIds(block.members, draft, fam.id, true)
  const events = useMemo(() => block.members.filter(m => scope.has(m.id)), [block.members, scope])
  const stale = !!draft.staleFrom || draft.pendingWindow != null

  /* ---- feature wiring (frame 3c) ----------------------------------------------------------------
     The slots live in the draft so they survive a walk to 01 and back, and mirror into `?wire=h3:peakedness`
     so every rewired state is a deep link as well as a click. Slot keys: h1–h3, tl, p1–p3. */
  const wiring = draft.wiring
  useEffect(() => {
    if (!wireQ) return
    const from = Object.fromEntries(wireQ.split(',').filter(Boolean).map(kv => kv.split(':') as [string, string]))
    if (JSON.stringify(from) !== JSON.stringify(draft.wiring)) setDraft(d => ({ ...d, wiring: from }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wireQ])
  const setWire = (slot: string, value: string) => {
    const next = { ...wiring, [slot]: value }
    setDraft(d => ({ ...d, wiring: next }))
    setWireQ(Object.entries(next).map(([k, v]) => `${k}:${v}`).join(',') || null)
  }
  const resetWiring = () => { setDraft(d => ({ ...d, wiring: {} })); setWireQ(null) }

  /* ---- the run ---- */
  const sim = useSim('analyse.interrogation.run')
  useEffect(() => {
    if (stateQ === 'running') { sim.force({ status: 'running', steps: RUN_STEPS, step: 2, fraction: 0.78, startedAt: Date.now() }); markSimForced(true) }
    else if (wasSimForced()) { sim.reset(); markSimForced(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])
  const runChain = () => {
    /* clear the forced-run flag first, or the `[stateQ]` effect resets the run we just started */
    markSimForced(false)
    setStateQ(null)
    sim.start({ steps: RUN_STEPS, stepMs: 700 })
    push({ text: `running ${RUN_STEPS.length} stages over ${fam.id} ${fam.name} (demo)` })
  }

  /* `?state=empty` forces the "nothing to aggregate" state; it is also reached for real when a family has
     fewer than 3 events in scope (a distribution needs more than two points). */
  const forcedEmpty = stateQ === 'empty' && !sim.busy && sim.status !== 'done'
  const status: Record<string, BadgeStatus> = {
    source: 'cached',
    block1: sim.status === 'running' && sim.step >= 1 ? 'running' : forcedEmpty ? 'new' : stale ? 'stale' : 'cached',
    block2: sim.status === 'running' && sim.step >= 2 ? 'running' : sim.busy ? 'new' : forcedEmpty ? 'new' : stale ? 'stale' : 'cached',
  }

  /* ---- colouring ---- */
  const categories = useMemo(() => {
    if (colourQ === 'recording') return [...new Set(events.map(e => e.recording))]
    if (colourQ === 'channel') return [...new Set(events.map(e => e.channel))]
    if (colourQ === 'verdict') return [...new Set(events.map(e => e.verdict))]
    return []
  }, [events, colourQ])
  const catOf = (m: InterrogationMember) => colourQ === 'recording' ? m.recording : colourQ === 'channel' ? m.channel : colourQ === 'verdict' ? m.verdict : ''
  const catColours = useMemo(() => {
    const out: Record<string, string> = {}
    categories.forEach((c, i) => {
      out[c] = colourQ === 'verdict' ? VERDICT_COLOUR[c as keyof typeof VERDICT_COLOUR] ?? 'var(--blue)'
        : [FAMILY_COLOURS['F-06'], '#E8900C', '#7446E0', '#1E6F7A', '#C97B63'][i % 5]
    })
    return out
  }, [categories, colourQ])
  const colourOf = (m: InterrogationMember) => (colourQ === 'none' ? 'var(--blue)' : catColours[catOf(m)] ?? 'var(--blue)')

  /* ---- what a value is, under the current interval definition ---- */
  const rowsFor = (key: string): FeatureRow[] =>
    key === 'interval_h' ? intervalRows(events, intervalQ) : events.map(m => ({ m, v: featureOf(m, key) }))

  /* Under MIN_FIT_N there are too few members for a null comparison to mean anything, so the recorded
     verdict is replaced rather than reprinted over a different n (§3: nothing claims more than it knows). */
  const tooFewForStats = events.length < MIN_FIT_N
  const nullLabel = nullQ === 'shuffled' ? 'shuffled onsets' : nullQ === 'none' ? 'no null' : 'matched windows'

  /* ---- three distributions ---- */
  const hists = up.hists.map((h, i) => {
    const key = wiring[`h${i + 1}`] ?? h.feature
    const rewired = key !== h.feature
    const spec = up.features.find(f => f.key === key)
    const rows = rowsFor(key)
    const values = rows.map(r => r.v)
    const domain: [number, number] = rewired || !values.length
      ? paddedDomain(values)
      : [Math.min(h.domain[0], ...values), Math.max(h.domain[1], ...values)]
    const nBins = binCount(values, binQ)
    const bars = binValues(values, domain, nBins)
    const nulls = nullQ === 'none' ? null : binValues(nullSample(values, key, nullQ), domain, nBins).map(b => b.count)
    const series: HistSeries[] = colourQ === 'none'
      ? [{ key: 'observed', label: 'observed', colour: h.colour, counts: countsIn(rows, bars) }]
      : categories.map(c => ({ key: c, label: c, colour: catColours[c], counts: countsIn(rows.filter(r => catOf(r.m) === c), bars) }))
    const median = values.length ? percentile(values, 0.5) : null
    const verdict = rewired
      ? `wired to ${spec?.label ?? key} · no recorded verdict for this feature`
      : tooFewForStats ? `n ${values.length} · too few to compare with the ${nullQ === 'none' ? 'null' : nullLabel}`
        : nullQ === 'none' ? 'no null · every interrogation result carries one (P10)'
          : nullQ === 'shuffled' ? h.verdictShuffled : h.verdict
    const tone = rewired || tooFewForStats || nullQ === 'none' ? 'amber' : nullQ === 'shuffled' ? h.verdictShuffledTone : h.verdictTone
    return {
      ...h, key, rewired, bars, nulls, series, values, median, verdict, tone,
      title: rewired ? (spec?.label ?? key) : h.title, unit: spec?.unit ?? h.unit, nBins,
    }
  })

  /* ---- the scaling pair ---- */
  const wiredPairs = useMemo(() => {
    const out: PairSpec[] = []
    up.pairs.forEach((p, i) => {
      const chosen = up.pairs.find(q => q.key === (wiring[`p${i + 1}`] ?? p.key)) ?? p
      if (!out.some(q => q.key === chosen.key)) out.push(chosen)
    })
    return out
  }, [up.pairs, wiring])
  const [pairQ, setPair] = useQueryState('pair', wiredPairs[0].key)
  const pair: PairSpec = wiredPairs.find(p => p.key === pairQ) ?? wiredPairs[0]
  const log = axesQ === 'log-log'
  const tx = (v: number) => (log ? Math.log10(Math.max(1e-6, v)) : v)
  const fmtAx = (v: number) => (log ? String(+Math.pow(10, v).toPrecision(2)) : formatShort(v))

  const pairPoints = useMemo(() => {
    if (pair.y === 'interval_h') return intervalRows(events, intervalQ).map(r => ({ m: r.m, x: featureOf(r.m, pair.x), y: r.v }))
    if (pair.x === 'interval_h') return intervalRows(events, intervalQ).map(r => ({ m: r.m, x: r.v, y: featureOf(r.m, pair.y) }))
    return events.map(e => ({ m: e, x: featureOf(e, pair.x), y: featureOf(e, pair.y) }))
  }, [events, pair, intervalQ])

  /* Outlier handling really removes or moves points, and the fit is recomputed from what is left. */
  const { used, dropped, note: outlierNote } = useMemo(() => {
    if (outliersQ === 'excluded') {
      const ys = pairPoints.map(p => p.y)
      const m = ys.reduce((a, b) => a + b, 0) / Math.max(1, ys.length)
      const sd = Math.sqrt(ys.reduce((s, y) => s + (y - m) ** 2, 0) / Math.max(1, ys.length)) || 1
      const out = pairPoints.filter(p => p.m.flags.length > 0 || Math.abs(p.y - m) / sd > 2)
      return { used: pairPoints.filter(p => !out.includes(p)), dropped: out, note: `${out.length} dropped · rule-flagged or |z| > 2` }
    }
    if (outliersQ === 'winsorised') {
      const xs = pairPoints.map(p => p.x), ys = pairPoints.map(p => p.y)
      const [xl, xh] = [percentile(xs, 0.05), percentile(xs, 0.95)]
      const [yl, yh] = [percentile(ys, 0.05), percentile(ys, 0.95)]
      const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
      return {
        used: pairPoints.map(p => ({ ...p, x: clamp(p.x, xl, xh), y: clamp(p.y, yl, yh) })),
        dropped: [] as typeof pairPoints, note: 'clamped at the 5th / 95th percentile',
      }
    }
    return { used: pairPoints, dropped: [] as typeof pairPoints, note: 'every point in the fit, flags kept' }
  }, [pairPoints, outliersQ])

  const fit: FitResult | null = useMemo(
    () => adjustedFit(pair, pairPoints.map(p => ({ x: p.x, y: p.y })), used.map(p => ({ x: p.x, y: p.y }))),
    [pair, pairPoints, used],
  )
  const nullFit = nullQ === 'shuffled' ? pair.nullShuffled : { beta: pair.nullBeta, ci: pair.nullCi }

  const nullPoints = useMemo(() => {
    if (nullQ === 'none') return []
    const rnd = seeded(pair.key.length * 31 + events.length + (nullQ === 'shuffled' ? 7 : 0))
    const spread = nullQ === 'shuffled' ? 1.1 : 0.8
    return used.flatMap(p => Array.from({ length: 3 }, () => ({
      x: p.x * (0.7 + rnd() * spread), y: p.y * (0.55 + rnd() * (spread + 0.1)),
    })))
  }, [used, pair.key, events.length, nullQ])

  const fitLine = useMemo(() => {
    if (!fit || !used.length) return [] as [number, number][]
    const xs = used.map(p => tx(p.x)), ys = used.map(p => tx(p.y))
    const x0 = Math.min(...xs), x1 = Math.max(...xs)
    const my = ys.reduce((a, b) => a + b, 0) / ys.length, mx = xs.reduce((a, b) => a + b, 0) / xs.length
    const b = log ? fit.beta : (Math.max(...ys) - Math.min(...ys)) / Math.max(1e-6, x1 - x0)
    return [[x0, my + b * (x0 - mx)], [x1, my + b * (x1 - mx)]] as [number, number][]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [used, fit, log])

  const catSeries = colourQ === 'none'
    ? [{ label: 'event', colour: 'var(--blue)', points: used.map(p => [tx(p.x), tx(p.y)] as [number, number]), dots: true, width: 0 }]
    : categories.map(c => ({
      label: c, colour: catColours[c],
      points: used.filter(p => catOf(p.m) === c).map(p => [tx(p.x), tx(p.y)] as [number, number]), dots: true, width: 0,
    }))

  /* ---- the timeline ---- */
  const timelineKey = wiring.tl ?? up.hists[0].feature
  const timelineLabel = timelineKey === up.hists[0].feature ? up.timelineHeight : (up.features.find(f => f.key === timelineKey)?.label ?? timelineKey)
  const timelineUnit = up.features.find(f => f.key === timelineKey)?.unit ?? 'mV'

  /* ---- actions ---- */
  const sendOutlier = () => {
    const outlier = [...events].sort((a, b) => b.depth_mV - a.depth_mV)[0]
    if (!outlier) return
    recordDemoWrite('review', 'add-queue', { id: `q-2${events.length % 9}`, source: `${fam.id} ${up.block} outlier`, kind: 'interrogation outlier', count: 1 })
    push({ text: `sent ${outlier.id} to Review · 1 span queued (demo)`, action: { label: 'Open in Review', onClick: () => navigate('review/queue') } })
  }

  const tooFew = events.length < 3 || forcedEmpty
  const stageStages = block.chain.map(b => (b.index ? `${String(b.index).padStart(2, '0')} ${b.label}` : b.label))
  const veilLabel = `${sim.steps[sim.step] ?? 'queued'} · ${Math.round(sim.fraction * 100)} %`

  return (
    <>
      <InterrogationToolbar
        sourceLabel={<>Library family · {fam.id} {fam.name}</>}
        sourceOpen={popover === 'source'} sourceRef={sourceRef} arrived={!stale} nullMethod={nullQ}
        onSourceToggle={() => setPopover(popover === 'source' ? null : 'source')}
        onSaveTemplate={() => setSaveOpen(true)} stale={stale}
        primary={sim.busy
          ? <Button icon="stop" onClick={() => { sim.cancel(); setStateQ(null) }} testid="cancel-run">Cancel</Button>
          : <Button variant="primary" icon={stale ? 'refresh' : 'play'} testid="run-chain"
            onClick={runChain}>{stale ? 'Re-run from 01' : 'Run chain'}</Button>}>
        <SourcePicker open={popover === 'source'} onClose={() => setPopover(null)} anchorRef={sourceRef} familyId={familyId}
          onPickFamily={id => { setFamilyId(id); setPopover(null) }} />
      </InterrogationToolbar>

      <ChainCard chain={block.chain} current="block2" status={status} onAddStage={() => setPopover(popover === 'stage' ? null : 'stage')}
        onSelect={id => navigate(id === 'source' ? `analyse/interrogation${familyId === 'F-03' ? '' : `?family=${familyId}`}`
          : id === 'block1' ? `analyse/interrogation/block/1${familyId === 'F-03' ? '' : `?family=${familyId}`}` : 'analyse/interrogation/block/2')} />
      <AddStagePopover open={popover === 'stage'} onClose={() => setPopover(null)} anchorRef={sourceRef}
        onPick={kind => {
          resetWiring()
          setQuery({ upstream: kind === 'slope' ? null : kind, pair: null, wire: null }, false)
          push({ text: `01 is now ${kind === 'slope' ? 'Resolve spans' : 'Spike shape'} · Aggregate re-wired from its Features` })
        }} />

      {tooFew ? (
        <EmptyState testid="aggregate-empty" icon="bar-chart"
          title={forcedEmpty ? '01 has not run yet' : `${fam.id} ${fam.name} has ${events.length} event${events.length === 1 ? '' : 's'} in scope`}
          caption={forcedEmpty
            ? 'Aggregate draws whatever 01 emits — with no Features in hand there is nothing to distribute, fit or plot'
            : 'distributions and a scaling fit need at least 3 events · pick another family or widen the distance threshold on the source block'}
          action={<Button variant="primary" icon={forcedEmpty ? 'play' : 'library'} testid="empty-action"
            onClick={() => (forcedEmpty ? runChain() : navigate('analyse/interrogation'))}>
            {forcedEmpty ? 'Run chain' : 'Open the source block'}</Button>} />
      ) : (
        <>
          {/* ------------------------------------------------ three distributions ------------------------------------------------ */}
          <div className="ig-grid3">
            {hists.map((h, i) => (
              <SectionCard key={h.key} testid={`hist-${h.key}`} title={h.title}
                info={`${h.key} · ${h.nBins} bins (${binQ === 'fd' ? 'Freedman–Diaconis' : binQ === 'sturges' ? 'Sturges' : 'fixed 20'}) · ${nullQ === 'none' ? 'the null is switched off, which P10 does not allow for a result' : `every bar is compared with the ${nullLabel} null drawn in grey behind it (P10)`}.`}
                subtitle={<span className="mono">{h.unit} · n {h.values.length}{h.key === 'interval_h' ? ` · ${INTERVAL_ENDS[intervalQ]?.label ?? intervalQ}${h.median == null ? '' : ` · median ${h.median.toFixed(4)} h`}` : ''}</span>}>
                <div className="ig-rel">
                  {sim.busy && <RunVeil label={veilLabel} fraction={sim.fraction} />}
                  <NullHistogram testid={`hist-plot-${h.key}`} height={150} bars={h.bars} nulls={h.nulls} series={h.series}
                    nullLabel={nullQ === 'shuffled' ? 'shuffled null' : 'null'} format={v => formatShort(v)} />
                </div>
                <div className="ig-foot" style={{ marginTop: 4 }} data-testid={`hist-verdict-${h.key}`}>
                  {h.tone === 'amber'
                    ? <span className="ig-amber-text"><Icon name="alert-triangle" size={11} /> {h.verdict}</span>
                    : <span><Icon name="bar-chart" size={11} /> {h.verdict}</span>}
                  {i === 1 && <InfoTip title="Inter-event interval">Intervals are taken within one recording × channel: a gap that spans two recordings is not an interval. The three definitions differ by the fall itself (6–11 s ≈ 0.002 h), so the choice moves the distribution only a little — the median above says by how much.</InfoTip>}
                </div>
              </SectionCard>
            ))}
          </div>

          {/* ------------------------------------------------ scaling + timeline ------------------------------------------------ */}
          <div className="ig-cols">
            <SectionCard testid="scaling-card" title="Scaling"
              info="A power-law fit on log axes. β is the exponent with its 95 % CI; the null β beneath it is the same fit on the null, so an exponent that does not clear its null is not a relationship (P10). Fewer than 12 points is not a fit and is not shown as one."
              actions={<Dropdown testid="axes" prefix="axes" value={axesQ} onChange={setAxes} options={block.params.axes} disabled={sim.busy} disabledReason={BUSY} />}>
              <div className="ig-row" style={{ marginBottom: 8 }}>
                <Seg testid="pair-seg" value={pair.key} onChange={setPair} options={wiredPairs.map(p => ({ value: p.key, label: p.label }))} />
                <Button ref={customRef} size="sm" variant="link" icon="plus" onClick={() => setPopover(popover === 'wiring' ? null : 'wiring')} testid="custom-pair">custom</Button>
              </div>
              <div className="ig-cols even" style={{ gap: 12 }}>
                <div className="ig-rel">
                  {sim.busy && <RunVeil label={veilLabel} fraction={sim.fraction} />}
                  <LineChart testid="scaling-plot" height={230} xLabel={`${pair.xLabel} · ${pair.x}`} yLabel={pair.yLabel} legend={false}
                    xFormat={fmtAx} yFormat={fmtAx}
                    series={[
                      ...(nullQ === 'none' ? [] : [{ label: 'null', colour: '#cbd5e1', points: nullPoints.map(p => [tx(p.x), tx(p.y)] as [number, number]), dots: true, width: 0 }]),
                      ...(dropped.length ? [{ label: 'excluded', colour: '#9ca3af', points: dropped.map(p => [tx(p.x), tx(p.y)] as [number, number]), dots: true, width: 0 }] : []),
                      ...catSeries,
                      ...(fit ? [{ label: 'fit', colour: 'var(--blue)', points: fitLine, width: 2 }] : []),
                    ]} />
                  <Legend items={[
                    { label: 'event', colour: 'var(--blue)', shape: 'dot' },
                    ...(nullQ === 'none' ? [] : [{ label: nullLabel, colour: '#cbd5e1', shape: 'dot' as const }]),
                    ...(dropped.length ? [{ label: 'excluded from the fit', colour: '#9ca3af', shape: 'dot' as const }] : []),
                    ...(fit ? [{ label: 'fit', colour: 'var(--blue)', shape: 'line' as const }] : []),
                  ]} />
                </div>
                <div className="ig-stack" style={{ gap: 8 }}>
                  {fit ? (
                    <div className="ig-beta" data-testid="beta-tile">
                      <div className="lbl">exponent β{pair.pooled ? ' · pooled' : ''}</div>
                      <div className="v">{fit.beta.toFixed(2)} [{fit.ci[0].toFixed(2)} – {fit.ci[1].toFixed(2)}]</div>
                      <div className="sub">{pair.relation} · R² {fit.r2.toFixed(2)} · n {fit.n}</div>
                    </div>
                  ) : (
                    <div className="ig-null-beta" data-testid="beta-tile" style={{ borderLeft: '3px solid var(--amber)' }}>
                      <div className="lbl"><Icon name="alert-triangle" size={11} /> exponent β · not fitted</div>
                      <div className="v">—</div>
                      <div className="ig-foot" style={{ marginTop: 2 }}>{used.length} point{used.length === 1 ? '' : 's'} · a power-law fit needs at least {MIN_FIT_N}</div>
                    </div>
                  )}
                  {fit && (
                    <div className="ig-null-beta" data-testid="null-beta-tile">
                      <div className="lbl">null β ({nullQ === 'shuffled' ? 'shuffled onsets' : nullQ === 'none' ? 'switched off' : 'matched windows'})</div>
                      <div className="v">{nullQ === 'none' ? '—' : `${nullFit.beta.toFixed(2)} [${nullFit.ci[0].toFixed(2).replace('-', '−')} – ${nullFit.ci[1].toFixed(2)}]`}</div>
                    </div>
                  )}
                  <div className="ig-foot" data-testid="fit-points">x {pair.x} · y {pair.y} · from {up.block} · {outlierNote}</div>
                  {fit && pair.byRecording && (
                    <div className="ig-foot" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }} data-testid="beta-by-recording">
                      <span>β by recording · null β {nullFit.beta.toFixed(2)}</span>
                      {pair.byRecording.map((r, i) => (
                        <span key={r.recording} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <ColourDot colour={catColours[r.recording] ?? [FAMILY_COLOURS['F-06'], '#E8900C', '#7446E0'][i % 3]} />
                          <b style={{ color: 'var(--text-2)' }}>{r.recording}</b>
                          {r.beta == null ? <span>n {r.n} · {r.note}</span> : <span>{r.beta.toFixed(2)} [{r.ci![0].toFixed(2)}–{r.ci![1].toFixed(2)}] · n {r.n}</span>}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </SectionCard>

            <SectionCard testid="timeline-card" title="When events happened"
              info="One lane per recording, on that recording's own hours-since-start axis (§0). Tick height is the plotted measure, so a recording drifting deeper over time is visible."
              subtitle={<span className="mono">height = {timelineLabel} · {timelineUnit}</span>}>
              <EventTimeline members={events} heightBy={timelineLabel} valueOf={m => featureOf(m, timelineKey)} unit={timelineUnit}
                colourOf={colourOf} onSelect={id => navigate(`analyse/interrogation/block/1?event=${id}`)} />
              {colourQ !== 'none' && <Legend items={categories.map(c => ({ label: c, colour: catColours[c], shape: 'box' as const }))} />}
            </SectionCard>
          </div>

          {/* ------------------------------------------------ parameters + summary ------------------------------------------------ */}
          <div className="ig-cols">
            <SectionCard testid="parameters-card" title="Parameters"
              info="Nothing on this block is stored with the run: Aggregate holds views. Changing a parameter here re-draws, it does not make 01 stale."
              subtitle={<span className="ig-foot"><Icon name="eye" size={11} /> views only · nothing here is stored</span>}>
              <div className="ig-rules">
                <div>
                  <div className="lb">colour by</div>
                  <Dropdown block testid="param-colour" value={colourQ} onChange={setColour} options={block.params.colourBy} disabled={sim.busy} disabledReason={BUSY} />
                </div>
                <div>
                  <div className="lb">null <InfoTip title="Null">Every interrogation result carries a null (P10). The method per analysis kind lives in Settings › Nulls.</InfoTip></div>
                  <Dropdown block active testid="param-null" value={nullQ} onChange={setNull} options={block.params.nulls} disabled={sim.busy} disabledReason={BUSY} />
                </div>
                <div>
                  <div className="lb">binning</div>
                  <Dropdown block testid="param-binning" value={binQ} onChange={setBin} options={block.params.binning} disabled={sim.busy} disabledReason={BUSY} />
                </div>
                <div>
                  <div className="lb">interval defined as</div>
                  <Dropdown block testid="param-interval" value={intervalQ} onChange={setInterval} options={block.params.interval} disabled={sim.busy} disabledReason={BUSY} />
                </div>
                <div>
                  <div className="lb">outliers</div>
                  <Dropdown block testid="param-outliers" value={outliersQ} onChange={setOutliers} options={block.params.outliers} disabled={sim.busy} disabledReason={BUSY} />
                </div>
                <div>
                  <div className="lb">purity check <InfoTip title="Purity">How many windows hold exactly one event. A window with two falls makes depth and duration meaningless.</InfoTip></div>
                  <Dropdown block testid="param-purity" value={purityQ} onChange={setPurity} disabled={sim.busy} disabledReason={BUSY}
                    options={[{ value: 'one', label: up.purity }, { value: 'none', label: 'no purity check' }]} />
                </div>
              </div>
              <div className="ig-foot" style={{ marginTop: 8 }} data-testid="parameters-effect">
                <Icon name="info" size={11} />
                {hists.map(h => `${h.title.toLowerCase()} ${h.nBins} bins`).join(' · ')} · {outlierNote} · {purityQ === 'none' ? 'purity not checked' : up.purity}
              </div>
            </SectionCard>

            <div className="ig-stack">
              <StatRow columns={2}>
                {up.tiles.map((t, i) => (
                  <StatTile key={t.label} tone={(i === 3 && purityQ === 'none') || (i === 1 && !fit) || (i === 2 && tooFewForStats) ? undefined : t.tone}
                    testid={`tile-${t.label.replace(/[^a-z]+/gi, '-')}`}
                    label={i === 1 ? `β ${pair.label.replace(/ ~ /, '~')}` : i === 3 && purityQ === 'none' ? 'purity' : t.label}
                    value={i === 0 ? String(events.length)
                      : i === 1 ? (fit ? fit.beta.toFixed(2) : 'not fitted')
                        : i === 3 && purityQ === 'none' ? 'not checked'
                          /* tiles 1 and 2 are recorded statistics over this family; under MIN_FIT_N they are
                             not this family's, so they are withheld rather than reprinted (§3). */
                          : i === 2 && tooFewForStats ? 'too few' : t.value} />
                ))}
              </StatRow>
              <div className="ig-row">
                <Button icon="download" onClick={() => notWired(`export ${events.length} rows and the fitted exponents as CSV`)} testid="aggregate-csv">CSV</Button>
                <Button icon="file" onClick={() => notWired('export the four figures as PDF with their parameters')} testid="aggregate-figures">Figures</Button>
                <Button variant="primary" icon="checklist" onClick={sendOutlier} testid="stage-outlier">Stage 1 outlier for Review</Button>
              </div>
              <div className="ig-foot"><Icon name="info" size={11} />figures export with parameters and recipe hash beneath</div>
              {tooFewForStats && (
                <Callout tone="amber" icon="alert-triangle" testid="too-few-callout">
                  {fam.id} {fam.name} has {events.length} events in scope · below {MIN_FIT_N} no exponent is fitted and no verdict is drawn against the null
                </Callout>
              )}
              {stale && <Callout tone="amber" icon="alert-triangle" testid="aggregate-stale">01 changed · these views are drawn from the last run</Callout>}
              <Callout tone="blue" icon="info" testid="generic-note" outlined>
                <Badge tone="purple">generic</Badge> one block per analysis type (P7) — Aggregate holds no algorithm, it draws whatever {up.block} declares.
                <Button size="sm" variant="link" onClick={() => setPopover('wiring')} testid="open-wiring">Feature wiring →</Button>
              </Callout>
            </div>
          </div>
        </>
      )}

      {/* ------------------------------------------------ feature wiring (frame 3c) ------------------------------------------------ */}
      <Popover open={popover === 'wiring'} onClose={() => setPopover(null)} anchorRef={customRef} placement="top-start" width={470}
        title={<span><Icon name="link" size={13} /> Feature wiring</span>} subtitle={`auto-wired from ${up.block}'s output schema`} testid="wiring-popover">
        <div className="ig-foot" style={{ marginBottom: 8, flexWrap: 'wrap' }}>
          upstream features · {up.features.map(f => <Chip key={f.key} size="sm" tone="grey" title={`${f.label} · ${f.unit}`}>{f.label}</Chip>)}
        </div>
        {[
          ...up.hists.map((h, i) => ({ slot: `h${i + 1}`, label: `histogram ${i + 1}`, value: wiring[`h${i + 1}`] ?? h.feature, kind: 'feature' as const })),
          { slot: 'tl', label: 'timeline height', value: timelineKey, kind: 'feature' as const },
          ...up.pairs.map((p, i) => ({ slot: `p${i + 1}`, label: `scaling pair ${i + 1}`, value: wiring[`p${i + 1}`] ?? p.key, kind: 'pair' as const })),
        ].map(row => (
          <div key={row.slot} className="ig-row" style={{ justifyContent: 'space-between', marginBottom: 6 }} data-testid={`wire-${row.label.replace(/\s+/g, '-')}`}>
            <span className="ig-foot" style={{ minWidth: 120 }}>{row.label}</span>
            <Dropdown width={230} value={row.value} onChange={v => setWire(row.slot, v)}
              testid={`wire-select-${row.label.replace(/\s+/g, '-')}`} ariaLabel={row.label}
              options={row.kind === 'pair'
                ? up.pairs.map(p => ({ value: p.key, label: `${p.x} → ${p.y}` }))
                : up.features.map(f => ({ value: f.key, label: f.label, description: f.unit }))} />
          </div>
        ))}
        <div className="ig-row">
          <Button size="sm" variant="link" icon="plus" onClick={() => notWired('add a scaling pair from the upstream feature list')} testid="add-scaling-pair">add scaling pair</Button>
          <Button size="sm" variant="link" icon="refresh" onClick={resetWiring} disabled={!Object.keys(wiring).length}
            disabledReason="already wired from the upstream schema" testid="reset-wiring">reset to {up.block}</Button>
        </div>
        <div className="ig-foot" style={{ marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
          <Icon name="info" size={11} />any block emitting Features over a SpanSet can feed Aggregate
        </div>
      </Popover>

      <SaveTemplateModal open={saveOpen} onClose={() => setSaveOpen(false)}
        defaultName={upstream === 'spike-shape' ? 'spike_shape_v1' : 'sharkfin_slope_v1'} stages={stageStages} />
    </>
  )
}

/* ------------------------------------------------------ helpers ------------------------------------------------------ */
/** Why a parameter control is dead while the chain runs (the shared convention). */
const BUSY = 'wait for the run'

function formatShort(v: number) {
  const a = Math.abs(v)
  return a >= 100 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : a >= 1 ? v.toFixed(2) : a >= 0.01 ? v.toFixed(2) : v.toFixed(3)
}
