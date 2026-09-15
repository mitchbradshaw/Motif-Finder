/* A page skeleton: the shell, the correct header, and the frame's main regions laid out and labelled.
 * Every route renders one of these until its workspace builder replaces it (brief, step 3). */
import { navigate } from '../state'
import { Header } from './Header'
import { pageById } from './pages'

export function Skeleton({ id }: { id: string }) {
  const p = pageById(id)
  if (!p) throw new Error(`no page registered with id ${id}`)
  return (
    <>
      <Header workspace={p.workspace} page={p.title} subtitle={p.subtitle} demo />
      <div className="page"><div className="page-inner" data-testid={`skeleton-${p.id}`}>
        <div className="card card-pad row between">
          <div>
            <div className="card-title">{p.id} · skeleton</div>
            <div className="muted small mono" style={{ marginTop: 4 }}>frames: {p.frames.map(f => f.split('/')[1]).join(' · ')}</div>
          </div>
          <button className="btn sm" onClick={() => navigate('explore/corpus')}>‹ Explore</button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
          {p.regions.map(r => (
            <div key={r} className="card card-pad" style={{ minHeight: 160 }} data-testid={`region-${r.replace(/\W+/g, '-')}`}>
              <div className="card-title">{r}</div>
              <div className="skeleton" style={{ height: 96, marginTop: 10 }} />
            </div>
          ))}
        </div>
      </div></div>
    </>
  )
}
