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
import { useEffect, useState } from 'react'
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

/* ---------------- a trace WITH its axis (fixup-g) ----------------
 * The bridge used to serve a decimated envelope's VALUES and discard its `t`, on a contract that "the x axis is
 * implied". `decimate.envelope` returns fewer, non-uniformly spaced points once a window exceeds 2 x px, so the
 * page drew everything right of t0 compressed by n_points/n_source while it drew the highlight band in true
 * seconds (U2), each bucket's min and max a whole "second" apart (U1's zigzag), and sliced envelope points as
 * though they were seconds for the padding (U3). Every trace now says where each point is. */

/** Which recording a trace was drawn from, and at what rate — the card says it, because "this event looks
 *  smooth" means something different at 1 Hz and at 10 Hz (Q24). */
export interface TraceSource {
  recording_id: number; label: string; source_file?: string; channel: string; fs: number; n_samples?: number
  /** `self`: the item's own recording. `parent`: the higher-resolution recording it was decimated from. */
  kind: 'self' | 'parent'; decimation: number | null; offset?: number | null
}
export interface TimeTrace {
  /** Seconds (absolute in the item's recording) and mV; a null is an all-NaN envelope bucket. Same length. */
  t: number[]; v: (number | null)[]
  /** The window's own edges, in the same seconds — the x extent to draw, whatever the points cover. */
  t0_s: number; t1_s: number
  fs: number | null
  /** Samples in the window, points served, and whether the points are a min/max envelope of the samples. */
  n_source: number; n_points: number; decimated: boolean
  /** The pixel budget the bridge served at; `capped` when the width asked for exceeded the bound and points were lost. */
  px: number; capped: boolean
  unit: string | null
  source: TraceSource | null
  /** Why the trace is empty, when it is. */
  reason?: string | null
}
export const EMPTY_TRACE: TimeTrace = { t: [], v: [], t0_s: 0, t1_s: 0, fs: null, n_source: 0, n_points: 0, decimated: false, px: 0, capped: false, unit: null, source: null, reason: null }

/** A served trace, validated: `t` and `v` are same-length arrays or the trace is empty WITH a reason. A bridge
 *  that sent a bare value list (the old contract) is reported, not drawn on a guessed axis. */
function traceOf(raw: any): TimeTrace {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return { ...EMPTY_TRACE, reason: Array.isArray(raw) ? 'the bridge served a trace without its time axis' : (raw == null ? 'no trace was served' : 'malformed trace') }
  }
  const t = Array.isArray(raw.t) ? raw.t as number[] : []
  const v = Array.isArray(raw.v) ? raw.v as (number | null)[] : []
  if (t.length !== v.length) return { ...EMPTY_TRACE, reason: `the trace's axis has ${t.length} times for ${v.length} values` }
  return {
    t, v,
    t0_s: Number(raw.t0_s ?? (t.length ? t[0] : 0)), t1_s: Number(raw.t1_s ?? (t.length ? t[t.length - 1] : 0)),
    fs: raw.fs == null ? null : Number(raw.fs),
    n_source: Number(raw.n_source ?? v.length), n_points: Number(raw.n_points ?? v.length), decimated: !!raw.decimated,
    px: Number(raw.px ?? 0), capped: !!raw.capped, unit: raw.unit ?? null,
    source: raw.source ?? null, reason: raw.reason ?? null,
  }
}

/** What the card tells the bridge: the width that will draw the traces (device pixels, so it is never served
 *  fewer points than pixels) and the context padding shown (seconds, symmetric). */
export interface TraceOpts { px?: number; padS?: number }
function traceQuery(o: TraceOpts = {}): string {
  const p = new URLSearchParams()
  if (o.px && o.px > 0) p.set('px', String(Math.round(o.px)))
  if (o.padS != null && o.padS >= 0) p.set('pad_s', String(Math.round(o.padS)))
  const s = p.toString()
  return s ? `?${s}` : ''
}

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
  /** The candidate with its padding, over exactly the window the card shows (`pad_s`), with its axis. */
  context: TimeTrace
  /** The candidate's own samples, from its own recording. */
  shape: TimeTrace
  /** The same window from the higher-resolution recording this one was decimated from (Q24) — at the parent's
   *  rate, in THIS recording's seconds — or null, with `shapeSourceReason` saying why. */
  shapeSource: TimeTrace | null
  shapeSourceReason: string | null
  nearest: NearestFamily[]; medoids: Record<string, number[]>
  /** Whether anything actually computed family affinity. An empty `nearest` with
   *  `nearestComputed: false` means nobody looked; with `true` it means nothing is near. */
  nearestComputed?: boolean
  artifact: ArtifactPanel; evidence: Evidence; thumb: number[]
  /** Set when the item belongs to a held-out recording (D6): nothing else is served. */
  refused?: string
}

export interface ClusterDetail { cluster: ReviewCluster; queue: ReviewQueue; members: ItemDetail[] }
export interface OtherChannelRow { channel: string; r: number | null; trace: TimeTrace; current: boolean }

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
  total?: number; judged?: number; remaining?: number; pace_s?: number | null
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
    total: Number(q.total ?? 0), judged: Number(q.judged ?? 0),
    // measured off `review_audit` by the core; null until there are two
    // gestures to measure between, and 0 means "faster than the ledger's
    // one-second resolution", not "unmeasured" (fixup-a item 8)
    paceS: q.pace_s == null ? null : Number(q.pace_s),
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
    context: traceOf(raw?.context),
    shape: traceOf(raw?.shape),
    shapeSource: raw?.shapeSource ? traceOf(raw.shapeSource) : null,
    shapeSourceReason: raw?.shapeSource ? null : (typeof raw?.shapeSourceReason === 'string' ? raw.shapeSourceReason : 'the bridge offered no source resolution for this item'),
    nearest: Array.isArray(raw?.nearest) ? raw.nearest : [],
    nearestComputed: !!raw?.nearestComputed,
    medoids: raw?.medoids ?? {},
    artifact: raw?.artifact,
    evidence: raw?.evidence,
    thumb: Array.isArray(raw?.thumb) ? raw.thumb : [],
    /* by the bridge's own flag, never by matching the label: a display name is not an identifier (fixup-f) */
    refused: raw?.refused ?? (entry?.heldOut ? refusal(entry.recording) : undefined),
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
    const rows = raw.map(r => rowOf(r, queue.id)).filter(r => !r.heldOut)
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

/** `opts.px` is the width of the plot that will draw the traces and `opts.padS` the context padding shown;
 *  the bridge sizes and pads the traces to them (fixup-g). */
export function getItem(queueId: string, itemId: string, opts: TraceOpts = {}): Promise<Sourced<ItemDetail | null>> {
  return live(req<any>(`/queues/${encodeURIComponent(queueId)}/items/${encodeURIComponent(itemId)}${traceQuery(opts)}`)
    .then(d => (d ? detailOf(d) : null)))
}

export function getCluster(queueId: string, no: number, opts: TraceOpts = {}): Promise<Sourced<ClusterDetail | null>> {
  return live(req<any>(`/queues/${encodeURIComponent(queueId)}/cluster/${no}${traceQuery(opts)}`).then(d => {
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

export function getOtherChannels(queueId: string, itemId: string, opts: TraceOpts = {}): Promise<Sourced<OtherChannelRow[]>> {
  return live(req<any[]>(`/queues/${encodeURIComponent(queueId)}/items/${encodeURIComponent(itemId)}/channels${traceQuery(opts)}`)
    .then(rows => (Array.isArray(rows) ? rows.map(r => ({ channel: String(r?.channel ?? ''), r: r?.r ?? null, trace: traceOf(r?.trace), current: !!r?.current })) : [])))
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

/** `note` and `tags` are the queue's optional annotation of the verdict. A bare list is routed by the
 *  core to the category that defines each term, and lands in whatever table the queue's `writes_to`
 *  names — `adjudication_tags` for a detection, `annotation_tags` for a human span (rule 5). A term
 *  outside `tag_vocabulary` is a 400 that refuses the WHOLE verdict, which is why the Annotate card
 *  offers `useTagVocabulary()` and refuses an unknown term itself. */
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


/* ---------------- the tag vocabulary (fixup-a item 9) ----------------
 * The Annotate card's suggestions used to be three fixture words
 * (`spike-train`, `regular`, `decaying`), none of which is in
 * `tag_vocabulary` — so wiring the card's tags to the write path without
 * this would have turned every tagged verdict into a 400. The 36 live terms
 * come from the route Settings › Vocabulary already serves. */
export interface TagTerm { category: string; value: string }

let tagVocabCache: Promise<TagTerm[]> | null = null

export function getTagVocabulary(): Promise<TagTerm[]> {
  if (!tagVocabCache) {
    tagVocabCache = fetch('/api/settings/vocabulary')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`${r.status} ${r.statusText}`))))
      .then((d: { tags?: { category: string; value: string; active?: number | boolean }[] }) =>
        (d.tags ?? []).filter(t => t.active !== 0 && t.active !== false).map(t => ({ category: t.category, value: t.value })))
      .catch(e => { tagVocabCache = null; throw e })
  }
  return tagVocabCache
}

/** The vocabulary for the Annotate card. `null` while it is loading or if the read failed — the card
 *  says so rather than offering terms the write path would refuse. */
export function useTagVocabulary(): { terms: TagTerm[] | null; error: string | null } {
  const [state, setState] = useState<{ terms: TagTerm[] | null; error: string | null }>({ terms: null, error: null })
  useEffect(() => {
    let alive = true
    getTagVocabulary().then(
      terms => { if (alive) setState({ terms, error: null }) },
      e => { if (alive) { console.error('tag vocabulary unavailable', e); setState({ terms: null, error: e instanceof Error ? e.message : String(e) }) } })
    return () => { alive = false }
  }, [])
  return state
}
