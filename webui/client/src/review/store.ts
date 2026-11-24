/* Review's SESSION write record (spec §10.3–10.6, P6, P20, P21).
 * One record per (queue, item) holds the current human verdict; every write is also a SessionWrite on an undo
 * stack whose entries carry before/after snapshots, so one Ctrl Z reverses a whole cluster batch (§10.5) and a
 * promotion (verdict + exemplar, §10.4) in one step. Survives navigation, not a reload.
 *
 * This is no longer where a verdict is STORED. The database is — see `commitWrite`/`commitUndo` at the foot of
 * this file: the bridge is written first and this stack is updated only once the POST was accepted, so the undo
 * affordance and the "previous" line keep working without the page ever showing a verdict nobody stored. */
import { getDemo, recordDemoWrite, setDemo, useDemoState } from '../kit'
import { clearItemCache, itemReadsInFlight, postBatch, postPromote, postVerdict, postVerdicts, readsIdle, type QueueCounts, type QueueEntry,
  type SaveItem, type SaveResult, type Verdict, type WriteAck } from '../api/review'
import { SAVE_BATCH_MAX, SAVE_WAIT_CAP_MS, SaveQueue, journalAdd, journalRemove, mayFlush, orphaned, pageGone, touchPage, type Pending, type StorageLike } from './saves'

export interface VerdictRecord {
  verdict: Verdict; className?: string; blind: boolean; at: number
  exemplarId?: string; family?: string | null; familyName?: string; tags?: string[]; note?: string
  /** fixup-y: the `motif_entry` / `motif_member` the promotion wrote, from the bridge's own reply. `exemplarId`
   *  is its label ("entry 3609"); it used to be minted here ("E-0217") and named no row at all. */
  entryId?: number; memberId?: number; entryCreated?: boolean
}
type Raw = VerdictRecord | null | undefined   // undefined = no session override (fixture state applies)

export interface SessionWrite {
  id: number; queueId: string; items: string[]; kind: 'verdict' | 'class' | 'promotion' | 'batch' | 'tags'
  label: string; clusterNo?: number; verdict?: Verdict; className?: string; count?: number
  before: Record<string, Raw>; after: Record<string, Raw>; at: number; undone: boolean; undoneAt?: number
  /** AS: a write that changed one row's verdict and nothing else about the queue (`commitWrite`'s `light`) */
  light?: boolean
}

const REC = 'review.records', STACK = 'review.stack'
export const key = (queueId: string, itemId: string) => `${queueId}/${itemId}`

export const VERDICT_LABEL: Record<Verdict, string> = { seed: 'seed', interesting: 'interesting', not_interesting: 'not interesting', artifact: 'artifact', unsure: 'unsure' }

export function baseRecord(entry: QueueEntry): VerdictRecord | null {
  return entry.baseVerdict ? { verdict: entry.baseVerdict, className: entry.baseClass, blind: entry.unit === 'window', at: 0 } : null
}

export function useRecords() { return useDemoState<Record<string, Raw>>(REC, () => ({}))[0] }
export function useStack() { return useDemoState<SessionWrite[]>(STACK, () => [])[0] }

export function effective(records: Record<string, Raw>, entry: QueueEntry): VerdictRecord | null {
  const k = key(entry.queueId, entry.id)
  return k in records && records[k] !== undefined ? records[k] ?? null : baseRecord(entry)
}
export const rawRecord = (queueId: string, itemId: string): Raw => getDemo<Record<string, Raw>>(REC, () => ({}))[key(queueId, itemId)]

let nextId = 1
export function applyWrite(w: Omit<SessionWrite, 'id' | 'at' | 'undone'>): SessionWrite {
  const full: SessionWrite = { ...w, id: nextId++, at: Date.now(), undone: false }
  setDemo<Record<string, Raw>>(REC, prev => ({ ...(prev ?? {}), ...full.after }))
  // a new write clears the redo tail
  setDemo<SessionWrite[]>(STACK, prev => [...(prev ?? []).filter(x => !x.undone), full])
  recordDemoWrite('review', w.kind, { queue: w.queueId, items: w.items, label: w.label, after: w.after })
  return full
}

/** Replace the `after` of an existing write in place (a promotion's family choice is confirmed later). */
export function amendWrite(id: number, after: Record<string, Raw>, detail: Record<string, unknown>) {
  setDemo<SessionWrite[]>(STACK, prev => (prev ?? []).map(x => x.id === id ? { ...x, after: { ...x.after, ...after } } : x))
  setDemo<Record<string, Raw>>(REC, prev => ({ ...(prev ?? {}), ...after }))
  recordDemoWrite('review', 'amend', detail)
}

export function lastLive(queueId: string): SessionWrite | undefined {
  return [...getDemo<SessionWrite[]>(STACK, () => [])].reverse().find(x => x.queueId === queueId && !x.undone)
}
export function nextRedo(queueId: string): SessionWrite | undefined {
  const all = getDemo<SessionWrite[]>(STACK, () => []).filter(x => x.queueId === queueId)
  const lastLiveIdx = all.map(x => !x.undone).lastIndexOf(true)
  return all.slice(lastLiveIdx + 1).find(x => x.undone)
}

export function undoWrite(w: SessionWrite) {
  setDemo<Record<string, Raw>>(REC, prev => ({ ...(prev ?? {}), ...w.before }))
  setDemo<SessionWrite[]>(STACK, prev => (prev ?? []).map(x => x.id === w.id ? { ...x, undone: true, undoneAt: Date.now() } : x))
  recordDemoWrite('review', 'undo', { queue: w.queueId, items: w.items, label: w.label })
}
export function redoWrite(w: SessionWrite) {
  setDemo<Record<string, Raw>>(REC, prev => ({ ...(prev ?? {}), ...w.after }))
  setDemo<SessionWrite[]>(STACK, prev => (prev ?? []).map(x => x.id === w.id ? { ...x, undone: false, undoneAt: undefined, at: Date.now() } : x))
  recordDemoWrite('review', 'redo', { queue: w.queueId, items: w.items, label: w.label })
}

/** Deep link helper (`?state=undone`): put a batch on the stack already undone, as frame 7 shows it. */
export function seedUndoneBatch(w: Omit<SessionWrite, 'id' | 'at' | 'undone'>, agoMs: number) {
  const full: SessionWrite = { ...w, id: nextId++, at: Date.now() - agoMs, undone: true, undoneAt: Date.now() - agoMs }
  setDemo<SessionWrite[]>(STACK, prev => [...(prev ?? []), full])
  setDemo<Record<string, Raw>>(REC, prev => ({ ...(prev ?? {}), ...full.before }))
  return full
}

/* ---- per-queue and personal preferences ---- */
export function useBlindOverrides() { return useDemoState<Record<string, boolean>>('review.blind', () => ({})) }
export function useAutoAdvance() { return useDemoState<boolean>('review.autoAdvance', () => true) }
export function usePad() { return useDemoState<'30' | '120' | '300'>('review.pad', () => '120') }

export interface QueueFilters { method: string; channels: string[]; score: [number, number]; status: 'unjudged' | 'judged' | 'all'; group: 'none' | 'sequence' | 'family' }
export const defaultFilters = (channels: string[], floor: number | null): QueueFilters =>
  ({ method: 'all', channels: channels.filter(c => c !== 'CH1_A1' || channels.length < 3), score: [floor ?? 0, 1], status: 'unjudged', group: 'sequence' })
export function useFilters(queueId: string, channels: string[], floor: number | null) {
  const [all, setAll] = useDemoState<Record<string, QueueFilters>>('review.filters', () => ({}))
  const value = all[queueId] ?? defaultFilters(channels, floor)
  return [value, (patch: Partial<QueueFilters> | null) => setAll(prev => ({ ...prev, [queueId]: patch === null ? defaultFilters(channels, floor) : { ...(prev[queueId] ?? defaultFilters(channels, floor)), ...patch } }))] as const
}

export interface Draft { tags: string[]; note: string; className?: string }
export function useDrafts() { return useDemoState<Record<string, Draft>>('review.drafts', () => ({})) }

/** Exemplar ids count up from E-0217 in memory (the first promotion mints E-0217, frame 6). */
export function mintExemplar(): string {
  const n = getDemo<number>('review.exemplarSeq', () => 217)
  setDemo<number>('review.exemplarSeq', n + 1)
  return `E-${String(n).padStart(4, '0')}`
}
export function releaseExemplar(id: string) {
  const n = getDemo<number>('review.exemplarSeq', () => 217)
  if (`E-${String(n - 1).padStart(4, '0')}` === id) setDemo<number>('review.exemplarSeq', n - 1)
}

export const getRecords = () => getDemo<Record<string, Raw>>(REC, () => ({}))

/** Tags and notes edited after the verdict update the record in place (not an undo step). */
export function patchRecord(queueId: string, itemId: string, base: VerdictRecord, patch: Partial<VerdictRecord>) {
  setDemo<Record<string, Raw>>(REC, prev => ({ ...(prev ?? {}), [key(queueId, itemId)]: { ...base, ...patch } }))
  recordDemoWrite('review', 'annotate', { queue: queueId, item: itemId, ...patch })
}

/** Human-readable label for the "previous" line. */
export function writeLabel(w: SessionWrite): string {
  if (w.kind === 'batch') return w.label
  const id = w.items[0]
  if (w.kind === 'promotion') return `${id} · seed · ${(w.after[key(w.queueId, id)] as VerdictRecord | null)?.exemplarId ?? 'exemplar'}`
  if (w.kind === 'class' && w.className) return `${id} · ${w.className} (class)`
  return `${id} · ${w.verdict ? VERDICT_LABEL[w.verdict] : 'class cleared'}`
}

/* ------------------------------------------------------------------------------------------------ *
 * The database is the source of truth; this session stack is the undo AFFORDANCE.
 *
 * Every keypress below goes to the bridge FIRST. Only when the POST has been accepted does the write
 * join the session stack (which drives Ctrl-Z's enablement and the "previous" line) and only then is
 * the queue/item read re-run, so what the page shows next is what the database actually holds rather
 * than what the client guessed it would hold.
 *
 * A REFUSED post changes nothing locally and records a `WriteFailure` the pages render as a red card.
 * That asymmetry is the whole point: a verdict that did not land must not look like one that did.
 * ------------------------------------------------------------------------------------------------ */

export interface WriteFailure {
  message: string; status?: number; label: string; at: number
  /** 2026-11-24: the item the refused write was about, so its card can be shown on it after the page moved on */
  queueId?: string; itemId?: string
}
const ERR = 'review.writeError', VERSION = 'review.dataVersion'

export function useWriteError() { return useDemoState<WriteFailure | null>(ERR, () => null)[0] }
/** The same failure, read imperatively right after an awaited commit returned null. */
export const getWriteError = () => getDemo<WriteFailure | null>(ERR, () => null)
export const clearWriteError = () => setDemo<WriteFailure | null>(ERR, null)
function failed(e: unknown, label: string, queueId?: string, itemId?: string): WriteFailure {
  const status = (e as { status?: number } | null)?.status
  return { message: e instanceof Error ? e.message : String(e), status, label, at: Date.now(), queueId, itemId }
}

/** Bumped after every accepted write that can change the queue's SET of rows (a promotion, a batch, an undo or
 *  redo, any write to a queue whose verdicts land in `annotations`). Review's reads carry it in their deps, so such
 *  a write re-reads the rows and the item instead of trusting the local record to have guessed right. */
export function useReviewVersion() { return useDemoState<number>(VERSION, () => 0)[0] }
export const bumpReviewVersion = () => { clearItemCache(); setDemo<number>(VERSION, n => (n ?? 0) + 1) }
/** AS: re-read the rows and keep the item cache - after the undo or redo of a light verdict, whose cached card (read
 *  before the verdict was given) already shows what the undo restores; emptying the cache made the step back to it a
 *  cold read under the rows' re-read (2.0 s measured, 0.09 s of it the undo). */
const bumpReviewRows = () => setDemo<number>(VERSION, n => (n ?? 0) + 1)

/** AR (the speed pass): bumped after every accepted write, including the single verdicts that change only one
 *  row's judged state. What carries it re-reads the queue's COUNTS (`/counts`, and the queue list's headers) —
 *  never every row, which was 5.3 s and 3 MB per verdict at 3,195 items on the real database. The row's own
 *  verdict is the session record the write just made, so the page shows what the bridge accepted. */
const COUNTS_VERSION = 'review.countsVersion'
export function useCountsVersion() { return useDemoState<number>(COUNTS_VERSION, () => 0)[0] }
const bumpCountsVersion = () => setDemo<number>(COUNTS_VERSION, n => (n ?? 0) + 1)

/* AS (2026-11-24): a verdict no longer re-reads the counts (`/counts`, and the open rail's queue list) - each one
 * competed with the next candidate's read. The save's answer carries the counts; the full read (pace, detections) is
 * re-run at most every COUNTS_BEAT_MS while verdicts flow, and once when the backlog of saves empties. */
const COUNTS_BEAT_MS = 5000
let countsAt = 0
let countsTimer: ReturnType<typeof setTimeout> | null = null
function bumpCountsSoon(now = Date.now()) {
  if (countsTimer) return
  const wait = countsAt + COUNTS_BEAT_MS - now
  if (wait <= 0) { countsAt = now; bumpCountsVersion(); return }
  countsTimer = setTimeout(() => { countsTimer = null; countsAt = Date.now(); bumpCountsVersion() }, wait)
}
function bumpCountsNow() {
  if (countsTimer) { clearTimeout(countsTimer); countsTimer = null }
  countsAt = Date.now(); bumpCountsVersion()
}

/** Explore changed the stored event. Session verdicts and prefetched traces
 * must defer to the database when Review opens again. The undo audit stays. */
export function refreshAfterSpanEdit() {
  setDemo<Record<string, Raw>>(REC, {})
  bumpReviewVersion()
  bumpCountsVersion()
}

/** night-a: writes sent and not yet answered. Undo and redo wait for them: a Ctrl Z inside a verdict's round trip
 *  undid the PREVIOUS item (the new write joins the stack only on its ack) while the new one still landed. */
let inFlight = 0

/* 2026-11-24 (the researcher: "noticeable load time between each candidate, load time after decision"): the Inspector
 * moves on the moment a verdict key is pressed and the verdict is written behind it. So more than one write can be
 * outstanding, and they go to the bridge ONE AT A TIME IN THE ORDER GIVEN: the audit rows, which undo walks newest
 * first, then keep the gestures' order, and the stack's last write is the bridge's last too. */
let chain: Promise<unknown> = Promise.resolve()
/* AS: the verdict saves queued before a promotion, a batch, an undo or a redo go before it, and those given after it
 * go after it: every save and every other write takes a sequence number, and an other write is a barrier the save
 * queue does not take past until it has been sent (`flushBefore`, then its own send). */
let seq = 0
const barriers = new Set<number>()
function inOrder<T>(send: () => Promise<T>): Promise<T> {
  const mine = ++seq
  barriers.add(mine)
  const run = chain.then(() => flushBefore(mine)).then(() => { barriers.delete(mine); return send() })
    .finally(() => { barriers.delete(mine); if (SAVES.count()) schedulePump() })
  chain = run.catch(() => undefined)
  return run
}
/** Resolves once every write sent so far has been answered (accepted or refused). */
export const writesSettled = (): Promise<void> => chain.then(() => undefined)

/** Wait for the writes still outstanding before an undo or redo; a refusal among them is said, not reversed past. */
async function waitForWrites(verb: 'undone' | 'redone'): Promise<string | null> {
  if (!inFlight) return null
  const before = getWriteError()
  hurrySaves()
  await writesSettled()
  const after = getWriteError()
  return after && after !== before ? `${after.label} was not written, so nothing was ${verb}` : null
}

/** What an undo or redo came to: the write it reversed or replayed; a plain refusal to toast (`say`: a write still
 *  in flight, or nothing to reverse); or the bridge's refusal (`failed`), recorded for the red card. tq-review: the
 *  in-flight refusal was copied into both pages' undo and redo; it is decided here, once, before anything else. */
export type Reversal = { w: SessionWrite } | { say: string } | { failed: true }

/** Send, then record. Returns the session write on success and `null` on a refusal. `light`: the write changes
 *  one row's verdict and nothing else about the queue (a verdict or class on a queue writing adjudications or
 *  window verdicts), so only the counts are re-read. */
export async function commitWrite(send: () => Promise<unknown>, w: Omit<SessionWrite, 'id' | 'at' | 'undone'>,
                                  opts: { light?: boolean } = {}): Promise<SessionWrite | null> {
  inFlight++
  try { await inOrder(send) } catch (e) { setDemo<WriteFailure | null>(ERR, failed(e, w.label, w.queueId, w.items[0])); return null } finally { inFlight-- }
  // an accepted write takes back the red card of ITS item (a retry); another item's refusal stays on screen
  const err = getWriteError()
  if (err && (!err.itemId || (err.itemId === w.items[0] && err.queueId === w.queueId))) clearWriteError()
  const full = applyWrite(w)
  if (!opts.light) bumpReviewVersion()
  bumpCountsVersion()
  return full
}

const BUSY = 'a verdict is still being written — try again'

/** Ctrl-Z on this queue's last live write. `send` posts the undo (`postUndo` — the server restores the prior verdict
 *  from its audit row; the local stack is only marked undone once it has).
 *
 *  AS (2026-11-24): the newest gesture may be a verdict save still WAITING in the queue - it is taken back and nothing
 *  is sent (it joins the stack as an undone write, so redo can give it again). One already sent is waited for, then
 *  undone at the bridge as before; a backlog of earlier saves goes first, and the page says so. */
export async function commitUndo(queueId: string, send: (w: SessionWrite) => Promise<unknown>): Promise<Reversal> {
  const unsent = SAVES.withdrawLast(queueId)
  if (unsent && unsent !== 'sending') {
    settleSave(unsent, { withdrawn: true })
    const full = applyWrite({ ...unsent.meta.w, light: unsent.meta.light })
    undoWrite(full)
    return { w: full }
  }
  const backlog = SAVES.count(queueId)
  setDemo<string | null>(UNDOING, backlog > 0 || carryBacklog > 10
    ? `undoing — saving ${backlog > 0 ? `${backlog} earlier verdict${backlog === 1 ? '' : 's'}` : `${carryBacklog} carries`} first`
    : 'undoing…')
  try {
    const refusedMeanwhile = await waitForWrites('undone')      // Ctrl Z straight after a verdict undoes THAT verdict
    if (refusedMeanwhile) return { say: refusedMeanwhile }
    if (inFlight) return { say: BUSY }
    const w = lastLive(queueId)
    if (!w) return { say: 'nothing to undo in this queue' }
    inFlight++
    try { await inOrder(() => send(w)) } catch (e) { setDemo<WriteFailure | null>(ERR, failed(e, `undo · ${w.label}`)); return { failed: true } } finally { inFlight-- }
    clearWriteError()
    undoWrite(w)
    if (w.light) bumpReviewRows(); else bumpReviewVersion()
    bumpCountsVersion()
    return { w }
  } finally {
    setDemo<string | null>(UNDOING, null)
  }
}

/** Ctrl-Shift-Z on this queue's next undone write. The bridge has no redo route, so `send` re-sends the original
 *  write (`resend` — the core's writers are upserts) and only then is the stack entry un-marked. */
export async function commitRedo(queueId: string, send: (w: SessionWrite) => Promise<unknown>): Promise<Reversal> {
  const refusedMeanwhile = await waitForWrites('redone')
  if (refusedMeanwhile) return { say: refusedMeanwhile }
  if (inFlight) return { say: BUSY }
  const w = nextRedo(queueId)
  if (!w) return { say: 'nothing to redo' }
  inFlight++
  try { await inOrder(() => send(w)) } catch (e) { setDemo<WriteFailure | null>(ERR, failed(e, `redo · ${w.label}`)); return { failed: true } } finally { inFlight-- }
  clearWriteError()
  redoWrite(w)
  if (w.light) bumpReviewRows(); else bumpReviewVersion()
  bumpCountsVersion()
  return { w }
}

/* ------------------------------------------------------------------------------------------------ *
 * AS (2026-11-24): verdicts saved behind the researcher.
 *
 * The researcher: "can you prioritise feeding the next candidate in faster over saving verdicts, so that momentum
 * [can] be gained ... and the lag for verdicts to catch up can increase but still process slowly in the background?"
 * A verdict (and a class key) goes into the save queue (`saves.ts`) and the page moves on. The queue is sent in
 * gesture order, several verdicts in one request (`POST …/verdicts`), and a save waits while an item read is in
 * flight, up to SAVE_WAIT_CAP_MS. Each waiting save is journalled in localStorage until its answer, so a reload or a
 * crash loses none (the next Review page replays it), and carries a client id, so the bridge never writes it twice.
 * The stack still takes a write only once the bridge accepted it, in the order the bridge wrote them.
 * ------------------------------------------------------------------------------------------------ */

export type SaveOutcome = { w: SessionWrite; ack: WriteAck & { duplicate?: boolean } } | { failed: WriteFailure } | { withdrawn: true }
interface SaveMeta { w: Omit<SessionWrite, 'id' | 'at' | 'undone'>; light: boolean; seq: number; resolve: (o: SaveOutcome) => void; replay?: boolean }

const SAVES = new SaveQueue<SaveMeta>()
const PENDING = 'review.savesPending', UNDOING = 'review.undoing', REPLAY = 'review.replaying'
let carryBacklog = 0
const PAGE = randomId()

function randomId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}
const storage = (): StorageLike | null => { try { return typeof localStorage !== 'undefined' ? localStorage : null } catch { return null } }
function journal(fn: (st: StorageLike) => void) {
  const st = storage()
  if (!st) return
  try { fn(st) } catch (e) { console.error('the review save journal could not be written', e) }   // full or blocked storage: said, not hidden
}

/** How many verdicts are waiting to be saved (all queues): the toolbar's "N saving…". */
export function useSavesPending() { return useDemoState<number>(PENDING, () => 0)[0] }
export const savesPending = (queueId?: string) => SAVES.count(queueId)
export function useUndoing() { return useDemoState<string | null>(UNDOING, () => null)[0] }
export function useReplaying() { return useDemoState<Record<string, number>>(REPLAY, () => ({}))[0] }
const publish = () => setDemo<number>(PENDING, SAVES.count())

/** Save one verdict behind the researcher. Resolves once the bridge answered it: the stack write (accepted), the
 *  refusal (recorded for the red card, and returned so the page can say WHICH verdict), or `withdrawn` (Ctrl Z took
 *  it back before it was sent). */
export async function commitSave(queueId: string, item: Omit<SaveItem, 'client_id'>, w: Omit<SessionWrite, 'id' | 'at' | 'undone'>,
                                  opts: { light?: boolean; clientId?: string; replay?: boolean } = {}): Promise<SaveOutcome> {
  const body: SaveItem = { ...item, client_id: opts.clientId ?? randomId() }
  return new Promise<SaveOutcome>(resolve => {
    journal(st => journalAdd(st, queueId, { ...body, at: Date.now(), label: w.label }, PAGE))
    inFlight++
    if (idleTimer) { clearTimeout(idleTimer); idleTimer = null }
    SAVES.add(queueId, body, { w, light: !!opts.light, seq: ++seq, resolve, replay: opts.replay }, Date.now())
    publish()
    schedulePump()
  })
}

function settleSave(p: Pending<SaveMeta>, o: SaveOutcome, keepJournal = false) {
  SAVES.done(p)
  if (!keepJournal) journal(st => journalRemove(st, p.queueId, p.body.client_id))
  inFlight--
  publish()
  if (!SAVES.count()) countsWhenIdle()
  p.meta.resolve(o)
}

/** The backlog emptied: re-read the full counts once the researcher pauses (a new save cancels it). */
let idleTimer: ReturnType<typeof setTimeout> | null = null
function countsWhenIdle() {
  if (idleTimer) clearTimeout(idleTimer)
  idleTimer = setTimeout(() => { idleTimer = null; if (!SAVES.count()) bumpCountsNow() }, 1500)
}

/** The verdicts of this queue still waiting to be saved, as records: what the window and the auto-advance count as
 *  judged (the page has moved past them), never what a card shows as stored. */
export function pendingRecords(queueId: string): Record<string, VerdictRecord> {
  const out: Record<string, VerdictRecord> = {}
  for (const p of SAVES.items) if (p.queueId === queueId) Object.assign(out, p.meta.w.after)
  return out
}

let pumpQueued = false
let hurry: (() => void) | null = null
const hurrySaves = () => { hurry?.() }
function schedulePump() {
  if (pumpQueued) return
  pumpQueued = true
  const run = chain.then(async () => { pumpQueued = false; await pump(true) })
  chain = run.catch(e => { console.error('the review save queue stopped', e) })
}

/** Send what is waiting, before the first barrier; `gated`: let item reads go first (up to the cap). */
async function pump(gated: boolean) {
  for (;;) {
    if (gated) await gate()
    const limit = barriers.size ? Math.min(...barriers) : Infinity
    const batch = SAVES.take(SAVE_BATCH_MAX, p => p.meta.seq < limit)
    if (!batch.length) return
    await sendBatch(batch)
  }
}
const flushBefore = async (mine: number) => {
  for (;;) {
    const batch = SAVES.take(SAVE_BATCH_MAX, p => p.meta.seq < mine)
    if (!batch.length) return
    await sendBatch(batch)
  }
}

/** Reads first: wait while an item read is in flight, up to the cap counted from the oldest waiting save. */
async function gate() {
  const oldest = SAVES.oldestWaiting()
  if (oldest == null || mayFlush(itemReadsInFlight(), oldest, Date.now())) return
  await new Promise<void>(resolve => {
    hurry = () => { hurry = null; resolve() }
    readsIdle(Math.max(0, oldest + SAVE_WAIT_CAP_MS - Date.now())).then(() => { hurry = null; resolve() })
  })
}

async function sendBatch(batch: Pending<SaveMeta>[]) {
  const queueId = batch[0].queueId
  let ack: { results: SaveResult[]; counts?: QueueCounts; carryQueued?: number }
  try {
    ack = await postVerdicts(queueId, batch.map(p => p.body as SaveItem))
  } catch (e) {
    // the whole request failed. A refusal (4xx) refuses them all, as separate POSTs would have been refused; a bridge
    // that did not answer (a network error, a 5xx) may have written some, so each stays in the journal and the next
    // Review page sends it again - its client id makes that safe - and the red card says so
    const status = (e as { status?: number } | null)?.status
    const kept = !(status != null && status >= 400 && status < 500)
    batch.forEach((p, i) => {
      const f = failed(e, kept ? `${p.meta.w.label} (kept in this browser; sent again when Review is next opened)` : p.meta.w.label, queueId, p.meta.w.items[0])
      if (i === 0) setDemo<WriteFailure | null>(ERR, f)
      settleSave(p, { failed: f }, kept)
    })
    return
  }
  carryBacklog = ack.carryQueued ?? 0
  const byId = new Map(ack.results.map(r => [r.client_id, r]))
  let changed = false
  for (const p of batch) {
    const r = byId.get(p.body.client_id)
    if (!r || !r.ok) {
      const f: WriteFailure = { message: r ? (r as { error: string }).error : 'the bridge did not answer this verdict', status: r ? (r as { status: number }).status : undefined,
                                label: p.meta.w.label, at: Date.now(), queueId, itemId: p.meta.w.items[0] }
      setDemo<WriteFailure | null>(ERR, f)
      settleSave(p, { failed: f })
      continue
    }
    // an accepted write takes back the red card of ITS item (a retry); another item's refusal stays on screen
    const err = getWriteError()
    if (err && (!err.itemId || (err.itemId === p.meta.w.items[0] && err.queueId === queueId))) clearWriteError()
    const full = applyWrite({ ...p.meta.w, light: p.meta.light && !p.meta.replay })
    if (!p.meta.light || p.meta.replay) changed = true
    settleSave(p, { w: full, ack: r as WriteAck })
  }
  if (changed) bumpReviewVersion()
  bumpCountsSoon()
}

/* the page must not be closed with verdicts only it holds; a crash still has the journal */
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', e => {
    if (!SAVES.count()) return
    e.preventDefault()
    e.returnValue = ''
  })
  // a page that unloads is gone at once (its unsaved verdicts are the next page's to send); one that crashed is gone
  // once its stamp is PAGE_STALE_MS old
  window.addEventListener('pagehide', () => journal(st => pageGone(st, PAGE)))
  journal(st => touchPage(st, PAGE, Date.now()))
  window.setInterval(() => journal(st => touchPage(st, PAGE, Date.now())), 2000)
}

/** The verdicts a page that is gone left unsaved (a reload, a crash), sent again in their order before any new verdict
 *  is taken - at a queue's first visit and every few seconds while it is open (a crashed page is gone only once its
 *  stamp is stale). Resolves with how many there were; a refused one stays loud (the red card and the returned
 *  failures). Cheap when there is nothing: one localStorage read. */
const replaying = new Set<string>()
export async function replayJournal(queueId: string): Promise<{ n: number; failed: WriteFailure[] }> {
  if (replaying.has(queueId)) return { n: 0, failed: [] }
  const st = storage()
  const entries = st ? orphaned(st, queueId, PAGE, Date.now()) : []
  if (!entries.length) return { n: 0, failed: [] }
  replaying.add(queueId)
  setDemo<Record<string, number>>(REPLAY, prev => ({ ...(prev ?? {}), [queueId]: entries.length }))
  try {
    const outs = await Promise.all(entries.map(e => {
      const k = key(queueId, e.target_id)
      const after: VerdictRecord = { verdict: e.verdict as Verdict, className: e.class_label, blind: false, at: e.at, tags: e.tags, note: e.note }
      journal(s2 => journalAdd(s2, queueId, e, PAGE))     // this page owns them now
      return commitSave(queueId, { target_id: e.target_id, verdict: e.verdict as Verdict, note: e.note, tags: e.tags, class_label: e.class_label },
        { queueId, items: [e.target_id], kind: 'verdict', verdict: e.verdict as Verdict, className: e.class_label, label: `${e.label} (from your last visit)`, before: { [k]: undefined }, after: { [k]: after } },
        { clientId: e.client_id, replay: true })
    }))
    return { n: entries.length, failed: outs.flatMap(o => 'failed' in o ? [o.failed] : []) }
  } finally {
    replaying.delete(queueId)
    setDemo<Record<string, number>>(REPLAY, prev => { const next = { ...(prev ?? {}) }; delete next[queueId]; return next })
  }
}

/** Re-send a session write, for Ctrl-Shift-Z. The bridge has no redo route and the core's writers are
 *  upserts, so replaying the act IS the redo. A batch that promoted one member replays as the promotion
 *  plus the batch of the rest, which is how it was sent the first time. */
export function resend(queueId: string, w: SessionWrite): Promise<unknown> {
  const v: Verdict = w.verdict ?? 'interesting'
  if (w.kind === 'promotion') return postPromote(queueId, w.items[0], 'seed')
  if (w.kind === 'batch') {
    const seedId = v === 'seed' ? w.items.find(id => (w.after[key(queueId, id)] as VerdictRecord | null)?.verdict === 'seed') : undefined
    if (seedId) {
      const rest = w.items.filter(i => i !== seedId)
      return rest.length
        ? postBatch(queueId, rest, 'interesting').then(() => postPromote(queueId, seedId, 'seed'))
        : postPromote(queueId, seedId, 'seed')
    }
    return postBatch(queueId, w.items, v)
  }
  // review-carry (R3): a redo re-sends the class the write carried, so the stored class comes back with it
  return postVerdict(queueId, w.items[0], v, w.className ? { classLabel: w.className } : {})
}
