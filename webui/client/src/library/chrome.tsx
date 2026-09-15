/* Shared Library chrome (inventory "Shared Library chrome"): section bar (Motifs · Window sets · Templates, P22),
 * breadcrumb, grouping bar with its popovers, omitted drawer, queue toast, and the in-memory Library store. */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  Breadcrumb, Button, Checkbox, Chip, DividerV, Drawer, Icon, InfoTip, MiniTrace, NumberField, Popover, Seg, Spacer, Tabs, Toolbar, fmtInt, recordDemoWrite,
  useDemoState, useQueryState, type CrumbItem,
} from '../kit'
import { useToast } from '../shell/Toast'
import { navigate, setQuery, useApp } from '../state'
import { CANON_SELECTION, GROUPING_G09, UNIT_LABEL, getGroupings, getLibraryCounts, getOmitted, motifShape, type Grouping, type OmittedEntry, type Unit } from '../api/library'
import { useSourced, type SourcedState } from '../api/seam'

/* ================================================================ store ================================================================ */
/** Empty library is a data condition of the Motifs section, reached with `?library=empty` (inventory decision). It is
 *  derived from the URL rather than stored, so leaving the flag (e.g. after an import) returns to the catalogue. */
export function useEmptyLibrary(): [boolean] {
  const { route } = useApp()
  return [route.query.library === 'empty']
}
export const useSelection = () => useDemoState<string[]>('library.selection', () => [...CANON_SELECTION])
export const useMotifGroupingId = () => useDemoState<string>('library.grouping.motifs', () => 'g-07')
export const useSequenceGroupingId = () => useDemoState<string>('library.grouping.sequences', () => 'g-08')
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
export const nextGroupingId = (all: Grouping[]) => `g-${String(Math.max(8, ...all.map(g => Number(g.id.slice(2)))) + 1).padStart(2, '0')}`
export { GROUPING_G09 }

/** Toast for "Send … to Review as a queue" (P20 naming). */
export function useQueueToast() {
  const { push } = useToast()
  return (name: string, n: number) => {
    recordDemoWrite('library', 'queue', { name, items: n })
    push({ text: `Queue "${name}" · ${fmtInt(n)} items · not wired yet: POST /api/review/queues`, action: { label: 'Open Review', onClick: () => navigate('review/queue/q-12') } })
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
  const tp = templatesCount ?? (c ? c.templates - archived.length + added.length : undefined)
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

/* ================================================================ thumbnails / plots ================================================================ */
export function OmittedThumb({ e, yDomain, width = 62, height = 44, title }: { e: OmittedEntry; yDomain: [number, number]; width?: number | string; height?: number; title?: string }) {
  const values = useMemo(() => e.kind === 'sequence'
    ? [...motifShape(e.shape, e.amp, e.seed, { n: 50 }), ...new Array(20).fill(0), ...motifShape(e.shape, e.amp * 0.8, e.seed + 1, { n: 50 })]
    : motifShape(e.shape, e.amp, e.seed, { n: 80 }), [e])
  return <MiniTrace values={values} yDomain={yDomain} width={width} height={height} stroke="#b76a00" ground="none" zeroLine={false} title={title ?? `${e.id} · nearest ${e.nearest} · d ${e.d.toFixed(2)}`} style={{ background: '#fff4e0', border: '1px solid #f6cf8f', borderRadius: 6 }} />
}

/** Motif card plot: exemplar (black) + medoid (family colour) on the page's shared mV domain, with +/mV/− labels. */
export function MotifPlot({ exemplar, medoid, colour, yDomain, height = 92, labels = true, testid, overlays = [] }: {
  exemplar?: number[]; medoid?: number[]; colour: string; yDomain: [number, number]; height?: number; labels?: boolean; testid?: string; overlays?: { values: number[]; stroke: string; width?: number }[]
}) {
  const top = `+${yDomain[1].toFixed(1)}`, bot = `−${Math.abs(yDomain[0]).toFixed(1)}`
  const ov = [...overlays, ...(medoid ? [{ values: medoid, stroke: colour, width: 1.5 }] : [])]
  return (
    <div className="lib-mplot" data-testid={testid}>
      {labels && <div className="lib-mplot-y" aria-hidden><span>{top}</span><span>mV</span><span>{bot}</span></div>}
      <MiniTrace values={exemplar ?? medoid ?? []} overlays={exemplar ? ov : overlays} yDomain={yDomain} width="100%" height={height} strokeWidth={1.5} stroke={exemplar ? '#1f2937' : colour} ground="grey" title={`exemplar and medoid, shared scale ${bot}…${top} mV`} />
    </div>
  )
}

/* ================================================================ omitted drawer ================================================================ */
export function OmittedDrawer({ groupingId, unit }: { groupingId: string; unit: Unit }) {
  const [drawer, setDrawer] = useQueryState('drawer', '')
  const open = drawer === 'omitted'
  const data = useSourced(() => getOmitted(groupingId), [groupingId])
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
    <Drawer open onClose={() => setDrawer(null)} title={`Omitted from ${groupingId}`} subtitle={data.data && !tabs ? `${fmtInt(total)} · flagged, not deleted` : undefined} width={540} testid="omitted-drawer"
      tabs={tabs} tab={tab} onTab={v => setTab(v as 'singles' | 'sequences')}>
      {data.error && <LoadFailed what="the omitted entries" error={data.error} onRetry={data.reload} />}
      {data.loading && <Loading height={260} />}
      {data.data && (
        <div className="stack" style={{ gap: 10 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="mono small">{tabs ? `Omitted from ${groupingId} · ${fmtInt(total)} · flagged, not deleted` : ''}</span>
            <Button size="sm" icon="checklist" testid="omitted-send" onClick={() => queue(`Library · ${groupingId} omitted`, total)}>Send omitted to Review as a queue</Button>
          </div>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span className="mono small muted">{tab === 'sequences' ? 'nearest family d > 0.50 · re-cut looser, or leave them flagged' : unit === 'sequences' ? 'not part of any sequence · switch the unit to single motifs to group these' : 'nearest family d > 0.50 · left out of counts, not deleted'}<InfoTip title="shared y">thumbnails share one mV scale (±0.45 mV); never normalised</InfoTip></span>
            <span className="mono small" style={{ whiteSpace: 'nowrap', flex: 'none' }}>{fmtInt((page - 1) * 10 + 1)}–{fmtInt(Math.min(list.length, page * 10))} of {fmtInt(list.length)}
              <button type="button" className="lib-pg" disabled={page <= 1} aria-label="previous page" title={page <= 1 ? 'already at the first page' : 'previous page'} onClick={() => setPage(p => p - 1)} data-testid="omitted-prev">‹</button>
              <button type="button" className="lib-pg" disabled={page >= pageCount} aria-label="next page" title={page >= pageCount ? 'already at the last page' : 'next page'} onClick={() => setPage(p => p + 1)} data-testid="omitted-next">›</button>
            </span>
          </div>
          <div className="lib-omitted-grid" data-testid="omitted-grid">
            {items.map(e => (
              <div key={e.id} className="lib-omitted-cell">
                <OmittedThumb e={e} yDomain={yDomain} width="100%" height={52} />
                <div className="mono small"><b>{e.id}</b> <span className="muted">d {e.d.toFixed(2)}</span></div>
                <div className="mono small muted">nearest {e.nearest} · {e.recording} · {e.channel} · {e.onsetH.toFixed(2)} h</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Drawer>
  )
}

export function setQueryReplace(patch: Record<string, string | null>) { setQuery(patch, true) }
