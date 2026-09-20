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
import {
  ESTIMATES, RUN_STEPS, SIGNAL_FS, SPAN_H, SPAN_S, WINDOWS, chainStatuses, droppedAtGaps, droppedByGapChange,
  splitGaps, splitLayout, type SplitBlock, type TrainingBlock,
} from '../fixtures/training'
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
      /* The frame's pending change is gap 5 → 10, so the *applied* set is the one with the old gap —
       * setting only `pending` left the two equal and the bar read "no unapplied changes". */
      setDraft(d => ({
        ...d,
        windows: {
          applied: { ...d.windows.applied, gap_min: WINDOWS.params.previousGap_min },
          pending: { ...d.windows.applied, gap_min: WINDOWS.params.gap_min },
        },
        staleFrom: 1,
      }))
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
  const leaking = splitKind === 'random'

  /* The gap field keeps its own raw entry: `onValid` never fires for a rejected number, so without this
   * the page kept the last good gap and the checks card, the estimate and Apply all carried on as if
   * nothing had been typed (P12 is exactly this guard). */
  const [gapEntry, setGapEntry] = useState<{ raw: string; reason: string | null } | null>(null)
  const gapReason = gapEntry?.reason ?? null
  const gapShown = gapEntry ? gapEntry.raw : String(p.gap_min)
  const gapInvalid = !!gapReason

  /* The split geometry is the two parameters that shape it — change either and the bands, the window
   * counts and the verdict bars move with it. */
  const layout = splitLayout(p.split, p.blocks)
  const nBlocks = layout.blocks.length
  const dropped = droppedAtGaps(p.gap_min, nBlocks)

  /* What is actually unapplied, field by field: the bar used to describe a gap change whatever changed. */
  const a0 = draft.windows.applied
  const changes: string[] = []
  if (p.gap_min !== a0.gap_min) changes.push(`gap ${a0.gap_min} → ${p.gap_min} min drops ${droppedByGapChange(a0.gap_min, p.gap_min, nBlocks)} windows`)
  if (p.split !== a0.split) changes.push(`split ${a0.split} → ${p.split}`)
  if (p.blocks !== a0.blocks) changes.push(`blocks ${a0.blocks} → ${p.blocks}`)
  if (p.seed !== a0.seed) changes.push(`seed ${a0.seed} → ${p.seed}`)
  if (p.length_min !== a0.length_min) changes.push(`window ${a0.length_min} → ${p.length_min} min`)
  if (p.stride_min !== a0.stride_min) changes.push(`stride ${a0.stride_min} → ${p.stride_min} min`)
  if (p.splitKind !== a0.splitKind) changes.push(`${a0.splitKind} → ${p.splitKind} split`)

  const chain = data.chain
  const status: Record<string, BadgeStatus> = chainStatuses(pending ? 1 : draft.staleFrom, chain)
  if (sim.status === 'running') chain.forEach((b, i) => { if (b.index != null) status[b.id] = i - 1 === sim.step ? 'running' : i - 1 < sim.step ? 'cached' : status[b.id] })

  const apply = () => {
    setStateQ(null)
    setDraft(d => ({ ...d, windows: { applied: live(d.windows), pending: null }, staleFrom: null }))
    recordDemoWrite('analyse', 'apply-block', { block: '01 Sliding windows', gap_min: p.gap_min, split: splitKind })
    sim.start({ steps: RUN_STEPS, stepMs: 600 })
  }
  const revert = () => {
    setStateQ(null); setSplitQ(null); setGapEntry(null)
    setDraft(d => ({ ...d, windows: { ...d.windows, pending: null } }))
  }
  const atRecommended = !pending && splitKind === 'blocked'

  const applyReason = gapInvalid ? `the gap is ${gapShown} min: ${gapReason} — windows either side would share samples`
    : sim.busy ? 'the chain is already running' : undefined

  /* One action, one label: the toolbar and the bar were offering "Apply & re-run from 01" and
   * "Re-run from 04" for the same page state. */
  const staleLabel = !pending && draft.staleFrom ? String(draft.staleFrom).padStart(2, '0') : null
  const primaryLabel = pending ? 'Apply & re-run from 01' : staleLabel ? `Re-run from ${staleLabel}` : 'Apply & re-run from 01'
  const primaryReason = applyReason ?? (!pending && !staleLabel ? 'no unapplied changes' : undefined)

  const primary = sim.busy
    ? <Button variant="danger" icon="stop" onClick={() => sim.cancel()} testid="cancel-run">Cancel</Button>
    : <Button variant="primary" icon="refresh" onClick={apply} disabled={!!primaryReason}
        disabledReason={primaryReason} testid="apply-rerun-top">{primaryLabel}</Button>

  return (
    <BlockFrame
      chain={chain} current="windows" status={status} source={source} onSource={s => setSource(s === 'signal' ? null : s)}
      name={draft.name} saved={draft.saved} onRename={v => setDraft(d => ({ ...d, name: v, saved: false }))}
      estimate={gapInvalid ? `gap ${gapShown} min · ${gapReason}` : pending ? `${changes[0] ?? 'edited'} · 01 → 05 stale` : ESTIMATES.chain}
      estimateTone={gapInvalid || pending ? 'amber' : 'muted'}
      onBack={() => navigate('analyse/training')} onNavigate={b => b.route && navigate(b.route)}
      onAddStage={() => notWired('insert a stage into the training chain (type-contract modal §6.4)')}
      primary={primary}
      footer={
        <UnappliedBar pending={pending} stage="01" count={changes.length} label={primaryLabel} applyReason={primaryReason}
          why={pending ? `${changes.join(' · ')} · 01 → 05 go stale`
            : draft.staleFrom ? '04 and 05 are stale from an earlier edit' : 'the window set on screen is the one the last run used'}
          staleLabel={staleLabel}
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
              {leaking
                ? <BandStrip domain={[0, SPAN_S]} timeUnit="h" rowHeight={22} labelWidth={0} testid="split-strip"
                    rows={[{ label: '', segments: layout.blocks.flatMap((b, i) => shuffleSegments(b.start_h, b.end_h, i))
                      .map(g => ({ ...g, start: g.start * 3600, end: g.end * 3600 })) }]} />
                : <SplitStrip blocks={layout.blocks} dropped={dropped} />}
              <Trace values={data.signal.values} fs={SIGNAL_FS} yDomain={data.signal.yDomain} timeUnit="h" height={90} ground="white" />
              <Legend items={[
                { label: 'train', colour: SPLIT_COLOUR.train }, { label: 'validation', colour: SPLIT_COLOUR.validation },
                { label: 'test', colour: SPLIT_COLOUR.test }, { label: 'gap', colour: '#e5a24d' },
                { label: `windows dropped at gaps (${dropped})`, colour: 'var(--red)' },
              ]} />
            </div>
          </SectionCard>

          <div className="tr-grid2">
            <SectionCard title="At a boundary" info="The close-up shows why the gap is a leakage guard, not a tidiness rule."
              subtitle={`${data.windows.boundary.from_h} – ${data.windows.boundary.to_h} h`} testid="boundary-card">
              <Boundary data={data} gapMin={gapInvalid ? Number(gapShown) || 0 : p.gap_min} />
              <span className="tr-bounds-cap" data-testid="boundary-caption">{data.windows.boundary.note}</span>
              <Callout tone={gapInvalid ? 'red' : 'green'} icon={gapInvalid ? 'alert-triangle' : 'check-circle'} testid="boundary-verdict">
                {gapInvalid
                  ? `gap ${gapShown} min is under the ${p.length_min} min window length — a training window would share samples with a validation window`
                  : data.windows.boundary.verdict}
              </Callout>
            </SectionCard>

            <SectionCard title="Human verdicts per split" info="Cluster labels exist for every window; a manual verdict exists only where somebody looked."
              testid="verdicts-card">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {layout.verdicts.map(v => (
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
                hint={gapInvalid ? undefined : `≥ window length · was ${a0.gap_min}`}
                error={gapInvalid ? `must be at least the ${p.length_min} min window length` : undefined}>
                <NumberField value={p.gap_min} onValid={v => { setGapEntry(null); setP({ gap_min: v }) }}
                  onChange={(raw, reason) => setGapEntry({ raw, reason })}
                  min={0} max={240} integer unit="min" width={130}
                  changed={p.gap_min !== a0.gap_min} validate={n => n < p.length_min ? `at least the ${p.length_min} min window length` : null} testid="gap-field" />
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
            {/* A check reads the settings on screen, not a fixed list: a red gap field or a random
                split has to turn its own tick over, or the card contradicts the page. */}
            <Checklist testid="window-checks" items={data.checks.map(c => {
              if (c.id === 'gap') return {
                id: c.id, label: `gap ${gapShown} min ${gapInvalid ? '<' : '≥'} window ${p.length_min} min`,
                state: gapInvalid ? 'fail' as const : 'pass' as const,
              }
              if (c.id === 'boundary') return {
                id: c.id,
                label: leaking ? 'windows DO cross split boundaries — a random split interleaves them' : c.label,
                state: leaking ? 'fail' as const : 'pass' as const,
              }
              return { id: c.id, label: c.label, state: c.state }
            })} />
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
              {fmtInt(WINDOWS.total)} windows · {splitKind === 'random' ? 'random split' : 'blocked split'} {p.split} · {nBlocks} blocks · gap {gapShown} min
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

export const SPLIT_COLOUR: Record<string, string> = { train: '#a8c1ec', validation: '#fdc77e', test: '#86d69e' }

/** The split strip the frame draws: the block's own label inside the band, a red mark on every break
 * where windows are dropped, and a tick row underneath so a window is a thing you can see. */
function SplitStrip({ blocks, dropped }: { blocks: SplitBlock[]; dropped: number }) {
  const pct = (h: number) => `${(h / SPAN_H) * 100}%`
  const gaps = splitGaps(blocks)
  const perGap = Math.round(dropped / Math.max(1, gaps.length))
  const TICKS = 120
  const inGap = (h: number) => gaps.some(([a, b]) => h >= a && h <= b)
  return (
    <div className="tr-split" data-testid="split-strip">
      <div className="bands">
        {blocks.map((b, i) => (
          <span key={i} className={`band ${b.kind}`} data-testid={`split-band-${i}`}
            style={{ left: pct(b.start_h), width: pct(b.end_h - b.start_h), background: SPLIT_COLOUR[b.kind] }}
            title={`${b.label} · ${b.start_h}–${b.end_h} h`}>
            {/* a clipped half-word is worse than none: narrow blocks keep the label in the tooltip */}
            {(b.end_h - b.start_h) / SPAN_H > 0.1 ? b.label : ''}
          </span>
        ))}
        {gaps.map(([a, b], i) => (
          <span key={`g${i}`} className="drop" data-testid={`split-drop-${i}`}
            style={{ left: pct(a + (b - a) / 2 - 0.06), width: pct(0.12) }}
            title={`${perGap} windows dropped at this break · gap ${a.toFixed(1)}–${b.toFixed(1)} h`} />
        ))}
      </div>
      <div className="ticks" data-testid="window-ticks" aria-label={`${TICKS} sampled windows across the span`}>
        {Array.from({ length: TICKS }, (_, i) => {
          const h = ((i + 0.5) / TICKS) * SPAN_H
          return <i key={i} className={inGap(h) ? 'drop' : undefined} style={{ left: `${(i / TICKS) * 100}%` }} />
        })}
      </div>
      <span className="striptitle">one tick per sampled window · red where a break drops them ({dropped})</span>
    </div>
  )
}

/** The 15.2 - 16.4 h close-up: window bars marching left to right across the break, one per row, so the
 * 50 % overlap between neighbours is the thing you see. The dropped ones are red. */
function Boundary({ data, gapMin }: { data: WindowsBlock; gapMin: number }) {
  const b = data.windows.boundary
  const lo = 14.55, hi = 16.75
  const x = (h: number) => `${((h - lo) / (hi - lo)) * 100}%`
  const gapEnd = b.from_h + Math.max(0, gapMin) / 60
  const rows = data.boundary
  return (
    <div className="tr-bounds" data-testid="boundary-plot" style={{ height: 24 + rows.length * 13 }}>
      <span className="gapband amber" style={{ left: x(b.from_h), width: `${((Math.max(gapEnd, b.from_h + 0.02) - b.from_h) / (hi - lo)) * 100}%` }} />
      <span className="lab" style={{ left: 4, top: 4 }}>train</span>
      <span className="lab" style={{ left: x(b.from_h), top: 4 }}>gap {gapMin} min</span>
      <span className="lab" style={{ left: x(b.to_h), top: 4 }}>val</span>
      {rows.map((w, i) => (
        <span key={i} className="bar" data-testid={`boundary-bar-${i}`}
          style={{
            left: x(w.start_h), width: `${((w.end_h - w.start_h) / (hi - lo)) * 100}%`, top: 20 + i * 13,
            background: w.dropped ? 'var(--red)' : w.side === 'val' ? SPLIT_COLOUR.validation : SPLIT_COLOUR.train,
          }} title={`${w.start_h.toFixed(2)}-${w.end_h.toFixed(2)} h · ${w.dropped ? 'dropped at the gap' : w.side}`} />
      ))}
    </div>
  )
}
