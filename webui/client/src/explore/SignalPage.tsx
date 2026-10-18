/* Explore › Signal (frames explore-2, 2a popovers, 2b–2d drawer): three tiers on one channel — overview with
   the draggable span box, the viewport, the selected motif — then the span-action row and the four ribbons,
   which open the drawer. The signal, annotations and live detections are live (bridge); on the canon channel
   (CH4_A2, id 4) the runs, methods, adjudications, families and drawer rows are demo canon (getSignalDemo) and
   the header shows the demo chip. The held-out recording renders a locked card from the API's refusal.
   Deep links: ?popover=detections|span-legend · ?drawer=annotations|detections|shortcuts · ?filters=closed ·
   ?motif=<ordinal> · ?state=loading|error */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { DatasetName } from '../naming'
import { ApiError, getChannel, getRecordings, getSpans, listRuns, type Channel, type DbRun, type Spans } from '../api'
import { useSourced } from '../api/seam'
import { getSignalDemo } from '../api/explore'
import { annotationKind, parseToggles, visibleDetections, type SpanKind, type ToggleKind, type Toggles } from './bandModel'
import { Callout, Dropdown, InfoTip, Seg, useDemoState, useQueryState } from '../kit'
import { ErrorBoundary } from '../shell/ErrorBoundary'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, useApp } from '../state'
import { DetectionsChip, DetectionsPicker } from './DetectionsPicker'
import { ErrorCard } from './ErrorCard'
import { LockedCard } from './LockedCard'
import { MotifView } from './MotifView'
import { Overview } from './Overview'
import { Ribbons, type DrawerTab } from './Ribbons'
import { SignalDrawer } from './SignalDrawer'
import { buildMotifs, chipLabel, defaultPicker, pickerRuns, visibleRunIds, type PickerState } from './signalModel'
import { SpanActions, takeSpanForReview } from './SpanActions'
import { SpanView, type Band } from './SpanView'
import { useElementSize } from './useElementSize'
import { useViewport } from './useViewport'
import { asApiError, fmtInt, fmtRangeH, type Motif } from './util'

function TopBar({ channelId, file, name, extra }: { channelId: number; file: string; name: string; extra?: React.ReactNode }) {
  return (
    <div className="ex-topbar" data-testid="signal-topbar">
      <div className="ex-crumb">
        <a onClick={() => navigate('explore/corpus')} data-testid="crumb-corpus">Corpus</a><span>›</span>
        <a onClick={() => navigate(`explore/corpus?rec=${encodeURIComponent(file)}&ch=${channelId}`)} data-testid="crumb-file"><DatasetName file={file} /></a><span>›</span>
        <span className="cur">{name}</span>
      </div>
      {extra}
      <span className="grow" />
      <a className="ex-back" onClick={() => navigate('explore/corpus')} data-testid="back-to-corpus">‹ back to corpus</a>
    </div>
  )
}

export function SignalPage({ channelId }: { channelId: number }) {
  const [forced] = useQueryState<string>('state', '')
  const [ch, setCh] = useState<Channel | null>(null)
  const [err, setErr] = useState<ApiError | null>(null)
  useEffect(() => {
    let alive = true
    setCh(null); setErr(null)
    if (!Number.isFinite(channelId)) { setErr(new ApiError(0, `bad channel id in the route: ${String(channelId)}`)); return }
    // Held-out guard first (spec §0 D6): if this channel id belongs to the held-out recording,
    // show the server's refusal from /api/recordings and never request the channel itself.
    getRecordings().then(files => {
      if (!alive) return
      const owner = files.find(f => f.channels.some(c => c.id === channelId))
      if (owner?.held_out) { setErr(new ApiError(423, owner.held_out_reason ?? `${owner.source_file} is held out (spec §0 D6)`)); return }
      getChannel(channelId).then(c => { if (alive) setCh(c) }).catch(e => { if (alive) setErr(asApiError(e)) })
    }).catch(e => { if (alive) setErr(asApiError(e)) })
    return () => { alive = false }
  }, [channelId])

  const shownErr = err ?? (forced === 'error' ? new ApiError(500, `GET /api/channels/${channelId} failed (forced by ?state=error: the page's failure state)`) : null)
  if (shownErr) {
    const locked = shownErr.status === 423
    return (
      <>
        <Header workspace="Explore" page="Signal" subtitle={locked ? `channel ${channelId} · held out` : `channel ${channelId} · error`} search="Search spans, runs, families" />
        <div className="page"><div className="page-inner">
          <div className="ex-topbar"><div className="ex-crumb"><a onClick={() => navigate('explore/corpus')} data-testid="crumb-corpus">Corpus</a><span>›</span><span className="cur">channel {channelId}</span></div><span className="grow" /><a className="ex-back" onClick={() => navigate('explore/corpus')}>‹ back to corpus</a></div>
          {locked ? <LockedCard error={shownErr} file="M4_aug_concat_fs1.mat" /> : <ErrorCard error={shownErr} title={`GET /api/channels/${channelId} failed`} />}
        </div></div>
      </>
    )
  }
  if (!ch || forced === 'loading') {
    return (
      <>
        <Header workspace="Explore" page="Signal" subtitle={`channel ${channelId} · loading…`} search="Search spans, runs, families" />
        <div className="page"><div className="page-inner" data-testid="signal-loading">
          <div className="skeleton" style={{ height: 30, width: 480 }} />
          <div className="skeleton" style={{ height: 150 }} />
          <div className="skeleton" style={{ height: 240 }} />
          <div className="skeleton" style={{ height: 200 }} />
        </div></div>
      </>
    )
  }
  return <SignalBody ch={ch} />
}

const TAB_LABEL: Record<DrawerTab, string> = { annotations: 'Annotations', detections: 'Detections', shortcuts: 'Shortcuts' }

/** span-plot: which band kinds draw, remembered in this browser for the Explore workspace (every channel). */
const TOGGLES_KEY = 'ub.explore.span-bands'
function useBandToggles(): [Toggles, (k: ToggleKind) => void] {
  const [t, setT] = useState<Toggles>(() => { try { return parseToggles(localStorage.getItem(TOGGLES_KEY)) } catch { return parseToggles(null) } })
  const flip = useCallback((k: ToggleKind) => setT(prev => {
    const next = { ...prev, [k]: !prev[k] }
    try { localStorage.setItem(TOGGLES_KEY, JSON.stringify(next)) } catch { /* not remembered: still applied */ }
    return next
  }), [])
  return [t, flip]
}

function SignalBody({ ch }: { ch: Channel }) {
  const { explore, setExplore, setSource } = useApp()
  const toast = useToast()
  const [plotRef, plotSize] = useElementSize<HTMLDivElement>()
  const [popover, setPopover] = useQueryState<string>('popover', '')
  const [drawerQ, setDrawerQ] = useQueryState<string>('drawer', '')
  const [motifQ, setMotifQ] = useQueryState<string>('motif', '')
  const drawer: DrawerTab | null = drawerQ === 'annotations' || drawerQ === 'detections' || drawerQ === 'shortcuts' ? drawerQ : null
  const [lastTab, setLastTab] = useDemoState<DrawerTab>('explore.signal.lastTab', () => 'annotations')
  const demoRead = useSourced(() => getSignalDemo(ch.id), [ch.id])
  const demo = demoRead.data ?? null

  const initial = useCallback((): [number, number] => {
    if (explore.channelId === ch.id && explore.view) return explore.view
    if (ch.source_file === 'M2_aug_concat_fs1.mat' && ch.name === 'CH4_A2') return [995040, 1002240]  // the frames' example span
    return [0, Math.min(7200, ch.duration_s)]
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps -- initial only
  const vp = useViewport(ch, initial, plotSize.width)
  useEffect(() => {
    const id = window.setTimeout(() => setExplore({ channelId: ch.id, view: vp.view }), 200)
    return () => window.clearTimeout(id)
  }, [vp.view, ch.id, setExplore])

  // every span on the channel, once, for ‹ N / M › and the live drawer
  const [all, setAll] = useState<Spans | null>(null)
  const [allErr, setAllErr] = useState<ApiError | null>(null)
  useEffect(() => {
    let alive = true
    getSpans(ch.id, 0, ch.duration_s).then(s => { if (alive) setAll(s) }).catch(e => { if (alive) setAllErr(asApiError(e)) })
    return () => { alive = false }
  }, [ch.id, ch.duration_s])
  // live runs feed the picker on channels without demo canon
  const [liveRuns, setLiveRuns] = useState<DbRun[] | null>(null)
  const [runsErr, setRunsErr] = useState<ApiError | null>(null)
  useEffect(() => {
    if (demoRead.loading || demo) return
    let alive = true
    listRuns(ch.id, 30).then(r => { if (alive) setLiveRuns(Array.isArray(r?.db_runs) ? r.db_runs : []) }).catch(e => { if (alive) setRunsErr(asApiError(e)) })
    return () => { alive = false }
  }, [ch.id, demo, demoRead.loading])

  const runs = useMemo(() => pickerRuns(demo, liveRuns), [demo, liveRuns])
  const [pickerSt, setPickerSt] = useDemoState<PickerState | null>(`explore.signal.picker.${ch.id}`, () => null)
  const st = pickerSt ?? defaultPicker(demo, runs)
  const [toggles, flipToggle] = useBandToggles()
  // ‹ N / M › walks what the span draws: a kind switched off in the legend is skipped
  const motifs = useMemo(() => buildMotifs(all, demo, runs, st, ch.fs).filter(m => toggles[m.kind === 'annotated' ? annotationKind(m.verdict) : 'detected']), [all, demo, runs, st, ch.fs, toggles])
  const capped = !!(all && (all.annotations_capped || all.detections_capped))
  const [sel, setSel] = useState<Motif | null>(null)
  const index = sel ? motifs.findIndex(m => m.key === sel.key) : -1
  const labelOf = (m: Motif | null, i: number) => (m ? (i >= 0 ? `MOTIF_${i + 1}` : `${m.kind === 'annotated' ? 'ANNOTATION' : 'DETECTION'}_${m.id}`) : null)
  const choose = useCallback((m: Motif | undefined, centre = true) => {
    if (!m) return
    setSel(m); if (centre) vp.centreOn(m.start_s, m.end_s)
    const i = motifs.findIndex(x => x.key === m.key)
    setMotifQ(i >= 0 ? String(i + 1) : null)
  }, [motifs, vp, setMotifQ])
  // ?motif=<ordinal> selects once the list is known
  const applied = useRef<string>('')
  useEffect(() => {
    if (!motifQ || !motifs.length || applied.current === motifQ || (demoRead.loading)) return
    applied.current = motifQ
    const m = motifs[Number(motifQ) - 1]
    if (m && m.key !== sel?.key) { setSel(m); vp.centreOn(m.start_s, m.end_s) }
  }, [motifQ, motifs, demoRead.loading])  // eslint-disable-line react-hooks/exhaustive-deps
  const next = () => {
    if (index >= 0) choose(motifs[index + 1])
    else choose(motifs.find(m => m.start_s >= vp.view[0]) ?? motifs[0])
  }
  const prev = () => {
    if (index >= 0) choose(motifs[index - 1])
    else { let last: Motif | undefined; for (const m of motifs) { if (m.start_s <= vp.view[1]) last = m; else break } choose(last ?? motifs[motifs.length - 1]) }
  }

  // bands in the viewport: the viewport's own spans read (span-plot: once — the whole-channel copy getSignalLive
  // holds was pushed a second time, and it is capped to the channel's first 5 000 detections)
  const vis = useMemo(() => visibleRunIds(runs, st), [runs, st])
  const runColour = useMemo(() => new Map(runs.map(r => [r.id, r.colour])), [runs])
  const [a, b] = vp.view
  // span-plot critic: say in words why detections in view are not all drawn — none picked, or a thinned read
  const bandNote = useMemo(() => {
    if (runs.length && vis.size === 0) return 'No runs are picked in “show detections from”, so no detections are drawn. Pick a run there to see its detections.'
    const sp = vp.spans
    if (sp?.detections_spread && sp.detections_total) return `Too many detections in this view to draw each one: ${fmtInt(sp.detections.length)} of the ${fmtInt(sp.detections_total)} here (every run) are drawn, spread evenly across the view. Zoom in to see every one.`
    return null
  }, [runs.length, vis, vp.spans])
  const inView = useMemo(() => motifs.filter(m => m.end_s > a && m.start_s < b), [motifs, a, b])
  // in the view as it is NOW: until the new view's read lands, vp.spans is the previous view's (critic round)
  const liveInView = useMemo(() => (vp.spans ? visibleDetections(vp.spans.detections.filter(d => !!d && d.end_s > a && d.start_s < b), vis, runs.length) : []), [vp.spans, runs, vis, a, b])
  const bands = useMemo<Band[]>(() => {
    const out: Band[] = []
    for (const an of vp.spans?.annotations ?? []) {
      if (!an || an.end_s <= a || an.start_s >= b) continue
      const m: Motif = { key: `a:${an.id}`, kind: 'annotated', id: an.id, start_s: an.start_s, end_s: an.end_s, verdict: an.verdict, tag: an.tag, note: an.note, source: an.source }
      const toggle = annotationKind(an.verdict)
      const kind: SpanKind = sel?.key === m.key ? 'selected' : toggle
      out.push({ start_s: an.start_s, end_s: an.end_s, kind, toggle, id: m.key, title: `annotation ${an.id} · ${an.verdict}`, motif: m })
    }
    for (const d of liveInView) {
      const m: Motif = { key: `d:${d.id}`, kind: 'detected', id: d.id, start_s: d.start_s, end_s: d.end_s, run_id: d.run_id, score: d.score }
      out.push({ start_s: d.start_s, end_s: d.end_s, kind: sel?.key === m.key ? 'selected' : 'detected', toggle: 'detected', id: m.key, title: `detection ${d.id} · run ${d.run_id}`, motif: m, colour: st.colourByRun ? runColour.get(`#${d.run_id}`) : undefined })
    }
    return out
  }, [vp.spans, liveInView, sel, st, runColour, a, b])

  const send = (t0: number, t1: number, label: string) => {
    setSource({ recording_id: ch.id, channel_name: ch.name, source_file: ch.source_file, fs: ch.fs, start_idx: Math.round(t0 * ch.fs), end_idx: Math.round(t1 * ch.fs), label })
    toast.push({ text: `${label} sent to Analyse as the chain source` })
    navigate('analyse/chain')
  }
  /* The selected motif's *Take for Review* is the same act as the span row's (fixup-y): its extent becomes
   * an `annotations` row with verdict `seed`, in the Explore spans queue. It was a demo write and a toast. */
  const reviewMotif = (m: Motif) => {
    const label = labelOf(m, motifs.findIndex(x => x.key === m.key)) ?? `MOTIF_${m.id}`
    takeSpanForReview(ch.id, ch.fs, [m.start_s, m.end_s])
      .then(r => toast.push({ text: `${label} taken for Review · annotation ${r.id} · in the Explore spans queue and offered as a seed in Discovery`, action: { label: 'Open Review →', onClick: () => navigate(`review/queue/${r.queue_id}`) } }))
      .catch(e => toast.push({ kind: 'error', text: `${label} was not taken for Review: ${e instanceof Error ? e.message : String(e)}` }))
  }
  const openDrawer = useCallback((t: DrawerTab, focus = false) => { setLastTab(t); setDrawerQ(t); if (focus) setFocusSignal(n => n + 1) }, [setLastTab, setDrawerQ])
  const [focusSignal, setFocusSignal] = useState(0)
  const [tagSignal, setTagSignal] = useState(0)
  const actions = useRef<{ take: () => void } | null>(null)

  // page keyboard map (frame explore-2d); ignored while typing
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return
      const t = e.target as HTMLElement | null
      if (t && (t.closest('input, textarea, select, [contenteditable="true"]') || t.getAttribute('role') === 'tab' && (e.key === 'ArrowLeft' || e.key === 'ArrowRight'))) return
      if (e.altKey || e.metaKey) return
      const [va, vb] = vp.viewRef.current
      const span = vb - va
      const k = e.key
      if (e.ctrlKey) {
        if (k === 'a' || k === 'A') { e.preventDefault(); toast.push({ text: `${inView.length} motif${inView.length === 1 ? '' : 's'} in view selected` }) }
        return
      }
      const act = (fn: () => void) => { e.preventDefault(); fn() }
      if (k === 'ArrowLeft' || k === 'ArrowRight') act(() => vp.setView([va + (k === 'ArrowLeft' ? -0.1 : 0.1) * span, vb + (k === 'ArrowLeft' ? -0.1 : 0.1) * span]))
      else if (k === '+' || k === '=') act(() => vp.zoomAt(1 / 1.5, (va + vb) / 2))
      else if (k === '-' || k === '_') act(() => vp.zoomAt(1.5, (va + vb) / 2))
      else if (k === 'f' || k === 'F') act(vp.fit)
      else if (k === '[') act(prev)
      else if (k === ']') act(next)
      else if (k === 'Home') act(() => navigate('explore/corpus'))
      else if (k === 'Escape') { if (sel) act(() => { setSel(null); setMotifQ(null) }) }
      else if (k === 'R' && e.shiftKey) { if (sel) act(() => reviewMotif(sel)) }
      else if (k === 'r') act(() => actions.current?.take())
      else if (k === 'a') act(() => send(va, vb, `${ch.name} · ${fmtRangeH(va, vb)}`))
      else if (k === 't') act(() => { setDrawerQ(null); setTagSignal(n => n + 1) })
      else if (k === 'c') act(() => navigate(`explore/cross-channel/${ch.id}${index >= 0 ? `?window=motif-${index + 1}` : ''}`))
      else if (k === 'd' || k === 'D') act(() => (drawer ? setDrawerQ(null) : openDrawer(lastTab)))
      else if (k === '/') act(() => openDrawer('annotations', true))
      else if (k === 'l' || k === 'L') act(() => setPopover(popover === 'span-legend' ? null : 'span-legend'))
      else if (k === '1') act(() => openDrawer('annotations'))
      else if (k === '2') act(() => openDrawer('detections'))
      else if (k === '3' || k === '?') act(() => openDrawer('shortcuts'))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  // the density ribbon follows the run picker when the whole-channel read holds every detection. span-plot, the pile
  // at t = 0: that read is capped at the channel's FIRST 5 000 detections by start, and this ribbon was built from it
  // whatever its size — every detection of a busy channel drawn in its opening hours. Capped, the ribbon is the
  // bridge's own count over the whole channel (every run).
  const demoDensity = useMemo(() => {
    if (!all || all.detections_capped || !runs.length) return undefined
    const n = ch.ribbons.buckets || 300, w = ch.duration_s / n
    const out = new Array(n).fill(0)
    for (const d of visibleDetections(all.detections, vis, runs.length)) out[Math.max(0, Math.min(n - 1, Math.floor(d.start_s / w)))]++
    return out
  }, [all, runs, vis, ch])
  const pickerAnchor = useRef<HTMLButtonElement>(null)
  const subtitle = drawer ? `${ch.name} · drawer, ${TAB_LABEL[drawer]}` : `${ch.name} · ${fmtInt(ch.summary.annotations)} annotations · ${fmtInt(ch.summary.detections)} detections`
  // span-plot critic: the live read's detections are capped at 5 000 — a capped copy is not the channel's count
  const totals = demo ? { annotations: demo.annotations.length, detections: all?.detections_capped ? ch.summary.detections : demo.detections.length } : { annotations: ch.summary.annotations, detections: ch.summary.detections }
  const initialDraft = demo ? { tags: demo.spanTags, selected: [demo.spanTags[0]], note: demo.spanNote } : { tags: [], selected: [], note: '' }
  const selLabel = labelOf(sel, index)

  return (
    <>
      <Header workspace="Explore" page="Signal" subtitle={subtitle} search="Search spans, runs, families" demo={!!demo} />
      <div className="page"><div className="page-inner ex-signal">
        <TopBar channelId={ch.id} file={ch.source_file} name={ch.name} extra={<>
          <span className="ex-topbar-seg"><Seg size="sm" value="signal" onChange={v => { if (v === 'cross') navigate(`explore/cross-channel/${ch.id}${index >= 0 ? `?window=motif-${index + 1}` : ''}`) }}
            options={[{ value: 'signal', label: 'Signal' }, { value: 'cross', label: 'Cross-channel' }]} ariaLabel="mode" testid="mode-seg" /></span>
          <DetectionsChip ref={pickerAnchor} label={chipLabel(runs, st)} open={popover === 'detections'} onClick={() => setPopover(popover === 'detections' ? null : 'detections')} />
          <Dropdown size="md" variant="outline" prefix="display" value="raw" onChange={() => {}} testid="display-chip"
            options={[{ value: 'raw', label: 'raw', description: ch.display_unit === null ? 'as stored — this recording declares no unit' : `in mV, converted from the ${ch.units ?? 'declared'} the files hold` }, { value: 'detrended', label: 'detrended (display only)', disabled: true, reason: 'the bridge serves raw mV only — no display transform yet' }]} />
          <InfoTip title="Signal" testid="signal-info">Three tiers on one time axis: the channel, the span you chose, the motif you opened. Press ? for the keyboard map.</InfoTip>
        </>} />

        {ch.display_unit === null && (
          <Callout tone="amber" icon="alert-triangle" testid="unit-undeclared">
            <b>{ch.source_file} declares no unit.</b> Its numbers are drawn as stored and the axis says “?”, not mV. {ch.units_note ?? ''}
          </Callout>
        )}
        {allErr && <ErrorCard error={allErr} title="span list for the whole channel failed" />}
        {runsErr && <ErrorCard error={runsErr} title="GET /api/runs failed" />}
        {demoRead.error && <ErrorCard error={asApiError(demoRead.error)} title="demo read getSignalDemo failed" />}

        {/* one boundary per tier (critique r1: a bad payload in one tier took the whole workspace down) */}
        <ErrorBoundary label="overview tier">
          <Overview ch={ch} view={vp.view} onView={vp.setView} demoDensity={demoDensity} />
        </ErrorBoundary>
        {demoRead.loading ? (
          <div className="skeleton" style={{ height: 420 }} data-testid="signal-demo-loading" />
        ) : drawer ? (
          <>
            <ErrorBoundary label="drawer">
              <SignalDrawer channelKey={String(ch.id)} channelName={ch.name} fs={ch.fs} demo={demo} live={all} tab={drawer} setTab={t => openDrawer(t)} onClose={() => setDrawerQ(null)} view={vp.view} focusSignal={focusSignal}
                onOpenRow={r => {
                  const key = r.kind === 'annotated' ? `a:${r.id}` : `d:${r.id}`   // span-plot: the live keys, on every channel
                  const found = motifs.find(m => m.key === key)
                  const row = r.row as unknown as Record<string, unknown>
                  choose(found ?? { key, kind: r.kind, id: r.id, start_s: r.start_s, end_s: r.end_s, demo: !!demo, verdict: row.verdict as string | undefined, tag: (row.tags as string[] | undefined)?.[0] ?? null,
                    adjudication: row.adjudication as string | undefined, family: (row.family as Motif['family']) ?? null })
                }} />
            </ErrorBoundary>
            <ErrorBoundary label="motif strip">
              <MotifView key="motif-strip" compact ch={ch} motif={sel} label={selLabel} medoid={demo?.medoid ?? null} onSend={() => {}} onReview={() => {}} />
            </ErrorBoundary>
          </>
        ) : (
          <>
            <ErrorBoundary label="span tier">
              <SpanView ch={ch} vp={vp} plotRef={plotRef} width={plotSize.width} bands={bands} selected={sel} selectedLabel={selLabel} onBandClick={m => choose(m, false)}
                nav={{ index, total: motifs.length, capped, prev, next }} legendOpen={popover === 'span-legend'} setLegendOpen={o => setPopover(o ? 'span-legend' : null)} demo={!!demo}
                toggles={toggles} onToggle={flipToggle} bandNote={bandNote} />
            </ErrorBoundary>
            <ErrorBoundary label="motif tier">
              <MotifView key="motif-tier" ch={ch} motif={sel} label={selLabel} medoid={demo?.medoid ?? null} onSend={m => send(m.start_s, m.end_s, `${selLabel ?? `MOTIF ${m.id}`} · ${ch.name}`)} onReview={reviewMotif} />
            </ErrorBoundary>
            <ErrorBoundary label="span actions">
              <SpanActionsBound actionsRef={actions} channelKey={String(ch.id)} channelName={ch.name} recordingId={ch.id} fs={ch.fs} initial={initialDraft} view={vp.view} nInView={inView.length} tagSignal={tagSignal}
                onSend={() => send(vp.view[0], vp.view[1], `${ch.name} · ${fmtRangeH(vp.view[0], vp.view[1])}`)} />
            </ErrorBoundary>
            <ErrorBoundary label="ribbons">
              <Ribbons totals={totals} onOpen={openDrawer} demo={!!demo} />
            </ErrorBoundary>
          </>
        )}
      </div></div>
      <DetectionsPicker runs={runs} st={st} setSt={setPickerSt} open={popover === 'detections'} setOpen={o => setPopover(o ? 'detections' : null)} demo={!!demo} loading={demoRead.loading || (!demo && liveRuns === null && !runsErr)} anchor={pickerAnchor} />
    </>
  )
}

/** SpanActions plus a handle so the page's `R` key can take the span for Review. */
function SpanActionsBound({ actionsRef, ...p }: Parameters<typeof SpanActions>[0] & { actionsRef: React.RefObject<{ take: () => void } | null> }) {
  useEffect(() => {
    actionsRef.current = { take: () => (document.querySelector('[data-testid="take-span"]') as HTMLButtonElement | null)?.click() }
    return () => { actionsRef.current = null }
  }, [actionsRef])
  return <SpanActions {...p} />
}
