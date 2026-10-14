/* A block's `derive` readout (POST /api/blocks/derive, server/readout.py), asked again on every edit:
   debounced, and one request in flight — an edit made meanwhile is asked for when that request lands, so a
   slow readout (up to the bridge's 2 s budget) never piles up behind typing. */
import { useEffect, useRef, useState } from 'react'
import { ApiError, getReadout, type Readout, type Step } from '../api'
import type { SourceSpan } from '../state'
import { isHeldOut } from './toolbar'
import { spanOf } from './useValidation'

export interface ReadoutState { r: Readout | null; error: { status: number; text: string } | null; pending: boolean }
interface Ask { steps: Step[]; index: number; recording_id: number; span: [number, number] | null; nudge: string }

const errText = (e: unknown) => e instanceof ApiError ? `${e.message}${e.traceback ? '\n' + e.traceback : ''}` : String(e)

/** Stage `index`'s readout, asked again when the chain up to it, the source or `nudge` changes — `nudge` is what
 *  it depends on outside the chain (a run that has just filled the step cache). The held-out recording is never
 *  sent (D6). */
export function useReadout(steps: Step[], index: number, source: SourceSpan | null, enabled: boolean, nudge: string, delayMs = 250): ReadoutState {
  const src = enabled && source && !isHeldOut(source) ? source : null
  // the key is the whole request: a stage after this one does not re-ask
  const key = src ? JSON.stringify({ steps: steps.slice(0, index + 1), index, recording_id: src.recording_id, span: spanOf(src), nudge } satisfies Ask) : null
  const [st, setSt] = useState<{ r: Readout | null; error: ReadoutState['error']; key: string | null }>({ r: null, error: null, key: null })
  const flight = useRef<{ busy: boolean; want: string | null }>({ busy: false, want: null })
  useEffect(() => {
    const f = flight.current
    f.want = key
    if (!key) return
    const send = () => {
      const k = f.want
      if (f.busy || !k) return
      f.busy = true
      const a = JSON.parse(k) as Ask
      getReadout(a.steps, a.index, a.recording_id, a.span)
        .then(r => { if (f.want === k) setSt({ r, error: null, key: k }) })
        .catch(e => {
          const status = e instanceof ApiError ? e.status : 0
          // a 4xx is the bridge refusing this chain (a stage refused the span, a parameter out of range): said on
          // the card. Anything else is a failure, and loud
          if (status < 400 || status >= 500) console.error('block readout failed', e)
          if (f.want === k) setSt({ r: null, error: { status, text: errText(e) }, key: k })
        })
        .finally(() => { f.busy = false; if (f.want && f.want !== k) send() })
    }
    const id = window.setTimeout(send, delayMs)
    return () => window.clearTimeout(id)
  }, [key, delayMs])
  useEffect(() => { const f = flight.current; return () => { f.want = null } }, [])   // nothing is asked for once the page has gone
  const mine = key !== null && st.key === key
  return { r: key ? st.r : null, error: mine ? st.error : null, pending: key !== null && !mine }
}
