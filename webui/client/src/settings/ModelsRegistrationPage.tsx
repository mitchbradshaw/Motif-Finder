/* Settings › Models & registration (frame settings-09 · spec §9.9, P12, P19) — LIVE (Prompt 02).
 * Defaults for new training jobs and the checks a model must pass to be registered (the settings table),
 * plus the registered models: real checkpoints (MODELS/*.pth) and classifier joblibs (DATA/derived/models)
 * with their sidecar manifests, and the ones on disk that are not registered yet (GET /api/registry/model). */
import { useEffect, useState } from 'react'
import { Badge, Button, Callout, Checklist, Chip, Modal, NumberField, SectionCard, Table, TextField, Toggle, CodeBlock, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { ApiError, checkCandidate, registerCandidate, unregisterRow, type Candidate, type CheckReport, type RegisteredArtifact } from '../api'
import { getModelsRegistration } from '../api/settings'
import { useToast } from '../shell/Toast'
import { LoadFailed, Loading, LockedChip, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function ModelsRegistrationPage() {
  const rd = useSourced(getModelsRegistration, [])
  return (
    <SettingsShell slug="models-registration" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the registration gate" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} reload={rd.reload} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getModelsRegistration>>['data']

const fmtBytes = (b: number | null) => b == null ? '—' : b >= 1e9 ? `${(b / 1e9).toFixed(2)} GB` : `${(b / 1e6).toFixed(1)} MB`

function Body({ data, reload }: { data: Data; reload: () => void }) {
  const s = useSettingsPage('models-registration')
  const test = s.num('test_pct'), val = s.num('validation_pct')
  const splitBad = test + val > 60
  const armManual = s.bool('arm.manual'), armCluster = s.bool('arm.cluster')
  const noArm = !armManual && !armCluster
  useEffect(() => {
    s.markInvalid('test_pct', splitBad ? 'Leave at least 40 % of windows for training' : null)
    s.markInvalid('arm.manual', noArm ? 'A training job needs at least one label arm' : null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [splitBad, noArm])

  return (
    <>
      <RegisteredModels registered={data.registered} candidates={data.candidates} roots={data.roots} mode={data.mode} reload={reload} />

      <SectionCard title="Evaluation split" subtitle="set aside before training" testid="split-card">
        <Row label="test portion" id="f-test-portion" dot={s.differs('test_pct') || s.differs('validation_pct')} unsaved={s.dirty('test_pct') || s.dirty('validation_pct')}
          testid="split-row" caption={splitBad ? 'Leave at least 40 % of windows for training' : 'applies to new training jobs · registered models keep their split'}>
          <NumberField value={test} min={5} max={40} integer unit="%" width={100} onValid={v => s.set('test_pct', v)} testid="test-pct" />
          <span className="mono small">validation</span>
          <NumberField value={val} min={5} max={40} integer unit="%" width={100} onValid={v => s.set('validation_pct', v)} testid="validation-pct" />
          {splitBad && <span className="small" style={{ color: 'var(--red)' }} data-testid="split-error">test + validation must leave 40 % for training</span>}
        </Row>
        <Row label="split" testid="split-locked-row" caption="never a random sample of windows">
          <LockedChip reason="blocked by time within each channel (P12)" testid="split-locked">blocked by time within each channel</LockedChip>
        </Row>
        <Row label="gap between blocks" dot={s.differs('gap_extra')} unsaved={s.dirty('gap_extra')} testid="gap-row"
          caption="the minimum is one window and cannot go lower">
          <span className="mono small">≥ window +</span>
          <NumberField value={s.num('gap_extra')} min={0} max={86400} integer unit="s" width={110} testid="gap-extra"
            onValid={v => { s.set('gap_extra', v); s.markInvalid('gap_extra', null) }}
            onChange={(_r, reason) => s.markInvalid('gap_extra', reason ? 'The gap cannot go below one window' : null)} />
        </Row>
        <Row label="linked recordings" testid="linked-row" caption="an excerpt and its parent stay on one side">
          <LockedChip reason="linked recordings (an excerpt and its parent) are never split across sides" testid="linked-locked">never split across sides</LockedChip>
        </Row>
        <Row label="warn below N test windows per class" dot={s.differs('warn_below')} unsaved={s.dirty('warn_below')} testid="warn-row"
          caption={`classes with fewer than ${s.num('warn_below')} test windows warn at launch`}>
          <NumberField value={s.num('warn_below')} min={1} max={1000} integer width={110} onValid={v => s.set('warn_below', v)} testid="warn-below" />
        </Row>
      </SectionCard>

      <SectionCard title="Training" testid="training-card">
        <Row label="label arms" dot={s.differs('arm.manual') || s.differs('arm.cluster')} unsaved={s.dirty('arm.manual') || s.dirty('arm.cluster')}
          testid="arms-row" caption="the random-forest baseline is always trained">
          <Chip tone={armManual ? 'green' : 'grey'} selected={armManual} onClick={() => s.set('arm.manual', !armManual)} testid="arm-manual">manual</Chip>
          <Chip tone={armCluster ? 'purple' : 'grey'} selected={armCluster} onClick={() => s.set('arm.cluster', !armCluster)} testid="arm-cluster">cluster</Chip>
          <LockedChip reason="the random-forest baseline is always trained" testid="arm-rf">RF baseline</LockedChip>
          {noArm && <span className="small" style={{ color: 'var(--red)' }} data-testid="arms-error">A training job needs at least one label arm</span>}
        </Row>
        <Row label="train on windows labelled in every arm" dot={s.differs('intersect_labelled')} unsaved={s.dirty('intersect_labelled')} testid="intersect-row"
          caption="keeps the arm comparison paired">
          <Toggle checked={s.bool('intersect_labelled')} onChange={v => s.set('intersect_labelled', v)} testid="intersect-labelled" />
        </Row>
        {!s.bool('intersect_labelled') && <Callout tone="amber" testid="intersect-warning">arms would train on different windows; the comparison is no longer paired</Callout>}
        <Row label="repeat with different seeds" dot={s.differs('repeats_on')} unsaved={s.dirty('repeats_on') || s.dirty('repeats_n')} testid="repeats-row"
          caption="a repeat is a full retrain">
          <Toggle checked={s.bool('repeats_on')} onChange={v => s.set('repeats_on', v)} testid="repeats-on" />
          <NumberField value={s.num('repeats_n')} min={2} max={10} integer unit="repeats" width={130} testid="repeats-n"
            disabled={!s.bool('repeats_on')} disabledReason="turn on seed repeats to set a count" onValid={v => s.set('repeats_n', v)} />
        </Row>
        <Row label="early stopping patience" dot={s.differs('patience')} unsaved={s.dirty('patience')} testid="patience-row" caption="epochs without improvement">
          <NumberField value={s.num('patience')} min={1} max={100} integer unit="epochs" width={130} onValid={v => s.set('patience', v)} testid="patience" />
        </Row>
      </SectionCard>

      <SectionCard title="Calibration" subtitle="per class, on the validation block" testid="calibration-card">
        <Row label="suggested threshold at precision" dot={s.differs('precision')} unsaved={s.dirty('precision')} testid="precision-row"
          caption="shown in the Threshold stage as its recommended value">
          <NumberField value={s.num('precision')} min={0.5} max={0.99} step={0.01} width={110} onValid={v => s.set('precision', v)} testid="precision" />
        </Row>
        <Row label="reliability bins" dot={s.differs('bins')} unsaved={s.dirty('bins')} testid="bins-row" caption="bins in the reliability diagram">
          <NumberField value={s.num('bins')} min={5} max={50} integer width={100} onValid={v => s.set('bins', v)} testid="bins" />
        </Row>
      </SectionCard>

      <SectionCard title="Registration gate" subtitle="the researcher has the final say" testid="gate-card">
        <Table rows={data.gate} rowKey={g => g.id} testid="gate-table" dense
          columns={[
            { key: 'check', header: 'check', width: '40%', render: g => <b>{g.label}</b> },
            {
              key: 'threshold', header: 'threshold', width: '34%', render: g => g.locked
                ? <LockedChip reason="enforced (P12, P19)" testid={`gate-locked-${g.id}`}>{g.suffix}</LockedChip>
                : (
                  <span className={s.dirty(`gate.${g.id}`) ? 'unsaved' : undefined} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <span className="mono small">{g.prefix}</span>
                    <TextField value={s.str(`gate.${g.id}`)} onChange={v => s.set(`gate.${g.id}`, v)} size="sm" width={90} testid={`gate-${g.id}`} />
                  </span>
                ),
            },
            {
              key: 'fail', header: 'if it fails', width: '26%', render: g => g.on_fail === '—'
                ? <span className="muted">—</span>
                : <Badge tone={g.on_fail === 'blocks registration' || g.on_fail === 'required' ? 'red' : 'amber'}>{g.on_fail}</Badge>,
            },
          ]} />
        <Row label="retiring a model a template still uses" testid="retire-row" caption="the list of templates is shown instead">
          <LockedChip reason="a template's model cannot be retired under it" testid="retire-locked">blocked</LockedChip>
        </Row>
      </SectionCard>
    </>
  )
}

/* ------------------------------------------------------------------ registered models (the registry, kind model) */

function RegisteredModels({ registered, candidates, roots, mode, reload }: { registered: RegisteredArtifact[]; candidates: Candidate[]; roots: string[]; mode: string; reload: () => void }) {
  const { push } = useToast()
  const [show, setShow] = useQueryState('manifest', '')
  const [busy, setBusy] = useState<string | null>(null)
  const [report, setReport] = useState<CheckReport | null>(null)
  const [producer, setProducer] = useState('')
  const [checkPath, setCheckPath] = useQueryState('check', '')
  const cand = candidates.find(c => c.path === checkPath) ?? null
  const summary = (m: Record<string, any> | null | undefined) => {
    if (!m) return '—'
    if (m.class) return `${m.class}${m.n_features_in_ != null ? ` · ${m.n_features_in_} features` : ''}${m.classes ? ` · classes ${m.classes.join('/')}` : ''}`
    return `${m.type ?? 'checkpoint'}${m.epoch != null ? ` · epoch ${m.epoch}` : ''}${m.n_params != null ? ` · ${(m.n_params / 1e6).toFixed(2)} M params` : ''}${m.n_tensors != null ? ` · ${m.n_tensors} tensors` : ''}`
  }
  const runCheck = async (c: Candidate) => {
    setBusy(c.path); setReport(null); setCheckPath(c.path)
    try { setReport(await checkCandidate('model', c.path)) } catch (e) { push({ text: e instanceof ApiError ? e.message : String(e), kind: 'error' }) } finally { setBusy(null) }
  }
  const doRegister = async (c: Candidate) => {
    setBusy(c.path)
    try {
      const r = await registerCandidate('model', c.path, {}, producer.trim() ? { producer: producer.trim() } : {})
      push({ text: `Registered ${r.name} · registered_artifacts id ${r.id} · ${r.note}` }); setCheckPath(''); setReport(null); reload()
    } catch (e) { push({ text: e instanceof ApiError ? e.message : String(e), kind: 'error' }) } finally { setBusy(null) }
  }
  const doUnregister = async (r: RegisteredArtifact) => {
    try { await unregisterRow('model', r.id); push({ text: `${r.name} unregistered · row kept inactive, file untouched` }); reload() }
    catch (e) { push({ text: e instanceof ApiError ? e.message : String(e), kind: 'error' }) }
  }
  const shown = registered.find(r => String(r.id) === show) ?? null
  return (
    <SectionCard title="Registered models" subtitle={`${registered.length} registered · ${candidates.length} on disk not registered · ${roots.join(', ')}`} testid="registered-models-card"
      footer={<span className="s-note">a registered model carries a sidecar manifest (docs/DATA_REGISTRATION.md) · {mode === 'sandbox' ? 'sandbox: rows land in the database copy' : 'project: rows land in the project database'}</span>}>
      {registered.length ? (
        <Table rows={registered} rowKey={r => String(r.id)} dense testid="registered-models-table"
          columns={[
            { key: 'name', header: 'model', width: '26%', render: r => <span className="mono" style={{ fontWeight: 600 }}>{r.name}{!r.exists && <span style={{ marginLeft: 6 }}><Badge tone="red">file missing</Badge></span>}</span> },
            { key: 'format', header: 'format', width: '9%', render: r => <Badge tone={r.params.format === 'pytorch' ? 'purple' : 'blue'}>{r.params.format ?? '—'}</Badge> },
            { key: 'summary', header: 'read from the file', width: '30%', render: r => <span className="small">{summary(r.params.summary)}</span> },
            { key: 'size', header: 'size', width: '8%', render: r => <span className="mono small">{fmtBytes(r.bytes)}</span> },
            { key: 'producer', header: 'producer', width: '12%', render: r => <span className="small muted">{r.producer ?? 'unknown'}</span> },
            {
              key: 'actions', header: '', width: '15%', render: r => <span style={{ display: 'flex', gap: 8 }}>
                <Button variant="link" size="sm" testid={`manifest-${r.id}`} onClick={() => setShow(String(r.id))}>manifest</Button>
                <Button variant="link" size="sm" testid={`unregister-model-${r.id}`} onClick={() => void doUnregister(r)}>unregister</Button>
              </span>,
            },
          ]} />
      ) : <span className="muted small" data-testid="registered-models-empty">No model is registered yet — the checkpoints below are on disk and can be registered.</span>}

      {candidates.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="s-card-sub" style={{ marginBottom: 6 }}>on disk, not registered</div>
          <Table rows={candidates} rowKey={c => c.path} dense testid="model-candidates-table" highlighted={checkPath}
            columns={[
              { key: 'name', header: 'file', width: '34%', render: c => <span className="mono">{c.name}</span> },
              { key: 'format', header: 'format', width: '10%', render: c => <Badge tone={c.facts.format === 'pytorch' ? 'purple' : 'blue'}>{c.facts.format}</Badge> },
              { key: 'size', header: 'size', width: '10%', render: c => <span className="mono small">{fmtBytes(c.facts.bytes)}</span> },
              { key: 'path', header: 'path', width: '28%', render: c => <span className="mono small muted">{c.path}</span> },
              {
                key: 'actions', header: '', width: '18%', render: c => <span style={{ display: 'flex', gap: 8 }}>
                  <Button variant="link" size="sm" testid={`check-model-${c.name}`} loading={busy === c.path} onClick={() => void runCheck(c)}>check</Button>
                  <Button variant="link" size="sm" testid={`register-model-${c.name}`} disabled={!(cand?.path === c.path && report?.ok) || busy === c.path}
                    disabledReason={cand?.path === c.path && report && !report.ok ? 'a check fails' : 'run the check first'} onClick={() => void doRegister(c)}>register</Button>
                </span>,
              },
            ]} />
          {cand && (
            <div style={{ marginTop: 8 }} data-testid="model-check-panel">
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                <b className="mono">{cand.name}</b>
                <TextField value={producer} onChange={setProducer} size="sm" width={320} placeholder="producer (recipe hash, HPC job, script) — optional" testid="model-producer" />
              </div>
              {report ? <Checklist items={[...report.checks.map(c => ({ label: `${c.name} · ${c.detail}`, state: c.ok ? 'pass' as const : 'fail' as const })), ...report.warnings.map(w => ({ label: w, state: 'warn' as const }))]} testid="model-checks" />
                : busy === cand.path ? <span className="muted small">loading the file…</span> : null}
            </div>
          )}
        </div>
      )}

      <Modal open={!!shown} onClose={() => setShow('')} title={shown ? `${shown.name} · manifest` : ''} size="md" testid="manifest-modal"
        footerNote={shown?.manifest_path ?? 'no sidecar on disk'}>
        {shown && <CodeBlock code={JSON.stringify(shown.manifest ?? { note: 'no sidecar on disk', row: { id: shown.id, path: shown.path, sha1: shown.sha1, created_at: shown.created_at } }, null, 2)} filename="registration manifest" lineNumbers testid="manifest-json" save={false} />}
      </Modal>
    </SectionCard>
  )
}
