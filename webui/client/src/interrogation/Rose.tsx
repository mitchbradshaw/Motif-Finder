/* The rose (frame interrogation-2: "Each fall as one angle"). Every fall becomes one angle — the arctangent
 * of its steepest slope, with −45° = −0.1 mV/s — drawn on a 0° … −90° quadrant with the radius set by event
 * order. The kit has no polar plot; requested in webui/pages/requests/interrogation.md. */
import { ColourDot, fmtInt } from '../kit'
import { FAMILY_COLOURS } from '../fixtures/canon'
import { VERDICT_COLOUR, angleOf, type InterrogationMember } from '../fixtures/interrogation'

const SPOKES = [0, -15, -30, -45, -60, -75, -90]
const RAMP = ['#5856D6', '#E85AAD', '#E8900C']

function rampColour(u: number) {
  const t = Math.max(0, Math.min(1, u)) * (RAMP.length - 1)
  const i = Math.min(RAMP.length - 2, Math.floor(t))
  const f = t - i
  const hex = (c: string) => [1, 3, 5].map(k => parseInt(c.slice(k, k + 2), 16))
  const [r0, g0, b0] = hex(RAMP[i]), [r1, g1, b1] = hex(RAMP[i + 1])
  const mix = (a: number, b: number) => Math.round(a + (b - a) * f)
  return `rgb(${mix(r0, r1)}, ${mix(g0, g1)}, ${mix(b0, b1)})`
}

export function Rose({ events, selected, colourBy, onSelect }: {
  events: InterrogationMember[]; selected: string | null; colourBy: string; onSelect: (id: string) => void
}) {
  const W = 420, H = 300, cx = 40, cy = 30, R = 236
  const depths = events.map(e => e.depth_mV)
  const dLo = Math.min(...depths, 0.12), dHi = Math.max(...depths, 0.40)
  const recordings = [...new Set(events.map(e => e.recording))]

  const colourOf = (e: InterrogationMember) =>
    colourBy === 'recording' ? (FAMILY_COLOURS[`F-0${(recordings.indexOf(e.recording) % 9) + 1}`] ?? 'var(--blue)')
      : colourBy === 'verdict' ? VERDICT_COLOUR[e.verdict]
        : rampColour((e.depth_mV - dLo) / Math.max(1e-6, dHi - dLo))

  const at = (deg: number, r: number) => {
    const rad = (deg * Math.PI) / 180
    return [cx + r * Math.cos(rad), cy - r * Math.sin(rad)] as [number, number]
  }
  const sel = events.find(e => e.id === selected)

  return (
    <div className="ig-rose" data-testid="rose">
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img"
        aria-label={`rose of ${events.length} fall angles, 0 to −90 degrees`}>
        {/* quadrant arc */}
        <path d={`M ${at(0, R)[0]} ${at(0, R)[1]} A ${R} ${R} 0 0 1 ${at(-90, R)[0]} ${at(-90, R)[1]}`} fill="none" stroke="var(--grey-200)" />
        {SPOKES.map(s => {
          const [x2, y2] = at(s, R)
          const [lx, ly] = at(s, R + 16)
          return (
            <g key={s}>
              <line x1={cx} y1={cy} x2={x2} y2={y2} stroke={s % 45 === 0 ? '#c8ccd4' : 'var(--grey-100)'} />
              <text x={lx} y={ly + 3} textAnchor={s <= -75 ? 'middle' : 'start'}>{s === 0 ? '0°' : `−${Math.abs(s)}°`}</text>
            </g>
          )
        })}
        {events.map((e, i) => {
          const a = angleOf(e.max_slope)
          const r = R * (0.24 + 0.72 * (events.length === 1 ? 0.5 : i / (events.length - 1)))
          const [x, y] = at(a, r)
          const on = e.id === selected
          return (
            <g key={e.id} style={{ cursor: 'pointer' }} onClick={() => onSelect(e.id)} data-testid={`rose-point-${e.id}`}>
              <circle cx={x} cy={y} r={on ? 7 : 5} fill={colourOf(e)} fillOpacity={on ? 1 : 0.85} />
              {on && <circle cx={x} cy={y} r={10} fill="none" stroke="var(--blue)" strokeWidth={2} />}
              <title>{`${e.id} · ${a.toFixed(1)}° · ${e.depth_mV.toFixed(3)} mV · event ${i + 1} of ${events.length}`}</title>
            </g>
          )
        })}
      </svg>
      <div className="ig-ramp">
        {colourBy === 'depth' && (
          <>
            <span>depth, mV</span>
            <span className="bar" />
            <span style={{ display: 'flex', justifyContent: 'space-between', width: 96 }}><span>{dLo.toFixed(2)}</span><span>{dHi.toFixed(2)}</span></span>
          </>
        )}
        {colourBy === 'recording' && recordings.map((r, i) => (
          <span key={r} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <ColourDot colour={FAMILY_COLOURS[`F-0${(i % 9) + 1}`] ?? 'var(--blue)'} />{r}
          </span>
        ))}
        {colourBy === 'verdict' && (['seed', 'interesting', 'unadjudicated', 'artifact'] as const).map(v => (
          <span key={v} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><ColourDot colour={VERDICT_COLOUR[v]} />{v}</span>
        ))}
        {sel && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, marginTop: 6, color: 'var(--blue-600)' }} data-testid="rose-selected">
            <ColourDot colour="var(--blue)" ring />event {events.indexOf(sel) + 1} · {angleOf(sel.max_slope).toFixed(1).replace('-', '−')}°
          </span>
        )}
        <span style={{ marginTop: 4 }}>{fmtInt(events.length)} events</span>
      </div>
    </div>
  )
}
