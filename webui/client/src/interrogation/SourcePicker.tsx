/* The source-chip popover (frame interrogation-1b): the four kinds of SpanSet source (§6.2).
 * Deep-linkable: ?popover=source&tab=family|run|review|explore. */
import { useState } from 'react'
import { Badge, Button, Chip, EmptyState, Icon, Popover, Tabs, TextField, fmtInt, useQueryState } from '../kit'
import { navigate } from '../state'
import { useNotWired } from '../kit'
import { useSourced } from '../api/seam'
import { getSourceChoices } from '../api/interrogation'
import { Loading, LoadFailed } from './chrome'

/** The row cell shows the first clause of a disabled reason; the whole reason is the row's tooltip. */
const short = (reason: string) => (reason.length <= 28 ? reason : `${reason.split(' · ')[0].slice(0, 28)}…`)

export function SourcePicker({ open, onClose, anchorRef, familyId, onPickFamily }: {
  open: boolean; onClose: () => void; anchorRef: React.RefObject<HTMLElement | null>; familyId: string; onPickFamily: (id: string) => void
}) {
  return (
    <Popover open={open} onClose={onClose} anchorRef={anchorRef} placement="bottom-start" width={560} flush testid="source-picker">
      <SourcePickerBody familyId={familyId} onPickFamily={id => { onPickFamily(id); onClose() }} onClose={onClose} />
    </Popover>
  )
}

function SourcePickerBody({ familyId, onPickFamily, onClose }: { familyId: string; onPickFamily: (id: string) => void; onClose: () => void }) {
  const choices = useSourced(getSourceChoices, [])
  const [tab, setTab] = useQueryState('tab', 'family')
  const [filter, setFilter] = useState('')
  const notWired = useNotWired()

  if (choices.error) return <div style={{ padding: 12 }}><LoadFailed what="the source list" error={choices.error} onRetry={choices.reload} /></div>
  if (!choices.data) return <Loading what="sources" />
  const c = choices.data
  const families = [...c.families, c.heldOut].filter(f => !filter || `${f.id} ${f.name}`.toLowerCase().includes(filter.toLowerCase()))

  return (
    <div data-testid="source-picker-body">
      <div style={{ padding: '10px 12px 0' }}>
        <Tabs variant="soft" value={tab} onChange={setTab} testid="source-tabs" items={[
          { value: 'family', label: 'Library family', icon: 'library' },
          { value: 'run', label: 'Prior run', icon: 'clock' },
          { value: 'review', label: 'Review selection', icon: 'checklist' },
          { value: 'explore', label: 'Explore spans', icon: 'wave' },
        ]} />
      </div>

      {tab === 'family' && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px' }}>
            <TextField value={filter} onChange={setFilter} placeholder="filter families" icon="search" block testid="family-filter" ariaLabel="filter families" />
            <span className="ig-muted ig-small mono" style={{ whiteSpace: 'nowrap' }}>clustering {c.clustering.version} · {c.clustering.method} t {c.clustering.t}</span>
          </div>
          <div style={{ maxHeight: 280, overflow: 'auto' }}>
            <table className="ig-pick" data-testid="family-table">
              <thead><tr><th style={{ width: '32%' }}>family</th><th className="num" style={{ width: '13%' }}>members</th><th className="num" style={{ width: '15%' }}>recordings</th><th className="num" style={{ width: '17%' }}>adjudicated</th><th /></tr></thead>
              <tbody>
                {families.map(f => {
                  const on = f.id === familyId
                  return (
                    <tr key={f.id} className={f.disabledReason ? 'dim' : on ? 'on' : undefined} data-testid={`family-row-${f.id}`}
                      title={f.disabledReason} aria-disabled={f.disabledReason ? true : undefined}
                      onClick={() => { if (f.disabledReason) return; onPickFamily(f.id) }}>
                      <td className="nm">{on && <Icon name="check" size={12} style={{ marginRight: 4, color: 'var(--blue)' }} />}{f.id} {f.name}</td>
                      <td className="num">{fmtInt(f.within)}</td>
                      <td className="num">{f.recordings.length}</td>
                      <td className="num" style={{ color: f.adjudicated === 0 ? '#b86e00' : undefined }}>{f.adjudicated} / {fmtInt(f.within)}</td>
                      <td>{f.disabledReason
                        ? <span className="ig-muted" title={f.disabledReason}>&#8856; {short(f.disabledReason)}</span>
                        : f.crossRecording && <Chip tone="purple" size="sm">cross-recording</Chip>}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {!families.length && <EmptyState size="sm" title="no family matches" caption="clear the filter" testid="family-empty" />}
          </div>
          <div className="ig-foot" style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }} data-testid="swap-note">
            <Icon name="info" size={12} />swapping a SpanSet source keeps 01 and 02; they re-run on the new members
          </div>
        </>
      )}

      {tab === 'run' && (
        <div style={{ padding: '6px 0 0' }} data-testid="run-list">
          <table className="ig-pick">
            <thead><tr><th style={{ width: '34%' }}>run</th><th style={{ width: '22%' }}>template</th><th className="num" style={{ width: '11%' }}>spans</th><th style={{ width: '14%' }}>terminal</th><th /></tr></thead>
            <tbody>
              {c.runs.map(r => {
                const reason = r.disabledReason
                return (
                  <tr key={r.id} className={reason ? 'dim' : undefined} data-testid={`run-row-${r.id}`} title={reason} aria-disabled={reason ? true : undefined}
                    onClick={() => { if (reason) return; notWired(`apply run ${r.label} to the source`); onClose() }}>
                    <td className="nm">{r.label}</td><td>{r.template}</td><td className="num">{fmtInt(r.spans)}</td>
                    <td><Badge tone={r.terminal === 'SpanSet' ? 'blue' : 'purple'}>{r.terminal}</Badge></td>
                    <td className="ig-muted" title={reason}>{reason ? <span>&#8856; {short(reason)}</span> : r.when}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="ig-foot" style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
            <Icon name="info" size={12} />a prior run supplies its spans · exclusions are re-applied by member identity
          </div>
        </div>
      )}

      {tab === 'review' && (
        <div style={{ padding: '6px 0 0' }} data-testid="review-list">
          <table className="ig-pick">
            <thead><tr><th style={{ width: '14%' }}>queue</th><th style={{ width: '38%' }}>source</th><th className="num" style={{ width: '18%' }}>judged</th><th /></tr></thead>
            <tbody>
              {c.reviewSelections.map(q => (
                <tr key={q.id} className={q.disabledReason ? 'dim' : undefined} data-testid={`review-row-${q.id}`} title={q.disabledReason} aria-disabled={q.disabledReason ? true : undefined}
                  onClick={() => { if (q.disabledReason) return; notWired(`take the ${q.judged} judged spans of ${q.id} as the source`); onClose() }}>
                  <td className="nm">{q.id}</td><td>{q.source}</td><td className="num">{q.judged} / {fmtInt(q.total)}</td>
                  <td title={q.disabledReason}>{q.disabledReason ? <span className="ig-muted">&#8856; {short(q.disabledReason)}</span> : q.blind ? <Badge tone="grey">blind</Badge> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="ig-foot" style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
            <Icon name="info" size={12} />verdicts stay in Review · a selection only scopes what is measured
          </div>
        </div>
      )}

      {tab === 'explore' && (
        <div style={{ padding: '6px 0 0' }} data-testid="explore-list">
          <table className="ig-pick">
            <thead><tr><th style={{ width: '18%' }}>span set</th><th style={{ width: '38%' }}>recording · channel</th><th className="num" style={{ width: '14%' }}>spans</th><th /></tr></thead>
            <tbody>
              {c.exploreSpans.map(s => (
                <tr key={s.id} data-testid={`explore-row-${s.id}`} onClick={() => { notWired(`take ${s.spans} spans from ${s.id}`); onClose() }}>
                  <td className="nm">{s.id}</td><td>{s.recording} · {s.channel}</td><td className="num">{s.spans}</td>
                  <td className="ig-muted">{s.from_h.toFixed(1)}–{s.to_h.toFixed(1)} h</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
            <Button size="sm" variant="link" icon="external" onClick={() => { navigate('explore/corpus'); onClose() }} testid="open-explore">Pick spans in Explore →</Button>
          </div>
        </div>
      )}
    </div>
  )
}
