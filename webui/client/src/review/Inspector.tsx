/* review.inspector — one candidate at a time (frames 1, 1b, 3, 4, 5 blind, 6 seed promoted). Verdicts are given
 * only here and on the cluster page (P6). Deep links: ?rail=queue|evidence|both · ?pop=other-channels|queues|blind|shortcuts
 * · ?state=promoted · ?pad=30|120|300. Blind queues (q-18, q-19) are a state of this page (P20). */
import { useEffect, useRef, useState } from 'react'
import { navigate, setQuery } from '../state'
import { Button, Chip, Icon, InfoTip, MiniTrace, cx, fmtInt, recordDemoWrite, useQueryState } from '../kit'
import { useAbortableSourced, useSourced } from '../api/seam'
import { useSize } from '../charts/useSize'
import { useToast } from '../shell/Toast'
import { plotPx } from './axis'
import { VOCABULARY, carryOf, clearItemCacheExcept, getItem, itemHeld, peekItem, prefetchItemThen, useThumbs, useQueuePeaks, postPromote, postUndo, postVerdict, type CarryFields, type ItemDetail, type QueueData, type QueueRow, type Verdict } from '../api/review'
import { Shell, useBlind, useRails, type MicroStat } from './Shell'
import { useReviewKeys } from './keys'
import { goUnit, indexOf, isJudged, judged, judgedRecord, nextUnjudgedAfter, queueHoldsAny, relTime, step, units } from './queue'
import { prefetchIds } from './prefetch'
import {
  AnnotateCard, ArtifactPill, ContextCard, EvidenceRail, NearestFamiliesCard, Pill, PromotionPanel, ShapeCard, VerdictCard, editInExplore, statusDot, statusText, useNow,
} from './parts'
import { Loading, NotFound, previousLines } from './common'
import { SuspectedArtifactCard } from './SuspectedArtifact'
import {
  VERDICT_LABEL, amendWrite, applyWrite, bumpReviewVersion, clearWriteError, commitRedo, commitUndo, commitWrite, effective, getRecords, writesInFlight, getWriteError, key, lastLive, nextRedo,
  patchRecord, rawRecord, releaseExemplar, resend, useAutoAdvance, useDrafts, usePad, useRecords, useReviewVersion, useStack, useWriteError, type Draft, type VerdictRecord,
} from './store'

/** night-review: how long the verdict flash shows before auto-advance moves on — counted from the bridge's accept, so
 *  a few frames, not the 350 ms it was (the researcher: "no noticeable lag between items"). The "previous" line
 *  under the verdict buttons names the write that landed. */
const ADVANCE_MS = 60
/** night-a: an item not yet held is read once it has been on screen this long, so stepping fast through a 10 k queue
 *  sends no read for the items passed (40 presses left the bridge 25-49 s of item reads behind) */
const STEP_SETTLE_MS = 150

export function Inspector({ data, itemId }: { data: QueueData; itemId: string }) {
  // review-carry: a detection that is one of an item's overlap set opens that item (a link by detection id from
  // Discovery or Explore names whichever detection it was)
  const row = data.rows.find(r => r.id === itemId)
    ?? data.rows.find(r => (carryOf(r).members ?? []).some(m => String(m) === itemId))
  const [corrected] = useQueryState<string>('corrected', '')
  if (!row) return corrected ? <CorrectedItem data={data} itemId={itemId} /> : <NotFound data={data} what={itemId} />
  return <InspectorItem data={data} row={row} />
}

/** edit-span: the item whose span was just corrected from Review. The correction is a human span over the detection,
 *  so the queue now counts the detection as already covered by a human and no longer serves it; the editor's Save
 *  returns with `?corrected=1` and the item is read on its own, so the researcher lands back on what they corrected
 *  (with the correction's verdict as its prior) instead of on "No 101 in queue 2". Only on that return: a plain link
 *  to an id the queue does not hold is still the loud not-found card. */
function CorrectedItem({ data, itemId }: { data: QueueData; itemId: string }) {
  const read = useSourced(() => getItem(data.queue.id, itemId).catch(() => ({ data: null, source: 'live' as const })),
    [data.queue.id, itemId])
  if (read.loading) return <Loading />
  const entry = read.data?.entry
  if (!entry) return <NotFound data={data} what={itemId} />
  const row: QueueRow = { thumb: [], family: '', judged: false, ...entry }
  return <InspectorItem data={data} row={row} />
}

function InspectorItem({ data, row }: { data: QueueData; row: QueueRow }) {
  const { queue } = data
  const q = queue.id, id = row.id
  const version = useReviewVersion()
  const peaks = useQueuePeaks(data)      // fix round B1: the reference bar's ends, worked out off the rows read
  const [pad, setPad] = usePad()
  // The traces are fetched at the width of the column that will draw them (fixup-g): measured, never guessed,
  // so the bridge serves at least one point per device pixel; and over the padding shown, so the context is
  // exactly the window drawn. Nothing is fetched until the column has a width (one frame).
  const [measureRef, column] = useSize<HTMLDivElement>()
  const px = plotPx(column.width, window.devicePixelRatio || 1)
  const det = useAbortableSourced(signal => {
    if (!px) return Promise.resolve({ data: null, source: 'live' as const })
    const opts = { px, padS: +pad }
    // night-review: an item already read OR being read (the window below) joins its read at once, with no settle
    if (peekItem(q, id, opts) || itemHeld(q, id, opts)) return getItem(q, id, opts)
    return new Promise<void>(res => window.setTimeout(res, STEP_SETTLE_MS))
      .then(() => signal.aborted ? Promise.reject(new DOMException('superseded', 'AbortError')) : getItem(q, id, opts))
  }, [q, id, version, px, pad])
  const records = useRecords()
  const stack = useStack()
  const writeError = useWriteError()
  const [blind, setBlind] = useBlind(q, queue.blind)
  const [auto] = useAutoAdvance()
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
  // night-a: a delayed advance belongs to the item it was set on. I then two quick arrows landed on the item after
  // the judged one: its timer (set only after the POST came back) fired after the researcher had moved on.
  const onItem = useRef(id)
  onItem.current = id
  useEffect(() => { timers.current.forEach(t => window.clearTimeout(t)); timers.current = []; setFlash(null) }, [id])
  useEffect(() => { if (padQ === '30' || padQ === '120' || padQ === '300') setPad(padQ) }, [padQ, setPad])
  // the refusal card belongs to the item it was raised on: moving on clears it, a new failure re-raises it
  useEffect(() => { setOverlay(''); clearWriteError() }, [id])

  // AR: a step paints from the item cache (prefetched below) in the same frame, before the read resolves; the
  // read itself is then answered from the same cache entry
  const peeked = px ? peekItem(q, id, { px, padS: +pad }) : null
  const d = (det.data && det.data.entry.id === id ? det.data : null) ?? (peeked && peeked.entry.id === id ? peeked : null)
  // AR: the moment this item is on screen, read the ones a key press can go to next, at the width and padding this
  // card asks for, so the step is a cache hit. night-review: the window is the next five unjudged items (a run of
  // verdicts), the very next unit (an arrow) and the previous one, read ONE AT A TIME nearest first — the next item
  // is in hand first, and the bridge never has the whole window in flight at once. Still only from an item the
  // researcher stopped on (STEP_SETTLE_MS), and the chain stops the moment they move: an item passed by fast
  // stepping is never read.
  useEffect(() => {
    if (!d || !px) return
    const opts = { px, padS: +pad }
    let live = true
    const t = window.setTimeout(async () => {
      const list = units(data)
      const recs = getRecords()
      for (const pid of prefetchIds(list, indexOf(list, { kind: 'item', id }), i => isJudged(data, recs, list[i]))) {
        if (!live) return
        await prefetchItemThen(q, pid, opts)
      }
    }, STEP_SETTLE_MS)
    return () => { live = false; window.clearTimeout(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d?.entry.id, px, pad, q])
  const rec = effective(records, row)
  const jrec = judgedRecord(records, row)      // night-a: what the database holds here (a prior is shown, not given)
  const k = key(q, id)
  const draft: Draft = drafts[k] ?? { tags: rec?.tags ?? row.tags, note: rec?.note ?? '' }
  const promoted = state === 'promoted' && rec?.verdict === 'seed' && !!rec.exemplarId
  const binary = queue.verdictKeys === 'binary+classes'
  const isWindow = row.unit === 'window'
  const masked = blind && !rec
  const unit = { kind: 'item' as const, id }
  // review-carry: the overlap set this item stands for, the class stored with its verdict, and where a carried
  // verdict came from — as the bridge serves them on the row (and on the detail, once read)
  // night-review fix round (F1): the ROW (re-read on every queue open) wins over the cached detail — a carry from
  // another queue no longer empties the item cache, so a detail read before it can lack the `carriedFrom` the row has
  const carry: CarryFields = { ...carryOf(d?.entry), ...carryOf(row) }
  const members = carry.members ?? []
  // R3: the class is stored on a detection's adjudication row; elsewhere it stays a session label
  const storesClass = queue.writes === 'adjudications'

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
    if (v === 'seed') { next.exemplarId = rec?.exemplarId; next.entryId = rec?.entryId; next.memberId = rec?.memberId; next.family = d?.nearest?.[0] && d.nearest[0].d <= 0.3 ? d.nearest[0].id : null }
    const note = draft.note.trim() || undefined
    // the Annotate card's tags go to the database with the verdict, through
    // whatever table the queue's `writes_to` names (fixup-a item 9)
    const tags = draft.tags.length ? draft.tags : undefined
    /* fixup-y: the exemplar is named by what was WRITTEN — the bridge's `entry_id` — and is filled in before
     * the write joins the session stack. It was minted here ("E-0217") while the row was motif_entry 3609. */
    let carried = 0
    let carriedIds: number[] = []
    const send = () => v === 'seed'
      ? postPromote(q, id, 'seed', { note, tags }).then(ack => {
        if (ack.entry_id != null) { next.entryId = ack.entry_id; next.memberId = ack.member_id; next.entryCreated = ack.created; next.exemplarId = `entry ${ack.entry_id}` }
        return ack
      })
      // review-carry: the class travels with the verdict and is stored (R3); the ack says how many other runs'
      // detections of the same event the verdict was carried to
      : postVerdict(q, id, v, { note, tags, classLabel: storesClass ? className : undefined }).then(ack => { carried = ack.carried ?? 0; carriedIds = ack.carriedIds ?? []; return ack })
    const w = await commitWrite(send, { queueId: q, items: [id], kind, verdict: v, className, label: `${id} · ${VERDICT_LABEL[v]}`, before: { [k]: before }, after: { [k]: next } },
      // AR: a verdict on a queue that does not write annotations changes one row's judged state and nothing else, so only
      // the counts are re-read; a promotion, or a write that makes a human span (which can change any queue's set), re-reads the rows
      { light: kind !== 'promotion' && queue.writes !== 'annotations' })
    if (!w) { refused(); return null }
    if (carried > 0) {
      // a carried row can judge other items of this queue (other runs' detections in it): re-read the rows — only then
      // (night-review). A carry that reached no row of this queue changes none of its rows; the counts are re-read anyway.
      // When the bridge names no ids (an older bridge), re-read as before.
      if (!carriedIds.length || queueHoldsAny(data, carriedIds)) bumpReviewVersion()
      // F1: the carried detections may be rows of OTHER queues; their cached details predate the carry
      else clearItemCacheExcept(q)
      say(`${VERDICT_LABEL[v]} · written${members.length > 1 ? ` to the ${members.length} detections of this event` : ''} · carried to ${carried} other detection${carried === 1 ? '' : 's'} of the same event`)
    }
    // P21: the seed verdict itself creates the Library exemplar (the bridge wrote it); the panel only chooses its family
    if (v === 'seed') return next
    if (opts.flash !== false && onItem.current === id) { setFlash(v); later(() => setFlash(null), ADVANCE_MS) }
    if (opts.advance && auto) later(() => { if (onItem.current === id) advance() }, ADVANCE_MS)
    return next
  }

  const verdict = async (v: Verdict) => {
    if (promoted) return say('confirm or undo the promotion first (Enter / Ctrl Z)')
    if (binary && (v === 'seed' || v === 'artifact' || v === 'unsure')) return say('this queue takes binary verdicts and classes')
    // fixup-AD: a suspected-artifact queue asks "artifact, or what is it really?" — the four words its queue names
    if ((queue.source as string) === 'suspected-artifact' && v === 'seed') return say('this queue takes artifact, interesting, not interesting or unsure — promote a seed from Explore or a detection queue')
    // fixup-FQ: a Library family queue's member is already in the Library — the question is what it is, not whether to add it
    if ((queue.source as string) === 'library-family' && v === 'seed') return say('this member is already in the Library — judge it interesting, not interesting, artifact or unsure')
    const next = await write(v, rec?.className, v === 'seed' ? 'promotion' : 'verdict', { advance: true })
    if (!next) return
    if (v === 'seed') {
      setQuery({ state: 'promoted' }, true)
      say(next.entryId == null ? 'seed · written, but the bridge named no Library entry · auto-advance paused'
        : next.entryCreated === false ? `seed · already in the Library as entry ${next.entryId} · auto-advance paused`
          : `seed · Library entry ${next.entryId} created · auto-advance paused`)
    }
  }

  /* A class key carries a VERDICT with it, and that verdict goes to the database. review-carry (R3): on a queue
   * that writes `adjudications` the class goes WITH it and is stored on the row, so a keypress that changes only
   * the class re-posts the verdict with the new class (one audit row, undone by Ctrl Z). Elsewhere the stores
   * have no class column and the class stays a session label, as the toast says. */
  const klass = async (ck: string) => {
    const c = VOCABULARY.classes.find(x => x.key === ck)
    if (!c) return
    if (promoted) return say('confirm or undo the promotion first (Enter / Ctrl Z)')
    if (!jrec) {
      const v: Verdict = c.informative ? 'interesting' : 'artifact'
      if (!await write(v, c.name, 'class', { advance: true })) return
      return say(`class ${c.name} · implies ${VERDICT_LABEL[v]} · written`)
    }
    if (storesClass && jrec.verdict !== 'seed') {
      const clear = jrec.className === c.name
      const v: Verdict = !clear && !c.informative && jrec.verdict !== 'artifact' ? 'artifact' : jrec.verdict
      if (!await write(v, clear ? undefined : c.name, 'class', { advance: false, flash: false })) return
      return say(clear ? `class ${c.name} cleared · verdict stays ${VERDICT_LABEL[v]} · stored`
        : v !== jrec.verdict ? `${c.name} is non-informative — artifact written with the class (Ctrl Z reverts)`
          : `class ${c.name} stored with the ${VERDICT_LABEL[v]} verdict`)
    }
    if (jrec.className === c.name) {
      applyWrite({ queueId: q, items: [id], kind: 'class', verdict: jrec.verdict, label: `${id} · class cleared`, before: { [k]: rawRecord(q, id) }, after: { [k]: { ...jrec, className: undefined, at: Date.now() } } })
      return say(`class ${c.name} cleared · verdict stays ${VERDICT_LABEL[jrec.verdict]} (the class is a session label)`)
    }
    const v: Verdict = !c.informative && jrec.verdict !== 'artifact' ? 'artifact' : jrec.verdict
    if (v !== jrec.verdict) {
      if (!await write(v, c.name, 'class', { advance: false, flash: false })) return
      return say(`${c.name} is non-informative — artifact written (Ctrl Z reverts)`)
    }
    applyWrite({ queueId: q, items: [id], kind: 'class', verdict: v, className: c.name, label: `${id} · ${c.name}`, before: { [k]: rawRecord(q, id) }, after: { [k]: { ...jrec, verdict: v, className: c.name, blind, at: Date.now() } } })
    say(`class ${c.name} added to the ${VERDICT_LABEL[v]} verdict (the class is a session label)`)
  }

  /* Ctrl-Z posts to the server, which restores the PRIOR verdict out of its audit row. The client does not
   * invent a reversal: only `review_audit.payload_json` knows whether this reverses to unjudged or back to
   * the verdict that was there before. The stack is marked undone only once the POST was accepted. */
  const undo = async () => {
    if (writesInFlight()) return say('a verdict is still being written — try again')
    const w = lastLive(q)
    if (!w) return say('nothing to undo in this queue')
    // F3: a verdict's pending advance (60 ms after its accept) must not move off the item being undone
    timers.current.forEach(t => window.clearTimeout(t)); timers.current = []
    if (!await commitUndo(() => postUndo(q), w)) return refused()
    if (w.kind === 'batch') { navigate(`review/queue/${q}/cluster/${w.clusterNo}?state=undone`); return }
    if (w.kind === 'promotion') {
      const ex = (w.after[key(q, w.items[0])] as VerdictRecord | null)?.exemplarId
      if (ex) { releaseExemplar(ex); recordDemoWrite('library', 'exemplar.remove', { id: ex, from: `${q}/${w.items[0]}`, reason: 'promotion undone' }) }
      say(`promotion undone · exemplar ${ex} removed`)
      if (w.items[0] === id) setQuery({ state: null }, true)
    } else say(`undone · ${w.label}`)
    // F3: from where the researcher IS when the undo lands, not the item this render was for
    if (onItem.current !== w.items[0]) navigate(`review/queue/${q}/${w.items[0]}`)
  }
  const redo = async () => {
    if (writesInFlight()) return say('a verdict is still being written — try again')
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
    next: () => { const u = step(data, unit, 1); if (u) goUnit(q, u); else say('this is the last item in the queue') },
    prev: () => { const u = step(data, unit, -1); if (u) goUnit(q, u); else say('this is the first item in the queue') },
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

  const earlier = row.baseVerdict
    ? `${VERDICT_LABEL[row.baseVerdict]}${carry.classLabel ? ` (${carry.classLabel})` : ''} · ${carry.carriedFrom != null ? `carried from detection ${carry.carriedFrom}` : 'earlier session'}`
    : 'none'
  const historyText = stack.filter(w => !w.undone && w.items.includes(id)).map(w => `${VERDICT_LABEL[w.verdict ?? 'interesting']}${w.className ? ` (${w.className})` : ''} · ${relTime(w.at, now)}`).reverse().join('; ') || earlier
  const evidence = d ? <EvidenceRail d={d} blind={blind} judged={!!jrec} historyVerdicts={historyText} /> : <Loading />
  const narrow = rails.left || rails.right

  return (
    <Shell data={data} unit={unit} blind={blind} setBlind={setBlind} paused={promoted} micro={micro} evidence={evidence}
      evidenceTitle={`${id}${row.detectionId ? ` · ${row.detectionId}` : ''}`}>
      <div ref={measureRef} aria-hidden style={{ width: '100%', height: 0, margin: 0, padding: 0 }} data-testid="review-measure" />
      {writeError && <div className="error-card" data-testid="write-refused">
        <h3><Icon name="alert-circle" /> Not written · {writeError.label}{writeError.status ? ` · HTTP ${writeError.status}` : ''}</h3>
        <p className="mono">{writeError.message}</p>
        <p>The database was not changed — what the page shows is whatever it held before.</p>
      </div>}
      {det.error && <div className="error-card" data-testid="item-error"><h3>{id} failed to load</h3><p className="mono">{det.error.message}</p></div>}
      {!d && !det.error && <Loading />}
      {d?.refused && <div className="error-card" data-testid="held-out-refusal"><h3><Icon name="lock" /> {id} is refused</h3><p>{d.refused}</p></div>}
      {d && !d.refused && (
        <div className={cx('rv-stack', det.loading && det.data?.entry.id === id && 'stale')} data-testid="inspector" data-item={id} data-blind={blind ? '1' : '0'}>
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
                : <Pill icon="target" label="score" value={(row.unit as string) === 'member' ? 'n/a · family member' : 'n/a · human span'} testid="pill-score" title={(row.unit as string) === 'member' ? 'a flagged family member: what flagged it is on the Suspected artifact card' : 'human spans carry no machine score'} />}
              {masked ? <Pill icon="eye-off" label="family" value="hidden until verdict" tone="purple" testid="pill-family" />
                : fam && <Pill dot={fam.colour} label="family" value={`${fam.id} d ${fam.d.toFixed(2)}`} testid="pill-family" />}
            </>}
            <ArtifactPill a={d.artifact} short={narrow} />
          </div>
          <div className="rv-meta mono" data-testid="meta-line" title={d.entry.recordingFile ? `source file ${d.entry.recordingFile}` : undefined}>{metaLine(d, narrow)}</div>
          {members.length > 1 && <div className="rv-meta mono" data-testid="covers-line">
            covers {members.length} detections · also {members.filter(m => String(m) !== id).join(', ')}
            <InfoTip label="why one item for several detections">This run's detector found overlapping spans here. They are one event, so Review asks once and writes your verdict to every one of them; each stays in the run exactly as the detector wrote it.</InfoTip>
          </div>}
          {carry.carriedFrom != null && row.baseVerdict && <div className="rv-meta mono" data-testid="carried-line">
            {VERDICT_LABEL[row.baseVerdict]} carried from detection {carry.carriedFrom} — the same event, judged in another run
          </div>}

          {d.suspectedArtifact && <SuspectedArtifactCard p={d.suspectedArtifact} />}

          <ContextCard d={d} title={isWindow ? 'Window in context' : row.unit === 'human span' ? 'Span in context' : 'Candidate in context'} pad={pad} setPad={p => { setPad(p); if (padQ) setQuery({ pad: null }, true) }}
            bandLabel={isWindow ? `${id} · ${row.durationS} s` : `${id} · ${row.durationS.toFixed(1)} s`} canEdit={!isWindow && !d.suspectedArtifact}
            memberBands={members.length > 1 ? (carry.memberBands ?? []).map(b => ({ start_s: b.t0_s, end_s: b.t1_s, label: b.id })) : []} />

          <div className="rv-row2">
            <ShapeCard d={d} family={masked ? null : (d.nearest.find(f => f.id === overlay) ?? d.nearest[0] ?? null)} blind={masked || isWindow} rows={data.rows} peaks={peaks} />
            {promoted && rec
              ? <PromotionPanel d={d} rec={rec} onUndo={undo} onConfirm={confirmPromotion} confirmRef={confirmRef} />
              : isWindow && blind ? <RevealCard data={data} current={row} now={now} />
                : masked ? <MaskedFamilies />
                  : <NearestFamiliesCard d={d} overlay={overlay || d.nearest[0]?.id || ''} setOverlay={setOverlay} />}
          </div>

          <VerdictCard selected={rec?.verdict ?? null} flash={flash} binary={binary} onVerdict={verdict} onSkip={() => goUnit(q, step(data, unit, 1))}
            previous={previousLines(data, promoted ? stack.filter(w => !(w.kind === 'promotion' && w.items[0] === id)) : stack, now)} undo={{ can: !!lastLive(q), run: undo }} />
          <AnnotateCard draft={draft} setDraft={setDraft} className={rec?.className ?? (records[k] === undefined ? carry.classLabel : undefined)} onClass={klass} />
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
  // a clause is printed only when there is something in it: a Discovery seed run's queue read
  // "run undefined seed search, exemplar undefined · match d undefined" (fixup-y)
  if (q.source === 'seed-search') return [...base, ['seed search', q.runId ? `run ${q.runId}` : null, q.exemplar ? `exemplar ${q.exemplar}` : null].filter(Boolean).join(' · '),
    e.d != null ? `match d ${e.d.toFixed(2)}` : null].filter(Boolean).join(' · ')
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
      <div className="rv-card-head"><Icon name="eye-off" size={15} className="rv-purple" /><h3>Nearest families</h3><span className="grow" /><span className="mono sm rv-purple">hidden until verdict</span>
        <InfoTip title="Hidden until verdict" placement="bottom-end">Family affinity is machine opinion: it is hidden in a blind queue until you give a verdict. Artifact likelihood stays visible.</InfoTip></div>
    </section>
  )
}

/** "Previous window, revealed" (frame 5): your call beside the model's, for the last judged window. No running agreement (§10.6). */
function RevealCard({ data, current, now }: { data: QueueData; current: QueueRow; now: number }) {
  const records = useRecords()
  const stack = useStack()
  const q = data.queue.id
  const last = [...stack].reverse().find(w => w.queueId === q && !w.undone)
  // AR: the last row before this one with a verdict, by one backward walk (it was two indexOf per row, per second)
  const lastRow = last ? data.rows.find(r => r.id === last.items[0]) : (() => {
    const at = data.rows.indexOf(current)
    for (let i = at - 1; i >= 0; i--) if (judged(records, data.rows[i])) return data.rows[i]
    return undefined
  })()
  const rec = lastRow ? effective(records, lastRow) : null
  const thumbOf = useThumbs(lastRow ? [lastRow] : [])      // AR: rows arrive without thumbnails; this one is paged in
  const you = rec ? rec.className ?? VERDICT_LABEL[rec.verdict] : null
  const call = lastRow?.modelCall
  const agree = !rec || !call ? null : rec.className ? rec.className === call.className : rec.verdict === 'artifact' ? call.className === 'electrode artifact' ? true : false : null
  return (
    <section className="rv-card" data-testid="reveal-card">
      <div className="rv-card-head"><Icon name="eye" size={15} className="rv-purple" /><h3>Previous window, revealed</h3><span className="grow" />
        <InfoTip title="Blind verification">After each verdict the previous window is revealed: your call beside the model's. Running agreement is shown only in Models › Registry, so it cannot steer the next verdict. Artifact likelihood is not blinded.</InfoTip></div>
      {lastRow && rec ? (
        <div className="rv-reveal">
          <div className="rv-reveal-box">
            <MiniTrace values={thumbOf(lastRow)} width={70} height={48} ground="white" zeroLine={false} />
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
          <div style={{ marginTop: 'auto' }}><Button variant="link" size="sm" iconRight="arrow-right" onClick={() => navigate('models/registry')} testid="reveal-agreement-link">Running agreement in Models › Registry</Button></div>
        </div>
      ) : <div className="rv-masked mono muted">No window judged yet in this queue.</div>}
    </section>
  )
}
