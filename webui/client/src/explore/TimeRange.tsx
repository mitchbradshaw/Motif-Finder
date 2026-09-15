/* Corpus toolbar `time` control (frame explore-1): a two-handle slider plus the `0 – 721 h` value chip.
   Crops the drawn bins client-side (no core call). Click the chip to type `a – b` in hours; the rule is
   0 ≤ a < b ≤ duration, with the reason shown inline in red while it is broken. */
import { useState } from 'react'
import { RangeSlider } from '../kit'

const fmt = (h: number) => (Number.isInteger(h) ? String(h) : h >= 10 ? String(Math.round(h)) : h.toFixed(1))

export function TimeRange({ durH, value, onChange }: { durH: number; value: [number, number]; onChange: (v: [number, number]) => void }) {
  const [edit, setEdit] = useState<string | null>(null)
  const parse = (s: string): [number, number] | string => {
    const m = s.replace(/h/gi, '').replace('−', '-').match(/^\s*(-?\d+(?:\.\d+)?)\s*[–-]\s*(-?\d+(?:\.\d+)?)\s*$/)
    if (!m) return 'type a range like 120 – 360'
    const a = Number(m[1]), b = Number(m[2])
    if (!(a >= 0 && b <= durH + 1e-9 && a < b)) return `range must be inside 0 – ${fmt(durH)} h`
    return [a, b]
  }
  const parsed = edit === null ? null : parse(edit)
  const commit = () => { if (parsed && typeof parsed !== 'string') { onChange(parsed); setEdit(null) } }
  const step = durH > 100 ? 1 : 0.1
  return (
    <span className="ex-time" data-testid="time-range">
      <span className="lbl">time</span>
      <RangeSlider value={value} onChange={v => onChange([Math.min(v[0], v[1] - step), v[1]])} min={0} max={durH} step={step} width={130} ariaLabel="time range in hours" testid="time-slider" />
      {edit === null ? (
        <button type="button" className="ex-chip-btn" onClick={() => setEdit(`${fmt(value[0])} – ${fmt(value[1])}`)} title="click to type a range in hours" data-testid="time-chip">{fmt(value[0])} – {fmt(value[1])} h</button>
      ) : (
        <span className="ex-time-edit">
          <input autoFocus className={`ex-time-input${typeof parsed === 'string' ? ' invalid' : ''}`} value={edit} onChange={e => setEdit(e.target.value)} aria-label="time range in hours" aria-invalid={typeof parsed === 'string'}
            onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { e.stopPropagation(); setEdit(null) } }} onBlur={() => { if (typeof parsed !== 'string') commit(); else setEdit(null) }} data-testid="time-input" />
          {typeof parsed === 'string' && <span className="ex-time-err" role="alert" data-testid="time-error">{parsed}</span>}
        </span>
      )}
    </span>
  )
}
