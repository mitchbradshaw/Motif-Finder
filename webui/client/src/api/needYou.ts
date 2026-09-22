/* The header's "N need you": how many items are waiting for a person across every open review queue.
 *
 * It lived as the fixture constant `DEMO_NEED_YOU = 3` while `/api/review/counts` — a route that exists,
 * is tested, and said 160 — was never called. That chip is the one piece of chrome whose whole job is to
 * tell a researcher there is work waiting, so a decorative number there is worse than none.
 *
 * A failed read resolves to 0 rather than throwing: this is ambient chrome on every page, and a Review
 * outage must not take the Explore header down with it. The failure is logged, not swallowed silently. */
import { useEffect, useState } from 'react'

interface Counts { need_you?: number }

export function useReviewNeedYou(): number {
  const [n, setN] = useState(0)
  useEffect(() => {
    let alive = true
    fetch('/api/review/counts', { headers: { 'content-type': 'application/json' } })
      .then(r => (r.ok ? (r.json() as Promise<Counts>) : Promise.reject(new Error(`${r.status} ${r.statusText}`))))
      .then(d => { if (alive) setN(Number(d?.need_you ?? 0)) },
            e => { if (alive) { console.warn('review counts unavailable for the header chip', e); setN(0) } })
    return () => { alive = false }
  }, [])
  return n
}
