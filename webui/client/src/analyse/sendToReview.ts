/* One call behind two buttons (fixup-L). The block page's slideshow *Send N to Review* and the chain
   footer's *Pass N to Review* both make a Review queue over the detections one completed run wrote —
   `POST /api/review/queues` with `{source_kind: 'discovery-run', filters: {run_id}}` — and open it. The
   queue is a filter over the rows the run wrote, not a copy, so nothing here duplicates a detection. */
import { useState } from 'react'
import { ApiError, sendRunToReview } from '../api'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'

export interface SendRunToReview {
  send: () => Promise<void>
  busy: boolean
  /** why the button is disabled, or undefined when it can be pressed */
  reason: string | undefined
}

export function useSendRunToReview(opts: { chainName: string; dbRunId: number | null; n: number; stale: boolean }): SendRunToReview {
  const { chainName, dbRunId, n, stale } = opts
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const reason = stale ? 'these spans are from a stale run · re-run first'
    : dbRunId === null ? 'needs a completed run: Review reads the detections the run wrote'
      : n === 0 ? 'no spans to review' : undefined
  const send = async () => {
    if (dbRunId === null || reason) return
    setBusy(true)
    try {
      const r = await sendRunToReview(`${chainName} · run #${dbRunId}`, dbRunId)
      toast.push({ text: `queue “${r.queue.name}” created over the ${n} detections of run #${dbRunId}` })
      navigate(`review/queue/${r.queue.id}`)
    } catch (e) {
      toast.push({ kind: 'error', text: `could not create the review queue · ${e instanceof ApiError ? e.message : String(e)}` })
    } finally { setBusy(false) }
  }
  return { send, busy, reason }
}
