/* Explore › Editing a span (frame explore-4; spec §4.2 revision model, §4.3 "Explore only, reached from Review",
   §5.5). A persistent amber banner names the candidate; the span is shown large with the original extent in grey
   behind your extent in blue, two draggable grips, numeric start / end with nudge steppers, `snap to` rules, and a
   card stating what saving writes. Fully demo (getSpanEdit): saving is an in-memory rev 2, then back to Review.
   Deep links: ?state=edited|invalid|saved · ?queue=q-12&candidate=12&of=50&return=<route> */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ApiError } from '../api'
import { useSourced } from '../api/seam'
import { getSpanEdit, type Revision, type SnapRule, type SpanEditDemo } from '../api/explore'
import { Button, Callout, Checklist, Chip, EmptyState, Icon, InfoTip, cx, fmtInt, recordDemoWrite, useDemoState, useQueryState, useSim } from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { ErrorCard } from './ErrorCard'
import { LockedCard } from './LockedCard'
import { useElementSize } from './useElementSize'
import { asApiError, hourTicks } from './util'

interface Extent { start: number; end: number }
const RULES: SnapRule[] = ['steepest sample', 'trough', 'zero crossing', 'free']

export function SpanEditPage({ memberId }: { memberId: string }) {
  const read = useSourced(() => getSpanEdit(memberId), [memberId])
  const head = (sub: string, demo = true) => <Header workspace="Explore" page="Editing a span" subtitle={sub} search="Search spans, runs, families" demo={demo} />
  if (read.error) return <>{head(`${memberId} · error`)}<div className="page"><div className="page-inner"><ErrorCard error={asApiError(read.error)} title="demo read getSpanEdit failed" /></div></div></>
  if (read.loading) return <>{head(`${memberId} · loading…`)}<div className="page"><div className="page-inner" data-testid="span-edit-loading"><div className="skeleton" style={{ height: 44 }} /><div className="skeleton" style={{ height: 100 }} /><div className="skeleton" style={{ height: 250 }} /></div></div></>
  const d = read.data
  if (!d) {
    return (
      <>{head(`${memberId} · not found`)}
        <div className="page"><div className="page-inner">
          <EmptyState icon="search" title={`No span ${memberId} in the demo data.`} caption="Span editing opens from a Review candidate (the demo canon has m-1846)." bordered testid="span-unknown"
            action={<Button iconRight="arrow-right" onClick={() => navigate('review')}>Back to Review</Button>} />
        </div></div>
      </>
    )
  }
  if (d.heldOut) {
    return (
      <>{head(`${memberId} · held out`, false)}
        <div className="page"><div className="page-inner">
          <LockedCard error={new ApiError(423, `${d.file} is held out and locked (D6): its spans cannot be opened or edited.`)} file={d.file} />
          <div><Button iconRight="arrow-right" onClick={() => navigate('review')}>Back to Review</Button></div>
        </div></div>
      </>
    )
  }
  return <SpanEditBody key={memberId} d={d} />
}

function SpanEditBody({ d }: { d: SpanEditDemo }) {
  const toast = useToast()
  const [forced, setForced] = useQueryState<string>('state', '')
  const [queue] = useQueryState<string>('queue', d.handoff.queueId)
  const [candidate] = useQueryState<string>('candidate', String(d.handoff.candidate))
  const [of] = useQueryState<string>('of', String(d.handoff.of))
  const [ret] = useQueryState<string>('return', '')
  const [extent, setExtent] = useDemoState<Extent>(`explore.spanEdit.${d.memberId}`, () => ({ ...d.original }))
  const [saved, setSaved] = useDemoState<boolean>(`explore.spanEdit.saved.${d.memberId}`, () => false)
  const [snap, setSnap] = useState<SnapRule>(d.snap)
  const sim = useSim(`explore.spanEdit.save.${d.memberId}`)
  const pending = useRef(false)

  useEffect(() => {
    if (forced === 'edited') { setExtent({ ...d.edited }); setSaved(false) }
    else if (forced === 'invalid') { setExtent({ start: d.edited.end, end: d.edited.end - 3 }); setSaved(false) }
    else if (forced === 'saved') { setExtent({ ...d.edited }); setSaved(true) }
    else if (forced === 'pristine') { setExtent({ ...d.original }); setSaved(false) }
  }, [forced])  // eslint-disable-line react-hooks/exhaustive-deps

  const fs = d.fs
  const changed = extent.start !== d.original.start || extent.end !== d.original.end
  const problem = extent.end <= extent.start ? 'start must be before end'
    : extent.end - extent.start < 2 ? 'a span needs at least 2 samples'
      : extent.start < 0 || extent.end > d.nSamples ? `outside the recording (0 – ${d.durationH} h)` : null
  const saveReason = saved ? 'already saved as rev 2' : problem ? 'fix the extent first' : !changed ? 'nothing changed — drag a handle or nudge start / end' : undefined
  const returnTo = ret || 'review'
  const back = (discard: boolean) => {
    if (discard && changed && !saved) toast.push({ text: 'edit discarded' })
    navigate(returnTo)
  }
  const save = () => {
    if (saveReason || sim.busy) return
    pending.current = true
    sim.start({ steps: ['saving'], stepMs: 400, queuedMs: 0 })
  }
  useEffect(() => {
    if (sim.status !== 'done' || !pending.current) return
    pending.current = false
    setSaved(true)
    recordDemoWrite('explore', 'span-revision', { member: d.memberId, rev: 2, annotation: 'a-2077', derived_from: 'd-0412', start: extent.start, end: extent.end, actor: 'this installation' })
    toast.push({ text: `${d.memberId} saved as rev 2 · annotation a-2077` })
    if (forced !== 'saved') navigate(`${returnTo}${returnTo.includes('?') ? '&' : '?'}edited=${d.memberId}`)
  }, [sim.status])  // eslint-disable-line react-hooks/exhaustive-deps

  // keyboard: Esc returns without saving (no field focused), Ctrl + Enter saves
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return
      const t = e.target as HTMLElement | null
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); save() }
      else if (e.key === 'Escape' && !(t && t.closest('input, textarea, select, [role="slider"]'))) { e.preventDefault(); back(true) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const snapTo = (s: number, rule: SnapRule) => {
    if (rule === 'free') return s
    const c = d.snapCandidates[rule]
    return c.length ? c.reduce((b, x) => (Math.abs(x - s) < Math.abs(b - s) ? x : b), c[0]) : s
  }
  const setRule = (rule: SnapRule) => {
    setSnap(rule); setForced(null)
    if (rule !== 'free') setExtent(x => ({ start: snapTo(x.start, rule), end: snapTo(x.end, rule) }))
  }
  const update = (next: Extent) => { setExtent(next); if (forced) setForced(null) }

  const dS = (extent.start - d.original.start) / fs, dE = (extent.end - d.original.end) / fs
  const dD = dE - dS
  const signed = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmtInt(Math.abs(v))} s`
  const revisions: (Revision & { label: string })[] = [
    { ...d.revisions[0], status: changed || saved ? 'kept' : 'current', label: changed || saved ? 'kept' : 'current' },
    ...(changed || saved ? [{ rev: 2, kind: 'annotation' as const, ref: 'a-2077', detail: 'this edit · human', origin: 'human' as const, status: saved ? 'current' as const : 'pending' as const, label: saved ? 'current' : 'current once saved' }] : []),
  ]

  return (
    <>
      <Header workspace="Explore" page="Editing a span" subtitle={`${d.memberId} · opened from Review`} search="Search spans, runs, families" demo />
      <div className="page"><div className="page-inner ex-span-edit" style={{ maxWidth: 1376 }} data-testid="span-edit-page">
        <div className="ex-topbar" data-testid="span-edit-topbar">
          <div className="ex-crumb">
            <a onClick={() => { if (changed && !saved) toast.push({ text: 'edit discarded' }); navigate('explore/corpus') }} data-testid="crumb-corpus">Corpus</a><span>›</span>
            <a onClick={() => { if (changed && !saved) toast.push({ text: 'edit discarded' }); navigate(`explore/corpus?rec=${encodeURIComponent(d.file)}&ch=${d.channelId}`) }}>{d.recordingLabel}</a><span>›</span>
            <a onClick={() => { if (changed && !saved) toast.push({ text: 'edit discarded' }); navigate(`explore/signal/${d.channelId}`) }} data-testid="crumb-channel">{d.channelName}</a><span>›</span>
            <span className="cur">edit span</span>
          </div>
          <span className="grow" />
          <span className="muted mono small">span editing always happens here, so human geometry stays in the human store</span>
        </div>

        <div className="ex-banner" data-testid="edit-banner">
          <span className="dot" />
          <b>Editing {d.memberId} for Review</b>
          <span className="mono ctx">candidate {candidate} of {of} · {d.handoff.runLabel}{queue !== d.handoff.queueId ? ` · ${queue}` : ''}</span>
          <span className="grow" />
          <Button onClick={() => back(true)} testid="return-without-saving">Return without saving</Button>
          <Button variant="primary" iconRight="arrow-right" onClick={save} loading={sim.busy} disabled={!!saveReason} disabledReason={saveReason} testid="save-and-return">{sim.busy ? 'Saving…' : 'Save and return to Review'}</Button>
        </div>
        {saved && <Callout tone="green" icon="check-circle" testid="saved-callout">{d.memberId} saved as rev 2 · annotation a-2077 · the family card still shows one member</Callout>}

        <Overview d={d} extent={extent} />
        <SpanPlot d={d} extent={extent} onChange={update} snapTo={s => snapTo(s, snap)} invalid={!!problem} />

        <div className="card card-pad ex-extent" data-testid="extent-card">
          <b className="title">Extent</b>
          <div className="grid">
            <div className="left">
              <div className="fields">
                <SampleField label="start" value={extent.start} fs={fs} invalid={!!problem} onCommit={v => update({ ...extent, start: v })} testid="start-field" />
                <SampleField label="end" value={extent.end} fs={fs} invalid={!!problem} onCommit={v => update({ ...extent, end: v })} testid="end-field" />
                <div className="fld"><span className="lbl">duration</span><span className="ro mono" data-testid="duration">{problem ? '—' : `${fmtInt((extent.end - extent.start) / fs)} s · ${fmtInt(extent.end - extent.start)} samples`}</span></div>
              </div>
              {problem && <span className="k-field-error" role="alert" data-testid="extent-error"><Icon name="alert-circle" size={11} />{problem}</span>}
              <div className="rule muted mono small">original onset rule: {d.onsetRule}
                <InfoTip title="Onset rule">The detector found this onset by walking back from the steepest sample while the signal kept descending. Snapping to the same rule keeps your edit comparable with the rest of {d.familyId}.</InfoTip></div>
            </div>
            <div className="right">
              <div className="snap"><span className="lbl">snap to</span>
                <div className="chips" role="radiogroup" aria-label="snap to">
                  {RULES.map(r => <Chip key={r} size="sm" tone={snap === r ? 'blue' : 'outline'} selected={snap === r} onClick={() => setRule(r)} testid={`snap-${r.replace(' ', '-')}`}>{r}</Chip>)}
                </div>
              </div>
              <div className="deltas mono small" data-testid="deltas"><span className="muted">vs original</span>
                <span className={cx(dS ? 'amber' : 'muted')}>start {signed(dS)}</span><span className="muted">·</span>
                <span className={cx(dE ? 'amber' : 'muted')}>end {signed(dE)}</span><span className="muted">·</span>
                <span className={cx(dD ? 'amber' : 'muted')}>duration {signed(dD)}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="card card-pad ex-writes" data-testid="saving-writes">
          <div className="ex-card-head"><b>What saving writes</b><span className="muted mono small">a new revision of this motif, not a replacement</span>
            <InfoTip title="Revisions">Revisions are spans, not edits to a span (§4.2). The member keeps both; the family shows one card.</InfoTip></div>
          <div className="grid">
            <div className="revs" data-testid="revisions">
              {revisions.map(r => (
                <div key={r.rev} className="rev" data-status={r.status} data-testid={`rev-${r.rev}`}>
                  <span className="muted">rev {r.rev}</span><span>{r.kind} {r.ref}</span><span className="muted">{r.detail}</span>
                  <span className="st"><span className="dot" style={{ background: r.status === 'pending' ? '#c7cbd1' : 'var(--green)' }} /><span className={r.status === 'current' ? 'cur' : r.status === 'pending' ? 'muted' : 'muted'}>{r.label}</span></span>
                </div>
              ))}
            </div>
            <Checklist items={[
              { label: 'run 128 still reproduces from its recipe — the detection is untouched', state: 'pass' },
              { label: 'later runs that find the original extent resolve to this same motif', state: 'pass' },
              { label: 'your geometry goes to the annotation store, never the detection table', state: 'pass' },
              { label: `${d.familyId} is marked partially stale until its distances are recomputed (m-1846 is its medoid)`, state: changed || saved ? 'warn' : 'pending' },
            ]} testid="saving-checks" />
          </div>
        </div>
      </div></div>
    </>
  )
}

function Overview({ d, extent }: { d: SpanEditDemo; extent: Extent }) {
  const [ref, size] = useElementSize<HTMLDivElement>()
  const W = size.width, H = 60
  const n = d.overview.length
  let lo = Infinity, hi = -Infinity
  for (const v of d.overview) { if (v < lo) lo = v; if (v > hi) hi = v }
  const path = d.overview.map((v, i) => `${i ? 'L' : 'M'}${((i / (n - 1)) * W).toFixed(1)} ${(H - 4 - ((v - lo) / (hi - lo || 1)) * (H - 8)).toFixed(1)}`).join('')
  const hx = (s: number) => (s / d.fs / 3600 / d.durationH) * W
  const x0 = hx(Math.min(extent.start, extent.end)), x1 = hx(Math.max(extent.start, extent.end))
  const cx0 = (x0 + x1) / 2
  return (
    <div className="card ex-tier" data-testid="span-edit-overview">
      <div className="head"><span className="card-title">Channel</span><span className="range">{d.channelName} · 0 – {d.durationH} h</span><span className="grow" /><span className="muted mono small">the span being edited is highlighted</span></div>
      <div className="ex-plot" ref={ref} style={{ height: H + 16, background: '#f7f8fa' }}>
        {W > 0 && (
          <svg width={W} height={H + 16}>
            <path d={path} fill="none" stroke="var(--trace)" strokeWidth={1} />
            <rect x={cx0 - 5} y={2} width={10} height={H - 4} fill="rgba(232,144,12,0.25)" stroke="var(--amber)" strokeWidth={1.2} rx={1} data-testid="overview-highlight"><title>{`${(extent.start / d.fs / 3600).toFixed(4)} h`}</title></rect>
            <g className="time-axis">{hourTicks(d.durationH).map((k, i, arr) => <text key={k.h} x={(k.h / d.durationH) * W} y={H + 12} textAnchor={i === 0 ? 'start' : i === arr.length - 1 ? 'end' : 'middle'}>{k.label}</text>)}</g>
          </svg>
        )}
      </div>
    </div>
  )
}

function SpanPlot({ d, extent, onChange, snapTo, invalid }: { d: SpanEditDemo; extent: Extent; onChange: (e: Extent) => void; snapTo: (s: number) => number; invalid: boolean }) {
  const [ref, size] = useElementSize<HTMLDivElement>()
  const W = size.width, H = 185, AX = 20, padL = 58, padR = 12
  const mv = d.trace.mv, n = mv.length, s0 = d.trace.t0Sample
  const plotW = Math.max(1, W - padL - padR)
  const x = (s: number) => padL + ((s - s0) / (n - 1)) * plotW
  const inv = (px: number) => Math.round(s0 + ((px - padL) / plotW) * (n - 1))
  let lo = Infinity, hi = -Infinity
  for (const v of mv) { if (v < lo) lo = v; if (v > hi) hi = v }
  const m = (hi - lo) * 0.08; lo -= m; hi += m
  const y = (v: number) => 8 + (1 - (v - lo) / (hi - lo)) * (H - 16)
  const path = mv.map((v, i) => `${i ? 'L' : 'M'}${x(s0 + i).toFixed(1)} ${y(v).toFixed(1)}`).join('')
  const drag = useRef<'start' | 'end' | null>(null)
  const [dragging, setDragging] = useState<'start' | 'end' | null>(null)
  const clampS = (v: number) => Math.max(s0, Math.min(s0 + n - 1, v))
  const move = (which: 'start' | 'end', sample: number) => {
    const v = clampS(sample)
    onChange(which === 'start' ? { start: Math.min(v, extent.end - 2), end: extent.end } : { start: extent.start, end: Math.max(v, extent.start + 2) })
  }
  const grip = (which: 'start' | 'end') => {
    const gx = x(which === 'start' ? extent.start : extent.end)
    return (
      <g key={which} role="slider" tabIndex={0} className="ex-focusable" aria-label={`${which} of your extent (← → nudge one sample, Shift ×10)`} aria-valuenow={which === 'start' ? extent.start : extent.end}
        style={{ cursor: 'ew-resize' }} data-testid={`grip-${which}`}
        onPointerDown={e => { e.preventDefault(); drag.current = which; setDragging(which); (e.currentTarget as Element).setPointerCapture(e.pointerId) }}
        onPointerMove={e => { if (drag.current !== which) return; const r = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect(); move(which, inv(e.clientX - r.left)) }}
        onPointerUp={() => { if (drag.current) { const cur = which === 'start' ? extent.start : extent.end; const sn = snapTo(cur); if (sn !== cur) move(which, sn) } drag.current = null; setDragging(null) }}
        onKeyDown={e => { if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return; e.preventDefault(); e.stopPropagation(); move(which, (which === 'start' ? extent.start : extent.end) + (e.key === 'ArrowLeft' ? -1 : 1) * (e.shiftKey ? 10 : 1)) }}>
        <rect x={gx - 8} y={H / 2 - 20} width={16} height={40} fill="transparent" />
        <rect x={gx - 4} y={H / 2 - 15} width={8} height={30} rx={3} fill={invalid ? 'var(--red)' : 'var(--blue)'} />
        <line x1={gx} x2={gx} y1={H / 2 - 8} y2={H / 2 + 8} stroke="#fff" strokeWidth={1.3} />
      </g>
    )
  }
  const spanS = n / d.fs
  const tickStep = 25
  const ticks: number[] = []
  for (let t = Math.ceil((s0 - d.original.start) / tickStep) * tickStep; t <= (s0 + n - 1 - d.original.start); t += tickStep) ticks.push(t)
  const a = Math.min(extent.start, extent.end), b = Math.max(extent.start, extent.end)
  return (
    <div className="card ex-tier" data-testid="span-edit-plot">
      <div className="head"><span className="card-title">The span</span><span className="range muted">drag either handle · arrow keys nudge one sample (1 s at 1 Hz)</span><span className="grow" /><span className="muted mono small" data-testid="px-scale">1 px = {plotW > 1 ? (spanS / plotW).toFixed(2) : '—'} s</span></div>
      <div className={cx('ex-plot', dragging && 'dragging')} ref={ref} style={{ height: H + AX }}>
        {W > 0 && (
          <svg width={W} height={H + AX}>
            <rect x={padL} y={0} width={plotW} height={H} fill="#fff" />
            <rect x={x(d.original.start)} y={2} width={Math.max(1, x(d.original.end) - x(d.original.start))} height={H - 4} fill="none" stroke="#6b7280" strokeWidth={1} data-testid="original-extent" />
            <rect x={x(a)} y={2} width={Math.max(1, x(b) - x(a))} height={H - 4} fill={invalid ? 'rgba(229,72,77,0.12)' : 'rgba(10,132,255,0.14)'} stroke={invalid ? 'var(--red)' : 'var(--blue)'} strokeWidth={1.2} data-testid="your-extent" />
            <path d={path} fill="none" stroke="var(--trace)" strokeWidth={1.1} strokeLinejoin="round" />
            {[hi - m, (hi + lo) / 2, lo + m].map(v => <text key={v} x={padL - 6} y={y(v) + 3} textAnchor="end" className="mono" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v > 0.0005 ? '+' : v < -0.0005 ? '−' : ''}{Math.abs(v).toFixed(2)} mV</text>)}
            {grip('start')}{grip('end')}
            <g className="time-axis">{ticks.map(t => <text key={t} x={x(d.original.start + t)} y={H + 14} textAnchor="middle">{t > 0 ? `+${t}` : t < 0 ? `−${-t}` : 0} s</text>)}</g>
          </svg>
        )}
      </div>
      <div className="ex-extent-legend mono small"><span><i className="orig" />original extent, from the detection</span><span className="blue"><i className="yours" />your extent</span></div>
    </div>
  )
}

function SampleField({ label, value, fs, invalid, onCommit, testid }: { label: string; value: number; fs: number; invalid: boolean; onCommit: (v: number) => void; testid: string }) {
  const [raw, setRaw] = useState<string | null>(null)
  const parse = (s: string): number | string => {
    const t = s.trim().replace(/−/g, '-')
    const h = t.match(/^(-?\d+(?:\.\d+)?)\s*h$/i)
    if (h) return Math.round(Number(h[1]) * 3600 * fs)
    const n = t.replace(/^#/, '').replace(/,/g, '')
    if (/^-?\d+$/.test(n)) return Number(n)
    return 'type a sample (#534967) or hours (148.6019 h)'
  }
  const p = raw === null ? null : parse(raw)
  const display = `${(value / fs / 3600).toFixed(4)} h · #${fmtInt(value)}`
  const commit = () => { if (typeof p === 'number') onCommit(p); setRaw(null) }
  const field: ReactNode = (
    <span className={cx('k-input', (invalid || typeof p === 'string') && 'invalid', 'ex-sample')}>
      <input value={raw ?? display} onFocus={() => setRaw(`#${value}`)} onChange={e => setRaw(e.target.value)} onBlur={commit} aria-label={label} data-testid={testid}
        onKeyDown={e => {
          if (e.key === 'Enter') commit()
          else if (e.key === 'Escape') { e.stopPropagation(); setRaw(null); (e.target as HTMLInputElement).blur() }
          else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') { e.preventDefault(); const nv = value + (e.key === 'ArrowUp' ? 1 : -1) * (e.shiftKey ? 10 : 1); onCommit(nv); setRaw(`#${nv}`) }
        }} />
      <span className="steps">
        <button type="button" aria-label={`${label} +1 sample`} onMouseDown={e => e.preventDefault()} onClick={() => onCommit(value + 1)} data-testid={`${testid}-up`}><Icon name="chevron-up" size={10} /></button>
        <button type="button" aria-label={`${label} −1 sample`} onMouseDown={e => e.preventDefault()} onClick={() => onCommit(value - 1)} data-testid={`${testid}-down`}><Icon name="chevron-down" size={10} /></button>
      </span>
    </span>
  )
  return (
    <div className="fld"><span className="lbl">{label}</span>{field}
      {typeof p === 'string' && <span className="k-field-error" role="alert">{p}</span>}
    </div>
  )
}

