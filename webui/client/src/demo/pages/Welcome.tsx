/* The welcome screen: what MycoWave is in one sentence, the three recordings, and the two ways in. */
import { Trace } from '../charts'
import { go, useDemo } from '../store'
import { startTour } from '../tour'

export function WelcomePage() {
  const { m, reset } = useDemo()
  return (
    <div className="page-body welcome">
      <div className="hero card">
        <h1>Myco<span>Wave</span></h1>
        <p className="lede">Mushrooms talk in electrical spikes. MycoWave finds them in days of recordings, sorts them into
          families, and lets you search for more like any one you pick.</p>
        <div className="hero-actions">
          <button className="btn primary big" data-testid="tour-start" onClick={() => { reset(); startTour(); go('explore') }}>Take the 3-minute tour</button>
          <button className="btn big" data-testid="explore-free" onClick={() => go('explore')}>Explore on my own</button>
        </div>
      </div>
      <div className="species">
        {m.datasets.map(d => {
          const s = m.slices.find(x => x.dataset === d.key)!
          return (
            <div key={d.key} className="card sp-card">
              <div className="sp-head"><b>{d.name}</b> <i>{d.latin}</i></div>
              <Trace sid={s.id} fs={s.fs} a={0} b={s.n} height={70} axis={false} color="#4f7dbd" />
              <p>{d.blurb}</p>
              <div className="muted small">{d.channels.length} electrodes · 24 hours</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
