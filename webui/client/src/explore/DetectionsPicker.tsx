/* "detections 3 of 6 runs · 3 methods ▾" chip + the "Show detections from" checklist (frame explore-2a).
   Rows regroup by run / method / template; a checked run's detections draw in the span tier and walk in
   ‹ N / M ›. Footer toggles: colour by run, hide surrogates, unadjudicated only. On the canon channel the
   runs, methods and colours are demo canon; elsewhere the rows are the live runs from /api/runs. */
import { forwardRef } from 'react'
import { Checkbox, fmtInt, Icon, Popover, Seg, cx } from '../kit'
import { DemoTag } from './bits'
import { chipLabel, type PickerRun, type PickerState } from './signalModel'

interface Props { runs: PickerRun[]; st: PickerState; setSt: (s: PickerState) => void; open: boolean; setOpen: (o: boolean) => void; demo: boolean; loading: boolean; anchor: React.RefObject<HTMLButtonElement | null> }

export const DetectionsChip = forwardRef<HTMLButtonElement, { label: string; open: boolean; onClick: () => void }>(function DetectionsChip({ label, open, onClick }, ref) {
  return (
    <button ref={ref} type="button" className="k-dd-trigger outline ex-det-chip" aria-haspopup="dialog" aria-expanded={open} onClick={onClick} data-testid="detection-runs-chip" title="choose which runs' detections are drawn">
      <span className="pre">detections</span><span className="val">{label}</span><Icon name="chevron-down" size={12} className="chev" />
    </button>
  )
})

export function DetectionsPicker({ runs, st, setSt, open, setOpen, demo, loading, anchor }: Props) {
  const toggleIds = (ids: string[]) => {
    const allOn = ids.every(id => st.checked.includes(id))
    setSt({ ...st, checked: allOn ? st.checked.filter(x => !ids.includes(x)) : [...new Set([...st.checked, ...ids])] })
  }
  const groups: { key: string; label: string; sub: string; ids: string[]; colour: string; count: number; surrogate: boolean }[] =
    st.group === 'run'
      ? runs.map(r => ({ key: r.id, label: `${r.name}  ${r.id}`, sub: r.method, ids: [r.id], colour: r.colour, count: r.count, surrogate: r.surrogate }))
      : [...new Set(runs.map(r => (st.group === 'method' ? r.method : r.template)))].map(k => {
        const rs = runs.filter(r => (st.group === 'method' ? r.method : r.template) === k)
        return { key: k, label: k, sub: `${rs.length} run${rs.length === 1 ? '' : 's'}: ${rs.map(r => r.id).join(', ')}`, ids: rs.map(r => r.id), colour: rs[0].colour, count: rs.reduce((s, r) => s + r.count, 0), surrogate: rs.every(r => r.surrogate) }
      })
  return (
    <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchor} placement="bottom-end" width={420} flush testid="detection-runs-popover" ariaLabel="Show detections from">
      <div className="ex-picker">
        <div className="hd"><b>Show detections from</b>{demo && <DemoTag />}<span className="grow" /><span className="ex-links"><button type="button" onClick={() => setSt({ ...st, checked: runs.map(r => r.id) })} data-testid="picker-all">select all</button> · <button type="button" onClick={() => setSt({ ...st, checked: [] })} data-testid="picker-none">none</button></span></div>
        <Seg options={[{ value: 'run', label: 'by run' }, { value: 'method', label: 'by method' }, { value: 'template', label: 'by template' }]} value={st.group} onChange={g => setSt({ ...st, group: g })} size="sm" ariaLabel="group rows" testid="picker-group" />
        <div className="rows">
          {loading && <div className="skeleton" style={{ height: 60 }} />}
          {!loading && !groups.length && <div className="muted small mono" style={{ padding: 10 }} data-testid="picker-empty">no run has written detections on this channel</div>}
          {groups.map(g => {
            const on = g.ids.every(id => st.checked.includes(id))
            const hidden = st.hideSurrogates && g.surrogate
            return (
              <div key={g.key} className={cx('r', on && !hidden && 'on')} data-testid={`picker-row-${g.key}`}>
                <Checkbox checked={on} onChange={() => toggleIds(g.ids)} disabled={hidden} disabledReason="hidden by ‘hide surrogates’" ariaLabel={`show ${g.label}`}
                  label={<span className="lbl"><i className="sw" style={{ background: g.colour }} /><span className="nm"><b>{g.label}</b><span className="sub">{g.sub}</span></span></span>} />
                <span className="cnt">{fmtInt(g.count)}</span>
              </div>
            )
          })}
        </div>
        <div className="ft">
          <Checkbox checked={st.colourByRun} onChange={v => setSt({ ...st, colourByRun: v })} label="colour by run" testid="picker-colour-by-run" />
          <Checkbox checked={st.hideSurrogates} onChange={v => setSt({ ...st, hideSurrogates: v })} label="hide surrogates" testid="picker-hide-surrogates" />
          <Checkbox checked={st.unadjudicatedOnly} onChange={v => setSt({ ...st, unadjudicatedOnly: v })} label="unadjudicated only" disabled={!demo} disabledReason="no adjudications in this database" testid="picker-unadjudicated" />
        </div>
      </div>
    </Popover>
  )
}

export { chipLabel }
