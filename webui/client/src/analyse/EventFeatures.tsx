/* fixup-d: what the per-event feature blocks show — the feature table (one row per event), the rule
   behind every measure (printed, never implied), the steepest-slope rose (gradients.rose_data, drawn
   from its own bins: the page never re-derives an angle) and the interval statistics per group.
   Shared by the Analyse block page (interrogation.event_shape / interrogation.intervals) and the
   Interrogation › Sequence page. Draws only what the payload carries. */
import { useState } from 'react'
import type { FeatureTable as FeatureTableT, IntervalNullBlock, IntervalNullStat, IntervalStats, MeasureRule, SpansetPayload } from '../api'
import { Rose } from '../kit'
import { useRoseReferenceLine } from '../library/roseReference'
import { fmtNum } from './fmtNum'

const UNIT: [RegExp, string][] = [[/_mv_s$/, 'mV/s'], [/_mv$/, 'mV'], [/_s$/, 's']]
export function unitOf(col: string): string { for (const [re, u] of UNIT) if (re.test(col)) return u; return '' }
export function labelOf(col: string): string {
  return col.replace(/_(mv_s|mv|s)$/, '').replace(/_idx$/, ' (sample in span)').replace(/_/g, ' ')
}
export { fmtNum } from './fmtNum'

/** One row per event; a column per measure, its unit in the header. Capped at `maxRows` shown. */
export function FeatureTable({ table, rowLabel, maxRows = 60, testid = 'feature-table' }: {
  table: FeatureTableT; rowLabel?: (i: number) => string; maxRows?: number; testid?: string
}) {
  const [all, setAll] = useState(false)
  if (!table.matrix) return <div className="muted mono small" data-testid={testid}>{table.n_columns} features per event · the table is too large to ship ({table.columns.join(', ')})</div>
  const rows = all ? table.matrix : table.matrix.slice(0, maxRows)
  return (
    <div data-testid={testid} style={{ overflowX: 'auto', maxHeight: 360, overflowY: 'auto' }}>
      <table className="mono" style={{ borderCollapse: 'collapse', fontSize: 11, whiteSpace: 'nowrap' }}>
        <thead>
          <tr>
            <th style={th}>#</th>
            {table.columns.map(c => <th key={c} style={th} title={c}>{labelOf(c)}{unitOf(c) && <span className="muted"> {unitOf(c)}</span>}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td style={td} className="muted">{rowLabel ? rowLabel(i) : i + 1}</td>
              {r.map((v, k) => <td key={k} style={{ ...td, textAlign: 'right' }}>{fmtNum(v, table.columns[k])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {table.matrix.length > maxRows && (
        <button className="btn ghost" style={{ marginTop: 4 }} onClick={() => setAll(a => !a)} data-testid={`${testid}-more`}>
          {all ? `show the first ${maxRows}` : `show all ${table.matrix.length} events`}
        </button>
      )}
    </div>
  )
}
const th: React.CSSProperties = { textAlign: 'left', padding: '3px 8px', borderBottom: '1px solid var(--grey-200, #e5e7eb)', position: 'sticky', top: 0, background: 'var(--surface, #fff)', fontWeight: 600 }
const td: React.CSSProperties = { padding: '2px 8px', borderBottom: '1px solid var(--grey-100, #f3f4f6)' }

/** The rule behind every measure, as the block printed it. */
export function RulesList({ rules, testid = 'measure-rules' }: { rules: MeasureRule[]; testid?: string }) {
  return (
    <details data-testid={testid} style={{ fontSize: 11.5 }}>
      <summary className="muted" style={{ cursor: 'pointer' }}>how each measure is defined · {rules.length} rules</summary>
      <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '3px 12px', margin: '6px 0 0' }}>
        {rules.map(r => <FragmentRule key={r.name} r={r} />)}
      </dl>
    </details>
  )
}
function FragmentRule({ r }: { r: MeasureRule }) {
  return <><dt className="mono" style={{ fontWeight: 600 }}>{r.name.replace(/_/g, ' ')}</dt><dd style={{ margin: 0 }}>{r.rule}</dd></>
}

export function IntervalStatsTable({ stats, testid = 'interval-stats' }: { stats: Record<string, IntervalStats>; testid?: string }) {
  const cols: [keyof IntervalStats, string][] = [['n_events', 'events'], ['n_intervals', 'intervals'], ['median_s', 'median s'], ['mean_s', 'mean s'], ['min_s', 'min s'], ['max_s', 'max s'], ['cv', 'CV (ddof=1)'], ['r2_trend', 'R² trend'], ['drift_ratio', 'drift (last/first third)'], ['lv', 'LV'], ['cv2', 'CV2']]
  const withNulls = Object.values(stats).some(s => s.nulls !== undefined)
  return (
    <>
      <table className="mono" data-testid={testid} style={{ borderCollapse: 'collapse', fontSize: 11.5 }}>
        <thead><tr><th style={th}>group</th>{cols.map(([, l]) => <th key={l} style={th}>{l}</th>)}</tr></thead>
        <tbody>{Object.entries(stats).map(([g, s]) => <tr key={g}><td style={td}>{g}</td>{cols.map(([k]) => <td key={k} style={{ ...td, textAlign: 'right' }} title={(k === 'lv' || k === 'cv2') && s.local_note ? s.local_note : undefined}>{fmtNum(s[k] as number | null, k)}</td>)}</tr>)}</tbody>
      </table>
      {withNulls && <IntervalNullsTable stats={stats} />}
    </>
  )
}

const f2 = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(2))
const fp = (p: number | null | undefined) => (p == null ? '—' : p < 0.001 ? '< 0.001' : p.toFixed(3))
/** Where the observed value sits against one null's 95 % band, in words (round-B B1). */
function nullWords(which: 'poisson' | 'shuffle', r: IntervalNullStat): string {
  if (r.observed == null || r.lo == null || r.hi == null) return 'not measured'
  if (r.observed < r.lo) return which === 'poisson' ? 'more regular than random' : 'neighbouring gaps more alike than shuffled'
  if (r.observed > r.hi) return which === 'poisson' ? 'burstier than random' : 'long and short gaps alternate more than shuffled'
  return 'inside the band'
}
function NullCell({ which, b, m }: { which: 'poisson' | 'shuffle'; b: IntervalNullBlock; m: 'lv' | 'cv2' }) {
  const r = b[m]
  if (!r) return <td style={{ ...td, color: 'var(--grey-500, #6b7280)' }} title={b.note ?? undefined}>not measured</td>
  const outside = r.observed != null && r.lo != null && r.hi != null && (r.observed < r.lo || r.observed > r.hi)
  return (
    <td style={td} data-testid={`interval-null-${which}-${m}`} data-outside={outside ? 1 : 0}
      title={`${b.note ?? ''} · ${r.n_used} of ${b.n_draws} draws defined`}>
      null {f2(r.null_mean)} <span className="muted">[{f2(r.lo)}–{f2(r.hi)}]</span> · p {fp(r.p)}
      {' '}<b style={{ fontWeight: outside ? 600 : 400, color: outside ? 'var(--amber-700, #b45309)' : undefined }}>{nullWords(which, r)}</b>
    </td>
  )
}
/** Round-B B1: each group's LV and CV2 against a rate-matched Poisson null (is the timing more regular, or burstier,
 *  than random?) and the group's own gaps shuffled (is their ORDER more regular than their distribution implies?).
 *  Every number is the core's (`Working.interrogation.intervals.interval_nulls`); the page only words the band. */
export function IntervalNullsTable({ stats, testid = 'interval-nulls' }: { stats: Record<string, IntervalStats>; testid?: string }) {
  const rows = Object.entries(stats)
  const draws = rows.map(([, s]) => s.nulls?.poisson.n_draws).find(n => n != null)
  return (
    <div data-testid={testid} style={{ marginTop: 8 }}>
      <div className="muted small" style={{ marginBottom: 4 }}>
        LV and CV2 against two nulls, per group · observed value against the null mean, its 95 % band [2.5–97.5 %] and a two-sided p
        {draws != null ? ` · ${draws} seeded draws each` : ''} · <b>Poisson</b>: the same number of onsets at random over the group's own span — is the timing
        more regular, or burstier, than random? · <b>shuffled</b>: the group's own gaps in random order — is the order of the gaps more regular than their distribution alone implies?
      </div>
      <table className="mono" style={{ borderCollapse: 'collapse', fontSize: 11.5 }}>
        <thead><tr><th style={th}>group</th><th style={th}>n</th><th style={th}>measure</th><th style={th}>observed</th><th style={th}>vs rate-matched Poisson</th><th style={th}>vs shuffled intervals</th></tr></thead>
        <tbody>
          {rows.flatMap(([g, s]) => {
            const nl = s.nulls
            if (nl === undefined) return []
            if (nl === null) return [<tr key={g}><td style={td}>{g}</td><td style={td} colSpan={5} className="muted">nulls off (null_draws = 0)</td></tr>]
            return (['lv', 'cv2'] as const).map((m, i) => (
              <tr key={`${g}-${m}`} data-testid="interval-null-row" data-group={g} data-measure={m}>
                {i === 0 && <td style={td} rowSpan={2}>{g}</td>}
                {i === 0 && <td style={{ ...td, textAlign: 'right' }} rowSpan={2} title={nl.local_note ?? undefined}>{nl.n_events} events · {nl.n_intervals} gaps</td>}
                <td style={td}>{m === 'lv' ? 'LV' : 'CV2'}</td>
                <td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>{f2(nl.poisson[m]?.observed ?? (m === 'lv' ? s.lv : s.cv2))}</td>
                <NullCell which="poisson" b={nl.poisson} m={m} />
                <NullCell which="shuffle" b={nl.shuffle} m={m} />
              </tr>
            ))
          })}
        </tbody>
      </table>
      {rows.some(([, s]) => s.nulls?.caveat || s.nulls?.local_note) && (
        <ul className="muted small" style={{ margin: '4px 0 0 16px', padding: 0 }} data-testid="interval-null-caveats">
          {rows.filter(([, s]) => s.nulls?.caveat || s.nulls?.local_note).map(([g, s]) =>
            <li key={g}>{g}: {[s.nulls?.local_note, s.nulls?.caveat].filter(Boolean).join(' · ')}</li>)}
        </ul>
      )}
    </div>
  )
}

/** The whole block-page view of a SpanSet that carries features. */
export function EventFeaturesPanel({ p }: { p: SpansetPayload }) {
  const roseRef = useRoseReferenceLine()   // family fix: every rose carries the accepted-motif reference line (a hook, before the early return)
  if (!p.features) return null
  return (
    <div className="stack" style={{ gap: 12, marginTop: 12 }} data-testid="event-features">
      {p.features_unit_note && <div className="callout warn small" data-testid="features-unit-note" style={{ padding: '6px 10px', background: '#fff7e6', borderRadius: 6 }}>{p.features_unit_note}</div>}
      <div>
        <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Per-event measures</h3><span className="sg">{p.n} events · {p.features.n_columns} columns · one row per span</span></div>
        <FeatureTable table={p.features} />
      </div>
      {p.rose && <div><div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Steepest slope, each event as one angle</h3></div><Rose rose={p.rose} reference={roseRef} testid="rose-fan" /></div>}
      {p.interval_stats && <div><div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Inter-event intervals</h3><span className="sg">per group, never pooled</span></div><IntervalStatsTable stats={p.interval_stats} /></div>}
      {p.rules && <RulesList rules={p.rules} />}
    </div>
  )
}
