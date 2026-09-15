/* Floating surfaces: Popover, Modal, Drawer, Menu, Dropdown, InfoTip.
 * Escape and outside-click go to the topmost surface only (hooks.useLayer). Modal uses shell/useDismiss for its
 * focus trap; Popover needs the trigger excluded from "outside", so it uses hooks.useSurfaceDismiss. */
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactElement, type ReactNode, type RefObject } from 'react'
import { useDismiss } from '../shell/useDismiss'
import { Button, IconButton } from './display'
import { useAnchoredPosition, useLayer, useSurfaceDismiss, type Placement } from './hooks'
import { Icon, type IconName } from './icons'
import { cx, Portal, PortalHostContext, tid, type TestIdProps } from './portal'
import { Tabs, type TabItem } from './nav'

/* ================= Popover ================= */
export interface PopoverProps extends TestIdProps {
  open: boolean; onClose: () => void
  /** The element the popover is anchored to (usually the trigger button). */
  anchorRef: RefObject<HTMLElement | null>
  children: ReactNode; placement?: Placement; title?: ReactNode; subtitle?: ReactNode
  width?: number | string; flush?: boolean; className?: string; style?: CSSProperties
  /** Return focus to the anchor on close (default true). */
  returnFocus?: boolean; role?: 'dialog' | 'menu' | 'listbox'; ariaLabel?: string
}
/** Anchored, flipping popover in a portal. Closes on Escape, outside click, or the trigger toggling `open`. */
export function Popover({ open, onClose, anchorRef, children, placement = 'bottom-start', title, subtitle, width, flush, className, style, returnFocus = true, role = 'dialog', ariaLabel, ...t }: PopoverProps) {
  const ref = useRef<HTMLDivElement>(null)
  const pos = useAnchoredPosition(anchorRef, ref, open, placement)
  const close = useCallback((reason: 'escape' | 'outside') => {
    onClose()
    if (returnFocus && reason === 'escape') anchorRef.current?.focus()
  }, [onClose, returnFocus, anchorRef])
  useSurfaceDismiss([ref, anchorRef], close, open)
  useEffect(() => {
    if (!open || role !== 'dialog') return
    const id = window.setTimeout(() => {
      const el = ref.current?.querySelector<HTMLElement>('[autofocus], input:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])')
      el?.focus({ preventScroll: true })
    }, 0)
    return () => window.clearTimeout(id)
  }, [open, role])
  if (!open) return null
  return (
    <Portal>
      <div ref={ref} role={role} aria-label={ariaLabel ?? (typeof title === 'string' ? title : undefined)} className={cx('k-popover', flush && 'flush', className)} data-testid={tid(t)}
        style={{ top: pos?.top ?? -9999, left: pos?.left ?? -9999, width, visibility: pos ? 'visible' : 'hidden', ...style }}>
        {title && <div className="k-popover-title">{title}{subtitle && <span className="sub">{subtitle}</span>}</div>}
        {children}
      </div>
    </Portal>
  )
}

/** Trigger + popover in one: `<PopoverButton label="History" icon="clock">{close => …}</PopoverButton>`. */
export function PopoverButton({ label, icon, variant, size, children, placement, title, width, testid, disabled, disabledReason }: {
  label: ReactNode; icon?: IconName; variant?: 'default' | 'primary' | 'ghost' | 'subtle' | 'link'; size?: 'sm' | 'md'
  children: (close: () => void) => ReactNode; placement?: Placement; title?: ReactNode; width?: number | string; testid?: string; disabled?: boolean; disabledReason?: string
}) {
  const [open, setOpen] = useState(false)
  const anchor = useRef<HTMLButtonElement>(null)
  const close = useCallback(() => setOpen(false), [])
  return (
    <>
      <Button ref={anchor} variant={variant} size={size} icon={icon} iconRight="chevron-down" disabled={disabled} disabledReason={disabledReason}
        aria-expanded={open} aria-haspopup="dialog" onClick={() => setOpen(o => !o)} testid={testid}>{label}</Button>
      <Popover open={open} onClose={close} anchorRef={anchor} placement={placement} title={title} width={width} testid={testid ? `${testid}-popover` : undefined}>{children(close)}</Popover>
    </>
  )
}

/* ================= InfoTip ================= */
export interface InfoTipProps extends TestIdProps { children: ReactNode; title?: ReactNode; label?: string; placement?: Placement; size?: number }
/** ⓘ icon that opens a small explanatory popover (spec P9: explanations live behind info icons). */
export function InfoTip({ children, title, label = 'more information', placement = 'bottom-start', size = 13, ...t }: InfoTipProps) {
  const [open, setOpen] = useState(false)
  const anchor = useRef<HTMLButtonElement>(null)
  return (
    <>
      <button ref={anchor} type="button" className="k-info" aria-label={typeof title === 'string' ? `about ${title}` : label} aria-expanded={open} title={typeof title === 'string' ? title : label}
        onClick={e => { e.stopPropagation(); setOpen(o => !o) }} data-testid={tid(t)}>
        <Icon name="info" size={size} />
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchor} placement={placement} className="info" testid={tid(t) ? `${tid(t)}-popover` : undefined}>
        {title && <div className="t">{title}</div>}
        <div>{children}</div>
      </Popover>
    </>
  )
}

/* ================= Modal ================= */
export interface ModalProps extends TestIdProps {
  open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode
  footer?: ReactNode; footerNote?: ReactNode; size?: 'sm' | 'md' | 'lg' | 'xl'; headerExtra?: ReactNode
  flushBody?: boolean; closeOnBackdrop?: boolean; width?: number | string; bodyStyle?: CSSProperties
}
/** role=dialog aria-modal; focus trap + Escape via shell/useDismiss; backdrop click closes; focus returns to the opener. */
export function Modal(p: ModalProps) { return p.open ? <ModalInner {...p} /> : null }
function ModalInner({ onClose, title, subtitle, children, footer, footerNote, size = 'md', headerExtra, flushBody, closeOnBackdrop = true, width, bodyStyle, ...t }: ModalProps) {
  const backdrop = useRef<HTMLDivElement>(null)
  const dialog = useRef<HTMLDivElement>(null)
  const [host, setHost] = useState<HTMLElement | null>(null)
  const titleId = useId()
  useLayer(true)
  useDismiss(backdrop, onClose)
  useLayoutEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    setHost(dialog.current)
    const first = dialog.current?.querySelector<HTMLElement>('[autofocus], .k-modal-body input:not([disabled]), .k-modal-body select:not([disabled]), .k-modal-body textarea:not([disabled])')
    ;(first ?? dialog.current)?.focus({ preventScroll: true })
    return () => { if (opener && document.contains(opener)) opener.focus({ preventScroll: true }) }
  }, [])
  return (
    <Portal>
      <div className="k-modal-backdrop" ref={backdrop} onMouseDown={e => { if (closeOnBackdrop && e.target === e.currentTarget) onClose() }}>
        <div ref={dialog} className={cx('k-modal', !width && size)} style={width ? { width } : undefined} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} data-testid={tid(t)}>
          <PortalHostContext.Provider value={host}>
            <div className="k-modal-head">
              <h2 id={titleId}>{title}</h2>
              {subtitle && <span className="sub">{subtitle}</span>}
              {headerExtra}
              <IconButton icon="x" label="close (Esc)" className="x" onClick={onClose} testid={tid(t) ? `${tid(t)}-close` : undefined} />
            </div>
            <div className={cx('k-modal-body', flushBody && 'flush')} style={bodyStyle}>{children}</div>
            {(footer || footerNote) && <div className="k-modal-foot">{footerNote && <span className="note">{footerNote}</span>}{!footerNote && <span style={{ marginRight: 'auto' }} />}{footer}</div>}
          </PortalHostContext.Provider>
        </div>
      </div>
    </Portal>
  )
}

/* ================= Drawer ================= */
export interface DrawerProps extends TestIdProps {
  open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode
  side?: 'right' | 'bottom'; mode?: 'overlay' | 'inline'; width?: number | string; height?: number | string
  tabs?: TabItem[]; tab?: string; onTab?: (v: string) => void; actions?: ReactNode; bodyStyle?: CSSProperties
}
/** Right or bottom drawer with optional tabs. `mode="overlay"` floats (Escape closes, focus returns); `inline` renders in flow as a card (explore-2b). */
export function Drawer(p: DrawerProps) { return p.open ? <DrawerInner {...p} /> : null }
function DrawerInner({ onClose, title, subtitle, children, side = 'right', mode = 'overlay', width = 420, height = 360, tabs, tab, onTab, actions, bodyStyle, ...t }: DrawerProps) {
  const ref = useRef<HTMLDivElement>(null)
  const overlay = mode === 'overlay'
  useSurfaceDismiss([ref], reason => { if (reason === 'escape') onClose() }, true, { outside: false })
  useLayoutEffect(() => {
    if (!overlay) return
    const opener = document.activeElement as HTMLElement | null
    ref.current?.focus({ preventScroll: true })
    return () => { if (opener && document.contains(opener)) opener.focus({ preventScroll: true }) }
  }, [overlay])
  const body = (
    <div ref={ref} className={cx('k-drawer', overlay ? side : 'inline')} role={overlay ? 'dialog' : 'region'} aria-label={typeof title === 'string' ? title : 'drawer'} tabIndex={-1}
      style={overlay ? (side === 'right' ? { width } : { height }) : undefined} data-testid={tid(t)}>
      <div className="k-drawer-head">
        {tabs ? <Tabs items={tabs} value={tab ?? tabs[0]?.value} onChange={v => onTab?.(v)} variant="soft" ariaLabel={typeof title === 'string' ? title : 'drawer tabs'} /> : <h3>{title}</h3>}
        {subtitle && <span className="sub">{subtitle}</span>}
        <div className="acts">{actions}<IconButton icon={side === 'bottom' || !overlay ? 'chevron-down' : 'x'} label={overlay ? 'close (Esc)' : 'collapse'} onClick={onClose} testid={tid(t) ? `${tid(t)}-close` : undefined} /></div>
      </div>
      <div className="k-drawer-body" style={bodyStyle}>{children}</div>
    </div>
  )
  return overlay ? <Portal>{body}</Portal> : body
}

/* ================= Menu / Dropdown ================= */
export interface MenuItem<V extends string = string> {
  value: V; label: ReactNode; description?: ReactNode; hint?: ReactNode; icon?: IconName
  disabled?: boolean; reason?: string; danger?: boolean; group?: string
}
function ListBody<V extends string>({ items, selected, onPick, role, activeIndex, setActive, listId }: {
  items: MenuItem<V>[]; selected?: V | null; onPick: (it: MenuItem<V>) => void; role: 'menu' | 'listbox'; activeIndex: number; setActive: (i: number) => void; listId: string
}) {
  let lastGroup: string | undefined
  return (
    <div className="k-menu" role={role} id={listId}>
      {items.map((it, i) => {
        const header = it.group && it.group !== lastGroup ? <div className="k-menu-group" key={`g-${it.group}`}>{it.group}</div> : null
        lastGroup = it.group
        const isSel = selected != null && it.value === selected
        return (
          <div key={it.value} style={{ display: 'contents' }}>
            {header}
            <button type="button" id={`${listId}-${i}`} role={role === 'menu' ? 'menuitem' : 'option'} aria-selected={role === 'listbox' ? isSel : undefined}
              aria-disabled={it.disabled || undefined} title={it.disabled ? it.reason : undefined} tabIndex={i === activeIndex ? 0 : -1}
              className={cx('k-menu-item', i === activeIndex && 'active', it.danger && 'danger')} data-value={it.value}
              onMouseEnter={() => setActive(i)} onClick={() => { if (!it.disabled) onPick(it) }}>
              {role === 'listbox' && <span className="check">{isSel && <Icon name="check" size={13} strokeWidth={2.2} />}</span>}
              {it.icon && <Icon name={it.icon} size={13} />}
              <span className="body"><span>{it.label}</span>{it.description && <span className="desc">{it.description}</span>}{it.disabled && it.reason && <span className="reason">⊘ {it.reason}</span>}</span>
              {it.hint && <span className="hint">{it.hint}</span>}
            </button>
          </div>
        )
      })}
    </div>
  )
}
function useListKeys<V extends string>(items: MenuItem<V>[], open: boolean, initial: number, onPick: (it: MenuItem<V>) => void, listRef: RefObject<HTMLDivElement | null>) {
  const [active, setActive] = useState(initial)
  useEffect(() => { if (open) setActive(initial) }, [open, initial])
  useEffect(() => {
    if (!open) return
    // the popover is visibility:hidden until positioned, so focus on the next frame
    const id = requestAnimationFrame(() => requestAnimationFrame(() => {
      const btns = listRef.current?.querySelectorAll<HTMLElement>('.k-menu-item')
      btns?.[active]?.focus({ preventScroll: true })
    }))
    return () => cancelAnimationFrame(id)
  }, [open, active, listRef])
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!items.length) return
    const move = (d: number) => { let i = active; for (let k = 0; k < items.length; k++) { i = (i + d + items.length) % items.length; if (!items[i].disabled) break } setActive(i) }
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1) }
    else if (e.key === 'Home') { e.preventDefault(); setActive(0) }
    else if (e.key === 'End') { e.preventDefault(); setActive(items.length - 1) }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); const it = items[active]; if (it && !it.disabled) onPick(it) }
  }
  return { active, setActive, onKeyDown }
}

export interface MenuProps<V extends string = string> extends TestIdProps {
  /** Render the trigger; spread `props` onto a button. */
  trigger: (props: { ref: RefObject<HTMLButtonElement | null>; onClick: () => void; 'aria-expanded': boolean; 'aria-haspopup': 'menu' }) => ReactElement
  items: MenuItem<V>[]; onSelect: (value: V) => void; placement?: Placement; width?: number | string
}
/** Action menu: any trigger opens a list; disabled items show their reason. Arrow keys, Enter, Escape. */
export function Menu<V extends string = string>({ trigger, items, onSelect, placement = 'bottom-start', width, ...t }: MenuProps<V>) {
  const [open, setOpen] = useState(false)
  const anchor = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLDivElement>(null)
  const listId = useId()
  const pick = (it: MenuItem<V>) => { setOpen(false); anchor.current?.focus(); onSelect(it.value) }
  const keys = useListKeys(items, open, Math.max(0, items.findIndex(i => !i.disabled)), pick, list)
  return (
    <>
      {trigger({ ref: anchor, onClick: () => setOpen(o => !o), 'aria-expanded': open, 'aria-haspopup': 'menu' })}
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchor} placement={placement} flush width={width} role="menu" testid={tid(t)}>
        <div ref={list} onKeyDown={keys.onKeyDown}><ListBody items={items} onPick={pick} role="menu" activeIndex={keys.active} setActive={keys.setActive} listId={listId} /></div>
      </Popover>
    </>
  )
}

export interface DropdownProps<V extends string = string> extends TestIdProps {
  value: V | null; onChange: (value: V) => void; options: MenuItem<V>[]
  prefix?: ReactNode; placeholder?: string; variant?: 'grey' | 'outline'; active?: boolean; size?: 'sm' | 'md'
  block?: boolean; width?: number | string; menuWidth?: number | string; disabled?: boolean; disabledReason?: string; ariaLabel?: string; placement?: Placement
}
/** Select-like button ("test 20 % ⌄") that opens a listbox. `active` tints it blue (a filter that is set). */
export function Dropdown<V extends string = string>({ value, onChange, options, prefix, placeholder = 'choose', variant = 'grey', active, size = 'md', block, width, menuWidth, disabled, disabledReason, ariaLabel, placement = 'bottom-start', ...t }: DropdownProps<V>) {
  const [open, setOpen] = useState(false)
  const anchor = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLDivElement>(null)
  const listId = useId()
  const sel = options.find(o => o.value === value)
  const pick = (it: MenuItem<V>) => { setOpen(false); anchor.current?.focus(); onChange(it.value) }
  const keys = useListKeys(options, open, Math.max(0, options.findIndex(o => o.value === value)), pick, list)
  const trigger = (
    <button ref={anchor} type="button" className={cx('k-dd-trigger', variant === 'outline' && 'outline', active && 'active', block && 'block', size === 'sm' && 'sm')} style={{ width }}
      aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? listId : undefined} aria-label={ariaLabel ?? (typeof prefix === 'string' ? prefix : undefined)}
      disabled={disabled} title={disabled ? disabledReason : undefined} data-testid={tid(t)} data-value={value ?? ''}
      onClick={() => setOpen(o => !o)} onKeyDown={e => {
        if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) { e.preventDefault(); setOpen(true) }
        else if (open && ['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(e.key)) keys.onKeyDown(e)
      }}>
      {prefix != null && <span className="pre">{prefix}</span>}
      <span className={cx('val', !sel && 'placeholder')}>{sel ? sel.label : placeholder}</span>
      <Icon name="chevron-down" size={12} className="chev" />
    </button>
  )
  return (
    <>
      {disabled && disabledReason ? <span className="k-disabled-wrap" tabIndex={0} title={disabledReason}>{trigger}</span> : trigger}
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchor} placement={placement} flush width={menuWidth} role="listbox" testid={tid(t) ? `${tid(t)}-menu` : undefined}>
        <div ref={list} onKeyDown={keys.onKeyDown}><ListBody items={options} selected={value} onPick={pick} role="listbox" activeIndex={keys.active} setActive={keys.setActive} listId={listId} /></div>
      </Popover>
    </>
  )
}
