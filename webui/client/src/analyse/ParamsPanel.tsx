/* Parameter controls generated from AdapterCard.params (spec §6.8): segmented for ≤4
   choices, select for more, range + number for bounded numerics, checkbox for bools,
   text otherwise. "= default" marks a value equal to the adapter default; "= recommended"
   is printed only for a value the adapter's recommend hook actually produced (none are served
   by this slice — critique r1); the description sits behind an info icon (P9). */
import { useEffect, useState } from 'react'
import { getDiscoveryBands, type AdapterCard, type DiscBand, type ParamSpec } from '../api'

export interface ParamsPanelProps {
  adapter: AdapterCard
  params: Record<string, unknown>
  onChange: (name: string, value: unknown) => void
  disabled?: boolean
  recommended?: Record<string, unknown>   // values a served recommend hook produced (none in this slice)
}

const eq = (a: unknown, b: unknown) => a === b || (typeof a === 'number' && typeof b === 'number' && Math.abs(a - b) < 1e-9) || String(a) === String(b)

function niceStep(spec: ParamSpec): number {
  if (spec.type === 'int') return 1
  if (spec.min !== null && spec.max !== null) { const r = spec.max - spec.min; const raw = r / 200; const p = Math.pow(10, Math.floor(Math.log10(raw))); return +(Math.ceil(raw / p) * p).toPrecision(2) }
  return 0.1
}

export function fmtParam(v: unknown): string {
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : String(+v.toPrecision(4))
  if (typeof v === 'boolean') return v ? 'yes' : 'no'
  return v === '' ? '—' : String(v)
}

export function ParamsPanel({ adapter, params, onChange, disabled, recommended }: ParamsPanelProps) {
  return (
    <div className="pp-grid">
      {adapter.params.map(spec => {
        const value = params[spec.name] ?? spec.default
        const isDefault = eq(value, spec.default)
        const recVal = recommended && spec.name in recommended ? recommended[spec.name] : undefined
        const rec = recVal !== undefined && eq(value, recVal)
        const numeric = spec.type === 'int' || spec.type === 'float'
        const bounded = numeric && spec.min !== null && spec.max !== null
        const wide = bounded || (spec.choices && spec.choices.length > 4) || spec.type === 'str'
        const testid = `param-${spec.name}`
        let ctl: React.ReactNode
        if (spec.choices && spec.choices.length) {
          ctl = spec.choices.length <= 4 ? (
            <div className="seg" data-testid={testid}>
              {spec.choices.map(c => <button key={String(c)} className={eq(c, value) ? 'on' : ''} disabled={disabled} onClick={() => onChange(spec.name, c)}>{String(c)}</button>)}
            </div>
          ) : (
            <select className="input" data-testid={testid} value={String(value)} disabled={disabled} onChange={e => { const c = spec.choices!.find(o => String(o) === e.target.value); onChange(spec.name, c ?? e.target.value) }}>
              {spec.choices.map(c => <option key={String(c)} value={String(c)}>{String(c)}</option>)}
            </select>
          )
        } else if (spec.type === 'bool') {
          ctl = <label className="checkbox"><input type="checkbox" data-testid={testid} checked={!!value} disabled={disabled} onChange={e => onChange(spec.name, e.target.checked)} /> {value ? 'on' : 'off'}</label>
        } else if (numeric) {
          const step = niceStep(spec)
          const num = typeof value === 'number' ? value : Number(value)
          ctl = (
            <>
              {bounded && <input type="range" min={spec.min!} max={spec.max!} step={step} value={num} disabled={disabled} onChange={e => onChange(spec.name, spec.type === 'int' ? parseInt(e.target.value, 10) : parseFloat(e.target.value))} />}
              <input type="number" className="input" data-testid={testid} min={spec.min ?? undefined} max={spec.max ?? undefined} step={step} value={Number.isFinite(num) ? num : ''} disabled={disabled}
                onChange={e => { const v = spec.type === 'int' ? parseInt(e.target.value, 10) : parseFloat(e.target.value); if (Number.isFinite(v)) onChange(spec.name, v) }} />
            </>
          )
        } else {
          ctl = <input type="text" className="input" data-testid={testid} value={String(value ?? '')} disabled={disabled} onChange={e => onChange(spec.name, e.target.value)} />
        }
        return (
          <div className={`pp-row${wide ? ' wide' : ''}`} key={spec.name}>
            <div className="pp-lab">
              <span>{spec.name}</span>
              <span className="info" title={spec.description || 'no description registered'}>i</span>
              {numeric && <span className="val">{fmtParam(value)}</span>}
            </div>
            <div className="pp-ctl">{ctl}</div>
            <div className={`pp-rec${rec || isDefault ? '' : ' no'}`} data-testid={`param-rec-${spec.name}`}>
              {rec ? '= recommended' : recVal !== undefined ? `rec ${fmtParam(recVal)}` : isDefault ? `= default${adapter.has_recommend ? ' · recommended: not computed' : ''}` : `default ${fmtParam(spec.default)}`}
            </div>
          </div>
        )
      })}
      {!adapter.params.length && <div className="muted mono small">this block has no parameters</div>}
      {adapter.name === 'preprocessing.bandpass' && <BandPresets params={params} onChange={onChange} disabled={disabled} />}
    </div>
  )
}

/* fixup-z, Q43: the project's named band list (Settings › Analysis defaults) as a bandpass block's presets — the
 * same bands Discovery's band scope offers, so a chain built here by hand and a band run there are one recipe. */
function BandPresets({ params, onChange, disabled }: { params: Record<string, unknown>; onChange: (name: string, value: unknown) => void; disabled?: boolean }) {
  const [bands, setBands] = useState<DiscBand[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  // read on every mount, so a list edited in Settings is the list offered next time the block opens
  useEffect(() => {
    let live = true
    getDiscoveryBands().then(r => { if (live) setBands(r.bands) }).catch(e => { if (live) setErr(e instanceof Error ? e.message : String(e)) })
    return () => { live = false }
  }, [])
  if (err) return <div className="pp-row wide small" data-testid="band-presets-error"><span className="muted">band presets unavailable: {err}</span></div>
  if (!bands) return null
  return (
    <div className="pp-row wide" data-testid="band-presets">
      <div className="pp-lab"><span>presets</span><span className="info" title="the named bands in Settings › Analysis defaults — the same list Discovery's band scope offers">i</span></div>
      <div className="pp-ctl seg">
        {bands.map(b => {
          const on = eq(params.low_hz, b.low_hz) && eq(params.high_hz, b.high_hz)
          return <button key={b.label} className={on ? 'on' : ''} disabled={disabled} data-testid={`band-preset-${b.label.replace(/[^A-Za-z0-9]+/g, '_')}`}
            onClick={() => { onChange('low_hz', b.low_hz); onChange('high_hz', b.high_hz) }}>{b.label}</button>
        })}
      </div>
      <div className="pp-rec">Settings › Analysis defaults</div>
    </div>
  )
}
