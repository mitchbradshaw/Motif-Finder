/* Run history (frame chain-1b, decision P2): a pop-up behind the History button. Filters, a paged list of past runs,
 * Open, and Apply to source — disabled with the reason when the run's source type does not fit the current source. */
import { useState, type RefObject } from 'react'
import { useSourced } from '../../api/seam'
import { getRunHistory, type DemoHistoryRun, type DemoRowStatus } from '../../api/analyse'
import { Button, Checkbox, Dropdown, EmptyState, Icon, Pager, Popover, TextField, recordDemoWrite, usePagedList } from '../../kit'
import { DEMO_SCENARIOS } from '../../fixtures/analyse'
import { navigate } from '../../state'
import { fromScenario, type DemoChainState } from './chainState'

export function DemoHistoryPopover({ anchorRef, st, template, onClose, onApply, onSave }: { anchorRef: RefObject<HTMLButtonElement | null>; st: DemoChainState; template: string; onClose: () => void; onApply: (next: DemoChainState) => void; onSave: () => void }) {
  const q = useSourced(getRunHistory, [])
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('any')
  const [terminal, setTerminal] = useState('SpanSet')
  const [status, setStatus] = useState('any')
  const [recording, setRecording] = useState('any')
  const [fitsOnly, setFitsOnly] = useState(false)
  const [selected, setSelected] = useState<number>(131)
  const all = q.data ?? []
  const filtered = all.filter(r => (source === 'any' || r.sourceKind === source) && (terminal === 'any' || r.terminal === terminal) && (status === 'any' || r.status === status)
    && (recording === 'any' || r.recording === recording) && (!fitsOnly || !r.applyReason) && (!search.trim() || `${r.name} #${r.id} ${r.hash} ${r.chain.map(c => c.label).join(' ')}`.toLowerCase().includes(search.trim().toLowerCase())))
  const pg = usePagedList(filtered, 6)

  const apply = (r: DemoHistoryRun) => {
    const sc = r.template ? DEMO_SCENARIOS[r.template] : undefined
    if (!sc || r.template !== template) { onClose(); navigate(`analyse/chain?template=${r.template ?? 'drop_motifs9'}&state=fresh`); return }
    const base = fromScenario(sc)
    const steps = base.steps.map(s => ({ ...s, params: { ...s.params, ...(r.params?.[s.block] ?? {}) } }))
    let diverged = false
    const status: Record<string, DemoRowStatus> = Object.fromEntries(steps.map((s, i) => {
      const cur = st.steps[i]
      const same = !!cur && cur.block === s.block && JSON.stringify(cur.params) === JSON.stringify(s.params)
      if (!same) diverged = true
      return [s.uid, diverged ? 'stale' : st.status[cur!.uid] === 'cached' ? 'cached' : 'stale']
    }))
    recordDemoWrite('analyse', 'apply-history', { run: r.id, template })
    onApply({ ...base, steps, status, name: r.name, note: 'unsaved', lastRun: `#${r.id}`, saved: false })
  }

  return (
    <Popover open onClose={onClose} anchorRef={anchorRef} placement="bottom-end" width={940} flush testid="history-popover" ariaLabel="Run history" style={{ maxWidth: 'calc(100vw - 32px)' }}>
      <div className="hist2">
        <div className="hist2-head">
          <Icon name="clock" size={15} /><b>Run history</b><span className="mono muted">{all.length} runs · this workspace</span>
          <button className="icon-btn" style={{ marginLeft: 'auto' }} onClick={onClose} aria-label="close" data-testid="history-close"><Icon name="x" size={14} /></button>
        </div>
        <div className="hist2-filters">
          <TextField value={search} onChange={setSearch} placeholder="name, block, recipe hash" icon="search" width={240} testid="history-search" />
          <Dropdown prefix="source" value={source} onChange={setSource} options={[{ value: 'any', label: 'any' }, { value: 'Signal', label: 'Signal span' }, { value: 'SpanSet', label: 'SpanSet' }, { value: 'surrogate', label: 'surrogate' }]} active={source !== 'any'} />
          <Dropdown prefix="terminal" value={terminal} onChange={setTerminal} options={[{ value: 'any', label: 'any' }, { value: 'SpanSet', label: 'SpanSet' }, { value: 'Scores', label: 'Scores' }, { value: 'Features', label: 'Features' }]} active={terminal !== 'any'} testid="history-terminal" />
          <Dropdown prefix="status" value={status} onChange={setStatus} options={[{ value: 'any', label: 'any' }, { value: 'completed', label: 'completed' }, { value: 'running', label: 'running' }, { value: 'failed', label: 'failed' }]} active={status !== 'any'} />
          <Dropdown prefix="recording" value={recording} onChange={setRecording} options={[{ value: 'any', label: 'any' }, { value: 'M2_aug fs1', label: 'M2_aug fs1' }, { value: 'M3_jul', label: 'M3_jul' }]} active={recording !== 'any'} />
          <span style={{ marginLeft: 'auto' }}><Checkbox checked={fitsOnly} onChange={setFitsOnly} label="fits current source only" testid="history-fits-only" /></span>
        </div>
        <div className="hist2-cols"><span>run</span><span>chain</span><span>source</span><span>when</span><span>result</span></div>
        <div className="hist2-list">
          {q.loading && <div className="skeleton" style={{ height: 180, margin: 12 }} />}
          {q.error && <div className="error-card"><h3>history failed to load</h3><pre>{q.error.message}</pre></div>}
          {!q.loading && !pg.items.length && <EmptyState size="sm" title="No runs match" caption="clear a filter" action={<Button size="sm" onClick={() => { setSearch(''); setSource('any'); setTerminal('any'); setStatus('any'); setRecording('any'); setFitsOnly(false) }}>Clear filters</Button>} />}
          {pg.items.map(r => (
            <div key={r.id} className={`hist2-row${selected === r.id ? ' on' : ''}`} onClick={() => setSelected(r.id)} data-testid={`history-run-${r.id}`}>
              <div className="cells">
                <div><div className="nm">{r.name}</div><div className="id">#{r.id} · {r.hash}</div></div>
                <div className="chainc">{r.chain.map((c, k) => <span key={k} style={{ display: 'contents' }}>{k > 0 && <Icon name="chevron-right" size={10} />}<span className={`cc ${c.tone ?? ''}`}>{c.label}</span></span>)}</div>
                <div>{r.source}</div>
                <div>{r.when}</div>
                <div className="acts">
                  <Button size="sm" onClick={e => { e.stopPropagation(); onClose(); navigate(r.open) }} testid={`history-open-${r.id}`}>Open</Button>
                  <Button size="sm" icon="undo" variant={selected === r.id && !r.applyReason ? 'primary' : 'default'} disabled={!!r.applyReason} disabledReason={r.applyReason} onClick={e => { e.stopPropagation(); apply(r) }} testid={`history-apply-${r.id}`}>Apply to source</Button>
                </div>
              </div>
              {r.applyReason && <div className="why"><Icon name="x-circle" size={11} /> {r.applyReason}</div>}
              {selected === r.id && r.diff && <div className="diff" data-testid="history-diff"><Icon name="branch" size={12} /><b>{r.diff.text}</b><span className="amber">{r.diff.detail}</span><span className="muted" style={{ marginLeft: 'auto' }}>{r.diff.source}</span></div>}
            </div>
          ))}
        </div>
        <div className="hist2-foot">
          <span className="mono muted"><Icon name="alert-triangle" size={12} /> applying replaces the unsaved chain on the canvas</span>
          <Button icon="save" onClick={onSave} style={{ marginLeft: 'auto' }} testid="history-save-first">Save current chain first</Button>
          <Pager page={pg.page} pageCount={pg.pageCount} onPage={pg.setPage} format="range" total={pg.total} pageSize={6} testid="history-pager" />
        </div>
      </div>
    </Popover>
  )
}
