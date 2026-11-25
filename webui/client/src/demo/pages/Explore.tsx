/* Stop 1 · Explore: one channel of one species, 24 hours. Auto-detect draws the drops it finds (the 24 Nov drop
   pool, v4, drops only); a drag marks a stretch to analyse or to search for. */
import { useEffect, useMemo, useState } from 'react'
import { Overview, Trace, type Box } from '../charts'
import { api, fmtDur, fmtH, go, useAsync, useDemo } from '../store'
import { onTourSkip, tourSignal } from '../tour'

const ZOOMS: [string, number][] = [['24 h', 24 * 3600], ['6 h', 6 * 3600], ['2 h', 2 * 3600], ['30 min', 1800], ['5 min', 300]]

export function ExplorePage() {
  const { m, thread, set, slice } = useDemo()
  const s = slice(thread.slice)
  const ds = m.datasets.find(d => d.key === s.dataset)!
  const [a, b] = thread.view
  const auto = useAsync(() => api.auto(s.id), [s.id])
  const boxes: Box[] = useMemo(() => !thread.autoOn || !auto.data ? [] :
    auto.data.events.map(e => ({ s: e.s, e: e.e, tone: 'auto', alpha: Math.max(0.35, e.confidence ?? 0.5), mark: e.extremum })), [thread.autoOn, auto.data])
  const inView = boxes.filter(x => x.e > a && x.s < b).length
  const width = b - a

  const setView = (c: number, w = width) => {
    const half = Math.round(w / 2)
    let p = Math.round(c) - half, q = p + w
    if (p < 0) { p = 0; q = Math.min(s.n, w) }
    if (q > s.n) { q = s.n; p = Math.max(0, s.n - w) }
    set({ view: [p, q] })
  }
  const zoom = (sec: number) => setView((a + b) / 2, Math.min(s.n, Math.round(sec * s.fs)))
  const pickSlice = (id: number) => {
    // keep the same stretch of TIME: the species are recorded at different rates (2 Hz, 1 Hz)
    const t = slice(id)
    const k = t.fs / s.fs
    const w = Math.min(t.n, Math.round(width * k))
    const p = Math.max(0, Math.min(Math.round(a * k), t.n - w))
    set({ slice: id, span: null, view: [p, p + w] })
  }
  const span = thread.span
  const spanS = span ? (span[1] - span[0]) / s.fs : 0
  useEffect(() => { if (span) tourSignal('span') }, [span])
  // the tour's "Mark a stretch" skipped: mark one around the first drop in view (or the middle of the view)
  useEffect(() => onTourSkip('span', () => {
    const ev = auto.data?.events.find(e => e.e > a && e.s < b)
    const pad = Math.round(90 * s.fs)
    set({ span: ev ? [Math.max(0, ev.s - pad), Math.min(s.n, ev.e + pad)] : [Math.round(a + width * 0.45), Math.round(a + width * 0.55)] })
  }), [auto.data, a, b, width, s.fs, s.n, set])

  return (
    <div className="page-body explore">
      <div className="toolbar">
        <div className="seg" data-tour="datasets">
          {m.datasets.map(d => {
            const first = m.slices.find(x => x.dataset === d.key)!
            return <button key={d.key} className={d.key === s.dataset ? 'on' : ''} onClick={() => pickSlice(first.id)} data-testid={`ds-${d.key}`}>{d.name}</button>
          })}
        </div>
        <div className="chips">
          {m.slices.filter(x => x.dataset === s.dataset).map(x =>
            <button key={x.id} className={`chip${x.id === s.id ? ' on' : ''}`} onClick={() => pickSlice(x.id)} data-testid={`ch-${x.id}`}>{x.label}</button>)}
        </div>
        <span className="grow" />
        <span className="muted small">{ds.latin} · 24 h at {s.fs} Hz</span>
      </div>

      <div className="explore-grid">
        <div className="card trace-card">
          <Overview sid={s.id} fs={s.fs} n={s.n} view={thread.view} onMove={c => setView(c)} boxes={boxes} />
          <div className="zoombar">
            {ZOOMS.map(([l, sec]) => <button key={l} className={`zoom${Math.abs(width - sec * s.fs) < 2 ? ' on' : ''}`} onClick={() => zoom(sec)}>{l}</button>)}
            <span className="grow" />
            <button className="zoom" onClick={() => setView(a + width / 2 - width * 0.75)} aria-label="earlier">◀</button>
            <span className="muted small">{fmtH(a, s.fs)} – {fmtH(b, s.fs)}</span>
            <button className="zoom" onClick={() => setView(a + width / 2 + width * 0.75)} aria-label="later">▶</button>
          </div>
          <Trace sid={s.id} fs={s.fs} a={a} b={b} height={330} boxes={boxes} span={span} testid="explore-trace" tour="trace"
            onSpan={(p, q) => set({ span: [p, q] })}
            onBox={i => { const x = boxes[i]; const pad = Math.round((x.e - x.s) * 0.4); set({ span: [Math.max(0, x.s - pad), Math.min(s.n, x.e + pad)] }) }} />
          <p className="hint">Drag across the trace to mark a stretch{thread.autoOn ? ', or click a drop' : ''}.</p>
        </div>

        <div className="side">
          <div className="card">
            <h3>Auto-detect</h3>
            <button className={`btn ${thread.autoOn ? 'ghost' : 'primary'}`} data-tour="auto" data-testid="auto-btn"
              onClick={() => { set({ autoOn: !thread.autoOn }); if (!thread.autoOn) tourSignal('auto') }}>
              {thread.autoOn ? 'Hide drops' : 'Auto-detect drops'}
            </button>
            {thread.autoOn && auto.data && <div className="stat-line" data-testid="auto-count">
              <b>{auto.data.n}</b> drops in 24 h · <b>{inView}</b> in view
              {span && <> · <b>{boxes.filter(x => x.e > span[0] && x.s < span[1]).length}</b> in your stretch</>}
            </div>}
            {thread.autoOn && <p className="hint">Darker means more confident.</p>}
            {auto.error && <div className="error-line">{auto.error.message}</div>}
          </div>

          <div className="card">
            <h3>Your stretch</h3>
            {span ? <>
              <div className="stat-line" data-testid="span-label">{fmtH(span[0], s.fs)} – {fmtH(span[1], s.fs)} · {fmtDur(spanS)}</div>
              <button className="btn primary" data-tour="analyse-btn" data-testid="analyse-btn" onClick={() => { tourSignal('analyse'); go('analyse') }}>Analyse this stretch</button>
              <button className="btn" data-testid="seed-btn" disabled={spanS > 300 || spanS * s.fs < 8}
                title={spanS > 300 ? 'mark at most 5 minutes to search for it' : ''}
                onClick={() => { set({ seed: 'live' }); go('seed') }}>Find more like this</button>
              {spanS > 300 && <p className="hint">Mark 5 minutes or less to search for more like it.</p>}
              <button className="link" onClick={() => set({ span: null })}>clear</button>
            </> : <p className="hint">Nothing marked yet.</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
