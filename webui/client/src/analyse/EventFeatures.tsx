/* fixup-d: what the per-event feature blocks show — the feature table (one row per event), the rule
   behind every measure (printed, never implied), the steepest-slope rose (gradients.rose_data, drawn
   from its own bins: the page never re-derives an angle) and the interval statistics per group.
   Shared by the Analyse block page (interrogation.event_shape / interrogation.intervals) and the
   Interrogation › Sequence page. Draws only what the payload carries. */
import { useState } from 'react'
import type { FeatureTable as FeatureTableT, IntervalStats, MeasureRule, RosePayload, SpansetPayload } from '../api'

const B = '#0a84ff', BL = '#bfdcff', G = '#9ca3af', AM = '#e8900c'

const UNIT: [RegExp, string][] = [[/_mv_s$/, 'mV/s'], [/_mv$/, 'mV'], [/_s$/, 's']]
export function unitOf(col: string): string { for (const [re, u] of UNIT) if (re.test(col)) return u; return '' }
export function labelOf(col: string): string {
  return col.replace(/_(mv_s|mv|s)$/, '').replace(/_idx$/, ' (sample in span)').replace(/_/g, ' ')
}
export function fmtNum(v: number | null | undefined, col = ''): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  if (col === 'polarity') return v < 0 ? 'drop' : 'spike'
  if (col.endsWith('_idx')) return String(Math.round(v))
  const a = Math.abs(v)
  return a >= 1000 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : a >= 0.01 ? v.toFixed(3) : v.toExponential(2)
}

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

/** The rose: gradients.rose_data's own 18 bins over the falling quadrant (0° … −90°), each a wedge whose
    length is its count; every event a dot at its angle; the circular mean as an arrow. */
export function RoseFan({ rose, highlight, testid = 'rose-fan' }: { rose: RosePayload; highlight?: number | null; testid?: string }) {
  const W = 300, H = 230, cx = 24, cy = 20, R = 190
  const max = Math.max(1, ...rose.counts)
  const at = (deg: number, r: number) => { const a = (deg * Math.PI) / 180; return [cx + r * Math.cos(a), cy - r * Math.sin(a)] as const }
  const half = rose.bin_width_deg / 2
  const stats = rose.n ? [
    ['events', String(rose.n)],
    ['mean direction', rose.mean_deg !== null ? `${rose.mean_deg.toFixed(1)}°` : '—'],
    ['resultant R', rose.resultant_length !== null ? rose.resultant_length.toFixed(3) : '—'],
    ['circular sd', rose.circular_sd_deg !== null ? `${rose.circular_sd_deg.toFixed(1)}°` : '—'],
    ['uniform over the quadrant, KS p', rose.uniformity_p !== null ? rose.uniformity_p.toPrecision(2) : '— (n < 3)'],
  ] : []
  return (
    <div data-testid={testid} style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`rose of ${rose.n} steepest-slope angles`} data-render="rose">
        <path d={`M ${at(0, R).join(' ')} A ${R} ${R} 0 0 1 ${at(-90, R).join(' ')}`} fill="none" stroke="#e5e7eb" />
        {[0, -15, -30, -45, -60, -75, -90].map(s => {
          const [x2, y2] = at(s, R); const [lx, ly] = at(s, R + 12)
          return <g key={s}><line x1={cx} y1={cy} x2={x2} y2={y2} stroke={s === -45 ? '#c8ccd4' : '#f0f1f3'} /><text x={lx} y={ly + 3} fontSize={9} fill={G} textAnchor={s <= -75 ? 'middle' : 'start'}>{s === 0 ? '0°' : `−${-s}°`}</text></g>
        })}
        {rose.counts.map((c, i) => {
          if (!c) return null
          const mid = rose.bin_centres_deg[i]; const r = R * (c / max)
          const [x1, y1] = at(mid + half, r); const [x2, y2] = at(mid - half, r)
          return <path key={i} d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2} Z`} fill={BL} stroke={B} strokeWidth={0.8}><title>{`${(mid + half).toFixed(0)}° … ${(mid - half).toFixed(0)}° · ${c} event${c === 1 ? '' : 's'}`}</title></path>
        })}
        {rose.angles_deg.map((a, k) => {
          const [x, y] = at(a, R - 6); const on = highlight !== undefined && highlight !== null && rose.event_index[k] === highlight
          return <circle key={k} cx={x} cy={y} r={on ? 4.5 : 2.6} fill={on ? AM : B} fillOpacity={on ? 1 : 0.7}><title>{`event ${rose.event_index[k] + 1} · ${a.toFixed(1)}°${rose.slopes_mv_s ? ` · ${rose.slopes_mv_s[k].toFixed(3)} mV/s` : ''}`}</title></circle>
        })}
        {rose.mean_deg !== null && (() => { const [x, y] = at(rose.mean_deg, R * 0.9); return <line x1={cx} y1={cy} x2={x} y2={y} stroke={AM} strokeWidth={2} data-testid="rose-mean" /> })()}
      </svg>
      <div style={{ fontSize: 12, minWidth: 200, maxWidth: 320 }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{rose.caption || 'no events with a measured fall'}</div>
        {stats.map(([k, v]) => <div key={k} className="mono" style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><span className="muted">{k}</span><span>{v}</span></div>)}
        {Object.keys(rose.groups).length > 1 && (
          <div style={{ marginTop: 6 }}>
            {Object.entries(rose.groups).map(([k, g]) => <div key={k} className="mono small">{k}: n {g.n} · mean {g.mean_deg?.toFixed(1) ?? '—'}° · R {g.resultant_length?.toFixed(2) ?? '—'}</div>)}
          </div>
        )}
        {rose.note && <div className="muted small" style={{ marginTop: 6 }}>{rose.note}</div>}
        <div className="muted small" style={{ marginTop: 4 }}>angle = arctan(steepest slope / reference) · scale {rose.scale} · bins {rose.bin_width_deg.toFixed(0)}° · KS against uniform over the quadrant, not Rayleigh (a Rayleigh test is significant by construction when every angle is in one quadrant)</div>
      </div>
    </div>
  )
}

export function IntervalStatsTable({ stats, testid = 'interval-stats' }: { stats: Record<string, IntervalStats>; testid?: string }) {
  const cols: [keyof IntervalStats, string][] = [['n_events', 'events'], ['n_intervals', 'intervals'], ['median_s', 'median s'], ['mean_s', 'mean s'], ['min_s', 'min s'], ['max_s', 'max s'], ['cv', 'CV (ddof=1)'], ['r2_trend', 'R² trend'], ['drift_ratio', 'drift (last/first third)']]
  return (
    <table className="mono" data-testid={testid} style={{ borderCollapse: 'collapse', fontSize: 11.5 }}>
      <thead><tr><th style={th}>group</th>{cols.map(([, l]) => <th key={l} style={th}>{l}</th>)}</tr></thead>
      <tbody>{Object.entries(stats).map(([g, s]) => <tr key={g}><td style={td}>{g}</td>{cols.map(([k]) => <td key={k} style={{ ...td, textAlign: 'right' }}>{fmtNum(s[k] as number | null)}</td>)}</tr>)}</tbody>
    </table>
  )
}

/** The whole block-page view of a SpanSet that carries features. */
export function EventFeaturesPanel({ p }: { p: SpansetPayload }) {
  if (!p.features) return null
  return (
    <div className="stack" style={{ gap: 12, marginTop: 12 }} data-testid="event-features">
      {p.features_unit_note && <div className="callout warn small" data-testid="features-unit-note" style={{ padding: '6px 10px', background: '#fff7e6', borderRadius: 6 }}>{p.features_unit_note}</div>}
      <div>
        <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Per-event measures</h3><span className="sg">{p.n} events · {p.features.n_columns} columns · one row per span</span></div>
        <FeatureTable table={p.features} />
      </div>
      {p.rose && <div><div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Steepest slope, each event as one angle</h3></div><RoseFan rose={p.rose} /></div>}
      {p.interval_stats && <div><div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Inter-event intervals</h3><span className="sg">per group, never pooled</span></div><IntervalStatsTable stats={p.interval_stats} /></div>}
      {p.rules && <RulesList rules={p.rules} />}
    </div>
  )
}
