/* Models workspace entry — owned by the Models builder. Routes: launch, results, compare, registry. */
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'

export function ModelsPage() {
  const { route } = useApp()
  const page = route.parts[0]
  if (page === 'results') return <Skeleton id="models.results" />
  if (page === 'compare') return <Skeleton id="models.compare" />
  if (page === 'registry') return <Skeleton id="models.registry" />
  return <Skeleton id="models.launch" />
}
