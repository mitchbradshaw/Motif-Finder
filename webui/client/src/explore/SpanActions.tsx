/* Span-action row (frame explore-2): the selected span with tags + note, Save span (in-memory write of
   range, tags and note only), Send span to Analyse (live), Take span for Review (in-memory staging into the
   Explore spans queue). Verdicts are never given here — the caption says so. Tags are removable chips; a
   click toggles a chip selected; `+ tag` opens an inline input with suggestions and validation. */
import { useEffect, useId, useState } from 'react'
import { Button, Chip, recordDemoWrite, useDemoState } from '../kit'
import { useToast } from '../shell/Toast'
import { fmtDuration, navigate } from '../state'
import { fmtRangeH } from './util'

const TAG_RULE = /^[a-z0-9]+(-[a-z0-9]+)*$/
const SUGGEST = ['sharkfin', 'spike-train', 'slow-drift', 'burst', 'plateau', 'biphasic']

export interface SpanDraft { tags: string[]; selected: string[]; note: string }

export function SpanActions({ channelKey, channelName, initial, view, nInView, onSend, tagSignal }: {
  channelKey: string; channelName: string; initial: SpanDraft; view: [number, number]; nInView: number; onSend: () => void; tagSignal: number
}) {
  const toast = useToast()
  const [draft, setDraft] = useDemoState<SpanDraft>(`explore.signal.span.${channelKey}`, () => initial)
  const [adding, setAdding] = useState(false)
  const [text, setText] = useState('')
  const listId = useId()
  useEffect(() => { if (tagSignal > 0) setAdding(true) }, [tagSignal])
  const t = text.trim()
  const reason = !t ? null : !TAG_RULE.test(t) || t.length > 32 ? 'tags are lower-case words joined by -' : draft.tags.includes(t) ? `already tagged ${t}` : null
  const commit = () => {
    if (!t) { setAdding(false); return }
    if (reason) return
    setDraft(d => ({ ...d, tags: [...d.tags, t], selected: [...d.selected, t] })); setText(''); setAdding(false)
  }
  const range = fmtRangeH(view[0], view[1])
  const save = () => {
    recordDemoWrite('explore', 'save-span', { channel: channelName, t0_s: view[0], t1_s: view[1], tags: draft.tags, note: draft.note })
    setDemoSaved(n => n + 1)
    toast.push({ text: `span saved · ${range} · tags and note only` })
  }
  const [, setDemoSaved] = useDemoState<number>('explore.savedSpans.count', () => 0)
  const take = () => {
    recordDemoWrite('explore', 'stage-span-for-review', { queue: 'Explore spans', channel: channelName, t0_s: view[0], t1_s: view[1], tags: draft.tags })
    toast.push({ text: 'span staged for Review · Explore spans queue', action: { label: 'Open Review →', onClick: () => navigate('review') } })
  }
  return (
    <div className="card ex-span-act" data-testid="span-actions">
      <div>
        <div className="line mono" style={{ fontSize: 11.5, color: 'var(--muted)' }}>
          <span>Selected span</span>
          <span style={{ color: 'var(--text-2)' }} data-testid="span-action-range">{range} · {fmtDuration(view[1] - view[0])} · {nInView} motif{nInView === 1 ? '' : 's'} in view</span>
        </div>
        <div className="line">
          <span className="k">tags</span>
          {draft.tags.map(tag => (
            <Chip key={tag} tone={draft.selected.includes(tag) ? 'blue' : 'grey'} selected={draft.selected.includes(tag)} size="sm" testid="span-tag"
              onClick={() => setDraft(d => ({ ...d, selected: d.selected.includes(tag) ? d.selected.filter(x => x !== tag) : [...d.selected, tag] }))}
              onRemove={() => setDraft(d => ({ ...d, tags: d.tags.filter(x => x !== tag), selected: d.selected.filter(x => x !== tag) }))} removeLabel={`remove tag ${tag}`}>{tag}</Chip>
          ))}
          {adding ? (
            <span className="ex-tag-edit">
              <input className={`input${reason ? ' invalid' : ''}`} autoFocus list={listId} style={{ height: 24, width: 140 }} value={text} placeholder="tag" aria-invalid={!!reason}
                onChange={e => setText(e.target.value.toLowerCase())} onBlur={() => { if (!reason) commit() }}
                onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { e.stopPropagation(); setText(''); setAdding(false) } }} data-testid="tag-input" />
              <datalist id={listId}>{SUGGEST.filter(s => !draft.tags.includes(s)).map(s => <option key={s} value={s} />)}</datalist>
              {reason && <span className="ex-time-err side" role="alert" data-testid="tag-error">{reason}</span>}
            </span>
          ) : <Chip size="sm" tone="outline" icon="plus" onClick={() => setAdding(true)} testid="add-tag" title="add a tag (T)">tag</Chip>}
        </div>
        <div className="line">
          <span className="k">note</span>
          <input className="input ex-note" placeholder="what you saw — kept with the span, never a verdict" value={draft.note} maxLength={500}
            onChange={e => setDraft(d => ({ ...d, note: e.target.value }))} data-testid="span-note" />
          {draft.note.length >= 400 && <span className="mono small" style={{ color: draft.note.length >= 500 ? 'var(--red)' : 'var(--muted)' }} data-testid="note-counter">{draft.note.length} / 500</span>}
        </div>
      </div>
      <div>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <Button onClick={save} testid="save-span">Save span</Button>
          <Button iconRight="arrow-right" onClick={onSend} testid="send-span">Send span to Analyse</Button>
          <Button variant="primary" iconRight="arrow-right" onClick={take} testid="take-span">Take span for Review</Button>
        </div>
        <div className="caption" style={{ textAlign: 'right' }}>saving stores tags and note only · verdicts are given in Review</div>
      </div>
    </div>
  )
}
