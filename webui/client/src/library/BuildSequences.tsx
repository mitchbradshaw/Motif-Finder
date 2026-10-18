/* library.atlas?unit=sequences — *Build sequences* (prompt `sequences`, 2026-10-18).
 *
 * In plain words: walk along one channel; where one Library member ends and the next one starts soon after, the two
 * belong to one sequence, read as the chain of their family labels (F-01 → F-02 → F-01). This card asks the bridge
 * what that join WOULD make on one channel (POST /api/library/sequences/preview — nothing is written), draws the
 * sequences as strips with a count per label chain, and stores them only on *Keep these* (POST …/keep), which also
 * saves the label-chain grouping the atlas then shows. The join itself is the core's (`Working/library/sequences.py`);
 * this card only sends the rule and the numbers. */
import { useEffect, useState } from 'react'
import { Button, InfoTip, NumberField, Seg, SelectField, fmtInt } from '../kit'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import {
  keepLibrarySequences, previewLibrarySequences,
  type LibSeqCandidate, type LibSeqKeep, type LibSeqPreview, type LibSeqRule,
} from '../api'
import { LabelKey, SequenceStrips } from './SequenceStrips'

const RULE_OPTIONS: { value: LibSeqRule; label: string; title: string }[] = [
  { value: 'fixed', label: 'fixed gap', title: 'a gap you set: the end of one member to the start of the next' },
  { value: 'adamatzky', label: 'adamatzky', title: 'adaptive: neighbours join while their onset gap is at most the mean onset gap' },
  { value: 'logisi', label: 'logISI', title: 'adaptive: the valley of the log-gap histogram is the cut (refuses with fewer than 10 gaps)' },
]

export function BuildSequences({ onKept }: { onKept: (r: LibSeqKeep) => void }) {
  const { push } = useToast()
  const [candidates, setCandidates] = useState<LibSeqCandidate[] | null>(null)
  const [candErr, setCandErr] = useState<string | null>(null)
  const [rid, setRid] = useState<string>('')
  const [rule, setRule] = useState<LibSeqRule>('fixed')
  const [gap, setGap] = useState(0)
  const [tolPct, setTolPct] = useState(10)
  const [minLen, setMinLen] = useState(2)
  const [preview, setPreview] = useState<LibSeqPreview | null>(null)
  const [busy, setBusy] = useState<'preview' | 'keep' | null>(null)
  const [err, setErr] = useState<string | null>(null)
  // the last keep, so its first family opens straight from here (under the grouping that keep saved)
  const [lastKept, setLastKept] = useState<LibSeqKeep | null>(null)

  // the picker: channels holding two or more labelled members, busiest first (the bridge's list)
  useEffect(() => {
    let off = false
    previewLibrarySequences({ rule: 'fixed', gap_s: 0, tol_frac: 0.1, candidates_only: true })
      .then(p => { if (!off) { setCandidates(p.candidates); if (p.candidates[0]) setRid(r => r || String(p.candidates[0].recordingId)) } })
      .catch((e: Error) => { if (!off) setCandErr(e.message) })
    return () => { off = true }
  }, [])

  const body = () => ({ recording_id: rid ? Number(rid) : null, rule, gap_s: gap, tol_frac: tolPct / 100, min_len: minLen })
  const runPreview = async () => {
    setBusy('preview'); setErr(null)
    try { setPreview(await previewLibrarySequences(body())) } catch (e) { setErr((e as Error).message); setPreview(null) } finally { setBusy(null) }
  }
  const keep = async () => {
    if (!preview) return
    setBusy('keep'); setErr(null)
    try {
      const r = await keepLibrarySequences({ ...body(), recording_id: preview.recordingId })
      push({ text: r.created ? `Kept ${fmtInt(r.created)} sequence${r.created === 1 ? '' : 's'}${r.already ? ` (${fmtInt(r.already)} already kept)` : ''} · grouping ${r.grouping} · ${fmtInt(r.families)} families`
        : `All ${fmtInt(r.already)} were already kept — nothing written` })
      setPreview(await previewLibrarySequences({ ...body(), recording_id: preview.recordingId }))
      setLastKept(r)
      onKept(r)
    } catch (e) { setErr((e as Error).message) } finally { setBusy(null) }
  }
  // the preview answers for the settings it was made with; change one and Keep waits for a new preview
  const stale = !!preview && (preview.rule !== rule || preview.gapS !== gap || Math.abs(preview.tolFrac - tolPct / 100) > 1e-9
    || preview.minLen !== minLen || (rid !== '' && String(preview.recordingId) !== rid))
  const fresh = preview ? preview.sequences.filter(s => !s.kept).length : 0
  const keepReason = !preview ? 'make a preview first' : stale ? 'the settings changed since this preview — preview again' : !preview.sequences.length ? 'this preview made no sequence' : !fresh ? 'every sequence in this preview is already kept' : ''
  const opts = (candidates ?? []).map(c => ({ value: String(c.recordingId), label: `${c.recording} · ${c.channel} · ${fmtInt(c.members)} members` }))
  return (
    <div className="k-card" style={{ padding: '12px 14px' }} data-testid="build-sequences">
      <div className="row" style={{ gap: 8, alignItems: 'center' }}>
        <span className="lib-h">Build sequences</span>
        <InfoTip title="Build sequences" testid="build-sequences-info">
          A sequence is one channel's ordered run of Library members — motifs that carry a family label — joined while the
          gap from one member's end to the next one's start is under a limit, the way spikes make a spike train. Two
          sequences are the same family when they have the same labels in the same order, whatever their gaps. The fixed
          rule's default is 0 s plus 10 % of the shorter member's length, because members rarely touch to the sample; the two
          adaptive rules set the limit from the data instead (Working/interrogation/trains.py). Nothing is stored until
          Keep these.
        </InfoTip>
        <span className="lib-cap" style={{ marginLeft: 4 }}>join neighbouring Library members on one channel into label chains — preview first, nothing is stored until you keep them</span>
      </div>
      <div className="row" style={{ gap: 10, flexWrap: 'wrap', alignItems: 'center', marginTop: 10 }}>
        <span className="lib-cap">channel</span>
        {candErr ? <span className="lib-cap" style={{ color: 'var(--red)' }} data-testid="build-sequences-candidates-error">could not list the channels: {candErr}</span>
          : <SelectField value={rid} onChange={setRid} size="sm" width={300} testid="build-sequences-recording" ariaLabel="recording channel"
            disabled={!opts.length} disabledReason={candidates == null ? 'listing the channels that hold members…' : 'no channel holds two or more Library members with a family label'}
            options={opts.length ? opts : [{ value: '', label: candidates == null ? 'listing channels…' : 'no channel with members' }]} />}
        <Seg size="sm" ariaLabel="join rule" testid="build-sequences-rule" value={rule} onChange={setRule} options={RULE_OPTIONS} />
        {rule === 'fixed' && <>
          <span className="lib-cap">max gap</span>
          <NumberField size="sm" width={80} value={gap} min={0} step={1} unit="s" onValid={setGap} testid="build-sequences-gap" ariaLabel="maximum gap in seconds" />
          <span className="lib-cap">+ tolerance</span>
          <NumberField size="sm" width={80} value={tolPct} min={0} max={100} step={1} unit="%" onValid={setTolPct} testid="build-sequences-tol" ariaLabel="tolerance as a percent of the shorter member" />
          <span className="lib-cap">of the shorter member</span>
        </>}
        <span className="lib-cap">min elements</span>
        <NumberField size="sm" width={70} value={minLen} min={2} step={1} integer onValid={setMinLen} testid="build-sequences-minlen" ariaLabel="minimum elements" />
        <Button variant="primary" size="sm" icon="play" testid="build-sequences-preview" loading={busy === 'preview'} onClick={runPreview}
          disabled={!!busy || (candidates != null && !opts.length)} disabledReason={busy ? 'working…' : 'no channel holds Library members with a family label'}>Preview</Button>
        <Button variant="primary" size="sm" icon="check" testid="build-sequences-keep" loading={busy === 'keep'} onClick={keep}
          disabled={!!keepReason || !!busy} disabledReason={keepReason || 'working…'}>Keep {fresh ? fmtInt(fresh) : ''} these</Button>
      </div>
      {lastKept?.grouping && lastKept.kept.length > 0 && (() => {
        const first = lastKept.kept.find(k => k.created) ?? lastKept.kept[0]
        return (
          <div className="lib-cap" style={{ marginTop: 8 }} data-testid="build-sequences-kept">
            kept into grouping {lastKept.grouping} · {fmtInt(lastKept.families)} label-chain families{' · '}
            <Button variant="link" size="sm" testid="build-sequences-open-kept"
              onClick={() => navigate(`library/family/${first.key}?unit=sequences&grouping=${lastKept.grouping}`)}>open family {first.key.split('.').join(' → ')}</Button>
          </div>
        )
      })()}
      {err && <div className="lib-cap" role="alert" style={{ color: 'var(--red)', marginTop: 8 }} data-testid="build-sequences-error">{err}</div>}
      {preview && (
        <div className="stack" style={{ gap: 8, marginTop: 12 }} data-testid="build-sequences-preview-result">
          <span className="lib-cap" data-testid="build-sequences-summary">
            {preview.recording} · {preview.channel} · {fmtInt(preview.nMembers)} labelled members (labels from grouping {preview.motifGrouping ?? '—'})
            {' → '}{fmtInt(preview.sequences.length)} sequences in {fmtInt(preview.families.length)} label chains · {preview.ruleWords}
          </span>
          {preview.note && <span className="lib-cap" data-testid="build-sequences-note">{preview.note}</span>}
          {!!preview.families.length && (
            <div className="row" style={{ gap: 6, flexWrap: 'wrap' }} data-testid="build-sequences-families">
              {preview.families.map(f => <span key={f.key} className="k-badge t-purple" title={`label chain ${f.name}`}>{f.name} × {f.count}</span>)}
            </div>
          )}
          {!!preview.sequences.length && <>
            <SequenceStrips strips={preview.sequences} testid="build-sequences-strips" showChannel={false} />
            <LabelKey colours={preview.colours} labels={preview.sequences.flatMap(s => s.labels)} />
          </>}
          {preview.sequences.some(s => s.kept) && (
            <span className="lib-cap">{fmtInt(preview.sequences.filter(s => s.kept).length)} of these are already kept
              {' · '}<Button variant="link" size="sm" testid="build-sequences-open-atlas" onClick={() => navigate('library/atlas?unit=sequences')}>see their families</Button></span>
          )}
        </div>
      )}
    </div>
  )
}
