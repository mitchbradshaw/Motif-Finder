/* Jobs page entry — owned by the Jobs builder. Routes: (all), run/<id>, run/<id>/upload, cluster/<id>. */
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'

export function JobsPage() {
  const { route } = useApp()
  const p = route.parts
  if (p[0] === 'run') return p[2] === 'upload' ? <Skeleton id="jobs.upload" /> : <Skeleton id="jobs.paused" />
  if (p[0] === 'cluster') return <Skeleton id="jobs.cluster" />
  return <Skeleton id="jobs.all" />
}
