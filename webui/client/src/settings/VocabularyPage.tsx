/* Settings › Vocabulary (frame settings-03 · spec §9.3).
 * One vocabulary across annotations and adjudications: verdicts (the core five), classes, morphology tags. */
import { useEffect, useRef, useState } from 'react'
import {
  Button, Callout, Chip, InfoTip, MiniTrace, Popover, SectionCard, SelectField, Table, TextField, Toggle,
  fmtInt, recordDemoWrite, useDemoState, useNotWired, useQueryState,
} from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import {
  classImpliesKey, classInformativeKey, getVocabulary, tagExample, verdictKeyKey, verdictNameKey,
  type ClassRow, type TagRow, type VerdictRow,
} from '../api/settings'
import { LoadFailed, Loading, LockedChip, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function VocabularyPage() {
  const rd = useSourced(getVocabulary, [])
  return (
    <SettingsShell slug="vocabulary" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the vocabulary" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getVocabulary>>['data']
const KEY_TAKEN: Record<string, string> = { E: '`E` opens in Explore (Keyboard & behaviour)', R: '`R` marks the viewport reviewed (Keyboard & behaviour)', ' ': 'Space skips without writing (Keyboard & behaviour)' }

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('vocabulary')
  const notWired = useNotWired()
  const [rename, setRename] = useQueryState('rename', '')
  const [renameTo] = useQueryState('to', '')
  const [rekey, setRekey] = useQueryState('rekey', '')
  const [adding, setAdding] = useQueryState('add', '')
  const [extraVerdicts, setExtraVerdicts] = useDemoState<VerdictRow[]>('settings.verdicts.extra', () => [])
  const [extraClasses, setExtraClasses] = useDemoState<ClassRow[]>('settings.classes.extra', () => [])
  const [extraTags, setExtraTags] = useDemoState<TagRow[]>('settings.tags.extra', () => [])

  const verdicts = [...data.verdicts, ...extraVerdicts]
  const classes = [...data.classes, ...extraClasses]
  const tags = [...data.tags, ...extraTags]
  const name = (v: VerdictRow) => s.str(verdictNameKey(v.name)) || v.name
  const vkey = (v: VerdictRow) => s.str(verdictKeyKey(v.name)) || v.key

  return (
    <>
      <SectionCard title="Verdicts" subtitle="keys, roles, counts in both stores" testid="verdicts-card"
        actions={<LockedChip reason="Review keys, seed promotion and training exclusions depend on the core five" testid="core-five">core five · rename or rekey, never remove</LockedChip>}>
        <Table rows={verdicts} rowKey={v => v.name} testid="verdicts-table" dense
          rowTone={v => (rename === v.name ? 'amber' : undefined)}
          columns={[
            { key: 'verdict', header: 'verdict', width: '18%', render: v => <span className="mono" style={{ fontWeight: 600 }}>{name(v)}</span> },
            {
              key: 'key', header: 'key', width: '8%', render: v => rekey === v.name
                ? <KeyCapture taken={verdicts.filter(x => x.name !== v.name).map(x => vkey(x)).concat(classes.map(c => c.key))}
                  onDone={k => { if (k) s.set(verdictKeyKey(v.name), k); setRekey('') }} />
                : <span className="s-keycap">{vkey(v)}</span>,
            },
            { key: 'colour', header: 'colour', width: '7%', render: v => <span className="s-swatch" style={{ background: v.colour }} /> },
            { key: 'role', header: 'role', width: '25%', render: v => <span className="small">{v.role}</span> },
            { key: 'ann', header: 'in annotations', width: '13%', align: 'right', render: v => fmtInt(v.n_annotations) },
            { key: 'adj', header: 'in adjudications', width: '13%', align: 'right', render: v => fmtInt(v.n_adjudications) },
            {
              key: 'actions', header: '', width: '16%', render: v => (
                <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <Button variant="link" size="sm" testid={`rename-${v.name}`} onClick={() => setRename(rename === v.name ? '' : v.name)}>rename</Button>
                  <Button variant="link" size="sm" testid={`rekey-${v.name}`} onClick={() => setRekey(rekey === v.name ? '' : v.name)}>rekey</Button>
                  {v.core && <LockedChip reason="the core five have no delete">core</LockedChip>}
                </span>
              ),
            },
          ]} />

        {rename && <RenameVerdict v={verdicts.find(x => x.name === rename)!} initial={renameTo} taken={verdicts.filter(x => x.name !== rename).map(x => name(x)).concat(classes.map(c => c.name))}
          onCancel={() => setRename('')} onSave={to => { s.set(verdictNameKey(rename), to); setRename('') }} />}

        {adding === 'verdict'
          ? <AddVerdict taken={verdicts.map(v => name(v))} onCancel={() => setAdding('')}
            onAdd={v => { setExtraVerdicts(x => [...x, v]); setAdding(''); recordDemoWrite('settings', 'add-verdict', { name: v.name }) }} />
          : <Button variant="link" size="sm" icon="plus" testid="add-verdict" onClick={() => setAdding('verdict')}>Add a verdict · needs a role</Button>}
      </SectionCard>

      <SectionCard title="Classes" subtitle="optional class keys in Review · classes for multi-class models" testid="classes-card"
        actions={<Button icon="plus" testid="add-class" onClick={() => setAdding(adding === 'class' ? '' : 'class')}>Add class</Button>}
        footer={<span className="s-note">an informative class implies interesting; a non-informative class names the verdict it implies · renaming a class rewrites its labels, models keep their own snapshot</span>}>
        <Table rows={classes} rowKey={c => c.key} testid="classes-table" dense
          columns={[
            { key: 'key', header: 'key', width: '7%', render: c => <span className="s-keycap">{c.key}</span> },
            { key: 'class', header: 'class', width: '20%', render: c => <b>{c.name}</b> },
            { key: 'colour', header: 'colour', width: '8%', render: c => <><span className="s-swatch" style={{ background: c.colour }} /> <span className="mono small muted">{c.colour}</span></> },
            {
              key: 'informative', header: 'informative', width: '16%', render: c => (
                <span className={s.dirty(classInformativeKey(c.key)) ? 'unsaved' : undefined} style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                  <Toggle checked={Boolean(s.value(classInformativeKey(c.key)) ?? c.informative)} testid={`informative-${c.key}`}
                    onChange={v => { s.set(classInformativeKey(c.key), v); s.set(classImpliesKey(c.key), v ? 'interesting' : 'artifact') }}
                    label={(s.value(classInformativeKey(c.key)) ?? c.informative) ? 'on' : 'off'} />
                </span>
              ),
            },
            {
              key: 'implies', header: 'implies', width: '17%', render: c => (s.value(classInformativeKey(c.key)) ?? c.informative)
                ? <LockedChip reason="an informative class implies interesting" testid={`implies-${c.key}`}>interesting</LockedChip>
                : <SelectField value={String(s.value(classImpliesKey(c.key)) ?? c.implies)} onChange={v => s.set(classImpliesKey(c.key), v)} size="sm" width={130}
                  options={data.verdicts.map(v => ({ value: v.name, label: v.name }))} testid={`implies-select-${c.key}`} />,
            },
            { key: 'labels', header: 'labels', width: '9%', align: 'right', render: c => fmtInt(c.labels) },
            {
              key: 'models', header: 'used by models', width: '15%', render: c => c.used_by.length
                ? <Button variant="link" size="sm" onClick={() => navigate(`models/registry?model=${c.used_by[0]}`)} testid={`usedby-${c.key}`}>{c.used_by.join(', ')}</Button>
                : <span className="muted">—</span>,
            },
            { key: 'rename', header: '', width: '8%', render: c => <Button variant="link" size="sm" onClick={() => notWired(`POST /api/vocabulary/class/${c.key}/rename`)}>rename</Button> },
          ]} />
        {adding === 'class' && <AddClass used={classes.map(c => c.key)} onCancel={() => setAdding('')}
          onAdd={c => { setExtraClasses(x => [...x, c]); setAdding('') }} />}
      </SectionCard>

      <SectionCard title="Morphology tags" subtitle="many-to-many on library entries, never a primary key" testid="tags-card"
        actions={<Button icon="plus" testid="add-tag" onClick={() => setAdding(adding === 'tag' ? '' : 'tag')}>Add tag</Button>}>
        <Table rows={tags} rowKey={t => t.name} testid="tags-table" dense
          columns={[
            { key: 'tag', header: 'tag', width: '14%', render: t => <span className="mono" style={{ fontWeight: 600 }}>{t.name}</span> },
            { key: 'definition', header: 'definition', width: '34%', render: t => <span className="small">{t.definition}</span> },
            {
              key: 'example', header: 'example', width: '12%', render: t => {
                const v = tagExample(t.shape)
                return <span className="s-spark" title="mV, not normalised"><MiniTrace values={v} yDomain={[Math.min(...v), Math.max(...v)]} width={60} height={24} /></span>
              },
            },
            { key: 'families', header: 'families', width: '9%', align: 'right', render: t => t.families },
            { key: 'members', header: 'members', width: '9%', align: 'right', render: t => fmtInt(t.members) },
            { key: 'aliases', header: 'aliases', width: '14%', render: t => t.aliases.length ? <Chip tone="grey" size="sm">{t.aliases[0]}</Chip> : <span className="muted">—</span> },
            {
              key: 'act', header: '', width: '12%', render: t => (
                <span style={{ display: 'flex', gap: 6 }}>
                  <Button variant="link" size="sm" onClick={() => notWired(`POST /api/vocabulary/tag/${t.name}/rename`)}>rename</Button>
                  <MergeTag tag={t} others={tags.filter(x => x.name !== t.name).map(x => x.name)} />
                </span>
              ),
            },
          ]} />
        {adding === 'tag' && <AddTag taken={tags.map(t => t.name)} onCancel={() => setAdding('')} onAdd={t => { setExtraTags(x => [...x, t]); setAdding('') }} />}
      </SectionCard>
    </>
  )
}

/* ------------------------------------------------------------------ inline editors */

function RenameVerdict({ v, initial, taken, onCancel, onSave }: { v: VerdictRow; initial: string; taken: string[]; onCancel: () => void; onSave: (to: string) => void }) {
  const [to, setTo] = useState(initial || v.name)
  useEffect(() => { setTo(initial || v.name) }, [initial, v.name])
  const rows = v.n_annotations + v.n_adjudications
  const err = !/^[a-z_]{2,24}$/.test(to) ? 'lowercase letters and underscores, 2–24' : to !== v.name && taken.includes(to) ? `\`${to}\` is already in the vocabulary` : null
  return (
    <div className="s-inline-edit" data-testid="rename-row">
      <span className="s-label mono">rename {v.name} →</span>
      <TextField value={to} onChange={t => setTo(t.toLowerCase())} width={200} invalid={!!err} autoFocus testid="rename-input" onEnter={() => !err && onSave(to)} />
      <span className="s-note" style={{ color: 'var(--amber)' }}>rewrites {fmtInt(rows)} rows across both stores atomically · existing exports keep the old name</span>
      <span className="k-spacer" />
      <Button size="sm" onClick={onCancel}>Cancel</Button>
      <Button size="sm" variant="primary" disabled={!!err} disabledReason={err ?? undefined} testid="rename-save" onClick={() => onSave(to)}>Stage rename</Button>
    </div>
  )
}

function KeyCapture({ taken, onDone }: { taken: string[]; onDone: (k: string | null) => void }) {
  const [err, setErr] = useState<string | null>(null)
  return (
    <span className={`s-keycap capture${err ? ' conflict' : ''}`} tabIndex={0} autoFocus data-testid="key-capture" title={err ?? 'press a key…'}
      onBlur={() => onDone(null)}
      onKeyDown={e => {
        if (e.key === 'Escape') return onDone(null)
        if (e.key.length !== 1) return
        const k = e.key.toUpperCase()
        if (KEY_TAKEN[k]) return setErr(KEY_TAKEN[k])
        if (taken.includes(k)) return setErr(`\`${k}\` is already a verdict or class key`)
        onDone(k)
      }}>{err ? err.slice(0, 3) : 'press a key…'}</span>
  )
}

function AddVerdict({ taken, onCancel, onAdd }: { taken: string[]; onCancel: () => void; onAdd: (v: VerdictRow) => void }) {
  const [name, setName] = useState('')
  const [key, setKey] = useState('')
  const [role, setRole] = useState('')
  const err = !/^[a-z_]{2,24}$/.test(name) ? 'lowercase letters and underscores, 2–24' : taken.includes(name) ? `\`${name}\` is already a verdict` : !key ? 'give it a key' : !role ? 'A new verdict needs a role' : null
  return (
    <div className="s-inline-edit" data-testid="add-verdict-row">
      <TextField value={name} onChange={v => setName(v.toLowerCase())} placeholder="name" width={170} invalid={!!name && !!err} testid="new-verdict-name" />
      <TextField value={key} onChange={v => setKey(v.slice(0, 1).toUpperCase())} placeholder="key" width={70} testid="new-verdict-key" />
      <SelectField value={role} onChange={setRole} width={150} testid="new-verdict-role"
        options={[{ value: '', label: 'role…' }, ...['accept', 'reject', 'flag', 'defer'].map(r => ({ value: r, label: r }))]} />
      <span className="k-spacer" />
      <Button size="sm" onClick={onCancel}>Cancel</Button>
      <Button size="sm" variant="primary" disabled={!!err} disabledReason={err ?? undefined} testid="new-verdict-add"
        onClick={() => onAdd({ name, key, colour: '#30B0C7', role, n_annotations: 0, n_adjudications: 0, core: false })}>Add verdict</Button>
    </div>
  )
}

function AddClass({ used, onCancel, onAdd }: { used: string[]; onCancel: () => void; onAdd: (c: ClassRow) => void }) {
  const free = ['5', '6', '7', '8'].filter(k => !used.includes(k))
  const [key, setKey] = useState(free[0] ?? '')
  const [name, setName] = useState('')
  const err = !key ? 'no free class key (5–8)' : !name ? 'name the class' : null
  return (
    <div className="s-inline-edit" data-testid="add-class-row">
      <SelectField value={key} onChange={setKey} width={80} options={free.map(k => ({ value: k, label: k }))} testid="new-class-key" />
      <TextField value={name} onChange={setName} placeholder="class name" width={200} testid="new-class-name" />
      <span className="s-note">labels 0 · informative by default</span>
      <span className="k-spacer" />
      <Button size="sm" onClick={onCancel}>Cancel</Button>
      <Button size="sm" variant="primary" disabled={!!err} disabledReason={err ?? undefined} testid="new-class-add"
        onClick={() => onAdd({ key, name, colour: '#30B0C7', informative: true, implies: 'interesting', labels: 0, used_by: [] })}>Add class</Button>
    </div>
  )
}

function AddTag({ taken, onCancel, onAdd }: { taken: string[]; onCancel: () => void; onAdd: (t: TagRow) => void }) {
  const [name, setName] = useState('')
  const [def, setDef] = useState('')
  const err = !name ? 'name the tag' : taken.includes(name) ? 'that tag exists' : !def ? 'a definition is required' : def.length > 140 ? 'at most 140 characters' : null
  return (
    <div className="s-inline-edit" data-testid="add-tag-row">
      <TextField value={name} onChange={v => setName(v.toLowerCase())} placeholder="tag" width={150} testid="new-tag-name" />
      <TextField value={def} onChange={setDef} placeholder="what the shape is, in one line" width={380} testid="new-tag-def" />
      <span className="s-note">no example yet</span>
      <span className="k-spacer" />
      <Button size="sm" onClick={onCancel}>Cancel</Button>
      <Button size="sm" variant="primary" disabled={!!err} disabledReason={err ?? undefined} testid="new-tag-add"
        onClick={() => onAdd({ name, definition: def, families: 0, members: 0, aliases: [], shape: 'plateau' })}>Add tag</Button>
    </div>
  )
}

function MergeTag({ tag, others }: { tag: TagRow; others: string[] }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [into, setInto] = useState(others[0] ?? '')
  const notWired = useNotWired()
  return (
    <>
      <Button ref={ref} variant="link" size="sm" testid={`merge-${tag.name}`} onClick={() => setOpen(o => !o)}>merge</Button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} title={`Merge ${tag.name}`} width={300} testid="merge-popover">
        <SelectField value={into} onChange={setInto} options={others.map(o => ({ value: o, label: o }))} width="100%" testid="merge-into" />
        <Callout tone="amber" icon={null} style={{ marginTop: 8 }}>{fmtInt(tag.members)} members move · alias {tag.name} kept</Callout>
        <Button size="sm" variant="primary" block style={{ marginTop: 8 }} testid="merge-confirm"
          onClick={() => { notWired(`POST /api/vocabulary/tag/merge (${tag.name} → ${into})`); setOpen(false) }}>Merge</Button>
      </Popover>
    </>
  )
}
