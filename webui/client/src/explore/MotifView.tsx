/* Tier 3 — MOTIF_233 (frame explore-2): the selected motif with ± context, ONSET / END lines, the motif
   region tinted orange, an axis relative to onset, and its own Send motif to Analyse / Review this motif.
   The label is the motif's ordinal in the ‹ N / M › list (the DB id stays in the tooltip). The signal is
   live; nearest family, tag and adjudication are demo canon when the motif is a demo detection, honest
   dashes otherwise. `overlay F-03 medoid` draws the family medoid (teal, mV, aligned at onset).
   `compact` is the strip that peeks out under the open drawer (frames 2b–2d). */
import { useEffect, useState } from 'react'
import { getWindow, type ApiError, type Channel, type WindowData } from '../api'
import { EnvelopePath } from '../charts/primitives'
import { makeX, makeY } from '../charts/scale'
import { useElementSize } from './useElementSize'
import { Button, Checkbox, Dropdown, InfoTip } from '../kit'
import { navigate } from '../state'
import { DemoTag } from './bits'
import { ErrorCard } from './ErrorCard'
import { MvLabels } from './MvLabels'
import { asApiError, envelopeOk, fmtSecs, MALFORMED_WINDOW, relativeTicks, vRange, type Motif } from './util'

const H = 110, AXIS_H = 20
const CONTEXTS = [10, 20, 60]
const TEAL = '#30B0C7'

export function MotifView({ ch, motif, label, onSend, onReview, medoid, compact = false }: {
  ch: Channel; motif: Motif | null; label: string | null; onSend: (m: Motif) => void; onReview: (m: Motif) => void
  medoid: number[] | null; compact?: boolean
}) {
  const [ctx, setCtx] = useState(20)
  const [overlay, setOverlay] = useState(false)   // off by default: the medoid is demo canon and would rescale a live trace (fog)
  const [ref, size] = useElementSize<HTMLDivElement>()
  const W = Math.max(0, size.width)
  const widthKey = Math.round(W / 50)
  const [win, setWin] = useState<{ data: WindowData & { round_trip_ms: number }; key: string } | null>(null)
  const [err, setErr] = useState<ApiError | null>(null)
  const key = motif ? `${motif.key}:${ctx}:${widthKey}` : ''
  const t0 = motif ? Math.max(0, motif.start_s - ctx) : 0
  const t1 = motif ? Math.min(ch.duration_s, motif.end_s + ctx) : 0
  useEffect(() => {
    if (!motif || widthKey <= 0) return
    let alive = true
    setErr(null)
    getWindow(ch.id, t0, t1, widthKey * 50)
      .then(w => { if (!alive) return; if (!envelopeOk(w?.envelope)) { setErr(MALFORMED_WINDOW); return } setWin({ data: w, key }) })   // shape guard (critique r1)
      .catch(e => { if (alive) setErr(asApiError(e)) })
    return () => { alive = false }
  }, [key, ch.id, t0, t1, widthKey, motif])

  const cur = win && win.key === key && envelopeOk(win.data?.envelope) ? win.data : null
  const plotH = compact ? 70 : H
  const x = makeX(t0, t1, W)
  const fam = motif?.family ?? null
  const medoidOk = !!(motif && fam && fam.id === 'F-03' && medoid?.length)
  // medoid aligned at the onset, offset to the live trace's value there (same mV scale, never normalised)
  let onsetV = 0
  if (cur && motif) {
    let best = Infinity
    cur.envelope.t.forEach((t, i) => { const d = Math.abs(t - motif.start_s); const v = cur.envelope.v[i]; if (d < best && v != null) { best = d; onsetV = v } })
  }
  const medT = medoidOk && medoid ? medoid.map((_, i) => motif!.start_s + i / ch.fs) : []
  const medV = medoidOk && medoid ? medoid.map(v => v - medoid[0] + onsetV) : []
  const baseRange = (cur && vRange(cur.envelope.v)) ?? ch.y_range
  const range: [number, number] = overlay && medoidOk ? [Math.min(baseRange[0], ...medV), Math.max(baseRange[1], ...medV)] : baseRange
  const y = makeY(range[0], range[1], plotH, 8, 8)
  const title = label ?? (motif ? `MOTIF_${motif.id}` : 'Motif')
  const origin = motif ? (motif.kind === 'annotated' ? `annotated, ${motif.verdict ?? 'no verdict'}` : motif.demo ? `detected, ${motif.adjudication ?? 'unadjudicated'}` : `detected, run ${motif.run_id}`) : ''
  const reviewReason = !motif ? 'select a motif first' : undefined

  if (compact) {
    return (
      <div className="card ex-tier" data-testid="motif-strip">
        <div className="head"><span className="card-title" title={motif ? `${motif.kind} id ${motif.id}` : undefined}>{title}</span>{!motif && <span className="range muted">no motif selected</span>}</div>
        <div className="ex-plot" ref={ref} style={{ height: plotH }}>
          {W > 0 && motif && (
            <svg width={W} height={plotH}>
              <rect x={0} y={0} width={W} height={plotH} fill="#fafbfc" />
              {cur ? <EnvelopePath t={cur.envelope.t} v={cur.envelope.v} x={x} y={y} stroke="var(--trace-orange)" width={1.4} /> : <rect className="skeleton" x={0} y={8} width={W} height={plotH - 16} fill="var(--grey-100)" />}
            </svg>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="card ex-tier" data-testid="signal-motif">
      <div className="head">
        <span className="card-title" title={motif ? `${motif.kind === 'annotated' ? 'annotation' : 'detection'} id ${motif.id}` : undefined} data-testid="motif-title">{title}</span>
        {motif ? (
          <span className="range" data-testid="motif-range">{(motif.start_s / 3600).toFixed(3)} – {(motif.end_s / 3600).toFixed(3)} h · {fmtSecs(motif.end_s - motif.start_s)} · {origin}</span>
        ) : <span className="range muted" data-testid="no-motif">no motif selected · click a band in the span, or use ‹ ›</span>}
        <span className="grow" />
        <Dropdown size="sm" variant="outline" prefix="context" value={String(ctx)} onChange={v => setCtx(Number(v))} options={CONTEXTS.map(c => ({ value: String(c), label: `±${c} s` }))} testid="motif-context" />
        <span data-testid="medoid-overlay" style={{ display: 'inline-flex' }}>
          <Checkbox checked={overlay && medoidOk} onChange={setOverlay} disabled={!medoidOk} label={<span style={{ color: medoidOk ? 'var(--text-2)' : undefined }}>overlay {fam ? `${fam.id} medoid` : 'family medoid'}</span>}
            disabledReason={!motif ? 'select a motif first' : !fam ? (motif.demo ? 'no family near this motif' : 'no families in this database') : 'no medoid trace for this family in the demo data'} testid="medoid-checkbox" />
        </span>
        <InfoTip title="Motif" placement="bottom-end">The opened motif with context. Onset and end are the stored span edges. The medoid is the family's most central member, drawn in mV and aligned at the onset.</InfoTip>
      </div>
      {err && <ErrorCard error={err} title="motif window failed" />}
      <div className="ex-plot" ref={ref} style={{ height: H + AXIS_H }}>
        {W > 0 && motif && (
          <svg width={W} height={H + AXIS_H} data-testid="motif-svg">
            <rect x={0} y={0} width={W} height={H + AXIS_H} fill="#fff" />
            <rect x={x(motif.start_s)} y={0} width={Math.max(1, x(motif.end_s) - x(motif.start_s))} height={H} fill="var(--band-selected)" data-testid="motif-region" />
            {cur ? <EnvelopePath t={cur.envelope.t} v={cur.envelope.v} x={x} y={y} stroke="var(--trace-orange)" width={1.3} testid="motif-path" />
              : <rect className="skeleton" x={0} y={8} width={W} height={H - 16} fill="var(--grey-100)" />}
            {overlay && medoidOk && <g data-testid="medoid-trace"><EnvelopePath t={medT} v={medV} x={x} y={y} stroke={TEAL} width={1.4} /></g>}
            <line x1={x(motif.start_s)} x2={x(motif.start_s)} y1={0} y2={H} stroke="var(--red)" strokeWidth={1} />
            <text x={x(motif.start_s) + 4} y={x(motif.start_s) < 70 ? 24 : 12} style={{ fill: 'var(--red)' }}>ONSET</text>
            <line x1={x(motif.end_s)} x2={x(motif.end_s)} y1={0} y2={H} stroke="var(--red)" strokeWidth={1} />
            <text x={x(motif.end_s) + 4} y={12} style={{ fill: 'var(--red)' }}>END</text>
            <MvLabels y={y} lo={range[0]} hi={range[1]} />
            <line x1={0} x2={W} y1={H} y2={H} stroke="var(--border)" />
            <g className="time-axis" transform={`translate(0,${H})`}>
              {relativeTicks(t0, t1, motif.start_s).map(k => <g key={k.t} transform={`translate(${x(k.t)},0)`}><line y1={0} y2={4} stroke="var(--border-strong)" /><text y={14} textAnchor="middle">{k.label}</text></g>)}
            </g>
          </svg>
        )}
        {W > 0 && !motif && <div className="muted small mono" style={{ padding: 12 }}>select a motif to see it here with ±{ctx} s of context</div>}
      </div>
      <div className="ex-motif-foot">
        <span className="fam" data-testid="motif-footer">
          nearest family {fam ? <><button type="button" className="ex-link teal" onClick={() => navigate(`library/family/${fam.id}`)} data-testid="family-link">{fam.id} →</button> d {fam.d.toFixed(2)}</> : '—'} · tagged {motif?.tag ?? '—'} · {motif ? (motif.kind === 'annotated' ? (motif.verdict ?? '—') : motif.demo ? motif.adjudication : '—') : '—'}
          {motif?.demo && <DemoTag />}
        </span>
        <span className="row">
          <Button iconRight="arrow-right" disabled={!motif} disabledReason="select a motif first" onClick={() => motif && onSend(motif)} testid="send-motif">Send motif to Analyse</Button>
          <Button variant="primary" iconRight="arrow-right" disabled={!!reviewReason} disabledReason={reviewReason} onClick={() => motif && onReview(motif)} testid="review-motif">Review this motif</Button>
        </span>
      </div>
    </div>
  )
}
