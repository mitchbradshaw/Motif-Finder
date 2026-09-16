/* analyse.training.model — 05 Model (frame training-4). `Encoding + labels → Model`.
 * The terminal block. It does not train the real model: it says what a trial run on THIS channel would
 * cost, what labels it would learn from, and what stands in the way — then hands the template to Models,
 * which is where a template is applied across channels and recordings (P11). */
import { useEffect, useState } from 'react'
import {
  Badge, Button, Callout, Checkbox, Checklist, Chip, CodeBlock, Dropdown, Icon, InfoTip, Page,
  RadioCards, SectionCard, fmtInt, recordDemoWrite, useNotWired, useQueryState, type BadgeStatus,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getModelBlock, type ModelBlock } from '../api/training'
import { CHANNEL, ESTIMATES, TRIAL, WINDOWS, chainStatuses, trialScript } from '../fixtures/training'
import { BlockFrame, LoadFailed, Loading, SaveTemplateModal, SendToReviewModal } from './chrome'
import { live, useSourceQuery, useTrainingDraft, type ModelParams } from './draft'

export function ModelPage() {
  const [source] = useSourceQuery()
  const block = useSourced(() => getModelBlock(source), [source])
  return (
    <>
      <Header workspace="Analyse" page="05 Model" search="Search spans, runs, families" demo={block.source === 'demo'}
        subtitle="build the training template · trial it here · train it in Models" />
      <Page testid="training-model">
        {block.error ? <LoadFailed what="the model block" error={block.error} onRetry={block.reload} />
          : !block.data ? <Loading what="the model block" /> : <Body data={block.data} />}
      </Page>
    </>
  )
}

/* The eight training parameters, each a Dropdown with one alternative, so nothing on the page is a dead
 * control. The alternatives are the ones the spec's model stage actually offers. */
const PARAM_FIELDS: { key: keyof ModelParamsUI; label: string; info: string; options: string[] }[] = [
  { key: 'architecture', label: 'architecture', info: 'the classifier trained on the encoded images. B0 is the smallest of the family and the one the registered models use.', options: ['EfficientNet-B0', 'EfficientNet-B2', 'ResNet-18'] },
  { key: 'input', label: 'input', info: 'the channels of the image the network sees — one per ticked encoding in 04, at the encoder set’s image size.', options: ['GASF + GADF + RP · 224', 'GASF + GADF · 224', 'GASF only · 224'] },
  { key: 'epochs', label: 'epochs', info: 'early stopping watches the validation metric and keeps the best epoch, so this is a ceiling, not a promise.', options: ['30 · early stop', '60 · early stop', '30 · fixed'] },
  { key: 'stopOn', label: 'stop on', info: 'the metric early stopping and model selection read. Balanced accuracy, because the six classes are far from equal in size.', options: ['val balanced acc.', 'val macro F1', 'val loss'] },
  { key: 'learningRate', label: 'learning rate', info: 'initial rate and schedule. Cosine decay over the epoch budget.', options: ['3e-4 · cosine', '1e-4 · cosine', '3e-4 · constant'] },
  { key: 'batchSeed', label: 'batch · seed', info: 'batch size and the seed for initialisation, shuffling and augmentation. The seed is written into the recipe hash.', options: ['32 · 17', '64 · 17', '32 · 4'] },
  { key: 'classBalance', label: 'class balance', info: 'C1 holds 260 windows and C6 holds 7. Without a correction the network can score well by never predicting the small classes.', options: ['inverse-frequency weights', 'balanced sampler', 'none'] },
  { key: 'augmentation', label: 'augmentation', info: 'applied to the window before encoding, never to the image — an encoded image flipped or cropped is not a signal any more.', options: ['time shift ± 10 %', 'time shift ± 20 %', 'none'] },
]
type ModelParamsUI = { architecture: string; input: string; epochs: string; stopOn: string; learningRate: string; batchSeed: string; classBalance: string; augmentation: string }

function Body({ data }: { data: ModelBlock }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [source, setSource] = useSourceQuery()
  const [draft, setDraft] = useTrainingDraft()
  const [modal, setModal] = useQueryState('modal', '')
  const [labelsQ, setLabelsQ] = useQueryState('labels', '')
  const [focus] = useQueryState('focus', '')
  const [params, setParams] = useState<ModelParamsUI>(() => ({ ...data.params }))
  const [trialJob, setTrialJob] = useState<string | null>(null)

  const p = live(draft.model)
  const setP = (patch: Partial<ModelParams>) =>
    setDraft(d => ({ ...d, model: { ...d.model, pending: { ...live(d.model), ...patch } } }))

  /* ?labels=manual|both is the deep link for the same click as the radio cards. */
  const labelsFrom = labelsQ || p.labelsFrom
  const setLabels = (v: string) => { setLabelsQ(v === 'cluster' ? null : v); setP({ labelsFrom: v }) }

  /* ?focus=trial scrolls the trial card into view — the chain row's "Trial job on this channel" lands here. */
  useEffect(() => {
    if (focus !== 'trial') return
    const el = document.querySelector('[data-testid="trial-card"]')
    if (el) el.scrollIntoView({ block: 'center' })
  }, [focus])

  const chain = data.chain
  const status: Record<string, BadgeStatus> = chainStatuses(draft.staleFrom, chain)

  const ticked = data.stages.filter(s => p.stages[s.id])
  const fromStage = ticked.length ? ticked[0].id : '05'
  const toStage = ticked.length ? ticked[ticked.length - 1].id : '05'
  const encodeOff = !p.stages['04']
  const script = trialScript(fromStage, toStage)

  const toggleStage = (id: string) => {
    const next = { ...p.stages, [id]: !p.stages[id] }
    if (id === '04' && p.stages['04']) next['05'] = false      // 05 has no images without 04
    setP({ stages: next })
  }

  const trainInModels = () => {
    recordDemoWrite('models', 'add-training-job', { id: `t-${Math.floor(Math.random() * 900) + 100}`, template: draft.name, arms: labelsFrom === 'both' ? 'cluster classes · manual verdicts (paired)' : labelsFrom })
    navigate(`models/launch?template=${draft.name}`)
  }

  const downloadTrial = () => {
    const id = `j-${Math.floor(Math.random() * 900) + 100}`
    setTrialJob(id)
    recordDemoWrite('jobs', 'add-job', { id, kind: 'analyse', title: `trial · ${draft.name} · stages ${fromStage} → ${toStage}`, status: 'queue', detail: `${CHANNEL} · one GPU task · uob-bc4`, for: 'Analyse › Training' })
    push({ text: `trial job ${id} created · in memory (demo)`, action: { label: 'Open in Jobs', onClick: () => navigate('jobs') } })
  }

  return (
    <BlockFrame
      chain={chain} current="model" status={status} source={source} onSource={s => setSource(s === 'signal' ? null : s)}
      name={draft.name} saved={draft.saved} onRename={v => setDraft(d => ({ ...d, name: v, saved: false }))}
      estimate={ESTIMATES.model}
      onBack={() => navigate('analyse/training')} onNavigate={b => b.route && navigate(b.route)}
      onAddStage={() => notWired('insert a stage into the training chain (type-contract modal §6.4)')}
      onSaveTemplate={() => setModal('save-template')}
      primary={<Button variant="primary" icon="rocket" onClick={trainInModels} testid="train-in-models-top">Train in Models</Button>}
    >
      <div className="tr-cols wide-right">
        <SectionCard number={5} title="Model" subtitle="Encoding + labels → Model" testid="model-card"
          actions={<span className="tr-muted tr-small">tick the stages the trial job runs</span>}>
          <div className="tr-stages" data-testid="stage-table">
            <div className="tr-stage hd" aria-hidden>
              <span className="tk" /><span className="nm">stage</span><span className="st">status</span>
              <span className="ct">cost</span><span className="on">runs on</span><span className="nt" />
            </div>
            {data.stages.map(s => {
              const on = !!p.stages[s.id]
              const blocked = s.id === '05' && encodeOff
              return (
                <div key={s.id} className={`tr-stage${on ? ' on' : ''}${blocked ? ' blocked' : ''}`} data-testid={`stage-${s.id}`}>
                  <span className="tk">
                    <Checkbox checked={on} onChange={() => toggleStage(s.id)} testid={`stage-tick-${s.id}`}
                      label={`${s.id} ${s.label}`}
                      disabled={blocked} disabledReason={blocked ? '04 Encode is unticked — 05 would have no images to train on' : undefined} />
                  </span>
                  <span className="nm"><span className="num">{s.id}</span>{s.label}</span>
                  <span className="st"><Badge status={s.status} size="sm" /></span>
                  <span className="ct tr-mono">{s.cost}</span>
                  <span className={`on tr-mono${s.runsOn.startsWith('cluster') ? ' cluster' : ''}`}>{s.runsOn}</span>
                  <span className="nt tr-muted">{blocked ? 'no images · tick 04 Encode first' : s.note}</span>
                </div>
              )
            })}
          </div>

          <div className="tr-labels" data-testid="labels-from">
            <span className="tr-muted tr-small">labels from
              <InfoTip title="Where the training labels come from">
                Cluster classes exist for every window; manual verdicts exist only for the {fmtInt(WINDOWS.reviewed)} windows a
                human has looked at. They are separate things and never overwrite each other — "both, paired" trains one arm on
                each over the same split and test set, which is a comparison Models runs, not Analyse.
              </InfoTip>
            </span>
            <RadioCards columns={3} value={labelsFrom} onChange={setLabels} testid="labels-cards"
              options={data.labelSources.map(l => ({ value: l.value, title: l.title, description: l.description }))} />
            {labelsFrom === 'manual' && (
              <Callout tone="amber" icon="alert-triangle" testid="labels-manual-note"
                action={<Button size="sm" icon="inbox" onClick={() => setModal('send-review')} testid="labels-send-review">Send {fmtInt(WINDOWS.unreviewed)} to Review</Button>}>
                {fmtInt(WINDOWS.reviewed)} reviewed windows · binary interesting / not · {fmtInt(WINDOWS.unreviewed)} windows carry no human verdict and are dropped from this arm
              </Callout>
            )}
            {labelsFrom === 'both' && (
              <Callout tone="blue" icon="rocket" testid="labels-both-note"
                action={<Button size="sm" variant="primary" icon="rocket" onClick={trainInModels} testid="labels-both-launch">Train in Models</Button>}>
                two arms over one split and one test set — the paired comparison runs in Models, not here
              </Callout>
            )}
          </div>
        </SectionCard>

        <SectionCard title="Training" testid="training-params">
          <div className="tr-grid2">
            {PARAM_FIELDS.map(f => (
              <div key={f.key}>
                <span className="tr-muted tr-small">{f.label}<InfoTip title={f.label}>{f.info}</InfoTip></span>
                <Dropdown block value={params[f.key]} onChange={v => setParams(q => ({ ...q, [f.key]: v }))}
                  testid={`param-${f.key}`} options={f.options.map(o => ({ value: o, label: o }))}
                  active={params[f.key] !== data.params[f.key]} />
              </div>
            ))}
          </div>
          <div className="tr-held" data-testid="held-out">
            <Icon name="lock" size={11} />{data.params.heldOut}
            <InfoTip title="Held out (D6)">
              M4_aug never enters a training, validation or test split, and no page here will load it. The lock lives in
              Settings › Datasets so one page cannot quietly undo it.
            </InfoTip>
          </div>
        </SectionCard>
      </div>

      <div className="tr-cols even">
        <SectionCard title="Before this trains" testid="before-trains">
          <Checklist items={data.checks.map(c => ({ label: c.label, state: c.state }))} />
          <div className="tr-row-flex" style={{ marginTop: 10 }}>
            <Button icon="layers" onClick={() => navigate('analyse/training/block/3?merge=C5,C6')} testid="merge-in-03">Merge C5 + C6 in 03</Button>
            <Button icon="inbox" onClick={() => setModal('send-review')} testid="send-review">Send {fmtInt(WINDOWS.unreviewed)} to Review</Button>
          </div>
        </SectionCard>

        <SectionCard title={TRIAL.title} subtitle={ticked.length ? `stages ${fromStage} → ${toStage} · one GPU task` : 'no stage ticked · the job would do nothing'} testid="trial-card"
          actions={<Dropdown prefix="template" value="guided · uob-bc4" onChange={() => notWired('switch the cluster job template')}
            testid="trial-template" options={[{ value: 'guided · uob-bc4', label: 'guided · uob-bc4' }, { value: 'raw sbatch', label: 'raw sbatch' }]} />}>
          <CodeBlock code={script} filename={`trial_${draft.name}.sh`} copy={false} save={false} maxHeight={110} />
          <div className="tr-row-flex" style={{ marginTop: 8 }}>
            <span className="tr-muted tr-small">{TRIAL.returns}</span>
            <span className="k-spacer" />
            <Button icon="copy" onClick={() => { void navigator.clipboard?.writeText(script); push({ text: 'trial script copied to the clipboard' }) }} testid="copy-script">Copy script</Button>
            <Button icon="download" onClick={downloadTrial} testid="download-trial">Download trial job</Button>
          </div>
          {trialJob && <Chip tone="blue" icon="check" testid="trial-job-chip" onClick={() => navigate('jobs')}>trial job {trialJob} queued · Jobs</Chip>}
          {ticked.length === 0 && <Badge status="invalid" testid="no-stage">no stage is ticked — the trial job would do nothing</Badge>}

          <div className="tr-handoff" data-testid="models-handoff" style={{ marginTop: 10 }}>
            <Icon name="rocket" size={15} />
            <span className="txt">
              <b>Train the real model in Models</b>
              <span>applies this template across channels and recordings · paired comparison · results and nulls</span>
            </span>
            <Button variant="primary" icon="arrow-right" onClick={trainInModels} testid="train-in-models">Train in Models</Button>
          </div>
        </SectionCard>
      </div>

      <SaveTemplateModal open={modal === 'save-template'} onClose={() => setModal(null)} defaultName={draft.name}
        stages={chain.filter(b => b.index != null).map(b => b.label)}
        onSaved={n => setDraft(d => ({ ...d, name: n, saved: true }))} />
      <SendToReviewModal open={modal === 'send-review'} onClose={() => setModal(null)} from="training · 05 Model"
        onSent={n => setDraft(d => ({ ...d, queuedToReview: d.queuedToReview + n }))} />
    </BlockFrame>
  )
}
