/* Review page parts shared by the inspector (frames 1, 1b, 3–6) and the cluster page (frames 2, 7). */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { datasetName, useDatasetNames, type DatasetNames } from '../naming'
import { navigate } from '../state'
import {
  Button, Callout, Chip, DisabledReason, Icon, IconButton, InfoTip, Kbd, Legend, MiniTrace, Pager, Popover, Seg, TextField, Toggle, Trace, cx, fmtInt, useDemoState, useQueryState, type IconName,
} from '../kit'
import { useSourced } from '../api/seam'
import { getSeedPage } from '../api/discovery'
import { VOCABULARY, getOtherChannels, useTagVocabulary, type ArtifactFactors, type ItemDetail, type NearestFamily, type QueueRow, type TimeTrace, type Verdict } from '../api/review'
import { drawable, sliceContext } from './axis'
import { baselinePeak, centreTrace, measuredDomain, referenceScale } from '../charts/domain'
import { ScaleBar } from '../charts/ScaleBar'
import { ReferenceBar, fmtRef, referenceWords } from '../charts/ReferenceBar'
import { VERDICT_LABEL, type Draft, type VerdictRecord } from './store'

/* Every Review plot is drawn on a domain measured from its own trace (charts/domain.ts, fixup-c, Q-R1.1). There
   used to be one hand-set domain for every trace, [-0.44, 0.44] — a correct centred domain for a whole channel's
   swing in VOLTS, hand-measured off data the bridge served unconverted — then ±440 mV after fixup-b. A
   candidate's own trace is a small fraction of a channel's swing, which is exactly why every Review plot read
   flat, and a candidate whose baseline sat outside it ran along the frame. The reviewer is judging whether this
   is a real event, so how big it is against the rest of the queue is evidence too: that is the Shape card's
   reference bar. */

export function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const id = window.setInterval(() => setNow(Date.now()), ms); return () => window.clearInterval(id) }, [ms])
  return now
}

/* ---------------- title row ---------------- */
export function Pill({ dot, icon, label, value, tone, title, testid, shrink }: { dot?: string; icon?: IconName; label: ReactNode; value: ReactNode; tone?: 'green' | 'amber' | 'blue' | 'purple'; title?: string; testid?: string; shrink?: boolean }) {
  return (
    <span className={cx('rv-pill', tone, shrink && 'shrink')} title={title ?? (typeof value === 'string' ? `${typeof label === 'string' ? label : 'artifact likelihood'} ${value}` : undefined)} data-testid={testid}>
      {dot && <i className="dot" style={{ background: dot }} />}{icon && <Icon name={icon} size={13} />}
      <span className="lbl">{label}</span><b>{value}</b>
    </span>
  )
}

export function statusText(rec: VerdictRecord | null) {
  if (!rec) return 'unadjudicated'
  if (rec.verdict === 'seed') return rec.exemplarId ? 'seed · promoted' : 'seed'
  return `${VERDICT_LABEL[rec.verdict]}${rec.className ? ` · ${rec.className}` : ''}`
}
export const statusDot = (rec: VerdictRecord | null) => !rec ? 'var(--muted-2)' : rec.verdict === 'seed' || rec.verdict === 'interesting' ? 'var(--green)' : rec.verdict === 'artifact' ? 'var(--red)' : rec.verdict === 'unsure' ? 'var(--amber)' : 'var(--muted)'

export function ArtifactPill({ a, short, testid = 'pill-artifact' }: { a: ArtifactFactors | { level: string | null }; short?: boolean; testid?: string }) {
  // `level` is null when nothing computed the factors. The pill still shows —
  // artifact likelihood is never hidden (spec §10.2) — but it says what is true
  // rather than defaulting to the red "high" tone of an unknown value.
  const known = a.level != null
  const tone = !known ? undefined : a.level === 'low' ? 'green' : a.level === 'medium' ? 'amber' : undefined
  const dot = !known ? 'var(--muted)' : a.level === 'low' ? 'var(--green)' : a.level === 'medium' ? 'var(--amber)' : 'var(--red)'
  return <Pill dot={dot} label={short ? 'artifact' : <>artifact<span className="long"> likelihood</span></>} value={known ? a.level : 'not computed'} tone={tone} title={known ? 'artifact likelihood is never hidden' : 'nothing has computed artifact factors for this queue yet'} testid={testid} />
}

/* ---------------- time ticks (hours since recording start, frame decimals) ---------------- */
export function TimeTicks({ t0, t1, n = 5, testid }: { t0: number; t1: number; n?: number; testid?: string }) {
  const span = t1 - t0
  const digits = span <= 450 ? 3 : 2
  return (
    <div className="rv-ticks mono" data-testid={testid}>
      <span style={{ left: 0, width: 38, textAlign: 'right' }}>mV</span>
      {Array.from({ length: n }, (_, i) => {
        const f = i / (n - 1)
        return <span key={i} style={{ left: `calc(44px + (100% - 54px) * ${f})`, transform: i === 0 ? 'none' : i === n - 1 ? 'translateX(-100%)' : 'translateX(-50%)' }}>{((t0 + span * f) / 3600).toFixed(digits)} h</span>
      })}
    </div>
  )
}

/* ---------------- context card (frames 1, 1b, 2, 5) ---------------- */
/* The band the item's own bounds draw, in absolute seconds — the ONE coordinate system every trace here shares. */
export const itemBand = (d: ItemDetail) => ({ start_s: d.entry.startH * 3600, end_s: d.entry.startH * 3600 + d.entry.durationS })

/** How a trace was served, in words a reviewer can check: samples in the window, points drawn, and whether the
 *  points are every sample or a min/max envelope. A capped trace says so rather than looking merely coarse. */
export function ResolutionNote({ tr, testid }: { tr: TimeTrace; testid?: string }) {
  if (!tr.n_source) return <span className="mono muted sm" data-testid={testid}>{tr.reason ?? 'no samples'}</span>
  const rate = tr.fs != null ? ` · ${tr.fs % 1 === 0 ? tr.fs : tr.fs.toFixed(2)} Hz` : ''
  return (
    <span className="mono muted sm" data-testid={testid} data-decimated={tr.decimated ? '1' : '0'} data-capped={tr.capped ? '1' : '0'}
      title={tr.decimated ? `${fmtInt(tr.n_source)} samples drawn as ${fmtInt(tr.n_points)} min/max points over ${tr.px} px` : `every one of the ${fmtInt(tr.n_source)} samples is drawn`}>
      {fmtInt(tr.n_source)} samples{rate}{tr.decimated ? ` · ${fmtInt(tr.n_points)} points` : ' · every sample drawn'}{tr.capped ? <b className="rv-amber"> · capped at {tr.px} px</b> : null}
    </span>
  )
}

export function ContextCard({ d, title, pad, setPad, bandLabel, canEdit, testid = 'context-card' }: { d: ItemDetail; title: string; pad: '30' | '120' | '300'; setPad: (p: '30' | '120' | '300') => void; bandLabel: string; canEdit: boolean; testid?: string }) {
  // by TIME, not by index: the served points are an envelope — fewer than the samples, not evenly spaced — and
  // the band beside them is in seconds. Slicing points as seconds is what made ±120 s look one-sided (U3).
  const ctx = useMemo(() => sliceContext(d.context, itemBand(d), +pad), [d, pad])
  const [pop, setPop] = useQueryPop()
  const ocRef = useRef<HTMLButtonElement>(null)
  const open = pop === 'other-channels'
  return (
    <section className="rv-card" data-testid={testid} data-pad={pad}>
      <div className="rv-card-head">
        <h3>{title}</h3><span className="mono muted sm">padding</span>
        <Seg size="sm" value={pad} onChange={setPad} options={[{ value: '30', label: '±30 s' }, { value: '120', label: '±120 s' }, { value: '300', label: '±300 s' }]} testid="padding-seg" />
        <ResolutionNote tr={d.context} testid="context-resolution" />
        <span className="grow" />
        <Button ref={ocRef} variant={open ? 'primary' : 'default'} icon="list" aria-expanded={open} onClick={() => setPop(open ? null : 'other-channels')} testid="other-channels-button">Other channels</Button>
        {canEdit && <Button icon="pencil" onClick={() => editInExplore(d)} testid="edit-span-button">Edit span in Explore</Button>}
      </div>
      <div className="rv-plot">
        <Trace t={ctx.t} values={ctx.v} xDomain={[ctx.t0, ctx.t1]} timeUnit="none" height={170} crosshair unitLabel={false}
          bands={[{ start_s: ctx.bandStart, end_s: ctx.bandEnd, kind: 'detected', label: bandLabel }]} testid="context-trace" />
        <TimeTicks t0={ctx.t0} t1={ctx.t1} testid="context-ticks" />
      </div>
      <OtherChannelsPopover d={d} pad={+pad} open={open} onClose={() => setPop(null)} anchorRef={ocRef} />
    </section>
  )
}

export function editInExplore(d: ItemDetail) {
  navigate(`explore/span-edit/${d.entry.detectionId ?? d.entry.id}?from=review&queue=${d.entry.queueId}&item=${d.entry.id}`)
}

function useQueryPop() { return useQueryState<string>('pop', '') }

/* ---------------- other channels (frame 1b) ---------------- */
const OC_PAGE = 6
const OC_PX = 480   // the popover's plots are ~400 css px wide
function OtherChannelsPopover({ d, pad, open, onClose, anchorRef }: { d: ItemDetail; pad: number; open: boolean; onClose: () => void; anchorRef: React.RefObject<HTMLButtonElement | null> }) {
  // fetched over the padding shown, at the popover's width — each row is a trace WITH its axis
  const rows = useSourced(() => open ? getOtherChannels(d.entry.queueId, d.entry.id, { px: OC_PX, padS: pad }) : Promise.resolve({ data: [], source: 'demo' as const }), [open, d.entry.id, pad])
  const all = rows.data ?? []
  const curIdx = Math.max(0, all.findIndex(r => r.current))
  const [page, setPage] = useState(1)
  useEffect(() => { setPage(Math.floor(curIdx / OC_PAGE) + 1) }, [curIdx, d.entry.id])
  const band = itemBand(d)
  const ctx = sliceContext(d.context, band, pad)
  // every row sliced by TIME to the same window, so the band (in seconds) sits on the same axis as the trace
  const sliced = useMemo(() => all.map(r => sliceContext(r.trace, band, pad)), [all, band.start_s, band.end_s, pad])
  const shown = all.slice((page - 1) * OC_PAGE, page * OC_PAGE)
  // each channel on its own measured scale; the bar places each channel's peak over this window on one shared
  // scale for every channel of the recording, so a quiet channel does not look like a loud one
  const chanScale = useMemo(() => referenceScale(sliced.map(s => baselinePeak(s.v))), [sliced])
  const a = d.artifact
  return (
    <Popover open={open} onClose={onClose} anchorRef={anchorRef} placement="bottom-end" width={590} className="rv-pop" testid="other-channels-popover"
      title={<><span>Other channels</span><span className="sub">same {(ctx.t0 / 3600).toFixed(3)} → {(ctx.t1 / 3600).toFixed(3)} h</span><span className="grow" /><IconButton icon="x" label="close other channels" onClick={onClose} testid="other-channels-close" /></>}>
      {rows.error && <div className="error-card">Other channels failed to load: {rows.error.message}</div>}
      {!rows.data && !rows.error && <div className="skeleton" style={{ height: 230 }} />}
      {rows.data && (
        <div className="rv-oc" data-testid="other-channels-rows">
          {shown.map((r, k) => {
            const s = sliced[(page - 1) * OC_PAGE + k] ?? sliceContext(r.trace, band, pad)
            return (
            <div key={r.channel} className={cx('rv-oc-row', r.current && 'current')} data-testid={`oc-row-${r.channel}`}>
              <span className="mono ch">{r.channel}</span>
              <span className="rv-oc-plot"><MiniTrace t={s.t} values={s.v} width="100%" height={30} ground="none" zeroLine={false} band={[s.bandStart, s.bandEnd]} stroke={r.current ? 'var(--text)' : 'var(--muted)'} strokeWidth={r.current ? 1.3 : 0.9} />
                <ReferenceBar scale={chanScale} peak={baselinePeak(s.v)} height={30} what={r.channel} testid={`oc-reference-${r.channel}`} /></span>
              <span className="mono r">{r.current ? 'this channel' : r.r != null ? `r ${r.r.toFixed(2)}` : 'r not computed'}</span>
            </div>
            )
          })}
          <div className="row between" style={{ marginTop: 4 }}>
            <span className="mono muted sm" title={referenceWords(chanScale)}>each channel on its own scale · bar: its peak across channels · r = coherence in the span</span>
            <Pager page={page} pageCount={Math.ceil(all.length / OC_PAGE)} onPage={setPage} format="range" total={all.length} pageSize={OC_PAGE} testid="other-channels-pager" />
          </div>
        </div>
      )}
      <div className="rv-oc-foot" data-testid="other-channels-artifact">
        <div className="row"><span className="mono muted">artifact likelihood</span>
          {a.level != null && a.p != null
            ? <Chip size="sm" tone={a.level === 'low' ? 'green' : a.level === 'medium' ? 'amber' : 'red'}>{a.level} · {a.p.toFixed(2)}</Chip>
            : <span className="muted" data-testid="artifact-not-computed">not computed</span>}
          <InfoTip title="Artifact likelihood">Combines cross-channel coherence, clipping, step changes and electrode flags. Artifacts are noted and kept out of training data. Never blinded.</InfoTip>
          <span className="grow" /><span className="mono muted sm">not blinded in any queue</span></div>
        <div className="mono sm rv-factors"><span className="muted">coherence in span</span> <b>{a.coherence != null ? a.coherence.toFixed(2) : '—'}</b> (flag ≥ 0.5) <span className="muted">clipping</span> <b>{a.clipping}</b> <span className="muted">step change</span> <b>{a.stepChange}</b> <span className="muted">electrode flag</span> <b>{a.electrodeFlag}</b></div>
        <Button variant="link" iconRight="arrow-right" onClick={() => navigate(`explore/cross-channel/4?h=${(ctx.t0 / 3600).toFixed(3)}-${(ctx.t1 / 3600).toFixed(3)}`)} testid="open-all-channels">Open all channels in Explore</Button>
      </div>
    </Popover>
  )
}

/* ---------------- shape and nearest families ---------------- */
/** Source resolution (Q24, default ON): when the item's recording is a decimated excerpt of a higher-resolution
 *  one, draw the Shape card from the parent. Persisted across items; a reviewer who turns it off for one queue
 *  keeps it off. */
export function useSourceResolution() { return useDemoState<boolean>('review.sourceResolution', () => true) }

/** Which recording a shape was drawn from, in words: the card has to say it, because "this event looks smooth"
 *  means something different at 1 Hz and at 10 Hz. */
export function drawnFrom(tr: TimeTrace, names: DatasetNames = {}): string {
  const s = tr.source
  if (!s) return tr.reason ?? 'nothing drawn'
  const rate = `${s.fs % 1 === 0 ? s.fs : s.fs.toFixed(2)} Hz`
  const samples = `${fmtInt(tr.n_source)} sample${tr.n_source === 1 ? '' : 's'}`
  return s.kind === 'parent'
    ? `${datasetName(names, s.source_file ?? s.label)} ${s.channel} · ${rate} · ${samples} · the ${s.decimation}:1 source of this recording`
    : `${datasetName(names, s.source_file ?? s.label)} ${s.channel} · ${rate} · ${samples}`
}

export function ShapeCard({ d, family, blind, rows }: { d: ItemDetail; family: NearestFamily | null; blind: boolean; rows: QueueRow[] }) {
  const names = useDatasetNames()
  const showMedoid = !blind && family
  const [wantSource, setWantSource] = useSourceResolution()
  // the parent when one is registered and the toggle is on; the item's own recording otherwise. A missing
  // parent is a DISABLED toggle carrying the bridge's reason, never a present-and-inert one.
  const fromSource = wantSource && !!d.shapeSource && d.shapeSource.v.length > 0
  const drawn = fromSource ? (d.shapeSource as TimeTrace) : d.shape
  // the candidate and the medoid each centred on their own baseline, on a domain measured from both (the one
  // rule) — so neither is ever cut off, and the medoid no longer drags the candidate's shape flat. Centring keeps
  // every point at its own time: the values shift, the axis does not.
  const shape = useMemo(() => centreTrace(drawable(drawn.v)), [drawn])
  const medoid = useMemo(() => showMedoid ? centreTrace(d.medoids[family.id] ?? []) : [], [showMedoid, family, d.medoids])
  const peak = baselinePeak(drawn.v)
  // the queue's shared scale: every candidate in it, by the same measure, computed once per queue read
  const scale = useMemo(() => referenceScale([...rows.map(r => baselinePeak(r.thumb)), peak]), [rows, peak])
  const what = d.entry.unit === 'window' ? 'this window' : 'this candidate'
  const staircase = !drawn.decimated && drawn.n_source > 0 && drawn.n_source <= 200
  return (
    <section className="rv-card" data-testid="shape-card" data-source={drawn.source?.kind ?? 'none'} data-source-available={d.shapeSource ? '1' : '0'}>
      <div className="rv-card-head">
        <h3>{showMedoid ? `Shape vs ${family.id} medoid · mV` : 'Shape · mV'}</h3>
        <InfoTip title="Shape">Drawn in mV on its own measured scale, centred on its own baseline, never normalised — and never smoothed: every vertex is a sample the recording holds, so a short candidate at 1 Hz is a staircase, which is its real resolution.{showMedoid ? ' The medoid is drawn in its own panel beneath, on its own samples: the bridge serves a medoid with no time axis, and stretching it across the candidate would draw a duration it does not have.' : ''} The bar at the right is {referenceWords(scale)}: the mark is where {what} sits against every candidate in this queue.</InfoTip>
        <span className="mono muted sm" data-testid="shape-peak">peak {fmtRef(peak)} mV</span>
        <span className="grow" />
        <Legend items={showMedoid ? [{ label: d.entry.unit === 'window' ? 'this window' : 'candidate', colour: 'var(--blue)', shape: 'line' }, { label: `${family.id} medoid`, colour: family.colour, shape: 'line' }]
          : [{ label: d.entry.unit === 'window' ? 'this window' : 'candidate', colour: 'var(--text)', shape: 'line' }]} />
      </div>
      <div className="rv-card-head" data-testid="shape-source-row">
        <span className="mono muted sm" data-testid="shape-drawn-from" title={drawn.capped ? `capped at ${drawn.px} px: fewer points than samples` : undefined}>drawn from {drawnFrom(drawn, names)}{drawn.capped ? <b className="rv-amber"> · capped</b> : null}</span>
        <span className="grow" />
        {d.shapeSource
          ? <Toggle size="sm" checked={fromSource} onChange={setWantSource} label={<span className="mono sm">source resolution</span>} ariaLabel="draw the shape from the higher-resolution source recording" testid="shape-source-toggle" />
          : <Toggle size="sm" checked={false} onChange={() => {}} disabled disabledReason={d.shapeSourceReason ?? 'no higher-resolution source is registered for this recording'} label={<span className="mono sm">source resolution</span>} ariaLabel="source resolution unavailable" testid="shape-source-toggle" />}
      </div>
      <div className="rv-plot">
        <div className="rv-shape-row">
          <Trace t={drawn.t} values={shape} xDomain={[drawn.t0_s, drawn.t1_s]} timeUnit="s" height={122} stroke={showMedoid ? 'var(--blue)' : 'var(--text)'} strokeWidth={2} sampleDots={staircase}
            zeroLine={false} testid="shape-trace" style={{ flex: 1, minWidth: 0 }} />
          <span style={{ paddingTop: 8 }}><ReferenceBar scale={scale} peak={peak} height={92} what={what} testid="shape-reference" /></span>
        </div>
        {/* fixup-h (`07` R17): the medoid used to be overlaid INDEX-STRETCHED across the candidate's duration — a
            medoid of any length redrawn as if it lasted exactly as long as the candidate. It has no time axis of
            its own (the bridge serves bare values), so it is drawn beside the candidate as what it is: its own
            samples, evenly spaced, on its own measured y with a scale bar. The comparison is of SHAPE, and the
            card says the durations are not comparable. */}
        {showMedoid && medoid.length > 1 && (() => {
          const dom = measuredDomain(medoid) ?? [-1, 1]
          return (
            <div className="rv-shape-row" style={{ marginTop: 6, alignItems: 'center' }} data-testid="shape-medoid">
              <MiniTrace values={medoid} yDomain={dom} width="100%" height={56} stroke={family.colour} strokeWidth={2} ground="white" zeroLine={false} style={{ flex: 1, minWidth: 0 }} title={`${family.id} medoid`} />
              <ScaleBar domain={dom} height={56} unit="mV" testid="shape-medoid-scale" />
              <span className="mono muted sm" style={{ maxWidth: 190 }}>{family.id} medoid · {medoid.length} samples on its own y · no time axis is served for it, so it is not stretched onto the candidate</span>
            </div>
          )
        })()}
      </div>
    </section>
  )
}

function DistanceBar({ d, colour }: { d: number; colour: string }) {
  return <span className="rv-dbar" aria-label={`distance ${d.toFixed(2)}`}><i className="fill" style={{ width: `${d * 100}%`, background: colour }} /><i className="knob" style={{ left: `${d * 100}%`, background: colour }} /></span>
}

export function NearestFamiliesCard({ d, overlay, setOverlay }: { d: ItemDetail; overlay: string; setOverlay: (id: string) => void }) {
  const first = d.nearest[0]
  // `nearest` is empty when nothing has computed family affinity for this item.
  // That is NOT "no family is near" — it is "nobody looked" — and saying the
  // first is what the bridge's `nearestComputed` flag distinguishes. Rendering
  // an empty list as a blank card, or dereferencing `nearest[0]`, is how this
  // card took the whole workspace down on every live item.
  if (!first) {
    return (
      <section className="rv-card" data-testid="nearest-families">
        <div className="rv-card-head"><h3>Nearest families</h3></div>
        <p className="muted sm" data-testid="nearest-not-computed">
          {d.nearestComputed
            ? 'No family is within range of this candidate.'
            : 'Family affinity is not computed for this queue yet — no distance is being withheld and none is being guessed at.'}
        </p>
      </section>
    )
  }
  return (
    <section className="rv-card" data-testid="nearest-families">
      <div className="rv-card-head">
        <h3>Nearest families</h3>
        <InfoTip title="Nearest families">Distance is shape only, 0 → 1; a longer bar is farther. Low distance is not a verdict. Click a family to overlay its medoid.</InfoTip>
        <span className="grow" /><span className="mono muted sm">shape distance, 0 → 1</span>
      </div>
      <div className="rv-fams">
        {d.nearest.map(f => (
          <button key={f.id} type="button" className={cx('rv-fam', overlay === f.id && 'on')} onClick={() => setOverlay(f.id)} aria-pressed={overlay === f.id} data-testid={`family-row-${f.id}`}>
            <MiniTrace values={d.medoids[f.id] ?? []} width={58} height={30} stroke={f.colour} strokeWidth={1.5} ground="white" zeroLine={false} />
            <span className="id"><b className="mono">{f.id}</b><span className="mono muted">{f.name}</span></span>
            <span className="mono muted mem">{f.members != null ? `${fmtInt(f.members)} members` : 'members n/a'}</span>
            <DistanceBar d={f.d} colour={f.colour} />
            <b className="mono dv">d {f.d.toFixed(2)}</b>
          </button>
        ))}
      </div>
      <Button variant="link" iconRight="arrow-right" onClick={() => navigate(`library/family/${first.id}`)} testid="open-family-library">Open {first.id} in Library</Button>
    </section>
  )
}

/* ---------------- verdict row ---------------- */
export interface VerdictDef { v: Verdict | 'skip'; key: string; label: string; caption?: string }
export const VERDICT_DEFS: VerdictDef[] = [
  { v: 'seed', key: 'S', label: 'seed', caption: 'promotes to Library' },
  { v: 'interesting', key: 'I', label: 'interesting' },
  { v: 'not_interesting', key: 'N', label: 'not interesting' },
  { v: 'artifact', key: 'A', label: 'artifact', caption: 'kept out of training' },
  { v: 'unsure', key: 'U', label: 'unsure' },
  { v: 'skip', key: 'Space', label: 'skip', caption: 'no write' },
]

export interface PreviousLine { text: string; go?: () => void; prefix?: string }

export function VerdictCard({ selected, flash, binary, onVerdict, onSkip, previous, undo, undoCaption = 'undo', children, testid = 'verdict-card' }: {
  selected: Verdict | null; flash: Verdict | null; binary: boolean; onVerdict: (v: Verdict) => void; onSkip: () => void
  previous: PreviousLine[]; undo: { can: boolean; run: () => void }; undoCaption?: string; children?: ReactNode; testid?: string
}) {
  const [pi, setPi] = useState(0)
  useEffect(() => { setPi(0) }, [previous.length, previous[0]?.text])
  const p = previous[Math.min(pi, previous.length - 1)]
  const defs = VERDICT_DEFS.filter(x => !binary || ['interesting', 'not_interesting', 'skip'].includes(x.v))
  return (
    <section className="rv-card" data-testid={testid}>
      <div className="rv-card-head">
        <h3>Verdict</h3>
        <IconButton icon="chevron-left" label="earlier verdict" bordered disabled={pi >= previous.length - 1} disabledReason="no earlier verdict this session" onClick={() => setPi(i => i + 1)} testid="previous-older" />
        <IconButton icon="chevron-right" label="later verdict" bordered disabled={pi === 0} disabledReason="this is the latest verdict" onClick={() => setPi(i => Math.max(0, i - 1))} testid="previous-newer" />
        {p ? <button type="button" className="rv-prev mono" onClick={p.go} disabled={!p.go} title={p.go ? 'open this item' : undefined} data-testid="previous-line"><span className="muted">{p.prefix ?? 'previous'}</span> {p.text}</button>
          : <span className="mono muted sm" data-testid="previous-line">no verdict yet in this queue</span>}
        <span className="grow" />
        <DisabledReason disabled={!undo.can} reason="nothing to undo in this queue this session">
          <button type="button" className="rv-undo" disabled={!undo.can} onClick={undo.run} title={undo.can ? 'undo the last write (Ctrl Z)' : undefined} data-testid="undo-button"><Kbd size="sm">Ctrl Z</Kbd><span className="mono muted">{undoCaption}</span></button>
        </DisabledReason>
      </div>
      <div className="rv-vcards" style={{ gridTemplateColumns: `repeat(${defs.length}, minmax(0, 1fr))` }}>
        {defs.map(x => {
          const on = x.v !== 'skip' && (selected === x.v || flash === x.v)
          return (
            <button key={x.v} type="button" className={cx('rv-vcard', on && 'on', x.v === 'seed' && 'seed')} aria-pressed={on} data-testid={`verdict-${x.v}`}
              onClick={e => { (e.currentTarget as HTMLButtonElement).blur(); if (x.v === 'skip') onSkip(); else onVerdict(x.v) }}>
              <Kbd size="sm">{x.key}</Kbd>
              <span className="txt"><span className="lbl">{x.label}</span>{x.caption && <span className={cx('cap mono', x.v === 'seed' && 'green')}>{x.caption}</span>}</span>
            </button>
          )
        })}
      </div>
      {binary && <div className="mono muted sm" style={{ marginTop: 8 }}>this queue takes binary verdicts and classes (Settings › Review queues)</div>}
      {children}
    </section>
  )
}

/* ---------------- annotate ---------------- */
// the vocabulary's own terms use `_` as well as `-` (`sharp_trough`, `type_specimen`)
const TAG_RE = /^[a-z0-9]+([-_][a-z0-9]+)*$/
export function AnnotateCard({ draft, setDraft, className, onClass }: { draft: Draft; setDraft: (d: Draft) => void; className?: string; onClass: (key: string) => void }) {
  const [adding, setAdding] = useState(false)
  const [tag, setTag] = useState('')
  /* The live `tag_vocabulary`, not the three fixture words this offered before
   * (`spike-train`, `regular`, `decaying` - none of them a term the database
   * defines). A tag outside the vocabulary is a 400 that refuses the whole
   * verdict, so the card refuses it here, where it costs nothing (fixup-a
   * item 9). */
  const vocab = useTagVocabulary()
  const known = useMemo(() => new Set((vocab.terms ?? []).map(t => t.value)), [vocab.terms])
  const suggestions = useMemo(
    () => [...new Set([...(vocab.terms ?? []).map(t => t.value), ...draft.tags])].sort(),
    [vocab.terms, draft.tags])
  const tagErr = !tag ? null
    : tag.length > 32 ? 'at most 32 characters'
      : !TAG_RE.test(tag) ? 'tags are lowercase words, digits, - and _'
        : draft.tags.includes(tag) ? 'already tagged'
          : vocab.terms && !known.has(tag) ? 'not in the tag vocabulary \u2014 add it in Settings \u203a Vocabulary'
            : vocab.error ? `the tag vocabulary could not be read (${vocab.error})`
              : null
  const addTag = () => { if (!tag || tagErr) return; setDraft({ ...draft, tags: [...draft.tags, tag] }); setTag(''); setAdding(false) }
  return (
    <section className="rv-card" data-testid="annotate-card">
      <div className="rv-card-head">
        <h3>Annotate</h3><span className="mono muted sm">optional</span><span className="grow" />
        <InfoTip title="Classes">A class implies interesting, unless the class is non-informative (electrode artifact implies artifact). Classes are bound to number keys in Settings › Vocabulary.</InfoTip>
        <span className="mono muted sm">a class implies interesting, unless the class is non-informative</span>
      </div>
      <div className="rv-ann-row"><span className="mono muted lbl">class</span>
        {VOCABULARY.classes.map(c => (
          <button key={c.key} type="button" className={cx('rv-class', className === c.name && 'on', !c.informative && 'noninf')} aria-pressed={className === c.name} data-testid={`class-${c.key}`}
            onClick={e => { (e.currentTarget as HTMLButtonElement).blur(); onClass(c.key) }}><Kbd size="sm">{c.key}</Kbd>{c.name}</button>
        ))}
      </div>
      <div className="rv-ann-row"><span className="mono muted lbl">tags</span>
        {suggestions.map(t => {
          const on = draft.tags.includes(t)
          return <button key={t} type="button" className={cx('rv-tag', on && 'on')} aria-pressed={on} onClick={() => setDraft({ ...draft, tags: on ? draft.tags.filter(x => x !== t) : [...draft.tags, t] })} data-testid={`tag-${t}`}>{t}</button>
        })}
        {adding
          ? <span className="rv-tag-input">
              <TextField value={tag} onChange={setTag} placeholder="new-tag" width={130} size="sm" invalid={!!tagErr} autoFocus onEnter={addTag} testid="tag-input" ariaLabel="new tag" />
              <Button size="sm" onClick={addTag} disabled={!tag || !!tagErr} disabledReason={tagErr ?? 'type a tag first'} testid="tag-add">Add</Button>
              <IconButton icon="x" label="cancel tag" onClick={() => { setAdding(false); setTag('') }} />
              {tagErr && <span className="mono sm rv-red" data-testid="tag-error">{tagErr}</span>}
            </span>
          : <button type="button" className="rv-tag add" onClick={() => setAdding(true)} data-testid="tag-add-open">+ tag</button>}
        <span className="k-divider-v" />
        <span className="mono muted lbl">note</span>
        <span className="rv-note">
          <TextField value={draft.note} onChange={v => setDraft({ ...draft, note: v.slice(0, 500) })} placeholder="Add a note…" block size="sm" testid="note-input" ariaLabel="note" />
          {draft.note.length > 400 && <span className={cx('mono sm', draft.note.length >= 500 ? 'rv-red' : 'muted')}>{draft.note.length} / 500</span>}
        </span>
      </div>
    </section>
  )
}

/* ---------------- promotion panel (frame 6) ---------------- */
export function PromotionPanel({ d, rec, onUndo, onConfirm, confirmRef }: { d: ItemDetail; rec: VerdictRecord; onUndo: () => void; onConfirm: (family: string | null, familyName?: string) => void; confirmRef: { current: (() => void) | null } }) {
  const nearest = d.nearest[0] ?? null
  const near = !!nearest && nearest.d <= 0.30
  const [choice, setChoice] = useState<'nearest' | 'new' | 'none'>(near ? 'nearest' : 'none')
  const [name, setName] = useState('')
  const nameErr = choice !== 'new' ? null : !name.trim() ? 'name the new family' : name.trim().length < 2 || name.trim().length > 40 ? 'a family name is 2–40 characters' : null
  const confirm = () => { if (nameErr) return; onConfirm(choice === 'nearest' ? (nearest?.id ?? null) : choice === 'new' ? 'new' : null, choice === 'new' ? name.trim() : undefined) }
  confirmRef.current = confirm   // Enter (review/keys.ts) confirms with the current family choice
  const opt = (v: typeof choice, label: ReactNode, testid: string) => (
    <button type="button" role="radio" aria-checked={choice === v} className={cx('rv-radio', choice === v && 'on')} onClick={() => setChoice(v)} data-testid={testid}><i />{label}</button>
  )
  return (
    <section className="rv-card rv-promo" data-testid="promotion-panel">
      <div className="rv-card-head">
        <Icon name="library" size={15} /><h3>Promoted to Library</h3><Chip size="sm" tone="green" testid="promo-entry">{rec.exemplarId ?? 'no Library entry named'}</Chip>
        <span className="grow" /><span className="mono muted sm">seed verdict · {relTimeShort(rec.at)}</span>
      </div>
      <div className="rv-promo-body">
        <div className="row wrap" role="radiogroup" aria-label="family"><span className="mono muted sm">family</span>
          {nearest && opt('nearest', <>{nearest.id} {nearest.name} · nearest, d {nearest.d.toFixed(2)}{near ? '' : ' · above 0.30'}</>, 'promo-family-nearest')}
          {opt('new', 'new family', 'promo-family-new')}
          {opt('none', 'no family yet', 'promo-family-none')}
        </div>
        {choice === 'new' && <div className="row"><TextField value={name} onChange={setName} placeholder="F-12 · name" width={220} size="sm" invalid={!!nameErr} testid="promo-family-name" ariaLabel="family name" autoFocus />{nameErr && <span className="mono sm rv-red">{nameErr}</span>}</div>}
        <div className="mono sm muted row"><Icon name="link" size={13} /> keeps span, recording, channel, content hash and the run's recipe hash{rec.entryCreated === false ? ' · this shape was already in the Library, so it joined that entry' : ''}</div>
        <Callout tone="amber" icon="pause">auto-advance paused until you confirm · Enter confirms and moves on</Callout>
        <div className="row wrap" style={{ gap: 12 }}><PromotedEntryLinks rec={rec} /></div>
        <div className="row">
          <Button icon="undo" onClick={onUndo} testid="promo-undo">Undo promotion</Button><Kbd size="sm">Ctrl Z</Kbd>
          <span className="grow" />
          <Button variant="primary" icon="check" onClick={confirm} disabled={!!nameErr} disabledReason={nameErr ?? undefined} testid="promo-confirm">Confirm and next</Button>
        </div>
      </div>
    </section>
  )
}
/** fixup-y: the two ways on from a promotion, both about the entry that was WRITTEN. *Open in Library* opens
 *  the family that holds it in the current grouping, with its member selected — it opened the panel's own
 *  family choice with a minted exemplar id no page knew. A freshly written entry is in no family until the
 *  next regroup, and the button says so rather than opening the Atlas. *Seed search in Discovery →* (§8.5,
 *  wiring `05-review.md` §12 item 5) opens the Seed page with this entry as the seed. */
function PromotedEntryLinks({ rec }: { rec: VerdictRecord }) {
  const entryId = rec.entryId ?? null
  const found = useSourced(() => entryId == null ? Promise.resolve({ data: null, source: 'live' as const }) : getSeedPage({ source: 'library', entry: entryId, limit: 1 }), [entryId])
  const family = found.data?.seeds[0]?.family ?? null
  const noEntry = entryId == null ? 'the bridge named no Library entry for this promotion' : null
  const noFamily = found.loading ? 'reading which family holds the entry…' : found.error ? `could not read the entry: ${found.error.message}`
    : !family ? `entry ${entryId} is in no family of the current grouping yet — the next regroup places it` : null
  return (
    <>
      <Button variant="link" disabled={!!(noEntry ?? noFamily)} disabledReason={noEntry ?? noFamily ?? undefined}
        onClick={() => navigate(`library/family/${encodeURIComponent(family!)}${rec.memberId != null ? `?member=m-${rec.memberId}` : ''}`)} testid="promo-open-library">Open in Library</Button>
      <Button variant="link" iconRight="arrow-right" disabled={!!noEntry} disabledReason={noEntry ?? undefined}
        onClick={() => navigate(`discovery/seed?entry=${entryId}`)} testid="promo-seed-search">Seed search in Discovery</Button>
    </>
  )
}
function relTimeShort(at: number) { const s = Math.round((Date.now() - at) / 1000); return s < 5 ? 'just now' : s < 60 ? `${s} s ago` : `${Math.round(s / 60)} min ago` }

/* ---------------- evidence rail (frame 4) ---------------- */
function EvSection({ id, icon, title, aside, children, masked }: { id: string; icon: IconName; title: string; aside?: ReactNode; children: ReactNode; masked?: boolean }) {
  return (
    <div className="rv-ev" id={`ev-${id}`} data-testid={`evidence-${id}`}>
      <div className="rv-ev-head"><Icon name={masked ? 'eye-off' : icon} size={14} /><h5>{title}</h5><span className="grow" />{masked ? <span className="mono sm rv-purple">hidden until verdict</span> : aside}</div>
      {!masked && children}
    </div>
  )
}
const KV = ({ k, children }: { k: ReactNode; children: ReactNode }) => <div className="rv-kv"><span className="k mono">{k}</span><span className="v mono">{children}</span></div>

export function EvidenceRail({ d, blind, judged, historyVerdicts }: { d: ItemDetail; blind: boolean; judged: boolean; historyVerdicts: string }) {
  const ev = d.evidence, a = d.artifact, f = d.nearest[0] ?? null
  const mask = blind && !judged
  return (
    <div data-testid="evidence-sections">
      <EvSection id="origin" icon="branch" title="Origin">
        {ev.origin.runId && <KV k="run"><Chip size="sm" tone="blue">{ev.origin.runKind}</Chip> <b>{ev.origin.runId}</b></KV>}
        {!ev.origin.runId && <KV k="source"><b>{ev.origin.runKind}</b></KV>}
        {ev.origin.windowSet && <KV k="window set">{ev.origin.windowSet}</KV>}
        {ev.origin.block && <KV k="block">{ev.origin.block}</KV>}
        {ev.origin.sample && <KV k="sample">stratified · {ev.origin.sample}</KV>}
        {ev.origin.template && !mask && <KV k={d.entry.unit === 'window' ? 'candidate' : 'template'}>{d.queue.model ?? ev.origin.template}</KV>}
        {ev.origin.template && mask && d.entry.unit === 'window' && <KV k="candidate"><span className="rv-purple">hidden until verdict</span></KV>}
        {ev.origin.stages.length > 0 && <div className="rv-stages">{ev.origin.stages.map((s, i) => <span key={s.label} className="row" style={{ gap: 4 }}>{i > 0 && <Icon name="chevron-right" size={11} />}<span className="rv-stage mono" title={s.full}>{s.label}</span></span>)}</div>}
        {ev.origin.recipeHash && <KV k="recipe hash">{ev.origin.recipeHash}</KV>}
        <KV k="ran">{ev.origin.ran} · {ev.origin.by}</KV>
        <KV k="scope">{ev.origin.scope}</KV>
        {ev.origin.runId && <Button variant="link" iconRight="arrow-right" onClick={() => navigate(`discovery/runs?run=${ev.origin.runId}`)} testid="open-run-discovery">Open run in Discovery</Button>}
      </EvSection>
      {ev.detection && (
        <EvSection id="detection" icon="target" title="Detection" masked={mask}>
          <KV k="score"><b>{ev.detection.score != null ? ev.detection.score.toFixed(2) : 'n/a · seed search ranks by distance'}</b></KV>
          <KV k="threshold">{ev.detection.threshold != null ? `${ev.detection.threshold.toFixed(2)} · recommended ${ev.detection.recommended?.toFixed(2)}` : 'n/a'}</KV>
          <KV k="rank">{ev.detection.rank ?? 'n/a'}</KV>
          <KV k="null expects">{ev.detection.nullExpects ?? 'no null run for this search'}</KV>
          <KV k="samples">{ev.detection.samples} · {ev.detection.fs}</KV>
        </EvSection>
      )}
      {d.entry.modelCall && (
        <EvSection id="model" icon="flask" title="Model call" masked={mask}>
          <KV k="model">{d.queue.model}</KV>
          <KV k="call"><b>{d.entry.modelCall.className} · p {d.entry.modelCall.p.toFixed(2)}</b></KV>
        </EvSection>
      )}
      <EvSection id="also" icon="layers" title="Also found by" masked={mask}>
        {ev.alsoFoundBy.runs.map(r => <KV key={r.run} k={r.run}><Chip size="sm" tone="purple">{r.badge}</Chip> {r.match}{r.match.startsWith('match d') && <InfoTip title="Seed-search distance">Seed-search distance, not the 0 → 1 shape distance.</InfoTip>}</KV>)}
        {ev.alsoFoundBy.runs.length === 0 && <KV k="other runs">none</KV>}
        <KV k="human annotations">{ev.alsoFoundBy.human}</KV>
        <KV k="prior adjudication">{ev.alsoFoundBy.prior}</KV>
      </EvSection>
      <EvSection id="family" icon="library" title="Family" aside={<span className="mono muted sm">nearest by shape, not a verdict</span>} masked={mask}>
        {/* No nearest family means nothing computed affinity for this item, which
            is not the same as "nothing is near". Rendering the absence in words
            keeps the rail honest; dereferencing `f` here took the whole
            workspace down on every live item that had an evidence rail open. */}
        {f ? (
          <div className="rv-ev-fam">
            <MiniTrace values={d.medoids[f.id] ?? []} width={70} height={34} stroke={f.colour} strokeWidth={1.5} ground="white" zeroLine={false} />
            <span><b className="mono">{f.id} · {f.name}</b><br /><span className="mono muted sm">d {f.d.toFixed(2)} · {f.members != null ? `${f.members} members` : 'members n/a'}</span></span>
          </div>
        ) : (
          <KV k="nearest">{d.nearestComputed ? 'no family within range' : 'not computed for this queue'}</KV>
        )}
      </EvSection>
      <EvSection id="artifact" icon="alert-triangle" title="Artifact likelihood" aside={<span className="mono muted sm">not blinded</span>}>
        {/* `level`/`p`/`coherence` are null when nothing computed artifact factors.
            Saying "not computed" is the honest render; a 0.00 beside a real
            waveform would be a finding that is not there. */}
        <KV k="likelihood">{a.level != null && a.p != null
          ? <Chip size="sm" tone={a.level === 'low' ? 'green' : a.level === 'medium' ? 'amber' : 'red'}>{a.level} · {a.p.toFixed(2)}</Chip>
          : <span className="muted" data-testid="artifact-not-computed">not computed</span>}</KV>
        <KV k="cross-channel coherence">{a.coherence != null ? `${a.coherence.toFixed(2)} · flag ≥ 0.5` : 'not computed'}</KV>
        <KV k="clipping · step change">{a.clipping} · {a.stepChange}</KV>
        <KV k="electrode flag">{a.electrodeFlag}</KV>
      </EvSection>
      <EvSection id="history" icon="clock" title="History">
        <KV k="span revisions">{ev.history.revisions}</KV>
        <KV k="verdicts">{historyVerdicts}</KV>
        <KV k="in queues">{ev.history.queues}</KV>
      </EvSection>
      <div className="rv-write-target mono" data-testid="write-target"><Icon name="database" size={13} />{ev.writeTarget}{blind ? ' (blind)' : ''}</div>
    </div>
  )
}
