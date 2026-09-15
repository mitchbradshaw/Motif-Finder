/* Review reads (spec §10). Every read returns Sourced<T>; until the bridge serves review queues these resolve
 * the fixtures in fixtures/review.ts and say `source: 'demo'`. Writes (verdicts, classes, promotions, blind
 * toggles) do not come through here: they go to the in-memory demo store (review/store.ts). */
import { demo, type Sourced } from './seam'
import { CLASSES, MORPHOLOGY_TAGS, RECORDINGS, VERDICTS } from '../fixtures/canon'
import {
  CLUSTERS, QUEUES, QUEUE_ENTRIES, REVIEW_TAG_SUGGESTIONS, artifactFactors, contextTrace, evidence, medoidTrace, nearestFamilies, otherChannels, shapeTrace, thumb,
  type ArtifactFactors, type Evidence, type NearestFamily, type QueueEntry, type ReviewCluster, type ReviewQueue,
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

export const getQueues = (): Promise<Sourced<ReviewQueue[]>> => demo(QUEUES)

/** Every queue with its rows (queue picker and queue rail counts). */
export async function getAllQueues(): Promise<Sourced<QueueData[]>> {
  const all = await Promise.all(QUEUES.map(x => getQueue(x.id)))
  return { data: all.map(a => a.data!).filter(Boolean), source: all.some(a => a.source === 'demo') ? 'demo' : 'live' }
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
  const queue = QUEUES.find(x => x.id === queueId)
  if (!queue) return demo(null)
  const rows = (QUEUE_ENTRIES[queueId] ?? []).filter(e => !HELD_OUT.includes(e.recording)).map(e => ({ ...e, thumb: thumb(e), family: nearestFamilies(e)[0].id }))
  return demo({ queue, rows, clusters: CLUSTERS.filter(c => c.queueId === queueId) })
}

function detail(entry: QueueEntry, queue: ReviewQueue): ItemDetail {
  const nearest = nearestFamilies(entry)
  return {
    entry, queue, context: contextTrace(entry), shape: shapeTrace(entry), nearest,
    medoids: Object.fromEntries(nearest.map(f => [f.id, medoidTrace(f.id, entry.durationS)])),
    artifact: artifactFactors(entry), evidence: evidence(entry, queue), thumb: thumb(entry),
    refused: HELD_OUT.includes(entry.recording) ? refusal(entry.recording) : undefined,
  }
}

export function getItem(queueId: string, itemId: string): Promise<Sourced<ItemDetail | null>> {
  const queue = QUEUES.find(x => x.id === queueId)
  const entry = QUEUE_ENTRIES[queueId]?.find(x => x.id === itemId)
  return demo(queue && entry ? detail(entry, queue) : null)
}

export function getCluster(queueId: string, no: number): Promise<Sourced<ClusterDetail | null>> {
  const cluster = CLUSTERS.find(c => c.no === no && c.queueId === queueId)
  const queue = QUEUES.find(x => x.id === queueId)
  if (!cluster || !queue) return demo(null)
  const members = cluster.members.map(id => detail(QUEUE_ENTRIES[queueId].find(x => x.id === id)!, queue))
  return demo({ cluster, queue, members })
}

/** Which queue a cluster number belongs to (the `#/review/cluster/<n>` alias). */
export function clusterQueue(no: number): string | null { return CLUSTERS.find(c => c.no === no)?.queueId ?? null }

export function getOtherChannels(queueId: string, itemId: string): Promise<Sourced<OtherChannelRow[]>> {
  const entry = QUEUE_ENTRIES[queueId]?.find(x => x.id === itemId)
  return demo(entry ? otherChannels(entry) : [], 120)
}
