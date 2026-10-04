/* fixup-W: cross-channel classification on the Family page, and the recurrence counts with the bins taken out.
 *
 * In plain words: the same event can show up on several electrodes. Seen at the same instant on two of them it is
 * contamination (one wire picking up another), not two events; seen a little later on the next one it is the event
 * travelling through the mycelium; otherwise the shape is recurring independently. The researcher decided the rule
 * (QUESTIONS.md Q40, Round 10 Q-W5); it is three numbers in Settings › Analysis defaults, and every count below prints
 * the rule that produced it behind its info icon.
 *
 *  - `CrossChannelCard`: *Classify across channels* — a `cross_channel` job with per-channel progress — and what it
 *    stored: pairs of members per bin, co-occurrences on a sibling channel with no member there (Q40c: counted, never
 *    an edge), the three recurrence counts, and the surrogate count from the run that produced the members (or why
 *    there is none). Nothing here re-bins or re-counts: the numbers are the core's (`matching.family_recurrence`).
 *  - `useCrossChannelJob`: start the job and follow it by polling the same row the Jobs workspace reads. */
import { useEffect, useRef, useState } from 'react'
import { Badge, Button, InfoTip, ProgressBar } from '../kit'
import { navigate } from '../state'
import { useToast } from '../shell/Toast'
import { useLibraryView } from './chrome'
import { classifyFamilyCrossChannel, getJob, sendSuspectedArtifacts, type JobRow, type LibClassifyResult, type LibCrossChannel, type LibFlagLine, type RecurrenceMode, type XBinCore, type XRule } from '../api'

export const XBINS: XBinCore[] = ['artifact', 'propagation', 'independent_recurrence']
/* fixup-AD: the bin is still spelled `artifact` on the edge; it means SUSPECTED — the machine flags, a human confirms */
export const XBIN_LABEL: Record<XBinCore, string> = { artifact: 'suspected artifact', propagation: 'propagation', independent_recurrence: 'independent' }
export const XBIN_TONE: Record<XBinCore, 'red' | 'amber' | 'green'> = { artifact: 'red', propagation: 'amber', independent_recurrence: 'green' }
export const MODE_LABEL: Record<RecurrenceMode, string> = { all: 'every member', excluding_artifacts: 'excluding artifacts', propagation_once: 'propagation counted once' }
/** What the core says, for a page that has no read carrying the words yet (`matching.RECURRENCE_RULES`). */
export const MODE_RULE_FALLBACK: Record<RecurrenceMode, string> = {
  all: 'every member of the family, each counted once — nothing taken out',
  excluding_artifacts: 'members a human marked artifact in Review are not counted, nor the other member of a member–member artifact pair a human confirmed. A machine flag alone takes nothing out: flagged members stay counted, drawn red, until a human decides',
  propagation_once: 'human-confirmed artifacts taken out as above, then members joined by propagation that beat its chance test count once — one travelling event — on the member with the earliest onset',
}

const ruleWords = (r: XRule) => `artifact |lag| ≤ ${r.artifact_max_lag_s} s${r.artifact_min_abs_r != null ? ` & |r| ≥ ${r.artifact_min_abs_r}` : ''} · propagation ≤ ${r.propagation_max_lag_s} s & |r| ≥ ${r.min_abs_r}${r.null_k != null ? ` · beats chance (${r.null_percentile}th pct of ${r.null_k} random times) · noise floor · min ${r.min_samples} samples` : ' (before the chance test)'}`

/** fixup-AD: *Send suspected artifacts to Review* — the family's queue, made once; then *Open in Review*. */
function SendToReview({ familyId, grouping, flagged, queue }: { familyId: string; grouping?: string; flagged: number; queue: LibCrossChannel['suspectedQueue'] }) {
  const toast = useToast()
  const [view] = useLibraryView()      // the page's view: the queue is over the members it shows
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  if (queue) {
    return <Button size="sm" icon="external" testid="open-suspected-queue" data-queue={queue.id} onClick={() => navigate(`review/queue/${queue.id}`)}>
      Open in Review · {queue.judged} of {queue.total} judged</Button>
  }
  return (
    <span className="row" style={{ gap: 6 }}>
      <Button size="sm" icon="flag" testid="send-suspected-artifacts" disabled={busy || flagged === 0}
        disabledReason={flagged === 0 ? 'no member is flagged as a suspected artifact' : 'sending'}
        onClick={async () => {
          setBusy(true); setErr(null)
          try {
            const r = await sendSuspectedArtifacts(familyId, grouping, view)
            toast.push({ text: `${r.name}: ${r.total} flagged member${r.total === 1 ? '' : 's'} to judge`, action: { label: 'Open Review', onClick: () => navigate(`review/queue/${r.queueId}`) } })
            navigate(`review/queue/${r.queueId}`)
          } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
        }}>Send {flagged} suspected artifact{flagged === 1 ? '' : 's'} to Review</Button>
      {err && <span className="lib-cap" style={{ color: 'var(--red)' }} data-testid="send-suspected-error">{err}</span>}
    </span>
  )
}

/** fixup-AD: the line beside *excluding artifacts* — the machine flags, a human decides. */
export function FlagLine({ f, testid = 'xc-flag-line' }: { f: Partial<LibFlagLine>; testid?: string }) {
  if (f.flagged == null) return null
  return (
    <span className="row lib-cap" style={{ gap: 4, alignItems: 'center' }} data-testid={testid}
      data-flagged={f.flagged} data-confirmed={f.confirmed} data-rejected={f.rejected} data-unjudged={f.unjudged}>
      machine-flagged {f.flagged} · confirmed {f.confirmed} · rejected {f.rejected}{f.unsure ? ` · unsure ${f.unsure}` : ''} · unjudged {f.unjudged}
      {f.flagRule && <InfoTip title="flagged, confirmed, rejected">{f.flagRule}</InfoTip>}
    </span>
  )
}

interface JobState { id: number; status: JobRow['status']; done: number; total: number | null; message: string; error: string | null; result: LibClassifyResult | null }

export function useCrossChannelJob(onDone?: (r: LibClassifyResult) => void) {
  const [job, setJob] = useState<JobState | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const busy = job != null && (job.status === 'queued' || job.status === 'running')
  const jobId = job?.id
  const done = useRef(onDone)
  done.current = onDone
  useEffect(() => {
    if (jobId == null || !busy) return
    let alive = true
    const timer = window.setInterval(async () => {
      try {
        const row = await getJob(jobId)
        if (!alive) return
        const p = (row.progress ?? {}) as { done?: number; total?: number | null; message?: string }
        const next: JobState = { id: jobId, status: row.status, done: p.done ?? 0, total: p.total ?? null, message: p.message ?? '',
          error: row.error ? row.error.message : null, result: (row.result as LibClassifyResult | null) ?? null }
        setJob(next)
        if (row.status === 'completed' && next.result) done.current?.(next.result)
      } catch (e) {
        // loud, not blank: the job may still be running, but this page has lost it
        if (alive) setJob(j => (j ? { ...j, status: 'failed', error: `lost the job: ${(e as Error).message}` } : j))
      }
    }, 600)
    return () => { alive = false; window.clearInterval(timer) }
  }, [jobId, busy])
  const start = async (familyId: string, grouping?: string) => {
    setStartError(null)
    try {
      const ack = await classifyFamilyCrossChannel(familyId, grouping)
      setJob({ id: ack.job_id, status: 'running', done: 0, total: null, message: `starting · ${ack.members} members of ${ack.family}`, error: null, result: null })
      return ack
    } catch (e) { setStartError((e as Error).message); return null }
  }
  return { job, busy, start, startError }
}

function Count({ n, label, tone, rule, testid }: { n: number; label: string; tone: 'red' | 'amber' | 'green' | 'grey'; rule: string; testid: string }) {
  return (
    <span className="row" style={{ gap: 4, alignItems: 'center' }} data-testid={testid}>
      <span className={`k-badge t-${tone}`}>{label} {n}</span>
      <InfoTip title={label}>{rule}</InfoTip>
    </span>
  )
}

export function CrossChannelCard({ familyId, grouping, cc, onReload }: { familyId: string; grouping?: string; cc: LibCrossChannel | undefined; onReload: () => void }) {
  const toast = useToast()
  const { job, busy, start, startError } = useCrossChannelJob(r => {
    onReload()
    toast.push({ text: `${r.family} classified across ${r.channels} channel${r.channels === 1 ? '' : 's'}: ${XBINS.map(b => `${XBIN_LABEL[b]} ${r.counts[b]}`).join(' · ')}` })
  })
  if (!cc) return null
  const wm = cc.withoutMember ?? {}
  const flags = cc.recurrence as typeof cc.recurrence & Partial<LibFlagLine>
  const n = cc.null
  return (
    <section className="k-card" style={{ padding: 12, display: 'grid', gap: 8 }} data-testid="cross-channel-card" data-classified={cc.classified ? 'yes' : 'no'} aria-label="Cross-channel classification">
      <div className="row" style={{ gap: 8, alignItems: 'center' }}>
        <b style={{ fontSize: 13 }}>Cross-channel</b>
        <InfoTip title="How a pair is classified">
          Each member is compared with every other channel of its recording over {cc.method}. The rule is Settings ›
          Analysis defaults ({ruleWords(cc.rule)}); r is tested by its size, and its sign is stored on the edge. Where a
          sibling channel holds no member of this family, the event seen there is counted as a co-occurrence without a
          member and never written as an edge (Q40c).
        </InfoTip>
        {!cc.classified && <Badge tone="grey" testid="cross-channel-unclassified">not classified yet</Badge>}
        {cc.stale && <Badge status="stale" title={`stored bins were computed under ${cc.computedUnder.map(ruleWords).join(' / ')}; Settings now says ${ruleWords(cc.rule)}. Classify again to bring them up to date.`} testid="cross-channel-stale">computed under a different rule</Badge>}
        <span style={{ marginLeft: 'auto' }} />
        <Button size="sm" icon="compare" testid="classify-across-channels" disabled={busy} disabledReason="a classification of this family is running"
          onClick={() => start(familyId, grouping)}>Classify across channels</Button>
        {cc.classified && <SendToReview familyId={familyId} grouping={grouping} flagged={flags.flagged ?? 0} queue={cc.suspectedQueue ?? null} />}
        <Button size="sm" variant="link" iconRight="arrow-right" testid="cross-channel-settings" onClick={() => navigate('settings/analysis-defaults')}>rule</Button>
      </div>
      {job && (busy || job.status !== 'completed') && (
        <div className="row" style={{ gap: 8 }} data-testid="cross-channel-job">
          {busy && <ProgressBar value={job.total ? job.done / job.total : 0} indeterminate={!job.total} width={220} size="sm"
            label={`${job.total ? `${job.done} of ${job.total} channels · ` : ''}${job.message}`} testid="cross-channel-progress" />}
          {job.status === 'failed' && <span className="lib-cap" style={{ color: 'var(--red)' }} data-testid="cross-channel-failed">job {job.id} failed · {job.error}</span>}
          {job.status === 'cancelled' && <span className="lib-cap">job {job.id} cancelled</span>}
          <Button size="sm" variant="link" onClick={() => navigate('jobs')}>job {job.id} in Jobs</Button>
        </div>
      )}
      {startError && <span className="lib-cap" style={{ color: 'var(--red)' }} data-testid="cross-channel-start-error">could not start: {startError}</span>}
      {job?.status === 'completed' && job.result && job.result.skipped > 0 && (
        <span className="lib-cap" data-testid="cross-channel-skipped">{job.result.skipped} comparison{job.result.skipped === 1 ? '' : 's'} not made: {job.result.skippedReasons.join(' · ')}</span>
      )}
      <div className="row" style={{ gap: 12, flexWrap: 'wrap' }} data-testid="cross-channel-counts">
        <span className="lib-muted-label">member pairs</span>
        {XBINS.map(b => <Count key={b} n={cc.counts[b] ?? 0} label={XBIN_LABEL[b]} tone={XBIN_TONE[b]} rule={cc.rules[b]} testid={`xc-count-${b}`} />)}
        <span className="lib-muted-label" style={{ marginLeft: 8 }}>co-occurrence without a member</span>
        <Count n={wm.artifact ?? 0} label="artifact" tone="red" testid="xc-without-artifact"
          rule={`A member's event seen on a sibling channel where this family has no member, binned artifact: ${cc.rules.artifact}. Counted per member × sibling channel; never written as an edge (Q40c).`} />
        <Count n={wm.propagation ?? 0} label="propagation" tone="amber" testid="xc-without-propagation"
          rule={`A member's event seen on a sibling channel where this family has no member, binned propagation: ${cc.rules.propagation}. Counted per member × sibling channel; never written as an edge (Q40c).`} />
        <span className="lib-muted-label" style={{ marginLeft: 8 }}>members</span>
        <Count n={cc.tooShort ?? 0} label="too short to tell" tone="grey" testid="xc-too-short"
          rule={cc.tooShortRule ?? 'a member under the minimum length is not classified'} />
      </div>
      <div className="row" style={{ gap: 12, flexWrap: 'wrap' }} data-testid="cross-channel-recurrence">
        <span className="lib-muted-label">recurrence</span>
        {(['all', 'excluding_artifacts', 'propagation_once'] as RecurrenceMode[]).map(m => (
          <Count key={m} n={cc.recurrence[m]} label={MODE_LABEL[m]} tone="grey" rule={cc.recurrence.rules[m]} testid={`xc-recurrence-${m}`} />
        ))}
        <FlagLine f={flags} />
      </div>
      {cc.chanceRule && <div className="lib-cap" data-testid="cross-channel-chance-rule">every bin {cc.chanceRule}; the percentile each pair reached is on its edge</div>}
      <div className="lib-cap" data-testid="cross-channel-null">
        {n.drawsTotal > 0
          ? <>null: these members came from {n.runs} run{n.runs === 1 ? '' : 's'}, which found {n.realDetections} detection{n.realDetections === 1 ? '' : 's'}; their paired surrogates ({n.draws} draw{n.draws === 1 ? '' : 's'} per run) found {n.perDraw == null ? '—' : n.perDraw.toFixed(1)} per draw. Both numbers are printed; nothing here is tested against the other.</>
          : <>null: {n.reason}</>}
      </div>
    </section>
  )
}
