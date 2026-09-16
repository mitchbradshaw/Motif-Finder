/* Analyse › Training entry — owned by the Training builder. Routes: analyse/training[/block/<1..5>].
 * The block index is 1-based and equals the displayed stage number (01 Sliding windows = block/1).
 * P15: under the WindowSet source the stages renumber, so the same route index means a different block. */
import { useApp } from '../state'
import { ChainPage } from './ChainPage'
import { WindowsPage } from './WindowsPage'
import { MatrixPage } from './MatrixPage'
import { ClusterPage } from './ClusterPage'
import { EncodePage } from './EncodePage'
import { ModelPage } from './ModelPage'

export function TrainingPage() {
  const { route } = useApp()
  const [, block, n] = route.parts          // ['training', 'block', '3']
  if (block === 'block') {
    if (n === '1') return <WindowsPage />
    if (n === '2') return <MatrixPage />
    if (n === '3') return <ClusterPage />
    if (n === '4') return <EncodePage />
    if (n === '5') return <ModelPage />
  }
  return <ChainPage />
}
