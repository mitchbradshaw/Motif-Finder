/* analyse.training — the training chain page (frames training-0, training-0b).
 * §6.1: this is a training chain because its last block emits a Model. P15: with the WindowSet source
 * the sliding-windows stage is *absent*, not greyed — the stages renumber and a callout states the
 * open question (backlog B7) instead of drawing a skipped row. */
import { useEffect, useState } from 'react'
import {
  Badge, BandStrip, Button, Callout, Chip, Icon, IconButton, InfoTip, Page, Trace, fmtInt,
  recordDemoWrite, useNotWired, useQueryState, useSim, type BadgeStatus,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getTrainingChain, type SourceKind, type TrainingChain } from '../api/training'
import {
  CLASS_COLOURS, ENCODE, ESTIMATES, NAME, RUN_STEPS, SIGNAL_FS, SPAN_H, SPAN_S, WINDOWS,
  chainStatuses, matrixValues, type TrainingBlock,
} from '../fixtures/training'
import { EncodingImage } from './Encoding'
import { Heat, LoadFailed, Loading, RunVeil, SaveTemplateModal, SendToReviewModal, TrainingToolbar, blanks } from './chrome'
import { markSimForced, useSourceQuery, useTrainingDraft, wasSimForced } from './draft'

export function ChainPage() {
  const [source] = useSourceQuery()
  const chain = useSourced(() => getTrainingChain(source), [source])
  return (
    <>
      <Header workspace="Analyse" page="Chain" search="Search spans, runs, families" demo={chain.source === 'demo'}
        subtitle={source === 'human-windows'
          ? 'illustrative · windows from the human-labelled set · not built yet'
          : 'training chain · terminal type Model → saves as a training template'} />
      <Page testid="training-chain">
        {chain.error ? <LoadFailed what="the training chain" error={chain.error} onRetry={chain.reload} />
          : !chain.data ? <Loading what="the chain" /> : <ChainBody data={chain.data} source={source} />}
      </Page>
    </>
  )
}

function ChainBody({ data, source }: { data: TrainingChain; source: SourceKind }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [, setSource] = useSourceQuery()
  const [draft, setDraft] = useTrainingDraft()
  const [popover, setPopover] = useQueryState('popover', '')
  const [modal, setModal] = useQueryState('modal', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [bypassed, setBypassed] = useState<Record<string, boolean>>({})

  const sim = useSim('analyse.training.run')
  useEffect(() => {
    if (stateQ === 'running') { sim.force({ status: 'running', steps: RUN_STEPS, step: 3, fraction: 0.62, startedAt: Date.now() }); markSimForced(true) }
    else if (stateQ === 'failed') { sim.force({ status: 'failed', steps: RUN_STEPS, step: 3, fraction: 0.6, finishedAt: Date.now(), error: 'encode stage failed (simulated): artifacts/encodings is not writable · the run stops rather than writing a partial image set' }); markSimForced(true) }
    else if (wasSimForced()) { sim.reset(); markSimForced(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const human = source === 'human-windows'
  const deleted = draft.deletedStage
  const chain = data.chain.filter(b => b.id !== deleted)
  const base = chainStatuses(draft.staleFrom, data.chain)
  const status: Record<string, BadgeStatus> = { ...base }
  /* The run steps are the numbered stages — the source row is not one of them, so a run step maps to
   * the stage at that position, never to the row at that position. */
  const stageRows = chain.filter(b => b.index != null)
  const atStep = (i: number) => stageRows[Math.min(i, stageRows.length - 1)]
  if (sim.status === 'running') stageRows.forEach((b, i) => { status[b.id] = i === sim.step ? 'running' : i < sim.step ? 'cached' : status[b.id] })
  const failedAt = sim.status === 'failed' ? atStep(sim.step) : null
  if (failedAt) {
    status[failedAt.id] = 'failed'
    stageRows.forEach((b, i) => { if (i < sim.step) status[b.id] = 'cached' })
  }
  if (deleted) status['model'] = 'invalid'
  if (!deleted && sim.status !== 'running' && sim.status !== 'failed' && status['matrix'] === 'cached') status['matrix'] = 'on cluster'
  /* A bypassed stage is paused, not cached: its output is the input passed straight through. */
  for (const id of Object.keys(bypassed)) if (bypassed[id] && status[id]) status[id] = 'paused'

  const runFailed = sim.status === 'failed'
  const failedLabel = failedAt ? `${String(failedAt.index).padStart(2, '0')} ${failedAt.label}` : '04 Encode'

  const deleteStage = (b: TrainingBlock) => {
    setDraft(d => ({ ...d, deletedStage: b.id, staleFrom: b.index ?? 1 }))
    recordDemoWrite('analyse', 'delete-stage', { chain: draft.name, stage: b.id })
    push({ text: `deleted ${b.label} · the junction into 05 Model is now invalid`, kind: 'error' })
  }
  const restore = () => { setDraft(d => ({ ...d, deletedStage: null })); push({ text: 'stage put back · the junction type-checks again' }) }

  const sendReview = (n: number) => setDraft(d => ({ ...d, queuedToReview: d.queuedToReview + n }))

  const trainInModels = () => {
    recordDemoWrite('models', 'add-training-job', { id: `t-${Math.floor(Math.random() * 900) + 100}`, template: draft.name, arms: 'cluster classes · manual verdicts (paired)' })
    navigate(`models/launch?template=${draft.name}`)
  }

  const stages = chain.filter(b => b.index != null).map(b => b.label)
  const primary = sim.busy
    ? <Button variant="danger" icon="stop" onClick={() => sim.cancel()} testid="cancel-run">Cancel</Button>
    : <Button variant="primary" icon="rocket" onClick={trainInModels} testid="train-in-models"
        disabled={!!deleted} disabledReason={deleted ? 'the chain has an invalid junction · put the stage back first' : undefined}>Train in Models</Button>

  return (
    <>
      <TrainingToolbar
        /* 0b is illustrative: there is no history to apply and nothing to import onto a source that is
         * not built, so the two secondary buttons are absent rather than dead (frame 0b). */
        minimal={human} showSave={human}
        name={draft.name} saved={draft.saved} onRename={v => setDraft(d => ({ ...d, name: v, saved: false }))}
        source={source} onSource={s => setSource(s === 'signal' ? null : s)}
        sourceOpen={popover === 'source'} onSourceToggle={() => setPopover(popover === 'source' ? null : 'source')}
        estimate={runFailed ? `run failed at ${failedLabel}` : sim.busy ? `${RUN_STEPS[sim.step] ?? ''} · running` : human ? 'illustrative · not built yet' : ESTIMATES.chain}
        estimateTone={runFailed ? 'amber' : human ? 'amber' : draft.staleFrom ? 'amber' : 'muted'}
        historyOpen={popover === 'history'} onHistory={() => setPopover(popover === 'history' ? null : 'history')}
        importOpen={popover === 'import'} onImport={() => setPopover(popover === 'import' ? null : 'import')}
        onSaveTemplate={() => setModal('save-template')}
        primary={primary}
      />

      {runFailed && (
        <Callout tone="red" icon="alert-triangle" title={`the run stopped at ${failedLabel}`}
          action={<Button size="sm" icon="refresh" onClick={() => { setStateQ(null); sim.reset() }} testid="clear-failure">Dismiss</Button>}>
          <span className="mono" data-testid="run-error">{sim.error}</span>
        </Callout>
      )}

      {human && (
        <Callout tone="amber" icon="help" title={data.human.b7.title} testid="b7-callout"
          action={<Badge tone="amber">{data.human.b7.tag}</Badge>}>
          {data.human.b7.body}
        </Callout>
      )}

      {deleted && (
        <Callout tone="red" icon="alert-triangle" title={`the junction into 05 Model does not type-check`}
          action={<Button size="sm" variant="primary" icon="undo" onClick={restore} testid="restore-stage">Put the stage back</Button>}>
          <span className="mono">a deleted stage leaves 05 Model expecting an Encoding nothing produces · the chain cannot run</span>
        </Callout>
      )}

      <div className="tr-rows tr-rel" data-testid="chain-rows">
        {sim.busy && <RunVeil label={`${RUN_STEPS[sim.step] ?? 'running'} · ${Math.round(sim.fraction * 100)} %`} fraction={sim.fraction} />}
        {chain.map((b, i) => (
          <div key={b.id}>
            <ChainRow block={b} status={status[b.id]} bypassed={!!bypassed[b.id]} human={human} invalid={!!deleted}
              onRestore={restore}
              onOpen={() => b.route && navigate(b.route)}
              onBypass={() => { setBypassed(x => ({ ...x, [b.id]: !x[b.id] })); push({ text: `${b.label} ${bypassed[b.id] ? 'back in the chain' : 'bypassed · its output passes straight through'}` }) }}
              onDuplicate={() => notWired(`duplicate the ${b.label} stage into the chain`)}
              onDelete={() => deleteStage(b)}
              data={data} />
            {i < chain.length - 1 && (
              <div className="tr-insert">
                <Button size="sm" variant="subtle" icon="plus" testid={`insert-${i}`}
                  onClick={() => notWired('insert a stage into the training chain (type-contract modal §6.4)')}>insert</Button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="k-card tr-foot" style={{ padding: '12px 14px' }} data-testid="chain-footer">
        <Chip tone="amber" icon="lock" testid="terminal-chip">terminal Model → training template <InfoTip title="Why this is a training chain (§6.1)">
          The chain's last block emits a `Model`, so it saves as a training template. Nothing switched a mode — the terminal type decides.
        </InfoTip></Chip>
        <span>
          <span className="fact" data-testid="footer-fact">{human ? `${fmtInt(data.human.windows)} windows · labels on every window` : `${fmtInt(WINDOWS.total)} windows · 6 classes`}</span>
          <br />
          <span className="sub" data-testid="footer-sub">{human ? data.human.footer.sub : `blocked split ${WINDOWS.params.split} · gap ${WINDOWS.params.gap_min} min · ${fmtInt(WINDOWS.unreviewed)} windows never human-reviewed`}</span>
        </span>
        <span className="k-spacer" />
        {human && <Chip tone="amber" icon="alert-triangle" testid="illustrative-chip">illustrative · out of scope</Chip>}
        {!human && (
          <Button icon="inbox" onClick={() => setModal('send-review')} testid="send-review"
            disabled={draft.queuedToReview > 0} disabledReason={draft.queuedToReview > 0 ? `${fmtInt(draft.queuedToReview)} windows are already queued this session` : undefined}>
            Send {fmtInt(WINDOWS.unreviewed)} unseen windows to Review
          </Button>
        )}
        <Button icon="download" onClick={() => notWired('export this run as a manifest + recipe bundle')} testid="export-run">Export run</Button>
      </div>

      <SaveTemplateModal open={modal === 'save-template'} onClose={() => setModal(null)} defaultName={draft.name} stages={stages}
        onSaved={n => setDraft(d => ({ ...d, name: n, saved: true }))} />
      <SendToReviewModal open={modal === 'send-review'} onClose={() => setModal(null)} onSent={sendReview} from={`${NAME} · training windows`} />
    </>
  )
}

/* ----------------------------------------------------------- one row ----------------------------------------------------------- */
function ChainRow({ block, status, bypassed, human, invalid, onOpen, onBypass, onDuplicate, onDelete, onRestore, data }: {
  block: TrainingBlock; status: BadgeStatus; bypassed: boolean; human: boolean; invalid: boolean
  onOpen: () => void; onBypass: () => void; onDuplicate: () => void; onDelete: () => void; onRestore: () => void; data: TrainingChain
}) {
  const isSource = block.index == null
  const broken = status === 'invalid'
  return (
    <div className={`tr-row${block.id === 'matrix' ? ' current' : ''}${bypassed ? ' bypassed' : ''}${broken ? ' invalid' : ''}`} data-testid={`chain-row-${block.id}`}>
      <div className="lhs">
        <span className="ttl">
          <Icon name="more" size={13} />
          {block.index != null && <span className="num">{String(block.index).padStart(2, '0')}</span>}
          {block.label}
        </span>
        <span className="meta"><Badge status={status} />{block.signature}</span>
        <span className="sum" data-testid={`chain-sum-${block.id}`}>
          {bypassed ? 'bypassed · its input passes straight through to the next stage' : block.summary}
        </span>
        {broken && (
          <span className="acts" data-testid={`row-fix-${block.id}`}>
            <Button size="sm" variant="primary" icon="undo" onClick={onRestore} testid={`row-restore-${block.id}`}>Put the stage back</Button>
            <Button size="sm" icon="sliders" onClick={onOpen} testid={`row-rebind-${block.id}`}>Open 05 and rebind its input</Button>
          </span>
        )}
        <span className="acts">
          <IconButton icon="sliders" label={`open ${block.label} settings`} onClick={onOpen} testid={`row-open-${block.id}`} />
          <IconButton icon="eye-off" label={bypassed ? `put ${block.label} back in the chain` : `bypass ${block.label}`} active={bypassed} onClick={onBypass} testid={`row-bypass-${block.id}`} />
          <IconButton icon="copy" label={`duplicate ${block.label}`} onClick={onDuplicate} testid={`row-duplicate-${block.id}`} />
          <IconButton icon="trash" label={`delete ${block.label}`} onClick={onDelete} disabled={isSource} disabledReason={isSource ? 'a chain needs a source block' : undefined} testid={`row-delete-${block.id}`} />
        </span>
      </div>
      <div className="rhs" data-testid={`row-plot-${block.id}`}>
        <RowPlot block={block} human={human} data={data} invalid={invalid} />
        <span className="cap">{block.caption}</span>
      </div>
    </div>
  )
}

function RowPlot({ block, human, data, invalid }: { block: TrainingBlock; human: boolean; data: TrainingChain; invalid: boolean }) {
  if (block.id === 'source' && human) {
    return (
      <div className="tr-ticks" data-testid="human-ticks" aria-label={`${data.human.sampled} of ${data.human.windows} windows, green interesting`}>
        {data.humanTicks.map((t, i) => <i key={i} style={{ background: t ? 'var(--green)' : '#d5d8dd' }} />)}
      </div>
    )
  }
  if (block.id === 'source') {
    return <Trace values={data.signal.values} fs={SIGNAL_FS} yDomain={data.signal.yDomain} timeUnit="h" height={56} ground="white" crosshair={false} unitLabel={false} zeroLine={false} />
  }
  if (block.id === 'windows') {
    return (
      <BandStrip domain={[0, SPAN_S]} timeUnit="h" rowHeight={16} labelWidth={0} testid="row-split-strip"
        rows={[{ label: '', segments: data.windows.blocks.map(b => ({ start: b.start_h * 3600, end: b.end_h * 3600, kind: b.kind, label: b.kind === 'validation' ? 'val' : b.kind })) }]} />
    )
  }
  if (block.id === 'matrix') {
    const ids = ['c22_01', 'c22_07', 'entropy_sample', 'wavelet_b2']
    return <Heat rows={blanks(ids.length)} values={matrixValues(ids)} cellHeight={13} rowLabelWidth={0} testid="row-matrix" />
  }
  if (block.id === 'cluster') {
    return (
      <BandStrip domain={[0, SPAN_S]} timeUnit="h" rowHeight={18} labelWidth={0} testid="row-occupancy"
        rows={[{ label: '', segments: data.occupancy.map(o => ({ start: o.start_h * 3600, end: o.end_h * 3600, colour: CLASS_COLOURS[o.klass], label: o.klass })) }]} />
    )
  }
  if (block.id === 'encode') {
    return (
      <div className="tr-encode-row">
        {data.encodings.map(e => (
          <span key={e.id} className={`tr-thumb${e.included ? '' : ' off'}`} data-testid={`row-encoding-${e.id}`}>
            <EncodingImage kind={e.id} window={ENCODE.window} size={62} />
            <span className="cap">{e.label}{e.included ? '' : ' ✕'}</span>
          </span>
        ))}
      </div>
    )
  }
  return (
    <div className="tr-handoff" data-testid="model-handoff">
      <Icon name="rocket" size={20} />
      <span className="txt">
        <b>{human ? data.human.handoff.title : 'Analyse builds this template · Models trains it across channels'}</b>
        <span>{human ? data.human.handoff.sub : block.caption}</span>
      </span>
      {/* 0b has no backlog to trial and no local channel to trial it on: only the hand-off stays. */}
      {!human && (
        <Button icon="flask" onClick={() => navigate('analyse/training/block/5?focus=trial')} testid="trial-job"
          disabled={invalid} disabledReason={invalid ? 'the chain has an invalid junction · put the deleted stage back first' : undefined}>
          Trial job on this channel
        </Button>
      )}
      <Button variant="primary" icon="rocket" onClick={() => navigate('models/launch?template=cnn_windows_v3')} testid="handoff-train"
        disabled={invalid} disabledReason={invalid ? 'the chain has an invalid junction · put the deleted stage back first' : undefined}>
        Train in Models
      </Button>
    </div>
  )
}
