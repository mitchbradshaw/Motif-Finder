/* Analyse › Training entry — owned by the Training builder. Routes: analyse/training[/block/<1..5>]. */
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'

const BLOCKS: Record<string, string> = { '1': 'analyse.training.windows', '2': 'analyse.training.matrix', '3': 'analyse.training.cluster', '4': 'analyse.training.encode', '5': 'analyse.training.model' }

export function TrainingPage() {
  const { route } = useApp()
  const [, block, n] = route.parts          // ['training', 'block', '3']
  return <Skeleton id={block === 'block' && BLOCKS[n] ? BLOCKS[n] : 'analyse.training'} />
}
