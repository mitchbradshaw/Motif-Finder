/* seed-search (2026-10-18), step 4 — keep the matches. Two ways (the researcher): *Use these as detections* writes the
 * preview's matches at or below the cut as a run, the preview's null being the run's null, with NO second search
 * (POST /api/discovery/seed/keep); *Run with the rigorous null* is the paired run (200 surrogate runs per channel,
 * POST /api/discovery/seed/run with nullMode 'paired'). "No null" is gone. Over the local limit the rigorous run is a
 * cluster job, and its button says so and why; Import HPC result lives in that state. When a run is done, *Send
 * unjudged to Review* puts its detections in the session's picked queue — the mechanism Discovery's browser uses
 * (`sendDetectionsToReview`, fixup-AL) — and *Open in Runs* opens it. */
import { useRef, useState } from 'react'
import { ApiError, cancelJob, postDiscoverySeedImport, runDiscoverySeedSearchOnce, sendDetectionsToReview, type DiscSeedEstimate } from '../../api'
import { fmtSeconds, keepSeedMatches, runDetectionIds, type DiscoveryRun, type SeedInfo } from '../../api/discovery'
import { Button, InfoTip, ProgressBar } from '../../kit'
import { useToast } from '../../shell/Toast'
import { navigate } from '../../state'
import type { Discovery } from '../session'

/** A file picker as a button: the result file `seed_job` wrote on the cluster, brought back by hand. */
export function ImportResultButton({ onFile, testid = 'import-result' }: { onFile: (f: File) => void; testid?: string }) {
  const ref = useRef<HTMLInputElement>(null)
  return (
    <>
      <input ref={ref} type="file" accept=".json,application/json" style={{ display: 'none' }} data-testid={`${testid}-file`}
        onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = '' }} />
      <Button icon="upload" onClick={() => ref.current?.click()} title="import a seed_job result file computed on the HPC" testid={testid}>Import HPC result</Button>
    </>
  )
}

const errText = (e: unknown) => e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)
const plural = (n: number, one: string, many = `${one}es`) => `${n} ${n === 1 ? one : many}`

export interface KeepCardProps {
  dx: Discovery; seed: SeedInfo; label: string
  /** the cut in force and how many preview matches are at or below it */
  cut: number | null; kept: number
  /** the preview's null draws per channel (the kept run's null) */
  previewDraws: number
  bank: { scales: number[]; overlap: string } | null; exclusion: number | null; k: number
  /** the rigorous run's cost on this scope (nullMode 'paired'), and whether it is over the local limit */
  rigorous: DiscSeedEstimate | null
  /** this search's runs, by how their null was drawn: the preview's matches kept, and the rigorous run */
  keptRun: DiscoveryRun | null; rigorousRun: DiscoveryRun | null
  onSave: () => void; onSlurm: () => void
  /** a run was made or found: the page re-reads the runs list */
  onChanged: () => void
  /** the bridge holds no preview of this query any more (409): the page goes back to step 2 */
  onNeedsPreview: () => void
}

export function KeepCard({ dx, seed, label, cut, kept, previewDraws, bank, exclusion, k, rigorous, keptRun, rigorousRun, onSave, onSlurm, onChanged, onNeedsPreview }: KeepCardProps) {
  const toast = useToast()
  const [keeping, setKeeping] = useState(false)
  const [starting, setStarting] = useState(false)
  const [importing, setImporting] = useState<string | null>(null)
  /** the kept run's detection ids, as the keep answered them (else read when sending) */
  const [keptIds, setKeptIds] = useState<{ key: string; ids: number[] } | null>(null)
  const scope = dx.scope!
  const channels = scope.channels
  const hours = scope.section[1] - scope.section[0]
  const overLimit = !!rigorous && rigorous.route === 'cluster'
  const noCut = cut == null ? 'no cut yet — choose one in step 3 (the histogram)' : null

  const keep = () => {
    setKeeping(true)
    keepSeedMatches(seed.id, channels, bank, exclusion, scope.section, cut, label)
      .then(r => {
        setKeptIds({ key: r.run_key, ids: r.detectionIds })
        onChanged()
        toast.push({ text: r.done ? `${r.label} · ${plural(r.found ?? 0, 'detection', 'detections')} kept · ${r.note}` : `${r.label} · ${r.note}`,
          action: { label: 'Open in Runs', onClick: () => navigate(`discovery/runs?run=${encodeURIComponent(r.run_key)}`) } })
      })
      .catch(e => {
        if (e instanceof ApiError && e.status === 409) { toast.push({ text: `not kept · ${e.message}` }); onNeedsPreview(); return }
        console.error('the matches could not be kept', e)
        toast.push({ text: `not kept · ${errText(e)}` })
      })
      .finally(() => setKeeping(false))
  }
  const runRigorous = () => {
    setStarting(true)
    runDiscoverySeedSearchOnce({
      seedId: seed.id, channels, t0: scope.section[0], t1: scope.section[1], k, cut: cut ?? undefined, label, nullMode: 'paired',
      ...(bank ? { scales: bank.scales, overlap: bank.overlap } : {}), ...(exclusion != null ? { exclusion } : {}),
    }).then(r => { onChanged(); if (r.reused && r.note) toast.push({ text: `${r.label} · ${r.note}` }) })
      .catch(e => { console.error('the rigorous run could not start', e); toast.push({ text: `the run did not start · ${errText(e)}` }) })
      .finally(() => setStarting(false))
  }
  const importResult = (file: File) => {
    setImporting(file.name)
    file.text().then(text => postDiscoverySeedImport(JSON.parse(text)))
      .then(r => { onChanged(); toast.push({ text: `${r.label} · ${r.nullDraws} null draws imported · ${r.candidates} candidates · the real search is running here` }) })
      .catch(e => { console.error('the result could not be imported', e); toast.push({ text: `not imported · ${errText(e)}` }) })
      .finally(() => setImporting(null))
  }

  const keepLine = cut == null ? null
    : `${plural(kept, 'match')} at d ≤ ${cut} · the preview's ${previewDraws}-draw null per channel stands behind them · nothing is searched again`
  const rigorousLine = rigorous
    ? `about ${fmtSeconds(rigorous.run.seconds)} · ${channels.length} ch × ${hours.toFixed(1)} h × ${rigorous.run.draws} paired null runs per channel${rigorous.run.measured ? '' : ' · assumed rate until one run has finished here'}`
    : 'estimating the rigorous run'

  return (
    <section className="k-card dsc-keep" data-testid="seed-keep-card" aria-label="Keep the matches">
      <div className="dsc-card-head">
        <h3>Keep the matches</h3>
        <InfoTip title="Two ways to keep">
          <b>Use these as detections</b> writes the preview's matches at or below the cut as a run on Discovery › Runs — one run per
          channel, their detections ready for Review — with the preview's null as the run's null. The preview was already the full
          search, so nothing is searched again; it takes seconds. <b>Run with the rigorous null</b> runs the search again as a real run
          paired with 200 surrogate runs per channel (Settings › Nulls): slower, and the null a result you report should stand on.
        </InfoTip>
      </div>
      <p className="small dsc-keep-lede">Turn the matches you chose into detections: as they are, or checked against the rigorous null.</p>

      {[keptRun, rigorousRun].filter((r): r is DiscoveryRun => !!r).map(r =>
        <RunState key={r.key} run={r} dx={dx} ids={keptIds && keptIds.key === r.key ? keptIds.ids : null} onImport={importResult} importing={importing} />)}

      <div className="dsc-keep-ways">
        {(!keptRun || keptRun.status === 'failed') && (
          <div className="dsc-keep-way" data-testid="keep-preview-way">
            <Button variant="primary" icon="check" onClick={keep} loading={keeping} disabled={!!noCut || keeping} disabledReason={noCut ?? 'keeping…'} testid="seed-keep">Use these as detections</Button>
            <span className="small mono" data-testid="seed-keep-line">{keepLine ?? noCut}</span>
          </div>
        )}
        {(!rigorousRun || rigorousRun.status === 'failed') && (overLimit ? (
          <div className="dsc-keep-way" data-testid="keep-cluster-way">
            <Button variant="cluster" icon="file" onClick={onSlurm} testid="seed-slurm">Run it on the cluster</Button>
            <span className="small mono amber" data-testid="seed-over-limit">
              about {fmtSeconds(rigorous!.run.seconds)} here with the rigorous null, over the {fmtSeconds(rigorous!.ceilingS)} limit — run it on the cluster
            </span>
            <ImportResultButton onFile={importResult} />
            {importing && <span className="small" data-testid="seed-importing-label"><ProgressBar indeterminate size="sm" width={90} labelPosition="none" /> importing {importing}…</span>}
          </div>
        ) : (
          <div className="dsc-keep-way" data-testid="keep-rigorous-way">
            <Button icon="play" onClick={runRigorous} loading={starting} disabled={starting} disabledReason="starting…" testid="run-seed-search">Run with the rigorous null</Button>
            <span className="small mono muted" data-testid="run-estimate">{rigorousLine}</span>
          </div>
        ))}
      </div>

      <div className="dsc-keep-save">
        <Button size="sm" className="dsc-btn-quiet-blue" icon="save" onClick={onSave} testid="save-as-template">Save as template</Button>
        <span className="small muted" data-testid="save-as-template-line">saves the recipe — this exemplar, d ≤ {cut ?? 'no cut'}, the scale bank and the exclusion zone — never the matches</span>
      </div>
    </section>
  )
}

/** One run of this search, by its status: running (with its own progress and Cancel), on the cluster (with Import),
 *  failed (loud), or done — with *Send unjudged to Review* and *Open in Runs*. */
function RunState({ run, dx, ids, onImport, importing }: { run: DiscoveryRun; dx: Discovery; ids: number[] | null; onImport: (f: File) => void; importing: string | null }) {
  const toast = useToast()
  const [sending, setSending] = useState(false)
  const running = run.status === 'running' || run.status === 'queued'
  const how = run.nullSource === 'preview' ? "the preview's matches · the preview's null" : run.nullSource === 'hpc' ? 'null from the cluster' : 'rigorous null · paired surrogate runs'
  const open = () => navigate(`discovery/runs?run=${encodeURIComponent(run.key)}`)
  const send = () => {
    const scope = dx.scope!
    setSending(true)
    Promise.resolve(ids ?? runDetectionIds(run.key, scope.channels, scope.section))
      .then(list => {
        if (!list.length) { toast.push({ text: `${run.label} has no detections to send` }); return null }
        return sendDetectionsToReview(run.key, list)
      })
      .then(r => {
        if (!r) return
        const judged = new Set(r.already_judged.map(d => d.id))
        const notAsked = new Set(r.not_asked)
        const fresh = r.added.filter(i => !judged.has(i) && !notAsked.has(i)).length
        const parts = [`${fresh} added to Review`, `${r.already_judged.length} already judged`]
        if (r.not_asked.length) parts.push(`${r.not_asked.length} covered by a human verdict`)
        if (r.already.length) parts.push(`${r.already.length} already in the queue`)
        toast.push({ text: `${parts.join(' · ')} · '${r.queue}'`, action: { label: 'Open Review', onClick: () => navigate(`review/queue/${r.queue_id}`) } })
        dx.reload()
      })
      .catch(e => { console.error('the detections could not be sent to Review', e); toast.push({ text: `not sent · ${errText(e)}` }) })
      .finally(() => setSending(false))
  }
  const cancel = () => {
    const id = run.job ? parseInt(run.job.replace(/^j-/, ''), 10) : NaN
    if (!Number.isFinite(id)) return
    cancelJob(id).then(() => dx.reload()).catch(e => console.error('the run could not be cancelled', e))
  }
  if (running) {
    const frac = run.progress ?? 0
    return (
      <div className="dsc-keep-run" data-testid={`seed-run-state-${run.key}`} data-status="running">
        <ProgressBar value={frac} width={180} labelPosition="none" testid="seed-progress" />
        <b data-testid="seed-running">{run.label} · {run.status === 'queued' ? 'queued · local' : `running · ${Math.round(frac * 100)} %`}{run.progressText ? ` · ${run.progressText}` : ''}</b>
        <span className="k-spacer" />
        <Button onClick={cancel} disabled={!run.job} disabledReason="no job to cancel" testid="seed-cancel">Cancel</Button>
      </div>
    )
  }
  if (run.status === 'on cluster') return (
    <div className="dsc-keep-run" data-testid={`seed-run-state-${run.key}`} data-status="on-cluster">
      <b>{run.label}</b>
      <span className="muted small mono" data-testid="on-cluster">on the cluster · import {run.hpc?.resultPath.split('/').pop() ?? 'the result'} when it is back</span>
      <span className="k-spacer" />
      <ImportResultButton onFile={onImport} testid="import-result-on-cluster" />
      {importing && <span className="small">importing {importing}…</span>}
    </div>
  )
  if (run.status === 'failed') return (
    <div className="dsc-keep-run" data-testid={`seed-run-state-${run.key}`} data-status="failed">
      <span className="dot" style={{ background: 'var(--red)', width: 9, height: 9 }} />
      <b className="red" data-testid="seed-failed">{run.label} failed · {run.error ?? 'see Runs'}</b>
      <span className="k-spacer" />
      <Button variant="link" size="sm" icon="external" onClick={open}>Open in Runs</Button>
    </div>
  )
  return (
    <div className="dsc-keep-run" data-testid={`seed-run-state-${run.key}`} data-status="done">
      <span className="dot" style={{ background: 'var(--green)', width: 9, height: 9 }} />
      <b data-testid="seed-done">{run.label} · {plural(run.found ?? 0, 'detection', 'detections')} · {how}{run.doneAt ? ` · done ${run.doneAt}` : ''}</b>
      <span className="k-spacer" />
      <Button variant="primary" size="sm" icon="inbox" onClick={send} loading={sending} disabled={sending || !run.found} disabledReason={sending ? 'sending…' : 'the run found nothing'} testid="seed-send-review">Send unjudged to Review</Button>
      <Button variant="link" size="sm" icon="external" onClick={open} testid="seed-open-runs">Open in Runs</Button>
    </div>
  )
}
