/* Frame discovery-1b: Add runs · Apply template. Saved templates filtered to the scope's type with their stage glyph
 * strips; detail pane with locked parameters, per-channel cost, compute / disk / null tiles and the sample preview.
 * Cost decides the primary action (§7.5): within the 20 min local limit Add and run; above it Create SLURM script. */
import { useMemo, useState } from 'react'
import {
  Button, Checkbox, Chip, DisabledReason, Dropdown, EmptyState, Icon, InfoTip, Modal, Seg, StatTile, TextField, cx, useNotWired, useQueryState,
} from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { useToast } from '../shell/Toast'
import { REBIND_EXEMPLARS, getBands, getTemplates, previewRun, fmtMin, DISCOVERY_LIMIT_MIN, type DiscoveryTemplate, type MeasuredPreview } from '../api/discovery'
import { applyDiscoveryTemplates, applyDiscoveryTemplatesWithBands, type DiscBand } from '../api'
import { RunGlyph } from './glyphs'
import { LoadFailed, Loading } from './chrome'
import type { Discovery } from './session'

export function AddTemplateModal({ open, onClose, dx, onSlurm }: { open: boolean; onClose: () => void; dx: Discovery; onSlurm: (keys: string[]) => void }) {
  const tpls = useSourced(getTemplates, [])
  /* Both of these used to open the modal holding `mp_discord_v3` and
   * `spike_shape_v1` -- fixture-era names that exist in no live registry (the
   * canonical nine are in `webui/server/templates.py`). The footer read
   * "0 templates selected" with both actions disabled and nothing on screen to
   * un-check, because the phantoms matched no row (fixup-a item 5). Nothing is
   * selected until the researcher selects it; `focus` falls back to the first
   * row of the list. */
  const [focusQ, setFocusQ] = useQueryState('tpl', '')
  const [sel, setSel] = useState<string[]>([])
  const [search, setSearch] = useState('')
  const [fits, setFits] = useState(true)
  const [kind, setKind] = useState('all')
  const [sort, setSort] = useState('last')
  const [exemplar, setExemplar] = useState<Record<string, string>>({})
  const toast = useToast()
  const notWired = useNotWired()
  const s = dx.scope!
  const nCh = s.channels.length
  /* fixup-z: the band scope. `none` is today's behaviour; with bands, each band becomes ONE run across the
   * channels in scope -- the template's chain with that band's bandpass prepended, built by the core's own band
   * materialisation, paired with its own null bandpassed the same way. The list is Settings › Analysis
   * defaults' (Q43). A band reaching this recording's Nyquist cannot be filtered and is offered disabled. */
  const bandsRead = useSourced(getBands, [])
  const [bandMode, setBandMode] = useQueryState('bands', 'none')
  const [bandSel, setBandSel] = useState<string[]>([])
  const bandList: DiscBand[] = bandsRead.data?.bands ?? []
  const nyq = bandsRead.data?.nyquistHz ?? null
  const bandReason = (b: DiscBand) => nyq != null && b.high_hz >= nyq ? `reaches ${b.high_hz} Hz, at or above this recording's Nyquist (${nyq} Hz) — a bandpass edge must lie below it` : null
  const chosenBands = bandMode === 'bands' ? bandList.filter(b => bandSel.includes(b.label) && !bandReason(b)) : []
  const nBands = chosenBands.length
  const bandMult = Math.max(1, nBands)
  const setMode = (v: string) => {
    setBandMode(v)
    if (v === 'bands' && bandSel.length === 0) setBandSel(bandList.filter(b => !bandReason(b)).map(b => b.label))
  }
  /* Already in this session is a NOTE, not a refusal. The same template against
   * a different scope is a different run and the server mints `<name>_2` for it
   * (`discovery.py::_next_key`) -- which is also why the client's own test was
   * wrong twice over: it matched `r.key === t.name`, and `_next_key` gives a
   * template's FIRST run exactly the bare template name, so applying a template
   * once made it un-selectable for the rest of the session (fixup-a item 5).
   * The server already computes this from `template_name`; use its answer. */
  const inSessionNote = (t: DiscoveryTemplate) => t.inSession ?? null
  const disabledReason = (t: DiscoveryTemplate) => !t.fits ? "doesn't fit Signal → SpanSet — Discovery applies detection templates" : null
  const list = useMemo(() => {
    let xs = (tpls.data ?? []).filter(t => (fits ? t.fits : true) && (kind === 'all' || t.kind === kind) && t.name.toLowerCase().includes(search.trim().toLowerCase()))
    xs = [...xs].sort((a, b) => sort === 'name' ? a.name.localeCompare(b.name) : sort === 'precision' ? (b.precision ?? -1) - (a.precision ?? -1) : a.lastUsed - b.lastUsed)
    return xs
  }, [tpls.data, fits, kind, search, sort])
  const chosen = (tpls.data ?? []).filter(t => sel.includes(t.name) && !disabledReason(t))
  const focus = (tpls.data ?? []).find(t => t.name === focusQ) ?? list[0] ?? null
  // §7.1: the only measured cost is *Preview on a sample*. A template carries no number until one has run
  // here, so the cost of a template that has not been previewed is not a small number — it is nothing.
  const [busy, setBusy] = useState(false)
  /* Keyed on the scope as well as the template: a measurement taken over
   * 320 h of six channels is not a measurement of 4 h of two, and the card was
   * still badging it "measured" after the scope shrank — out by eighty. */
  // and on the band: a preview with a band scope is the FIRST chosen band's chain, bandpass included
  const scopeKey = `${s.channels.join(',')}|${s.section.join('-')}|${chosenBands[0]?.label ?? ''}`
  const [previews, setPreviews] = useState<Record<string, MeasuredPreview & { scope: string }>>({})
  const previewOf = (name: string) => { const p = previews[name]; return p && p.scope === scopeKey ? p : undefined }
  const [previewing, setPreviewing] = useState<string | null>(null)
  const [previewErr, setPreviewErr] = useState<string | null>(null)
  // cost is N bands × the sweep (fixup-z): one band's measured sweep, once per band
  const costMin = (t: DiscoveryTemplate): number | null => { const p = previewOf(t.name); return p ? (p.estimate_s / 60) * bandMult : null }
  const noCost = (t: DiscoveryTemplate) => t.previewNote ?? 'not previewed — run Preview on a sample to get a measured number'
  const focusPreview = focus ? previewOf(focus.name) : undefined
  const focusCost = focusPreview ? (focusPreview.estimate_s / 60) * bandMult : null
  const priced = chosen.filter(t => costMin(t) != null)
  const estimate = priced.reduce((a, t) => a + (costMin(t) ?? 0), 0)
  const unpriced = chosen.length - priced.length
  // a measured cost above the ceiling routes to cluster; with nothing measured the footer says so and the
  // bridge's apply route picks the route itself rather than the page guessing one
  const over = priced.length > 0 && estimate > DISCOVERY_LIMIT_MIN
  const preview = async (t: DiscoveryTemplate) => {
    setPreviewing(t.name)
    setPreviewErr(null)
    try {
      const r = await previewRun({ template: t.name, channels: s.channels, t0: s.section[0], t1: s.section[1], sampleHours: 4, band: chosenBands[0] })
      setPreviews(prev => ({ ...prev, [t.name]: { ...r.data, scope: scopeKey } }))
    } catch (e) {
      setPreviewErr(e instanceof Error ? e.message : String(e))
    } finally {
      setPreviewing(null)
    }
  }
  const needsExemplar = chosen.find(t => t.bind === 'rebind' && !exemplar[t.name])
  const blockReason = chosen.length === 0 ? 'select at least one template' : needsExemplar ? `${needsExemplar.name} needs an exemplar`
    : bandMode === 'bands' && nBands === 0 ? 'choose at least one band, or set the band scope to none' : null
  const apply = (run: boolean) => nBands
    ? applyDiscoveryTemplatesWithBands(chosen.map(t => t.name), s.channels, s.section[0], s.section[1], run, chosenBands)
    : applyDiscoveryTemplates(chosen.map(t => t.name), s.channels, s.section[0], s.section[1], run)

  /* §7.5's *Add runs* / *Add and run*. This is a real POST: it used to add a
   * row to React state and drive a timer, which meant the row's "running", its
   * progress and its "done 03:24" were all invented, and the keys it invented
   * were then sent back to /fires and /scoreboard, which rightly answered 404.
   * The server decides the route, so `run` is a request rather than a promise:
   * over the ceiling it adds the run and leaves it for *Create SLURM script*. */
  const add = async (run: boolean) => {
    setBusy(true)
    try {
      const results = await apply(run)
      setSel([])            // or reopening the modal shows the last add's templates, silently un-checked
      onClose()
      await dx.reload()
      const started = results.filter(r => r.started).length
      const held = results.filter(r => !r.started)
      toast.push({
        text: `${results.length} run${results.length === 1 ? '' : 's'} added`
          + (nBands ? ` · ${nBands} band${nBands === 1 ? '' : 's'} × ${chosen.length} template${chosen.length === 1 ? '' : 's'}` : '')
          + (started ? ` · ${started} running locally` : '')
          + (held.length ? ` · ${held.length} not started: ${held[0].note ?? 'over the local ceiling'}` : ''),
      })
    } catch (e) {
      toast.push({ text: `could not add the run: ${e instanceof Error ? e.message : String(e)}` })
    } finally {
      setBusy(false)
    }
  }
  // added but not started: the SLURM modal writes the script for them
  const slurm = async () => {
    setBusy(true)
    try {
      const results = await apply(false)
      setSel([])
      await dx.reload()
      onSlurm(results.map(r => r.run_key))
    } catch (e) {
      toast.push({ text: `could not add the run: ${e instanceof Error ? e.message : String(e)}` })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add runs" width={1080} flushBody testid="add-template-modal"
      headerExtra={<Seg size="sm" value="template" onChange={v => { if (v === 'seed') { onClose(); navigate('discovery/seed') } }} options={[{ value: 'template', label: 'Apply template' }, { value: 'seed', label: 'Seed search' }]} testid="add-runs-mode" />}
      footer={
        <div className="dsc-add-foot">
          <span><b>{chosen.length} template{chosen.length === 1 ? '' : 's'} selected</b> <span className="muted small" data-testid="add-multiplier">{nBands ? `× ${nBands} band${nBands === 1 ? '' : 's'} ` : ''}× {nCh} channel{nCh === 1 ? '' : 's'}</span></span>
          <span className="k-spacer" />
          {chosen.length > 0 && <span className={cx('small mono', over ? 'amber' : 'muted')} data-testid="add-estimate">
            {priced.length === 0 ? 'cost not measured — Preview on a sample'
              : `${fmtMin(estimate)}${nBands ? ` (${nBands} bands × the sweep)` : ''} · ${over ? 'cluster' : 'local'}${unpriced > 0 ? ` · ${unpriced} not previewed` : ''}`}
          </span>}
          <Button onClick={onClose}>Cancel</Button>
          <Button icon="plus" onClick={() => add(false)} disabled={!!blockReason || busy} disabledReason={blockReason ?? (busy ? 'adding the run…' : undefined)} testid="add-runs">Add {chosen.length || ''} run{chosen.length === 1 ? '' : 's'}</Button>
          {over ? (
            <>
              <DisabledReason reason={blockReason ?? `above the ${DISCOVERY_LIMIT_MIN} min local limit · create a SLURM script`}><Button icon="play" disabled disabledReason={blockReason ?? `above the ${DISCOVERY_LIMIT_MIN} min local limit · create a SLURM script`} testid="add-and-run">Add and run</Button></DisabledReason>
              <Button variant="cluster" icon="file" onClick={slurm} disabled={!!blockReason || busy} disabledReason={blockReason ?? (busy ? 'adding the run…' : undefined)} testid="add-slurm">Create SLURM script</Button>
            </>
          ) : (
            <Button variant="primary" icon="play" onClick={() => add(true)} disabled={!!blockReason || busy} disabledReason={blockReason ?? (busy ? 'starting the run…' : undefined)} testid="add-and-run">Add and run</Button>
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
                      <span className="muted small">{t.fits && inSessionNote(t) ? `${inSessionNote(t)} · ${t.lastScore}` : t.lastScore}</span>
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
                      <span className="mono"><span className="muted">{dx.sectionH} h</span> {focusPreview
                        ? <span className={cx(focusPreview.per_channel_s / 60 > DISCOVERY_LIMIT_MIN ? 'amber' : 'muted')}>{fmtMin(focusPreview.per_channel_s / 60)}</span>
                        : <span className="muted">not measured</span>}</span>
                    </div>
                  ))}
                </div>
                <div className="dsc-sub-label row" style={{ gap: 6 }} data-testid="band-scope-head">
                  Bands
                  <InfoTip title="Band scope">A band is a scope, like the channel list. With bands, each band becomes one run across every channel in scope: this template's chain with a bandpass prepended — exactly the chain you would build by inserting the block in Analyse, saving and applying it. Each band run is paired with its own null, bandpassed the same way. Compare takes the band runs of one application as one side, their union.</InfoTip>
                  <span className="k-spacer" />
                  <Seg size="sm" value={bandMode} onChange={setMode} testid="band-scope-mode"
                    options={[{ value: 'none', label: 'none' }, { value: 'bands', label: nBands ? `${nBands} band${nBands === 1 ? '' : 's'}` : 'bands' }]} />
                </div>
                {bandMode === 'bands' && (
                  <div className="dsc-scope-channels" data-testid="band-scope">
                    {bandsRead.error ? <LoadFailed what="the band list" error={bandsRead.error} onRetry={bandsRead.reload} />
                      : !bandsRead.data ? <Loading height={60} label="reading the band list" />
                        : bandList.map(b => {
                          const why = bandReason(b)
                          return (
                            <div key={b.label} className="row between small">
                              <Checkbox checked={bandSel.includes(b.label) && !why} disabled={!!why} disabledReason={why ?? undefined}
                                onChange={v => setBandSel(v ? [...bandSel, b.label] : bandSel.filter(x => x !== b.label))}
                                label={<span className="mono">{b.label}</span>} testid={`band-check-${b.label.replace(/[^A-Za-z0-9]+/g, '_')}`} />
                              <span className="mono muted">{b.kind} {b.low_hz}–{b.high_hz} Hz</span>
                            </div>
                          )
                        })}
                    <div className="muted small" data-testid="band-scope-note">
                      {nBands ? `${nBands} run${nBands === 1 ? '' : 's'} per template, each across ${nCh} channel${nCh === 1 ? '' : 's'} · cost is ${nBands} × the sweep` : 'no band chosen'}
                      {bandsRead.data && ` · ${bandsRead.data.source === 'settings' ? 'your list' : 'the seeded list'} from Settings › Analysis defaults`}
                      <Button variant="link" size="sm" icon="external" onClick={() => { onClose(); navigate('settings/analysis-defaults') }} testid="edit-bands">edit</Button>
                    </div>
                  </div>
                )}
                <div className="dsc-tiles">
                  <StatTile label="compute" value={!focus.fits ? '—' : focusCost != null ? fmtMin(focusCost) : 'not measured'}
                    caption={!focus.fits ? (focus.fitsReason ?? 'does not fit the scope') : focusCost != null ? focus.complexity : noCost(focus)}
                    tone={focusCost != null && focusCost > DISCOVERY_LIMIT_MIN ? 'amber' : undefined} size="sm" />
                  <StatTile label="disk" value={!focus.fits ? '—' : focus.diskGB != null ? `${focus.diskGB.toFixed(focus.diskGB < 0.1 ? 2 : 1)} GB` : 'not measured'}
                    caption={focus.diskGB != null ? 'scores kept' : noCost(focus)} size="sm" />
                  <StatTile label="null" value={s.nullMethod ? `${s.nullN}×` : 'off'} caption={s.nullMethod ?? s.nullReason ?? 'Settings › Nulls names no method this scope can run'} size="sm" />
                </div>
                {focus.fits && (
                  <div className="dsc-preview-card" data-testid="template-preview">
                    <div className="row" style={{ gap: 6 }}>
                      <Icon name="flask" size={13} /><b>Sample preview</b>
                      <span className="muted small">{focusPreview ? `${focusPreview.sample_hours.toFixed(1)} h of ${focusPreview.channel}` : '4 h of one channel'}</span>
                      <span className="k-spacer" />
                      <span className={cx('k-badge', focusPreview ? 't-green' : 't-grey')}>{focusPreview ? 'measured' : 'not previewed'}</span>
                      <Button size="sm" icon="flask" onClick={() => preview(focus)} disabled={previewing !== null} disabledReason={previewing ? `previewing ${previewing}` : undefined} testid="run-preview">
                        {focusPreview ? 'Preview again' : 'Preview on a 4 h sample'}
                      </Button>
                    </div>
                    {previewing === focus.name ? <div className="mono small muted" data-testid="preview-running">running the chain on the sample and timing it…</div>
                      : focusPreview ? (
                        <>
                          <div className="mono small">{focusPreview.spans_in_sample} spans in {focusPreview.sample_hours.toFixed(1)} h of {focusPreview.channel} · measured {fmtMin(focusPreview.measured_s / 60)} → ≈ {focusPreview.extrapolated_spans.toLocaleString('en-US')} spans over {nCh} channel{nCh === 1 ? '' : 's'}</div>
                          {focusPreview.route === 'cluster'
                            ? <div className="mono small amber">above the local ceiling → routes to cluster</div>
                            : <div className="mono small muted">within the {DISCOVERY_LIMIT_MIN} min local limit → runs here</div>}
                        </>
                      ) : <div className="mono small muted" data-testid="preview-note">{noCost(focus)}</div>}
                    {previewErr && <div className="dsc-err" data-testid="preview-error">{previewErr}</div>}
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
