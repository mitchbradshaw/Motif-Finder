/* Small Explore-local pieces the kit does not carry (requests/explore.md lists the ones worth promoting):
   DemoTag (the "demo" marker on a fixture-backed region), MultiPick (a select-like chip that opens a
   checklist), LegendRow (a swatch + sentence in a legend popover), SectionHead (rail title + InfoTip + rule). */
import { useRef, useState, type ReactNode } from 'react'
import { Checkbox, Icon, InfoTip, Popover, cx } from '../kit'

export function DemoTag({ title = 'fixture data from the spec §0 placeholder canon — not read from your database' }: { title?: string }) {
  return <span className="ex-demo" title={title} data-testid="demo-tag">demo</span>
}

export interface PickOption { value: string; label: ReactNode; sub?: ReactNode; count?: ReactNode; dot?: string; disabled?: boolean; reason?: string }
/** "runs  all · 34 ▾" → a checklist popover with select all · none. `value` empty = all. */
export function MultiPick({ prefix, options, value, onChange, allLabel, testid, block = true, title }: {
  prefix: string; options: PickOption[]; value: string[] | null; onChange: (v: string[] | null) => void; allLabel: string; testid: string; block?: boolean; title?: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)
  const all = options.map(o => o.value)
  const sel = value ?? all
  const label = value === null || sel.length === all.length ? allLabel : `${sel.length} of ${all.length}`
  const toggle = (v: string) => {
    const next = sel.includes(v) ? sel.filter(x => x !== v) : all.filter(x => x === v || sel.includes(x))
    onChange(next.length === all.length ? null : next)
  }
  return (
    <>
      <button ref={ref} type="button" className={cx('k-dd-trigger', block && 'block', value !== null && sel.length !== all.length && 'active')} aria-haspopup="dialog" aria-expanded={open}
        onClick={() => setOpen(o => !o)} data-testid={testid} data-value={label}>
        <span className="pre">{prefix}</span><span className="val">{label}</span><Icon name="chevron-down" size={12} className="chev" />
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} width={300} testid={`${testid}-popover`}
        title={<span className="row" style={{ justifyContent: 'space-between', width: '100%' }}>{title ?? prefix}<span className="ex-links"><button type="button" onClick={() => onChange(null)}>select all</button> · <button type="button" onClick={() => onChange([])}>none</button></span></span>}>
        <div className="ex-pick-list">
          {options.map(o => (
            <Checkbox key={o.value} checked={sel.includes(o.value)} onChange={() => toggle(o.value)} dot={o.dot} disabled={o.disabled} disabledReason={o.reason}
              label={<span className="ex-pick-lbl"><span>{o.label}</span>{o.sub && <span className="sub">{o.sub}</span>}</span>} count={o.count} testid={`${testid}-opt-${o.value}`} />
          ))}
        </div>
      </Popover>
    </>
  )
}

export function SectionHead({ title, info, extra }: { title: ReactNode; info?: ReactNode; extra?: ReactNode }) {
  return <h4 className="ex-sec-head"><span>{title}</span>{info && <InfoTip title={typeof title === 'string' ? title : undefined}>{info}</InfoTip>}{extra && <span className="ex-sec-extra">{extra}</span>}</h4>
}

export function LegendRow({ swatch, children }: { swatch: ReactNode; children: ReactNode }) {
  return <div className="ex-legend-row"><span className="sw">{swatch}</span><span>{children}</span></div>
}
