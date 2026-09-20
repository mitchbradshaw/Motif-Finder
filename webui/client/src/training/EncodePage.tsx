/* analyse.training.encode — 04 Encode (frame training-3). `WindowSet → Encoding`.
 * The page's job is to let you look at exactly what the classifier will see, one window at a time, and
 * to say what a parameter change costs: an encoder set or image size that is not the one already in the
 * registry registers as a NEW encoder version, and trained models keep the old one. */
import { useEffect, useState } from 'react'
import {
  Badge, Button, Callout, Checkbox, Chip, Dropdown, Icon, InfoTip, NumberField, Page, SectionCard, Seg, Slider,
  StatTile, Trace, fmtInt, recordDemoWrite, useNotWired, useQueryState, useSim, type BadgeStatus,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getEncodeBlock, type EncodeBlock } from '../api/training'
import {
  CLASS_COLOURS, CLASS_Y, ENCODE, ESTIMATES, RUN_STEPS, WINDOWS, chainStatuses, classForWindow, encodeCost,
  fmtGB, fmtMin, hoursForWindow, splitForWindow, windowTrace, windowsOfClass, type EncodingKind,
} from '../fixtures/training'
import { EncodingImage } from './Encoding'
import { BlockFrame, LoadFailed, Loading, RunVeil, SaveTemplateModal, UnappliedBar } from './chrome'
import { isPending, live, markSimForced, useSourceQuery, useTrainingDraft, wasSimForced, type EncodeParams } from './draft'

export function EncodePage() {
  const [source] = useSourceQuery()
  const block = useSourced(() => getEncodeBlock(source), [source])
  return (
    <>
      <Header workspace="Analyse" page="04 Encode" search="Search spans, runs, families" demo={block.source === 'demo'}
        subtitle="windows as images · browse what the classifier will see" />
      <Page testid="training-encode">
        {block.error ? <LoadFailed what="the encodings" error={block.error} onRetry={block.reload} />
          : !block.data ? <Loading what="the encodings" /> : <Body data={block.data} />}
      </Page>
    </>
  )
}

/** The +1 … −1 strip beside each encoding: the same ramp `Encoding.tsx` paints the image with. */
function Scale() {
  return (
    <span className="tr-scale" aria-hidden>
      <span className="bar" />
      <span className="tk">+1</span><span className="tk bot">−1</span>
    </span>
  )
}

function Body({ data }: { data: EncodeBlock }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [source, setSource] = useSourceQuery()
  const [draft, setDraft] = useTrainingDraft()
  const [modal, setModal] = useQueryState('modal', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [encoderQ] = useQueryState('encoder', '')
  const [windowQ, setWindowQ] = useQueryState('window', '')
  const [browse, setBrowse] = useQueryState('browse', 'gasf')
  const [nonce, setNonce] = useState(0)

  const p = live(draft.encode)
  const pending = isPending(draft.encode)
  const setP = (patch: Partial<EncodeParams>) =>
    setDraft(d => ({ ...d, encode: { ...d.encode, pending: { ...live(d.encode), ...patch } }, staleFrom: 4 }))

  /* deep links: ?state=edited stages the fusion tick · ?encoder=new opens on a new encoder version */
  useEffect(() => {
    if (stateQ === 'edited' && !draft.encode.pending) setP({ included: { ...p.included, fusion: true } })
    if (encoderQ === 'new' && p.encoder === ENCODE.recommended.encoder) setP({ encoder: 'new · v3', size: '256 × 256' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ, encoderQ])

  const sim = useSim('analyse.training.run')
  useEffect(() => {
    if (stateQ === 'running') { sim.force({ status: 'running', steps: RUN_STEPS, step: 3, fraction: 0.7, startedAt: Date.now() }); markSimForced(true) }
    else if (wasSimForced()) { sim.reset(); markSimForced(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const window_ = Math.max(1, Math.min(ENCODE.total, Number(windowQ) || ENCODE.window))
  const setWindow = (v: number) => setWindowQ(v === ENCODE.window ? null : String(Math.max(1, Math.min(ENCODE.total, v))))

  const ticked = data.encodings.filter(e => p.included[e.id])
  const images = WINDOWS.total * ticked.length
  const newVersion = p.encoder !== ENCODE.recommended.encoder || p.size !== ENCODE.recommended.size
  /* §6.8: the disk estimate for this signature is images × px × channels, so the image size and the PAA
   * reduction have to move it — they were label-only. */
  const cost = encodeCost(images, p.size, p.paa)

  /* One window, one hour, one class, shared with 02's readout: the card used to name a different class
   * from the readout that opened it. */
  const windowClass = (w: number) => classForWindow(w)

  const chain = data.chain
  const status: Record<string, BadgeStatus> = chainStatuses(draft.staleFrom, chain)
  if (sim.status === 'running') status.encode = 'running'

  const apply = () => {
    setStateQ(null)
    setDraft(d => ({ ...d, encode: { applied: live(d.encode), pending: null }, staleFrom: 5 }))
    recordDemoWrite('analyse', 'apply-block', { block: '04 Encode', encodings: ticked.map(e => e.id), images })
    sim.start({ steps: RUN_STEPS, stepMs: 600 })
  }
  const revert = () => { setStateQ(null); setDraft(d => ({ ...d, encode: { ...d.encode, pending: null } })) }

  const primary = sim.busy
    ? <Button variant="danger" icon="stop" onClick={() => sim.cancel()} testid="cancel-run">Cancel</Button>
    : <Button variant="primary" icon="refresh" testid="apply-rerun-top" onClick={apply}
        disabled={!pending && !draft.staleFrom} disabledReason={!pending && !draft.staleFrom ? 'no unapplied changes' : undefined}>Apply &amp; re-run from 04</Button>

  /* 3 sampled windows per class (P8 keeps this well under 10), and they really are windows of that
   * class — the old arithmetic sample opened a C5 window from the C4 card. */
  const sampleFor = (klass: string) => windowsOfClass(klass, 3, nonce)

  return (
    <BlockFrame
      chain={chain} current="encode" status={status} source={source} onSource={s => setSource(s === 'signal' ? null : s)}
      name={draft.name} saved={draft.saved} onRename={v => setDraft(d => ({ ...d, name: v, saved: false }))}
      estimate={pending ? `${fmtInt(images)} images · ${fmtGB(cost.bytes)} · ${fmtMin(cost.minutes)}` : ESTIMATES.encode}
      estimateTone={pending ? 'amber' : 'muted'}
      onBack={() => navigate('analyse/training')} onNavigate={b => b.route && navigate(b.route)}
      onAddStage={() => notWired('insert a stage into the training chain (type-contract modal §6.4)')}
      onSaveTemplate={() => setModal('save-template')}
      primary={primary}
      footer={
        <UnappliedBar pending={pending} stage="04"
          why={pending
            ? `${ticked.length} encodings ticked · ${fmtInt(images)} images to write · 05 re-runs on them`
            : ENCODE.footer}
          staleLabel={!pending && draft.staleFrom ? '04' : null}
          revertReason={!pending ? 'already at the recommended values' : undefined}
          onRevert={revert} onApply={apply} busy={sim.busy} onCancel={() => sim.cancel()} />
      }
    >
      <div className="tr-cols wide-right">
        <SectionCard number={4} title="Encode" subtitle="WindowSet → Encoding" testid="encode-card"
          actions={
            <span className="tr-row-flex" data-testid="window-pager">
              <Button size="sm" variant="ghost" icon="chevron-left" aria-label="previous window" testid="window-prev"
                disabled={window_ <= 1} disabledReason={window_ <= 1 ? 'this is the first window' : undefined}
                onClick={() => setWindow(window_ - 1)} />
              <span className="tr-muted tr-small">window</span>
              <NumberField value={window_} onValid={setWindow} min={1} max={ENCODE.total} integer width={78} testid="window-field" ariaLabel="window number" />
              <span className="tr-muted tr-small tr-mono">/ {fmtInt(ENCODE.total)}</span>
              <Button size="sm" variant="ghost" icon="chevron-right" aria-label="next window" testid="window-next"
                disabled={window_ >= ENCODE.total} disabledReason={window_ >= ENCODE.total ? 'this is the last window' : undefined}
                onClick={() => setWindow(window_ + 1)} />
              <Chip size="sm" tone="blue" dot={CLASS_COLOURS[windowClass(window_)]} testid="window-class">
                {windowClass(window_)} · {splitForWindow(window_)} · {hoursForWindow(window_).toFixed(1)} h · {ENCODE.verdict}
              </Chip>
            </span>
          }>
          <div className="tr-rel">
            {sim.busy && <RunVeil label={`${RUN_STEPS[sim.step] ?? 'running'} · ${Math.round(sim.fraction * 100)} %`} fraction={sim.fraction} />}
            <span className="tr-muted tr-small tr-mono" data-testid="window-signal-caption">{ENCODE.signalNote}</span>
            <Trace values={windowTrace(window_)} fs={1 / 5} yDomain={CLASS_Y} timeUnit="s" height={78} ground="white" crosshair={false} testid="window-signal" />

            <div className="tr-encodings" data-testid="encodings">
              {data.encodings.map(e => {
                const on = !!p.included[e.id]
                return (
                  <div key={e.id} className={`tr-enc ${on ? 'on' : 'off'}`} data-testid={`encoding-${e.id}`}>
                    <span className="nm">{e.label}<InfoTip title={e.label}>{e.note}</InfoTip></span>
                    <span className="tr-row-flex" style={{ gap: 5, flexWrap: 'nowrap' }}>
                      <EncodingImage kind={e.id as EncodingKind} window={window_} size={168} n={22} testid={`encoding-img-${e.id}`} />
                      <Scale />
                    </span>
                    <Checkbox checked={on} onChange={() => setP({ included: { ...p.included, [e.id]: !on } })}
                      label={e.label} testid={`encoding-tick-${e.id}`} />
                  </div>
                )
              })}
            </div>
            {ticked.length === 0 && <Badge status="invalid" testid="no-encoding">no encoding is ticked — 05 has no images to train on</Badge>}
          </div>
        </SectionCard>

        <SectionCard title="Parameters" testid="encode-params">
          <div className="tr-grid2">
            <Dropdown prefix="encoder set" value={p.encoder} onChange={v => setP({ encoder: v })} block testid="encoder-set"
              options={[
                { value: 'existing · v2', label: 'existing · v2', description: 'the encoders the registered models were trained on' },
                { value: 'new · v3', label: 'new · v3', description: 'registers as a new encoder version' },
              ]} />
            <Dropdown prefix="image size" value={p.size} onChange={v => setP({ size: v })} block testid="image-size"
              options={[
                { value: '224 × 224', label: '224 × 224', description: 'what EfficientNet-B0 expects' },
                { value: '256 × 256', label: '256 × 256', description: 'registers as a new encoder version' },
                { value: '128 × 128', label: '128 × 128', description: 'registers as a new encoder version' },
              ]} />
            <Dropdown prefix="PAA reduction" value={p.paa} onChange={v => setP({ paa: v })} block testid="paa"
              options={[{ value: 'none', label: 'none' }, { value: '2 ×', label: '2 ×' }, { value: '4 ×', label: '4 ×' }]} />
            <div>
              <span className="tr-muted tr-small">recurrence ε</span>
              <Slider value={p.epsilon} onChange={v => setP({ epsilon: +v.toFixed(2) })} min={0.05} max={0.6} step={0.01}
                format={v => v.toFixed(2)} ariaLabel="recurrence epsilon" testid="epsilon"
                disabled={!p.included.rp} disabledReason={!p.included.rp ? 'the recurrence plot is unticked' : undefined} />
              <span className="tr-muted tr-small tr-mono">{p.epsilon === ENCODE.recommended.epsilon ? '= current models' : `≠ current models (${ENCODE.recommended.epsilon})`}</span>
            </div>
            <Dropdown prefix="fusion channels" value={p.fusion} onChange={v => setP({ fusion: v })} block testid="fusion"
              options={[{ value: 'GASF / GADF / RP', label: 'GASF / GADF / RP' }, { value: 'GASF / GADF / signal', label: 'GASF / GADF / signal' }]} />
            <Dropdown prefix="write to" value={p.writeTo} onChange={v => setP({ writeTo: v })} block testid="write-to"
              options={[
                { value: 'artifacts/encodings', label: 'artifacts/encodings' },
                { value: 'artifacts/encodings_v3', label: 'artifacts/encodings_v3' },
              ]} />
          </div>
          <Callout tone={newVersion ? 'amber' : 'grey'} icon={newVersion ? 'alert-triangle' : 'lock'} testid="encoder-note">
            {newVersion ? ENCODE.newVersionNote : ENCODE.note}
          </Callout>
          <div className="tr-grid3" style={{ marginTop: 10 }}>
            <StatTile variant="flat" label="images" value={fmtInt(images)} caption={`${ticked.length} of ${data.encodings.length} encodings`} testid="images-tile" />
            <StatTile variant="flat" label="disk" value={fmtGB(cost.bytes)} caption={`${p.size}${p.paa === 'none' ? '' : ` · PAA ${p.paa}`}`} testid="disk-tile" />
            <StatTile variant="flat" label="time" value={fmtMin(cost.minutes)} caption={p.writeTo} testid="time-tile" />
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Browse by class" subtitle={`${ENCODE.browseNote} · ${browse.toUpperCase()}`} testid="browse-card"
        actions={
          <span className="tr-row-flex">
            <Seg value={browse} onChange={v => setBrowse(v === 'gasf' ? null : v)} size="sm" testid="browse-seg"
              options={[{ value: 'gasf', label: 'GASF' }, { value: 'gadf', label: 'GADF' },
                { value: 'rp', label: 'Recurrence', disabled: !p.included.rp, reason: !p.included.rp ? 'the recurrence plot is unticked' : undefined }]} />
            <Button size="sm" icon="shuffle" testid="resample-windows"
              onClick={() => { setNonce(n => n + 1); push({ text: 'resampled 3 windows per class · seeded, so it is repeatable' }) }}>Resample</Button>
          </span>
        }>
        <div className="tr-classes" data-testid="browse-classes">
          {data.classes.map(c => (
            <button type="button" key={c.id} className={`tr-class${c.tooSmall ? ' small' : ''}`} data-testid={`browse-class-${c.id}`}
              title={`open the first ${c.id} window`} onClick={() => setWindow(sampleFor(c.id)[0])}>
              <span className="hd"><span className="tr-dot" style={{ background: c.colour }} />{c.id}<span className="k-spacer" />
                <span className="tr-muted">{fmtInt(c.windows * ticked.length)} img</span></span>
              <span className="bd tr-row-flex" style={{ gap: 4, padding: 4, flexWrap: 'nowrap' }}>
                {sampleFor(c.id).map(wn => <EncodingImage key={wn} kind={browse as EncodingKind} window={wn} size={58} n={16} />)}
              </span>
              <span className="ft">train {c.train} · val {c.val} · test {c.test}</span>
              {c.tooSmall && <span className="ft flag"><Icon name="alert-triangle" size={10} /> under {ENCODE.splitFloor} per split</span>}
            </button>
          ))}
        </div>
      </SectionCard>

      <SaveTemplateModal open={modal === 'save-template'} onClose={() => setModal(null)} defaultName={draft.name}
        stages={chain.filter(b => b.index != null).map(b => b.label)}
        onSaved={n => setDraft(d => ({ ...d, name: n, saved: true }))} />
    </BlockFrame>
  )
}
