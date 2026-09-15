/* Shared pieces of the demo block pages (spec §6.8 block contract): cards, generated-looking parameter rows with the
 * recommended marker and an info pop-over (P9), tiles, a width-aware plot box and a draggable line. */
import { useRef, type ReactNode } from 'react'
import { useSize } from '../../../charts/useSize'
import { InfoTip, SelectField, Slider, cx } from '../../../kit'
import type { DemoChainBundle, DemoStep, BlockFixtures } from '../../../api/analyse'
import type { DemoActions, DemoChainState, RowView } from '../chainState'

export interface BlockProps {
  st: DemoChainState; bundle: DemoChainBundle; fx: BlockFixtures; rows: RowView[]; index: number; step: DemoStep
  draft: Record<string, unknown>; setDraft: (name: string, value: unknown) => void; actions: DemoActions
  running: boolean; stale: boolean
}

export function BlockCard({ title, sub, info, actions, children, testid, className, style }: { title: ReactNode; sub?: ReactNode; info?: string; actions?: ReactNode; children: ReactNode; testid?: string; className?: string; style?: React.CSSProperties }) {
  return (
    <div className={cx('card card-pad bx-card', className)} data-testid={testid} style={style}>
      <div className="bx-head"><h3>{title}</h3>{info && <InfoTip title={typeof title === 'string' ? title : undefined}>{info}</InfoTip>}{sub && <span className="sub">{sub}</span>}{actions && <span className="acts">{actions}</span>}</div>
      {children}
    </div>
  )
}

export function ParamsCard({ children, title = 'Parameters', note = 'recommended', testid = 'params-panel' }: { children: ReactNode; title?: string; note?: ReactNode; testid?: string }) {
  return (
    <div className="card card-pad bx-card" data-testid={testid}>
      <div className="bx-head"><h3>{title}</h3><span className="acts bx-rec-legend">{note}</span></div>
      <div className="bx-params">{children}</div>
    </div>
  )
}

const same = (a: unknown, b: unknown) => a === b || (typeof a === 'number' && typeof b === 'number' && Math.abs(a - b) < 1e-9)

export function ParamSlider({ label, info, value, onChange, min, max, step = 1, unit = '', format, rec, recNote, was, wide, testid, disabled, tone }: {
  label: string; info: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number; unit?: string; format?: (v: number) => string
  rec?: number; recNote?: string; was?: number; wide?: boolean; testid?: string; disabled?: boolean; tone?: 'red'
}) {
  const f = format ?? ((v: number) => `${+v.toFixed(3)}${unit ? ` ${unit}` : ''}`)
  const isRec = rec !== undefined && same(value, rec)
  return (
    <div className={cx('bx-param', wide && 'wide')} data-testid={testid}>
      <div className="lab"><span>{label}</span><InfoTip title={label}>{info}</InfoTip><b className="val">{f(value)}{was !== undefined && !same(was, value) && <span className="was">(was {f(was).replace(` ${unit}`, '')})</span>}</b></div>
      <Slider value={value} onChange={onChange} min={min} max={max} step={step} showValue={false} disabled={disabled} disabledReason="wait for the run" ariaLabel={label} testid={testid ? `${testid}-slider` : undefined} />
      {rec !== undefined && <div className={cx('rec', !isRec && 'no', tone)}>{isRec ? `= ${recNote ?? 'recommended'}` : `rec ${f(rec)}${recNote ? ` · ${recNote}` : ''}`}</div>}
    </div>
  )
}

export function ParamSelect({ label, info, value, options, onChange, wide, testid, rec, recNote, disabled }: { label: string; info: string; value: string; options: string[]; onChange: (v: string) => void; wide?: boolean; testid?: string; rec?: string; recNote?: string; disabled?: boolean }) {
  return (
    <div className={cx('bx-param', wide && 'wide')}>
      <div className="lab"><span>{label}</span><InfoTip title={label}>{info}</InfoTip></div>
      <SelectField value={value} onChange={onChange} options={options.map(o => ({ value: o, label: o }))} testid={testid} disabled={disabled} disabledReason="wait for the run" />
      {rec !== undefined && <div className={cx('rec', value !== rec && 'no')}>{value === rec ? `= ${recNote ?? 'recommended'}` : `rec ${rec}`}</div>}
    </div>
  )
}

export function Tiles({ items, columns }: { items: { k: string; v: ReactNode; tone?: 'red' | 'blue' | 'green' | 'amber' | 'purple' }[]; columns?: number }) {
  return <div className="bp-tiles" style={{ gridTemplateColumns: `repeat(${columns ?? items.length}, minmax(0, 1fr))` }} data-testid="stat-tiles">{items.map(t => <div className="bp-tile" key={t.k}><div className="k" title={t.k}>{t.k}</div><div className={cx('v', t.tone && `t-${t.tone}`)}>{t.v}</div></div>)}</div>
}

export function PlotBox({ height, children, testid, className }: { height: number; children: (w: number, h: number) => ReactNode; testid?: string; className?: string }) {
  const [ref, size] = useSize<HTMLDivElement>()
  return <div ref={ref} className={cx('bx-plot', className)} style={{ height }} data-testid={testid}>{size.width > 0 && <svg width={size.width} height={height}>{children(size.width, height)}</svg>}</div>
}

/** A horizontal line the user drags vertically; `toValue` maps a pixel y to a value. */
export function DragH({ y, width, onValue, toValue, colour, label, testid, labelLeft }: { y: number; width: number; onValue: (v: number) => void; toValue: (py: number) => number; colour: string; label: string; testid?: string; labelLeft?: boolean }) {
  const drag = useRef(false)
  const move = (e: React.PointerEvent<SVGRectElement>) => {
    if (!drag.current) return
    const svg = e.currentTarget.ownerSVGElement; if (!svg) return
    onValue(toValue(e.clientY - svg.getBoundingClientRect().top))
  }
  return (
    <g data-testid={testid} className="bx-drag">
      <line x1={0} x2={width} y1={y} y2={y} stroke={colour} strokeWidth={1.4} />
      <text x={labelLeft ? 4 : width - 4} y={y - 3} textAnchor={labelLeft ? 'start' : 'end'} style={{ fill: colour, fontSize: 10, paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3 }}>{label}</text>
      <rect x={0} y={y - 6} width={width} height={12} fill="transparent" style={{ cursor: 'ns-resize' }}
        onPointerDown={e => { drag.current = true; e.currentTarget.setPointerCapture(e.pointerId) }} onPointerMove={move}
        onPointerUp={e => { drag.current = false; e.currentTarget.releasePointerCapture(e.pointerId) }} />
    </g>
  )
}
/** A vertical line dragged horizontally. */
export function DragV({ x, height, onValue, toValue, colour, label, testid }: { x: number; height: number; onValue: (v: number) => void; toValue: (px: number) => number; colour: string; label: string; testid?: string }) {
  const drag = useRef(false)
  const move = (e: React.PointerEvent<SVGRectElement>) => {
    if (!drag.current) return
    const svg = e.currentTarget.ownerSVGElement; if (!svg) return
    onValue(toValue(e.clientX - svg.getBoundingClientRect().left))
  }
  return (
    <g data-testid={testid} className="bx-drag">
      <line x1={x} x2={x} y1={0} y2={height} stroke={colour} strokeWidth={1.6} />
      <text x={x + 5} y={12} style={{ fill: colour, fontSize: 10.5 }}>{label}</text>
      <rect x={x - 7} y={0} width={14} height={height} fill="transparent" style={{ cursor: 'ew-resize' }}
        onPointerDown={e => { drag.current = true; e.currentTarget.setPointerCapture(e.pointerId) }} onPointerMove={move}
        onPointerUp={e => { drag.current = false; e.currentTarget.releasePointerCapture(e.pointerId) }} />
    </g>
  )
}

export const num = (v: unknown, d: number) => (typeof v === 'number' && Number.isFinite(v) ? v : d)
export const str = (v: unknown, d: string) => (typeof v === 'string' ? v : d)
