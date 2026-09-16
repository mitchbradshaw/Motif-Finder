/* models.registry (frame models-5; spec §7b.5, P19). The list of models with their status and what uses them, and the
 * three-part registration gate: automatic held-out checks, human verification judged in Review, and a written
 * decision. Retiring is blocked while a template uses the model; rejected models keep their failed checks. */
import { useRef } from 'react'
import {
  Badge, BlockGlyph, Button, Checkbox, Chip, Icon, InfoTip, KeyValue, Modal, Page, Popover, ProgressBar,
  SectionCard, Seg, SelectField, StatRow, StatTile, TextField, fmtPct, recordDemoWrite, useDemoState, useQueryState,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, setQuery, useApp } from '../state'
import { useSourced } from '../api/seam'
import {
  CLASS_COLOUR, MODEL_CLASSES, REGISTRY_NOTE, getRegistry,
  type ModelClass, type RegistryModel, type RegistryStatus, type Verification,
} from '../api/models'
import { Loading, LoadFailed, ModelsTabs, TrainingJobsLink, f2 } from './chrome'

const NAME_RE = /^[a-z0-9_]{3,60}$/
const FILTERS: { value: string; label: string }[] = [
  { value: 'all', label: 'all' }, { value: 'registered', label: 'registered' }, { value: 'candidates', label: 'candidates' }, { value: 'retired', label: 'retired' },
]
const STATUS_TONE: Record<RegistryStatus, 'grey' | 'green' | 'amber' | 'red'> = { candidate: 'grey', registered: 'green', retired: 'amber', rejected: 'red' }
const FRAME_REASON = 'Burst is under-sampled on the test block; its suggested threshold (0.71) is conservative. Re-check when the sep14 window set adds CH7 burst verdicts.'

type Edit = { status?: RegistryStatus; verification?: Verification; signoff?: RegistryModel['signoff']; registeredAs?: string; session?: boolean }

export function RegistryPage() {
  const { route } = useApp()
  const reg = useSourced(getRegistry, [])
  const selectedId = route.parts[1] || 'cnn_windows_v3.manual'
  return (
    <>
      <Header workspace="Models" page="Registry" subtitle="register · version · retire" demo={reg.source === 'demo'} />
      <Page testid="models-registry">
        <div className="m-toolbar" data-testid="registry-toolbar">
          <span className="m-tool-chip strong"><Icon name="library" size={13} />model registry</span>
        </div>
        <ModelsTabs current="registry" jobsLink={<TrainingJobsLink base={2} />} />
        {reg.error ? <LoadFailed what="the model registry" error={reg.error} onRetry={reg.reload} />
          : !reg.data ? <Loading />
            : <RegistryBody models={reg.data} selectedId={selectedId} />}
      </Page>
    </>
  )
}

function RegistryBody({ models: fixture, selectedId }: { models: RegistryModel[]; selectedId: string }) {
  const { push } = useToast()
  const [filter, setFilter] = useQueryState('filter', 'all')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [confirm, setConfirm] = useQueryState('confirm', '')
  const [popover, setPopover] = useQueryState('popover', '')
  const [edits, setEdits] = useDemoState<Record<string, Edit>>('models.registry.edits', () => ({}))

  const models = fixture.map(m => ({ ...m, ...edits[m.id] }))
  const selected = models.find(m => m.id === selectedId) ?? models[0]
  const rows = models.filter(m => filter === 'all' ? true
    : filter === 'registered' ? m.status === 'registered'
      : filter === 'candidates' ? m.status === 'candidate'
        : m.status === 'retired' || m.status === 'rejected')

  const blocked = models.find(m => m.status === 'registered' && m.usedBy.length > 0)
  const usedByModel = selected.usedBy.length ? selected : blocked

  const write = (id: string, patch: Edit) => setEdits(e => ({ ...e, [id]: { ...e[id], ...patch } }))

  return (
    <>
      <div className="m-cols half">
        {/* ------------------------------------------------ left: the list ------------------------------------------------ */}
        <div className="m-stack">
          <SectionCard title="Models" testid="models-card"
            info="Every model this installation has scored. A candidate has results but no sign-off; a registered model can be inserted in Analyse as a Model stage; a retired one can be restored; a rejected one keeps the checks it failed."
            actions={<Seg size="sm" testid="status-filter" ariaLabel="status filter" options={FILTERS} value={filter} onChange={v => setFilter(v === 'all' ? null : v)} />}>
            <table className="m-table" data-testid="models-table">
              <thead><tr><th>model · version</th><th>status</th><th className="num">test F1</th><th>used by</th><th /></tr></thead>
              <tbody>
                {rows.map(m => (
                  <ModelRow key={m.id} m={m} selected={m.id === selected.id} onSelect={() => navigate(`models/registry/${m.id}`)}
                    onAct={act => setQuery({ confirm: act })} popover={popover} setPopover={setPopover} session={!!edits[m.id]?.session} />
                ))}
                {rows.length === 0 && <tr><td colSpan={5} className="m-muted">no model has this status yet</td></tr>}
              </tbody>
            </table>
            {blocked && (
              <div className="m-lock-note" style={{ marginTop: 10 }} data-testid="retire-lock">
                <Icon name="lock" size={15} />
                <div>
                  <div className="t">Retire is blocked while a template uses the model</div>
                  <div className="m-muted">{blocked.name} {`v${blocked.version}`} → {blocked.usedBy.map(u => u.template).join(', ')} · replace the stage first</div>
                </div>
              </div>
            )}
          </SectionCard>

          <SectionCard title={usedByModel ? `Used by · ${usedByModel.name} · v${usedByModel.version}` : 'Used by'} testid="used-by-card"
            info="A template that names this model runs it as a Model stage; the Discovery runs counted here used that template.">
            {!usedByModel || usedByModel.usedBy.length === 0 ? (
              <div className="m-mono m-small m-muted" data-testid="used-by-none">no template uses this model — it can be retired without replacing a stage</div>
            ) : usedByModel.usedBy.map(u => (
              <div key={u.template} className="m-usedby" style={{ marginBottom: 6 }} data-testid={`used-by-${u.template}`}>
                <Icon name="layers" size={14} />
                <span><span className="t">{u.template}</span> <span className="s">{u.signature}</span></span>
                <span className="r">used in {u.discoveryRuns} Discovery run{u.discoveryRuns === 1 ? '' : 's'}</span>
                <Button size="sm" variant="link" icon="external" onClick={() => navigate('analyse/chain')} testid={`open-${u.template}`}>Open</Button>
              </div>
            ))}
            <div className="m-mono m-small m-muted" style={{ marginTop: 8 }}>{REGISTRY_NOTE}</div>
          </SectionCard>
        </div>

        {/* ------------------------------------------------ right: the gate ------------------------------------------------ */}
        {selected.status === 'candidate'
          ? <RegisterPanel m={selected} simulate={stateQ === 'verified'} onSimulate={() => { setStateQ('verified'); push({ text: 'simulated: the last 7 verification windows came back from Review' }) }}
            onWrite={write} push={push} onConfirm={c => setQuery({ confirm: c })} />
          : <DecidedPanel m={selected} onConfirm={c => setQuery({ confirm: c })} />}
      </div>

      {/* ------------------------------------------------ confirms ------------------------------------------------ */}
      <Modal open={confirm === 'retire'} onClose={() => setConfirm(null)} title={`Retire ${selected.name}?`} size="sm" testid="retire-modal"
        footerNote="retiring changes nothing already detected — it only stops the model being inserted again"
        footer={<><Button onClick={() => setConfirm(null)}>Cancel</Button>
          <Button variant="danger-solid" testid="retire-confirm" onClick={() => {
            write(selected.id, { status: 'retired', session: true }); recordDemoWrite('models', 'retire', { id: selected.id })
            setConfirm(null); push({ text: `${selected.name} retired · this session` })
          }}>Retire</Button></>}>
        <p className="m-mono m-small">A retired model keeps its results, its checks and its sign-off. It disappears from Analyse’s insert modal and can be restored from this page.</p>
      </Modal>

      <Modal open={confirm === 'restore'} onClose={() => setConfirm(null)} title={`Restore ${selected.name}?`} size="sm" testid="restore-modal"
        footer={<><Button onClick={() => setConfirm(null)}>Cancel</Button>
          <Button variant="primary" testid="restore-confirm" onClick={() => {
            write(selected.id, { status: 'registered', session: true }); recordDemoWrite('models', 'restore', { id: selected.id })
            setConfirm(null); push({ text: `${selected.name} restored · this session` })
          }}>Restore</Button></>}>
        <p className="m-mono m-small">It goes back to registered with the sign-off it already had ({selected.signoff?.at ?? 'no sign-off recorded'}). Nothing is re-checked.</p>
      </Modal>

      <RejectModal open={confirm === 'reject'} m={selected} onClose={() => setConfirm(null)}
        onReject={reason => {
          write(selected.id, { status: 'rejected', session: true, signoff: { actor: 'this installation', at: 'this session', reason, name: selected.registeringAs ?? selected.id, version: `v${selected.version}` } })
          recordDemoWrite('models', 'reject', { id: selected.id, reason }); setConfirm(null); push({ text: `${selected.name} rejected · it keeps its checks` })
        }} />
    </>
  )
}

/* ---------------------------------------------------------------- list row ---------------------------------------------------------------- */
function ModelRow({ m, selected, onSelect, onAct, popover, setPopover, session }: {
  m: RegistryModel; selected: boolean; onSelect: () => void; onAct: (act: string) => void
  popover: string; setPopover: (v: string | null) => void; session: boolean
}) {
  const whyRef = useRef<HTMLButtonElement>(null)
  const used = m.usedBy.length
  return (
    <tr className={`m-reg-row m-row-click ${selected ? 'on' : ''}`} onClick={onSelect} data-testid={`model-row-${m.id}`}
      aria-selected={selected} title={`open ${m.name}`}>
      <td>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BlockGlyph name="model" width={34} height={22} />
          <span>
            <span className="m-reg-name">{m.name}</span>
            <div className="m-reg-sub">v{m.version} · {m.from}{session ? ' · this session' : ''}</div>
          </span>
        </div>
      </td>
      <td><Badge tone={STATUS_TONE[m.status]} size="sm">{m.status}</Badge></td>
      <td className={`num ${m.status === 'rejected' ? 'm-red-text' : ''}`}>{f2(m.testF1)}</td>
      <td className="m-muted">{used ? `${used} template${used === 1 ? '' : 's'}` : '—'}</td>
      <td onClick={e => e.stopPropagation()}>
        {m.status === 'registered' && (
          <Button size="sm" testid={`retire-${m.id}`} disabled={used > 0} disabledReason={used ? `used by ${used} template${used === 1 ? '' : 's'} · replace the stage first` : undefined}
            onClick={() => { onSelect(); onAct('retire') }}>Retire</Button>
        )}
        {m.status === 'retired' && <Button size="sm" testid={`restore-${m.id}`} onClick={() => { onSelect(); onAct('restore') }}>Restore</Button>}
        {m.status === 'rejected' && (
          <>
            <Button size="sm" ref={whyRef} testid={`why-${m.id}`} onClick={() => setPopover(popover === 'why' ? null : 'why')}>Why</Button>
            <Popover open={popover === 'why'} onClose={() => setPopover(null)} anchorRef={whyRef} title="Rejected because" width={340} testid="why-popover">
              <ul className="m-mono m-small" style={{ margin: 0, paddingLeft: 16 }}>
                {(m.rejectedBecause ?? ['no reason recorded']).map(r => <li key={r} style={{ marginBottom: 4 }}>{r}</li>)}
              </ul>
              {m.signoff && <div className="m-mono m-small m-muted" style={{ marginTop: 6 }}>{m.signoff.actor} · {m.signoff.at}</div>}
            </Popover>
          </>
        )}
      </td>
    </tr>
  )
}

/* ---------------------------------------------------------------- register (candidate) ---------------------------------------------------------------- */
function RegisterPanel({ m, simulate, onSimulate, onWrite, push, onConfirm }: {
  m: RegistryModel; simulate: boolean; onSimulate: () => void
  onWrite: (id: string, patch: Edit) => void; push: (t: { text: string }) => number; onConfirm: (c: string) => void
}) {
  const [name, setName] = useDemoState<string>(`models.registry.name.${m.id}`, () => m.registeringAs ?? m.id.replace(/\./g, '_'))
  const [version, setVersion] = useDemoState<string>(`models.registry.version.${m.id}`, () => 'v1')
  const [reason, setReason] = useDemoState<string>(`models.registry.reason.${m.id}`, () => (m.id === 'cnn_windows_v3.manual' ? FRAME_REASON : ''))
  const [ticked, setTicked] = useDemoState<boolean>(`models.registry.ticked.${m.id}`, () => m.id === 'cnn_windows_v3.manual')

  const base = m.verification
  const v: Verification = simulate && base.judged < base.of
    ? { ...base, judged: base.of, agree: Math.round(base.of * (base.agree / Math.max(1, base.judged))), perClass: base.perClass }
    : base
  const left = v.of - v.judged
  const failed = m.checks.filter(c => c.state === 'fail')
  const warned = m.checks.filter(c => c.state === 'warn')
  const nameError = !NAME_RE.test(name) ? 'lowercase letters, digits and _ only (3–60)'
    : name === 'cnn_windows_v2_manual' ? 'already registered · pick a new name or version' : null
  const reasonError = warned.length && reason.trim().length < 20 ? 'a warning needs a written reason (at least 20 characters)' : null

  const blocker = failed.length ? `${failed[0].label} failed — a failed check blocks registration`
    : left > 0 ? `sign-off waits on verification · ${left} window${left === 1 ? '' : 's'} left`
      : nameError ? `registered name: ${nameError}`
        : reasonError ? reasonError
          : !ticked ? 'tick the confirmation — the researcher has the final say'
            : null

  return (
    <SectionCard title={`Register ${m.name}`} testid="register-card"
      info="Three parts, in order: the automatic checks, a judged sample, and your written decision. The first two inform; only the third registers anything."
      actions={<Badge tone={STATUS_TONE[m.status]}>{m.status}</Badge>}>

      {/* 1 · held-out checks */}
      <div className="m-sub-h"><h5>1 · Held-out checks</h5><span>automatic · failures block · warnings need a reason</span></div>
      <div data-testid="checks">
        {m.checks.map(c => (
          <div key={c.label} className="m-check-row" data-state={c.state}>
            <Icon name={c.state === 'pass' ? 'check-circle' : c.state === 'warn' ? 'alert-triangle' : 'x-circle'} size={15}
              className={c.state === 'pass' ? 'm-green-text' : c.state === 'warn' ? 'm-amber-text' : 'm-red-text'} title={c.state} />
            <span>{c.label}</span>
            <span className={c.state === 'pass' ? 'm-muted' : c.state === 'warn' ? 'm-amber-text' : 'm-red-text'}>{c.detail}</span>
          </div>
        ))}
      </div>

      {/* 2 · human verification */}
      <div className="m-sub-h" style={{ marginTop: 12 }}><h5>2 · Human verification</h5><span>a stratified sample of test-block predictions, judged in Review</span></div>
      <ProgressBar value={v.judged / v.of} tone="green" label={`${v.judged} / ${v.of} judged`} labelPosition="right" testid="verification-progress" />
      <StatRow columns={5} style={{ marginTop: 8 }}>
        <StatTile size="sm" label="agree with model" value={`${v.agree} / ${v.judged}`} caption={v.judged ? fmtPct(v.agree / v.judged) : 'not started'} tone={v.judged ? 'green' : 'muted'} testid="agree-tile" />
        {v.perClass.map(p => (
          <StatTile key={p.cls} size="sm" label={p.cls} value={`${p.agree} / ${p.judged}`} caption="agree"
            tone={p.judged && p.agree / p.judged < 0.7 ? 'amber' : undefined} />
        ))}
      </StatRow>
      <div className="m-foot-line" style={{ marginTop: 8 }}>
        <Button size="sm" icon="external" testid="open-sample" onClick={() => { push({ text: `verification sample q-19 opened in Review · ${left} left` }); navigate('review/queue/q-19') }}>Open sample in Review</Button>
        <Button size="sm" variant="link" icon="plus" testid="add-20" onClick={() => {
          onWrite(m.id, { verification: { ...v, of: v.of + 20 } })
          recordDemoWrite('review', 'add-queue', { id: 'q-19', source: m.name, kind: 'review', count: 20, blind: true })
          push({ text: `20 more windows queued in Review · q-19 now ${v.of + 20}` })
        }}>Add 20 more</Button>
        <span className="k-spacer" />
        {v.note && <span>{v.note}</span>}
        {left > 0 && <Button size="sm" variant="link" testid="simulate-verification" onClick={onSimulate}>simulate the last {left} judgements</Button>}
      </div>

      {/* 3 · decision */}
      <div className="m-sub-h" style={{ marginTop: 14 }}><h5>3 · Decision</h5><span>the researcher has the final say</span></div>
      <div className="m-grid3" style={{ gap: 10 }}>
        <label className="m-mono m-small" style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'flex-start' }}>
          <span className="m-muted">registered name <InfoTip title="Registered name">The name Analyse’s insert modal shows. It must be unique across registered models; a new version of the same model keeps the name and raises the version.</InfoTip></span>
          <TextField value={name} onChange={setName} invalid={!!nameError} block testid="registered-name" />
          {nameError && <span className="m-red-text" data-testid="name-error">{nameError}</span>}
        </label>
        <label className="m-mono m-small" style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'flex-start' }}>
          <span className="m-muted">version <InfoTip title="Version">v1 is the first registration of this name. A later retrain of the same template registers as v2 and supersedes it.</InfoTip></span>
          <SelectField value={version} onChange={setVersion} width="100%" testid="version-select"
            options={[{ value: 'v1', label: 'v1' }, { value: 'v2', label: 'v2', disabled: true, reason: 'v1 is not registered yet' }]} />
        </label>
        <label className="m-mono m-small" style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'stretch' }}>
          <span className="m-muted">classes <InfoTip title="Classes">The classifier stage decided this: four informative classes, multi-class. It cannot be changed here.</InfoTip></span>
          <SelectField value="4" onChange={() => { }} width="100%" disabled disabledReason="the template’s classifier stage decides the classes" testid="classes-select"
            options={[{ value: '4', label: `${MODEL_CLASSES.length} classes` }]} />
        </label>
      </div>
      <div style={{ marginTop: 10 }}>
        <span className="m-mono m-small m-muted">reason for accepting the warning</span>
        <TextField multiline value={reason} onChange={setReason} block invalid={!!reasonError} testid="reason-field"
          placeholder={warned.length ? `why ${warned[0].label} is acceptable` : 'no warning to explain'} />
        {reasonError && <span className="m-red-text m-small" data-testid="reason-error">{reasonError}</span>}
      </div>
      <div className="m-foot-line" style={{ marginTop: 10 }}>
        <Checkbox checked={ticked} onChange={setTicked} testid="confirm-check" label="I have read the checks and judged the sample" />
        <span className="k-spacer" />
        {blocker && <span data-testid="register-blocker">{blocker}</span>}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
        <Button variant="danger" icon="x-circle" testid="reject" onClick={() => onConfirm('reject')}>Reject</Button>
        <span className="k-spacer" />
        <Button testid="save-draft" onClick={() => { recordDemoWrite('models', 'save-draft', { id: m.id, name, version, reason }); push({ text: `draft saved for ${m.name} · this session` }) }}>Save draft</Button>
        <Button variant="primary" testid="register" disabled={!!blocker} disabledReason={blocker ?? undefined}
          onClick={() => {
            onWrite(m.id, {
              status: 'registered', session: true, registeredAs: name, verification: v,
              signoff: { actor: 'this installation', at: 'this session', reason: reason || 'no warning accepted', name, version },
            })
            recordDemoWrite('models', 'register', { id: m.id, name, version, reason })
            push({ text: `${name} ${version} registered · it now appears in Analyse’s insert modal` })
          }}>Register {version}</Button>
      </div>
      <div className="m-after-row" style={{ marginTop: 12 }} data-testid="after-registering">
        <Icon name="layers" size={15} />
        <div><strong>After registering</strong>
          <div className="d">appears in Analyse’s insert modal as a Model stage · usable in detection templates run by Discovery</div></div>
      </div>
    </SectionCard>
  )
}

/* ---------------------------------------------------------------- registered / retired / rejected ---------------------------------------------------------------- */
function DecidedPanel({ m, onConfirm }: { m: RegistryModel; onConfirm: (c: string) => void }) {
  const used = m.usedBy.length
  return (
    <SectionCard title={`${m.name} · v${m.version}`} testid="decided-card"
      info="A model that has already been decided. Its sign-off, the checks it passed or failed, and the thresholds Analyse offers when it is inserted."
      actions={<Badge tone={STATUS_TONE[m.status]}>{m.status}</Badge>}>
      {m.signoff && (
        <>
          <div className="m-sub-h"><h5>Sign-off</h5><span>recorded with the model (§11)</span></div>
          <KeyValue items={[
            { k: 'registered as', v: m.signoff.name },
            { k: 'version', v: m.signoff.version },
            { k: 'by', v: m.signoff.actor },
            { k: 'at', v: m.signoff.at },
            { k: 'reason', v: m.signoff.reason },
          ]} lines />
        </>
      )}
      {m.status === 'rejected' && m.rejectedBecause && (
        <>
          <div className="m-sub-h" style={{ marginTop: 12 }}><h5>Rejected because</h5><span>the failed checks are kept</span></div>
          <ul className="m-mono m-small m-red-text" style={{ margin: 0, paddingLeft: 16 }} data-testid="rejected-because">
            {m.rejectedBecause.map(r => <li key={r} style={{ marginBottom: 3 }}>{r}</li>)}
          </ul>
        </>
      )}
      <div className="m-sub-h" style={{ marginTop: 12 }}><h5>Held-out checks</h5><span>as they stood at sign-off</span></div>
      <div data-testid="decided-checks">
        {m.checks.map(c => (
          <div key={c.label} className="m-check-row" data-state={c.state}>
            <Icon name={c.state === 'pass' ? 'check-circle' : c.state === 'warn' ? 'alert-triangle' : 'x-circle'} size={15}
              className={c.state === 'pass' ? 'm-green-text' : c.state === 'warn' ? 'm-amber-text' : 'm-red-text'} title={c.state} />
            <span>{c.label}</span><span className="m-muted">{c.detail}</span>
          </div>
        ))}
      </div>
      {m.thresholds ? (
        <>
          <div className="m-sub-h" style={{ marginTop: 12 }}><h5>Calibration thresholds</h5><span>Analyse offers these as the Threshold stage’s recommended values</span></div>
          <div className="m-foot-line" data-testid="thresholds">
            {MODEL_CLASSES.map(cls => (
              <span key={cls} className="m-pill"><span className="m-dot" style={{ background: CLASS_COLOUR[cls as ModelClass] }} />{cls} {m.thresholds![cls].toFixed(2)}</span>
            ))}
          </div>
        </>
      ) : (
        <div className="m-mono m-small m-muted" style={{ marginTop: 12 }} data-testid="thresholds-unavailable">calibration thresholds: unavailable — this model was rejected before calibration was accepted</div>
      )}
      <div className="m-sub-h" style={{ marginTop: 12 }}><h5>Verification</h5><span>the sample judged in Review</span></div>
      <ProgressBar value={m.verification.judged / m.verification.of} tone="green" label={`${m.verification.judged} / ${m.verification.of} judged · ${m.verification.judged ? fmtPct(m.verification.agree / m.verification.judged) : '0 %'} agree`} testid="decided-verification" />
      <div style={{ display: 'flex', gap: 8, marginTop: 14, alignItems: 'center' }}>
        {m.status === 'registered' && (
          <Button variant="danger" icon="trash" testid="retire-panel" disabled={used > 0} onClick={() => onConfirm('retire')}
            disabledReason={used ? `used by ${used} template${used === 1 ? '' : 's'} · replace the stage first` : undefined}>Retire</Button>
        )}
        {m.status === 'retired' && <Button variant="primary" icon="undo" testid="restore-panel" onClick={() => onConfirm('restore')}>Restore</Button>}
        {m.status === 'rejected' && <Chip tone="red" testid="rejected-chip">rejected · a new job would register a new candidate</Chip>}
        <span className="k-spacer" />
        <Button variant="link" icon="bar-chart" onClick={() => navigate('models/results')} testid="open-results">Open its results</Button>
      </div>
    </SectionCard>
  )
}

function RejectModal({ open, m, onClose, onReject }: { open: boolean; m: RegistryModel; onClose: () => void; onReject: (reason: string) => void }) {
  const [reason, setReason] = useDemoState<string>(`models.registry.rejectReason.${m.id}`, () => '')
  const short = reason.trim().length < 10
  return (
    <Modal open={open} onClose={onClose} title={`Reject ${m.name}?`} size="sm" testid="reject-modal"
      footerNote="a rejected model keeps its checks and its results — nothing is deleted"
      footer={<><Button onClick={onClose}>Cancel</Button>
        <Button variant="danger-solid" testid="reject-confirm" disabled={short} disabledReason="say why in a sentence (at least 10 characters)"
          onClick={() => onReject(reason.trim())}>Reject</Button></>}>
      <p className="m-mono m-small">The reason is recorded with the model, like a sign-off, so the next person sees why this candidate was not used.</p>
      <TextField multiline block value={reason} onChange={setReason} placeholder="why this candidate is not worth registering" testid="reject-reason" />
    </Modal>
  )
}
