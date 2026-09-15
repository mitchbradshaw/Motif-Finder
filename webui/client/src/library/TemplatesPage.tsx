/* library.templates — frame library-7 (§8.9): every saved chain with version, signature, stage glyph strip, badges, latest
 * score with its scope and run count; the rail shows stages with locked parameters, versions with diff, scores by run,
 * and the hand-offs. Duplicate / import / archive write to the in-memory store. */
import { useMemo, useState } from 'react'
import {
  BlockGlyph, Button, ChainRibbon, CodeBlock, EmptyState, Icon, InfoTip, Modal, Page, Seg, SelectField, SourceGlyph, TextField, recordDemoWrite, useDemoState, useQueryState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getTemplates, type Template, type TemplateKind } from '../api/library'
import { LoadFailed, Loading, SectionBar, useExternalNavKey } from './chrome'

const PAGE = 7
const KIND_TONE: Record<TemplateKind, string> = { detection: 't-blue', 'seed search': 't-purple', training: 't-grey', interrogation: 't-grey' }

export function TemplatesPage() {
  const tpl = useSourced(getTemplates, [])
  const [archived, setArchived] = useDemoState<string[]>('library.templates.archived', () => [])
  const [added, setAdded] = useDemoState<Template[]>('library.templates.added', () => [])
  const [, setModal] = useQueryState('modal', '')
  const navKey = useExternalNavKey()
  const all = useMemo(() => [...added, ...(tpl.data ?? [])].filter(t => !archived.includes(t.name)), [tpl.data, added, archived])
  return (
    <>
      <Header workspace="Library" page="Templates" subtitle={`${tpl.data ? all.length : '…'} saved`} search="Search spans, runs, families" demo={tpl.source === 'demo'} />
      <Page testid="templates-page">
        <SectionBar section="templates" templatesCount={tpl.data ? all.length : undefined}
          actions={<span className="row lib-ui-btn" style={{ gap: 8 }}>
            <Button icon="link" testid="new-in-analyse" onClick={() => navigate('analyse/chain')}>New in Analyse</Button>
            <Button icon="download" testid="import-json" onClick={() => setModal('import')}>Import JSON</Button>
          </span>} />
        {tpl.error && <LoadFailed what="the templates" error={tpl.error} onRetry={tpl.reload} />}
        {tpl.loading && <Loading height={680} testid="templates-loading" />}
        {tpl.data && <Templates key={navKey} all={all} existing={tpl.data} setArchived={setArchived} setAdded={setAdded} />}
      </Page>
    </>
  )
}

function Templates({ all, existing, setArchived, setAdded }: { all: Template[]; existing: Template[]; setArchived: (f: (x: string[]) => string[]) => void; setAdded: (f: (x: Template[]) => Template[]) => void }) {
  const [kindQ, setKindQ] = useQueryState<'all' | TemplateKind>('kind', 'all')
  const [modelQ, setModelQ] = useQueryState('model', '')
  const [pageQ, setPageQ] = useQueryState('page', '1')
  const [tplQ, setTplQ] = useQueryState('template', 'mp_drops_v3')
  const [modal, setModal] = useQueryState('modal', '')
  const [fromQ] = useQueryState('from', '')
  const [sort, setSort] = useState<'last run' | 'name' | 'runs' | 'version'>('last run')
  const { push } = useToast()
  const filtered = all.filter(t => (kindQ === 'all' || t.kind === kindQ) && (modelQ !== '1' || t.containsModel))
  const ordered = sort === 'name' ? [...filtered].sort((a, b) => a.name.localeCompare(b.name)) : sort === 'runs' ? [...filtered].sort((a, b) => b.runCount - a.runCount) : sort === 'version' ? [...filtered].sort((a, b) => b.version - a.version) : filtered
  const pageCount = Math.max(1, Math.ceil(ordered.length / PAGE))
  const page = Math.min(pageCount, Math.max(1, Number(pageQ) || 1))
  const items = ordered.slice((page - 1) * PAGE, page * PAGE)
  const selected = all.find(t => t.name === tplQ) ?? items[0] ?? null
  const others = ordered.filter(t => !items.includes(t)).map(t => t.name)
  const nextName = (base: string) => { let n = `${base}_copy`, i = 2; while (all.some(t => t.name === n)) n = `${base}_copy${i++}`; return n }
  const archive = (t: Template) => {
    setArchived(a => [...a, t.name]); recordDemoWrite('library', 'template.archive', { name: t.name, version: t.version }); setModal(null); setTplQ(null)
    push({ text: `Archived ${t.name} v${t.version} · runs keep their template version · not wired yet: POST /api/templates/${t.name}/archive`, action: { label: 'Undo', onClick: () => setArchived(a => a.filter(x => x !== t.name)) } })
  }
  const duplicate = (t: Template) => {
    const name = nextName(t.name)
    setAdded(a => [{ ...t, name, version: 1, runs: '0 runs', runCount: 0, lastRun: '—', latest: null, latestMuted: 'not yet run', scores: [], versions: [{ v: 1, change: `duplicated from ${t.name} v${t.version}`, date: '16 Sep' }] }, ...a])
    recordDemoWrite('library', 'template.duplicate', { from: t.name, name }); setTplQ(name); setPageQ(null)
    push({ text: `Duplicated as ${name} v1 · not wired yet: POST /api/templates` })
  }

  return (
    <div className="lib-split">
      <div className="stack" style={{ gap: 10, minWidth: 0 }}>
        <div className="k-card lib-filterbar" data-testid="template-filters">
          <Seg size="sm" ariaLabel="kind" testid="kind-seg" value={kindQ} onChange={v => { setKindQ(v); setPageQ(null) }} options={[{ value: 'all', label: 'all' }, { value: 'detection', label: 'detection' }, { value: 'seed search', label: 'seed search' }, { value: 'training', label: 'training' }, { value: 'interrogation', label: 'interrogation' }]} />
          <button type="button" className={`k-chip ${modelQ === '1' ? 'blue' : 'outline'} k-chip-btn lg`} aria-pressed={modelQ === '1'} data-testid="model-stage-toggle" onClick={() => { setModelQ(modelQ === '1' ? null : '1'); setPageQ(null) }}><Icon name="cpu" size={13} />contains a Model stage</button>
          <span style={{ marginLeft: 'auto' }} className="lib-muted-label">sort</span>
          <SelectField value={sort} onChange={v => { setSort(v as typeof sort); setPageQ(null) }} width={150} testid="template-sort" ariaLabel="sort" options={['last run', 'name', 'runs', 'version'].map(o => ({ value: o, label: o }))} />
        </div>
        <div className="stack" style={{ gap: 10 }} data-testid="template-list" role="listbox" aria-label="templates" tabIndex={0}
          onKeyDown={e => { const i = items.findIndex(t => t.name === selected?.name); const d = e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0; if (d && items.length) { e.preventDefault(); setTplQ(items[Math.max(0, Math.min(items.length - 1, i + d))].name) } }}>
          {items.map(t => {
            const on = t.name === selected?.name
            return (
              <div key={t.name} role="option" aria-selected={on} className={`k-card lib-tcard${on ? ' selected' : ''}`} style={{ cursor: 'pointer', background: on ? '#f3f8ff' : undefined }} data-testid={`template-card-${t.name}`} onClick={() => setTplQ(t.name)}>
                <div className="stack" style={{ gap: 5, minWidth: 0 }}>
                  <div className="row" style={{ gap: 6 }}><span className="nm">{t.name}</span><span className="k-badge t-grey">v{t.version}</span>{t.badges.map(b => <span key={b.label} className={`k-badge t-${b.tone}`}>{b.label}</span>)}</div>
                  <span className="lib-cap">{t.signature}</span>
                  <ChainRibbon variant="thumbs" blocks={t.stages.map((s, i) => ({ id: `${t.name}-${i}`, label: s.name, glyph: s.glyph }))} ariaLabel={`${t.name} stages`} />
                </div>
                <div className="stack" style={{ gap: 3, paddingTop: 8 }}>
                  {t.latest ? <><span className="mono b" style={{ fontSize: 12 }}>{t.latest.text}</span><span className="lib-cap">{t.latest.scope}</span></> : <span className="mono small muted">{t.latestMuted}</span>}
                </div>
                <span className="lib-cap" style={{ paddingTop: 10, textAlign: 'right' }}>{t.runs}</span>
              </div>
            )
          })}
          {!items.length && <EmptyState title="No templates match" caption="no saved chain has this kind and a Model stage" action={<Button size="sm" testid="clear-template-filters" onClick={() => { setKindQ(null); setModelQ(null) }}>Clear filters</Button>} bordered testid="templates-filtered-empty" />}
        </div>
        <div className="row" data-testid="template-pager">
          <span className="lib-cap" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>{ordered.length ? `${(page - 1) * PAGE + 1}–${Math.min(ordered.length, page * PAGE)} of ${ordered.length}` : '0 of 0'}{others.length ? ` · also ${others.slice(0, 5).join(', ')}${others.length > 5 ? ' …' : ''}` : ''}</span>
          <span style={{ marginLeft: 'auto' }} />
          {page > 1 && <Button variant="link" testid="template-prev" onClick={() => setPageQ(page - 1 === 1 ? null : String(page - 1))}>‹ prev</Button>}
          <Button variant="link" testid="template-next" disabled={page >= pageCount} disabledReason="last page" onClick={() => setPageQ(String(page + 1))}>next ›</Button>
        </div>
      </div>
      {selected ? <TemplateRail t={selected} onDuplicate={() => duplicate(selected)} /> : <aside className="k-card lib-rail"><EmptyState size="sm" title="No template selected" caption="pick one from the list" /></aside>}

      <DiffModal t={selected} open={modal === 'diff' && !!selected} from={fromQ} onClose={() => setModal(null)} />
      <Modal open={modal === 'export' && !!selected} onClose={() => setModal(null)} title={`Export ${selected?.name} v${selected?.version}`} subtitle="template JSON · recipe and locked parameters" size="lg" testid="export-json-modal">
        {selected && <CodeBlock code={JSON.stringify({ name: selected.name, version: selected.version, kind: selected.kind, signature: selected.signature, recipe: selected.recipe, null: selected.nullModel, stages: selected.stages.map(s => ({ block: s.glyph, name: s.name, params: s.params })) }, null, 2)} filename={`${selected.name}.json`} maxHeight={380} testid="export-json-code" />}
      </Modal>
      <ImportJsonModal open={modal === 'import'} onClose={() => setModal(null)} existing={[...existing, ...all]} onImport={t => { setAdded(a => [t, ...a]); setTplQ(t.name); setPageQ(null); setModal(null) }} />
      <Modal open={modal === 'archive' && !!selected} onClose={() => setModal(null)} size="sm" title={`Archive ${selected?.name}?`} testid="archive-modal"
        footer={<><Button onClick={() => setModal(null)}>Cancel</Button><Button variant="danger-solid" testid="archive-confirm" onClick={() => selected && archive(selected)}>Archive</Button></>}>
        <p style={{ margin: 0 }}>Runs keep their template version; it leaves this list. {selected?.runCount ? `${selected.runs} recorded against it stay reproducible.` : ''}</p>
      </Modal>
    </div>
  )
}

function TemplateRail({ t, onDuplicate }: { t: Template; onDuplicate: () => void }) {
  const [, setModal] = useQueryState('modal', '')
  const [, setFrom] = useQueryState('from', '')
  const applyReason = t.kind === 'training' ? 'a training template produces a Model — launch it in Models' : t.kind === 'interrogation' ? 'an interrogation chain reads a family (SpanSet); it does not search a recording' : null
  const head = t.scoreHeader ?? ['run', 'prec', 'recall']
  return (
    <aside className="k-card lib-rail" data-testid="template-rail" aria-label={t.name}>
      <div className="row"><b className="mono" style={{ fontSize: 14 }}>{t.name}</b><span className="k-badge t-grey">v{t.version}</span><span className={`k-badge ${KIND_TONE[t.kind]}`} style={{ marginLeft: 'auto' }}>{t.kind}</span></div>
      <span className="lib-cap" style={{ marginTop: -6 }}>recipe {t.recipe} · null: {t.nullModel}</span>
      <span className="lib-cap" style={{ fontSize: 11 }}>stages · parameters locked</span>
      <div className="stack" style={{ gap: 6 }} data-testid="template-stages">
        {t.stages.map((s, i) => (
          <div key={i} className="lib-stage">
            {s.glyph === 'source' ? <SourceGlyph width={36} height={24} /> : <BlockGlyph name={s.glyph} width={36} height={24} />}
            <span className="stack" style={{ gap: 0, minWidth: 0 }}><span style={{ fontSize: 12, fontWeight: 600 }}>{s.name}</span><span className="lib-cap">{s.params}</span></span>
          </div>
        ))}
      </div>
      <span className="lib-cap" style={{ fontSize: 11 }}>versions</span>
      <div className="stack" style={{ gap: 2 }} data-testid="template-versions">
        {t.versions.map((v, i) => (
          <div key={v.v} className="lib-vrow">
            <span className={`k-badge ${i === 0 ? 't-blue' : 't-grey'}`}>v{v.v}</span><span style={{ color: i === 0 ? 'var(--text)' : 'var(--muted)' }}>{v.change} · {v.date}</span>
            {i > 0 && <Button variant="link" size="sm" className="diff" testid={`diff-v${v.v}`} onClick={() => { setFrom(`v${v.v}`); setModal('diff') }}>diff</Button>}
          </div>
        ))}
      </div>
      <span className="lib-cap" style={{ fontSize: 11 }}>scores belong to runs <InfoTip title="scores belong to runs">a template has no score of its own; each run scores it on that run's scope against reviewed spans (§4.8)</InfoTip></span>
      {t.scores.length ? <>
        <table className="lib-scores" data-testid="template-scores">
          <thead><tr><th>{head[0]}</th><th>scope</th><th className="num">{head[1] === 'prec' ? 'prec' : 'prec'}</th><th className="num">recall</th><th className="num">× null</th></tr></thead>
          <tbody>{t.scores.map(s => (
            <tr key={s.run}>
              <td><button type="button" className="lib-plain mono" style={{ color: 'var(--blue)', fontSize: 11 }} onClick={() => navigate(s.run.startsWith('j-') ? `jobs/cluster/${s.run}` : s.run.startsWith('#') ? `analyse/chain?run=${s.run.slice(1)}` : `discovery/runs?run=${s.run}`)}>{s.run}</button></td>
              <td title={s.scopeFull}>{s.scope}</td><td className="num">{s.prec?.toFixed(2) ?? '—'}</td><td className="num">{s.recall == null ? '—' : s.recall.toFixed(2)}</td><td className="num">{s.xNull ?? '—'}</td>
            </tr>
          ))}</tbody>
        </table>
        {t.scores.some(s => s.recall == null) && <span className="lib-cap">recall “—”: no reviewed overlap on that scope</span>}
      </> : <EmptyState size="sm" icon="bar-chart" title={t.latestMuted ?? 'not yet scored'} caption={`${t.runs} · nothing claims a score before a run`} testid="template-scores-empty" />}
      <div className="lib-rail-actions">
        <Button variant="primary" icon="target" iconRight="arrow-right" testid="apply-in-discovery" disabled={!!applyReason} disabledReason={applyReason ?? undefined} onClick={() => navigate(`discovery/runs?modal=add-template&template=${t.name}`)}>Apply in Discovery</Button>
        {t.kind === 'training'
          ? <Button icon="rocket" iconRight="arrow-right" testid="launch-in-models" onClick={() => navigate(`models/launch?template=${t.name}`)}>Launch in Models</Button>
          : <Button icon="link" iconRight="arrow-right" testid="open-in-analyse" onClick={() => navigate(t.kind === 'interrogation' ? `analyse/interrogation?template=${t.name}` : `analyse/chain?template=${t.name}`)}>Open in Analyse</Button>}
        <span className="row" style={{ width: '100%', gap: 14 }}>
          <Button variant="link" icon="copy" testid="duplicate-template" onClick={onDuplicate}>Duplicate</Button>
          <Button variant="link" icon="upload" testid="export-json" onClick={() => setModal('export')}>Export JSON</Button>
          <Button variant="link" icon="inbox" testid="archive-template" style={{ marginLeft: 'auto' }} onClick={() => setModal('archive')}>Archive</Button>
        </span>
      </div>
    </aside>
  )
}

function DiffModal({ t, open, from, onClose }: { t: Template | null; open: boolean; from: string; onClose: () => void }) {
  if (!t) return null
  const fromV = Number(from.replace('v', '')) || (t.versions[1]?.v ?? 1)
  const to = t.versions.find(v => v.v === fromV + 1)
  const hasTo = !!to
  return (
    <Modal open={open} onClose={onClose} size="md" title={`${t.name} · v${fromV} → v${hasTo ? fromV + 1 : '?'}`} subtitle={to ? `${to.change} · ${to.date}` : 'no later version'} testid="diff-modal">
      {to?.diff?.length ? <div className="stack" style={{ gap: 4 }}>
        {to.diff.map((d, i) => (
          <div key={i} className="stack" style={{ gap: 2 }}>
            <span className="lib-cap">{d.param}</span>
            <div className="lib-diff-row del"><span>−</span><span>{d.from}</span></div>
            <div className="lib-diff-row add"><span>+</span><span>{d.to}</span></div>
          </div>
        ))}
      </div> : <EmptyState size="sm" title="No parameter diff recorded" caption={to ? to.change : `v${fromV} is the latest version`} />}
    </Modal>
  )
}

function ImportJsonModal({ open, onClose, existing, onImport }: { open: boolean; onClose: () => void; existing: Template[]; onImport: (t: Template) => void }) {
  const [text, setText] = useState('')
  const { push } = useToast()
  const parsed = useMemo((): { t: Template | null; error: string | null; note?: string } => {
    if (!text.trim()) return { t: null, error: null }
    let j: unknown
    try { j = JSON.parse(text) } catch (e) { return { t: null, error: `not valid JSON: ${(e as Error).message}` } }
    const o = j as { name?: unknown; stages?: unknown; kind?: unknown; signature?: unknown }
    if (typeof o.name !== 'string' || !/^[a-z0-9_-]{3,48}$/i.test(o.name)) return { t: null, error: '`name` must be 3–48 letters, digits, _ or -' }
    if (!Array.isArray(o.stages) || !o.stages.length) return { t: null, error: '`stages` must be a non-empty list' }
    const same = existing.filter(x => x.name === o.name)
    const version = same.length ? Math.max(...same.map(x => x.version)) + 1 : 1
    const kind = (['detection', 'seed search', 'training', 'interrogation'] as const).includes(o.kind as TemplateKind) ? o.kind as TemplateKind : 'detection'
    const t: Template = {
      name: o.name, version, kind, signature: typeof o.signature === 'string' ? o.signature : 'Signal → SpanSet', badges: [], containsModel: false, recipe: 'new…hash', nullModel: 'circular shift 200×',
      stages: [{ glyph: 'source', name: 'Source', params: 'one channel · any recording' }, ...(o.stages as { block?: string; name?: string; params?: string }[]).map(s => ({ glyph: s.block ?? 'threshold', name: s.name ?? s.block ?? 'stage', params: s.params ?? '' }))],
      latest: null, latestMuted: 'not yet run', runs: '0 runs', runCount: 0, lastRun: '—', versions: [{ v: version, change: 'imported from JSON', date: '16 Sep' }], scores: [],
    }
    return { t, error: null, note: same.length ? `saves as ${o.name} v${version}` : undefined }
  }, [text, existing])
  return (
    <Modal open={open} onClose={onClose} size="lg" title="Import template JSON" subtitle="a template exported from this or another installation" testid="import-json-modal"
      footerNote={parsed.note}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon="download" testid="import-json-confirm" disabled={!parsed.t} disabledReason={parsed.error ?? 'paste a template JSON'}
        onClick={() => { if (!parsed.t) return; onImport(parsed.t); recordDemoWrite('library', 'template.import', { name: parsed.t.name, version: parsed.t.version }); push({ text: `Imported ${parsed.t.name} v${parsed.t.version} · not wired yet: POST /api/templates/import` }); setText('') }}>Import</Button></>}>
      <div className="stack" style={{ gap: 8 }}>
        <TextField multiline rows={10} value={text} onChange={setText} placeholder={'{ "name": "mp_drops_v4", "kind": "detection", "stages": [{ "block": "matrix_profile", "name": "Matrix profile", "params": "m = 120 s" }] }'} invalid={!!parsed.error} block testid="import-json-text" />
        {parsed.error && <span className="k-field-error" role="alert" data-testid="import-json-error"><Icon name="alert-circle" size={11} />{parsed.error}</span>}
        {parsed.t && <span className="lib-cap" data-testid="import-json-ok"><Icon name="check-circle" size={11} style={{ color: 'var(--green)', verticalAlign: -1 }} /> {parsed.t.name} v{parsed.t.version} · {parsed.t.stages.length - 1} stages · {parsed.t.kind}</span>}
      </div>
    </Modal>
  )
}
