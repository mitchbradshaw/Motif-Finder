/* Frame discovery-1b: Add runs · Apply template. Saved templates filtered to the scope's type with their stage glyph
 * strips; detail pane with locked parameters, per-channel cost, compute / disk / null tiles and the sample preview.
 * Cost decides the primary action (§7.5): within the 20 min local limit Add and run; above it Create SLURM script. */
import { useMemo, useState } from 'react'
import {
  Button, Checkbox, Chip, DisabledReason, Dropdown, EmptyState, Icon, InfoTip, Modal, Seg, StatTile, TextField, cx, recordDemoWrite, startSim, useNotWired, useQueryState,
} from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { useToast } from '../shell/Toast'
import { EXTRA_RUN_COLOURS, REBIND_EXEMPLARS, getTemplates, fmtMin, DISCOVERY_LIMIT_MIN, type DiscoveryRun, type DiscoveryTemplate } from '../api/discovery'
import { RunGlyph } from './glyphs'
import { LoadFailed, Loading } from './chrome'
import type { Discovery } from './session'

export function AddTemplateModal({ open, onClose, dx, onSlurm }: { open: boolean; onClose: () => void; dx: Discovery; onSlurm: (keys: string[]) => void }) {
  const tpls = useSourced(getTemplates, [])
  const [focusQ, setFocusQ] = useQueryState('tpl', 'mp_discord_v3')
  const [sel, setSel] = useState<string[]>(['mp_discord_v3', 'spike_shape_v1'])
  const [search, setSearch] = useState('')
  const [fits, setFits] = useState(true)
  const [kind, setKind] = useState('all')
  const [sort, setSort] = useState('last')
  const [exemplar, setExemplar] = useState<Record<string, string>>({})
  const toast = useToast()
  const notWired = useNotWired()
  const s = dx.scope!
  const nCh = s.channels.length
  const inSessionReason = (t: DiscoveryTemplate) => dx.runs.some(r => r.key === t.name || r.template === t.name) ? (t.inSession ?? 'in this session') : null
  const disabledReason = (t: DiscoveryTemplate) => !t.fits ? "doesn't fit Signal → SpanSet — Discovery applies detection templates" : inSessionReason(t)
  const list = useMemo(() => {
    let xs = (tpls.data ?? []).filter(t => (fits ? t.fits : true) && (kind === 'all' || t.kind === kind) && t.name.toLowerCase().includes(search.trim().toLowerCase()))
    xs = [...xs].sort((a, b) => sort === 'name' ? a.name.localeCompare(b.name) : sort === 'precision' ? (b.precision ?? -1) - (a.precision ?? -1) : a.lastUsed - b.lastUsed)
    return xs
  }, [tpls.data, fits, kind, search, sort])
  const chosen = (tpls.data ?? []).filter(t => sel.includes(t.name) && !disabledReason(t))
  const focus = (tpls.data ?? []).find(t => t.name === focusQ) ?? list[0] ?? null
  const perRunMin = (t: DiscoveryTemplate) => t.perChannelMin * nCh * (dx.sectionH / 174)
  const estimate = chosen.reduce((a, t) => a + perRunMin(t), 0)
  const over = estimate > DISCOVERY_LIMIT_MIN
  const needsExemplar = chosen.find(t => t.bind === 'rebind' && !exemplar[t.name])
  const blockReason = chosen.length === 0 ? 'select at least one template' : needsExemplar ? `${needsExemplar.name} needs an exemplar` : null

  const toRuns = (status: DiscoveryRun['status']): DiscoveryRun[] => chosen.map((t, i) => ({
    key: t.name, label: t.name, kind: t.kind, colour: EXTRA_RUN_COLOURS[(dx.runs.length + i) % EXTRA_RUN_COLOURS.length],
    glyph: (t.stages.find(st => ['mp', 'seed', 'model', 'spike', 'drop'].includes(st.glyph))?.glyph ?? 'threshold'),
    detail: t.kind === 'seed' ? `${exemplar[t.name] ?? 'carried exemplar'} · MASS` : `${t.stages.length - 1} stages`, template: t.name, status, perChannelMin: t.perChannelMin, addedThisSession: true,
  }))
  const add = (run: boolean) => {
    const runs = toRuns(run ? 'running' : 'new')
    dx.addRuns(runs)
    if (run) runs.forEach(r => startSim(`discovery.run.${r.key}`, { steps: (tpls.data ?? []).find(t => t.name === r.key)!.stages.slice(1).map(st => `${st.index} ${st.name}`).concat('null 200×'), stepMs: 1000 }))
    recordDemoWrite('discovery', run ? 'add-and-run' : 'add-runs', { templates: runs.map(r => r.key), channels: s.channels, exemplars: exemplar })
    toast.push({ text: `${runs.length} run${runs.length === 1 ? '' : 's'} added${run ? ' · running locally' : ''}` })
    onClose()
  }
  const slurm = () => {
    const runs = toRuns('new')
    dx.addRuns(runs)
    recordDemoWrite('discovery', 'add-runs', { templates: runs.map(r => r.key), channels: s.channels, route: 'cluster' })
    onSlurm(runs.map(r => r.key))
  }

  return (
    <Modal open={open} onClose={onClose} title="Add runs" width={1080} flushBody testid="add-template-modal"
      headerExtra={<Seg size="sm" value="template" onChange={v => { if (v === 'seed') { onClose(); navigate('discovery/seed') } }} options={[{ value: 'template', label: 'Apply template' }, { value: 'seed', label: 'Seed search' }]} testid="add-runs-mode" />}
      footer={
        <div className="dsc-add-foot">
          <span><b>{chosen.length} template{chosen.length === 1 ? '' : 's'} selected</b> <span className="muted small">× {nCh} channel{nCh === 1 ? '' : 's'}</span></span>
          <span className="k-spacer" />
          {chosen.length > 0 && <span className={cx('small mono', over ? 'amber' : 'muted')} data-testid="add-estimate">{fmtMin(estimate)} · {over ? 'cluster' : 'local'}</span>}
          <Button onClick={onClose}>Cancel</Button>
          <Button icon="plus" onClick={() => add(false)} disabled={!!blockReason} disabledReason={blockReason ?? undefined} testid="add-runs">Add {chosen.length || ''} run{chosen.length === 1 ? '' : 's'}</Button>
          {over ? (
            <>
              <DisabledReason reason={blockReason ?? `above the ${DISCOVERY_LIMIT_MIN} min local limit · create a SLURM script`}><Button icon="play" disabled disabledReason={blockReason ?? `above the ${DISCOVERY_LIMIT_MIN} min local limit · create a SLURM script`} testid="add-and-run">Add and run</Button></DisabledReason>
              <Button variant="cluster" icon="file" onClick={slurm} disabled={!!blockReason} disabledReason={blockReason ?? undefined} testid="add-slurm">Create SLURM script</Button>
            </>
          ) : (
            <Button variant="primary" icon="play" onClick={() => add(true)} disabled={!!blockReason} disabledReason={blockReason ?? undefined} testid="add-and-run">Add and run</Button>
          )}
        </div>
      }>
      {tpls.error ? <div style={{ padding: 16 }}><LoadFailed what="templates" error={tpls.error} onRetry={tpls.reload} /></div> : !tpls.data ? <Loading height={520} /> : (
        <div className="dsc-add-body">
          <div className="dsc-add-left">
            <div className="dsc-add-filters">
              <TextField value={search} onChange={setSearch} placeholder="Search templates" icon="search" width={150} testid="template-search" ariaLabel="search templates" />
              <Chip tone={fits ? 'blue' : 'outline'} onClick={() => setFits(!fits)} selected={fits} testid="fits-toggle" title={fits ? 'showing templates that fit the scope — click to show every template' : 'showing every template'}>fits Signal → SpanSet {fits && <Icon name="check" size={11} />}</Chip>
              <Dropdown prefix="kind" value={kind} onChange={setKind} options={[{ value: 'all', label: 'all' }, { value: 'template', label: 'template' }, { value: 'seed', label: 'seed' }]} size="sm" testid="template-kind" />
              <span className="k-spacer" />
              <Dropdown prefix="sort" value={sort} onChange={setSort} options={[{ value: 'last', label: 'last used' }, { value: 'name', label: 'name' }, { value: 'precision', label: 'precision' }]} size="sm" testid="template-sort" />
            </div>
            <div className="dsc-notice small" data-testid="models-notice">
              <Icon name="cpu" size={13} /> Models run inside detection templates — add a Model stage in Analyse
              <span className="k-spacer" />
              <Button variant="link" size="sm" icon="external" onClick={() => { onClose(); navigate('analyse/chain') }} testid="open-analyse">Open Analyse</Button>
            </div>
            <div className="dsc-tpl-list" data-testid="template-list">
              {list.length === 0 && <EmptyState size="sm" icon="search" title="No template matches" caption={search ? `nothing called “${search}”` : 'clear a filter'} />}
              {list.map(t => {
                const reason = disabledReason(t)
                const checked = sel.includes(t.name) && !reason
                return (
                  <div key={t.name} className={cx('dsc-tpl', focus?.name === t.name && 'focused', reason && 'disabled')} data-testid={`template-row-${t.name}`}>
                    <Checkbox checked={checked} onChange={v => { setSel(v ? [...sel, t.name] : sel.filter(x => x !== t.name)); setFocusQ(t.name) }} disabled={!!reason} disabledReason={reason ?? undefined} ariaLabel={`select ${t.name}`} testid={`template-check-${t.name}`} />
                    <button type="button" className="dsc-tpl-body" onClick={() => setFocusQ(t.name)} aria-pressed={focus?.name === t.name}>
                      <b>{t.name}</b>
                      <span className="row" style={{ gap: 6 }}><span className={cx('k-badge', t.kind === 'seed' ? 't-purple' : 't-blue')}>{t.kind}</span><span className="mono muted small">{t.signature}</span>{t.hasModel && <span className="k-badge t-grey" title="a model reaches Discovery only as a stage inside a detection template (P16)">model stage</span>}</span>
                      <span className="muted small">{reason && t.fits ? reason : t.lastScore}</span>
                    </button>
                    <span className="dsc-tpl-glyphs">{t.stages.slice(1).map((st, i) => <span key={i} className="row" style={{ gap: 3 }}>{i > 0 && <span className="muted">›</span>}<RunGlyph kind={st.glyph} width={38} height={24} /></span>)}</span>
                  </div>
                )
              })}
            </div>
          </div>
          <div className="dsc-add-right" data-testid="template-detail">
            {!focus ? <EmptyState size="sm" title="Pick a template" /> : (
              <>
                <div className="row" style={{ gap: 8 }}>
                  <b className="dsc-tpl-title">{focus.name}</b><span className={cx('k-badge', focus.kind === 'seed' ? 't-purple' : 't-blue')}>{focus.kind}</span>
                  <span className="k-spacer" />
                  <Button variant="link" size="sm" icon="external" onClick={() => { notWired(`import template ${focus.name} in Analyse`); onClose(); navigate('analyse/chain') }} testid="detail-open-analyse">Open in Analyse</Button>
                </div>
                <div className="dsc-sub-label">Stages</div>
                <div className="dsc-stage-list">
                  {focus.stages.map((st, i) => (
                    <div key={i} className="dsc-stage-row">
                      <span className="mono muted small dsc-stage-idx">{st.index}</span>
                      <RunGlyph kind={st.glyph} width={36} height={24} />
                      <span className="dsc-stage-name"><b>{st.name}</b><span className="mono muted small">{st.signature}</span></span>
                      {st.locked && <span className="mono muted small row" style={{ gap: 4 }}><Icon name="lock" size={11} />{st.locked}</span>}
                    </div>
                  ))}
                </div>
                <div className="dsc-locked-note small"><Icon name="lock" size={11} /> parameters come from the template <InfoTip title="Locked parameters">A template's parameters come from the template. Open in Analyse to change them and save a new version.</InfoTip></div>
                {focus.bind === 'rebind' && (
                  <div className="dsc-rebind" data-testid="rebind-exemplar">
                    <span className="small"><b>exemplar</b> <span className="muted">required · rebind asks for one when applied</span></span>
                    <Dropdown value={exemplar[focus.name] ?? ''} placeholder="choose an exemplar" onChange={v => setExemplar({ ...exemplar, [focus.name]: v })} options={REBIND_EXEMPLARS} testid="rebind-select" block />
                    {sel.includes(focus.name) && !exemplar[focus.name] && <span className="dsc-err">{focus.name} needs an exemplar</span>}
                  </div>
                )}
                <div className="dsc-sub-label">Channels in scope</div>
                <div className="dsc-scope-channels">
                  {s.channels.map(c => (
                    <div key={c} className="row between small">
                      <Checkbox checked onChange={() => undefined} disabled disabledReason="a template runs across every channel in scope" label={<span className="mono">{c}</span>} />
                      <span className="mono"><span className="muted">{dx.sectionH} h</span> <span className={cx(focus.perChannelMin * dx.sectionH / 174 > DISCOVERY_LIMIT_MIN ? 'amber' : 'muted')}>{fmtMin(focus.perChannelMin * dx.sectionH / 174)}</span></span>
                    </div>
                  ))}
                </div>
                <div className="dsc-tiles">
                  <StatTile label="compute" value={focus.fits ? fmtMin(perRunMin(focus)) : '—'} caption={focus.complexity} tone={perRunMin(focus) > DISCOVERY_LIMIT_MIN ? 'amber' : undefined} size="sm" />
                  <StatTile label="disk" value={focus.fits ? `${focus.diskGB.toFixed(focus.diskGB < 0.1 ? 2 : 1)} GB` : '—'} caption="scores kept" size="sm" />
                  <StatTile label="null" value={`${s.nullN}×`} caption={s.nullMethod} size="sm" />
                </div>
                {focus.fits && (
                  <div className="dsc-preview-card" data-testid="template-preview">
                    <div className="row" style={{ gap: 6 }}><Icon name="flask" size={13} /><b>Sample preview</b><span className="muted small">{focus.preview.hours} h of {focus.preview.channel}</span><span className="k-spacer" /><span className="k-badge t-green">done</span></div>
                    <div className="mono small">{focus.preview.spans} spans in {focus.preview.hours} h · null gives {focus.preview.nullGives} → ≈ {Math.round(focus.preview.spans * dx.sectionH * nCh / focus.preview.hours).toLocaleString('en-US')} over {Math.round(dx.sectionH * nCh).toLocaleString('en-US')} h</div>
                    {perRunMin(focus) > DISCOVERY_LIMIT_MIN ? <div className="mono small amber">above the local ceiling → routes to cluster</div> : <div className="mono small muted">within the {DISCOVERY_LIMIT_MIN} min local limit → runs here</div>}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}
