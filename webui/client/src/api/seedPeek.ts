/* a2-p4: the Seed page's preview, READ and never started (round A_2, 2026-10-17).
 *
 * Choosing a seed used to start the preview at once, and so did every change of channel, section, scale bank or
 * exclusion step — one heavy search (up to 200 noise copies per channel) per slider step. The researcher asked
 * that nothing run until *Run preview* or *Run seed search* is pressed. So the page's read only PEEKS, through
 * `GET /api/discovery/seed/results`, which never computes, and ends one of three ways:
 *
 *  - `ready`: a result is in hand for this query (cached, imported from the cluster, or a job just finished);
 *  - a job is running for this query (started by *Run preview*, here or in another tab): it is joined and
 *    watched — its progress reported — until it ends;
 *  - `not-run` (nothing is running and nothing is kept) or `cancelled` (the newest job for the query was
 *    cancelled, and a cancelled preview is never kept).
 *
 * The one request that starts it, *Run preview*, is `api/discovery.ts::runSeedPreview`. This module cannot start anything:
 * it is pure TypeScript with no imports and is handed its read, so the headless suite runs it under Node
 * (tests/test_webui_seed_on_demand_client.py), as it runs charts/domain.ts. */

/** What the bridge answers while there is no result for the query. `job_id` is the running job's (null when
 *  none runs); `cancelled` / `cancelledJob` say the newest job for the query was cancelled. */
export interface PreviewPending {
  ready: false
  job_id: number | null
  cancelled?: boolean | null
  cancelledJob?: number | null
  progress?: { done?: number; total?: number; message?: string } | null
  elapsedS?: number | null
  etaS?: number | null
  note?: string | null
}

/** A running job's progress, in units of work (the search plus every draw, per channel). */
export interface PreviewProgress { done: number; total: number; message: string; elapsedS: number | null; etaS: number | null; jobId: number }

export type PreviewPeek<T> =
  | { status: 'ready'; result: T }
  | { status: 'not-run'; note: string | null }
  | { status: 'cancelled'; jobId: number | null; note: string | null }

export interface PeekOptions {
  sleep: (ms: number) => Promise<unknown>
  now?: () => number
  /** between two reads while a job runs */
  pollMs?: number
  /** a running job is watched this long at most (a long section's preview is hours) */
  giveUpMs?: number
  onProgress?: (p: PreviewProgress) => void
  /** false once the page has moved on to another query: this read is nobody's any more */
  alive?: () => boolean
  superseded?: () => Error
  timedOut?: (last: PreviewPending) => Error
}

export const PEEK_POLL_MS = 1500
export const PEEK_GIVE_UP_MS = 12 * 60 * 60 * 1000

/** Read the preview for one query: a result, a running job watched to its end, or why there is none. Never starts
 *  a search — there is nothing here that could. A read that fails (a 500 naming a failed job) throws. */
export async function peekPreview<T extends { ready: true }>(get: () => Promise<T | PreviewPending>, o: PeekOptions): Promise<PreviewPeek<T>> {
  const now = o.now ?? (() => Date.now())
  const startedAt = now()
  for (;;) {
    if (o.alive && !o.alive()) throw (o.superseded ? o.superseded() : new Error('superseded by a newer search on the page'))
    const r = await get()
    if (r.ready) return { status: 'ready', result: r as T }
    const pending = r as PreviewPending
    if (pending.job_id == null) {
      return pending.cancelled
        ? { status: 'cancelled', jobId: pending.cancelledJob ?? null, note: pending.note ?? null }
        : { status: 'not-run', note: pending.note ?? null }
    }
    o.onProgress?.({
      done: pending.progress?.done ?? 0, total: pending.progress?.total ?? 0, message: pending.progress?.message ?? '',
      elapsedS: pending.elapsedS ?? null, etaS: pending.etaS ?? null, jobId: pending.job_id,
    })
    if (now() - startedAt > (o.giveUpMs ?? PEEK_GIVE_UP_MS)) {
      throw (o.timedOut ? o.timedOut(pending) : new Error(`the preview is still running after ${Math.round((o.giveUpMs ?? PEEK_GIVE_UP_MS) / 60000)} minutes`))
    }
    await o.sleep(o.pollMs ?? PEEK_POLL_MS)
  }
}
