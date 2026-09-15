/* Queue order, units (item or cluster), counts and navigation — pure helpers over the queue read + the records. */
import { navigate } from '../state'
import type { QueueData, QueueRow } from '../api/review'
import { effective, key, type QueueFilters, type VerdictRecord } from './store'

export type UnitRef = { kind: 'item'; id: string } | { kind: 'cluster'; no: number; members: string[] }
type Records = Record<string, VerdictRecord | null | undefined>

export const unitHash = (queueId: string, u: UnitRef) => u.kind === 'item' ? `review/queue/${queueId}/${u.id}` : `review/queue/${queueId}/cluster/${u.no}`
export const unitKey = (u: UnitRef) => u.kind === 'item' ? u.id : `cluster/${u.no}`

/** Replace the current history entry (redirects must not trap Back). */
export function replaceHash(path: string) {
  history.replaceState(null, '', `#/${path.replace(/^#?\//, '')}`)
  window.dispatchEvent(new HashChangeEvent('hashchange'))
}

/** Units in queue order. With grouping on, the members of a cluster collapse into one unit at the first member's place. */
export function units(data: QueueData, group: QueueFilters['group'] = 'sequence'): UnitRef[] {
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

export function isJudged(data: QueueData, records: Records, u: UnitRef): boolean {
  const ids = u.kind === 'item' ? [u.id] : u.members
  const rows = ids.map(id => data.rows.find(r => r.id === id)).filter(Boolean) as QueueRow[]
  return u.kind === 'item' ? !!effective(records, rows[0]) : rows.some(r => !!effective(records, r))
}

export function currentUnit(data: QueueData, records: Records): UnitRef | null {
  return units(data).find(u => !isJudged(data, records, u)) ?? null
}

export function indexOf(list: UnitRef[], u: UnitRef | { kind: 'item'; id: string }) {
  return list.findIndex(x => unitKey(x) === unitKey(u as UnitRef) || (u.kind === 'item' && x.kind === 'cluster' && x.members.includes(u.id)))
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

/** Judged / left for the whole queue: the fixture's counts plus this session's writes on the materialised rows. */
export function counts(data: QueueData, records: Records) {
  let delta = 0
  for (const r of data.rows) {
    const k = key(r.queueId, r.id)
    if (!(k in records) || records[k] === undefined) continue
    delta += (records[k] ? 1 : 0) - (r.baseVerdict ? 1 : 0)
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
    delta += (records[k] ? 1 : 0) - (r.baseVerdict ? 1 : 0)
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
