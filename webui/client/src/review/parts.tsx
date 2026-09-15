/* Review page parts shared by the inspector (frames 1, 1b, 3–6) and the cluster page (frames 2, 7). */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { navigate } from '../state'
import {
  Button, Callout, Chip, Icon, IconButton, InfoTip, Kbd, Legend, MiniTrace, Pager, Popover, Seg, TextField, Trace, cx, fmtInt, useQueryState, type IconName,
} from '../kit'
import { useSourced } from '../api/seam'
import { CONTEXT_PAD_MAX, VOCABULARY, getOtherChannels, type ArtifactFactors, type ItemDetail, type NearestFamily, type Verdict } from '../api/review'
import { THUMB_Y } from './Shell'
import { VERDICT_LABEL, type Draft, type VerdictRecord } from './store'

export const Y_MV: [number, number] = [-0.44, 0.44]

export function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const id = window.setInterval(() => setNow(Date.now()), ms); return () => window.clearInterval(id) }, [ms])
  return now
}

/* ---------------- title row ---------------- */
export function Pill({ dot, icon, label, value, tone, title, testid }: { dot?: string; icon?: IconName; label: ReactNode; value: ReactNode; tone?: 'green' | 'amber' | 'blue' | 'purple'; title?: string; testid?: string }) {
  return (
    <span className={cx('rv-pill', tone)} title={title} data-testid={testid}>
      {dot && <i className="dot" style={{ background: dot }} />}{icon && <Icon name={icon} size={13} />}
      <span className="lbl">{label}</span><b>{value}</b>
    </span>
  )
}

export function statusText(rec: VerdictRecord | null) {
  if (!rec) return 'unadjudicated'
  if (rec.verdict === 'seed') return rec.exemplarId ? 'seed · promoted' : 'seed'
  return `${VERDICT_LABEL[rec.verdict]}${rec.className ? ` · ${rec.className}` : ''}`
}
export const statusDot = (rec: VerdictRecord | null) => !rec ? 'var(--muted-2)' : rec.verdict === 'seed' || rec.verdict === 'interesting' ? 'var(--green)' : rec.verdict === 'artifact' ? 'var(--red)' : rec.verdict === 'unsure' ? 'var(--amber)' : 'var(--muted)'

export function ArtifactPill({ a, short, testid = 'pill-artifact' }: { a: ArtifactFactors | { level: string }; short?: boolean; testid?: string }) {
  const tone = a.level === 'low' ? 'green' : a.level === 'medium' ? 'amber' : undefined
  return <Pill dot={a.level === 'low' ? 'var(--green)' : a.level === 'medium' ? 'var(--amber)' : 'var(--red)'} label={short ? 'artifact' : <>artifact<span className="long"> likelihood</span></>} value={a.level} tone={tone} title="artifact likelihood is never hidden" testid={testid} />
}

/* ---------------- time ticks (hours since recording start, frame decimals) ---------------- */
export function TimeTicks({ t0, t1, n = 5, testid }: { t0: number; t1: number; n?: number; testid?: string }) {
  const span = t1 - t0
  const digits = span <= 450 ? 3 : 2
  return (
    <div className="rv-ticks mono" data-testid={testid}>
      <span style={{ left: 0, width: 38, textAlign: 'right' }}>mV</span>
      {Array.from({ length: n }, (_, i) => {
        const f = i / (n - 1)
        return <span key={i} style={{ left: `calc(44px + (100% - 54px) * ${f})`, transform: i === 0 ? 'none' : i === n - 1 ? 'translateX(-100%)' : 'translateX(-50%)' }}>{((t0 + span * f) / 3600).toFixed(digits)} h</span>
      })}
    </div>
  )
}

/* ---------------- context card (frames 1, 1b, 2, 5) ---------------- */
export function sliceContext(d: ItemDetail, pad: number) {
  const off = CONTEXT_PAD_MAX - pad
  const values = d.context.values.slice(off, d.context.values.length - off)
  const t0 = d.context.t0_s + off
  return { values, t0, t1: t0 + values.length - 1, bandStart: d.entry.startH * 3600, bandEnd: d.entry.startH * 3600 + d.entry.durationS }
}

export function ContextCard({ d, title, pad, setPad, bandLabel, canEdit, testid = 'context-card' }: { d: ItemDetail; title: string; pad: '30' | '120' | '300'; setPad: (p: '30' | '120' | '300') => void; bandLabel: string; canEdit: boolean; testid?: string }) {
  const ctx = sliceContext(d, +pad)
  const [pop, setPop] = useQueryPop()
  const ocRef = useRef<HTMLButtonElement>(null)
  const open = pop === 'other-channels'
  return (
    <section className="rv-card" data-testid={testid}>
      <div className="rv-card-head">
        <h3>{title}</h3><span className="mono muted sm">padding</span>
        <Seg size="sm" value={pad} onChange={setPad} options={[{ value: '30', label: '±30 s' }, { value: '120', label: '±120 s' }, { value: '300', label: '±300 s' }]} testid="padding-seg" />
        <span className="grow" />
        <Button ref={ocRef} variant={open ? 'primary' : 'default'} icon="list" aria-expanded={open} onClick={() => setPop(open ? null : 'other-channels')} testid="other-channels-button">Other channels</Button>
        {canEdit && <Button icon="pencil" onClick={() => editInExplore(d)} testid="edit-span-button">Edit span in Explore</Button>}
      </div>
      <div className="rv-plot">
        <Trace values={ctx.values} t0={ctx.t0} timeUnit="none" yDomain={Y_MV} height={170} crosshair unitLabel={false}
          bands={[{ start_s: ctx.bandStart, end_s: ctx.bandEnd, kind: 'detected', label: bandLabel }]} testid="context-trace" />
        <TimeTicks t0={ctx.t0} t1={ctx.t1} testid="context-ticks" />
      </div>
      <OtherChannelsPopover d={d} pad={+pad} open={open} onClose={() => setPop(null)} anchorRef={ocRef} />
    </section>
  )
}

export function editInExplore(d: ItemDetail) {
  navigate(`explore/span-edit/${d.entry.detectionId ?? d.entry.id}?from=review&queue=${d.entry.queueId}&item=${d.entry.id}`)
}

function useQueryPop() { return useQueryState<string>('pop', '') }

/* ---------------- other channels (frame 1b) ---------------- */
const OC_PAGE = 6
function OtherChannelsPopover({ d, pad, open, onClose, anchorRef }: { d: ItemDetail; pad: number; open: boolean; onClose: () => void; anchorRef: React.RefObject<HTMLButtonElement | null> }) {
  const rows = useSourced(() => open ? getOtherChannels(d.entry.queueId, d.entry.id) : Promise.resolve({ data: [], source: 'demo' as const }), [open, d.entry.id])
  const all = rows.data ?? []
  const curIdx = Math.max(0, all.findIndex(r => r.current))
  const [page, setPage] = useState(1)
  useEffect(() => { setPage(Math.floor(curIdx / OC_PAGE) + 1) }, [curIdx, d.entry.id])
  const ctx = sliceContext(d, pad)
  const off = CONTEXT_PAD_MAX - pad
  const i0 = CONTEXT_PAD_MAX - off, i1 = i0 + d.entry.durationS
  const shown = all.slice((page - 1) * OC_PAGE, page * OC_PAGE)
  const a = d.artifact
  return (
    <Popover open={open} onClose={onClose} anchorRef={anchorRef} placement="bottom-end" width={590} className="rv-pop" testid="other-channels-popover"
      title={<><span>Other channels</span><span className="sub">same {(ctx.t0 / 3600).toFixed(3)} → {(ctx.t1 / 3600).toFixed(3)} h</span><span className="grow" /><IconButton icon="x" label="close other channels" onClick={onClose} testid="other-channels-close" /></>}>
      {rows.error && <div className="error-card">Other channels failed to load: {rows.error.message}</div>}
      {!rows.data && !rows.error && <div className="skeleton" style={{ height: 230 }} />}
      {rows.data && (
        <div className="rv-oc" data-testid="other-channels-rows">
          {shown.map(r => (
            <div key={r.channel} className={cx('rv-oc-row', r.current && 'current')} data-testid={`oc-row-${r.channel}`}>
              <span className="mono ch">{r.channel}</span>
              <MiniTrace values={r.values.slice(off, r.values.length - off)} yDomain={THUMB_Y} width="100%" height={30} ground="none" zeroLine={false} band={[i0, i1]} stroke={r.current ? 'var(--text)' : 'var(--muted)'} strokeWidth={r.current ? 1.3 : 0.9} />
              <span className="mono r">{r.current ? 'this channel' : `r ${r.r!.toFixed(2)}`}</span>
            </div>
          ))}
          <div className="row between" style={{ marginTop: 4 }}>
            <span className="mono muted sm">shared mV scale · r = coherence in the span</span>
            <Pager page={page} pageCount={Math.ceil(all.length / OC_PAGE)} onPage={setPage} format="range" total={all.length} pageSize={OC_PAGE} testid="other-channels-pager" />
          </div>
        </div>
      )}
      <div className="rv-oc-foot" data-testid="other-channels-artifact">
        <div className="row"><span className="mono muted">artifact likelihood</span>
          <Chip size="sm" tone={a.level === 'low' ? 'green' : a.level === 'medium' ? 'amber' : 'red'}>{a.level} · {a.p.toFixed(2)}</Chip>
          <InfoTip title="Artifact likelihood">Combines cross-channel coherence, clipping, step changes and electrode flags. Artifacts are noted and kept out of training data. Never blinded.</InfoTip>
          <span className="grow" /><span className="mono muted sm">not blinded in any queue</span></div>
        <div className="mono sm rv-factors"><span className="muted">coherence in span</span> <b>{a.coherence.toFixed(2)}</b> (flag ≥ 0.5) <span className="muted">clipping</span> <b>{a.clipping}</b> <span className="muted">step change</span> <b>{a.stepChange}</b> <span className="muted">electrode flag</span> <b>{a.electrodeFlag}</b></div>
        <Button variant="link" iconRight="arrow-right" onClick={() => navigate(`explore/cross-channel/4?h=${(ctx.t0 / 3600).toFixed(3)}-${(ctx.t1 / 3600).toFixed(3)}`)} testid="open-all-channels">Open all channels in Explore</Button>
      </div>
    </Popover>
  )
}

/* ---------------- shape and nearest families ---------------- */
export function ShapeCard({ d, family, blind }: { d: ItemDetail; family: NearestFamily | null; blind: boolean }) {
  const showMedoid = !blind && family
  return (
    <section className="rv-card" data-testid="shape-card">
      <div className="rv-card-head">
        <h3>{showMedoid ? `Shape vs ${family.id} medoid · mV` : 'Shape · mV'}</h3>
        {showMedoid && <InfoTip title="Shape">Drawn in mV, never normalised (D5). The medoid is stretched to the candidate's duration to overlay it.</InfoTip>}
        <span className="grow" />
        <Legend items={showMedoid ? [{ label: d.entry.unit === 'window' ? 'this window' : 'candidate', colour: 'var(--blue)', shape: 'line' }, { label: `${family.id} medoid`, colour: family.colour, shape: 'line' }]
          : [{ label: d.entry.unit === 'window' ? 'this window' : 'candidate', colour: 'var(--text)', shape: 'line' }]} />
      </div>
      <div className="rv-plot">
        <Trace values={d.shape} timeUnit="s" yDomain={Y_MV} height={122} stroke={showMedoid ? 'var(--blue)' : 'var(--text)'} strokeWidth={2}
          overlays={showMedoid ? [{ values: d.medoids[family.id], stroke: family.colour, width: 2 }] : []} zeroLine={false} testid="shape-trace" />
      </div>
    </section>
  )
}

function DistanceBar({ d, colour }: { d: number; colour: string }) {
  return <span className="rv-dbar" aria-label={`distance ${d.toFixed(2)}`}><i className="fill" style={{ width: `${d * 100}%`, background: colour }} /><i className="knob" style={{ left: `${d * 100}%`, background: colour }} /></span>
}

export function NearestFamiliesCard({ d, overlay, setOverlay }: { d: ItemDetail; overlay: string; setOverlay: (id: string) => void }) {
  const first = d.nearest[0]
  return (
    <section className="rv-card" data-testid="nearest-families">
      <div className="rv-card-head">
        <h3>Nearest families</h3>
        <InfoTip title="Nearest families">Distance is shape only, 0 → 1; a longer bar is farther. Low distance is not a verdict. Click a family to overlay its medoid.</InfoTip>
        <span className="grow" /><span className="mono muted sm">shape distance, 0 → 1</span>
      </div>
      <div className="rv-fams">
        {d.nearest.map(f => (
          <button key={f.id} type="button" className={cx('rv-fam', overlay === f.id && 'on')} onClick={() => setOverlay(f.id)} aria-pressed={overlay === f.id} data-testid={`family-row-${f.id}`}>
            <MiniTrace values={d.medoids[f.id]} yDomain={THUMB_Y} width={58} height={30} stroke={f.colour} strokeWidth={1.5} ground="white" zeroLine={false} />
            <span className="id"><b className="mono">{f.id}</b><span className="mono muted">{f.name}</span></span>
            <span className="mono muted mem">{f.members != null ? `${fmtInt(f.members)} members` : 'members n/a'}</span>
            <DistanceBar d={f.d} colour={f.colour} />
            <b className="mono dv">d {f.d.toFixed(2)}</b>
          </button>
        ))}
      </div>
      <Button variant="link" iconRight="arrow-right" onClick={() => navigate(`library/family/${first.id}`)} testid="open-family-library">Open {first.id} in Library</Button>
    </section>
  )
}

/* ---------------- verdict row ---------------- */
export interface VerdictDef { v: Verdict | 'skip'; key: string; label: string; caption?: string }
export const VERDICT_DEFS: VerdictDef[] = [
  { v: 'seed', key: 'S', label: 'seed', caption: 'promotes to Library' },
  { v: 'interesting', key: 'I', label: 'interesting' },
  { v: 'not_interesting', key: 'N', label: 'not interesting' },
  { v: 'artifact', key: 'A', label: 'artifact', caption: 'kept out of training' },
  { v: 'unsure', key: 'U', label: 'unsure' },
  { v: 'skip', key: 'Space', label: 'skip', caption: 'no write' },
]

export interface PreviousLine { text: string; go?: () => void; prefix?: string }

export function VerdictCard({ selected, flash, binary, onVerdict, onSkip, previous, undo, undoCaption = 'undo', children, testid = 'verdict-card' }: {
  selected: Verdict | null; flash: Verdict | null; binary: boolean; onVerdict: (v: Verdict) => void; onSkip: () => void
  previous: PreviousLine[]; undo: { can: boolean; run: () => void }; undoCaption?: string; children?: ReactNode; testid?: string
}) {
  const [pi, setPi] = useState(0)
  useEffect(() => { setPi(0) }, [previous.length, previous[0]?.text])
  const p = previous[Math.min(pi, previous.length - 1)]
  const defs = VERDICT_DEFS.filter(x => !binary || ['interesting', 'not_interesting', 'skip'].includes(x.v))
  return (
    <section className="rv-card" data-testid={testid}>
      <div className="rv-card-head">
        <h3>Verdict</h3>
        <IconButton icon="chevron-left" label="earlier verdict" bordered disabled={pi >= previous.length - 1} disabledReason="no earlier verdict this session" onClick={() => setPi(i => i + 1)} testid="previous-older" />
        <IconButton icon="chevron-right" label="later verdict" bordered disabled={pi === 0} disabledReason="this is the latest verdict" onClick={() => setPi(i => Math.max(0, i - 1))} testid="previous-newer" />
        {p ? <button type="button" className="rv-prev mono" onClick={p.go} disabled={!p.go} title={p.go ? 'open this item' : undefined} data-testid="previous-line"><span className="muted">{p.prefix ?? 'previous'}</span> {p.text}</button>
          : <span className="mono muted sm" data-testid="previous-line">no verdict yet in this queue</span>}
        <span className="grow" />
        <button type="button" className="rv-undo" disabled={!undo.can} onClick={undo.run} title={undo.can ? 'undo the last write (Ctrl Z)' : 'nothing to undo'} data-testid="undo-button"><Kbd size="sm">Ctrl Z</Kbd><span className="mono muted">{undoCaption}</span></button>
      </div>
      <div className="rv-vcards" style={{ gridTemplateColumns: `repeat(${defs.length}, minmax(0, 1fr))` }}>
        {defs.map(x => {
          const on = x.v !== 'skip' && (selected === x.v || flash === x.v)
          return (
            <button key={x.v} type="button" className={cx('rv-vcard', on && 'on', x.v === 'seed' && 'seed')} aria-pressed={on} data-testid={`verdict-${x.v}`}
              onClick={e => { (e.currentTarget as HTMLButtonElement).blur(); if (x.v === 'skip') onSkip(); else onVerdict(x.v) }}>
              <Kbd size="sm">{x.key}</Kbd>
              <span className="txt"><span className="lbl">{x.label}</span>{x.caption && <span className={cx('cap mono', x.v === 'seed' && 'green')}>{x.caption}</span>}</span>
            </button>
          )
        })}
      </div>
      {binary && <div className="mono muted sm" style={{ marginTop: 8 }}>this queue takes binary verdicts and classes (Settings › Review queues)</div>}
      {children}
    </section>
  )
}

/* ---------------- annotate ---------------- */
const TAG_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/
export function AnnotateCard({ draft, setDraft, className, onClass }: { draft: Draft; setDraft: (d: Draft) => void; className?: string; onClass: (key: string) => void }) {
  const [adding, setAdding] = useState(false)
  const [tag, setTag] = useState('')
  const suggestions = [...new Set([...VOCABULARY.tagSuggestions, ...draft.tags])]
  const tagErr = !tag ? null : tag.length > 32 ? 'at most 32 characters' : !TAG_RE.test(tag) ? 'tags are lowercase words joined by -' : draft.tags.includes(tag) || suggestions.includes(tag) && draft.tags.includes(tag) ? 'already tagged' : null
  const addTag = () => { if (!tag || tagErr) return; setDraft({ ...draft, tags: [...draft.tags, tag] }); setTag(''); setAdding(false) }
  return (
    <section className="rv-card" data-testid="annotate-card">
      <div className="rv-card-head">
        <h3>Annotate</h3><span className="mono muted sm">optional</span><span className="grow" />
        <InfoTip title="Classes">A class implies interesting, unless the class is non-informative (electrode artifact implies artifact). Classes are bound to number keys in Settings › Vocabulary.</InfoTip>
        <span className="mono muted sm">a class implies interesting, unless the class is non-informative</span>
      </div>
      <div className="rv-ann-row"><span className="mono muted lbl">class</span>
        {VOCABULARY.classes.map(c => (
          <button key={c.key} type="button" className={cx('rv-class', className === c.name && 'on', !c.informative && 'noninf')} aria-pressed={className === c.name} data-testid={`class-${c.key}`}
            onClick={e => { (e.currentTarget as HTMLButtonElement).blur(); onClass(c.key) }}><Kbd size="sm">{c.key}</Kbd>{c.name}</button>
        ))}
      </div>
      <div className="rv-ann-row"><span className="mono muted lbl">tags</span>
        {suggestions.map(t => {
          const on = draft.tags.includes(t)
          return <button key={t} type="button" className={cx('rv-tag', on && 'on')} aria-pressed={on} onClick={() => setDraft({ ...draft, tags: on ? draft.tags.filter(x => x !== t) : [...draft.tags, t] })} data-testid={`tag-${t}`}>{t}</button>
        })}
        {adding
          ? <span className="rv-tag-input">
              <TextField value={tag} onChange={setTag} placeholder="new-tag" width={130} size="sm" invalid={!!tagErr} autoFocus onEnter={addTag} testid="tag-input" ariaLabel="new tag" />
              <Button size="sm" onClick={addTag} disabled={!tag || !!tagErr} disabledReason={tagErr ?? 'type a tag first'} testid="tag-add">Add</Button>
              <IconButton icon="x" label="cancel tag" onClick={() => { setAdding(false); setTag('') }} />
              {tagErr && <span className="mono sm rv-red" data-testid="tag-error">{tagErr}</span>}
            </span>
          : <button type="button" className="rv-tag add" onClick={() => setAdding(true)} data-testid="tag-add-open">+ tag</button>}
        <span className="k-divider-v" />
        <span className="mono muted lbl">note</span>
        <span className="rv-note">
          <TextField value={draft.note} onChange={v => setDraft({ ...draft, note: v.slice(0, 500) })} placeholder="Add a note…" block size="sm" testid="note-input" ariaLabel="note" />
          {draft.note.length > 400 && <span className={cx('mono sm', draft.note.length >= 500 ? 'rv-red' : 'muted')}>{draft.note.length} / 500</span>}
        </span>
      </div>
    </section>
  )
}

/* ---------------- promotion panel (frame 6) ---------------- */
export function PromotionPanel({ d, rec, onUndo, onConfirm, confirmRef }: { d: ItemDetail; rec: VerdictRecord; onUndo: () => void; onConfirm: (family: string | null, familyName?: string) => void; confirmRef: { current: (() => void) | null } }) {
  const nearest = d.nearest[0]
  const near = nearest.d <= 0.30
  const [choice, setChoice] = useState<'nearest' | 'new' | 'none'>(near ? 'nearest' : 'none')
  const [name, setName] = useState('')
  const nameErr = choice !== 'new' ? null : !name.trim() ? 'name the new family' : name.trim().length < 2 || name.trim().length > 40 ? 'a family name is 2–40 characters' : null
  const confirm = () => { if (nameErr) return; onConfirm(choice === 'nearest' ? nearest.id : choice === 'new' ? 'new' : null, choice === 'new' ? name.trim() : undefined) }
  confirmRef.current = confirm   // Enter (review/keys.ts) confirms with the current family choice
  const opt = (v: typeof choice, label: ReactNode, testid: string) => (
    <button type="button" role="radio" aria-checked={choice === v} className={cx('rv-radio', choice === v && 'on')} onClick={() => setChoice(v)} data-testid={testid}><i />{label}</button>
  )
  return (
    <section className="rv-card rv-promo" data-testid="promotion-panel">
      <div className="rv-card-head">
        <Icon name="library" size={15} /><h3>Promoted to Library</h3><Chip size="sm" tone="green">exemplar {rec.exemplarId}</Chip>
        <span className="grow" /><span className="mono muted sm">seed verdict · {relTimeShort(rec.at)}</span>
      </div>
      <div className="rv-promo-body">
        <div className="row wrap" role="radiogroup" aria-label="family"><span className="mono muted sm">family</span>
          {opt('nearest', <>{nearest.id} {nearest.name} · nearest, d {nearest.d.toFixed(2)}{near ? '' : ' · above 0.30'}</>, 'promo-family-nearest')}
          {opt('new', 'new family', 'promo-family-new')}
          {opt('none', 'no family yet', 'promo-family-none')}
        </div>
        {choice === 'new' && <div className="row"><TextField value={name} onChange={setName} placeholder="F-12 · name" width={220} size="sm" invalid={!!nameErr} testid="promo-family-name" ariaLabel="family name" autoFocus />{nameErr && <span className="mono sm rv-red">{nameErr}</span>}</div>}
        <div className="mono sm muted row"><Icon name="link" size={13} /> keeps span, recording, channel, content hash and the run's recipe hash</div>
        <Callout tone="amber" icon="pause">auto-advance paused until you confirm · Enter confirms and moves on</Callout>
        <div className="row">
          <Button icon="undo" onClick={onUndo} testid="promo-undo">Undo promotion</Button><Kbd size="sm">Ctrl Z</Kbd>
          <span className="grow" />
          <Button variant="link" onClick={() => navigate(choice === 'nearest' ? `library/family/${nearest.id}?exemplar=${rec.exemplarId}` : 'library/atlas')} testid="promo-open-library">Open in Library</Button>
          <Button variant="primary" icon="check" onClick={confirm} disabled={!!nameErr} disabledReason={nameErr ?? undefined} testid="promo-confirm">Confirm and next</Button>
        </div>
      </div>
    </section>
  )
}
function relTimeShort(at: number) { const s = Math.round((Date.now() - at) / 1000); return s < 5 ? 'just now' : s < 60 ? `${s} s ago` : `${Math.round(s / 60)} min ago` }

/* ---------------- evidence rail (frame 4) ---------------- */
function EvSection({ id, icon, title, aside, children, masked }: { id: string; icon: IconName; title: string; aside?: ReactNode; children: ReactNode; masked?: boolean }) {
  return (
    <div className="rv-ev" id={`ev-${id}`} data-testid={`evidence-${id}`}>
      <div className="rv-ev-head"><Icon name={masked ? 'eye-off' : icon} size={14} /><h5>{title}</h5><span className="grow" />{masked ? <span className="mono sm rv-purple">hidden until verdict</span> : aside}</div>
      {!masked && children}
    </div>
  )
}
const KV = ({ k, children }: { k: ReactNode; children: ReactNode }) => <div className="rv-kv"><span className="k mono">{k}</span><span className="v mono">{children}</span></div>

export function EvidenceRail({ d, blind, judged, historyVerdicts }: { d: ItemDetail; blind: boolean; judged: boolean; historyVerdicts: string }) {
  const ev = d.evidence, a = d.artifact, f = d.nearest[0]
  const mask = blind && !judged
  return (
    <div data-testid="evidence-sections">
      <EvSection id="origin" icon="branch" title="Origin">
        {ev.origin.runId && <KV k="run"><Chip size="sm" tone="blue">{ev.origin.runKind}</Chip> <b>{ev.origin.runId}</b></KV>}
        {!ev.origin.runId && <KV k="source"><b>{ev.origin.runKind}</b></KV>}
        {ev.origin.windowSet && <KV k="window set">{ev.origin.windowSet}</KV>}
        {ev.origin.block && <KV k="block">{ev.origin.block}</KV>}
        {ev.origin.sample && <KV k="sample">stratified · {ev.origin.sample}</KV>}
        {ev.origin.template && !mask && <KV k={d.entry.unit === 'window' ? 'candidate' : 'template'}>{d.queue.model ?? ev.origin.template}</KV>}
        {ev.origin.template && mask && d.entry.unit === 'window' && <KV k="candidate"><span className="rv-purple">hidden until verdict</span></KV>}
        {ev.origin.stages.length > 0 && <div className="rv-stages">{ev.origin.stages.map((s, i) => <span key={s.label} className="row" style={{ gap: 4 }}>{i > 0 && <Icon name="chevron-right" size={11} />}<span className="rv-stage mono" title={s.full}>{s.label}</span></span>)}</div>}
        {ev.origin.recipeHash && <KV k="recipe hash">{ev.origin.recipeHash}</KV>}
        <KV k="ran">{ev.origin.ran} · {ev.origin.by}</KV>
        <KV k="scope">{ev.origin.scope}</KV>
        {ev.origin.runId && <Button variant="link" iconRight="arrow-right" onClick={() => navigate(`discovery/runs?run=${ev.origin.runId}`)} testid="open-run-discovery">Open run in Discovery</Button>}
      </EvSection>
      {ev.detection && (
        <EvSection id="detection" icon="target" title="Detection" masked={mask}>
          <KV k="score"><b>{ev.detection.score != null ? ev.detection.score.toFixed(2) : 'n/a · seed search ranks by distance'}</b></KV>
          <KV k="threshold">{ev.detection.threshold != null ? `${ev.detection.threshold.toFixed(2)} · recommended ${ev.detection.recommended?.toFixed(2)}` : 'n/a'}</KV>
          <KV k="rank">{ev.detection.rank ?? 'n/a'}</KV>
          <KV k="null expects">{ev.detection.nullExpects ?? 'no null run for this search'}</KV>
          <KV k="samples">{ev.detection.samples} · {ev.detection.fs}</KV>
        </EvSection>
      )}
      {d.entry.modelCall && (
        <EvSection id="model" icon="flask" title="Model call" masked={mask}>
          <KV k="model">{d.queue.model}</KV>
          <KV k="call"><b>{d.entry.modelCall.className} · p {d.entry.modelCall.p.toFixed(2)}</b></KV>
        </EvSection>
      )}
      <EvSection id="also" icon="layers" title="Also found by" masked={mask}>
        {ev.alsoFoundBy.runs.map(r => <KV key={r.run} k={r.run}><Chip size="sm" tone="purple">{r.badge}</Chip> {r.match}{r.match.startsWith('match d') && <InfoTip title="Seed-search distance">Seed-search distance, not the 0 → 1 shape distance.</InfoTip>}</KV>)}
        {ev.alsoFoundBy.runs.length === 0 && <KV k="other runs">none</KV>}
        <KV k="human annotations">{ev.alsoFoundBy.human}</KV>
        <KV k="prior adjudication">{ev.alsoFoundBy.prior}</KV>
      </EvSection>
      <EvSection id="family" icon="library" title="Family" aside={<span className="mono muted sm">nearest by shape, not a verdict</span>} masked={mask}>
        <div className="rv-ev-fam">
          <MiniTrace values={d.medoids[f.id]} yDomain={THUMB_Y} width={70} height={34} stroke={f.colour} strokeWidth={1.5} ground="white" zeroLine={false} />
          <span><b className="mono">{f.id} · {f.name}</b><br /><span className="mono muted sm">d {f.d.toFixed(2)} · {f.members != null ? `${f.members} members` : 'members n/a'}{f.id === 'F-03' ? ' · medoid m-1846' : ''}</span></span>
        </div>
      </EvSection>
      <EvSection id="artifact" icon="alert-triangle" title="Artifact likelihood" aside={<span className="mono muted sm">not blinded</span>}>
        <KV k="likelihood"><Chip size="sm" tone={a.level === 'low' ? 'green' : a.level === 'medium' ? 'amber' : 'red'}>{a.level} · {a.p.toFixed(2)}</Chip></KV>
        <KV k="cross-channel coherence">{a.coherence.toFixed(2)} · flag ≥ 0.5</KV>
        <KV k="clipping · step change">{a.clipping} · {a.stepChange}</KV>
        <KV k="electrode flag">{a.electrodeFlag}</KV>
      </EvSection>
      <EvSection id="history" icon="clock" title="History">
        <KV k="span revisions">{ev.history.revisions}</KV>
        <KV k="verdicts">{historyVerdicts}</KV>
        <KV k="in queues">{ev.history.queues}</KV>
      </EvSection>
      <div className="rv-write-target mono" data-testid="write-target"><Icon name="database" size={13} />{ev.writeTarget}{blind ? ' (blind)' : ''}</div>
    </div>
  )
}
