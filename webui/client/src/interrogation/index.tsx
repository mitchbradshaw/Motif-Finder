/* Analyse › Interrogation entry — owned by the Interrogation builder. Routes: analyse/interrogation[/block/<n>].
 * The block index is 1-based and equals the displayed stage number (01 Resolve spans = block/1). */
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'
import { SourcePage } from './SourcePage'
import { SlopePage } from './SlopePage'
import { AggregatePage } from './AggregatePage'

export function InterrogationPage() {
  const { route } = useApp()
  const [, block, n] = route.parts          // ['interrogation', 'block', '1']
  if (block === 'block' && n === '1') return <SlopePage />
  if (block === 'block' && n === '2') return <AggregatePage />
  if (block === 'block') return <Skeleton id="analyse.interrogation" />
  return <SourcePage />
}
