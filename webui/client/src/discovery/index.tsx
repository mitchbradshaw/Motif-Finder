/* Discovery workspace entry — owned by the Discovery builder. Routes: runs, seed, map, compare, compare/stages (spec §7, P17).
 * Every page reads fixtures through api/discovery.ts; the session (scope, runs, picks) is shared through session.ts. */
import './discovery.css'
import { useApp } from '../state'
import { RunsPage } from './RunsPage'
import { SeedPage } from './SeedPage'
import { ComparePage } from './ComparePage'
import { StagesPage } from './StagesPage'
import { MapPage } from './MapPage'

export function DiscoveryPage() {
  const { route } = useApp()
  const [page, sub] = route.parts
  if (page === 'seed') return <SeedPage />
  if (page === 'map') return <MapPage />
  if (page === 'compare') return sub === 'stages' ? <StagesPage /> : <ComparePage />
  return <RunsPage />
}
