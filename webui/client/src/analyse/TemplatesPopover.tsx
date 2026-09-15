/* Import: a popover of templates (builtin + saved in the throwaway DB copy). Picking one
   replaces the chain's steps; the name becomes the template's short name. */
import { useEffect, useState } from 'react'
import { ApiError, getTemplates, type Template } from '../api'
import { navigate } from '../state'

export const shortName = (t: Template) => t.name.split(' · ')[0].trim()

export function TemplatesPopover({ onPick, onClose }: { onPick: (t: Template) => void; onClose: () => void }) {
  const [items, setItems] = useState<Template[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    getTemplates().then(t => { if (alive) setItems(t) }).catch(e => { if (alive) setErr(e instanceof ApiError ? e.message : String(e)) })
    return () => { alive = false }
  }, [])
  return (
    <div className="an-pop" style={{ width: 460 }} data-testid="templates-popover">
      <h4>Templates <span>{items ? `${items.length} · builtin and saved` : ''}</span><button className="btn sm" style={{ marginLeft: 'auto' }} onClick={onClose}>Close</button></h4>
      {err && <div className="error-card"><h3>templates failed to load</h3><div className="mono">{err}</div></div>}
      {!items && !err && <div className="an-pop-note">loading…</div>}
      {items?.map(t => (
        <div key={String(t.id)} className="an-pop-item btnlike" onClick={() => onPick(t)} data-testid={`template-${shortName(t)}`}>
          <span className={`chip ${t.builtin ? 'grey' : 'green'}`} style={{ height: 20, fontSize: 10 }}>{t.builtin ? 'builtin' : 'saved'}</span>
          <div className="grow" style={{ minWidth: 0 }}>
            <div className="b" style={{ fontFamily: 'var(--font-ui)', fontSize: 12.5 }}>{shortName(t)}</div>
            <div className="muted" style={{ fontSize: 10.5 }}>{t.steps.map(s => s.algorithm).join(' › ')}</div>
          </div>
          <span className="muted">{t.steps.length} stage{t.steps.length === 1 ? '' : 's'}</span>
        </div>
      ))}
      <div className="an-pop-note">importing replaces the chain on the canvas · the last run's rows are forgotten</div>
      <h4 style={{ marginTop: 10 }}>Concept-frame chains <span>demo blocks · simulated runs · fixture results</span></h4>
      {[['drop_motifs9', 'Source › 01 Baseline › 02 Noise floor › 03 Encoding › 04 Detection (B24)'], ['mp_span_CH4', 'Signal → Scores · 6 h span'], ['mp_full_channel_CH4', 'whole channel · a stage over the local ceiling'], ['sax_vs_mp', 'paused run a-0098 · result in place'], ['spiketrain_cnn_CH4', 'sliding windows › model stage › threshold']].map(([name, note]) => (
        <div key={name} className="an-pop-item btnlike" onClick={() => { onClose(); navigate(`analyse/chain?template=${name}&state=default`) }} data-testid={`demo-template-${name}`}>
          <span className="chip demo" style={{ height: 20, fontSize: 10 }}>demo</span>
          <div className="grow" style={{ minWidth: 0 }}><div className="b" style={{ fontFamily: 'var(--font-ui)', fontSize: 12.5 }}>{name}</div><div className="muted" style={{ fontSize: 10.5 }}>{note}</div></div>
        </div>
      ))}
    </div>
  )
}
