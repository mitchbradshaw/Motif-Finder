/* Explore › Auto-detect (2026-11-23, the researcher: "integrate the auto-detect into the site"): one button on a
   channel runs the reference line-up (detectors, tight seed families, the event rule, R4; on the signal and again on
   the inverted signal) as a job with real progress and a time left; the candidates are drawn over the signal shaded
   by confidence, drops ▼ and sharp rises ▲, the sequences in their own band; what the researcher picks goes to
   Review - candidates as machine detections in a listed queue, the sequences into sequence review.
   Route: #/explore/autodetect/<channelId>[?job=<id>]. Reached from Explore › Signal's top bar. */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, cancelJob, getChannel, getRecordings, subscribeJob, type Channel } from '../api'
import { getAdSetup, getAdSignal, getAutoDetect, listAutoDetect, sendAutoDetect, startAutoDetect, type AdJobSnap, type AdListed, type AdResult, type AdSetup } from '../api/autodetect'
import { Button, Callout, Checkbox, Chip, KeyValue, ProgressBar, SectionCard, Slider, useQueryState } from '../kit'
import { DatasetName } from '../naming'
import { ErrorBoundary } from '../shell/ErrorBoundary'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { COLOUR, NONE, SCAN, byStart, clock, decodeSignal, duration, hoursOf, isShown, minutes, parseHour, sourceCounts, sourcesOf, type Filter, type Sig } from './autoDetectModel'
import { AutoDetectViewer, clampView } from './AutoDetectViewer'
import { ErrorCard } from './ErrorCard'
import { asApiError } from './util'
import './autodetect.css'

const typeWord = (pol: number) => (pol ? '▲ rise' : '▼ drop')

export function AutoDetectPage({ channelId }: { channelId: number }) {
  const [ch, setCh] = useState<Channel | null>(null)
  const [err, setErr] = useState<ApiError | null>(null)
  useEffect(() => {
    let alive = true
    setCh(null); setErr(null)
    if (!Number.isFinite(channelId)) { setErr(new ApiError(0, `bad channel id in the route: ${String(channelId)}`)); return }
    getRecordings().then(files => {
      if (!alive) return
      const owner = files.find(f => f.channels.some(c => c.id === channelId))
      if (owner?.held_out) { setErr(new ApiError(423, owner.held_out_reason ?? `${owner.source_file} is held out`)); return }
      getChannel(channelId).then(c => { if (alive) setCh(c) }).catch(e => { if (alive) setErr(asApiError(e)) })
    }).catch(e => { if (alive) setErr(asApiError(e)) })
    return () => { alive = false }
  }, [channelId])
  if (err) {
    return (
      <>
        <Header workspace="Explore" page="Auto-detect" subtitle={`channel ${channelId} · ${err.status === 423 ? 'held out' : 'error'}`} />
        <div className="page"><div className="page-inner"><ErrorCard error={err} title={err.status === 423 ? 'auto-detect refuses the held-out recording' : `GET /api/channels/${channelId} failed`} /></div></div>
      </>
    )
  }
  if (!ch) {
    return (
      <>
        <Header workspace="Explore" page="Auto-detect" subtitle={`channel ${channelId} · loading…`} />
        <div className="page"><div className="page-inner" data-testid="ad-loading"><div className="skeleton" style={{ height: 120 }} /><div className="skeleton" style={{ height: 420 }} /></div></div>
      </>
    )
  }
  return <AutoDetectBody ch={ch} />
}

function AutoDetectBody({ ch }: { ch: Channel }) {
  const toast = useToast()
  const [jobQ, setJobQ] = useQueryState<string>('job', '')
  const [setup, setSetup] = useState<AdSetup | null>(null)
  const [list, setList] = useState<AdListed[] | null>(null)
  const [running, setRunning] = useState<AdJobSnap | null>(null)
  const [listErr, setListErr] = useState<ApiError | null>(null)
  const [rev, setRev] = useState(0)
  useEffect(() => { getAdSetup().then(setSetup).catch(e => setListErr(asApiError(e))) }, [])
  useEffect(() => {
    let alive = true
    listAutoDetect(ch.id).then(r => { if (!alive) return; setList(r.results); setRunning(r.running) }).catch(e => { if (alive) setListErr(asApiError(e)) })
    return () => { alive = false }
  }, [ch.id, rev])

  // the result shown: ?job=, else the newest
  const jobId = jobQ ? Number(jobQ) : (list && list.length ? list[0].job_id : null)
  const [res, setRes] = useState<AdResult | null>(null)
  const [sig, setSig] = useState<Sig | null>(null)
  const [resErr, setResErr] = useState<ApiError | null>(null)
  useEffect(() => {
    if (jobId == null || !Number.isFinite(jobId)) { setRes(null); setSig(null); return }
    let alive = true
    setResErr(null)
    getAutoDetect(jobId).then(r => {
      if (!alive) return
      setRes(r)
      if (!sig || sig.start_idx !== r.start_idx || sig.n !== r.n || sig.fs !== r.fs) {
        getAdSignal(ch.id, r.start_idx, r.start_idx + r.n).then(s => { if (alive) setSig(decodeSignal(s)) }).catch(e => { if (alive) setResErr(asApiError(e)) })
      }
    }).catch(e => { if (alive) setResErr(asApiError(e)) })
    return () => { alive = false }
  }, [jobId, ch.id])  // eslint-disable-line react-hooks/exhaustive-deps -- the signal is re-read only when the stretch changes

  return (
    <>
      <Header workspace="Explore" page="Auto-detect"
        subtitle={res?.summary ? `${ch.name} · ${res.summary.candidates.toLocaleString()} candidates · ${res.summary.at_05.toLocaleString()} at 0.5 or more` : `${ch.name} · auto-detect`} />
      <div className="page"><div className="page-inner ad-page" data-testid="ad-page">
        <div className="ex-topbar" data-testid="ad-topbar">
          <div className="ex-crumb">
            <a onClick={() => navigate('explore/corpus')} data-testid="crumb-corpus">Corpus</a><span>›</span>
            <a onClick={() => navigate(`explore/corpus?rec=${encodeURIComponent(ch.source_file)}&ch=${ch.id}`)}><DatasetName file={ch.source_file} /></a><span>›</span>
            <a onClick={() => navigate(`explore/signal/${ch.id}`)} data-testid="crumb-signal">{ch.name}</a><span>›</span>
            <span className="cur">Auto-detect</span>
          </div>
          <span className="grow" />
          <a className="ex-back" onClick={() => navigate(`explore/signal/${ch.id}`)}>‹ back to the signal</a>
        </div>
        {listErr && <ErrorCard error={listErr} title="auto-detect's list of runs failed" />}
        <ErrorBoundary label="auto-detect run panel">
          <RunPanel ch={ch} setup={setup} list={list} running={running} jobId={jobId}
            onPick={id => setJobQ(String(id))}
            onStarted={snap => setRunning(snap)}
            onFinished={id => { setRunning(null); setRev(n => n + 1); if (id != null) setJobQ(String(id)) }} />
        </ErrorBoundary>
        {resErr && <ErrorCard error={resErr} title={`auto-detect result ${jobId} could not be read`} />}
        {res && sig ? (
          <ErrorBoundary label="auto-detect result">
            <ResultView key={res.job_id} ch={ch} res={res} sig={sig} onSent={() => { setRev(n => n + 1); getAutoDetect(res.job_id).then(setRes).catch(() => {}) }} toast={toast} />
          </ErrorBoundary>
        ) : jobId != null && !resErr ? (
          <div className="skeleton" style={{ height: 420 }} data-testid="ad-result-loading" />
        ) : list && !list.length && !running ? (
          <Callout tone="blue" title="Not run on this channel yet" testid="ad-empty">
            Auto-detect finds drops and sharp rises with every detector that has earned its place, the tight seed families,
            your event rule and R4, then runs the whole process again on the inverted signal. Press <b>Run auto-detect</b> above.
          </Callout>
        ) : null}
      </div></div>
    </>
  )
}

// ── run ──────────────────────────────────────────────────────────────────

function RunPanel(p: { ch: Channel; setup: AdSetup | null; list: AdListed[] | null; running: AdJobSnap | null; jobId: number | null
  onPick: (id: number) => void; onStarted: (s: AdJobSnap) => void; onFinished: (id: number | null) => void }) {
  const { ch, setup, running } = p
  const toast = useToast()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [busy, setBusy] = useState(false)
  const [live, setLive] = useState<{ done: number; total: number; message: string; t0: number } | null>(null)
  const hours = ch.duration_s / 3600
  const t0h = from.trim() ? parseHour(from) : 0
  const t1h = to.trim() ? parseHour(to) : hours
  const bad = t0h == null || t1h == null || t0h < 0 || t1h > hours + 1e-9 || t1h <= t0h
  const n = bad ? 0 : Math.round((t1h! - t0h!) * 3600 * ch.fs)
  const estimate = setup ? (setup.fixed_s ?? 0) + setup.seconds_per_sample * n : null

  // follow a running job through its event stream (a late subscriber gets the whole history); keyed on the job id
  // alone, so a re-render never closes the stream, with the callbacks read through refs
  const finished = useRef(p.onFinished)
  finished.current = p.onFinished
  const toastRef = useRef(toast)
  toastRef.current = toast
  const runningId = running?.job_id ?? null
  useEffect(() => {
    if (runningId == null || !running) return
    setLive({ done: running.progress?.done ?? 0, total: running.progress?.total ?? 1000, message: running.progress?.message ?? '', t0: Date.now() - (running.elapsed_s ?? 0) * 1000 })
    let ended = false
    const h = subscribeJob(runningId, e => {
      const ev = e as unknown as { event: string; done?: number; total?: number; message?: string; status?: string; result?: { job_id?: number } | null; error?: { message?: string } | null }
      if (ev.event === 'progress') setLive(l => ({ done: ev.done ?? 0, total: ev.total ?? 1000, message: ev.message ?? '', t0: l?.t0 ?? Date.now() }))
      if (ev.event === 'job_end' && !ended) {
        ended = true
        setLive(null)
        if (ev.status === 'completed') { toastRef.current.push({ text: `Auto-detect finished on ${ch.name}` }); finished.current(ev.result?.job_id ?? runningId) }
        else if (ev.status === 'cancelled') { toastRef.current.push({ text: `Auto-detect cancelled on ${ch.name}; nothing was saved` }); finished.current(null) }
        else { toastRef.current.push({ kind: 'error', text: `Auto-detect ${ev.status}${ev.error?.message ? `: ${ev.error.message}` : ''}` }); finished.current(null) }
      }
    })
    return () => h.close()
  }, [runningId])  // eslint-disable-line react-hooks/exhaustive-deps -- one stream per running job

  const start = async () => {
    setBusy(true)
    try {
      const r = await startAutoDetect(ch.id, from.trim() ? t0h! * 3600 : null, to.trim() ? t1h! * 3600 : null)
      p.onStarted({ job_id: r.job_id, status: 'running', elapsed_s: 0, error: null, progress: { done: 0, total: 1000, message: 'starting' }, meta: {} })
    } catch (e) {
      const ae = asApiError(e)
      const other = (ae.detail as { job_id?: number } | null)?.job_id
      toast.push({ kind: 'error', text: `Auto-detect did not start: ${ae.message}` })
      if (ae.status === 409 && other) p.onStarted({ job_id: other, status: 'running', elapsed_s: 0, error: null, progress: { done: 0, total: 1000, message: 'already running' }, meta: {} })
    } finally { setBusy(false) }
  }
  // a stage runs to its end before a cancel lands (about 40 s on a whole channel): say so on the button meanwhile
  const [cancelling, setCancelling] = useState(false)
  useEffect(() => { if (!running && !live) setCancelling(false) }, [running, live])
  const stop = () => {
    if (!running) return
    setCancelling(true)
    cancelJob(running.job_id).then(() => toast.push({ text: 'Cancelling auto-detect after the stage it is in' }))
      .catch(e => { setCancelling(false); toast.push({ kind: 'error', text: String(e) }) })
  }
  const frac = live && live.total ? live.done / live.total : 0
  const msg = live?.message ?? ''
  const [stage, left] = msg.includes(' · ') ? [msg.slice(0, msg.lastIndexOf(' · ')), msg.slice(msg.lastIndexOf(' · ') + 3)] : [msg, '']
  const notReady = setup && !setup.ready ? setup.problems.join('; ') : null

  return (
    <SectionCard title="Auto-detect" testid="ad-run"
      info={'One button: the drop detectors (whole stretch and 6-hour windows), BEADS → 10σ, the tight seed families, your event rule as a finder, and R4 scoring every candidate and scanning windows — on the signal and again on the inverted signal, so sharp rises are found the way drops are. Confidence = 1 − (1 − R4) × Π(1 − ½ × precision of each agreeing source). Nothing is written to the database until you send to Review.'}
      actions={p.list && p.list.length > 0 ? (
        <label className="ad-pick">earlier runs
          <select value={p.jobId ?? ''} onChange={e => p.onPick(Number(e.target.value))} data-testid="ad-pick">
            {p.list.map(r => (
              <option key={r.job_id} value={r.job_id}>
                job {r.job_id} · {r.created_at?.replace('T', ' ').slice(0, 16) ?? '?'} · {r.summary ? `${r.summary.candidates} candidates` : '?'}{r.sent.length ? ' · sent' : ''}
              </option>))}
          </select>
        </label>) : undefined}>
      {notReady && <Callout tone="red" title="Auto-detect cannot run on this bridge" testid="ad-not-ready">{notReady}</Callout>}
      {ch.fs > 2.0001 && (
        <Callout tone="amber" testid="ad-rate-note">
          Auto-detect was tuned on channels sampled at 1–2 Hz; this one is at {ch.fs} Hz. Here the event rule's
          5-sample minimum spans {(5 / ch.fs).toFixed(1)} s instead of 2.5–5 s, and a run takes longer. A 2 Hz copy of
          the recording, where there is one, matches the tuning.
        </Callout>
      )}
      {setup && setup.missing_detectors.length > 0 && (
        <Callout tone="amber" testid="ad-missing">This database has no {setup.missing_detectors.join(', ')} template; a run goes on without {setup.missing_detectors.length === 1 ? 'it' : 'them'} and says so.</Callout>
      )}
      <div className="ad-run-row">
        <label>from <input className="ad-time" value={from} onChange={e => setFrom(e.target.value)} placeholder="0:00" data-testid="ad-from" /></label>
        <label>to <input className="ad-time" value={to} onChange={e => setTo(e.target.value)} placeholder={clock(ch.duration_s, false)} data-testid="ad-to" /></label>
        <span className="muted">{bad ? 'a stretch inside the channel, as h:mm or hours' : `${duration(n, ch.fs)} · ${(n / 1e6).toFixed(2)} M samples · about ${minutes(estimate)}`}</span>
        <span className="grow" />
        {running || live ? (
          <Button variant="danger" onClick={stop} loading={cancelling} disabled={cancelling} disabledReason="the run stops after the stage it is in"
            testid="ad-cancel">{cancelling ? 'Cancelling…' : 'Cancel'}</Button>
        ) : (
          <Button variant="next" icon="play" onClick={start} loading={busy} disabled={!!notReady || bad || !setup}
            disabledReason={notReady ?? (bad ? 'the stretch is not inside the channel' : 'reading the set-up')} testid="ad-run-button">
            Run auto-detect
          </Button>
        )}
      </div>
      {(running || live) && (
        <div className="ad-progress" data-testid="ad-progress">
          <ProgressBar value={frac} eta={left || undefined} />
          <div className="muted ad-stage" data-testid="ad-stage">{stage || 'starting'} · job {running?.job_id ?? ''}</div>
        </div>
      )}
    </SectionCard>
  )
}

// ── result ───────────────────────────────────────────────────────────────

function ResultView({ ch, res, sig, onSent, toast }: { ch: Channel; res: AdResult; sig: Sig; onSent: () => void; toast: ReturnType<typeof useToast> }) {
  const c = res.candidates
  const counts = useMemo(() => sourceCounts(c, res.sources), [c, res.sources])
  const allSources = useMemo(() => [...res.sources, SCAN, NONE], [res.sources])
  const [filter, setFilter] = useState<Filter>(() => ({ minc: 0.5, drop: true, rise: true, src: new Set(allSources) }))
  const [markers, setMarkers] = useState(true)
  const [showSeq, setShowSeq] = useState(true)
  const [view, setViewState] = useState<[number, number]>(() => [0, sig.n])
  const setView = useCallback((v: [number, number]) => setViewState(clampView(v[0], v[1], sig.n)), [sig.n])
  const [sel, setSel] = useState(-1)
  const [order, setOrder] = useState<'time' | 'conf'>('time')
  const [goto, setGoto] = useState('')
  const shown = useCallback((i: number) => isShown(c, res.sources, filter, i), [c, res.sources, filter])
  const listed = useMemo(() => {
    const L = byStart(c).filter(shown)
    if (order === 'conf') L.sort((a, b) => c.c[b] - c.c[a] || c.s[a] - c.s[b])
    return L
  }, [c, shown, order])
  const label = (k: string) => res.source_labels[k] ?? (k === NONE ? 'R4 alone, inside another box' : k)
  const focus = useCallback((i: number) => {
    setSel(i)
    const d = c.e[i] - c.s[i], w = Math.max(d * 8, 600 * sig.fs), mid = (c.s[i] + c.e[i]) / 2
    setView([mid - w / 2, mid + w / 2])
  }, [c, sig.fs, setView])
  const step = useCallback((dir: number) => {
    if (!listed.length) return
    let k = listed.indexOf(sel)
    if (k < 0) {
      const mid = (view[0] + view[1]) / 2
      k = dir > 0 ? listed.findIndex(i => c.s[i] > mid) : (() => { let j = -1; listed.forEach((i, q) => { if (c.s[i] < mid) j = q }); return j })()
      if (k < 0) k = dir > 0 ? 0 : listed.length - 1
    } else k = (k + dir + listed.length) % listed.length
    focus(listed[k])
  }, [listed, sel, view, c, focus])
  const zoom = (f: number) => { const m = (view[0] + view[1]) / 2, h = (view[1] - view[0]) * f / 2; setView([m - h, m + h]) }
  const goTo = () => {
    const h = parseHour(goto)
    if (h == null) return
    const idx = h * 3600 * sig.fs - sig.start_idx, half = 600 * sig.fs
    setView([idx - half, idx + half])
  }
  // keys: n / p step, + − zoom, ← → pan, 0 the whole stretch
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && t.closest('input, textarea, select, [contenteditable="true"]')) return
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const span = view[1] - view[0]
      if (e.key === 'n') { e.preventDefault(); step(1) }
      else if (e.key === 'p') { e.preventDefault(); step(-1) }
      else if (e.key === '+' || e.key === '=') { e.preventDefault(); zoom(0.6) }
      else if (e.key === '-' || e.key === '_') { e.preventDefault(); zoom(1 / 0.6) }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); setView([view[0] - 0.2 * span, view[1] - 0.2 * span]) }
      else if (e.key === 'ArrowRight') { e.preventDefault(); setView([view[0] + 0.2 * span, view[1] + 0.2 * span]) }
      else if (e.key === '0') { e.preventDefault(); setView([0, sig.n]) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const describe = useCallback((i: number) => {
    const src = sourcesOf(c, res.sources, i).map(label)
    return [
      `#${c.id[i]} · ${typeWord(c.pol[i])} · confidence ${c.c[i].toFixed(2)}`,
      `${clock((c.s[i] + sig.start_idx) / sig.fs)}–${clock((c.e[i] + sig.start_idx) / sig.fs)} · ${duration(c.e[i] - c.s[i], sig.fs)}${c.dep[i] != null ? ` · ${c.dep[i]!.toFixed(2)} mV` : ''}`,
      `found by ${src.length ? src.join(', ') : 'no source (R4 alone)'}${c.inv[i] ? ' · on the inverted signal' : ''}${c.both[i] ? ' · both runs' : ''}`,
      `R4 ${c.p[i] == null ? '–' : c.p[i]!.toFixed(2)}${c.shp[i] != null ? ` · sharpness ${c.shp[i]!.toFixed(0)}` : ''}${c.seq[i] >= 0 ? ` · sequence S${c.seq[i]}` : ''}`,
    ]
  }, [c, res.sources, sig])  // eslint-disable-line react-hooks/exhaustive-deps -- label reads res only

  const s05 = res.summary
  return (
    <>
      <div className="ad-chips" data-testid="ad-chips">
        <Chip>{duration(sig.n, sig.fs)} from {clock(sig.start_idx / sig.fs, false)}</Chip>
        <Chip>{c.s.length.toLocaleString()} candidates</Chip>
        {s05 && <Chip>{s05.at_05.toLocaleString()} at ≥ 0.5: {s05.drops_05.toLocaleString()} ▼ · {s05.rises_05.toLocaleString()} ▲</Chip>}
        <Chip>{res.sequences.s.length} sequences</Chip>
        {res.wall_s != null && <Chip>{minutes(res.wall_s)} to run</Chip>}
        {res.sent.length > 0 && <Chip tone="green" testid="ad-sent-chip">sent to Review ({res.sent.reduce((a, s) => a + s.detections, 0)} candidates)</Chip>}
      </div>
      {sig.unit_note && <Callout tone="amber" testid="ad-unit-note">{sig.unit_note}</Callout>}
      <div className="card ad-card">
        <div className="ad-controls">
          <Button size="sm" onClick={() => zoom(0.5)} testid="ad-zoom-in">＋</Button>
          <Button size="sm" onClick={() => zoom(2)} testid="ad-zoom-out">－</Button>
          <Button size="sm" onClick={() => setView([0, sig.n])} testid="ad-whole">Whole stretch</Button>
          <label className="ad-goto">go to <input value={goto} onChange={e => setGoto(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') goTo() }} placeholder="h:mm" data-testid="ad-goto" /></label>
          <Button size="sm" onClick={() => step(-1)} testid="ad-prev">◀ Prev</Button>
          <Button size="sm" onClick={() => step(1)} testid="ad-next">Next ▶</Button>
          <select value={order} onChange={e => setOrder(e.target.value as 'time' | 'conf')} data-testid="ad-order">
            <option value="time">by time</option><option value="conf">by confidence</option>
          </select>
          <span className="muted">{listed.indexOf(sel) >= 0 ? `${listed.indexOf(sel) + 1} of ${listed.length}` : `${listed.length.toLocaleString()} shown`}</span>
          <span className="grow" />
          <span className="ad-minc">min confidence
            <Slider value={filter.minc} onChange={v => setFilter(f => ({ ...f, minc: v }))} min={0} max={1} step={0.01} width={150} format={v => v.toFixed(2)} ariaLabel="min confidence" testid="ad-minc" />
          </span>
        </div>
        <div className="ad-controls ad-filters">
          <span className="muted">type:</span>
          <Checkbox checked={filter.drop} onChange={v => setFilter(f => ({ ...f, drop: v }))} label="▼ drops" dot={COLOUR.drop} count={counts.drop.toLocaleString()} testid="ad-show-drops" />
          <Checkbox checked={filter.rise} onChange={v => setFilter(f => ({ ...f, rise: v }))} label="▲ rises" dot={COLOUR.rise} count={counts.spike.toLocaleString()} testid="ad-show-rises" />
          <span className="muted">found by:</span>
          {allSources.filter(k => (counts[k] ?? 0) > 0).map(k => (
            <Checkbox key={k} checked={filter.src.has(k)} label={label(k)} count={(counts[k] ?? 0).toLocaleString()} testid={`ad-src-${k}`}
              onChange={v => setFilter(f => { const s = new Set(f.src); if (v) s.add(k); else s.delete(k); return { ...f, src: s } })} />
          ))}
          <Checkbox checked={markers} onChange={setMarkers} label="markers" testid="ad-markers" />
          <Checkbox checked={showSeq} onChange={setShowSeq} label="sequences" testid="ad-sequences" />
        </div>
        <AutoDetectViewer sig={sig} cands={c} seqs={res.sequences} sources={res.sources} filter={filter} markers={markers} showSeq={showSeq}
          view={view} onView={setView} selected={sel} onSelect={i => setSel(i)} describe={describe} />
        <div className="ad-legend muted">
          <span><i style={{ background: COLOUR.drop }} />▼ drop</span><span><i style={{ background: COLOUR.rise }} />▲ rise</span>
          <span><i style={{ background: COLOUR.scan }} />found by R4's window scan alone</span>
          <span><i style={{ background: COLOUR.seqDrop }} />/<i style={{ background: COLOUR.seqRise }} />sequence of drops / of rises</span>
          <span>darker = more confident · scroll to zoom, drag to pan, shift-drag to zoom into a range, double-click for the whole stretch · keys n / p, + −, ← →, 0</span>
        </div>
      </div>
      <div className="ad-grid">
        <SectionCard title="Selected candidate" testid="ad-detail">
          {sel >= 0 ? <Detail res={res} sig={sig} i={sel} label={label} /> : <span className="muted">Click a candidate on the plot or in the table.</span>}
        </SectionCard>
        <SendPanel res={res} onSent={onSent} toast={toast} ch={ch} />
      </div>
      <CandidateTable res={res} sig={sig} listed={listed} sel={sel} onPick={focus} label={label} />
      <SectionCard title="How this run went" collapsible defaultOpen={false} testid="ad-notes">
        {res.notes.map((t, k) => <p key={k} className="ad-note">{t}</p>)}
        {res.missing_detectors.length > 0 && <p className="ad-note">Detectors missing from this database: {res.missing_detectors.join(', ')}.</p>}
      </SectionCard>
    </>
  )
}

function Detail({ res, sig, i, label }: { res: AdResult; sig: Sig; i: number; label: (k: string) => string }) {
  const c = res.candidates
  let lifts: [string, number][] = []
  try { lifts = JSON.parse(c.lifts[i]) } catch { /* not shown */ }
  const src = sourcesOf(c, res.sources, i).map(label)
  return (
    <KeyValue dense labelWidth={150} testid="ad-detail-kv" items={[
      { k: 'candidate', v: `#${c.id[i]} · ${typeWord(c.pol[i])}` },
      { k: 'when', v: `${clock((c.s[i] + sig.start_idx) / sig.fs)}–${clock((c.e[i] + sig.start_idx) / sig.fs)} (${hoursOf(sig, c.s[i]).toFixed(3)} h) · ${duration(c.e[i] - c.s[i], sig.fs)}` },
      { k: 'confidence', v: c.c[i].toFixed(3) },
      { k: 'R4 on its box', v: c.p[i] == null ? 'could not read' : c.p[i]!.toFixed(3) },
      { k: 'found by', v: src.length ? src.join(', ') : 'no source vouched for it: it is inside another candidate\'s box, scored by R4 alone' },
      { k: 'found on', v: `${c.inv[i] ? 'the inverted signal (its drops are this signal\'s rises)' : 'the signal'}${c.both[i] ? '; the other run found it too' : ''}` },
      { k: 'depth', v: c.dep[i] == null ? '–' : `${c.dep[i]!.toFixed(3)} mV; the box runs to ${c.rec[i] ? (c.pol[i] ? 'half way back down' : 'half recovery') : 'where it levels off'}` },
      { k: 'sharpness', v: c.shp[i] == null ? '–' : `steepest 1-second step ${c.shp[i]!.toFixed(1)} × the channel's step noise` },
      { k: 'seed families', v: c.fam[i] || '–' },
      { k: 'how it was built', v: lifts.length ? lifts.map(([k, v], q) => (q === 0 ? `R4 ${v.toFixed(2)}` : `+ ${label(k)} → ${v.toFixed(2)}`)).join(' ') : '–' },
      { k: 'sequence', v: c.seq[i] >= 0 ? `S${c.seq[i]}` : 'none' },
    ]} />
  )
}

function CandidateTable({ res, sig, listed, sel, onPick, label }: { res: AdResult; sig: Sig; listed: number[]; sel: number; onPick: (i: number) => void; label: (k: string) => string }) {
  const c = res.candidates
  const [rows, setRows] = useState(200)
  const [sort, setSort] = useState<{ k: 'time' | 'conf' | 'depth' | 'dur'; dir: 1 | -1 }>({ k: 'conf', dir: -1 })
  const sorted = useMemo(() => {
    const key = (i: number) => (sort.k === 'time' ? c.s[i] : sort.k === 'conf' ? c.c[i] : sort.k === 'depth' ? c.dep[i] ?? -1 : c.e[i] - c.s[i])
    return [...listed].sort((a, b) => (key(a) - key(b)) * sort.dir || c.s[a] - c.s[b])
  }, [listed, sort, c])
  const head = (k: typeof sort.k, text: string) => (
    <th className="num" onClick={() => setSort(s => ({ k, dir: s.k === k ? (s.dir === 1 ? -1 : 1) : k === 'time' ? 1 : -1 }))} data-testid={`ad-sort-${k}`}>
      {text}{sort.k === k ? (sort.dir > 0 ? ' ▲' : ' ▼') : ''}
    </th>)
  return (
    <SectionCard title={`Candidates · ${listed.length.toLocaleString()} shown`} testid="ad-table">
      <div className="ad-tablewrap">
        <table className="ad-table">
          <thead><tr><th>#</th>{head('time', 'when')}<th>type</th>{head('depth', 'mV')}{head('dur', 'duration')}{head('conf', 'confidence')}<th className="num">R4</th><th>found by</th><th>seq</th></tr></thead>
          <tbody>
            {sorted.slice(0, rows).map(i => (
              <tr key={i} className={i === sel ? 'sel' : undefined} onClick={() => onPick(i)} data-testid="ad-row">
                <td className="num">{c.id[i]}</td>
                <td className="num">{clock((c.s[i] + sig.start_idx) / sig.fs)}</td>
                <td><span style={{ color: c.pol[i] ? COLOUR.rise : COLOUR.drop }}>{typeWord(c.pol[i])}</span>{c.inv[i] ? <span className="muted"> inv</span> : null}</td>
                <td className="num">{c.dep[i] == null ? '–' : c.dep[i]!.toFixed(2)}</td>
                <td className="num">{duration(c.e[i] - c.s[i], sig.fs)}</td>
                <td className="num"><span className="ad-bar" style={{ width: Math.round(c.c[i] * 50), background: c.k[i] === 1 ? COLOUR.scan : c.pol[i] ? COLOUR.rise : COLOUR.drop }} /> {c.c[i].toFixed(2)}</td>
                <td className="num">{c.p[i] == null ? '–' : c.p[i]!.toFixed(2)}</td>
                <td>{sourcesOf(c, res.sources, i).map(label).join(', ') || 'R4 alone'}</td>
                <td>{c.seq[i] >= 0 ? `S${c.seq[i]}` : ''}</td>
              </tr>))}
          </tbody>
        </table>
      </div>
      {sorted.length > rows && <Button size="sm" onClick={() => setRows(r => r + 1000)} testid="ad-more">Show {Math.min(1000, sorted.length - rows).toLocaleString()} more</Button>}
    </SectionCard>
  )
}

function SendPanel({ res, onSent, toast, ch }: { res: AdResult; onSent: () => void; toast: ReturnType<typeof useToast>; ch: Channel }) {
  const c = res.candidates
  const [minc, setMinc] = useState(0.5)
  const [drops, setDrops] = useState(true)
  const [rises, setRises] = useState(true)
  const [withSeq, setWithSeq] = useState(true)
  const [busy, setBusy] = useState(false)
  const sentIds = useMemo(() => new Set(res.sent.flatMap(s => s.candidate_ids)), [res.sent])
  const pick = useMemo(() => {
    const out: number[] = []
    for (let i = 0; i < c.s.length; i++) if (c.c[i] >= minc && (c.pol[i] ? rises : drops)) out.push(i)
    return out
  }, [c, minc, drops, rises])
  const fresh = pick.filter(i => !sentIds.has(c.id[i]))
  // the server's rule: a sequence goes when two or more picked candidates make it, and never twice
  const sentSeq = useMemo(() => new Set(res.sent.flatMap(s => s.sequence_ids ?? [])), [res.sent])
  const seqIds = useMemo(() => {
    const members = new Map<number, number>()
    for (const i of pick) if (c.seq[i] >= 0) members.set(c.seq[i], (members.get(c.seq[i]) ?? 0) + 1)
    return new Set([...members].filter(([s, m]) => m >= 2 && !sentSeq.has(s)).map(([s]) => s))
  }, [pick, c, sentSeq])
  const send = async () => {
    setBusy(true)
    try {
      const r = await sendAutoDetect(res.job_id, { min_confidence: minc, polarities: [...(drops ? ['drop'] : []), ...(rises ? ['spike'] : [])], sequences: withSeq })
      const parts = [`${r.detections.toLocaleString()} candidates`]
      if (r.held_back) parts.push(`Review holds back ${r.held_back.toLocaleString()} that match a span you already judged`)
      if (r.held_back_error) parts.push(`could not count what Review holds back (${r.held_back_error})`)
      if (r.sequences) parts.push(`${r.sequences} sequences`)
      if (r.already_sent) parts.push(`${r.already_sent.toLocaleString()} already sent`)
      toast.push({ kind: r.held_back_error ? 'error' : undefined, text: `Sent to Review from ${ch.name}: ${parts.join(' · ')}`, action: r.queue_id ? { label: 'Open the queue →', onClick: () => navigate(`review/queue/${r.queue_id}`) } : r.sequence_queue_id ? { label: 'Open sequence review →', onClick: () => navigate(`review/queue/${r.sequence_queue_id}`) } : undefined })
      onSent()
    } catch (e) {
      toast.push({ kind: 'error', text: `Not sent: ${asApiError(e).message}` })
    } finally { setBusy(false) }
  }
  return (
    <SectionCard title="Send to Review" testid="ad-send"
      info="Each candidate becomes a machine detection in a new Review queue, in time order, and is asked about on its own: candidates whose boxes overlap go in separate runs so that Review does not fold them into one item. A verdict there is yours and the candidate stays the machine's. Review holds back a candidate that matches a span you already judged. The sequences that the sent candidates make go to sequence review. Nothing is sent twice.">
      <div className="ad-send-row">
        <span>confidence at least</span>
        <Slider value={minc} onChange={setMinc} min={0} max={1} step={0.05} width={140} format={v => v.toFixed(2)} ariaLabel="send at least" testid="ad-send-minc" />
      </div>
      <div className="ad-send-row">
        <Checkbox checked={drops} onChange={setDrops} label="▼ drops" dot={COLOUR.drop} testid="ad-send-drops" />
        <Checkbox checked={rises} onChange={setRises} label="▲ rises" dot={COLOUR.rise} testid="ad-send-rises" />
        <Checkbox checked={withSeq} onChange={setWithSeq} label="and their sequences" testid="ad-send-seq" />
      </div>
      {res.judged_here != null && (
        <p className="muted ad-send-what" data-testid="ad-judged-here">
          {res.judged_here > 0
            ? `Review holds back a candidate that matches one of the ${res.judged_here.toLocaleString()} spans you judged on this recording. `
            : 'You have no judged spans on this recording, so Review will ask about every candidate. '}
          It does not see verdicts given on another copy of this channel (another sampling rate), so events judged there come up again.
        </p>
      )}
      <p className="muted ad-send-what" data-testid="ad-send-what">
        {fresh.length.toLocaleString()} candidate{fresh.length === 1 ? '' : 's'} to send
        {pick.length > fresh.length ? ` (${(pick.length - fresh.length).toLocaleString()} already sent)` : ''}
        {withSeq && seqIds.size ? ` · up to ${seqIds.size} sequence${seqIds.size === 1 ? '' : 's'}` : ''}
      </p>
      <Button variant="next" icon="checklist" onClick={send} loading={busy} disabled={!fresh.length && !(withSeq && seqIds.size)}
        disabledReason="nothing new to send at this confidence" testid="ad-send-button">Send to Review</Button>
      {res.sent.length > 0 && (
        <div className="ad-sent" data-testid="ad-sent">
          {res.sent.map((s, k) => (
            <div key={k} className="muted">
              {s.at.replace('T', ' ').slice(0, 16)}: {s.detections} candidates at ≥ {s.min_confidence}
              {s.queue_id ? <> · <a onClick={() => navigate(`review/queue/${s.queue_id}`)}>queue {s.queue_id}</a></> : null}
              {s.sequence_queue_id ? <> · {s.sequences} sequences, <a onClick={() => navigate(`review/queue/${s.sequence_queue_id}`)}>queue {s.sequence_queue_id}</a></> : null}
            </div>))}
        </div>
      )}
    </SectionCard>
  )
}
