/* analyse.interrogation.aggregate — 02 Aggregate (frames interrogation-3, 3b, 3c).
 * §6.8 `Features → views`, P7: the block is generic — every plot is wired from the Features the upstream
 * block declares, so the same page serves slope analysis and spike shape. P10: a null behind every plot. */
import { useMemo, useRef, useState } from 'react'
import {
  Badge, Bars, Button, Callout, Chip, ColourDot, Dropdown, EmptyState, Histogram, Icon, InfoTip, Legend, LineChart,
  Page, Popover, SectionCard, Seg, StatRow, StatTile, binValues, fmtInt, recordDemoWrite, useNotWired, useQueryState,
  useSim, type BadgeStatus,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, setQuery } from '../state'
import { useSourced } from '../api/seam'
import { getAggregateBlock, type AggregateBlock } from '../api/interrogation'
import { FAMILY_COLOURS, seeded } from '../fixtures/canon'
import { NULL_GREY, RUN_STEPS, VERDICT_COLOUR, type InterrogationMember, type PairSpec } from '../fixtures/interrogation'
import { AddStagePopover, ChainCard, InterrogationToolbar, LoadFailed, Loading, RunVeil, SaveTemplateModal } from './chrome'
import { SourcePicker } from './SourcePicker'
import { EventTimeline } from './EventTimeline'
import { inScopeIds, useFamilyQuery, useInterrogationDraft, useUpstreamQuery } from './draft'

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
/** Intervals are taken within a recording × channel — an interval across two recordings is not an interval. */
function intervals(members: InterrogationMember[]): number[] {
  const groups = new Map<string, number[]>()
  for (const m of members) {
    const k = `${m.recording}/${m.channel}`
    groups.set(k, [...(groups.get(k) ?? []), m.onset_h])
  }
  const out: number[] = []
  for (const xs of groups.values()) {
    const s = [...xs].sort((a, b) => a - b)
    for (let i = 1; i < s.length; i++) out.push(+(s[i] - s[i - 1]).toFixed(3))
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

/** A deterministic null sample for a feature: matched random windows, wider and flatter than the real one. */
function nullSample(values: number[], key: string): number[] {
  if (!values.length) return []
  const rnd = seeded(key.length * 977 + values.length)
  const lo = Math.min(...values), hi = Math.max(...values)
  const mid = (lo + hi) / 2, half = (hi - lo) / 2 || 0.1
  return Array.from({ length: Math.round(values.length * 1.6) }, () => +(mid + (rnd() + rnd() + rnd() - 1.5) * half * 1.5).toFixed(4))
}

/* ------------------------------------------------------ body ------------------------------------------------------ */
function AggregateBody({ block }: { block: AggregateBlock }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [familyId, setFamilyId] = useFamilyQuery()
  const [upstream] = useUpstreamQuery()
  const [draft] = useInterrogationDraft()
  const [popover, setPopover] = useQueryState('popover', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [colourQ, setColour] = useQueryState('colour', 'none')
  const [pairQ, setPair] = useQueryState('pair', block.upstream.pairs[0].key)
  const [axesQ, setAxes] = useQueryState('axes', 'log-log')
  const [nullQ, setNull] = useQueryState('null', 'matched')
  const [binQ, setBin] = useQueryState('binning', 'fd')
  const [intervalQ, setInterval] = useQueryState('interval', 'onset-onset')
  const [outliersQ, setOutliers] = useQueryState('outliers', 'kept')
  const [wiring, setWiring] = useState<Record<string, string>>({})
  const [saveOpen, setSaveOpen] = useState(false)
  const sourceRef = useRef<HTMLButtonElement>(null)
  const customRef = useRef<HTMLButtonElement>(null)

  const fam = block.family
  const up = block.upstream
  const scope = inScopeIds(block.members, draft, fam.id, true)
  const events = useMemo(() => block.members.filter(m => scope.has(m.id)), [block.members, scope])
  const stale = !!draft.staleFrom || draft.pendingWindow != null

  const sim = useSim('analyse.interrogation.run')
  const status: Record<string, BadgeStatus> = {
    source: 'cached',
    block1: stale ? 'stale' : 'cached',
    block2: sim.status === 'running' ? 'running' : stale ? 'stale' : 'cached',
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

  /* ---- three histograms ---- */
  const nBins = binQ === 'fixed' ? 20 : binQ === 'sturges' ? 6 : 7
  const histData = up.hists.map(h => {
    const values = h.feature === 'interval_h' ? intervals(events) : events.map(e => featureOf(e, h.feature))
    const domain: [number, number] = values.length
      ? [Math.min(h.domain[0], Math.min(...values)), Math.max(h.domain[1], Math.max(...values))]
      : h.domain
    return { ...h, values, domain, nulls: nullQ === 'none' ? [] : nullSample(values, h.feature) }
  })

  /* ---- the scaling pair ---- */
  const pair: PairSpec = up.pairs.find(p => p.key === pairQ) ?? up.pairs[0]
  const log = axesQ === 'log-log'
  const tx = (v: number) => (log ? Math.log10(Math.max(1e-6, v)) : v)
  const fmtAx = (v: number) => (log ? String(+Math.pow(10, v).toPrecision(2)) : formatShort(v))

  const pairPoints = useMemo(() => {
    if (pair.y === 'interval_h') {
      const per = intervals(events)
      return events.slice(0, per.length).map((e, i) => ({ m: e, x: featureOf(e, pair.x), y: per[i] }))
    }
    return events.map(e => ({ m: e, x: featureOf(e, pair.x), y: featureOf(e, pair.y) }))
  }, [events, pair])

  const nullPoints = useMemo(() => {
    const rnd = seeded(pair.key.length * 31 + events.length)
    return pairPoints.flatMap(p => Array.from({ length: 3 }, () => ({
      x: p.x * (0.7 + rnd() * 0.8), y: p.y * (0.55 + rnd() * 0.9),
    })))
  }, [pairPoints, pair.key, events.length])

  const fitLine = useMemo(() => {
    if (!pairPoints.length) return [] as [number, number][]
    const xs = pairPoints.map(p => tx(p.x)), ys = pairPoints.map(p => tx(p.y))
    const x0 = Math.min(...xs), x1 = Math.max(...xs)
    const my = ys.reduce((a, b) => a + b, 0) / ys.length, mx = xs.reduce((a, b) => a + b, 0) / xs.length
    const b = log ? pair.beta : (Math.max(...ys) - Math.min(...ys)) / Math.max(1e-6, x1 - x0)
    return [[x0, my + b * (x0 - mx)], [x1, my + b * (x1 - mx)]] as [number, number][]
  }, [pairPoints, pair.beta, log])

  const catSeries = colourQ === 'none'
    ? [{ label: 'event', colour: 'var(--blue)', points: pairPoints.map(p => [tx(p.x), tx(p.y)] as [number, number]), dots: true, width: 0 }]
    : categories.map(c => ({
      label: c, colour: catColours[c],
      points: pairPoints.filter(p => catOf(p.m) === c).map(p => [tx(p.x), tx(p.y)] as [number, number]), dots: true, width: 0,
    }))

  /* ---- actions ---- */
  const sendOutlier = () => {
    const outlier = [...events].sort((a, b) => b.depth_mV - a.depth_mV)[0]
    if (!outlier) return
    recordDemoWrite('review', 'add-queue', { id: `q-2${events.length % 9}`, source: `${fam.id} ${up.block} outlier`, kind: 'interrogation outlier', count: 1 })
    push({ text: `sent ${outlier.id} to Review · 1 span queued (demo)`, action: { label: 'Open in Review', onClick: () => navigate('review/queue') } })
  }

  /* `?state=empty` forces the "nothing to aggregate" state; it is also reached for real when a family has
     fewer than 3 events in scope (a distribution and a fit need more than two points). */
  const forcedEmpty = stateQ === 'empty'
  const tooFew = events.length < 3 || forcedEmpty
  const stageStages = block.chain.map(b => (b.index ? `${String(b.index).padStart(2, '0')} ${b.label}` : b.label))

  return (
    <>
      <InterrogationToolbar
        sourceLabel={<>Library family · {fam.id} {fam.name}</>}
        sourceOpen={popover === 'source'} sourceRef={sourceRef} arrived={!stale}
        onSourceToggle={() => setPopover(popover === 'source' ? null : 'source')}
        onSaveTemplate={() => setSaveOpen(true)} stale={stale}
        primary={sim.busy
          ? <Button icon="stop" onClick={() => { sim.cancel(); setStateQ(null) }} testid="cancel-run">Cancel</Button>
          : <Button variant="primary" icon={stale ? 'refresh' : 'play'} testid="run-chain"
            onClick={() => { setStateQ(null); sim.start({ steps: RUN_STEPS, stepMs: 700 }) }}>{stale ? 'Re-run from 01' : 'Run chain'}</Button>}>
        <SourcePicker open={popover === 'source'} onClose={() => setPopover(null)} anchorRef={sourceRef} familyId={familyId}
          onPickFamily={id => { setFamilyId(id); setPopover(null) }} />
      </InterrogationToolbar>

      <ChainCard chain={block.chain} current="block2" status={status} onAddStage={() => setPopover(popover === 'stage' ? null : 'stage')}
        onSelect={id => navigate(id === 'source' ? `analyse/interrogation${familyId === 'F-03' ? '' : `?family=${familyId}`}`
          : id === 'block1' ? `analyse/interrogation/block/1${familyId === 'F-03' ? '' : `?family=${familyId}`}` : 'analyse/interrogation/block/2')} />
      <AddStagePopover open={popover === 'stage'} onClose={() => setPopover(null)} anchorRef={sourceRef}
        onPick={kind => { setQuery({ upstream: kind === 'slope' ? null : kind, pair: null }, false); push({ text: `01 is now ${kind === 'slope' ? 'Resolve spans' : 'Spike shape'} · Aggregate re-wired from its Features` }) }} />

      {tooFew ? (
        <EmptyState testid="aggregate-empty" icon="bar-chart"
          title={forcedEmpty ? '01 has not run yet' : `${fam.id} ${fam.name} has ${events.length} event${events.length === 1 ? '' : 's'} in scope`}
          caption={forcedEmpty
            ? 'Aggregate draws whatever 01 emits — with no Features in hand there is nothing to distribute, fit or plot'
            : 'distributions and a scaling fit need at least 3 events · pick another family or widen the distance threshold on the source block'}
          action={<Button variant="primary" icon={forcedEmpty ? 'play' : 'library'} testid="empty-action"
            onClick={() => (forcedEmpty ? (setStateQ(null), sim.start({ steps: RUN_STEPS, stepMs: 700 })) : navigate('analyse/interrogation'))}>
            {forcedEmpty ? 'Run chain' : 'Open the source block'}</Button>} />
      ) : (
        <>
          {/* ------------------------------------------------ three distributions ------------------------------------------------ */}
          <div className="ig-grid3">
            {histData.map((h, i) => (
              <SectionCard key={h.feature} testid={`hist-${h.feature}`} title={h.title}
                info={`${h.feature} · every bar is compared with the ${nullQ === 'shuffled' ? 'shuffled-onset' : 'matched random window'} null drawn in grey behind it (P10).`}
                subtitle={<span className="mono">{h.unit} · n {h.values.length}</span>}>
                <div className="ig-rel">
                  {sim.busy && <RunVeil label={`${sim.steps[sim.step] ?? 'queued'}`} fraction={sim.fraction} />}
                  {colourQ === 'none' ? (
                    <Histogram testid={`hist-plot-${h.feature}`} height={150} domain={h.domain} nBins={nBins}
                      values={h.nulls} colour={NULL_GREY}
                      overlay={{ values: h.values, colour: h.colour, label: 'observed' }}
                      format={v => formatShort(v)} label="null" />
                  ) : (
                    <StackedHist values={h.values} events={events} domain={h.domain} nBins={nBins} categories={categories} catColours={catColours} catOf={catOf}
                      feature={h.feature} testid={`hist-plot-${h.feature}`} />
                  )}
                </div>
                <div className="ig-foot" style={{ marginTop: 4 }} data-testid={`hist-verdict-${h.feature}`}>
                  {h.verdictTone === 'amber'
                    ? <span className="ig-amber-text"><Icon name="alert-triangle" size={11} /> {h.verdict}</span>
                    : <span><Icon name="bar-chart" size={11} /> {h.verdict}</span>}
                  {i === 1 && <InfoTip title="Inter-event interval">Intervals are taken within one recording × channel: a gap that spans two recordings is not an interval. The null shuffles onsets inside the same window.</InfoTip>}
                </div>
              </SectionCard>
            ))}
          </div>

          {/* ------------------------------------------------ scaling + timeline ------------------------------------------------ */}
          <div className="ig-cols">
            <SectionCard testid="scaling-card" title="Scaling"
              info="A power-law fit on log axes. β is the exponent with its 95 % CI; the null β beneath it is the same fit on matched random windows, so an exponent that does not clear its null is not a relationship (P10)."
              actions={<Dropdown testid="axes" prefix="axes" value={axesQ} onChange={setAxes} options={block.params.axes} />}>
              <div className="ig-row" style={{ marginBottom: 8 }}>
                <Seg testid="pair-seg" value={pairQ} onChange={setPair} options={up.pairs.map(p => ({ value: p.key, label: p.label }))} />
                <Button ref={customRef} size="sm" variant="link" icon="plus" onClick={() => setPopover(popover === 'wiring' ? null : 'wiring')} testid="custom-pair">custom</Button>
              </div>
              <div className="ig-cols even" style={{ gap: 12 }}>
                <div className="ig-rel">
                  {sim.busy && <RunVeil label="02 Aggregate" fraction={sim.fraction} />}
                  <LineChart testid="scaling-plot" height={230} xLabel={`${pair.xLabel} · ${pair.x}`} yLabel={pair.yLabel} legend={false}
                    xFormat={fmtAx} yFormat={fmtAx}
                    series={[
                      ...(nullQ === 'none' ? [] : [{ label: 'null', colour: '#cbd5e1', points: nullPoints.map(p => [tx(p.x), tx(p.y)] as [number, number]), dots: true, width: 0 }]),
                      ...catSeries,
                      { label: 'fit', colour: 'var(--blue)', points: fitLine, width: 2 },
                    ]} />
                  <Legend items={[
                    { label: 'event', colour: 'var(--blue)', shape: 'dot' },
                    ...(nullQ === 'none' ? [] : [{ label: 'null', colour: '#cbd5e1', shape: 'dot' as const }]),
                    { label: 'fit', colour: 'var(--blue)', shape: 'line' },
                  ]} />
                </div>
                <div className="ig-stack" style={{ gap: 8 }}>
                  <div className="ig-beta" data-testid="beta-tile">
                    <div className="lbl">exponent β{pair.pooled ? ' · pooled' : ''}</div>
                    <div className="v">{pair.beta.toFixed(2)} [{pair.ci[0].toFixed(2)} – {pair.ci[1].toFixed(2)}]</div>
                    <div className="sub">{pair.relation} · R² {pair.r2.toFixed(2)} · n {events.length}</div>
                  </div>
                  <div className="ig-null-beta" data-testid="null-beta-tile">
                    <div className="lbl">null β ({nullQ === 'shuffled' ? 'shuffled onsets' : 'matched windows'})</div>
                    <div className="v">{pair.nullBeta.toFixed(2)} [{pair.nullCi[0].toFixed(2).replace('-', '−')} – {pair.nullCi[1].toFixed(2)}]</div>
                  </div>
                  <div className="ig-foot">x {pair.x} · y {pair.y} · from {up.block}</div>
                  {pair.byRecording && (
                    <div className="ig-foot" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }} data-testid="beta-by-recording">
                      <span>β by recording · null β {pair.nullBeta.toFixed(2)}</span>
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
              subtitle={<span className="mono">height = {up.timelineHeight}</span>}>
              <EventTimeline members={events} heightBy={up.timelineHeight} colourOf={colourOf} onSelect={id => navigate(`analyse/interrogation/block/1?event=${id}`)} />
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
                  <Dropdown block testid="param-colour" value={colourQ} onChange={setColour} options={block.params.colourBy} />
                </div>
                <div>
                  <div className="lb">null <InfoTip title="Null">Every interrogation result carries a null (P10). The method per analysis kind lives in Settings › Nulls.</InfoTip></div>
                  <Dropdown block active testid="param-null" value={nullQ} onChange={setNull} options={block.params.nulls} />
                </div>
                <div>
                  <div className="lb">binning</div>
                  <Dropdown block testid="param-binning" value={binQ} onChange={setBin} options={block.params.binning} />
                </div>
                <div>
                  <div className="lb">interval defined as</div>
                  <Dropdown block testid="param-interval" value={intervalQ} onChange={setInterval} options={block.params.interval} />
                </div>
                <div>
                  <div className="lb">outliers</div>
                  <Dropdown block testid="param-outliers" value={outliersQ} onChange={setOutliers} options={block.params.outliers} />
                </div>
                <div>
                  <div className="lb">purity check <InfoTip title="Purity">How many windows hold exactly one event. A window with two falls makes depth and duration meaningless.</InfoTip></div>
                  <Dropdown block testid="param-purity" value="one" onChange={() => notWired('change the purity check')} options={[{ value: 'one', label: up.purity }, { value: 'none', label: 'no purity check' }]} />
                </div>
              </div>
            </SectionCard>

            <div className="ig-stack">
              <StatRow columns={2}>
                {up.tiles.map((t, i) => (
                  <StatTile key={t.label} tone={t.tone} testid={`tile-${t.label.replace(/[^a-z]+/gi, '-')}`}
                    label={i === 1 ? `β ${pair.label.replace(/ ~ /, '~')}` : t.label}
                    value={i === 0 ? String(events.length) : i === 1 ? pair.beta.toFixed(2) : t.value} />
                ))}
              </StatRow>
              <div className="ig-row">
                <Button icon="download" onClick={() => notWired(`export ${events.length} rows and the fitted exponents as CSV`)} testid="aggregate-csv">CSV</Button>
                <Button icon="file" onClick={() => notWired('export the four figures as PDF with their parameters')} testid="aggregate-figures">Figures</Button>
                <Button variant="primary" icon="checklist" onClick={sendOutlier} testid="stage-outlier">Stage 1 outlier for Review</Button>
              </div>
              <div className="ig-foot"><Icon name="info" size={11} />figures export with parameters and recipe hash beneath</div>
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
          ...up.hists.map((h, i) => ({ slot: `histogram ${i + 1}`, value: h.feature })),
          { slot: 'timeline height', value: up.hists[0].feature },
          ...up.pairs.map((p, i) => ({ slot: `scaling pair ${i + 1}`, value: `${p.x} → ${p.y}` })),
        ].map(row => (
          <div key={row.slot} className="ig-row" style={{ justifyContent: 'space-between', marginBottom: 6 }} data-testid={`wire-${row.slot.replace(/\s+/g, '-')}`}>
            <span className="ig-foot" style={{ minWidth: 120 }}>{row.slot}</span>
            <Dropdown width={230} value={wiring[row.slot] ?? row.value} onChange={v => setWiring(w => ({ ...w, [row.slot]: v }))}
              testid={`wire-select-${row.slot.replace(/\s+/g, '-')}`} ariaLabel={row.slot}
              options={row.slot.startsWith('scaling')
                ? up.pairs.map(p => ({ value: `${p.x} → ${p.y}`, label: `${p.x} → ${p.y}` }))
                : up.features.map(f => ({ value: f.key, label: f.label, description: f.unit }))} />
          </div>
        ))}
        <Button size="sm" variant="link" icon="plus" onClick={() => notWired('add a scaling pair from the upstream feature list')} testid="add-scaling-pair">add scaling pair</Button>
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
function formatShort(v: number) {
  const a = Math.abs(v)
  return a >= 100 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : a >= 1 ? v.toFixed(2) : a >= 0.01 ? v.toFixed(2) : v.toFixed(3)
}

/** Observed bars split by the colour-by category (frame 3b), over the same bins. */
function StackedHist({ values, events, domain, nBins, categories, catColours, catOf, feature, testid }: {
  values: number[]; events: InterrogationMember[]; domain: [number, number]; nBins: number
  categories: string[]; catColours: Record<string, string>; catOf: (m: InterrogationMember) => string; feature: string; testid: string
}) {
  const bins = binValues(values, domain, nBins)
  const w = bins.length > 1 ? bins[0].x1 - bins[0].x0 : 1
  const dp = w >= 1 ? 0 : w >= 0.1 ? 1 : w >= 0.01 ? 2 : w >= 0.001 ? 3 : 4
  const labels = bins.map(b => b.x0.toFixed(dp))
  const series = categories.map(c => ({
    key: c, label: c, colour: catColours[c],
    values: bins.map(b => events.filter(e => catOf(e) === c && featureOf(e, feature) >= b.x0 && featureOf(e, feature) < b.x1).length),
  }))
  return <Bars testid={testid} categories={labels} series={series} mode="stacked" height={150} valueLabels={false} legend />
}
