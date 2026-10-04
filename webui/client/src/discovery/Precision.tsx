/* fixup-X — Q-D2's two precision figures, each with its rule (QUESTIONS.md Q-D2, answered 2026-09-23).
 *
 * (a) containment over the window labels: does the detector fire where a human saw something?
 * (c) extent agreement over the event-shaped rows (§4.6): does it get the extent right? Printed with the width
 *     distribution of the rows it is over, because they run from two minutes to ninety hours and a figure over
 *     them without it is as uninterpretable as the 0.00 it replaces (Q-D2's caveat).
 *
 * Both count a verdict given on the run's own detection in Review first. Used by the scoreboard (one cell, both
 * figures) and by Compare's side headers. A figure with no denominator prints the server's words, never 0. */
import type { PrecisionFigure, PrecisionFigures } from '../api'
import { InfoTip } from '../kit'

const SHORT = { containment: 'containment', extent: 'extent' } as const

function widthsLine(f: PrecisionFigure): string | null {
  const w = f.widths
  if (!w) return null
  if (!w.n) return 'no event-shaped row inside this run’s span'
  const s = (v: number | null) => (v == null ? '—' : fmtSamples(v))
  return `${w.n} event row${w.n === 1 ? '' : 's'} inside the span · ${s(w.min)} – ${s(w.max)} · median ${s(w.median)}${w.n >= 4 ? ` · middle half ${s(w.p25)} – ${s(w.p75)}` : ''}`
}

/** Samples, with the 1 Hz reading beside them when it helps (every recording on this project is 1 Hz or 10 Hz;
 *  the unit stated is samples, which is what the matching rule counts in). */
function fmtSamples(v: number): string {
  const n = Math.round(v)
  return n >= 10000 ? `${(n / 1000).toFixed(n >= 100000 ? 0 : 1)}k samples` : `${n.toLocaleString()} samples`
}

export function PrecisionFigureLine({ f, testid }: { f: PrecisionFigure | null | undefined; testid: string }) {
  if (!f) return <span className="muted small" data-testid={testid}>—</span>
  const widths = widthsLine(f)
  return (
    <span className="dsc-prec-line" data-testid={testid} data-value={f.value ?? ''} data-judged={f.judged}>
      <span className="muted small">{SHORT[f.key]}</span>{' '}
      {f.value == null
        ? <span className="muted small">{f.note ?? 'not yet scored'}</span>
        : <b>{`${Math.round(f.value * 100)} %`}</b>}
      {f.value != null && <span className="muted small"> {f.yes}/{f.judged}</span>}
      <InfoTip title={f.label} testid={`${testid}-rule`}>
        <p>{f.rule}.</p>
        <p className="muted small">{f.yes} yes of {f.judged} judged{f.byAdjudication ? ` · ${f.byAdjudication} by a verdict given in Review` : ''}.</p>
        {widths && <p className="muted small" data-testid={`${testid}-widths`}>The denominator’s event rows: {widths}. A precision over rows this varied is dominated by whichever few are event-sized (Q-D2’s caveat).</p>}
      </InfoTip>
    </span>
  )
}

/** The scoreboard's precision cell: both figures, stacked. */
export function PrecisionCell({ precisions, fallback }: { precisions?: PrecisionFigures | null; fallback?: string | null }) {
  if (!precisions) return <span className="muted">{fallback ?? 'not yet scored'}</span>
  return (
    <span className="dsc-prec" data-testid="score-precisions">
      <PrecisionFigureLine f={precisions.containment} testid="score-precision-containment" />
      <PrecisionFigureLine f={precisions.extent} testid="score-precision-extent" />
    </span>
  )
}
