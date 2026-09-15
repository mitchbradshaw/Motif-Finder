/* Analyse › Interrogation entry — owned by the Interrogation builder. Routes: analyse/interrogation[/block/<n>]. */
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'

export function InterrogationPage() {
  const { route } = useApp()
  const [, block, n] = route.parts          // ['interrogation', 'block', '1']
  if (block === 'block' && n === '1') return <Skeleton id="analyse.interrogation.slope" />
  if (block === 'block' && n === '2') return <Skeleton id="analyse.interrogation.aggregate" />
  return <Skeleton id="analyse.interrogation" />
}
