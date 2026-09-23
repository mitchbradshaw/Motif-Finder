/* review.inspector — one candidate at a time (frames 1, 1b, 3, 4, 5 blind, 6 seed promoted). Verdicts are given
 * only here and on the cluster page (P6). Deep links: ?rail=queue|evidence|both · ?pop=other-channels|queues|blind|shortcuts
 * · ?state=promoted · ?pad=30|120|300. Blind queues (q-18, q-19) are a state of this page (P20). */
import { useEffect, useRef, useState } from 'react'
import { navigate, setQuery } from '../state'
import { Chip, Icon, InfoTip, MiniTrace, cx, fmtInt, recordDemoWrite, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { useToast } from '../shell/Toast'
import { VOCABULARY, getItem, postPromote, postUndo, postVerdict, type ItemDetail, type QueueData, type QueueRow, type Verdict } from '../api/review'
import { Shell, useBlind, useRails, type MicroStat } from './Shell'
import { useReviewKeys } from './keys'
import { goUnit, nextUnjudgedAfter, relTime, step } from './queue'
import {
  AnnotateCard, ArtifactPill, ContextCard, EvidenceRail, NearestFamiliesCard, Pill, PromotionPanel, ShapeCard, VerdictCard, editInExplore, statusDot, statusText, useNow,
} from './parts'
import { Loading, NotFound, previousLines } from './common'
import {
  VERDICT_LABEL, amendWrite, applyWrite, clearWriteError, commitRedo, commitUndo, commitWrite, effective, getRecords, getWriteError, key, lastLive, mintExemplar, nextRedo,
  patchRecord, rawRecord, releaseExemplar, resend, useAutoAdvance, useDrafts, usePad, useRecords, useReviewVersion, useStack, useWriteError, type Draft, type VerdictRecord,
} from './store'

const ADVANCE_MS = 350

export function Inspector({ data, itemId }: { data: QueueData; itemId: string }) {
  const row = data.rows.find(r => r.id === itemId)
  if (!row) return <NotFound data={data} what={itemId} />
  return <InspectorItem data={data} row={row} />
}

function InspectorItem({ data, row }: { data: QueueData; row: QueueRow }) {
  const { queue } = data
  const q = queue.id, id = row.id
  const version = useReviewVersion()
  const det = useSourced(() => getItem(q, id), [q, id, version])
  const records = useRecords()
  const stack = useStack()
  const writeError = useWriteError()
  const [blind, setBlind] = useBlind(q, queue.blind)
  const [auto] = useAutoAdvance()
  const [pad, setPad] = usePad()
  const [padQ] = useQueryState<string>('pad', '')
  const [state] = useQueryState<string>('state', '')
  const [drafts, setDrafts] = useDrafts()
  const [flash, setFlash] = useState<Verdict | null>(null)
  const [overlay, setOverlay] = useState('')
  const toast = useToast()
  const rails = useRails()
  const now = useNow(1000)
  const confirmRef = useRef<(() => void) | null>(null)
  const timers = useRef<number[]>([])
  useEffect(() => () => { timers.current.forEach(t => window.clearTimeout(t)) }, [])
  useEffect(() => { if (padQ === '30' || padQ === '120' || padQ === '300') setPad(padQ) }, [padQ, setPad])
  // the refusal card belongs to the item it was raised on: moving on clears it, a new failure re-raises it
  useEffect(() => { setOverlay(''); clearWriteError() }, [id])

  const d = det.data && det.data.entry.id === id ? det.data : null
  const rec = effective(records, row)
  const k = key(q, id)
  const draft: Draft = drafts[k] ?? { tags: rec?.tags ?? row.tags, note: rec?.note ?? '' }
  const promoted = state === 'promoted' && rec?.verdict === 'seed' && !!rec.exemplarId
  const binary = queue.verdictKeys === 'binary+classes'
  const isWindow = row.unit === 'window'
  const masked = blind && !rec
  const unit = { kind: 'item' as const, id }

  const say = (text: string) => toast.push({ text })
  /** Loud, and never a blank: the bridge's own refusal text, beside the red card the render puts up. */
  const refused = () => { const f = getWriteError(); toast.push({ kind: 'error', text: `not written · ${f?.label ?? 'write'} · ${f?.message ?? 'the bridge refused it'}` }) }
  const later = (fn: () => void, ms: number) => { timers.current.push(window.setTimeout(fn, ms)) }
  const advance = () => goUnit(q, nextUnjudgedAfter(data, getRecords(), unit))

  const setDraft = (next: Draft) => {
    setDrafts(prev => ({ ...prev, [k]: next }))
    if (rec) patchRecord(q, id, rec, { tags: next.tags, note: next.note })
  }

  /** A keypress writes to the DATABASE and only then to the session stack. `seed` goes through the
   *  promotion door (P21: the verdict and the Library entry in one core call); every other verdict is one
   *  POST. A refused write returns null, leaves the session untouched, and is shown as a red card. */
  async function write(v: Verdict, className: string | undefined, kind: 'verdict' | 'class' | 'promotion', opts: { advance: boolean; flash?: boolean }): Promise<VerdictRecord | null> {
    const before = rawRecord(q, id)
    const next: VerdictRecord = { verdict: v, className, blind, at: Date.now(), tags: draft.tags, note: draft.note }
    const minted = v === 'seed' && !rec?.exemplarId
    if (v === 'seed') { next.exemplarId = rec?.exemplarId ?? mintExemplar(); next.family = d?.nearest?.[0] && d.nearest[0].d <= 0.3 ? d.nearest[0].id : null }
    const note = draft.note.trim() || undefined
    // the Annotate card's tags go to the database with the verdict, through
    // whatever table the queue's `writes_to` names (fixup-a item 9)
    const tags = draft.tags.length ? draft.tags : undefined
    const send = () => v === 'seed' ? postPromote(q, id, 'seed', { note, tags }) : postVerdict(q, id, v, { note, tags })
    const w = await commitWrite(send, { queueId: q, items: [id], kind, verdict: v, className, label: `${id} · ${VERDICT_LABEL[v]}`, before: { [k]: before }, after: { [k]: next } })
    if (!w) { if (minted && next.exemplarId) releaseExemplar(next.exemplarId); refused(); return null }
    if (v === 'seed') {
      // P21: the seed verdict itself creates the Library exemplar; the panel only chooses its family
      if (minted) recordDemoWrite('library', 'exemplar.create', { id: next.exemplarId, from: `${q}/${id}`, family: next.family, recording: row.recording, channel: row.channel, span_h: [row.startH, +(row.startH + row.durationS / 3600).toFixed(4)], blind })
      return next
    }
    if (opts.flash !== false) { setFlash(v); later(() => setFlash(null), ADVANCE_MS) }
    if (opts.advance && auto) later(advance, ADVANCE_MS)
    return next
  }

  const verdict = async (v: Verdict) => {
    if (promoted) return say('confirm or undo the promotion first (Enter / Ctrl Z)')
    if (binary && (v === 'seed' || v === 'artifact' || v === 'unsure')) return say('this queue takes binary verdicts and classes')
    const next = await write(v, rec?.className, v === 'seed' ? 'promotion' : 'verdict', { advance: true })
    if (!next) return
    if (v === 'seed') {
      setQuery({ state: 'promoted' }, true)
      say(`seed · exemplar ${next.exemplarId} created in the Library · auto-advance paused`)
    }
  }

  /* A class key carries a VERDICT with it, and THAT is what goes to the database. The class name itself
   * has no field in any of the contract's write bodies, so it stays a session label; a keypress that
   * changes only the class therefore posts nothing, adds no audit row, and says so. */
  const klass = async (ck: string) => {
    const c = VOCABULARY.classes.find(x => x.key === ck)
    if (!c) return
    if (promoted) return say('confirm or undo the promotion first (Enter / Ctrl Z)')
    if (!rec) {
      const v: Verdict = c.informative ? 'interesting' : 'artifact'
      if (!await write(v, c.name, 'class', { advance: true })) return
      return say(`class ${c.name} · implies ${VERDICT_LABEL[v]} · written`)
    }
    if (rec.className === c.name) {
      applyWrite({ queueId: q, items: [id], kind: 'class', verdict: rec.verdict, label: `${id} · class cleared`, before: { [k]: rawRecord(q, id) }, after: { [k]: { ...rec, className: undefined, at: Date.now() } } })
      return say(`class ${c.name} cleared · verdict stays ${VERDICT_LABEL[rec.verdict]} (the class is a session label)`)
    }
    const v: Verdict = !c.informative && rec.verdict !== 'artifact' ? 'artifact' : rec.verdict
    if (v !== rec.verdict) {
      if (!await write(v, c.name, 'class', { advance: false, flash: false })) return
      return say(`${c.name} is non-informative — artifact written (Ctrl Z reverts)`)
    }
    applyWrite({ queueId: q, items: [id], kind: 'class', verdict: v, className: c.name, label: `${id} · ${c.name}`, before: { [k]: rawRecord(q, id) }, after: { [k]: { ...rec, verdict: v, className: c.name, blind, at: Date.now() } } })
    say(`class ${c.name} added to the ${VERDICT_LABEL[v]} verdict (the class is a session label)`)
  }

  /* Ctrl-Z posts to the server, which restores the PRIOR verdict out of its audit row. The client does not
   * invent a reversal: only `review_audit.payload_json` knows whether this reverses to unjudged or back to
   * the verdict that was there before. The stack is marked undone only once the POST was accepted. */
  const undo = async () => {
    const w = lastLive(q)
    if (!w) return say('nothing to undo in this queue')
    if (!await commitUndo(() => postUndo(q), w)) return refused()
    if (w.kind === 'batch') { navigate(`review/queue/${q}/cluster/${w.clusterNo}?state=undone`); return }
    if (w.kind === 'promotion') {
      const ex = (w.after[key(q, w.items[0])] as VerdictRecord | null)?.exemplarId
      if (ex) { releaseExemplar(ex); recordDemoWrite('library', 'exemplar.remove', { id: ex, from: `${q}/${w.items[0]}`, reason: 'promotion undone' }) }
      say(`promotion undone · exemplar ${ex} removed`)
      if (w.items[0] === id) setQuery({ state: null }, true)
    } else say(`undone · ${w.label}`)
    if (!w.items.includes(id)) navigate(`review/queue/${q}/${w.items[0]}`)
  }
  const redo = async () => {
    const w = nextRedo(q)
    if (!w) return say('nothing to redo')
    if (!await commitRedo(() => resend(q, w), w)) return refused()
    say(`redone · ${w.label}`)
    if (w.kind === 'batch') navigate(`review/queue/${q}/cluster/${w.clusterNo}`)
    else if (w.kind === 'promotion') navigate(`review/queue/${q}/${w.items[0]}?state=promoted`)
    else if (!w.items.includes(id)) navigate(`review/queue/${q}/${w.items[0]}`)
  }

  const confirmPromotion = (family: string | null, familyName?: string) => {
    if (!rec || !d) return
    const w = [...stack].reverse().find(x => x.kind === 'promotion' && x.items[0] === id && !x.undone)
    const after = { ...rec, family, familyName }
    if (w) amendWrite(w.id, { [k]: after }, { item: id, family, familyName })
    recordDemoWrite('library', 'exemplar.family', { id: rec.exemplarId, family: family === 'new' ? `new: ${familyName}` : family, span: [row.startH, +(row.startH + row.durationS / 3600).toFixed(4)], recording: row.recording, channel: row.channel, contentHash: `sha1:${row.seed.toString(16)}…`, recipeHash: d.evidence.origin.recipeHash, blind })
    say(`exemplar ${rec.exemplarId} confirmed ${family === 'new' ? `in new family ${familyName}` : family ? `in ${family}` : 'with no family yet'}`)
    setQuery({ state: null }, true)
    advance()
  }

  // deep link ?state=promoted renders the promotion without a keypress (frame 6)
  useEffect(() => {
    if (state === 'promoted' && d && rec?.verdict !== 'seed') {
      if (binary) { setQuery({ state: null }, true); return }
      void write('seed', rec?.className, 'promotion', { advance: false })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, d?.entry.id])

  useReviewKeys({
    verdict, klass, undo, redo,
    skip: () => { if (promoted) return say('confirm or undo the promotion first (Enter / Ctrl Z)'); goUnit(q, step(data, unit, 1)) },
    enter: () => { if (promoted && confirmRef.current) { confirmRef.current(); return true } return false },
    next: () => { const u = step(data, unit, 1); if (u) goUnit(q, u); else say('this is the last item in the demo fixture') },
    prev: () => { const u = step(data, unit, -1); if (u) goUnit(q, u); else say('this is the first item in the queue fixture') },
    edit: isWindow ? () => say('windows have no span to edit') : () => d && editInExplore(d),
    rails: rails.toggleBoth,
  })

  const historyCount = stack.filter(w => !w.undone && w.items.includes(id)).length + (row.baseVerdict ? 1 : 0)
  const fam = d?.nearest?.[0]
  const micro: MicroStat[] = isWindow && blind
    ? [{ value: '', label: 'model', icon: rec ? 'eye' : 'eye-off', tone: 'purple', section: 'model', title: rec ? `model ${row.modelCall?.className ?? 'n/a'}` : 'model call hidden until verdict' },
       { value: '', label: 'family', icon: rec ? 'eye' : 'eye-off', tone: 'purple', section: 'family', title: 'family affinity hidden until verdict' },
       { value: d?.artifact?.level ?? '…', label: 'artifact', tone: d?.artifact?.level === 'low' ? 'green' : 'amber', section: 'artifact' },
       { value: row.sampleIndex ? `${row.sampleIndex}/${queue.total}` : fmtInt(historyCount), label: row.sampleIndex ? 'sample' : 'history', section: 'origin' }]
    : [
       ...(row.unit === 'detection' ? [masked ? { value: '', label: 'score', icon: 'eye-off' as const, tone: 'purple' as const, section: 'detection' } : { value: row.score != null ? row.score.toFixed(2) : row.d != null ? row.d.toFixed(2) : '—', label: row.score != null ? 'score' : 'match d', section: 'detection' }] : [{ value: 'n/a', label: 'score', tone: 'muted' as const, title: 'human spans have no score' }]),
       ...(row.queueId === 'q-12' && !masked ? [{ value: '6.1×', label: '× null', section: 'detection' }] : []),
       masked ? { value: '', label: 'family d', icon: 'eye-off' as const, tone: 'purple' as const, section: 'family' } : { value: fam ? fam.d.toFixed(2) : '…', label: `${fam?.id ?? 'family'} d`, section: 'family' },
       { value: d?.artifact?.level ?? '…', label: 'artifact', tone: d?.artifact?.level === 'low' ? 'green' : 'amber', section: 'artifact' },
       { value: String(historyCount), label: 'history', section: 'history' },
      ]

  const historyText = stack.filter(w => !w.undone && w.items.includes(id)).map(w => `${VERDICT_LABEL[w.verdict ?? 'interesting']}${w.className ? ` (${w.className})` : ''} · ${relTime(w.at, now)}`).reverse().join('; ') || (row.baseVerdict ? `${VERDICT_LABEL[row.baseVerdict]} · earlier session` : 'none')
  const evidence = d ? <EvidenceRail d={d} blind={blind} judged={!!rec} historyVerdicts={historyText} /> : <Loading />
  const narrow = rails.left || rails.right

  return (
    <Shell data={data} unit={unit} blind={blind} setBlind={setBlind} paused={promoted} micro={micro} evidence={evidence}
      evidenceTitle={`${id}${row.detectionId ? ` · ${row.detectionId}` : ''}`}>
      {writeError && <div className="error-card" data-testid="write-refused">
        <h3><Icon name="alert-circle" /> Not written · {writeError.label}{writeError.status ? ` · HTTP ${writeError.status}` : ''}</h3>
        <p className="mono">{writeError.message}</p>
        <p>The database was not changed — what the page shows is whatever it held before.</p>
      </div>}
      {det.error && <div className="error-card" data-testid="item-error"><h3>{id} failed to load</h3><p className="mono">{det.error.message}</p></div>}
      {!d && !det.error && <Loading />}
      {d?.refused && <div className="error-card" data-testid="held-out-refusal"><h3><Icon name="lock" /> {id} is refused</h3><p>{d.refused}</p></div>}
      {d && !d.refused && (
        <div className={cx('rv-stack', det.loading && 'stale')} data-testid="inspector" data-item={id} data-blind={blind ? '1' : '0'}>
          <div className="rv-title" data-testid="title-row">
            <h1 className="mono">{id}</h1>
            {row.unit === 'detection' && <Chip size="sm" tone="blue">detection</Chip>}
            {row.unit === 'human span' && <Chip size="sm" tone="green">human span</Chip>}
            {isWindow && <><Chip size="sm" tone="grey">window</Chip><Chip size="sm" tone="purple">{row.block === 'test' ? 'test block' : 'train block'}</Chip></>}
            {rec?.exemplarId && <Chip size="sm" tone="green" testid="exemplar-chip">exemplar {rec.exemplarId}</Chip>}
            <span className="grow" />
            <Pill dot={statusDot(rec)} label="status" value={statusText(rec)} tone={rec?.verdict === 'seed' ? 'green' : undefined} shrink testid="pill-status" />
            {isWindow ? (
              masked ? <Pill icon="eye-off" label="model call" value="hidden until verdict" tone="purple" testid="pill-model" />
                : row.modelCall ? <Pill icon="eye" label="model call" value={`${row.modelCall.className} · p ${row.modelCall.p.toFixed(2)}`} tone="purple" testid="pill-model" />
                  : <Pill icon="flask" label="model call" value="none · training windows" testid="pill-model" />
            ) : <>
              {row.unit === 'detection'
                ? masked ? <Pill icon="eye-off" label="score" value="hidden until verdict" tone="purple" testid="pill-score" />
                  : <Pill icon="target" label={row.score != null ? 'score' : 'match'} value={row.score != null ? `${row.score.toFixed(2)}${q === 'q-12' ? ' · 6.1× null' : ''}` : `d ${row.d?.toFixed(2)} · seed search`} testid="pill-score" />
                : <Pill icon="target" label="score" value="n/a · human span" testid="pill-score" title="human spans carry no machine score" />}
              {masked ? <Pill icon="eye-off" label="family" value="hidden until verdict" tone="purple" testid="pill-family" />
                : fam && <Pill dot={fam.colour} label="family" value={`${fam.id} d ${fam.d.toFixed(2)}`} testid="pill-family" />}
            </>}
            <ArtifactPill a={d.artifact} short={narrow} />
          </div>
          <div className="rv-meta mono" data-testid="meta-line">{metaLine(d, narrow)}</div>

          <ContextCard d={d} title={isWindow ? 'Window in context' : row.unit === 'human span' ? 'Span in context' : 'Candidate in context'} pad={pad} setPad={p => { setPad(p); if (padQ) setQuery({ pad: null }, true) }}
            bandLabel={isWindow ? `${id} · ${row.durationS} s` : `${id} · ${row.durationS.toFixed(1)} s`} canEdit={!isWindow} />

          <div className="rv-row2">
            <ShapeCard d={d} family={masked ? null : (d.nearest.find(f => f.id === overlay) ?? d.nearest[0] ?? null)} blind={masked || isWindow} rows={data.rows} />
            {promoted && rec
              ? <PromotionPanel d={d} rec={rec} onUndo={undo} onConfirm={confirmPromotion} confirmRef={confirmRef} />
              : isWindow && blind ? <RevealCard data={data} current={row} now={now} />
                : masked ? <MaskedFamilies />
                  : <NearestFamiliesCard d={d} overlay={overlay || d.nearest[0]?.id || ''} setOverlay={setOverlay} />}
          </div>

          <VerdictCard selected={rec?.verdict ?? null} flash={flash} binary={binary} onVerdict={verdict} onSkip={() => goUnit(q, step(data, unit, 1))}
            previous={previousLines(data, promoted ? stack.filter(w => !(w.kind === 'promotion' && w.items[0] === id)) : stack, now)} undo={{ can: !!lastLive(q), run: undo }} />
          <AnnotateCard draft={draft} setDraft={setDraft} className={rec?.className} onClass={klass} />
        </div>
      )}
    </Shell>
  )
}

function metaLine(d: ItemDetail, narrow: boolean) {
  const e = d.entry, q = d.queue
  const endH = e.startH + e.durationS / 3600
  if (e.unit === 'window') {
    const h = (x: number) => x.toFixed(2)
    return [e.recording, e.channel, `${h(e.startH)} → ${h(endH)} h`, `${e.durationS} s window`,
      q.source === 'model-verification' ? `stratified test sample, ${e.sampleIndex} of ${q.total}` : `train block · ${d.evidence.origin.windowSet}`,
      q.model ? `candidate ${q.model}` : null].filter(Boolean).join(' · ')
  }
  const h = (x: number) => x.toFixed(3)
  const base = [e.recording, e.channel, `${h(e.startH)} → ${h(endH)} h`, `${e.durationS.toFixed(1)} s`]
  if (e.unit === 'human span') return [...base, 'annotation, taken for Review'].join(' · ')
  if (q.source === 'seed-search') return [...base, `run ${q.runId} seed search, exemplar ${q.exemplar}`, `match d ${e.d?.toFixed(2)}`].join(' · ')
  /* Neither clause is printed unless there is something to print. This read
   * `run undefined · rank undefined of 30 by score` on every item (fixup-a
   * item 7) — and the ordering claim is gone with it: the resolver orders by
   * detection id, so a position in the queue is not a rank by score. */
  const runId = e.runId ?? q.runId
  return [...base,
    runId ? `run ${runId}` : null,
    e.rank ? `rank ${e.rank} of ${fmtInt(q.total)}` : null,
  ].filter(Boolean).join(' · ')
}

function MaskedFamilies() {
  return (
    <section className="rv-card" data-testid="nearest-families-masked">
      <div className="rv-card-head"><Icon name="eye-off" size={15} className="rv-purple" /><h3>Nearest families</h3><span className="grow" /><span className="mono sm rv-purple">hidden until verdict</span></div>
      <div className="rv-masked mono muted">Family affinity is machine opinion: it is hidden in a blind queue until you give a verdict. Artifact likelihood stays visible.</div>
    </section>
  )
}

/** "Previous window, revealed" (frame 5): your call beside the model's, for the last judged window. No running agreement (§10.6). */
function RevealCard({ data, current, now }: { data: QueueData; current: QueueRow; now: number }) {
  const records = useRecords()
  const stack = useStack()
  const q = data.queue.id
  const last = [...stack].reverse().find(w => w.queueId === q && !w.undone)
  const lastRow = last ? data.rows.find(r => r.id === last.items[0]) : [...data.rows].reverse().find(r => r.baseVerdict && data.rows.indexOf(r) < data.rows.indexOf(current))
  const rec = lastRow ? effective(records, lastRow) : null
  const you = rec ? rec.className ?? VERDICT_LABEL[rec.verdict] : null
  const call = lastRow?.modelCall
  const agree = !rec || !call ? null : rec.className ? rec.className === call.className : rec.verdict === 'artifact' ? call.className === 'electrode artifact' ? true : false : null
  return (
    <section className="rv-card" data-testid="reveal-card">
      <div className="rv-card-head"><Icon name="eye" size={15} className="rv-purple" /><h3>Previous window, revealed</h3><span className="grow" />
        <InfoTip title="Blind verification">After each verdict the previous window is revealed: your call beside the model's. Running agreement is shown only in Models › Registry, so it cannot steer the next verdict.</InfoTip></div>
      {lastRow && rec ? (
        <div className="rv-reveal">
          <div className="rv-reveal-box">
            <MiniTrace values={lastRow.thumb} width={70} height={48} ground="white" zeroLine={false} />
            <div className="kv mono">
              <b>{lastRow.id}</b>
              <div><span className="muted">you</span> <b>{you}</b>{last && <span className="muted"> · {relTime(last.at, now)}</span>}</div>
              <div><span className="muted">model</span> <b>{call ? `${call.className} · p ${call.p.toFixed(2)}` : 'no model yet · training windows'}</b></div>
            </div>
            <span className="grow" />
            {agree === true && <Chip size="sm" tone="green" testid="reveal-agree">agree</Chip>}
            {agree === false && <Chip size="sm" tone="amber" testid="reveal-differs">differs</Chip>}
            {agree === null && call && <Chip size="sm" tone="grey" title="no class was given, so the calls cannot be compared">no class given</Chip>}
          </div>
          <div className="mono sm">The model's call on this window stays hidden until you press a key.</div>
          <div className="mono sm muted">Running agreement is shown in <button type="button" className="rv-inline-link" onClick={() => navigate('models/registry')}>Models › Registry</button>, not here.</div>
          <div className="mono sm muted" style={{ marginTop: 'auto' }}>artifact likelihood is not blinded</div>
        </div>
      ) : <div className="rv-masked mono muted">No window judged yet in this queue. After your first verdict the window is revealed here.</div>}
    </section>
  )
}
