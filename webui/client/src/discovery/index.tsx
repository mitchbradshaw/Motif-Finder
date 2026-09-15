/* Discovery workspace entry — owned by the Discovery builder. Routes: runs, seed, compare, compare/stages. */
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'

export function DiscoveryPage() {
  const { route } = useApp()
  const [page, sub] = route.parts
  if (page === 'seed') return <Skeleton id="discovery.seed" />
  if (page === 'compare') return sub === 'stages' ? <Skeleton id="discovery.stages" /> : <Skeleton id="discovery.compare" />
  return <Skeleton id="discovery.runs" />
}
