/* Tier 2 — SPAN 276.4 – 278.4 h · 2.0 h (frame explore-2): the viewport. The envelope is
   re-fetched per viewport (see useViewport); while a fetch is in flight the previous path is kept
   under a translate/scale transform. Pan = pointer drag, zoom = wheel about the cursor or the
   −/+/fit buttons, ‹ N / M › walks the motif list. Tinted bands + caps mark detections and annotations by
   verdict (span-plot, 2026-10-18: six kinds, each its own colour and each a switch in the legend — bandModel.ts),
   and the selected motif (amber). The span's edges are typeable fields (seconds, three decimals). Real mV. */
import { useEffect, useRef, useState } from 'react'
import type { Channel } from '../api'
import { EnvelopePath, TimeGrid } from '../charts/primitives'
import { BAND_KINDS, bandGeometry, parseEdge, stepEdge, type SpanKind, type ToggleKind, type Toggles } from './bandModel'
import { Icon, InfoTip, Popover } from '../kit'
import { LegendRow } from './bits'
import { makeX, makeY } from '../charts/scale'
import { fmtDuration } from '../state'
import { ErrorCard } from './ErrorCard'
import { MvLabels } from './MvLabels'
import { envelopeOk, fmtInt, fmtMs, MALFORMED_WINDOW, MIN_SPAN_S, mvDigits, viewportHourTicks, vRange, type Motif } from './util'
import type { Viewport } from './useViewport'

const H = 150, TOP = 18, AXIS_H = 20
/** Past this CSS scale the kept path is a stretched/squashed sliver, not a preview: show the skeleton instead (critique r1). */
const MAX_STRETCH = 8
/** Left gutter kept clear of the y labels ("−201.60 mV" at x=4, 10 px mono ≈ 6.2 px/glyph) so the motif label
 *  never overprints them; widens with the labels' own printed length — integer digits too, now that a
 *  baseline reads −3670 mV rather than −3.67 — never below the critique's 64 px. */
const labelGutter = (lo: number, hi: number) => {
  const d = mvDigits(lo, hi)
  const chars = Math.max(Math.abs(lo).toFixed(d).length, Math.abs(hi).toFixed(d).length) + 4   // sign, space, "mV"
  return Math.max(64, 12 + chars * 6.2)
}

/** A drawn band. `kind` is what it draws as (`selected` for the open motif); `toggle` is the legend kind that
 *  switches it — an annotation's verdict, or `detected` — so the selected motif still knows what it is. */
export interface Band { start_s: number; end_s: number; kind: SpanKind; toggle: ToggleKind; id: string; title: string; motif: Motif; colour?: string; capOnly?: boolean }

const KIND_DEF = new Map(BAND_KINDS.map(k => [k.key, k]))
const FILL = (k: SpanKind) => (k === 'selected' ? 'var(--band-selected)' : KIND_DEF.get(k)?.fill ?? 'rgba(107,114,128,0.12)')
const CAP = (k: SpanKind) => (k === 'selected' ? 'var(--amber)' : KIND_DEF.get(k)?.cap ?? 'var(--muted-2)')
/** Per-span full-height translucent fill + a cap above (spec 5.2). `colour` = colour by run; `capOnly` = the
 *  detection already has a verdict (frame 2a legend). Keeps testid span-bands (smoke counts its rects); each
 *  rect carries its kind (`data-kind`, the verdict for an annotation) and the second it starts at. */
function BandLayer({ bands, view, width, height, capY, capH, onClick }: { bands: Band[]; view: [number, number]; width: number; height: number; capY: number; capH: number; onClick: (b: Band) => void }) {
  return (
    <g className="span-bands" data-testid="span-bands">
      {bands.map(b => {
        const { x: x0, w } = bandGeometry(b.start_s, b.end_s, view[0], view[1], width)   // the checked map: t → px on [a, b]
        const sel = b.kind === 'selected'
        const cap = sel ? CAP('selected') : b.colour ?? CAP(b.kind)
        const fill = sel ? FILL('selected') : b.capOnly ? 'transparent' : b.colour ? hexToFill(b.colour) : FILL(b.kind)
        return (
          <g key={b.id} onClick={e => { e.stopPropagation(); onClick(b) }} onPointerDown={e => e.stopPropagation()} style={{ cursor: 'pointer' }} data-kind={b.kind} data-toggle={b.toggle} data-cap-only={b.capOnly ? '1' : '0'}>
            <rect x={x0} y={0} width={w} height={height} fill={fill} stroke={sel ? 'var(--amber)' : 'none'} strokeWidth={sel ? 1.2 : 0} data-kind={b.kind} data-start-s={b.start_s.toFixed(3)} data-in-view={b.end_s > view[0] && b.start_s < view[1] ? '1' : '0'}><title>{b.title}</title></rect>
            <rect x={x0} y={capY} width={w} height={capH} rx={2} fill={cap} opacity={b.kind === 'detected' && !b.colour ? 0.35 : 1} />
          </g>
        )
      })}
    </g>
  )
}

/** One edge of the span as a number field (seconds, three decimals, hours beside). Typing moves the view live
 *  (debounced 150 ms); the view's own changes show here whenever the field is not being typed in; ↑ ↓ step by
 *  the last digit typed; a value the view cannot take shows why, in place, and moves nothing. */
function EdgeField({ side, value, other, dur, minSpan, onCommit }: { side: 'left' | 'right'; value: number; other: number; dur: number; minSpan: number; onCommit: (v: number) => void }) {
  const [text, setText] = useState<string | null>(null)   // null = mirroring the view
  const shown = text ?? value.toFixed(3)
  const parsed = text === null ? value : parseEdge(text, side, other, dur, minSpan)
  const bad = typeof parsed === 'string' ? parsed : null
  const commit = useRef(onCommit)
  commit.current = onCommit
  useEffect(() => {
    if (text === null || typeof parsed !== 'number') return
    const id = window.setTimeout(() => commit.current(parsed), 150)
    return () => window.clearTimeout(id)
  }, [text, parsed])
  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      const next = stepEdge(shown, e.key === 'ArrowUp' ? 1 : -1)
      if (next !== null) { e.preventDefault(); setText(next) }
    } else if (e.key === 'Enter') {
      if (typeof parsed === 'number') { commit.current(parsed); setText(null) }
    } else if (e.key === 'Escape') { e.stopPropagation(); setText(null) }
  }
  const label = side === 'left' ? 'left edge' : 'right edge'
  return (
    <span className="ex-edge" data-testid={`span-${side}`}>
      <input className={`ex-edge-input${bad ? ' invalid' : ''}`} value={shown} inputMode="decimal" spellCheck={false}
        onChange={e => setText(e.target.value)} onKeyDown={onKey} onBlur={() => { if (typeof parsed === 'number' && text !== null) commit.current(parsed); setText(null) }}
        aria-label={`${label} of the span, seconds (↑ ↓ step by the last digit)`} aria-invalid={!!bad} title={bad ?? `${label}, seconds from the channel start · ↑ ↓ step by the last digit`} data-testid={`span-${side}-input`} />
      <span className="ex-edge-unit">s</span>
      <span className="ex-edge-h" data-testid={`span-${side}-h`}>{(((typeof parsed === 'number' ? parsed : value)) / 3600).toFixed(4)} h</span>
      {bad && <span className="ex-edge-err" role="alert" data-testid={`span-${side}-error`}>{bad}</span>}
    </span>
  )
}

/** The legend as a row of switches, one per band kind, each with its own colour and how many are in view. */
function BandToggles({ toggles, onToggle, counts }: { toggles: Toggles; onToggle: (k: ToggleKind) => void; counts: Record<ToggleKind, number> }) {
  return (
    <span className="legend ex-band-toggles" role="group" aria-label="band kinds shown on the span" data-testid="band-toggles">
      {BAND_KINDS.map(k => (
        <button key={k.key} type="button" className={`ex-band-toggle${toggles[k.key] ? '' : ' off'}`} aria-pressed={toggles[k.key]} onClick={() => onToggle(k.key)}
          title={`${toggles[k.key] ? 'hide' : 'show'} ${k.label} bands — ${k.tip}`} data-testid={`band-toggle-${k.key}`} data-on={toggles[k.key] ? '1' : '0'}>
          <i style={{ background: k.cap }} />{k.label}<span className="n">{counts[k.key]}</span>
        </button>
      ))}
    </span>
  )
}
function hexToFill(hex: string) {
  const n = parseInt(hex.replace('#', ''), 16)
  return Number.isNaN(n) ? 'var(--band-detected)' : `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, 0.16)`
}

export function SpanView({ ch, vp, plotRef, width, bands: allBands, selected, selectedLabel, onBandClick, nav, legendOpen, setLegendOpen, demo, toggles, onToggle, bandNote }: {
  ch: Channel; vp: Viewport; plotRef: React.Ref<HTMLDivElement>; width: number
  bands: Band[]; selected: Motif | null; selectedLabel: string | null; onBandClick: (m: Motif) => void
  nav: { index: number; total: number; capped: boolean; prev: () => void; next: () => void }
  legendOpen: boolean; setLegendOpen: (o: boolean) => void; demo: boolean
  toggles: Toggles; onToggle: (k: ToggleKind) => void
  /** span-plot critic: why fewer detections draw than are in view (no runs picked; a thinned read), in words */
  bandNote?: string | null
}) {
  const legendRef = useRef<HTMLButtonElement>(null)
  const W = Math.max(0, width)
  const [a, b] = vp.view
  // the legend switches what draws; the open motif draws whatever its kind
  const bands = allBands.filter(bd => bd.kind === 'selected' || toggles[bd.toggle])
  const counts = { detected: 0, interesting: 0, not_interesting: 0, unsure: 0, artifact: 0, seed: 0 } as Record<ToggleKind, number>
  for (const bd of allBands) counts[bd.toggle]++
  const minSpan = Math.min(ch.duration_s, MIN_SPAN_S)
  const x = makeX(a, b, W)
  const win = vp.win
  const envOk = !win || envelopeOk(win.data?.envelope)   // shape guard: a malformed 200 draws an ErrorCard, not a throw
  const range = (win && envOk ? vRange(win.data.envelope.v) : null) ?? ch.y_range
  const y = makeY(range[0], range[1], H, TOP + 6, 8)
  // transform from the fetched viewport onto the current one (kept until the new data lands)
  let transform: string | undefined
  let xf = x
  let stale = false   // the kept path would be stretched > MAX_STRETCH× or does not overlap the new view: draw the skeleton
  if (win) {
    const [fa, fb] = win.view
    xf = makeX(fa, fb, W)
    const s = (fb - fa) / (b - a)
    const dx = ((fa - a) / (b - a)) * W
    if (Math.abs(s - 1) > 1e-9 || Math.abs(dx) > 1e-6) transform = `translate(${dx.toFixed(2)},0) scale(${s.toFixed(6)},1)`
    stale = s > MAX_STRETCH || s < 1 / MAX_STRETCH || fb <= a || fa >= b
  }

  const svgRef = useRef<SVGSVGElement | null>(null)
  const drag = useRef<{ x0: number; view: [number, number]; moved: boolean } | null>(null)
  const [dragging, setDragging] = useState(false)
  const { zoomAt, viewRef, setView } = vp

  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const [va, vb] = viewRef.current
      const anchor = va + ((e.clientX - r.left) / r.width) * (vb - va)
      const notches = Math.max(-10, Math.min(10, e.deltaY / 100))
      zoomAt(Math.pow(1.15, notches), anchor)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomAt, viewRef, W])

  const onDown = (e: React.PointerEvent<SVGSVGElement>) => { if (e.button !== 0) return; drag.current = { x0: e.clientX, view: viewRef.current, moved: false } }
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current
    if (!d || W <= 0) return
    const dx = e.clientX - d.x0
    if (!d.moved) { if (Math.abs(dx) < 3) return; d.moved = true; setDragging(true); e.currentTarget.setPointerCapture(e.pointerId) }
    const [va, vb] = d.view
    const dt = (-dx / W) * (vb - va)
    setView([va + dt, vb + dt])
  }
  const onUp = () => { drag.current = null; setDragging(false) }
  // keyboard (critique r1: pan/zoom were pointer-only): ← → pan a tenth of the view (Shift: half), + − zoom about the centre
  const onKey = (e: React.KeyboardEvent<SVGSVGElement>) => {
    const [va, vb] = viewRef.current
    const span = vb - va
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      e.preventDefault()
      const dt = (e.shiftKey ? 0.5 : 0.1) * span * (e.key === 'ArrowLeft' ? -1 : 1)
      setView([va + dt, vb + dt])
    } else if (e.key === '+' || e.key === '=') { e.preventDefault(); zoomAt(1 / 1.5, (va + vb) / 2) }
    else if (e.key === '-' || e.key === '_') { e.preventDefault(); zoomAt(1.5, (va + vb) / 2) }
  }

  const st = vp.lastStat
  const ticks = viewportHourTicks(a, b)
  // stale numbers (previous view) read as live otherwise: grey from the moment the view moves, not only once the debounced fetch starts
  const dim = vp.fetching || (!!win && (win.view[0] !== a || win.view[1] !== b))

  return (
    <div className="card ex-tier" data-testid="signal-span-card">
      <div className="head">
        <span className="card-title">Span</span>
        <span className="range ex-edges" data-testid="span-range" data-left={a.toFixed(3)} data-right={b.toFixed(3)}>
          <EdgeField side="left" value={a} other={b} dur={ch.duration_s} minSpan={minSpan} onCommit={v => setView([v, viewRef.current[1]])} />
          <span className="ex-edge-sep">–</span>
          <EdgeField side="right" value={b} other={a} dur={ch.duration_s} minSpan={minSpan} onCommit={v => setView([viewRef.current[0], v])} />
          <span className="ex-edge-dur" data-testid="span-duration">· {fmtDuration(b - a)}</span>
        </span>
        {vp.fetching && <span className="stat">fetching…</span>}
        <span className="grow" />
        <span className="ex-nav" data-testid="motif-nav">
          <button onClick={nav.prev} title="previous motif ( [ )" aria-label="previous motif" data-testid="motif-prev"><Icon name="chevron-left" size={13} /></button>
          <span>{nav.index >= 0 ? nav.index + 1 : '–'} / {fmtInt(nav.total)}{nav.capped ? '+' : ''}</span>
          <button onClick={nav.next} title="next motif ( ] )" aria-label="next motif" data-testid="motif-next"><Icon name="chevron-right" size={13} /></button>
        </span>
        <span className="ex-zoom">
          <button title="zoom out (−)" data-testid="zoom-out" onClick={() => zoomAt(1.5, (a + b) / 2)}><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5M8 11h6" /></svg></button>
          <button title="zoom in (+)" data-testid="zoom-in" onClick={() => zoomAt(1 / 1.5, (a + b) / 2)}><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5M8 11h6M11 8v6" /></svg></button>
          <button title="fit whole channel (F)" data-testid="zoom-fit" onClick={vp.fit}><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" /></svg></button>
          <button ref={legendRef} title="Reading the span (L)" aria-label="Reading the span" aria-expanded={legendOpen} onClick={() => setLegendOpen(!legendOpen)} data-testid="span-legend-button"><Icon name="info" size={14} /></button>
        </span>
      </div>
      {vp.error && <ErrorCard error={vp.error} title="viewport fetch failed" />}
      {!envOk && <ErrorCard error={MALFORMED_WINDOW} title="viewport payload cannot be drawn" />}
      <div className={`ex-plot pan${dragging ? ' dragging' : ''}`} ref={plotRef} style={{ height: H + AXIS_H }}>
        {W > 0 && (
          <svg ref={svgRef} width={W} height={H + AXIS_H} data-testid="signal-span" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}
            tabIndex={0} role="group" aria-label="span viewport: ← → pan, Shift for a larger step, + − zoom" aria-keyshortcuts="ArrowLeft ArrowRight + -" onKeyDown={onKey}>
            <rect x={0} y={0} width={W} height={H + AXIS_H} fill="#fff" />
            <g transform={`translate(0,${TOP})`}><TimeGrid x={x} t0={a} t1={b} height={H - TOP} /></g>
            <g transform={`translate(0,${TOP})`}>
              <BandLayer bands={bands} view={vp.view} width={W} height={H - TOP} capY={-13} capH={6} onClick={bd => onBandClick(bd.motif)} />
            </g>
            {selected && selected.end_s > a && selected.start_s < b && (
              // starts at the band, but never inside the y-label gutter (critique r1: MOTIF_744 overprinted "−0.23 mV")
              <text x={Math.max(labelGutter(range[0], range[1]), x(selected.start_s) + 4)} y={TOP + 12} style={{ fill: 'var(--amber)', fontWeight: 600 }} pointerEvents="none" data-testid="motif-label">{selectedLabel ?? `MOTIF_${selected.id}`}</text>
            )}
            {win && envOk && !stale ? (
              <g transform={transform} data-testid="envelope-group" data-transformed={transform ? '1' : '0'}>
                <EnvelopePath t={win.data.envelope.t} v={win.data.envelope.v} x={xf} y={y} testid="envelope-path" />
              </g>
            ) : <rect className="skeleton" x={0} y={TOP + 8} width={W} height={H - TOP - 16} fill="var(--grey-100)" data-testid="span-skeleton" data-reason={!win ? 'no-data' : !envOk ? 'malformed' : 'stale-transform'} />}
            <MvLabels y={y} lo={range[0]} hi={range[1]} dim={dim || stale} unit={win?.data.unit} />
            <line x1={0} x2={W} y1={H} y2={H} stroke="var(--border)" />
            <g className="time-axis" transform={`translate(0,${H})`} data-testid="span-axis" data-t0={a.toFixed(3)} data-t1={b.toFixed(3)}>
              {ticks.map(k => { const px = x(k.t); return <g key={k.t} transform={`translate(${px},0)`}><line y1={0} y2={4} stroke="var(--border-strong)" /><text x={px < 24 ? 2 : 0} y={14} textAnchor={px < 24 ? 'start' : px > W - 24 ? 'end' : 'middle'}>{k.label}</text></g> })}
            </g>
          </svg>
        )}
      </div>
      {bandNote && <div className="ex-band-note" data-testid="span-band-note">{bandNote}</div>}
      <div className="row between" style={{ marginTop: 6 }}>
        <span className="row" style={{ gap: 10 }}>
          <BandToggles toggles={toggles} onToggle={onToggle} counts={counts} />
          <span className="legend"><span><i style={{ background: 'var(--amber)' }} />selected</span>{demo && <span className="ex-demo" title="detections, runs and adjudications on this channel are demo canon">demo</span>}</span>
        </span>
        <InfoTip title="Span viewport" testid="span-info">
          Drag to pan, wheel to zoom, or click the plot and use ← → and + −. The peak-preserving min/max envelope is re-fetched for every viewport; real mV, never normalised. Click a band to open that motif.
          {st && <span className="mono" style={{ display: 'block', marginTop: 6, fontSize: 11 }} data-testid="zoom-stat" data-dim={dim ? '1' : '0'}>{fmtInt(st.n_points)} pts · server {fmtMs(st.decimate_ms)} · round trip {fmtMs(st.round_trip_ms)} · paint {fmtMs(st.paint_ms)}</span>}
        </InfoTip>
      </div>
      <Popover open={legendOpen} onClose={() => setLegendOpen(false)} anchorRef={legendRef} placement="bottom-end" width={330} title="Reading the span" testid="span-legend">
        <div className="ex-legend-pop">
          {BAND_KINDS.map(k => <LegendRow key={k.key} swatch={<i className="cap" style={{ background: k.cap }} />}>{k.label} — {k.tip}</LegendRow>)}
          <LegendRow swatch={<i className="cap" style={{ background: 'var(--amber)' }} />}>selected — the motif opened in the tier below, whatever its kind</LegendRow>
          <LegendRow swatch={<i className="cap" style={{ background: '#4b5563' }} />}>cap only, no fill — detection already has a verdict in Review</LegendRow>
          <div className="foot" style={{ fontStyle: 'normal' }}>Coverage ribbon: green reviewed · amber partly reviewed · red artifact-dense · grey never reviewed. Live, this database colours it by the verdict per bucket.</div>
        </div>
      </Popover>
    </div>
  )
}
