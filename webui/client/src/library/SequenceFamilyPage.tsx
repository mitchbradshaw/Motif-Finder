/* library.family?unit=sequences — the sequence family page (prompt `sequences`, 2026-10-18). Replaces
 * `SequenceFamilyPlaceholder`.
 *
 * In plain words: a sequence family is every sequence with the same family labels in the same order. The page draws,
 * top to bottom: every sequence as a strip of its elements with the gaps to scale (one strip per sequence, each
 * element the colour its motif family has in the atlas); the medoid shape at each element position (the most typical
 * element there); how long the silences between elements are, and how many elements the sequences have; the first
 * three sequences as real traces with their elements shaded; and the rail — verdicts on the elements, remove a
 * sequence from the family (a hand edit, restorable), send the unjudged elements to Review.
 *
 * Everything is read from GET /api/library/sequences/{id} — the medoids, the bins and the nearest other family are
 * the bridge's numbers, never recomputed here. */
import { useEffect, useState } from 'react'
import { Button, EmptyState, Histogram, InfoTip, KeyValue, MiniTrace, fmtInt } from '../kit'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import {
  deleteLibraryHandEdit, getLibrarySequenceFamily, postLibraryHandEdit, sendSequenceFamilyReview,
  type LibSeqFamily, type LibSeqStrip,
} from '../api'
import type { SequenceFamily } from '../api/library'
import { LoadFailed, Loading, centreTrace } from './chrome'
import { LabelKey, SequenceStrips, SequenceTrace, fmtDur } from './SequenceStrips'

export function SequenceFamilyPage({ f, grouping }: { f: SequenceFamily; grouping?: string }) {
  const [data, setData] = useState<LibSeqFamily | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let off = false
    setError(null)
    getLibrarySequenceFamily(f.id, grouping).then(d => { if (!off) setData(d) }).catch((e: Error) => { if (!off) { setError(e); setData(null) } })
    return () => { off = true }
  }, [f.id, grouping, tick])
  const reload = () => setTick(t => t + 1)
  if (error) return <LoadFailed what={`sequence family ${f.id}`} error={error} onRetry={reload} />
  if (!data) return <Loading height={640} testid="sequence-family-loading" />
  return (
    <div className="lib-split" data-testid="sequence-family-page">
      <div className="stack" style={{ gap: 14, minWidth: 0 }}>
        <div className="k-card" style={{ padding: '12px 14px' }}>
          <div className="row" style={{ gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span className="lib-h" data-testid="sequence-family-name">{data.name}</span>
            <InfoTip title="a sequence family" testid="sequence-family-info">
              Every sequence here has the same family labels in the same order ({data.name}); their gaps and durations may
              differ. A sequence that differs by one element is its own family — the nearest one is named beside the title.
              Labels are read from motif grouping {data.motifGrouping ?? '—'}; the families from sequence grouping {data.grouping}.
            </InfoTip>
            <span className="lib-cap">{fmtInt(data.sequences.length)} sequences · {fmtInt(data.recordings)} channel{data.recordings === 1 ? '' : 's'} · grouping {data.grouping}</span>
            {data.nearest
              ? <span className="lib-cap" style={{ marginLeft: 'auto' }} data-testid="sequence-family-nearest">nearest other family:{' '}
                <Button variant="link" size="sm" testid="sequence-family-nearest-link" onClick={() => navigate(`library/family/${data.nearest!.id}?unit=sequences&grouping=${data.grouping}`)}>{data.nearest.name}</Button>
                {' '}· {data.nearest.distance} element{data.nearest.distance === 1 ? '' : 's'} different</span>
              : <span className="lib-cap" style={{ marginLeft: 'auto' }}>the only family in this grouping</span>}
          </div>
          <div className="lib-cap" style={{ marginTop: 4 }}>each strip is one sequence: its elements in order, coloured by motif family, with the gaps between them drawn to scale on one shared time axis</div>
          <div style={{ marginTop: 10 }}>
            {data.sequences.length ? <SequenceStrips strips={data.sequences} testid="sequence-family-strips" />
              : <EmptyState icon="layers" title="Every sequence of this family has been removed by hand" caption="restore one from the rail" />}
          </div>
          <div style={{ marginTop: 8 }}><LabelKey colours={data.colours} labels={data.labels} /></div>
        </div>

        <div className="k-card" style={{ padding: '12px 14px' }} data-testid="sequence-family-medoids">
          <span className="lib-h">The medoid shape at each position</span>
          <span className="lib-cap" style={{ marginLeft: 8 }}>the most typical element at that place in the chain, each on its own measured scale</span>
          <div className="row" style={{ gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
            {data.medoids.map(m => (
              <div key={m.position} className="stack" style={{ gap: 2, width: 150 }} data-testid="sequence-family-medoid">
                <span className="lib-cap"><b style={{ color: m.colour }}>{m.position + 1}. {m.label}</b> · of {fmtInt(m.drawnFrom ?? 0)}{m.drawnFrom !== m.n ? ` (of ${fmtInt(m.n)})` : ''}</span>
                {m.trace.length ? <MiniTrace values={centreTrace(m.trace)} width={150} height={56} stroke={m.colour} strokeWidth={1.5} title={`position ${m.position + 1} medoid · member ${m.memberId}`} />
                  : <span className="lib-cap" style={{ height: 56, display: 'flex', alignItems: 'center' }}>no waveform (unit undeclared or not on disk)</span>}
              </div>
            ))}
          </div>
          {data.unitNote && <div className="lib-cap" style={{ marginTop: 6 }}>{data.unitNote}</div>}
        </div>

        <div className="lib-grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div className="k-card" style={{ padding: '12px 14px' }}>
            <span className="lib-h">Gaps between elements</span>
            <div className="lib-cap">seconds from one element's end to the next one's start · {fmtInt(data.gaps.length)} gaps</div>
            <Histogram bins={data.gapBins} height={150} xLabel="gap (s)" showCounts testid="sequence-family-gap-hist" />
          </div>
          <div className="k-card" style={{ padding: '12px 14px' }}>
            <span className="lib-h">Sequence length</span>
            <div className="lib-cap">elements per sequence · {fmtInt(data.lengths.length)} sequences</div>
            <Histogram bins={data.lengthBins} height={150} xLabel="elements" showCounts format={v => String(Math.round(v))} testid="sequence-family-length-hist" />
          </div>
        </div>

        <div className="k-card" style={{ padding: '12px 14px' }} data-testid="sequence-family-examples">
          <span className="lib-h">Example traces</span>
          <span className="lib-cap" style={{ marginLeft: 8 }}>the first {data.examples.length} sequences, with each element shaded in its family's colour</span>
          <div className="stack" style={{ gap: 10, marginTop: 8 }}>
            {data.examples.map(ex => <SequenceTrace key={ex.sequenceId} trace={ex.trace} durationS={ex.durationS} bands={ex.bands} testid="sequence-family-example" />)}
          </div>
        </div>
      </div>
      <SequenceRail data={data} onChanged={reload} />
    </div>
  )
}

function SequenceRail({ data, onChanged }: { data: LibSeqFamily; onChanged: () => void }) {
  const { push } = useToast()
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const act = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key); setErr(null)
    try { await fn(); onChanged() } catch (e) { setErr((e as Error).message) } finally { setBusy(null) }
  }
  const remove = (s: LibSeqStrip) => act(`rm-${s.sequenceId}`, () => postLibraryHandEdit({ contentHash: s.contentHash ?? '', kind: 'remove_member', familyLabel: data.id, grouping: data.grouping }))
  const restore = (editId: number) => act(`re-${editId}`, () => deleteLibraryHandEdit(editId))
  const review = () => act('review', async () => {
    const r = await sendSequenceFamilyReview(data.id, data.grouping)
    push({ text: `${r.name} · ${fmtInt(r.sent)} elements sent`, action: { label: 'Open Review', onClick: () => navigate(`review/queue/${r.queueId}`) } })
  })
  const unjudged = data.judgedOf - data.judged
  return (
    <div className="k-card stack" style={{ padding: '12px 14px', gap: 10 }} data-testid="sequence-family-rail">
      <span className="lib-h">{data.name}</span>
      <KeyValue dense items={[
        { k: 'sequences', v: fmtInt(data.sequences.length) },
        { k: 'elements judged', v: `${fmtInt(data.judged)} of ${fmtInt(data.judgedOf)}` },
        ...Object.entries(data.byVerdict).sort().map(([k, v]) => ({ k: `  ${k}`, v: fmtInt(v) })),
        { k: 'median gap', v: data.gaps.length ? fmtDur([...data.gaps].sort((a, b) => a - b)[Math.floor(data.gaps.length / 2)]) : '—' },
      ]} />
      <Button variant="primary" size="sm" icon="external" testid="sequence-family-review" loading={busy === 'review'} onClick={review}
        disabled={!unjudged || !!busy} disabledReason={!unjudged ? 'every element is already judged' : 'working…'}>Send {fmtInt(unjudged)} unjudged elements to Review</Button>
      {err && <span className="lib-cap" role="alert" style={{ color: 'var(--red)' }} data-testid="sequence-family-rail-error">{err}</span>}
      <span className="lib-cap">members</span>
      <div className="stack" style={{ gap: 4, maxHeight: 360, overflow: 'auto' }}>
        {data.sequences.map(s => (
          <div key={s.sequenceId} className="row" style={{ gap: 6, alignItems: 'center' }} data-testid="sequence-family-member">
            <span className="lib-cap" style={{ flex: 1, minWidth: 0 }}>{s.id} · {s.channel} · {s.startH.toFixed(2)} h · {fmtDur(s.durationS)}</span>
            <Button variant="link" size="sm" testid="sequence-family-remove" loading={busy === `rm-${s.sequenceId}`} disabled={!!busy || !s.contentHash}
              disabledReason={!s.contentHash ? 'this sequence carries no identity to key a hand edit to' : 'working…'} onClick={() => remove(s)}>remove</Button>
          </div>
        ))}
      </div>
      {!!data.removed.length && <>
        <span className="lib-cap">removed by hand</span>
        {data.removed.map(r => (
          <div key={r.editId} className="row" style={{ gap: 6, alignItems: 'center' }} data-testid="sequence-family-removed">
            <span className="lib-cap" style={{ flex: 1 }}>{r.id}</span>
            <Button variant="link" size="sm" testid="sequence-family-restore" loading={busy === `re-${r.editId}`} disabled={!!busy} disabledReason="working…" onClick={() => restore(r.editId)}>restore</Button>
          </div>
        ))}
      </>}
      <Button variant="link" size="sm" testid="sequence-family-back" onClick={() => navigate(`library/atlas?unit=sequences&family=${encodeURIComponent(data.id)}`)}>‹ back to atlas</Button>
    </div>
  )
}
