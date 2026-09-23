/* The reference bar (fixup-c): the page's shared scale, drawn beside a card whose own trace is on its own
 * measured domain. The bar is the same on every card of a page — a track with a tick per decade — and the card
 * marks where its own peak sits on it. So a micro-volt family and a millivolt one never look alike: their
 * shapes are each legible on their own axes, and the bar says how big each is against the rest of the page.
 * The scale and the position come from `charts/domain.ts`; this file only draws them. */
import { referencePosition, type ReferenceScale } from './domain'

/** Short mV figure for a decade or a peak: 0.01, 0.1, 1, 10, 100, and 0.025 / 15.6 for a peak. */
export function fmtRef(v: number): string {
  if (!Number.isFinite(v)) return '—'
  const a = Math.abs(v)
  if (a >= 100) return String(Math.round(v))
  if (a >= 1) return String(+v.toPrecision(3))
  return String(+v.toPrecision(2))
}

/** The words every bar and every page legend use, so they cannot drift apart. */
export function referenceWords(scale: ReferenceScale | null): string {
  return scale ? `one shared log scale for the page, ${fmtRef(scale.lo)}–${fmtRef(scale.hi)} mV, a tick per decade` : 'no card on this page has a peak to place'
}

export function ReferenceBar({ scale, peak, height, colour = 'var(--text)', what = 'this card', testid = 'reference-bar' }: {
  scale: ReferenceScale | null; peak: number | null | undefined; height: number; colour?: string
  /** what the marker is, for the tooltip: "F-01", "this candidate" */
  what?: string; testid?: string
}) {
  const W = 12, PAD = 3
  const pos = referencePosition(scale, peak)
  const yOf = (f: number) => PAD + (1 - f) * (height - 2 * PAD)
  const title = !scale ? `no shared scale on this page`
    : pos === null ? `${what} has no peak to place on the page's shared scale (${referenceWords(scale)})`
      : `${what} peaks at ${fmtRef(peak as number)} mV · the bar is ${referenceWords(scale)}; the mark is where ${what} sits on it`
  return (
    <svg className="k-refbar" width={W} height={height} viewBox={`0 0 ${W} ${height}`} role="img" aria-label={title}
      data-testid={testid} data-position={pos === null ? '' : pos.toFixed(3)} style={{ flex: 'none', display: 'block' }}>
      <title>{title}</title>
      <line x1={W / 2} x2={W / 2} y1={PAD} y2={height - PAD} stroke="var(--border-strong, #c9ced6)" strokeWidth={2} strokeLinecap="round" />
      {scale && scale.decades.map((d, i) => {
        const f = scale.decades.length > 1 ? i / (scale.decades.length - 1) : 0
        return <line key={d} x1={W / 2 - 2.5} x2={W / 2 + 2.5} y1={yOf(f)} y2={yOf(f)} stroke="var(--muted-2, #9aa3ae)" strokeWidth={1} />
      })}
      {pos !== null && <rect x={1} y={yOf(pos) - 1.5} width={W - 2} height={3} rx={1} fill={colour} data-testid={`${testid}-mark`} />}
    </svg>
  )
}
