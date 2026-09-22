/* discovery.seed — frame discovery-2. A seed search set up in place as a draft run (§7.6, P17): seed source and
 * provenance, carry / rebind, parameters with the where-to-cut histogram (null behind, draggable threshold), the distance
 * profile on one channel, match cards sorted by distance, and the apply bar (Save as template · Run seed search). */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Button, Callout, Checkbox, DisabledReason, Dropdown, EmptyState, Icon, InfoTip, Modal, NumberField, Pager, Popover, ProgressBar, RadioCards, RangeSlider,
  Seg, SelectField, Slider, TextField, cx, forceSim, recordDemoWrite, useDemoState, useQueryState, useSim,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, useApp } from '../state'
import { useSourced } from '../api/seam'
import { runDiscoverySeedSearch, type CutRule } from '../api'
import { useSize } from '../charts/useSize'
import {
  getSeedProfile, getSeedResults, getSeedSetup, getTemplates, heldOutReason, isHeldOut, type SeedDraft, type SeedInfo, type SeedMatch, type SeedParams, type SeedResults, type SeedSource,
} from '../api/discovery'
import { CostChip, DiscoveryToolbar, HistoryButton, LoadFailed, Loading, NullChip, Refreshing, RunsCard, ScopeCard } from './chrome'
import { RunGlyph } from './glyphs'
import { useDiscovery, type Discovery } from './session'

const SEED_COLOUR = '#AF52DE', KEPT_LIGHT = '#E6CCF5', THRESH = '#E8900C'
/** How many matches the run keeps before the cut filters them. Generous on
 *  purpose: the cut is a filter over what came back, so a small k would
 *  silently bound the histogram. */
const SEED_K = 200
/** A per-draw expectation is usually a fraction; 0 stays 0 rather than '0.00'. */
const fmtNull = (v: number) => v === 0 ? '0' : v < 1 ? v.toFixed(2) : v.toFixed(1)
const SIM_ID = 'discovery.seed.seed_F03_native_2'

export function SeedPage() {
  const dx = useDiscovery()
  const setup = useSourced(getSeedSetup, [])
  const [draftStore, setDraftStore] = useDemoState<SeedDraft | null>('discovery.seed.draft', () => null)
  const draft = draftStore ?? setup.data?.draft ?? null
  const [sourceQ, setSourceQ] = useQueryState<SeedSource>('source', 'library')
  const [stateQ] = useQueryState('state', '')
  const [modal, setModal] = useQueryState('modal', '')
  const sim = useSim(SIM_ID)
  const toast = useToast()
  const { source: exploreSpan } = useApp()

  const setDraft = (patch: Partial<SeedDraft>) => { if (draft) setDraftStore({ ...draft, ...patch }) }
  const setParams = (patch: Partial<SeedParams>) => { if (draft) setDraftStore({ ...draft, params: { ...draft.params, ...patch } }) }
  const seeds = setup.data?.seeds ?? []
  /* The seed is the draft's, and `?source=` narrows to that KIND of seed
   * rather than naming one. The old line looked up 'm-1846' and 'E-0102',
   * invented ids no seed carries — a real seed id is
   * "<source>:<recording>:<start>:<end>" — so `seed` was always null and the
   * page drew none of its histogram, profile or matches. */
  const wanted = sourceQ === 'medoid' || sourceQ === 'explore' || sourceQ === 'library' ? sourceQ : null
  const seed: SeedInfo | null = (wanted
    ? seeds.find(s => s.source === wanted) ?? null
    : seeds.find(s => s.id === draft?.seedId) ?? seeds[0] ?? null)
  const channels = dx.scope?.channels ?? []
  const noResults: SeedResults = { candidates: [], nullDistances: [], recommendedCut: null, cutRule: null, nullDraws: 0, nullMethod: null, nullSupported: true, nullReason: null }
  const results = useSourced(() => seed ? getSeedResults(seed.id, channels) : Promise.resolve({ data: noResults, source: 'demo' as const }), [seed?.id, channels.join(',')])

  // deep links ?state=running|done|failed put the simulated search straight into that state
  useEffect(() => {
    if (stateQ === 'running' && sim.status !== 'running') forceSim(SIM_ID, { status: 'running', steps: stepsFor(channels), step: 1, fraction: 0.45, startedAt: Date.now() })
    if (stateQ === 'failed' && sim.status !== 'failed') forceSim(SIM_ID, { status: 'failed', steps: stepsFor(channels), step: 2, fraction: 0.66, error: 'MASS failed on CH7_B2 · distance profile ran out of memory (simulated)' })
    if (stateQ === 'done' && sim.status !== 'done') forceSim(SIM_ID, { status: 'done', steps: stepsFor(channels), step: 3, fraction: 1, finishedAt: Date.now() })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  // no cut is no cut: nothing is kept until a threshold exists, and a stand-in d would draw a match list
  // the search never returned
  /* §7.6's "match threshold with a recommended marker": until the researcher
   * drags the line, the cut IS the recommendation the null produced. Waiting
   * for an explicit choice left the page with no histogram at all after a
   * search that had already computed one. */
  const recommendedCut = results.data?.recommendedCut ?? null
  const chosen = draft?.params.threshold ?? null
  const threshold = chosen ?? recommendedCut
  const cutIsRecommended = chosen == null && recommendedCut != null
  const kept = useMemo(() => threshold == null ? [] : (results.data?.candidates ?? []).filter(c => c.d <= threshold), [results.data, threshold])
  /* §7.6: "You see how many matches chance alone would give at the moment you
   * choose where to cut." `nullDistances` is POOLED over every draw of every
   * channel, while `kept` is one realisation over every channel — so the count
   * has to be divided by the draws per channel to be the same quantity. Taking
   * the pooled count raw overstated the null by the draw count (ten-fold on a
   * ten-draw search), and the error was invisible at the recommended cut,
   * which sits below every null distance and reads 0 either way. */
  const nullDraws = Math.max(1, results.data?.nullDraws ?? 1)
  const perDraw = (cut: number | null) => cut == null ? 0
    : (results.data?.nullDistances ?? []).filter(d => d <= cut).length / nullDraws
  const nullKept = perDraw(threshold)
  const recCut = recommendedCut
  const nullAtRec = perDraw(recCut)

  /* The run row is the server's: the old version invented one client-side,
   * keyed by the draft and carrying `template: 'seed_F03_native_2'`, a name no
   * templates row has. When the sweep lands, re-read the runs list and mark the
   * draft's parameters applied. */
  useEffect(() => {
    if (sim.status !== 'done' || !draft) return
    dx.reload()
    setDraftStore({ ...draft, applied: { ...draft.params } })
    if (stateQ !== 'done') toast.push({ text: `${draft.label} finished · ${kept.length} matches`, action: { label: 'Open in Runs', onClick: () => navigate('discovery/runs') } })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sim.status, draft?.key])

  // the server keys a seed run on the label it was given, and appends `_2`,
  // `_3`… when that key is taken in this session
  const seedRunKey = (r: { key: string }) => draft && (r.key === draft.label || r.key.startsWith(draft.label + '_'))
  const runs = !!draft && dx.runs.some(seedRunKey)
  const draftRow = draft && !runs ? <DraftRow draft={draft} seed={seed} sim={sim} /> : null

  return (
    <>
      <Header workspace="Discovery" page="Seed search" subtitle="find more of a shape you already have" demo={dx.demo || setup.source === 'demo'} />
      <div className="k-page dsc-page" data-testid="discovery-seed-page">
        <div className="k-page-inner" style={{ maxWidth: 1376, gap: 12 }}>
          {(dx.error || setup.error) && <LoadFailed what="the seed search" error={(dx.error ?? setup.error)!} onRetry={() => { dx.reload(); setup.reload() }} />}
          {(dx.firstLoad || (setup.loading && !setup.data)) && !dx.error && <Loading height={600} label="loading the seed search" />}
          {!(dx.firstLoad || (setup.loading && !setup.data)) && !dx.error
            && <Refreshing on={dx.refreshing || setup.loading} label="re-reading the search" />}
          {dx.scope && draft && (
            <>
              <DiscoveryToolbar dx={dx} right={<><NullChip dx={dx} /><CostChip dx={dx} label={<><b>≈ {Math.max(1, channels.length)} s</b> <span className="muted">local · {channels.length} channels</span></>} /><HistoryButton dx={dx} /></>} />
              <ScopeCard dx={dx} />
              {!dx.recording?.heldOut && (
                <div className="dsc-cols">
                  <RunsCard dx={dx} mode="seed" selected={runs ? dx.runs.find(seedRunKey)?.key : undefined} draft={draftRow} onAddTemplate={() => navigate('discovery/runs?modal=add-template')} />
                  <div className="dsc-right">
                    <div className="dsc-seed-top">
                      <SeedCard draft={draft} seed={seed} seeds={seeds} source={sourceQ} onSource={s => { setSourceQ(s); setDraft({ source: s, seedId: s === 'medoid' ? 'm-1846' : s === 'library' ? 'E-0102' : draft.seedId }) }}
                        onSeed={id => { setDraft({ seedId: id, source: id.startsWith('m-') ? 'medoid' : 'library' }); setSourceQ(id.startsWith('m-') ? 'medoid' : 'library') }}
                        exploreSpan={exploreSpan} onBind={b => { setDraft({ bind: b }); recordDemoWrite('discovery', 'seed-bind', { bind: b }) }} />
                      <ParamsCard draft={draft} recommended={setup.data!.recommended} seed={seed} setParams={setParams} results={results.data} nullAtRec={nullAtRec} kept={kept.length} nullKept={nullKept} cut={threshold} cutIsRecommended={cutIsRecommended} />
                    </div>
                    {!seed ? null : results.error ? <LoadFailed what="seed matches" error={results.error} onRetry={results.reload} /> : !results.data ? <Loading height={220} /> : (
                      <>
                        {results.data.candidates.length === 0
                          ? <section className="k-card" data-testid="no-cut"><EmptyState size="sm" icon="bar-chart" title="No matches"
                            caption="the search returned nothing on this scope" /></section>
                          : <>
                            <DistanceProfile dx={dx} seed={seed} candidates={results.data.candidates} threshold={threshold} />
                            {/* with no cut nothing is KEPT, but the closest matches are still what
                                the researcher is looking at — hiding them makes "nothing beats the
                                null" look like "the search did not run" */}
                            <MatchesCard seed={seed} matches={threshold == null ? results.data.candidates.slice(0, 12) : kept}
                              channels={channels.length}
                              note={threshold == null ? `no cut: none of the ${results.data.candidates.length} matches is closer than the null gives — these are the closest` : null} />
                          </>}
                      </>
                    )}
                    <ApplyBar dx={dx} draft={draft} recommended={setup.data!.recommended} kept={threshold == null ? null : kept.length} seed={seed} sim={sim} onSave={() => setModal('save-template')} />
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
      {draft && <SaveTemplateModal open={modal === 'save-template'} onClose={() => setModal(null)} draft={draft} seed={seed} />}
    </>
  )
}
const stepsFor = (channels: string[]) => [...channels.map(c => `MASS ${c}`), 'null 200×']

function DraftRow({ draft, seed, sim }: { draft: SeedDraft; seed: SeedInfo | null; sim: ReturnType<typeof useSim> }) {
  return (
    <div className="dsc-run selected draft" style={{ ['--run' as string]: SEED_COLOUR }} data-testid="run-row-draft" data-status={sim.busy ? 'running' : 'draft'}>
      <div className="dsc-run-body" role="group" aria-label={`${draft.label} draft`}>
        <RunGlyph kind="seed" width={40} height={28} />
        <span className="dsc-run-text">
          <b>{draft.label}</b>
          <span className="dsc-run-meta"><span className="k-badge t-amber">draft</span><span className="muted">{seed ? `${seed.id} ${seed.role}` : 'Explore selection'} · MASS</span></span>
          <span className="dsc-run-line small">
            {sim.busy ? <span className="dsc-run-progress"><ProgressBar value={sim.fraction} size="sm" labelPosition="none" width={96} /><span className="blue">{sim.steps[sim.step] ?? 'queued'}</span></span>
              : sim.status === 'failed' ? <span className="red">failed · see the apply bar</span> : <span className="amber">draft · not run</span>}
          </span>
        </span>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ seed card */
function SeedCard({ draft, seed, seeds, source, onSource, onSeed, exploreSpan, onBind }: {
  draft: SeedDraft; seed: SeedInfo | null; seeds: SeedInfo[]; source: SeedSource; onSource: (s: SeedSource) => void; onSeed: (id: string) => void
  exploreSpan: ReturnType<typeof useApp>['source']; onBind: (b: 'carry' | 'rebind') => void
}) {
  const changeRef = useRef<HTMLButtonElement>(null)
  const [popQ, setPopQ] = useQueryState('popover', '')
  const yDomain = useMemo<[number, number]>(() => seed ? padDomain(seed.trace) : [-0.4, 0.1], [seed])
  const exploreRefused = exploreSpan && isHeldOut(exploreSpan.source_file) ? heldOutReason(exploreSpan.source_file) : null
  return (
    <section className="k-card dsc-seed" data-testid="seed-card" aria-label="Seed">
      <div className="dsc-card-head">
        <h3>Seed</h3>
        <InfoTip title="Seed">The shape to search for. Its window is its native length; the card shows provenance — recording, channel, samples and content hash — so a saved template can say exactly what it carried.</InfoTip>
        <span className="muted small">type Signal span</span>
      </div>
      <div className="dsc-seed-body">
        <Seg value={source} onChange={onSource} size="sm" testid="seed-source" options={[{ value: 'library', label: 'Library exemplar' }, { value: 'explore', label: 'Explore selection' }, { value: 'medoid', label: 'Family medoid' }]} />
        {source === 'explore' ? (
          exploreRefused ? <Callout tone="red" icon="lock" title="Held out" testid="seed-explore-refused">{exploreRefused}</Callout>
            : exploreSpan ? (
              <div className="dsc-seed-row" data-testid="seed-explore">
                <div className="dsc-seed-thumb unavailable"><Icon name="wave" size={16} /><span className="small muted">shape read when the search runs</span></div>
                <div className="dsc-seed-kv">
                  <b>{exploreSpan.label ?? 'span from Explore'}</b>
                  <span>{exploreSpan.source_file.replace(/\.(mat|csv)$/, '')} · {exploreSpan.channel_name}</span>
                  <span>{(exploreSpan.start_idx / exploreSpan.fs / 3600).toFixed(2)} h · {Math.round((exploreSpan.end_idx - exploreSpan.start_idx) / exploreSpan.fs)} s · {exploreSpan.end_idx - exploreSpan.start_idx} samples</span>
                  <span className="muted">hash unavailable until read</span>
                  <Button variant="link" size="sm" onClick={() => navigate('explore/corpus')}>change in Explore ›</Button>
                </div>
              </div>
            ) : <EmptyState size="sm" icon="scan" title="No span selected in Explore" caption="select a span in Explore, then come back" testid="seed-explore-empty" action={<Button size="sm" icon="external" onClick={() => navigate('explore/corpus')}>Select a span in Explore</Button>} />
        ) : seed && (
          <div className="dsc-seed-row" data-testid="seed-provenance">
            <div className="dsc-seed-thumb"><SeedThumb values={seed.trace} yDomain={yDomain} /><span className="small muted mono">{seed.samples} samples · {seed.lengthS} s</span></div>
            <div className="dsc-seed-kv">
              <b>{seed.title}</b>
              <span>{seed.familyLine}</span>
              <span>{seed.recording} · {seed.channel}</span>
              <span>{seed.startH.toFixed(2)} h · {seed.lengthS} s · hash {seed.hash}</span>
              <button ref={changeRef} type="button" className="dsc-inline-link blue" onClick={() => setPopQ(popQ === 'change-seed' ? null : 'change-seed')} data-testid="change-seed">change seed ›</button>
              <Popover open={popQ === 'change-seed'} onClose={() => setPopQ(null)} anchorRef={changeRef} title="Change seed" width={320} testid="change-seed-popover">
                {seeds.map(s => (
                  <button key={s.id} type="button" className={cx('dsc-seed-option', s.id === seed.id && 'on')} onClick={() => { onSeed(s.id); setPopQ(null) }} data-testid={`seed-option-${s.id}`}>
                    <SeedThumb values={s.trace} yDomain={padDomain(s.trace)} width={54} height={30} />
                    <span><b>{s.title}</b><span className="muted small mono">{s.samples} samples · {s.familyLine}</span></span>
                  </button>
                ))}
              </Popover>
            </div>
          </div>
        )}
        <div className="row" style={{ gap: 8 }}>
          <DisabledReason reason="MASS takes one seed"><button type="button" className="dsc-add-channel" disabled><Icon name="plus" size={11} /> seed</button></DisabledReason>
          <span className="muted small mono">MASS takes one seed</span>
          <InfoTip title="Several seeds">A search taking several seeds — e.g. every medoid of a family — appears when an algorithm supports it.</InfoTip>
        </div>
        <div className="dsc-divider" />
        <div className="row" style={{ gap: 6 }}><span className="small">When saved as a template</span><InfoTip title="carry or rebind">carry: the exemplar travels with the template, so applying it always searches for this shape. rebind: applying the template asks for an exemplar each time.</InfoTip></div>
        <RadioCards columns={1} value={draft.bind} onChange={onBind} testid="seed-bind" options={[
          { value: 'carry', title: 'carry', description: 'this exemplar travels with the template' },
          { value: 'rebind', title: 'rebind', description: 'ask for an exemplar when applied' },
        ]} />
      </div>
    </section>
  )
}
/** A domain over the FINITE values. The wire spells a non-finite sample null
 *  and the adapter turns it back into NaN, and Math.min over an array holding
 *  one NaN is NaN — which makes every y NaN and the browser reject the path. */
function padDomain(values: number[]): [number, number] {
  const f = values.filter(Number.isFinite)
  if (!f.length) return [-1, 1]
  const lo = Math.min(...f), hi = Math.max(...f), m = (hi - lo) * 0.12 || 0.05
  return [lo - m, hi + m]
}
function SeedThumb({ values, yDomain, width = 132, height = 78, overlay }: { values: number[]; yDomain: [number, number]; width?: number; height?: number; overlay?: number[] }) {
  const padL = width > 80 ? 26 : 2
  const x = (i: number, n: number) => padL + (i / Math.max(1, n - 1)) * (width - padL - 3)
  const y = (v: number) => 3 + (1 - (v - yDomain[0]) / (yDomain[1] - yDomain[0])) * (height - 6)
  // the seed's own trace can carry a non-finite sample too; lift the pen there
  const path = (vs: number[]) => {
    let d = '', pen = false
    vs.forEach((v, i) => {
      if (!Number.isFinite(v)) { pen = false; return }
      d += `${pen ? 'L' : 'M'}${x(i, vs.length).toFixed(1)} ${y(v).toFixed(1)}`
      pen = true
    })
    return d
  }
  return (
    <svg width={width} height={height} role="img" aria-label="seed shape in mV" className="dsc-seed-svg">
      <rect x={padL} y={0} width={width - padL} height={height} fill="#fff" />
      {padL > 2 && <><text x={padL - 3} y={10} textAnchor="end" className="dsc-axis-t">{fmtTick(yDomain[1])}</text><text x={padL - 3} y={height - 3} textAnchor="end" className="dsc-axis-t">{fmtTick(yDomain[0])}</text><text x={padL - 3} y={height / 2 + 3} textAnchor="end" className="dsc-axis-t">mV</text></>}
      {overlay && <path d={path(overlay)} fill="none" stroke="var(--trace)" strokeWidth={1.1} />}
      <path d={path(values)} fill="none" stroke={SEED_COLOUR} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  )
}
const fmtTick = (v: number) => `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(2)}`

/* ------------------------------------------------------------------ parameters + where to cut */
function ParamsCard({ draft, recommended, seed, setParams, results, nullAtRec, kept, nullKept, cut, cutIsRecommended }: {
  draft: SeedDraft; recommended: SeedParams; seed: SeedInfo | null; setParams: (p: Partial<SeedParams>) => void
  results: { candidates: SeedMatch[]; nullDistances: number[]; cutRule?: CutRule | null } | null; nullAtRec: number; kept: number; nullKept: number
  /** The cut in force: the researcher's if they chose one, else the null's own
   *  recommendation. `recommended.threshold` is always null — the parameter card
   *  cannot know a cut before the search has drawn a null. */
  cut: number | null; cutIsRecommended: boolean
}) {
  const p = draft.params
  const m = seed?.samples ?? 21
  const half = Math.round(m / 2 - 0.01)
  const differs = (Object.keys(recommended) as (keyof SeedParams)[]).some(k => p[k] !== recommended[k])
  const [thrRaw, setThrRaw] = useState<string | null>(null)
  return (
    <section className="k-card dsc-params" data-testid="params-card" aria-label="Parameters">
      <div className="dsc-card-head">
        <h3>Parameters</h3>
        <InfoTip title="Parameters">MASS slides the seed along every channel and returns a z-normalised Euclidean distance per position. The threshold cuts where a match is kept; the null (circular shift 200×) shows what chance alone would keep.</InfoTip>
        <span className="k-spacer" />
        <Button variant="link" icon="undo" onClick={() => { setParams({ ...recommended }); recordDemoWrite('discovery', 'seed-revert', {}) }} disabled={!differs} disabledReason="already at recommended values" testid="revert-recommended">Revert to recommended</Button>
      </div>
      <div className="dsc-params-grid">
        <ParamField label="algorithm" info="MASS: Mueen's algorithm for similarity search, z-normalised Euclidean distance.">
          <Dropdown value={p.algorithm} onChange={v => setParams({ algorithm: v })} block testid="param-algorithm"
            options={[{ value: 'mass', label: 'MASS · z-norm Euclidean' }, { value: 'mpjoin', label: 'matrix profile join', disabled: true, reason: 'not built' }]} />
        </ParamField>
        <ParamField label="window m" info="Locked at the exemplar's native length: a seed is searched at the length it was drawn.">
          <SelectField value="native" onChange={() => undefined} options={[{ value: 'native', label: `${m} samples · native` }]} disabled disabledReason={`window is the exemplar's native length (${m} samples)`} testid="param-window" />
        </ParamField>
        <ParamField label="scale bank" info="A bank searches several stretched copies of the seed. MASS searches one length.">
          <Dropdown value={p.scaleBank} onChange={v => setParams({ scaleBank: v })} block testid="param-scale-bank"
            options={[{ value: 'none', label: 'none' }, { value: '3', label: '3 lengths · 0.8× 1× 1.25×', disabled: true, reason: 'needs a scale-bank algorithm' }]} />
        </ParamField>
        {/* The figure is the guard that RAN — stumpy.match's m/4 — and the note carries §7.6's m/2
            beside it. The slider is disabled because `detection.seed_matches` takes no exclusion
            parameter: a control that moved this would move the card and not the search. */}
        <ParamField label="exclusion zone" info={p.exclusionNote ?? 'Matches closer than this to a better match are dropped. m/2 is the trivial-match guard.'}
          aside={<b className="mono">{p.exclusionSettable === false ? `m/4 = ${p.exclusionS} s` : p.exclusionS === half ? `m/2 = ${half} s` : `${p.exclusionS} s`}</b>}>
          <Slider value={p.exclusionS} onChange={v => setParams({ exclusionS: v })} min={0} max={m} step={1} showValue={false} testid="param-exclusion" ariaLabel="exclusion zone"
            disabled={p.exclusionSettable === false} disabledReason={p.exclusionSettable === false ? 'detection.seed_matches takes no exclusion parameter — stumpy.match applies its own m/4' : undefined} />
          {/* one line here, the whole sentence in the info-tip: the note runs to
              three sentences and printed in full it crowded the histogram */}
          <span className={cx('small mono', p.exclusionSettable === false ? 'muted' : p.exclusionS === half ? 'green' : p.exclusionS < half ? 'amber' : 'muted')} data-testid="exclusion-caption">
            {p.exclusionSettable === false
              ? `stumpy.match's own guard · §7.6 asks m/2 (${p.specExclusionS ?? half} s)`
              : p.exclusionNote ?? (p.exclusionS === half ? '= trivial-match guard' : p.exclusionS < half ? 'below m/2 lets trivial matches through' : 'wider than m/2 · fewer neighbouring matches')}
          </span>
        </ParamField>
        {/* the cut is computed from the null distribution, so there is none until a search has drawn one */}
        <ParamField label="match threshold" info="Keep matches with distance d at or below this. The green tick is the recommended cut: where the null starts to keep matches." aside={
          p.threshold != null
            ? <NumberField value={p.threshold} min={0.1} max={8} step={0.1} width={78} onValid={v => { setParams({ threshold: +v.toFixed(1) }); setThrRaw(null) }} onChange={(_, r) => setThrRaw(r ?? null)} testid="param-threshold-number" ariaLabel="match threshold d" />
            : <span className="muted small mono">no cut</span>}>
          {p.threshold != null ? (
            <>
              <Slider value={cut ?? 0} onChange={v => setParams({ threshold: +v.toFixed(1) })} min={0} max={8} step={0.1} showValue={false} marks={cut != null ? [{ value: cut, label: '' }] : []} testid="param-threshold" ariaLabel="match threshold" />
              <span className="small mono green">{thrRaw ? <span className="dsc-err">{thrRaw}</span> : cut != null ? <>{cutIsRecommended ? 'recommended' : 'chosen'} {cut} · the null gives {fmtNull(nullAtRec)} per draw</> : 'no recommended cut yet — it is read off the null distribution'}</span>
              {/* a statistic whose rule is unstated cannot be falsified (fixup-a item 12) */}
              {results?.cutRule && <span className="small mono muted" data-testid="cut-rule">{results.cutRule.text}</span>}
            </>
          ) : <span className="small mono muted" data-testid="threshold-none">no cut chosen · the recommended cut is read off the null distribution, so there is none until the search has drawn one</span>}
        </ParamField>
        <ParamField label="on overlap" info="When two kept matches overlap, which one survives.">
          <Dropdown value={p.overlap} onChange={v => setParams({ overlap: v })} block testid="param-overlap"
            options={[{ value: 'lowest', label: 'keep lowest distance' }, { value: 'first', label: 'keep first' }, { value: 'all', label: 'keep all (overlapping)' }]} />
        </ParamField>
      </div>
      {results && results.candidates.length
        ? <CutHistogram candidates={results.candidates} nullDistances={results.nullDistances} threshold={cut} recommended={cut} kept={kept} nullKept={nullKept} rule={results.cutRule ?? null} onThreshold={t => setParams({ threshold: t })} />
        : <div className="dsc-cut-empty"><EmptyState size="sm" icon="bar-chart" title={results ? 'No cut yet' : 'No distances yet'}
          caption={results ? 'the recommended cut comes from the null distribution — run the search to draw one' : 'pick a seed to see where to cut'} /></div>}
    </section>
  )
}
function ParamField({ label, info, aside, children }: { label: string; info: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="dsc-param">
      <div className="dsc-param-head"><span className="muted small">{label}</span><InfoTip title={label} size={11}>{info}</InfoTip><span className="k-spacer" />{aside}</div>
      {children}
    </div>
  )
}

/** Where to cut: match-distance histogram, null distribution behind, self bin shaded, recommended tick, draggable threshold. */
/** `threshold` is null when the null gives nothing away: no distance in this
 *  search is closer than chance, so there is no cut to draw. The bars and the
 *  null behind them are exactly the evidence for that, so they still draw —
 *  hiding the histogram would make "nothing beats the null" look like "the
 *  search did not run". */
function CutHistogram({ candidates, nullDistances, threshold, recommended, kept, nullKept, rule, onThreshold }: {
  candidates: SeedMatch[]; nullDistances: number[]; threshold: number | null; recommended: number | null; kept: number; nullKept: number
  rule: CutRule | null; onThreshold: (t: number) => void
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const [dragging, setDragging] = useState(false)
  const W = size.width, H = 150, padL = 34, padR = 12, padT = 22, padB = 30
  /* The axis follows the DATA. It was fixed at 0-8 d, and a z-normalised MASS
   * distance over a 711-sample exemplar runs to 17: `count()` clamped every
   * value into the last bin, so the card drew one bar at 7.8-8.0 whose tooltip
   * read "132 matches" about distances none of which was anywhere near it, and
   * the slider could not reach a cut that kept anything. */
  const dMax = useMemo(() => {
    const all = [...candidates.map(c => c.d), ...nullDistances].filter(Number.isFinite)
    return Math.max(1, Math.ceil((all.length ? Math.max(...all) : 8) * 1.05))
  }, [candidates, nullDistances])
  const bins = 40, bw = dMax / bins
  const count = (xs: number[]) => { const c = new Array(bins).fill(0); xs.forEach(d => { const i = Math.min(bins - 1, Math.floor(d / bw)); if (i >= 0) c[i]++ }); return c }
  const cand = useMemo(() => count(candidates.map(c => c.d)), [candidates, dMax])
  const nul = useMemo(() => count(nullDistances), [nullDistances, dMax])
  const maxC = Math.max(1, ...cand, ...nul)
  const x = (d: number) => padL + (d / dMax) * (W - padL - padR)
  const y = (c: number) => H - padB - (c / maxC) * (H - padT - padB)
  const toD = (px: number) => Math.max(0.1, Math.min(dMax, Math.round(((px - padL) / (W - padL - padR)) * dMax * 10) / 10))
  const move = (e: React.PointerEvent<SVGSVGElement>) => { if (!dragging) return; const r = e.currentTarget.getBoundingClientRect(); onThreshold(toD(e.clientX - r.left)) }
  return (
    <div className="dsc-cut" ref={ref} data-testid="cut-histogram">
      {W > 0 && (
        <svg width={W} height={H} onPointerMove={move} onPointerUp={() => setDragging(false)} onPointerLeave={() => setDragging(false)} role="img" aria-label={threshold == null
            ? `match distance histogram over ${candidates.length} matches; no cut — none is closer than the null gives`
            : `match distance histogram, ${kept} kept at d ≤ ${threshold}, the null gives ${fmtNull(nullKept)} per draw`}>
          <rect x={x(0)} y={padT} width={Math.max(2, x(dMax / 20) - x(0))} height={H - padT - padB} fill="#FDECEC" />
          <text x={x(0) + 3} y={padT + 10} className="dsc-axis-t" style={{ fill: '#c0392b' }}>self</text>
          <text x={padL - 6} y={padT + 4} textAnchor="end" className="dsc-axis-t">count</text>
          {nul.map((c, i) => c > 0 && <rect key={`n${i}`} x={x(i * bw) + 1} width={Math.max(1, x(bw) - x(0) - 2)} y={y(c)} height={H - padB - y(c)} fill="#D1D5DB" />)}
          {cand.map((c, i) => c > 0 && <rect key={`c${i}`} x={x(i * bw) + 2.5} width={Math.max(1, x(bw) - x(0) - 5)} y={y(c)} height={H - padB - y(c)} fill={threshold != null && (i + 0.5) * bw <= threshold ? SEED_COLOUR : KEPT_LIGHT}><title>{`d ${(i * bw).toFixed(1)}–${((i + 1) * bw).toFixed(1)}: ${c} matches · null ${nul[i]}`}</title></rect>)}
          <line x1={padL} x2={W - padR} y1={H - padB} y2={H - padB} stroke="var(--border-strong)" />
          {[0, 0.25, 0.5, 0.75, 1].map(f => { const t = +(dMax * f).toFixed(1); return <text key={f} x={x(t)} y={H - padB + 13} textAnchor={f === 0 ? 'start' : f === 1 ? 'end' : 'middle'} className="dsc-axis-t">{f === 1 ? `${t} d` : t}</text> })}
          {recommended != null && <line x1={x(recommended)} x2={x(recommended)} y1={H - padB - 8} y2={H - padB + 3} stroke="var(--green)" strokeWidth={2.5} />}
          {threshold != null ? (
            <>
              <g className="dsc-thresh" onPointerDown={e => { (e.currentTarget.ownerSVGElement as SVGSVGElement).setPointerCapture(e.pointerId); setDragging(true) }} style={{ cursor: 'ew-resize' }}
                tabIndex={0} role="slider" aria-label="threshold" aria-valuemin={0.1} aria-valuemax={dMax} aria-valuenow={threshold} data-testid="cut-threshold"
                onKeyDown={e => { if (e.key === 'ArrowLeft') { e.preventDefault(); onThreshold(Math.max(0.1, +(threshold - 0.1).toFixed(1))) } if (e.key === 'ArrowRight') { e.preventDefault(); onThreshold(Math.min(dMax, +(threshold + 0.1).toFixed(1))) } }}>
                <line x1={x(threshold)} x2={x(threshold)} y1={padT - 6} y2={H - padB} stroke={THRESH} strokeWidth={2} />
                <rect x={x(threshold) - 8} y={padT - 12} width={16} height={H - padT - padB + 12} fill="transparent" />
                <circle cx={x(threshold)} cy={padT - 8} r={6} fill="#fff" stroke={THRESH} strokeWidth={2} />
              </g>
              <text x={Math.min(x(threshold) + 10, W - 150)} y={padT - 4} className="dsc-axis-t" style={{ fill: THRESH, fontWeight: 600 }} data-testid="cut-label">{kept} kept · the null gives {fmtNull(nullKept)} per draw</text>
            </>
          ) : (
            <text x={padL + 4} y={padT - 4} className="dsc-axis-t" style={{ fill: 'var(--muted)', fontWeight: 600 }} data-testid="cut-label">
              no cut · nothing here is closer than the null gives · drag to choose one anyway
            </text>
          )}
          {/* with no cut the whole width is still draggable, so a researcher who
              wants to look past the null can */}
          {threshold == null && <rect x={padL} y={padT - 12} width={Math.max(0, W - padL - padR)} height={H - padT - padB + 12} fill="transparent"
            style={{ cursor: 'ew-resize' }} onPointerDown={e => { (e.currentTarget.ownerSVGElement as SVGSVGElement).setPointerCapture(e.pointerId); setDragging(true) }} data-testid="cut-threshold" />}
        </svg>
      )}
      {W === 0 && <div style={{ height: H }} />}
      <div className="dsc-legend-row small mono">
        <span><i className="sw" style={{ background: SEED_COLOUR }} />kept</span><span><i className="sw" style={{ background: KEPT_LIGHT }} />not kept</span>
        <span><i className="sw" style={{ background: '#D1D5DB' }} />surrogate</span><span><i className="sw line" style={{ background: 'var(--green)' }} />recommended</span>
        {/* the marker's rule, beside the marker (fixup-a item 12) */}
        {rule && <span className="muted" data-testid="cut-rule-legend">{rule.text}</span>}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ distance profile */
function DistanceProfile({ dx, seed, candidates, threshold }: { dx: Discovery; seed: SeedInfo; candidates: SeedMatch[]; threshold: number | null }) {
  const s = dx.scope!
  const [chQ, setChQ] = useQueryState('pch', 'CH4_A2')
  // the default was the fixture's '192.0-194.0', which clamped to an INVERTED
  // [192, 84] against a live 80-84 h section and asked the server for it
  const [viewQ, setViewQ] = useQueryState('view', '')
  const [judged, setJudged] = useState(true)
  const viewRef = useRef<HTMLButtonElement>(null)
  const [viewOpen, setViewOpen] = useState(false)
  const ch = s.channels.includes(chQ) ? chQ : s.channels[0]
  const view = parseView(viewQ, s.section)
  const prof = useSourced(() => getSeedProfile(seed.id, ch, view, candidates), [seed.id, ch, view.join(','), candidates.length])
  const [ref, size] = useSize<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const W = size.width, labelW = 70, padR = 8
  // with no cut every candidate is shown: the track is "where the matches are",
  // and an empty track over a search that found 132 of them would be a lie
  const inView = candidates.filter(c => c.channel === ch && (threshold == null || c.d <= threshold) && c.atH >= view[0] && c.atH <= view[1] && (judged || !c.judged))
  const x = (h: number) => labelW + ((h - view[0]) / (view[1] - view[0])) * (W - labelW - padR)
  const [selQ] = useQueryState('match', '')
  return (
    <section className="k-card dsc-profile" data-testid="distance-profile" aria-label="Distance profile">
      <div className="dsc-card-head">
        <h3>Distance profile</h3>
        <InfoTip title="Distance profile">One channel and one zoomed view at a time: the clean signal, MASS's distance at every position with the threshold, and a matches track beneath. Nothing is drawn on the signal itself.</InfoTip>
        <span className="muted small">one channel at a time</span>
        <span className="k-spacer" />
        <span className="dsc-legend-row small mono"><span><i className="sw" style={{ background: SEED_COLOUR }} />new match</span><span><i className="sw" style={{ background: 'var(--green)' }} />already judged</span></span>
        <Dropdown prefix="channel" value={ch} onChange={v => setChQ(v)} options={s.channels.map(c => ({ value: c, label: c }))} size="sm" testid="profile-channel" />
        <button ref={viewRef} type="button" className="dsc-section-chip" onClick={() => setViewOpen(o => !o)} data-testid="profile-view"><span className="muted">view</span> {view[0].toFixed(1)}–{view[1].toFixed(1)} h <Icon name="chevron-down" size={11} /></button>
        <ViewPopover open={viewOpen} onClose={() => setViewOpen(false)} anchorRef={viewRef} view={view} section={s.section} minW={0.1} maxW={24} onApply={v => setViewQ(`${v[0].toFixed(1)}-${v[1].toFixed(1)}`)} />
        <Checkbox checked={judged} onChange={setJudged} label="show already judged" testid="profile-show-judged" />
      </div>
      <div className="dsc-profile-body" ref={ref}>
        {prof.error ? <LoadFailed what="the distance profile" error={prof.error} onRetry={prof.reload} /> : !prof.data || W === 0 ? <Loading height={190} /> : (() => {
          const { signal, distance } = prof.data
          const n = signal.length
          const hAt = (i: number) => view[0] + (i / Math.max(1, n - 1)) * (view[1] - view[0])
          const [slo, shi] = padDomain(signal)
          const sy = (v: number) => 8 + (1 - (v - slo) / (shi - slo)) * 54
          // the domain is the returned array's, not a constant: real MASS distances
          // on this data run 16-52, and a fixed 7 pinned every one of them to the
          // same y and drew the profile as a dead straight line
          const dFin = distance.filter(Number.isFinite)
          const dLo = dFin.length ? Math.min(...dFin) : 0
          const dHi = Math.max(dFin.length ? Math.max(...dFin) : 1, threshold ?? 0) * 1.05
          const dy = (d: number) => 86 + ((Math.min(dHi, Math.max(dLo, d)) - dLo) / Math.max(1e-9, dHi - dLo)) * 56
          const step = Math.max(1, Math.floor(n / (W - labelW)))
          /* The distance array is SHORTER than the signal by m - 1: a profile has
           * one value per position, not per sample. Iterating to the signal's
           * length read past its end and drew NaN for the tail. Each line now
           * walks its own array and lifts the pen at a non-finite value. */
          const line = (vals: number[], yf: (v: number) => number) => {
            let d = '', pen = false
            for (let i = 0; i < vals.length; i += step) {
              if (!Number.isFinite(vals[i])) { pen = false; continue }
              d += `${pen ? 'L' : 'M'}${x(hAt(i)).toFixed(1)} ${yf(vals[i]).toFixed(1)}`
              pen = true
            }
            return d
          }
          const ticks = Array.from({ length: 5 }, (_, i) => view[0] + (i * (view[1] - view[0])) / 4)
          return (
            <svg width={W} height={196} role="img" aria-label={`distance profile on ${ch}, ${inView.length} matches in view`}
              onPointerMove={e => { const r = e.currentTarget.getBoundingClientRect(); const px = e.clientX - r.left; setHover(px >= labelW && px <= W - padR ? px : null) }} onPointerLeave={() => setHover(null)}>
              <text x={0} y={30} className="dsc-axis-t">signal</text>
              <text x={0} y={100} className="dsc-axis-t">distance</text>
              <text x={0} y={112} className="dsc-axis-t" style={{ fill: THRESH }}>{threshold == null ? `d ${dLo.toFixed(1)}–${dHi.toFixed(1)}` : `— d ${threshold.toFixed(1)}`}</text>
              <text x={0} y={168} className="dsc-axis-t">matches</text>
              <path d={line(signal, sy)} fill="none" stroke="var(--trace)" strokeWidth={1.1} />
              <path d={line(distance, dy)} fill="none" stroke={SEED_COLOUR} strokeWidth={1.1} />
              {threshold != null && <line x1={labelW} x2={W - padR} y1={dy(threshold)} y2={dy(threshold)} stroke={THRESH} strokeWidth={1.6} />}
              <rect x={labelW} y={160} width={W - labelW - padR} height={12} fill="#f3f4f6" rx={2} />
              {inView.map(c => { const cx0 = x(c.atH); return <rect key={c.id} x={cx0 - 22} y={160} width={44} height={12} rx={2} fill={c.judged ? 'var(--green)' : SEED_COLOUR} stroke={selQ === c.id ? 'var(--text)' : 'none'} strokeWidth={1.5} data-testid={`profile-match-${c.id}`}><title>{`${c.id} · d ${c.d.toFixed(2)} · ${c.atH.toFixed(2)} h${c.judged ? ' · already judged' : ''}`}</title></rect> })}
              <line x1={labelW} x2={W - padR} y1={180} y2={180} stroke="var(--border)" />
              {ticks.map((t, i) => <text key={i} x={x(t)} y={193} textAnchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'} className="dsc-axis-t">{i === 0 || i === 4 ? `${t.toFixed(1)} h` : t.toFixed(1)}</text>)}
              {hover != null && (() => { const h = view[0] + ((hover - labelW) / (W - labelW - padR)) * (view[1] - view[0]); const i = Math.round(((h - view[0]) / (view[1] - view[0])) * (n - 1)); return <g pointerEvents="none"><line x1={hover} x2={hover} y1={4} y2={176} stroke="var(--blue)" strokeDasharray="3 3" /><text x={Math.min(hover + 6, W - 130)} y={82} className="dsc-axis-t" style={{ fill: 'var(--text)', paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{h.toFixed(2)} h · d {distance[i]?.toFixed(2)}</text></g> })()}
            </svg>
          )
        })()}
      </div>
    </section>
  )
}
/** A view inside the section, or the section's own first hour.
 *
 *  The clamp used to be applied AFTER the only validity test, so a query
 *  outside the section inverted: '192.0-194.0' against a section of 80-84 h
 *  clamped to [192, 84] and the page asked the server for it. The clamped
 *  range is tested too, and an empty query opens on the section's start. */
export function parseView(q: string, section: [number, number]): [number, number] {
  const width = Math.min(1, Math.max(0.05, section[1] - section[0]))
  const fallback: [number, number] = [section[0], Math.min(section[1], section[0] + width)]
  const [a, b] = q.split('-').map(Number)
  if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) return fallback
  const lo = Math.max(section[0], Math.min(a, section[1]))
  const hi = Math.min(section[1], Math.max(b, section[0]))
  return hi > lo ? [lo, hi] : fallback
}
export function ViewPopover({ open, onClose, anchorRef, view, section, minW, maxW, onApply }: { open: boolean; onClose: () => void; anchorRef: React.RefObject<HTMLButtonElement | null>; view: [number, number]; section: [number, number]; minW: number; maxW: number; onApply: (v: [number, number]) => void }) {
  const [v, setV] = useState<[number, number]>(view)
  useEffect(() => { if (open) setV(view) }, [open]) // eslint-disable-line react-hooks/exhaustive-deps
  const w = v[1] - v[0]
  const err = v[0] < section[0] || v[1] > section[1] ? `view must lie inside the section ${section[0]}–${section[1]} h` : w < minW || w > maxW ? `view must be ${minW}–${maxW} h wide` : null
  return (
    <Popover open={open} onClose={onClose} anchorRef={anchorRef} placement="bottom-end" title="View" subtitle={`inside the section ${section[0]}–${section[1]} h`} width={340} testid="view-popover">
      <RangeSlider value={v} onChange={setV} min={section[0]} max={section[1]} step={0.1} format={x => `${x.toFixed(1)} h`} />
      <div className="row" style={{ gap: 8, marginTop: 8 }}>
        <NumberField value={+v[0].toFixed(1)} step={0.1} unit="h" width={110} onValid={n => setV([n, v[1]])} ariaLabel="view from" testid="view-from" />
        <span className="muted">to</span>
        <NumberField value={+v[1].toFixed(1)} step={0.1} unit="h" width={110} onValid={n => setV([v[0], n])} ariaLabel="view to" testid="view-to" />
      </div>
      {err && <div className="dsc-err" data-testid="view-error">{err}</div>}
      <div className="row end" style={{ gap: 8, marginTop: 10 }}><Button size="sm" onClick={onClose}>Cancel</Button><Button size="sm" variant="primary" disabled={!!err} disabledReason={err ?? undefined} onClick={() => { onApply(v); onClose() }} testid="view-apply">Apply</Button></div>
    </Popover>
  )
}

/* ------------------------------------------------------------------ matches */
function MatchesCard({ seed, matches, channels, note = null }: { seed: SeedInfo; matches: SeedMatch[]; channels: number; note?: string | null }) {
  const [pageQ, setPageQ] = useQueryState('mpage', '1')
  const [selQ, setSelQ] = useQueryState('match', '')
  const [, setChQ] = useQueryState('pch', 'CH4_A2')
  const [, setViewQ] = useQueryState('view', '192.0-194.0')
  const per = 8
  const pages = Math.max(1, Math.ceil(matches.length / per))
  const page = Math.min(pages, Math.max(1, parseInt(pageQ, 10) || 1))
  const shown = matches.slice((page - 1) * per, page * per)
  const yDomain = useMemo<[number, number]>(() => padDomain([...seed.trace, ...shown.flatMap(m => m.trace)]), [seed, shown])
  return (
    <section className="k-card dsc-matches" data-testid="matches-card" aria-label="Matches">
      <div className="dsc-card-head">
        <h3>{note ? `${matches.length} closest` : `${matches.length} matches`}</h3>
        {/* the note explains a truncation; it was passed in and never rendered,
            which left "12 closest" over a search that returned 132 */}
        {note && <span className="muted small" data-testid="matches-note">{note}</span>}
        <InfoTip title="Matches">Sorted by distance, eight at a time. Each card overlays the match (black) on the seed (purple) in mV on one shared scale. A green dot marks a match that already has a verdict — it will not be put to you twice.</InfoTip>
        <span className="muted small">{channels} channel{channels === 1 ? '' : 's'} · sorted by distance</span>
        <span className="k-spacer" />
        <Pager page={page} pageCount={pages} onPage={p => setPageQ(String(p))} format="range" total={matches.length} pageSize={per} label="page of matches" testid="matches-pager" />
        <span className="dsc-legend-row small mono"><span><i className="sw" style={{ background: SEED_COLOUR }} />seed</span><span><i className="sw line" style={{ background: 'var(--trace)' }} />match</span></span>
      </div>
      {matches.length === 0 ? <EmptyState size="sm" icon="search" title="No match under this threshold" caption="raise the threshold, or check what the null gives first" testid="matches-empty" /> : (
        <div className="dsc-match-grid" data-testid="match-grid">
          {shown.map(mt => (
            <button key={mt.id} type="button" className={cx('dsc-match', selQ === mt.id && 'on')} data-testid={`match-${mt.id}`}
              onClick={() => { setSelQ(mt.id); setChQ(mt.channel); setViewQ(`${Math.max(0, mt.atH - 1).toFixed(1)}-${(mt.atH + 1).toFixed(1)}`) }} title={`show ${mt.id} in the distance profile`}>
              <span className="row between mono small"><b>{mt.id}</b><span className="muted">d {mt.d.toFixed(2)}</span></span>
              <SeedThumb values={seed.trace} overlay={mt.trace} yDomain={yDomain} width={130} height={40} />
              <span className="mono small muted row" style={{ gap: 4 }}>{mt.judged && <span className="dot" style={{ background: 'var(--green)' }} title="already judged" />}{mt.channel} · {mt.atH.toFixed(1)} h</span>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

/* ------------------------------------------------------------------ apply bar */
function ApplyBar({ dx, draft, recommended, kept, seed, sim, onSave }: { dx: Discovery; draft: SeedDraft; recommended: SeedParams; kept: number | null; seed: SeedInfo | null; sim: ReturnType<typeof useSim>; onSave: () => void }) {
  // §7.6's apply bar diffs the parameters against the ones the last search ran with. `applied` is null
  // until the search has run once: then every parameter is unapplied, which is not "no changes".
  const label: Record<keyof SeedParams, string> = {
    algorithm: 'algorithm', windowSamples: 'window', windowS: 'window length', windowLocked: 'window locked',
    scaleBank: 'scale bank', exclusionSamples: 'exclusion samples', exclusionS: 'exclusion zone',
    exclusionNote: 'exclusion guard', specExclusionS: 'spec exclusion zone', exclusionSettable: 'exclusion settable',
    threshold: 'threshold', overlap: 'on overlap',
  }
  // the fields the parameter card sets; the rest of SeedParams is the server describing what it did
  // `exclusionS` is not in this list any more: the block takes no exclusion
  // parameter, so it can never differ from the applied search and an "exclusion
  // zone" chip in the apply bar would be a change nothing could make
  const settable: (keyof SeedParams)[] = ['algorithm', 'windowSamples', 'scaleBank', 'threshold', 'overlap']
  const applied = draft.applied
  const show = (v: SeedParams[keyof SeedParams]) => v == null ? 'none' : String(v)
  const changes = applied ? settable.filter(k => draft.params[k] !== applied[k]) : settable
  const diff = applied ? changes.map(k => `${label[k]} ${show(applied[k])} → ${show(draft.params[k])}`).join(' · ')
    : settable.map(k => `${label[k]} ${show(draft.params[k])}`).join(' · ')
  const finished = dx.runs.find(r => r.key === draft.label || r.key.startsWith(draft.label + '_'))
  const channels = dx.scope?.channels ?? []
  const noSeedReason = !seed ? 'pick a seed first — no span selected' : null
  /* §7.6's apply bar: "A run seed search becomes a normal run row." It is a
   * real run — POST /api/discovery/seed/run starts a sweep over the scope and
   * the row arrives from the server on the next read of the runs list. The
   * progress strip still comes from `sim`, because the page has no SSE
   * subscription yet (reported in 04-discovery.md, "Left"). */
  const run = () => {
    if (!seed || !dx.scope) return
    sim.start({ steps: stepsFor(channels), stepMs: 800 })
    runDiscoverySeedSearch({
      seedId: seed.id, channels, t0: dx.scope.section[0], t1: dx.scope.section[1],
      k: SEED_K, cut: draft.params.threshold ?? undefined, label: draft.label,
    }).then(() => dx.reload())
      .catch(e => { sim.reset?.(); console.error('the seed search could not start', e) })
  }
  return (
    <section className="k-card dsc-apply" data-testid="apply-bar" aria-label="Apply">
      {sim.busy ? (
        <>
          <ProgressBar value={sim.fraction} width={180} labelPosition="none" testid="seed-progress" />
          <b>{sim.status === 'queued' ? 'queued · local' : `running · ${sim.steps[sim.step]} (${sim.step + 1} of ${sim.steps.length})`}</b>
          <span className="k-spacer" />
          <Button onClick={() => { sim.cancel(); recordDemoWrite('discovery', 'cancel-seed-search', { run: draft.key }) }} testid="seed-cancel">Cancel</Button>
        </>
      ) : sim.status === 'failed' ? (
        <>
          <span className="dot" style={{ background: 'var(--red)', width: 9, height: 9 }} />
          <b className="red" data-testid="seed-failed">{sim.error}</b>
          <span className="k-spacer" />
          <Button onClick={onSave} icon="save">Save as template</Button>
          <Button variant="primary" icon="refresh" onClick={run} testid="seed-retry">Retry</Button>
        </>
      ) : (
        <>
          <span className="dot" style={{ background: finished && changes.length === 0 ? 'var(--green)' : 'var(--amber)', width: 9, height: 9 }} />
          {finished && changes.length === 0
            ? <><b data-testid="seed-done">{draft.label} · {kept == null ? 'no cut chosen — nothing kept yet' : `${kept} found`} · done {finished.doneAt}</b><Button variant="link" size="sm" icon="external" onClick={() => navigate(`discovery/runs?run=${draft.key}`)} testid="seed-open-runs">Open in Runs</Button></>
            : <><b data-testid="apply-state">{finished ? 'run' : 'draft'} · {!applied ? 'never run — no parameters applied yet' : changes.length === 0 ? 'no unapplied changes' : `${changes.length} unapplied change${changes.length === 1 ? '' : 's'}`}</b><span className="muted small mono">{diff ? `${diff} · ` : ''}preview counts update live</span></>}
          {sim.status === 'cancelled' && <span className="muted small">last search cancelled · nothing written</span>}
          <span className="k-spacer" />
          <Button icon="save" onClick={onSave} testid="save-as-template">Save as template</Button>
          <Button variant="primary" icon="play" onClick={run} disabled={!!noSeedReason || (!!finished && changes.length === 0)} disabledReason={noSeedReason ?? 'already run with these settings'} testid="run-seed-search">Run seed search</Button>
        </>
      )}
    </section>
  )
}

/* ------------------------------------------------------------------ save as template */
const TPL_RE = /^[a-z0-9_]{3,40}$/
function SaveTemplateModal({ open, onClose, draft, seed }: { open: boolean; onClose: () => void; draft: SeedDraft; seed: SeedInfo | null }) {
  const tpls = useSourced(getTemplates, [])
  const [saved, setSaved] = useDemoState<string[]>('discovery.saved-templates', () => [])
  const [name, setName] = useState(draft.label)
  const toast = useToast()
  const taken = (tpls.data ?? []).some(t => t.name === name) || saved.includes(name)
  const err = !name ? 'a template needs a name' : !TPL_RE.test(name) ? 'lower-case letters, digits and _ only (3–40)' : taken ? `a template called ${name} exists` : null
  const save = () => {
    setSaved([...saved, name])
    recordDemoWrite('library', 'save-template', { name, from: `Discovery seed search ${draft.key}`, bind: draft.bind, seed: seed?.id })
    toast.push({ text: `Saved ${name} · Library › Templates`, action: { label: 'Open', onClick: () => navigate('library/templates') } })
    onClose()
  }
  return (
    <Modal open={open} onClose={onClose} title="Save as template" subtitle="a seed search saved is a template with badge seed" size="md" testid="save-template-modal"
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon="save" onClick={save} disabled={!!err} disabledReason={err ?? undefined} testid="save-template-confirm">Save template</Button></>}>
      <div className="dsc-save-form">
        <label className="small muted" htmlFor="tpl-name">name</label>
        <TextField id="tpl-name" value={name} onChange={setName} invalid={!!err} block onEnter={() => { if (!err) save() }} testid="save-template-name" />
        {err && <span className="dsc-err" data-testid="save-template-error">{err}</span>}
        <div className="dsc-save-summary mono small">
          <span><span className="muted">seed</span> {seed ? seed.title : 'Explore selection'}{seed && ` · hash ${seed.hash}`}</span>
          <span><span className="muted">bind</span> {draft.bind === 'carry' ? 'carry · this exemplar travels with the template' : 'rebind · asks for an exemplar when applied'}</span>
          <span><span className="muted">signature</span> Signal + exemplar → SpanSet</span>
          <span><span className="muted">parameters</span> MASS · window {seed?.samples ?? 21} samples · exclusion {draft.params.exclusionS} s · {draft.params.threshold != null ? `d ≤ ${draft.params.threshold}` : 'no cut chosen'} ·{draft.params.overlap === 'lowest' ? 'keep lowest distance' : draft.params.overlap === 'first' ? 'keep first' : 'keep all'}</span>
        </div>
      </div>
    </Modal>
  )
}
