/* Shell + routing. Every workspace is lazy-loaded behind its own error boundary, so a module that fails to
   load or render shows a red card for that workspace only (loud, never blank) and the rest of the app stays
   usable. Explore › Corpus/Signal and Analyse › Chain/Block are live against the bridge; every other page
   draws fixture data through src/api/<workspace>.ts and says so with the header's "demo data" chip. */
import { lazy, Suspense, useEffect, type ComponentType } from 'react'
import { listRuns } from './api'
import { ErrorBoundary } from './shell/ErrorBoundary'
import { Header } from './shell/Header'
import { NavRail } from './shell/NavRail'
import { ToastProvider } from './shell/Toast'
import { AppProvider, myJobIds, useApp } from './state'

const lazyNamed = <K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) =>
  lazy(() => load().then(m => ({ default: m[name] })))

const WORKSPACES: Record<string, ComponentType> = {
  explore: lazyNamed(() => import('./explore'), 'ExplorePage'),
  analyse: lazyNamed(() => import('./analyse'), 'AnalysePage'),
  discovery: lazyNamed(() => import('./discovery'), 'DiscoveryPage'),
  models: lazyNamed(() => import('./models'), 'ModelsPage'),
  review: lazyNamed(() => import('./review'), 'ReviewPage'),
  library: lazyNamed(() => import('./library'), 'LibraryPage'),
  jobs: lazyNamed(() => import('./jobs'), 'JobsPage'),
  settings: lazyNamed(() => import('./settings'), 'SettingsPage'),
  kit: lazyNamed(() => import('./kit/Gallery'), 'KitGallery'),
}

function Loading({ ws }: { ws: string }) {
  return (
    <>
      <Header workspace={ws[0].toUpperCase() + ws.slice(1)} page="" subtitle="loading…" />
      <div className="page"><div className="page-inner"><div className="skeleton" style={{ height: 240 }} data-testid="workspace-loading" /></div></div>
    </>
  )
}

function Unknown({ ws }: { ws: string }) {
  return (
    <>
      <Header workspace="Not found" page={`#/${ws}`} />
      <div className="page"><div className="page-inner">
        <div className="error-card" data-testid="unknown-route"><h3>No workspace called “{ws}”</h3>
          <p className="muted" style={{ margin: 0 }}>Use the nav rail, or go to <a href="#/explore/corpus">Explore › Corpus</a>.</p></div>
      </div></div>
    </>
  )
}

function Body() {
  const { route, setLiveJobs, setNeedYou, setBridgeDown } = useApp()
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const r = await listRuns(undefined, 1)
        if (!alive) return
        const mine = new Set(myJobIds())
        setLiveJobs(r.jobs.filter(j => j.status === 'running').length)
        setNeedYou(r.jobs.filter(j => j.status === 'failed' && mine.has(j.job_id)).length)
        setBridgeDown(false)
      } catch { if (alive) setBridgeDown(true) }
    }
    tick(); const id = window.setInterval(tick, 5000)
    return () => { alive = false; window.clearInterval(id) }
  }, [setLiveJobs, setNeedYou, setBridgeDown])
  const ws = route.workspace
  const Page = WORKSPACES[ws]
  return (
    <div className="app">
      <NavRail />
      <div className="main">
        <ErrorBoundary key={ws} label={`${ws} workspace`}>
          {Page ? <Suspense fallback={<Loading ws={ws} />}><Page /></Suspense> : <Unknown ws={ws} />}
        </ErrorBoundary>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <ToastProvider>
        <ErrorBoundary label="application">
          <Body />
        </ErrorBoundary>
      </ToastProvider>
    </AppProvider>
  )
}
