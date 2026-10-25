/* night-a: whether the DATABASE holds this queue's verdict on a row, before any write of this session.
 *
 * The bridge's own `judged` flag decides when it sent one. A row can carry a verdict and still be unjudged in THIS
 * queue: an explore-spans queue serves human spans already marked `seed` that the queue has not asked about, and
 * counting them judged opened a 622-left queue on "No more items". That verdict is shown as the row's prefilled prior
 * (`baseVerdict`); it never makes the row judged. A row with no bridge flag (a fixture row) falls back to its verdict.
 *
 * tq-review (2026-10-25): applied once, in `rowOf`, as `QueueRow.judged`. The row used to keep a wrong `judged` beside
 * a corrected `servedJudged`, and every count re-derived the truth from both. Pure, no imports:
 * `tests/test_tq_review.py` runs it under Node. */
export function rowJudged(raw: { judged?: unknown; baseVerdict?: unknown; verdict?: unknown } | null | undefined): boolean {
  if (raw?.judged != null) return raw.judged === true || raw.judged === 1
  return !!(raw?.baseVerdict ?? raw?.verdict)
}
