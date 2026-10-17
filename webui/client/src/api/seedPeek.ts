/* a2-p4: the Seed page's preview, READ and never started (round A_2, 2026-10-17).
 *
 * Choosing a seed used to start the preview at once, and so did every change of channel, section, scale bank or
 * exclusion step — one heavy search (up to 200 noise copies per channel) per slider step. The researcher asked
 * that nothing run until *Run preview* or *Run seed search* is pressed. So the page's read only PEEKS, through
 * `GET /api/discovery/seed/results`, which never computes, and ends one of these ways:
 *
 *  - `ready`: a result is in hand for this query (cached, imported from the cluster, or a job just finished);
 *  - a job is running for this query (started by *Run preview*, here or in another tab, or a seed run drawing the
 *    preview first — `drawnBy`): it is joined and watched — its progress reported — until it ends;
 *  - `not-run` (nothing is running and nothing is kept), `cancelled` (the newest job for the query was
 *    cancelled, and a cancelled preview is never kept), or `failed` (the newest job failed: its message and
 *    traceback come with it, and the page offers *Run preview* beside them).
 *
 * The one request that starts it, *Run preview*, is `api/discovery.ts::runSeedPreview`. This module cannot start anything:
 * it is pure TypeScript with no imports and is handed its read, so the headless suite runs it under Node
 * (tests/test_webui_seed_on_demand_client.py), as it runs charts/domain.ts. */

/** A seed run drawing this query's preview as the first act of its own job (it was asked for the preview's null
 *  before a preview was in): the preview is that run's, so it is watched here and stopped from the run. */
export interface PreviewDrawnBy { runKey: string; label: string }

/** What the bridge answers while there is no result for the query. `job_id` is the running job's (null when
 *  none runs); `cancelled` / `cancelledJob` say the newest job for the query was cancelled; `failed` / `failedJob`
 *  / `error` that it failed, with the job's own message and traceback; `drawnBy` that a seed run is drawing it. */
export interface PreviewPending {
  ready: false
  job_id: number | null
  cancelled?: boolean | null
  cancelledJob?: number | null
  failed?: boolean | null
  failedJob?: number | null
  error?: { message?: string | null; traceback?: string | null } | null
  drawnBy?: PreviewDrawnBy | null
  progress?: { done?: number; total?: number; message?: string } | null
  elapsedS?: number | null
  etaS?: number | null
  note?: string | null
}

/** A running job's progress, in units of work (the search plus every draw, per channel), and the run drawing it
 *  when the job is a seed run's rather than a preview's own. */
export interface PreviewProgress { done: number; total: number; message: string; elapsedS: number | null; etaS: number | null; jobId: number; drawnBy: PreviewDrawnBy | null }

/** What a failed preview left: the job's own words and its traceback, shown on the face. */
export interface PreviewFailure { message: string; traceback: string | null }

export type PreviewPeek<T> =
  | { status: 'ready'; result: T }
  | { status: 'not-run'; note: string | null }
  | { status: 'cancelled'; jobId: number | null; note: string | null }
  /** fix round (F1): the newest job for the query failed. A state, not a thrown read: the read that threw left the
   *  page no way to run the query again, because its Retry only read again. */
  | { status: 'failed'; jobId: number | null; note: string | null; error: PreviewFailure }

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
 *  a search — there is nothing here that could. A read that fails (the bridge refusing the query) throws. */
export async function peekPreview<T extends { ready: true }>(get: () => Promise<T | PreviewPending>, o: PeekOptions): Promise<PreviewPeek<T>> {
  const now = o.now ?? (() => Date.now())
  const startedAt = now()
  for (;;) {
    if (o.alive && !o.alive()) throw (o.superseded ? o.superseded() : new Error('superseded by a newer search on the page'))
    const r = await get()
    if (r.ready) return { status: 'ready', result: r as T }
    const pending = r as PreviewPending
    if (pending.job_id == null) {
      if (pending.failed) {
        return { status: 'failed', jobId: pending.failedJob ?? null, note: pending.note ?? null,
          error: { message: pending.error?.message ?? 'the preview failed and the bridge gave no message', traceback: pending.error?.traceback ?? null } }
      }
      return pending.cancelled
        ? { status: 'cancelled', jobId: pending.cancelledJob ?? null, note: pending.note ?? null }
        : { status: 'not-run', note: pending.note ?? null }
    }
    o.onProgress?.({
      done: pending.progress?.done ?? 0, total: pending.progress?.total ?? 0, message: pending.progress?.message ?? '',
      elapsedS: pending.elapsedS ?? null, etaS: pending.etaS ?? null, jobId: pending.job_id, drawnBy: pending.drawnBy ?? null,
    })
    if (now() - startedAt > (o.giveUpMs ?? PEEK_GIVE_UP_MS)) {
      throw (o.timedOut ? o.timedOut(pending) : new Error(`the preview is still running after ${Math.round((o.giveUpMs ?? PEEK_GIVE_UP_MS) / 60000)} minutes`))
    }
    await o.sleep(o.pollMs ?? PEEK_POLL_MS)
  }
}
