/* Settings shared chrome (inventory "settings.shell"): the settings nav, the page title row with its
 * scope badge and "Reset page to defaults", the row grammar (label · control · consequence), the
 * locked-field glyphs, the sticky save bar and the leave guard. Every #/settings/* page is built from it. */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  Badge, Button, Chip, DisabledReason, EmptyState, Icon, InfoTip, Modal, Page, PageTitle, Popover, SideNav, TextField,
  Tooltip, useQueryFlag, useQueryState,
} from '../kit'
import { Header } from '../shell/Header'
import { navigate } from '../state'
import { NAV_GROUPS, PAGE_META, SEARCH_INDEX, SLUGS } from '../api/settings'
import { useToast } from '../shell/Toast'
import { publishDisplayPrefs, useNavDots, useSettingsPage, useSeededDraft, type SettingsPageStore } from './store'
import './settings.css'

/* ------------------------------------------------------------------ small parts */

export const Loading = ({ height = 320, testid = 'settings-loading' }: { height?: number; testid?: string }) =>
  <div className="skeleton" style={{ height }} data-testid={testid} aria-label="loading" />

export function LoadFailed({ what, error, onRetry }: { what: string; error: Error; onRetry?: () => void }) {
  return (
    <div className="error-card" data-testid="settings-load-failed" role="alert">
      <h3>Could not read {what}</h3>
      <div className="mono small" style={{ color: 'var(--red)' }}>{error.message}</div>
      {onRetry && <div style={{ marginTop: 8 }}><Button size="sm" icon="refresh" onClick={onRetry}>Retry</Button></div>}
    </div>
  )
}

/** A settings form row: mono label (with its amber diff dot and ⓘ), the control, the consequence caption. */
export function Row({ label, sub, info, children, caption, dot, unsaved, id, testid, wide }: {
  label: ReactNode; sub?: ReactNode; info?: ReactNode; children: ReactNode; caption?: ReactNode
  dot?: boolean; unsaved?: boolean; id?: string; testid?: string; wide?: boolean
}) {
  return (
    <div className={`s-row${wide ? ' wide' : ''}`} id={id} data-testid={testid}>
      <div className="s-row-label">
        <span className="s-label mono">{dot && <span className="s-dot" aria-label="differs from default" />}{label}{info && <InfoTip>{info}</InfoTip>}</span>
        {sub && <span className="s-sub mono">{sub}</span>}
      </div>
      <div className={`s-row-control${unsaved ? ' unsaved' : ''}`}>{children}</div>
      {caption ? <div className="s-row-caption mono">{caption}</div> : <span />}
    </div>
  )
}

/** Label above an input in a field grid (Datasets metadata). */
export function GridField({ label, info, dot, unsaved, children, testid }: { label: ReactNode; info?: ReactNode; dot?: boolean; unsaved?: boolean; children: ReactNode; testid?: string }) {
  return (
    <div className="s-gf" data-testid={testid}>
      <span className="s-label mono">{dot && <span className="s-dot" />}{label}{info && <InfoTip>{info}</InfoTip>}</span>
      <div className={unsaved ? 'unsaved' : undefined}>{children}</div>
    </div>
  )
}

/** A value the tool enforces: grey fill, lock glyph, never editable and never a diff dot. */
export function LockedField({ children, reason, testid, width }: { children: ReactNode; reason: string; testid?: string; width?: number | string }) {
  return (
    <Tooltip content={`Enforced by the tool: ${reason}`}>
      <span className="s-locked mono" data-testid={testid} style={{ width }} tabIndex={0}><Icon name="lock" size={12} />{children}</span>
    </Tooltip>
  )
}

export function LockedChip({ children, reason, testid }: { children: ReactNode; reason: string; testid?: string }) {
  return (
    <Tooltip content={`Enforced by the tool: ${reason}`}>
      <span className="s-locked-chip mono" data-testid={testid} tabIndex={0}><Icon name="lock" size={11} />{children}</span>
    </Tooltip>
  )
}

/** A toggle the tool enforces: pale, not clickable, with the rule behind it. */
export function LockedToggle({ on = true, reason, testid }: { on?: boolean; reason: string; testid?: string }) {
  return (
    <Tooltip content={`Enforced by the tool: ${reason}`}>
      <span className={`s-locked-toggle${on ? ' on' : ''}`} data-testid={testid} tabIndex={0} role="img" aria-label={`${on ? 'on' : 'off'} · enforced`}>
        <span className="knob" /><Icon name="lock" size={10} />
      </span>
    </Tooltip>
  )
}

/* ------------------------------------------------------------------ the shell */

export interface ShellProps {
  slug: string
  demo?: boolean
  children: ReactNode
  /** extra chips on the title row, right of the scope badge */
  chips?: ReactNode
  /** extra buttons left of "Reset page to defaults" (Audit log's Export CSV) */
  actions?: ReactNode
  /** hide "Reset page to defaults" (About and Audit log have nothing to reset) */
  noReset?: boolean
}

export function SettingsShell({ slug, demo, children, chips, actions, noReset }: ShellProps) {
  const meta = PAGE_META[slug]
  const store = useSettingsPage(slug)
  const [state] = useQueryState('state', '')
  useSeededDraft(slug, state === 'unsaved')
  const dots = useNavDots()
  /* the search modal and the reset popover are deep-linkable (?search=1, ?reset=1) so they follow the
     URL like every other surface — a repeated navigation to the same route cannot leave one open */
  const [search, setSearch] = useQueryFlag('search')
  const [leaveTo, setLeaveTo] = useState<string | null>(null)
  const [resetOpen, setResetOpen] = useQueryFlag('reset')
  const resetRef = useRef<HTMLButtonElement>(null)
  const [focusId] = useQueryState('focus', '')
  const { push } = useToast()
  /* the two personal pages are read here, not only on their own page: density paints every table and
     the leave guard is the toggle on Keyboard & behaviour (§9.15, §9.16) */
  const display = useSettingsPage('display')
  const keyboard = useSettingsPage('keyboard')
  const density = display.str('density')
  const guardLeave = keyboard.bool('confirm_leave')
  const timeAxis = display.str('time_axis'), amplitude = display.str('amplitude'), sampleIndices = display.bool('sample_indices')

  useEffect(() => {
    document.documentElement.dataset.density = density
    publishDisplayPrefs({ density, time_axis: timeAxis, amplitude, sample_indices: sampleIndices })
  }, [density, timeAxis, amplitude, sampleIndices])

  const groups = useMemo(() => NAV_GROUPS.flatMap(sec => sec.groups.map((g, i) => ({
    section: i === 0 ? sec.section : undefined,
    sectionIcon: i === 0 ? sec.icon : undefined,
    sectionTone: i === 0 ? sec.tone : undefined,
    label: g.label,
    items: g.slugs.map(s => ({ value: s, label: PAGE_META[s].title, differs: dots[s] })),
  }))), [dots])

  /* the header's search pill calls back into Settings (orchestrator, R1); Ctrl K is bound here */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      /* a key-capture cell owns every chord while it is open — Ctrl K there is a binding, not a search */
      if (document.activeElement?.hasAttribute('data-capturing')) return
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setSearch(true) }
    }
    /* a surface belongs to the route it was opened on: close it when the hash changes */
    const onHash = () => setLeaveTo(null)
    window.addEventListener('keydown', onKey)
    window.addEventListener('hashchange', onHash)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('hashchange', onHash) }
  }, [])

  /* ?focus=<field> pulses the field for 2 s (header chip and search both deep-link into it) */
  useEffect(() => {
    if (!focusId) return
    const el = document.getElementById(`f-${focusId}`)
    if (!el) return
    el.scrollIntoView({ block: 'center', behavior: 'smooth' })
    el.classList.add('s-pulse')
    const t = window.setTimeout(() => el.classList.remove('s-pulse'), 2200)
    return () => window.clearTimeout(t)
  }, [focusId, slug])

  const go = (to: string) => {
    if (to === slug) return
    const n = store.changes.length
    if (n && guardLeave) { setLeaveTo(to); return }
    if (n) push({ text: `${n} unsaved change${n === 1 ? '' : 's'} left on ${meta?.title ?? slug} · nothing was written` })
    navigate(`settings/${to}`)
  }

  const invalidCount = Object.keys(store.invalid).length

  return (
    <>
      <Header workspace="Settings" page={meta?.title ?? slug} subtitle={store.scope} search="Search settings" demo={demo} onSearch={() => setSearch(true)} />
      <div className="s-shell" data-testid="settings-shell">
        <SideNav groups={groups} value={slug} onChange={go} testid="settings-nav" ariaLabel="settings pages" />
        <div className="s-col" data-testid="settings-column">
          <Page maxWidth={1120} testid="settings-page">
            <PageTitle title={meta?.title ?? slug}
              actions={(
                <>
                  {actions}
                  {!noReset && <>
                  <Button ref={resetRef} variant="link" icon="refresh" testid="reset-page"
                    disabled={store.differingCount === 0} disabledReason="Nothing differs from default"
                    onClick={() => setResetOpen(!resetOpen)}>Reset page to defaults</Button>
                  <Popover open={resetOpen} onClose={() => setResetOpen(false)} anchorRef={resetRef} placement="bottom-end" width={330}
                    title={`Reset ${meta?.title ?? slug} to defaults?`} testid="reset-popover">
                    <div className="small" style={{ lineHeight: 1.5 }}>
                      {store.differingCount} value{store.differingCount === 1 ? '' : 's'} differ{store.differingCount === 1 ? 's' : ''} from the default.
                      {store.scope === 'project'
                        ? ' The defaults are staged as unsaved edits — nothing is written until you save.'
                        : ' Personal settings apply to this browser immediately.'}
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 10, justifyContent: 'flex-end' }}>
                      <Button size="sm" onClick={() => setResetOpen(false)}>Cancel</Button>
                      <Button size="sm" variant="primary" testid="reset-confirm" onClick={() => { store.resetToDefaults(); setResetOpen(false) }}>Reset</Button>
                    </div>
                  </Popover>
                  </>}
                </>
              )}>
              <Badge tone={store.scope === 'project' ? 'blue' : 'grey'} testid="scope-badge">
                {store.scope === 'project' ? 'project · recorded with runs' : 'personal · this browser'}
              </Badge>
              {chips}
            </PageTitle>
            {meta?.lede && <div className="s-lede mono" data-testid="page-lede">{meta.lede}</div>}
            {children}
            <div style={{ height: store.changes.length ? 8 : 24 }} />
          </Page>

          {store.changes.length > 0 && store.scope === 'project' && (
            <div className="s-savebar" data-testid="save-bar">
              <span className="s-dot" />
              <b>{store.changes.length} unsaved change{store.changes.length === 1 ? '' : 's'}</b>
              <span className="s-consequence mono" data-testid="save-consequence">{store.sentence}</span>
              <span className="k-spacer" />
              <Button testid="discard" onClick={store.discard}>Discard</Button>
              <Button variant="primary" testid="save-changes" disabled={invalidCount > 0}
                disabledReason={invalidCount > 0 ? `Fix ${invalidCount} invalid value${invalidCount === 1 ? '' : 's'} first` : undefined}
                onClick={store.save}>Save changes</Button>
            </div>
          )}
        </div>
      </div>

      <Modal open={!!leaveTo} onClose={() => setLeaveTo(null)} title={`Leave with ${store.changes.length} unsaved change${store.changes.length === 1 ? '' : 's'}?`}
        size="sm" testid="leave-guard"
        footerNote="from Keyboard & behaviour · confirm before leaving unsaved settings (turn it off there to leave without asking)"
        footer={<>
          <Button onClick={() => setLeaveTo(null)}>Stay</Button>
          <Button variant="danger" testid="discard-and-leave" onClick={() => { const to = leaveTo!; store.discard(); setLeaveTo(null); navigate(`settings/${to}`) }}>Discard and leave</Button>
        </>}>
        <div className="small">{store.sentence || 'The edits are held in this browser and are not written anywhere yet.'}</div>
      </Modal>

      <SettingsSearch open={search} onClose={() => setSearch(false)} />
    </>
  )
}

/* ------------------------------------------------------------------ Ctrl K search */

function SettingsSearch({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState('')
  useEffect(() => { if (open) setQ('') }, [open])
  const hits = SEARCH_INDEX.filter(h => `${h.page} ${h.card} ${h.field}`.toLowerCase().includes(q.toLowerCase())).slice(0, 12)
  const openHit = (slug: string, field: string) => { onClose(); navigate(`settings/${slug}?focus=${encodeURIComponent(field.replace(/[^a-z0-9]+/gi, '-').toLowerCase())}`) }
  return (
    <Modal open={open} onClose={onClose} title="Search settings" size="md" testid="settings-search"
      footerNote={`${SEARCH_INDEX.length} indexed fields across ${SLUGS.length} pages · a UI-only index (F2)`}>
      <TextField value={q} onChange={setQ} block autoFocus placeholder="field, card or page" icon="search" testid="settings-search-input"
        onEnter={() => hits[0] && openHit(hits[0].slug, hits[0].field)} />
      <div className="s-hits" data-testid="settings-search-hits">
        {hits.map(h => (
          <button key={`${h.slug}-${h.field}`} type="button" className="s-hit" onClick={() => openHit(h.slug, h.field)} data-testid={`hit-${h.slug}`}>
            <span className="mono muted">{h.page} › {h.card} ›</span> <b>{h.field}</b>
          </button>
        ))}
        {!hits.length && <EmptyState size="sm" title={`Nothing matches “${q}”`} caption="the index covers one field per card" testid="search-empty" />}
      </div>
    </Modal>
  )
}

/* ------------------------------------------------------------------ helpers pages reuse */

/** "8 more channels" style disclosure. */
export function Disclosure({ open, onToggle, more, fewer, testid }: { open: boolean; onToggle: () => void; more: string; fewer: string; testid?: string }) {
  return <Button variant="link" size="sm" icon={open ? 'chevron-up' : 'chevron-down'} onClick={onToggle} testid={testid}>{open ? fewer : more}</Button>
}

/** Read-only chip listing a held-out refusal (D6) — used wherever M4_aug would be offered. */
export function HeldOutNote({ what }: { what: string }) {
  return <Chip tone="grey" icon="lock" testid="held-out-note">M4_aug is held out · {what}</Chip>
}

export function reasonFor(store: SettingsPageStore, id: string): string | undefined { return store.invalid[id] }
