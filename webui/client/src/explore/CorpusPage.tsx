/* Explore › Corpus (frames explore-1-corpus, explore-1b-corpus-menus): recording toolbar, the channels ×
   time coverage map, the filter rail and the selected-channel bottom bar.

   All of it is live: /api/recordings, /api/corpus/{file}/coverage (map, verdict filter, run and method
   filters, counts) and, through `getCorpusLive`, the tag vocabulary with per-channel counts, reviewed
   coverage and the run / method lists. Nothing on this page is fixture-backed; it said otherwise in
   four places until fixup-a items 13 and 15. The held-out recording renders a locked card and is never
   fetched.
   Deep links: ?rec=<file> · ?ch=<id> · ?colour=<annotations|detections|both|disagree> · ?popover=recordings|legend
   · ?state=no-selection|nothing-shown|zero-match|loading|error */
import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, getCoverageFiltered, getRecordings, type Coverage, type RecordingFile } from '../api'
import { useSourced } from '../api/seam'
import { getCorpusLive } from '../api/explore'
import { Button, Dropdown, EmptyState, Icon, IconButton, Popover, useQueryState } from '../kit'
import { ErrorBoundary } from '../shell/ErrorBoundary'
import { Header } from '../shell/Header'
import { navigate, setQuery, useApp } from '../state'
import { DemoTag, LegendRow } from './bits'
import { ErrorCard } from './ErrorCard'
import { DISAGREE_DEF, Heatmap } from './Heatmap'
import { LockedCard } from './LockedCard'
import { RecordingMenu } from './RecordingMenu'
import { RightRail, type DemoFilters, type ShowState } from './RightRail'
import { TimeRange } from './TimeRange'
import { AMBER_RAMP, asApiError, COLOUR_BY, COLOUR_BY_LABEL, fmtInt, MATRIX_UNIT, RAMP, VERDICTS, type ColourBy } from './util'

const BIN_CHOICES = [57, 28, 114]
type ForcedState = '' | 'no-selection' | 'nothing-shown' | 'zero-match' | 'loading' | 'error'

export function CorpusPage() {
  const { explore, setExplore } = useApp()
  const [popover, setPopover] = useQueryState<string>('popover', '')
  const [forced, setForced] = useQueryState<ForcedState>('state', '')
  const [recQ] = useQueryState<string>('rec', '')
  const [chQ] = useQueryState<string>('ch', '')
  const [colourQ] = useQueryState<string>('colour', '')

  const [recs, setRecs] = useState<RecordingFile[] | null>(null)
  const [recErr, setRecErr] = useState<ApiError | null>(null)
  useEffect(() => {
    let alive = true
    getRecordings().then(r => { if (alive) setRecs(r) }).catch(e => { if (alive) setRecErr(asApiError(e)) })
    return () => { alive = false }
  }, [])
  // deep-link overrides (?rec, ?ch, ?colour) are applied once they are readable
  useEffect(() => {
    const patch: Partial<typeof explore> = {}
    if (recQ && recQ !== explore.file) Object.assign(patch, { file: recQ, channelId: null, view: null })
    if (chQ && Number(chQ) !== explore.channelId) patch.channelId = Number(chQ)
    if (colourQ && (COLOUR_BY as string[]).includes(colourQ) && colourQ !== explore.colourBy) patch.colourBy = colourQ
    if (Object.keys(patch).length) setExplore(patch)
  }, [recQ, chQ, colourQ])  // eslint-disable-line react-hooks/exhaustive-deps

  const files = recs ?? []
  const openFiles = useMemo(() => files.filter(f => !f.held_out), [files])
  const file = useMemo(() => files.find(f => f.source_file === explore.file) ?? openFiles[0] ?? null, [files, openFiles, explore.file])
  const colourBy: ColourBy = (COLOUR_BY as string[]).includes(explore.colourBy) ? (explore.colourBy as ColourBy) : 'both'
  const [bins, setBins] = useState(57)
  const [show, setShow] = useState<ShowState>({ annotations: true, detections: true, reviewed: false, unreviewedOnly: false })
  const [verdicts, setVerdicts] = useState<string[]>(['seed', 'interesting'])
  const [filters, setFilters] = useState<DemoFilters>({ runs: null, methods: null, tags: ['sharkfin'] })
  const [cov, setCov] = useState<Coverage | null>(null)
  const [covErr, setCovErr] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(false)
  const [lockErr, setLockErr] = useState<ApiError | null>(null)
  const [cleared, setCleared] = useState(false)
  const fileName = file?.source_file ?? null
  const heldOut = file?.held_out ?? false
  const durH = file?.duration_h ?? 0
  const [range, setRange] = useState<[number, number] | null>(null)
  useEffect(() => { setRange(null) }, [fileName])

  // forced deep-link states drive the real controls, so the page is in that state rather than painted as it
  useEffect(() => {
    if (!forced) return
    setShow(s => ({ ...s, annotations: forced !== 'nothing-shown', detections: forced !== 'nothing-shown' }))
    setVerdicts(v => (forced === 'zero-match' ? [] : v.length ? v : ['seed', 'interesting']))
    setCleared(forced === 'no-selection')
  }, [forced])

  const verdictKey = verdicts.length === VERDICTS.length ? '' : verdicts.join(',')
  const noVerdicts = verdicts.length === 0
  const rows = useMemo(() => (cov && cov.source_file === fileName ? cov.rows : []), [cov, fileName])
  const names = useMemo(() => rows.map(r => r.name), [rows])
  const chanRefs = useMemo(() => rows.map(r => ({ id: r.id, name: r.name })), [rows])
  const demoRead = useSourced(() => getCorpusLive(fileName ?? '', chanRefs, bins), [fileName, names.join(','), bins])
  const demo = demoRead.data

  /* The run and method filters go to the route, which has served `run=` and
   * `method=` all along; this page fetched the unfiltered map and printed a
   * note admitting it (fixup-a item 15). Both rail pickers are multi-select
   * while `method=` is one substring, so the pair is resolved to the run ids
   * it names - against the same run list the rail shows - and sent as `run=`.
   * Exact, and it needs nothing new on the server.
   *
   * An empty intersection is NOT "no filter": `run=-1` matches no run, so the
   * detection layers come back empty, which is what was asked for. Sending
   * nothing would quietly show every run instead. */
  const runIdFilter = useMemo<number[] | undefined>(() => {
    if (!filters.runs && !filters.methods) return undefined
    const keep = (demo?.runs ?? []).filter(r => (!filters.runs || filters.runs.includes(r.id))
      && (!filters.methods || filters.methods.includes(r.method)))
    const ids = keep.map(r => Number(String(r.id).replace('#', ''))).filter(n => Number.isFinite(n))
    return ids.length ? ids : [-1]
  }, [filters.runs, filters.methods, demo])
  const runKey = (runIdFilter ?? []).join(',')

  useEffect(() => {
    if (!fileName) return
    let alive = true
    if (heldOut) {
      // Never fetch anything for the held-out recording: the locked card carries the server's own
      // refusal text from /api/recordings (held_out_reason), so no data request is ever made for M4.
      setCov(null)
      setLockErr(new ApiError(423, file?.held_out_reason ?? `${fileName} is held out (spec §0 D6)`))
      return () => { alive = false }
    }
    setLoading(true); setCovErr(null)
    // zero-match (no verdict ticked) still fetches the rows so the grid can be drawn, then blanks every cell
    getCoverageFiltered(fileName, bins, {
      verdicts: verdictKey && !noVerdicts ? verdictKey.split(',') : undefined,
      run: runIdFilter,
    })
      .then(c => { if (!alive) return; setCov(c); setLoading(false) })
      .catch(e => { if (!alive) return; setCovErr(asApiError(e)); setLoading(false) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileName, heldOut, file, bins, verdictKey, noVerdicts, runKey])

  const nothingShown = !show.annotations && !show.detections
  const matrix: ColourBy | null = nothingShown ? null : show.annotations && show.detections ? colourBy : show.annotations ? 'annotations' : 'detections'
  const selId = useMemo(() => {
    if (!rows.length || cleared) return null
    if (explore.channelId != null && rows.some(r => r.id === explore.channelId)) return explore.channelId
    return (rows.find(r => r.name === 'CH4_A2') ?? rows[0]).id
  }, [rows, explore.channelId, cleared])
  const selRow = rows.find(r => r.id === selId) ?? null

  // matching readout: live from the drawn matrix, or the demo tag count when a tag is ticked
  const demoChannels = demo?.channels
  const matching = useMemo(() => {
    const total = rows.length || file?.n_channels || 0
    // the note that admitted the map ignored the run / method filters is gone:
    // the route is given them now (fixup-a item 15)
    const runNote = runIdFilter && runIdFilter[0] === -1
      ? 'no run matches both filters — the detection layers are empty by request' : undefined
    if (noVerdicts) return { spans: 0, channels: 0, total, demo: false, note: runNote }
    if (filters.tags.length && demoChannels) {
      let spans = 0, channels = 0
      for (const c of demoChannels) {
        let s = filters.tags.reduce((a, t) => a + (c.tagCounts[t] ?? 0), 0)
        if (show.unreviewedOnly) s = Math.round(s * (1 - c.reviewedPct / 100))
        spans += s; if (s > 0) channels++
      }
      return { spans, channels, total, demo: false, note: runNote }
    }
    let spans = 0, channels = 0
    if (matrix) for (const r of rows) { const vals = r[matrix]; if (!Array.isArray(vals)) continue; let s = 0; for (const c of vals) s += Number(c) || 0; spans += s; if (s > 0) channels++ }
    return { spans, channels, total, demo: false, note: runNote }
  }, [rows, matrix, filters, demoChannels, show.unreviewedOnly, forced, noVerdicts, file, runIdFilter])
  const zeroMatch = matching.spans === 0 && !nothingShown && (rows.length > 0 || noVerdicts)
  const overlay = useMemo(() => ({
    reviewed: demoChannels ? Object.fromEntries(demoChannels.map(c => [c.name, c.reviewed])) : undefined,
    hatchUnreviewed: show.reviewed, dimReviewed: show.unreviewedOnly,
    dimRows: filters.tags.length && demoChannels ? new Set(demoChannels.filter(c => filters.tags.every(t => !(c.tagCounts[t] > 0))).map(c => c.name)) : undefined,
    blank: zeroMatch,
  }), [demoChannels, show.reviewed, show.unreviewedOnly, filters.tags, zeroMatch])

  const select = (id: number) => { setCleared(false); if (forced === 'no-selection') setForced(null); if (id !== selId) setExplore({ channelId: id, view: null }) }
  const open = (id: number) => navigate(`explore/signal/${id}`)
  const pickFile = (f: RecordingFile) => { setCleared(false); setExplore({ file: f.source_file, channelId: null, view: null }); if (recQ) setQuery({ rec: null, ch: null }, true) }
  const pageIdx = files.findIndex(f => f.source_file === fileName)
  const binH = cov && cov.source_file === fileName ? cov.bin_h : durH / bins
  const c = selRow?.counts
  const legendRef = useRef<HTMLButtonElement>(null)
  const shownRange: [number, number] = range ?? [0, Math.round(durH * 10) / 10]
  const rangeLabel = `${fmtH(shownRange[0])} – ${fmtH(shownRange[1])} h`
  const clearFilters = () => { setVerdicts(VERDICTS); setFilters({ runs: null, methods: null, tags: [] }); setShow(s => ({ ...s, unreviewedOnly: false })); if (forced === 'zero-match') setForced(null) }
  const showLoading = forced === 'loading'
  const forcedErr = forced === 'error' ? new ApiError(500, `GET /api/corpus/${fileName ?? '<file>'}/coverage?bins=${bins} failed (forced by ?state=error: the page's failure state)`) : null
  const selectionReason = heldOut ? 'held out · locked' : !selRow ? 'select a channel first' : undefined

  return (
    <>
      <Header workspace="Explore" page="Corpus" subtitle="bird's-eye across every channel" search="Search spans, runs, families" demo={demoRead.source === 'demo' && !heldOut} />
      <div className="page"><div className="page-inner">
        <div className="ex-toolbar" data-testid="corpus-toolbar">
          <RecordingMenu files={recs} current={file} open={popover === 'recordings'} setOpen={o => setPopover(o ? 'recordings' : null)} onPick={pickFile} />
          <span className="ex-pager" data-testid="recording-pager">
            <IconButton icon="chevron-left" label="previous recording" disabled={pageIdx <= 0} disabledReason="already at the first recording" onClick={() => pickFile(files[pageIdx - 1])} testid="recording-prev" />
            <span>{pageIdx >= 0 ? pageIdx + 1 : '–'} / {files.length || '–'}</span>
            <IconButton icon="chevron-right" label="next recording" disabled={pageIdx < 0 || pageIdx >= files.length - 1} disabledReason="already at the last recording" onClick={() => pickFile(files[pageIdx + 1])} testid="recording-next" />
          </span>
          <span className="divider-v" />
          <TimeRange durH={Math.round(durH * 10) / 10 || 1} value={shownRange} onChange={v => setRange(v[0] <= 0 && v[1] >= Math.round(durH * 10) / 10 ? null : v)} />
          <Dropdown prefix="bin" variant="outline" value={String(bins)} onChange={v => setBins(Number(v))} testid="bin-select"
            options={BIN_CHOICES.map(b => ({ value: String(b), label: `${b === 57 ? 'auto · ' : ''}${durH ? (durH / b).toFixed(1) : '—'} h`, hint: `${b} bins` }))} />
          <span className="divider-v" />
          <span className="lbl">colour by</span>
          <div className="seg" data-testid="colour-by">
            {COLOUR_BY.map(k => <button key={k} className={colourBy === k ? 'on' : ''} onClick={() => setExplore({ colourBy: k })} data-testid={`colour-by-${k}`}
              title={k === 'both' ? 'annotations + detections per bin \u2014 a sum, not the bins where both are present' : undefined}>{COLOUR_BY_LABEL[k]}</button>)}
          </div>
          {loading && <span className="muted">loading…</span>}
        </div>

        {recErr && <ErrorCard error={recErr} title="GET /api/recordings failed" />}
        {covErr && <ErrorCard error={covErr} title={`coverage for ${fileName} failed`} />}
        {demoRead.error && <ErrorCard error={asApiError(demoRead.error)} title="live read getCorpusLive failed" />}
        {forcedErr && <ErrorCard error={forcedErr} title={`coverage for ${fileName} failed`} />}

        {heldOut ? (
          <LockedCard error={lockErr} file={fileName ?? undefined} />
        ) : forcedErr ? null : (
          <div className="ex-corpus-grid">
            <div className="card card-pad ex-map-card" data-testid="coverage-card">
              <div className="ex-card-head">
                <span className="card-title">Coverage map</span>
                <span className="meta">{rows.length || file?.n_channels || '—'} channels · {rangeLabel} · bin {binH ? binH.toFixed(1) : '—'} h</span>
                <span className="grow" />
                <span className="ex-ramp-block">
                  <span className="meta" data-testid="matrix-label">{matrix ?? 'nothing shown'} · spans per bin</span>
                  <span className="ex-legend" data-testid="ramp-legend" data-ramp={matrix === 'disagree' ? 'amber' : 'blue'}>low {(matrix === 'disagree' ? AMBER_RAMP : RAMP).map(col => <i key={col} style={{ background: col }} />)} high</span>
                </span>
                <button ref={legendRef} type="button" className="k-icon-btn bordered" aria-label="Reading the coverage map" title="Reading the coverage map" aria-expanded={popover === 'legend'}
                  onClick={() => setPopover(popover === 'legend' ? null : 'legend')} data-testid="map-legend-button"><Icon name="info" size={14} /></button>
              </div>
              <div className="mono" style={{ fontSize: 10, color: 'var(--muted-2)', marginBottom: 2 }}>channel</div>
              <div className="ex-map-wrap" onKeyDown={e => { if (e.key === 'Escape' && !e.defaultPrevented) { setCleared(true) } }}>
                {cov && cov.source_file === fileName && !showLoading ? (
                  <ErrorBoundary label="coverage map">
                    <Heatmap cov={cov} matrix={matrix} unit={matrix ? MATRIX_UNIT[matrix] : 'spans'} selectedId={selId} onSelect={select} onOpen={open} range={range ?? undefined} overlay={overlay} />
                  </ErrorBoundary>
                ) : covErr ? null : <div className="skeleton" style={{ height: 16 * 34 + 22 }} data-testid="coverage-skeleton" />}
                {nothingShown && !showLoading && (
                  <div className="ex-map-empty" data-testid="nothing-shown">
                    <EmptyState icon="eye-off" title="nothing shown" caption="Tick annotations or detections to colour the map." bordered
                      action={<Button size="sm" onClick={() => { setShow(s => ({ ...s, annotations: true, detections: true })); if (forced === 'nothing-shown') setForced(null) }} testid="show-both">Show both</Button>} />
                  </div>
                )}
              </div>
              {zeroMatch && <div className="ex-zero" data-testid="zero-match">no span matches these filters · <button type="button" className="ex-link" onClick={clearFilters}>clear filters</button></div>}
              {show.reviewed && <div className="muted small mono" style={{ marginTop: 6 }} data-testid="reviewed-caption">hatched bins have not been reviewed <DemoTag /></div>}
            </div>
            <RightRail cov={cov && cov.source_file === fileName ? cov : null} demo={demo} show={show} setShow={setShow} verdicts={verdicts} setVerdicts={setVerdicts}
              filters={filters} setFilters={setFilters} matching={matching} />
          </div>
        )}

        <div className="card ex-bottom" data-testid="corpus-bottom-bar">
          <div className="row" style={{ gap: 18 }}>
            <span className="name" data-testid="selected-channel-name">{heldOut ? '—' : selRow?.name ?? '—'}</span>
            <span className="counts" title={`disagree = ${DISAGREE_DEF}`} data-testid="selected-channel-counts">
              {heldOut ? 'held out · no channel can be opened' : c
                ? `${fmtInt(c.annotations)} annotations · ${fmtInt(c.detections)} detections · ${
                  // "disagree" compares the two sources; with one of them empty there is nothing to compare (critique r1)
                  c.detections > 0 && c.annotations > 0 ? `${fmtInt(c.disagree)} disagree` : `— disagree (${c.detections > 0 ? 'no annotations' : 'no detections'})`
                } · ${c.reviewed_pct == null ? '—' : Math.round(c.reviewed_pct) + ' %'} reviewed`
                : 'select a channel'}
            </span>
          </div>
          <div className="row">
            <Button icon="grid" disabled={!!selectionReason} disabledReason={selectionReason} onClick={() => selRow && navigate(`explore/cross-channel/${selRow.id}`)} testid="cross-channel-from">Cross-channel from {selRow?.name ?? '…'}</Button>
            <Button variant="primary" iconRight="arrow-right" disabled={!!selectionReason} disabledReason={selectionReason} onClick={() => selRow && open(selRow.id)} testid="open-channel">Open {selRow?.name ?? '…'}</Button>
          </div>
        </div>
      </div></div>

      <Popover open={popover === 'legend' && !heldOut} onClose={() => setPopover(null)} anchorRef={legendRef} placement="bottom-end" width={340} title="Reading the coverage map" testid="map-legend">
        <div className="ex-legend-pop">
          <LegendRow swatch={<span className="ramp">{RAMP.slice(1).map(col => <i key={col} style={{ background: col }} />)}</span>}>Cell darkness is spans per bin, counted under ‘colour by’. Grey cells hold none. Shades are quantile ranks among the non-zero cells.</LegendRow>
          <LegendRow swatch={<span className="outline" />}>Outlined row is the selected channel. Click to select, double-click to open.</LegendRow>
          <LegendRow swatch={<span className="solid" style={{ background: 'var(--amber)' }} />}>Disagree mode: amber where a detection has no overlapping annotation or the reverse.</LegendRow>
          <div className="foot">A tag that clusters on two channels is a lead; one spread evenly is probably not.</div>
        </div>
      </Popover>
    </>
  )
}

function fmtH(h: number) { return Number.isInteger(h) ? String(h) : h >= 10 ? String(Math.round(h)) : h.toFixed(1) }
