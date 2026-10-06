/* fixup-ah — Review's BLIND test queue: a seeded sample of a B.2 run's test and exam windows, labelled interesting /
 * not without the model's answer (`Working/training/blind.py`).
 *
 * In plain words: a model has sorted these windows; you say what each one is without seeing what it said. The card
 * therefore shows the window's raw trace in true millivolts, shaded, with one window-length of context either side,
 * and its length said plainly (a 1-minute and a 30-minute window look alike once drawn the same width) — and
 * NOTHING else that could tip the answer: no prediction, no cluster, no score, no exam, no recording or channel, no
 * place in the recording (the time axis is relative to the window), no earlier label on the span, and when a window
 * comes round a second time (some do, for self-agreement) your first answer is not shown. The queue rail with its
 * thumbnails is not drawn either: a repeat would be found by eye.
 *
 * Keyboard-first: I interesting · N not interesting · U can't tell · A artifact · Z undo · → next · ← previous ·
 * space the next unlabelled. Each answer is written to the database at once (Review's own verdict route — undo and
 * the audit are the core's), and the queue resumes at the first unlabelled window in a later session. */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { scaleLinear } from 'd3'
import { ApiError } from '../api'
import { getBlindQueue, getBlindShowing, type BlindQueuePage, type BlindShowing, type BlindVerdict } from '../api/blind'
import { postUndo, postVerdict, type Verdict } from '../api/review'
import { EnvelopePath } from '../charts/primitives'
import { useSize } from '../charts/useSize'
import { Button, InfoTip, ProgressBar } from '../kit'
import { Header } from '../shell/Header'
import { ErrorBoundary } from '../shell/ErrorBoundary'
import { navigate } from '../state'
import { replaceHash } from './queue'

const WORDS: { v: BlindVerdict; key: string; label: string; primary: boolean }[] = [
  { v: 'interesting', key: 'I', label: 'interesting', primary: true },
  { v: 'not_interesting', key: 'N', label: 'not interesting', primary: true },
  { v: 'unsure', key: 'U', label: "can't tell", primary: false },
  { v: 'artifact', key: 'A', label: 'artifact', primary: false },
]
const SAY: Record<BlindVerdict, string> = { interesting: 'interesting', not_interesting: 'not interesting', unsure: "can't tell", artifact: 'artifact' }
const errText = (e: unknown) => (e instanceof ApiError ? e.message : String(e))

export function BlindTestPage({ queueId, showingPart }: { queueId: string; showingPart?: string }) {
  const [page, setPage] = useState<BlindQueuePage | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [writeErr, setWriteErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)
  const reload = useCallback(() => getBlindQueue(queueId).then(p => { setPage(p); setErr(null); return p })
    .catch(e => { console.error('blind queue failed to load', e); setErr(errText(e)); return null }), [queueId])
  useEffect(() => { void reload() }, [reload])

  const n = page?.showings.length ?? 0
  const asked = showingPart != null && showingPart !== '' ? Number(showingPart) : null
  const cur = asked != null && Number.isFinite(asked) && asked >= 0 && asked < n ? asked : null
  // resume: with no showing in the URL, open the first unlabelled one (or the end of the queue)
  useEffect(() => {
    if (!page || cur != null) return
    if (page.next_unjudged != null) replaceHash(`review/queue/${queueId}/${page.next_unjudged}`)
  }, [page, cur, queueId])

  const go = (i: number) => navigate(`review/queue/${queueId}/${i}`)
  const nextUnjudgedAfter = (p: BlindQueuePage, from: number) => {
    for (let k = 1; k <= p.showings.length; k++) {
      const j = (from + k) % p.showings.length
      if (!p.showings[j].judged) return j
    }
    return null
  }

  async function answer(v: BlindVerdict) {
    if (cur == null || busy) return
    setBusy(true); setWriteErr(null)
    try {
      await postVerdict(queueId, String(cur), v as Verdict)
      const p = await reload()
      setFlash(`showing ${cur + 1} · ${SAY[v]} · written`)
      if (p) { const nx = nextUnjudgedAfter(p, cur); if (nx != null) go(nx); else navigate(`review/queue/${queueId}`) }
    } catch (e) { setWriteErr(errText(e)) } finally { setBusy(false) }
  }
  async function undo() {
    if (busy) return
    setBusy(true); setWriteErr(null)
    try {
      const ack = await postUndo(queueId) as { undone?: { target_ids?: (number | string)[] } | null }
      await reload()
      const t = ack?.undone?.target_ids?.[0]
      setFlash(t != null ? `undone · showing ${Number(t) + 1}` : 'nothing to undo in this queue')
      if (t != null) go(Number(t))
    } catch (e) { setWriteErr(errText(e)) } finally { setBusy(false) }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return
      if (e.altKey || e.metaKey) return
      const k = e.key.toLowerCase()
      if (k === 'z') { e.preventDefault(); void undo(); return }
      if (e.ctrlKey) return
      const w = WORDS.find(x => x.key.toLowerCase() === k)
      if (w) { e.preventDefault(); void answer(w.v); return }
      if (!page || cur == null) return
      if (e.key === 'ArrowRight') { e.preventDefault(); if (cur + 1 < n) go(cur + 1) }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); if (cur > 0) go(cur - 1) }
      else if (e.key === ' ') { e.preventDefault(); const nx = nextUnjudgedAfter(page, cur); if (nx != null) go(nx) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })   // re-bound every render so the handlers see the current showing

  const q = page?.queue
  const sub = q ? `queue ${q.id} · ${q.judged.toLocaleString()} of ${q.total.toLocaleString()} labelled` : `queue ${queueId}`
  return (
    <>
      <Header workspace="Review" page="Blind test" subtitle={sub} />
      <div className="rv-root">
        <div className="bt-page" data-testid="blind-page" data-queue={queueId} style={{ padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 12, overflow: 'auto' }}>
          {err && <div className="error-card" data-testid="blind-error"><h3>The blind queue {queueId} failed to load</h3><p className="mono">{err}</p></div>}
          {!page && !err && <div className="skeleton" style={{ height: 320 }} aria-label="loading" />}
          {page && q && (
            <>
              <div className="row" style={{ gap: 12, alignItems: 'center', flexWrap: 'wrap' }} data-testid="blind-progress" data-judged={q.judged} data-total={q.total}>
                <b className="mono">{q.name}</b>
                <div style={{ width: 260 }}><ProgressBar value={q.total ? q.judged / q.total : 0} label={`${q.judged.toLocaleString()} / ${q.total.toLocaleString()}`} /></div>
                <span className="mono small muted">{q.remaining.toLocaleString()} to go{q.pace_s != null ? ` · ${q.pace_s < 1 ? 'under 1' : q.pace_s.toFixed(0)} s a window · about ${Math.ceil((q.remaining * Math.max(1, q.pace_s)) / 60)} min left` : ''}</span>
                <InfoTip title="What is hidden, and why" testid="blind-hidden-info">
                  Hidden on purpose: {page.hidden}. Your answers are ordinary human labels (one row each over the window's span, marked as
                  this queue's); the comparison with the model is on Models › Results › against a blind human.
                </InfoTip>
                <span className="grow" style={{ flex: 1 }} />
                <Button size="sm" icon="external" testid="blind-to-results" onClick={() => navigate(`models/results/b2/${q.run_id}`)}>Models › Results</Button>
              </div>
              {cur == null ? (
                <div className="k-callout green" data-testid="blind-done" role="status" style={{ padding: 14 }}>
                  <b>Every window in this queue has an answer.</b> The comparison is on Models › Results ›
                  <Button variant="link" size="sm" onClick={() => navigate(`models/results/b2/${q.run_id}`)}>against a blind human</Button>.
                  Use ← and → (or open a showing) to change an answer.
                  {n > 0 && <Button size="sm" onClick={() => go(0)} testid="blind-first">Showing 1</Button>}
                </div>
              ) : (
                <ErrorBoundary label={`showing ${cur + 1}`}>
                  <BlindCard key={cur} queueId={queueId} showing={cur} n={n} own={page.showings[cur]?.verdict ?? null} busy={busy} onAnswer={answer} onUndo={undo}
                    onPrev={cur > 0 ? () => go(cur - 1) : undefined} onNext={cur + 1 < n ? () => go(cur + 1) : undefined} />
                </ErrorBoundary>
              )}
              {writeErr && <div className="error-card" data-testid="blind-write-refused"><h3>Not written</h3><p className="mono">{writeErr}</p><p>The database was not changed.</p></div>}
              {flash && <div className="mono small muted" data-testid="blind-flash">{flash}</div>}
            </>
          )}
        </div>
      </div>
    </>
  )
}

function BlindCard({ queueId, showing, n, own, busy, onAnswer, onUndo, onPrev, onNext }: {
  queueId: string; showing: number; n: number; own: BlindVerdict | null; busy: boolean
  onAnswer: (v: BlindVerdict) => void; onUndo: () => void; onPrev?: () => void; onNext?: () => void
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const width = Math.max(360, Math.round(size.width || 900))
  const [w, setW] = useState<BlindShowing | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    setW(null); setErr(null)
    getBlindShowing(queueId, showing, width).then(x => { if (alive) setW(x) })
      .catch(e => { console.error('blind showing failed to load', e); if (alive) setErr(errText(e)) })
    return () => { alive = false }
  }, [queueId, showing, width > 0 ? Math.round(width / 200) : 0])   // eslint-disable-line react-hooks/exhaustive-deps
  const keys = w ? Object.keys(w).concat(Object.keys(w.trace)).sort().join(' ') : ''
  return (
    <section className="rv-card" data-testid="blind-card" data-showing={showing} data-keys={keys} style={{ padding: 14 }}>
      <div className="rv-card-head" style={{ alignItems: 'baseline', gap: 10 }}>
        <h3 className="mono">showing {showing + 1} of {n.toLocaleString()}</h3>
        {w && <span className="mono" style={{ fontSize: 15, fontWeight: 700 }} data-testid="blind-duration">{w.scale_text}</span>}
        <span className="grow" style={{ flex: 1 }} />
        <span className="mono small muted">the window is shaded · {w ? `${w.pad_windows === 1 ? 'one window-length' : `${w.pad_windows} window-lengths`} of context either side` : ''} · time from the window's start</span>
      </div>
      <div ref={ref} style={{ width: '100%' }}>
        {err && <div className="error-card" data-testid="blind-card-error"><h3>Showing {showing + 1} failed to load</h3><p className="mono">{err}</p></div>}
        {!w && !err && <div className="skeleton" style={{ height: 300 }} aria-label="loading" />}
        {w && <BlindTracePlot w={w} width={width} />}
      </div>
      <div className="row" style={{ gap: 8, marginTop: 10, flexWrap: 'wrap', alignItems: 'center' }} data-testid="blind-verdicts">
        {WORDS.map(x => (
          <Button key={x.v} variant={own === x.v ? 'primary' : x.primary ? 'default' : 'ghost'} size={x.primary ? 'lg' : 'md'} disabled={busy} disabledReason="writing the last answer"
            onClick={() => onAnswer(x.v)} testid={`blind-${x.v}`} aria-pressed={own === x.v}>
            <span className="mono" style={{ opacity: 0.7, marginRight: 6 }}>{x.key}</span>{x.label}
          </Button>
        ))}
        <span className="grow" style={{ flex: 1 }} />
        <Button size="sm" icon="undo" onClick={onUndo} disabled={busy} disabledReason="writing" testid="blind-undo">Z undo</Button>
        <Button size="sm" onClick={onPrev} disabled={!onPrev} disabledReason="the first showing" testid="blind-prev">← previous</Button>
        <Button size="sm" onClick={onNext} disabled={!onNext} disabledReason="the last showing" testid="blind-next">next →</Button>
      </div>
      <div className="mono small muted" style={{ marginTop: 6 }} data-testid="blind-own">
        {own ? `your answer to this showing: ${SAY[own]} (press another key to change it)` : 'no answer yet'}
        {' · '}I interesting · N not interesting · U can't tell · A artifact · Z undo · ← → move · space the next unlabelled
      </div>
    </section>
  )
}

const H = 300, PAD_L = 52, PAD_B = 24, PAD_T = 8

/** The window's raw trace in mV, shaded, context either side, the time axis RELATIVE to the window's start (so the
 *  place in the recording is not read off it). Also the step-through's plot on Models › Results. */
export function BlindTracePlot({ w, width, testid = 'blind-plot' }: { w: BlindShowing; width: number; testid?: string }) {
  const t0 = w.window.t0_s
  const t = useMemo(() => w.trace.t.map(x => x - t0), [w, t0])
  const vals = w.trace.v.filter((x): x is number => x != null && Number.isFinite(x))
  if (!t.length || !vals.length) {
    return <div className="error-card" data-testid="blind-plot-empty"><h3>No trace to draw</h3><p className="mono">{w.trace.reason ?? 'the bridge returned no samples for this window'}</p></div>
  }
  const lo = Math.min(...vals), hi = Math.max(...vals)
  const pad = (hi - lo) * 0.06 || 0.05
  const x = scaleLinear().domain([w.trace.t0_s - t0, w.trace.t1_s - t0]).range([PAD_L, width - 8])
  const y = scaleLinear().domain([lo - pad, hi + pad]).range([H - PAD_B, PAD_T])
  const ticks = y.ticks(5)
  const dec = Math.max(0, -Math.floor(Math.log10(Math.max(1e-9, (ticks[1] ?? 1) - (ticks[0] ?? 0)))))
  return (
    <svg width={width} height={H} role="img" aria-label={`the window's raw trace in ${w.unit ?? 'its unit'}, shaded, with context either side`} data-testid={testid}>
      <rect x={x(0)} y={PAD_T} width={Math.max(1, x(w.duration_s) - x(0))} height={H - PAD_B - PAD_T} fill="var(--amber-bg, #fdf3d0)" data-testid="blind-window-band" />
      {ticks.map(v => (
        <g key={v}>
          <line x1={PAD_L} x2={width - 8} y1={y(v)} y2={y(v)} stroke="var(--line, #e6e6e6)" strokeWidth={0.5} />
          <text x={PAD_L - 5} y={y(v) + 3} textAnchor="end" style={{ fontSize: 10 }}>{v.toFixed(dec)}</text>
        </g>
      ))}
      <text x={4} y={14} style={{ fontSize: 10 }}>{w.unit ?? ''}</text>
      <EnvelopePath t={t} v={w.trace.v} x={x} y={y} stroke="var(--text, #111)" width={1.3} testid="blind-trace" />
      <RelAxis x={x} y={H - PAD_B} t0={w.trace.t0_s - t0} t1={w.trace.t1_s - t0} />
    </svg>
  )
}

/** Time from the window's start, in seconds for a short view and minutes for a long one (the place in the recording
 *  is deliberately not shown). */
function RelAxis({ x, y, t0, t1 }: { x: ReturnType<typeof scaleLinear<number, number>>; y: number; t0: number; t1: number }) {
  const mins = t1 - t0 > 240
  const k = mins ? 60 : 1
  const s = scaleLinear().domain([t0 / k, t1 / k])
  const [r0, r1] = x.range()
  return (
    <g className="time-axis" data-testid="blind-time-axis">
      <line x1={r0} x2={r1} y1={y} y2={y} stroke="var(--border)" />
      {s.ticks(8).map(v => (
        <g key={v}>
          <line x1={x(v * k)} x2={x(v * k)} y1={y} y2={y + 4} stroke="var(--border)" />
          <text x={x(v * k)} y={y + 15} textAnchor="middle" style={{ fontSize: 10 }}>{v > 0 ? '+' : v < 0 ? '−' : ''}{Math.abs(v)} {mins ? 'min' : 's'}</text>
        </g>
      ))}
    </g>
  )
}
