/* Stop 4 · Discovery: the visitor's detector on every demo channel at once, against chance (the same detector on
   10 noise copies of each channel, which keep the channel's spectrum and lose its events), beside the three
   detectors the researcher prepared. */
import { useEffect } from 'react'
import { Strip } from '../charts'
import { api, comboLabel, fmtNum, go, useAsync, useDemo } from '../store'
import { tourSignal } from '../tour'

export function ratioTone(r: number | null): string {
  if (r === null) return 'grey'
  return r >= 3 ? 'good' : r >= 1.5 ? 'ok' : 'bad'
}

export function ratioText(r: number | null): string {
  if (r === null) return 'no null drawn'
  if (r < 1) return 'no better than chance'
  return `${r >= 10 ? Math.round(r) : r.toFixed(1)}× chance`
}

export function DiscoveryPage() {
  const { m, thread, slice } = useDemo()
  const combo = thread.ran ?? thread.combo
  const sum = useAsync(() => api.discovery(combo), [combo])
  const refs = useAsync(() => api.references(), [])
  useEffect(() => { api.addRun(combo).catch(() => { /* the run list is a convenience; the page reads the store */ }) }, [combo])
  const d = sum.data

  return (
    <div className="page-body discovery">
      <div className="toolbar">
        <span className="src-chip">Your detector: <b>{comboLabel(m, combo)}</b></span>
        <button className="link" onClick={() => go('build')}>change it</button>
      </div>

      {sum.error && <div className="card error-line">{sum.error.message}</div>}
      {d && <div className="card big-stat" data-tour="chance" data-testid="disc-summary">
        <div><div className="num">{d.n.toLocaleString()}</div><div className="lab">events on 12 channels, 3 species</div></div>
        <div><div className="num muted">{fmtNum(d.null, 0)}</div><div className="lab">on noise copies of the same channels</div></div>
        <div className={`badge ${ratioTone(d.ratio)}`} data-testid="disc-ratio">{ratioText(d.ratio)}</div>
      </div>}

      {d && m.datasets.map(ds => (
        <div key={ds.key} className="card ds-block">
          <div className="ds-head"><b>{ds.name}</b> <i className="muted">{ds.latin}</i>
            <span className="grow" /><span className="muted small">{d.by_dataset[ds.key]?.n ?? 0} events · chance {fmtNum(d.by_dataset[ds.key]?.null ?? null, 0)}</span></div>
          {d.per_slice.filter(p => slice(p.slice).dataset === ds.key).map(p => {
            const s = slice(p.slice)
            return (
              <div key={p.slice} className="ch-row">
                <span className="ch-lab">{s.label}</span>
                <span className="ch-n"><b>{p.n}</b> <span className="muted">/ {fmtNum(p.null_mean, 0)}</span></span>
                <Strip n={s.n} spans={p.spans} />
              </div>
            )
          })}
        </div>
      ))}

      <div className="card">
        <h3>Against the researcher's detectors</h3>
        <table className="cmp" data-testid="disc-compare">
          <thead><tr><th></th>{m.datasets.map(ds => <th key={ds.key}>{ds.name}</th>)}<th>vs chance</th></tr></thead>
          <tbody>
            {d && <tr className="mine"><td>Your detector</td>{m.datasets.map(ds => <td key={ds.key}>{d.by_dataset[ds.key]?.n ?? 0}</td>)}
              <td><span className={`badge small ${ratioTone(d.ratio)}`}>{ratioText(d.ratio)}</span></td></tr>}
            {refs.data?.map(r => <tr key={r.key}><td>{r.label}</td>{m.datasets.map(ds => <td key={ds.key}>{r.by_dataset[ds.key]?.n ?? 0}</td>)}
              <td><span className={`badge small ${ratioTone(r.ratio)}`}>{r.combo === null ? 'judged by eye' : ratioText(r.ratio)}</span></td></tr>)}
          </tbody>
        </table>
      </div>

      <div className="cta-bar">
        <span className="muted">Are these real events? Judge five of them.</span>
        <span className="grow" />
        <button className="btn primary big" data-tour="judge-btn" data-testid="judge-btn" onClick={() => { tourSignal('judge'); go('judge') }}>Judge five</button>
      </div>
    </div>
  )
}
