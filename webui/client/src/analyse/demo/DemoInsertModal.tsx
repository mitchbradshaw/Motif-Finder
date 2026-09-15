/* Insert a stage in a demo chain (frame chain-2, spec §6.4): the type contract as three pills, every demo block as a
 * card — incompatible ones visible and disabled with their reason — and a detail panel with defaults, cost, null and
 * what goes stale. The live chain keeps its own modal (InsertStageModal.tsx) against the bridge's registry. */
import { useMemo, useState } from 'react'
import { blockByName, DEMO_KIND_LABEL, demoCompatibleAt, type DemoBlock, type DemoStep } from '../../api/analyse'
import { Button, Dropdown, Icon, InfoTip, Modal, Seg, TextField, Toggle } from '../../kit'
import { Glyph } from '../glyphs'
import { pad2 } from './chainState'

const CATS = ['all', 'preprocess', 'encode', 'detect', 'cluster', 'model', 'control'] as const
const glyphAdapter = (b: DemoBlock) => ({ name: b.glyph, input_kind: (b.input === 'features' || b.input === 'views' ? 'spanset' : b.input) as never, output_kind: (b.output === 'features' || b.output === 'views' ? 'spanset' : b.output) as never })

export function DemoInsertModal({ steps, position, onClose, onInsert }: { steps: DemoStep[]; position: number; onClose: () => void; onInsert: (block: string, openSettings: boolean) => void }) {
  const compat = useMemo(() => demoCompatibleAt(steps, position), [steps, position])
  const [q, setQ] = useState('')
  const [cat, setCat] = useState<(typeof CATS)[number]>('all')
  const [sort, setSort] = useState('fits')
  const [showIncompat, setShowIncompat] = useState(true)
  const firstFit = compat.fits.find(f => f.ok)?.block.name ?? null
  const [selected, setSelected] = useState<string | null>(compat.fits.some(f => f.ok && f.block.name === 'demo.run_length') ? 'demo.run_length' : firstFit)
  const atEnd = position >= steps.length
  const nameOf = (s: DemoStep | undefined, i: number) => s ? `${pad2(i + 1)} ${blockByName(s.block)?.page_name ?? s.block}` : 'Source'
  const prevName = position > 0 ? nameOf(steps[position - 1], position - 1) : 'Source'
  const nextName = atEnd ? null : nameOf(steps[position], position)
  const sel = selected ? blockByName(selected) ?? null : null

  const list = useMemo(() => {
    let rows = compat.fits.filter(f => cat === 'all' || f.block.category === cat)
    if (q.trim()) { const s = q.trim().toLowerCase(); rows = rows.filter(f => `${f.block.page_name} ${f.block.signature} ${f.block.description}`.toLowerCase().includes(s)) }
    if (sort === 'name') rows = [...rows].sort((a, b) => a.block.page_name.localeCompare(b.block.page_name))
    return { fits: rows.filter(f => f.ok), nofit: rows.filter(f => !f.ok) }
  }, [compat, cat, q, sort])
  const nFit = compat.fits.filter(f => f.ok).length

  const card = (f: (typeof compat.fits)[number]) => {
    const b = f.block
    return (
      <button key={b.name} className={`ins-card${f.ok ? '' : ' nofit'}${selected === b.name ? ' selected' : ''}`} disabled={!f.ok} aria-disabled={!f.ok} onClick={() => f.ok && setSelected(b.name)} onDoubleClick={() => f.ok && onInsert(b.name, false)}
        data-testid={`modal-card-${b.name}`} title={f.ok ? b.description : f.reason}>
        <div className="hd"><Glyph adapter={glyphAdapter(b)} /><div style={{ minWidth: 0 }}><div className="nm">{b.page_name}</div><div className="sg">{b.signature}</div></div></div>
        <div className="chips">
          <span className={b.ceiling_note ? 'p' : ''} title={b.ceiling_note}>{b.cost}</span>
          <span className={b.has_null ? 'g' : ''}>{b.has_null ? 'has null' : 'no null'}</span>
          {b.side && <span className="p">needs {b.side}</span>}
        </div>
        <div className={`fit${f.ok ? '' : ' no'}`}>{f.ok ? <><Icon name="check-circle" size={11} /> fits here</> : <><Icon name="x-circle" size={11} /> {f.reason}</>}</div>
      </button>
    )
  }

  const emits = sel ? DEMO_KIND_LABEL[sel.output] : compat.nextRequires ? DEMO_KIND_LABEL[compat.nextRequires] : '?'
  return (
    <Modal open onClose={onClose} width={1100} flushBody testid="insert-modal"
      title={<span className="row" style={{ gap: 8 }}><Icon name="plus" size={16} /> Insert a stage</span>}
      subtitle={atEnd ? 'at the end of the chain' : `between ${prevName} and ${nextName}`}
      footerNote={<span className="mono muted" style={{ fontSize: 11 }}>{compat.fits.length} blocks in the registry · a new technique is one adapter file</span>}
      footer={<>
        <Button onClick={onClose} testid="modal-cancel">Cancel</Button>
        <Button icon="plus" disabled={!sel} disabledReason="select a block that fits" onClick={() => sel && onInsert(sel.name, false)} testid="modal-insert">Insert</Button>
        <Button variant="primary" icon="arrow-right" disabled={!sel} disabledReason="select a block that fits" onClick={() => sel && onInsert(sel.name, true)} testid="modal-insert-open">Insert and open settings</Button>
      </>}>
      <div className="ins-demo">
        <div className="ins-ribbon" data-testid="modal-ribbon">
          <span>chain</span>
          <span className="rc"><Icon name="circle-dashed" size={9} /> Source</span>
          {steps.map((s, i) => (
            <span key={s.uid} style={{ display: 'contents' }}>
              {i === position && <><Icon name="chevron-right" size={11} /><span className="rc new">+ new stage</span></>}
              <Icon name="chevron-right" size={11} /><span className="rc"><span className="muted">{pad2(i + 1)}</span>&nbsp;{blockByName(s.block)?.short ?? s.block}</span>
            </span>
          ))}
          {atEnd && <><Icon name="chevron-right" size={11} /><span className="rc new">+ new stage</span></>}
          <span className="note">{atEnd ? 'inserting at the end changes the terminal type' : `inserting makes ${pad2(position + 1)} stale`}</span>
        </div>
        <div className="ins-pills" data-testid="modal-contract">
          <span className="ins-pill">{position === 0 ? 'Source' : pad2(position)} outputs <b>{DEMO_KIND_LABEL[compat.producing]}</b></span>
          <Icon name="arrow-right" size={12} />
          <span className="ins-pill new">new stage accepts <b className="a">{DEMO_KIND_LABEL[compat.producing]}</b> → emits <b className="a">{emits}</b></span>
          <Icon name="arrow-right" size={12} />
          {compat.nextRequires ? <span className="ins-pill">{pad2(position + 1)} requires <b>{DEMO_KIND_LABEL[compat.nextRequires]}</b></span> : <span className="ins-pill" style={{ background: 'var(--grey-100)' }}>end of chain · terminal becomes <b>{emits}</b></span>}
          <span className="count" data-testid="modal-fit-count">{nFit} of {compat.fits.length} blocks fit <InfoTip title="Two constraints">A stage inserted between two blocks must accept what arrives and emit what the next stage requires. At the end it has one constraint — and it changes the chain's terminal type.</InfoTip></span>
        </div>
        <div className="ins-controls">
          <TextField value={q} onChange={setQ} placeholder="search blocks" icon="search" width={250} testid="modal-search" autoFocus />
          <Seg options={CATS.map(c => ({ value: c, label: c }))} value={cat} onChange={v => setCat(v)} size="sm" testid="modal-category" />
          <span style={{ flex: 1 }} />
          <Dropdown prefix="sort" value={sort} onChange={setSort} options={[{ value: 'fits', label: 'fits first' }, { value: 'registry', label: 'registry order' }, { value: 'name', label: 'name' }]} testid="modal-sort" />
          <Toggle checked={showIncompat} onChange={setShowIncompat} label="show incompatible" tone="blue" testid="modal-show-incompatible" />
        </div>
        <div className="ins-body">
          <div className="ins-grid-wrap" data-testid="modal-cards">
            {sort === 'registry' ? (
              <div className="ins-grid">{compat.fits.filter(f => (cat === 'all' || f.block.category === cat) && (showIncompat || f.ok) && (!q.trim() || f.block.page_name.toLowerCase().includes(q.trim().toLowerCase()))).map(card)}</div>
            ) : (
              <>
                <div className="ins-group">Fits here <span>{list.fits.length}</span></div>
                {list.fits.length ? <div className="ins-grid">{list.fits.map(card)}</div> : <div className="mono muted small" style={{ marginBottom: 14 }} data-testid="modal-no-fit">no block {q ? `matching “${q}” ` : ''}accepts {DEMO_KIND_LABEL[compat.producing]} here{compat.nextRequires ? ` and emits ${DEMO_KIND_LABEL[compat.nextRequires]}` : ''}</div>}
                {showIncompat && <><div className="ins-group">Doesn't fit at this point <span>{list.nofit.length} · reasons shown</span></div><div className="ins-grid">{list.nofit.map(card)}</div></>}
              </>
            )}
          </div>
          <div className="ins-detail" data-testid="modal-detail">
            {sel ? (
              <>
                <h3>{sel.page_name}</h3>
                <div className="sg">{sel.signature}</div>
                <div className="glyph"><Glyph adapter={glyphAdapter(sel)} width={272} height={96} /></div>
                <div className="desc">{sel.description}</div>
                <div className="defaults">
                  <div className="k">defaults</div>
                  <div className="kv2">{sel.defaults.map(([k, val]) => <span key={k} style={{ display: 'contents' }}><span className="muted">{k}</span><span style={{ textAlign: 'right' }}>{val}</span></span>)}</div>
                </div>
                <div className="tiles">
                  <div className="tile"><div className="k">est. cost</div><div className="v">{sel.cost.replace('≈ ', '')}</div></div>
                  <div className="tile"><div className="k">null</div><div className="v" style={{ color: sel.has_null ? '#15794f' : undefined }}>{sel.has_null ? 'yes' : 'no'}</div></div>
                  <div className="tile"><div className="k">side-inputs</div><div className="v">{sel.side ?? 'none'}</div></div>
                </div>
                {!atEnd && <div className="amber" data-testid="modal-stale-note"><Icon name="clock" size={11} /> {pad2(position + 1)} goes stale · 00–{pad2(position)} stay cached</div>}
                <div className="grey"><Icon name="info" size={11} /> inserting at the end changes the terminal type</div>
              </>
            ) : <div className="mono muted small">select a block that fits to see its defaults and cost</div>}
          </div>
        </div>
      </div>
    </Modal>
  )
}
