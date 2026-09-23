/* Shared Library chrome (inventory "Shared Library chrome"): section bar (Motifs · Window sets · Templates, P22),
 * breadcrumb, grouping bar with its popovers, omitted drawer, queue toast, and the in-memory Library store. */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { UNDECLARED_NOTE } from '../charts/units'
import {
  Breadcrumb, Button, Checkbox, Chip, DividerV, Drawer, Icon, InfoTip, MiniTrace, NumberField, Popover, Seg, Spacer, Tabs, Toolbar, fmtInt, recordDemoWrite,
  useDemoState, useQueryState, type CrumbItem,
} from '../kit'
import { useToast } from '../shell/Toast'
import { navigate, setQuery, useApp } from '../state'
import { GROUPING_G09, UNIT_LABEL, getGroupings, getLibraryCounts, getOmitted, motifShape, type Grouping, type OmittedEntry, type Unit } from '../api/library'
import { useSourced, type SourcedState } from '../api/seam'

/* ================================================================ store ================================================================ */
/** Empty library is a data condition of the Motifs section, reached with `?library=empty` (inventory decision). It is
 *  derived from the URL rather than stored, so leaving the flag (e.g. after an import) returns to the catalogue. */
export function useEmptyLibrary(): [boolean] {
  const { route } = useApp()
  return [route.query.library === 'empty']
}
/** The scope: `recKey:channel` keys the person picked. It starts EMPTY. It used to start from three fixture
 *  keys, which named channels a live corpus does not have — a selection nobody made, of things that are not
 *  there. Nothing is selected until someone selects it. */
export const useSelection = () => useDemoState<string[]>('library.selection', () => [])

/** The grouping id a section is looking at. There is no default id: `g-07` and `g-08` are fixture names and
 *  no live grouping is called either, so defaulting to one made every atlas and every matrix fall to
 *  "undrawn". It resolves to the NEWEST saved grouping of the right unit instead — the same one the bridge
 *  picks when a read omits `?grouping=` — and stays `''` when there is none, which is the honest state of a
 *  library nobody has grouped yet. */
function useResolvedGroupingId(key: string, unit: Unit): [string, (next: string | ((prev: string) => string)) => void] {
  const [id, setId] = useDemoState<string>(key, () => '')
  const g = useSourced(getGroupings, [])
  useEffect(() => {
    if (id || !g.data) return
    const newest = newestGrouping(g.data, unit)
    if (newest) setId(newest.id)
  }, [id, g.data, unit, setId])
  return [id, setId]
}
export const useMotifGroupingId = () => useResolvedGroupingId('library.grouping.motifs', 'motifs')
export const useSequenceGroupingId = () => useResolvedGroupingId('library.grouping.sequences', 'sequences')

/** The newest grouping of one unit, by id. `undefined` when the library holds none of that unit. */
export function newestGrouping(all: Grouping[], unit: Unit): Grouping | undefined {
  const mine = all.filter(g => g.unit === unit)
  if (!mine.length) return undefined
  return mine.reduce((a, b) => (groupingNum(b.id) > groupingNum(a.id) ? b : a))
}

/** What a section knows about its grouping, for pages that must tell "still loading" apart from "this library
 *  has no grouping of this unit yet" — two states that must not draw the same. */
export function useGroupingState(unit: Unit): { id: string; grouping: Grouping | null; all: Grouping[]; loading: boolean; error: Error | null; none: boolean; reload: () => void } {
  // both hooks run every render: which one answers is a value, not a branch
  const [motifId] = useMotifGroupingId()
  const [seqId] = useSequenceGroupingId()
  const id = unit === 'sequences' ? seqId : motifId
  const { all, loading, error, reload } = useAllGroupings()
  const none = !loading && !error && !all.some(g => g.unit === unit)
  return { id, grouping: all.find(g => g.id === id) ?? null, all, loading, error, none, reload }
}
export const useSavedGroupings = () => useDemoState<Grouping[]>('library.groupings.saved', () => [])
export interface LibraryFilters { adjudicated: boolean; minMembers: number; extra: string[] }
export const useFilters = () => useDemoState<LibraryFilters>('library.filters', () => ({ adjudicated: false, minMembers: 10, extra: [] }))

/** All groupings: fixture ones plus the ones saved in this session. */
export function useAllGroupings(): SourcedState<Grouping[]> & { all: Grouping[] } {
  const g = useSourced(getGroupings, [])
  const [saved] = useSavedGroupings()
  const all = useMemo(() => [...(g.data ?? []), ...saved.filter(s => !(g.data ?? []).some(x => x.id === s.id))], [g.data, saved])
  return { ...g, all }
}
/** The number in a `g-NN` id, or NaN. The bridge emits `g-` plus a zero-padded integer, but a saved grouping
 *  named anything else must not poison a Math.max into NaN. */
export const groupingNum = (id: string) => { const m = /^g-0*(\d+)$/.exec(String(id ?? '')); return m ? Number(m[1]) : NaN }
export const nextGroupingId = (all: Grouping[]) => {
  const nums = all.map(g => groupingNum(g.id)).filter(n => Number.isFinite(n))
  return `g-${String((nums.length ? Math.max(...nums) : 0) + 1).padStart(2, '0')}`
}
export { GROUPING_G09 }

/** Toast for "Send … to Review as a queue" (P20 naming). */
export function useQueueToast() {
  const { push } = useToast()
  return (name: string, n: number) => {
    recordDemoWrite('library', 'queue', { name, items: n })
    push({ text: `Queue "${name}" · ${fmtInt(n)} items · not wired yet: POST /api/review/queues`, action: { label: 'Open Review', onClick: () => navigate('review') } })
  }
}

/** Increments on every real navigation (a typed/deep link, `navigate()`), but not on the query replacements pages
 *  make while you work (`setQuery(…, true)` dispatches a synthetic hashchange with no URLs). Key a surface on it
 *  so a deep link always opens fresh while in-page edits keep their draft. */
export function useExternalNavKey(): number {
  const [n, setN] = useState(0)
  useEffect(() => {
    const on = (e: HashChangeEvent) => { if (e.newURL) setN(x => x + 1) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return n
}

/* ================================================================ loading / failure ================================================================ */
export function LoadFailed({ what, error, onRetry }: { what: string; error: Error; onRetry?: () => void }) {
  return (
    <div className="error-card" data-testid="library-load-failed" role="alert">
      <h3 style={{ margin: '0 0 4px' }}>Could not read {what}</h3>
      <div className="mono small" style={{ color: 'var(--red)' }}>{error.message}</div>
      {onRetry && <div style={{ marginTop: 8 }}><Button size="sm" icon="refresh" onClick={onRetry}>Retry</Button></div>}
    </div>
  )
}
export const Loading = ({ height = 320, testid = 'library-loading' }: { height?: number; testid?: string }) => <div className="skeleton" style={{ height }} data-testid={testid} />

/* ================================================================ section bar ================================================================ */
export type Section = 'motifs' | 'window-sets' | 'templates'
export function SectionBar({ section, crumbs, actions, motifsCount, windowSetsCount, templatesCount }: {
  section: Section; crumbs?: CrumbItem[]; actions?: ReactNode; motifsCount?: number; windowSetsCount?: number; templatesCount?: number
}) {
  const counts = useSourced(getLibraryCounts, [])
  const [empty] = useEmptyLibrary()
  const [lastMotifs] = useDemoState<string>('library.lastMotifsRoute', () => 'library/recurrence')
  const [deletedSets] = useDemoState<string[]>('library.windowSets.deleted', () => [])
  const [archived] = useDemoState<string[]>('library.templates.archived', () => [])
  const [added] = useDemoState<{ name: string }[]>('library.templates.added', () => [])
  const c = counts.data
  const m = motifsCount ?? (empty ? 0 : c?.motifs)
  const ws = windowSetsCount ?? (c ? c.windowSets - deletedSets.length : undefined)
  const tp = templatesCount ?? (c ? Math.max(0, c.templates - archived.length + added.length) : undefined)
  const go = (v: string) => navigate(v === 'motifs' ? (empty ? 'library/import?library=empty' : lastMotifs) : `library/${v}`)
  return (
    <Toolbar testid="library-section-bar" nowrap>
      <Tabs variant="track" ariaLabel="Library sections" testid="library-sections" value={section} onChange={go}
        items={[
          { value: 'motifs', label: 'Motifs', icon: 'target', count: m == null ? '…' : fmtInt(m) },
          { value: 'window-sets', label: 'Window sets', icon: 'grid', count: ws == null ? '…' : ws },
          { value: 'templates', label: 'Templates', icon: 'file', count: tp == null ? '…' : tp },
        ]} />
      {crumbs && crumbs.length > 0 && <><DividerV /><Breadcrumb links items={crumbs} testid="library-crumbs" /></>}
      <Spacer />
      {actions}
    </Toolbar>
  )
}

/** Remember the last Motifs route so the section tab returns there. */
export function useRememberMotifsRoute() {
  const { route } = useApp()
  const [, setLast] = useDemoState<string>('library.lastMotifsRoute', () => 'library/recurrence')
  useEffect(() => {
    const p = route.path
    if (p.startsWith('library/recurrence') || p.startsWith('library/atlas') || p.startsWith('library/family')) setLast(p)
  }, [route.path, setLast])
}

export function MotifsActions({ onImport }: { onImport?: () => void }) {
  const { push } = useToast()
  return (
    <>
      <Button icon="scan" testid="find-by-shape" onClick={() => push({ text: 'not wired yet: shape query (sketch or span → nearest families)' })}>Find by shape</Button>
      <Button icon="download" testid="library-import" onClick={() => (onImport ? onImport() : navigate('library/import'))}>Import</Button>
      <ExportButton />
    </>
  )
}
function ExportButton() {
  const [gid] = useMotifGroupingId()
  const { push } = useToast()
  return <Button icon="upload" testid="library-export" onClick={() => push({ text: `not wired yet: export grouping ${gid} (families × channels CSV)` })}>Export</Button>
}

/* ================================================================ grouping bar ================================================================ */
export function GroupingBar({ unit, grouping, from, inert, onUnit }: { unit: Unit; grouping: Grouping | null; from: string; inert?: boolean; onUnit?: (u: Unit) => void }) {
  const [filters, setFilters] = useFilters()
  const [, setMotifGrouping] = useMotifGroupingId()
  const [, setSeqGrouping] = useSequenceGroupingId()
  const { all } = useAllGroupings()
  const { push } = useToast()
  const [, setDrawer] = useQueryState('drawer', '')
  const basisRef = useRef<HTMLButtonElement>(null), minRef = useRef<HTMLButtonElement>(null), artRef = useRef<HTMLButtonElement>(null), addRef = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState<'' | 'basis' | 'min' | 'artifact' | 'add'>('')
  const [minDraft, setMinDraft] = useState(filters.minMembers)
  const [minInvalid, setMinInvalid] = useState(false)
  const navKey = useExternalNavKey()
  useEffect(() => setOpen(''), [navKey])
  const close = () => setOpen('')
  const pickGrouping = (g: Grouping) => {
    close()
    recordDemoWrite('library', 'switch-grouping', { grouping: g.id })
    if (g.unit === 'motifs') setMotifGrouping(g.id)
    if (g.unit === 'sequences') setSeqGrouping(g.id)
    if (onUnit) onUnit(g.unit)
    else if (g.unit === 'sequences') navigate('library/atlas?unit=sequences')
    push({ text: `Grouping ${g.id} applied · scope cleared` })
  }
  const unitChange = (u: Unit) => {
    if (u === 'spike-trains') { navigate(`library/grouping?unit=spike-trains&from=${encodeURIComponent(from)}`); return }
    if (onUnit) onUnit(u)
  }
  const omittedLabel = grouping ? `${fmtInt(grouping.omitted)} omitted · flagged` : '…'
  return (
    <div className="k-card lib-gbar" data-testid="grouping-bar" aria-disabled={inert || undefined}>
      <span className="lib-muted-label">group</span>
      <Seg size="sm" ariaLabel="what to group" testid="unit-seg" value={unit} onChange={unitChange}
        options={(['motifs', 'sequences', 'spike-trains'] as Unit[]).map(u => ({ value: u, label: UNIT_LABEL[u], title: u === 'spike-trains' ? 'no saved grouping for spike trains — opens Edit grouping' : undefined, disabled: !onUnit && u !== unit, reason: 'switch grouping from the atlas' }))} />
      <button ref={basisRef} type="button" className="lib-basis-chip" data-testid="basis-chip" aria-expanded={open === 'basis'} onClick={() => setOpen(o => o === 'basis' ? '' : 'basis')}>
        <span>by</span> <b>{grouping?.chip[0] ?? '…'}</b> <span className="lib-basis-sub">{grouping?.chip[1]}</span><Icon name="chevron-down" size={12} />
      </button>
      <DividerV />
      <Chip tone={filters.adjudicated ? 'blue' : 'outline'} testid="filter-adjudicated" selected={filters.adjudicated}
        onClick={() => { setFilters(f => ({ ...f, adjudicated: !f.adjudicated })); push({ text: 'not wired yet: regroup filter adjudicated_only' }) }}>adjudicated only</Chip>
      <button ref={minRef} type="button" className="k-chip blue k-chip-btn" data-testid="filter-min-members" onClick={() => { setMinDraft(filters.minMembers); setMinInvalid(false); setOpen(o => o === 'min' ? '' : 'min') }}>≥ {filters.minMembers} members</button>
      <button ref={artRef} type="button" className="k-chip blue k-chip-btn" data-testid="filter-artifact" onClick={() => setOpen(o => o === 'artifact' ? '' : 'artifact')}>artifact <b style={{ fontWeight: 600 }}>flagged</b></button>
      {filters.extra.map(x => <Chip key={x} tone="blue" onRemove={() => setFilters(f => ({ ...f, extra: f.extra.filter(e => e !== x) }))} removeLabel={`remove filter ${x}`}>{x}</Chip>)}
      {unit === 'motifs' && <button ref={addRef} type="button" className="k-chip outline k-chip-btn" data-testid="filter-add" onClick={() => setOpen(o => o === 'add' ? '' : 'add')}>+ filter</button>}
      <Spacer />
      <button type="button" className="k-chip amber k-chip-btn" data-testid="omitted-chip" onClick={() => setDrawer('omitted')}><Icon name="flag" size={12} />{omittedLabel}</button>
      <Button icon="sliders" testid="edit-grouping" onClick={() => navigate(`library/grouping?from=${encodeURIComponent(from)}${unit !== 'motifs' ? `&unit=${unit}` : ''}`)}>Edit grouping</Button>

      <Popover open={open === 'basis'} onClose={close} anchorRef={basisRef} title="Groupings" subtitle="saved · computed by the Library" width={400} testid="groupings-popover">
        <div className="lib-radio-list" role="radiogroup" aria-label="saved groupings">
          {all.map(g => (
            <button key={g.id} type="button" role="radio" aria-checked={g.id === grouping?.id} className="lib-radio-row" data-testid={`grouping-option-${g.id}`} onClick={() => pickGrouping(g)}>
              <span className="lib-radio" />
              <span className="mono"><b>{g.id}</b> · {UNIT_LABEL[g.unit]} · {g.basisLabel} · {g.params} · {g.families} families{g.note ? ` · ${g.note}` : ''}</span>
              {g.id === grouping?.id && <span className="k-badge t-blue">current</span>}
            </button>
          ))}
        </div>
        <div style={{ borderTop: '1px solid var(--border)', marginTop: 8, paddingTop: 6 }}>
          <Button variant="link" icon="sliders" onClick={() => { close(); navigate(`library/grouping?from=${encodeURIComponent(from)}`) }}>Edit grouping…</Button>
        </div>
      </Popover>
      <Popover open={open === 'min'} onClose={close} anchorRef={minRef} title="Minimum members" width={260} testid="min-members-popover">
        <div className="stack">
          <NumberField value={minDraft} onValid={n => { setMinDraft(n); setMinInvalid(false) }} onChange={(_, reason) => setMinInvalid(!!reason)} validate={n => (Number.isInteger(n) && n >= 1 && n <= 1000 ? null : 'whole number from 1 to 1000')} ariaLabel="minimum members" testid="min-members-input" />
          <div className="row" style={{ justifyContent: 'flex-end' }}>
            <Button size="sm" onClick={close}>Cancel</Button>
            <Button size="sm" variant="primary" testid="min-members-apply" disabled={minInvalid} disabledReason="whole number from 1 to 1000" onClick={() => { setFilters(f => ({ ...f, minMembers: minDraft })); recordDemoWrite('library', 'filter', { minMembers: minDraft }); close(); push({ text: `not wired yet: regroup filter min_members=${minDraft}` }) }}>Apply</Button>
          </div>
        </div>
      </Popover>
      <Popover open={open === 'artifact'} onClose={close} anchorRef={artRef} title="Cross-channel artifacts" width={300} testid="artifact-popover">
        <div className="lib-radio-list" role="radiogroup">
          <button type="button" role="radio" aria-checked className="lib-radio-row" onClick={close}><span className="lib-radio" /><span className="mono">flagged · kept visible</span></button>
          <span className="k-disabled-wrap block" title="cross-channel artifacts stay visible in the Library (§8.4)">
            <button type="button" role="radio" aria-checked={false} className="lib-radio-row" disabled title="cross-channel artifacts stay visible in the Library (§8.4)"><span className="lib-radio" /><span className="mono">excluded</span><span className="mono muted small">⊘ stay visible in the Library (§8.4)</span></button>
          </span>
        </div>
      </Popover>
      <Popover open={open === 'add'} onClose={close} anchorRef={addRef} title="Add filter" width={240} flush testid="add-filter-popover">
        <div className="k-menu" role="menu">
          {['recording', 'class', 'tag', 'judged fraction', 'hand edits only'].map(k => (
            <button key={k} type="button" role="menuitem" className="k-menu-item" data-value={k} onClick={() => { close(); setFilters(f => ({ ...f, extra: f.extra.includes(k) ? f.extra : [...f.extra, k] })); push({ text: `not wired yet: regroup filter ${k}` }) }}>
              <span className="body"><span>{k}</span></span>
            </button>
          ))}
        </div>
      </Popover>
    </div>
  )
}

/* ================================================================ mV scale ================================================================ */
/** A mV value with enough significant figures to be distinguishable from zero. `toFixed(1)` printed every mV
 *  axis label in the Library as `0.0`/`−0.0` once the real traces arrived (per-family peaks run from 0.02 mV
 *  to 70 mV — first recorded here 1000x smaller, when stored volts were printed as mV), which is a number
 *  that is not true. */
export function fmtMv(v: number): string {
  if (!Number.isFinite(v)) return '—'
  const a = Math.abs(v)
  if (a === 0) return '0'
  if (a >= 0.1) return v.toFixed(2)
  if (a >= 0.01) return v.toFixed(3)
  return String(Number(v.toPrecision(2)))
}
/** `fmtMv` with an explicit sign, for an axis label. */
export const fmtMvSigned = (v: number) => (v > 0 ? `+${fmtMv(v)}` : v < 0 ? `−${fmtMv(Math.abs(v))}` : '0')

/** The trace with its OWN DC offset (its median) removed. Nothing is scaled — the mV span of the trace stays
 *  exactly what the recording held, which is the property PRD Part 2 forbids destroying. Removing the offset
 *  is what makes one shared domain possible at all: the library's traces carry baselines down to −3.67 V
 *  while the motifs riding on them are millivolts, so an offset-carrying domain is ~1,000x too tall and every
 *  card draws as a flat line pinned to the floor. (This comment once said "−3.67 mV" and "micro-volts": the
 *  bridge printed stored volts as mV until fixup-b. The ratio was right; the unit was not.) */
export function centreTrace(values: number[]): number[] {
  if (!values || values.length === 0) return values ?? []
  const s = [...values].sort((a, b) => a - b)
  const mid = s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2
  return values.map(v => v - mid)
}
/** Largest |v| in a trace — its peak deviation from its own baseline, once centred. */
export const tracePeak = (values: number[]) => (values ?? []).reduce((m, v) => Math.max(m, Math.abs(v)), 0)

/** Round a magnitude UP to two significant figures, so a domain of 0.01435 mV prints as 0.015 rather than the
 *  0.1 mV that `niceMvDomain`'s fixed 0.1 step forces on it. */
function ceilSig(v: number, digits = 2): number {
  if (!(v > 0) || !Number.isFinite(v)) return 0
  const mag = Math.pow(10, Math.floor(Math.log10(v)) - (digits - 1))
  return +(Math.ceil(v / mag) * mag).toPrecision(digits + 2)
}

/** ONE shared, unnormalised mV domain for a page of traces, set at the `p`-th percentile of the per-trace peak
 *  instead of at its maximum.
 *
 *  This is D5 made usable. The domain stays shared and nothing is normalised, so a 0.1 mV family is still
 *  drawn 200x taller than a 0.5 µV one (mV-scale families and µV-scale ones, after fixup-b); what changes is that one outlier no longer sets the scale for all 149.
 *  A family above the domain is CLIPPED, and a clipped card is marked and prints its own measured peak — a
 *  clip marker is still unnormalised evidence, a flat line is not. */
export function sharedMvDomain(peaks: number[], p = 0.75): [number, number] {
  const s = peaks.filter(v => Number.isFinite(v) && v > 0).sort((a, b) => a - b)
  if (!s.length) return [-0.01, 0.01]
  const top = ceilSig(s[Math.min(s.length - 1, Math.floor(p * (s.length - 1)))]) || ceilSig(s[s.length - 1]) || 0.01
  return [-top, top]
}

/* ================================================================ omission reasons ================================================================ */
/** The engine's five omission reasons, in the words `grouping_assignments.omit_reason` stores them. Imported
 *  by `GroupingPage` too, so the editor's panel and the drawer cannot drift apart. */
export const OMIT_REASON_LABEL: Record<string, string> = {
  outside_bins: 'outside every bin', past_cut: 'past the nearest-family distance',
  group_too_small: 'in a group under the minimum', not_in_a_sequence: 'in no sequence', no_label: 'carry no label',
}
export const omitReasonOf = (e: OmittedEntry): string | null => (e as unknown as { omitReason?: string | null }).omitReason ?? null
const shapeLabelOf = (e: OmittedEntry): string => (e as unknown as { shapeLabel?: string }).shapeLabel ?? 'shape not recorded'
const shapeKnown = (e: OmittedEntry): boolean => (e as unknown as { shapeKnown?: boolean }).shapeKnown !== false
/** `nearest`/`d` measure the distance to the nearest family, which only `past_cut` is about. For every other
 *  reason the bridge carries `nearest "—"` and `d 0.0`, and printing `d 0.00` reads as a perfect match that was
 *  thrown away anyway. */
export const nearestMeansSomething = (e: OmittedEntry) => omitReasonOf(e) === 'past_cut' && e.nearest !== '—' && e.nearest !== ''
/** One entry's reason, in words, carrying the nearest-family distance only where that is what the reason is. */
export function omittedReasonText(e: OmittedEntry): string {
  const r = omitReasonOf(e)
  const words = r ? OMIT_REASON_LABEL[r] ?? r : 'reason not recorded'
  return nearestMeansSomething(e) ? `${words} · nearest ${e.nearest} d ${e.d.toFixed(2)}` : words
}
/** The caption over a list of omitted entries, derived from the reasons the list actually holds. It used to be
 *  hard-coded to the `omit_d` one ("nearest family d > 0.50 · re-cut looser"), which was false for all 364
 *  entries in this installation: they were dropped by `min_group`, and re-cutting looser recovers none of them. */
export function omittedReasonSummary(list: OmittedEntry[]): string {
  if (!list.length) return 'nothing was left out of this grouping'
  const counts = new Map<string, number>()
  for (const e of list) { const k = omitReasonOf(e) ?? 'not recorded'; counts.set(k, (counts.get(k) ?? 0) + 1) }
  const parts = [...counts].sort((a, b) => b[1] - a[1])
    .map(([k, n]) => `${fmtInt(n)} ${OMIT_REASON_LABEL[k] ?? (k === 'not recorded' ? 'with no reason recorded' : k)}`)
  return `${parts.join(' · ')} · left out of counts, not deleted`
}

/* ================================================================ thumbnails / plots ================================================================ */
/** The omitted rows carry `(shape, amplitude, seed)` and NO waveform — `/api/library/omitted` ships no trace
 *  for any of them. So this is a SKETCH of the recorded shape at the recorded amplitude, and every caption
 *  beside it says so. It used to be captioned "thumbnails share one mV scale (±0.45 mV); never normalised",
 *  which described a drawing as signal read off the recording. An entry whose shape was never recorded gets no
 *  drawing at all. */
export const OMITTED_SKETCH_NOTE = 'shape sketch from the recorded shape and amplitude — this read carries no waveform for an omitted entry'
export function OmittedThumb({ e, yDomain, width = 62, height = 44, title }: { e: OmittedEntry; yDomain: [number, number]; width?: number | string; height?: number; title?: string }) {
  const known = shapeKnown(e)
  const amp = e.amp
  const values = useMemo(() => !known || amp === null ? [] : e.kind === 'sequence'
    ? [...motifShape(e.shape, amp, e.seed, { n: 50 }), ...new Array(20).fill(0), ...motifShape(e.shape, amp * 0.8, e.seed + 1, { n: 50 })]
    : motifShape(e.shape, amp, e.seed, { n: 80 }), [e, known, amp])
  if (known && amp === null) {
    // fixup-b: the entry's recording declares no unit, so there is no mV amplitude to sketch it at
    return (
      <span className="mono" data-testid={`omitted-nounit-${e.id}`} title={`${e.id} · ${UNDECLARED_NOTE}`}
        style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: typeof width === 'number' ? width : '100%', height, background: '#f6f7f9', border: '1px dashed var(--border-strong)', borderRadius: 6, fontSize: 9, color: 'var(--text-2)', textAlign: 'center', lineHeight: 1.1, padding: 2 }}>
        unit undeclared
      </span>
    )
  }
  if (!known) {
    return (
      <span className="mono" data-testid={`omitted-noshape-${e.id}`} title={`${e.id} · ${shapeLabelOf(e)} — there is nothing to sketch`}
        style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: typeof width === 'number' ? width : '100%', height, background: '#f6f7f9', border: '1px dashed var(--border-strong)', borderRadius: 6, fontSize: 9, color: 'var(--text-2)', textAlign: 'center', lineHeight: 1.1, padding: 2 }}>
        no shape recorded
      </span>
    )
  }
  return <MiniTrace values={values} yDomain={yDomain} width={width} height={height} stroke="#b76a00" ground="none" zeroLine={false}
    title={title ?? `${e.id} · ${omittedReasonText(e)} · ${OMITTED_SKETCH_NOTE}`} style={{ background: '#fff4e0', border: '1px solid #f6cf8f', borderRadius: 6 }} />
}

/** Motif card plot: exemplar (black) + medoid (family colour) on the page's shared mV domain, with its real
 *  +/mV/− labels. `clippedPeak` is the trace's own measured peak when it runs past the domain — the plot then
 *  says so, because `MiniTrace` clamps every sample to the domain silently. */
export function MotifPlot({ exemplar, medoid, colour, yDomain, height = 92, labels = true, testid, overlays = [], clippedPeak, unitNote }: {
  exemplar?: number[]; medoid?: number[]; colour: string; yDomain: [number, number]; height?: number; labels?: boolean; testid?: string
  overlays?: { values: number[]; stroke: string; width?: number }[]; clippedPeak?: number | null
  /** fixup-b: set when the family's traces are withheld because their recording declares no unit */
  unitNote?: string | null
}) {
  const top = fmtMvSigned(yDomain[1]), bot = fmtMvSigned(yDomain[0])
  const ov = [...overlays, ...(medoid ? [{ values: medoid, stroke: colour, width: 1.5 }] : [])]
  const clipNote = clippedPeak ? ` · CLIPPED: this trace peaks at ${fmtMv(clippedPeak)} mV, past the shared domain` : ''
  return (
    <div className="lib-mplot" data-testid={testid} style={{ position: 'relative' }}>
      {labels && <div className="lib-mplot-y" aria-hidden><span>{top}</span><span>mV</span><span>{bot}</span></div>}
      <MiniTrace values={exemplar ?? medoid ?? []} overlays={exemplar ? ov : overlays} yDomain={yDomain} width="100%" height={height} strokeWidth={1.5} stroke={exemplar ? '#1f2937' : colour} ground="grey" title={`exemplar and medoid, shared scale ${bot}…${top} mV${clipNote}`} />
      {!!unitNote && !(exemplar?.length || medoid?.length) && <span className="lib-cap" data-testid="plot-unit-undeclared" title={unitNote}
        style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, textAlign: 'center', padding: '0 34px', pointerEvents: 'auto' }}>unit undeclared · not drawn in mV</span>}
      {!!clippedPeak && <span className="k-badge t-amber" data-testid="plot-clipped" title={`this family peaks at ${fmtMv(clippedPeak)} mV, past the shared domain of ${top} mV — the drawing is cut off, the number is not`}
        style={{ position: 'absolute', top: 2, right: 2, fontSize: 9 }}>clipped · {fmtMv(clippedPeak)} mV</span>}
    </div>
  )
}

/* ================================================================ omitted drawer ================================================================ */
export function OmittedDrawer({ groupingId, unit }: { groupingId: string; unit: Unit }) {
  const [drawer, setDrawer] = useQueryState('drawer', '')
  const open = drawer === 'omitted'
  const data = useSourced(() => getOmitted(groupingId), [groupingId])
  const gLabel = groupingId || data.data?.groupingId || 'the current grouping'
  const [tab, setTab] = useState<'singles' | 'sequences'>('singles')
  const [page, setPage] = useState(1)
  const queue = useQueueToast()
  useEffect(() => setPage(1), [tab, groupingId])
  if (!open) return null
  const list = data.data ? (tab === 'sequences' ? data.data.sequences : data.data.singles) : []
  const total = data.data ? data.data.singles.length + data.data.sequences.length : 0
  const pageCount = Math.max(1, Math.ceil(list.length / 10))
  const items = list.slice((page - 1) * 10, page * 10)
  const yDomain: [number, number] = [-0.45, 0.45]
  const tabs = unit === 'sequences' && data.data ? [{ value: 'singles', label: `${fmtInt(data.data.singles.length)} single motifs` }, { value: 'sequences', label: `${data.data.sequences.length} sequences` }] : undefined
  return (
    <Drawer open onClose={() => setDrawer(null)} title={`Omitted from ${gLabel}`} subtitle={data.data && !tabs ? `${fmtInt(total)} · flagged, not deleted` : undefined} width={540} testid="omitted-drawer"
      tabs={tabs} tab={tab} onTab={v => setTab(v as 'singles' | 'sequences')}>
      {data.error && <LoadFailed what="the omitted entries" error={data.error} onRetry={data.reload} />}
      {data.loading && <Loading height={260} />}
      {data.data && (
        <div className="stack" style={{ gap: 10 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="mono small">{tabs ? `Omitted from ${gLabel} · ${fmtInt(total)} · flagged, not deleted` : ''}</span>
            <Button size="sm" icon="checklist" testid="omitted-send" onClick={() => queue(`Library · ${gLabel} omitted`, total)}>Send omitted to Review as a queue</Button>
          </div>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
            {/* the caption is the SET OF REASONS this list actually carries. It used to state the `omit_d`
                reason for every list, which is false for all 364 entries here: the min-group rule dropped
                them, and the drawer was telling the researcher to re-cut looser, which recovers none. */}
            <span className="mono small muted" data-testid="omitted-reason-summary">{omittedReasonSummary(list)}<InfoTip title="what these drawings are">{OMITTED_SKETCH_NOTE}. They share one mV scale (±0.45 mV) and nothing is normalised, but none of them is a waveform read off the recording.</InfoTip></span>
            <span className="mono small" style={{ whiteSpace: 'nowrap', flex: 'none' }}>{fmtInt((page - 1) * 10 + 1)}–{fmtInt(Math.min(list.length, page * 10))} of {fmtInt(list.length)}
              <button type="button" className="lib-pg" disabled={page <= 1} aria-label="previous page" title={page <= 1 ? 'already at the first page' : 'previous page'} onClick={() => setPage(p => p - 1)} data-testid="omitted-prev">‹</button>
              <button type="button" className="lib-pg" disabled={page >= pageCount} aria-label="next page" title={page >= pageCount ? 'already at the last page' : 'next page'} onClick={() => setPage(p => p + 1)} data-testid="omitted-next">›</button>
            </span>
          </div>
          <div className="lib-omitted-grid" data-testid="omitted-grid">
            {items.map(e => (
              <div key={e.id} className="lib-omitted-cell">
                <OmittedThumb e={e} yDomain={yDomain} width="100%" height={52} />
                {/* the per-entry reason the bridge already sends. `nearest`/`d` are printed only for the one
                    reason they measure; for the rest the bridge carries `—`/`0.0`, and "d 0.00" read as a
                    perfect match that was discarded anyway. */}
                <div className="mono small"><b>{e.id}</b> {nearestMeansSomething(e) && <span className="muted">d {e.d.toFixed(2)}</span>}</div>
                <div className="mono small muted" data-testid={`omitted-reason-${e.id}`}>{omittedReasonText(e)}</div>
                <div className="mono small muted">{e.recording} · {e.channel} · {e.onsetH.toFixed(2)} h</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Drawer>
  )
}

export function setQueryReplace(patch: Record<string, string | null>) { setQuery(patch, true) }
