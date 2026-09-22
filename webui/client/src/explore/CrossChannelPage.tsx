/* Explore › Cross-channel (frames explore-3 as recorded, explore-3b lag-aligned; spec §5.4 "deliberately loose").
   The same window on every selected channel against a reference: lag, r and a bin per pair, a classification
   summary, hand-offs and the open design questions. Live since stage-3 prompt 01 (getCrossChannel → GET /api/cross/{id}):
   lag, r and the bin are the core's (Working.cross_channel.classify_waveforms) on the window in view.
   Deep links: ?align=lag · ?window=motif-<n> · ?pad=60 · ?channels=4,3,1 · ?maxlag=10 · ?lag=channel ·
   ?y=absolute|centred|per-channel · ?popover=channels · ?questions=open · ?state=computing

   The y scale lives in ./crossScale — read its header before changing how a row is drawn. One absolute
   mV domain across the stack is ~3.9 mV tall on M2_aug while a channel's own window spans 0.001–0.03 mV,
   so an absolute domain draws every trace as a flat line; 'centred' is the default for that reason. */
import { useMemo, useRef, useState } from 'react'
import { ApiError } from '../api'
import { useSourced } from '../api/seam'
import { getCrossChannel, getSignalDemo, lookupChannel, type CrossDemo, type XBin, type XRow } from '../api/explore'
import { EnvelopePath } from '../charts/primitives'
import { makeX } from '../charts/scale'
import { Y_MODES, Y_MODE_LABEL, Y_MODE_NOTE, fmtMvAt, isYMode, scaleNote, stackGeom, type YMode } from './crossScale'
import { Badge, Button, Checkbox, Chip, DisabledReason, Dropdown, EmptyState, Icon, InfoTip, Popover, ProgressBar, Seg, Tooltip, cx, fmtInt, recordDemoWrite, useDemoState, useNotWired, useQueryState, useSim, type IconName } from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { DetectionsChip, DetectionsPicker } from './DetectionsPicker'
import { ErrorCard } from './ErrorCard'
import { LockedCard } from './LockedCard'
import { chipLabel, defaultPicker, pickerRuns, visibleRunIds, type PickerState } from './signalModel'
import { useElementSize } from './useElementSize'
import { asApiError, relativeTicks } from './util'

const BIN_TONE: Record<XBin, 'blue' | 'red' | 'amber' | 'green' | 'grey'> = { reference: 'blue', artifact: 'red', propagation: 'amber', independent: 'green', 'no match': 'grey' }
const BIN_DOT: Record<XBin, string> = { reference: 'var(--blue)', artifact: 'var(--red)', propagation: 'var(--amber)', independent: 'var(--green)', 'no match': '#9ca3af' }
const BIN_TIP: Record<XBin, string> = {
  reference: 'the channel every other row is compared against',
  artifact: 'core rule: |lag| ≤ 1 sample and r ≥ 0.99 — likely a shared electrical path',
  propagation: 'core rule: |lag| ≤ 50 samples (and not an artifact)',
  independent: 'core rule: |lag| > 50 samples — independent recurrence',
  'no match': 'lag or r undefined on this window (flat or non-finite trace)',
}
const CAP = 10
const fmtLag = (l: number | null) => (l === null ? '— s' : l === 0 ? '0.0 s' : `${l > 0 ? '+' : '−'}${Math.abs(l).toFixed(Math.abs(l) >= 10 ? 1 : 2)} s`)

export function CrossChannelPage({ channelId }: { channelId: number }) {
  const look = useSourced(() => lookupChannel(channelId), [channelId])
  const [pad] = useQueryState<string>('pad', '20')
  const read = useSourced(() => getCrossChannel(channelId, pad === '60' ? 60 : 20), [channelId, pad])
  const header = (subtitle: string, demo = true) => <Header workspace="Explore" page="Cross-channel" subtitle={subtitle} search="Search spans, runs, families" demo={demo} />
  if (look.error || read.error) return <>{header(`channel ${channelId} · error`)}<div className="page"><div className="page-inner"><ErrorCard error={asApiError(look.error ?? read.error)} title="demo read for Cross-channel failed" /></div></div></>
  if (look.loading || read.loading || !look.data) return <>{header(`channel ${channelId} · loading…`)}<div className="page"><div className="page-inner" data-testid="cross-loading"><div className="skeleton" style={{ height: 30, width: 480 }} /><div className="skeleton" style={{ height: 50 }} /><div className="skeleton" style={{ height: 440 }} /></div></div></>
  if (look.data.heldOut) {
    return (
      <>{header(`channel ${channelId} · held out`, false)}
        <div className="page"><div className="page-inner">
          <div className="ex-topbar"><div className="ex-crumb"><a onClick={() => navigate('explore/corpus')} data-testid="crumb-corpus">Corpus</a><span>›</span><span className="cur">channel {channelId}</span></div><span className="grow" /><a className="ex-back" onClick={() => navigate('explore/corpus')}>‹ back to corpus</a></div>
          <LockedCard error={new ApiError(423, look.data.reason ?? 'held out')} file="M4_aug_concat_fs1.mat" />
        </div></div>
      </>
    )
  }
  if (!read.data) {
    return (
      <>{header(`channel ${channelId} · no demo data`)}
        <div className="page"><div className="page-inner">
          <EmptyState icon="compare" title={`No cross-channel view for channel ${channelId} in the demo data.`} caption="The demo canon carries the M2_aug fs1 channels (ids 1–16)." bordered testid="cross-unknown"
            action={<Button variant="link" iconRight="arrow-right" onClick={() => navigate('explore/cross-channel/4')}>Open CH4_A2</Button>} />
        </div></div>
      </>
    )
  }
  return <CrossBody key={channelId} data={read.data} />
}

function CrossBody({ data }: { data: CrossDemo }) {
  const toast = useToast()
  const notWired = useNotWired()
  const ref = data.referenceId
  const [align, setAlign] = useQueryState<string>('align', 'recorded')
  const [windowQ] = useQueryState<string>('window', '')
  const [pad, setPad] = useQueryState<string>('pad', '20')
  const [lagMode, setLagMode] = useQueryState<string>('lag', 'window')
  const [maxLagQ, setMaxLag] = useQueryState<string>('maxlag', '30')
  const [channelsQ, setChannelsQ] = useQueryState<string>('channels', '')
  const [yQ, setYQ] = useQueryState<string>('y', 'centred')
  const yMode: YMode = isYMode(yQ) ? yQ : 'centred'
  const [popover, setPopover] = useQueryState<string>('popover', '')
  const [questions, setQuestions] = useQueryState<string>('questions', '')
  const [forced] = useQueryState<string>('state', '')
  const [focusBin, setFocusBin] = useState<XBin | null>(null)
  const sim = useSim(`explore.cross.compute.${ref}`)
  const computing = forced === 'computing' || sim.busy
  const recompute = () => sim.start({ steps: ['computing lag'], stepMs: 600, queuedMs: 0 })
  const maxLag = Number(maxLagQ) || 30

  const selected = useMemo(() => {
    const ids = channelsQ ? channelsQ.split(',').map(Number).filter(n => data.rows.some(r => r.channelId === n)) : data.defaultSelected
    return [ref, ...ids.filter(i => i !== ref)].slice(0, CAP)
  }, [channelsQ, data, ref])
  const setSelected = (ids: number[]) => { setChannelsQ([ref, ...ids.filter(i => i !== ref)].join(',')); recompute() }
  const byId = useMemo(() => new Map(data.rows.map(r => [r.channelId, r])), [data])
  const refName = data.referenceName
  const CORE_BIN: Record<string, XBin> = { reference: 'reference', artifact: 'artifact', propagation: 'propagation', independent_recurrence: 'independent', undefined: 'no match' }
  const binOf = (r: XRow): XBin => {
    if (r.channelId === ref) return 'reference'
    if (r.classification && CORE_BIN[r.classification]) return CORE_BIN[r.classification]     // the core's verdict (Working.cross_channel.classify_waveforms), never re-binned here
    if (r.lagS === null || r.r === null || Math.abs(r.lagS) > maxLag) return 'no match'
    if (r.r >= 0.95 && Math.abs(r.lagS) < 0.5) return 'artifact'
    return r.r >= 0.6 ? 'propagation' : 'independent'
  }
  // the rows are what the bridge measured on this window; no value is rescaled, only the y origin moves
  const rows = selected.map(id => byId.get(id)!).filter(Boolean)
  const counts = { artifact: 0, propagation: 0, independent: 0, 'no match': 0 } as Record<Exclude<XBin, 'reference'>, number>
  for (const r of rows) { const b = binOf(r); if (b !== 'reference') counts[b]++ }
  const sharedPair = rows.find(r => r.sharedGroundWith)
  const windowLabel = `${data.window.label} ± ${pad === '60' ? 60 : 20} s`
  const tooFew = rows.length < 2
  const subtitle = align === 'lag' ? `${refName} reference · lag-aligned` : `${refName} reference · ${rows.length} channel${rows.length === 1 ? '' : 's'}`

  // detections chip: the reference row's runs (the same picker state as Signal)
  const sig = useSourced(() => getSignalDemo(ref), [ref])
  const runs = useMemo(() => pickerRuns(sig.data ?? null, null), [sig.data])
  const [pickerSt, setPickerSt] = useDemoState<PickerState | null>(`explore.signal.picker.${ref}`, () => null)
  const st = pickerSt ?? defaultPicker(sig.data ?? null, runs)
  const vis = visibleRunIds(runs, st)
  // DetectionRow carries samples (api/explore.ts builds them as start_s * fs), the window carries absolute
  // seconds — divide, and overlap the two in the same frame instead of against a fixture-era origin
  const detFs = sig.data?.fs || data.window.fs || 1
  const refDetections = (sig.data?.detections ?? [])
    .filter(d => vis.has(d.runId) && d.end / detFs > data.window.t0S && d.start / detFs < data.window.t0S + data.window.durS)
    .map(d => ({ id: d.id, t0: d.start / detFs, t1: d.end / detFs, colour: st.colourByRun ? runs.find(r => r.id === d.runId)?.colour ?? '#0A84FF' : '#0A84FF' }))
  const pickerAnchor = useRef<HTMLButtonElement>(null)
  const channelsAnchor = useRef<HTMLButtonElement>(null)

  const [hoverT, setHoverT] = useState<number | null>(null)
  const [dragFrom, setDragFrom] = useState<number | null>(null)
  const [dragOver, setDragOver] = useState<number | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const move = (from: number, to: number) => {
    if (from === 0 || to === 0 || from === to) return   // the reference stays first
    const ids = [...selected]; const [x] = ids.splice(from, 1); ids.splice(to, 0, x)
    setChannelsQ(ids.join(','))
  }
  const [plotRef, plotSize] = useElementSize<HTMLDivElement>()
  const W = plotSize.width
  const ROWH = 52   // .panel is 54px with border-box and a 1px border, so 52px is the content box
  const [t0, t1] = [data.window.t0S, data.window.t0S + data.window.durS]
  // one x scale over the window's own absolute seconds, shared by the traces, the band, the detection
  // marks and the axis — the envelope's t is what places a sample, never t0 + i / fs, which stops being
  // true the moment the bridge decimates (min/max buckets are not evenly spaced)
  const x = useMemo(() => makeX(t0, t1, Math.max(1, W)), [t0, t1, W])
  const px = (t: number) => x(t)
  // y geometry: ./crossScale. 'centred' is the default because one absolute domain across electrodes
  // sitting ~3.9 mV apart draws every 0.005 mV waveform as a flat line, which is what this page did.
  const rowsKey = rows.map(r => r.channelId).join(',')
  const geom = useMemo(() => stackGeom(rows, yMode, ROWH, data.yDomain), [rowsKey, yMode, data])  // eslint-disable-line react-hooks/exhaustive-deps
  const ticks = useMemo(() => relativeTicks(t0, t1, data.window.motifStartS, pad === '60' ? 9 : 7), [t0, t1, data.window.motifStartS, pad])
  // lag-aligned slides a row's own time base by the lag the core measured, which is what brings the two
  // waveforms on top of each other; the reference never moves
  const shiftFor = (r: XRow) => (align === 'lag' && r.channelId !== ref && r.lagS !== null && Math.abs(r.lagS) <= maxLag ? r.lagS : 0)
  const reviewAll = () => {
    recordDemoWrite('explore', 'stage-window-for-review', { queue: 'Explore spans', window: windowLabel, channels: rows.map(r => r.name) })
    toast.push({ text: `${rows.length} spans staged for Review`, action: { label: 'Open Review →', onClick: () => navigate('review') } })
  }

  return (
    <>
      <Header workspace="Explore" page="Cross-channel" subtitle={subtitle} search="Search spans, runs, families" demo={false} />   {/* getCrossChannel is live (api/explore.ts) */}
      <div className="page"><div className="page-inner ex-signal" data-testid="cross-page">
        <div className="ex-topbar" data-testid="cross-topbar">
          <div className="ex-crumb">
            <a onClick={() => navigate('explore/corpus')} data-testid="crumb-corpus">Corpus</a><span>›</span>
            <a onClick={() => navigate(`explore/corpus?rec=${encodeURIComponent(data.file)}&ch=${ref}`)}>{data.file}</a><span>›</span>
            <span className="cur">{refName}</span>
          </div>
          <span className="ex-topbar-seg"><Seg size="sm" value="cross" onChange={v => { if (v === 'signal') navigate(`explore/signal/${ref}${windowQ.startsWith('motif-') ? `?motif=${windowQ.slice(6)}` : ''}`) }}
            options={[{ value: 'signal', label: 'Signal' }, { value: 'cross', label: 'Cross-channel' }]} ariaLabel="mode" testid="mode-seg" /></span>
          <DetectionsChip ref={pickerAnchor} label={chipLabel(runs, st)} open={popover === 'detections'} onClick={() => setPopover(popover === 'detections' ? null : 'detections')} />
          <Dropdown variant="outline" prefix="display" value="raw" onChange={() => {}} testid="display-chip"
            options={[{ value: 'raw', label: 'raw' }, { value: 'detrended', label: 'detrended (display only)', disabled: true, reason: 'the bridge serves raw mV — no display transform yet. The y control moves each row’s drawing origin; it does not change a value.' }]} />
          <InfoTip title="Cross-channel">The same window drawn on every selected channel. The detections chip filters the reference row only.</InfoTip>
          <span className="grow" />
          <a className="ex-back" onClick={() => navigate('explore/corpus')} data-testid="back-to-corpus">‹ back to corpus</a>
        </div>

        <div className="card ex-cross-controls" data-testid="cross-controls">
          <Dropdown prefix="reference" variant="outline" value={String(ref)} onChange={v => navigate(`explore/cross-channel/${v}${align === 'lag' ? '?align=lag' : ''}`)} options={data.channels.map(c => ({ value: String(c.id), label: c.name }))} testid="reference-select" menuWidth={180} />
          <button ref={channelsAnchor} type="button" className="k-dd-trigger outline" aria-haspopup="dialog" aria-expanded={popover === 'channels'} onClick={() => setPopover(popover === 'channels' ? null : 'channels')} data-testid="channels-select">
            <span className="pre">channels</span><span className="val">{rows.length} of {data.channels.length}</span><Icon name="chevron-down" size={12} className="chev" />
          </button>
          <Dropdown prefix="window" variant="outline" value={pad === '60' ? '60' : '20'} onChange={v => { setPad(v === '20' ? null : v); recompute() }} testid="window-select" menuWidth={260}
            options={[{ value: '20', label: windowLabel.replace(/± \d+ s/, '± 20 s') }, { value: '60', label: windowLabel.replace(/± \d+ s/, '± 60 s') }, { value: 'span', label: 'selected span 276.4 – 278.4 h', disabled: true, reason: 'longer than 10 min — cross-channel compares short windows' }]} />
          <span className="lbl">align</span>
          <Seg value={align === 'lag' ? 'lag' : 'recorded'} onChange={v => setAlign(v === 'recorded' ? null : v)} options={[{ value: 'recorded', label: 'as recorded' }, { value: 'lag', label: 'lag-aligned' }]} ariaLabel="align" testid="align-seg" />
          <Dropdown prefix="lag" variant="outline" value={lagMode} onChange={v => { setLagMode(v === 'window' ? null : v); recompute() }} testid="lag-select" menuWidth={220}
            options={[{ value: 'window', label: 'computed on window' }, { value: 'channel', label: 'computed on whole channel · not available yet', disabled: true, reason: 'the bridge computes lag on the window in view; a whole-channel lag is a longer job (Prompt 04)' }]} />
          <Dropdown prefix="max lag" variant="outline" value={String(maxLag)} onChange={v => { setMaxLag(v === '30' ? null : v); recompute() }} testid="maxlag-select"
            options={[10, 30, 60].map(n => ({ value: String(n), label: `±${n} s` }))} />
          <Dropdown prefix="y" variant="outline" value={yMode} onChange={v => setYQ(v === 'centred' ? null : v)} testid="y-select" menuWidth={300}
            options={Y_MODES.map(m => ({ value: m, label: Y_MODE_LABEL[m], description: Y_MODE_NOTE[m] }))} />
          <span className="grow" />
          <InfoTip title="Lag, r and the y scale" placement="bottom-end">
            Every selected channel over the reference's window. Lag is where the cross-correlation peaks within max lag; r is its height.
            The channels of this recording sit several mV apart in DC offset while each one&rsquo;s signal inside a window spans
            thousandths of a mV, so one <b>absolute mV</b> domain across the stack flattens every trace. <b>Shared gain, centred</b>
            keeps one mV-per-pixel for the whole stack and moves only each row&rsquo;s origin — no value and no span changes, so depth
            stays comparable. <b>Per channel</b> autoscales each row and is therefore normalised: amplitude no longer compares across
            rows, and every such row says so on the row. r is signed — a row at r &minus;0.9 is genuinely anti-correlated and draws as
            a mirror image of the reference, which is the core&rsquo;s measurement, not a drawing fault.
          </InfoTip>
        </div>

        <div className="card ex-stack" data-testid="channel-stack">
          <div className="ex-stack-head">
            <span className="card-title">Same window, every selected channel</span>
            <span className="range mono">{data.window.startH.toFixed(3)} – {data.window.endH.toFixed(3)} h · {+data.window.durS.toFixed(1)} s</span>
            <span className="muted mono small" data-testid="scale-note">{scaleNote(geom)}</span>
            {yMode === 'per-channel' && <Badge tone="amber" testid="normalised-badge">normalised</Badge>}
            {/* every lag on this corpus is either 0 or past the max-lag cut, so lag-aligned routinely moves
                nothing — leaving it looking applied would be a claim the drawing does not support */}
            {align === 'lag' && !rows.some(r => shiftFor(r)) && <span className="muted mono small" data-testid="nothing-to-align">no row is within ±{maxLag} s — nothing to align</span>}
            {computing && <ProgressBar indeterminate width={220} size="sm" label={`computing lag · ${rows.length} channels`} testid="computing" />}
            <span className="grow" />
            <span className="cols mono"><span>lag</span><span>r</span><span>bin</span></span>
          </div>
          <div className="ex-stack-rows" ref={listRef}>
            {rows.map((r, i) => {
              const bin = binOf(r)
              const dim = focusBin && bin !== focusBin && bin !== 'reference'
              const g = geom.rows[i]
              const shift = shiftFor(r)
              const tShifted = shift ? r.t.map(t => t - shift) : r.t
              return (
                <div key={r.channelId} className={cx('ex-xrow', dim && 'dim', dragOver === i && dragFrom !== null && dragFrom !== i && 'over')} data-testid={`xrow-${r.name}`} data-bin={bin}
                  onPointerEnter={() => { if (dragFrom !== null) setDragOver(i) }}>
                  <button type="button" className="nm ex-link-plain" onClick={() => navigate(`explore/signal/${r.channelId}`)} title={`open ${r.name} in Signal`}>{r.name}</button>
                  {i === 0 ? <span className="grip locked" title="the reference is pinned first"><Icon name="lock" size={11} /></span> : (
                    <button type="button" className={cx('grip', dragFrom === i && 'dragging')} aria-label={`reorder ${r.name} (Alt + ↑ / ↓)`} title="drag to reorder · Alt + ↑ / ↓"
                      onPointerDown={e => { e.preventDefault(); setDragFrom(i); setDragOver(i); const up = () => { window.removeEventListener('pointerup', up); setDragFrom(f => { setDragOver(o => { if (f !== null && o !== null) move(f, o); return null }); return null }) }; window.addEventListener('pointerup', up) }}
                      onKeyDown={e => { if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) { e.preventDefault(); move(i, Math.max(1, Math.min(rows.length - 1, i + (e.key === 'ArrowUp' ? -1 : 1)))) } }}
                      data-testid={`grip-${r.name}`}>⠿</button>
                  )}
                  <div className="panel" ref={i === 0 ? plotRef : undefined}
                    onPointerMove={e => { if (!W) return; const rect = e.currentTarget.getBoundingClientRect(); setHoverT(t0 + ((e.clientX - rect.left) / rect.width) * (t1 - t0)) }} onPointerLeave={() => setHoverT(null)}>
                    {W > 0 && (
                      <svg width={W} height={ROWH} data-testid={i === 0 ? 'reference-trace' : undefined}>
                        <defs><clipPath id={`xclip-${r.channelId}`}><rect x={0} y={0} width={W} height={ROWH} /></clipPath></defs>
                        {/* the window's own span, on the reference only (pages/inventory/explore.md: "the orange motif region on the reference only") */}
                        {i === 0 && <rect x={px(data.window.motifStartS)} y={0} width={Math.max(0, px(data.window.motifEndS) - px(data.window.motifStartS))} height={ROWH} fill="var(--band-selected)" data-testid="cross-motif-region" />}
                        {ticks.map(k => <line key={k.t} x1={px(k.t)} x2={px(k.t)} y1={0} y2={ROWH} stroke="var(--border)" strokeOpacity={0.7} />)}
                        {i === 0 && refDetections.map(d => <rect key={d.id} x={px(d.t0)} y={0} width={Math.max(2, px(d.t1) - px(d.t0))} height={4} rx={1} fill={d.colour} data-testid="cross-detection"><title>{`detection ${d.id}`}</title></rect>)}
                        <g clipPath={`url(#xclip-${r.channelId})`}>
                          {/* the baseline 'centred' subtracted, carrying its value: a dashed line with no number
                              attached is the line a reader mistakes for zero. Never drawn in 'per-channel',
                              where the origin is an autoscaled midpoint and means nothing. */}
                          {g?.centreIsBaseline && <line x1={0} x2={W} y1={g.y(g.centre)} y2={g.y(g.centre)} stroke="var(--border-strong)" strokeOpacity={0.5} strokeDasharray="2 4" data-testid={`baseline-${r.name}`}><title>{`baseline ${fmtMvAt(g.centre, g.places)} mV — subtracted for drawing only`}</title></line>}
                          {g && <EnvelopePath t={tShifted} v={r.v} x={x} y={g.y} stroke={i === 0 ? 'var(--blue)' : 'var(--trace)'} width={1.2} testid={`xtrace-${r.name}`} />}
                        </g>
                        {/* short in the panel, whole on hover: the panel clips, and a loud failure trimmed
                            into a blank is the thing CLAUDE.md's web-UI gate forbids */}
                        {r.error && <text x={6} y={ROWH / 2 + 4} className="mono ex-xrow-err" data-testid={`xrow-error-${r.name}`}>{r.error.split(':')[0]} — read failed<title>{r.error}</title></text>}
                        {!r.error && g && !g.extent && <text x={6} y={ROWH / 2 + 4} className="mono ex-xrow-err">no finite sample in this window</text>}
                        {/* the row's own ABSOLUTE extent, in every mode — the sentence that makes centring
                            honest, since the raw record is still stated when the drawing origin has moved */}
                        {g?.extent && <text x={W - 4} y={ROWH - 4} textAnchor="end" className="mono ex-xrow-mv" data-testid={`mv-${r.name}`}>
                          {yMode === 'per-channel' ? 'own scale · ' : ''}{fmtMvAt(g.extent[0], g.places)} … {fmtMvAt(g.extent[1], g.places)} mV
                        </text>}
                        {hoverT !== null && <line x1={px(hoverT)} x2={px(hoverT)} y1={0} y2={ROWH} stroke="var(--blue)" strokeOpacity={0.55} strokeDasharray="3 3" data-testid="crosshair" />}
                        {hoverT !== null && i === 0 && <text x={Math.min(px(hoverT) + 5, W - 60)} y={12} className="mono ex-xrow-mv">t = {hoverT - data.window.motifStartS >= 0 ? '+' : '−'}{Math.abs(hoverT - data.window.motifStartS).toFixed(1)} s</text>}
                      </svg>
                    )}
                  </div>
                  <span className="dot" style={{ background: BIN_DOT[bin] }} />
                  {/* lag-aligned leaves a row past max lag where it was — say so on the row rather than
                      letting the stack claim an alignment it did not apply */}
                  <span className="lag mono">{computing ? '…' : align === 'lag' && i > 0 && r.lagS !== null && Math.abs(r.lagS) > maxLag
                    ? <Tooltip content={`|lag| ${Math.abs(r.lagS).toFixed(1)} s is past max lag ±${maxLag} s — this row is still as recorded`}><span className="ex-unaligned" data-testid={`lag-unaligned-${r.name}`}>{fmtLag(r.lagS)} ·&nbsp;not aligned</span></Tooltip>
                    : fmtLag(r.lagS)}</span>
                  <span className="r mono">{computing ? '…' : r.channelId === ref ? '' : r.r === null ? '—' : r.r.toFixed(2)}</span>
                  <span className="bin"><Tooltip content={BIN_TIP[bin]}><span><Badge tone={BIN_TONE[bin]} testid={`bin-${r.name}`}>{bin}</Badge></span></Tooltip></span>
                </div>
              )
            })}
            {tooFew && (
              <div className="ex-xrow-empty" data-testid="too-few">
                <EmptyState size="sm" icon="compare" title={`Pick at least one more channel to compare against ${refName}.`} action={<Button size="sm" onClick={() => setPopover('channels')} testid="choose-channels">Choose channels</Button>} />
              </div>
            )}
          </div>
          <div className="ex-stack-axis mono">
            <span />
            {/* positions absolute, labels relative to the window's onset — and the frame said out loud */}
            <div className="ticks" style={{ width: W || undefined }} data-testid="cross-axis">{W > 0 && ticks.map(k => <span key={k.t} style={{ left: px(k.t) }}>{k.label}</span>)}</div>
            <span className="frame">s from onset</span>
          </div>
        </div>

        <div className="ex-cross-bottom">
          <div className="card card-pad" data-testid="classification">
            <div className="ex-card-head"><b>Classification for this window</b><InfoTip title="Classification">Each channel is paired with the reference and binned by lag and r. Shared-ground pairs come from Settings › Channels &amp; events.</InfoTip><span className="grow" /><span className="muted mono small">pairs against {refName} reference</span></div>
            <div className={cx('ex-tiles', computing && 'dim')}>
              {(['artifact', 'propagation', 'independent', 'no match'] as const).map(b => (
                <button key={b} type="button" className={cx('ex-tile', `t-${BIN_TONE[b]}`, focusBin === b && 'on')} onClick={() => setFocusBin(focusBin === b ? null : b)} aria-pressed={focusBin === b} data-testid={`tile-${b.replace(' ', '-')}`}
                  title={focusBin === b ? 'click again to clear' : `highlight the ${b} rows`}>
                  <span className="n">{computing ? '…' : counts[b]}</span><span className="l">{b}</span>
                </button>
              ))}
            </div>
            {sharedPair && (
              <div className="ex-warn" data-testid="shared-ground-warning"><Icon name="alert-triangle" size={13} />
                <span>{sharedPair.name} ↔ {sharedPair.sharedGroundWith} is a known shared-ground pair — excluded from recurrence counts · <button type="button" className="ex-link" onClick={() => navigate('settings/channels')}>Settings › Channels &amp; events</button></span>
              </div>
            )}
          </div>
          <div className="card card-pad" data-testid="take-further">
            <b style={{ display: 'block', marginBottom: 8 }}>Take it further</b>
            <ActionRow icon="library" title="Classify every F-03 member in Library" caption="runs across all channels and stores bins on edges" testid="act-classify" onClick={() => notWired('classify F-03 members across channels (Library edges job)')} />
            <ActionRow icon="target" title={`Apply a template across these ${rows.length} channels`} caption="opens Discovery with a channel scope" testid="act-template" onClick={() => navigate(`discovery/runs?modal=add-template&channels=${selected.join(',')}`)} />
            <ActionRow icon="checklist" title="Review this window on all channels" caption={`stages ${rows.length} spans in Review`} testid="act-review" onClick={reviewAll} disabled={tooFew} reason="pick at least one more channel first" />
          </div>
        </div>

        <div className="card ex-questions" data-testid="open-questions">
          <button type="button" className="ex-disclosure" aria-expanded={questions === 'open'} onClick={() => setQuestions(questions === 'open' ? null : 'open')} data-testid="questions-toggle">
            <Icon name="chevron-right" size={13} className={questions === 'open' ? 'rot90' : ''} /><b>Open design questions</b><span className="muted mono small">{data.openQuestions.length} · multivariate direction parked</span>
          </button>
          {questions === 'open' && <ol className="ex-qlist" data-testid="questions-list">{data.openQuestions.map(q => <li key={q}>{q}</li>)}</ol>}
        </div>
      </div></div>

      <Popover open={popover === 'channels'} onClose={() => setPopover(null)} anchorRef={channelsAnchor} width={300} testid="channels-popover"
        title={<span className="row" style={{ justifyContent: 'space-between', width: '100%' }}>Channels<span className="ex-links"><button type="button" onClick={() => setSelected([])} data-testid="channels-none">select none</button></span></span>}>
        <div className="ex-pick-list">
          {data.channels.map(c => {
            const on = selected.includes(c.id)
            const isRef = c.id === ref
            const capped = !on && selected.length >= CAP
            const shared = (refName === 'CH4_A2' && c.name === 'CH3_A2') || (refName === 'CH3_A2' && c.name === 'CH4_A2')
            return (
              <div key={c.id} className="row between" style={{ gap: 8 }}>
                <Checkbox checked={on} onChange={v => setSelected(v ? [...selected, c.id] : selected.filter(x => x !== c.id))} label={c.name} disabled={isRef || capped}
                  disabledReason={isRef ? 'the reference is always shown' : `at most ${CAP} channels in one stack (P8)`} testid={`channel-opt-${c.name}`} />
                {shared && <Chip size="sm" tone="amber">shared ground</Chip>}
              </div>
            )
          })}
        </div>
        <div className="muted mono small" style={{ marginTop: 6 }}>{fmtInt(selected.length)} of {data.channels.length} · cap {CAP}</div>
      </Popover>
      <DetectionsPicker runs={runs} st={st} setSt={setPickerSt} open={popover === 'detections'} setOpen={o => setPopover(o ? 'detections' : null)} demo={!!sig.data} loading={sig.loading} anchor={pickerAnchor} />
    </>
  )
}

function ActionRow({ icon, title, caption, onClick, testid, disabled, reason }: { icon: IconName; title: string; caption: string; onClick: () => void; testid: string; disabled?: boolean; reason?: string }) {
  const btn = (
    <button type="button" className="ex-action" onClick={onClick} disabled={disabled} data-testid={testid}>
      <Icon name={icon} size={15} className="ic" /><span className="body"><span className="t">{title}</span><span className="c">{caption}</span></span><Icon name="arrow-right" size={14} />
    </button>
  )
  return disabled && reason ? <DisabledReason reason={reason} block>{btn}</DisabledReason> : btn
}

