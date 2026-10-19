/* night-a: whether the DATABASE holds this queue's verdict on a row, before any write of this session.
 *
 * The bridge's own `judged` flag decides when it sent one (`servedJudged`). A row can carry a verdict and still be
 * unjudged in THIS queue: an explore-spans queue serves human spans already marked `seed` that the queue has not
 * asked about, and counting them judged opened a 622-left queue on "No more items". That verdict is shown as the
 * row's prefilled prior (`baseVerdict`); it never makes the row judged. A row with no bridge flag (a fixture row)
 * falls back to its verdict. Pure, no imports: `tests/test_night_a_review.py` runs it under Node. */
export interface JudgedFlags { baseVerdict?: string | null; judged?: boolean; servedJudged?: boolean }

export function baseJudged(row: JudgedFlags): boolean {
  if (typeof row.servedJudged === 'boolean') return row.servedJudged
  return !!row.baseVerdict || row.judged === true
}
