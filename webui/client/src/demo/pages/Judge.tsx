/* Stop 5 · Judge five: the human in the loop. Five of the visitor's detections, one at a time; then how many they
   accepted (their detector's precision, on five) and, where the researcher judged the same stretch, whether they
   agreed. Verdicts stay in this station's private copy. */
import { useEffect, useState } from 'react'
import { Trace } from '../charts'
import { api, comboLabel, fmtH, go, useDemo } from '../store'
import type { Judge } from '../api'
import { tourSignal } from '../tour'

const WORD: Record<string, string> = { yes: 'Yes', no: 'No', unsure: 'Not sure' }

export function JudgePage() {
  const { m, thread, slice } = useDemo()
  const combo = thread.ran ?? thread.combo
  const [j, setJ] = useState<Judge | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.judge(combo).then(setJ, e => setErr(String(e.message || e))) }, [combo])
  if (err) return <div className="page-body"><div className="card error-line">{err}</div></div>
  if (!j) return <div className="page-body"><div className="skeleton" style={{ height: 320 }} /></div>
  if (!j.items.length) return <div className="page-body"><div className="card">
    <h3>Nothing to judge</h3><p>This detector found no events. <button className="link" onClick={() => go('build')}>Change it</button></p></div></div>
  const done = j.items.filter(it => j.verdicts[String(it.item)]).length
  const cur = j.items.find(it => !j.verdicts[String(it.item)])

  const say = async (v: string) => {
    if (!cur || busy) return
    setBusy(true)
    try {
      const r = await api.verdict(combo, cur.item, v)
      setJ({ ...j, verdicts: r.verdicts })
      if (Object.keys(r.verdicts).length >= j.items.length) tourSignal('judged')
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }

  if (cur) {
    const s = slice(cur.slice)
    const w = cur.e - cur.s
    const pad = Math.max(w * 2, Math.round(120 * s.fs))
    const a = Math.max(0, cur.s - pad), b = Math.min(s.n, cur.e + pad)
    const ds = m.datasets.find(d => d.key === s.dataset)!
    return (
      <div className="page-body judge">
        <div className="judge-head">
          <div className="dots">{j.items.map(it => <i key={it.item} className={j.verdicts[String(it.item)] ? 'done' : it.item === cur.item ? 'cur' : ''} />)}</div>
          <span className="muted">{done + 1} of {j.items.length} · {ds.name} {s.label} at {fmtH(cur.s, s.fs)}</span>
        </div>
        <div className="card" data-tour="judge-card">
          <h2 className="q">Is the shaded stretch an event?</h2>
          <Trace sid={s.id} fs={s.fs} a={a} b={b} height={260} boxes={[{ s: cur.s, e: cur.e, tone: 'mine', alpha: 1, mark: cur.extremum }]} testid="judge-trace" />
          <div className="verdicts">
            <button className="btn primary big" disabled={busy} onClick={() => say('yes')} data-testid="v-yes">Yes, an event</button>
            <button className="btn big danger" disabled={busy} onClick={() => say('no')} data-testid="v-no">No</button>
            <button className="btn big ghost" disabled={busy} onClick={() => say('unsure')} data-testid="v-unsure">Not sure</button>
          </div>
        </div>
      </div>
    )
  }

  const yes = j.items.filter(it => j.verdicts[String(it.item)] === 'yes').length
  const judged = j.items.filter(it => it.researcher)
  const agree = judged.filter(it => it.researcher === j.verdicts[String(it.item)]).length
  return (
    <div className="page-body judge">
      <div className="card big-stat" data-testid="judge-summary">
        <div><div className="num">{yes} / {j.items.length}</div><div className="lab">you said were events: your detector's precision, as you judged it</div></div>
        <div><div className="num">{judged.length ? `${agree} / ${judged.length}` : '–'}</div><div className="lab">agreed with the researcher, where they judged it too</div></div>
      </div>
      <div className="card">
        <table className="cmp">
          <thead><tr><th>#</th><th>where</th><th>you</th><th>the researcher</th></tr></thead>
          <tbody>{j.items.map(it => {
            const s = slice(it.slice)
            const ds = m.datasets.find(d => d.key === s.dataset)!
            const mine = j.verdicts[String(it.item)]
            return <tr key={it.item}><td>{it.item + 1}</td><td>{ds.name} {s.label} · {fmtH(it.s, s.fs)}</td><td>{WORD[mine] ?? mine}</td>
              <td>{it.researcher ? <span className={it.researcher === mine ? 'agree' : 'disagree'}>{WORD[it.researcher]}</span> : <span className="muted">not judged</span>}</td></tr>
          })}</tbody>
        </table>
        <p className="hint">Detector: {comboLabel(m, combo)}. The researcher judged thousands of these the same way; the Library is what they kept.</p>
      </div>
      <div className="cta-bar"><span className="grow" />
        <button className="btn primary big" data-testid="to-library" onClick={() => go('library')}>Browse the Library</button></div>
    </div>
  )
}
