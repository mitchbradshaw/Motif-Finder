/* Queue order, units (item or cluster), counts and navigation — pure helpers over the queue read + the records. */
import { navigate } from '../state'
import type { QueueData, QueueRow } from '../api/review'
import { effective, key, type QueueFilters, type VerdictRecord } from './store'
import { baseJudged } from './judged'

export type UnitRef = { kind: 'item'; id: string } | { kind: 'cluster'; no: number; members: string[] }
type Records = Record<string, VerdictRecord | null | undefined>

export const unitHash = (queueId: string, u: UnitRef) => u.kind === 'item' ? `review/queue/${queueId}/${u.id}` : `review/queue/${queueId}/cluster/${u.no}`
export const unitKey = (u: UnitRef) => u.kind === 'item' ? u.id : `cluster/${u.no}`

/** Replace the current history entry (redirects must not trap Back). */
export function replaceHash(path: string) {
  history.replaceState(null, '', `#/${path.replace(/^#?\//, '')}`)
  window.dispatchEvent(new HashChangeEvent('hashchange'))
}

/* AR (the speed pass): a queue read is immutable once it arrives, so its row index and its unit lists are built once
 * per read and kept beside it. Every lookup below used to be `data.rows.find`, and `currentUnit`, the queue rail's
 * filter and the up-next list each did one per unit — quadratic, 10^8 steps a render at 10,000 rows. */
const ROW_INDEX = new WeakMap<QueueData, Map<string, QueueRow>>()
export function rowById(data: QueueData, id: string): QueueRow | undefined {
  let m = ROW_INDEX.get(data)
  if (!m) { m = new Map(data.rows.map(r => [r.id, r])); ROW_INDEX.set(data, m) }
  return m.get(id)
}
const UNITS = new WeakMap<QueueData, Map<string, UnitRef[]>>()
const UNIT_AT = new WeakMap<UnitRef[], Map<string, number>>()

/** Units in queue order. With grouping on, the members of a cluster collapse into one unit at the first member's place. */
export function units(data: QueueData, group: QueueFilters['group'] = 'sequence'): UnitRef[] {
  const g = group === 'none' ? 'none' : 'grouped'
  let byGroup = UNITS.get(data)
  if (!byGroup) { byGroup = new Map(); UNITS.set(data, byGroup) }
  const hit = byGroup.get(g)
  if (hit) return hit
  const built = buildUnits(data, group)
  byGroup.set(g, built)
  return built
}

function buildUnits(data: QueueData, group: QueueFilters['group']): UnitRef[] {
  const out: UnitRef[] = []
  const seen = new Set<number>()
  for (const r of data.rows) {
    if (r.clusterNo != null && group !== 'none') {
      if (seen.has(r.clusterNo)) continue
      seen.add(r.clusterNo)
      const c = data.clusters.find(x => x.no === r.clusterNo)
      out.push({ kind: 'cluster', no: r.clusterNo, members: c ? c.members : data.rows.filter(x => x.clusterNo === r.clusterNo).map(x => x.id) })
    } else out.push({ kind: 'item', id: r.id })
  }
  return out
}

/** Does the DATABASE hold a verdict on this row? The session's own write wins when there is one (that is
 *  what Ctrl-Z reverses); otherwise it is the bridge's `judged` flag, which `queue_items` reports off the
 *  table the queue writes. `judged` is used and not a synthesised `baseVerdict`, because the bridge sends
 *  no verdict VALUE for an item judged in an earlier session and a guessed one would be a fabricated human
 *  verdict on the screen. */
export function judged(records: Records, row: QueueRow): boolean {
  const k = key(row.queueId, row.id)
  if (k in records && records[k] !== undefined) return records[k] !== null
  return baseJudged(row)
}

/** night-a: the record of a verdict the DATABASE holds for this queue (or this session wrote) — `effective()` only when
 *  `judged()`; a prior or carried verdict on an unjudged row is shown, never treated as given. */
export function judgedRecord(records: Records, row: QueueRow): VerdictRecord | null {
  return judged(records, row) ? effective(records, row) : null
}

export function isJudged(data: QueueData, records: Records, u: UnitRef): boolean {
  const ids = u.kind === 'item' ? [u.id] : u.members
  const rows = ids.map(id => rowById(data, id)).filter(Boolean) as QueueRow[]
  return u.kind === 'item' ? judged(records, rows[0]) : rows.some(r => judged(records, r))
}

export function currentUnit(data: QueueData, records: Records): UnitRef | null {
  return units(data).find(u => !isJudged(data, records, u)) ?? null
}

export function indexOf(list: UnitRef[], u: UnitRef | { kind: 'item'; id: string }) {
  // AR: the first unit that is `u` or (for an item) the cluster holding it — from an index built once per list
  let at = UNIT_AT.get(list)
  if (!at) {
    at = new Map()
    list.forEach((x, i) => {
      const k = unitKey(x)
      if (!at!.has(k)) at!.set(k, i)
      if (x.kind === 'cluster') for (const m of x.members) if (!at!.has(`member:${m}`)) at!.set(`member:${m}`, i)
    })
    UNIT_AT.set(list, at)
  }
  const own = at.get(unitKey(u as UnitRef))
  const held = u.kind === 'item' ? at.get(`member:${u.id}`) : undefined
  if (own === undefined) return held ?? -1
  return held === undefined ? own : Math.min(own, held)
}

export function nextUnjudgedAfter(data: QueueData, records: Records, u: UnitRef): UnitRef | null {
  const list = units(data)
  const i = indexOf(list, u)
  return list.slice(i + 1).find(x => !isJudged(data, records, x)) ?? null
}

export function step(data: QueueData, u: UnitRef, d: 1 | -1): UnitRef | null {
  const list = units(data)
  const i = indexOf(list, u)
  return list[i + d] ?? null
}

export function goUnit(queueId: string, u: UnitRef | null, emptyIfNone = true) {
  if (u) navigate(unitHash(queueId, u))
  else if (emptyIfNone) navigate(`review/queue/${queueId}?state=exhausted`)
}

/** Judged / left for the whole queue: the bridge's counts plus this session's not-yet-re-read writes. */
export function counts(data: QueueData, records: Records) {
  let delta = 0
  for (const r of data.rows) {
    const k = key(r.queueId, r.id)
    if (!(k in records) || records[k] === undefined) continue
    // the base is what the DATABASE said when the queue was last read, so a re-read after an accepted
    // write cancels its own delta instead of counting the same verdict twice
    delta += (records[k] ? 1 : 0) - (baseJudged(r) ? 1 : 0)
  }
  const judged = Math.min(data.queue.total, data.queue.judged + delta)
  return { judged, left: data.queue.total - judged, total: data.queue.total }
}

export function queueCounts(queueId: string, base: { judged: number; total: number }, rows: QueueRow[] | undefined, records: Records) {
  if (!rows) return { judged: base.judged, left: base.total - base.judged }
  let delta = 0
  for (const r of rows) {
    const k = key(queueId, r.id)
    if (!(k in records) || records[k] === undefined) continue
    delta += (records[k] ? 1 : 0) - (baseJudged(r) ? 1 : 0)
  }
  return { judged: base.judged + delta, left: base.total - base.judged - delta }
}

export function relTime(at: number, now: number) {
  const s = Math.max(0, Math.round((now - at) / 1000))
  if (s < 2) return 'just now'
  if (s < 60) return `${s} s ago`
  const m = Math.round(s / 60)
  return m < 60 ? `${m} min ago` : `${Math.round(m / 60)} h ago`
}
