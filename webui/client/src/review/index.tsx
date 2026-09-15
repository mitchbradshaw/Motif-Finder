/* Review workspace entry — owned by the Review builder.
   Routes: queue/<queueId>[/<itemId>] (inspector; blind queues are a state of it), queue/<queueId>/cluster/<n>. */
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'

export function ReviewPage() {
  const { route } = useApp()
  const p = route.parts
  if (p[0] === 'cluster' || (p[0] === 'queue' && p[2] === 'cluster')) return <Skeleton id="review.cluster" />
  return <Skeleton id="review.inspector" />
}
