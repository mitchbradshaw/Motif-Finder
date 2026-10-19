/* Gauge (discovery-coverage, 2026-10-19; colours confirmed by the researcher, Q44): a small SVG ring split into a
 * good arc, a bad arc and a grey remainder, for "how the humans judged this". Counts only: no percentage on the face;
 * the tooltip (a native <title>, so it works in a table row and a button alike) says the counts and the total. An
 * empty total draws an empty ring and says so. The caller passes the counts and the words; the ring computes nothing
 * but the arc lengths. */
import type { CSSProperties } from 'react'

export interface GaugeProps {
  /** the green arc's count (e.g. interesting + seed) */
  good: number
  /** the red arc's count (e.g. not interesting + artifact) */
  bad: number
  /** the whole: good + bad + the grey remainder (e.g. unsure) */
  total: number
  /** the tooltip, line by line; the empty ring's tooltip when `total` is 0 */
  title: string
  /** what an empty ring says beside itself */
  emptyLabel?: string
  size?: number
  stroke?: number
  testid?: string
  style?: CSSProperties
}

export function Gauge({ good, bad, total, title, emptyLabel = 'no verdicts yet', size = 22, stroke = 4, testid, style }: GaugeProps) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const empty = !(total > 0)
  const g = empty ? 0 : Math.max(0, Math.min(1, good / total))
  const b = empty ? 0 : Math.max(0, Math.min(1 - g, bad / total))
  const ring = (frac: number, offset: number, colour: string, key: string) => frac > 0
    ? <circle key={key} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={colour} strokeWidth={stroke}
        strokeDasharray={`${frac * c} ${c}`} strokeDashoffset={-offset * c} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
    : null
  return (
    <span className="k-gauge" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, ...style }} data-testid={testid}
          data-empty={empty ? '1' : '0'} data-good={good} data-bad={bad} data-total={total} title={title}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={title}>
        <title>{title}</title>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={empty ? 'var(--grey-200)' : 'var(--muted-2)'} strokeWidth={stroke}
          strokeDasharray={empty ? '2 2' : undefined} />
        {ring(g, 0, 'var(--green)', 'g')}
        {ring(b, g, 'var(--red)', 'b')}
      </svg>
      {empty && emptyLabel && <span className="muted small">{emptyLabel}</span>}
    </span>
  )
}
