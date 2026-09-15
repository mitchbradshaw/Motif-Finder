/* Analyse workspace entry — routes #/analyse/chain, #/analyse/block/<index>, #/analyse/glyphs, and dispatches
   #/analyse/interrogation/… and #/analyse/training/… to their own directories (other builders own those;
   keep these two lines when editing this file).
   Demo mode: `?template=<demo chain>` or `?state=…` opens the B24 detection chain (and the other frame chains) built from
   `demo.*` blocks; without them the chain and block pages run live against the bridge's adapters. */
import { lazy } from 'react'
import './analyse.css'
import './demo/demo.css'
import { useApp } from '../state'
import { Skeleton } from '../shell/Skeleton'
import { isDemoTemplate } from '../api/analyse'
import { BlockPage } from './BlockPage'
import { ChainPage } from './ChainPage'
import { DemoChainPage } from './demo/DemoChainPage'

const InterrogationPage = lazy(() => import('../interrogation').then(m => ({ default: m.InterrogationPage })))
const TrainingPage = lazy(() => import('../training').then(m => ({ default: m.TrainingPage })))

export function AnalysePage() {
  const { route } = useApp()
  if (route.page === 'interrogation') return <InterrogationPage />
  if (route.page === 'training') return <TrainingPage />
  if (route.page === 'glyphs') return <Skeleton id="analyse.glyphs" />
  const q = route.query
  const demoTemplate = isDemoTemplate(q.template) ? q.template : q.state === 'empty' ? 'untitled' : q.state ? 'drop_motifs9' : null
  if (route.page === 'block') {
    const idx = Number(route.params.id)
    return <BlockPage index={Number.isFinite(idx) ? idx : 0} />
  }
  if (demoTemplate) return <DemoChainPage key={demoTemplate} template={demoTemplate} />
  return <ChainPage />
}
