/* Encoding view (fixup-h). Minimum: THREE SAMPLED IMAGES, a scan through the rest, a colour bar carrying the
 * real value range, and no-data in grey (never painted at the bottom of the ramp).
 *
 * What "an image" is depends on the value, and the bridge decides it once (serialize.py `_frames`): the k-th
 * image of a stack; a chunk of a time-aligned image's columns at the image's own resolution; or the whole of
 * any other image. Every frame says which seconds of signal it came from, and the row marks them on the time
 * axis the other rows share — three images side by side would otherwise have left that axis.
 *
 * A symbolic Encoding is already one picture of the whole span on that axis, so its thumbnail is the strip. On
 * the settings page it too gets three sampled chunks, at a scale where a symbol can be read against the signal
 * it was cut from. Where symbols outnumber pixels a column is drawn as the MIX of the symbols under it (stacked
 * by share), never one symbol standing in for the rest: a majority vote would erase exactly the rare symbol —
 * a fall — the encoding exists to find. */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { ApiError, getStepFrame, type EncodingFrame, type EncodingImagePayload, type EncodingSymbolicPayload, type EnvelopeSeries } from '../../api'
import { EnvelopePath } from '../../charts/primitives'
import { makeX, makeY, polylinePath, type XScale } from '../../charts/scale'
import { useSize } from '../../charts/useSize'
import { Pager } from '../../kit'
import { fmtDuration, fmtHours } from '../../state'
import { ColourBar, Empty, FrameCanvas, PixelCanvas, finiteRange, type ViewCtx } from './common'

export const CAT9 = ['#0a84ff', '#22a06b', '#e8900c', '#8e5cf7', '#e5484d', '#0891b2', '#7c3aed', '#65a30d', '#db2777']
/** alphabet 3 = down / same / up → amber / grey / blue */
export const SYM3 = ['#e8900c', '#c7cbd1', '#0a84ff']
const FRAME_TINT = ['#0a84ff', '#8e5cf7', '#22a06b', '#e8900c']

export const symbolColour = (p: EncodingSymbolicPayload, s: number) => (p.alphabet_size === 3 ? SYM3[s] ?? '#999' : CAT9[((s % CAT9.length) + CAT9.length) % CAT9.length])
export const secondsPerSymbol = (p: EncodingSymbolicPayload, ctx: { t0: number; t1: number }) => p.seconds_per_symbol ?? (ctx.t1 - ctx.t0) / Math.max(1, p.n_symbols)

/* ============================== symbolic ============================== */
export function SymbolicView({ p, ctx, brackets }: { p: EncodingSymbolicPayload; ctx: ViewCtx; brackets?: { t0: number; t1: number; n: number }[] }) {
  const n = p.symbols.length
  const sps = secondsPerSymbol(p, ctx)
  const cell = ctx.x(ctx.t0 + sps) - ctx.x(ctx.t0)
  const top = 4, h = ctx.height - 8
  const [r0, r1] = ctx.x.range()
  // more symbols than pixels: one column per pixel, each a stack of the shares of the symbols under it
  const mix = useMemo(() => {
    if (cell >= 1 || !n) return null
    const cols = Math.max(1, Math.round(r1 - r0))
    const k = Math.max(1, p.alphabet_size)
    const counts = Array.from({ length: cols }, () => new Array(k).fill(0))
    const ta = ctx.x.invert(r0), tb = ctx.x.invert(r1)
    for (let i = 0; i < n; i++) {
      const c = Math.floor((((p.t0_s + (i + 0.5) * sps) - ta) / (tb - ta)) * cols)
      if (c >= 0 && c < cols && p.symbols[i] >= 0 && p.symbols[i] < k) counts[c][p.symbols[i]]++
    }
    return counts
  }, [cell, n, r0, r1, p.symbols, p.alphabet_size, p.t0_s, sps, ctx.x])
  if (!n) return <Empty text="no symbols" />
  return (
    <svg width={ctx.width} height={ctx.height} data-render="symbolic" data-mixed={mix ? '1' : '0'}>
      {mix ? mix.map((col, c) => {
        const total = col.reduce((a, b) => a + b, 0)
        if (!total) return null
        let acc = 0
        return <g key={c}>{col.map((cnt, s) => { if (!cnt) return null; const y0 = top + (acc / total) * h; acc += cnt; return <rect key={s} x={r0 + c} y={y0} width={1.05} height={(cnt / total) * h} fill={symbolColour(p, s)} /> })}</g>
      }) : p.symbols.map((s, i) => {
        const x0 = ctx.x(p.t0_s + i * sps)
        if (x0 > ctx.width || x0 + cell < 0) return null
        return (
          <g key={i}>
            <rect x={x0} y={top} width={Math.max(1, cell - (cell > 3 ? 0.5 : 0))} height={h} fill={symbolColour(p, s)} opacity={0.85}><title>{`symbol ${i} · ${p.letters[i] ?? s} · ${(p.t0_s + i * sps).toFixed(0)} s`}</title></rect>
            {cell >= 10 && <text x={x0 + cell / 2} y={top + h / 2 + 3.5} textAnchor="middle" fill="#fff" style={{ fontSize: 9 }}>{p.letters[i] ?? ''}</text>}
          </g>
        )
      })}
      {brackets?.map((b, k) => (
        <g key={k} data-testid={`chunk-bracket-${b.n}`}>
          <rect x={ctx.x(b.t0)} y={1} width={Math.max(2, ctx.x(b.t1) - ctx.x(b.t0))} height={ctx.height - 2} fill="none" stroke={FRAME_TINT[k % FRAME_TINT.length]} strokeWidth={2} rx={2} />
          <text x={ctx.x(b.t0) + 3} y={11} style={{ fill: FRAME_TINT[k % FRAME_TINT.length], fontWeight: 700, paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{b.n}</text>
        </g>
      ))}
      {!ctx.hideKey && <text x={ctx.width - 6} y={ctx.height - 5} textAnchor="end" fill="var(--muted)" style={{ paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>
        {p.alphabet_size === 3 ? 'amber down · grey same · blue up' : `alphabet ${p.alphabet_size} · categorical`}{mix ? ` · ${(1 / cell).toFixed(1)} symbols per px, each column the mix under it` : ''}{p.capped ? ' · capped' : ''}
      </text>}
    </svg>
  )
}

/** how many symbols one sampled chunk holds: few enough that each is wide enough to carry its letter */
const CHUNK_SYMBOLS = 48

function sliceEnv(env: EnvelopeSeries, a: number, b: number): { t: number[]; v: (number | null)[] } {
  const t: number[] = [], v: (number | null)[] = []
  for (let i = 0; i < env.t.length; i++) if (env.t[i] >= a && env.t[i] <= b) { t.push(env.t[i]); v.push(env.v[i]) }
  return { t, v }
}

function SymbolChunk({ p, ghost, k, sps, tint, n }: { p: EncodingSymbolicPayload; ghost: EnvelopeSeries | null; k: number; sps: number; tint: string; n: number }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const i0 = k * CHUNK_SYMBOLS, i1 = Math.min(p.symbols.length, i0 + CHUNK_SYMBOLS)
  const ta = p.t0_s + i0 * sps, tb = p.t0_s + i1 * sps
  const w = Math.max(10, size.width), H = 96, sigH = 62
  const x = makeX(ta, tb, w)
  const seg = ghost ? sliceEnv(ghost, ta, tb) : null
  const r = seg ? finiteRange(seg.v) : null
  const y = r ? makeY(r[0], r[1], sigH, 4, 4) : null
  const cell = x(ta + sps) - x(ta)
  return (
    <div style={{ flex: 1, minWidth: 0 }} data-testid={`symbol-chunk-${n}`} data-chunk={k}>
      <div className="mono small" style={{ color: tint, fontWeight: 600 }}>{n} · symbols {i0.toLocaleString()}–{(i1 - 1).toLocaleString()} <span className="muted" style={{ fontWeight: 400 }}>· {fmtHours(ta, 3)} + {fmtDuration(tb - ta)}</span></div>
      <div ref={ref} className="plot-surface" style={{ height: H, borderColor: tint }}>
        {size.width > 0 && (
          <svg width={w} height={H} data-plot-box data-rule9="trace">
            {seg && y ? <g data-trace><EnvelopePath t={seg.t} v={seg.v} x={x} y={y} stroke="var(--trace)" /></g> : <text x={4} y={14} fill="var(--muted)">the input signal is not loaded</text>}
            {Array.from({ length: i1 - i0 }, (_, j) => {
              const s = p.symbols[i0 + j]; const x0 = x(ta + j * sps)
              return (
                <g key={j}>
                  <line x1={x0} x2={x0} y1={0} y2={sigH} stroke="var(--grey-100)" />
                  <rect x={x0} y={sigH + 2} width={Math.max(1, cell - 0.5)} height={H - sigH - 4} fill={symbolColour(p, s)} opacity={0.9}><title>{`symbol ${i0 + j} · ${p.letters[i0 + j] ?? s}`}</title></rect>
                  {cell >= 9 && <text x={x0 + cell / 2} y={sigH + 2 + (H - sigH - 4) / 2 + 3.5} textAnchor="middle" fill="#fff" style={{ fontSize: 9 }}>{p.letters[i0 + j] ?? ''}</text>}
                </g>
              )
            })}
          </svg>
        )}
      </div>
    </div>
  )
}

/** Three sampled chunks of a symbolic encoding against the signal they were cut from, and a scan through the rest. */
export function SymbolChunks({ p, ctx, children }: { p: EncodingSymbolicPayload; ctx: ViewCtx; children: (brackets: { t0: number; t1: number; n: number }[]) => ReactNode }) {
  const sps = secondsPerSymbol(p, ctx)
  const nChunks = Math.max(1, Math.ceil(p.symbols.length / CHUNK_SYMBOLS))
  const picks = nChunks <= 3 ? Array.from({ length: nChunks }, (_, i) => i) : [0, Math.floor((nChunks - 1) / 2), nChunks - 1]
  const [scan, setScan] = useState<number | null>(null)
  const shown = scan === null ? picks : [...picks, scan]
  const bracket = (k: number, n: number) => ({ t0: p.t0_s + k * CHUNK_SYMBOLS * sps, t1: p.t0_s + Math.min(p.symbols.length, (k + 1) * CHUNK_SYMBOLS) * sps, n })
  return (
    <>
      {children(shown.map((k, i) => bracket(k, i + 1)))}
      <div className="bp-card-title" style={{ marginTop: 10 }}>
        <h3 style={{ fontSize: 13 }}>Sampled chunks</h3>
        <span className="sg">{picks.length} of {nChunks} · {CHUNK_SYMBOLS} symbols each · the numbered brackets above are where each was cut</span>
        <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6 }} className="sg">
          scan the rest <Pager page={(scan ?? picks[0]) + 1} pageCount={nChunks} onPage={n => setScan(Math.max(0, Math.min(nChunks - 1, n - 1)))} testid="chunk-scan" label="chunk" />
        </span>
      </div>
      <div style={{ display: 'flex', gap: 10 }} data-testid="symbol-chunks">
        {shown.map((k, i) => <SymbolChunk key={`${i}-${k}`} p={p} ghost={ctx.ghost ?? null} k={k} sps={sps} tint={FRAME_TINT[i % FRAME_TINT.length]} n={i + 1} />)}
      </div>
    </>
  )
}

/* ---- PAA and cutlines: drawn whenever the payload carries them (they used to be a dSAX-only view, by name) ---- */
export function PaaSteps({ paa, t0, sps, x, h }: { paa: number[]; t0: number; sps: number; x: XScale; h: number }) {
  const r = finiteRange(paa) ?? [0, 1]
  const y = makeY(r[0], r[1], h)
  const t: number[] = []; const v: number[] = []
  paa.forEach((q, i) => { t.push(t0 + i * sps, t0 + (i + 1) * sps); v.push(q, q) })
  return <path d={polylinePath(t, v, x, y)} fill="none" stroke="var(--blue-600)" strokeWidth={1.4} />
}

/* ============================== image ============================== */
const frameTime = (f: EncodingFrame) => (f.t0_s === null || f.t1_s === null ? 'position in the signal not known' : `${fmtHours(f.t0_s, 3)} + ${fmtDuration(f.t1_s - f.t0_s)}`)

/** Where each frame came from, on the row's own time axis. */
function FrameLocator({ frames, ctx, y, h }: { frames: EncodingFrame[]; ctx: ViewCtx; y: number; h: number }) {
  return (
    <g data-testid="frame-locator">
      <rect x={0} y={y} width={ctx.width} height={h} fill="var(--grey-100)" />
      {frames.map((f, i) => f.t0_s === null || f.t1_s === null ? null : (
        <rect key={i} x={ctx.x(f.t0_s)} y={y} width={Math.max(2, ctx.x(f.t1_s) - ctx.x(f.t0_s))} height={h} fill={FRAME_TINT[i % FRAME_TINT.length]}><title>{`${i + 1} · ${f.label} · ${frameTime(f)}`}</title></rect>
      ))}
    </g>
  )
}

export function ImageView({ p, ctx, extraFrame }: { p: EncodingImagePayload; ctx: ViewCtx; extraFrame?: EncodingFrame | null }) {
  if (p.ndim === 1 && p.series) {
    const r = finiteRange(p.series) ?? [0, 1]
    const bw = ctx.width / p.series.length
    return (
      <svg width={ctx.width} height={ctx.height} data-render="image-1d">
        {p.series.map((v, i) => { const hh = ((v - r[0]) / ((r[1] - r[0]) || 1)) * (ctx.height - 16); return <rect key={i} x={i * bw} y={ctx.height - 4 - hh} width={Math.max(1, bw - 0.5)} height={hh} fill="var(--blue)" /> })}
        <text x={4} y={11} fill="var(--muted)">{p.summary}</text>
      </svg>
    )
  }
  const fr = p.frames
  if (!fr || !fr.shown.length) return <Empty text={`encoding image · ${p.summary}`} />
  // every cell NaN: there is no image. Say that in words rather than paint a rectangle under a range that is not true.
  if (p.all_nan) return (
    <div className="an-plot-empty" data-render="image-all-nan" data-testid="image-all-nan" style={{ height: ctx.height }}>
      nothing to paint: every cell of this {p.shape.join('×')} image is NaN.
      {' '}The block left the whole span uncovered — no scale in the transform produced a finite coefficient here.
    </div>
  )
  const frames = extraFrame ? [...fr.shown, extraFrame] : fr.shown
  const LOC = 7, CAP = ctx.interactive ? 16 : 0
  const imgH = ctx.height - LOC - CAP - 2
  const gap = 6
  const each = (ctx.width - gap * (frames.length - 1)) / frames.length
  return (
    <div data-render="image" data-frames={frames.length} data-axis={fr.axis} style={{ height: ctx.height, position: 'relative' }}>
      <div style={{ display: 'flex', gap, height: imgH + CAP }}>
        {frames.map((f, i) => {
          // a time chunk fills its slot; anything else keeps its aspect, centred — a stretched Gramian reads as a different image
          const keep = fr.axis !== 'time'
          const w = keep ? Math.min(each, imgH * (f.shape[1] / f.shape[0])) : each
          return (
            <div key={`${i}-${f.index}`} style={{ width: each, display: 'flex', flexDirection: 'column', alignItems: 'center' }} data-testid={`frame-${i + 1}`} data-frame-index={f.index}>
              {ctx.interactive && <div className="mono" style={{ height: CAP, fontSize: 10.5, color: FRAME_TINT[i % FRAME_TINT.length], fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: each }}>{i + 1} · {f.label} <span className="muted" style={{ fontWeight: 400 }}>· {frameTime(f)}</span></div>}
              <FrameCanvas frame={f} style={{ width: w, height: imgH, borderBottom: `2px solid ${FRAME_TINT[i % FRAME_TINT.length]}` }} />
            </div>
          )
        })}
      </div>
      <svg width={ctx.width} height={LOC + 2} style={{ position: 'absolute', left: 0, bottom: 0 }}><FrameLocator frames={frames} ctx={ctx} y={2} h={LOC} /></svg>
      {!ctx.interactive && <span className="mono" style={{ position: 'absolute', right: 6, top: 2, fontSize: 10, color: 'var(--muted)', background: 'rgba(255,255,255,0.85)', padding: '0 4px', borderRadius: 3 }}>{fr.shown.length} of {fr.n.toLocaleString()} {fr.axis === 'stack' ? 'images' : fr.axis === 'time' ? 'chunks' : 'image'} · the bar below marks where each is</span>}
    </div>
  )
}

/** The settings-tier evidence of an image Encoding: the colour bar, the no-data count, and the scan. */
export function ImageEvidence({ p, jobId, index, onFrame }: { p: EncodingImagePayload; jobId: number | null; index: number; onFrame: (f: EncodingFrame | null) => void }) {
  const fr = p.frames
  const [scan, setScan] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    if (scan === null || !fr || jobId === null) return
    const have = fr.shown.find(f => f.index === scan)
    if (have) { onFrame(null); setErr(null); return }
    let alive = true
    getStepFrame(jobId, index, scan).then(f => { if (alive) { onFrame(f); setErr(null) } })
      .catch(e => { if (alive) { onFrame(null); setErr(e instanceof ApiError ? e.message : String(e)) } })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scan, jobId, index])
  if (!fr) return null
  const noData = { cells: fr.shown.reduce((a, f) => a + f.nan_cells, 0), of: fr.shown.reduce((a, f) => a + f.n_cells, 0) }
  const what = fr.axis === 'stack' ? 'images in the stack' : fr.axis === 'time' ? `chunks of ${fr.frame_columns} columns, at the image's own resolution` : 'image: the whole span'
  return (
    <div style={{ marginTop: 8 }} data-testid="image-evidence">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <ColourBar range={fr.value_range} channels={fr.shown[0]?.channels ?? 1} noData={noData} />
        <span className="mono muted small" style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {fr.shown.length} of {fr.n.toLocaleString()} {what}
          {fr.n > fr.shown.length && <> · scan the rest <Pager page={(scan ?? fr.shown[0].index) + 1} pageCount={fr.n} onPage={n => setScan(Math.max(0, Math.min(fr.n - 1, n - 1)))} testid="frame-scan" label="frame" /></>}
        </span>
      </div>
      {err && <div className="error-card" style={{ padding: '6px 10px', marginTop: 6 }} data-testid="frame-scan-error"><div className="mono small">{err}</div></div>}
      {!!p.nan_cells && <div className="muted mono small" data-testid="image-no-data" style={{ marginTop: 4 }}>{p.nan_cells.toLocaleString()} of {(p.n_cells ?? 0).toLocaleString()} cells of the whole image have no data — the block left those samples uncovered</div>}
    </div>
  )
}

/** A whole image stretched across the time axis (the upstream of an Encoding → Scores / SpanSet block), with an
 *  optional band of rows marked on it. Only for a time-aligned image: any other has no column-to-time mapping. */
export function AlignedImage({ p, ctx, band, testid = 'aligned-image' }: { p: EncodingImagePayload; ctx: ViewCtx; band?: [number, number] | null; testid?: string }) {
  if (!p.pixels_b64 || !p.display_shape || p.frames?.axis !== 'time') return null
  const [r0, r1] = ctx.x.range()
  // row 0 of the array is the top row of the canvas, and the band is a fraction of the array's rows
  const top = band ? band[0] * ctx.height : 0, bot = band ? band[1] * ctx.height : 0
  return (
    <div style={{ position: 'relative', height: ctx.height }} data-testid={testid}>
      <PixelCanvas pixels={p.pixels_b64} mask={p.nan_b64} shape={p.display_shape} channels={p.channels ?? 1} style={{ position: 'absolute', left: r0, top: 0, width: r1 - r0, height: ctx.height }} />
      {band && (
        <svg width={ctx.width} height={ctx.height} style={{ position: 'absolute', inset: 0 }} data-testid="summed-band">
          <rect x={r0} y={top} width={r1 - r0} height={Math.max(2, bot - top)} fill="none" stroke="var(--amber)" strokeWidth={2} />
          <text x={r0 + 6} y={Math.max(11, top + 12)} style={{ fill: '#fff', paintOrder: 'stroke', stroke: '#8a4b00', strokeWidth: 3, fontSize: 10.5 }}>rows summed · {Math.round(band[0] * 100)}–{Math.round(band[1] * 100)} % of the image height</text>
        </svg>
      )}
    </div>
  )
}
