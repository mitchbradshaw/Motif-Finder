/* Settings › Nulls (frame settings-04 · spec §9.4, P10).
 * Method, count and seed per analysis kind; whether a null runs is not a setting. */
import { useEffect } from 'react'
import { NumberField, SectionCard, Seg, SelectField, Table, Toggle, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getNulls } from '../api/settings'
import { LoadFailed, Loading, LockedChip, LockedToggle, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function NullsPage() {
  const rd = useSourced(getNulls, [])
  return (
    <SettingsShell slug="nulls" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the null settings" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getNulls>>['data']

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('nulls')
  const [, setFixedSeed] = useQueryState('seed', '')
  /* the smallest reportable p is set by the kinds that report one; the full-model shuffle (a handful of
     retrains drawn as dots) and grouping stability never quote a p, so their draws do not bound α */
  const minDraws = Math.min(...data.kinds.filter(k => k.p_value).map(k => Number(s.value(`null.${k.id}.draws`) ?? k.draws)))
  const smallestP = 1 / minDraws
  const alpha = Number(s.value('alpha') ?? 0.01)
  const alphaTooSmall = alpha > 0 && alpha < smallestP
  useEffect(() => {
    s.markInvalid('alpha', alphaTooSmall
      ? `α ${alpha} is below the smallest reportable p (${smallestP.toFixed(3)}) — raise draws to at least ${Math.ceil(1 / alpha).toLocaleString('en-US')}`
      : null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alphaTooSmall, alpha, smallestP])

  return (
    <>
      <SectionCard title="Null per analysis kind" testid="nulls-card"
        actions={<LockedChip reason="whether a null runs is not a setting (P10)" testid="always-on">always on</LockedChip>}
        footer={<span className="s-note">each method is chosen per kind because the thing that must be destroyed differs: timing for detection, labels for training, membership for groupings</span>}>
        <Table rows={data.kinds} rowKey={k => k.id} testid="nulls-table" dense
          columns={[
            { key: 'kind', header: 'analysis kind', width: '20%', render: k => <b>{k.kind}</b> },
            { key: 'used', header: 'used in', width: '14%', render: k => <span className="muted small">{k.used_in}</span> },
            {
              key: 'method', header: 'method', width: '21%', render: k => (
                <span className={s.dirty(`null.${k.id}.method`) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                  <SelectField value={String(s.value(`null.${k.id}.method`) ?? k.methods[0])} onChange={v => s.set(`null.${k.id}.method`, v)}
                    options={k.methods.map(m => ({ value: m, label: m }))} size="sm" width={200} testid={`method-${k.id}`} />
                </span>
              ),
            },
            {
              key: 'draws', header: 'draws', width: '13%', render: k => {
                const full = k.id === 'full-model'
                const max = full ? 50 : 10000
                return (
                  <span className={s.dirty(`null.${k.id}.draws`) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                    <NumberField value={Number(s.value(`null.${k.id}.draws`) ?? k.draws)} min={full ? 1 : 20} max={max} integer width={100} testid={`draws-${k.id}`}
                      onValid={n => { s.set(`null.${k.id}.draws`, n); s.markInvalid(`null.${k.id}.draws`, null) }}
                      onChange={(_r, reason) => s.markInvalid(`null.${k.id}.draws`, reason ? `Draws must be a whole number between ${full ? 1 : 20} and ${max.toLocaleString('en-US')}` : null)} />
                  </span>
                )
              },
            },
            {
              key: 'seed', header: 'seed', width: '14%', render: k => (
                <SelectField value={String(s.value(`null.${k.id}.seed`) ?? k.seed)} size="sm" width={120} testid={`seed-${k.id}`}
                  onChange={v => { s.set(`null.${k.id}.seed`, v); if (v === 'fixed') setFixedSeed(k.id) }}
                  options={data.seedOptions.map(o => ({ value: o, label: o }))} />
              ),
            },
            { key: 'shown', header: 'shown as', width: '18%', render: k => <span className="muted small">{k.shown_as}</span> },
          ]} />
      </SectionCard>

      <SectionCard title="Significance" testid="significance-card">
        <Row label="significance level α" id="f-significance-level" testid="alpha-row"
          info="Results with p below α are marked significant."
          dot={s.differs('alpha')} unsaved={s.dirty('alpha')}
          caption={`with ${minDraws.toLocaleString('en-US')} draws the smallest reportable p is ${smallestP.toFixed(3)}`}>
          <NumberField value={alpha} min={0.0001} max={0.1} step={0.001} width={110} testid="alpha"
            onValid={n => { s.set('alpha', n) }}
            onChange={(_r, reason) => { if (reason) s.markInvalid('alpha', 'α must be between 0 and 0.10') }} />
          {alphaTooSmall && <span className="small" style={{ color: 'var(--red)' }} data-testid="alpha-error">{s.invalid.alpha}</span>}
        </Row>
        <Row label="multiple channels" sub="correction when a result is tested per channel" testid="correction-row"
          dot={s.differs('correction')} unsaved={s.dirty('correction')}
          caption="per-channel p values in Discovery shown corrected; runs are not re-run">
          <Seg value={String(s.value('correction') ?? 'none')} onChange={v => s.set('correction', v)} testid="correction"
            options={['none', 'Holm', 'Benjamini–Hochberg'].map(o => ({ value: o, label: o }))} />
        </Row>
        <Row label="show × null beside counts" testid="xnull-row"
          dot={s.differs('show_x_null')} unsaved={s.dirty('show_x_null')}
          caption="Discovery scoreboard, templates, run reports">
          <Toggle checked={s.bool('show_x_null')} onChange={v => s.set('show_x_null', v)} testid="show-x-null" />
        </Row>
      </SectionCard>

      <SectionCard title="Running nulls" testid="running-nulls-card">
        <Row label="reuse null draws while the recipe is unchanged" testid="reuse-row"
          dot={s.differs('reuse_draws')} unsaved={s.dirty('reuse_draws')}
          caption="a changed parameter invalidates the cached draws">
          <Toggle checked={s.bool('reuse_draws')} onChange={v => s.set('reuse_draws', v)} testid="reuse-draws" />
        </Row>
        <Row label="null draws count toward local limits" testid="count-limits-row"
          caption={<>estimates include them, so a 200× null can route a stage to the cluster · <button type="button" className="k-link" onClick={() => navigate('settings/compute-hpc')}>Compute &amp; HPC</button></>}>
          <LockedToggle reason="estimates include null draws (Compute & HPC)" testid="count-toward-limits" />
        </Row>
      </SectionCard>
    </>
  )
}
