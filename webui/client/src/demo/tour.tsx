/* The guided tour (Q9 = A): one highlighted element and one line per step, across the eight stops. A step either
   waits for the visitor to do the thing it points at (pages call tourSignal) or offers Next. Skippable, and
   restartable from "?". Progress lives in localStorage, per station. */
import { useEffect, useLayoutEffect, useState, type CSSProperties } from 'react'
import { go } from './store'

export type TourStep = { route: string; target?: string; title: string; text: string; wait?: string; skip?: string }

export const STEPS: TourStep[] = [
  { route: 'explore', target: 'trace', title: 'A day in the life of a mushroom',
    text: "24 hours of electrical activity from one electrode in a lion's mane culture (CH14). Each sharp downward step is a spike." },
  { route: 'explore', target: 'overview', title: 'The whole day',
    text: 'The strip on top is all 24 hours. Drag on it to move the window.' },
  { route: 'explore', target: 'auto', title: 'Find them all', wait: 'auto',
    text: 'Press Auto-detect: MycoWave finds every drop on its own, and shades each by how sure it is.' },
  { route: 'explore', target: 'trace', title: 'Mark a stretch', wait: 'span', skip: 'span',
    text: 'Drag across the trace to mark a stretch, or click one of the purple drops.' },
  { route: 'explore', target: 'analyse-btn', title: 'Take it apart', wait: 'analyse',
    text: 'Open the stretch in Analyse.' },
  { route: 'analyse', target: 'step-clean', title: 'A detector is a chain',
    text: 'First it removes the slow drift, so a spike stands out from the baseline…' },
  { route: 'analyse', target: 'step-find', title: 'Finding events',
    text: "…then it finds the events. This is the thesis drop detector: it spells the trace as letters and catches the steep falls." },
  { route: 'build', target: 'detectors', title: 'Build your own', wait: 'knob',
    text: 'Change a setting: try 5 s letters and watch more drops appear. Every combination answers at once, because all 108 were computed in advance.' },
  { route: 'build', target: 'run-btn', title: 'Run it everywhere', wait: 'run',
    text: 'Run your detector on all 12 electrodes, in three species.' },
  { route: 'discovery', target: 'chance', title: 'Better than chance?',
    text: 'MycoWave also runs your detector on noise copies of the same channels. Real events should beat chance by a wide margin.' },
  { route: 'discovery', target: 'judge-btn', title: 'People decide', wait: 'judge',
    text: 'Machines propose, people decide. Judge five of your detections.' },
  { route: 'judge', target: 'judge-card', title: 'Your verdict', wait: 'judged', skip: 'judged',
    text: 'Yes, no or not sure? After five you see how you compare with the researcher.' },
  { route: 'library', target: 'families', title: 'The Library', wait: 'family',
    text: 'Drops the researcher accepted, grouped by shape. Open a family.' },
  { route: 'library', target: 'family-seed', title: 'More like these', wait: 'family-seed',
    text: 'Search every channel of all three species for drops like these.' },
  { route: 'seed', target: 'seed-result', title: 'Across species',
    text: 'Every match closer than chance allows, across the 12 electrodes. Try the CH14 wide drop on the shelf: it turns up in oyster too.' },
  { route: 'stats', target: 'icicles', title: 'The population',
    text: 'How often, how regular, and every event at its own size: big and small drops share one shape.' },
]

const KEY = 'mw.tour'

export function tourStep(): number | null {
  try { const v = localStorage.getItem(KEY); return v === null || v === 'off' ? null : Number(v) } catch { return null }
}

function setStep(n: number | null) {
  try { if (n === null) localStorage.setItem(KEY, 'off'); else localStorage.setItem(KEY, String(n)) } catch { /* private mode */ }
  window.dispatchEvent(new CustomEvent('demo:tour-step'))
}

export function startTour() { setStep(0) }
export function endTour() { setStep(null) }

/** A page tells the tour something happened ("auto", "span", "analyse", "knob", "run", ...). */
export function tourSignal(name: string) {
  window.dispatchEvent(new CustomEvent('demo:tour', { detail: name }))
}

/** A page that can stand in for a skipped step listens for this (e.g. Explore marks a stretch itself). */
export function onTourSkip(name: string, f: () => void) {
  const h = (e: Event) => { if ((e as CustomEvent).detail === name) f() }
  window.addEventListener('demo:tour-skip', h)
  return () => window.removeEventListener('demo:tour-skip', h)
}

export function Tour({ route }: { route: string }) {
  const [n, setN] = useState<number | null>(tourStep)
  const [rect, setRect] = useState<DOMRect | null>(null)
  useEffect(() => {
    const on = () => setN(tourStep())
    window.addEventListener('demo:tour-step', on)
    return () => window.removeEventListener('demo:tour-step', on)
  }, [])
  const step = n !== null ? STEPS[n] : null
  useEffect(() => {
    if (!step?.wait) return
    const h = (e: Event) => { if ((e as CustomEvent).detail === step.wait) advance() }
    window.addEventListener('demo:tour', h)
    return () => window.removeEventListener('demo:tour', h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [n])
  useLayoutEffect(() => {
    if (!step) { setRect(null); return }
    let alive = true
    const measure = () => {
      if (!alive) return
      const el = step.target ? document.querySelector(`[data-tour="${step.target}"]`) : null
      if (el) {
        const r = el.getBoundingClientRect()
        if (r.width > 0) {
          if (r.top < 60 || r.bottom > window.innerHeight - 20) el.scrollIntoView({ block: 'center', behavior: 'smooth' })
          setRect(r)
          return
        }
      }
      setRect(null)
    }
    measure()
    const id = window.setInterval(measure, 350)
    window.addEventListener('resize', measure)
    return () => { alive = false; window.clearInterval(id); window.removeEventListener('resize', measure) }
  }, [step, route])
  if (!step || n === null) return null

  function advance() {
    if (n === null) return
    const next = n + 1
    if (next >= STEPS.length) { endTour(); return }
    setStep(next)
    if (STEPS[next].route !== STEPS[n].route) go(STEPS[next].route)
  }
  const next = () => { if (step.skip) window.dispatchEvent(new CustomEvent('demo:tour-skip', { detail: step.skip })); advance() }
  const onPage = route === step.route
  const pad = 8
  const popStyle: CSSProperties = rect && onPage
    ? (rect.right + 340 < window.innerWidth
      ? { left: rect.right + 16, top: Math.max(70, Math.min(rect.top, window.innerHeight - 220)) }
      : rect.bottom + 200 < window.innerHeight
        ? { left: Math.max(16, Math.min(rect.left, window.innerWidth - 360)), top: rect.bottom + 14 }
        : { left: Math.max(16, Math.min(rect.left, window.innerWidth - 360)), top: Math.max(70, rect.top - 190) })
    : { right: 24, bottom: 24 }
  return (
    <>
      {rect && onPage && <div className="tour-spot" style={{ left: rect.left - pad, top: rect.top - pad, width: rect.width + 2 * pad, height: rect.height + 2 * pad }} />}
      <div className="tour-pop" style={popStyle} data-testid="tour-pop">
        <div className="tour-n">{n + 1} / {STEPS.length}</div>
        <div className="tour-title">{step.title}</div>
        <div className="tour-text">{step.text}</div>
        <div className="tour-actions">
          {!onPage && <button className="btn primary" onClick={() => go(step.route)}>Take me there</button>}
          {onPage && <button className={`btn ${step.wait ? '' : 'primary'}`} onClick={next} data-testid="tour-next">{step.wait ? 'Skip' : n + 1 === STEPS.length ? 'Finish' : 'Next'}</button>}
          <button className="link" onClick={endTour} data-testid="tour-end">End tour</button>
        </div>
      </div>
    </>
  )
}
