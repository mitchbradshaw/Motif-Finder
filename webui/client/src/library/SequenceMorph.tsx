/* Round-B B2: the "morph" readout on Library › Sequences (GET /api/library/sequence-morph, core
 * `Working.library.morph`).
 *
 * In plain words: like a flip-book, a sequence MORPHS when each step changes the shape a little while the first and
 * last events are far apart. Per sequence: the share of consecutive steps whose shape distance is smaller than the
 * first-to-last distance, against the same events in shuffled order (seeded) — null mean, 95 % band, one-sided p.
 * The summary line counts the sequences that beat their null at p < 0.05 against the number expected by chance.
 * The step-size companion (2026-10-28) asks a related, weaker question on the same orders, which short sequences can
 * answer: is the mean step between neighbouring events smaller than a shuffled order's? Persistence (runs of like
 * events) passes it as well as a steady morph, so its reading never says "morphs". Every number is the bridge's; the
 * page only lays them out. */
import { useEffect, useState } from 'react'
import { InfoTip, fmtInt } from '../kit'
import { getLibrarySequenceMorph, type LibSeqMorph } from '../api'
import { LoadFailed, Loading } from './chrome'

const f2 = (v: number | null) => (v == null ? '—' : v.toFixed(2))
const fp = (v: number | null) => (v == null ? '—' : v < 0.001 ? '< 0.001' : v.toFixed(3))
const th: React.CSSProperties = { textAlign: 'left', padding: '3px 8px', borderBottom: '1px solid var(--grey-200, #e5e7eb)', fontWeight: 600, position: 'sticky', top: 0, background: 'var(--surface, #fff)' }
const td: React.CSSProperties = { padding: '2px 8px', borderBottom: '1px solid var(--grey-100, #f3f4f6)' }

/** `family` set: that family's sequences, every row shown. Unset: every stored sequence, the rows folded. */
export function SequenceMorph({ family, grouping }: { family?: string; grouping?: string }) {
  const [data, setData] = useState<LibSeqMorph | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let off = false
    setError(null); setData(null)
    getLibrarySequenceMorph(family, grouping).then(d => { if (!off) setData(d) }).catch((e: Error) => { if (!off) setError(e) })
    return () => { off = true }
  }, [family, grouping, tick])
  const title = family ? 'Does the shape morph along the sequence?' : 'Morph readout over every stored sequence'
  return (
    <div className="k-card" style={{ padding: '12px 14px' }} data-testid="sequence-morph">
      <div className="row" style={{ gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="lib-h">{title}</span>
        <InfoTip title="the morph readout" testid="sequence-morph-info">
          Like a flip-book: a sequence morphs when each step changes the shape a little while the first and last events are far
          apart. The morph fraction is the share of consecutive steps whose shape distance is smaller than the first-to-last
          distance (1 = a steady morph). The null is the same events in shuffled order; p is how often a shuffled order scores at
          least as high. The step size asks a related, weaker question that short sequences can answer: are neighbouring events
          more alike than random pairs (ratio below 1)? A steady morph passes it, but so do runs of near-identical events; it
          does not tell the two apart. Both p values come from the same orders. {data ? `Distance: ${data.distance}. ${data.rule} ${data.stepRule}` : ''}
        </InfoTip>
      </div>
      {error && <LoadFailed what="the morph readout" error={error} onRetry={() => setTick(t => t + 1)} />}
      {!error && !data && <Loading height={60} testid="sequence-morph-loading" />}
      {data && <>
        <div className="lib-cap" style={{ marginTop: 4 }} data-testid="sequence-morph-summary"
          data-beat={data.summary.nBeat} data-tested={data.summary.nTested} data-expected={data.summary.expected.toFixed(2)}>
          <b>{fmtInt(data.summary.nBeat)}</b> of {fmtInt(data.summary.nTested)} testable sequences morph more than their shuffled order at
          p &lt; {data.summary.alpha}, against <b>{data.summary.expected.toFixed(1)}</b> expected by chance
          {data.summary.nSequences > data.summary.nTested ? ` · ${fmtInt(data.summary.nSequences - data.summary.nTested)} of ${fmtInt(data.summary.nSequences)} not testable (too short for the readout to reach p < ${data.summary.alpha}, or an element flat or without a waveform)` : ''}
          {' '}· {fmtInt(data.draws)} seeded shuffles per sequence, or every order when there are fewer
        </div>
        <div className="lib-cap" style={{ marginTop: 2 }} data-testid="sequence-morph-steps-summary"
          data-beat={data.summary.steps.nBeat} data-tested={data.summary.steps.nTested} data-expected={data.summary.steps.expected.toFixed(2)}>
          Step size: <b>{fmtInt(data.summary.steps.nBeat)}</b> of {fmtInt(data.summary.steps.nTested)} testable sequences take smaller steps
          than their shuffled order at p &lt; {data.summary.alpha}, against <b>{data.summary.steps.expected.toFixed(1)}</b> expected by chance
          {data.summary.nSequences > data.summary.steps.nTested ? ` · ${fmtInt(data.summary.nSequences - data.summary.steps.nTested)} not testable (under five elements, a null that cannot reach p < ${data.summary.alpha}, or not scored)` : ''}
        </div>
        {family ? <MorphTable data={data} /> : (
          <details style={{ marginTop: 6 }} data-testid="sequence-morph-rows">
            <summary className="lib-cap" style={{ cursor: 'pointer' }}>every sequence · {fmtInt(data.rows.length)} rows</summary>
            <MorphTable data={data} />
          </details>
        )}
      </>}
    </div>
  )
}

function MorphTable({ data }: { data: LibSeqMorph }) {
  if (!data.rows.length) return <div className="lib-cap" style={{ marginTop: 6 }} data-testid="sequence-morph-empty">no sequence to read</div>
  return (
    <div style={{ overflow: 'auto', maxHeight: 320, marginTop: 6 }}>
      <table className="mono" style={{ borderCollapse: 'collapse', fontSize: 11.5 }} data-testid="sequence-morph-table">
        <thead><tr><th style={th}>sequence</th><th style={th}>n</th><th style={th}>morph fraction</th><th style={th}>shuffled null [95 % band]</th><th style={th}>p</th><th style={th}>step ratio · shuffled [95 % band]</th><th style={th}>p</th><th style={th}>reading</th></tr></thead>
        <tbody>
          {data.rows.map(r => {
            const beat = r.tested && r.p != null && r.p < data.summary.alpha
            const s = r.steps
            const sBeat = !!s && s.tested && s.p != null && s.p < data.summary.alpha
            const reading = r.fraction == null ? (r.note ?? 'not scored')
              : !r.tested ? `not testable · ${r.note ?? ''}`
              : beat ? 'morphs more than shuffled' : 'not told apart from shuffled'
            const stepReading = !s ? '' : !s.tested ? `steps: not testable · ${s.note ?? ''}`
              : sBeat ? 'steps: smaller than shuffled' : 'steps: not told apart from shuffled'
            // the band is of the shuffled mean step; shown as ratios to the shuffled mean, like the observed step
            const band = (v: number | null) => (s && v != null && s.nullMean ? v / s.nullMean : null)
            return (
              <tr key={r.sequenceId} data-testid="sequence-morph-row" data-beat={beat ? 1 : 0} data-tested={r.tested ? 1 : 0}
                data-steps-beat={sBeat ? 1 : 0} data-steps-tested={s?.tested ? 1 : 0}>
                <td style={td} title={r.labels.join(' → ')}>{r.id}{r.recording ? <span className="muted"> · {r.recording}</span> : null}</td>
                <td style={{ ...td, textAlign: 'right' }}>{r.nElements}</td>
                <td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>{f2(r.fraction)}</td>
                <td style={td}>{r.fraction == null ? '—' : <>{f2(r.nullMean)} <span className="muted">[{f2(r.lo)}–{f2(r.hi)}]</span> <span className="muted">· {r.exact ? `all ${fmtInt(r.nDraws)} orders` : `${fmtInt(r.nDraws)} shuffles`}</span></>}</td>
                <td style={{ ...td, textAlign: 'right' }}>{fp(r.p)}</td>
                <td style={td} data-testid="sequence-morph-step">{!s ? '—' : <><b>{f2(s.ratio)}</b> <span className="muted">[{f2(band(s.lo))}–{f2(band(s.hi))}]</span></>}</td>
                <td style={{ ...td, textAlign: 'right' }}>{s ? fp(s.p) : '—'}</td>
                <td style={{ ...td, color: beat || sBeat ? 'var(--amber-700, #b45309)' : undefined, fontWeight: beat || sBeat ? 600 : 400, whiteSpace: 'normal', maxWidth: 420 }}>
                  {reading}{stepReading ? <><br />{stepReading}</> : null}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
