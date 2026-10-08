/* discovery.seed — frame discovery-2. A seed search set up in place as a draft run (§7.6, P17): seed source and
 * provenance, carry / rebind, parameters with the where-to-cut histogram (null behind, draggable threshold), the distance
 * profile on one channel, match cards sorted by distance, and the apply bar (Save as template · Run seed search). */
import { axisUnit } from '../charts/units'
import { DatasetName } from '../naming'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Button, Callout, Checkbox, CodeBlock, DisabledReason, Dropdown, EmptyState, Icon, InfoTip, Modal, NumberField, Pager, Popover, ProgressBar, RadioCards, RangeSlider,
  Seg, SelectField, Slider, TextField, cx, forceSim, recordDemoWrite, useDemoState, useQueryState, useSim,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { ApiError, cancelJob, postDiscoverySeedImport, postDiscoverySeedSlurm, putDiscoverySeedDraft, runDiscoverySeedSearchOnce, saveDiscoverySeedTemplate, type CutRule, type DiscSeedEstimate, type DiscSeedSlurm } from '../api'
import { useSize } from '../charts/useSize'
import {
  fmtSeconds, getSeedEstimate, getSeedPage, getSeedProfile, getSeedResults, getSeedSetup, getTemplates, saveSeedDraft, type SeedProgress, type DiscoveryRun, type SeedDraft, type SeedInfo, type SeedMatch, type SeedParams, type SeedResults, type SeedSource,
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
  /* `?seed=` / `?entry=` open that seed and make it the draft on the session row (fixup-y): Review's
   * *Seed search in Discovery →* links here with `?entry=N`, and picking a seed in the picker sets
   * `?seed=`, so a reload stays on the seed that was chosen. */
  const [seedQ, setSeedQ] = useQueryState('seed', '')
  const [entryQ, setEntryQ] = useQueryState('entry', '')
  const setup = useSourced(() => getSeedSetup({ seed: seedQ || undefined, entry: entryQ ? Number(entryQ) : undefined }), [seedQ, entryQ])
  const [draftStore, setDraftStore] = useDemoState<SeedDraft | null>('discovery.seed.draft', () => null)
  // the in-memory draft is this seed's only: a cut is read off one seed's distances
  const draft = draftStore && draftStore.seedId === setup.data?.draft.seedId ? draftStore : setup.data?.draft ?? null
  const [sourceQ, setSourceQ] = useQueryState<SeedSource | ''>('source', '')
  const [stateQ] = useQueryState('state', '')
  const [modal, setModal] = useQueryState('modal', '')
  const sim = useSim(SIM_ID)
  const toast = useToast()

  /* A dragged cut was lost on reload: the draft lived only in this tab's memory. It is written to the
   * session row too (PUT /api/discovery/seed/draft), a beat after the last change. */
  const saveTimer = useRef<number | null>(null)
  const persist = (d: SeedDraft) => {
    if (saveTimer.current) window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(() => { saveSeedDraft(d.seedId, d.params).catch(e => console.error('the seed draft could not be saved', e)) }, 400)
  }
  const setDraft = (patch: Partial<SeedDraft>) => { if (draft) setDraftStore({ ...draft, ...patch }) }
  const setParams = (patch: Partial<SeedParams>) => {
    if (!draft) return
    const next = { ...draft, params: { ...draft.params, ...patch } }
    setDraftStore(next)
    persist(next)
  }
  const pickSeed = (id: string) => { setEntryQ(null); setSeedQ(id); setSourceQ(null) }
  /* The seed is the draft's own — `setup.seed` — whether or not it is on any page of the picker. The old
   * line took the first seed of the `?source=` kind, so a seed chosen in *change seed* never took effect. */
  const seed: SeedInfo | null = setup.data?.seed ?? null
  const tab: SeedSource = (sourceQ || seed?.source || 'library') as SeedSource
  const channels = dx.scope?.channels ?? []
  const noResults: SeedResults = { candidates: [], nullDistances: [], recommendedCut: null, cutRule: null, nullDraws: 0, nullMethod: null, nullSupported: true, nullReason: null }
  /* fixup-v: the scale bank. Its lengths are Settings' one key (`analysis-defaults · seed.scale_bank`), served on
   * the setup; choosing it searches the seed resampled to each length, and the result, the null and the run are
   * all of that search. */
  const bank = setup.data?.recommended.bank ?? null
  const bankOn = !!bank && draft?.params.scaleBank === 'bank'
  const bankQ = bankOn ? { scales: bank!.scales, overlap: draft!.params.overlap === 'first' || draft!.params.overlap === 'all' ? draft!.params.overlap : 'lowest' } : null
  /* fixup-AD: the exclusion zone is the block's own parameter now (a fraction of m, default m/2, Round 11); the slider
   * holds seconds, the search takes the fraction, and the result's key and the run's recipe carry it */
  const exclusionQ = draft && (draft.params.windowS ?? 0) > 0 && draft.params.exclusionSettable !== false
    ? Math.round((draft.params.exclusionS / (draft.params.windowS ?? 1)) * 1000) / 1000 : null
  // the preview's own progress while it runs (the job's done/total, elapsed and remaining), null once it is in
  const [progress, setProgress] = useState<SeedProgress | null>(null)
  // only the newest loader reports progress: an older one (another zone, scope or seed) is told to stop
  const loaderToken = useRef(0)
  const results = useSourced(() => {
    const mine = ++loaderToken.current
    setProgress(null)
    return seed ? getSeedResults(seed.id, channels, bankQ, exclusionQ, dx.scope?.section, p => { if (loaderToken.current === mine) setProgress(p) }, () => loaderToken.current === mine)
      : Promise.resolve({ data: noResults, source: 'demo' as const })
  }, [seed?.id, channels.join(','), dx.scope?.section.join(','), bankQ?.scales.join(','), bankQ?.overlap, exclusionQ])
  // before the button: what the preview and the run will cost on this scope
  const estimate = useSourced(() => dx.scope ? getSeedEstimate(channels, dx.scope.section) : Promise.resolve({ data: null, source: 'demo' as const }), [channels.join(','), dx.scope?.section.join(',')])

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
  /* One cut, one figure: the parameter card printed the null at the RECOMMENDED cut beside the
   * histogram's figure at the cut in force — "chosen 14.5 · the null gives 0 per draw" beside "5 kept
   * · the null gives 6.3 per draw" (fixup-y). Both read this one number now. */
  const nullKept = perDraw(threshold)

  /* The Seed page's own run is found by its SEED and its CUT, which the server carries on the row
   * (fixup-y) — never by the label, which three runs of one seed all shared. */
  const sameCut = (a: number | null | undefined, b: number | null) => (a ?? null) == null ? b == null : b != null && Math.abs((a as number) - b) < 1e-9
  const sameBank = (a: number[] | null | undefined) => (a ?? []).join(',') === (bankQ?.scales ?? []).join(',')
  /* A run that failed, was cancelled or was discarded is not "this search, already run": the server starts a
   * new one for it, so the button must not refuse. Two runs lost in a server restart held it shut for a day. */
  const dead = (r: DiscoveryRun) => r.status === 'failed' || r.status === 'cancelled' || r.status === 'superseded'
  const finished = seed ? dx.runs.find(r => r.kind === 'seed' && !dead(r) && r.seedId === seed.id && sameCut(r.cut, threshold) && sameBank(r.scales)) ?? null : null

  /* The run row is the server's: the old version invented one client-side,
   * keyed by the draft and carrying `template: 'seed_F03_native_2'`, a name no
   * templates row has. When the sweep lands, re-read the runs list and mark the
   * draft's parameters applied. */
  const [lastRun, setLastRun] = useState<{ key: string; label: string } | null>(null)
  const [startedAt, setStartedAt] = useState<number | null>(null)
  /* The run started from this page is the server's row (the session re-reads the runs list every 2 s while one
   * runs), so its progress bar is the sweep's own and not a simulated strip. When it lands, the draft's parameters
   * are applied and the toast says so. */
  const live = lastRun ? dx.runs.find(r => r.key === lastRun.key) ?? null : null
  const wasRunning = useRef(false)
  useEffect(() => {
    const running = !!live && (live.status === 'running' || live.status === 'queued')
    if (wasRunning.current && !running && live && draft) {
      dx.reload()
      setDraftStore({ ...draft, applied: { ...draft.params } })
      if (live.status === 'done') toast.push({ text: `${live.label} finished · ${live.found ?? 0} found`, action: { label: 'Open in Runs', onClick: () => navigate(`discovery/runs?run=${encodeURIComponent(live.key)}`) } })
      else if (live.status === 'failed') toast.push({ text: `${live.label} failed · ${live.error ?? 'see Runs'}` })
    }
    wasRunning.current = running
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live?.status])
  /* Only a search that finishes while the page is open says so: the simulated strip stays `done` across
   * navigation, and remounting the page toasted "seed c61395 finished · 0 matches" for a run long done,
   * before its matches had been read (fixup-y). */
  const wasBusy = useRef(sim.busy)
  useEffect(() => {
    const finishedHere = wasBusy.current && sim.status === 'done'
    wasBusy.current = sim.busy
    if (!finishedHere && stateQ !== 'done') return
    if (sim.status !== 'done' || !draft) return
    dx.reload()
    setDraftStore({ ...draft, applied: { ...draft.params } })
    const key = lastRun?.key ?? finished?.key
    if (stateQ !== 'done') toast.push({ text: `${lastRun?.label ?? draft.label} finished · ${kept.length} matches`, action: { label: 'Open in Runs', onClick: () => navigate(key ? `discovery/runs?run=${encodeURIComponent(key)}` : 'discovery/runs') } })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sim.status, draft?.key])

  const draftRow = draft && !finished ? <DraftRow draft={draft} seed={seed} sim={sim} /> : null

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
              <DiscoveryToolbar dx={dx} right={<><NullChip dx={dx} /><CostChip dx={dx} label={estimate.data
                ? <><b>≈ {fmtSeconds(estimate.data.run.seconds)}</b> <span className="muted">a run · {channels.length} ch × {(dx.scope.section[1] - dx.scope.section[0]).toFixed(1)} h × {estimate.data.run.draws} draws{estimate.data.run.measured ? '' : ' · assumed rate'}</span></>
                : <><b>≈ ?</b> <span className="muted">estimating</span></>} /><HistoryButton dx={dx} /></>} />
              <ScopeCard dx={dx} />
              {!dx.recording?.heldOut && (
                <div className="dsc-cols">
                  <RunsCard dx={dx} mode="seed" selected={finished?.key} draft={draftRow} onAddTemplate={() => navigate('discovery/runs?modal=add-template')} />
                  <div className="dsc-right">
                    <div className="dsc-seed-top">
                      <SeedCard draft={draft} seed={seed} tab={tab} dx={dx} onTab={s => setSourceQ(s === seed?.source ? null : s)}
                        onSeed={pickSeed} onBind={b => { setDraft({ bind: b }); recordDemoWrite('discovery', 'seed-bind', { bind: b }) }} />
                      <ParamsCard draft={draft} recommended={setup.data!.recommended} seed={seed} setParams={setParams} results={results.data} kept={kept.length} nullKept={nullKept} cut={threshold} cutIsRecommended={cutIsRecommended} />
                    </div>
                    {/* while a new seed's search runs, the previous seed's (or the empty) result is still in
                        hand — reading "No matches" off it said the search found nothing before it had run */}
                    {!seed ? null : results.error ? <LoadFailed what="seed matches" error={results.error} onRetry={results.reload} /> : !results.data || results.loading ? <SearchProgress progress={progress} estimate={estimate.data} /> : (
                      <>
                        {results.data.candidates.length === 0
                          ? <section className="k-card" data-testid="no-cut"><EmptyState size="sm" icon="bar-chart" title="No matches"
                            caption="the search returned nothing on this scope" /></section>
                          : <>
                            <DistanceProfile dx={dx} seed={seed} candidates={results.data.candidates} threshold={threshold} />
                            {/* with no cut nothing is KEPT, but the closest matches are still what
                                the researcher is looking at — hiding them makes "nothing beats the
                                null" look like "the search did not run" */}
                            <MatchesCard seed={seed} matches={threshold == null ? results.data.candidates.slice(0, 12) : kept} nullDraws={results.data.nullDraws} hours={dx.scope ? dx.scope.section[1] - dx.scope.section[0] : null}
                              channels={channels.length}
                              note={threshold == null ? `no cut: none of the ${results.data.candidates.length} matches is closer than the null gives — these are the closest` : null} />
                          </>}
                      </>
                    )}
                    <ApplyBar dx={dx} draft={draft} kept={threshold == null ? null : kept.length} cut={threshold} finished={finished} seed={seed} sim={sim} bank={bankQ}
                      estimate={estimate.data} live={live} startedAt={startedAt} exclusion={exclusionQ}
                      onStarted={r => { setLastRun(r); setStartedAt(Date.now()) }} onSave={() => setModal('save-template')}
                      onSlurm={() => setModal('slurm')} onImported={() => { results.reload(); dx.reload() }} />
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
      {draft && seed && dx.scope && <SeedSlurmModal open={modal === 'slurm'} onClose={() => setModal(null)} dx={dx} draft={draft} seed={seed} cut={threshold} bank={bankQ} exclusion={exclusionQ}
        estimate={estimate.data} onImported={r => { setLastRun({ key: r.run_key, label: r.label }); setStartedAt(Date.now()); results.reload(); dx.reload() }} />}
      {draft && <SaveTemplateModal open={modal === 'save-template'} onClose={() => setModal(null)} draft={draft} seed={seed} cut={threshold} bank={bankQ} exclusion={exclusionQ}
        onSaved={name => { setDraft({ label: name }); putDiscoverySeedDraft({ seedId: draft.seedId, label: name }).catch(e => console.error('the draft could not be renamed', e)) }} />}
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
          <span className="dsc-run-meta"><span className="k-badge t-amber">draft</span><span className="muted">{seed ? `${seed.title} · ${seed.role}` : 'no seed'} · MASS</span></span>
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
const SOURCE_KIND: Record<string, string> = { review: 'promoted in Review', annotation: 'from an annotation', event_store: 'machine-extracted' }
function SeedCard({ draft, seed, tab, dx, onTab, onSeed, onBind }: {
  draft: SeedDraft; seed: SeedInfo | null; tab: SeedSource; dx: Discovery; onTab: (s: SeedSource) => void; onSeed: (id: string) => void
  onBind: (b: 'carry' | 'rebind') => void
}) {
  const changeRef = useRef<HTMLButtonElement>(null)
  const [popQ, setPopQ] = useQueryState('popover', '')
  const yDomain = useMemo<[number, number]>(() => seed ? padDomain(seed.trace) : [-0.4, 0.1], [seed])
  const showing = !!seed && seed.source === tab
  return (
    <section className="k-card dsc-seed" data-testid="seed-card" aria-label="Seed">
      <div className="dsc-card-head">
        <h3>Seed</h3>
        <InfoTip title="Seed">The shape to search for. Its window is its native length; the card shows provenance — recording, channel, samples and content hash — so a saved template can say exactly what it carried. A Library exemplar names its entry; the researcher's own (promoted in Review, or from an annotation) are listed first.</InfoTip>
        <span className="muted small">type Signal span</span>
      </div>
      <div className="dsc-seed-body">
        <Seg value={tab} onChange={onTab} size="sm" testid="seed-source" options={[{ value: 'library', label: 'Library exemplar' }, { value: 'explore', label: 'Explore selection' }, { value: 'medoid', label: 'Family medoid' }]} />
        {showing && seed ? (
          <div className="dsc-seed-row" data-testid="seed-provenance" data-seed-id={seed.id} data-entry-id={seed.entryId ?? ''}>
            <div className="dsc-seed-thumb"><SeedThumb values={seed.trace} yDomain={yDomain} unit={seed.unit} /><span className="small muted mono">{seed.samples} samples · {seed.lengthS} s</span></div>
            <div className="dsc-seed-kv">
              <b data-testid="seed-title">{seed.title}</b>
              <span>{seed.familyLine}</span>
              <span><DatasetName file={seed.recordingFile ?? seed.recording} /> · {seed.channel}</span>
              <span>{seed.startH.toFixed(2)} h · {seed.lengthS} s · hash {seed.hash}</span>
              <button ref={changeRef} type="button" className="dsc-inline-link blue" onClick={() => setPopQ(popQ === 'change-seed' ? null : 'change-seed')} data-testid="change-seed">change seed ›</button>
              <Popover open={popQ === 'change-seed'} onClose={() => setPopQ(null)} anchorRef={changeRef} title="Change seed" subtitle={seed.role} width={420} testid="change-seed-popover">
                <SeedPicker source={tab} dx={dx} currentId={seed.id} onPick={id => { onSeed(id); setPopQ(null) }} />
              </Popover>
            </div>
          </div>
        ) : <SeedPicker source={tab} dx={dx} currentId={seed?.id ?? null} onPick={onSeed} inline />}
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

/** §7.6's seed sources, paged and filtered (fixup-y). The Library half reaches every entry — it was the
 *  first 24 of 3,603 rows, all machine-extracted — with the researcher's own exemplars first; the
 *  Explore half is the spans taken for Review in Explore › Signal, newest first. */
const PICK_PER = 8
function SeedPicker({ source, dx, currentId, onPick, inline }: { source: SeedSource; dx: Discovery; currentId: string | null; onPick: (id: string) => void; inline?: boolean }) {
  const [kind, setKind] = useState<string>('')
  const [family, setFamily] = useState('')
  const [recording, setRecording] = useState('')
  const [channel, setChannel] = useState('')
  const [page, setPage] = useState(1)
  useEffect(() => { setPage(1) }, [source, kind, family, recording, channel])
  const q = { source, kind: kind || undefined, family: family || undefined, recording: recording || undefined, channel: channel || undefined, offset: (page - 1) * PICK_PER, limit: PICK_PER }
  const data = useSourced(() => getSeedPage(q), [source, kind, family, recording, channel, page])
  const p = data.data
  const rec = dx.recordings.find(r => r.file === recording) ?? null
  const channelOptions = rec ? rec.channels : [...new Set(dx.recordings.filter(r => !r.heldOut).flatMap(r => r.channels))]
  const pages = Math.max(1, Math.ceil((p?.total ?? 0) / PICK_PER))
  return (
    <div className={cx('dsc-seed-picker', inline && 'inline')} data-testid={`seed-picker-${source}`}>
      {source === 'library' && (
        <div className="row wrap" style={{ gap: 6 }}>
          <Seg value={kind} onChange={setKind} size="sm" testid="seed-filter-kind" options={[
            { value: '', label: `all${p ? ` ${fmtCount(p.counts.library)}` : ''}` },
            { value: 'review', label: `review ${p?.kinds.review ?? 0}` },
            { value: 'annotation', label: `annotation ${p?.kinds.annotation ?? 0}` },
            { value: 'event_store', label: `machine ${fmtCount(p?.kinds.event_store ?? 0)}` },
          ]} />
          <Dropdown size="sm" prefix="family" value={family} onChange={setFamily} testid="seed-filter-family"
            options={[{ value: '', label: 'any' }, ...(p?.families ?? []).map(f => ({ value: f, label: f }))]} />
        </div>
      )}
      {source !== 'medoid' && (
        <div className="row wrap" style={{ gap: 6 }}>
          <Dropdown size="sm" prefix="recording" value={recording} onChange={v => { setRecording(v); setChannel('') }} testid="seed-filter-recording"
            options={[{ value: '', label: 'any' }, ...dx.recordings.filter(r => !r.heldOut).map(r => ({ value: r.file, label: r.label }))]} />
          <Dropdown size="sm" prefix="channel" value={channel} onChange={setChannel} testid="seed-filter-channel"
            options={[{ value: '', label: 'any' }, ...channelOptions.map(c => ({ value: c, label: c }))]} />
        </div>
      )}
      {data.error ? <LoadFailed what="the seeds" error={data.error} onRetry={data.reload} />
        : !p ? <Loading height={120} />
          : p.seeds.length === 0 ? (source === 'explore'
            ? <EmptyState size="sm" icon="scan" title="No span taken in Explore" caption="brush a span on Explore › Signal and press Take span for Review; it is offered here at once" testid="seed-explore-empty"
              action={<Button size="sm" icon="external" onClick={() => navigate('explore/corpus')}>Select a span in Explore</Button>} />
            : <EmptyState size="sm" icon="search" title="No seed under these filters" caption={`${fmtCount(p.counts.library ?? 0)} Library entries in all`} testid="seed-picker-empty" />)
            : (
              <>
                <div className="dsc-seed-options" data-testid="seed-options">
                  {p.seeds.map(s => (
                    <button key={s.id} type="button" className={cx('dsc-seed-option', s.id === currentId && 'on')} onClick={() => onPick(s.id)} data-testid={`seed-option-${s.id}`} data-source-kind={s.sourceKind ?? ''}>
                      <SeedThumb values={s.trace} yDomain={padDomain(s.trace)} width={54} height={30} />
                      <span>
                        <b>{s.title}</b>{s.sourceKind && s.sourceKind !== 'event_store' && <span className="k-badge t-green" style={{ marginLeft: 6 }}>{SOURCE_KIND[s.sourceKind] ?? s.sourceKind}</span>}
                        <span className="muted small mono">{s.recordingLabel ?? s.recording} · {s.channel} · {s.startH.toFixed(2)} h · {s.samples} samples{s.family ? ` · ${s.family}` : ''}</span>
                      </span>
                    </button>
                  ))}
                </div>
                {source !== 'medoid' && <Pager page={page} pageCount={pages} onPage={setPage} format="range" total={p.total} pageSize={PICK_PER} label="page of seeds" testid="seed-picker-pager" />}
              </>
            )}
    </div>
  )
}
const fmtCount = (n: number | undefined) => (n ?? 0).toLocaleString('en-US')
/** A domain over the FINITE values. The wire spells a non-finite sample null
 *  and the adapter turns it back into NaN, and Math.min over an array holding
 *  one NaN is NaN — which makes every y NaN and the browser reject the path. */
function padDomain(values: number[]): [number, number] {
  const f = values.filter(Number.isFinite)
  if (!f.length) return [-1, 1]
  const lo = Math.min(...f), hi = Math.max(...f), m = (hi - lo) * 0.12 || 0.05
  return [lo - m, hi + m]
}
function SeedThumb({ values, yDomain, width = 132, height = 78, overlay, unit }: { values: number[]; yDomain: [number, number]; width?: number; height?: number; overlay?: number[]; unit?: 'mV' | null }) {
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
      {padL > 2 && <><text x={padL - 3} y={10} textAnchor="end" className="dsc-axis-t">{fmtTick(yDomain[1])}</text><text x={padL - 3} y={height - 3} textAnchor="end" className="dsc-axis-t">{fmtTick(yDomain[0])}</text><text x={padL - 3} y={height / 2 + 3} textAnchor="end" className="dsc-axis-t">{axisUnit(unit)}</text></>}
      {overlay && <path d={path(overlay)} fill="none" stroke="var(--trace)" strokeWidth={1.1} />}
      <path d={path(values)} fill="none" stroke={SEED_COLOUR} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  )
}
/** A trace less its own mean over the finite samples; non-finite samples stay NaN (the pen lifts there). */
function centred(values: number[]): number[] {
  const f = values.filter(Number.isFinite)
  if (!f.length) return values
  const mean = f.reduce((a, b) => a + b, 0) / f.length
  return values.map(v => Number.isFinite(v) ? v - mean : NaN)
}
const fmtTick = (v: number) => `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(2)}`

/* ------------------------------------------------------------------ parameters + where to cut */
function ParamsCard({ draft, recommended, seed, setParams, results, kept, nullKept, cut, cutIsRecommended }: {
  draft: SeedDraft; recommended: SeedParams; seed: SeedInfo | null; setParams: (p: Partial<SeedParams>) => void
  results: { candidates: SeedMatch[]; nullDistances: number[]; cutRule?: CutRule | null; nullByScale?: SeedResults['nullByScale'] } | null; kept: number; nullKept: number
  /** The cut in force: the researcher's if they chose one, else the null's own
   *  recommendation. `recommended.threshold` is always null — the parameter card
   *  cannot know a cut before the search has drawn a null. */
  cut: number | null; cutIsRecommended: boolean
}) {
  const p = draft.params
  /* the slider and the field reach the data: z-normalised MASS distances on this data run to 70-odd, and a
   * ceiling of 8 could not express any cut the histogram showed. `closest` is the cut that keeps the
   * single closest match — a start when the null gives none (the researcher can still ask). */
  const dMax = Math.max(8, Math.ceil(Math.max(0, ...(results?.candidates ?? []).map(c => c.d), ...(results?.nullDistances ?? [])) * 1.05))
  const closest = +(Math.ceil(Math.min(Infinity, ...(results?.candidates ?? []).map(c => c.d)) * 10) / 10).toFixed(1)
  const m = seed?.samples ?? 21
  const half = Math.round(m / 2 - 0.01)
  const bank = recommended.bank ?? null
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
        <ParamField label="scale bank" info={`A bank searches stretched copies of the seed: the seed resampled to each length, MASS at each, every distance put on the native length's footing (d·√(m/L)) so one cut means one thing, and matches of two lengths that overlap reduced by the overlap policy below. The null is drawn per length. The lengths are Settings › Analysis defaults${bank ? ` (${bank.settings})` : ''}.`}>
          <Dropdown value={p.scaleBank === 'bank' && bank ? 'bank' : 'none'} onChange={v => setParams({ scaleBank: v })} block testid="param-scale-bank"
            options={[{ value: 'none', label: 'none · native length' }, { value: 'bank', label: bank ? `${bank.label} (${bank.lengths.join(' · ')} samples)` : 'scale bank', disabled: !bank, reason: 'no scale bank is set in Settings › Analysis defaults' }]} />
        </ParamField>
        {/* fixup-AD: the block takes the zone (a fraction of m, default m/2) and passes it to stumpy.match, so the
            figure here IS the guard the search runs under, and moving the slider changes the search, its result
            key and the run's recipe. Until 2026-10-05 the block took none and stumpy ran its own m/4. */}
        <ParamField label="exclusion zone" info={p.exclusionNote ?? 'Matches closer than this to a better match are dropped. m/2 is the trivial-match guard.'}
          aside={<b className="mono" data-testid="exclusion-figure">{p.exclusionSettable === false ? `m/4 = ${p.exclusionS} s` : p.exclusionS === (p.specExclusionS ?? half) ? `m/2 = ${p.exclusionS} s` : `${p.exclusionS} s`}</b>}>
          <Slider value={p.exclusionS} onChange={v => setParams({ exclusionS: v })} min={0} max={m} step={1} showValue={false} testid="param-exclusion" ariaLabel="exclusion zone"
            disabled={p.exclusionSettable === false} disabledReason={p.exclusionSettable === false ? 'detection.seed_matches takes no exclusion parameter — stumpy.match applies its own m/4' : undefined} />
          {/* one line here, the whole sentence in the info-tip: the note runs to
              three sentences and printed in full it crowded the histogram */}
          <span className={cx('small mono', p.exclusionSettable === false ? 'muted' : p.exclusionS === half ? 'green' : p.exclusionS < half ? 'amber' : 'muted')} data-testid="exclusion-caption">
            {p.exclusionSettable === false
              ? `stumpy.match's own guard · §7.6 asks m/2 (${p.specExclusionS ?? half} s)`
              : p.exclusionS === (p.specExclusionS ?? half) ? 'm/2 = the trivial-match guard (§7.6)' : p.exclusionS < (p.specExclusionS ?? half) ? 'below m/2 lets trivial matches through' : 'wider than m/2 · fewer neighbouring matches'}
          </span>
        </ParamField>
        {/* the cut is computed from the null distribution, so there is none until a search has drawn one */}
        <ParamField label="match threshold" info="Keep matches with distance d at or below this. The green tick is the recommended cut: where the null starts to keep matches." aside={
          p.threshold != null
            ? <NumberField value={p.threshold} min={0.1} max={dMax} step={0.1} width={78} onValid={v => { setParams({ threshold: +v.toFixed(1) }); setThrRaw(null) }} onChange={(_, r) => setThrRaw(r ?? null)} testid="param-threshold-number" ariaLabel="match threshold d" />
            : <span className="muted small mono">no cut</span>}>
          {p.threshold != null ? (
            <>
              <Slider value={cut ?? 0} onChange={v => setParams({ threshold: +v.toFixed(1) })} min={0} max={dMax} step={0.1} showValue={false} marks={cut != null ? [{ value: cut, label: '' }] : []} testid="param-threshold" ariaLabel="match threshold" />
              <span className="small mono green">{thrRaw ? <span className="dsc-err">{thrRaw}</span> : cut != null ? <><span data-testid="param-cut-line">{cutIsRecommended ? 'recommended' : 'chosen'} {cut} · {kept} kept · the null gives {fmtNull(nullKept)} per draw</span></> : 'no recommended cut yet — it is read off the null distribution'}</span>
              {/* a statistic whose rule is unstated cannot be falsified (fixup-a item 12) */}
              {results?.cutRule && <span className="small mono muted" data-testid="cut-rule">{results.cutRule.text}</span>}
            </>
          ) : <span className="small mono muted row" style={{ gap: 8, alignItems: 'center' }} data-testid="threshold-none">
            {results && results.candidates.length
              ? <><span>no cut: nothing here beats the null</span><Button size="sm" onClick={() => setParams({ threshold: closest })} testid="choose-cut">choose a cut anyway · d ≤ {closest}</Button></>
              : 'no cut chosen · the recommended cut is read off the null distribution, so there is none until the search has drawn one'}
          </span>}
        </ParamField>
        <ParamField label="on overlap" info="When two kept matches overlap, which one survives.">
          <Dropdown value={p.overlap} onChange={v => setParams({ overlap: v })} block testid="param-overlap"
            options={[{ value: 'lowest', label: 'keep lowest distance' }, { value: 'first', label: 'keep first' }, { value: 'all', label: 'keep all (overlapping)' }]} />
        </ParamField>
      </div>
      {results && results.candidates.length && results.nullByScale ? <NullPerLength results={results} cut={cut} m={m} /> : null}
      {results && results.candidates.length
        ? <CutHistogram candidates={results.candidates} nullDistances={results.nullDistances} threshold={cut} recommended={cut} kept={kept} nullKept={nullKept} rule={results.cutRule ?? null} onThreshold={t => setParams({ threshold: t })} />
        : <div className="dsc-cut-empty"><EmptyState size="sm" icon="bar-chart" title={results ? 'No cut yet' : 'No distances yet'}
          caption={results ? 'the recommended cut comes from the null distribution — run the search to draw one' : 'pick a seed to see where to cut'} /></div>}
    </section>
  )
}
/** fixup-v: with a scale bank the null is drawn per length — a search at 1.25× is a different search from one at
 *  0.8× and has its own chance level — so each length's kept count stands beside what its own null gives. Counts,
 *  not a test: nothing here says whether a length beats its null. */
function NullPerLength({ results, cut, m }: { results: { candidates: SeedMatch[]; nullByScale?: SeedResults['nullByScale'] }; cut: number | null; m: number }) {
  const rows = Object.entries(results.nullByScale ?? {}).map(([k, v]) => {
    const scale = Number(k)
    const kept = cut == null ? 0 : results.candidates.filter(c => (c.scale ?? 1) === scale && c.d <= cut).length
    const nullHits = cut == null ? 0 : v.distances.filter(d => d <= cut).length
    return { scale, length: Math.round(m * scale), kept, perDraw: v.draws ? nullHits / v.draws : null, draws: v.draws }
  }).sort((a, b) => a.scale - b.scale)
  return (
    <div className="mono small" data-testid="null-per-length" style={{ display: 'grid', gap: 2, margin: '4px 0 2px' }}>
      <span className="muted">per length, at {cut == null ? 'no cut' : `d ≤ ${cut}`} · kept · the null gives (per draw)</span>
      {rows.map(r => (
        <span key={r.scale} data-testid={`null-length-${r.scale}`}>
          {r.scale}× · {r.length} samples · {r.kept} kept · {r.perDraw == null ? 'no null drawn' : `${fmtNull(r.perDraw)} per draw (${r.draws} draws)`}
        </span>
      ))}
    </div>
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

/* ------------------------------------------------------------------ the preview's progress */
/** The search's own progress — the job's done/total in units of work (the search plus every draw, per channel), elapsed
 *  and remaining — in place of an indeterminate strip. Before the first poll lands, the estimate stands in. */
function SearchProgress({ progress, estimate }: { progress: SeedProgress | null; estimate: DiscSeedEstimate | null }) {
  const frac = progress && progress.total > 0 ? progress.done / progress.total : 0
  const eta = progress?.etaS ?? (progress ? null : estimate?.preview.seconds ?? null)
  return (
    <section className="k-card dsc-loading" style={{ height: 220, flexDirection: 'column', gap: 10 }} data-testid="seed-search-progress" aria-label="Searching for the seed">
      <ProgressBar value={frac} indeterminate={!progress} size="md" width={360} labelPosition="none" />
      <b>searching for the seed{progress ? ` · ${Math.round(frac * 100)} %` : ''}</b>
      <span className="mono small muted">{progress?.message || (estimate ? `${estimate.channels} channels × ${estimate.preview.draws} null draws` : 'starting')}</span>
      <span className="mono small muted" data-testid="seed-search-eta">
        {progress?.elapsedS != null ? `${fmtSeconds(progress.elapsedS)} so far` : ''}
        {eta != null ? `${progress?.elapsedS != null ? ' · ' : ''}about ${fmtSeconds(eta)} ${progress ? 'left' : 'expected'}${!progress && estimate && !estimate.preview.measured ? ' (assumed rate)' : ''}` : ''}
      </span>
    </section>
  )
}

/* ------------------------------------------------------------------ matches */
function MatchesCard({ seed, matches, channels, note = null, nullDraws = null, hours = null }: { seed: SeedInfo; matches: SeedMatch[]; channels: number; note?: string | null; nullDraws?: number | null; hours?: number | null }) {
  const [pageQ, setPageQ] = useQueryState('mpage', '1')
  const [selQ, setSelQ] = useQueryState('match', '')
  const [, setChQ] = useQueryState('pch', 'CH4_A2')
  const [, setViewQ] = useQueryState('view', '192.0-194.0')
  const per = 8
  const pages = Math.max(1, Math.ceil(matches.length / per))
  const page = Math.min(pages, Math.max(1, parseInt(pageQ, 10) || 1))
  const shown = matches.slice((page - 1) * per, page * per)
  /* Each card overlays the MATCH on the seed (§7.6). The server served every candidate `trace: []`, so the
   * cards drew the seed alone (fixup-y). MASS compares z-normalised shapes, so a match an hour away can sit
   * millivolts above or below the seed; each trace is centred on its own mean, in mV on one shared scale,
   * so the two shapes are drawn on top of each other rather than as two flat lines far apart. */
  const seedC = useMemo(() => centred(seed.trace), [seed])
  const shownC = useMemo(() => shown.map(m => ({ ...m, trace: centred(m.trace) })), [shown])
  const yDomain = useMemo<[number, number]>(() => padDomain([...seedC, ...shownC.flatMap(m => m.trace)]), [seedC, shownC])
  // the picked card, drawn large below the grid (it may be on another page of cards)
  const selected = useMemo(() => { const m = matches.find(x => x.id === selQ); return m ? { ...m, trace: centred(m.trace) } : null }, [matches, selQ])
  return (
    <section className="k-card dsc-matches" data-testid="matches-card" aria-label="Matches">
      <div className="dsc-card-head">
        <h3>{note ? `${matches.length} closest` : `${matches.length} matches`}</h3>
        {/* the note explains a truncation; it was passed in and never rendered,
            which left "12 closest" over a search that returned 132 */}
        {note && <span className="muted small" data-testid="matches-note">{note}</span>}
        <InfoTip title="Matches">These are the full search's matches — every position in every channel of the scope was scored against the seed, and these are the ones under the cut (or, with no cut, the closest). Not a sample. The preview's null is capped at a few draws per channel over a long scope; the run draws the full 200. To put matches to Review, run the search: the run row on Discovery › Runs has *Send N unjudged to Review*. Each card overlays the match (black) on the seed (purple), centred on its own mean, in mV on one shared scale; a green dot marks a match that already has a verdict.</InfoTip>
        <span className="muted small" data-testid="matches-scope">the full search · {channels} channel{channels === 1 ? '' : 's'}{hours != null ? ` × ${hours.toFixed(1)} h` : ''}{nullDraws != null ? ` · null ${nullDraws} draw${nullDraws === 1 ? '' : 's'} per channel here, 200 in the run` : ''} · sorted by distance · to review them, run it</span>
        <span className="k-spacer" />
        <Pager page={page} pageCount={pages} onPage={p => setPageQ(String(p))} format="range" total={matches.length} pageSize={per} label="page of matches" testid="matches-pager" />
        <span className="dsc-legend-row small mono"><span><i className="sw" style={{ background: SEED_COLOUR }} />seed</span><span><i className="sw line" style={{ background: 'var(--trace)' }} />match</span></span>
      </div>
      {matches.length === 0 ? <EmptyState size="sm" icon="search" title="No match under this threshold" caption="raise the threshold, or check what the null gives first" testid="matches-empty" /> : (
        <div className="dsc-match-grid" data-testid="match-grid">
          {shownC.map(mt => (
            <button key={mt.id} type="button" className={cx('dsc-match', selQ === mt.id && 'on')} data-testid={`match-${mt.id}`}
              onClick={() => { setSelQ(mt.id); setChQ(mt.channel); setViewQ(`${Math.max(0, mt.atH - 1).toFixed(1)}-${(mt.atH + 1).toFixed(1)}`) }} title={`show ${mt.id} in the distance profile`}>
              <span className="row between mono small"><b>{mt.id}</b><span className="muted">d {mt.d.toFixed(2)}</span></span>
              <SeedThumb values={seedC} overlay={mt.trace} yDomain={yDomain} width={130} height={40} />
              {mt.trace.length === 0 && <span className="small muted" data-testid="match-no-trace">no trace served for this match</span>}
              <span className="mono small muted row" style={{ gap: 4 }}>{mt.judged && <span className="dot" style={{ background: 'var(--green)' }} title="already judged" />}{mt.channel} · {mt.atH.toFixed(1)} h{mt.scale != null && <span data-testid="match-scale" title={`found by the seed stretched to ${mt.length} samples`}> · {mt.scale}×</span>}</span>
            </button>
          ))}
        </div>
      )}
      {selected && <SelectedMatch seed={seedC} match={selected} yDomain={yDomain} />}
    </section>
  )
}
/** The picked match, large: the match (black) over the seed (purple), each centred on its own mean, in mV; the
 *  cards above are 130 px wide, which is a thumbnail, not something a shape can be read off. */
function SelectedMatch({ seed, match, yDomain }: { seed: number[]; match: SeedMatch & { trace: number[] }; yDomain: [number, number] }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const W = Math.max(0, size.width)
  return (
    <div className="dsc-selected-match" ref={ref} style={{ marginTop: 10 }} data-testid="selected-match">
      <div className="row between mono small" style={{ marginBottom: 4 }}>
        <b>{match.id}</b>
        <span className="muted">d {match.d.toFixed(2)} · {match.channel} · {match.atH.toFixed(2)} h · {match.length ?? match.trace.length} samples{match.judged ? ` · already judged${match.verdict ? ` (${match.verdict})` : ''}` : ''}</span>
      </div>
      {W > 0 && <SeedThumb values={seed} overlay={match.trace} yDomain={yDomain} width={W} height={180} unit="mV" />}
    </div>
  )
}

/* ------------------------------------------------------------------ apply bar */
function ApplyBar({ dx, draft, kept, cut, finished, seed, sim, onStarted, onSave, bank = null, estimate = null, live = null, startedAt = null, exclusion = null, onSlurm, onImported }: {
  dx: Discovery; draft: SeedDraft; kept: number | null; cut: number | null; finished: DiscoveryRun | null; seed: SeedInfo | null
  sim: ReturnType<typeof useSim>; onStarted: (r: { key: string; label: string }) => void; onSave: () => void
  bank?: { scales: number[]; overlap: string } | null
  /** the run's cost on this scope, before the button; the run this page started, while it runs; when it was pressed */
  estimate?: DiscSeedEstimate | null; live?: DiscoveryRun | null; startedAt?: number | null
  exclusion?: number | null
  /** over the ceiling: *Create SLURM script* is the primary action; a result file brought back is imported here */
  onSlurm?: () => void; onImported?: () => void
}) {
  const toast = useToast()
  const [now, setNow] = useState(Date.now())
  const onCluster = !!finished && finished.status === 'on cluster'
  const overCeiling = !!estimate && estimate.route === 'cluster'
  const importResult = (file: File) => {
    file.text().then(text => postDiscoverySeedImport(JSON.parse(text)))
      .then(r => { onStarted({ key: r.run_key, label: r.label }); onImported?.(); toast.push({ text: `${r.label} · ${r.nullDraws} null draws imported · ${r.candidates} candidates · the real search is running here` }) })
      .catch(e => { console.error('the result could not be imported', e); toast.push({ text: `not imported · ${e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)}` }) })
  }
  const running = !!live && (live.status === 'running' || live.status === 'queued')
  useEffect(() => { if (!running) return; const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t) }, [running])
  // §7.6's apply bar diffs the parameters against the ones the last search ran with. `applied` is null
  // until the search has run once: then every parameter is unapplied, which is not "no changes".
  const label: Record<keyof SeedParams, string> = {
    algorithm: 'algorithm', windowSamples: 'window', windowS: 'window length', windowLocked: 'window locked',
    scaleBank: 'scale bank', exclusionSamples: 'exclusion samples', exclusionS: 'exclusion zone',
    exclusionNote: 'exclusion guard', specExclusionS: 'spec exclusion zone', exclusionSettable: 'exclusion settable',
    threshold: 'threshold', overlap: 'on overlap', bank: 'bank lengths',
  }
  // the fields the parameter card sets; the rest of SeedParams is the server describing what it did
  // fixup-AD: the exclusion zone is a parameter of the block again, so a changed zone is a change the apply bar shows
  const settable: (keyof SeedParams)[] = ['algorithm', 'windowSamples', 'scaleBank', 'exclusionS', 'threshold', 'overlap']
  const applied = draft.applied
  const show = (v: SeedParams[keyof SeedParams]) => v == null ? 'none' : String(v)
  const changes = applied ? settable.filter(k => draft.params[k] !== applied[k]) : settable
  const diff = applied ? changes.map(k => `${label[k]} ${show(applied[k])} → ${show(draft.params[k])}`).join(' · ')
    : settable.map(k => `${label[k]} ${show(draft.params[k])}`).join(' · ')
  /* `finished` is THIS search — the run with this seed and this cut (fixup-y). It used to be the first run
   * whose label began with the draft's, and *Open in Runs* navigated to the draft's key `seed_a9147c`
   * while the run's key was `seed a9147c`. The link now carries the run's own key. */
  const done = !!finished && (finished.status === 'done' || finished.status === 'completed')
  const channels = dx.scope?.channels ?? []
  const noSeedReason = !seed ? 'pick a seed first' : null
  /* §7.6's apply bar: "A run seed search becomes a normal run row." It is a
   * real run — POST /api/discovery/seed/run starts a sweep over the scope and
   * the row arrives from the server on the next read of the runs list. The cut
   * sent is the cut IN FORCE — the recommended one until the line is dragged —
   * so the run keeps what the histogram says is kept. An unchanged search is
   * the same run: the server returns it rather than adding a second row. The
   * progress strip still comes from `sim`, because the page has no SSE
   * subscription yet (reported in 04-discovery.md, "Left"). */
  const run = () => {
    if (!seed || !dx.scope) return
    runDiscoverySeedSearchOnce({
      seedId: seed.id, channels, t0: dx.scope.section[0], t1: dx.scope.section[1],
      k: SEED_K, cut: cut ?? undefined, label: draft.label,
      ...(bank ? { scales: bank.scales, overlap: bank.overlap } : {}),
      // fixup-AD: the zone the slider holds, as the fraction of m the block takes; the run's recipe records it
      ...((draft.params.windowS ?? 0) > 0 && draft.params.exclusionSettable !== false ? { exclusion: Math.round((draft.params.exclusionS / (draft.params.windowS ?? 1)) * 1000) / 1000 } : {}),
    }).then(r => { onStarted({ key: r.run_key, label: r.label }); dx.reload() })
      .catch(e => { console.error('the seed search could not start', e) })
  }
  /* the run's own progress: the server's fraction over the sweep (channels and their draws), the time since the
   * button was pressed, and what is left at that pace — the simulated strip said "MASS CH2 (2 of 4)" about
   * nothing */
  const frac = live?.progress ?? 0
  const elapsedS = startedAt ? (now - startedAt) / 1000 : null
  const leftS = elapsedS != null && frac > 0.02 ? elapsedS * (1 - frac) / frac : (estimate ? estimate.run.seconds : null)
  const cancel = () => {
    const id = live?.job ? parseInt(live.job.replace(/^j-/, ''), 10) : NaN
    if (!Number.isFinite(id)) return
    cancelJob(id).then(() => dx.reload()).catch(e => console.error('the run could not be cancelled', e))
  }
  const costLine = estimate
    ? `about ${fmtSeconds(estimate.run.seconds)} · ${estimate.channels} ch × ${(estimate.sectionH[1] - estimate.sectionH[0]).toFixed(1)} h × ${estimate.run.draws} null draws${estimate.run.measured ? '' : ' · assumed rate until one run has finished here'}`
    : null
  return (
    <section className="k-card dsc-apply" data-testid="apply-bar" aria-label="Apply">
      {running ? (
        <>
          <ProgressBar value={frac} width={180} labelPosition="none" testid="seed-progress" />
          <b data-testid="seed-running">{live!.status === 'queued' ? 'queued · local' : `running · ${Math.round(frac * 100)} %`}{live!.progressText ? ` · ${live!.progressText}` : live!.channelsDone ? ` · ${live!.channelsDone} channels` : ''}</b>
          <span className="muted small mono">{elapsedS != null ? `${fmtSeconds(elapsedS)} so far` : ''}{leftS != null ? ` · about ${fmtSeconds(leftS)} left` : ''}</span>
          <span className="k-spacer" />
          <Button onClick={cancel} disabled={!live?.job} disabledReason="no job to cancel" testid="seed-cancel">Cancel</Button>
        </>
      ) : sim.busy ? (
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
          <span className="dot" style={{ background: finished ? 'var(--green)' : 'var(--amber)', width: 9, height: 9 }} />
          {finished
            ? <><b data-testid="seed-done">{finished.label} · {kept == null ? 'no cut chosen — nothing kept' : `${finished.found ?? kept} found`}{done ? ` · done ${finished.doneAt ?? ''}` : ` · ${finished.status}`}</b>
              <Button variant="link" size="sm" icon="external" onClick={() => navigate(`discovery/runs?run=${encodeURIComponent(finished.key)}`)} testid="seed-open-runs">Open in Runs</Button></>
            : sim.status === 'done'
              ? <><b data-testid="seed-done">{draft.label} · {kept == null ? 'no cut chosen — nothing kept yet' : `${kept} found`}</b>
                <Button variant="link" size="sm" icon="external" onClick={() => navigate('discovery/runs')} testid="seed-open-runs">Open in Runs</Button></>
              : <><b data-testid="apply-state">draft · {!applied ? 'not run with this cut yet' : changes.length === 0 ? 'no unapplied changes' : `${changes.length} unapplied change${changes.length === 1 ? '' : 's'}`}</b><span className="muted small mono">{diff ? `${diff} · ` : ''}preview counts update live</span></>}
          {sim.status === 'cancelled' && <span className="muted small">last search cancelled · nothing written</span>}
          <span className="k-spacer" />
          {costLine && !finished && <span className="muted small mono" data-testid="run-estimate">{costLine}{overCeiling ? ` · over the ${fmtSeconds(estimate!.ceilingS)} local limit` : ''}</span>}
          {onCluster && <span className="muted small mono" data-testid="on-cluster">on the cluster · import {finished!.hpc?.resultPath.split('/').pop() ?? 'the result'} when it is back</span>}
          <ImportResultButton onFile={importResult} />
          <Button icon="save" onClick={onSave} testid="save-as-template">Save as template</Button>
          {overCeiling || onCluster
            ? <Button variant="cluster" icon="file" onClick={onSlurm} disabled={!!noSeedReason} disabledReason={noSeedReason ?? undefined} testid="seed-slurm">{onCluster ? 'SLURM script' : 'Create SLURM script'}</Button>
            : null}
          <Button variant={overCeiling ? undefined : 'primary'} icon="play" onClick={run} disabled={!!noSeedReason || !!finished || overCeiling}
            disabledReason={noSeedReason ?? (overCeiling ? `about ${fmtSeconds(estimate!.run.seconds)} — over the ${fmtSeconds(estimate!.ceilingS)} local limit; run it on the HPC` : `already run with this seed and cut — ${finished?.label}`)} testid="run-seed-search">Run seed search</Button>
        </>
      )}
    </section>
  )
}

/* ------------------------------------------------------------------ the HPC route */
/** A file picker as a button: the result file `seed_job` wrote on the cluster, brought back by hand. */
function ImportResultButton({ onFile, testid = 'import-result' }: { onFile: (f: File) => void; testid?: string }) {
  const ref = useRef<HTMLInputElement>(null)
  return (
    <>
      <input ref={ref} type="file" accept=".json,application/json" style={{ display: 'none' }} data-testid={`${testid}-file`}
        onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = '' }} />
      <Button icon="upload" onClick={() => ref.current?.click()} title="import a seed_job result file computed on the HPC" testid={testid}>Import HPC result</Button>
    </>
  )
}

/** Over the ceiling the search is a SLURM job (the researcher, 2026-10-06): `POST /api/discovery/seed/slurm` writes the spec
 *  (the exemplar's samples, the channels, the span, the parameters, the session's null) and the script around
 *  `python -m Working.discovery.seed_job`; the run row stands *on cluster*; the result file comes back through the import. */
function SeedSlurmModal({ open, onClose, dx, draft, seed, cut, bank, exclusion, estimate, onImported }: {
  open: boolean; onClose: () => void; dx: Discovery; draft: SeedDraft; seed: SeedInfo; cut: number | null
  bank: { scales: number[]; overlap: string } | null; exclusion: number | null; estimate: DiscSeedEstimate | null
  onImported: (r: { run_key: string; label: string }) => void
}) {
  const toast = useToast()
  const [made, setMade] = useState<DiscSeedSlurm | null>(null)
  const [err, setErr] = useState<Error | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!open || made || !dx.scope) return
    setBusy(true); setErr(null)
    postDiscoverySeedSlurm({ seedId: seed.id, channels: dx.scope.channels, t0: dx.scope.section[0], t1: dx.scope.section[1], k: SEED_K, label: draft.label,
      ...(cut != null ? { cut } : {}), ...(bank ? { scales: bank.scales, overlap: bank.overlap } : {}), ...(exclusion != null ? { exclusion } : {}) })
      .then(r => { setMade(r); dx.reload() })
      .catch(e => setErr(e instanceof Error ? e : new Error(String(e))))
      .finally(() => setBusy(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])
  const importResult = (file: File) => {
    file.text().then(text => postDiscoverySeedImport(JSON.parse(text)))
      .then(r => { onImported(r); toast.push({ text: `${r.label} · ${r.nullDraws} null draws imported · the real search is running here` }); onClose() })
      .catch(e => { console.error('the result could not be imported', e); toast.push({ text: `not imported · ${e instanceof Error ? e.message : String(e)}` }) })
  }
  const cost = estimate ? `about ${fmtSeconds(estimate.run.seconds)} here · ${estimate.channels} ch × ${(estimate.sectionH[1] - estimate.sectionH[0]).toFixed(1)} h × ${estimate.run.draws} null draws · over the ${fmtSeconds(estimate.ceilingS)} limit` : ''
  return (
    <Modal open={open} onClose={onClose} title="Seed search on the HPC" subtitle={cost} testid="seed-slurm-modal"
      footerNote={made ? `sync the spec and the script to the cluster · ${made.sbatch_command} · bring ${made.result_path.split('/').pop()} back and import it` : 'the spec carries the exemplar’s own samples, the channels, the section and the null, so the cluster runs exactly this search'}
      footer={<><ImportResultButton onFile={importResult} testid="modal-import-result" /><Button variant="primary" onClick={onClose}>Done</Button></>}>
      {err ? <LoadFailed what="the SLURM script" error={err} onRetry={() => { setMade(null); setErr(null) }} />
        : busy || !made ? <Loading height={260} label="writing the spec and the script through Working.discovery.seed_job" />
          : <>
            <div className="mono small muted" style={{ marginBottom: 8 }} data-testid="seed-slurm-paths">
              spec {made.spec_path}<br />script {made.script_path}<br />result expected at {made.result_path}
              {made.warnings?.length ? <><br /><span className="amber">{made.warnings.join(' · ')}</span></> : null}
            </div>
            <CodeBlock title={made.script_path} code={made.script} filename={made.script_path.split(/[\\/]/).pop() ?? 'seed.sh'} lineNumbers testid="seed-slurm-script" />
          </>}
    </Modal>
  )
}

/* ------------------------------------------------------------------ save as template */
const TPL_RE = /^[a-z0-9_]{3,40}$/
/** The save is a write: `POST /api/discovery/seed/template` stores the one step this search runs, with the cut in
 *  force, the bank and the exclusion zone. It used to go to the in-memory store only — the name read "exists"
 *  after one press and Library › Templates never held the template. */
function SaveTemplateModal({ open, onClose, draft, seed, cut, bank, exclusion, onSaved }: {
  open: boolean; onClose: () => void; draft: SeedDraft; seed: SeedInfo | null; onSaved?: (name: string) => void
  cut: number | null; bank: { scales: number[]; overlap: string } | null; exclusion: number | null
}) {
  const tpls = useSourced(getTemplates, [open])
  // a label is 'seed 8576e5'; a template name has no space
  const [name, setName] = useState(draft.label.toLowerCase().replace(/[^a-z0-9_]+/g, '_'))
  const [failed, setFailed] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const toast = useToast()
  const taken = (tpls.data ?? []).some(t => t.name === name)
  const err = !seed ? 'pick a seed first' : !name ? 'a template needs a name' : !TPL_RE.test(name) ? 'lower-case letters, digits and _ only (3–40)' : taken ? `a template called ${name} exists` : saving ? 'saving…' : null
  const save = () => {
    if (!seed) return
    setSaving(true); setFailed(null)
    saveDiscoverySeedTemplate({
      seedId: seed.id, name, k: SEED_K, bind: draft.bind, ...(cut != null ? { cut } : {}),
      ...(bank ? { scales: bank.scales, overlap: bank.overlap } : {}), ...(exclusion != null ? { exclusion } : {}),
    }).then(() => {
      toast.push({ text: `Saved ${name} · Library › Templates · the next run is called ${name}`, action: { label: 'Open', onClick: () => navigate('library/templates') } })
      onSaved?.(name)
      onClose()
    }).catch(e => {
      // a taken name is the form's own error (409); anything else is a failure and is logged as one
      if (!(e instanceof ApiError && e.status === 409)) console.error('the template could not be saved', e)
      setFailed(e instanceof Error ? e.message : String(e)); tpls.reload()
    }).finally(() => setSaving(false))
  }
  return (
    <Modal open={open} onClose={onClose} title="Save as template" subtitle="a seed search saved is a template with badge seed" size="md" testid="save-template-modal"
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon="save" onClick={save} disabled={!!err} disabledReason={err ?? undefined} testid="save-template-confirm">Save template</Button></>}>
      <div className="dsc-save-form">
        <label className="small muted" htmlFor="tpl-name">name</label>
        <TextField id="tpl-name" value={name} onChange={setName} invalid={!!err} block onEnter={() => { if (!err) save() }} testid="save-template-name" />
        {(err || failed) && <span className="dsc-err" data-testid="save-template-error">{err ?? failed}</span>}
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
