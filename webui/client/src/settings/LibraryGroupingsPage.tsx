/* Settings › Library groupings (frame settings-10 · spec §9.10, P22, B16, B17).
 * Defaults for new groupings. Every grouping is saved with its settings. */
import { useEffect } from 'react'
import { Button, Callout, NumberField, SectionCard, Seg, SelectField, Table, TextField } from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getLibraryGroupings } from '../api/settings'
import { LoadFailed, Loading, LockedChip, LockedToggle, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function LibraryGroupingsPage() {
  const rd = useSourced(getLibraryGroupings, [])
  return (
    <SettingsShell slug="library-groupings" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the grouping defaults" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getLibraryGroupings>>['data']

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('library-groupings')
  const unit = s.str('unit')
  const bases = data.basisByUnit[unit] ?? data.basisByUnit['single motifs']
  const basis = bases.includes(s.str('basis')) ? s.str('basis') : bases[0]
  const isDistance = basis.startsWith('shape distance') || basis.startsWith('sequence similarity')
  const wShapes = s.num('w_shapes'), wGaps = s.num('w_gaps')
  const weightsBad = Math.abs(wShapes + wGaps - 1) > 0.001
  useEffect(() => {
    s.markInvalid('w_shapes', weightsBad ? 'Weights must sum to 1.0' : null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weightsBad])

  return (
    <>
      <SectionCard title="Default grouping" subtitle="used for imports and new catalogues" testid="grouping-card">
        <Row label="unit" dot={s.differs('unit')} unsaved={s.dirty('unit')} testid="unit-row" caption="what one entry in a grouping is">
          <Seg value={unit} onChange={v => s.set('unit', v)} testid="unit-seg" options={data.units.map(u => ({ value: u, label: u }))} />
        </Row>
        {unit === 'spike trains' && <Callout tone="amber" testid="spike-train-note">what a spike train is when not imported as one is undecided (B17)</Callout>}
        <Row label="basis" dot={s.differs('basis')} unsaved={s.dirty('basis')} testid="basis-row"
          caption={isDistance ? 'the linkage cut is the grouping' : 'bins come from Feature bases below'}>
          <SelectField value={basis} onChange={v => s.set('basis', v)} width={220} testid="basis"
            options={bases.map(b => ({ value: b, label: b }))} />
          {isDistance ? (
            <>
              <span className="mono small muted">cut</span>
              <NumberField value={s.num('cut')} min={0.05} max={2} step={0.01} width={100} onValid={v => s.set('cut', v)} testid="cut" />
            </>
          ) : (
            <Button variant="link" size="sm" testid="to-feature-bases"
              onClick={() => document.querySelector('[data-testid="feature-bases-card"]')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>bins set in Feature bases ↓</Button>
          )}
        </Row>
      </SectionCard>

      <SectionCard title="What does not fit" subtitle="omitted from that grouping round" testid="omit-card">
        <Row label="omit motifs with nearest family d >" id="f-omit-motifs-with-nearest-family-d-" dot={s.differs('omit_d')} unsaved={s.dirty('omit_d')} testid="omit-d-row"
          caption="omitted entries are flagged and listed">
          <NumberField value={s.num('omit_d')} min={0.05} max={2} step={0.05} width={100} testid="omit-d"
            onValid={v => { s.set('omit_d', v); s.markInvalid('omit_d', null) }}
            onChange={(_r, reason) => s.markInvalid('omit_d', reason ? 'Enter 0.05–2.00' : null)} />
          {s.num('omit_d') < 0.3 && <span className="small" style={{ color: 'var(--amber)' }} data-testid="omit-warning">
            Review suggests families up to d 0.30 — <button type="button" className="k-link" onClick={() => navigate('settings/review-queues')}>Review queues</button>
          </span>}
        </Row>
        <Row label="omit groups smaller than" dot={s.differs('omit_min')} unsaved={s.dirty('omit_min')} testid="omit-min-row" caption="a group under this is not a family">
          <NumberField value={s.num('omit_min')} min={2} max={1000} integer unit="members" width={130} onValid={v => s.set('omit_min', v)} testid="omit-min" />
        </Row>
        <Row label="omitted entries are deleted" testid="never-delete-row" caption="they are listed with the grouping instead">
          <LockedChip reason="omitted entries are flagged, never deleted" testid="never-delete">never</LockedChip>
        </Row>
      </SectionCard>

      <SectionCard title="Sequences" subtitle="shared with Review clusters" testid="sequences-card">
        <Row label="events belong to one sequence when" id="f-sequence-gap" dot={s.differs('seq_gap') || s.differs('seq_events')}
          unsaved={s.dirty('seq_gap') || s.dirty('seq_events')} testid="sequence-row"
          caption={<>also changes <button type="button" className="k-link" onClick={() => navigate('settings/review-queues?focus=cohesion-limit')}>Review clusters</button></>}>
          <span className="mono small">same run and channel, gap ≤</span>
          <NumberField value={s.num('seq_gap')} min={0.5} max={120} step={0.5} unit="min" width={110} onValid={v => s.set('seq_gap', v)} testid="seq-gap" />
          <span className="mono small">at least</span>
          <NumberField value={s.num('seq_events')} min={2} max={100} integer unit="events" width={120} onValid={v => s.set('seq_events', v)} testid="seq-events" />
        </Row>
        <Row label="sequence similarity weights" dot={s.differs('w_shapes')} unsaved={s.dirty('w_shapes') || s.dirty('w_gaps')} testid="weights-row"
          caption={weightsBad ? 'Weights must sum to 1.0' : 'weights sum to 1'}>
          <span className="mono small">event shapes</span>
          <NumberField value={wShapes} min={0} max={1} step={0.1} width={90} testid="w-shapes"
            onValid={v => { s.set('w_shapes', v); s.set('w_gaps', Number((1 - v).toFixed(1))) }} />
          <span className="mono small">gaps</span>
          <NumberField value={wGaps} min={0} max={1} step={0.1} width={90} testid="w-gaps"
            onValid={v => { s.set('w_gaps', v); s.set('w_shapes', Number((1 - v).toFixed(1))) }} />
        </Row>
      </SectionCard>

      <SectionCard title="Feature bases" subtitle="bins, no distance" testid="feature-bases-card">
        <Table rows={data.featureBases} rowKey={f => f.basis} testid="feature-bases-table" dense
          columns={[
            { key: 'basis', header: 'basis', width: '18%', render: f => <b>{f.basis}</b> },
            {
              key: 'feature', header: 'feature', width: '28%', render: f => (
                <SelectField value={s.str(`fb.${f.basis}.feature`)} onChange={v => s.set(`fb.${f.basis}.feature`, v)} size="sm" width={250} testid={`feature-${f.basis}`}
                  options={f.features.map(x => ({ value: x, label: x }))} />
              ),
            },
            {
              key: 'bins', header: 'bins', width: '18%', render: f => (
                <SelectField value={s.str(`fb.${f.basis}.bins`)} onChange={v => s.set(`fb.${f.basis}.bins`, v)} size="sm" width={150} testid={`bins-${f.basis}`}
                  disabled={f.basis === 'polarity'} disabledReason={f.basis === 'polarity' ? 'polarity has three fixed bins' : undefined}
                  options={f.bins.map(x => ({ value: x, label: x }))} />
              ),
            },
            {
              key: 'count', header: 'count', width: '14%', render: f => (
                <NumberField value={s.num(`fb.${f.basis}.count`)} min={2} max={20} integer width={90} testid={`count-${f.basis}`}
                  disabled={f.basis === 'polarity'} disabledReason={f.basis === 'polarity' ? 'three bins: up, down, biphasic' : undefined}
                  onValid={v => s.set(`fb.${f.basis}.count`, v)} />
              ),
            },
            {
              key: 'range', header: 'range', width: '22%', render: f => {
                const v = s.str(`fb.${f.basis}.range`)
                const nyq = f.basis === 'frequency content' && /([\d.]+)\s*(?:–|-)\s*([\d.]+)\s*Hz/.test(v) && Number(v.match(/(?:–|-)\s*([\d.]+)/)?.[1] ?? 0) > 0.5
                return (
                  <span style={{ display: 'inline-flex', flexDirection: 'column', gap: 2 }}>
                    <TextField value={v} onChange={t => s.set(`fb.${f.basis}.range`, t)} size="sm" width={190} testid={`range-${f.basis}`}
                      disabled={s.str(`fb.${f.basis}.bins`) === 'quantiles'} disabledReason={s.str(`fb.${f.basis}.bins`) === 'quantiles' ? 'quantile bins take their edges from the data' : undefined} />
                    {nyq && <span className="small" style={{ color: 'var(--amber)' }} data-testid="nyquist-warning">above Nyquist for 1 Hz recordings (M2_aug fs1, M3_jul, M4_aug)</span>}
                  </span>
                )
              },
            },
          ]} />
      </SectionCard>

      <SectionCard title="Hand edits" testid="hand-edits-card">
        <Row label="re-apply hand edits when regrouping" testid="reapply-row" caption="a hand edit outlives the grouping it was made on">
          <LockedToggle reason="hand edits survive regrouping (P22)" testid="reapply-hand-edits" />
        </Row>
        <Row label="orphaned hand edits" sub="orphaned = pointing at a family the new grouping lacks"
          dot={s.differs('orphaned')} unsaved={s.dirty('orphaned')} testid="orphaned-row"
          caption="held edits wait in the grouping report">
          <Seg value={s.str('orphaned')} onChange={v => s.set('orphaned', v)} testid="orphaned"
            options={[{ value: 'keep as a hand group', label: 'keep as a hand group' }, { value: 'hold', label: 'hold' }]} />
        </Row>
      </SectionCard>
    </>
  )
}
