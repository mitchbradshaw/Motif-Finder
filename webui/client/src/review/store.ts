/* Review's in-memory write path (brief: writes stay in memory; spec §10.3–10.6, P6, P20, P21).
 * One record per (queue, item) holds the current human verdict; every write is also a SessionWrite on an undo
 * stack whose entries carry before/after snapshots, so one Ctrl Z reverses a whole cluster batch (§10.5) and a
 * promotion (verdict + exemplar, §10.4) in one step. Survives navigation, not a reload. */
import { getDemo, recordDemoWrite, setDemo, useDemoState } from '../kit'
import type { QueueEntry, Verdict } from '../api/review'

export interface VerdictRecord {
  verdict: Verdict; className?: string; blind: boolean; at: number
  exemplarId?: string; family?: string | null; familyName?: string; tags?: string[]; note?: string
}
type Raw = VerdictRecord | null | undefined   // undefined = no session override (fixture state applies)

export interface SessionWrite {
  id: number; queueId: string; items: string[]; kind: 'verdict' | 'class' | 'promotion' | 'batch' | 'tags'
  label: string; clusterNo?: number; verdict?: Verdict; className?: string; count?: number
  before: Record<string, Raw>; after: Record<string, Raw>; at: number; undone: boolean; undoneAt?: number
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
