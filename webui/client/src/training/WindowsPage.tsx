/* analyse.training.windows — 01 Sliding windows (frame training-01). `Signal → WindowSet` (§6.8, §6.9).
 * P12 lives here as parameters, not prose: the gap between blocks is editable and validated ≥ one window
 * length, the random split is selectable but marked as leaking, and the checks card says what holds. */
import { useEffect, useState } from 'react'
import {
  Badge, BandStrip, Button, Callout, Checklist, Dropdown, Field, Icon, InfoTip, Legend, NumberField, Page,
  SectionCard, Seg, Slider, Trace, fmtInt, fmtPct, recordDemoWrite, useNotWired, useQueryState, useSim,
  type BadgeStatus,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getWindowsBlock, type WindowsBlock } from '../api/training'
import { ESTIMATES, RUN_STEPS, SIGNAL_FS, SPAN_H, WINDOWS, chainStatuses, type TrainingBlock } from '../fixtures/training'
import { BlockFrame, LoadFailed, Loading, RunVeil, SaveWindowSetModal, SendToReviewModal, UnappliedBar } from './chrome'
import { isPending, live, markSimForced, useSourceQuery, useTrainingDraft, wasSimForced, type WindowParams } from './draft'

export function WindowsPage() {
  const block = useSourced(() => getWindowsBlock(), [])
  return (
    <>
      <Header workspace="Analyse" page="01 Sliding windows" search="Search spans, runs, families" demo={block.source === 'demo'}
        subtitle="windows and the train / val / test split · leakage guarded here" />
      <Page testid="training-windows">
        {block.error ? <LoadFailed what="the sliding-windows block" error={block.error} onRetry={block.reload} />
          : !block.data ? <Loading what="the window set" /> : <Body data={block.data} />}
      </Page>
    </>
  )
}

function Body({ data }: { data: WindowsBlock }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [source, setSource] = useSourceQuery()
  const [draft, setDraft] = useTrainingDraft()
  const [modal, setModal] = useQueryState('modal', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [splitQ, setSplitQ] = useQueryState('split', '')

  /* `?state=edited` is the frame's pending state: the route itself opens clean (see the inventory's
   * conflicts note — the frame's chain row already shows the change as applied). */
  useEffect(() => {
    if (stateQ === 'edited' && !draft.windows.pending) {
      setDraft(d => ({ ...d, windows: { ...d.windows, pending: { ...d.windows.applied, gap_min: 10 } }, staleFrom: 1 }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const sim = useSim('analyse.training.run')
  useEffect(() => {
    if (stateQ === 'running') { sim.force({ status: 'running', steps: RUN_STEPS, step: 0, fraction: 0.28, startedAt: Date.now() }); markSimForced(true) }
    else if (wasSimForced() && stateQ !== 'running') { sim.reset(); markSimForced(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const p = live(draft.windows)
  const pending = isPending(draft.windows)
  const setP = (patch: Partial<WindowParams>) =>
    setDraft(d => ({ ...d, windows: { ...d.windows, pending: { ...live(d.windows), ...patch } }, staleFrom: 1 }))

  const splitKind = (splitQ === 'random' ? 'random' : p.splitKind) as 'blocked' | 'random'
  const gapInvalid = p.gap_min < p.length_min
  const leaking = splitKind === 'random'

  const chain = data.chain
  const status: Record<string, BadgeStatus> = chainStatuses(pending || draft.staleFrom ? 1 : draft.staleFrom, chain)
  if (sim.status === 'running') chain.forEach((b, i) => { if (b.index != null) status[b.id] = i - 1 === sim.step ? 'running' : i - 1 < sim.step ? 'cached' : status[b.id] })

  const apply = () => {
    setStateQ(null)
    setDraft(d => ({ ...d, windows: { applied: live(d.windows), pending: null }, staleFrom: null }))
    recordDemoWrite('analyse', 'apply-block', { block: '01 Sliding windows', gap_min: p.gap_min, split: splitKind })
    sim.start({ steps: RUN_STEPS, stepMs: 600 })
  }
  const revert = () => {
    setStateQ(null); setSplitQ(null)
    setDraft(d => ({ ...d, windows: { ...d.windows, pending: null } }))
  }
  const atRecommended = !pending && splitKind === 'blocked'

  const applyReason = gapInvalid ? `gap ${p.gap_min} min is under the ${p.length_min} min window length — windows either side would share samples`
    : sim.busy ? 'the chain is already running' : undefined

  const primary = sim.busy
    ? <Button variant="danger" icon="stop" onClick={() => sim.cancel()} testid="cancel-run">Cancel</Button>
    : <Button variant="primary" icon="refresh" onClick={apply} disabled={!!applyReason || (!pending && !draft.staleFrom)}
        disabledReason={applyReason ?? (!pending && !draft.staleFrom ? 'no unapplied changes' : undefined)} testid="apply-rerun-top">Apply &amp; re-run from 01</Button>

  const dropped = pending ? WINDOWS.droppedByPendingGap : WINDOWS.droppedAtGaps

  return (
    <BlockFrame
      chain={chain} current="windows" status={status} source={source} onSource={s => setSource(s === 'signal' ? null : s)}
      name={draft.name} saved={draft.saved} onRename={v => setDraft(d => ({ ...d, name: v, saved: false }))}
      estimate={pending ? `gap ${WINDOWS.params.previousGap_min} → ${p.gap_min} min · 01 → 05 stale` : ESTIMATES.chain}
      estimateTone={pending ? 'amber' : 'muted'}
      onBack={() => navigate('analyse/training')} onNavigate={b => b.route && navigate(b.route)}
      onAddStage={() => notWired('insert a stage into the training chain (type-contract modal §6.4)')}
      primary={primary}
      footer={
        <UnappliedBar pending={pending} stage="01"
          why={pending ? `gap ${WINDOWS.params.previousGap_min} → ${p.gap_min} min drops ${dropped} windows · 01 → 05 go stale`
            : draft.staleFrom ? '04 and 05 are stale from an earlier edit' : 'the window set on screen is the one the last run used'}
          staleLabel={!pending && draft.staleFrom ? '04' : null}
          revertReason={atRecommended ? 'already at the recommended values' : undefined}
          onRevert={revert} onApply={apply} busy={sim.busy} onCancel={() => sim.cancel()} />
      }
    >
      {leaking && (
        <Callout tone="red" icon="alert-triangle" title="a random split leaks (P12)" testid="leak-callout"
          action={<Button size="sm" onClick={() => { setSplitQ(null); setP({ splitKind: 'blocked' }) }} testid="back-to-blocked">Back to blocked by time</Button>}>
          {data.randomWarning}
        </Callout>
      )}

      <div className="tr-cols wide-right">
        <div className="tr-stack">
          <SectionCard number={1} title="Sliding windows" subtitle="Signal → WindowSet" flush={false} testid="windows-card"
            actions={
              <div className="tr-row-flex">
                <Seg size="sm" ariaLabel="split kind" value={splitKind} onChange={v => { setSplitQ(v === 'blocked' ? null : v); setP({ splitKind: v as 'blocked' | 'random' }) }}
                  options={[{ value: 'blocked', label: 'blocked by time' }, { value: 'random', label: 'random ✕' }]} testid="split-seg" />
                <InfoTip title="Why blocked by time (P12)">{data.randomWarning}</InfoTip>
              </div>
            }>
            <div className="tr-rel">
              {sim.busy && <RunVeil label={`${RUN_STEPS[sim.step] ?? 'running'} · ${Math.round(sim.fraction * 100)} %`} fraction={sim.fraction} />}
              <BandStrip domain={[0, SPAN_H]} timeUnit="h" rowHeight={22} labelWidth={0} testid="split-strip"
                rows={[{ label: '', segments: leaking
                  ? data.windows.blocks.flatMap((b, i) => shuffleSegments(b.start_h, b.end_h, i))
                  : data.windows.blocks.map(b => ({ start: b.start_h, end: b.end_h, kind: b.kind, label: b.label })) }]} />
              <Trace values={data.signal.values} fs={SIGNAL_FS} yDomain={data.signal.yDomain} timeUnit="h" height={90} ground="white" />
              <Legend items={[
                { label: 'train', colour: 'var(--blue)' }, { label: 'validation', colour: '#c88ce0' },
                { label: 'test', colour: 'var(--green)' }, { label: 'gap', colour: '#e5a24d' },
                { label: `windows dropped at gaps (${dropped})`, colour: 'var(--red)' },
              ]} />
            </div>
          </SectionCard>

          <div className="tr-grid2">
            <SectionCard title="At a boundary" info="The close-up shows why the gap is a leakage guard, not a tidiness rule."
              subtitle={`${data.windows.boundary.from_h} – ${data.windows.boundary.to_h} h`} testid="boundary-card">
              <Boundary data={data} gapMin={p.gap_min} />
              <Callout tone={gapInvalid ? 'red' : 'green'} icon={gapInvalid ? 'alert-triangle' : 'check-circle'} testid="boundary-verdict">
                {gapInvalid
                  ? `gap ${p.gap_min} min is under the ${p.length_min} min window length — a training window would share samples with a validation window`
                  : data.windows.boundary.verdict}
              </Callout>
            </SectionCard>

            <SectionCard title="Human verdicts per split" info="Cluster labels exist for every window; a manual verdict exists only where somebody looked."
              testid="verdicts-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {data.windows.verdictsPerSplit.map(v => (
                  <div key={v.split} data-testid={`verdict-${v.split}`}>
                    <div className="tr-row-flex" style={{ justifyContent: 'space-between' }}>
                      <span className="tr-mono"><b>{v.split}</b> <span className="tr-muted">{fmtInt(v.windows)} windows</span></span>
                      <span className="tr-mono tr-muted">{v.reviewed} reviewed · {v.interesting} interesting</span>
                    </div>
                    <div style={{ height: 8, borderRadius: 4, background: 'var(--grey-100)', overflow: 'hidden', marginTop: 4 }}>
                      <span style={{ display: 'block', width: fmtPct(v.reviewed / v.windows), height: '100%', background: 'var(--green)' }} />
                    </div>
                  </div>
                ))}
                <Callout tone="grey" icon="info" testid="verdict-note">{data.windows.verdictNote}</Callout>
              </div>
            </SectionCard>
          </div>
        </div>

        <div className="tr-stack">
          <SectionCard title="Parameters" actions={<span className="tr-mono tr-small" style={{ color: 'var(--green)' }}>| recommended</span>} testid="parameters-card">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <Field label="windows from" info="P15 · a saved window set would make this stage redundant, so it would be absent rather than greyed.">
                <Seg size="sm" value={p.from === 'sliding signal span' ? 'sliding' : 'set'} ariaLabel="windows from"
                  onChange={v => v === 'set' ? navigate('analyse/training?source=human-windows') : setP({ from: 'sliding signal span' })}
                  options={[{ value: 'sliding', label: 'sliding over the source' }, { value: 'set', label: 'human-labelled window set' }]} testid="windows-from" />
              </Field>
              <div className="tr-grid2">
                <Field label="window length" hint="= current CNN input" info="The image encoders downstream expect exactly this many samples.">
                  <Slider value={p.length_min} onChange={v => setP({ length_min: v })} min={2} max={30} step={1} format={v => `${v} min`} ariaLabel="window length" testid="window-length" />
                </Field>
                <Field label="stride" hint={`= recommended · ${Math.round((1 - p.stride_min / p.length_min) * 100)} % overlap`}>
                  <Slider value={p.stride_min} onChange={v => setP({ stride_min: v })} min={1} max={p.length_min} step={1} format={v => `${v} min`} ariaLabel="stride" testid="stride" />
                </Field>
              </div>
              <Field label="gap between blocks" info="P12 · the guard that keeps a validation window from sharing samples with a training window."
                hint={gapInvalid ? undefined : `≥ window length · was ${WINDOWS.params.previousGap_min}`}
                error={gapInvalid ? `must be at least the ${p.length_min} min window length` : undefined}>
                <NumberField value={p.gap_min} onValid={v => setP({ gap_min: v })} min={0} max={240} integer unit="min" width={130}
                  changed={pending} validate={n => n < p.length_min ? `at least the ${p.length_min} min window length` : null} testid="gap-field" />
              </Field>
              <div className="tr-grid2">
                <Field label="split"><Dropdown value={p.split} onChange={v => setP({ split: v })} block testid="split-ratio"
                  options={[{ value: '70 / 15 / 15', label: '70 / 15 / 15' }, { value: '60 / 20 / 20', label: '60 / 20 / 20' }, { value: '80 / 10 / 10', label: '80 / 10 / 10' }]} /></Field>
                <Field label="blocks"><Dropdown value={p.blocks} onChange={v => setP({ blocks: v })} block testid="blocks"
                  options={[{ value: '4 contiguous', label: '4 contiguous' }, { value: '6 contiguous', label: '6 contiguous' }, { value: '2 contiguous', label: '2 contiguous', disabled: true, reason: 'two blocks cannot hold train, validation and test without a repeat' }]} /></Field>
              </div>
              <Field label="seed"><Dropdown value={p.seed} onChange={v => setP({ seed: v })} block testid="seed"
                options={[{ value: '17', label: '17' }, { value: '42', label: '42' }, { value: '2026', label: '2026' }]} /></Field>
            </div>
          </SectionCard>

          <SectionCard title="Checks" testid="checks-card">
            <Checklist testid="window-checks" items={data.checks.map(c => ({
              id: c.id,
              label: c.id === 'gap' ? `gap ${p.gap_min} min ${gapInvalid ? '<' : '≥'} window ${p.length_min} min` : c.label,
              state: c.id === 'gap' ? (gapInvalid ? 'fail' as const : 'pass' as const) : c.state,
            }))} />
            <div style={{ marginTop: 10 }}>
              <Button icon="inbox" block onClick={() => setModal('send-review')} testid="send-review"
                disabled={draft.queuedToReview > 0} disabledReason={draft.queuedToReview > 0 ? `${fmtInt(draft.queuedToReview)} windows are already queued this session` : undefined}>
                Send {fmtInt(WINDOWS.unreviewed)} unseen windows to Review
              </Button>
              <div className="tr-muted tr-small tr-mono" style={{ marginTop: 5 }} data-testid="queue-cap">Review queue holds up to {fmtInt(WINDOWS.queueCap)} windows</div>
            </div>
          </SectionCard>

          <SectionCard title="Window set" subtitle="P18 · reusable in Models across channels" testid="window-set-card">
            <div className="tr-row-flex">
              <Button icon="save" onClick={() => setModal('save-window-set')} testid="save-window-set">Save window set</Button>
              {draft.savedWindowSets.length > 0 && <Badge status="new">{draft.savedWindowSets[0]}</Badge>}
            </div>
            <div className="tr-muted tr-small tr-mono" style={{ marginTop: 6 }}>
              {fmtInt(WINDOWS.total)} windows · blocked split {p.split} · gap {p.gap_min} min
            </div>
          </SectionCard>
        </div>
      </div>

      <SendToReviewModal open={modal === 'send-review'} onClose={() => setModal(null)}
        onSent={n => setDraft(d => ({ ...d, queuedToReview: d.queuedToReview + n }))} from="cnn_windows_v3 · 01 Sliding windows" />
      <SaveWindowSetModal open={modal === 'save-window-set'} onClose={() => setModal(null)}
        onSaved={id => { setDraft(d => ({ ...d, savedWindowSets: [id, ...d.savedWindowSets] })) }} />
    </BlockFrame>
  )
}

/** The random-split illustration: the same span cut into interleaved pieces, which is exactly the leak. */
function shuffleSegments(a: number, b: number, i: number) {
  const kinds = ['train', 'validation', 'test'] as const
  const n = 6
  const w = (b - a) / n
  return Array.from({ length: n }, (_, k) => ({ start: a + k * w, end: a + (k + 1) * w, kind: kinds[(k + i) % 3] }))
}

/** The 15.2 – 16.4 h close-up: window bars either side of the gap, the dropped ones in red. */
function Boundary({ data, gapMin }: { data: WindowsBlock; gapMin: number }) {
  const b = data.windows.boundary
  const lo = 14.55, hi = 16.75
  const x = (h: number) => `${((h - lo) / (hi - lo)) * 100}%`
  const gapEnd = b.from_h + gapMin / 60
  return (
    <div className="tr-bounds" data-testid="boundary-plot" style={{ height: 118 }}>
      <span className="gapband" style={{ left: x(b.from_h), width: `${((Math.min(gapEnd, b.to_h) - b.from_h) / (hi - lo)) * 100}%` }} />
      <span className="lab" style={{ left: 4, top: 4 }}>train</span>
      <span className="lab" style={{ left: x(b.from_h), top: 4 }}>gap {gapMin} min</span>
      <span className="lab" style={{ left: x(b.to_h), top: 4 }}>val</span>
      {data.boundary.map((w, i) => (
        <span key={i} className="bar" data-testid={`boundary-bar-${i}`}
          style={{
            left: x(w.start_h), width: `${((w.end_h - w.start_h) / (hi - lo)) * 100}%`, top: 22 + i * 9,
            background: w.dropped ? 'var(--red)' : w.side === 'val' ? '#c88ce0' : 'var(--blue)',
          }} title={`${w.start_h.toFixed(2)}–${w.end_h.toFixed(2)} h · ${w.dropped ? 'dropped at the gap' : w.side}`} />
      ))}
      <span className="lab" style={{ left: 4, bottom: 3 }}>{b.note}</span>
    </div>
  )
}
