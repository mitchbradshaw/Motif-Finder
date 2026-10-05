/* Library › Window sets › New window set (fixup-af, RQ1 version 2).
 *
 * One recording, the channels (whole packs one click each), one or more scales (1 / 10 / 30 minutes ticked by
 * default — the "build at 1 / 10 / 30 min" shortcut is just the three ticks), a non-overlapping grid, the artifact
 * exclusion, and a seeded sample where the supply is large. Each scale is one saved window set: unlabelled windows
 * cut from the signal (manual labels ignored), artifact spans left out and counted, NO roles — the train / test
 * fence is laid over the pool that combines sets (`AG`'s *Window pool* block over `Working/training/pool.py`).
 * The build is a background job; its progress is drawn from the job, and the new rows appear in the list when it
 * ends. A failure is shown loudly, never swallowed. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Callout, Checkbox, Modal, NumberField, ProgressBar, SelectField, fmtInt, useQueryState } from '../kit'
import { getJob, type JobRow } from '../api'
import { useSourced } from '../api/seam'
import { buildUnlabelledSets, getUnlabelledSources, type BuiltSet, type SourceRecording } from '../api/windowsets'

const SCALES = [1, 10, 30]
/** above this many windows a scale says its supply is large: a pool samples it per scale AFTER the fence is laid
 *  (the default — every window is saved, bounds only); a sample here is for a set used on its own */
const LARGE_SUPPLY = 100_000

function useJob(jobId: number | null, onEnd: (j: JobRow) => void) {
  const [job, setJob] = useState<JobRow | null>(null)
  const endRef = useRef(onEnd); endRef.current = onEnd
  useEffect(() => {
    if (jobId == null) { setJob(null); return }
    let alive = true
    const tick = () => getJob(jobId).then(j => {
      if (!alive) return
      setJob(j)
      if (['completed', 'failed', 'cancelled'].includes(j.status)) endRef.current(j)
      else window.setTimeout(tick, 600)
    }, e => { if (alive) { console.error('job poll failed', e); window.setTimeout(tick, 1500) } })
    tick()
    return () => { alive = false }
  }, [jobId])
  return job
}

const stemOf = (file: string) => file.replace(/\.[^.]+$/, '')

export function NewWindowSetModal({ open, onClose, onBuilt }: { open: boolean; onClose: () => void; onBuilt: (sets: BuiltSet[]) => void }) {
  const src = useSourced(getUnlabelledSources, [open])
  return (
    <Modal open={open} onClose={onClose} size="lg" testid="new-window-set-modal" title="New window set"
      subtitle="unlabelled windows cut from the signal — manual labels ignored · one set per scale · no roles: the train / test fence is laid over the pool that combines sets">
      {src.error && <Callout tone="red" title="Could not read the recordings" testid="new-window-set-error">{src.error.message}</Callout>}
      {src.loading && !src.data && <ProgressBar indeterminate label="reading the recordings…" testid="new-window-set-loading" />}
      {src.data && (src.data.recordings.length
        ? <NewWindowSetForm recordings={src.data.recordings} heldOut={src.data.held_out} exclusions={src.data.exclusions} onClose={onClose} onBuilt={onBuilt} />
        : <Callout tone="amber" title="No recording to cut">this installation holds no recording other than the held-out one</Callout>)}
    </Modal>
  )
}

function NewWindowSetForm({ recordings, heldOut, exclusions, onClose, onBuilt }: {
  recordings: SourceRecording[]; heldOut: { file: string; name: string; reason: string }; exclusions: string
  onClose: () => void; onBuilt: (sets: BuiltSet[]) => void
}) {
  /* the recording is in the URL (?nwsrec=<source file>), so a link or a smoke state can open the modal on one */
  const [fileQ, setFileQ] = useQueryState('nwsrec', recordings[0].source_file)
  const file = recordings.some(r => r.source_file === fileQ) ? fileQ : recordings[0].source_file
  const setFile = (v: string) => setFileQ(v)
  const rec = recordings.find(r => r.source_file === file) ?? recordings[0]
  const [channels, setChannels] = useState<number[]>(() => rec.channels.map(c => c.channel))
  useEffect(() => { setChannels(rec.channels.map(c => c.channel)) }, [rec.source_file])  // eslint-disable-line react-hooks/exhaustive-deps
  const [scales, setScales] = useState<number[]>(SCALES)
  const [stride, setStride] = useState(1)
  const [exclude, setExclude] = useState(true)
  const [sampleOn, setSampleOn] = useState<Record<string, boolean>>({})
  const [sampleN, setSampleN] = useState<Record<string, number>>({})
  const [seed, setSeed] = useState(0)
  const [jobId, setJobId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<BuiltSet[] | null>(null)

  const fraction = channels.length / Math.max(1, rec.channels.length)
  const supplyOf = (s: number) => Math.floor((rec.supply[String(s)] ?? 0) * fraction / Math.max(1, stride))
  const sampleFor = (s: number) => sampleOn[String(s)] ?? false
  const nFor = (s: number) => sampleN[String(s)] ?? 50_000
  const stem = stemOf(rec.source_file)
  const names = useMemo(() => [...scales].sort((a, b) => a - b).map(s => `ws_${stem}_${s}min`), [scales, stem])

  const job = useJob(jobId, j => {
    setJobId(null)
    if (j.status === 'completed') {
      const sets = ((j.result as { sets?: BuiltSet[] } | undefined)?.sets) ?? []
      setDone(sets); onBuilt(sets)
    } else {
      setError(j.error ? `${j.error.type ?? 'error'}: ${j.error.message ?? ''}` : `the build ${j.status}`)
    }
  })
  const running = jobId != null
  const p = job?.progress as { done?: number; total?: number | null; message?: string } | undefined
  const blocked = !channels.length ? 'tick at least one channel' : !scales.length ? 'tick at least one scale' : running ? 'building…' : null

  const build = () => {
    setError(null); setDone(null)
    const sample: Record<string, number> = {}
    for (const s of scales) if (sampleFor(s) && nFor(s) < supplyOf(s)) sample[String(s)] = nFor(s)
    buildUnlabelledSets({ source_file: rec.source_file, channels, scales_min: [...scales].sort((a, b) => a - b), stride_factor: stride,
      exclude_artifacts: exclude, sample, seed })
      .then(j => setJobId(j.job_id), e => { console.error('build failed', e); setError(String(e?.message ?? e)) })
  }
  const togglePack = (idx: number[], on: boolean) => setChannels(cs => on ? [...new Set([...cs, ...idx])].sort((a, b) => a - b) : cs.filter(c => !idx.includes(c)))

  return (
    <div className="stack" style={{ gap: 14 }} data-testid="new-window-set-form">
      <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
        <span className="lib-muted-label" style={{ width: 90 }}>recording</span>
        <SelectField value={file} onChange={setFile} width={420} testid="nws-recording" ariaLabel="recording"
          options={[...recordings.map(r => ({ value: r.source_file, label: `${r.name}${r.name !== r.source_file ? ` · ${r.source_file}` : ''} · ${r.channels.length} ch · ${r.hours.toFixed(0)} h` })),
            { value: heldOut.file, label: `${heldOut.name} · held out`, disabled: true, reason: 'locked (Settings › Datasets, after the freeze)' }]} />
      </div>

      <div className="stack" style={{ gap: 6 }}>
        <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
          <span className="lib-muted-label" style={{ width: 90 }}>channels</span>
          <Button size="sm" testid="nws-all" onClick={() => setChannels(rec.channels.map(c => c.channel))}>all {rec.channels.length}</Button>
          {Object.entries(rec.packs).map(([k, idx]) => {
            const on = idx.every(i => channels.includes(i))
            return <Checkbox key={k} testid={`nws-pack-${k}`} checked={on} indeterminate={!on && idx.some(i => channels.includes(i))}
              label={`pack ${k} (CH${idx[0] + 1}–${idx[idx.length - 1] + 1})`} onChange={v => togglePack(idx, v)} />
          })}
          <span className="lib-cap">{channels.length} of {rec.channels.length} ticked</span>
        </div>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap', paddingLeft: 100 }} data-testid="nws-channels">
          {rec.channels.map(c => <Checkbox key={c.channel} testid={`nws-ch-${c.channel}`} checked={channels.includes(c.channel)}
            label={<span className="mono small" title={`${c.hours} h · ${c.artifact_spans} artifact span(s)`}>{c.name}</span>}
            onChange={v => setChannels(cs => v ? [...cs, c.channel].sort((a, b) => a - b) : cs.filter(x => x !== c.channel))} />)}
        </div>
      </div>

      <div className="stack" style={{ gap: 6 }}>
        <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
          <span className="lib-muted-label" style={{ width: 90 }}>scales</span>
          {SCALES.map(s => <Checkbox key={s} testid={`nws-scale-${s}`} checked={scales.includes(s)} label={`${s} min`}
            onChange={v => setScales(xs => v ? [...xs, s] : xs.filter(x => x !== s))} />)}
          <span className="lib-cap">one window set per scale · all three ticked = build at 1 / 10 / 30 min</span>
        </div>
        <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
          <span className="lib-muted-label" style={{ width: 90 }}>grid</span>
          <span className="lib-cap">stride =</span>
          <NumberField value={stride} onValid={setStride} min={1} max={10} step={1} unit="× window" width={120} testid="nws-stride" ariaLabel="stride in windows" />
          <span className="lib-cap">1 = windows abut, none overlaps (a stride under one window is refused)</span>
        </div>
        <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
          <span className="lib-muted-label" style={{ width: 90 }}>artifacts</span>
          <Checkbox testid="nws-exclude" checked={exclude} onChange={setExclude} label="leave artifact spans out (counted)" />
        </div>
        {exclude && <span className="lib-cap" style={{ paddingLeft: 100 }} data-testid="nws-exclusions">{exclusions}</span>}
      </div>

      <div className="k-card" style={{ padding: '10px 12px' }} data-testid="nws-supply">
        <div className="row" style={{ gap: 10, marginBottom: 6 }}><b style={{ fontSize: 12.5 }}>supply and sample</b>
          <span className="lib-cap">seed</span><NumberField value={seed} onValid={setSeed} min={0} integer width={90} testid="nws-seed" ariaLabel="seed" /></div>
        {[...scales].sort((a, b) => a - b).map(s => (
          <div key={s} className="row" style={{ gap: 10, flexWrap: 'wrap', padding: '3px 0' }} data-testid={`nws-supply-${s}`}>
            <span className="mono small b" style={{ width: 60 }}>{s} min</span>
            <span className="mono small" style={{ width: 170 }}>{fmtInt(supplyOf(s))} windows on the grid</span>
            <Checkbox testid={`nws-sample-on-${s}`} checked={sampleFor(s)} onChange={v => setSampleOn(o => ({ ...o, [String(s)]: v }))} label="keep a seeded sample of" />
            <NumberField value={nFor(s)} onValid={n => setSampleN(o => ({ ...o, [String(s)]: n }))} min={1} integer width={120} disabled={!sampleFor(s)}
              disabledReason="every window is kept" testid={`nws-sample-${s}`} ariaLabel={`sample at ${s} min`} />
            {!sampleFor(s) && <span className="lib-cap">{supplyOf(s) > LARGE_SUPPLY ? "a large supply: every window is saved (bounds only) and the pool samples this scale after the fence is laid" : "all kept"}</span>}
          </div>
        ))}
        <span className="lib-cap">saved as {names.map(n => <span key={n} className="mono">{n} </span>)}(a name that exists gets a new version)</span>
      </div>

      {running && <ProgressBar testid="nws-progress" value={p?.total ? (p.done ?? 0) / p.total : 0} label={p?.message ?? 'starting…'} />}
      {error && <Callout tone="red" title="The build failed" testid="nws-failed">{error}</Callout>}
      {done && <Callout tone="green" title={`${done.length} window set${done.length === 1 ? '' : 's'} saved`} testid="nws-done">
        {done.map(d => <div key={d.window_set_id} className="mono small">{d.name} v{d.version} · {d.scale_min} min · {fmtInt(d.n_windows)} windows · artifact {fmtInt(d.counts.artifact_human ?? 0)} · excluded by Settings {fmtInt(d.counts.excluded_by_settings ?? 0)} · sampled out {fmtInt(d.counts.sampled_out ?? 0)}</div>)}
      </Callout>}

      <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
        <Button onClick={onClose} testid="nws-close">{done ? 'Close' : 'Cancel'}</Button>
        <Button variant="primary" icon="plus" testid="nws-build" disabled={!!blocked} disabledReason={blocked ?? undefined} onClick={build}>
          {`Build ${scales.length} set${scales.length === 1 ? '' : 's'}`}
        </Button>
      </div>
    </div>
  )
}
