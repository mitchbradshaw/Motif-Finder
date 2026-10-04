/* fixup-AD: the *Suspected artifact* card on Review's inspector (QUESTIONS.md Round 12 Q3).
 *
 * In plain words: the machine noticed that this family member looks almost exactly like what another electrode
 * recorded at the same moment — the signature of one wire picking up another rather than two events. It only
 * FLAGS; you decide. To decide you need what the agent's Q40d gallery showed: every channel of the recording over
 * the member's span (plus one span each side), in TRUE millivolts on ONE shared axis — so a 25 mV event beside a
 * 0.2 mV "twin" looks like what it is — the member bold, and beside each flagging sibling its r, lag, amplitude
 * ratio and how it did against chance (the same sibling at K random other times). Each trace has only its own
 * median taken off, so the traces sit on one baseline without changing their size.
 * (`webui/screenshots/fixup/Q40d/examples_gallery_mV.png` is the picture this matches.) */
import { useMemo } from 'react'
import { scaleLinear } from 'd3'
import { InfoTip } from '../kit'
import { EnvelopePath, TimeAxis } from '../charts/primitives'
import { useSize } from '../charts/useSize'
import type { SuspectedArtifactPanel } from '../api/review'

const PALETTE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
const H = 260
const PAD_L = 44
const PAD_B = 22

function median(v: (number | null)[]): number {
  const xs = v.filter((x): x is number => x != null && Number.isFinite(x)).sort((a, b) => a - b)
  if (!xs.length) return 0
  const m = xs.length >> 1
  return xs.length % 2 ? xs[m] : (xs[m - 1] + xs[m]) / 2
}

const fmtR = (r: number | null) => (r == null ? '—' : `${r >= 0 ? '+' : ''}${r.toFixed(3)}`)

export function SuspectedArtifactCard({ p }: { p: SuspectedArtifactPanel }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const width = Math.max(320, size.width || 640)
  const lines = useMemo(() => p.channels.map((c, i) => {
    const m = median(c.trace.v)
    return { ...c, colour: c.member ? 'var(--text)' : PALETTE[i % PALETTE.length], v: c.trace.v.map(x => (x == null ? null : x - m)) }
  }), [p])
  const all = lines.flatMap(l => l.v.filter((x): x is number => x != null))
  const lo = all.length ? Math.min(...all) : -1
  const hi = all.length ? Math.max(...all) : 1
  const padY = (hi - lo) * 0.06 || 0.1
  const x = scaleLinear().domain([p.t0_s, p.t1_s]).range([PAD_L, width - 6])
  const y = scaleLinear().domain([lo - padY, hi + padY]).range([H - PAD_B, 6])
  const yt = y.ticks(5)
  const flagging = lines.filter(l => l.flagging)
  const drawn = lines.filter(l => l.trace.t.length)
  const undrawn = lines.filter(l => !l.trace.t.length)
  return (
    <section className="rv-card" data-testid="suspected-artifact-card" data-channels={p.channels.length} data-unit={p.unit ?? ''}>
      <div className="rv-card-head">
        <h3>Suspected artifact · every channel</h3>
        <InfoTip title="What you are deciding">
          The cross-channel classifier flagged {p.member}{p.family ? ` (${p.family})` : ''}: on the electrode(s) named below
          the same shape appears at the same instant with |r| ≥ 0.98, more alike than the same electrode at 100 random
          other times, and both swings clear the noise floor. That is what one wire picking up another looks like — or a
          coincidence the test let through. Every channel is drawn in {p.unit ?? 'its unit'} on ONE axis, each minus its
          own median, the member bold, its span shaded, one span of padding each side. {p.verdictNote}
        </InfoTip>
        <span className="grow" />
        <span className="mono muted sm" data-testid="suspected-artifact-axis">one shared axis · {p.unit ?? 'unit undeclared'} · each trace minus its own median</span>
      </div>
      <div ref={ref} className="rv-plot">
        <svg width={width} height={H} role="img" aria-label="every channel of the recording over the member's span, one shared millivolt axis" data-testid="suspected-artifact-plot">
          <rect x={x(p.span_s[0])} y={6} width={Math.max(1, x(p.span_s[1]) - x(p.span_s[0]))} height={H - PAD_B - 6} fill="var(--amber-bg, #fdf3d0)" />
          {yt.map(v => (
            <g key={v}>
              <line x1={PAD_L} x2={width - 6} y1={y(v)} y2={y(v)} stroke="var(--line, #e6e6e6)" strokeWidth={0.5} />
              <text x={PAD_L - 4} y={y(v) + 3} textAnchor="end" style={{ fontSize: 9 }}>{v}</text>
            </g>
          ))}
          <text x={4} y={12} style={{ fontSize: 9 }}>{p.unit ?? ''}</text>
          {drawn.filter(l => !l.member).map(l => (
            <EnvelopePath key={l.recording_id} t={l.trace.t} v={l.v} x={x} y={y} stroke={l.colour}
              width={l.flagging ? 1.4 : 0.8} opacity={l.flagging ? 1 : 0.45} testid={`sa-trace-${l.channel_index}`} />
          ))}
          {drawn.filter(l => l.member).map(l => (
            <EnvelopePath key={l.recording_id} t={l.trace.t} v={l.v} x={x} y={y} stroke={l.colour} width={2.4} testid="sa-trace-member" />
          ))}
          <TimeAxis x={x} y={H - PAD_B} t0={p.t0_s} t1={p.t1_s} n={6} />
        </svg>
      </div>
      <div className="row" style={{ gap: 10, flexWrap: 'wrap', marginTop: 6 }} data-testid="suspected-artifact-flags">
        {lines.filter(l => l.member).map(l => (
          <span key="m" className="mono sm" style={{ fontWeight: 700 }}>{l.channel} · the member ({p.member})</span>
        ))}
        {flagging.map(l => (
          <span key={l.recording_id} className="mono sm" style={{ color: l.colour }} data-testid={`sa-flag-${l.channel_index}`}>
            {l.channel}: r {fmtR(l.r)} · lag {l.lag_s == null ? '—' : `${l.lag_s >= 0 ? '+' : ''}${l.lag_s.toFixed(1)} s`} · amp ×{l.amplitude_ratio == null ? '—' : l.amplitude_ratio.toFixed(2)}
            {' · '}chance {l.chance?.percentile == null ? '—' : `${l.chance.percentile.toFixed(0)}th pct of ${l.chance.k}`}
            {l.other_member ? ` · member ${l.other_member}` : ' · no member there'}
          </span>
        ))}
        {undrawn.length > 0 && <span className="mono sm muted">not drawn: {undrawn.map(l => `${l.channel} (${l.trace.reason ?? 'no samples'})`).join(' · ')}</span>}
      </div>
    </section>
  )
}
