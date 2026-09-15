/* Analyse workspace entry — routes #/analyse/chain, #/analyse/block/<index>, #/analyse/glyphs, and dispatches
   #/analyse/interrogation/… and #/analyse/training/… to their own directories (other builders own those;
   keep these two lines when editing this file). */
import { lazy } from 'react'
import './analyse.css'
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'
import { BlockPage } from './BlockPage'
import { ChainPage } from './ChainPage'

const InterrogationPage = lazy(() => import('../interrogation').then(m => ({ default: m.InterrogationPage })))
const TrainingPage = lazy(() => import('../training').then(m => ({ default: m.TrainingPage })))

export function AnalysePage() {
  const { route } = useApp()
  if (route.page === 'interrogation') return <InterrogationPage />
  if (route.page === 'training') return <TrainingPage />
  if (route.page === 'glyphs') return <Skeleton id="analyse.glyphs" />
  if (route.page === 'block') {
    const idx = Number(route.params.id)
    return <BlockPage index={Number.isFinite(idx) ? idx : 0} />
  }
  return <ChainPage />
}
