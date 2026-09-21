/* library.templates — frame library-7 (§8.9): every saved chain with version, signature, stage glyph strip, badges
 * and run count; the rail shows stages with locked parameters, versions, scores by run, and the hand-offs.
 *
 * Live over `GET /api/library/templates`, which maps the REAL `templates` table (§4.5: there is no second
 * template store). Three things changed, and one of them is a gap this page now states instead of hiding:
 *
 *   - **`versions`, `scores`, `latest` and `lastRun` come back EMPTY, for every template, always.** No version
 *     history and no per-run scoring table exists anywhere in the schema. The old page rendered an empty
 *     versions list and an empty-state captioned "not yet scored", which reads as "this template has never been
 *     run" — a different and false claim, since `runCount` is real and often non-zero. Both now say *not
 *     recorded* and name what is missing. This is a schema gap, not a wiring failure.
 *   - templates are identified by the row's `id` where the bridge supplies one (`keyOf`), not by name alone:
 *     `api.ts`'s `Template` is id-keyed and two rows may legitimately share a name across versions.
 *   - the "last run" sort is gone (`lastRun` is never recorded, so it sorted nothing), the duplicate stamp is
 *     today rather than the frozen `'16 Sep'`, and the score-table run link no longer guesses the workspace
 *     from a `j-` / `#` prefix that only fixture run ids carried.
 *
 * Duplicate / import / archive remain in-memory: there is no template write route on the bridge yet, and each
 * one says so in its toast.
 */
import { useMemo, useState } from 'react'
import {
  BlockGlyph, Button, Callout, ChainRibbon, CodeBlock, EmptyState, Icon, InfoTip, Modal, Page, Seg, SelectField, SourceGlyph, TextField, recordDemoWrite, useDemoState, useQueryState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getTemplates, type Template, type TemplateKind } from '../api/library'
import { LoadFailed, Loading, SectionBar, useExternalNavKey } from './chrome'

const PAGE = 7
const KIND_TONE: Record<TemplateKind, string> = { detection: 't-blue', 'seed search': 't-purple', training: 't-grey', interrogation: 't-grey' }

/** A template's stable identity. The bridge carries the `templates` row id on the payload; the presentation
 *  type does not declare it, so it is read defensively. Falling back to the name keeps a locally-duplicated
 *  template (which has no row of its own) addressable. */
const keyOf = (t: Template): string => {
  const id = (t as Template & { id?: number }).id
  return id == null ? t.name : `#${id}`
}
/** Today, in the same `D Mon` form the version rows use. Computed per call, not frozen at module load. */
const today = () => new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })

export function TemplatesPage() {
  const tpl = useSourced(getTemplates, [])
  const [archived, setArchived] = useDemoState<string[]>('library.templates.archived', () => [])
  const [added, setAdded] = useDemoState<Template[]>('library.templates.added', () => [])
  const [, setModal] = useQueryState('modal', '')
  const navKey = useExternalNavKey()
  const all = useMemo(() => [...added, ...(tpl.data ?? [])].filter(t => !archived.includes(keyOf(t))), [tpl.data, added, archived])
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
        {tpl.data && (all.length
          ? <Templates key={navKey} all={all} existing={tpl.data} setArchived={setArchived} setAdded={setAdded} />
          : <div className="k-card" style={{ padding: 30 }}><EmptyState icon="file" testid="templates-none" title="No saved templates" caption="a chain becomes a template when it is saved in Analyse"
            action={<Button variant="primary" icon="link" onClick={() => navigate('analyse/chain')}>New in Analyse</Button>} /></div>)}
      </Page>
    </>
  )
}

function Templates({ all, existing, setArchived, setAdded }: { all: Template[]; existing: Template[]; setArchived: (f: (x: string[]) => string[]) => void; setAdded: (f: (x: Template[]) => Template[]) => void }) {
  const [kindQ, setKindQ] = useQueryState<'all' | TemplateKind>('kind', 'all')
  const [modelQ, setModelQ] = useQueryState('model', '')
  const [pageQ, setPageQ] = useQueryState('page', '1')
  /* No default template id: the first row of the live list is the selection, which is what `?? items[0]` below
     resolves to. `mp_drops_v3` was a fixture name that addresses nothing here. */
  const [tplQ, setTplQ] = useQueryState('template', '')
  const [modal, setModal] = useQueryState('modal', '')
  const [fromQ] = useQueryState('from', '')
  /* 'last run' is not offered: `lastRun` is not recorded anywhere, so that option sorted nothing and silently
     left the list in the order the bridge happened to return. */
  const [sort, setSort] = useState<'runs' | 'name' | 'version'>('runs')
  const { push } = useToast()
  const filtered = all.filter(t => (kindQ === 'all' || t.kind === kindQ) && (modelQ !== '1' || t.containsModel))
  const ordered = sort === 'name' ? [...filtered].sort((a, b) => a.name.localeCompare(b.name)) : sort === 'version' ? [...filtered].sort((a, b) => b.version - a.version) : [...filtered].sort((a, b) => b.runCount - a.runCount)
  const pageCount = Math.max(1, Math.ceil(ordered.length / PAGE))
  const page = Math.min(pageCount, Math.max(1, Number(pageQ) || 1))
  const items = ordered.slice((page - 1) * PAGE, page * PAGE)
  /* A `?template=` may name the row id (`#12`) or the name — both resolve, so a readable deep link keeps
     working while duplicate names no longer collide. */
  const selected = all.find(t => keyOf(t) === tplQ) ?? all.find(t => t.name === tplQ) ?? items[0] ?? null
  const others = ordered.filter(t => !items.includes(t)).map(t => t.name)
  const nextName = (base: string) => { let n = `${base}_copy`, i = 2; while (all.some(t => t.name === n)) n = `${base}_copy${i++}`; return n }
  const archive = (t: Template) => {
    setArchived(a => [...a, keyOf(t)]); recordDemoWrite('library', 'template.archive', { name: t.name, version: t.version }); setModal(null); setTplQ(null)
    push({ text: `Hidden ${t.name} v${t.version} in this session · runs keep their template version · not wired yet: POST /api/templates/${t.name}/archive`, action: { label: 'Undo', onClick: () => setArchived(a => a.filter(x => x !== keyOf(t))) } })
  }
  const duplicate = (t: Template) => {
    const name = nextName(t.name)
    setAdded(a => [{ ...t, name, version: 1, runs: '0 runs', runCount: 0, lastRun: '', latest: null, latestMuted: 'not yet run', scores: [], versions: [{ v: 1, change: `duplicated from ${t.name} v${t.version}`, date: today() }] }, ...a])
    recordDemoWrite('library', 'template.duplicate', { from: t.name, name }); setTplQ(name); setPageQ(null)
    push({ text: `Duplicated as ${name} v1 in this session only · not wired yet: POST /api/templates` })
  }

  return (
    <div className="lib-split">
      <div className="stack" style={{ gap: 10, minWidth: 0 }}>
        <div className="k-card lib-filterbar" data-testid="template-filters">
          <Seg size="sm" ariaLabel="kind" testid="kind-seg" value={kindQ} onChange={v => { setKindQ(v); setPageQ(null) }} options={[{ value: 'all', label: 'all' }, { value: 'detection', label: 'detection' }, { value: 'seed search', label: 'seed search' }, { value: 'training', label: 'training' }, { value: 'interrogation', label: 'interrogation' }]} />
          <button type="button" className={`k-chip ${modelQ === '1' ? 'blue' : 'outline'} k-chip-btn lg`} aria-pressed={modelQ === '1'} data-testid="model-stage-toggle" onClick={() => { setModelQ(modelQ === '1' ? null : '1'); setPageQ(null) }}><Icon name="cpu" size={13} />contains a Model stage</button>
          <span style={{ marginLeft: 'auto' }} className="lib-muted-label">sort</span>
          <SelectField value={sort} onChange={v => { setSort(v as typeof sort); setPageQ(null) }} width={150} testid="template-sort" ariaLabel="sort" options={['runs', 'name', 'version'].map(o => ({ value: o, label: o }))} />
        </div>
        <div className="stack" style={{ gap: 10 }} data-testid="template-list" role="listbox" aria-label="templates" tabIndex={0}
          onKeyDown={e => { const i = selected ? items.findIndex(t => keyOf(t) === keyOf(selected)) : -1; const d = e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0; if (d && items.length) { e.preventDefault(); setTplQ(items[Math.max(0, Math.min(items.length - 1, i + d))].name) } }}>
          {items.map(t => {
            const on = selected != null && keyOf(t) === keyOf(selected)
            return (
              <div key={keyOf(t)} role="option" aria-selected={on} className={`k-card lib-tcard${on ? ' selected' : ''}`} style={{ cursor: 'pointer', background: on ? '#f3f8ff' : undefined }} data-testid={`template-card-${t.name}`} onClick={() => setTplQ(t.name)}>
                <div className="stack" style={{ gap: 5, minWidth: 0 }}>
                  <div className="row" style={{ gap: 6 }}><span className="nm">{t.name}</span><span className="k-badge t-grey">v{t.version}</span>{t.badges.map(b => <span key={b.label} className={`k-badge t-${b.tone}`}>{b.label}</span>)}</div>
                  <span className="lib-cap">{t.signature}</span>
                  <ChainRibbon variant="thumbs" blocks={t.stages.map((s, i) => ({ id: `${keyOf(t)}-${i}`, label: s.name, glyph: s.glyph }))} ariaLabel={`${t.name} stages`} />
                </div>
                <div className="stack" style={{ gap: 3, paddingTop: 8 }}>
                  {t.latest ? <><span className="mono b" style={{ fontSize: 12 }}>{t.latest.text}</span><span className="lib-cap">{t.latest.scope}</span></>
                    : <span className="mono small muted" title="no score is recorded for any run of any template">{t.latestMuted ?? 'score not recorded'}</span>}
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
      <Modal open={modal === 'export' && !!selected} onClose={() => setModal(null)} title={`Export ${selected?.name} v${selected?.version}`} subtitle="the presentation shape: stages and their locked parameters, not a runnable recipe" size="lg" testid="export-json-modal">
        {selected && <CodeBlock code={JSON.stringify({ name: selected.name, version: selected.version, kind: selected.kind, signature: selected.signature, recipe: selected.recipe, null: selected.nullModel, stages: selected.stages.map(s => ({ block: s.glyph, name: s.name, params: s.params })) }, null, 2)} filename={`${selected.name}.json`} maxHeight={380} testid="export-json-code" />}
      </Modal>
      <ImportJsonModal open={modal === 'import'} onClose={() => setModal(null)} existing={[...existing, ...all]} onImport={t => { setAdded(a => [t, ...a]); setTplQ(t.name); setPageQ(null); setModal(null) }} />
      <Modal open={modal === 'archive' && !!selected} onClose={() => setModal(null)} size="sm" title={`Archive ${selected?.name}?`} testid="archive-modal"
        footer={<><Button onClick={() => setModal(null)}>Cancel</Button><Button variant="danger-solid" testid="archive-confirm" onClick={() => selected && archive(selected)}>Archive</Button></>}>
        <p style={{ margin: 0 }}>Runs keep their template version; it leaves this list. {selected?.runCount ? `${selected.runs} recorded against it stay reproducible.` : ''} Archiving is not wired: the row is hidden for this session only and returns on reload.</p>
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
      <div className="row"><b className="mono" style={{ fontSize: 14 }}>{t.name}</b><span className="k-badge t-grey">v{t.version}</span><span className={`k-badge ${KIND_TONE[t.kind] ?? 't-grey'}`} style={{ marginLeft: 'auto' }}>{t.kind}</span></div>
      <span className="lib-cap" style={{ marginTop: -6 }}>recipe {t.recipe || '— no description recorded'} · null: {t.nullModel}</span>
      <span className="lib-cap" style={{ fontSize: 11 }}>stages · parameters locked</span>
      <div className="stack" style={{ gap: 6 }} data-testid="template-stages">
        {t.stages.length ? t.stages.map((s, i) => (
          <div key={i} className="lib-stage">
            {s.glyph === 'source' ? <SourceGlyph width={36} height={24} /> : <BlockGlyph name={s.glyph} width={36} height={24} />}
            <span className="stack" style={{ gap: 0, minWidth: 0 }}><span style={{ fontSize: 12, fontWeight: 600 }}>{s.name}</span><span className="lib-cap">{s.params}</span></span>
          </div>
        )) : <span className="lib-cap">this template row carries no steps</span>}
      </div>
      <span className="lib-cap" style={{ fontSize: 11 }}>versions</span>
      {t.versions.length ? (
        <div className="stack" style={{ gap: 2 }} data-testid="template-versions">
          {t.versions.map((v, i) => (
            <div key={v.v} className="lib-vrow">
              <span className={`k-badge ${i === 0 ? 't-blue' : 't-grey'}`}>v{v.v}</span><span style={{ color: i === 0 ? 'var(--text)' : 'var(--muted)' }}>{v.change} · {v.date}</span>
              {i > 0 && <Button variant="link" size="sm" className="diff" testid={`diff-v${v.v}`} onClick={() => { setFrom(`v${v.v}`); setModal('diff') }}>diff</Button>}
            </div>
          ))}
        </div>
      ) : (
        <Callout tone="grey" title="Version history is not recorded" testid="template-versions-none" stacked>
          the row carries a version number (<b>v{t.version}</b>) but nothing stores what changed between versions, so there is no history to show and no diff to take. Not "unchanged" — <b>unrecorded</b>.
        </Callout>
      )}
      <span className="lib-cap" style={{ fontSize: 11 }}>scores belong to runs <InfoTip title="scores belong to runs">a template has no score of its own; each run would score it on that run's scope against reviewed spans (§4.8)</InfoTip></span>
      {t.scores.length ? <>
        <table className="lib-scores" data-testid="template-scores">
          <thead><tr><th>{head[0]}</th><th>scope</th><th className="num">prec</th><th className="num">recall</th><th className="num">× null</th></tr></thead>
          <tbody>{t.scores.map(s => (
            <tr key={s.run}>
              <td><button type="button" className="lib-plain mono" style={{ color: 'var(--blue)', fontSize: 11 }} onClick={() => navigate(runRoute(s.run))}>{s.run}</button></td>
              <td title={s.scopeFull}>{s.scope}</td><td className="num">{s.prec?.toFixed(2) ?? '—'}</td><td className="num">{s.recall == null ? '—' : s.recall.toFixed(2)}</td><td className="num">{s.xNull ?? '—'}</td>
            </tr>
          ))}</tbody>
        </table>
        {t.scores.some(s => s.recall == null) && <span className="lib-cap">recall “—”: no reviewed overlap on that scope</span>}
      </> : (
        <Callout tone="grey" title="No scores are recorded" testid="template-scores-none" stacked>
          {t.runCount > 0
            ? <>this template has <b>{t.runs}</b> against it, but no run stores a precision, a recall or an × null anywhere in this installation — so this is <b>not</b> “never run”, it is “never scored”.</>
            : <>no run is recorded against this template, and no run of any template stores a score anywhere in this installation.</>}
        </Callout>
      )}
      <div className="lib-rail-actions">
        <Button variant="primary" icon="target" iconRight="arrow-right" testid="apply-in-discovery" disabled={!!applyReason} disabledReason={applyReason ?? undefined} onClick={() => navigate(`discovery/runs?modal=add-template&template=${encodeURIComponent(t.name)}`)}>Apply in Discovery</Button>
        {t.kind === 'training'
          ? <Button icon="rocket" iconRight="arrow-right" testid="launch-in-models" onClick={() => navigate(`models/launch?template=${encodeURIComponent(t.name)}`)}>Launch in Models</Button>
          : <Button icon="link" iconRight="arrow-right" testid="open-in-analyse" onClick={() => navigate(t.kind === 'interrogation' ? `analyse/interrogation?template=${encodeURIComponent(t.name)}` : `analyse/chain?template=${encodeURIComponent(t.name)}`)}>Open in Analyse</Button>}
        <span className="row" style={{ width: '100%', gap: 14 }}>
          <Button variant="link" icon="copy" testid="duplicate-template" onClick={onDuplicate}>Duplicate</Button>
          <Button variant="link" icon="upload" testid="export-json" onClick={() => setModal('export')}>Export JSON</Button>
          <Button variant="link" icon="inbox" testid="archive-template" style={{ marginLeft: 'auto' }} onClick={() => setModal('archive')}>Archive</Button>
        </span>
      </div>
    </aside>
  )
}

/** Where a scored run lives. A run in this installation is a numeric `runs.id`, so that is what is matched;
 *  the old `j-` / `#` prefix sniffing only ever recognised fixture ids and sent everything else to Discovery. */
export function runRoute(run: string): string {
  const id = String(run ?? '').replace(/^#/, '')
  return /^\d+$/.test(id) ? `analyse/chain?run=${id}` : `jobs?run=${encodeURIComponent(id)}`
}

function DiffModal({ t, open, from, onClose }: { t: Template | null; open: boolean; from: string; onClose: () => void }) {
  if (!t) return null
  /* The next version RECORDED, not `fromV + 1`: nothing guarantees version numbers are consecutive. */
  const sorted = [...t.versions].sort((a, b) => a.v - b.v)
  const fromV = Number(from.replace('v', '')) || (sorted[0]?.v ?? t.version)
  const to = sorted.find(v => v.v > fromV)
  return (
    <Modal open={open} onClose={onClose} size="md" title={`${t.name} · v${fromV} → ${to ? `v${to.v}` : 'nothing later'}`} subtitle={to ? `${to.change} · ${to.date}` : 'no later version is recorded'} testid="diff-modal">
      {to?.diff?.length ? <div className="stack" style={{ gap: 4 }}>
        {to.diff.map((d, i) => (
          <div key={i} className="stack" style={{ gap: 2 }}>
            <span className="lib-cap">{d.param}</span>
            <div className="lib-diff-row del"><span>−</span><span>{d.from}</span></div>
            <div className="lib-diff-row add"><span>+</span><span>{d.to}</span></div>
          </div>
        ))}
      </div> : <EmptyState size="sm" title="No parameter diff recorded" caption={to ? to.change : `v${fromV} is the latest version recorded`} />}
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
      name: o.name, version, kind, signature: typeof o.signature === 'string' ? o.signature : 'Signal → SpanSet', badges: [], containsModel: false, recipe: '', nullModel: '—',
      stages: [{ glyph: 'source', name: 'Source', params: 'one channel · any recording' }, ...(o.stages as { block?: string; name?: string; params?: string }[]).map(s => ({ glyph: s.block ?? 'threshold', name: s.name ?? s.block ?? 'stage', params: s.params ?? '' }))],
      latest: null, latestMuted: 'not yet run', runs: '0 runs', runCount: 0, lastRun: '', versions: [{ v: version, change: 'imported from JSON', date: today() }], scores: [],
    }
    return { t, error: null, note: same.length ? `saves as ${o.name} v${version}` : undefined }
  }, [text, existing])
  return (
    <Modal open={open} onClose={onClose} size="lg" title="Import template JSON" subtitle="parsed and previewed here only — there is no template write route yet" testid="import-json-modal"
      footerNote={parsed.note}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon="download" testid="import-json-confirm" disabled={!parsed.t} disabledReason={parsed.error ?? 'paste a template JSON'}
        onClick={() => { if (!parsed.t) return; onImport(parsed.t); recordDemoWrite('library', 'template.import', { name: parsed.t.name, version: parsed.t.version }); push({ text: `Imported ${parsed.t.name} v${parsed.t.version} into this session only · not wired yet: POST /api/templates/import` }); setText('') }}>Import</Button></>}>
      <div className="stack" style={{ gap: 8 }}>
        <TextField multiline rows={10} value={text} onChange={setText} placeholder={'{ "name": "mp_drops_v4", "kind": "detection", "stages": [{ "block": "matrix_profile", "name": "Matrix profile", "params": "m = 120 s" }] }'} invalid={!!parsed.error} block testid="import-json-text" />
        {parsed.error && <span className="k-field-error" role="alert" data-testid="import-json-error"><Icon name="alert-circle" size={11} />{parsed.error}</span>}
        {parsed.t && <span className="lib-cap" data-testid="import-json-ok"><Icon name="check-circle" size={11} style={{ color: 'var(--green)', verticalAlign: -1 }} /> {parsed.t.name} v{parsed.t.version} · {parsed.t.stages.length - 1} stages · {parsed.t.kind}</span>}
      </div>
    </Modal>
  )
}
