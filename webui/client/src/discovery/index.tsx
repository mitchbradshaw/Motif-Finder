/* Discovery workspace entry — owned by the Discovery builder. Routes: runs, seed, compare, compare/stages (spec §7, P17).
 * Every page reads fixtures through api/discovery.ts; the session (scope, runs, picks) is shared through session.ts. */
import './discovery.css'
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'
import { RunsPage } from './RunsPage'

export function DiscoveryPage() {
  const { route } = useApp()
  const [page, sub] = route.parts
  if (page === 'seed') return <Skeleton id="discovery.seed" />
  if (page === 'compare') return sub === 'stages' ? <Skeleton id="discovery.stages" /> : <Skeleton id="discovery.compare" />
  return <RunsPage />
}
