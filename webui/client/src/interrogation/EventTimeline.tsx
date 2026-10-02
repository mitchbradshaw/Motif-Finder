/* "When events happened" (frame interrogation-3): one lane per recording, hours since that recording's
 * start (§0), one tick per event whose height is the event's depth/amplitude. The kit has no
 * variable-height event rail; requested in webui/pages/requests/interrogation.md.
 *
 * fixup-e: `valueOf` may return null — the event was NOT measured for the plotted height (a drop's rise
 * time, an event that never recovered). Such an event is drawn as a hollow stub at the baseline and titled
 * "not measured", never as a tick of height 0 among real heights.
 *
 * fixup-h (`03` I8): the τ per recording is Kendall's, computed by the core over the events of the lane whose
 * height is measured (`POST /api/interrogation/trend`). It used to be read from a fixture keyed by fixture
 * recording names, so every live recording printed "no trend test". A lane that cannot be tested says why. */
import { useEffect, useMemo, useState } from 'react'
import { getTimelineTrend, type LaneTrend } from '../api'
import { Tooltip } from '../kit'
import type { InterrogationMember } from '../fixtures/interrogation'

export function EventTimeline({ members, heightBy, valueOf, unit = 'mV', colourOf, selected, onSelect }: {
  members: InterrogationMember[]
  heightBy: string
  /** what the tick height is, so the wiring's "timeline height" slot really changes the lanes; null = not measured */
  valueOf?: (m: InterrogationMember) => number | null
  unit?: string
  colourOf: (m: InterrogationMember) => string
  selected?: string | null
  onSelect?: (id: string) => void
}) {
  const recordings = [...new Set(members.map(m => m.recording))]
  const height = valueOf ?? ((m: InterrogationMember) => m.depth_mV)
  const measured = members.map(height).filter((v): v is number => v !== null && Number.isFinite(v))
  const nMissing = members.length - measured.length
  const hLo = Math.min(0, ...measured)
  const hSpan = Math.max(1e-6, Math.max(...measured) - hLo)
  const lanes = useMemo(() => Object.fromEntries(recordings.map(rec => {
    const xs = members.filter(m => m.recording === rec)
    return [rec, { t: xs.map(m => m.onset_h), v: xs.map(m => { const v = height(m); return v === null || !Number.isFinite(v) ? null : v }) }]
  })), [members, heightBy])   // eslint-disable-line react-hooks/exhaustive-deps
  const [trend, setTrend] = useState<Record<string, LaneTrend> | null>(null)
  const [trendError, setTrendError] = useState<string | null>(null)
  const lanesKey = JSON.stringify(lanes)
  useEffect(() => {
    let alive = true
    setTrend(null); setTrendError(null)
    getTimelineTrend(lanes).then(r => { if (alive) setTrend(r.trend) }, e => { if (alive) setTrendError(String(e?.message ?? e)) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lanesKey])
  return (
    <div className="ig-tl" data-testid="timeline">
      {recordings.map(rec => {
        const xs = members.filter(m => m.recording === rec)
        const lo = Math.floor(Math.min(...xs.map(m => m.onset_h)))
        const hi = Math.ceil(Math.max(...xs.map(m => m.onset_h)))
        const span = Math.max(1, hi - lo)
        const t = trend?.[rec]
        return (
          <div key={rec} data-testid={`timeline-${rec}`}>
            <div className="hd">
              <span className="nm">{rec}</span>
              <span>{lo} – {hi} h</span>
              <span className="tau" data-testid="timeline-tau">{trendError ? 'trend not computed' : !t ? '…' : t.tau == null ? (t.note ?? `n ${t.n} · not tested`) : `τ ${t.tau.toFixed(2).replace('-', '−')} · p ${t.p == null ? '—' : t.p < 0.001 ? '< 0.001' : t.p.toFixed(3)} · n ${t.n}`}</span>
            </div>
            <svg className="lane" width="100%" height={54} viewBox="0 0 400 54" preserveAspectRatio="none" role="img" aria-label={`${xs.length} events in ${rec}`}>
              {xs.map(m => {
                const x = 6 + ((m.onset_h - lo) / span) * 388
                const v = height(m)
                const on = m.id === selected
                if (v === null || !Number.isFinite(v)) {
                  return (
                    <rect key={m.id} x={x} y={44} width={on ? 4 : 2.6} height={6} rx={1} fill="none" stroke="#9ca3af" strokeWidth={0.8} strokeDasharray="1.5 1"
                      style={onSelect ? { cursor: 'pointer' } : undefined} onClick={onSelect ? () => onSelect(m.id) : undefined} data-testid="timeline-not-measured">
                      <title>{`${m.id} · ${m.onset_h.toFixed(2)} h · ${heightBy} not measured`}</title>
                    </rect>
                  )
                }
                const h = 6 + (Math.max(0, v - hLo) / hSpan) * 40
                return (
                  <rect key={m.id} x={x} y={50 - h} width={on ? 4 : 2.6} height={h} rx={1} fill={colourOf(m)} opacity={on ? 1 : 0.9}
                    style={onSelect ? { cursor: 'pointer' } : undefined} onClick={onSelect ? () => onSelect(m.id) : undefined}>
                    <title>{`${m.id} · ${m.onset_h.toFixed(2)} h · ${heightBy} ${v.toFixed(3)} ${unit}`}</title>
                  </rect>
                )
              })}
            </svg>
          </div>
        )
      })}
      <div className="ig-foot">
        <Tooltip content="τ is Kendall's rank correlation between onset time and the plotted height, per recording. A recording with fewer than 3 events is not tested.">
          <span>height = {heightBy} · τ per recording</span>
        </Tooltip>
        {nMissing > 0 && <span data-testid="timeline-missing"> · {nMissing} of {members.length} not measured for {heightBy} (hollow stubs)</span>}
      </div>
    </div>
  )
}
