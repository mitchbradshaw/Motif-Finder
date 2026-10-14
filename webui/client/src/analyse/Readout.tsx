/* Analyse › block page: the block's `derive` readout beside its Parameters (2026-10-14) — what the block works
   out before a run (a noise floor, a cut, how many segments) and what it warns about (a span with gaps).
   The bridge computes it on what a run would hand the block (server/readout.py): the stages before it read
   from the step cache or re-run in memory, nothing written — on the stored span instead, the noise threshold
   after baseline removal printed a σ_n 8-20x too large and drop detection said "run the encoding first" even
   after a run. The request and its pacing are useReadout's. */
import type { SourceSpan } from '../state'
import { isHeldOut } from './toolbar'
import { pad2 } from './useAdapters'
import type { ReadoutState } from './useReadout'

/** One row per readout line, `warn` amber and `error` red; what it was computed on; why it was not. */
export function ReadoutCard({ state, source, pageName }: { state: ReadoutState; source: SourceSpan | null; pageName: (name: string) => string }) {
  const { r, error, pending } = state
  const shown = error ? 'error' : r?.skipped ? 'skipped' : r ? 'ready' : 'empty'
  const why = !source ? 'no source — the readout is computed on a span; use the example span from the chain page'
    : isHeldOut(source) ? 'the held-out recording is never sent to the bridge (D6)' : null
  return (
    <div className="card card-pad bp-readout" data-testid="readout-card" data-state={pending ? 'computing' : shown}>
      <div className="pp-head"><h3>Readout</h3>
        <span className="muted mono small" data-testid="readout-status">{pending ? 'computing…' : r && !r.skipped ? `computed in ${r.elapsed_s < 0.05 ? '<0.1' : r.elapsed_s.toFixed(1)} s` : ''}</span></div>
      {why && <div className="bp-readout-note" data-testid="readout-why">{why}</div>}
      {r && (
        <div className="bp-readout-on" data-testid="readout-on">
          {r.input.length === 0 ? 'on the source span — this block reads it as it is'
            : <>on this block's input, after {r.input.map((s, k) => (
                <span key={s.index}>{k > 0 && ' → '}<span className="stage" data-testid="readout-input" data-index={s.index} data-from={s.from}
                  title={s.from === 'cache' ? 'read from the step cache a run wrote' : 're-run in memory for this readout · nothing written'}>
                  {pad2(s.index + 1)} {pageName(s.name)}{s.from === 'cache' ? ' (cached)' : ''}</span></span>))}</>}
        </div>
      )}
      {r && r.rows.length > 0 && (
        <div className={`bp-readout-rows${pending ? ' stale' : ''}`}>
          {r.rows.map((row, k) => (
            <div key={k} className={`bp-readout-row${row.severity ? ` ${row.severity}` : ''}`} data-testid="readout-row" data-label={row.label} data-severity={row.severity}
              title={row.severity ? `${row.severity} · from the block's own readout` : undefined}>
              <span className="k">{row.severity === 'warn' ? '⚠ ' : row.severity === 'error' ? '✕ ' : ''}{row.label}</span><span className="v">{row.value}</span>
            </div>
          ))}
        </div>
      )}
      {r && !r.skipped && r.rows.length === 0 && <div className="bp-readout-note">the block has nothing to read out for these parameters</div>}
      {r?.skipped && <div className="bp-readout-note" data-testid="readout-skipped">not computed: {r.skipped}</div>}
      {error && (
        <div className="error-card" style={{ marginTop: 8 }} data-testid="readout-error">
          <h3>{error.status === 422 ? 'refused by the bridge (422)' : `readout failed (${error.status || 'no response'})`}</h3>
          <pre>{error.text}</pre>
        </div>
      )}
    </div>
  )
}
