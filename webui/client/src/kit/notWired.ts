/* "No dead clicks" (brief): a control whose real behaviour would need the bridge or the core and cannot
 * sensibly be simulated shows a toast naming what it would call. Use sparingly — prefer a simulated
 * run (kit/sim.ts) or an in-memory write (kit/store.ts) whenever the frame shows a result. */
import { useCallback } from 'react'
import { useToast } from '../shell/Toast'

export function useNotWired() {
  const { push } = useToast()
  return useCallback((what: string) => { push({ text: `not wired yet: ${what}` }) }, [push])
}
