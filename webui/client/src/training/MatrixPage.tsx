/* analyse.training.matrix — 02 Window matrix (frame training-1). `WindowSet → WindowSet + features`.
 * P12 lives here as a parameter, not prose: the two label-derived groups are off by default and ticking
 * one raises the leak, because their scores come from models trained on the manual verdicts the
 * clustering is later compared against. */
import { useEffect, useState } from 'react'
import {
  Badge, Button, Callout, Checkbox, Checklist, CodeBlock, Dropdown, Icon, InfoTip, KeyValue, Modal, Page,
  SectionCard, StatTile, TextField, Trace, fmtInt, recordDemoWrite, useNotWired, useQueryState, useSim,
  type BadgeStatus,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { getMatrixBlock, type MatrixBlock } from '../api/training'
import {
  ESTIMATES, MATRIX, MATRIX_BAND_COL, MATRIX_COLS, MATRIX_READOUT, RUN_STEPS, SIGNAL_FS, SLURM_MATRIX, WINDOWS,
  chainStatuses, matrixValues, readoutForColumn, type FeatureGroup,
} from '../fixtures/training'
import { BlockFrame, Heat, LoadFailed, Loading, RunVeil, SaveTemplateModal, UnappliedBar, blanks } from './chrome'
import { isPending, live, markSimForced, useSourceQuery, useTrainingDraft, wasSimForced, type MatrixParams } from './draft'

export function MatrixPage() {
  const [source] = useSourceQuery()
  const block = useSourced(() => getMatrixBlock(source), [source])
  return (
    <>
      <Header workspace="Analyse" page="02 Window matrix" search="Search spans, runs, families" demo={block.source === 'demo'}
        subtitle="features per window · one time axis with the signal" />
      <Page testid="training-matrix">
        {block.error ? <LoadFailed what="the window matrix" error={block.error} onRetry={block.reload} />
          : !block.data ? <Loading what="the matrix" /> : <Body data={block.data} />}
      </Page>
    </>
  )
}

interface Readout { col: number; window: number; from_h: number; klass: string; feature: string }
/* The window, the hour and the class all come from one place, so 02's readout and the card 04 opens
 * for the same window cannot disagree about which class it is or when it happened. */
const DEFAULT_READOUT: Readout = { ...MATRIX_READOUT, feature: MATRIX.readout.feature }

/** σ the clip control is set to — the heat ramp and the legend both read it. */
const clipSigma = (clip: string) => (clip === '± 2 σ' ? 2 : clip === 'none' ? 6 : 3)

function Body({ data }: { data: MatrixBlock }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [source, setSource] = useSourceQuery()
  const [draft, setDraft] = useTrainingDraft()
  const [modal, setModal] = useQueryState('modal', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [openGroup, setOpenGroup] = useQueryState('open', '')
  const [readout, setReadout] = useState<Readout>(DEFAULT_READOUT)

  /* The frame opens with a pending exclusion (its chain row already shows it applied) — the route opens
   * clean and `?state=edited` sets the pair up: the cached run included Random Forest, the edit drops it. */
  useEffect(() => {
    if (stateQ === 'edited' && !draft.matrix.pending) {
      setDraft(d => ({
        ...d,
        matrix: { applied: { ...live(d.matrix), groups: { ...live(d.matrix).groups, rf: true } }, pending: { ...live(d.matrix), groups: { ...live(d.matrix).groups, rf: false } } },
        staleFrom: 3,
      }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const sim = useSim('analyse.training.run')
  useEffect(() => {
    if (stateQ === 'running') { sim.force({ status: 'running', steps: RUN_STEPS, step: 1, fraction: 0.4, startedAt: Date.now() }); markSimForced(true) }
    else if (wasSimForced()) { sim.reset(); markSimForced(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const p = live(draft.matrix)
  const pending = isPending(draft.matrix)
  const setP = (patch: Partial<MatrixParams>) =>
    setDraft(d => ({ ...d, matrix: { ...d.matrix, pending: { ...live(d.matrix), ...patch } }, staleFrom: 3 }))
  const toggleGroup = (g: FeatureGroup) => setP({ groups: { ...p.groups, [g.id]: !p.groups[g.id] } })

  const included = data.groups.filter(g => p.groups[g.id])
  const leaking = included.filter(g => g.labelDerived)
  const nCols = included.reduce((n, g) => n + g.count, 0)

  /* normalise and clip are what the matrix *is*, so they have to show in it. Per-window z-scoring
   * centres every column, which is exactly the caption's warning made visible; `none` leaves the
   * features on their own scale; the clip is the ramp's domain. */
  const sigma = clipSigma(p.clip)
  const shape = (vals: number[][]): number[][] => {
    let v = vals
    if (p.normalise === 'z-score · per window') {
      const mean = (v[0] ?? []).map((_, c) => v.reduce((t, r) => t + r[c], 0) / v.length)
      v = v.map(r => r.map((x, c) => x - mean[c]))
    } else if (p.normalise === 'none') {
      v = v.map((r, i) => r.map(x => x * (1.1 + (i % 3) * 0.6)))
    }
    return v.map(r => r.map(x => Math.max(-sigma, Math.min(sigma, +x.toFixed(2)))))
  }

  /* What is unapplied, field by field — the bar said "Random Forest excluded" for every edit. */
  const a0 = draft.matrix.applied
  const changes: string[] = []
  data.groups.forEach(g => {
    if (!!a0.groups[g.id] !== !!p.groups[g.id]) changes.push(`${g.label} ${p.groups[g.id] ? 'included' : 'excluded'}`)
  })
  if (p.normalise !== a0.normalise) changes.push(`normalise ${a0.normalise} → ${p.normalise}`)
  if (p.clip !== a0.clip) changes.push(`clip ${a0.clip} → ${p.clip}`)
  /* Dropping columns reuses the cache; changing how a value is scaled does not. */
  const recompute = p.normalise !== a0.normalise || p.clip !== a0.clip

  const chain = data.chain
  const status: Record<string, BadgeStatus> = chainStatuses(draft.staleFrom, chain)
  if (sim.status === 'running') chain.forEach(b => { if (b.id === 'matrix') status[b.id] = 'running' })

  const apply = () => {
    setStateQ(null)
    setDraft(d => ({ ...d, matrix: { applied: live(d.matrix), pending: null }, staleFrom: 3 }))
    recordDemoWrite('analyse', 'apply-block', { block: '02 Window matrix', groups: Object.keys(p.groups).filter(k => p.groups[k]) })
    sim.start({ steps: RUN_STEPS, stepMs: 600 })
  }
  const revert = () => { setStateQ(null); setDraft(d => ({ ...d, matrix: { ...d.matrix, pending: null } })) }

  const primary = sim.busy
    ? <Button variant="danger" icon="stop" onClick={() => sim.cancel()} testid="cancel-run">Cancel</Button>
    : <Button variant="primary" icon="refresh" onClick={apply} testid="apply-rerun-top"
        disabled={!pending && !draft.staleFrom} disabledReason={!pending && !draft.staleFrom ? 'no unapplied changes' : undefined}>Apply &amp; re-run from 02</Button>

  return (
    <BlockFrame
      chain={chain} current="matrix" status={status} source={source} onSource={s => setSource(s === 'signal' ? null : s)}
      name={draft.name} saved={draft.saved} onRename={v => setDraft(d => ({ ...d, name: v, saved: false }))}
      estimate={pending ? (recompute ? '≈ 3 h on the cluster · the values are rescaled' : 'columns dropped · no recompute') : ESTIMATES.matrix}
      estimateTone={pending ? 'amber' : 'muted'}
      onBack={() => navigate('analyse/training')} onNavigate={b => b.route && navigate(b.route)}
      onAddStage={() => notWired('insert a stage into the training chain (type-contract modal §6.4)')}
      onSaveTemplate={() => setModal('save-template')}
      primary={primary}
      footer={
        <UnappliedBar pending={pending} stage="02" count={changes.length}
          why={pending
            ? `${changes.join(' · ')} · 03 → 05 go stale · ${recompute ? '02 recomputes (the values are rescaled)' : '02 reuses its cache (columns dropped, no recompute)'}`
            : draft.staleFrom ? '04 and 05 are stale from an earlier cut' : 'the matrix on screen is the one the last run used'}
          staleLabel={!pending && draft.staleFrom ? '04' : null}
          revertReason={!pending ? 'already at the recommended values' : undefined}
          onRevert={revert} onApply={apply} busy={sim.busy} onCancel={() => sim.cancel()} />
      }
    >
      {leaking.length > 0 && (
        <Callout tone="red" icon="alert-triangle" title={`${leaking.map(g => g.label).join(' and ')} leak manual labels into 03 (P12)`} testid="leak-callout"
          action={<Button size="sm" onClick={() => setP({ groups: { ...p.groups, ...Object.fromEntries(leaking.map(g => [g.id, false])) } })} testid="drop-label-derived">Exclude them again</Button>}>
          {MATRIX.labelDerivedWarning}
        </Callout>
      )}

      <div className="tr-cols">
        <SectionCard number={2} title="Window matrix" subtitle="WindowSet → WindowSet + features" testid="matrix-card"
          actions={
            <div className="tr-row-flex">
              <Dropdown prefix="normalise" value={p.normalise} onChange={v => setP({ normalise: v })} width={230} testid="normalise"
                options={[
                  { value: 'z-score · per channel', label: 'z-score · per channel' },
                  { value: 'z-score · per window', label: 'z-score · per window', description: 'removes the between-window differences the clustering is looking for' },
                  { value: 'none', label: 'none', description: 'features keep their own units' },
                ]} />
              <Dropdown prefix="clip" value={p.clip} onChange={v => setP({ clip: v })} width={120} testid="clip"
                options={[{ value: '± 3 σ', label: '± 3 σ' }, { value: '± 2 σ', label: '± 2 σ' }, { value: 'none', label: 'none' }]} />
              <InfoTip title="What this matrix is">
                One column per window, one row per feature, z-scored down each row. Nothing here is a plot of mV — the signal below shares the time axis so a band can be read against the trace.
              </InfoTip>
            </div>
          }>
          <div className="tr-rel" data-testid="matrix-groups">
            {sim.busy && <RunVeil label={`${RUN_STEPS[sim.step] ?? 'running'} · ${Math.round(sim.fraction * 100)} %`} fraction={sim.fraction} />}
            {data.groups.map(g => {
              const on = !!p.groups[g.id]
              const open = g.collapsedByDefault ? openGroup === g.id : true
              const ids = open ? g.features : [g.id]
              return (
                <div key={g.id} className={`tr-mxgroup${on ? '' : ' off'}`} data-testid={`matrix-group-${g.id}`}>
                  <div className="hd">
                    <button type="button" className="chev" data-testid={`matrix-toggle-${g.id}`}
                      aria-expanded={open} title={open ? `collapse ${g.label}` : `show all ${g.count} ${g.label} features`}
                      onClick={() => setOpenGroup(open && g.collapsedByDefault ? null : g.id)}>
                      <Icon name={open ? 'chevron-down' : 'chevron-right'} size={12} />
                    </button>
                    <span className="nm">{g.label}</span>
                    <span className="ct">{open ? '' : `· ${g.count}`}</span>
                    {g.labelDerived && !on && <span className="ld">label-derived · excluded</span>}
                  </div>
                  <Heat
                    rows={open ? g.features : blanks(1)} values={shape(matrixValues(ids))} cellHeight={open ? 11 : 13}
                    domain={[-sigma, sigma]}
                    selectedCols={[readout.col]} testid={`matrix-heat-${g.id}`}
                    onCellClick={(r, c) => setReadout({
                      ...readoutForColumn(c, MATRIX_COLS),
                      feature: c === MATRIX_BAND_COL ? MATRIX.readout.feature
                        : `${(open ? g.features[r] : g.label)} ${(((c % 7) - 3) / 1.4).toFixed(1)}σ`,
                    })}
                  />
                </div>
              )
            })}
          </div>

          <div className="tr-mxlegend" data-testid="matrix-legend">
            <span className="mono">−{sigma}σ</span>
            <span className="ramp" />
            <span className="mono">+{sigma}σ</span>
            <span className="mono tr-muted">{p.normalise}</span>
            <span className="k-spacer" />
            <span className="mono tr-muted">{MATRIX.greyNote}</span>
          </div>

          <div className="tr-mxsignal" data-testid="matrix-signal">
            <span className="lab mono">signal · same axis</span>
            <Trace values={data.signal.values} fs={SIGNAL_FS} yDomain={data.signal.yDomain} timeUnit="h" height={62} ground="white" crosshair={false} />
          </div>

          <div className="tr-readout" data-testid="matrix-readout">
            <Icon name="target" size={13} />
            <span><b>window {readout.window}</b> · {readout.from_h.toFixed(1)} – {(readout.from_h + WINDOWS.params.length_min / 60).toFixed(1)} h · class {readout.klass} · {readout.feature}</span>
            <span className="k-spacer" />
            <span className="tr-muted">{MATRIX.readout.band.replace('4 of 4', `${included.filter(g => !g.labelDerived).length} of ${included.length}`)}</span>
            <Button size="sm" icon="arrow-right" onClick={() => navigate(`analyse/training/block/4?window=${readout.window}`)} testid="open-in-encode">Open in Encode</Button>
          </div>
        </SectionCard>

        <div className="tr-stack">
          <SectionCard title="Feature groups" testid="groups-card"
            info="A group is included or not as a whole — the clustering in 03 sees exactly the ticked columns.">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.groups.map(g => (
                <Checkbox key={g.id} checked={!!p.groups[g.id]} onChange={() => toggleGroup(g)} testid={`group-${g.id}`}
                  label={<span>{g.label} <span className="tr-muted tr-small">{g.count}{g.labelDerived ? ' · label-derived' : ''}</span></span>} />
              ))}
            </div>
            <Callout tone="amber" icon="alert-triangle" testid="label-derived-warning">{MATRIX.labelDerivedWarning}</Callout>
            <div className="tr-kv" data-testid="windows-from">
              <span className="tr-muted tr-small">windows from 01</span>
              <span className="tr-mono tr-small">{MATRIX.windowsFrom}</span>
              <Button variant="link" size="sm" onClick={() => navigate('analyse/training/block/1')} testid="edit-windows">edit</Button>
            </div>
            <div className="tr-kv">
              <span className="tr-muted tr-small">columns in 03</span>
              <span className="tr-mono tr-small" data-testid="column-count">{fmtInt(nCols)} features × {fmtInt(WINDOWS.total)} windows</span>
            </div>
          </SectionCard>

          <SectionCard title="Compute" testid="compute-card">
            <Callout tone="green" icon="check-circle" testid="compute-cached">
              <b className="tr-mono">{MATRIX.compute.state} · {MATRIX.compute.recipe}</b><br />
              <span className="tr-mono">{MATRIX.compute.where}</span>
            </Callout>
            <Callout tone="grey" icon="hourglass" testid="compute-local">{MATRIX.compute.localNote}</Callout>
            <div className="tr-row-flex" style={{ marginTop: 8 }}>
              <Button icon="terminal" onClick={() => setModal('slurm')} testid="create-slurm">Create SLURM script</Button>
              <Button icon="upload" onClick={() => setModal('upload')} testid="upload-matrix">Upload matrix</Button>
            </div>
            <StatTile variant="flat" label="local ceiling" value={MATRIX.compute.localLimit} caption="above it, the work goes to the cluster" tone="amber" />
          </SectionCard>
        </div>
      </div>

      <Modal open={modal === 'slurm'} onClose={() => setModal(null)} size="lg" title="Create SLURM script"
        subtitle="02 Window matrix · the cluster runs it and the manifest comes back through Jobs (P4)" testid="slurm-modal"
        footerNote="the script is a file you run — nothing here submits it for you"
        footer={<><Button onClick={() => setModal(null)}>Close</Button>
          <Button variant="primary" icon="inbox" testid="slurm-create-job" onClick={() => {
            const id = `j-0${218 + Math.floor(Math.random() * 9)}`
            recordDemoWrite('jobs', 'add-job', { id, kind: 'cluster', title: `02 Window matrix · ${draft.name}`, status: 'queue', detail: 'awaiting manifest · uob-bc4', for: 'Analyse › Training' })
            setModal(null)
            push({ text: `${id} added to Jobs · in memory (demo)`, action: { label: 'Open in Jobs', onClick: () => navigate('jobs') } })
          }}>Track it in Jobs</Button></>}>
        <CodeBlock title="SLURM script" code={SLURM_MATRIX} filename={`matrix_${draft.name}.sh`} lineNumbers />
      </Modal>

      <Modal open={modal === 'upload'} onClose={() => setModal(null)} size="md" title="Upload matrix"
        subtitle="place a matrix computed elsewhere · it is checked before it is bound to the recipe" testid="upload-modal"
        footer={<><Button onClick={() => setModal(null)}>Cancel</Button>
          <Button variant="primary" icon="upload" testid="upload-confirm"
            onClick={() => { setModal(null); notWired('bind an uploaded matrix artifact to recipe a7f3…9c') }}>Place matrix</Button></>}>
        <TextField value="cluster_out/manifest.json" onChange={() => {}} block variant="outline" ariaLabel="manifest path" testid="upload-path" />
        <div style={{ marginTop: 10 }}>
          <Checklist testid="upload-checks" items={[
            { label: 'recipe hash matches a7f3…9c', state: 'pass' },
            { label: '543 columns · one per window in 01', state: 'pass' },
            { label: 'feature order matches the ticked groups', state: 'pending' },
          ]} />
        </div>
        <div style={{ marginTop: 10 }}>
          <KeyValue dense items={[
            { k: 'from', v: 'Jobs › Manifest inbox' },
            { k: 'refused', v: 'M4_aug — held out (D6)', tone: 'red' },
          ]} />
        </div>
      </Modal>

      <SaveTemplateModal open={modal === 'save-template'} onClose={() => setModal(null)} defaultName={draft.name}
        stages={chain.filter(b => b.index != null).map(b => b.label)}
        onSaved={n => setDraft(d => ({ ...d, name: n, saved: true }))} />
      {included.length === 0 && <Badge status="invalid">no feature group is included — 03 has nothing to cluster</Badge>}
    </BlockFrame>
  )
}
