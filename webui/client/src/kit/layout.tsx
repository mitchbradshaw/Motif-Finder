/* Layout: Page, PageTitle, Toolbar, Spacer, Card, SectionCard, SplitPane, Rail, SideNav. */
import { useState, type CSSProperties, type ReactNode } from 'react'
import { DisabledReason, IconButton } from './display'
import { useControllable } from './hooks'
import { Icon, type IconName } from './icons'
import { cx, tid, type TestIdProps } from './portal'
import { InfoTip } from './surfaces'

/* ================= Page ================= */
export interface PageProps extends TestIdProps { children: ReactNode; maxWidth?: number | string; gap?: number; style?: CSSProperties }
/** Scrolling page body under the Header: centred column, default max width 1376 px, 12 px gap. */
export function Page({ children, maxWidth = 1376, gap = 12, style, ...t }: PageProps) {
  return <div className="k-page" data-testid={tid(t) ?? 'page'}><div className="k-page-inner" style={{ maxWidth, gap, ...style }}>{children}</div></div>
}
/** Large in-page title ("Compute & HPC  project · recorded with runs") with right-side actions. */
export function PageTitle({ title, subtitle, children, actions }: { title: ReactNode; subtitle?: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  return <div className="k-page-title"><h1>{title}</h1>{children}{subtitle && <span className="sub">{subtitle}</span>}{actions && <><span className="k-spacer" />{actions}</>}</div>
}

/* ================= Toolbar ================= */
export function Toolbar({ children, card, nowrap, style, ...t }: { children: ReactNode; card?: boolean; nowrap?: boolean; style?: CSSProperties } & TestIdProps) {
  return <div className={cx('k-toolbar', card && 'k-card card', nowrap && 'nowrap')} style={style} role="toolbar" data-testid={tid(t)}>{children}</div>
}
export const Spacer = () => <span className="k-spacer" />
export const DividerV = () => <span className="k-divider-v" aria-hidden />

/* ================= Card ================= */
export interface CardProps extends TestIdProps {
  children: ReactNode; padding?: 'none' | 'md' | 'lg'; variant?: 'default' | 'flat' | 'grey'
  tone?: 'amber' | 'green' | 'red' | 'blue' | 'purple'; selected?: boolean; onClick?: () => void; title?: string; className?: string; style?: CSSProperties; ariaLabel?: string
}
/** White card, 1 px border, 10 px radius. With `onClick` it is a button (keyboard + focus ring). */
export function Card({ children, padding = 'md', variant = 'default', tone, selected, onClick, title, className, style, ariaLabel, ...t }: CardProps) {
  const cls = cx('k-card', padding === 'md' && 'pad', padding === 'lg' && 'pad-lg', variant !== 'default' && variant, tone && `tone-${tone}`, selected && 'selected', onClick && 'k-card-click', className)
  if (onClick) return <button type="button" className={cls} style={style} onClick={onClick} title={title} aria-pressed={selected} aria-label={ariaLabel} data-testid={tid(t)}>{children}</button>
  return <div className={cls} style={style} title={title} data-testid={tid(t)}>{children}</div>
}

/* ================= SectionCard ================= */
export interface SectionCardProps extends TestIdProps {
  title: ReactNode; number?: number | string; info?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; icon?: IconName
  children?: ReactNode; footer?: ReactNode; collapsible?: boolean; open?: boolean; defaultOpen?: boolean; onToggle?: (open: boolean) => void
  flush?: boolean; tone?: CardProps['tone']; style?: CSSProperties; bodyStyle?: CSSProperties; id?: string
}
/** Numbered section card: "① Training template ⓘ from Analyse ……… Open in Analyse". `info` is InfoTip text. */
export function SectionCard({ title, number, info, subtitle, actions, icon, children, footer, collapsible, open, defaultOpen = true, onToggle, flush, tone, style, bodyStyle, id, ...t }: SectionCardProps) {
  const [isOpen, setOpen] = useControllable(open, defaultOpen, onToggle)
  const heading = <>{number != null && <span className="k-section-num">{number}</span>}{icon && <Icon name={icon} size={15} />}<h3>{title}</h3></>
  return (
    <section id={id} className={cx('k-card k-section', !isOpen && 'collapsed', tone && `tone-${tone}`)} style={style} data-testid={tid(t)} aria-label={typeof title === 'string' ? title : undefined}>
      <div className="k-section-head">
        {collapsible
          ? <button type="button" className="k-section-toggle" aria-expanded={isOpen} onClick={() => setOpen(!isOpen)}><Icon name="chevron-down" size={14} className="chev" />{heading}</button>
          : heading}
        {info && <InfoTip title={typeof title === 'string' ? title : undefined}>{info}</InfoTip>}
        {subtitle && <span className="sub">{subtitle}</span>}
        {actions && <div className="acts">{actions}</div>}
      </div>
      {isOpen && children != null && <div className={cx('k-section-body', flush && 'flush')} style={bodyStyle}>{children}</div>}
      {isOpen && footer && <div className="k-section-foot">{footer}</div>}
    </section>
  )
}

/* ================= SplitPane / Rail ================= */
export interface SplitPaneProps extends TestIdProps { children: ReactNode; left?: ReactNode; right?: ReactNode; leftWidth?: number; rightWidth?: number; gap?: number; style?: CSSProperties }
/** Main column with optional fixed-width left/right rails ("1fr 320px"). Rails collapse themselves (see Rail). */
export function SplitPane({ children, left, right, leftWidth = 260, rightWidth = 320, gap = 12, style, ...t }: SplitPaneProps) {
  const cols = [left ? 'auto' : null, 'minmax(0, 1fr)', right ? 'auto' : null].filter(Boolean).join(' ')
  return (
    <div className="k-split" style={{ gridTemplateColumns: cols, gap, ...style, ['--k-left-w' as string]: `${leftWidth}px`, ['--k-right-w' as string]: `${rightWidth}px` }} data-testid={tid(t)}>
      {left}{children}{right}
    </div>
  )
}
export interface RailProps extends TestIdProps { children: ReactNode; title?: ReactNode; side?: 'left' | 'right'; width?: number; collapsible?: boolean; defaultCollapsed?: boolean; actions?: ReactNode; style?: CSSProperties; card?: boolean }
/** Side rail card. Collapsible rails shrink to a 36 px strip with an expand button. */
export function Rail({ children, title, side = 'right', width, collapsible, defaultCollapsed = false, actions, style, card = true, ...t }: RailProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)
  const w = width ?? `var(--k-${side}-w, 320px)`
  const toggle = collapsible && <IconButton icon={side === 'right' ? 'panel-right' : 'panel-left'} label={collapsed ? `expand ${typeof title === 'string' ? title : 'rail'}` : `collapse ${typeof title === 'string' ? title : 'rail'}`} onClick={() => setCollapsed(c => !c)} testid={tid(t) ? `${tid(t)}-toggle` : undefined} />
  if (collapsed) return <aside className={cx('k-rail collapsed', card && 'k-card')} style={style} data-testid={tid(t)}><div className="k-rail-head">{toggle}</div>{typeof title === 'string' && <span className="k-rail-collapsed-label">{title}</span>}</aside>
  return (
    <aside className={cx('k-rail', card && 'k-card')} style={{ width: w, ...style }} data-testid={tid(t)}>
      {(title || collapsible || actions) && <div className="k-rail-head">{title && <h4>{title}</h4>}<div className="acts">{actions}{toggle}</div></div>}
      <div className="k-rail-body">{children}</div>
    </aside>
  )
}

/* ================= SideNav ================= */
export interface SideNavItem { value: string; label: ReactNode; count?: ReactNode; differs?: boolean; disabled?: boolean; reason?: string; icon?: IconName }
export interface SideNavGroup { section?: ReactNode; sectionIcon?: IconName; sectionTone?: 'blue' | 'muted'; label?: ReactNode; items: SideNavItem[] }
export interface SideNavProps extends TestIdProps { groups: SideNavGroup[]; value: string; onChange: (value: string) => void; legend?: ReactNode; style?: CSSProperties; ariaLabel?: string }
/** Settings-style grouped nav: section headings, group labels, active item, trailing amber dot "differs from default". */
export function SideNav({ groups, value, onChange, legend, style, ariaLabel = 'section navigation', ...t }: SideNavProps) {
  const anyDiffers = groups.some(g => g.items.some(i => i.differs))
  return (
    <nav className="k-sidenav" style={style} aria-label={ariaLabel} data-testid={tid(t)}>
      {groups.map((g, gi) => (
        <div key={gi} style={{ display: 'contents' }}>
          {g.section && <div className={cx('k-nav-section', g.sectionTone === 'muted' && 'personal')}>{g.sectionIcon && <Icon name={g.sectionIcon} size={12} />}{g.section}</div>}
          {g.label && <div className="k-nav-group">{g.label}</div>}
          {g.items.map(it => {
            const btn = (
              <button key={it.value} type="button" className={cx('k-nav-item', it.value === value && 'on')} aria-current={it.value === value ? 'page' : undefined} aria-disabled={it.disabled || undefined}
                onClick={() => { if (!it.disabled) onChange(it.value) }} data-testid={tid(t) ? `${tid(t)}-${it.value}` : `nav-item-${it.value}`} title={it.differs ? 'differs from default' : undefined}>
                {it.icon && <Icon name={it.icon} size={14} />}<span>{it.label}</span>{it.count != null && <span className="count">{it.count}</span>}{it.differs && <span className="dot" aria-label="differs from default" />}
              </button>
            )
            return it.disabled && it.reason ? <DisabledReason key={it.value} reason={it.reason} block>{btn}</DisabledReason> : btn
          })}
        </div>
      ))}
      {(legend ?? anyDiffers) && <div className="k-nav-legend">{legend === undefined || legend === true ? <><span className="dot" />differs from default</> : legend}</div>}
    </nav>
  )
}
