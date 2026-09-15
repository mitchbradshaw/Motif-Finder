/* library.grouping — frame library-4: the Edit grouping modal over the (inert) page it was opened from.
 * 1 what to group · 2 group by (9 bases in 3 kinds) · 3 parameters with the feature's distribution · 4 what does not
 * fit · Preview (groups, members, omitted, recompute, hand edits) · Save as grouping / Apply grouping (sim job l-0031). */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Bars, Button, Callout, Checkbox, Icon, InfoTip, Modal, NumberField, ProgressBar, Seg, SelectField, Slider, TextField, Toggle, fmtInt, getSim, recordDemoWrite, useQueryState, useSim,
  type IconName,
} from '../kit'
import { useToast } from '../shell/Toast'
import { navigate, useApp } from '../state'
import { useSourced } from '../api/seam'
import { HAND_EDITS_ORPHANED, UNIT_LABEL, getGroupingEditor, type BasisKind, type BasisOption, type FeatureBin, type Grouping, type Unit } from '../api/library'
import { nextGroupingId, useExternalNavKey, useAllGroupings, useMotifGroupingId, useSavedGroupings, useSelection, useSequenceGroupingId } from './chrome'
import { AtlasPage } from './AtlasPage'
import { FamilyPage } from './FamilyPage'
import { RecurrencePage } from './RecurrencePage'

type BinMode = 'quantiles' | 'log' | 'fixed'
interface Draft {
  unit: Unit; basis: BasisKind; feature: string; bins: BinMode; nBins: number; lo: number; hi: number; edges: string
  cut: number; nearest: number; maxGap: number; keepOrder: boolean; biphasic: number; tagMode: 'first' | 'combo'; provBy: 'recording' | 'run' | 'spike train'; clustering: string
  omitOutside: boolean; omitSmall: boolean; minMembers: number
}
const BASE: Omit<Draft, 'unit' | 'basis'> = { feature: 'dominant frequency · Welch PSD', bins: 'log', nBins: 6, lo: 0.002, hi: 0.5, edges: '0.002, 0.01, 0.03, 0.1, 0.5', cut: 0.42, nearest: 0.5, maxGap: 360, keepOrder: true, biphasic: 0.3, tagMode: 'first', provBy: 'recording', clustering: 'a-0098', omitOutside: true, omitSmall: true, minMembers: 10 }
const FEATURES: Partial<Record<BasisKind, { options: string[]; unit: string; extent: [number, number]; lo: number; hi: number; scale: 'log' | 'linear' }>> = {
  'frequency-content': { options: ['dominant frequency · Welch PSD', 'spectral centroid · Welch PSD'], unit: 'Hz', extent: [0.001, 1], lo: 0.002, hi: 0.5, scale: 'log' },
  amplitude: { options: ['peak-to-peak mV', 'depth mV'], unit: 'mV', extent: [0.05, 0.85], lo: 0.1, hi: 0.7, scale: 'linear' },
  timescale: { options: ['duration', 'rise time'], unit: 's', extent: [0.5, 60], lo: 0.5, hi: 50, scale: 'log' },
}
const GROUP_ICON: Record<string, IconName> = { distance: 'target', 'feature bins · no distance': 'bar-chart', labels: 'tag' }

function parseEdges(s: string): { edges: number[]; error: string | null } {
  const parts = s.split(',').map(x => x.trim()).filter(Boolean)
  const nums = parts.map(Number)
  if (parts.some(p => !Number.isFinite(Number(p)))) return { edges: [], error: `not a number: ${parts.find(p => !Number.isFinite(Number(p)))}` }
  if (nums.length < 3) return { edges: nums, error: 'at least 3 edges (2 bins)' }
  for (let i = 1; i < nums.length; i++) if (nums[i] <= nums[i - 1]) return { edges: nums, error: `edges must increase: ${nums[i]} ≤ ${nums[i - 1]} at position ${i + 1}` }
  return { edges: nums, error: null }
}

export function validate(d: Draft): { field: string; message: string } | null {
  const feat = FEATURES[d.basis]
  if (feat) {
    if (d.bins === 'fixed') { const e = parseEdges(d.edges).error; if (e) return { field: 'edges', message: e } }
    else {
      if (!Number.isInteger(d.nBins) || d.nBins < 2 || d.nBins > 20) return { field: 'number of bins', message: '2 to 20 bins' }
      if (d.bins === 'log') {
        if (!(d.lo < d.hi)) return { field: 'range', message: 'the lower edge must be below the upper edge' }
        if (d.lo <= 0) return { field: 'range', message: 'log-spaced bins need a range above 0' }
        if (d.lo < feat.extent[0] || d.hi > feat.extent[1]) return { field: 'range', message: `outside the data: ${feat.extent[0]}–${feat.extent[1]} ${feat.unit}` }
      }
    }
  }
  if (d.omitSmall && (!Number.isInteger(d.minMembers) || d.minMembers < 1 || d.minMembers > 1000)) return { field: 'minimum members', message: 'whole number from 1 to 1000' }
  return null
}

export function preview(d: Draft, unitCount: number): { groups: number; members: number; omitted: number; outside: number; small: number; smallGroups: number; recompute: string; minutes: number; apply: number; orphaned: number } {
  let groups = 5, outside = 0, small = 0, smallGroups = 0, minutes = 10
  const feat = FEATURES[d.basis]
  if (d.basis === 'shape-distance') {
    groups = Math.max(2, Math.round(10 * Math.pow(0.42 / d.cut, 1.3))); outside = Math.round(38 * Math.pow(d.nearest / 0.5, -1.5)); minutes = d.unit === 'sequences' ? 46 : 4
    if (d.unit === 'motifs' && d.cut === 0.42 && d.nearest === 0.5) outside = 38
  } else if (d.basis === 'sequence-similarity') { groups = Math.max(2, Math.round(6 * Math.pow(0.5 / d.cut, 1.2))); outside = 17; minutes = 12 }
  else if (feat) {
    const nb = d.bins === 'fixed' ? Math.max(1, parseEdges(d.edges).edges.length - 1) : d.nBins
    outside = d.bins === 'quantiles' ? 0 : d.basis === 'frequency-content' ? (d.hi >= 0.9 ? 0 : 14) : 9
    smallGroups = d.bins === 'quantiles' ? 0 : nb >= 6 ? 1 : 0; small = smallGroups * 7
    groups = nb; minutes = d.basis === 'frequency-content' ? 10 : 3
  } else if (d.basis === 'polarity') { groups = 3; minutes = 2 }
  else if (d.basis === 'tag') { groups = d.tagMode === 'first' ? 6 : 11; smallGroups = d.tagMode === 'combo' ? 3 : 0; small = smallGroups * 4; outside = 312; minutes = 1 }
  else if (d.basis === 'provenance') { groups = d.provBy === 'recording' ? 3 : d.provBy === 'run' ? 7 : 16; minutes = 1 }
  else if (d.basis === 'custom') { groups = 6; outside = 1211; minutes = 1 }
  if (!d.omitOutside) outside = 0
  if (!d.omitSmall) { small = 0; smallGroups = 0 }
  if (d.basis === 'custom') outside = 1211 // unassigned outside the clustering's scope is always explicit (§8.3)
  const omitted = outside + small
  const bins = !!feat || d.basis === 'polarity' || d.basis === 'tag' || d.basis === 'provenance' || d.basis === 'custom'
  const orphaned = d.basis === 'shape-distance' && d.cut === 0.42 ? 0 : bins ? 3 : 1
  return { groups: Math.max(1, groups - smallGroups), members: unitCount - omitted, omitted, outside, small, smallGroups, recompute: `~${minutes} min, ${minutes > 20 ? 'over the 20 min local limit' : 'local'}`, minutes, apply: 14 - orphaned, orphaned }
}

export function GroupingPage() {
  const { route } = useApp()
  const from = route.query.from ?? 'atlas'
  const navKey = useExternalNavKey()
  const background = from === 'recurrence' ? <RecurrencePage /> : from.startsWith('family/') ? <FamilyPage familyId={from.split('/')[1]} /> : <AtlasPage backdrop />
  return (
    <>
      {background}
      <GroupingEditor key={navKey} from={from} />
    </>
  )
}

const SIM_ID = 'library.regroup.l-0031'
const STEPS = ['compute feature', 'bin', 're-apply 14 hand edits', 'write grouping']

function GroupingEditor({ from }: { from: string }) {
  const editor = useSourced(getGroupingEditor, [])
  const { all } = useAllGroupings()
  const [motifGid, setMotifGid] = useMotifGroupingId()
  const [seqGid, setSeqGid] = useSequenceGroupingId()
  const [saved, setSaved] = useSavedGroupings()
  const [, setSel] = useSelection()
  const { push } = useToast()
  const [unitQ, setUnitQ] = useQueryState<string>('unit', 'motifs')
  const [basisQ, setBasisQ] = useQueryState<string>('basis', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const startUnit: Unit = unitQ === 'sequences' || unitQ === 'spike-trains' ? unitQ : 'motifs'
  const current = all.find(g => g.id === (startUnit === 'sequences' ? seqGid : motifGid))
  const initialBasis: BasisKind = (basisQ as BasisKind) || (startUnit === 'sequences' ? 'sequence-similarity' : startUnit === 'spike-trains' ? 'amplitude' : 'shape-distance')
  const [d, setD] = useState<Draft>(() => ({ ...BASE, unit: startUnit, basis: initialBasis, cut: initialBasis === 'sequence-similarity' ? 0.5 : 0.42, ...(FEATURES[initialBasis] ? { feature: FEATURES[initialBasis]!.options[0], lo: FEATURES[initialBasis]!.lo, hi: FEATURES[initialBasis]!.hi } : null) }))
  const [savedSig, setSavedSig] = useState<{ sig: string; id: string } | null>(null)
  const run = useSim(SIM_ID)
  const forced = useRef(false)
  const close = () => { if (run.busy) run.cancel(); run.reset(); navigate(`library/${from}`) }

  // deep links: ?state=running | failed
  useEffect(() => {
    if (stateQ === 'running' && getSim(SIM_ID).status === 'idle') { forced.current = true; run.force({ status: 'running', steps: STEPS.map((s, i) => i === 3 ? `write grouping ${nextGroupingId(all)}` : s), step: 1, fraction: 0.38, startedAt: Date.now() }) }
    if (stateQ === 'failed' && getSim(SIM_ID).status === 'idle') { forced.current = true; run.force({ status: 'failed', steps: STEPS, step: 3, fraction: 0.8, error: 'write grouping failed: the catalogue changed during the regroup (3 motifs imported) · nothing was written' }) }
  }, [stateQ]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => { if (forced.current) run.reset() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const units = editor.data?.units ?? []
  const unitCount = units.find(u => u.unit === d.unit)?.count ?? 1402
  const basis = editor.data?.bases.find(b => b.kind === d.basis)
  const invalid = validate(d)
  const pv = useMemo(() => preview(d, unitCount), [d, unitCount])
  const sig = JSON.stringify(d)
  const unchanged = d.unit === 'motifs' && d.basis === 'shape-distance' && d.cut === 0.42 && d.nearest === 0.5 && d.omitOutside && d.omitSmall && d.minMembers === 10 && motifGid === 'g-07'
  const nextId = savedSig?.sig === sig ? savedSig.id : nextGroupingId([...all, ...saved])
  const overLimit = pv.minutes > 20
  const set = (patch: Partial<Draft>) => setD(x => ({ ...x, ...patch }))
  const pickUnit = (u: Unit) => {
    const ok = (b: BasisOption) => b.units.includes(u)
    const cur = editor.data?.bases.find(b => b.kind === d.basis)
    const nextBasis = cur && ok(cur) ? d.basis : (editor.data?.bases.find(ok)?.kind ?? 'amplitude')
    set({ unit: u, basis: nextBasis }); setUnitQ(u === 'motifs' ? null : u); if (nextBasis !== d.basis) setBasisQ(nextBasis)
  }
  const pickBasis = (b: BasisKind) => {
    const f = FEATURES[b]
    set({ basis: b, ...(f ? { feature: f.options[0], lo: f.lo, hi: f.hi } : null), cut: b === 'sequence-similarity' ? 0.5 : b === 'shape-distance' ? 0.42 : d.cut })
    setBasisQ(b)
  }
  const buildGrouping = (id: string): Grouping => {
    const title = basis?.title ?? d.basis
    const params = FEATURES[d.basis] ? (d.bins === 'fixed' ? `edges ${d.edges}` : `${d.bins === 'log' ? 'log-spaced' : 'quantiles'} · ${d.nBins} bins${d.bins === 'log' ? ` · ${d.lo}–${d.hi} ${FEATURES[d.basis]!.unit}` : ''}`)
      : d.basis === 'shape-distance' || d.basis === 'sequence-similarity' ? `cut ${d.cut.toFixed(2)}` : d.basis === 'provenance' ? `by ${d.provBy}` : d.basis === 'tag' ? (d.tagMode === 'first' ? 'first tag' : 'per combination') : d.basis === 'custom' ? d.clustering : 'up · down · biphasic'
    return { id, unit: d.unit, basis: d.basis, basisLabel: title, params, chip: [title, params], computed: '16 Sep 2026', motifs: unitCount, families: pv.groups, omitted: pv.omitted, handEditsKept: 14 }
  }
  const save = () => {
    const g = buildGrouping(nextId)
    setSaved(s => [...s.filter(x => x.id !== g.id), g]); setSavedSig({ sig, id: g.id })
    recordDemoWrite('library', 'grouping.save', { id: g.id, unit: d.unit, basis: d.basis })
    push({ text: `Saved ${g.id} · not applied · not wired yet: POST /api/library/groupings` })
  }
  const apply = () => {
    if (overLimit) { push({ text: `not wired yet: export a cluster job for the regroup (${pv.recompute})` }); return }
    run.start({ steps: STEPS.map((s, i) => i === 3 ? `write grouping ${nextId}` : s), stepMs: 900 })
    recordDemoWrite('library', 'grouping.apply', { id: nextId, job: 'l-0031' })
  }
  // done → switch the catalogue to the new grouping, clear the scope, go to the atlas
  useEffect(() => {
    if (run.status !== 'done' || forced.current) return
    const id = run.steps[3]?.replace('write grouping ', '') || nextId
    const g = buildGrouping(id)
    setSaved(s => [...s.filter(x => x.id !== id), g])
    if (d.unit === 'motifs') setMotifGid(id)
    if (d.unit === 'sequences') setSeqGid(id)
    setSel([])
    run.reset()
    push({ text: `Grouping ${id} applied · ${pv.groups} groups · ${pv.omitted} omitted · scope cleared · ${current?.id ?? 'g-07'} stays saved` })
    navigate(d.unit === 'sequences' ? 'library/atlas?unit=sequences' : 'library/atlas')
  }, [run.status]) // eslint-disable-line react-hooks/exhaustive-deps

  const busy = run.busy
  const failed = run.status === 'failed'
  const saveReason = invalid ? `fix ${invalid.field}: ${invalid.message}` : unchanged ? `same as ${current?.id ?? 'g-07'}` : savedSig?.sig === sig ? `saved as ${savedSig.id}` : null
  const applyReason = invalid ? `fix ${invalid.field}: ${invalid.message}` : unchanged ? 'already the current grouping' : d.unit === 'spike-trains' ? 'no atlas draws spike-train groupings yet (B17) — save it instead' : null
  const footer = busy || failed ? (
    <div className="row" style={{ gap: 10, width: '100%' }} data-testid="regroup-progress">
      {failed ? <span className="mono small" style={{ color: 'var(--red)' }}>job l-0031 failed at {run.steps[run.step]}</span>
        : <><span className="mono small muted">job l-0031 · {run.status === 'queued' ? 'queued' : `${run.step + 1}/${run.steps.length} ${run.steps[run.step]}`}</span><ProgressBar value={run.fraction} width={260} /></>}
      <span style={{ marginLeft: 'auto' }} />
      {failed ? <><Button onClick={() => { run.reset(); setStateQ(null); forced.current = false }}>Back to settings</Button><Button variant="primary" icon="refresh" testid="regroup-retry" onClick={() => { forced.current = false; setStateQ(null); run.reset(); apply() }}>Retry</Button></>
        : <Button testid="regroup-cancel" onClick={() => { run.cancel(); run.reset(); setStateQ(null); forced.current = false; push({ text: 'Regroup l-0031 cancelled · nothing was written' }) }}>Cancel job</Button>}
    </div>
  ) : (
    <>
      <Button icon="save" testid="save-grouping" disabled={!!saveReason} disabledReason={saveReason ?? undefined} onClick={save}>Save as grouping {nextId}</Button>
      {overLimit
        ? <Button variant="cluster" icon="server" testid="apply-grouping" disabled={!!applyReason} disabledReason={applyReason ?? undefined} onClick={apply}>Create SLURM script</Button>
        : <Button variant="primary" icon="check" testid="apply-grouping" disabled={!!applyReason} disabledReason={applyReason ?? undefined} onClick={apply}>Apply grouping</Button>}
    </>
  )
  const groupsOfBases = ['distance', 'feature bins · no distance', 'labels'] as const
  return (
    <Modal open onClose={close} width={810} testid="edit-grouping-modal" closeOnBackdrop={!busy}
      title={<span className="row" style={{ gap: 8 }}><Icon name="sliders" size={16} />Edit grouping</span>}
      subtitle={`from ${current?.id ?? 'g-07'} · ${current?.basisLabel.split(' · ')[0] ?? 'shape distance'}`}
      footerNote={busy || failed ? undefined : <Button testid="grouping-cancel" onClick={close}>Cancel</Button>} footer={footer} bodyStyle={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {editor.error && <Callout tone="red" title="Could not read the grouping options">{editor.error.message}</Callout>}
      {editor.loading && <div className="skeleton" style={{ height: 420 }} />}
      {editor.data && basis && <>
        <section className="lib-ge-sec" data-testid="ge-unit">
          <h4>1&nbsp; What to group</h4>
          <div className="lib-units" role="radiogroup" aria-label="what to group">
            {units.map(u => (
              <button key={u.unit} type="button" role="radio" aria-checked={d.unit === u.unit} className="lib-unit" data-testid={`unit-${u.unit}`} disabled={busy} onClick={() => pickUnit(u.unit)}>
                <span className="lib-radio" /><span className="stack" style={{ gap: 1 }}><span className="t">{UNIT_LABEL[u.unit]}</span><span className="c">{u.caption}</span></span>
                <span className="n" title={u.unit === 'sequences' ? '350 reads as motifs in sequences; 139 sequences (flagged)' : undefined}>{fmtInt(u.count)}</span>
              </button>
            ))}
          </div>
        </section>
        <section className="lib-ge-sec" data-testid="ge-basis">
          <h4>2&nbsp; Group by</h4>
          <div className="lib-bases">
            {groupsOfBases.map(grp => (
              <div key={grp} className="col" role="radiogroup" aria-label={grp}>
                <span className="colhead"><Icon name={GROUP_ICON[grp]} size={12} />{grp}</span>
                {editor.data!.bases.filter(b => b.group === grp).map(b => {
                  const dis = !b.units.includes(d.unit)
                  const btn = (
                    <button key={b.kind} type="button" role="radio" aria-checked={d.basis === b.kind} className="lib-basis" data-testid={`basis-${b.kind}`} disabled={dis || busy} title={dis ? b.reason : undefined} onClick={() => pickBasis(b.kind)}>
                      <span className="lib-radio" /><span><span className="t">{b.title}</span><span className="c">{dis && b.reason !== b.caption ? `⊘ ${b.reason}` : b.caption}</span></span>
                    </button>
                  )
                  return btn
                })}
              </div>
            ))}
          </div>
        </section>
        <section className="lib-ge-sec" data-testid="ge-params">
          <h4>3&nbsp; {basis.title[0].toUpperCase() + basis.title.slice(1)}</h4>
          <Params d={d} set={set} basis={d.basis} dist={editor.data.distributions[d.basis]} clusterings={editor.data.clusterings} invalid={invalid} />
        </section>
        <section className="lib-ge-sec" data-testid="ge-misfits">
          <h4>4&nbsp; What does not fit</h4>
          <div className="row" style={{ gap: 22, flexWrap: 'wrap' }}>
            <span className="row" style={{ gap: 6 }}>
              <Checkbox checked={d.omitOutside} onChange={v => set({ omitOutside: v })} testid="omit-outside" disabled={d.basis === 'custom'} disabledReason="members outside a custom clustering's scope are always listed as unassigned (§8.3)"
                label={FEATURES[d.basis] ? 'omit and flag motifs outside every bin' : d.basis === 'custom' ? 'unassigned outside the clustering scope' : 'omit and flag motifs past the nearest-family distance'} />
              <span className="mono small" style={{ color: '#c27400' }}>{fmtInt(preview({ ...d, omitOutside: true }, unitCount).outside)} motifs</span>
            </span>
            <span className="row" style={{ gap: 6 }}>
              <Checkbox checked={d.omitSmall} onChange={v => set({ omitSmall: v })} testid="omit-small" label={<>omit and flag groups under</>} />
              <NumberField size="sm" width={58} value={d.minMembers} integer min={1} max={1000} showError={false} ariaLabel="minimum members" testid="min-members" onValid={n => set({ minMembers: n })} onChange={(raw, reason) => { if (reason) set({ minMembers: Number(raw) || -1 }) }} disabled={!d.omitSmall} disabledReason="tick the box to set a minimum size" />
              <span className="mono small">members</span>
              <span className="mono small" style={{ color: '#c27400' }}>{(() => { const p = preview({ ...d, omitSmall: true }, unitCount); return `${p.small} motifs · ${p.smallGroups} group${p.smallGroups === 1 ? '' : 's'}` })()}</span>
            </span>
          </div>
        </section>
        <div className="lib-preview" data-testid="grouping-preview">
          <div className="nums">
            <b style={{ marginLeft: 0, fontSize: 13 }}>Preview</b>
            <span>groups<b data-testid="preview-groups">{invalid ? '—' : pv.groups}</b></span>
            <span>members<b>{invalid ? '—' : fmtInt(pv.members)}</b></span>
            <span>omitted · flagged<b style={{ color: '#c27400' }} data-testid="preview-omitted">{invalid ? '—' : fmtInt(pv.omitted)}</b></span>
            <span>recompute<b style={{ color: overLimit ? '#c27400' : undefined }}>{invalid ? '—' : pv.recompute}</b></span>
          </div>
          {invalid && <span className="mono small" style={{ color: 'var(--red)' }} data-testid="preview-invalid"><Icon name="alert-circle" size={11} style={{ verticalAlign: -1 }} /> {invalid.field}: {invalid.message}</span>}
          <span className="mono small" style={{ color: 'var(--k-purple-text, #6b3fd4)' }}><Icon name="user" size={11} style={{ verticalAlign: -1 }} /> 14 hand edits: {pv.apply} apply{pv.orphaned ? ` · ${pv.orphaned} point at families this grouping lacks → kept as the hand group “F-03 additions”` : ''}
            {pv.orphaned > 0 && <InfoTip title="kept as a hand group">{HAND_EDITS_ORPHANED.slice(0, pv.orphaned).join(', ')} were added to F-03 by hand; this grouping has no F-03, so they stay together as “F-03 additions” (§8.3)</InfoTip>}</span>
          <span className="mono small muted"><Icon name="info" size={11} style={{ verticalAlign: -1 }} /> applying regroups the whole catalogue and clears the current scope; {current?.id ?? 'g-07'} stays saved</span>
          {overLimit && <span className="mono small" style={{ color: '#c27400' }}><Icon name="hourglass" size={11} style={{ verticalAlign: -1 }} /> over the local limit — the regroup is exported as a cluster job</span>}
        </div>
        {failed && <Callout tone="red" title="Regroup failed · nothing was written" testid="regroup-failed">{run.error}</Callout>}
      </>}
    </Modal>
  )
}

function Params({ d, set, basis, dist, clusterings, invalid }: { d: Draft; set: (p: Partial<Draft>) => void; basis: BasisKind; dist?: FeatureBin[]; clusterings: { value: string; label: string; scope: string }[]; invalid: { field: string; message: string } | null }) {
  const feat = FEATURES[basis]
  const err = (field: string) => invalid?.field === field ? <span className="k-field-error" role="alert" data-testid="param-error"><Icon name="alert-circle" size={11} />{invalid.message}</span> : null
  if (feat && dist) {
    const edges = d.bins === 'fixed' ? parseEdges(d.edges).edges : d.bins === 'log' ? Array.from({ length: d.nBins + 1 }, (_, i) => d.lo * Math.pow(d.hi / d.lo, i / d.nBins)) : quantileEdges(dist, d.nBins)
    return (
      <div className="lib-params">
        <div className="stack" style={{ gap: 6 }}>
          <span className="lib-cap" style={{ fontSize: 11 }}>feature</span>
          <SelectField value={d.feature} onChange={v => set({ feature: v })} options={feat.options.map(o => ({ value: o, label: o }))} testid="param-feature" />
          <div className="lib-param-row"><span>bins</span><Seg size="sm" ariaLabel="bins" testid="param-bins" value={d.bins} onChange={v => set({ bins: v })} options={[{ value: 'quantiles', label: 'quantiles' }, { value: 'log', label: 'log-spaced' }, { value: 'fixed', label: 'fixed edges' }]} /></div>
          {d.bins !== 'fixed' && <div className="lib-param-row"><span>number of bins</span><NumberField size="sm" width={64} value={d.nBins} integer min={2} max={20} showError={false} testid="param-nbins" ariaLabel="number of bins" onValid={n => set({ nBins: n })} onChange={(raw, reason) => { if (reason) set({ nBins: Number(raw) || 0 }) }} /></div>}
          {err('number of bins')}
          {d.bins === 'log' && <div className="lib-param-row"><span>range</span><span className="row" style={{ gap: 4 }}>
            <NumberField size="sm" width={72} value={d.lo} showError={false} testid="param-lo" ariaLabel="range lower" onValid={n => set({ lo: n })} onChange={(raw, reason) => { if (reason) set({ lo: Number(raw) || 0 }) }} />–
            <NumberField size="sm" width={72} value={d.hi} unit={feat.unit} showError={false} testid="param-hi" ariaLabel="range upper" onValid={n => set({ hi: n })} />
          </span></div>}
          {err('range')}
          {d.bins === 'fixed' && <><div className="lib-param-row"><span>edges</span><TextField size="sm" value={d.edges} onChange={v => set({ edges: v })} invalid={invalid?.field === 'edges'} testid="param-edges" width={190} suffix={feat.unit} /></div>{err('edges')}</>}
          {d.bins === 'quantiles' && <span className="lib-cap">edges at the quantiles; every motif falls in a bin</span>}
        </div>
        <FeatureHistogram bins={dist} edges={invalid ? [] : edges} scale={feat.scale} unit={feat.unit} lo={d.bins === 'log' ? d.lo : edges[0]} hi={d.bins === 'log' ? d.hi : edges[edges.length - 1]} title={`motifs per ${feat.unit === 'Hz' ? 'frequency' : feat.unit === 'mV' ? 'amplitude' : 'duration'} · ${feat.scale} axis`} />
      </div>
    )
  }
  if (basis === 'shape-distance' || basis === 'sequence-similarity') {
    return (
      <div className="lib-params">
        <div className="stack" style={{ gap: 6 }}>
          <div className="lib-param-row"><span>linkage</span><SelectField size="sm" value="ward" onChange={() => undefined} options={[{ value: 'ward', label: 'Ward' }]} width={120} /></div>
          <div className="lib-param-row"><span>cut</span><Slider value={d.cut} min={0.1} max={1} step={0.01} onChange={v => set({ cut: +v.toFixed(2) })} format={v => v.toFixed(2)} width={190} testid="param-cut" ariaLabel="cut" /></div>
          {basis === 'shape-distance' ? <div className="lib-param-row"><span>nearest family past</span><NumberField size="sm" width={64} value={d.nearest} min={0.1} max={1} step={0.01} testid="param-nearest" ariaLabel="nearest family distance" onValid={n => set({ nearest: n })} /></div>
            : <><div className="lib-param-row"><span>max gap between events</span><NumberField size="sm" width={80} value={d.maxGap} min={1} max={3600} integer unit="s" testid="param-maxgap" ariaLabel="max gap" onValid={n => set({ maxGap: n })} /></div>
              <div className="lib-param-row"><span>order</span><Toggle size="sm" checked={d.keepOrder} onChange={v => set({ keepOrder: v })} label="events must keep order" testid="param-order" /></div></>}
        </div>
        <FeatureHistogram bins={dist ?? []} edges={[]} scale="linear" unit="" lo={0} hi={1} cut={d.cut} title={basis === 'shape-distance' ? `merge heights · ${preview(d, 1402).groups} families at ${d.cut.toFixed(2)}` : `pairwise sequence similarity · cut ${d.cut.toFixed(2)}`} />
      </div>
    )
  }
  const bars = basis === 'polarity' ? { cats: ['up', 'down', 'biphasic'], vals: [388, 702, 312] } : basis === 'tag' ? { cats: ['sharkfin', 'biphasic', 'plateau-top', 'ramp', 'notched', 'spike-doublet'], vals: [301, 244, 180, 170, 110, 85] }
    : basis === 'provenance' ? (d.provBy === 'recording' ? { cats: ['M2_aug fs1', 'M3_jul', 'L_LM_Jul26_J'], vals: [902, 380, 120] } : d.provBy === 'run' ? { cats: ['#128', '#131', '#97', 'r-0412', 'r-0415', 'r-0431', 'import'], vals: [410, 220, 180, 260, 142, 80, 110] } : { cats: Array.from({ length: 16 }, (_, i) => `st-${i + 1}`), vals: Array.from({ length: 16 }, (_, i) => 20 + ((i * 37) % 60)) })
      : { cats: ['c0', 'c1', 'c2', 'c3', 'c4', 'c5', 'unassigned'], vals: [42, 38, 31, 29, 30, 21, 1211] }
  return (
    <div className="lib-params">
      <div className="stack" style={{ gap: 6 }}>
        {basis === 'polarity' && <div className="lib-param-row"><span>biphasic ratio</span><NumberField size="sm" width={64} value={d.biphasic} min={0} max={1} step={0.05} testid="param-biphasic" ariaLabel="biphasic ratio" onValid={n => set({ biphasic: n })} /></div>}
        {basis === 'tag' && <><div className="lib-param-row"><span>tag set</span><SelectField size="sm" value="morphology" onChange={() => undefined} options={[{ value: 'morphology', label: 'morphology tags' }]} width={160} /></div>
          <div className="lib-param-row"><span>several tags</span><Seg size="sm" value={d.tagMode} onChange={v => set({ tagMode: v })} options={[{ value: 'first', label: 'first tag' }, { value: 'combo', label: 'one group per combination' }]} /></div>
          <span className="lib-cap">312 motifs carry no tag · omitted and flagged</span></>}
        {basis === 'provenance' && <div className="lib-param-row"><span>by</span><Seg size="sm" value={d.provBy} onChange={v => set({ provBy: v })} testid="param-prov" options={[{ value: 'recording', label: 'recording' }, { value: 'run', label: 'run' }, { value: 'spike train', label: 'spike train' }]} /></div>}
        {basis === 'custom' && <><span className="lib-cap" style={{ fontSize: 11 }}>clustering</span><SelectField value={d.clustering} onChange={v => set({ clustering: v })} options={clusterings.map(c => ({ value: c.value, label: c.label }))} testid="param-clustering" />
          <Callout tone="amber" icon="info">{clusterings.find(c => c.value === d.clustering)?.scope}</Callout></>}
      </div>
      <div className="k-card grey" style={{ padding: 10 }} data-testid="param-bars">
        <Bars categories={bars.cats} series={[{ key: 'n', label: 'motifs', colour: '#8cbfff', values: bars.vals }]} height={130} legend={false} />
      </div>
    </div>
  )
}

function quantileEdges(dist: FeatureBin[], n: number): number[] {
  const total = dist.reduce((s, b) => s + b.n, 0), out = [dist[0].lo]
  let acc = 0, k = 1
  for (const b of dist) { acc += b.n; while (k < n && acc >= (total * k) / n) { out.push(b.hi); k++ } }
  out.push(dist[dist.length - 1].hi)
  return out
}

/** Distribution with bin edges (or a cut) drawn on it; log or linear x. Bars outside [lo, hi] are amber. */
function FeatureHistogram({ bins, edges, scale, unit, lo, hi, cut, title }: { bins: FeatureBin[]; edges: number[]; scale: 'log' | 'linear'; unit: string; lo: number; hi: number; cut?: number; title: string }) {
  const W = 430, H = 112, padL = 8, padR = 8, padT = 22, padB = 18
  if (!bins.length) return <div className="k-card grey" style={{ padding: 10 }}><span className="lib-cap">no distribution</span></div>
  const x0 = bins[0].lo, x1 = bins[bins.length - 1].hi
  const tx = (v: number) => padL + (scale === 'log' ? (Math.log(v) - Math.log(x0)) / (Math.log(x1) - Math.log(x0)) : (v - x0) / (x1 - x0)) * (W - padL - padR)
  const max = Math.max(...bins.map(b => b.n))
  const ty = (n: number) => H - padB - (n / max) * (H - padT - padB)
  const ticks = scale === 'log' ? [lo, Math.sqrt(lo * hi), hi].map(v => +v.toPrecision(1)) : [x0, (x0 + x1) / 2, x1].map(v => +v.toFixed(2))
  const outside = (b: FeatureBin) => cut == null && (b.hi > hi * 1.0001 || b.lo < lo * 0.9999)
  return (
    <div className="k-card grey" style={{ padding: '6px 8px' }} data-testid="feature-histogram">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 9 }}>
        <text x={padL} y={11} fill="var(--muted)">{title}</text>
        {bins.map((b, i) => <rect key={i} x={tx(b.lo) + 0.8} width={Math.max(1, tx(b.hi) - tx(b.lo) - 1.6)} y={ty(b.n)} height={H - padB - ty(b.n)} fill={outside(b) ? '#f6c27a' : '#94c2ff'}><title>{`${b.lo}–${b.hi} ${unit} · ${b.n} motifs`}</title></rect>)}
        <line x1={padL} x2={W - padR} y1={H - padB} y2={H - padB} stroke="var(--border-strong)" />
        {edges.map((e, i) => <line key={i} x1={tx(e)} x2={tx(e)} y1={padT - 4} y2={H - padB} stroke={i === 0 || i === edges.length - 1 ? 'var(--blue)' : '#1f2937'} strokeWidth={1} />)}
        {cut != null && <g><line x1={tx(cut)} x2={tx(cut)} y1={padT - 6} y2={H - padB} stroke="var(--amber)" strokeWidth={1.5} strokeDasharray="4 3" /><text x={tx(cut) + 4} y={padT} fill="#c27400">cut {cut.toFixed(2)}</text></g>}
        {cut == null && bins.some(outside) && <text x={W - padR} y={padT} textAnchor="end" fill="#c27400">outside range</text>}
        {ticks.map((t, i) => <text key={i} x={tx(Math.min(x1, Math.max(x0, t)))} y={H - 5} textAnchor={i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle'} fill="var(--muted)">{t}{i === ticks.length - 1 ? ` ${unit}` : ''}</text>)}
      </svg>
    </div>
  )
}
