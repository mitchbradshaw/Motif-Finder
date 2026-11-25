/* Stop 8 · Spike statistics: the events as a population, the three species side by side. The same measures for
   whichever events you choose: your detector's, the researcher's accepted ones, or Auto-detect's. */
import type { ReactNode } from 'react'
import { Bars, Hist, Icicles, Rose, Scatter } from '../charts'
import { api, comboLabel, fmtDur, fmtNum, useAsync, useDemo } from '../store'

export function StatsPage() {
  const { m, thread, set } = useDemo()
  const mine = thread.ran ?? thread.combo
  const source = thread.source === 'mine' ? mine : thread.source
  const st = useAsync(() => api.stats(source), [source])
  const S = st.data
  const refSlope = (() => {
    if (!S) return 1
    const all = Object.values(S).flatMap(d => d.slopes_mv_s).filter(v => v > 0).sort((a, b) => a - b)
    return all.length ? all[Math.floor(all.length / 2)] : 1
  })()
  const opts: [string, string][] = [['library', "The researcher's accepted drops"], ['mine', 'Your detector'], ['auto', 'Auto-detect']]
  return (
    <div className="page-body stats">
      <div className="toolbar">
        <div className="seg" data-tour="stats-source">
          {opts.map(([k, l]) => <button key={k} className={thread.source === k ? 'on' : ''} onClick={() => set({ source: k })} data-testid={`src-${k}`}>{l}</button>)}
        </div>
        {thread.source === 'mine' && <span className="muted small">{comboLabel(m, mine)}</span>}
      </div>
      {st.error && <div className="card error-line">{st.error.message}</div>}
      {!S && !st.error && <div className="skeleton" style={{ height: 500 }} />}
      {S && <div className="stats-grid" data-testid="stats-grid">
        {m.datasets.map(ds => {
          const d = S[ds.key]
          return (
            <div key={ds.key} className="card stats-col">
              <div className="ds-head"><b>{ds.name}</b> <i className="muted">{ds.latin}</i></div>
              <div className="num-row"><b>{d?.n ?? 0}</b> events in 24 h on 4 electrodes</div>
              {!d || d.n === 0 ? <div className="empty-chart" style={{ height: 120 }}>no events</div> : <>
                <Block title="Events per hour"><Bars values={d.rate_per_h} labels={d.rate_per_h.map((_, i) => i % 6 === 0 ? `${i} h` : '')} /></Block>
                <Block title="Gaps between events" foot={<>median {fmtDur(d.median_interval_s ?? 0)} · CV {fmtNum(d.cv, 2)} · LV {fmtNum(d.lv, 2)}</>}
                  info="CV is spread over mean: 1 for random timing, below 1 for a regular rhythm. LV compares each gap with the next: under 1 means a steady beat.">
                  {d.intervals ? <Hist edges={d.intervals.edges_s} series={[{ counts: d.intervals.counts, color: '#0a84ff', label: 'gaps' }]} logX height={120} /> : <div className="empty-chart" style={{ height: 120 }}>too few events</div>}
                </Block>
                <Block title="Depth against width"><Scatter pts={d.scatter} /></Block>
                <Block title="Every event at its own size" info="Each drop from its onset, unscaled. Normalising would hide that big and small drops share one shape.">
                  <Icicles rows={d.icicles} height={170} /></Block>
                <Block title="How steep the fastest fall is" info="An angle per event: 45° is the typical steepness across all three species.">
                  <Rose slopes={d.slopes_mv_s} refSlope={refSlope} /></Block>
              </>}
            </div>
          )
        })}
      </div>}
    </div>
  )
}

function Block({ title, children, foot, info }: { title: string; children: ReactNode; foot?: ReactNode; info?: string }) {
  return (
    <div className="block">
      <div className="block-h">{title}{info && <span className="info" title={info}>i</span>}</div>
      {children}
      {foot && <div className="block-foot">{foot}</div>}
    </div>
  )
}
