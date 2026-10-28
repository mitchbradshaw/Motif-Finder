/* Explore › Cross-channel — the census card (xc-S1; round-B question B4, docs/prompts/changes/cross-channel-explorer.md).
 *
 * In plain words: every event one detector found on every channel is paired with every event on another channel
 * that starts within the propagation ceiling, measured on the same stretch of both, tested against luck, and put in
 * a bin. Nobody picks the stretches, so these are the numbers B4 is answered with; every count sits beside its null.
 *
 * States: none (Run census), running (real progress and a time estimate from the job's done/total and elapsed time),
 * done, stale (why, and Re-run). The detector is choosable; one without a real run on every channel is listed
 * disabled with its reason. Every number and every rule's words come from the bridge (`api/cross.ts`); this file only
 * formats them. A read or job that fails is said in red, never left blank. */
import { useCallback, useEffect, useState } from 'react'
import { getJob, type JobRow } from '../api'
import { CENSUS_BINS, getCensus, startCensus, type CensusBin, type CensusRead, type CensusRow } from '../api/cross'
import { Badge, Button, Dropdown, InfoTip, ProgressBar } from '../kit'
import { navigate } from '../state'

const BIN_LABEL: Record<CensusBin, string> = {
  artifact: 'artifact', propagation: 'propagation', independent_recurrence: 'independent', shared_driver: 'shared driver',
  pack_unknown: 'pack unknown',
}
const BIN_TONE: Record<CensusBin, 'red' | 'amber' | 'green' | 'blue' | 'grey'> = {
  artifact: 'red', propagation: 'amber', independent_recurrence: 'green', shared_driver: 'blue', pack_unknown: 'grey',
}

const fmtP = (p: number | null | undefined) => p == null ? '—' : p < 0.001 ? '< 0.001' : p.toFixed(3)
const fmtQ = (q: number | null | undefined) => q == null ? 'fails' : `passes (≤ ${q.toFixed(3)})`
const fmtN = (v: number | null | undefined, d = 1) => v == null ? '—' : v.toFixed(d)
const fmtS = (s: number) => s < 90 ? `${Math.round(s)} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${(s / 3600).toFixed(1)} h`

interface JobState { id: number; status: JobRow['status']; done: number; total: number | null; message: string; elapsed: number; error: string | null }

function toJobState(j: JobRow): JobState {
  const p = (j.progress ?? {}) as { done?: number; total?: number | null; message?: string }
  const elapsed = (j as unknown as { elapsed_s?: number }).elapsed_s ?? 0
  return { id: j.job_id, status: j.status, done: p.done ?? 0, total: p.total ?? null, message: p.message ?? '', elapsed,
    error: j.error ? j.error.message : null }
}

/** The time left from the job's own counts: elapsed × (total − done) / done. Null until a unit is done. */
function estimate(j: JobState): string | null {
  if (!j.total || !j.done || j.done >= j.total) return null
  return `about ${fmtS(j.elapsed * (j.total - j.done) / j.done)} left`
}

export function CensusCard({ sourceFile }: { sourceFile: string }) {
  const [detector, setDetector] = useState<string | null>(null)
  const [read, setRead] = useState<CensusRead | null>(null)
  const [readError, setReadError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [job, setJob] = useState<JobState | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const reload = useCallback(() => setReloadKey(k => k + 1), [])

  useEffect(() => {
    let live = true
    setReadError(null)
    getCensus(sourceFile, detector ?? undefined).then(r => {
      if (!live) return
      setRead(r)
      if (r.running && (!job || job.id !== r.running.job_id)) setJob(toJobState(r.running))
    }).catch(e => {
      if (!live) return
      console.error('census read failed', e)
      setReadError((e as Error).message)
    })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceFile, detector, reloadKey])

  const running = job?.status === 'running' || job?.status === 'queued'
  useEffect(() => {
    if (!job || !running) return
    let live = true
    const timer = window.setInterval(async () => {
      try {
        const j = toJobState(await getJob(job.id))
        if (!live) return
        setJob(j)
        if (j.status === 'completed') reload()
      } catch (e) {
        console.error('census job lost', e)
        if (live) setJob(s => (s ? { ...s, status: 'failed', error: `lost the job: ${(e as Error).message}` } : s))
      }
    }, 800)
    return () => { live = false; window.clearInterval(timer) }
  }, [job?.id, running, reload]) // eslint-disable-line react-hooks/exhaustive-deps

  const det = detector ?? read?.detector ?? null
  const status = read?.detectors.find(d => d.detector === det) ?? null
  const census = read?.census ?? null
  const start = async () => {
    if (!det) return
    setStartError(null)
    try {
      const ack = await startCensus(sourceFile, det)
      setJob({ id: ack.job_id, status: 'running', done: 0, total: null, message: 'starting', elapsed: 0, error: null })
    } catch (e) {
      console.error('census start failed', e)
      setStartError((e as Error).message)
    }
  }

  const head = (
    <div className="ex-card-head" style={{ gap: 8, alignItems: 'center' }}>
      <b>Census of co-occurring events</b>
      <InfoTip title="The census">
        Every event the chosen detector found on every channel is paired with every event on another channel that
        starts close to it ({read?.rules.co_occurrence ?? 'the propagation ceiling'}). Each pair is measured on the same
        stretch of both channels ({read?.rules.window ?? ''}; {read?.rules.lag_search ?? ''}) and binned. Nobody picks
        the stretches, so these are the numbers round-B question B4 is answered with, each beside what luck alone gives.
        Onsets: {read?.rules.onset ?? ''}. {read?.rules.correction ?? ''}.
      </InfoTip>
      <span className="grow" />
      {read && (
        <Dropdown size="sm" value={det} onChange={v => setDetector(v)} ariaLabel="census detector" testid="census-detector"
          options={read.detectors.map(d => ({ value: d.detector, label: d.detector, disabled: !d.full, reason: d.reason ?? undefined,
            hint: d.full ? `${d.nChannels} channels` : `${d.nWithRun} of ${d.nChannels}` }))} />
      )}
      {census && census.stale && <Badge status="stale" testid="census-stale">stale</Badge>}
      {status && (
        <Button size="sm" variant={census ? 'default' : 'primary'} icon="play" testid="census-run" onClick={() => void start()}
          disabled={!status.full || running} disabledReason={running ? 'a census of this recording is running' : status.reason ?? 'not available'}>
          {census ? 'Re-run census' : 'Run census'}
        </Button>
      )}
    </div>
  )

  if (readError) {
    return (
      <div className="card card-pad" data-testid="census-card" data-state="error">
        <div className="ex-card-head"><b>Census of co-occurring events</b></div>
        <div style={{ color: 'var(--red)' }} className="small" data-testid="census-error">could not read the census: {readError}</div>
      </div>
    )
  }
  if (!read) {
    return <div className="card card-pad" data-testid="census-card" data-state="loading"><div className="skeleton" style={{ height: 40 }} /></div>
  }

  const state = running ? 'running' : !census ? 'none' : census.stale ? 'stale' : 'done'
  return (
    <div className="card card-pad" data-testid="census-card" data-state={state} style={{ display: 'grid', gap: 8 }}>
      {head}
      <div className="muted small">
        Every detected event, on every channel, paired with events on other channels that start within the propagation
        ceiling — none of it picked by eye — with each count set beside what chance gives.
      </div>
      {!read.layoutKnown && (
        <div className="ex-warn ex-info small" data-testid="census-layout-unknown">
          <span>{read.layoutNote ?? 'packs not set — layout unknown'}{census ? ` · ${census.summary.pack_unknown} pair${census.summary.pack_unknown === 1 ? '' : 's'} with exactly one channel unplaced counted apart as pack unknown` : ''} ·{' '}
            <button type="button" className="ex-link" onClick={() => navigate('settings/channels')}>Settings › Channels &amp; events</button></span>
        </div>
      )}
      {status && !status.full && (
        <div className="small" style={{ color: 'var(--amber)' }} data-testid="census-not-full">
          This recording has no full census by {status.detector}: {status.reason}.
        </div>
      )}
      {job && running && (
        <ProgressBar value={job.total ? job.done / job.total : 0} width={360} size="sm" testid="census-progress"
          label={`${job.total ? `${job.done} of ${job.total} · ` : 'starting · '}${job.message}${estimate(job) ? ` · ${estimate(job)}` : ''}`} />
      )}
      {job?.status === 'failed' && <div className="small" style={{ color: 'var(--red)' }} data-testid="census-job-failed">census job {job.id} failed · {job.error}</div>}
      {job?.status === 'cancelled' && <div className="small muted" data-testid="census-job-cancelled">census job {job.id} was cancelled; nothing was written</div>}
      {startError && <div className="small" style={{ color: 'var(--red)' }} data-testid="census-start-error">could not start the census: {startError}</div>}
      {!census && !running && status?.full && <div className="small muted" data-testid="census-none">No census of this recording by {status.detector} yet. Run it to see the bins and their nulls.</div>}
      {census && <CensusBody c={census} />}
    </div>
  )
}

function CensusBody({ c }: { c: CensusRow }) {
  const s = c.summary
  const r = s.rules
  const pairs = [...s.pairs].sort((a, b) => b.n - a.n)
  const busy = pairs.filter(p => p.n > 0)
  const quiet = pairs.length - busy.length
  return (
    <div style={{ display: 'grid', gap: 10 }} data-testid="census-body">
      {c.stale && (
        <div className="small" style={{ color: 'var(--amber)' }} data-testid="census-stale-why">
          This census was computed from different inputs: {c.staleWhy.join('; ')}. Re-run it to bring it up to date.
        </div>
      )}
      <div className="row small mono" style={{ gap: 12, flexWrap: 'wrap' }} data-testid="census-meta">
        <span>{s.n_events} events on {s.n_channels} channels · {s.n_cooccurrences} co-occurrences</span>
        <span>onsets: {s.onset_from.label} from labels, {s.onset_from.steepest_fall} from the steepest fall</span>
        {s.unmeasured > 0 && <span>{s.unmeasured} unmeasurable (flat or non-finite)</span>}
        <span title={c.hash} data-testid="census-hash">census {c.hash.slice(0, 12)}</span>
        <span>{c.finishedAt}</span>
      </div>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }} data-testid="census-bins">
        {CENSUS_BINS.map(b => (
          <span key={b} className="row" style={{ gap: 4, alignItems: 'center' }} data-testid={`census-bin-${b}`}>
            <Badge tone={BIN_TONE[b]}>{BIN_LABEL[b]} {s.bins[b]}</Badge>
            <InfoTip title={BIN_LABEL[b]}>{r.bins[b]}</InfoTip>
          </span>
        ))}
        {s.common_mode_pairs > 0 && <span className="small muted">{s.common_mode_pairs} artifact pairs are common mode <InfoTip title="common mode">{r.common_mode}</InfoTip></span>}
      </div>

      <div data-testid="census-overall" className="small">
        <b>Within packs, overall:</b> {s.overall.within_pack.n} co-occurrences against {fmtN(s.overall.within_pack.null_mean)} by
        rotation (95th percentile {fmtN(s.overall.within_pack.null_p95)}), p {fmtP(s.overall.within_pack.p)}
        <InfoTip title="rotation null">{r.nulls.excess}</InfoTip>
        {' · '}<b>across packs:</b> {s.overall.shared_driver.n} shared-driver co-occurrences against {fmtN(s.overall.shared_driver.null_mean)}, p {fmtP(s.overall.shared_driver.p)}
      </div>

      <div className="k-table-wrap">
        <table className="k-table" data-testid="census-pairs" style={{ width: '100%', fontSize: 11.5 }}>
          <thead>
            <tr>
              <th>pair (within one pack)</th><th>pack</th><th>co-occur</th><th>by chance (mean · 95th)</th><th>p</th>
              <th>BH <InfoTip title="Benjamini–Hochberg">{r.correction}</InfoTip></th>
              <th>timetable lag <InfoTip title="timetable">{r.nulls.timetable}</InfoTip></th><th>keep time</th><th>p</th><th>BH</th>
            </tr>
          </thead>
          <tbody>
            {busy.map(p => (
              <tr key={`${p.a}-${p.b}`} data-testid={`census-pair-${p.a_name}-${p.b_name}`}>
                <td className="mono">{p.a_name} → {p.b_name}</td><td>{p.pack}</td><td>{p.n}</td>
                <td>{fmtN(p.null_mean, 2)} · {fmtN(p.null_p95, 0)}</td><td>{fmtP(p.p)}</td><td>{fmtQ(p.q)}</td>
                {p.timetable.testable
                  ? <><td>{fmtN(p.timetable.L_s)} s (median {fmtN(p.timetable.median_lag_s)} ± {fmtN(p.timetable.mad_s)} MAD)</td>
                    <td>{p.timetable.count} of {p.timetable.n_noncopy} (chance {fmtN(p.timetable.null_mean)})</td>
                    <td>{fmtP(p.timetable.p)}</td><td>{fmtQ(p.timetable.q)}</td></>
                  : <td colSpan={4} className="muted">{p.timetable.reason}</td>}
              </tr>
            ))}
          </tbody>
        </table>
        {quiet > 0 && <div className="k-table-foot small muted" data-testid="census-quiet-pairs">{quiet} within-pack pair{quiet === 1 ? '' : 's'} with no co-occurrence (each p 1)</div>}
      </div>

      <div data-testid="census-breadth">
        <b className="small">Instants (events joined by copies)</b> <InfoTip title="breadth">{r.nulls.breadth}. {r.common_mode}</InfoTip>
        {s.breadth.length === 0 ? <div className="small muted">no copy at any instant</div> : (
          <table className="k-table" style={{ width: '100%', fontSize: 11.5 }}>
            <thead><tr><th>at</th><th>breadth</th><th>packs</th><th>common mode</th><th>p</th><th>BH</th></tr></thead>
            <tbody>
              {s.breadth.slice(0, 50).map(i => (
                <tr key={i.instant_id} data-testid={`census-instant-${i.instant_id}`}>
                  <td className="mono">{fmtS(i.onset_s)}</td><td title={i.names.join(', ')}>{i.breadth} channels</td><td>{i.packs.join(' ')}</td>
                  <td>{i.common_mode ? `yes — ${i.why}` : 'no'}</td><td>{fmtP(i.p)}</td><td>{fmtQ(i.q)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {s.breadth.length > 50 && <div className="small muted">and {s.breadth.length - 50} more instants</div>}
      </div>

      <div data-testid="census-shared-driver">
        <b className="small">Shared driver, per pack pair</b> <InfoTip title="shared driver">{r.bins.shared_driver}. {r.nulls.shared_driver}</InfoTip>
        {s.shared_driver.length === 0 ? <div className="small muted">one pack only: no pack pair to compare</div> : (
          <table className="k-table" style={{ width: '100%', fontSize: 11.5 }}>
            <thead><tr><th>packs</th><th>shared driver</th><th>copies</th><th>by chance (mean · 95th)</th><th>p</th><th>BH</th></tr></thead>
            <tbody>
              {s.shared_driver.map(d => (
                <tr key={d.packs.join('-')} data-testid={`census-sd-${d.packs.join('-')}`}>
                  <td>{d.packs.join(' · ')}</td><td>{d.n}</td><td>{d.copies}</td><td>{fmtN(d.null_mean, 2)} · {fmtN(d.null_p95, 0)}</td>
                  <td>{fmtP(d.p)}</td><td>{fmtQ(d.q)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
