/* Review reads (spec §10), wired to the bridge (`server/review.py`, prefix `/api/review`).
 *
 * Every exported name and signature is what it was when these resolved fixtures — components import the
 * types from here and call the same functions. What changed is the bodies: the six reads (`getQueues`,
 * `getAllQueues`, `getQueue`, `getItem`, `getCluster`, `getOtherChannels`) now wrap a bridge call in
 * `live(...)`. A failed fetch THROWS (`ApiError` carrying the server's message and traceback); nothing
 * here falls back to the fixture, because a silent fixture fallback is the "catch an error into a blank"
 * the repo forbids and `useSourced` renders errors loudly on purpose.
 *
 * Two things stay fixture-shaped and are called out rather than hidden:
 *   - `clusterQueue(no)` is SYNCHRONOUS (the `#/review/cluster/<n>` alias resolves before any read) and
 *     there is no synchronous live source for it, so it still reads `CLUSTERS`. Known remainder.
 *   - `VOCABULARY` is presentation canon (class keys, verdict colours, tag suggestions), not queue data.
 *
 * The queue row/detail payloads are taken from the bridge verbatim where the contract does not name a
 * body; only the queue header is assembled here, from the columns the contract does name
 * (`name`/`source_kind`/`unit`/`writes_to`/`blind`/`cap` plus total/judged/remaining), because the
 * fixture-era `ReviewQueue` carries presentation fields (icon, titles, order text) the database has no
 * column for. Those are DERIVED from source kind — never invented data. */
import { live, type Sourced } from './seam'
import { ApiError } from '../api'
import { CLASSES, MORPHOLOGY_TAGS, RECORDINGS, VERDICTS } from '../fixtures/canon'
import {
  CLUSTERS, REVIEW_TAG_SUGGESTIONS,
  type ArtifactFactors, type Evidence, type NearestFamily, type QueueEntry, type ReviewCluster, type ReviewQueue, type QueueSource, type Unit, type Verdict,
} from '../fixtures/review'

export type { ArtifactFactors, Evidence, NearestFamily, QueueEntry, ReviewCluster, ReviewQueue, QueueSource, Unit, Verdict } from '../fixtures/review'
export { CONTEXT_PAD_MAX } from '../fixtures/review'

/** `judged` is the DATABASE's answer, not the session's: `queue_items` reports whether this target already
 *  carries a verdict in the table the queue writes. It carries no verdict VALUE (see `rowOf`), so it is kept
 *  as its own flag instead of being turned into a `baseVerdict` nobody sent. */
export interface QueueRow extends QueueEntry { thumb: number[]; family: string; judged: boolean }
export interface QueueData { queue: ReviewQueue; rows: QueueRow[]; clusters: ReviewCluster[] }

/** Artifact factors as the bridge serves them: a TYPED ABSENCE when nothing has
 *  computed them. Plain `null` is what `d.artifact.level` crashed the whole
 *  workspace on, and a plausible-looking number beside a real waveform would be
 *  a finding that is not there — so the numeric fields are null and the word
 *  fields say "not computed". */
export interface ArtifactPanel {
  computed: boolean
  level: 'low' | 'medium' | 'high' | null
  p: number | null
  coherence: number | null
  clipping: string; stepChange: string; electrodeFlag: string
  reason?: string
}

export interface ItemDetail {
  entry: QueueEntry; queue: ReviewQueue
  context: { values: number[]; t0_s: number }
  shape: number[]; nearest: NearestFamily[]; medoids: Record<string, number[]>
  /** Whether anything actually computed family affinity. An empty `nearest` with
   *  `nearestComputed: false` means nobody looked; with `true` it means nothing is near. */
  nearestComputed?: boolean
  artifact: ArtifactPanel; evidence: Evidence; thumb: number[]
  /** Set when the item belongs to a held-out recording (D6): nothing else is served. */
  refused?: string
}

export interface ClusterDetail { cluster: ReviewCluster; queue: ReviewQueue; members: ItemDetail[] }
export interface OtherChannelRow { channel: string; r: number | null; values: number[]; current: boolean }

const HELD_OUT = RECORDINGS.filter(r => r.held_out).map(r => r.label)
const refusal = (rec: string) => `${rec} is held out (D6): it is locked for the final evaluation and cannot be reviewed, plotted or queued.`

/* ---------------------------------------------------------------- bridge ---------------------------------------------------------------- */

/** One fetch. Non-2xx throws `ApiError` with the server's message (and traceback on a 500) — never a blank. */
async function req<T>(path: string): Promise<T> {
  const r = await fetch(`/api/review${path}`, { headers: { 'content-type': 'application/json' } })
  if (!r.ok) {
    let body: any = null
    try { body = await r.json() } catch { /* not json */ }
    const msg = body?.error ?? (typeof body?.detail === 'string' ? body.detail : body?.detail?.message) ?? `${r.status} ${r.statusText}`
    throw new ApiError(r.status, msg, body?.detail ?? body, body?.traceback)
  }
  return r.json() as Promise<T>
}

/** The bridge's queue row, as the contract's `get_queue`/`list_queues` describe it. Fields the fixture-era
 *  header needs but the table has no column for are derived below. */
interface SrvQueue {
  id: number | string; name: string; source_kind: string; source_ref?: string | null
  unit?: string | null; writes_to?: string | null; blind?: number | boolean | null; cap?: number | null
  verdict_options?: string[] | null; filters?: unknown; note?: string | null; closed?: number | boolean | null
  total?: number; judged?: number; remaining?: number
}
interface SrvQueueData { queue: SrvQueue; rows?: unknown[]; items?: unknown[]; clusters?: unknown[] }

const ICONS: Record<string, ReviewQueue['icon']> = {
  'discovery-run': 'target', 'seed-search': 'scan', 'explore-spans': 'wave',
  'training-windows': 'grid', 'model-verification': 'flask', 'extract-events': 'wave',
}
const RANKS: Record<string, ReviewQueue['rankKind']> = {
  'discovery-run': 'score', 'seed-search': 'distance', 'explore-spans': 'time',
  'training-windows': 'stratified', 'model-verification': 'stratified', 'extract-events': 'time',
}
const ORDER: Record<ReviewQueue['rankKind'], string> = {
  score: 'sorted by score', distance: 'sorted by distance', time: 'sorted by time', stratified: 'stratified by channel',
}
const UNITS: Record<string, string> = { detection: 'detection', window: 'window', 'human span': 'human span', sequence: 'sequence' }
const WRITES: Record<string, ReviewQueue['writes']> = {
  adjudications: 'adjudications', annotations: 'annotations', window_verdicts: 'window verdicts', 'window verdicts': 'window verdicts',
}

/** The queue header the pages render, assembled from the columns the contract names. Nothing is invented:
 *  icon, order text and rank kind are a fixed function of `source_kind`, and the titles are the queue's own
 *  name and source. */
function queueOf(q: SrvQueue): ReviewQueue {
  const kind = String(q.source_kind ?? '')
  const rankKind = RANKS[kind] ?? 'time'
  const unit = (UNITS[String(q.unit ?? '')] ?? 'detection') as Unit
  const blind = !!q.blind
  const writes = WRITES[String(q.writes_to ?? '')] ?? 'adjudications'
  const ref = q.source_ref ? String(q.source_ref) : undefined
  const subtitleParts = [ref, `${unit}s`, writes].filter(Boolean) as string[]
  return {
    id: String(q.id), source: kind as QueueSource, icon: ICONS[kind] ?? 'target',
    title: q.name, subtitle: subtitleParts.join(' · '), toolbarLabel: q.name,
    headerSubtitle: `queue ${kind.replace('-', ' ')}${ref ? ` · ${ref}` : ''}`,
    runId: kind === 'discovery-run' || kind === 'seed-search' ? ref : undefined,
    template: kind === 'training-windows' ? ref : undefined,
    exemplar: kind === 'seed-search' ? ref : undefined,
    model: kind === 'model-verification' ? ref : undefined,
    unit, blind,
    verdictKeys: unit === 'window' ? (blind ? 'binary+classes' : 'full+classes') : 'full',
    writes,
    order: ORDER[rankKind],
    total: Number(q.total ?? 0), judged: Number(q.judged ?? 0), paceS: null,
    channels: [], scoreFloor: null, previousLine: null, rankKind,
  }
}

/** A queue row: the bridge's item dict, kept verbatim, with the two presentation fields the table needs.
 *  `thumb` is whatever decimated trace the bridge sent — an absent one stays EMPTY rather than being
 *  synthesised, because a synthetic trace drawn beside a real one is a finding that is not there. */
function rowOf(raw: any, queueId: string): QueueRow {
  /* `baseVerdict` is set ONLY when the bridge sent a verdict value. `queue_items` sends `judged: true`
   * without saying which verdict it was, and guessing one would put a human verdict on the screen that
   * nobody gave — so the flag is carried as `judged` and the pages treat it as "the database holds a
   * verdict here", never as a particular one. */
  const base = raw?.baseVerdict ?? raw?.verdict
  return {
    ...(raw as QueueEntry),
    id: String(raw?.id ?? ''),
    queueId,
    baseVerdict: base ? (base as Verdict) : undefined,
    judged: raw?.judged === true || raw?.judged === 1 || !!base,
    thumb: Array.isArray(raw?.thumb) ? raw.thumb as number[] : [],
    family: String(raw?.family ?? raw?.familyId ?? ''),
    tags: Array.isArray(raw?.tags) ? raw.tags as string[] : [],
  }
}

/** An item detail as the bridge serves it, with the D6 refusal applied client-side as well (the bridge
 *  refuses held-out recordings on every route; this keeps the inspector's own banner honest). */
function detailOf(raw: any, fallbackQueue?: ReviewQueue): ItemDetail {
  const entry = (raw?.entry ?? {}) as QueueEntry
  const queue = raw?.queue ? queueOf(raw.queue as SrvQueue) : fallbackQueue
  return {
    entry, queue: queue as ReviewQueue,
    context: raw?.context ?? { values: [], t0_s: 0 },
    shape: Array.isArray(raw?.shape) ? raw.shape : [],
    nearest: Array.isArray(raw?.nearest) ? raw.nearest : [],
    nearestComputed: !!raw?.nearestComputed,
    medoids: raw?.medoids ?? {},
    artifact: raw?.artifact,
    evidence: raw?.evidence,
    thumb: Array.isArray(raw?.thumb) ? raw.thumb : [],
    refused: raw?.refused ?? (entry?.recording && HELD_OUT.includes(entry.recording) ? refusal(entry.recording) : undefined),
  }
}

/* ---------------------------------------------------------------- reads ---------------------------------------------------------------- */

export const getQueues = (): Promise<Sourced<ReviewQueue[]>> =>
  live(req<SrvQueue[]>('/queues').then(qs => qs.map(queueOf)))

/** Every queue with its rows (queue picker and queue rail counts). */
export async function getAllQueues(): Promise<Sourced<QueueData[]>> {
  const heads = await req<SrvQueue[]>('/queues')
  const all = await Promise.all(heads.map(h => getQueue(String(h.id))))
  return { data: all.map(a => a.data!).filter(Boolean), source: 'live' }
}

/** Settings › Vocabulary: classes bound to number keys, verdict colours, tag suggestions. Synchronous because the
 *  key handlers need it on the first keypress; a live version would load it once at startup. */
export const VOCABULARY = {
  classes: CLASSES.map(c => ({ key: c.key as string, name: c.name as string, colour: c.colour as string, informative: c.informative as boolean })),
  verdictColours: Object.fromEntries(VERDICTS.map(v => [v.key, v.colour])) as Record<string, string>,
  tagSuggestions: [...REVIEW_TAG_SUGGESTIONS],
  morphologyTags: [...MORPHOLOGY_TAGS],
}

export function getQueue(queueId: string): Promise<Sourced<QueueData | null>> {
  return live(req<SrvQueueData>(`/queues/${encodeURIComponent(queueId)}`).then(d => {
    if (!d?.queue) return null
    const queue = queueOf(d.queue)
    const raw = (d.rows ?? d.items ?? []) as any[]
    const rows = raw.map(r => rowOf(r, queue.id)).filter(r => !HELD_OUT.includes(r.recording))
    // The queue rail's channel filter is `f.channels.includes(r.channel)`, and its
    // default is the queue's own channel list. An empty list therefore matches
    // NOTHING: the rail read "129 left · No items match these filters", which is
    // a filter excluding every row while the count says they are there. Both
    // fields are properties of the rows that came back, so they are derived here
    // rather than left at the fixture-era empty defaults.
    queue.channels = Array.from(new Set(rows.map(r => r.channel).filter(Boolean)))
    const scores = rows.map(r => r.score).filter((v): v is number => typeof v === 'number')
    queue.scoreFloor = scores.length ? Math.min(...scores) : null
    return { queue, rows, clusters: (d.clusters ?? []) as ReviewCluster[] }
  }))
}

export function getItem(queueId: string, itemId: string): Promise<Sourced<ItemDetail | null>> {
  return live(req<any>(`/queues/${encodeURIComponent(queueId)}/items/${encodeURIComponent(itemId)}`)
    .then(d => (d ? detailOf(d) : null)))
}

export function getCluster(queueId: string, no: number): Promise<Sourced<ClusterDetail | null>> {
  return live(req<any>(`/queues/${encodeURIComponent(queueId)}/cluster/${no}`).then(d => {
    if (!d?.cluster) return null
    const queue = d.queue ? queueOf(d.queue as SrvQueue) : undefined
    return {
      cluster: d.cluster as ReviewCluster,
      queue: queue as ReviewQueue,
      members: ((d.members ?? []) as any[]).map(m => detailOf(m, queue)),
    }
  }))
}

/** Which queue a cluster number belongs to (the `#/review/cluster/<n>` alias). KNOWN REMAINDER: synchronous,
 *  so it still resolves against the fixture cluster list — there is no synchronous live source and every
 *  caller would have to become async to get one. */
export function clusterQueue(no: number): string | null { return CLUSTERS.find(c => c.no === no)?.queueId ?? null }

export function getOtherChannels(queueId: string, itemId: string): Promise<Sourced<OtherChannelRow[]>> {
  return live(req<OtherChannelRow[]>(`/queues/${encodeURIComponent(queueId)}/items/${encodeURIComponent(itemId)}/channels`)
    .then(rows => (Array.isArray(rows) ? rows : [])))
}

/* ---------------------------------------------------------------- writes --------------------------------------------------------------- */
/* The keyboard writes to the DATABASE. Every verdict, batch, undo, promotion, cluster decision and
 * extraction below is a POST to `server/review.py`, which calls `Working.review` — the client holds no
 * verdict logic and decides nothing about which table a verdict lands in (that is the queue's stored
 * `writes_to`, enforced in the core by refusal).
 *
 * Non-2xx THROWS `ApiError`, exactly as the reads do. Nothing here is caught into a blank and nothing
 * falls back to the in-memory store: a refused verdict has to reach the page, because a Review surface
 * that drops verdicts on the floor looks identical to one that is working. */

/** One POST. Same error contract as `req`: the server's message, and its traceback on a 500. */
async function post<T>(path: string, body: unknown = {}): Promise<T> {
  const r = await fetch(`/api/review${path}`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) {
    let payload: any = null
    try { payload = await r.json() } catch { /* not json */ }
    const msg = payload?.error ?? (typeof payload?.detail === 'string' ? payload.detail : payload?.detail?.message) ?? `${r.status} ${r.statusText}`
    throw new ApiError(r.status, msg, payload?.detail ?? payload, payload?.traceback)
  }
  return r.json() as Promise<T>
}

/** The live counts the bridge returns with every write, straight off the resolved source. */
export interface QueueCounts { total: number; judged: number; remaining: number }
export interface WriteAck { verdict?: unknown; batch?: unknown; undone?: unknown; written?: unknown[]; counts?: QueueCounts }
export interface PromoteAck { entry_id?: number; member_id?: number; created?: boolean; verdict?: unknown; audit_id?: number }
export interface ExtractEvent { start_idx: number; end_idx: number }

/** `note` and `tags` are the queue's optional annotation of the verdict. NOTE: no caller passes `tags`
 *  yet — the bridge's body takes `list[str]` while the core's writers take `{category: [values]}`, so a
 *  tag sent from here would 500. Named here rather than silently dropped. */
export interface VerdictOpts { note?: string; tags?: string[]; windowIndex?: number }

const qp = (queueId: string) => `/queues/${encodeURIComponent(queueId)}`
const opt = (o: VerdictOpts) => ({
  ...(o.note ? { note: o.note } : {}),
  ...(o.tags && o.tags.length ? { tags: o.tags } : {}),
  ...(o.windowIndex != null ? { window_index: o.windowIndex } : {}),
})

/** One verdict on one target. `targetId` is the row's `id`, which IS the core's `target_id`. */
export const postVerdict = (queueId: string, targetId: string, verdict: Verdict, o: VerdictOpts = {}): Promise<WriteAck> =>
  post<WriteAck>(`${qp(queueId)}/verdict`, { target_id: targetId, verdict, ...opt(o) })

/** N targets under ONE `review_audit` row, so one undo reverses the gesture as the single act it was. */
export const postBatch = (queueId: string, targetIds: string[], verdict: Verdict, o: VerdictOpts = {}): Promise<WriteAck> =>
  post<WriteAck>(`${qp(queueId)}/batch`, { target_ids: targetIds, verdict, ...opt(o) })

/** Ctrl-Z. The SERVER owns undo: it restores the prior verdict from `review_audit.payload_json`. The
 *  client never invents a reversal — reversing to unjudged and reversing to "it was interesting before"
 *  are different acts and only the audit row knows which one this is. */
export const postUndo = (queueId: string): Promise<WriteAck> => post<WriteAck>(`${qp(queueId)}/undo`, {})

/** P21: the seed verdict plus the Library entry/member it mints, in one core call. */
export const postPromote = (queueId: string, targetId: string, verdict: Verdict = 'seed', o: VerdictOpts = {}): Promise<PromoteAck> =>
  post<PromoteAck>(`${qp(queueId)}/promote`, { target_id: targetId, verdict, ...opt(o) })

/** A whole cluster accepted or rejected — the bridge resolves the members and writes them as one batch. */
export const postClusterVerdict = (queueId: string, no: number, decision: 'accept' | 'reject'): Promise<WriteAck> =>
  post<WriteAck>(`${qp(queueId)}/cluster/${no}/${decision}`, {})

/** extract-events: the spans a reviewer marked inside a flagged sequence. */
export const postExtract = (queueId: string, sequenceId: string, events: ExtractEvent[], complete = false): Promise<WriteAck> =>
  post<WriteAck>(`${qp(queueId)}/extract`, { sequence_id: sequenceId, events, complete })
