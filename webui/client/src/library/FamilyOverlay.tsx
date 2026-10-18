/* library-family-actions (the researcher, 2026-10-15): PICK A TRACE in the family overlay and act on it.
 *
 * The overlay is the family page's summary panel: the medoid in the family colour over the members on this page,
 * each read off the recording and centred on its own baseline, stretched to one width, on one measured mV domain
 * (the drawing `MiniTrace` did here before — same rule, same domain). It is drawn in real pixels rather than a
 * stretched viewBox so a click can be HIT-TESTED: the member whose path passes nearest the pointer, within 6 px,
 * is picked; a click on empty plot clears the pick. ↑ / ↓ move the pick between members, Esc clears it.
 *
 * The picked trace is drawn heavy in the family colour, and `PickCaption` names its detection (recording,
 * channel, time, verdict) with three actions: remove from the family, send to Review, open in Explore. No
 * "make exemplar": what a medoid is stays a separate decision. The overlay itself writes nothing. */
import { useMemo, type KeyboardEvent, type MouseEvent } from 'react'
import { scaleLinear } from 'd3'
import { Button } from '../kit'
import { measuredDomain } from '../charts/domain'
import { useSize } from '../charts/useSize'

export interface OverlayTrace { id: string; values: number[] }

/** Hit radius in screen pixels (the prompt's 6 px). */
export const PICK_RADIUS_PX = 6
const MAX_POINTS = 400

/** Distance from (px, py) to the segment a–b. */
function segDist(px: number, py: number, ax: number, ay: number, bx: number, by: number) {
  const dx = bx - ax, dy = by - ay
  const L = dx * dx + dy * dy
  const t = L ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / L)) : 0
  const x = ax + t * dx - px, y = ay + t * dy - py
  return Math.sqrt(x * x + y * y)
}

/** Each trace as screen points, stretched to the width (the members differ in length; the overlay is of shape). */
function toPoints(values: number[], width: number, y: (v: number) => number): [number, number][] {
  const k = values.length
  if (!k) return []
  const step = Math.max(1, Math.floor(k / MAX_POINTS))
  const out: [number, number][] = []
  for (let i = 0; i < k; i += step) {
    const v = values[i]
    if (!Number.isFinite(v)) continue
    out.push([(i / Math.max(1, k - 1)) * width, y(v)])
  }
  return out
}

/** The id of the trace nearest (px, py) within `radius` px, or null. Exported for its rule, not for reuse. */
export function nearestTrace(paths: { id: string; pts: [number, number][] }[], px: number, py: number, radius = PICK_RADIUS_PX): string | null {
  let best: string | null = null, bestD = radius
  for (const p of paths) {
    for (let i = 0; i < p.pts.length; i++) {
      const a = p.pts[i], b = p.pts[Math.min(p.pts.length - 1, i + 1)]
      const d = segDist(px, py, a[0], a[1], b[0], b[1])
      if (d <= bestD) { bestD = d; best = p.id }
    }
  }
  return best
}

const pathOf = (pts: [number, number][]) => pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join('')

export function FamilyOverlay({ medoid, members, colour, picked, onPick, height = 104, title, testid = 'summary-overlay' }: {
  medoid: number[]; members: OverlayTrace[]; colour: string
  picked: string | null; onPick: (id: string | null) => void
  height?: number; title?: string; testid?: string
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const W = Math.max(0, Math.floor(size.width))
  const domain = useMemo(() => measuredDomain(medoid, ...members.map(m => m.values)) ?? [-1, 1] as [number, number], [medoid, members])
  const paths = useMemo(() => {
    if (!W) return { medoid: [] as [number, number][], members: [] as { id: string; pts: [number, number][] }[] }
    const y = scaleLinear().domain(domain).range([height - 2, 2])
    return { medoid: toPoints(medoid, W, y), members: members.map(m => ({ id: m.id, pts: toPoints(m.values, W, y) })) }
  }, [W, domain, height, medoid, members])
  const onClick = (e: MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect()
    onPick(nearestTrace(paths.members, e.clientX - box.left, e.clientY - box.top))
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!members.length) return
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const i = members.findIndex(m => m.id === picked)
      const j = i < 0 ? (e.key === 'ArrowDown' ? 0 : members.length - 1) : (i + (e.key === 'ArrowDown' ? 1 : -1) + members.length) % members.length
      onPick(members[j].id)
    } else if (e.key === 'Escape' && picked) { e.preventDefault(); onPick(null) }
  }
  const on = paths.members.find(p => p.id === picked) ?? null
  return (
    <div ref={ref} tabIndex={0} onKeyDown={onKey} style={{ width: '100%', outline: 'none' }} data-testid={`${testid}-box`}
      aria-label="the members on this page overlaid: click a trace to pick it, ↑ ↓ move the pick, Esc clears it">
      {W > 0 && (
        <svg className="k-mini" width={W} height={height} role="img" aria-label={title ?? 'member overlay'} onClick={onClick}
          style={{ background: 'var(--grey-50, #f7f8fa)', cursor: 'pointer', display: 'block' }} data-testid={testid} data-plot-box
          data-domain={`${domain[0]},${domain[1]}`} data-picked={picked ?? ''}>
          {title && <title>{title}</title>}
          <g data-trace>
            {paths.members.map(p => (
              <path key={p.id} d={pathOf(p.pts)} fill="none" stroke={p.id === picked ? 'rgba(107,114,128,0.2)' : 'rgba(107,114,128,0.45)'} strokeWidth={1}
                data-testid={`overlay-trace-${p.id}`} data-member={p.id} />
            ))}
            <path d={pathOf(paths.medoid)} fill="none" stroke={colour} strokeWidth={1.8} strokeLinejoin="round" opacity={picked ? 0.45 : 1} />
            {on && <path d={pathOf(on.pts)} fill="none" stroke="#111827" strokeWidth={2.6} strokeLinejoin="round" data-testid="overlay-picked-trace" data-member={on.id} />}
          </g>
        </svg>
      )}
    </div>
  )
}

/** What the caption needs of a member: the bridge's own fields, nothing derived. */
export interface PickMember {
  id: string; recording: string; channel: string; onsetH: number; verdict: string
  recordingId?: number | null; startS?: number | null; endS?: number | null
}

const fmtS = (s: number) => (s >= 100 ? s.toFixed(0) : s.toFixed(1))

/** The picked trace, named, with its three actions beside it. */
export function PickCaption({ m, busy, onRemove, onSend, onExplore, onClear }: {
  m: PickMember; busy: boolean
  onRemove: () => void; onSend: () => void; onExplore: () => void; onClear: () => void
}) {
  const judged = m.verdict !== 'unjudged'
  const noSpan = m.recordingId == null || m.startS == null || m.endS == null
  return (
    <div className="k-card" style={{ padding: '8px 10px', marginTop: 6, fontSize: 11.5 }} data-testid="overlay-pick-card" data-member={m.id}>
      <div className="row" style={{ gap: 6, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <b data-testid="overlay-pick-id">{m.id}</b>
        <span className="lib-cap" data-testid="overlay-pick-where">{m.recording} · {m.channel} · {m.onsetH.toFixed(1)} h{!noSpan ? ` (${fmtS(m.startS!)}–${fmtS(m.endS!)} s)` : ''}</span>
        <span className="lib-cap" data-testid="overlay-pick-verdict" style={{ color: judged ? undefined : '#c27400' }}>{m.verdict}</span>
        <span style={{ marginLeft: 'auto' }} />
        <Button size="sm" variant="link" testid="overlay-pick-clear" onClick={onClear}>clear</Button>
      </div>
      <div className="row" style={{ gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
        <Button size="sm" icon="minus" testid="overlay-pick-remove" disabled={busy} disabledReason="writing…" onClick={onRemove}>Remove from family</Button>
        <Button size="sm" icon="checklist" testid="overlay-pick-review" disabled={busy || judged} disabledReason={busy ? 'writing…' : `already judged (${m.verdict}): Review holds its verdict`} onClick={onSend}>Send to Review</Button>
        <Button size="sm" icon="external" testid="overlay-pick-explore" disabled={noSpan} disabledReason="this member carries no recording span" onClick={onExplore}>Open in Explore</Button>
      </div>
    </div>
  )
}
