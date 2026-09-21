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
  type ArtifactFactors, type Evidence, type NearestFamily, type QueueEntry, type ReviewCluster, type ReviewQueue, type QueueSource, type Unit,
} from '../fixtures/review'

export type { ArtifactFactors, Evidence, NearestFamily, QueueEntry, ReviewCluster, ReviewQueue, QueueSource, Unit, Verdict } from '../fixtures/review'
export { CONTEXT_PAD_MAX } from '../fixtures/review'

export interface QueueRow extends QueueEntry { thumb: number[]; family: string }
export interface QueueData { queue: ReviewQueue; rows: QueueRow[]; clusters: ReviewCluster[] }

export interface ItemDetail {
  entry: QueueEntry; queue: ReviewQueue
  context: { values: number[]; t0_s: number }
  shape: number[]; nearest: NearestFamily[]; medoids: Record<string, number[]>
  artifact: ArtifactFactors; evidence: Evidence; thumb: number[]
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
  return {
    ...(raw as QueueEntry),
    id: String(raw?.id ?? ''),
    queueId,
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
