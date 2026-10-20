/* site-runs item 4 (2026-10-20): the scoreboard's answer counts only for the read it answers.
 * Pure (no runtime imports) so tests/test_site_runs_scope_link.py runs it under Node.
 *
 * The cause of "Send 0 unjudged" and "no finished run on this scope yet" beside a run whose detections were on
 * screen: the first scoreboard read goes out before the runs are in, with no run keys, and answers [] at once.
 * `useSourced` keeps the last answer while the next read is out, and the real read over the researcher's session
 * (16 channels x 52 runs, 721 h) took 461 s cold on a copy of the real database — so the [] stood for minutes.
 * An answer is now tagged with the key it was read for, and any other key reads "not in yet" (null). */

export const scoreKey = (runKeys: string[], channels: string[], section: [number, number]) =>
  `${runKeys.join(',')}|${channels.join(',')}|${section.join(',')}`

export interface KeyedScores<T> { key: string; rows: T[] }

/** The rows when `read` answered `key`, else null: never an answer for another set of runs. */
export function scoresFor<T>(read: KeyedScores<T> | null, key: string): T[] | null {
  return read && read.key === key ? read.rows : null
}
