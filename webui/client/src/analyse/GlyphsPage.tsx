/* Analyse › Algorithm glyphs (frame chain-6b, spec §6.8 glyph row): the registry — one static picture per algorithm,
 * never drawn from data, the same at 44 × 26 on insert-stage cards and 272 × 96 in the detail panel. A card opens the
 * detail drawer (?focus=<block>): sizes side by side, registry name, colour key, where the block is used. */
import { useState } from 'react'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getDemoTemplates, getGlyphRegistry, type DemoBlock } from '../api/analyse'
import { Button, Chip, Drawer, EmptyState, KeyValue, Legend, TextField, copyToClipboard, useQueryState } from '../kit'
import { Glyph, glyphSource } from './glyphs'

const KEY = [
  { label: 'input / context', colour: '#9ca3af' }, { label: 'what the block emits', colour: '#0a84ff' }, { label: 'found / kept', colour: '#22a06b' },
  { label: 'cut / threshold', colour: '#e8900c' }, { label: 'discord / excluded', colour: '#e5484d' }, { label: 'exemplar / second input', colour: '#8e5cf7' },
]
const asAdapter = (b: DemoBlock) => ({ name: b.glyph, input_kind: (['features', 'views'].includes(b.input) ? 'spanset' : b.input) as never, output_kind: (['features', 'views'].includes(b.output) ? 'spanset' : b.output) as never })

export function GlyphsPage() {
  const reg = useSourced(getGlyphRegistry, [])
  const tpl = useSourced(getDemoTemplates, [])
  const toast = useToast()
  const [focus, setFocus] = useQueryState('focus', '')
  const [filter, setFilter] = useState('')
  const blocks = reg.data?.blocks ?? []
  const shown = blocks.filter(b => !filter.trim() || `${b.page_name} ${b.signature} ${b.glyph}`.toLowerCase().includes(filter.trim().toLowerCase()))
  const sel = blocks.find(b => b.name === focus) ?? null
  const usedBy = sel ? (tpl.data ?? []).filter(t => t.steps.some(s => s.block === sel.name)).map(t => t.name) : []

  return (
    <>
      <Header workspace="Analyse" page="Insert a stage" subtitle="glyph registry · every block registers one" search="Search spans, runs, families" demo />
      <div className="page"><div className="page-inner" data-testid="glyphs-page">
        <div className="gl-title">
          <div>
            <h1>Algorithm glyphs</h1>
            <div className="mono muted" style={{ fontSize: 11.5 }}>Drawn once per algorithm, never from data. Same picture at 44 × 26 on insert-stage cards and 272 × 96 in the detail panel.</div>
          </div>
          <TextField value={filter} onChange={setFilter} placeholder="filter glyphs" icon="search" width={220} testid="glyph-filter" />
        </div>
        <div className="gl-key" data-testid="glyph-key"><span className="mono muted">colour key</span><Legend items={KEY.map(k => ({ ...k, shape: 'line' as const }))} /></div>
        {reg.error && <div className="error-card"><h3>glyph registry failed to load</h3><pre>{reg.error.message}</pre></div>}
        {reg.loading && <div className="skeleton" style={{ height: 400 }} />}
        {!reg.loading && !shown.length && <EmptyState title="No glyph matches" caption="clear the filter" action={<Button size="sm" onClick={() => setFilter('')}>Clear</Button>} testid="glyph-empty" />}
        {(reg.data?.groups ?? []).map(g => {
          const items = shown.filter(b => b.glyph_group === g.key)
          if (!items.length) return null
          return (
            <section key={g.key} className="gl-group" data-testid={`glyph-group-${g.key}`}>
              <div className="gl-group-title mono">{g.title}</div>
              <div className="gl-grid">
                {items.map(b => (
                  <button key={b.name} className={`gl-card${focus === b.name ? ' on' : ''}`} onClick={() => setFocus(b.name)} data-testid={`glyph-${b.name}`} title={`${b.page_name} · ${b.signature}`}>
                    <div className="big"><Glyph adapter={asAdapter(b)} width={180} height={72} /></div>
                    <div className="foot"><Glyph adapter={asAdapter(b)} /><div style={{ minWidth: 0 }}><b>{b.page_name}</b><div className="sg">{b.signature}</div></div></div>
                  </button>
                ))}
              </div>
            </section>
          )
        })}
      </div></div>
      <Drawer open={!!sel} onClose={() => setFocus(null)} title={sel?.page_name ?? ''} width={400} testid="glyph-drawer">
        {sel && (
          <div className="gl-detail">
            <div className="mono" style={{ color: 'var(--blue-600)', fontSize: 11.5 }}>{sel.signature}</div>
            <div className="gl-sizes">
              <div><Glyph adapter={asAdapter(sel)} width={272} height={96} /><span className="mono muted">272 × 96 · detail panel</span></div>
              <div className="row" style={{ gap: 16, alignItems: 'flex-end' }}>
                <div><Glyph adapter={asAdapter(sel)} /><span className="mono muted">44 × 26 · cards</span></div>
                <div><Glyph adapter={asAdapter(sel)} width={88} height={52} /><span className="mono muted">88 × 52</span></div>
              </div>
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-2)' }}>{sel.description}</div>
            <KeyValue dense labelWidth={110} items={[
              { k: 'registry name', v: <span className="mono">{sel.glyph}</span> },
              { k: 'glyph', v: glyphSource(sel.glyph) === 'own' ? 'registered with the block' : 'type-signature fallback' },
              { k: 'category', v: sel.category }, { k: 'null', v: sel.has_null ? 'has a surrogate null' : 'no null' },
              { k: 'used by', v: usedBy.length ? usedBy.join(' · ') : 'no saved template yet' },
            ]} />
            {glyphSource(sel.glyph) !== 'own' && <Chip tone="amber" size="sm">no glyph registered · the signature glyph stands in</Chip>}
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <Button icon="copy" onClick={() => { void copyToClipboard(sel.glyph).then(ok => toast.push({ text: ok ? `copied ${sel.glyph}` : 'the clipboard refused the copy' })) }} testid="glyph-copy">Copy registry name</Button>
              <Button variant="primary" icon="plus" onClick={() => navigate('analyse/chain?template=drop_motifs9&state=default&modal=insert&at=4')} testid="glyph-insert">Find it in Insert a stage</Button>
            </div>
          </div>
        )}
      </Drawer>
    </>
  )
}
