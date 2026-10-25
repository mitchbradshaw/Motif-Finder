/* library.grouping — frame library-4: the Edit grouping modal over the (inert) page it was opened from.
 * 1 what to group · 2 group by (9 bases in 3 kinds) · 3 parameters with the feature's distribution ·
 * 4 what does not fit · Preview (groups, members, omitted, recompute, hand edits) · Save / Apply.
 *
 * Wiring notes (stage 3, prompt 03 · P2). This page was the worst offender in the fixture audit and almost
 * none of it survives unchanged:
 *
 *  - `preview(draft, unitCount)` — a hand-written simulation of the regrouping result, full of magic numbers
 *    (`10 * (0.42/cut)^1.3`, `outside = 1211`, `minutes = 46`, `handEditsKept: 14`, `apply: 14 - orphaned`) —
 *    is GONE. The preview is now what the core measured: `POST /api/library/groupings/run` starts a `regroup`
 *    job, the page streams it, and the job's result carries spec §8.2's panel — groups, members, omitted (with
 *    the core's five omission reasons), the recompute cost, and what happens to every hand edit. Nothing is
 *    written by that job; it is a preview in the literal sense.
 *  - Because the numbers are measured rather than guessed, they do not exist until the preview has run. The
 *    panel says so, and Save and Apply are disabled until it has. That is the honest shape of "the core
 *    decides": a page cannot show you the answer before the answer is computed.
 *  - Saving writes the real rows: `POST /api/library/groupings` with the job's own assignments. The server
 *    assigns the id and the `computed` stamp, so `buildGrouping`, `nextGroupingId` and the frozen
 *    `'16 Sep 2026'` are gone with it.
 *  - `FEATURES` — a client-side table of extents, ranges and feature options — is gone. Every range and every
 *    bin edge is now read off the live distribution the bridge returns for that basis
 *    (`GET /grouping-editor`, keyed `frequency-content | amplitude | timescale | shape-distance |
 *    sequence-similarity`). What stays hard-coded is the UNIT of each feature and its axis scale, because
 *    those are facts of `Working/library/grouping/bases.py` (Welch dominant frequency in Hz, peak-to-peak mV,
 *    duration in s), not measurements.
 *  - `unitCount ?? 1402` is gone: the count comes from the editor read, and says `…` until it lands.
 *  - A basis that does not apply to the selected unit is disabled WITH the core's own `reason` (§8.2). The
 *    editor read is re-issued per unit, which is what makes `reason` right.
 *  - `kit/sim.ts`'s `'library.regroup.l-0031'` simulation is gone; `?state=running|failed` remain as pure
 *    display deep links for the screenshot pass and are labelled as such on screen.
 *  - Controls with no parameter behind them were removed rather than left as decoration: sequence
 *    "max gap"/"order" (those belong to sequence extraction, not to Ward), the polarity "biphasic ratio", and
 *    the "omit motifs outside every bin" tick — §8.2 flags what does not fit ALWAYS, so that tick could only
 *    ever have lied. The fabricated bar charts for polarity / tag / provenance / custom went the same way:
 *    the bridge returns no distribution for those bases, so the panel says there is none. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Callout, Checkbox, Icon, InfoTip, Modal, NumberField, ProgressBar, fmtInt, useQueryState, type IconName } from '../kit'
import { useToast } from '../shell/Toast'
import { navigate, useApp } from '../state'
import { useSourced } from '../api/seam'
import { UNIT_LABEL, getGroupingEditor, type BasisKind, type BasisOption, type Grouping, type Unit } from '../api/library'
/* The grouping write has no fixture-shaped wrapper in `api/library.ts` (that module is the READ seam), so it is
 * taken from the typed bridge client directly. */
import { ApiError, saveLibraryGrouping, type LibGrouping, type LibGroupingMethod, type LibGroupingRefusal } from '../api'
/* the five omission reasons live in `chrome` so the drawer and this panel cannot word them differently */
import { NoiseBadge, OMIT_REASON_LABEL, newestGrouping, useExternalNavKey, useAllGroupings, useMotifGroupingId, useSavedGroupings, useSelection, useSequenceGroupingId } from './chrome'
/* tq-grouping (2026-10-25): the draft model, the regroup job, the tree panel and section 3's parameters live in their
 * own modules; this file is the page and the editor that ties them together */
import { BASE, DISTANCE_BASES, METHOD_FOR, SHARED_PARAMS, binExtent, isTreeGrouping, methodOf, paramsFor, seedFromGrouping, validate, type Draft } from './groupingDraft'
import { useGroupingJob, type RunRecompute, type RunResult } from './useGroupingJob'
import { TreePanel, useGroupingTree } from './TreePanel'
import { Params } from './GroupingParams'
import { AtlasPage } from './AtlasPage'
import { FamilyPage } from './FamilyPage'
import { RecurrencePage } from './RecurrencePage'

const GROUP_ICON: Record<string, IconName> = { distance: 'target', 'feature bins · no distance': 'bar-chart', labels: 'tag' }

/* ================================================================ page ================================================================ */
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

function GroupingEditor({ from }: { from: string }) {
  const { all } = useAllGroupings()
  const [motifGid, setMotifGid] = useMotifGroupingId()
  const [seqGid, setSeqGid] = useSequenceGroupingId()
  const [, setSaved] = useSavedGroupings()
  const [, setSel] = useSelection()
  const { push } = useToast()
  const [unitQ, setUnitQ] = useQueryState<string>('unit', 'motifs')
  const [basisQ, setBasisQ] = useQueryState<string>('basis', '')
  const [stateQ, setStateQ] = useQueryState('state', '')
  /* fixup-an: the Ward cut is in the address, so the tree's cut line, the cut field and the URL are one value */
  const [cutQ, setCutQ] = useQueryState<string>('cut', '')
  const urlCut = useRef<number | null>(Number(cutQ) > 0 ? Number(cutQ) : null)
  const startUnit: Unit = unitQ === 'sequences' || unitQ === 'spike-trains' ? unitQ : 'motifs'
  const initialBasis: BasisKind = (basisQ as BasisKind) || (startUnit === 'sequences' ? 'sequence-similarity' : startUnit === 'spike-trains' ? 'amplitude' : 'shape-distance')
  const [d, setD] = useState<Draft>(() => ({ ...BASE, unit: startUnit, basis: initialBasis, cut: urlCut.current ?? (initialBasis === 'sequence-similarity' ? 0.5 : 0.42) }))
  /* fix round: the slider keeps a cut-sized range (0.1-1), growing only to reach a cut set above it (a dragged line,
   * a typed URL) — the tree's full height belongs to the dendrogram, where 0.1-1 was 5 % of the slider */
  const [cutMax, setCutMax] = useState(1)
  useEffect(() => { if (d.cut > cutMax) setCutMax(Math.ceil(d.cut * 10) / 10) }, [d.cut, cutMax])

  // the bases a unit admits depend on the unit, so the editor is re-read when it changes: that is what makes
  // "disabled WITH its reason" (§8.2) the core's answer rather than the page's guess
  const editor = useSourced(() => getGroupingEditor(d.unit), [d.unit])
  const job = useGroupingJob()
  const [writeError, setWriteError] = useState<string | null>(null)
  const [writing, setWriting] = useState(false)
  const [savedId, setSavedId] = useState<string | null>(null)

  const units = editor.data?.units ?? []
  const unitCount = units.find(u => u.unit === d.unit)?.count ?? null
  const basis = editor.data?.bases.find(b => b.kind === d.basis)
  const dist = editor.data?.distributions[d.basis]
  const extent = useMemo(() => binExtent(dist), [dist])
  const invalid = validate(d, extent)
  // w2-f: the registered methods this basis can use (the editor read), and the one the draft runs
  const methods: LibGroupingMethod[] = editor.data?.methods?.[d.basis] ?? []
  const method = methodOf(d)
  const methodSpec = methods.find(m => m.name === method)

  // a feature range starts as the measured extent of that feature, and returns to it when the basis changes
  useEffect(() => {
    if (!extent || d.range) return
    setD(x => (x.range ? x : { ...x, range: extent }))
  }, [extent, d.range])
  // the clustering select starts on whichever clustering the registry actually holds
  useEffect(() => {
    const first = editor.data?.clusterings[0]?.value
    if (first && !d.clustering) setD(x => (x.clustering ? x : { ...x, clustering: first }))
  }, [editor.data, d.clustering])

  const sig = JSON.stringify({ unit: d.unit, basis: d.basis, method, params: paramsFor(d, extent, methodSpec) })
  const pv = job.view.result && job.view.sig === sig ? job.view.result.preview : null
  const stale = !!job.view.result && job.view.sig !== sig
  const overLimit = pv?.recompute.where === 'cluster'
  const busy = job.view.phase === 'running' || writing
  const failed = job.view.phase === 'failed'
  const currentAny = all.find(g => g.id === (d.unit === 'sequences' ? seqGid : motifGid))
  /* night-review: the editor opens on a TREE grouping by default (the researcher, 2026-10-20: the dendrogram "on by
   * default in add new grouping"). The newest grouping is often a feature-bin one (g-09 on the real database), which
   * builds no tree, so the panel was not on the page at all. Unless the address names a non-tree basis, the editor
   * seeds from the current grouping when it is Ward on a distance basis, else from the newest one of this unit that is. */
  const currentOfUnit = currentAny?.unit === d.unit ? currentAny : undefined
  const current: Grouping | undefined = basisQ && !DISTANCE_BASES.includes(basisQ) ? currentAny
    : isTreeGrouping(currentOfUnit) ? currentOfUnit : newestGrouping(all.filter(isTreeGrouping), d.unit) ?? currentOfUnit
  // the core's own identity for "this is the grouping you already have" — the recipe hash, not a comparison
  // against the literal settings of `g-07` — unless this run kept a tree the current grouping lacks (fixup-an:
  // "Build the tree" is exactly that re-run)
  const unchanged = !!pv && !!current?.recipeHash && current.recipeHash === job.view.result?.recipeHash && !(job.view.result?.tree && !current.treeKey)

  /* "from g-02" has to mean g-02's parameters. The draft starts on `BASE` because the groupings read has not
     landed when the modal mounts; the moment the current grouping resolves, the draft is seeded FROM IT —
     unless the person has already touched a control, or the route pinned a basis with `?basis=`. */
  const [seededFrom, setSeededFrom] = useState<string | null>(null)
  const touched = useRef(false)
  useEffect(() => {
    if (!current || current.unit !== d.unit || !editor.data) return
    if (seededFrom === current.id) return
    if (touched.current && seededFrom !== null) return
    setSeededFrom(current.id)
    const seed = seedFromGrouping(current, editor.data.methods)
    // a cut named in the address (a shared link, a reload) wins over the grouping's own, once
    const fromUrl = urlCut.current; urlCut.current = null
    setD(x => ({ ...x, ...seed, ...(fromUrl ? { cut: fromUrl } : {}), basis: basisQ ? x.basis : (seed.basis ?? x.basis), range: null }))
  }, [current, d.unit, basisQ, seededFrom, editor.data])
  // fixup-an: the draft's Ward cut follows into the address — once the draft has been seeded, so the BASE default
  // never lands there and then overrules the grouping's own cut
  const wardDraft = DISTANCE_BASES.includes(d.basis) && method === 'ward'
  useEffect(() => {
    if (!wardDraft || (current && seededFrom === null && !touched.current)) return
    const s = String(d.cut)
    if (s !== cutQ) setCutQ(s)
  }, [d.cut, wardDraft, seededFrom]) // eslint-disable-line react-hooks/exhaustive-deps
  /* the tree panel draws the CURRENT grouping's kept tree, when it is a Ward grouping of this unit and the draft is Ward */
  const treeGid = current && current.unit === d.unit && wardDraft && isTreeGrouping(current) ? current.id : null
  /* ux-1018: the tree the last regroup job built for the current grouping's settings, drawn in the panel before Apply
   * saves it (Build the tree is that job; its result carries the key the server wrote) */
  const built = job.view.result
  const builtKey = built?.tree?.key && current && built.unit === current.unit && built.basis === current.basis && built.method === 'ward' ? built.tree.key : null
  // fix 1 (critic 12): a refusal describes the settings it refused; once they change it is stale, so it goes
  useEffect(() => { if (job.view.refusal && job.view.refusalSig !== sig) job.clearRefusal() }, [sig, job.view.refusal, job.view.refusalSig]) // eslint-disable-line react-hooks/exhaustive-deps

  const tree = useGroupingTree(treeGid, builtKey)
  // leaving unmounts the editor, and unmount aborts the regroup job (useGroupingJob), so a close is only the navigation
  const close = () => navigate(`library/${from}`)

  // ?state=running | failed — display deep links for the screenshot pass. They carry no numbers.
  useEffect(() => {
    if (stateQ === 'running') job.force({ phase: 'running', jobId: null, sig, progress: { done: 2, total: 4, message: 'grouping' }, result: null, error: null })
    if (stateQ === 'failed') job.force({ phase: 'failed', jobId: null, result: null, error: 'the regroup job failed · nothing was written' })
  }, [stateQ]) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (patch: Partial<Draft>) => { touched.current = true; setD(x => ({ ...x, ...patch })); setWriteError(null); setSavedId(null) }
  const pickUnit = (u: Unit) => {
    const ok = (b: BasisOption) => b.units.includes(u)
    const cur = editor.data?.bases.find(b => b.kind === d.basis)
    const nextBasis = cur && ok(cur) ? d.basis : (editor.data?.bases.find(ok)?.kind ?? d.basis)
    // a different unit means a different current grouping: let it seed this draft again
    setSeededFrom(null); touched.current = false
    set({ unit: u, basis: nextBasis as BasisKind, range: null })
    setUnitQ(u === 'motifs' ? null : u)
    if (nextBasis !== d.basis) setBasisQ(nextBasis)
  }
  const pickBasis = (b: BasisKind) => {
    const served = (editor.data?.methods?.[b] ?? []).map(m => m.name)
    const keep = !served.length || served.includes(d.method) ? d.method : 'ward'
    set({ basis: b, range: null, cut: b === 'sequence-similarity' ? 0.5 : b === 'shape-distance' ? 0.42 : d.cut, method: keep })
    setBasisQ(b)
  }

  const runPreview = (after?: (r: RunResult) => void) => {
    setWriteError(null); setSavedId(null)
    job.start(sig, { unit: d.unit, basis: d.basis, method, params: paramsFor(d, extent, methodSpec) }, after)
  }
  /** w2-b: one click on a refusal's cheaper setting — its params become the draft's, and the preview runs on them */
  const runCheaper = (c: LibGroupingRefusal['cheaper'][number]) => {
    const own: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(c.params)) if (!SHARED_PARAMS.has(k) && k !== 'omit_small') own[k] = v
    const minMembers = typeof c.params.min_group === 'number' ? c.params.min_group : d.minMembers
    const next: Draft = method === 'ward'
      ? { ...d, minMembers, cut: typeof c.params.cut === 'number' ? c.params.cut : d.cut, nearest: typeof c.params.omit_d === 'number' ? c.params.omit_d : d.nearest }
      : { ...d, minMembers, mparams: { ...d.mparams, [method]: { ...(d.mparams[method] ?? {}), ...own } } }
    touched.current = true; setD(next); setWriteError(null); setSavedId(null)
    const nsig = JSON.stringify({ unit: next.unit, basis: next.basis, method, params: paramsFor(next, extent, methodSpec) })
    job.start(nsig, { unit: next.unit, basis: next.basis, method, params: paramsFor(next, extent, methodSpec) })
  }

  /* night-review: the tree is ON by default — a grouping with no kept tree has it built the moment the editor opens on
   * it (the same regroup *Build the tree* runs: at the grouping's own settings, nothing saved until Apply), once per
   * editor, only while the draft is untouched and no job has run. Motifs on shape distance only: a sequence-similarity
   * tree build fails in the core ("tree.tree_key and tree.from_fit disagree", job 727 on the sandbox), so sequences
   * keep the button. A refused or failed build shows the button. */
  const [autoBuilt, setAutoBuilt] = useState(false)
  const treeMissing = !!tree.tree && !tree.tree.tree && tree.tree.canBuild
  useEffect(() => {
    if (autoBuilt || !treeMissing || busy) return
    if (!(d.unit === 'motifs' && d.basis === 'shape-distance' && seededFrom === treeGid && !touched.current && !stateQ
      && job.view.phase === 'idle' && !job.view.result && !job.view.refusal)) return
    setAutoBuilt(true)
    runPreview()
  }, [autoBuilt, treeMissing, busy, d.unit, d.basis, seededFrom, treeGid, stateQ, job.view.phase, job.view.result, job.view.refusal]) // eslint-disable-line react-hooks/exhaustive-deps

  /** Write the grouping the job computed. The server assigns the id, the family counts and the `computed`
   *  stamp; nothing about the saved row is decided here. */
  const write = async (r: RunResult): Promise<LibGrouping | null> => {
    setWriting(true); setWriteError(null)
    try {
      const saved = await saveLibraryGrouping({
        unit: r.unit, basis: r.basis, method: r.method, params: r.params,
        cut: typeof r.params.cut === 'number' ? (r.params.cut as number) : null,
        assignments: r.assignments,
        // w2-b: the job's fit summary, unchanged — the saved grouping keeps its null's verdict on every family
        fit_summary: r.fitSummary ?? null,
        // fixup-an: the tree the job kept, by key — the saved grouping references it, so its tree can be drawn
        tree_key: r.tree?.key ?? null,
      })
      setSaved(s => [...s.filter(x => x.id !== saved.id), saved as unknown as Grouping])
      setSavedId(saved.id)
      return saved
    } catch (err) {
      setWriteError(err instanceof ApiError ? err.message : String(err))
      return null
    } finally { setWriting(false) }
  }

  const onSave = () => {
    const r = pv ? job.view.result! : null
    if (r) { void write(r).then(g => { if (g) push({ text: `Saved ${g.id} · ${g.families} families · not applied` }) }); return }
    runPreview(res => { void write(res).then(g => { if (g) push({ text: `Saved ${g.id} · ${g.families} families · not applied` }) }) })
  }

  const applyResult = (r: RunResult) => {
    if (r.preview.recompute.where === 'cluster') {
      push({ text: `not wired yet: export a cluster job for this regroup (${recomputeLabel(r.preview.recompute)})` })
      return
    }
    void write(r).then(g => {
      if (!g) return
      if (g.unit === 'motifs') setMotifGid(g.id)
      if (g.unit === 'sequences') setSeqGid(g.id)
      setSel([])
      push({ text: `Grouping ${g.id} applied · ${g.families} families · ${fmtInt(g.omitted)} omitted · scope cleared${current ? ` · ${current.id} stays saved` : ''}` })
      // the applied grouping is named in the address (fixup-grouping-url), so the atlas that opens is its atlas
      navigate(`library/atlas?${g.unit === 'sequences' ? 'unit=sequences&' : ''}grouping=${encodeURIComponent(g.id)}`)
    })
  }
  const onApply = () => { const r = pv ? job.view.result! : null; if (r) applyResult(r); else runPreview(applyResult) }

  const previewReason = invalid ? `fix ${invalid.field}: ${invalid.message}` : null
  const saveReason = previewReason ?? (busy ? 'the preview is running' : savedId ? `saved as ${savedId}` : null)
  const applyReason = previewReason ?? (busy ? 'the preview is running' : unchanged ? 'this is already the current grouping' : d.unit === 'spike-trains' ? 'no atlas draws spike-train groupings yet (B17) — save it instead' : null)

  const footer = busy || failed ? (
    <div className="row" style={{ gap: 10, width: '100%' }} data-testid="regroup-progress">
      {failed ? <span className="mono small" style={{ color: 'var(--red)' }}>{job.view.jobId != null ? `job ${job.view.jobId} failed` : 'the regroup failed'}</span>
        : <>
          <span className="mono small muted">{writing ? 'writing the grouping' : `job ${job.view.jobId ?? '…'} · ${job.view.progress.message || 'running'}`}</span>
          <ProgressBar value={job.view.progress.total ? Math.min(1, job.view.progress.done / job.view.progress.total) : 0} width={260} />
        </>}
      <span style={{ marginLeft: 'auto' }} />
      {failed
        ? <><Button variant="primary" onClick={() => { job.reset(); setStateQ(null) }}>Back to settings</Button><Button variant="primary" icon="refresh" testid="regroup-retry" onClick={() => { setStateQ(null); job.reset(); runPreview() }}>Retry</Button></>
        : <Button variant="danger" testid="regroup-cancel" disabled={writing} disabledReason="the grouping is being written" onClick={() => { job.cancel(); setStateQ(null); push({ text: 'Regroup cancelled · nothing was written' }) }}>Cancel job</Button>}
    </div>
  ) : (
    <>
      <Button variant="primary" icon="save" testid="save-grouping" disabled={!!saveReason} disabledReason={saveReason ?? undefined} onClick={onSave}>{pv ? 'Save as a grouping' : 'Compute and save'}</Button>
      {overLimit
        ? <Button variant="cluster" icon="server" testid="apply-grouping" disabled={!!applyReason} disabledReason={applyReason ?? undefined} onClick={onApply}>Create SLURM script</Button>
        : <Button variant="primary" icon="check" testid="apply-grouping" disabled={!!applyReason} disabledReason={applyReason ?? undefined} onClick={onApply}>{pv ? 'Apply grouping' : 'Compute and apply'}</Button>}
    </>
  )

  const groupsOfBases = ['distance', 'feature bins · no distance', 'labels'] as const
  return (
    <Modal open onClose={close} width={810} testid="edit-grouping-modal" closeOnBackdrop={!busy}
      title={<span className="row" style={{ gap: 8 }}><Icon name="sliders" size={16} />Edit grouping</span>}
      subtitle={current ? `${seededFrom === current.id ? 'from' : 'seeding from'} ${current.id} · ${current.basisLabel.split(' · ')[0]} · ${current.params}` : 'no grouping of this unit yet — starting from the defaults'}
      footerNote={busy || failed ? undefined : <Button testid="grouping-cancel" onClick={close}>Cancel</Button>} footer={footer} bodyStyle={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {editor.error && <Callout tone="red" title="Could not read the grouping options">{editor.error.message}</Callout>}
      {editor.loading && <div className="skeleton" style={{ height: 420 }} />}
      {editor.data && basis && <>
        {treeGid && (
          <TreePanel gid={treeGid} read={tree} cut={d.cut} minGroup={d.minMembers} omitSmall={d.omitSmall} nearest={d.nearest}
            onCut={c => set({ cut: c })} busy={busy} building={autoBuilt && busy} onBuild={() => runPreview()} builtKey={builtKey} />
        )}
        <section className="lib-ge-sec" data-testid="ge-unit">
          <h4>1&nbsp; What to group</h4>
          <div className="lib-units" role="radiogroup" aria-label="what to group">
            {units.map(u => (
              <button key={u.unit} type="button" role="radio" aria-checked={d.unit === u.unit} className="lib-unit" data-testid={`unit-${u.unit}`} disabled={busy} onClick={() => pickUnit(u.unit)}>
                <span className="lib-radio" /><span className="stack" style={{ gap: 1 }}><span className="t">{UNIT_LABEL[u.unit]}</span><span className="c">{u.caption}</span></span>
                <span className="n">{fmtInt(u.count)}</span>
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
                  return (
                    <button key={b.kind} type="button" role="radio" aria-checked={d.basis === b.kind} className="lib-basis" data-testid={`basis-${b.kind}`}
                      disabled={dis || busy} title={dis ? (b.reason ?? `does not apply to ${UNIT_LABEL[d.unit]}`) : undefined} onClick={() => pickBasis(b.kind as BasisKind)}>
                      <span className="lib-radio" />
                      <span><span className="t">{b.title}</span><span className="c">{dis ? `⊘ ${b.reason ?? `does not apply to ${UNIT_LABEL[d.unit]}`}` : b.caption}</span></span>
                    </button>
                  )
                })}
              </div>
            ))}
          </div>
        </section>

        <section className="lib-ge-sec" data-testid="ge-params">
          <h4>3&nbsp; {basis.title[0].toUpperCase() + basis.title.slice(1)}</h4>
          <Params d={d} set={set} basis={d.basis} dist={dist} extent={extent} clusterings={editor.data.clusterings} invalid={invalid} methods={methods}
            cutMax={cutMax} />
        </section>

        <section className="lib-ge-sec" data-testid="ge-misfits">
          <h4>4&nbsp; What does not fit</h4>
          <div className="row" style={{ gap: 22, flexWrap: 'wrap' }}>
            <span className="row" style={{ gap: 6 }} data-testid="omit-outside">
              <Icon name="flag" size={12} style={{ color: '#c27400' }} />
              <span className="mono small">
                {method === 'hdbscan' ? `members ${OMIT_REASON_LABEL.not_in_a_dense_family}` : method === 'kshape' ? 'members further from their family’s centre than noise of the same colour sits (or past a fixed omit_d)' : DISTANCE_BASES.includes(d.basis) ? 'members past the nearest-family distance' : METHOD_FOR[d.basis] === 'labels' ? 'members carrying no label' : 'members outside every bin'} are omitted and flagged
                <InfoTip title="always flagged, never dropped">§8.2: what does not fit is flagged and listed, never deleted — so this is not a switch</InfoTip>
              </span>
            </span>
            <span className="row" style={{ gap: 6 }}>
              <Checkbox checked={d.omitSmall} onChange={v => set({ omitSmall: v })} testid="omit-small" label={<>omit and flag groups under</>} />
              <NumberField size="sm" width={58} value={d.minMembers} integer min={1} max={1000} showError={false} ariaLabel="minimum members" testid="min-members" onValid={n => set({ minMembers: n })} onChange={(raw, reason) => { if (reason) set({ minMembers: Number(raw) || -1 }) }} disabled={!d.omitSmall} disabledReason="tick the box to set a minimum size" />
              <span className="mono small">members</span>
            </span>
            {pv && <span className="mono small" style={{ color: '#c27400' }} data-testid="omit-breakdown">
              {Object.entries(pv.omittedByReason).length
                ? Object.entries(pv.omittedByReason).map(([k, n]) => `${fmtInt(n)} ${OMIT_REASON_LABEL[k] ?? k}`).join(' · ')
                : 'nothing was omitted'}
            </span>}
          </div>
        </section>

        <div className="lib-preview" data-testid="grouping-preview">
          <div className="nums">
            <b style={{ marginLeft: 0, fontSize: 13 }}>Preview</b>
            <span>groups<b data-testid="preview-groups">{pv ? fmtInt(pv.groups) : '—'}</b></span>
            <span>members<b>{pv ? fmtInt(pv.members) : '—'}</b></span>
            <span>omitted · flagged<b style={{ color: '#c27400' }} data-testid="preview-omitted">{pv ? fmtInt(pv.omitted) : '—'}</b></span>
            <span>recompute<b style={{ color: overLimit ? '#c27400' : undefined }}>{pv ? recomputeLabel(pv.recompute) : '—'}</b></span>
          </div>

          {invalid && <span className="mono small" style={{ color: 'var(--red)' }} data-testid="preview-invalid"><Icon name="alert-circle" size={11} style={{ verticalAlign: -1 }} /> {invalid.field}: {invalid.message}</span>}

          {!invalid && !pv && (
            <span className="row mono small muted" style={{ gap: 8 }} data-testid="preview-uncomputed">
              <Icon name="info" size={11} style={{ verticalAlign: -1 }} />
              {stale ? 'the settings changed since the last preview' : 'the preview is measured, not estimated'} — {unitCount == null ? 'the catalogue' : `${fmtInt(unitCount)} ${UNIT_LABEL[d.unit]}`} are grouped without writing anything
              <Button variant="primary" size="sm" icon="play" testid="compute-preview" disabled={busy} disabledReason="already running" onClick={() => runPreview()}>Compute preview</Button>
            </span>
          )}

          {pv && job.view.result?.families && job.view.result.families.length > 0 && (
            <span className="row mono small" style={{ gap: 6, flexWrap: 'wrap' }} data-testid="preview-families">
              {job.view.result.families.map(f => (
                <span key={f.label} className="row" style={{ gap: 3 }} data-testid={`preview-family-${f.label}`}>{f.label} · {fmtInt(f.size)}<NoiseBadge flags={f.flags} testid={`noise-badge-${f.label}`} /></span>
              ))}
            </span>
          )}

          {pv && (
            <span className="mono small" style={{ color: 'var(--k-purple-text, #6b3fd4)' }} data-testid="preview-hand-edits">
              <Icon name="user" size={11} style={{ verticalAlign: -1 }} /> {fmtInt(pv.handEdits.total)} hand edit{pv.handEdits.total === 1 ? '' : 's'}: {fmtInt(pv.handEdits.applies)} apply
              {pv.handEdits.orphaned ? ` · ${fmtInt(pv.handEdits.orphaned)} point at families this grouping lacks → kept as the hand group “${pv.handEdits.orphan_group_label ?? 'additions'}”` : ''}
              {pv.handEdits.orphaned > 0 && pv.handEdits.orphan_labels.length > 0 &&
                <InfoTip title="kept as a hand group">{pv.handEdits.orphan_labels.slice(0, 8).join(', ')} — this grouping has no such family, so those members stay together (§8.3)</InfoTip>}
            </span>
          )}

          {/* polish: what Apply does is a consequence to know, not a call to act — ⓘ, text-2 (not an amber ⚠) */}
          <span className="mono small" style={{ color: 'var(--text-2)' }} data-testid="apply-clears-scope"><Icon name="info" size={11} style={{ verticalAlign: -1 }} /> applying regroups the whole catalogue and clears the current scope{current ? `; ${current.id} stays saved` : ''}</span>
          {overLimit && <span className="mono small" style={{ color: '#c27400' }}><Icon name="hourglass" size={11} style={{ verticalAlign: -1 }} /> over the core's local limit — the regroup is exported as a cluster job</span>}
          {pv && job.view.result?.treeNote && <span className="mono small muted" data-testid="preview-tree-note"><Icon name="info" size={11} style={{ verticalAlign: -1 }} /> the tree: {job.view.result.treeNote}</span>}
          {savedId && <span className="mono small" style={{ color: 'var(--green)' }} data-testid="grouping-saved"><Icon name="check" size={11} style={{ verticalAlign: -1 }} /> saved as {savedId}</span>}
          {job.view.phase === 'cancelled' && <span className="mono small muted" data-testid="regroup-cancelled">cancelled · nothing was written</span>}
        </div>

        {failed && <Callout tone="red" title="Regroup failed · nothing was written" testid="regroup-failed">{job.view.error}</Callout>}
        {job.view.refusal && job.view.phase !== 'running' && (
          <Callout tone="amber" title={`Not run · about ${fmtSeconds(job.view.refusal.estimateSeconds)} here, over the ${fmtSeconds(job.view.refusal.localLimitSeconds)} limit`} testid="regroup-refused">
            <div className="mono small">{job.view.refusal.message}</div>
            {job.view.refusal.cheaper.length
              ? <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginTop: 6 }}>{job.view.refusal.cheaper.map((c, i) => (
                <Button variant="primary" key={i} size="sm" icon="play" testid={`cheaper-${i}`} disabled={busy} disabledReason="already running" onClick={() => runCheaper(c)}>{c.change} · ~{fmtSeconds(c.seconds)}</Button>
              ))}</div>
              : <div className="mono small muted">the method names no cheaper setting that fits; reduce the members grouped</div>}
          </Callout>
        )}
        {writeError && <Callout tone="red" title="Could not write the grouping" testid="grouping-write-failed">{writeError}</Callout>}
      </>}
    </Modal>
  )
}

const fmtSeconds = (s: number): string => (s < 90 ? `${Math.max(1, Math.round(s))} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${(s / 3600).toFixed(1)} h`)

/** The core's own recompute estimate (`engine._recompute_cost`), rendered. Nothing is recomputed here. */
function recomputeLabel(r: RunRecompute): string {
  const text = r.seconds < 90 ? `~${Math.max(1, Math.round(r.seconds))} s` : `~${r.minutes.toFixed(r.minutes < 10 ? 1 : 0)} min`
  return `${text}, ${r.where}`
}
