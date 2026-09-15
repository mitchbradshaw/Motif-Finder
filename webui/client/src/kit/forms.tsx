/* Forms: Field, TextField, NumberField, SelectField, Toggle, Checkbox, Slider, RangeSlider, RadioCards. */
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { DisabledReason } from './display'
import { Icon, type IconName } from './icons'
import { cx, tid, type TestIdProps } from './portal'
import { InfoTip } from './surfaces'

/* ================= Field ================= */
export interface FieldProps { label?: ReactNode; hint?: ReactNode; error?: ReactNode; info?: ReactNode; required?: boolean; aside?: ReactNode; inline?: boolean; labelWidth?: number; htmlFor?: string; children: ReactNode; style?: CSSProperties; testid?: string }
/** Label + control + hint + error slot. `inline` = settings row (label | control | hint on the right). */
export function Field({ label, hint, error, info, required, aside, inline, labelWidth, htmlFor, children, style, testid }: FieldProps) {
  return (
    <div className={cx('k-field', inline && 'inline')} style={{ ...(labelWidth ? { ['--k-label-w' as string]: `${labelWidth}px` } : null), ...style }} data-testid={testid}>
      {label != null && <label className="k-field-label" htmlFor={htmlFor}>{label}{required && <span className="req">*</span>}{info && <InfoTip title={typeof label === 'string' ? label : undefined}>{info}</InfoTip>}{aside != null && <span className="aside">{aside}</span>}</label>}
      {inline ? <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>{children}</div> : children}
      {inline ? <span className="k-field-hint">{hint}</span> : hint && !error && <span className="k-field-hint">{hint}</span>}
      {error && <span className="k-field-error" role="alert"><Icon name="alert-circle" size={11} />{error}</span>}
    </div>
  )
}

/* ================= TextField ================= */
export interface TextFieldProps extends TestIdProps {
  value: string; onChange: (v: string) => void; placeholder?: string; prefix?: ReactNode; suffix?: ReactNode; icon?: IconName
  width?: number | string; block?: boolean; disabled?: boolean; disabledReason?: string; invalid?: boolean; variant?: 'grey' | 'outline'; size?: 'sm' | 'md'
  multiline?: boolean; rows?: number; id?: string; ariaLabel?: string; onEnter?: () => void; autoFocus?: boolean
}
export function TextField({ value, onChange, placeholder, prefix, suffix, icon, width, block, disabled, disabledReason, invalid, variant = 'grey', size = 'md', multiline, rows = 3, id, ariaLabel, onEnter, autoFocus, ...t }: TextFieldProps) {
  const el = (
    <span className={cx('k-input', variant === 'outline' && 'outline', invalid && 'invalid', disabled && 'disabled', size === 'sm' && 'sm', block && 'block', multiline && 'area')} style={{ width }}>
      {icon && <Icon name={icon} size={13} />}{prefix != null && <span className="pre">{prefix}</span>}
      {multiline
        ? <textarea id={id} value={value} rows={rows} placeholder={placeholder} disabled={disabled} aria-label={ariaLabel ?? placeholder} aria-invalid={invalid || undefined} onChange={e => onChange(e.target.value)} data-testid={tid(t)} autoFocus={autoFocus} />
        : <input id={id} type="text" value={value} placeholder={placeholder} disabled={disabled} aria-label={ariaLabel ?? placeholder} aria-invalid={invalid || undefined} onChange={e => onChange(e.target.value)} data-testid={tid(t)} autoFocus={autoFocus}
          onKeyDown={e => { if (e.key === 'Enter' && onEnter) onEnter() }} />}
      {suffix != null && <span className="suf">{suffix}</span>}
    </span>
  )
  return disabled && disabledReason ? <DisabledReason reason={disabledReason} block={block}>{el}</DisabledReason> : el
}

/* ================= NumberField ================= */
export interface NumberFieldProps extends TestIdProps {
  value: number | null; onValid: (n: number) => void
  /** Every keystroke: the raw text and the validation reason (null when valid). */
  onChange?: (raw: string, reason: string | null) => void
  min?: number; max?: number; step?: number; integer?: boolean; unit?: ReactNode; width?: number | string
  disabled?: boolean; disabledReason?: string; variant?: 'grey' | 'outline'; size?: 'sm' | 'md'; id?: string; ariaLabel?: string
  /** Extra rule: return a reason string to reject. */
  validate?: (n: number) => string | null; showError?: boolean; changed?: boolean
}
export function validateNumber(raw: string, o: { min?: number; max?: number; integer?: boolean; validate?: (n: number) => string | null }): string | null {
  const s = raw.trim().replace('−', '-')
  if (s === '') return 'a value is required'
  if (!/^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(s)) return 'not a number'
  const n = Number(s)
  if (o.integer && !Number.isInteger(n)) return 'must be a whole number'
  if (o.min != null && n < o.min) return `must be ≥ ${o.min}`
  if (o.max != null && n > o.max) return `must be ≤ ${o.max}`
  return o.validate?.(n) ?? null
}
/** Numeric input that validates as you type, shows the reason inline in red, and calls `onValid` only with valid numbers. ↑/↓ step. */
export function NumberField({ value, onValid, onChange, min, max, step = 1, integer, unit, width = 110, disabled, disabledReason, variant = 'grey', size = 'md', id, ariaLabel, validate, showError = true, changed, ...t }: NumberFieldProps) {
  const [raw, setRaw] = useState(value == null ? '' : String(value))
  const [reason, setReason] = useState<string | null>(null)
  const focused = useRef(false)
  useEffect(() => { if (!focused.current) { setRaw(value == null ? '' : String(value)); setReason(null) } }, [value])
  const errId = useId()
  const accept = (s: string) => {
    setRaw(s)
    const r = validateNumber(s, { min, max, integer, validate })
    setReason(r); onChange?.(s, r)
    if (!r) onValid(Number(s.trim().replace('−', '-')))
  }
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return
    e.preventDefault()
    const cur = Number(raw); const base = Number.isFinite(cur) ? cur : (min ?? 0)
    let n = base + (e.key === 'ArrowUp' ? step : -step) * (e.shiftKey ? 10 : 1)
    if (min != null) n = Math.max(min, n); if (max != null) n = Math.min(max, n)
    accept(String(+n.toFixed(10)))
  }
  const el = (
    <span style={{ display: 'inline-flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
      <span className={cx('k-input', variant === 'outline' && 'outline', reason && 'invalid', !reason && changed && 'changed', disabled && 'disabled', size === 'sm' && 'sm')} style={{ width }}>
        <input id={id} type="text" inputMode="decimal" value={raw} disabled={disabled} aria-label={ariaLabel} aria-invalid={!!reason || undefined} aria-describedby={reason ? errId : undefined}
          onFocus={() => { focused.current = true }} onBlur={() => { focused.current = false }} onChange={e => accept(e.target.value)} onKeyDown={onKey} data-testid={tid(t)} />
        {unit != null && <span className="suf">{unit}</span>}
      </span>
      {showError && reason && <span id={errId} className="k-field-error" role="alert" data-testid={tid(t) ? `${tid(t)}-error` : undefined}><Icon name="alert-circle" size={11} />{reason}</span>}
    </span>
  )
  return disabled && disabledReason ? <DisabledReason reason={disabledReason}>{el}</DisabledReason> : el
}

/* ================= SelectField ================= */
export interface SelectOption { value: string; label: string; disabled?: boolean; reason?: string }
export interface SelectFieldProps extends TestIdProps { value: string; onChange: (v: string) => void; options: SelectOption[]; width?: number | string; variant?: 'grey' | 'outline'; size?: 'sm' | 'md'; disabled?: boolean; disabledReason?: string; invalid?: boolean; id?: string; ariaLabel?: string }
/** Native select in kit styling (form contexts). Disabled options append their reason to the label. For a richer list use Dropdown. */
export function SelectField({ value, onChange, options, width, variant = 'grey', size = 'md', disabled, disabledReason, invalid, id, ariaLabel, ...t }: SelectFieldProps) {
  const el = (
    <select id={id} className={cx('k-select', variant === 'outline' && 'outline', size === 'sm' && 'sm', invalid && 'invalid')} style={{ width }} value={value} disabled={disabled} aria-label={ariaLabel} onChange={e => onChange(e.target.value)} data-testid={tid(t)}>
      {options.map(o => <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}{o.disabled && o.reason ? ` — ${o.reason}` : ''}</option>)}
    </select>
  )
  return disabled && disabledReason ? <DisabledReason reason={disabledReason}>{el}</DisabledReason> : el
}

/* ================= Toggle ================= */
export interface ToggleProps extends TestIdProps { checked: boolean; onChange: (v: boolean) => void; label?: ReactNode; disabled?: boolean; disabledReason?: string; tone?: 'green' | 'blue'; size?: 'sm' | 'md'; ariaLabel?: string }
/** role=switch, green when on. */
export function Toggle({ checked, onChange, label, disabled, disabledReason, tone = 'green', size = 'md', ariaLabel, ...t }: ToggleProps) {
  const el = (
    <button type="button" role="switch" aria-checked={checked} className={cx('k-toggle', tone === 'blue' && 'blue', size === 'sm' && 'sm')} disabled={disabled} aria-label={ariaLabel ?? (typeof label === 'string' ? label : undefined)}
      onClick={() => onChange(!checked)} data-testid={tid(t)}>
      <span className="knob" />{label != null && <span>{label}</span>}
    </button>
  )
  return disabled && disabledReason ? <DisabledReason reason={disabledReason}>{el}</DisabledReason> : el
}

/* ================= Checkbox ================= */
export interface CheckboxProps extends TestIdProps { checked: boolean; onChange: (v: boolean) => void; label?: ReactNode; dot?: string; count?: ReactNode; indeterminate?: boolean; disabled?: boolean; disabledReason?: string; dimWhenOff?: boolean; ariaLabel?: string; style?: CSSProperties }
/** Blue square checkbox with optional colour dot and trailing count (rail filter lists). */
export function Checkbox({ checked, onChange, label, dot, count, indeterminate, disabled, disabledReason, dimWhenOff, ariaLabel, style, ...t }: CheckboxProps) {
  const el = (
    <label className={cx('k-check', disabled && 'disabled', dimWhenOff && !checked && 'off')} style={style} title={disabled ? disabledReason : undefined}>
      <input type="checkbox" checked={checked} disabled={disabled} ref={r => { if (r) r.indeterminate = !!indeterminate }} onChange={e => onChange(e.target.checked)} aria-label={ariaLabel} data-testid={tid(t)} />
      {dot && <span className="dot" style={{ background: dot }} />}
      {label != null && <span className="lbl">{label}</span>}
      {count != null && <span className="cnt">{count}</span>}
    </label>
  )
  return disabled && disabledReason ? <DisabledReason reason={disabledReason} block>{el}</DisabledReason> : el
}

/* ================= Slider / RangeSlider ================= */
export interface SliderMark { value: number; label: ReactNode }
export interface SliderProps extends TestIdProps { value: number; onChange: (v: number) => void; min: number; max: number; step?: number; marks?: SliderMark[]; format?: (v: number) => ReactNode; disabled?: boolean; disabledReason?: string; width?: number | string; ariaLabel?: string; showValue?: boolean }
const pct = (v: number, min: number, max: number) => `${((v - min) / (max - min || 1)) * 100}%`
function Marks({ marks, min, max }: { marks?: SliderMark[]; min: number; max: number }) {
  if (!marks?.length) return null
  return <div className="marks" aria-hidden>{marks.map(m => <span key={m.value} style={{ left: pct(m.value, min, max) }}>{m.label}</span>)}</div>
}
export function Slider({ value, onChange, min, max, step = 1, marks, format = v => String(v), disabled, disabledReason, width, ariaLabel, showValue = true, ...t }: SliderProps) {
  const el = (
    <div className="k-slider" style={{ width }}>
      <div className="row1">
        <div className="track-wrap">
          <input type="range" min={min} max={max} step={step} value={value} disabled={disabled} aria-label={ariaLabel} onChange={e => onChange(Number(e.target.value))} data-testid={tid(t)}
            style={{ ['--k-fill-pct' as string]: pct(value, min, max) }} />
        </div>
        {showValue && <span className="val">{format(value)}</span>}
      </div>
      <Marks marks={marks} min={min} max={max} />
    </div>
  )
  return disabled && disabledReason ? <DisabledReason reason={disabledReason} block>{el}</DisabledReason> : el
}
export interface RangeSliderProps extends TestIdProps { value: [number, number]; onChange: (v: [number, number]) => void; min: number; max: number; step?: number; marks?: SliderMark[]; format?: (v: number) => ReactNode; disabled?: boolean; width?: number | string; ariaLabel?: string }
/** Two-handle range (two native range inputs, so both handles are keyboard accessible). */
export function RangeSlider({ value, onChange, min, max, step = 1, marks, format = v => String(v), disabled, width, ariaLabel = 'range', ...t }: RangeSliderProps) {
  const [lo, hi] = value
  return (
    <div className="k-slider k-range" style={{ width }} data-testid={tid(t)}>
      <div className="row1">
        <div className="track-wrap">
          <div className="k-range-rail" />
          <div className="k-range-sel"style={{ left: `calc(7px + (100% - 14px) * ${(lo - min) / (max - min || 1)})`, width: `calc((100% - 14px) * ${(hi - lo) / (max - min || 1)})` }} />
          <input type="range" min={min} max={max} step={step} value={lo} disabled={disabled} aria-label={`${ariaLabel} lower`} onChange={e => onChange([Math.min(Number(e.target.value), hi), hi])} data-testid={tid(t) ? `${tid(t)}-lo` : undefined} />
          <input type="range" min={min} max={max} step={step} value={hi} disabled={disabled} aria-label={`${ariaLabel} upper`} onChange={e => onChange([lo, Math.max(Number(e.target.value), lo)])} data-testid={tid(t) ? `${tid(t)}-hi` : undefined} />
        </div>
        <span className="val">{format(lo)}–{format(hi)}</span>
      </div>
      <Marks marks={marks} min={min} max={max} />
    </div>
  )
}

/* ================= RadioCards ================= */
export interface RadioCardOption<V extends string = string> { value: V; title: ReactNode; description?: ReactNode; icon?: IconName; badge?: ReactNode; disabled?: boolean; reason?: string }
export interface RadioCardsProps<V extends string = string> extends TestIdProps { options: RadioCardOption<V>[]; value: V | null; onChange: (v: V) => void; columns?: number; ariaLabel?: string; showRadio?: boolean }
/** Selectable cards (radiogroup, arrow keys). Disabled cards print their reason. */
export function RadioCards<V extends string = string>({ options, value, onChange, columns = 2, ariaLabel = 'options', showRadio = true, ...t }: RadioCardsProps<V>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0
    if (!d) return
    e.preventDefault()
    let j = i
    for (let k = 0; k < options.length; k++) { j = (j + d + options.length) % options.length; if (!options[j].disabled) break }
    refs.current[j]?.focus(); onChange(options[j].value)
  }
  const selIdx = options.findIndex(o => o.value === value)
  return (
    <div className="k-radio-cards" role="radiogroup" aria-label={ariaLabel} style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }} data-testid={tid(t)}>
      {options.map((o, i) => (
        <button key={o.value} ref={el => { refs.current[i] = el }} type="button" role="radio" aria-checked={o.value === value} className="k-radio-card" disabled={o.disabled} title={o.disabled ? o.reason : undefined}
          tabIndex={o.value === value || (selIdx < 0 && i === 0) ? 0 : -1} onClick={() => onChange(o.value)} onKeyDown={e => onKey(e, i)} data-value={o.value}>
          {showRadio && <span className="radio" />}
          {o.icon && <span className="ic"><Icon name={o.icon} size={15} /></span>}
          <span className="body">
            <span className="t">{o.title}{o.badge}</span>
            {o.description && <span className="d">{o.description}</span>}
            {o.disabled && o.reason && <span className="reason">⊘ {o.reason}</span>}
          </span>
        </button>
      ))}
    </div>
  )
}
