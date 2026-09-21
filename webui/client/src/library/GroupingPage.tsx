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
import {
  Button, Callout, Checkbox, Icon, InfoTip, Modal, NumberField, ProgressBar, Seg, SelectField, Slider, TextField, fmtInt, useQueryState,
  type IconName,
} from '../kit'
import { useToast } from '../shell/Toast'
import { navigate, useApp } from '../state'
import { useSourced } from '../api/seam'
import { UNIT_LABEL, getGroupingEditor, type BasisKind, type BasisOption, type FeatureBin, type Grouping, type Unit } from '../api/library'
/* The grouping job and the grouping write have no fixture-shaped wrapper in `api/library.ts` (that module is
 * the READ seam), so they are taken from the typed bridge client directly. */
import { ApiError, cancelJob, getJob, runLibraryGrouping, saveLibraryGrouping, subscribeJob, type LibGrouping, type LibGroupingAssignment } from '../api'
import { useExternalNavKey, useAllGroupings, useMotifGroupingId, useSavedGroupings, useSelection, useSequenceGroupingId } from './chrome'
import { AtlasPage } from './AtlasPage'
import { FamilyPage } from './FamilyPage'
import { RecurrencePage } from './RecurrencePage'

/* ================================================================ the draft ================================================================ */
type BinMode = 'quantiles' | 'log' | 'fixed'
interface Draft {
  unit: Unit; basis: BasisKind
  bins: BinMode; nBins: number; range: [number, number] | null; edges: string
  cut: number; nearest: number
  tagMode: 'first' | 'each'; provBy: 'recording' | 'run' | 'spike_train'; clustering: string
  omitSmall: boolean; minMembers: number
}
/** Spec 9.10's two defaults, and the two the core's own methods declare (`ward.DEFAULT_CUT`, `DEFAULT_OMIT_D`). */
const BASE: Omit<Draft, 'unit' | 'basis'> = {
  bins: 'quantiles', nBins: 6, range: null, edges: '',
  cut: 0.42, nearest: 0.5, tagMode: 'first', provBy: 'recording', clustering: '',
  omitSmall: true, minMembers: 10,
}

/** Which registered method serves which basis (`Working/library/grouping/methods/*.applies_to`). */
const METHOD_FOR: Record<BasisKind, string> = {
  'shape-distance': 'ward', 'sequence-similarity': 'ward',
  amplitude: 'feature_bins', timescale: 'feature_bins', 'frequency-content': 'feature_bins', polarity: 'feature_bins',
  tag: 'labels', provenance: 'labels', custom: 'labels',
}
/** The three bin methods, spelled the way `bases.BIN_METHODS` spells them. */
const BIN_METHOD: Record<BinMode, string> = { quantiles: 'quantiles', log: 'log-spaced', fixed: 'fixed edges' }
const DISTANCE_BASES: BasisKind[] = ['shape-distance', 'sequence-similarity']
/** The unit each feature is measured in and the axis it reads best on. Facts of `bases.py`, not measurements:
 *  `frequency_content` returns the Welch dominant frequency in Hz, `amplitude` the peak-to-peak in the
 *  waveform's own mV, `timescale` the duration in seconds. The RANGE is never from here — it is the live
 *  distribution's own extent. */
const FEATURE_AXIS: Partial<Record<BasisKind, { unit: string; label: string; scale: 'log' | 'linear' }>> = {
  'frequency-content': { unit: 'Hz', label: 'dominant frequency · Welch PSD', scale: 'log' },
  amplitude: { unit: 'mV', label: 'peak-to-peak amplitude', scale: 'linear' },
  timescale: { unit: 's', label: 'duration', scale: 'log' },
  polarity: { unit: '', label: 'signed polarity, −1 … +1', scale: 'linear' },
}
const GROUP_ICON: Record<string, IconName> = { distance: 'target', 'feature bins · no distance': 'bar-chart', labels: 'tag' }
/** The engine's five omission reasons, in the words `grouping_assignments.omit_reason` stores. */
const OMIT_REASON_LABEL: Record<string, string> = {
  outside_bins: 'outside every bin', past_cut: 'past the nearest-family distance',
  group_too_small: 'in a group under the minimum', not_in_a_sequence: 'in no sequence', no_label: 'carry no label',
}

/** A distribution's own extent — the only honest source for a feature's range. */
function extentOf(dist: FeatureBin[] | undefined): [number, number] | null {
  if (!dist || !dist.length) return null
  const lo = dist[0].lo, hi = dist[dist.length - 1].hi
  return Number.isFinite(lo) && Number.isFinite(hi) && hi > lo ? [lo, hi] : null
}

export function parseEdges(s: string): { edges: number[]; error: string | null } {
  const parts = s.split(',').map(x => x.trim()).filter(Boolean)
  const nums = parts.map(Number)
  if (parts.some(p => !Number.isFinite(Number(p)))) return { edges: [], error: `not a number: ${parts.find(p => !Number.isFinite(Number(p)))}` }
  if (nums.length < 3) return { edges: nums, error: 'at least 3 edges (2 bins)' }
  for (let i = 1; i < nums.length; i++) if (nums[i] <= nums[i - 1]) return { edges: nums, error: `edges must increase: ${nums[i]} ≤ ${nums[i - 1]} at position ${i + 1}` }
  return { edges: nums, error: null }
}

/** Form validation only — whether the draft is a question the core can be asked. It says nothing about the
 *  answer; the answer comes from the job. */
export function validate(d: Draft, extent: [number, number] | null): { field: string; message: string } | null {
  const feature = !DISTANCE_BASES.includes(d.basis) && METHOD_FOR[d.basis] === 'feature_bins'
  if (feature) {
    if (d.bins === 'fixed') { const e = parseEdges(d.edges).error; if (e) return { field: 'edges', message: e } }
    else {
      if (!Number.isInteger(d.nBins) || d.nBins < 2 || d.nBins > 20) return { field: 'number of bins', message: '2 to 20 bins' }
      const [lo, hi] = d.range ?? extent ?? [0, 0]
      if (!(lo < hi)) return { field: 'range', message: 'the lower edge must be below the upper edge' }
      if (d.bins === 'log' && lo <= 0) return { field: 'range', message: 'log-spaced bins need a range above 0' }
      if (extent && (lo < extent[0] * 0.999 || hi > extent[1] * 1.001)) {
        return { field: 'range', message: `outside the measured range: ${extent[0].toPrecision(3)}–${extent[1].toPrecision(3)}` }
      }
    }
  }
  if (DISTANCE_BASES.includes(d.basis) && !(d.cut > 0)) return { field: 'cut', message: 'the cut must be above 0' }
  if (d.omitSmall && (!Number.isInteger(d.minMembers) || d.minMembers < 1 || d.minMembers > 1000)) return { field: 'minimum members', message: 'whole number from 1 to 1000' }
  return null
}

/** The draft as the engine's `params` dict. Only keys a registered method actually declares are sent — an
 *  invented key would still land in the recipe hash and make two identical groupings look different. */
export function paramsFor(d: Draft, extent: [number, number] | null): Record<string, unknown> {
  const shared: Record<string, unknown> = { min_group: d.minMembers, omit_small: d.omitSmall }
  const method = METHOD_FOR[d.basis]
  if (method === 'ward') return { ...shared, cut: d.cut, omit_d: d.nearest }
  if (method === 'feature_bins') {
    const range = d.bins === 'fixed' ? parseEdges(d.edges).edges : (d.range ?? extent ?? null)
    return { ...shared, feature: d.basis, bin_method: BIN_METHOD[d.bins], count: d.nBins, range }
  }
  return { ...shared, provenance_by: d.provBy, tag_mode: d.tagMode }
}

/* ================================================================ the regroup job ================================================================ */
interface RunRecompute { seconds: number; minutes: number; where: 'local' | 'cluster' }
interface RunHandEdits { total: number; applies: number; orphaned: number; orphan_group_label: string | null; orphan_labels: string[] }
interface RunPreview {
  groups: number; members: number; omitted: number; omittedByReason: Record<string, number>
  recompute: RunRecompute; handEdits: RunHandEdits
}
interface RunResult {
  unit: string; basis: string; method: string; params: Record<string, unknown>; recipeHash: string
  preview: RunPreview; mergeHeights: number[]; assignments: LibGroupingAssignment[]
}
type Phase = 'idle' | 'running' | 'done' | 'failed' | 'cancelled'
interface JobView {
  phase: Phase; jobId: number | null; sig: string
  progress: { done: number; total: number | null; message: string }
  result: RunResult | null; error: string | null; forced?: boolean
}
const IDLE: JobView = { phase: 'idle', jobId: null, sig: '', progress: { done: 0, total: null, message: '' }, result: null, error: null }

const errText = (e: unknown): string => {
  if (e && typeof e === 'object' && 'message' in e && typeof (e as { message: unknown }).message === 'string') return (e as { message: string }).message
  return e ? String(e) : 'the grouping job failed'
}

/** Start a `regroup` job and follow it. The SSE stream is the fast path; a stream error falls back to polling
 *  `GET /api/jobs/{id}`, the same shape `analyse/store.ts` uses, so a dropped socket never leaves the panel
 *  computing forever. */
function useGroupingJob() {
  const [view, setView] = useState<JobView>(IDLE)
  const stream = useRef<{ close: () => void } | null>(null)
  const poll = useRef<number | null>(null)
  const then = useRef<((r: RunResult) => void) | null>(null)
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false; stream.current?.close(); if (poll.current) window.clearInterval(poll.current) }, [])

  const stop = () => { stream.current?.close(); stream.current = null; if (poll.current) { window.clearInterval(poll.current); poll.current = null } }

  const settle = (status: string, result: unknown, error: unknown) => {
    if (!alive.current) return
    stop()
    if (status === 'completed' && result) {
      const r = result as RunResult
      setView(v => ({ ...v, phase: 'done', result: r, error: null }))
      const after = then.current; then.current = null
      if (after) after(r)
      return
    }
    then.current = null
    if (status === 'cancelled') { setView(v => ({ ...v, phase: 'cancelled', error: null })); return }
    setView(v => ({ ...v, phase: 'failed', error: errText(error) || 'the grouping job produced no result' }))
  }

  const watch = (jobId: number) => {
    stream.current = subscribeJob(jobId, raw => {
      if (!alive.current) return
      // `subscribeJob` also relays the generic-job frames (`job_start`, `progress`, `job_end`), which the
      // chain-run `RunEvent` union does not name
      const e = raw as unknown as { event: string; done?: number; total?: number | null; message?: string; status?: string; result?: unknown; error?: unknown }
      if (e.event === 'progress') {
        setView(v => (v.jobId === jobId ? { ...v, progress: { done: Number(e.done ?? 0), total: e.total ?? null, message: String(e.message ?? '') } } : v))
      } else if (e.event === 'job_end') {
        settle(String(e.status ?? 'failed'), e.result, e.error)
      }
    }, () => {
      // the stream dropped: keep the job, watch it by polling instead
      stream.current?.close(); stream.current = null
      if (poll.current || !alive.current) return
      poll.current = window.setInterval(() => {
        getJob(jobId).then(row => {
          if (row.status === 'running' || row.status === 'queued') {
            const p = row.progress as { done?: number; total?: number | null; message?: string } | undefined
            setView(v => (v.jobId === jobId ? { ...v, progress: { done: Number(p?.done ?? 0), total: p?.total ?? null, message: String(p?.message ?? 'running') } } : v))
            return
          }
          settle(row.status, row.result, row.error)
        }).catch(err => settle('failed', null, err))
      }, 2000)
    })
  }

  const start = (sig: string, body: { unit: string; basis: string; method: string; params: Record<string, unknown> }, after?: (r: RunResult) => void) => {
    stop()
    then.current = after ?? null
    setView({ ...IDLE, phase: 'running', sig, progress: { done: 0, total: 4, message: 'starting' } })
    runLibraryGrouping(body).then(j => {
      if (!alive.current) return
      setView(v => ({ ...v, jobId: j.job_id }))
      watch(j.job_id)
    }).catch(err => { then.current = null; if (alive.current) setView(v => ({ ...v, phase: 'failed', error: err instanceof ApiError ? err.message : String(err) })) })
  }

  const cancel = () => {
    const id = view.jobId
    then.current = null
    stop()
    setView(v => ({ ...v, phase: 'cancelled' }))
    if (id != null) void cancelJob(id).catch(() => undefined)
  }
  const reset = () => { then.current = null; stop(); setView(IDLE) }
  /** the two `?state=` deep links: a display state for the screenshot pass, never a result */
  const force = (v: Partial<JobView>) => setView(x => ({ ...x, ...v, forced: true }))
  return { view, start, cancel, reset, force }
}

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
  const startUnit: Unit = unitQ === 'sequences' || unitQ === 'spike-trains' ? unitQ : 'motifs'
  const initialBasis: BasisKind = (basisQ as BasisKind) || (startUnit === 'sequences' ? 'sequence-similarity' : startUnit === 'spike-trains' ? 'amplitude' : 'shape-distance')
  const [d, setD] = useState<Draft>(() => ({ ...BASE, unit: startUnit, basis: initialBasis, cut: initialBasis === 'sequence-similarity' ? 0.5 : 0.42 }))

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
  const extent = useMemo(() => extentOf(dist), [dist])
  const invalid = validate(d, extent)

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

  const sig = JSON.stringify({ unit: d.unit, basis: d.basis, params: paramsFor(d, extent) })
  const pv = job.view.result && job.view.sig === sig ? job.view.result.preview : null
  const stale = !!job.view.result && job.view.sig !== sig
  const overLimit = pv?.recompute.where === 'cluster'
  const busy = job.view.phase === 'running' || writing
  const failed = job.view.phase === 'failed'
  const current = all.find(g => g.id === (d.unit === 'sequences' ? seqGid : motifGid))
  // the core's own identity for "this is the grouping you already have" — the recipe hash, not a comparison
  // against the literal settings of `g-07`
  const currentHash = (current as (Grouping & { recipeHash?: string | null }) | undefined)?.recipeHash ?? null
  const unchanged = !!pv && !!currentHash && currentHash === job.view.result?.recipeHash

  const close = () => { if (job.view.phase === 'running') job.cancel(); job.reset(); navigate(`library/${from}`) }

  // ?state=running | failed — display deep links for the screenshot pass. They carry no numbers.
  useEffect(() => {
    if (stateQ === 'running') job.force({ phase: 'running', jobId: null, sig, progress: { done: 2, total: 4, message: 'grouping' }, result: null, error: null })
    if (stateQ === 'failed') job.force({ phase: 'failed', jobId: null, result: null, error: 'the regroup job failed · nothing was written' })
  }, [stateQ]) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (patch: Partial<Draft>) => { setD(x => ({ ...x, ...patch })); setWriteError(null); setSavedId(null) }
  const pickUnit = (u: Unit) => {
    const ok = (b: BasisOption) => b.units.includes(u)
    const cur = editor.data?.bases.find(b => b.kind === d.basis)
    const nextBasis = cur && ok(cur) ? d.basis : (editor.data?.bases.find(ok)?.kind ?? d.basis)
    set({ unit: u, basis: nextBasis as BasisKind, range: null })
    setUnitQ(u === 'motifs' ? null : u)
    if (nextBasis !== d.basis) setBasisQ(nextBasis)
  }
  const pickBasis = (b: BasisKind) => {
    set({ basis: b, range: null, cut: b === 'sequence-similarity' ? 0.5 : b === 'shape-distance' ? 0.42 : d.cut })
    setBasisQ(b)
  }

  const runPreview = (after?: (r: RunResult) => void) => {
    setWriteError(null); setSavedId(null)
    job.start(sig, { unit: d.unit, basis: d.basis, method: METHOD_FOR[d.basis], params: paramsFor(d, extent) }, after)
  }

  /** Write the grouping the job computed. The server assigns the id, the family counts and the `computed`
   *  stamp; nothing about the saved row is decided here. */
  const write = async (r: RunResult): Promise<LibGrouping | null> => {
    setWriting(true); setWriteError(null)
    try {
      const saved = await saveLibraryGrouping({
        unit: r.unit, basis: r.basis, method: r.method, params: r.params,
        cut: typeof r.params.cut === 'number' ? (r.params.cut as number) : null,
        assignments: r.assignments,
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
      navigate(g.unit === 'sequences' ? 'library/atlas?unit=sequences' : 'library/atlas')
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
        ? <><Button onClick={() => { job.reset(); setStateQ(null) }}>Back to settings</Button><Button variant="primary" icon="refresh" testid="regroup-retry" onClick={() => { setStateQ(null); job.reset(); runPreview() }}>Retry</Button></>
        : <Button testid="regroup-cancel" disabled={writing} disabledReason="the grouping is being written" onClick={() => { job.cancel(); setStateQ(null); push({ text: 'Regroup cancelled · nothing was written' }) }}>Cancel job</Button>}
    </div>
  ) : (
    <>
      <Button icon="save" testid="save-grouping" disabled={!!saveReason} disabledReason={saveReason ?? undefined} onClick={onSave}>{pv ? 'Save as a grouping' : 'Compute and save'}</Button>
      {overLimit
        ? <Button variant="cluster" icon="server" testid="apply-grouping" disabled={!!applyReason} disabledReason={applyReason ?? undefined} onClick={onApply}>Create SLURM script</Button>
        : <Button variant="primary" icon="check" testid="apply-grouping" disabled={!!applyReason} disabledReason={applyReason ?? undefined} onClick={onApply}>{pv ? 'Apply grouping' : 'Compute and apply'}</Button>}
    </>
  )

  const groupsOfBases = ['distance', 'feature bins · no distance', 'labels'] as const
  return (
    <Modal open onClose={close} width={810} testid="edit-grouping-modal" closeOnBackdrop={!busy}
      title={<span className="row" style={{ gap: 8 }}><Icon name="sliders" size={16} />Edit grouping</span>}
      subtitle={current ? `from ${current.id} · ${current.basisLabel.split(' · ')[0]}` : 'no grouping of this unit yet'}
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
          <Params d={d} set={set} basis={d.basis} dist={dist} extent={extent} clusterings={editor.data.clusterings} invalid={invalid} />
        </section>

        <section className="lib-ge-sec" data-testid="ge-misfits">
          <h4>4&nbsp; What does not fit</h4>
          <div className="row" style={{ gap: 22, flexWrap: 'wrap' }}>
            <span className="row" style={{ gap: 6 }} data-testid="omit-outside">
              <Icon name="flag" size={12} style={{ color: '#c27400' }} />
              <span className="mono small">
                {DISTANCE_BASES.includes(d.basis) ? 'members past the nearest-family distance' : METHOD_FOR[d.basis] === 'labels' ? 'members carrying no label' : 'members outside every bin'} are omitted and flagged
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
              <Button size="sm" icon="play" testid="compute-preview" disabled={busy} disabledReason="already running" onClick={() => runPreview()}>Compute preview</Button>
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

          <span className="mono small muted"><Icon name="info" size={11} style={{ verticalAlign: -1 }} /> applying regroups the whole catalogue and clears the current scope{current ? `; ${current.id} stays saved` : ''}</span>
          {overLimit && <span className="mono small" style={{ color: '#c27400' }}><Icon name="hourglass" size={11} style={{ verticalAlign: -1 }} /> over the core's local limit — the regroup is exported as a cluster job</span>}
          {savedId && <span className="mono small" style={{ color: 'var(--green)' }} data-testid="grouping-saved"><Icon name="check" size={11} style={{ verticalAlign: -1 }} /> saved as {savedId}</span>}
          {job.view.phase === 'cancelled' && <span className="mono small muted" data-testid="regroup-cancelled">cancelled · nothing was written</span>}
        </div>

        {failed && <Callout tone="red" title="Regroup failed · nothing was written" testid="regroup-failed">{job.view.error}</Callout>}
        {writeError && <Callout tone="red" title="Could not write the grouping" testid="grouping-write-failed">{writeError}</Callout>}
      </>}
    </Modal>
  )
}

/** The core's own recompute estimate (`engine._recompute_cost`), rendered. Nothing is recomputed here. */
function recomputeLabel(r: RunRecompute): string {
  const text = r.seconds < 90 ? `~${Math.max(1, Math.round(r.seconds))} s` : `~${r.minutes.toFixed(r.minutes < 10 ? 1 : 0)} min`
  return `${text}, ${r.where}`
}

/* ================================================================ parameters ================================================================ */
function Params({ d, set, basis, dist, extent, clusterings, invalid }: {
  d: Draft; set: (p: Partial<Draft>) => void; basis: BasisKind; dist?: FeatureBin[]; extent: [number, number] | null
  clusterings: { value: string; label: string; scope: string }[]; invalid: { field: string; message: string } | null
}) {
  const axis = FEATURE_AXIS[basis]
  const err = (field: string) => invalid?.field === field ? <span className="k-field-error" role="alert" data-testid="param-error"><Icon name="alert-circle" size={11} />{invalid.message}</span> : null

  if (METHOD_FOR[basis] === 'feature_bins') {
    const [lo, hi] = d.range ?? extent ?? [0, 1]
    const edges = d.bins === 'fixed' ? parseEdges(d.edges).edges
      : d.bins === 'log' && lo > 0 ? Array.from({ length: d.nBins + 1 }, (_, i) => lo * Math.pow(hi / lo, i / d.nBins))
        : dist && dist.length ? quantileEdges(dist, d.nBins) : []
    return (
      <div className="lib-params">
        <div className="stack" style={{ gap: 6 }}>
          <span className="lib-cap" style={{ fontSize: 11 }}>feature</span>
          {/* one basis, one measurement: `bases.py` computes exactly one number per feature basis, so there is
              no feature to choose and the old two-option select was a choice that did not exist */}
          <div className="mono small">{axis?.label ?? basis}{axis?.unit ? ` · ${axis.unit}` : ''}</div>
          <div className="lib-param-row"><span>bins</span><Seg size="sm" ariaLabel="bins" testid="param-bins" value={d.bins} onChange={v => set({ bins: v })} options={[{ value: 'quantiles', label: 'quantiles' }, { value: 'log', label: 'log-spaced' }, { value: 'fixed', label: 'fixed edges' }]} /></div>
          {d.bins !== 'fixed' && <div className="lib-param-row"><span>number of bins</span><NumberField size="sm" width={64} value={d.nBins} integer min={2} max={20} showError={false} testid="param-nbins" ariaLabel="number of bins" onValid={n => set({ nBins: n })} onChange={(raw, reason) => { if (reason) set({ nBins: Number(raw) || 0 }) }} /></div>}
          {err('number of bins')}
          {d.bins !== 'fixed' && <div className="lib-param-row"><span>range</span><span className="row" style={{ gap: 4 }}>
            <NumberField size="sm" width={78} value={lo} showError={false} testid="param-lo" ariaLabel="range lower" onValid={n => set({ range: [n, hi] })} />–
            <NumberField size="sm" width={78} value={hi} unit={axis?.unit} showError={false} testid="param-hi" ariaLabel="range upper" onValid={n => set({ range: [lo, n] })} />
          </span></div>}
          {err('range')}
          {d.bins === 'fixed' && <><div className="lib-param-row"><span>edges</span><TextField size="sm" value={d.edges} onChange={v => set({ edges: v })} invalid={invalid?.field === 'edges'} testid="param-edges" width={190} suffix={axis?.unit} /></div>{err('edges')}</>}
          {d.bins === 'quantiles' && <span className="lib-cap">edges at the quantiles; every member falls in a bin</span>}
          {extent && <span className="lib-cap">measured range {extent[0].toPrecision(3)} – {extent[1].toPrecision(3)} {axis?.unit}</span>}
        </div>
        {dist && dist.length
          ? <FeatureHistogram bins={dist} edges={invalid ? [] : edges} scale={axis?.scale ?? 'linear'} unit={axis?.unit ?? ''} lo={lo} hi={hi}
            title={`members per ${axis?.label ?? basis} · ${axis?.scale ?? 'linear'} axis · sampled from the catalogue`} />
          : <NoDistribution what={basis} />}
      </div>
    )
  }

  if (DISTANCE_BASES.includes(basis)) {
    return (
      <div className="lib-params">
        <div className="stack" style={{ gap: 6 }}>
          <div className="lib-param-row"><span>linkage</span><SelectField size="sm" value="ward" onChange={() => undefined} options={[{ value: 'ward', label: 'Ward' }]} width={120} /></div>
          <div className="lib-param-row"><span>cut</span><Slider value={d.cut} min={0.1} max={1} step={0.01} onChange={v => set({ cut: +v.toFixed(2) })} format={v => v.toFixed(2)} width={190} testid="param-cut" ariaLabel="cut" /></div>
          <div className="lib-param-row"><span>nearest family past</span><NumberField size="sm" width={64} value={d.nearest} min={0.1} max={1} step={0.01} testid="param-nearest" ariaLabel="nearest family distance" onValid={n => set({ nearest: n })} /></div>
          {err('cut')}
          <span className="lib-cap">how many families the cut gives is measured by the preview, not guessed here</span>
        </div>
        {dist && dist.length
          ? <FeatureHistogram bins={dist} edges={[]} scale="linear" unit="" lo={0} hi={1} cut={d.cut}
            title={basis === 'shape-distance' ? 'Ward merge heights · sampled from the catalogue' : 'pairwise sequence similarity · sampled from the catalogue'} />
          : <NoDistribution what={basis} />}
      </div>
    )
  }

  return (
    <div className="lib-params">
      <div className="stack" style={{ gap: 6 }}>
        {basis === 'tag' && <>
          <div className="lib-param-row"><span>several tags</span><Seg size="sm" value={d.tagMode} onChange={v => set({ tagMode: v })} testid="param-tag-mode" options={[{ value: 'first', label: 'first tag' }, { value: 'each', label: 'one group per tag' }]} /></div>
          <span className="lib-cap">a member with no tag is omitted and flagged; how many that is, is what the preview measures</span>
        </>}
        {basis === 'provenance' && <div className="lib-param-row"><span>by</span><Seg size="sm" value={d.provBy} onChange={v => set({ provBy: v })} testid="param-prov" options={[{ value: 'recording', label: 'recording' }, { value: 'run', label: 'run' }, { value: 'spike_train', label: 'spike train' }]} /></div>}
        {basis === 'custom' && (clusterings.length
          ? <>
            <span className="lib-cap" style={{ fontSize: 11 }}>clustering</span>
            <SelectField value={d.clustering} onChange={v => set({ clustering: v })} options={clusterings.map(c => ({ value: c.value, label: c.label }))} testid="param-clustering" />
            <Callout tone="amber" icon="info">{clusterings.find(c => c.value === d.clustering)?.scope ?? 'registered clustering'}</Callout>
          </>
          : <Callout tone="amber" icon="info" testid="no-clusterings">No clustering is registered. Export one from Analyse and register it before grouping by it.</Callout>)}
      </div>
      <div className="k-card grey" style={{ padding: 10 }} data-testid="param-bars">
        {/* polarity, tag, provenance and custom used to draw invented bar charts here (`vals: [388, 702, 312]`).
            `GET /grouping-editor` returns distributions for five bases and this is not one of them. */}
        <NoDistribution what={basis} />
      </div>
    </div>
  )
}

function NoDistribution({ what }: { what: string }) {
  return <div className="stack" style={{ gap: 4, padding: 6 }}><span className="lib-cap">no distribution for {what}</span><span className="lib-cap" style={{ fontSize: 10 }}>the editor read carries distributions for amplitude, timescale, frequency content and the two distance bases; the group sizes for this basis are what the preview measures</span></div>
}

function quantileEdges(dist: FeatureBin[], n: number): number[] {
  if (!dist.length || n < 1) return []
  const total = dist.reduce((s, b) => s + b.n, 0), out = [dist[0].lo]
  let acc = 0, k = 1
  for (const b of dist) { acc += b.n; while (k < n && total > 0 && acc >= (total * k) / n) { out.push(b.hi); k++ } }
  out.push(dist[dist.length - 1].hi)
  return out
}

/** Distribution with bin edges (or a cut) drawn on it; log or linear x. Bars outside [lo, hi] are amber.
 *  Every bar is a live count from the editor read — nothing here is generated. */
function FeatureHistogram({ bins, edges, scale, unit, lo, hi, cut, title }: { bins: FeatureBin[]; edges: number[]; scale: 'log' | 'linear'; unit: string; lo: number; hi: number; cut?: number; title: string }) {
  const W = 430, H = 112, padL = 8, padR = 8, padT = 22, padB = 18
  if (!bins.length) return <div className="k-card grey" style={{ padding: 10 }}><span className="lib-cap">no distribution</span></div>
  const x0 = bins[0].lo, x1 = bins[bins.length - 1].hi
  const logOk = scale === 'log' && x0 > 0 && x1 > x0
  const tx = (v: number) => padL + (logOk ? (Math.log(Math.max(v, x0)) - Math.log(x0)) / (Math.log(x1) - Math.log(x0)) : (v - x0) / (x1 - x0 || 1)) * (W - padL - padR)
  const max = Math.max(...bins.map(b => b.n), 1)
  const ty = (n: number) => H - padB - (n / max) * (H - padT - padB)
  const ticks = logOk ? [lo, Math.sqrt(Math.max(lo, x0) * hi), hi].map(v => +v.toPrecision(2)) : [x0, (x0 + x1) / 2, x1].map(v => +v.toPrecision(3))
  const outside = (b: FeatureBin) => cut == null && (b.hi > hi * 1.0001 || b.lo < lo * 0.9999)
  return (
    <div className="k-card grey" style={{ padding: '6px 8px' }} data-testid="feature-histogram">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 9 }}>
        <text x={padL} y={11} fill="var(--muted)">{title}</text>
        {bins.map((b, i) => <rect key={i} x={tx(b.lo) + 0.8} width={Math.max(1, tx(b.hi) - tx(b.lo) - 1.6)} y={ty(b.n)} height={H - padB - ty(b.n)} fill={outside(b) ? '#f6c27a' : '#94c2ff'}><title>{`${b.lo.toPrecision(3)}–${b.hi.toPrecision(3)} ${unit} · ${b.n} members`}</title></rect>)}
        <line x1={padL} x2={W - padR} y1={H - padB} y2={H - padB} stroke="var(--border-strong)" />
        {edges.map((e, i) => <line key={i} x1={tx(e)} x2={tx(e)} y1={padT - 4} y2={H - padB} stroke={i === 0 || i === edges.length - 1 ? 'var(--blue)' : '#1f2937'} strokeWidth={1} />)}
        {cut != null && <g><line x1={tx(cut)} x2={tx(cut)} y1={padT - 6} y2={H - padB} stroke="var(--amber)" strokeWidth={1.5} strokeDasharray="4 3" /><text x={tx(cut) + 4} y={padT} fill="#c27400">cut {cut.toFixed(2)}</text></g>}
        {cut == null && bins.some(outside) && <text x={W - padR} y={padT} textAnchor="end" fill="#c27400">outside range</text>}
        {ticks.map((t, i) => <text key={i} x={tx(Math.min(x1, Math.max(x0, t)))} y={H - 5} textAnchor={i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle'} fill="var(--muted)">{t}{i === ticks.length - 1 && unit ? ` ${unit}` : ''}</text>)}
      </svg>
    </div>
  )
}
