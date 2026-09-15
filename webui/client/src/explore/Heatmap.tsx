/* COVERAGE MAP body (frame explore-1): one row per channel, one rounded cell per time bin,
   colour = 5-step ramp by QUANTILE RANK among the non-zero cells of the drawn matrix (critique
   r1: a linear count/max ramp went flat once one hot cell existed). Blue ramp, amber in `disagree`
   (§3 amber = differs). The selected row gets a blue outline and a blue label. Hovering a cell shows
   "CH4_A2 · 341–354 h · 12 annotations". Click selects, double-click (or Enter on the selected row)
   opens the channel. `range` crops the drawn bins client-side (time slider). Demo overlays: hatched
   unreviewed bins (reviewed coverage), dimmed reviewed bins (unreviewed only), dimmed rows with no
   span under the checked tags. A row without its matrix array renders an ErrorCard instead of throwing. */
import { useMemo, useState } from 'react'
import { ApiError, type Coverage } from '../api'
import { useSize } from '../charts/useSize'
import { ErrorCard } from './ErrorCard'
import { AMBER_RAMP, hourTicks, quantileRamp, RAMP, type ColourBy } from './util'

const LABEL_W = 64, ROW_H = 34, CELL_PAD = 3, AXIS_H = 22, RIGHT_PAD = 6

/** What "disagree" counts (server/corpus.py): printed in the tooltip, the legend and the bottom bar. */
export const DISAGREE_DEF = 'annotations with no overlapping detection + detections with no overlapping annotation'

export interface HeatmapOverlay {
  /** per channel name: reviewed flag per bin (demo) */
  reviewed?: Record<string, boolean[]>
  hatchUnreviewed?: boolean
  dimReviewed?: boolean
  /** channel names drawn dimmed (no span under the demo tag filter) */
  dimRows?: Set<string>
  /** every cell grey (zero-match / nothing shown) */
  blank?: boolean
}

export function Heatmap({ cov, matrix, unit, selectedId, onSelect, onOpen, range, overlay = {} }: {
  cov: Coverage; matrix: ColourBy | null; unit: string; selectedId: number | null; onSelect: (id: number) => void; onOpen?: (id: number) => void
  range?: [number, number]; overlay?: HeatmapOverlay
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const W = Math.max(0, size.width)
  const plotW = Math.max(1, W - LABEL_W - RIGHT_PAD)
  const bins = cov.bins
  const [h0, h1] = range ?? [0, cov.duration_h]
  const i0 = Math.max(0, Math.min(bins - 1, Math.floor(h0 / cov.bin_h)))
  const i1 = Math.max(i0 + 1, Math.min(bins, Math.ceil(h1 / cov.bin_h - 1e-9)))
  const nShown = i1 - i0
  const cellW = plotW / nShown
  const rows = Array.isArray(cov.rows) ? cov.rows : null
  const bad = rows && matrix ? rows.find(r => !Array.isArray(r?.[matrix])) : undefined
  const ramp = matrix === 'disagree' ? AMBER_RAMP : RAMP
  const { level, max } = useMemo(() => {
    const all: number[] = []
    if (rows && matrix && !bad) for (const r of rows) for (const c of r[matrix]) all.push(typeof c === 'number' ? c : 0)
    return { level: quantileRamp(all), max: all.reduce((m, v) => (v > m ? v : m), 0) }
  }, [rows, matrix, bad])
  if (!rows) return <ErrorCard error={new ApiError(0, 'malformed coverage payload: rows is not an array')} title="coverage map cannot be drawn" />
  if (bad) return <ErrorCard error={new ApiError(0, `malformed coverage payload: row ${String(bad?.name ?? '?')} has no ${matrix} array`)} title="coverage map cannot be drawn" />
  const H = rows.length * ROW_H + AXIS_H
  const edge = (i: number) => {
    const e = cov.bin_edges_h?.[i] ?? (i * cov.bin_h)
    return cov.bin_h >= 1 ? String(Math.round(e)) : e.toFixed(2)
  }
  const spanH = (i1 - i0) * cov.bin_h
  const hx = (h: number) => LABEL_W + ((h - i0 * cov.bin_h) / Math.max(1e-9, spanH)) * plotW

  return (
    <div className="ex-heat" ref={ref}>
      {W > 0 && (
        <svg width={W} height={H} data-testid="corpus-heatmap" data-matrix={matrix ?? 'none'} data-max={max} data-ramp={matrix === 'disagree' ? 'amber-quantile' : 'quantile'} data-bins-shown={nShown}>
          <defs>
            <pattern id="ex-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="5" stroke="#8a97a8" strokeWidth="1.4" strokeOpacity="0.55" />
            </pattern>
          </defs>
          {rows.map((r, ri) => {
            const vals = matrix ? r[matrix] : null
            const sel = r.id === selectedId
            const y = ri * ROW_H
            // "disagree" is a comparison: with no detections (or no annotations) on the channel there is nothing to compare
            const nAnn = r.counts?.annotations ?? 0, nDet = r.counts?.detections ?? 0
            const degenerate = matrix === 'disagree' && !(nAnn > 0 && nDet > 0)
            const missing = nDet > 0 ? 'no annotations' : 'no detections'
            const dimRow = overlay.dimRows?.has(r.name)
            const rev = overlay.reviewed?.[r.name]
            return (
              <g key={r.id} data-testid={`heatmap-row-${r.name}`} data-selected={sel ? '1' : '0'} data-dim={dimRow ? '1' : '0'}
                onClick={() => onSelect(r.id)} onDoubleClick={() => onOpen?.(r.id)} style={{ cursor: 'pointer' }}
                tabIndex={0} role="button" aria-pressed={sel} aria-label={`channel ${r.name}${sel ? ' (selected — Enter opens it)' : ''}`}
                onKeyDown={e => {
                  if (e.key === 'Enter' && sel && onOpen) { e.preventDefault(); onOpen(r.id) }
                  else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(r.id) }
                }}>
                <rect x={0} y={y} width={W} height={ROW_H} fill="transparent" />
                <text x={LABEL_W - 10} y={y + ROW_H / 2 + 3.5} textAnchor="end" style={{ fill: sel ? 'var(--blue)' : 'var(--muted)', fontWeight: sel ? 600 : 400 }}>{r.name}</text>
                <g opacity={dimRow ? 0.28 : 1}>
                  {Array.from({ length: nShown }, (_, k) => {
                    const bi = i0 + k
                    const c = vals ? (Number(vals[bi]) || 0) : 0
                    const lvl = degenerate || overlay.blank ? 0 : level(c)
                    const cx = LABEL_W + k * cellW
                    const reviewed = rev?.[bi]
                    const text = degenerate
                      ? `${r.name} · ${edge(bi)}–${edge(bi + 1)} h · disagree — (${missing} on this channel)`
                      : `${r.name} · ${edge(bi)}–${edge(bi + 1)} h · ${c} ${unit}${matrix === 'disagree' ? ' · unmatched annotations + unmatched detections' : ''}${rev ? (reviewed ? ' · reviewed (demo)' : ' · not reviewed (demo)') : ''}`
                    return (
                      <g key={bi}>
                        <rect data-testid="heatmap-cell" data-count={c} data-level={lvl}
                          x={cx + 0.5} y={y + CELL_PAD} width={Math.max(0.5, cellW - 1)} height={ROW_H - 2 * CELL_PAD} rx={2} fill={ramp[lvl]}
                          opacity={overlay.dimReviewed && reviewed ? 0.25 : 1}
                          onPointerEnter={() => setTip({ x: cx + cellW / 2, y: y + CELL_PAD, text })}
                          onPointerLeave={() => setTip(null)} />
                        {overlay.hatchUnreviewed && rev && !reviewed && <rect x={cx + 0.5} y={y + CELL_PAD} width={Math.max(0.5, cellW - 1)} height={ROW_H - 2 * CELL_PAD} rx={2} fill="url(#ex-hatch)" pointerEvents="none" data-testid="heatmap-hatch" />}
                      </g>
                    )
                  })}
                </g>
                {sel && <rect x={LABEL_W - 3} y={y + 1} width={plotW + 6} height={ROW_H - 2} rx={4} fill="none" stroke="var(--blue)" strokeWidth={1.5} pointerEvents="none" data-testid="heatmap-selected-outline" />}
              </g>
            )
          })}
          <g className="time-axis" transform={`translate(0,${rows.length * ROW_H})`}>
            {(range ? cropTicks(i0 * cov.bin_h, i1 * cov.bin_h) : hourTicks(cov.duration_h)).map((k, i, arr) => {
              const x = range ? hx(k.h) : LABEL_W + (cov.duration_h > 0 ? k.h / cov.duration_h : 0) * plotW
              return <text key={k.h} x={x} y={15} textAnchor={i === 0 ? 'start' : i === arr.length - 1 ? 'end' : 'middle'}>{k.label}</text>
            })}
          </g>
        </svg>
      )}
      {tip && <div className="ex-tip" style={{ left: tip.x, top: tip.y }} data-testid="heatmap-tooltip">{tip.text}</div>}
    </div>
  )
}

function cropTicks(a: number, b: number): { h: number; label: string }[] {
  const out: { h: number; label: string }[] = []
  const n = 6
  for (let i = 0; i <= n; i++) { const h = a + ((b - a) * i) / n; out.push({ h, label: `${b - a >= 60 ? Math.round(h) : h.toFixed(1)} h` }) }
  return out
}
