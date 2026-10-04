/* fixup-X item 4 — where a run and the human record disagree, broken down by channel, by time and by morphology.
 *
 * Drawn on Discovery › Compare when one side is *human annotations*, below the set overlap — where the researcher
 * already is; no new workspace. The two disagreement cells come from `Working/discovery/divergence.py`, the same
 * module the overlap above was paired by:
 *   machine yes · human no  — a detection a human rejected in Review, or one inside reviewed windows that say no
 *   machine no · human yes  — a label a human said yes to, where the run covered the place and found nothing
 * A place the run never covered, or no human reviewed, is *not comparable* — counted, never a disagreement.
 *
 * There is no test of structure and no null here, and the card says so the way Interrogation does: a table that
 * looks clustered is a lead, not a finding. The density strip uses the Corpus map's amber ramp and quantile rule
 * so the two read the same. */
import type { DivBreakdown, DivChannelRow } from '../api'
import { Callout, InfoTip, fmtInt } from '../kit'
import { AMBER_RAMP, quantileRamp } from '../explore/util'

const YN = 'machine_yes_human_no' as const
const NY = 'machine_no_human_yes' as const

export function DivergenceBreakdown({ data, humanSide }: { data: DivBreakdown; humanSide: 'A' | 'B' }) {
  const all = data.by_channel.flatMap(r => r.bins)
  const level = quantileRamp(all)
  const tot = data.by_channel.reduce((s, r) => ({ yn: s.yn + r[YN], ny: s.ny + r[NY], nc: s.nc + r.not_comparable }), { yn: 0, ny: 0, nc: 0 })
  const human = data.by_morphology.human
  return (
    <section className="k-card dsc-divergence" data-testid="divergence-breakdown" aria-label="Where the run and the human record disagree">
      <div className="dsc-card-head">
        <h3>Where they disagree</h3>
        <InfoTip title="The two disagreement cells">
          <p><b>machine yes · human no</b> — a detection a human rejected in Review, or one inside reviewed windows that say no.</p>
          <p><b>machine no · human yes</b> — a label a human said yes to, where the run covered the place and found nothing.</p>
          <p className="muted small">Containment: {data.rules.containment}.</p>
          <p className="muted small">Extent: {data.rules.extent}.</p>
          <p className="muted small">A place the run never covered, or no human reviewed, is not comparable — counted beside the cells, never in them. Human annotations are side {humanSide}.</p>
        </InfoTip>
        <span className="muted small" data-testid="divergence-totals">{fmtInt(tot.yn)} machine yes · human no · {fmtInt(tot.ny)} machine no · human yes · {fmtInt(tot.nc)} not comparable</span>
      </div>

      <Callout tone="grey" testid="divergence-no-null">{data.structure_note}</Callout>

      <div className="dsc-div-grid">
        <div>
          <div className="muted small dsc-div-sub">by channel</div>
          <table className="dsc-table" data-testid="divergence-by-channel">
            <thead><tr><th>channel</th><th>machine yes · human no</th><th>machine no · human yes</th><th>yes · yes</th><th>no · no</th><th>not comparable</th></tr></thead>
            <tbody>
              {data.by_channel.map(r => (
                <tr key={r.recording_id} data-testid={`divergence-row-${r.channel}`}>
                  <td>{r.channel}</td><td><b>{fmtInt(r[YN])}</b></td><td><b>{fmtInt(r[NY])}</b></td>
                  <td className="muted">{fmtInt(r.machine_yes_human_yes)}</td><td className="muted">{fmtInt(r.machine_no_human_no)}</td>
                  <td className="muted" title={whyLine(r)}>{fmtInt(r.not_comparable)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <div className="muted small dsc-div-sub">by time · {data.t0H}–{data.t1H} h · bin {data.binH} h · both cells per bin</div>
          <div className="dsc-div-strips" data-testid="divergence-density">
            {data.by_channel.map(r => (
              <div key={r.recording_id} className="dsc-div-strip">
                <span className="mono small">{r.channel}</span>
                <span className="cells">
                  {r.bins.map((c, i) => {
                    const t = data.by_time[i]
                    return <i key={i} data-testid="divergence-cell" data-count={c} style={{ background: AMBER_RAMP[level(c)] }}
                      title={`${r.channel} · ${t?.t0H ?? ''}–${t?.t1H ?? ''} h · ${c} disagreement${c === 1 ? '' : 's'}`} />
                  })}
                </span>
              </div>
            ))}
          </div>
          <div className="muted small" style={{ marginTop: 4 }}>all channels: {data.by_time.map(b => b[YN] + b[NY]).join(' · ')}</div>
        </div>

        <div>
          <div className="muted small dsc-div-sub">by morphology</div>
          <table className="dsc-table" data-testid="divergence-by-morphology">
            <thead><tr><th>human `element` tag</th><th>machine yes · human no</th><th>machine no · human yes</th></tr></thead>
            <tbody>
              {human.length ? human.map(r => <tr key={r.tag}><td>{r.tag}</td><td>{fmtInt(r[YN])}</td><td>{fmtInt(r[NY])}</td></tr>)
                : <tr><td colSpan={3} className="muted">no disagreement here rests on a tagged human label</td></tr>}
            </tbody>
          </table>
          <div className="muted small" data-testid="divergence-morph-human-note">{data.by_morphology.human_note}.</div>
          {data.by_morphology.machine.length
            ? <table className="dsc-table"><thead><tr><th>detector morphology</th><th>yes · no</th><th>no · yes</th></tr></thead>
              <tbody>{data.by_morphology.machine.map(r => <tr key={r.morphology}><td>{r.morphology}</td><td>{r[YN]}</td><td>{r[NY]}</td></tr>)}</tbody></table>
            : <div className="muted small" data-testid="divergence-morph-machine-note">Machine side: {data.by_morphology.machine_note}.</div>}
        </div>
      </div>
    </section>
  )
}

function whyLine(r: DivChannelRow) {
  const parts = Object.entries(r.not_comparable_why).map(([k, n]) => `${n} ${k}`)
  return parts.length ? `not comparable: ${parts.join(' · ')}` : 'nothing not comparable'
}
