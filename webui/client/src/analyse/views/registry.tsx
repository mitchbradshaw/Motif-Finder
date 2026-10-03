/* THE drawing standard on the client (fixup-h; docs/BLOCK_INTEGRATION.md §2; webui/server/views.py).
 *
 *   The OUTPUT type decides what kind of picture you get. The INPUT type decides what one "thing" is in that
 *   picture, and whether there is a before/after to show.
 *
 * `VIEWS` holds the seven type views, keyed on the output type. Each is ONE component drawn at two tiers: the
 * chain thumbnail (interaction off: one glanceable shape) and the block settings page (`ctx.interactive`: the
 * shape plus the evidence). `MODIFIERS` holds the twelve conversions, keyed `input->output`: each is the
 * settings-tier composition for that conversion — the type view, plus what the INPUT contributes to it.
 *
 * Nothing here is selected by a block's name. A block nobody has written yet is drawn by `VIEWS[its output]`,
 * through `MODIFIERS[its conversion]` when that conversion has a row and through `PlainProcess` when it does
 * not. `tests/test_block_standard.py` checks these two tables against the server's, key for key. */
import { useMemo, useRef, useState, type ReactNode } from 'react'
import {
  type EncodingFrame, type EncodingImagePayload, type EncodingSymbolicPayload, type EnvelopeSeries, type GroupingPayload, type LabelCoverage,
  type ModelPayload, type Payload, type ScoresPayload, type SignalPayload, type SpansetPayload, type TypeKind, type WindowsetPayload,
} from '../../api'
import { EnvelopePath, SpanBands } from '../../charts/primitives'
import { clamp, makeX, makeY, polylinePath, type XScale } from '../../charts/scale'
import { useSize } from '../../charts/useSize'
import { axisUnit } from '../../charts/units'
import { Button, Histogram, InfoTip, Rose } from '../../kit'
import { fmtHours } from '../../state'
import { DetectorFunnel, funnelOf } from '../DetectorFunnel'
import { useSendRunToReview } from '../sendToReview'
import { FeatureTable, IntervalStatsTable, RulesList, labelOf, unitOf } from '../EventFeatures'
import { AlignedImage, ImageEvidence, ImageView, PaaSteps, SYM3, SymbolChunks, SymbolicView, secondsPerSymbol, symbolColour } from './EncodingView'
import { ClusterExemplars, ClusterSizes, GroupingView } from './GroupingView'
import { ModelView } from './ModelView'
import { ScoreHistogram, ScoresView, scoreWords, scoreY, type ScoreCut } from './ScoresView'
import { SignalNote, SignalView } from './SignalView'
import { DurationHistogram, SpanSetView, SpanSlideshow } from './SpanSetView'
import { WindowSetKey, WindowSetView } from './WindowSetView'
import { Empty, StaleVeil, Strip, Surface, finiteRange, fmtN, loadWindow, type ProcessProps, type ViewCtx } from './common'

type View = (props: { payload: Payload; ctx: ViewCtx }) => ReactNode

/* ============================== the seven type views ============================== */
export const VIEWS: Record<TypeKind, View> = {
  signal: ({ payload, ctx }) => <SignalView p={payload as SignalPayload} ctx={ctx} />,
  scores: ({ payload, ctx }) => <ScoresView p={payload as ScoresPayload} ctx={ctx} />,
  spanset: ({ payload, ctx }) => <SpanSetView p={payload as SpansetPayload} ctx={ctx} />,
  encoding: ({ payload, ctx }) => <EncodingAny p={payload as EncodingSymbolicPayload | EncodingImagePayload} ctx={ctx} />,
  windowset: ({ payload, ctx }) => <WindowSetView p={payload as WindowsetPayload} ctx={ctx} />,
  grouping: ({ payload, ctx }) => <GroupingView p={payload as GroupingPayload} ctx={ctx} />,
  model: ({ payload, ctx }) => <ModelView p={payload as ModelPayload} ctx={ctx} />,
}

function EncodingAny({ p, ctx }: { p: EncodingSymbolicPayload | EncodingImagePayload; ctx: ViewCtx }) {
  return p.kind === 'symbolic' ? <SymbolicView p={p as EncodingSymbolicPayload} ctx={ctx} /> : <ImageView p={p as EncodingImagePayload} ctx={ctx} />
}

/** The type view of a payload, or null for a type with no view (the caller draws its error card). */
export function TypeView({ payload, ctx }: { payload: Payload; ctx: ViewCtx }): ReactNode {
  const V = VIEWS[payload.type as TypeKind]
  return V ? <V payload={payload} ctx={ctx} /> : null
}
export const hasView = (type: string): boolean => type in VIEWS

/* ============================== settings-tier pieces ============================== */
const NoResult = ({ what = 'this stage' }: { what?: string }) => <div className="muted mono small" data-testid="no-result" style={{ padding: '18px 0' }}>no result for {what} yet · run the chain and its work is drawn here</div>

const as = <T extends Payload>(p: Payload | null, type: string): T | null => (p && p.type === type && !('error' in p && (p as { error?: unknown }).error) ? p as T : null)

/** The type view at full size on the page's time axis, veiled when it is from a stale run. */
function Full({ q, height, children, testid = 'type-view', axis = true }: { q: ProcessProps; height: number; children: (ctx: ViewCtx) => ReactNode; testid?: string; axis?: boolean }) {
  return (
    <Surface height={height} t0={q.ctx.t0} t1={q.ctx.t1} testid={testid} axis={axis}>
      {(x, w) => <>{children({ ...q.ctx, x, width: w, height, interactive: true })}<StaleVeil on={q.stale && !!q.payload} /></>}
    </Surface>
  )
}

/** The cut of the block that consumes these scores, when it has one: a float parameter named `threshold`
 *  (the convention in docs/BLOCK_INTEGRATION.md — an absolute level in the scores' own units). */
function thresholdOf(step: { params: Record<string, unknown> } | null, card: ProcessProps['card']): number | null {
  if (!step || !card) return null
  const spec = card.params.find(p => p.name === 'threshold' && p.type === 'float')
  if (!spec) return null
  const v = Number(step.params.threshold ?? spec.default)
  return Number.isFinite(v) ? v : null
}

/* ---------------- Signal ---------------- */
function SignalProcess(q: ProcessProps) {
  const p = as<SignalPayload>(q.payload, 'signal')
  if (!p) return <NoResult />
  return (
    <>
      <Full q={q} height={260}>{ctx => <SignalView p={p} ctx={ctx} />}</Full>
      <SignalNote p={p} ctx={q.ctx} />
      <div className="bp-legend" style={{ paddingLeft: 0 }}><span><i style={{ background: 'var(--trace-ghost)' }} />before · this block's input</span><span><i style={{ background: 'var(--trace-blue)' }} />after · this block's output</span><span>hover for both values at one time</span></div>
    </>
  )
}

/* ---------------- Scores ---------------- */
function ScoresProcess({ q, above }: { q: ProcessProps; above?: ReactNode }) {
  const p = as<ScoresPayload>(q.payload, 'scores')
  if (!p) return <>{above}<NoResult /></>
  const nextCut = q.nextCard?.modifier === 'scores->spanset' ? thresholdOf(q.next, q.nextCard) : null
  const cut: ScoreCut | null = nextCut === null ? null : { value: nextCut, label: `cut of ${q.nextCard?.page_name ?? 'the next stage'} ${fmtN(nextCut)}` }
  return (
    <>
      {above}
      <Full q={q} height={above ? 190 : 280} testid="type-view">{ctx => <ScoresView p={p} ctx={above ? { ...ctx, ghost: null } : ctx} cut={cut} />}</Full>
      <div className="bp-card-title" style={{ marginTop: 8 }}><h3 style={{ fontSize: 13 }}>{p.m ? 'Profile values' : 'Score values'}</h3><span className="sg">{p.histogram ? `${p.histogram.counts.length} bins` : ''}{cut ? ' · amber = above the next stage\'s cut' : ' · no stage after this one cuts these scores'}</span></div>
      <ScoreHistogram p={p} cut={cut} />
    </>
  )
}

/** encoding → scores: the image above, the curve below, same x, the summed band marked on the image. The band is
 *  read from the step's `row_from` / `row_to` (fractions of the image height) when the block has them. */
function EncodingToScores(q: ProcessProps) {
  const up = as<EncodingImagePayload>(q.upstream, 'encoding')
  // a parameter the chain does not set is at its declared default
  const param = (name: string) => Number(q.step.params[name] ?? q.card?.params.find(p => p.name === name)?.default)
  const a = param('row_from'), b = param('row_to')
  const band: [number, number] | null = Number.isFinite(a) && Number.isFinite(b) && b > a ? [a, b] : null
  const above = !up || up.kind !== 'image' ? <div className="muted mono small" style={{ marginBottom: 6 }}>the upstream Encoding is not loaded · run the chain to see the image these scores were computed from</div>
    : up.frames?.axis === 'time'
      ? <><Full q={q} height={150} testid="scores-upstream-image" axis={false}>{ctx => <AlignedImage p={up} ctx={ctx} band={band} />}</Full><div className="muted mono small" style={{ margin: '2px 0 6px' }}>the image these scores were computed from, on the same x{band ? ' · the amber box is the band of rows the block summed' : ''}</div></>
      : <><Full q={q} height={130} testid="scores-upstream-image" axis={false}>{ctx => <ImageView p={up} ctx={{ ...ctx, interactive: false }} />}</Full><div className="muted mono small" style={{ margin: '2px 0 6px' }}>the images these scores were computed from · each is marked on the bar where it sits in time</div></>
  return <ScoresProcess q={q} above={above} />
}

/* ---------------- SpanSet ---------------- */
function useSendToReview(q: ProcessProps, n: number) {
  // the same call the chain footer's *Pass N to Review* makes (fixup-L): one queue over this run, opened
  const { send, busy, reason } = useSendRunToReview({ chainName: q.chainName, dbRunId: q.dbRunId, n, stale: q.stale })
  return <Button variant="primary" icon="arrow-right" onClick={send} disabled={!!reason || busy} disabledReason={reason} loading={busy} testid="send-to-review">Send {n} to Review</Button>
}

function SpanSetProcess({ q, lead, featuresFirst }: { q: ProcessProps; lead?: ReactNode; featuresFirst?: boolean }) {
  const p = as<SpansetPayload>(q.payload, 'spanset')
  const [selected, setSelected] = useState<number | null>(null)
  const action = useSendToReview(q, p?.n ?? 0)
  const rec = q.source.recording_id
  const load = useMemo(() => (e: { window?: [number, number] | null }) => loadWindow(rec, e.window![0], e.window![1], 420), [rec])
  if (!p) return <>{lead}<NoResult /></>
  const funnel = funnelOf(p)
  const impure = (p.window_counts ?? []).filter(c => c > 1).length
  const spans = (
    <>
      <Full q={q} height={featuresFirst ? 110 : 190}>{ctx => <SpanSetView p={p} ctx={ctx} selected={selected} onSelect={setSelected} />}</Full>
      <div className="bp-legend" style={{ paddingLeft: 0 }}>
        <span><i style={{ background: 'var(--band-detected)', border: '1px solid var(--blue)' }} />span</span>
        {p.marks && <span><i style={{ background: 'var(--blue)', opacity: 0.45 }} />the fall inside its window (onset → extremum)</span>}
        {impure > 0 && <span><i style={{ background: 'var(--band-artifact)', border: '1px solid var(--red)' }} />window holding more than one {p.window_count_of === 'falls' ? 'fall' : 'span'}</span>}
        <span><i style={{ background: 'var(--amber)' }} />selected · click a span or a card</span>
        {p.marks && <span>overlapping windows are shared context, not double-counting</span>}
      </div>
    </>
  )
  return (
    <>
      {featuresFirst && lead}
      {!featuresFirst && lead}
      {spans}
      {funnel && <DetectorFunnel funnel={funnel} />}
      <div style={{ marginTop: 10 }}>
        <SpanSlideshow p={p} t0={q.ctx.t0} t1={q.ctx.t1} load={load} selected={selected} onSelect={setSelected} action={action} unit={q.sourceUnit || 'as stored'} />
      </div>
      <div className="bp-card-title" style={{ marginTop: 10 }}><h3 style={{ fontSize: 13 }}>Span durations</h3><span className="sg">{p.n} span{p.n === 1 ? '' : 's'}</span></div>
      <DurationHistogram p={p} />
    </>
  )
}

/** Contiguous runs of the decimated envelope above a threshold (approximate — the core thresholds every sample). */
function runsAbove(env: EnvelopeSeries, thr: number): { start_s: number; end_s: number }[] {
  const out: { start_s: number; end_s: number }[] = []
  let open: number | null = null
  for (let i = 0; i < env.t.length; i++) {
    const v = env.v[i]
    const above = v !== null && v > thr
    if (above && open === null) open = env.t[i]
    if (!above && open !== null) { out.push({ start_s: open, end_s: env.t[i] }); open = null }
  }
  if (open !== null) out.push({ start_s: open, end_s: env.t[env.t.length - 1] + 1 })
  return out
}

/** A draggable vertical cut on a value axis. */
function CutLineV({ x, value, onChange, height, label }: { x: XScale; value: number; onChange: (v: number) => void; height: number; label: string }) {
  const drag = useRef(false)
  const px = clamp(x(value), x.range()[0], x.range()[1])
  const [lo, hi] = x.domain()
  return (
    <g data-testid="spans-vs-cut-line">
      <line x1={px} x2={px} y1={0} y2={height} stroke="var(--amber)" strokeWidth={1.5} />
      <text x={px > x.range()[1] - 90 ? px - 5 : px + 5} y={12} textAnchor={px > x.range()[1] - 90 ? 'end' : 'start'} fill="var(--amber)" style={{ fontSize: 10, fontWeight: 600, paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{label}</text>
      <rect x={px - 7} y={0} width={14} height={height} fill="transparent" style={{ cursor: 'ew-resize' }}
        onPointerDown={e => { drag.current = true; e.currentTarget.setPointerCapture(e.pointerId) }}
        onPointerMove={e => { if (!drag.current) return; const svg = e.currentTarget.ownerSVGElement; if (!svg) return; onChange(+clamp(x.invert(e.clientX - svg.getBoundingClientRect().left), lo, hi).toPrecision(4)) }}
        onPointerUp={e => { drag.current = false; e.currentTarget.releasePointerCapture(e.pointerId) }} />
    </g>
  )
}

/** Span count for 41 cut values across the score range, from the same envelope the curve is drawn from. */
function SpansVsCut({ scores, threshold, onThreshold }: { scores: ScoresPayload; threshold: number; onThreshold: (v: number) => void }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width); const h = 130
  const curve = useMemo(() => {
    const r = scores.value_range ?? [0, 1]
    const lo = Math.min(0, r[0]), hi = Math.max(0, r[1])
    if (!(hi > lo)) return null
    const cuts: number[] = []; const counts: number[] = []
    for (let k = 0; k <= 40; k++) { const c = lo + (hi - lo) * k / 40; cuts.push(c); counts.push(runsAbove(scores.envelope, c).length) }
    return { cuts, counts, lo, hi }
  }, [scores])
  const nowN = runsAbove(scores.envelope, threshold).length
  return (
    <div data-testid="spans-vs-cut">
      <div className="plot-surface" ref={ref} style={{ height: h }}>
        {size.width > 0 && curve && (() => {
          const x = makeX(curve.lo, curve.hi, w, 30, 8)
          const y = makeY(0, Math.max(1, ...curve.counts), h - 18, 6, 0)
          return (
            <svg width={w} height={h}>
              <path d={polylinePath(curve.cuts, curve.counts, x, y)} fill="none" stroke="var(--blue)" strokeWidth={1.4} />
              <text x={26} y={y(Math.max(1, ...curve.counts)) + 3} textAnchor="end" fill="var(--muted)">{Math.max(1, ...curve.counts)}</text>
              <text x={26} y={y(0) + 3} textAnchor="end" fill="var(--muted)">0</text>
              <text x={30} y={h - 4} fill="var(--muted-2)">{fmtN(curve.lo)}</text>
              <text x={w - 8} y={h - 4} textAnchor="end" fill="var(--muted-2)">{fmtN(curve.hi)} · cut value</text>
              <circle cx={x(threshold)} cy={y(nowN)} r={3.5} fill="var(--amber)" stroke="#fff" strokeWidth={1} />
              <CutLineV x={x} value={threshold} onChange={onThreshold} height={h - 18} label={`cut ${fmtN(threshold)} → ${nowN}`} />
            </svg>
          )
        })()}
        {size.width > 0 && !curve && <div className="an-plot-empty">the scores have no range to cut</div>}
      </div>
      <div className="muted mono small">≈ {nowN} span{nowN === 1 ? '' : 's'} at this cut, counted on the drawn envelope (the core cuts every sample)</div>
    </div>
  )
}

/** scores → spanset: the cut drawn on the score curve, draggable when the block's cut is an absolute level. */
function ScoresToSpans(q: ProcessProps) {
  const scores = as<ScoresPayload>(q.upstream, 'scores')
  const result = as<SpansetPayload>(q.payload, 'spanset')
  const thr = thresholdOf(q.step, q.card)
  const lead = !scores
    ? <div className="muted mono small" style={{ marginBottom: 8 }}>the upstream Scores are not loaded — run the chain so the stage before this one has a result, and its curve is drawn here with this block's cut on it</div>
    : (
      <>
        <Strip label="scores + cut" sub={thr !== null ? 'drag the line' : 'upstream'} height={160} t0={q.ctx.t0} t1={q.ctx.t1} testid="threshold-strip">
          {(x, w, h) => {
            const y = scoreY(scores, h, 20)
            if (!y) return <text x={4} y={14} fill="var(--muted)">the upstream scores hold no finite value</text>
            const above = thr !== null ? runsAbove(scores.envelope, thr) : []
            return (
              <>
                <SpanBands spans={above.map((s, i) => ({ ...s, kind: 'selected' as const, id: i, title: 'above the cut now (from the drawn envelope)' }))} x={x} height={h} minPx={2} />
                <ScoresView p={scores} ctx={{ ...q.ctx, x, width: w, height: h, ghost: null, interactive: false, hideKey: true }} marks={false}
                  cut={thr !== null ? { value: thr, label: `threshold ${fmtN(thr)}`, onChange: v => q.setParam('threshold', v) } : null} />
                {thr !== null && <text x={4} y={h - 16} fill="var(--muted-2)">amber = above the cut now ({above.length} run{above.length === 1 ? '' : 's'}, approximate)</text>}
              </>
            )
          }}
        </Strip>
        {thr === null && <div className="muted mono small" style={{ paddingLeft: 76, marginBottom: 6 }} data-testid="no-draggable-cut">this block's cut is not one absolute level in the scores' units (it has no <code>threshold</code> parameter), so there is no line to drag · its decisions are the spans below{funnelOf(result) ? ' and the stages of its funnel' : ''}</div>}
        {thr !== null && (
          <div className="row" style={{ alignItems: 'flex-start', gap: 12, marginBottom: 8 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="bp-card-title" style={{ marginTop: 4 }}><h3 style={{ fontSize: 13 }}>{scoreWords(scores)} values</h3><span className="sg">amber = above the cut</span></div>
              <ScoreHistogram p={scores} cut={{ value: thr, label: `cut ${fmtN(thr)}` }} />
            </div>
            <div style={{ width: 320 }}>
              <div className="bp-card-title" style={{ marginTop: 4 }}><h3 style={{ fontSize: 13 }}>Spans vs cut</h3><span className="sg">drag the cut</span></div>
              <SpansVsCut scores={scores} threshold={thr} onThreshold={v => q.setParam('threshold', v)} />
            </div>
          </div>
        )}
      </>
    )
  return <SpanSetProcess q={q} lead={lead} />
}

/** encoding → spanset: which cells or symbols fired, marked on the encoding itself. */
function EncodingToSpans(q: ProcessProps) {
  const up = as<EncodingSymbolicPayload | EncodingImagePayload>(q.upstream, 'encoding')
  const result = as<SpansetPayload>(q.payload, 'spanset')
  const outlines = (x: XScale, h: number) => result?.start_s.map((s, i) => (
    <rect key={i} x={x(s)} y={1} width={Math.max(2, x(result.end_s[i]) - x(s))} height={h - 2} fill="none" stroke="var(--text)" strokeWidth={1.5} rx={2} data-testid="fired-outline"><title>{`span #${i + 1}`}</title></rect>
  ))
  const lead = !up
    ? <div className="muted mono small" style={{ marginBottom: 8 }}>the upstream Encoding is not loaded — run the chain and the symbols this block read are drawn here with the ones that fired outlined</div>
    : up.kind === 'symbolic'
      ? (
        <Strip label="what fired" sub="spans outlined" height={56} t0={q.ctx.t0} t1={q.ctx.t1} testid="fired-on-encoding">
          {(x, w, h) => <><foreignObject x={0} y={0} width={w} height={h}><SymbolicView p={up as EncodingSymbolicPayload} ctx={{ ...q.ctx, x, width: w, height: h, hideKey: true, interactive: false }} /></foreignObject>{outlines(x, h)}</>}
        </Strip>
      )
      : (up as EncodingImagePayload).frames?.axis === 'time'
        ? (
          <div style={{ position: 'relative', marginBottom: 8 }} data-testid="fired-on-encoding">
            <Full q={q} height={130} axis={false} testid="fired-image">{ctx => <><AlignedImage p={up as EncodingImagePayload} ctx={ctx} /><svg width={ctx.width} height={ctx.height} style={{ position: 'absolute', inset: 0 }}>{outlines(ctx.x, ctx.height)}</svg></>}</Full>
          </div>
        )
        : <div className="muted mono small" style={{ marginBottom: 8 }}>the upstream image has no column-per-sample time axis, so the spans cannot be marked on it · they are marked on the signal below</div>
  return <SpanSetProcess q={q} lead={lead} />
}

/** an axis label short enough for a narrow card */
const short = (v: number) => String(+v.toPrecision(3))

/** One small histogram per measure, with what was NOT measured on the face of it. */
function FeatureHistograms({ p }: { p: SpansetPayload }) {
  const f = p.features
  if (!f || !f.matrix) return f ? <div className="muted mono small">{f.n_columns} measures per event · the table is too large to ship ({f.columns.join(', ')})</div> : null
  const cols = f.columns.map((c, k) => ({ c, k })).filter(({ c }) => !c.endsWith('_idx') && c !== 'polarity')
  const n = f.matrix.length
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))', gap: 10 }} data-testid="feature-histograms">
      {cols.map(({ c, k }) => {
        const vals = f.matrix!.map(r => r[k]).filter((v): v is number => v !== null && Number.isFinite(v))
        const missing = n - vals.length
        const r = finiteRange(vals)
        const rule = p.rules?.find(x => c.startsWith(x.name) || x.name.startsWith(c.replace(/_(mv_s|mv|s)$/, '')))
        return (
          <div key={c} className="card" style={{ padding: '8px 10px' }} data-testid={`measure-${c}`}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <b style={{ fontSize: 12 }}>{labelOf(c)}</b><span className="muted mono small">{unitOf(c)}</span>
              {rule && <InfoTip title={labelOf(c)}>{rule.rule}</InfoTip>}
            </div>
            {vals.length >= 2 && r && r[1] > r[0]
              ? <Histogram values={vals} nBins={Math.min(16, Math.max(5, Math.round(Math.sqrt(vals.length))))} height={96} colour="var(--blue-200)" format={short} xTicks={3} label={`${labelOf(c)} distribution`} />
              : <div className="muted mono small" style={{ height: 96, display: 'flex', alignItems: 'center' }}>{vals.length === 0 ? 'nothing to draw' : vals.length === 1 || (r && r[0] === r[1]) ? `every measured event is ${fmtN(vals[0])}` : ''}</div>}
            {/* an absence is the result, and stays on the face of the card (Q21) */}
            <div className="mono small" style={{ color: missing ? '#a05e00' : 'var(--muted)' }} data-testid={missing ? 'measure-absent' : undefined}>
              {missing ? `${missing} of ${n} events have no ${labelOf(c)}` : `n ${vals.length}${r ? ` · ${fmtN(r[0])} … ${fmtN(r[1])}` : ''}`}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** spanset → spanset: THE FEATURES, NOT THE SPANS. A feature block passes its spans through; what it found is the
 *  measures, so those lead: a histogram per measure, the rose, the interval statistics. The table is still
 *  there, folded away, because the point of this page is not to read a table. */
function SpansToSpans(q: ProcessProps) {
  const p = as<SpansetPayload>(q.payload, 'spanset')
  if (!p) return <NoResult />
  const lead = !p.features ? <div className="muted mono small" style={{ marginBottom: 8 }}>this block returned its spans with no measures attached</div> : (
    <div className="stack" style={{ gap: 12, marginBottom: 14 }} data-testid="event-features">
      {p.features_unit_note && <div className="callout warn small" data-testid="features-unit-note" style={{ padding: '6px 10px', background: '#fff7e6', borderRadius: 6 }}>{p.features_unit_note}</div>}
      <div>
        <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>What was measured</h3><span className="sg">{p.n} events · one distribution per measure · the rule behind each is under its ⓘ</span></div>
        <FeatureHistograms p={p} />
      </div>
      {p.rose && <div><div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Steepest slope, each event as one angle</h3></div><Rose rose={p.rose} testid="rose-fan" /></div>}
      {p.interval_stats && <div><div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Inter-event intervals</h3><span className="sg">per group, never pooled</span></div><IntervalStatsTable stats={p.interval_stats} /></div>}
      <details data-testid="feature-table-fold">
        <summary className="muted" style={{ cursor: 'pointer', fontSize: 11.5 }}>the per-event table · {p.features.n_columns} columns × {p.n} rows</summary>
        <FeatureTable table={p.features} />
      </details>
      {p.rules && <RulesList rules={p.rules} />}
      <div className="bp-card-title" style={{ marginTop: 2 }}><h3 style={{ fontSize: 13 }}>The spans that were measured</h3><span className="sg">passed through unchanged from the stage before</span></div>
    </div>
  )
  return <SpanSetProcess q={q} lead={lead} featuresFirst />
}

/* ---------------- Encoding ---------------- */
function EncodingProcess(q: ProcessProps) {
  const p = as<EncodingSymbolicPayload | EncodingImagePayload>(q.payload, 'encoding')
  const [extra, setExtra] = useState<EncodingFrame | null>(null)
  if (!p) return <NoResult />
  if (p.kind !== 'symbolic') {
    const img = p as EncodingImagePayload
    const what = q.card?.input_kind === 'windowset' ? 'which window each image is' : 'which chunk of signal each image came from'
    return (
      <>
        <Full q={q} height={img.ndim === 1 ? 180 : 250}>{ctx => <ImageView p={img} ctx={ctx} extraFrame={extra} />}</Full>
        {img.frames && <Strip label="where" sub="in the signal" height={44} t0={q.ctx.t0} t1={q.ctx.t1} testid="frame-source">
          {(x, w, h) => {
            const gr = q.ctx.ghost ? finiteRange(q.ctx.ghost.v) : null
            const frames = extra ? [...img.frames!.shown, extra] : img.frames!.shown
            const tint = ['#0a84ff', '#8e5cf7', '#22a06b', '#e8900c']
            return (
              <>
                {frames.map((f, i) => f.t0_s === null || f.t1_s === null ? null : <g key={i}><rect x={x(f.t0_s)} y={0} width={Math.max(2, x(f.t1_s) - x(f.t0_s))} height={h} fill={tint[i % 4]} fillOpacity={0.22} stroke={tint[i % 4]} /><text x={x(f.t0_s) + 3} y={11} style={{ fill: tint[i % 4], fontWeight: 700 }}>{i + 1}</text></g>)}
                {q.ctx.ghost && gr ? <EnvelopePath t={q.ctx.ghost.t} v={q.ctx.ghost.v} x={x} y={makeY(gr[0], gr[1], h)} stroke="var(--trace)" /> : <text x={w - 6} y={h - 5} textAnchor="end" fill="var(--muted)">the input signal is not loaded</text>}
                {frames.every(f => f.t0_s === null) && <text x={4} y={h - 5} fill="var(--muted)">this result does not say where its images sit in time</text>}
              </>
            )
          }}
        </Strip>}
        <div className="muted mono small" style={{ paddingLeft: 76 }}>{what} · numbered as the images above</div>
        <ImageEvidence p={img} jobId={q.jobId} index={q.index} onFrame={setExtra} />
      </>
    )
  }
  const s = p as EncodingSymbolicPayload
  const sps = secondsPerSymbol(s, q.ctx)
  const paa = s.paa
  const cuts = s.cutlines ?? []
  const deltas = paa ? paa.slice(1).map((v, i) => v - paa[i]) : null
  const ghost = q.ctx.ghost
  const gr = ghost ? finiteRange(ghost.v) : null
  return (
    <SymbolChunks p={s} ctx={q.ctx}>
      {brackets => (
        <>
          {(ghost || paa) && (
            <Strip label={paa ? 'signal + PAA' : 'signal'} sub={`${fmtN(sps)} s segments`} height={100} t0={q.ctx.t0} t1={q.ctx.t1} testid="symbolic-signal">
              {(x, _w, h) => <>{ghost && gr && <EnvelopePath t={ghost.t} v={ghost.v} x={x} y={makeY(gr[0], gr[1], h)} stroke="var(--trace)" />}{paa && <PaaSteps paa={paa} t0={s.t0_s} sps={sps} x={x} h={h} />}</>}
            </Strip>
          )}
          {deltas && (
            <Strip label="Δ per segment" sub={cuts.length ? 'and cutlines' : undefined} height={84} t0={q.ctx.t0} t1={q.ctx.t1} testid="symbolic-cutlines">
              {(x, w, h) => {
                const ext = Math.max(...deltas.map(Math.abs), ...cuts.map(Math.abs), 1e-9)
                const y = makeY(-ext, ext, h, 6, 6)
                const cw = Math.max(1, x(q.ctx.t0 + sps) - x(q.ctx.t0) - 0.5)
                return (
                  <>
                    <line x1={0} x2={w} y1={y(0)} y2={y(0)} stroke="var(--border)" />
                    {deltas.map((d, i) => <rect key={i} x={x(s.t0_s + (i + 1) * sps)} y={Math.min(y(0), y(d))} width={cw} height={Math.abs(y(d) - y(0))} fill={s.alphabet_size === 3 ? SYM3[s.symbols[i + 1] ?? 1] : symbolColour(s, s.symbols[i + 1] ?? 0)} opacity={0.8} />)}
                    {cuts.map((c, i) => <g key={i} data-testid="symbolic-cutline"><line x1={0} x2={w} y1={y(c)} y2={y(c)} stroke="var(--red)" strokeDasharray="4 3" /><text x={c >= 0 ? w - 4 : 4} y={c >= 0 ? y(c) - 3 : y(c) + 10} textAnchor={c >= 0 ? 'end' : 'start'} fill="var(--red)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{c > 0 ? '+' : ''}{c.toExponential(2)} · learned · not a parameter</text></g>)}
                  </>
                )
              }}
            </Strip>
          )}
          <Strip label={`symbols · k ${s.alphabet_size}`} sub={`${s.n_symbols.toLocaleString()} symbols`} height={44} t0={q.ctx.t0} t1={q.ctx.t1} axis testid="symbolic-strip">
            {(x, w, h) => <><foreignObject x={0} y={0} width={w} height={h}><SymbolicView p={s} ctx={{ ...q.ctx, x, width: w, height: h, hideKey: true, interactive: false }} brackets={brackets} /></foreignObject>{q.stale && <rect x={0} y={0} width={w} height={h} fill="rgba(255,255,255,0.55)" />}</>}
          </Strip>
          <div className="bp-legend">
            {s.alphabet_size === 3 ? <><span><i style={{ background: SYM3[0] }} />down</span><span><i style={{ background: SYM3[1] }} />same</span><span><i style={{ background: SYM3[2] }} />up</span></> : <span>alphabet {s.alphabet_size}{s.alphabet ? ` · ${s.alphabet}` : ''} · one colour per symbol</span>}
            {paa && <span><i style={{ background: 'var(--blue-600)' }} />PAA mean · own scale</span>}
            {cuts.length > 0 && <span><i style={{ background: 'var(--red)' }} />cutlines · learned</span>}
            {!paa && <span>this encoder ships no PAA or cutlines for this result</span>}
          </div>
        </>
      )}
    </SymbolChunks>
  )
}

/* ---------------- WindowSet · Grouping · Model ---------------- */
function WindowSetProcess(q: ProcessProps) {
  const p = as<WindowsetPayload>(q.payload, 'windowset')
  if (!p) return <NoResult />
  return (
    <>
      <Full q={q} height={p.features?.matrix ? Math.min(420, 60 + 12 * p.features.n_columns) : 150}>{ctx => <WindowSetView p={p} ctx={ctx} />}</Full>
      <WindowSetKey p={p} />
    </>
  )
}

function GroupingProcess(q: ProcessProps) {
  const p = as<GroupingPayload>(q.payload, 'grouping')
  if (!p) return <NoResult />
  return (
    <>
      <Full q={q} height={Math.min(300, 70 + 30 * Math.max(1, p.clusters.length))}>{ctx => <GroupingView p={p} ctx={ctx} />}</Full>
      <div className="muted mono small" style={{ marginTop: 2 }}>{p.class_names ? 'top: the label of every window, in time (grey = excluded) · below: where each label falls' : 'top: the cluster of every window, in time · below: when each cluster is active'}</div>
      {p.coverage && <LabelCoverageLine c={p.coverage} />}
      {p.rules && <RulesList rules={p.rules} testid="label-rules" />}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12 }}>
        <div style={{ width: 300 }}>
          <div className="bp-card-title" style={{ marginTop: 10 }}><h3 style={{ fontSize: 13 }}>{p.class_names ? 'Class sizes' : 'Cluster sizes'}</h3><span className="sg">{p.n.toLocaleString()} windows</span></div>
          <ClusterSizes p={p} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}><ClusterExemplars p={p} recordingId={q.source.recording_id} unit={q.sourceUnit || 'as stored'} /></div>
      </div>
    </>
  )
}

/** The labelled Grouping's coverage, every fate on the face (an absence is the result, never hidden). */
function LabelCoverageLine({ c }: { c: LabelCoverage }) {
  const cells: [string, number | string][] = [['windows', c.n_windows], ['labelled', c.labelled], ['interesting', c.interesting], ['not_interesting', c.not_interesting],
    ['unlabelled', c.unlabelled], ['conflicting', c.conflicting], ['artifact', c.artifact], ['dropped for overlap', c.dropped_for_overlap]]
  return (
    <div className="bp-tiles" data-testid="label-coverage" style={{ marginTop: 8 }}>
      {cells.map(([k, v]) => <div className="bp-tile" key={k}><div className="k">{k}</div><div className="v">{typeof v === 'number' ? v.toLocaleString() : v}</div></div>)}
      {c.non_overlap_rule && <div className="bp-tile"><div className="k">non-overlap</div><div className="v">{c.non_overlap_rule}</div></div>}
    </div>
  )
}

function ModelProcess(q: ProcessProps) {
  const p = as<ModelPayload>(q.payload, 'model')
  if (!p) return <NoResult />
  return <div style={{ position: 'relative' }} data-testid="type-view"><ModelView p={p} ctx={{ ...q.ctx, interactive: true }} /><StaleVeil on={q.stale} /></div>
}

/* ============================== the twelve modifiers ============================== */
type Process = (q: ProcessProps) => ReactNode

export const MODIFIERS: Record<string, Process> = {
  'signal->signal': SignalProcess,
  'signal->scores': q => <ScoresProcess q={q} />,
  'encoding->scores': EncodingToScores,
  'scores->spanset': ScoresToSpans,
  'encoding->spanset': EncodingToSpans,
  'signal->spanset': q => <SpanSetProcess q={q} />,
  'spanset->spanset': SpansToSpans,
  'signal->encoding': EncodingProcess,
  'windowset->encoding': EncodingProcess,
  'signal->windowset': WindowSetProcess,
  'windowset->grouping': GroupingProcess,
  'grouping->model': ModelProcess,
}

/** A conversion with no modifier row: the output type's own settings tier, with nothing input-specific added. */
const PLAIN: Record<TypeKind, Process> = {
  signal: SignalProcess, scores: q => <ScoresProcess q={q} />, spanset: q => <SpanSetProcess q={q} />, encoding: EncodingProcess,
  windowset: WindowSetProcess, grouping: GroupingProcess, model: ModelProcess,
}

/** The settings tier of one block: its conversion's modifier, else its output type's view. Never a generic dump. */
export function BlockProcess(q: ProcessProps): ReactNode {
  const key = q.card?.modifier ?? null
  const kind = (q.card?.view ?? q.payload?.type) as TypeKind | undefined
  const P = (key && MODIFIERS[key]) || (kind && PLAIN[kind])
  if (!P) return <Empty text={`no view for output type "${kind ?? '?'}"`} />
  return <div data-testid="block-view" data-view={kind} data-modifier={key ?? 'none'}><P {...q} /></div>
}
