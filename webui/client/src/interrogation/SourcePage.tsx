/* analyse.interrogation — the source block (frames interrogation-1, interrogation-1b).
 * §6.2: a chain starts from a source block; this one emits a SpanSet from a Library family, with
 * per-member include/exclude that scopes the run and leaves the Library entry alone. */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Badge, Button, Callout, Checkbox, ColourDot, Dropdown, EmptyState, Field, Icon, InfoTip, LineChart, MiniTrace, Page, Pager,
  SectionCard, fmtInt, recordDemoWrite, useNotWired, useQueryState, useSim, type BadgeStatus,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, setQuery } from '../state'
import { useSourced } from '../api/seam'
import { getSourceBlock, type SourceBlock } from '../api/interrogation'
import {
  ALIGNMENTS, FAMILY_Y_DOMAIN, RUN_STEPS, SORTS, VERDICT_COLOUR, VERDICT_ORDER, eventCurve,
  type InterrogationMember,
} from '../fixtures/interrogation'
import { AddStagePopover, ChainCard, EmptyScope, InterrogationToolbar, LoadFailed, Loading, RunVeil, SaveTemplateModal } from './chrome'
import { SourcePicker } from './SourcePicker'
import { inScopeIds, useFamilyQuery, useInterrogationDraft, useUpstreamQuery } from './draft'

export function SourcePage() {
  const [familyId] = useFamilyQuery()
  const [upstream] = useUpstreamQuery()
  const [draft] = useInterrogationDraft()
  const block = useSourced(() => getSourceBlock(familyId, upstream), [familyId, upstream])
  const fam = block.data?.family
  const nScope = block.data ? inScopeIds(block.data.members, draft, fam!.id, true).size : 0
  return (
    <>
      <Header workspace="Analyse" page="Library family" search="Search spans, runs, families" demo={block.source === 'demo'}
        subtitle={fam ? `${fam.id} ${fam.name} · ${nScope} of ${fam.within} members in scope` : 'source block'} />
      <Page testid="interrogation-source">
        {block.error ? <LoadFailed what="the source block" error={block.error} onRetry={block.reload} />
          : !block.data ? <Loading what="the family" /> : <SourceBody block={block.data} />}
      </Page>
    </>
  )
}

function SourceBody({ block }: { block: SourceBlock }) {
  const { push } = useToast()
  const notWired = useNotWired()
  const [familyId, setFamilyId] = useFamilyQuery()
  const [upstream] = useUpstreamQuery()
  const [draft, setDraft] = useInterrogationDraft()
  const [popover, setPopover] = useQueryState('popover', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  const [excludeArtifacts, setExcludeArtifacts] = useQueryState('artifacts', 'out')
  const [adjOnly, setAdjOnly] = useQueryState('adjudicated', '')
  const [recordingQ, setRecordingQ] = useQueryState('recording', 'all')
  const [channelQ, setChannelQ] = useQueryState('channel', 'all')
  const [sortQ, setSortQ] = useQueryState('sort', 'distance')
  const [alignQ, setAlignQ] = useQueryState('align', 'onset')
  const [distanceQ, setDistanceQ] = useQueryState('distance', String(block.family.threshold))
  const [scopeQ, setScopeQ] = useQueryState('scope', 'all')
  const [page, setPage] = useState(1)
  const [overlaySeed, setOverlaySeed] = useState(0)
  const [saveOpen, setSaveOpen] = useState(false)

  const sourceRef = useRef<HTMLButtonElement>(null)
  const stageRef = useRef<HTMLButtonElement>(null)

  const fam = block.family
  const hidesArtifacts = excludeArtifacts === 'out'
  const handExcluded = draft.excluded[fam.id] ?? []
  const scope = scopeQ === 'none' ? new Set<string>() : inScopeIds(block.members, draft, fam.id, hidesArtifacts)

  /* ---- filters, sort, paging (the tile grid caps at 10 — P8) ---- */
  const visible = useMemo(() => {
    let xs = block.members.filter(m => m.d <= Number(distanceQ))
    if (adjOnly === '1') xs = xs.filter(m => m.verdict !== 'unadjudicated')
    if (recordingQ !== 'all') xs = xs.filter(m => m.recording === recordingQ)
    if (channelQ !== 'all') xs = xs.filter(m => m.channel === channelQ)
    const by: Record<string, (a: InterrogationMember, b: InterrogationMember) => number> = {
      distance: (a, b) => a.d - b.d,
      onset: (a, b) => a.onset_h - b.onset_h,
      depth: (a, b) => b.depth_mV - a.depth_mV,
      verdict: (a, b) => VERDICT_ORDER.indexOf(a.verdict) - VERDICT_ORDER.indexOf(b.verdict),
    }
    return [...xs].sort(by[sortQ] ?? by.distance)
  }, [block.members, distanceQ, adjOnly, recordingQ, channelQ, sortQ])
  const pageCount = Math.max(1, Math.ceil(visible.length / 10))
  const p = Math.min(page, pageCount)
  const tiles = visible.slice((p - 1) * 10, p * 10)

  /* ---- the run ---- */
  const sim = useSim('analyse.interrogation.run')
  useEffect(() => {
    if (stateQ === 'running') sim.force({ status: 'running', steps: RUN_STEPS, step: 1, fraction: 0.42, startedAt: Date.now() })
    if (stateQ === 'failed') sim.force({ status: 'failed', steps: RUN_STEPS, step: 1, fraction: 0.4, finishedAt: Date.now(), error: 'resolve from original recording failed (simulated): M2_aug_concat_fs1.mat could not be opened for member s-0344 · on missing source = fail the run' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const staleFrom = draft.staleFrom
  const status: Record<string, BadgeStatus> = {
    source: sim.status === 'running' && sim.step === 0 ? 'running' : 'cached',
    block1: sim.status === 'running' && sim.step >= 1 ? 'running' : sim.status === 'failed' ? 'failed' : staleFrom ? 'stale' : 'cached',
    block2: sim.status === 'running' && sim.step >= 2 ? 'running' : staleFrom ? 'stale' : 'cached',
  }

  const markStale = () => setDraft(d => ({ ...d, staleFrom: 'block1' }))
  const toggleMember = (id: string, on: boolean) => {
    setDraft(d => {
      const cur = d.excluded[fam.id] ?? []
      return { ...d, staleFrom: 'block1', excluded: { ...d.excluded, [fam.id]: on ? cur.filter(x => x !== id) : [...cur, id] } }
    })
    recordDemoWrite('analyse', 'scope-member', { family: fam.id, member: id, in_scope: on })
  }
  const setAll = (mode: 'all' | 'none' | 'invert') => {
    setScopeQ(null)
    setDraft(d => {
      const cur = new Set(d.excluded[fam.id] ?? [])
      const next = mode === 'all' ? [] : mode === 'none' ? visible.map(m => m.id)
        : visible.filter(m => !cur.has(m.id)).map(m => m.id)
      return { ...d, staleFrom: 'block1', excluded: { ...d.excluded, [fam.id]: next } }
    })
  }

  const runChain = () => { setStateQ(null); setDraft(d => ({ ...d, staleFrom: null })); sim.start({ steps: RUN_STEPS, stepMs: 800 }) }

  const nScope = scope.size
  const runReason = nScope === 0 ? 'no members in scope · nothing to measure'
    : fam.disabledReason ? fam.disabledReason : sim.busy ? 'the chain is already running' : undefined

  /* ---- scope matrix ---- */
  const channels = useMemo(() => [...new Set(block.members.map(m => m.channel))].sort(), [block.members])
  const matrix = useMemo(() => {
    const recs = [...new Set(block.members.map(m => m.recording))]
    const rows = recs.map(rec => ({
      rec,
      cells: channels.map(ch => block.members.filter(m => m.recording === rec && m.channel === ch && scope.has(m.id)).length),
    }))
    const excludedCells = channels.map(ch => block.members.filter(m => m.channel === ch && !scope.has(m.id)).length)
    return { rows, excludedCells }
  }, [block.members, channels, scope])

  /* ---- overlay: a seeded random 10 of the members in scope (P8) ---- */
  const overlayMembers = useMemo(() => {
    const inScope = block.members.filter(m => scope.has(m.id))
    const step = Math.max(1, Math.floor(inScope.length / 10))
    return Array.from({ length: Math.min(10, inScope.length) }, (_, i) => inScope[(i * step + overlaySeed * 3) % inScope.length])
  }, [block.members, scope, overlaySeed])
  const medoidCurve = useMemo(() => {
    const m = block.members.find(x => scope.has(x.id)) ?? block.members[0]
    return eventCurve({ ...m, depth_mV: 0.27, duration_s: 8.4, recovery_s: 12.6 }, 20, 30)
  }, [block.members, scope])

  const toPoints = (vs: number[], pre: number) => vs.map((v, i) => [i - pre, v] as [number, number]).filter(pt => pt[0] <= 40)

  return (
    <>
      <InterrogationToolbar
        backDisabledReason="this is the full chain · the source block is the chain root"
        sourceLabel={<>Library family · {fam.id} {fam.name}</>}
        sourceOpen={popover === 'source'} sourceRef={sourceRef} arrived
        onSourceToggle={() => setPopover(popover === 'source' ? null : 'source')}
        onSaveTemplate={() => setSaveOpen(true)}
        stale={!!staleFrom}
        primary={sim.busy
          ? <Button icon="stop" onClick={() => { sim.cancel(); setStateQ(null) }} testid="cancel-run">Cancel</Button>
          : <Button variant="primary" icon={staleFrom ? 'refresh' : 'play'} disabled={!!runReason} disabledReason={runReason} onClick={runChain} testid="run-chain">
            {staleFrom ? 'Re-run from 01' : 'Run chain'}
          </Button>}>
        <SourcePicker open={popover === 'source'} onClose={() => setPopover(null)} anchorRef={sourceRef} familyId={familyId}
          onPickFamily={id => { setQuery({ family: id === 'F-03' ? null : id, popover: null, tab: null }, false); setFamilyId(id); setPage(1) }} />
      </InterrogationToolbar>

      <ChainCard chain={block.chain} current="source" status={status} onAddStage={() => setPopover(popover === 'stage' ? null : 'stage')}
        onSelect={id => { if (id === 'block1') navigate(`analyse/interrogation/block/1${familyId === 'F-03' ? '' : `?family=${familyId}`}`); else if (id === 'block2') navigate(`analyse/interrogation/block/2${familyId === 'F-03' ? '' : `?family=${familyId}`}`) }} />
      <span ref={stageRef} style={{ display: 'none' }} />
      <AddStagePopover open={popover === 'stage'} onClose={() => setPopover(null)} anchorRef={sourceRef}
        onPick={kind => { setQuery({ upstream: kind === 'slope' ? null : kind }, false); push({ text: `01 is now ${kind === 'slope' ? 'Resolve spans — slope analysis' : 'Spike shape'} · 02 Aggregate re-wires from its Features` }) }} />

      {sim.status === 'failed' && (
        <Callout tone="red" title="The run failed at 01 Resolve spans" testid="run-failed"
          action={<Button size="sm" icon="refresh" onClick={runChain}>Retry</Button>}>{sim.error}</Callout>
      )}
      {sim.status === 'done' && (
        <Callout tone="green" icon="check-circle" testid="run-done" action={<Button size="sm" variant="primary" icon="bar-chart" onClick={() => navigate('analyse/interrogation/block/2')}>Open 02 Aggregate</Button>}>
          ran {RUN_STEPS.length} stages over {nScope} members · results are the fixture results (demo)
        </Callout>
      )}

      <div className="ig-cols">
        {/* ------------------------------------------------ the family ------------------------------------------------ */}
        <div className="ig-stack">
          <SectionCard testid="source-block" title={<span>● Library family <span className="ig-muted mono ig-small">— → SpanSet</span></span>}
            info="A source block does not measure anything; it decides which spans the chain runs over. Excluding a member scopes this run only — the Library entry is untouched."
            actions={<Dropdown testid="clustering" value="v3" onChange={() => notWired('change the clustering the family came from')}
              options={[{ value: 'v3', label: `clustering ${block.clustering.method} · t ${block.clustering.t} · ${block.clustering.version}` }, { value: 'v2', label: 'clustering Ward · t 8.4 · v2', description: 'the family had 94 members under v2' }]} />}>
            <div className="ig-fact" data-testid="family-facts" style={{ marginBottom: 8 }}>
              {fam.id} {fam.name} · {fmtInt(fam.members)} members · {fam.within} within d ≤ {fam.threshold.toFixed(2)} · {fam.recordings.length} recordings · {fam.channels.length} channels · {fam.adjudicated} adjudicated
            </div>

            <div className="ig-row" style={{ marginBottom: 8 }} data-testid="member-filters">
              <Checkbox checked={adjOnly === '1'} onChange={v => { setAdjOnly(v ? '1' : null); setPage(1) }} label="adjudicated only" testid="filter-adjudicated" />
              <Checkbox checked={hidesArtifacts} onChange={v => { setExcludeArtifacts(v ? null : 'in'); setPage(1); markStale() }} label="exclude artifacts" testid="filter-artifacts" />
              <Dropdown size="sm" testid="filter-distance" prefix="distance ≤" value={distanceQ} onChange={v => { setDistanceQ(v); setPage(1); markStale() }} active
                options={['0.25', '0.30', '0.35', '0.40'].map(v => ({ value: v, label: v }))} />
              <Dropdown size="sm" testid="filter-recording" prefix="recording" value={recordingQ} onChange={v => { setRecordingQ(v); setPage(1) }}
                options={[{ value: 'all', label: 'all' }, ...fam.recordings.map(r => ({ value: r, label: r })),
                  { value: 'M4_aug', label: 'M4_aug', disabled: true, reason: 'M4_aug_concat_fs1.mat is held out (D6) · every workspace refuses it' }]} />
              <Dropdown size="sm" testid="filter-channel" prefix="channel" value={channelQ} onChange={v => { setChannelQ(v); setPage(1) }}
                options={[{ value: 'all', label: 'all' }, ...channels.map(ch => ({ value: ch, label: ch }))]} />
              <span className="k-spacer" />
              <Dropdown size="sm" testid="filter-sort" prefix="sort" value={sortQ} onChange={v => { setSortQ(v); setPage(1) }} options={SORTS} />
            </div>

            <div className="ig-row" style={{ marginBottom: 8 }} data-testid="scope-row">
              <b style={{ fontSize: 12.5 }}>{nScope} of {fam.within} in scope</b>
              <Button size="sm" variant="link" onClick={() => setAll('all')} testid="select-all">select all</Button>
              <Button size="sm" variant="link" onClick={() => setAll('none')} testid="select-none">none</Button>
              <Button size="sm" variant="link" onClick={() => setAll('invert')} testid="select-invert">invert</Button>
              <span className="k-spacer" />
              <span className="ig-foot"><Icon name="link" size={11} />shared y · 0 to −0.45 mV · unnormalised</span>
            </div>

            <div className="ig-rel">
              {sim.busy && <RunVeil label={`${sim.steps[sim.step] ?? 'queued'} · ${Math.round(sim.fraction * 100)} %`} fraction={sim.fraction} />}
              {nScope === 0 && <EmptyScope onSelectAll={() => setAll('all')} />}
              {tiles.length === 0
                ? <EmptyState testid="no-member-match" size="sm" icon="filter" title="no member matches these filters"
                  caption={`${fam.within} members are within d ≤ ${fam.threshold.toFixed(2)} · widen the distance, recording or channel filter`}
                  action={<Button onClick={() => { setDistanceQ(null); setRecordingQ(null); setChannelQ(null); setAdjOnly(null); setPage(1) }} testid="clear-filters">Clear filters</Button>} />
                : (
                  <div className="ig-members" data-testid="member-grid">
                    {tiles.map(m => {
                      const on = scope.has(m.id)
                      const excludedByHand = handExcluded.includes(m.id)
                      return (
                        <div key={m.id} className={`ig-member ${on ? 'on' : 'off'}`} data-testid={`member-${m.id}`}>
                          <div className="hd">
                            <Checkbox checked={on} onChange={v => toggleMember(m.id, v)} ariaLabel={`${m.id} in scope`} testid={`member-check-${m.id}`}
                              disabled={m.verdict === 'artifact' && hidesArtifacts} disabledReason={m.verdict === 'artifact' && hidesArtifacts ? 'artifacts are excluded by the filter above' : undefined} />
                            <span className="id">{m.id}</span>
                            <span className="k-spacer" />
                            <ColourDot colour={VERDICT_COLOUR[m.verdict]} title={m.verdict} />
                          </div>
                          <div className="bd" role="button" tabIndex={0} title={`open ${m.id} in 01 Resolve spans`}
                            onClick={() => navigate(`analyse/interrogation/block/1?event=${m.id}${familyId === 'F-03' ? '' : `&family=${familyId}`}`)}
                            onKeyDown={e => { if (e.key === 'Enter') navigate(`analyse/interrogation/block/1?event=${m.id}`) }}>
                            <MiniTrace values={eventCurve(m)} yDomain={FAMILY_Y_DOMAIN} width="100%" height={54}
                              stroke={on ? fam.colour : 'var(--muted-2)'} title={`${m.id} · ${m.depth_mV.toFixed(3)} mV`} />
                          </div>
                          <div className="ft">
                            <span>{m.channel} · {m.onset_h.toFixed(1)} h</span>
                            {excludedByHand || (m.verdict === 'artifact' && hidesArtifacts) ? <span className="ex">excluded</span> : <span>d {m.d.toFixed(2)}</span>}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
            </div>

            <div className="ig-row" style={{ marginTop: 8 }}>
              <span className="ig-foot" data-testid="verdict-legend">
                {VERDICT_ORDER.map(v => <span key={v} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginRight: 10 }}>
                  <ColourDot colour={VERDICT_COLOUR[v]} />{v}
                </span>)}
              </span>
              <span className="k-spacer" />
              <Pager format="range" page={p} pageCount={pageCount} total={visible.length} pageSize={10} onPage={setPage} testid="member-pager" />
            </div>
          </SectionCard>

          <SectionCard testid="members-overlaid" title="Members overlaid"
            info="A seeded random sample, never all of them: families run to hundreds of members (P8). Traces are detrended mV on the family's shared scale — not normalised (D5)."
            subtitle={`random ${overlayMembers.length} of ${nScope} in scope · aligned on ${alignQ}`}
            actions={<>
              <Button size="sm" icon="shuffle" onClick={() => setOverlaySeed(s => s + 1)} testid="overlay-resample">resample</Button>
              <Dropdown testid="overlay-align" prefix="align" value={alignQ} onChange={setAlignQ} options={ALIGNMENTS} />
            </>}>
            {nScope === 0
              ? <EmptyState testid="overlay-empty" size="sm" icon="wave" title="nothing in scope to overlay" caption="tick a member above" />
              : <><LineChart testid="overlay-plot" height={190} xLabel={`seconds from ${alignQ}`} yLabel="mV" yDomain={FAMILY_Y_DOMAIN}
              xDomain={[-20, 40]} xFormat={v => `${v > 0 ? '+' : ''}${v} s`}
              series={[
                ...overlayMembers.map(m => ({ label: m.id, colour: fam.colour, points: toPoints(eventCurve(m, 20, 30), 20), width: 1 })),
                { label: `medoid ${fam.medoid}`, colour: '#111827', points: toPoints(medoidCurve, 20), width: 2 },
              ]} legend={false} />
              <div className="ig-foot" style={{ marginTop: 4 }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><span style={{ width: 14, height: 2, background: fam.colour }} />member</span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><span style={{ width: 14, height: 2, background: '#111827' }} />medoid {fam.medoid}</span>
              </div></>}
          </SectionCard>
        </div>

        {/* ------------------------------------------------ rails ------------------------------------------------ */}
        <div className="ig-stack">
          <SectionCard testid="scope-card" title="Scope" info="How the members in scope fall across recordings and channels. A family that lives on one channel measures one electrode, not one organism."
            subtitle="members in scope by recording × channel">
            <table className="ig-scope">
              <thead><tr><th>recording</th>{channels.map(ch => <th key={ch}>{ch}</th>)}<th>Σ</th></tr></thead>
              <tbody>
                {matrix.rows.map(r => (
                  <tr key={r.rec} data-testid={`scope-row-${r.rec}`}>
                    <td>{r.rec}</td>
                    {r.cells.map((n, i) => <td key={i} className={n ? undefined : 'z'}>{n || '—'}</td>)}
                    <td className="sum">{r.cells.reduce((a, b) => a + b, 0)}</td>
                  </tr>
                ))}
                <tr className="ex" data-testid="scope-excluded">
                  <td>excluded</td>
                  {matrix.excludedCells.map((n, i) => <td key={i}>{n || ''}</td>)}
                  <td className="sum" style={{ color: '#c4282d' }}>{matrix.excludedCells.reduce((a, b) => a + b, 0) || ''}</td>
                </tr>
              </tbody>
            </table>
          </SectionCard>

          <SectionCard testid="source-settings" title="Source settings">
            <Field inline label="members" info="Which of the family's members this run resolves." labelWidth={120}>
              <Dropdown testid="setting-members" value={draft.settings.members} onChange={v => { setDraft(d => ({ ...d, staleFrom: 'block1', settings: { ...d.settings, members: v } })) }}
                options={block.settings.members.map(o => ({ ...o, label: o.value === 'in-scope' ? `all in scope (${nScope})` : o.label }))} />
            </Field>
            <Field inline label="resolve from" info="Where the samples come from. The original recording is the only source with full resolution." labelWidth={120}>
              <Dropdown testid="setting-resolve" value={draft.settings.resolveFrom} onChange={v => setDraft(d => ({ ...d, staleFrom: 'block1', settings: { ...d.settings, resolveFrom: v } }))} options={block.settings.resolveFrom} />
            </Field>
            <Field inline label="context padding" info="Samples either side of each span, so 01 can walk back to an onset that sits before the span." labelWidth={120}>
              <Dropdown testid="setting-padding" value={draft.settings.padding} onChange={v => setDraft(d => ({ ...d, staleFrom: 'block1', settings: { ...d.settings, padding: v } }))} options={block.settings.padding} />
            </Field>
            <Field inline label="on missing source" info="What happens when a member's recording is not on this installation." labelWidth={120}>
              <Dropdown testid="setting-missing" value={draft.settings.onMissing} onChange={v => setDraft(d => ({ ...d, staleFrom: 'block1', settings: { ...d.settings, onMissing: v } }))} options={block.settings.onMissing} />
            </Field>
            <div className="ig-foot" style={{ marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
              <Icon name="link" size={12} />members keep identity by file · channel · sample range
              <InfoTip title="Identity across the hand-off">Members are matched by content (file, channel, sample range), not by row id, so measurements write back per member and re-running the recipe is idempotent (§6.2).</InfoTip>
            </div>
          </SectionCard>

          <SectionCard testid="provenance-card" title="Where this family came from"
            actions={<Button variant="link" icon="external" onClick={() => navigate(`library/family?family=${fam.id}`)} testid="open-in-library">Open in Library →</Button>}>
            <div className="ig-prov">
              <div><Icon name="branch" size={13} />promoted from {fam.promotedFrom} · {fam.promotedOn}</div>
              {fam.exemplar && <div><Icon name="flag" size={13} />seeded by exemplar {fam.exemplar}</div>}
              <div><Icon name="link" size={13} />edges: scale-invariant distance · threshold {fam.threshold.toFixed(2)}</div>
              <div><Icon name="terminal" size={13} />recipe {fam.recipe} · clustering {block.clustering.version}</div>
              <div><Icon name="info" size={13} />exclusions scope this run only · Library unchanged</div>
            </div>
          </SectionCard>

          {staleFrom && (
            <Callout tone="amber" icon="alert-triangle" testid="stale-callout"
              action={<Button size="sm" variant="primary" icon="refresh" onClick={runChain} disabled={!!runReason} disabledReason={runReason}>Re-run from 01</Button>}>
              the source changed · 01 and 02 show the last run until you re-run
            </Callout>
          )}
          {fam.disabledReason && <Callout tone="amber" icon="alert-circle" testid="family-blocked">{fam.disabledReason}</Callout>}
          {fam.adjudicated === 0 && <Callout tone="amber" icon="alert-circle" testid="none-adjudicated">no member of {fam.id} has a human verdict yet · every number below is machine-only <Badge tone="blue">machine</Badge></Callout>}
        </div>
      </div>

      <SaveTemplateModal open={saveOpen} onClose={() => setSaveOpen(false)}
        defaultName={upstream === 'spike-shape' ? 'spike_shape_v1' : 'sharkfin_slope_v1'}
        stages={block.chain.map(b => (b.index ? `${String(b.index).padStart(2, '0')} ${b.label}` : b.label))} />
    </>
  )
}
