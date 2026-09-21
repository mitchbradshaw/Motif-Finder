/* Explore › Cross-channel (frames explore-3 as recorded, explore-3b lag-aligned; spec §5.4 "deliberately loose").
   The same window on every selected channel against a reference: lag, r and a bin per pair, a classification
   summary, hand-offs and the open design questions. Live since stage-3 prompt 01 (getCrossChannel → GET /api/cross/{id}):
   lag, r and the bin are the core's (Working.cross_channel.classify_waveforms) on the window in view.
   Deep links: ?align=lag · ?window=motif-<n> · ?pad=60 · ?channels=4,3,1 · ?maxlag=10 · ?lag=channel ·
   ?popover=channels · ?questions=open · ?state=computing */
import { useMemo, useRef, useState } from 'react'
import { ApiError } from '../api'
import { useSourced } from '../api/seam'
import { getCrossChannel, getSignalDemo, lookupChannel, type CrossDemo, type XBin, type XRow } from '../api/explore'
import { Badge, Button, Checkbox, Chip, DisabledReason, Dropdown, EmptyState, Icon, InfoTip, Popover, ProgressBar, Seg, Tooltip, cx, fmtInt, recordDemoWrite, useDemoState, useNotWired, useQueryState, useSim, type IconName } from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { DetectionsChip, DetectionsPicker } from './DetectionsPicker'
import { ErrorCard } from './ErrorCard'
import { LockedCard } from './LockedCard'
import { chipLabel, defaultPicker, pickerRuns, visibleRunIds, type PickerState } from './signalModel'
import { useElementSize } from './useElementSize'
import { asApiError } from './util'

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
  // the rows are what the bridge measured on this window; nothing is rescaled client-side
  const effective = (r: XRow): XRow => r
  const CORE_BIN: Record<string, XBin> = { reference: 'reference', artifact: 'artifact', propagation: 'propagation', independent_recurrence: 'independent', undefined: 'no match' }
  const binOf = (r: XRow): XBin => {
    if (r.channelId === ref) return 'reference'
    if (r.classification && CORE_BIN[r.classification]) return CORE_BIN[r.classification]     // the core's verdict (Working.cross_channel.classify_waveforms), never re-binned here
    if (r.lagS === null || r.r === null || Math.abs(r.lagS) > maxLag) return 'no match'
    if (r.r >= 0.95 && Math.abs(r.lagS) < 0.5) return 'artifact'
    return r.r >= 0.6 ? 'propagation' : 'independent'
  }
  const rows = selected.map(id => byId.get(id)!).filter(Boolean).map(effective)
  const counts = { artifact: 0, propagation: 0, independent: 0, 'no match': 0 } as Record<Exclude<XBin, 'reference'>, number>
  for (const r of rows) { const b = binOf(r); if (b !== 'reference') counts[b]++ }
  const sharedPair = rows.find(r => r.sharedGroundWith)
  const windowLabel = `${windowQ.startsWith('motif-') ? `MOTIF_${windowQ.slice(6)}` : 'MOTIF_233'} ± ${pad === '60' ? 60 : 20} s`
  const tooFew = rows.length < 2
  const subtitle = align === 'lag' ? `${refName} reference · lag-aligned` : `${refName} reference · ${rows.length} channel${rows.length === 1 ? '' : 's'}`

  // detections chip: the reference row's runs (the same picker state as Signal)
  const sig = useSourced(() => getSignalDemo(ref), [ref])
  const runs = useMemo(() => pickerRuns(sig.data ?? null, null), [sig.data])
  const [pickerSt, setPickerSt] = useDemoState<PickerState | null>(`explore.signal.picker.${ref}`, () => null)
  const st = pickerSt ?? defaultPicker(sig.data ?? null, runs)
  const vis = visibleRunIds(runs, st)
  const motifStartAbs = 998323
  const refDetections = (sig.data?.detections ?? []).filter(d => vis.has(d.runId) && d.end > motifStartAbs + data.window.t0S && d.start < motifStartAbs + data.window.t0S + data.window.durS)
    .map(d => ({ id: d.id, t0: d.start - motifStartAbs, t1: d.end - motifStartAbs, colour: st.colourByRun ? runs.find(r => r.id === d.runId)?.colour ?? '#0A84FF' : '#0A84FF' }))
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
  const [t0, t1] = [data.window.t0S, data.window.t0S + data.window.durS]
  const px = (t: number) => ((t - t0) / (t1 - t0)) * W
  // one shared mV scale across the stack (§3: never normalised per row), from the drawn rows' extent
  const [y0, y1] = useMemo((): [number, number] => {
    let lo = Infinity, hi = -Infinity
    for (const r of rows) for (const v of r.trace) { if (v < lo) lo = v; if (v > hi) hi = v }
    if (!(lo < hi)) return data.yDomain
    const m = (hi - lo) * 0.06
    return [lo - m, hi + m]
  }, [rows.map(r => r.channelId).join(','), data])  // eslint-disable-line react-hooks/exhaustive-deps
  const ROWH = 54
  const py = (v: number) => ROWH - 3 - ((v - y0) / (y1 - y0)) * (ROWH - 6)
  const ticks = [-20, -10, 0, 10, 20, 30, 40].filter(t => t >= t0 && t <= t1)
  if (pad === '60') ticks.splice(0, ticks.length, -60, -40, -20, 0, 20, 40, 60, 80)

  const pathFor = (r: XRow) => {
    const shift = align === 'lag' && r.channelId !== ref && r.lagS !== null && Math.abs(r.lagS) <= maxLag ? r.lagS : 0
    let d = ''
    r.trace.forEach((v, i) => { const t = t0 + i / data.window.fs - shift; d += `${i ? 'L' : 'M'}${px(t).toFixed(1)} ${py(v).toFixed(1)}` })
    return d
  }
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
            options={[{ value: 'raw', label: 'raw' }, { value: 'detrended', label: 'detrended (display only)', disabled: true, reason: 'no display transform in the demo data' }]} />
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
          <span className="grow" />
          <InfoTip title="Lag and r" placement="bottom-end">Every selected channel over the reference's window. Lag is where the cross-correlation peaks within max lag; r is its height.</InfoTip>
        </div>

        <div className="card ex-stack" data-testid="channel-stack">
          <div className="ex-stack-head">
            <span className="card-title">Same window, every selected channel</span>
            <span className="range mono">{data.window.startH.toFixed(3)} – {data.window.endH.toFixed(3)} h · {data.window.durS} s</span>
            <span className="muted mono small">shared y · {y0 < 0 ? '−' : ''}{Math.abs(y0).toFixed(2)} – {y1 < 0 ? '−' : '+'}{Math.abs(y1).toFixed(2)} mV</span>
            {computing && <ProgressBar indeterminate width={220} size="sm" label={`computing lag · ${rows.length} channels`} testid="computing" />}
            <span className="grow" />
            <span className="cols mono"><span>lag</span><span>r</span><span>bin</span></span>
          </div>
          <div className="ex-stack-rows" ref={listRef}>
            {rows.map((r, i) => {
              const bin = binOf(r)
              const dim = focusBin && bin !== focusBin && bin !== 'reference'
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
                        {i === 0 && <rect x={px(data.window.motifStartS)} y={0} width={px(data.window.motifEndS) - px(data.window.motifStartS)} height={ROWH} fill="var(--band-selected)" data-testid="cross-motif-region" />}
                        {i === 0 && refDetections.map(d => <rect key={d.id} x={px(d.t0)} y={0} width={Math.max(2, px(d.t1) - px(d.t0))} height={4} rx={1} fill={d.colour} data-testid="cross-detection"><title>{`detection ${d.id} (demo)`}</title></rect>)}
                        {[0, 20].map(g => <line key={g} x1={px(g)} x2={px(g)} y1={0} y2={ROWH} stroke="var(--border-strong)" strokeOpacity={0.6} />)}
                        <path d={pathFor(r)} fill="none" stroke={i === 0 ? 'var(--blue)' : 'var(--trace)'} strokeWidth={1.2} clipPath={`url(#xclip-${r.channelId})`} strokeLinejoin="round" />
                        {hoverT !== null && <line x1={px(hoverT)} x2={px(hoverT)} y1={0} y2={ROWH} stroke="var(--blue)" strokeOpacity={0.55} strokeDasharray="3 3" data-testid="crosshair" />}
                        {hoverT !== null && i === 0 && <text x={Math.min(px(hoverT) + 5, W - 60)} y={12} className="mono" style={{ fill: 'var(--text-2)', fontSize: 10, paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>t = {hoverT >= 0 ? '+' : '−'}{Math.abs(hoverT).toFixed(1)} s</text>}
                      </svg>
                    )}
                  </div>
                  <span className="dot" style={{ background: BIN_DOT[bin] }} />
                  <span className="lag mono">{computing ? '…' : fmtLag(r.lagS)}</span>
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
            <div className="ticks" style={{ width: W || undefined }}>{W > 0 && ticks.map(t => <span key={t} style={{ left: px(t) }}>{t > 0 ? `+${t}` : t < 0 ? `−${-t}` : 0} s</span>)}</div>
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

