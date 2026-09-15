/* Import a template into the current source (frame chain-1c): search, kind tabs, a list whose rows say whether each
 * template fits this source (and why not), and a detail panel with the blocks and what happens on apply. */
import { useState } from 'react'
import { useSourced } from '../../api/seam'
import { blockByName, getDemoTemplates, type DemoSource, type DemoTemplate } from '../../api/analyse'
import { Button, Chip, EmptyState, Icon, InfoTip, KeyValue, Modal, Seg, TextField, useNotWired } from '../../kit'
import { pad2 } from './chainState'

const KIND_TONE: Record<DemoTemplate['kind'], 'blue' | 'purple' | 'amber'> = { detection: 'blue', interrogation: 'purple', training: 'amber' }

export function ImportTemplateModal({ source, onClose, onApply }: { source: DemoSource; onClose: () => void; onApply: (name: string) => void }) {
  const q = useSourced(getDemoTemplates, [])
  const notWired = useNotWired()
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState<'all' | DemoTemplate['kind']>('all')
  const [selected, setSelected] = useState('drop_motifs9')
  const all = q.data ?? []
  const rows = all.filter(t => (kind === 'all' || t.kind === kind) && (!search.trim() || `${t.name} ${t.kind}`.toLowerCase().includes(search.trim().toLowerCase())))
  const sel = all.find(t => t.name === selected) ?? null
  const applyReason = !sel ? 'select a template' : !sel.fits ? sel.reason ?? 'does not fit this source' : undefined
  const spanLabel = source.chip.replace(/^Signal( span)? · /, '')
  return (
    <Modal open onClose={onClose} width={1024} testid="import-modal"
      title={<span className="row" style={{ gap: 8 }}><Icon name="download" size={16} /> Import a template</span>} subtitle={`into ${source.chip}`}
      footerNote={<Button icon="file" onClick={() => notWired('import a template from a .json file (validated against the registry before it replaces the chain)')} testid="import-json">Import .json file</Button>}
      footer={<>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" icon="undo" disabled={!!applyReason} disabledReason={applyReason} onClick={() => sel && onApply(sel.name)} testid="import-apply">Apply to this source</Button>
      </>}>
      {q.error && <div className="error-card"><h3>templates failed to load</h3><pre>{q.error.message}</pre></div>}
      <div className="imp-grid">
        <div style={{ minWidth: 0 }}>
          <div className="row" style={{ gap: 10, marginBottom: 10 }}>
            <TextField value={search} onChange={setSearch} placeholder="search templates" icon="search" block testid="import-search" autoFocus />
            <Seg options={[{ value: 'all', label: 'all' }, { value: 'detection', label: 'detection' }, { value: 'interrogation', label: 'interrogation' }, { value: 'training', label: 'training' }]} value={kind} onChange={v => setKind(v as typeof kind)} size="sm" testid="import-kind" />
          </div>
          <div className="imp-list" data-testid="import-list">
            {q.loading && <div className="skeleton" style={{ height: 200 }} />}
            {!q.loading && !rows.length && <EmptyState size="sm" title="No templates match" caption="clear the search or pick another kind" action={<Button size="sm" onClick={() => { setSearch(''); setKind('all') }}>Clear</Button>} />}
            {rows.map(t => (
              <button key={t.name} className={`imp-row${selected === t.name ? ' on' : ''}${t.fits ? '' : ' nofit'}`} onClick={() => setSelected(t.name)} data-testid={`import-row-${t.name}`} title={t.fits ? undefined : t.reason}>
                <div className="r1"><b>{t.name}</b><Chip tone={KIND_TONE[t.kind]} size="sm">{t.kind}</Chip><span className="muted mono" style={{ marginLeft: 'auto', fontSize: 10.5 }}>{t.version} · {t.date}</span></div>
                <div className="r2"><span>needs {t.needs}{t.wholeChannel ? ' · whole channel' : ''} · {t.blocks} blocks{t.sideInputs.startsWith('exemplar') ? ' · 1 side-input' : ''}</span>
                  <span className={`note ${t.noteTone}`}><Icon name={t.noteTone === 'green' ? 'check-circle' : t.noteTone === 'amber' ? 'alert-triangle' : 'x-circle'} size={11} /> {t.note}</span></div>
              </button>
            ))}
          </div>
        </div>
        <div className="imp-detail" data-testid="import-detail">
          {sel ? (
            <>
              <h3>{sel.name}</h3>
              <div className="mono muted" style={{ fontSize: 11 }}>{sel.kind} template · {sel.version} · recipe {sel.recipe} · code {sel.code}</div>
              <div className="imp-steps">
                {sel.steps.map((s, i) => { const b = blockByName(s.block); return <div key={i} className="imp-step"><span className="muted mono">{pad2(i + 1)}</span><b>{b?.page_name ?? s.block}</b><span className="mono muted" style={{ fontSize: 10.5 }}>{b?.signature}</span><span className="mono" style={{ marginLeft: 'auto', fontSize: 11 }}>{s.summary}</span></div> })}
              </div>
              <div className="imp-apply">
                <div className="row" style={{ gap: 6, marginBottom: 6 }}><b>On apply</b><InfoTip title="On apply">The template's blocks replace the chain on the canvas and bind to this source. The last run's rows are forgotten.</InfoTip></div>
                <KeyValue dense items={[{ k: 'recording + span', v: `this source · ${spanLabel}` }, { k: 'side-inputs', v: sel.sideInputs }, { k: 'surrogate', v: 'phase-rand · 200× · seed from template' }]} labelWidth={130} />
              </div>
              {!sel.fits && <div className="k-callout red" style={{ marginTop: 8 }}><Icon name="x-circle" size={13} /> {sel.reason}</div>}
              {sel.wholeChannel && <div className="k-callout amber" style={{ marginTop: 8 }}><Icon name="alert-triangle" size={13} /> expects a whole channel · this span is 50 s — applying works, the training stages will say the windows are too few</div>}
              <div className="mono muted" style={{ fontSize: 10.5, marginTop: 8 }}><Icon name="info" size={11} /> templates store no recording or span — scores stay with runs</div>
            </>
          ) : <EmptyState size="sm" title="Select a template" caption="its blocks and what applying does appear here" />}
        </div>
      </div>
    </Modal>
  )
}
