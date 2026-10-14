/* WindowSet view (fixup-h). Minimum: the windows on the time axis and the feature matrix AS A HEATMAP, not a
 * truncated table. Thumbnail: the heatmap stretched to the row's width on the source signal's own time axis,
 * grey where there is no window.
 *
 * The two producers differ, and the picture follows what the payload carries rather than which block made it:
 *  - a set with a feature matrix (`preprocessing.window_matrix`) is the heatmap — every feature a row, every
 *    window at its own time, each feature scaled to its own min → max (features have no common unit);
 *  - a set with NO features (`preprocessing.sliding_windows`) is its windows as bands coloured train /
 *    validation / test, which is the leakage guard you actually want to check on that block.
 *
 * Too many windows for the pixels are averaged per pixel column, and the plot says so. A cell with no value is
 * grey — never the bottom of the ramp. */
import { useEffect, useMemo, useRef, useState } from 'react'
import type { WindowsetPayload } from '../../api'
import { EnvelopePath } from '../../charts/primitives'
import { makeY } from '../../charts/scale'
import { NO_DATA, NO_DATA_CSS, finiteRange, fmtN, type ViewCtx } from './common'

export const SPLIT_COLOUR: Record<string, string> = { train: '#a8c1ec', validation: '#fdc77e', test: '#86d69e' }
const LO: [number, number, number] = [238, 245, 255], HI: [number, number, number] = [10, 132, 255]

/** For each pixel column of the plot, the windows that start in it (their indices), or the one window covering it. */
function columnsOf(p: WindowsetPayload, ctx: ViewCtx): { cols: number; r0: number; hits: number[][] } {
  const [r0, r1] = ctx.x.range()
  const cols = Math.max(1, Math.round(r1 - r0))
  const hits: number[][] = Array.from({ length: cols }, () => [])
  const ta = ctx.x.invert(r0), tb = ctx.x.invert(r0 + cols)
  const perPx = (tb - ta) / cols
  p.starts_s.forEach((s, j) => {
    // a column belongs to the window its CENTRE lies in, so two abutting windows never share one
    const a = Math.ceil((s - ta) / perPx - 0.5), b = Math.ceil((s + p.length_s - ta) / perPx - 0.5) - 1
    if (p.length_s >= perPx) { for (let c = Math.max(0, a); c <= Math.min(cols - 1, b); c++) hits[c].push(j) }   // a window wider than a pixel covers its columns
    else { const c = Math.floor((s - ta) / perPx); if (c >= 0 && c < cols) hits[c].push(j) }                                                                // narrower: it lands in one
  })
  return { cols, r0, hits }
}

export function WindowSetView({ p, ctx }: { p: WindowsetPayload; ctx: ViewCtx }) {
  const matrix = p.features?.matrix ?? null
  const nF = matrix ? p.features!.n_columns : 0
  const stripH = ctx.interactive ? 30 : 0
  const mapH = ctx.height - stripH
  const canvas = useRef<HTMLCanvasElement>(null)
  const grid = useMemo(() => columnsOf(p, ctx), [p, ctx.x, ctx.width])   // eslint-disable-line react-hooks/exhaustive-deps
  const dense = useMemo(() => Math.max(0, ...grid.hits.map(h => h.length)), [grid])
  const [hover, setHover] = useState<{ c: number; k: number; px: number; py: number } | null>(null)
  useEffect(() => {
    const cv = canvas.current
    if (!cv || !matrix || !nF) return
    const img = new ImageData(grid.cols, nF)
    const ranges = p.features!.col_range ?? []
    for (let c = 0; c < grid.cols; c++) {
      const ws = grid.hits[c]
      for (let k = 0; k < nF; k++) {
        let sum = 0, cnt = 0
        const lo = ranges[k]?.[0], hi = ranges[k]?.[1]
        for (const j of ws) {
          const v = matrix[j]?.[k]
          if (v === null || v === undefined || lo === null || lo === undefined || hi === null || hi === undefined) continue
          sum += hi > lo ? (v - lo) / (hi - lo) : 0.5; cnt++
        }
        const o = (k * grid.cols + c) * 4
        // no window here, or no finite value: grey, which is not on the ramp
        const rgb = cnt ? LO.map((a, q) => a + (HI[q] - a) * (sum / cnt)) : NO_DATA
        img.data[o] = rgb[0]; img.data[o + 1] = rgb[1]; img.data[o + 2] = rgb[2]; img.data[o + 3] = 255
      }
    }
    cv.width = grid.cols; cv.height = nF
    cv.getContext('2d')?.putImageData(img, 0, 0)
  }, [grid, matrix, nF, p.features])
  const gr = ctx.ghost && ctx.ghost.t.length ? finiteRange(ctx.ghost.v) : null

  if (matrix && nF) {
    const covered = grid.hits.filter(h => h.length).length
    const cell = hover ? { ws: grid.hits[hover.c], name: p.features!.columns[hover.k] } : null
    const val = cell && cell.ws.length ? matrix[cell.ws[0]]?.[hover!.k] : null
    return (
      <div data-render="windowset" data-mode="heatmap" data-features={nF} data-covered={covered} style={{ position: 'relative', height: ctx.height }}>
        {ctx.interactive && (
          <svg width={ctx.width} height={stripH} style={{ display: 'block' }} data-testid="window-ticks">
            {ctx.ghost && gr && <EnvelopePath t={ctx.ghost.t} v={ctx.ghost.v} x={ctx.x} y={makeY(gr[0], gr[1], stripH)} stroke="var(--trace-ghost)" />}
            {dense <= 1 && p.starts_s.map((s, i) => <line key={i} x1={ctx.x(s)} x2={ctx.x(s)} y1={0} y2={stripH} stroke="var(--blue)" strokeOpacity={0.55} />)}
          </svg>
        )}
        <canvas ref={canvas} data-testid="feature-heatmap" style={{ position: 'absolute', left: grid.r0, top: stripH, width: grid.cols, height: mapH, imageRendering: 'pixelated' }}
          onPointerMove={ctx.interactive ? e => { const r = e.currentTarget.getBoundingClientRect(); setHover({ c: Math.max(0, Math.min(grid.cols - 1, Math.floor(e.clientX - r.left))), k: Math.max(0, Math.min(nF - 1, Math.floor(((e.clientY - r.top) / r.height) * nF))), px: e.clientX - r.left, py: e.clientY - r.top }) } : undefined}
          onPointerLeave={() => setHover(null)} />
        {hover && cell && (
          <div className="k-plot-tip" style={{ left: grid.r0 + hover.px, top: stripH + hover.py }} data-testid="heatmap-readout">
            {cell.name} · {cell.ws.length === 0 ? 'no window here' : cell.ws.length === 1 ? `window ${cell.ws[0] + 1} = ${val === null || val === undefined ? 'no value' : fmtN(val)}` : `${cell.ws.length} windows averaged`}
          </div>
        )}
        <span className="mono" style={{ position: 'absolute', right: 6, top: stripH + 2, fontSize: 10, color: 'var(--text-2)', background: 'rgba(255,255,255,0.85)', padding: '0 4px', borderRadius: 3 }}>
          {p.n_windows.toLocaleString()} windows × {nF} features · each row its own min → max{dense > 1 ? ` · up to ${dense} windows averaged per px` : ''}{covered < grid.cols ? ' · grey = no window' : ''}{p.capped ? ' · capped' : ''}
        </span>
      </div>
    )
  }

  // no feature matrix: the windows themselves, by split when the set carries one
  const names = p.split?.names ?? {}
  const colourOf = (i: number) => p.split ? SPLIT_COLOUR[names[String(p.split.labels[i])] ?? ''] ?? '#dfe3e8' : 'var(--band-detected)'
  const [r0, r1] = ctx.x.range()
  return (
    <svg width={ctx.width} height={ctx.height} data-render="windowset" data-mode={p.split ? 'split' : 'windows'}>
      <rect x={r0} y={0} width={r1 - r0} height={ctx.height} fill={NO_DATA_CSS} fillOpacity={0.18} />
      {p.starts_s.map((s, i) => {
        const x0 = ctx.x(s), w = Math.max(1, ctx.x(s + p.length_s) - x0 - (dense <= 1 ? 1 : 0))
        return <rect key={i} x={x0} y={0} width={w} height={ctx.height} fill={colourOf(i)} data-split={p.split ? names[String(p.split.labels[i])] : undefined}><title>{`window ${i + 1}${p.split ? ` · ${names[String(p.split.labels[i])] ?? '?'}` : ''}`}</title></rect>
      })}
      {ctx.ghost && gr && <EnvelopePath t={ctx.ghost.t} v={ctx.ghost.v} x={ctx.x} y={makeY(gr[0], gr[1], ctx.height)} stroke="var(--trace)" opacity={0.75} />}
      <text x={ctx.width - 6} y={11} textAnchor="end" fill="var(--text-2)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>
        {p.n_windows.toLocaleString()} windows · {p.length_s} s · no features{p.split ? ' · ' + Object.entries(p.split.counts).map(([k, c]) => `${c} ${k}`).join(' / ') : ''}{p.capped ? ' · capped' : ''}
      </text>
    </svg>
  )
}

/** w2-f: a window set cut AROUND EVENTS (`catalogue.event_windows`, spanset → windowset), drawn on the trace: each
 *  input event as a faint band, each window as a blue outline around its event, the anchor (`anchor.offset_s` into
 *  the window, the same for every window) as an amber tick inside it, and every event that got no window outlined
 *  red with its reason — an absence is drawn, never hidden. Separate from `WindowSetView` because only this
 *  producer has events and an anchor; the generic view would need an `if` on every path. */
export function EventWindowsView({ p, events, ctx }: { p: WindowsetPayload; events: { start_s: number[]; end_s: number[] } | null; ctx: ViewCtx }) {
  const anchor = p.anchor!
  const [r0, r1] = ctx.x.range()
  const h = ctx.height
  const gr = ctx.ghost && ctx.ghost.t.length ? finiteRange(ctx.ghost.v) : null
  const reasonOf = useMemo(() => {
    const m = new Map<number, string>()
    for (const [reason, rows] of Object.entries(p.events?.omitted_rows ?? {})) for (const r of rows ?? []) m.set(r, reason)
    return m
  }, [p.events])
  const nOmitted = Object.values(p.events?.omitted ?? {}).reduce((a, b) => a + (b ?? 0), 0)
  // fix 1 (critic 11): an event with no window is outlined even when `omitted_rows` was capped and does not list
  // it — by set difference against the events the windows were cut around
  const windowed = useMemo(() => new Set(p.event_index ?? []), [p.event_index])
  const narrow = p.starts_s.length > 0 && ctx.x(p.starts_s[0] + p.length_s) - ctx.x(p.starts_s[0]) < 3
  return (
    <svg width={ctx.width} height={h} data-render="windowset" data-mode="event-windows" data-testid="event-windows" data-windows={p.n_windows} data-omitted={nOmitted} data-plot-box data-rule9="ghost">
      <rect x={r0} y={0} width={r1 - r0} height={h} fill={NO_DATA_CSS} fillOpacity={0.12} />
      {events && events.start_s.map((s, i) => {
        const why = reasonOf.get(i) ?? (p.event_index && !windowed.has(i) ? 'not listed (omitted_rows is capped — see the notes)' : undefined)
        const x0 = ctx.x(s), w = Math.max(1, ctx.x(events.end_s[i]) - x0)
        return why
          ? <rect key={`e${i}`} x={x0} y={1} width={w} height={h - 2} fill="var(--band-artifact)" stroke="var(--red)" strokeDasharray="3 2" data-testid={reasonOf.has(i) ? 'event-omitted' : 'event-windowless'}><title>{`event ${i + 1} · no window: ${why.replace(/_/g, ' ')}`}</title></rect>
          : <rect key={`e${i}`} x={x0} y={0} width={w} height={h} fill="var(--band-detected)" opacity={0.55}><title>{`event ${i + 1}`}</title></rect>
      })}
      {ctx.ghost && gr && <g data-trace><EnvelopePath t={ctx.ghost.t} v={ctx.ghost.v} x={ctx.x} y={makeY(gr[0], gr[1], h)} stroke="var(--trace)" opacity={0.8} /></g>}
      {p.starts_s.map((s, i) => {
        const x0 = ctx.x(s), w = Math.max(1, ctx.x(s + p.length_s) - x0), xa = ctx.x(s + anchor.offset_s)
        const ev = p.event_index?.[i]
        return (
          <g key={i} data-window={i}>
            <rect x={x0} y={3} width={w} height={h - 6} fill="none" stroke="var(--blue)" strokeWidth={narrow ? 0.8 : 1.3} strokeOpacity={0.9}>
              <title>{`window ${i + 1}${ev !== undefined && ev >= 0 ? ` · around event ${ev + 1}` : ''} · ${p.length_s} s · anchor (${anchor.used ?? 'onset'}) ${anchor.offset_s} s in`}</title>
            </rect>
            <line x1={xa} x2={xa} y1={3} y2={h - 3} stroke="var(--amber)" strokeWidth={1.4} data-testid="window-anchor" />
          </g>
        )
      })}
      <text x={ctx.width - 6} y={11} textAnchor="end" fill="var(--text-2)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>
        {p.n_windows.toLocaleString()} of {(p.events?.n_events ?? p.n_windows).toLocaleString()} events windowed · {p.length_s} s each · anchor {anchor.offset_s} s in{nOmitted ? ` · ${nOmitted} left out` : ''}{p.capped ? ' · capped' : ''}
      </text>
    </svg>
  )
}

/** w2-f: what happened to every event, under the event-windows plot: the omissions by reason, overlaps, split leaks,
 *  the block's warnings. Every number the block counted is on the face. */
export function EventWindowsKey({ p }: { p: WindowsetPayload }) {
  const ev = p.events
  const a = p.anchor!
  const omitted = Object.entries(ev?.omitted ?? {}).filter(([, n]) => (n ?? 0) > 0)
  return (
    <div data-testid="event-windows-key" style={{ marginTop: 4 }}>
      <div className="bp-legend" style={{ paddingLeft: 0 }}>
        <span><i style={{ background: 'var(--band-detected)' }} />input event</span>
        <span><i style={{ background: 'transparent', border: '1.5px solid var(--blue)' }} />its window ({p.length_s} s{ev?.length_basis ? ` · ${ev.length_basis}` : ''})</span>
        <span><i style={{ background: 'var(--amber)', width: 3 }} />anchor · {a.used ?? a.requested ?? 'onset'} · {a.offset_s} s into the window{a.pre_frac != null ? ` (${Math.round(a.pre_frac * 100)} %)` : ''}{a.fallback ? ` · ${a.fallback} fell back` : ''}</span>
        <span><i style={{ background: 'var(--band-artifact)', border: '1px dashed var(--red)' }} />event with no window</span>
      </div>
      <div className="mono small" data-testid="event-windows-fates" style={{ color: 'var(--text-2)' }}>
        {omitted.length ? `left out: ${omitted.map(([r, n]) => `${n} ${r.replace(/_/g, ' ')}`).join(' · ')}` : 'every event got a window'}
        {ev?.n_overlapping ? ` · ${ev.n_overlapping} window${ev.n_overlapping === 1 ? '' : 's'} overlap the next` : ''}
        {ev?.n_split_leaks ? ` · ${ev.n_split_leaks} share samples with a window of another split role` : ''}
        {ev?.n_duration_unmeasured ? ` · ${ev.n_duration_unmeasured} event${ev.n_duration_unmeasured === 1 ? '' : 's'} too slow to measure (counted, not dropped)` : ''}
        {ev?.n_recovery_outside_window ? ` · ${ev.n_recovery_outside_window} recover after their window ends` : ''}
      </div>
      {(ev?.warnings ?? []).map((w, i) => <div key={i} className="mono small" style={{ color: 'var(--amber-700, #b76a00)' }} data-testid="event-windows-warning">{w}</div>)}
      {(ev?.notes ?? []).map((w, i) => <div key={`n${i}`} className="mono small muted" data-testid="event-windows-note">{w}</div>)}
      {p.n_windows === 0 && <div className="mono small" data-testid="event-windows-none" style={{ color: 'var(--amber-700, #b76a00)' }}>no window: {(ev?.n_events ?? 0) === 0 ? 'the detector upstream found no events on this span' : 'every event was left out (reasons above)'}</div>}
    </div>
  )
}

/** The key under the settings-tier plot. */
export function WindowSetKey({ p }: { p: WindowsetPayload }) {
  if (p.features?.matrix) {
    const stops = `rgb(${LO.join(',')}), rgb(${HI.join(',')})`
    return (
      <div data-testid="windowset-key">
        <div className="mono muted small" style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
          <span>each feature's own min</span><span style={{ width: 120, height: 9, borderRadius: 3, background: `linear-gradient(90deg, ${stops})` }} /><span>max</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><i style={{ width: 12, height: 9, borderRadius: 2, background: NO_DATA_CSS, display: 'inline-block' }} />no window / no value</span>
          <span>· hover a cell for the feature and its value</span>
        </div>
        <details className="muted mono small" style={{ marginTop: 4 }}>
          <summary style={{ cursor: 'pointer' }}>{p.features.n_columns} features, top row first</summary>
          {p.features.columns.map((c, i) => `${i + 1} ${c}`).join(' · ')}
        </details>
      </div>
    )
  }
  if (p.split) return (
    <div className="bp-legend" style={{ paddingLeft: 0 }} data-testid="windowset-key">
      {Object.entries(p.split.counts).map(([k, c]) => <span key={k}><i style={{ background: SPLIT_COLOUR[k] ?? '#dfe3e8' }} />{k} · {c}</span>)}
      <span>this producer carries no features — the split is what there is to check: whole time blocks per role, never two roles sharing samples</span>
    </div>
  )
  return <div className="muted mono small" data-testid="windowset-key">the window set carries neither features nor a split</div>
}
