/* night-review: which items the Inspector keeps warm while one is on screen, so the next card paints from memory.
 *
 * The window is the next PREFETCH_AHEAD unjudged items (where a verdict's auto-advance lands, one after another),
 * the very next unit (where → or Skip lands, judged or not) and the previous one (←), nearest first. Clusters are
 * not items (their read is the cluster route), so they are passed over. AS (2026-11-24): sixteen ahead, refilled in one
 * batch when it runs low (`refillIds`). Pure, no imports:
 * `tests/test_night_review.py` runs it under Node. The near sibling `nextUnjudgedAfter` (queue.ts) finds only the
 * first unjudged unit and imports the store; this walks the same list once for the whole window. */
export const PREFETCH_AHEAD = 16
/** AS (2026-11-24): the window is refilled when this many of its ids are missing (or the very next one is), all of
 *  them in ONE batched read; a refill of one id per step was a read per step again (the burst that emptied the
 *  five-deep window, measured: six fast steps, then 0.4-4 s each). */
export const REFILL_AT = 4

export interface WindowUnit { kind: 'item' | 'cluster'; id?: string }

export function prefetchIds(list: WindowUnit[], at: number, judgedAt: (i: number) => boolean, ahead: number = PREFETCH_AHEAD): string[] {
  const out: string[] = []
  if (at < 0 || at >= list.length) return out
  const add = (u: WindowUnit | undefined) => { if (u && u.kind === 'item' && u.id != null && !out.includes(u.id)) out.push(u.id) }
  let found = 0
  for (let i = at + 1; i < list.length && found < ahead; i++) {
    if (list[i].kind !== 'item' || judgedAt(i)) continue
    add(list[i]); found++
  }
  add(list[at + 1])
  add(list[at - 1])
  return out
}

/** AS: which of the window's ids to read now, in one request, nearest first: none while the window is nearly full; all
 *  the missing ones once REFILL_AT are missing, or as soon as the first (where the next verdict lands) is. */
export function refillIds(ids: string[], held: (id: string) => boolean, at: number = REFILL_AT): string[] {
  const missing = ids.filter(id => !held(id))
  if (!missing.length) return []
  return missing.length >= at || missing[0] === ids[0] ? missing : []
}
