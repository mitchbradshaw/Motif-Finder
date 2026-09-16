/* Settings › Models & registration (frame settings-09 · spec §9.9, P12, P19).
 * Defaults for new training jobs and the checks a model must pass to be registered. */
import { useEffect } from 'react'
import { Badge, Callout, Chip, NumberField, SectionCard, Table, TextField, Toggle } from '../kit'
import { useSourced } from '../api/seam'
import { getModelsRegistration } from '../api/settings'
import { LoadFailed, Loading, LockedChip, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function ModelsRegistrationPage() {
  const rd = useSourced(getModelsRegistration, [])
  return (
    <SettingsShell slug="models-registration" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the registration gate" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getModelsRegistration>>['data']

function Body({ data }: { data: Data }) {
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
        <Row label="linked recordings" testid="linked-row" caption="fs1 and fs2 of one recording stay on one side">
          <LockedChip reason="linked recordings are never split across sides" testid="linked-locked">never split across sides</LockedChip>
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
