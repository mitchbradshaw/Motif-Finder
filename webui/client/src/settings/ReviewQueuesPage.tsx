/* Settings › Review queues (frame settings-08 · spec §9.8, P20, P21, B16).
 * Defaults for new queues. The blind state is stored with every verdict. */
import { Callout, InfoTip, NumberField, SectionCard, SelectField, Table, TextField, Toggle } from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getReviewQueues } from '../api/settings'
import { LoadFailed, Loading, LockedToggle, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function ReviewQueuesPage() {
  const rd = useSourced(getReviewQueues, [])
  return (
    <SettingsShell slug="review-queues" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the queue defaults" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getReviewQueues>>['data']
const MEASURED = new Set(['training', 'verification'])

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('review-queues')
  const unblinded = data.queues.filter(q => MEASURED.has(q.id) && !s.bool(`q.${q.id}.blind`))
  const suggestD = s.num('suggest_d')

  return (
    <>
      <SectionCard title="Queue defaults by source" testid="queues-card"
        footer={<span className="s-note">blind hides score, family affinity and model calls until the verdict · artifact likelihood is never hidden</span>}>
        <Table rows={data.queues} rowKey={q => q.id} testid="queues-table" dense
          columns={[
            { key: 'source', header: 'source', width: '18%', render: q => <b>{q.icon} {q.source}</b> },
            {
              key: 'blind', header: 'blind', width: '16%', render: q => (
                <span className={s.dirty(`q.${q.id}.blind`) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                  <Toggle checked={s.bool(`q.${q.id}.blind`)} onChange={v => s.set(`q.${q.id}.blind`, v)} testid={`blind-${q.id}`}
                    tone="blue" label={s.bool(`q.${q.id}.blind`) ? 'blind' : 'visible'} />
                </span>
              ),
            },
            {
              key: 'keys', header: 'verdict keys', width: '20%', render: q => (
                <SelectField value={s.str(`q.${q.id}.keys`)} onChange={v => s.set(`q.${q.id}.keys`, v)} size="sm" width={185} testid={`keys-${q.id}`}
                  options={data.keySets.map(k => ({ value: k, label: k }))} />
              ),
            },
            {
              key: 'cap', header: 'cap', width: '12%', render: q => (
                <span className={s.dirty(`q.${q.id}.cap`) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                  <TextField value={s.str(`q.${q.id}.cap`)} size="sm" width={90} testid={`cap-${q.id}`}
                    invalid={!!s.invalid[`q.${q.id}.cap`]}
                    onChange={v => {
                      s.set(`q.${q.id}.cap`, v)
                      const n = Number(v.replace(/,/g, ''))
                      const ok = v.trim() === '' || v.trim() === '—' || (Number.isInteger(n) && n >= 1 && n <= 100000)
                      s.markInvalid(`q.${q.id}.cap`, ok ? null : 'Cap must be a whole number up to 100,000, or —')
                    }} />
                </span>
              ),
            },
            {
              key: 'order', header: 'order', width: '18%', render: q => (
                <SelectField value={s.str(`q.${q.id}.order`)} onChange={v => s.set(`q.${q.id}.order`, v)} size="sm" width={165} testid={`order-${q.id}`}
                  options={data.orders.map(o => ({ value: o, label: o }))} />
              ),
            },
            {
              key: 'writes', header: 'writes', width: '16%', render: q => (
                <span className="muted small">{q.writes}
                  <InfoTip title="write target">Detections are machine-only; annotations and adjudications are human-only (P20).</InfoTip>
                </span>
              ),
            },
          ]} />
        {unblinded.length > 0 && (
          <Callout tone="amber" testid="unblind-warning">
            {unblinded.map(q => q.source).join(' and ')} would show the machine's call first — the human verdict is the measurement here, and showing the
            score first anchors it (P20). New queues store their verdicts as not blind.
          </Callout>
        )}
      </SectionCard>

      <SectionCard title="Clusters" subtitle="batch verdicts in Review" testid="clusters-card">
        <Row label="cohesion limit" id="f-cohesion-limit" info="A member farther than this from the medoid is left out of the batch unless it is picked."
          dot={s.differs('cohesion')} unsaved={s.dirty('cohesion')} testid="cohesion-row"
          caption="a member farther than this from the medoid is excluded from the batch by default">
          <NumberField value={s.num('cohesion')} min={0.05} max={1} step={0.05} width={100} testid="cohesion"
            onValid={v => { s.set('cohesion', v); s.markInvalid('cohesion', null) }}
            onChange={(_r, reason) => s.markInvalid('cohesion', reason ? 'Enter 0.05–1.00' : null)} />
        </Row>
        <Row label="a sequence is" sub="shared with Library sequences" testid="sequence-row" id="f-sequence-gap"
          dot={s.differs('seq_gap') || s.differs('seq_events')} unsaved={s.dirty('seq_gap') || s.dirty('seq_events')}
          caption={<>also changes <button type="button" className="k-link" onClick={() => navigate('settings/library-groupings?focus=sequence-gap')}>Library sequences</button></>}>
          <span className="mono small">same run and channel, gap ≤</span>
          <NumberField value={s.num('seq_gap')} min={0.5} max={120} step={0.5} unit="min" width={110} onValid={v => s.set('seq_gap', v)} testid="seq-gap" />
          <span className="mono small">at least</span>
          <NumberField value={s.num('seq_events')} min={2} max={100} integer unit="events" width={120} onValid={v => s.set('seq_events', v)} testid="seq-events" />
        </Row>
        <Row label="largest batch" dot={s.differs('largest_batch')} unsaved={s.dirty('largest_batch')} testid="batch-row" caption="a batch beyond this is split">
          <NumberField value={s.num('largest_batch')} min={2} max={500} integer unit="members" width={130} onValid={v => s.set('largest_batch', v)} testid="largest-batch" />
        </Row>
        <Row label="undo reverses the whole batch" testid="undo-row" caption="a mis-keyed batch must be reversible in one step">
          <LockedToggle reason="undo reverses a whole batch" testid="undo-batch" />
        </Row>
      </SectionCard>

      <SectionCard title="Promotion" subtitle="the seed verdict" testid="promotion-card">
        <Row label="S promotes to the Library" testid="promote-row" caption="a separate promote step would duplicate the seed key">
          <LockedToggle reason="pressing S is the promotion (P21)" testid="s-promotes" />
        </Row>
        <Row label="suggest the nearest family when d ≤" dot={s.differs('suggest_d')} unsaved={s.dirty('suggest_d')} testid="suggest-row"
          caption={suggestD > 0.5 ? 'suggested families would be ones the Library omits' : 'otherwise the panel suggests no family yet'}>
          <NumberField value={suggestD} min={0.05} max={1} step={0.05} width={100} testid="suggest-d"
            onValid={v => { s.set('suggest_d', v); s.markInvalid('suggest_d', null) }}
            onChange={(_r, reason) => s.markInvalid('suggest_d', reason ? 'Enter 0.05–1.00' : null)} />
          {suggestD > 0.5 && <span className="small" style={{ color: 'var(--amber)' }} data-testid="suggest-warning">past the Library's omit distance (0.50)</span>}
        </Row>
      </SectionCard>
    </>
  )
}
