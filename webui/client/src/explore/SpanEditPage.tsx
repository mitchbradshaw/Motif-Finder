/* Explore › Editing a span (frame explore-4; spec §4.2 revision model, §4.3 "Explore only, reached from Review").
   edit-span (2026-10-18): live. The page reads GET /api/explore/span-edit/<ref> — `ref` is a detection id (a Review
   detection item) or `m-<id>` (a Library member) — draws the channel around the span (±2 span lengths, the
   bridge's envelope), the original extent in grey behind your extent in blue with two draggable handles, and
   numeric start / end in seconds (three decimals, ±1-sample steppers) kept in sync with the handles both ways.
   Saving POSTs the corrected span: a Library member gets a new revision (history kept), a plain detection gets a
   human annotation carrying the item's verdict. The detection row is never written (CLAUDE.md rule 5).
   Back / Cancel / Save return to `review/queue/<queue>/<item>` from the `from=review&queue=…&item=…` the Review
   button builds; any other `from` (the Family page's) is returned to as given. */
import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../api'
import { useSourced } from '../api/seam'
import { getSpanEdit, saveSpanEdit, type SpanEdit } from '../api/explore'
import { Button, Callout, EmptyState, Icon, InfoTip, TextField, cx, fmtInt, useQueryState } from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { ErrorCard } from './ErrorCard'
import { LockedCard } from './LockedCard'
import { useElementSize } from './useElementSize'
import { asApiError } from './util'

interface Extent { start: number; end: number }

/** Where Back, Cancel and Save land: the same Review queue and item, or the page that opened the editor. */
function useReturnRoute(): string {
  const [from] = useQueryState<string>('from', '')
  const [queue] = useQueryState<string>('queue', '')
  const [item] = useQueryState<string>('item', '')
  if (from === 'review' || (!from && queue)) return queue ? (item ? `review/queue/${queue}/${item}` : `review/queue/${queue}`) : 'review'
  return from || 'review'
}

export function SpanEditPage({ memberId: ref }: { memberId: string }) {
  const read = useSourced(() => getSpanEdit(ref), [ref])
  const returnTo = useReturnRoute()
  const head = (sub: string) => <Header workspace="Explore" page="Editing a span" subtitle={sub} search="Search spans, runs, families" />
  const back = <Button iconRight="arrow-right" onClick={() => navigate(returnTo)} testid="span-edit-back">{returnTo.startsWith('review') ? 'Back to Review' : 'Back'}</Button>
  if (read.error) {
    const err = asApiError(read.error)
    return (
      <>{head(`${ref} · ${err.status === 423 ? 'held out' : err.status === 404 ? 'not found' : 'error'}`)}
        <div className="page"><div className="page-inner">
          {err.status === 423 ? <LockedCard error={err} />
            : err.status === 404
              ? <EmptyState icon="search" title={`Nothing to edit: ${err.message}.`} bordered testid="span-unknown"
                  caption="Span editing opens from a Review item (a detection, or a Library member) or a Family page's Redraw in Explore." />
              : <ErrorCard error={err} title="GET /api/explore/span-edit failed" />}
          <div>{back}</div>
        </div></div>
      </>
    )
  }
  if (read.loading || !read.data) {
    return <>{head(`${ref} · loading…`)}<div className="page"><div className="page-inner" data-testid="span-edit-loading"><div className="skeleton" style={{ height: 44 }} /><div className="skeleton" style={{ height: 250 }} /><div className="skeleton" style={{ height: 100 }} /></div></div></>
  }
  return <SpanEditBody key={ref} refId={ref} d={read.data} returnTo={returnTo} />
}

function SpanEditBody({ refId, d, returnTo }: { refId: string; d: SpanEdit; returnTo: string }) {
  const toast = useToast()
  const fs = d.fs
  // the span the item shows now: a member's CURRENT revision, else the detection's own span
  const original: Extent = d.member ? { start: d.member.current.start_idx, end: d.member.current.end_idx }
    : { start: d.detection!.start_idx, end: d.detection!.end_idx }
  const [extent, setExtent] = useState<Extent>(original)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState<ApiError | null>(null)

  const changed = extent.start !== original.start || extent.end !== original.end
  const problem = extent.end - extent.start < 2 ? 'a span needs at least two samples, and its start before its end'
    : extent.start < 0 || extent.end > d.n_samples ? `outside the channel (0 – ${fmtSec(d.n_samples / fs)} s)` : null
  const saveReason = busy ? 'saving…' : problem ? 'fix the extent first' : !changed ? 'nothing changed — drag a handle or edit start / end' : undefined
  const label = d.member ? `member ${d.member.ref}` : `detection ${d.detection_id}`
  const verdictWord = d.verdict ?? 'interesting'
  const writes = d.member
    ? `a new revision (rev ${d.member.current.revision_no + 1}) of ${d.member.ref}, backed by a human annotation (${d.verdict ? `verdict ${d.verdict}` : 'interesting, as the member has no verdict yet'}); the earlier revisions stay in its history and the detection is untouched`
    : `a human annotation over the corrected span with the item's verdict (${verdictWord}${d.verdict ? '' : ', as the item has none'}); the detection is untouched`

  const back = (discard: boolean) => {
    if (discard && changed) toast.push({ text: 'edit discarded' })
    navigate(returnTo)
  }
  const save = () => {
    if (saveReason) return
    setBusy(true); setFailed(null)
    saveSpanEdit(refId, { start_idx: extent.start, end_idx: extent.end, note: note.trim() || null })
      .then(r => {
        const what = r.kind === 'revision' ? `${r.member} saved as rev ${r.revision?.revision_no} · annotation ${r.annotation.id}`
          : `annotation ${r.annotation.id} written (${r.annotation.verdict}) · detection ${d.detection_id} untouched`
        const stale = r.stale_edges?.length ? ` · ${r.stale_edges.length} family distance${r.stale_edges.length === 1 ? '' : 's'} now stale` : ''
        toast.push({ text: what + stale })
        // the corrected item is now covered by a human span, so its queue no longer serves it: say so on the way
        // back, and the Inspector reads the item on its own instead of calling it absent (integration fix)
        navigate(/^review\/queue\/[^/?]+\/[^/?]+$/.test(returnTo) ? `${returnTo}?corrected=1` : returnTo)
      })
      .catch(e => { setFailed(asApiError(e)); setBusy(false) })
  }

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

  const dS = (extent.start - original.start) / fs, dE = (extent.end - original.end) / fs
  const signed = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmtSec(Math.abs(v))} s`
  return (
    <>
      <Header workspace="Explore" page="Editing a span" subtitle={`${label} · ${d.channel}`} search="Search spans, runs, families" />
      <div className="page"><div className="page-inner ex-span-edit" style={{ maxWidth: 1376 }} data-testid="span-edit-page" data-kind={d.member ? 'member' : 'detection'}>
        <div className="ex-topbar" data-testid="span-edit-topbar">
          <div className="ex-crumb">
            <a onClick={() => back(true)} data-testid="crumb-back">{returnTo.startsWith('review') ? 'Review' : 'Back'}</a><span>›</span>
            <a onClick={() => { if (changed) toast.push({ text: 'edit discarded' }); navigate(`explore/signal/${d.recording_id}`) }} data-testid="crumb-channel">{d.channel}</a><span>›</span>
            <span className="cur">edit span</span>
          </div>
          <span className="grow" />
          <span className="muted mono small">your corrected span is stored as a human record; the machine's detection is never changed</span>
        </div>

        <div className="ex-banner" data-testid="edit-banner">
          <span className="dot" />
          <b>Editing {label}</b>
          <span className="mono ctx">{d.verdict ? `verdict ${d.verdict}` : 'no verdict yet'}{d.member ? ` · current rev ${d.member.current.revision_no}` : ''}</span>
          <span className="grow" />
          <Button onClick={() => back(true)} testid="return-without-saving">Cancel</Button>
          <Button variant="primary" iconRight="arrow-right" onClick={save} loading={busy} disabled={!!saveReason} disabledReason={saveReason} testid="save-and-return">{busy ? 'Saving…' : 'Save and return'}</Button>
        </div>
        {failed && <Callout tone="red" icon="alert-circle" testid="save-failed">Not saved: {failed.message}</Callout>}

        <SpanPlot d={d} original={original} extent={extent} onChange={setExtent} invalid={!!problem} />

        <div className="card card-pad ex-extent" data-testid="extent-card">
          <b className="title">Extent <InfoTip title="Extent">Start and end are seconds from the start of the recording, to three decimals (one sample is {fmtSec(1 / fs)} s here). Type a value and press Enter, use the arrows (one sample; Shift for ten), or drag a handle on the plot — the two stay in step.</InfoTip></b>
          <div className="grid">
            <div className="left">
              <div className="fields">
                <SecondsField label="start (s)" value={extent.start} fs={fs} invalid={!!problem} onCommit={v => setExtent(x => ({ ...x, start: v }))} testid="start-field" />
                <SecondsField label="end (s)" value={extent.end} fs={fs} invalid={!!problem} onCommit={v => setExtent(x => ({ ...x, end: v }))} testid="end-field" />
                <div className="fld"><span className="lbl">duration</span><span className="ro mono" data-testid="duration">{problem ? '—' : `${fmtSec((extent.end - extent.start) / fs)} s · ${fmtInt(extent.end - extent.start)} samples`}</span></div>
              </div>
              {problem && <span className="k-field-error" role="alert" data-testid="extent-error"><Icon name="alert-circle" size={11} />{problem}</span>}
              <div className="deltas mono small" data-testid="deltas" style={{ marginTop: 8 }}><span className="muted">vs {d.member ? `rev ${d.member.current.revision_no}` : 'the detection'} </span>
                <span className={cx(dS ? 'amber' : 'muted')}>start {signed(dS)}</span><span className="muted"> · </span>
                <span className={cx(dE ? 'amber' : 'muted')}>end {signed(dE)}</span>
              </div>
            </div>
            <div className="right stack" style={{ gap: 6 }}>
              <span className="lbl">note (optional)</span>
              <TextField multiline rows={2} value={note} onChange={setNote} placeholder="why the span moved" testid="span-edit-note" block />
            </div>
          </div>
        </div>

        <div className="card card-pad" data-testid="saving-writes">
          <b>What saving writes</b>
          <p className="muted small" style={{ margin: '6px 0 0' }} data-testid="saving-writes-text">{writes}.</p>
        </div>
      </div></div>
    </>
  )
}

const fmtSec = (s: number) => s.toFixed(3)

function SpanPlot({ d, original, extent, onChange, invalid }: { d: SpanEdit; original: Extent; extent: Extent; onChange: (e: Extent) => void; invalid: boolean }) {
  const [ref, size] = useElementSize<HTMLDivElement>()
  const tr = d.context_trace
  const fs = d.fs
  const W = size.width, H = 220, AX = 20, padL = 62, padR = 14
  const plotW = Math.max(1, W - padL - padR)
  const t0 = tr.t0_s, t1 = Math.max(tr.t1_s, tr.t0_s + 1 / fs)
  const x = (sec: number) => padL + ((sec - t0) / (t1 - t0)) * plotW
  const inv = (px: number) => Math.round((t0 + ((px - padL) / plotW) * (t1 - t0)) * fs)
  let lo = Infinity, hi = -Infinity
  for (const v of tr.v) if (v != null) { if (v < lo) lo = v; if (v > hi) hi = v }
  const drawable = Number.isFinite(lo) && Number.isFinite(hi)
  if (!drawable) { lo = -1; hi = 1 }
  const m = (hi - lo || 1) * 0.08; lo -= m; hi += m
  const y = (v: number) => 8 + (1 - (v - lo) / (hi - lo)) * (H - 16)
  let path = '', pen = false
  tr.v.forEach((v, i) => { if (v == null) { pen = false; return } path += `${pen ? 'L' : 'M'}${x(tr.t[i]).toFixed(1)} ${y(v).toFixed(1)}`; pen = true })
  const drag = useRef<'start' | 'end' | null>(null)
  const [dragging, setDragging] = useState<'start' | 'end' | null>(null)
  const lo0 = Math.round(t0 * fs), hi0 = Math.round(t1 * fs)
  const move = (which: 'start' | 'end', sample: number) => {
    const v = Math.max(lo0, Math.min(hi0, sample))
    onChange(which === 'start' ? { start: Math.min(v, extent.end - 2), end: extent.end } : { start: extent.start, end: Math.max(v, extent.start + 2) })
  }
  const clampX = (sec: number) => Math.max(padL, Math.min(padL + plotW, x(sec)))
  const grip = (which: 'start' | 'end') => {
    const gx = clampX((which === 'start' ? extent.start : extent.end) / fs)
    return (
      <g key={which} role="slider" tabIndex={0} className="ex-focusable" aria-label={`${which} of your extent (← → nudge one sample, Shift ×10)`} aria-valuenow={which === 'start' ? extent.start : extent.end}
        style={{ cursor: 'ew-resize' }} data-testid={`grip-${which}`}
        onPointerDown={e => { e.preventDefault(); drag.current = which; setDragging(which); (e.currentTarget as Element).setPointerCapture(e.pointerId) }}
        onPointerMove={e => { if (drag.current !== which) return; const r = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect(); move(which, inv(e.clientX - r.left)) }}
        onPointerUp={() => { drag.current = null; setDragging(null) }}
        onKeyDown={e => { if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return; e.preventDefault(); e.stopPropagation(); move(which, (which === 'start' ? extent.start : extent.end) + (e.key === 'ArrowLeft' ? -1 : 1) * (e.shiftKey ? 10 : 1)) }}>
        <rect x={gx - 8} y={H / 2 - 20} width={16} height={40} fill="transparent" />
        <rect x={gx - 4} y={H / 2 - 15} width={8} height={30} rx={3} fill={invalid ? 'var(--red)' : 'var(--blue)'} />
        <line x1={gx} x2={gx} y1={H / 2 - 8} y2={H / 2 + 8} stroke="#fff" strokeWidth={1.3} />
      </g>
    )
  }
  // ticks: seconds relative to the original start, at a round step that gives about six
  const spanS = t1 - t0
  const step = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1800, 3600].find(s => spanS / s <= 7) ?? 3600
  const o = original.start / fs
  const ticks: number[] = []
  for (let k = Math.ceil((t0 - o) / step); o + k * step <= t1; k++) ticks.push(k * step)
  const a = Math.min(extent.start, extent.end) / fs, b = Math.max(extent.start, extent.end) / fs
  const outside = extent.start / fs < t0 || extent.end / fs > t1
  return (
    <div className="card ex-tier" data-testid="span-edit-plot" data-drawn={drawable ? '1' : '0'}>
      <div className="head"><span className="card-title">The span on {d.channel}</span>
        <span className="range muted">±2 span lengths of context · drag either handle · arrow keys nudge one sample</span><span className="grow" />
        <span className="muted mono small" data-testid="context-window">{fmtSec(t0)} – {fmtSec(t1)} s · {fmtInt(tr.n_source)} samples{tr.decimated ? ` as ${fmtInt(tr.n_points)} points` : ''}</span></div>
      {!drawable && <Callout tone="amber" icon="alert-circle" testid="trace-reason">The channel is not drawn: {tr.reason ?? 'no samples in this window'}. The fields still edit the span.</Callout>}
      {outside && <Callout tone="amber" icon="alert-circle" testid="extent-outside-window">Your extent runs past the drawn window; the band is clipped at its edge.</Callout>}
      <div className={cx('ex-plot', dragging && 'dragging')} ref={ref} style={{ height: H + AX }}>
        {W > 0 && (
          <svg width={W} height={H + AX}>
            <rect x={padL} y={0} width={plotW} height={H} fill="#fff" />
            <rect x={clampX(original.start / fs)} y={2} width={Math.max(1, clampX(original.end / fs) - clampX(original.start / fs))} height={H - 4} fill="none" stroke="#6b7280" strokeDasharray="4 3" strokeWidth={1} data-testid="original-extent" />
            <rect x={clampX(a)} y={2} width={Math.max(1, clampX(b) - clampX(a))} height={H - 4} fill={invalid ? 'rgba(229,72,77,0.12)' : 'rgba(10,132,255,0.14)'} stroke={invalid ? 'var(--red)' : 'var(--blue)'} strokeWidth={1.2} data-testid="your-extent" />
            {drawable && <path d={path} fill="none" stroke="var(--trace)" strokeWidth={1.1} strokeLinejoin="round" data-testid="span-edit-trace" />}
            {drawable && [hi - m, (hi + lo) / 2, lo + m].map(v => <text key={v} x={padL - 6} y={y(v) + 3} textAnchor="end" className="mono" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v > 0.0005 ? '+' : v < -0.0005 ? '−' : ''}{Math.abs(v).toFixed(3)} {tr.unit ?? ''}</text>)}
            {grip('start')}{grip('end')}
            <g className="time-axis">{ticks.map(t => <text key={t} x={x(o + t)} y={H + 14} textAnchor="middle">{t > 0 ? `+${+t.toFixed(3)}` : t < 0 ? `−${+(-t).toFixed(3)}` : 0} s</text>)}</g>
          </svg>
        )}
      </div>
      <div className="ex-extent-legend mono small"><span><i className="orig" />{d.member ? `rev ${d.member.current.revision_no} (current)` : 'the detection'}</span><span className="blue"><i className="yours" />your extent</span></div>
    </div>
  )
}

/** Seconds to three decimals, with ±1-sample steppers; commits on Enter / blur, so the plot follows what is typed. */
function SecondsField({ label, value, fs, invalid, onCommit, testid }: { label: string; value: number; fs: number; invalid: boolean; onCommit: (v: number) => void; testid: string }) {
  const [raw, setRaw] = useState<string | null>(null)
  // what the field showed when it took focus: blurring it unchanged must not round the span to three decimals
  const shown = useRef<string | null>(null)
  const parse = (s: string): number | string => {
    const t = s.trim().replace(/−/g, '-').replace(/\s*s$/i, '')
    if (/^#-?\d+$/.test(t)) return Number(t.slice(1))
    if (/^-?\d+(\.\d+)?$/.test(t)) return Math.round(Number(t) * fs)
    return 'type seconds (e.g. 1234.567) or a sample (#1234567)'
  }
  const p = raw === null ? null : parse(raw)
  const commit = () => { if (typeof p === 'number' && raw !== shown.current) onCommit(p); setRaw(null); shown.current = null }
  return (
    <div className="fld"><span className="lbl">{label}</span>
      <span className={cx('k-input', (invalid || typeof p === 'string') && 'invalid', 'ex-sample')}>
        <input value={raw ?? fmtSec(value / fs)} onFocus={() => { shown.current = fmtSec(value / fs); setRaw(shown.current) }} onChange={e => { setRaw(e.target.value); const q = parse(e.target.value); if (typeof q === 'number') onCommit(q) }} onBlur={commit} aria-label={label} data-testid={testid}
          onKeyDown={e => {
            if (e.key === 'Enter') commit()
            else if (e.key === 'Escape') { e.stopPropagation(); setRaw(null); (e.target as HTMLInputElement).blur() }
            else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') { e.preventDefault(); const nv = value + (e.key === 'ArrowUp' ? 1 : -1) * (e.shiftKey ? 10 : 1); onCommit(nv); shown.current = fmtSec(nv / fs); setRaw(shown.current) }
          }} />
        <span className="steps">
          <button type="button" aria-label={`${label} +1 sample`} onMouseDown={e => e.preventDefault()} onClick={() => onCommit(value + 1)} data-testid={`${testid}-up`}><Icon name="chevron-up" size={10} /></button>
          <button type="button" aria-label={`${label} −1 sample`} onMouseDown={e => e.preventDefault()} onClick={() => onCommit(value - 1)} data-testid={`${testid}-down`}><Icon name="chevron-down" size={10} /></button>
        </span>
      </span>
      <span className="muted mono small" data-testid={`${testid}-sample`}>#{fmtInt(value)}</span>
      {typeof p === 'string' && <span className="k-field-error" role="alert">{p}</span>}
    </div>
  )
}
