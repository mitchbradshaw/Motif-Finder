/* Settings › Analysis defaults (frame settings-05 · spec §9.5, D4).
 * The matching rule, the recommended-value rules each block evaluates on its span, artifact
 * likelihood factors and the step cache. These travel into every recipe hash. */
import { useRef, useState } from 'react'
import {
  Button, Modal, NumberField, Popover, ProgressBar, SectionCard, SelectField, Slider, Table, TextField,
  useNotWired, useQueryState,
} from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getAnalysisDefaults, ruleKey, type RecommendRule } from '../api/settings'
import { LoadFailed, Loading, LockedField, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function AnalysisDefaultsPage() {
  const rd = useSourced(getAnalysisDefaults, [])
  return (
    <SettingsShell slug="analysis-defaults" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the analysis defaults" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getAnalysisDefaults>>['data']

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('analysis-defaults')
  const notWired = useNotWired()
  const [ctx, setCtx] = useQueryState('ctx', data.contexts[0])
  const [modal, setModal] = useQueryState('modal', '')
  const [clearing, setClearing] = useState<'idle' | 'running' | 'done'>('idle')
  const [cacheGb, setCacheGb] = useState(data.cacheGb)

  const nyquist = ctx.startsWith('M2_aug fs2') ? 1 : 0.5
  const ruleError = (r: RecommendRule, v: string): string | null => {
    if (r.parameter === 'band') {
      const m = v.match(/^\s*([\d.]+)\s*[–-]\s*([\d.]+)\s*Hz\s*$/i)
      if (!m) return null
      const lo = Number(m[1]), hi = Number(m[2])
      if (!(lo > 0 && lo < hi)) return 'The lower edge must be above 0 and below the upper edge'
      if (hi > nyquist) return `Upper edge ${hi} Hz is above Nyquist (${nyquist} Hz) on ${ctx.split(' ')[0]}`
    }
    if (r.parameter === 'alphabet') {
      const m = v.match(/^(\d+)\s+symbols/)
      if (m && (Number(m[1]) < 3 || Number(m[1]) > 20)) return 'Between 3 and 20 symbols'
    }
    return null
  }

  return (
    <>
      <SectionCard title="Matching rule" subtitle="what counts as the same event · §4.6" testid="matching-card">
        <Row label="reciprocal overlap (IoU)" info="Two spans are the same event when their overlap divided by their union is at least this."
          dot={s.differs('iou')} unsaved={s.dirty('iou')} testid="iou-row" id="f-reciprocal-overlap-iou-"
          caption="every precision and recall figure is a function of this">
          <Slider value={s.num('iou')} onChange={v => s.set('iou', v)} min={0.05} max={1} step={0.05} width={170} format={v => v.toFixed(2)} testid="iou" />
        </Row>
        <Row label="onset tolerance" dot={s.differs('onset')} unsaved={s.dirty('onset')} testid="onset-row"
          caption="a detection whose onset is inside this counts as matched">
          <Slider value={s.num('onset')} onChange={v => s.set('onset', v)} min={0} max={1} step={0.05} width={170} format={v => `${v.toFixed(2)} × duration`} testid="onset" />
        </Row>
        <Row label="seed-search exclusion zone" dot={s.differs('exclusion')} unsaved={s.dirty('exclusion')} testid="exclusion-row"
          caption="the trivial-match guard">
          <SelectField value={s.str('exclusion')} onChange={v => s.set('exclusion', v)} width={110} testid="exclusion"
            options={['m / 4', 'm / 2', 'm'].map(o => ({ value: o, label: o }))} />
        </Row>
      </SectionCard>

      <SectionCard title="Recommended values" subtitle="Settings holds the rule · each block evaluates it on its span" testid="rules-card"
        footer={<Button variant="link" size="sm" icon="plus" testid="add-rule" onClick={() => notWired('POST /api/settings/analysis-defaults/rules')}>Add a rule for a block parameter</Button>}>
        <Table rows={data.rules} rowKey={r => `${r.block}.${r.parameter}`} testid="rules-table" dense
          columns={[
            { key: 'block', header: 'block', width: '16%', render: r => <b>{r.block}</b> },
            { key: 'parameter', header: 'parameter', width: '11%', render: r => <span className="mono">{r.parameter}</span> },
            {
              key: 'rule', header: 'rule', width: '31%', render: r => {
                const id = ruleKey(r.block, r.parameter)
                const v = s.str(id) || r.rule
                const err = ruleError(r, v)
                return r.locked
                  ? <LockedField reason={r.parameter === 'gap' ? 'gap ≥ window' : "every detector reads the recording's noise floor (Datasets)"} testid={`rule-locked-${r.parameter}`}>{r.rule}</LockedField>
                  : (
                    <span className={s.dirty(id) ? 'unsaved' : undefined} style={{ display: 'inline-flex', flexDirection: 'column', gap: 2 }}>
                      <TextField value={v} onChange={t => { s.set(id, t); s.markInvalid(id, ruleError(r, t)) }} width={280} invalid={!!err} testid={`rule-${r.parameter}`} />
                      {err && <span className="small" style={{ color: 'var(--red)' }} data-testid={`rule-error-${r.parameter}`}>{err}</span>}
                    </span>
                  )
              },
            },
            { key: 'on', header: 'evaluated on', width: '14%', render: r => <span className="muted small">{r.evaluated_on}</span> },
            {
              key: 'example', header: (
                <SelectField value={ctx} onChange={setCtx} size="sm" width={175} testid="rule-context" ariaLabel="evaluation context"
                  options={[...data.contexts.map(c => ({ value: c, label: `on ${c}` })), { value: 'M4_aug CH1_A1', label: 'on M4_aug CH1_A1', disabled: true, reason: 'held out · locked' }]} />
              ), width: '16%', render: r => {
                const ex = data.examples[ctx]?.[`${r.block}.${r.parameter}`]
                return ex ? <span><span className="s-rec-bar" /><b className="mono">{ex}</b></span> : <span className="muted">—</span>
              },
            },
            { key: 'history', header: '', width: '12%', render: r => <History rule={r} onRestore={v => s.set(ruleKey(r.block, r.parameter), v)} /> },
          ]} />
      </SectionCard>

      <SectionCard title="Artifact likelihood" subtitle="shown in Review, never blinded" testid="artifact-card">
        <Row label="cross-channel coherence flag" dot={s.differs('coherence')} unsaved={s.dirty('coherence')} testid="coherence-row"
          caption="coherence in the span across channels sharing a clock">
          <span className="mono small">≥</span>
          <NumberField value={s.num('coherence')} min={0} max={1} step={0.05} width={100} onValid={v => s.set('coherence', v)} testid="coherence" />
        </Row>
        <Row label="clipping" dot={s.differs('clipping')} unsaved={s.dirty('clipping')} testid="clipping-row" caption="samples at the rail">
          <span className="mono small">≥</span>
          <NumberField value={s.num('clipping')} min={50} max={100} integer unit="% range" width={130} onValid={v => s.set('clipping', v)} testid="clipping" />
        </Row>
        <Row label="step change" dot={s.differs('step_x')} unsaved={s.dirty('step_x')} testid="step-row" caption="a jump this big is read as an electrode event">
          <span className="mono small">&gt;</span>
          <NumberField value={s.num('step_x')} min={1} max={50} width={90} onValid={v => s.set('step_x', v)} testid="step-x" />
          <span className="mono small">× floor within</span>
          <NumberField value={s.num('step_within')} min={0.1} max={60} step={0.1} unit="s" width={100} onValid={v => s.set('step_within', v)} testid="step-within" />
        </Row>
        <Row label="bands" sub="likelihood from the weighted factors" dot={s.differs('band_low')} unsaved={s.dirty('band_low') || s.dirty('band_medium')} testid="bands-row"
          caption="low green · medium amber · high red">
          <span className="s-swatch" style={{ background: 'var(--green)' }} /><span className="mono small">low &lt;</span>
          <NumberField value={s.num('band_low')} min={0.01} max={0.99} step={0.05} width={90} testid="band-low"
            onValid={v => { s.set('band_low', v); s.markInvalid('band_low', v >= s.num('band_medium') ? 'low must be below medium' : null) }} />
          <span className="s-swatch" style={{ background: 'var(--amber)' }} /><span className="mono small">medium &lt;</span>
          <NumberField value={s.num('band_medium')} min={0.02} max={1} step={0.05} width={90} testid="band-medium"
            onValid={v => { s.set('band_medium', v); s.markInvalid('band_low', s.num('band_low') >= v ? 'low must be below medium' : null) }} />
          <span className="s-swatch" style={{ background: 'var(--red)' }} /><span className="mono small">high</span>
        </Row>
      </SectionCard>

      <SectionCard title="Step cache" testid="cache-card">
        <Row label="write stage artifacts slower than" dot={s.differs('cache_min_s')} unsaved={s.dirty('cache_min_s')} testid="cache-min-row"
          caption="faster stages re-run instead of being cached">
          <Slider value={s.num('cache_min_s')} onChange={v => s.set('cache_min_s', v)} min={0} max={30} step={0.5} width={170} format={v => `${v.toFixed(1)} s`} testid="cache-min" />
        </Row>
        <Row label="keep stale artifacts for" id="f-keep-stale-artifacts-for" dot={s.differs('cache_keep_days')} unsaved={s.dirty('cache_keep_days')} testid="cache-keep-row"
          caption="a stale artifact is one whose recipe changed">
          <NumberField value={s.num('cache_keep_days')} min={1} max={365} integer unit="days" width={120} onValid={v => s.set('cache_keep_days', v)} testid="cache-keep" />
        </Row>
        <Row label="location" dot={s.differs('cache_location')} unsaved={s.dirty('cache_location')} testid="cache-location-row"
          caption={<>{cacheGb.toFixed(1)} GB in use · <button type="button" className="k-link" onClick={() => navigate('settings/storage-backups')}>Storage</button></>}>
          <TextField value={s.str('cache_location')} onChange={v => s.set('cache_location', v)} width={220} testid="cache-location" />
          <Button icon="trash" testid="clear-cache" onClick={() => setModal('clear-cache')}>Clear cache</Button>
        </Row>
      </SectionCard>

      <Modal open={modal === 'clear-cache'} onClose={() => { setModal(''); setClearing('idle') }} title="Clear the step cache?" size="sm" testid="clear-cache-modal"
        footer={<>
          <Button onClick={() => { setModal(''); setClearing('idle') }}>Cancel</Button>
          <Button variant="danger" testid="confirm-clear" loading={clearing === 'running'} disabled={clearing !== 'idle'}
            disabledReason={clearing !== 'idle' ? 'clearing…' : undefined}
            onClick={() => {
              setClearing('running')
              window.setTimeout(() => { setClearing('done'); setCacheGb(0); notWired('DELETE /api/cache/steps'); setModal('') }, 1500)
            }}>Clear cache</Button>
        </>}>
        <p className="small" style={{ marginTop: 0 }}>{cacheGb.toFixed(1)} GB · cached stages re-run the next time their chains run. Runs, templates and exports are kept.</p>
        {clearing === 'running' && <ProgressBar indeterminate label="clearing…" testid="clear-progress" />}
      </Modal>
    </>
  )
}

function History({ rule, onRestore }: { rule: RecommendRule; onRestore: (v: string) => void }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [history, setHistory] = useQueryState('history', '')
  const id = rule.parameter
  if (!rule.history.length) return <span className="muted small">—</span>
  return (
    <>
      <Button ref={ref} variant="link" size="sm" testid={`history-${id}`} onClick={() => setHistory(history === id ? '' : id)}>history</Button>
      <Popover open={history === id} onClose={() => setHistory('')} anchorRef={ref} title={`${rule.block} · ${rule.parameter}`} width={340} testid="history-popover">
        {rule.history.map((h, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderTop: i ? '1px solid var(--border)' : undefined }}>
            <span className="mono small">{h.rule}</span><span className="muted small">{h.when}</span>
            <span className="k-spacer" />
            <Button variant="link" size="sm" onClick={() => { onRestore(h.rule); setHistory('') }} testid={`restore-${i}`}>restore</Button>
          </div>
        ))}
      </Popover>
    </>
  )
}
