/* fixup-j: a detector's own account of what it decided. `detection.summation_threshold` ships every
   stage of the Dehshibi funnel in its payload (serialize.py `_funnel`): the candidate regions cut
   from the score's extrema, which of them the signal confirmed, which it set aside, the envelope
   regions, and the spikes. This draws them as one strip per stage on the span's own time axis, with
   the count that was found. The honest minimum — the visual idiom for every block's process view is
   prompt H's; this only refuses to hide the stages behind a single row of spans. Draws only what the
   payload carries. */
import type { SpansetPayload } from '../api'

export interface FunnelStage { key: string; label: string; n: number; capped: boolean; start_s: number[]; end_s: number[] }
export interface FunnelPayload { stages: FunnelStage[]; chunks_s: [number, number][]; peaks_s: number[]; valleys_s: number[] }
export type SpansetWithFunnel = SpansetPayload & { funnel?: FunnelPayload }

export function funnelOf(p: unknown): FunnelPayload | null {
  const f = (p as SpansetWithFunnel | null)?.funnel
  return f && Array.isArray(f.stages) && f.stages.length > 0 ? f : null
}

const COLOUR: Record<string, string> = { B: '#7b6fd0', C: '#2f9e44', D: '#868e96', R: '#f08c00', R_kept: '#e8900c', S: '#e03131' }
const W = 1000, H = 16

function fmtSpan(s: number): string {
  return s >= 7200 ? `${(s / 3600).toFixed(1)} h` : s >= 120 ? `${(s / 60).toFixed(0)} min` : `${s.toFixed(0)} s`
}

export function DetectorFunnel({ funnel }: { funnel: FunnelPayload }) {
  const lo = funnel.chunks_s.length ? Math.min(...funnel.chunks_s.map(c => c[0])) : Math.min(...funnel.stages.flatMap(s => s.start_s), 0)
  const hi = funnel.chunks_s.length ? Math.max(...funnel.chunks_s.map(c => c[1])) : Math.max(...funnel.stages.flatMap(s => s.end_s), 1)
  const span = Math.max(hi - lo, 1e-9)
  const x = (t: number) => ((t - lo) / span) * W
  const n = (key: string) => funnel.stages.find(s => s.key === key)?.n ?? 0
  const covered = (() => {
    const s = funnel.stages.find(st => st.key === 'S')
    return s ? s.start_s.reduce((acc, a, i) => acc + (s.end_s[i] - a), 0) / span : 0
  })()
  return (
    <div data-testid="detector-funnel" style={{ marginTop: 12 }}>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>What the detector decided, stage by stage</h3>
        <span className="sg" style={{ marginLeft: 'auto' }}>{funnel.chunks_s.length} window{funnel.chunks_s.length === 1 ? '' : 's'} · {fmtSpan(span)}</span></div>
      <div className="mono small" data-testid="funnel-summary" style={{ margin: '4px 0 8px' }}>
        {n('B')} candidate regions → {n('C')} confirmed by the signal, {n('D')} set aside · {n('R')} envelope regions, {n('R_kept')} kept → <b>{n('S')} spikes</b>, covering {(100 * covered).toFixed(0)}% of the span
      </div>
      {funnel.stages.map(st => (
        <div key={st.key} data-testid={`funnel-stage-${st.key}`} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          <div className="small" style={{ width: 330, flex: '0 0 330px', color: COLOUR[st.key] ?? '#555', textAlign: 'right' }} title={st.label}>
            <span className="mono" style={{ fontWeight: 600 }}>{st.n}</span> {st.label}{st.capped ? ` · first ${st.start_s.length} drawn` : ''}
          </div>
          <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: '100%', height: H, background: 'var(--panel-2, #f3f4f6)' }} role="img"
               aria-label={`${st.n} ${st.label}`} data-render="funnel-strip">
            {funnel.chunks_s.slice(1).map((c, i) => <line key={`w${i}`} x1={x(c[0])} x2={x(c[0])} y1={0} y2={H} stroke="#9ca3af" strokeWidth={1} strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />)}
            {st.start_s.map((a, i) => (
              <rect key={i} x={x(a)} y={2} width={Math.max(x(st.end_s[i]) - x(a), 1)} height={H - 4} fill={COLOUR[st.key] ?? '#555'} fillOpacity={0.8}>
                <title>{`${st.key} ${i + 1}: ${a.toFixed(0)}–${st.end_s[i].toFixed(0)} s (${(st.end_s[i] - a).toFixed(0)} s)`}</title>
              </rect>
            ))}
          </svg>
        </div>
      ))}
      <div className="muted small" style={{ marginTop: 4 }}>
        Dashed lines are window boundaries: each window is normalised and cut on its own. A spike is a confirmed candidate widened to the envelope regions it meets; overlapping results are merged.
      </div>
    </div>
  )
}
