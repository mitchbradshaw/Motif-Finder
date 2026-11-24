/* AS (2026-11-24): Review's verdict saves, queued behind the researcher.
 *
 * The researcher: "can you prioritise feeding the next candidate in faster over saving verdicts, so that momentum
 * [can] be gained, candidates can be done quickly and consistently, and the lag for verdicts to catch up can increase
 * but still process slowly in the background?" So a verdict key moves the page on at once and its save waits here:
 *
 * - `SaveQueue` holds the saves not yet answered, in gesture order. `take()` hands out the waiting saves at the head,
 *   all of one queue, for ONE request (`POST …/verdicts`), and nothing more until those are `done()` — the bridge
 *   writes them in that order, one audit row each, so undo (which reverses the queue's newest audit row) still
 *   reverses the newest gesture. `withdrawLast()` is Ctrl Z on a save not sent yet: it is taken back and nothing is
 *   sent; on one in flight it answers 'sending' and the caller waits for the answer.
 * - The journal keeps every save not yet answered in `localStorage`, per queue, so a reload or a crash loses none:
 *   the next Review page replays a DEAD page's entries (each page stamps itself alive), never a live tab's. Each save
 *   carries a client id and the bridge answers one it already wrote with its original ack, so a replay that races a
 *   slow POST writes nothing twice.
 * - `mayFlush` is the priority rule: a save waits while an item read is in flight, up to SAVE_WAIT_CAP_MS.
 *
 * Pure, no imports: `tests/test_as_review_momentum.py` runs it under Node. */

/** the most verdicts one save request carries */
export const SAVE_BATCH_MAX = 50
/** how long a waiting save may be held back by item reads before it goes anyway (saves are the researcher's work) */
export const SAVE_WAIT_CAP_MS = 2000
/** a page whose alive stamp is older than this is gone; its journal entries are replayed by the next page */
export const PAGE_STALE_MS = 8000
export const JOURNAL_PREFIX = 'review.journal.'
export const PAGES_KEY = 'review.journal.pages'

export interface SaveBody { client_id: string; target_id: string; verdict: string; note?: string; tags?: string[]; class_label?: string }
export interface Pending<T> { queueId: string; body: SaveBody; meta: T; at: number; state: 'waiting' | 'sending' }

export class SaveQueue<T = unknown> {
  items: Pending<T>[] = []

  add(queueId: string, body: SaveBody, meta: T, at: number): Pending<T> {
    const p: Pending<T> = { queueId, body, meta, at, state: 'waiting' }
    this.items.push(p)
    return p
  }

  count(queueId?: string): number {
    return queueId == null ? this.items.length : this.items.filter(p => p.queueId === queueId).length
  }

  /** The waiting saves at the head, all of the head's queue, at most `max`, marked sending; none while the head is
   *  already sending (one request at a time keeps the audit rows in gesture order). */
  take(max: number = SAVE_BATCH_MAX, until: (p: Pending<T>) => boolean = () => true): Pending<T>[] {
    const head = this.items[0]
    if (!head || head.state !== 'waiting' || !until(head)) return []
    const out: Pending<T>[] = []
    for (const p of this.items) {
      // `until`: the store's barrier - a promotion or an undo given after a save goes before it
      if (p.state !== 'waiting' || p.queueId !== head.queueId || out.length >= max || !until(p)) break
      p.state = 'sending'
      out.push(p)
    }
    return out
  }

  /** Ctrl Z on this queue's newest save: taken back (and returned) while it waits; 'sending' once it is out. */
  withdrawLast(queueId: string): Pending<T> | 'sending' | null {
    for (let i = this.items.length - 1; i >= 0; i--) {
      const p = this.items[i]
      if (p.queueId !== queueId) continue
      if (p.state === 'sending') return 'sending'
      this.items.splice(i, 1)
      return p
    }
    return null
  }

  done(p: Pending<T>) {
    const i = this.items.indexOf(p)
    if (i >= 0) this.items.splice(i, 1)
  }

  oldestWaiting(): number | null {
    const p = this.items.find(x => x.state === 'waiting')
    return p ? p.at : null
  }
}

/** A save may go now: no item read is in flight, or the oldest waiting save has waited the cap. */
export function mayFlush(readsInFlight: number, oldestAt: number | null, now: number, capMs: number = SAVE_WAIT_CAP_MS): boolean {
  if (oldestAt == null) return false
  return readsInFlight <= 0 || now - oldestAt >= capMs
}

/* ---------------- the journal ---------------- */

export interface StorageLike { getItem(k: string): string | null; setItem(k: string, v: string): void; removeItem(k: string): void }
export interface JournalEntry extends SaveBody { at: number; label: string; page?: string }

function readJson<V>(store: StorageLike, k: string, fallback: V): V {
  try { const raw = store.getItem(k); return raw ? JSON.parse(raw) as V : fallback } catch { return fallback }
}

export function journalEntries(store: StorageLike, queueId: string): JournalEntry[] {
  const got = readJson<JournalEntry[]>(store, JOURNAL_PREFIX + queueId, [])
  return Array.isArray(got) ? got : []
}

export function journalAdd(store: StorageLike, queueId: string, entry: Omit<JournalEntry, 'page'>, page: string) {
  const list = journalEntries(store, queueId).filter(e => e.client_id !== entry.client_id)
  list.push({ ...entry, page })
  store.setItem(JOURNAL_PREFIX + queueId, JSON.stringify(list))
}

export function journalRemove(store: StorageLike, queueId: string, clientId: string) {
  const list = journalEntries(store, queueId)
  const left = list.filter(e => e.client_id !== clientId)
  if (left.length === list.length) return
  if (left.length) store.setItem(JOURNAL_PREFIX + queueId, JSON.stringify(left))
  else store.removeItem(JOURNAL_PREFIX + queueId)
}

/** This page is alive at `now` (called every couple of seconds while it has saves to make, and at load). */
export function touchPage(store: StorageLike, page: string, now: number) {
  const pages = readJson<Record<string, number>>(store, PAGES_KEY, {})
  pages[page] = now
  for (const [k, t] of Object.entries(pages)) if (now - t > 24 * 3600_000) delete pages[k]   // a day: long gone
  store.setItem(PAGES_KEY, JSON.stringify(pages))
}

/** This page is going away (unload): its entries are a dead page's from now, so the next page replays them at once. */
export function pageGone(store: StorageLike, page: string) {
  const pages = readJson<Record<string, number>>(store, PAGES_KEY, {})
  delete pages[page]
  store.setItem(PAGES_KEY, JSON.stringify(pages))
}

/** The journal entries of this queue left by a page that is gone — not this page's, not a live tab's — in order. */
export function orphaned(store: StorageLike, queueId: string, myPage: string, now: number, staleMs: number = PAGE_STALE_MS): JournalEntry[] {
  const pages = readJson<Record<string, number>>(store, PAGES_KEY, {})
  return journalEntries(store, queueId)
    .filter(e => e.page !== myPage && !(e.page && pages[e.page] != null && now - pages[e.page] < staleMs))
    .sort((a, b) => a.at - b.at)
}
