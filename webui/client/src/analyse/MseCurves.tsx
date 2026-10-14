/* W3-F: a window set that carries a CURVE per window (`payload.curves`, a payload convention — multiscale entropy
 * ships one: entropy against blur scale). Drawn the way DetectorFunnel is wired: `curvesOf(payload)` reads the
 * payload, never the block's name.
 *
 *  - x is the scale on a LOG axis (seconds), y the value; one thin line per sampled window, the median bold;
 *  - an undefined scale (`null`) is a GAP: the line is broken there, never joined across it (drawing rule 1), and a
 *    defined point between two gaps is drawn as a dot so it does not vanish;
 *  - a scale the block's collapse guard flagged is marked (amber ring) on every window it flagged, and counted under
 *    the axis; a scale undefined in every window is shaded and named.
 *
 * No null band: the paired null is a count today (`nullText` in toolbar.tsx) — the draws' own curves are not
 * reachable from the page. Drawing one would need the bridge to keep each null draw's step payload (or its meta)
 * for the step, the way it keeps the real run's. */
import { useMemo } from 'react'
import type { CurvesPayload, WindowsetPayload } from '../api'
import { makeX, makeY, polylinePath } from '../charts/scale'
import { useSize } from '../charts/useSize'
import { InfoTip } from '../kit'

export function curvesOf(p: unknown): CurvesPayload | null {
  const c = (p as WindowsetPayload | null)?.curves
  return c && Array.isArray(c.scales_s) && c.scales_s.length > 0 && Array.isArray(c.windows) ? c : null
}

const fmtS = (s: number) => (s >= 3600 ? `${+(s / 3600).toPrecision(3)} h` : s >= 60 ? `${+(s / 60).toPrecision(3)} min` : `${+s.toPrecision(3)} s`)
const LINE = '#7fb8ff', MEDIAN = 'var(--blue)', FLAG = 'var(--amber)'

export function MseCurves({ p }: { p: WindowsetPayload }) {
  const c = curvesOf(p)!
  const flags = p.curve_flags ?? {}
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width), h = 240, padL = 40, padR = 12, padT = 10, padB = 34
  const lx = useMemo(() => c.scales_s.map(s => Math.log10(Math.max(s, 1e-9))), [c.scales_s])
  const range = useMemo(() => {
    const vals = [...c.windows.flatMap(win => win.values), ...c.median].filter((v): v is number => v !== null && Number.isFinite(v))
    return vals.length ? [Math.min(...vals), Math.max(...vals)] as [number, number] : null
  }, [c])
  const blank = new Set((flags.blank_scales_s ?? []).map(s => +s.toPrecision(6)))
  const collapse = flags.collapse ?? []
  if (!range) {
    return <div className="an-plot-empty" data-testid="mse-curves" data-state="empty" style={{ height: 80 }}>no scale was defined in any sampled window · {(flags.blank_scales_s ?? []).length} scales blank · see the block's warnings</div>
  }
  const x = makeX(lx[0], lx[lx.length - 1] === lx[0] ? lx[0] + 1 : lx[lx.length - 1], w, padL, padR)
  const y = makeY(range[0], range[1], h - padB + padT, padT, 0)
  const isolated = (vals: (number | null)[], j: number) => vals[j] !== null && (j === 0 || vals[j - 1] === null) && (j === vals.length - 1 || vals[j + 1] === null)
  return (
    <div data-testid="mse-curves" data-n-curves={c.windows.length}>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>The curve of each window</h3>
        <span className="sg">{c.windows.length} of {c.n_windows} window{c.n_windows === 1 ? '' : 's'}{c.sampled ? ' (a seeded sample)' : ''} · median bold · scale on a log axis · a gap is a scale with no defined value</span>
        <InfoTip title="Reading the curves">{c.form ?? 'one value per scale'}. A gap is never interpolated: the scale had too few coarse points, or no template matched. An amber ring is a value the block's collapse guard flagged (the window drifts, so the tolerance is the drift's, not the noise's) — kept and flagged, never blanked. Compare a curve with phase-randomised (AAFT) copies of the same recording before reading anything into it.</InfoTip>
      </div>
      <div ref={ref} className="plot-surface" style={{ height: h }}>
        {size.width > 0 && (
          <svg width={w} height={h} data-render="curves" data-plot-box>
            {c.scales_s.map((s, j) => blank.has(+s.toPrecision(6))
              ? <rect key={`b${j}`} x={x(lx[j]) - 4} y={padT} width={8} height={h - padB - padT + padT} fill="var(--grey-100)" data-testid="mse-blank-scale"><title>{`${fmtS(s)}: undefined in every window`}</title></rect>
              : null)}
            {c.windows.map(win => (
              <g key={win.index} data-testid="mse-curve">
                <path d={polylinePath(lx, win.values, x, y)} fill="none" stroke={LINE} strokeWidth={1} opacity={0.75}><title>{`window ${win.index} · starts ${fmtS(win.start_s)}${win.inflation != null ? ` · inflation ${win.inflation.toFixed(2)}` : ''}`}</title></path>
                {win.values.map((v, j) => isolated(win.values, j) ? <circle key={j} cx={x(lx[j])} cy={y(v as number)} r={1.8} fill={LINE} /> : null)}
                {win.values.map((v, j) => v !== null && win.collapsed?.[j] ? <circle key={`f${j}`} cx={x(lx[j])} cy={y(v)} r={3.2} fill="none" stroke={FLAG} strokeWidth={1.2} data-testid="mse-collapsed"><title>{`window ${win.index} at ${fmtS(c.scales_s[j])}: flagged by the collapse guard`}</title></circle> : null)}
              </g>
            ))}
            <path d={polylinePath(lx, c.median, x, y)} fill="none" stroke={MEDIAN} strokeWidth={2.4} data-testid="mse-median" />
            {c.median.map((v, j) => isolated(c.median, j) ? <circle key={`m${j}`} cx={x(lx[j])} cy={y(v as number)} r={2.6} fill={MEDIAN} /> : null)}
            <line x1={padL} x2={w - padR} y1={h - padB + padT} y2={h - padB + padT} stroke="var(--border)" />
            {c.scales_s.map((s, j) => (
              <g key={`t${j}`}>
                <line x1={x(lx[j])} x2={x(lx[j])} y1={h - padB + padT} y2={h - padB + padT + 3} stroke="var(--muted)" />
                {(c.scales_s.length <= 8 || j % 2 === 0 || j === c.scales_s.length - 1) && <text x={x(lx[j])} y={h - padB + padT + 13} textAnchor="middle" fill="var(--muted)">{fmtS(s)}</text>}
                {collapse[j] ? <text x={x(lx[j])} y={h - 4} textAnchor="middle" fill={FLAG} style={{ fontSize: 9.5 }}>{collapse[j]}⚑</text> : null}
              </g>
            ))}
            <text x={4} y={padT + 8} fill="var(--muted)">{range[1].toFixed(2)}</text>
            <text x={4} y={h - padB + padT} fill="var(--muted)">{range[0].toFixed(2)}</text>
            <text x={w - padR} y={padT + 8} textAnchor="end" fill="var(--muted)">entropy (nats) · scale (log)</text>
          </svg>
        )}
      </div>
      <div className="bp-legend" style={{ paddingLeft: 0 }}>
        <span><i style={{ background: LINE }} />one sampled window</span>
        <span><i style={{ background: 'var(--blue)' }} />median over the windows</span>
        <span><i style={{ background: 'transparent', border: `1.5px solid ${FLAG}`, borderRadius: 999 }} />flagged by the collapse guard{flags.inflation_limit != null ? ` (window inflation > ${flags.inflation_limit})` : ''} · the ⚑ count under a scale is how many windows</span>
        {blank.size > 0 && <span><i style={{ background: 'var(--grey-100)' }} />undefined in every window: {[...blank].map(fmtS).join(', ')}</span>}
      </div>
    </div>
  )
}
