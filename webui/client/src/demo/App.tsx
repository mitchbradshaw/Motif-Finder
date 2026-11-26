/* The demo's shell: the eight stops down the left, one page at a time, the tour on top. A station that has been
   handed to someone else says so instead of letting an old tab write into the next visitor's copy. A page that
   throws shows a red card (loud, never blank) and the rest of the demo stays usable. */
import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { api, claimToken, hubClaimUrl, type Manifest } from './api'
import { breadth, go, numWord, useDemo } from './store'
import { Tour, startTour, tourStep } from './tour'
import { AnalysePage } from './pages/Analyse'
import { DiscoveryPage } from './pages/Discovery'
import { ExplorePage } from './pages/Explore'
import { JudgePage } from './pages/Judge'
import { LibraryPage } from './pages/Library'
import { SeedPage } from './pages/Seed'
import { StatsPage } from './pages/Stats'
import { WelcomePage } from './pages/Welcome'

const STOPS: { key: string; label: string; title: string; sub: string | ((m: Manifest) => string) }[] = [
  { key: 'explore', label: 'Explore', title: 'Explore a recording', sub: 'One electrode, 24 hours' },
  { key: 'analyse', label: 'Analyse', title: 'Analyse a stretch', sub: 'The steps of a detector, one by one' },
  { key: 'build', label: 'Build', title: 'Build your own detector', sub: 'Every setting answers at once' },
  { key: 'discovery', label: 'Discovery', title: 'Run it everywhere', sub: m => `All ${breadth(m).channels} electrodes, ${numWord(breadth(m).species)} species, against chance` },
  { key: 'judge', label: 'Judge', title: 'Judge five', sub: 'Machines propose, people decide' },
  { key: 'library', label: 'Library', title: 'The Library', sub: 'Accepted drops, by shape family' },
  { key: 'seed', label: 'Seed search', title: 'Find more like this', sub: 'One shape, searched across species' },
  { key: 'stats', label: 'Statistics', title: 'Spike statistics', sub: 'The events as a population' },
]

class Boundary extends Component<{ label: string; children: ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null }
  static getDerivedStateFromError(err: Error) { return { err } }
  componentDidCatch(err: Error) { console.error(`[demo] ${this.props.label} failed:`, err) }
  render() {
    if (this.state.err) return <div className="page-body"><div className="card error-card" data-testid="render-error">
      <h3>This page hit an error</h3><p className="mono">{this.state.err.message}</p>
      <button className="btn" onClick={() => this.setState({ err: null })}>Try again</button></div></div>
    return this.props.children
  }
}

function useStation() {
  const { reset } = useDemo()
  const [lost, setLost] = useState<string | null>(null)
  const last = useRef(0)
  const hub = useRef<string | null>(null)
  const check = useCallback(async () => {
    try {
      const r = await api.ping()
      hub.current = r.hub
      const seen = sessionStorage.getItem('mw.epoch')
      if (r.hub && !r.mine) { setLost(r.hub); return }
      if (seen !== null && Number(seen) !== r.epoch) { reset(); go('welcome') }
      sessionStorage.setItem('mw.epoch', String(r.epoch))
    } catch { /* the bridge is down: the pages say so on their own reads */ }
  }, [reset])
  useEffect(() => {
    claimToken()
    check()
    const on = () => { const t = Date.now(); if (t - last.current > 15000) { last.current = t; check() } }
    window.addEventListener('pointerdown', on)
    window.addEventListener('keydown', on)
    const id = window.setInterval(() => { if (document.visibilityState === 'visible') check() }, 60000)
    return () => { window.removeEventListener('pointerdown', on); window.removeEventListener('keydown', on); window.clearInterval(id) }
  }, [check])
  return { lost, hub }
}

export function App() {
  const { route, reset, m } = useDemo()
  const { lost, hub } = useStation()
  const [confirm, setConfirm] = useState(false)
  const page = route.page
  const stop = STOPS.find(s => s.key === page)
  const idx = STOPS.findIndex(s => s.key === page)
  const small = Math.min(window.innerWidth, window.innerHeight) < 600
  const startOver = async () => {
    setConfirm(false)
    try { const r = await api.startOver(); sessionStorage.setItem('mw.epoch', String(r.epoch)) } catch { /* standalone */ }
    reset()
    go('welcome')
  }
  let body: ReactNode
  switch (page) {
    case 'explore': body = <ExplorePage />; break
    case 'analyse': body = <AnalysePage build={false} />; break
    case 'build': body = <AnalysePage build={true} />; break
    case 'discovery': body = <DiscoveryPage />; break
    case 'judge': body = <JudgePage />; break
    case 'library': body = <LibraryPage />; break
    case 'seed': body = <SeedPage />; break
    case 'stats': body = <StatsPage />; break
    default: body = <WelcomePage />
  }
  return (
    <div className="demo-app">
      <nav className="rail2" data-testid="rail">
        <button className="logo" onClick={() => go('welcome')} title="Welcome">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round"><path d="M12 20V10M12 10c0-4 3-6 7-6 0 4-3 6-7 6zM12 13c0-3-2.5-5-6-5 0 3 2.5 5 6 5z" /></svg>
          <span>Myco<b>Wave</b></span>
        </button>
        <div className="stops">
          {STOPS.map((s, i) => <button key={s.key} className={`stop${page === s.key ? ' on' : ''}${idx > i ? ' past' : ''}`} onClick={() => go(s.key)} data-testid={`stop-${s.key}`}>
            <span className="stop-n">{i + 1}</span><span>{s.label}</span></button>)}
        </div>
        <div className="rail-foot2">
          <button className="foot-btn" title="Guided tour" onClick={() => { if (tourStep() === null) startTour(); if (page === 'welcome') go('explore') }} data-testid="tour-help"><span className="foot-long">? Tour</span><span className="foot-short">?</span></button>
          <button className="foot-btn" title="Start over" onClick={() => setConfirm(true)} data-testid="start-over"><span className="foot-long">Start over</span><span className="foot-short">↺</span></button>
        </div>
      </nav>
      <main className="main2">
        {stop && <header className="head2"><div><h1>{stop.title}</h1><div className="sub">{typeof stop.sub === 'function' ? stop.sub(m) : stop.sub}</div></div>
          {idx < STOPS.length - 1 && <button className="btn ghost small" onClick={() => go(STOPS[idx + 1].key)} data-testid="next-stop">Next: {STOPS[idx + 1].label} →</button>}</header>}
        {small && <div className="phone-note">MycoWave is best on a laptop or tablet screen.</div>}
        <Boundary key={page} label={page}>{body}</Boundary>
      </main>
      <Tour route={page} />
      {confirm && <div className="modal-back" onClick={() => setConfirm(false)}><div className="modal" onClick={e => e.stopPropagation()}>
        <h3>Start over?</h3><p>Your detector, runs and verdicts on this copy are cleared.</p>
        <div className="modal-actions"><button className="btn" onClick={() => setConfirm(false)}>Cancel</button>
          <button className="btn primary" onClick={startOver} data-testid="start-over-yes">Start over</button></div></div></div>}
      {lost && <div className="modal-back"><div className="modal" data-testid="station-lost">
        <h3>This copy has moved on</h3><p>It was idle for a while and is now someone else's. Get a fresh copy of your own.</p>
        <div className="modal-actions"><a className="btn primary" href={hubClaimUrl(hub.current ?? lost)}>Get a new copy</a></div></div></div>}
    </div>
  )
}
