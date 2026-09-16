/* Buttons and data display: Button, IconButton, Tooltip, DisabledReason, Chip, Badge, StatTile, KeyValue,
 * EmptyState, ProgressBar, CodeBlock, Callout, Stepper, Checklist, ColourDot, Kbd. */
import { cloneElement, isValidElement, useId, useRef, useState, type ButtonHTMLAttributes, type CSSProperties, type ReactElement, type ReactNode, type Ref } from 'react'
import { useToast } from '../shell/Toast'
import { useNotWired } from './notWired'
import { copyToClipboard, useAnchoredPosition, type Placement } from './hooks'
import { Icon, type IconName } from './icons'
import { cx, Portal, tid, type TestIdProps } from './portal'

export type Tone = 'blue' | 'grey' | 'green' | 'amber' | 'red' | 'purple'

/* ================= Tooltip ================= */
export interface TooltipProps { content: ReactNode; children: ReactElement; placement?: Placement; delayMs?: number; block?: boolean }
/** Dark hover/focus tooltip around one element. For disabled controls use DisabledReason (disabled elements get no hover). */
export function Tooltip({ content, children, placement = 'top', delayMs = 250, block }: TooltipProps) {
  const [open, setOpen] = useState(false)
  const anchor = useRef<HTMLSpanElement>(null)
  const tip = useRef<HTMLDivElement>(null)
  const timer = useRef(0)
  const id = useId()
  const pos = useAnchoredPosition(anchor, tip, open, placement, 6)
  const show = () => { window.clearTimeout(timer.current); timer.current = window.setTimeout(() => setOpen(true), delayMs) }
  const hide = () => { window.clearTimeout(timer.current); setOpen(false) }
  if (content == null || content === '') return children
  return (
    <span ref={anchor} style={{ display: block ? 'flex' : 'inline-flex', minWidth: 0 }} onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide} aria-describedby={open ? id : undefined}>
      {children}
      {open && <Portal><div ref={tip} id={id} role="tooltip" className="k-tooltip" style={{ top: pos?.top ?? -9999, left: pos?.left ?? -9999 }}>{content}</div></Portal>}
    </span>
  )
}

/* ================= DisabledReason ================= */
export interface DisabledReasonProps { reason: string; children: ReactElement; disabled?: boolean; block?: boolean; placement?: Placement }
/** Wrap a disabled control so its reason shows as a tooltip on hover AND keyboard focus, and as `title` on both the
 *  wrapper and the control. When `disabled` is false the child renders untouched. */
export function DisabledReason({ reason, children, disabled = true, block, placement = 'top' }: DisabledReasonProps) {
  if (!disabled) return children
  const child = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, { title: reason, 'data-disabled-reason': reason, tabIndex: -1 })
    : children
  return (
    <Tooltip content={reason} placement={placement} block={block}>
      <span className={cx('k-disabled-wrap', block && 'block')} tabIndex={0} title={reason} aria-label={`unavailable: ${reason}`} data-disabled-reason={reason}>{child}</span>
    </Tooltip>
  )
}

/* ================= Button ================= */
export type ButtonVariant = 'default' | 'primary' | 'cluster' | 'success' | 'danger' | 'danger-solid' | 'ghost' | 'subtle' | 'link'
export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'>, TestIdProps {
  variant?: ButtonVariant; size?: 'sm' | 'md' | 'lg'; icon?: IconName; iconRight?: IconName; loading?: boolean
  /** Required whenever `disabled` is true: shown as tooltip + title. */
  disabledReason?: string; block?: boolean; children?: ReactNode; ref?: Ref<HTMLButtonElement>
}
const warnedNoReason = new Set<string>()
/** The kit button (mono label, 30 px). `variant="cluster"` is the purple "Create SLURM script" button. */
export function Button({ variant = 'default', size = 'md', icon, iconRight, loading, disabledReason, block, children, className, disabled, type = 'button', ref, ...rest }: ButtonProps) {
  const isDisabled = !!disabled || !!loading
  const iconOnly = !children && !!icon
  if (import.meta.env.DEV && disabled && !disabledReason) {
    const k = String(rest['aria-label'] ?? children ?? icon)
    if (!warnedNoReason.has(k)) { warnedNoReason.add(k); console.warn(`[kit] disabled Button "${k}" has no disabledReason`) }
  }
  const { testid: _t, 'data-testid': _d, ...html } = rest
  const btn = (
    <button ref={ref} type={type} {...html} data-testid={tid(rest)} disabled={isDisabled} aria-busy={loading || undefined}
      className={cx('k-btn', variant !== 'default' && variant, size !== 'md' && size, block && 'block', iconOnly && 'icon-only', className)}>
      {loading ? <Icon name="refresh" className="k-spin" size={size === 'sm' ? 12 : 14} /> : icon && <Icon name={icon} size={size === 'sm' ? 12 : 14} />}
      {children}
      {iconRight && <Icon name={iconRight} size={size === 'sm' ? 12 : 14} />}
    </button>
  )
  return disabled && disabledReason ? <DisabledReason reason={disabledReason} block={block}>{btn}</DisabledReason> : btn
}

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'>, TestIdProps {
  icon: IconName; label: string; active?: boolean; bordered?: boolean; size?: number; disabledReason?: string
}
/** Square icon-only button; `label` is the accessible name and the hover title. */
export function IconButton({ icon, label, active, bordered, size = 14, disabledReason, className, disabled, type = 'button', ...rest }: IconButtonProps) {
  const { testid: _t, 'data-testid': _d, ...html } = rest
  const b = (
    <button type={type} {...html} data-testid={tid(rest)} aria-label={label} title={disabled ? disabledReason ?? label : label} disabled={disabled} aria-pressed={active}
      className={cx('k-icon-btn', active && 'on', bordered && 'bordered', className)}>
      <Icon name={icon} size={size} />
    </button>
  )
  return disabled && disabledReason ? <DisabledReason reason={disabledReason}>{b}</DisabledReason> : b
}

/* ================= Chip ================= */
export interface ChipProps extends TestIdProps {
  tone?: Tone | 'outline' | 'demo'; size?: 'sm' | 'md' | 'lg'; icon?: IconName; dot?: string; prefix?: ReactNode
  children?: ReactNode; onClick?: () => void; onRemove?: () => void; removeLabel?: string; selected?: boolean; title?: string; className?: string; style?: CSSProperties
}
/** Pill chip. Clickable when `onClick` is set (renders a button); removable with `onRemove` (× button). `tone="demo"` is the dashed amber chip. */
export function Chip({ tone = 'outline', size = 'md', icon, dot, prefix, children, onClick, onRemove, removeLabel, selected, title, className, style, ...t }: ChipProps) {
  const cls = cx('k-chip', tone, size !== 'md' && size, onClick && 'k-chip-btn', selected && 'selected', className)
  const inner = (
    <>
      {dot && <span className="dot" style={{ background: dot }} />}
      {icon && <Icon name={icon} size={size === 'sm' ? 11 : 12} />}
      {prefix != null && <span className="pre">{prefix}</span>}
      {children != null && <span className="txt">{children}</span>}
    </>
  )
  if (onClick && !onRemove) return <button type="button" className={cls} onClick={onClick} title={title} style={style} aria-pressed={selected} data-testid={tid(t)}>{inner}</button>
  return (
    <span className={cls} title={title} style={style} data-testid={tid(t)}>
      {onClick ? <button type="button" onClick={onClick} style={{ border: 0, background: 'transparent', padding: 0, font: 'inherit', color: 'inherit', display: 'inline-flex', gap: 6, alignItems: 'center' }}>{inner}</button> : inner}
      {onRemove && <button type="button" className="rm" onClick={e => { e.stopPropagation(); onRemove() }} aria-label={removeLabel ?? `remove ${typeof children === 'string' ? children : ''}`.trim()} title={removeLabel ?? 'remove'}><Icon name="x" size={10} strokeWidth={2.2} /></button>}
    </span>
  )
}

/* ================= Badge ================= */
export type BadgeStatus = 'cached' | 'stale' | 'new' | 'running' | 'paused' | 'failed' | 'on cluster' | 'invalid' | 'done' | 'finished' | 'queued' | 'cancelled'
  | 'waiting' | 'blocked' | 'pending' | 'blind' | 'template' | 'seed' | 'detection' | 'machine' | 'human' | 'artifact' | 'imported' | 'draft' | 'saved' | 'locked' | 'held out' | 'unsaved' | 'idle'
/** Spec §3 colour semantics: blue active/machine · green human/cached · amber attention/stale · red failed/artifact · purple cluster/second algorithm · grey inactive. */
export const STATUS_TONE: Record<BadgeStatus, Tone> = {
  cached: 'green', done: 'green', finished: 'green', human: 'green', imported: 'green', saved: 'green',
  stale: 'amber', paused: 'amber', waiting: 'amber',
  running: 'blue', template: 'blue', detection: 'blue', machine: 'blue',
  failed: 'red', invalid: 'red', artifact: 'red',
  'on cluster': 'purple', blind: 'purple', seed: 'purple',
  new: 'grey', queued: 'grey', cancelled: 'grey', blocked: 'grey', pending: 'grey', draft: 'grey', locked: 'grey', 'held out': 'grey', unsaved: 'grey', idle: 'grey',
}
export interface BadgeProps extends TestIdProps { status?: BadgeStatus; tone?: Tone | 'outline'; children?: ReactNode; dot?: boolean; size?: 'sm' | 'lg'; title?: string; icon?: IconName }
/** Small square-cornered status badge. `status` picks tone + label; `children` overrides the label; `tone` overrides the colour. */
export function Badge({ status, tone, children, dot, size = 'sm', title, icon, ...t }: BadgeProps) {
  const tn = tone ?? (status ? STATUS_TONE[status] : 'grey')
  return (
    <span className={cx('k-badge', `t-${tn}`, size === 'lg' && 'lg', status === 'running' && 'running', status && `st-${status.replace(' ', '-')}`)} title={title} data-testid={tid(t)} data-status={status}>
      {(dot ?? status === 'running') && <span className="dot" />}
      {icon && <Icon name={icon} size={11} />}
      {children ?? status}
    </span>
  )
}

/* ================= StatTile ================= */
export interface StatTileProps extends TestIdProps { label: ReactNode; value: ReactNode; caption?: ReactNode; tone?: Tone | 'muted'; variant?: 'fill' | 'flat' | 'card'; size?: 'sm' | 'md' | 'lg'; info?: ReactNode; title?: string; style?: CSSProperties }
/** Label · big value · sub-caption. `variant="flat"` is the header-row metric (models-3), `fill` the grey estimate tile (models-1). */
export function StatTile({ label, value, caption, tone, variant = 'fill', size = 'md', info, title, style, ...t }: StatTileProps) {
  return (
    <div className={cx('k-stat', variant !== 'fill' && variant, size !== 'md' && size, tone && `tone-${tone}`)} title={title} style={style} data-testid={tid(t)}>
      {/* a string `info` is the explanation itself, so show it behind an ⓘ affordance (P9) instead of
          printing it beside the label, where it silently read as part of the label (Discovery builder's
          finding). Pass an <InfoTip> element for the full pop-over; surfaces.tsx imports this module, so
          this one cannot import InfoTip back without a cycle. */}
      <div className="lbl">{label}{typeof info === 'string'
        ? <Tooltip content={info}><span className="k-stat-i" aria-label={info} tabIndex={0}>ⓘ</span></Tooltip>
        : info}</div>
      <div className="val">{value}</div>
      {caption != null && <div className="cap">{caption}</div>}
    </div>
  )
}
/** Grid of StatTiles with equal columns. */
export function StatRow({ children, columns, style }: { children: ReactNode; columns?: number; style?: CSSProperties }) {
  const n = columns ?? (Array.isArray(children) ? children.length : 1)
  return <div className="k-stats" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))`, ...style }}>{children}</div>
}

/* ================= KeyValue ================= */
export interface KVItem { k: ReactNode; v: ReactNode; tone?: Tone | 'muted'; strong?: boolean; info?: ReactNode; id?: string }
export interface KeyValueProps extends TestIdProps { items: KVItem[]; align?: 'left' | 'right'; dense?: boolean; lines?: boolean; labelWidth?: number | string; style?: CSSProperties }
/** Two-column label / value list in mono (library-2 side panel uses align="right"). */
export function KeyValue({ items, align = 'left', dense, lines, labelWidth, style, ...t }: KeyValueProps) {
  return (
    <div className={cx('k-kv', align === 'right' && 'right', dense && 'dense', lines && 'lines')} style={{ ...(labelWidth ? { gridTemplateColumns: `${typeof labelWidth === 'number' ? labelWidth + 'px' : labelWidth} minmax(0, 1fr)` } : null), ...style }} data-testid={tid(t)}>
      {items.map((it, i) => (
        <div key={it.id ?? i} style={{ display: 'contents' }}>
          <span className="k">{it.k}{it.info}</span>
          <span className={cx('v', it.tone && `tone-${it.tone}`, it.strong && 'strong')}>{it.v}</span>
        </div>
      ))}
    </div>
  )
}

/* ================= EmptyState ================= */
export interface EmptyStateProps extends TestIdProps { icon?: IconName; title: ReactNode; caption?: ReactNode; action?: ReactNode; size?: 'sm' | 'md'; bordered?: boolean; style?: CSSProperties }
/** Icon, title, one-line caption, optional action. Say what is empty and what the user can do about it. */
export function EmptyState({ icon = 'inbox', title, caption, action, size = 'md', bordered, style, ...t }: EmptyStateProps) {
  return (
    <div className={cx('k-empty', size === 'sm' && 'sm', bordered && 'bordered')} style={style} data-testid={tid(t)}>
      <div className="ic"><Icon name={icon} size={size === 'sm' ? 15 : 18} /></div>
      <div className="t">{title}</div>
      {caption && <div className="c">{caption}</div>}
      {action && <div className="a">{action}</div>}
    </div>
  )
}

/* ================= ProgressBar ================= */
export interface ProgressBarProps extends TestIdProps { value?: number; indeterminate?: boolean; label?: ReactNode; eta?: string; tone?: Tone; size?: 'sm' | 'md' | 'lg'; labelPosition?: 'right' | 'top' | 'none'; width?: number | string; ariaLabel?: string }
/** Determinate (`value` 0–1) or indeterminate bar. Default label "64 %", with `eta` "64 % · 0.2 s left". */
export function ProgressBar({ value = 0, indeterminate, label, eta, tone = 'blue', size = 'md', labelPosition = 'right', width, ariaLabel, ...t }: ProgressBarProps) {
  const v = Math.max(0, Math.min(1, value))
  const text = label ?? (indeterminate ? (eta ?? 'working…') : `${Math.round(v * 100)} %${eta ? ` · ${eta}` : ''}`)
  return (
    <div className={cx('k-progress', tone !== 'blue' && tone, size !== 'md' && size, indeterminate && 'indet', labelPosition === 'top' && 'stacked')} style={{ width }} data-testid={tid(t)}>
      {labelPosition === 'top' && <span className="lbl">{text}</span>}
      <div className="track" role="progressbar" aria-label={ariaLabel ?? (typeof text === 'string' ? text : 'progress')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={indeterminate ? undefined : Math.round(v * 100)}>
        <div className="fill" style={{ width: `${v * 100}%` }} />
      </div>
      {labelPosition === 'right' && <span className="lbl">{text}</span>}
    </div>
  )
}

/* ================= CodeBlock ================= */
export interface CodeBlockProps extends TestIdProps { code: string; title?: ReactNode; filename?: string; lineNumbers?: boolean; highlight?: number[]; copy?: boolean; save?: boolean; onSave?: () => void; maxHeight?: number | string; style?: CSSProperties }
function colourLine(line: string): ReactNode {
  if (/^\s*#/.test(line)) return <span className={line.startsWith('#!') ? 'sh' : 'cm'}>{line}</span>
  const parts = line.split(/("[^"]*"|'[^']*')/g)
  return parts.map((p, i) => (i % 2 ? <span key={i} className="st">{p}</span> : p))
}
/** Dark code block with Copy (clipboard + toast) and Save (not wired → toast, unless `onSave`). `highlight` is 1-based line numbers. */
export function CodeBlock({ code, title, filename = 'script.sh', lineNumbers, highlight = [], copy = true, save = true, onSave, maxHeight, style, ...t }: CodeBlockProps) {
  const { push } = useToast()
  const notWired = useNotWired()
  const lines = code.replace(/\n$/, '').split('\n')
  const ext = filename.includes('.') ? filename.slice(filename.lastIndexOf('.')) : ''
  const doCopy = async () => {
    const ok = await copyToClipboard(code)
    push(ok ? { text: `copied ${lines.length} line${lines.length === 1 ? '' : 's'} to the clipboard` } : { text: 'the browser refused clipboard access', kind: 'error' })
  }
  return (
    <div style={style} data-testid={tid(t)}>
      {title && <div className="k-code-head"><h4>{title}</h4></div>}
      <div className="k-code" style={{ maxHeight }} tabIndex={0} aria-label={typeof title === 'string' ? title : 'code'}>
        <pre>{lines.map((l, i) => (
          <div key={i} className={cx('ln', highlight.includes(i + 1) && 'hl')}>
            {lineNumbers && <span className="no">{i + 1}</span>}
            <span>{colourLine(l) || ' '}</span>
          </div>
        ))}</pre>
      </div>
      {(copy || save) && (
        <div className="k-code-acts">
          {copy && <Button icon="copy" onClick={doCopy} testid={tid(t) ? `${tid(t)}-copy` : undefined}>Copy</Button>}
          {save && <Button icon="download" onClick={() => (onSave ? onSave() : notWired(`save ${filename} to disk`))} testid={tid(t) ? `${tid(t)}-save` : undefined}>Save {ext || filename}</Button>}
        </div>
      )}
    </div>
  )
}

/* ================= Callout ================= */
const CALLOUT_ICON: Record<Tone | 'grey', IconName> = { amber: 'alert-triangle', red: 'alert-circle', blue: 'info', green: 'check-circle', grey: 'info', purple: 'server' }
export interface CalloutProps extends TestIdProps { tone?: Tone; icon?: IconName | null; title?: ReactNode; children?: ReactNode; action?: ReactNode; outlined?: boolean; stacked?: boolean; style?: CSSProperties }
/** Tinted strip with icon (amber warning strip "over the 2 h local limit · Train locally is off"). `stacked` puts the action under the text. */
export function Callout({ tone = 'amber', icon, title, children, action, outlined, stacked, style, ...t }: CalloutProps) {
  const ic = icon === null ? null : icon ?? CALLOUT_ICON[tone]
  return (
    <div className={cx('k-callout', tone, outlined && 'outlined', stacked && 'stacked')} role={tone === 'red' ? 'alert' : 'status'} style={style} data-testid={tid(t)}>
      {stacked ? (
        <>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>{ic && <Icon name={ic} className="ic" />}<div className="body">{title && <div className="t">{title}</div>}{children && <div className={title ? 'd' : undefined}>{children}</div>}</div></div>
          {action && <div className="act">{action}</div>}
        </>
      ) : (
        <>
          {ic && <Icon name={ic} className="ic" />}
          <div className="body">{title && <div className="t">{title}</div>}{children && <div className={title ? 'd' : undefined}>{children}</div>}</div>
          {action && <div className="act">{action}</div>}
        </>
      )}
    </div>
  )
}

/* ================= Stepper ================= */
export type StepState = 'done' | 'current' | 'running' | 'todo' | 'failed' | 'paused'
export interface StepItem { label: ReactNode; detail?: ReactNode; state: StepState; id?: string }
export interface StepperProps extends TestIdProps { steps: StepItem[]; variant?: 'pills' | 'numbered'; orientation?: 'horizontal' | 'vertical'; onSelect?: (index: number) => void; current?: number }
const STEP_ICON: Record<StepState, IconName> = { done: 'check-circle', current: 'hourglass', running: 'refresh', todo: 'circle-dashed', failed: 'x-circle', paused: 'pause' }
/** Steps with done / current / todo state. `pills` (jobs-1 stage list) or `numbered` (wizard circles joined by lines). */
export function Stepper({ steps, variant = 'pills', orientation = variant === 'pills' ? 'vertical' : 'horizontal', onSelect, ...t }: StepperProps) {
  return (
    <ol className={cx('k-stepper', orientation, variant === 'numbered' && 'numbered')} style={{ listStyle: 'none', margin: 0, padding: 0 }} data-testid={tid(t)}>
      {steps.map((s, i) => {
        const st = s.state === 'paused' ? 'current' : s.state
        const content = variant === 'numbered'
          ? <><span className="circ">{s.state === 'done' ? <Icon name="check" size={12} strokeWidth={2.4} /> : s.state === 'failed' ? <Icon name="x" size={11} strokeWidth={2.4} /> : i + 1}</span><span>{s.label}</span>{s.detail && <span className="d">{s.detail}</span>}</>
          : <><Icon name={STEP_ICON[s.state]} size={13} className={s.state === 'running' ? 'k-spin' : undefined} /><span className="n">{i + 1}</span><span>{s.label}</span>{s.detail && <span className="d">· {s.detail}</span>}</>
        return (
          <li key={s.id ?? i} style={{ display: 'contents' }}>
            {variant === 'numbered' && i > 0 && orientation === 'horizontal' && <span className={cx('line', steps[i - 1].state === 'done' && 'done')} aria-hidden />}
            {onSelect
              ? <button type="button" className={cx('k-step', st, 'k-step-btn')} onClick={() => onSelect(i)} aria-current={s.state === 'current' || s.state === 'running' ? 'step' : undefined} data-state={s.state}>{content}</button>
              : <span className={cx('k-step', st)} aria-current={s.state === 'current' || s.state === 'running' ? 'step' : undefined} data-state={s.state}>{content}</span>}
          </li>
        )
      })}
    </ol>
  )
}

/* ================= Checklist ================= */
export type CheckState = 'pass' | 'warn' | 'fail' | 'pending'
const CHECK_ICON: Record<CheckState, IconName> = { pass: 'check-circle', warn: 'alert-triangle', fail: 'x-circle', pending: 'circle-dashed' }
export interface ChecklistProps extends TestIdProps { items: { label: ReactNode; state: CheckState; id?: string }[]; columns?: 1 | 2 }
/** Pass / warn / fail / pending list ("Before launch", "Held-out checks"). */
export function Checklist({ items, columns = 1, ...t }: ChecklistProps) {
  return (
    <ul className={cx('k-checklist', columns === 2 && 'cols2')} data-testid={tid(t)}>
      {items.map((it, i) => <li key={it.id ?? i} className={it.state} data-state={it.state}><Icon name={CHECK_ICON[it.state]} size={14} title={it.state} /><span>{it.label}</span></li>)}
    </ul>
  )
}

/* ================= ColourDot / Kbd ================= */
export function ColourDot({ colour, size = 8, ring, title, style }: { colour: string; size?: number; ring?: boolean; title?: string; style?: CSSProperties }) {
  return <span className={cx('k-dot', ring && 'ring')} style={{ width: size, height: size, background: colour, color: colour, ...style }} title={title} aria-hidden={title ? undefined : true} role={title ? 'img' : undefined} aria-label={title} />
}
export function Kbd({ children, size = 'md', dark }: { children: ReactNode; size?: 'sm' | 'md'; dark?: boolean }) {
  return <kbd className={cx('k-kbd', size === 'sm' && 'sm', dark && 'dark')}>{children}</kbd>
}
