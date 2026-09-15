/* In-page navigation: Tabs, Seg, Breadcrumb, Pager. */
import { useRef, type ReactNode } from 'react'
import { useQueryState } from './hooks'
import { Icon, type IconName } from './icons'
import { cx, tid, type TestIdProps } from './portal'

/* ================= Tabs ================= */
export interface TabItem { value: string; label: ReactNode; icon?: IconName; count?: ReactNode; disabled?: boolean; reason?: string }
export interface TabsProps extends TestIdProps {
  items: TabItem[]; value?: string; onChange?: (value: string) => void
  /** Bind the selected tab to a hash query parameter (`?tab=results`); `value`/`onChange` are then optional. */
  queryKey?: string
  /** pill = white pill on the page ground (models "Launch · Results"); track = grey track (library "Motifs 1,402"); soft = blue-tint (drawer tabs); underline. */
  variant?: 'pill' | 'track' | 'soft' | 'underline'; ariaLabel?: string
}
/** Tab bar with roving focus (← → Home End). Tabs whose value is disabled carry their reason as title. */
export function Tabs({ items, value, onChange, queryKey, variant = 'pill', ariaLabel = 'tabs', ...t }: TabsProps) {
  const [qv, setQv] = useQueryState(queryKey ?? '__no_tab_key', items[0]?.value ?? '')
  const current = queryKey ? qv : value ?? items[0]?.value
  const change = (v: string) => { if (queryKey) setQv(v); onChange?.(v) }
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const enabled = items.map((it, k) => (it.disabled ? -1 : k)).filter(k => k >= 0)
    const pos = enabled.indexOf(i)
    let next: number | undefined
    if (e.key === 'ArrowRight') next = enabled[(pos + 1) % enabled.length]
    else if (e.key === 'ArrowLeft') next = enabled[(pos - 1 + enabled.length) % enabled.length]
    else if (e.key === 'Home') next = enabled[0]
    else if (e.key === 'End') next = enabled[enabled.length - 1]
    if (next === undefined) return
    e.preventDefault(); refs.current[next]?.focus(); change(items[next].value)
  }
  return (
    <div className={cx('k-tabs', variant !== 'pill' && variant)} role="tablist" aria-label={ariaLabel} data-testid={tid(t)}>
      {items.map((it, i) => {
        const on = it.value === current
        return (
          <button key={it.value} ref={el => { refs.current[i] = el }} type="button" role="tab" className="k-tab" aria-selected={on} tabIndex={on ? 0 : -1}
            disabled={it.disabled} title={it.disabled ? it.reason : undefined} data-testid={tid(t) ? `${tid(t)}-${it.value}` : `tab-${it.value}`}
            onClick={() => change(it.value)} onKeyDown={e => onKey(e, i)}>
            {it.icon && <Icon name={it.icon} size={14} />}{it.label}{it.count != null && <span className="count">{it.count}</span>}
          </button>
        )
      })}
    </div>
  )
}

/* ================= Seg ================= */
export interface SegOption<V extends string = string> { value: V; label: ReactNode; disabled?: boolean; reason?: string; title?: string }
export interface SegProps<V extends string = string> extends TestIdProps { options: SegOption<V>[]; value: V; onChange: (v: V) => void; size?: 'sm' | 'md' | 'lg'; label?: ReactNode; ariaLabel?: string }
/** Segmented control (radiogroup, ← → keys). Disabled options show their reason on hover. */
export function Seg<V extends string = string>({ options, value, onChange, size = 'md', label, ariaLabel, ...t }: SegProps<V>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const onKey = (e: React.KeyboardEvent, i: number) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const d = e.key === 'ArrowRight' ? 1 : -1
    let j = i
    for (let k = 0; k < options.length; k++) { j = (j + d + options.length) % options.length; if (!options[j].disabled) break }
    refs.current[j]?.focus(); onChange(options[j].value)
  }
  const seg = (
    <div className={cx('k-seg', size !== 'md' && size)} role="radiogroup" aria-label={ariaLabel ?? (typeof label === 'string' ? label : undefined)} data-testid={tid(t)}>
      {options.map((o, i) => (
        <button key={o.value} ref={el => { refs.current[i] = el }} type="button" role="radio" aria-checked={o.value === value} tabIndex={o.value === value ? 0 : -1}
          disabled={o.disabled} title={o.disabled ? o.reason : o.title} data-value={o.value} onClick={() => onChange(o.value)} onKeyDown={e => onKey(e, i)}>{o.label}</button>
      ))}
    </div>
  )
  return label ? <span className="row" style={{ gap: 8 }}><span className="k-seg-label">{label}</span>{seg}</span> : seg
}

/* ================= Breadcrumb ================= */
export interface CrumbItem { label: ReactNode; onClick?: () => void; href?: string }
/** "Corpus › M2_aug_concat_fs1.mat › CH4_A2". The last item is the current page. `links` = blue sans links (library "Recurrence › Atlas"). */
export function Breadcrumb({ items, links, ...t }: { items: CrumbItem[]; links?: boolean } & TestIdProps) {
  return (
    <nav className={cx('k-crumb', links && 'links')} aria-label="breadcrumb" data-testid={tid(t)}>
      {items.map((it, i) => {
        const last = i === items.length - 1
        return (
          <span key={i} style={{ display: 'contents' }}>
            {i > 0 && <span className="sep" aria-hidden>›</span>}
            {last ? <span className="cur" aria-current="page">{it.label}</span>
              : <button type="button" onClick={() => { if (it.onClick) it.onClick(); else if (it.href) window.location.hash = it.href }}>{it.label}</button>}
          </span>
        )
      })}
    </nav>
  )
}

/* ================= Pager ================= */
export interface PagerProps extends TestIdProps {
  page: number; pageCount: number; onPage: (page: number) => void
  /** index: "‹ 233 / 344 ›"; range: "1–10 of 112 ‹ ›" (needs total + pageSize). */
  format?: 'index' | 'range'; total?: number; pageSize?: number; boxed?: boolean; label?: string
}
export function Pager({ page, pageCount, onPage, format = 'index', total, pageSize = 10, boxed, label = 'page', ...t }: PagerProps) {
  const fmt = (n: number) => n.toLocaleString('en-US')
  const first = page <= 1, last = page >= pageCount
  const prev = <button type="button" onClick={() => onPage(page - 1)} disabled={first} aria-label={`previous ${label}`} title={first ? `already at the first ${label}` : `previous ${label}`} data-testid={tid(t) ? `${tid(t)}-prev` : undefined}><Icon name="chevron-left" size={13} /></button>
  const next = <button type="button" onClick={() => onPage(page + 1)} disabled={last} aria-label={`next ${label}`} title={last ? `already at the last ${label}` : `next ${label}`} data-testid={tid(t) ? `${tid(t)}-next` : undefined}><Icon name="chevron-right" size={13} /></button>
  if (format === 'range') {
    const n = total ?? pageCount * pageSize
    const from = n ? (page - 1) * pageSize + 1 : 0, to = Math.min(n, page * pageSize)
    return <div className={cx('k-pager', boxed && 'boxed')} data-testid={tid(t)}><span className="lbl">{fmt(from)}–{fmt(to)} of {fmt(n)}</span>{prev}{next}</div>
  }
  return <div className={cx('k-pager', boxed && 'boxed')} data-testid={tid(t)}>{prev}<span className="lbl"><span className="cur">{fmt(page)}</span> / {fmt(pageCount)}</span>{next}</div>
}
